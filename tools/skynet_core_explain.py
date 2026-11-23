"""Headless experimental host for the static Cognitive Core explain_code scenario."""
import argparse
from contextlib import ExitStack
from functools import cache
import json
from pathlib import Path
import sys
from threading import Lock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skynet_scope_lab as lab
from skynet_core_task import AnswerProposal, EvidenceSet, Rejected, Task

SOURCE_ID = "skynetvs.retrieval"
REVIEW_QUESTION = "Что я изменил относительно Git HEAD и какие связанные участки кода стоит проверить?"
_runtime_lock = Lock()


@cache
def _runtime():
    # The pinned module loader is single-use. Reuse only its verified tools across hosts.
    return lab.trusted_tools()


def open_profile(baseline):
    with _runtime_lock:
        core, launch, ground = _runtime()
    return lab.snapshot(core, launch, baseline=baseline), ground


def checked_item(src, locator):
    if not isinstance(locator, dict) or not {"path", "start", "end"} <= locator.keys():
        raise Rejected("invalid_reference")
    path, lo, hi = locator["path"], locator["start"], locator["end"]
    if not isinstance(path, str) or path not in src.raw or type(lo) is not int or type(hi) is not int:
        raise Rejected("invalid_reference")
    try:
        span = src.span(path, lo, hi)
    except (ValueError, KeyError, IndexError):
        raise Rejected("invalid_reference") from None
    canonical = lab.cli.calls.with_url(src, span["ref"], path, lo, hi)
    if locator != canonical:
        raise Rejected("invalid_reference")
    return dict(ref_id=canonical["id"], text=span["text"], locator=canonical)


def grounded_relations(relations, observations, items):
    """Bind the composer's exact-site joins to issued anchors, without resolving calls again."""
    grounded = []
    for edge in relations:
        site = edge["site"]
        matched = [o for o in observations if "call_site" in o and
                   all(o["call_site"].get(k) == v for k, v in site.items())]
        if len(matched) != 1:
            raise Rejected("unbound_relation")
        anchors = matched[0]["anchors"]
        supports = {}
        for role, path, start, end in (
                ("call",site["path"],site["line"],site["end_line"]),
                ("definition",site["definition_path"],site["definition_line"],site["definition_line"])):
            for a in anchors:
                loc = items[a["ref_id"]]["locator"]
                if (loc.get("snapshot_id", loc.get("commit")) == site.get("snapshot_id", site.get("commit"))
                        and loc["path"] == path
                        and loc["start"] <= start <= end <= loc["end"]):
                    supports[role] = a["ref_id"]
                    break
            else:
                raise Rejected("unbound_relation")
        grounded.append(dict(edge, basis="same_resolved_call_in_calls_and_flow", supports=supports))
    return grounded


def collect(request, src, ground):
    # compose delegates single questions to auto; both dispatch calls and flow in-process.
    result = lab.ask("compose", request.question, src, ground)
    return pack_result(request, src, result)


def pack_result(request, src, result):
    """Issue snapshot-bound evidence for one trusted static tool observation."""
    items = {}

    def issue(ref):
        item = checked_item(src, ref)
        if items.setdefault(item["ref_id"], item) != item:
            raise Rejected("conflicting_reference")
        return dict(ref_id=item["ref_id"], lines=[ref["start"], ref["end"]])

    observations = []
    for claim in result["claims"]:
        anchors = [issue(ref) for ref in claim["evidence_blocks"]]
        if not anchors:
            raise Rejected("unanchored_observation")
        observation = dict(text=claim["text"], anchors=anchors)
        if "call_site" in claim:
            observation["call_site"] = claim["call_site"]
        observations.append(observation)
    selection = [issue(ref) for ref in result.get("selection_evidence", [])]
    route = result.get("auto_route")
    actions = result.get("actions", [])
    if route in ("calls", "flow"):
        actions = [dict(tool=route, target=result["auto_target"], status=result["status"])]
    status = result["status"]
    reason = None
    if status in ("flow_limited", "composed_limited"):
        reason = "partial_trace"
    elif status == "withheld":
        reason = {"external":"out_of_scope", "live":"observation_required",
                  "ambiguous":"clarification", "incomplete":"no_match"}.get(result.get("reason"), "insufficient")
    elif status not in ("call_sites", "composed", "flow") or not observations:
        raise Rejected("unexpected_tool_result")

    analysis = dict(route=route, actions=actions, tool_status=status, reason=reason,
                    allowed_paths=sorted(src.raw), observations=observations, selection=selection,
                    relations=grounded_relations(result.get("relations", []), observations, items), message=result["text"],
                    call_coverage=result.get("call_coverage"), clarification=result.get("clarification"))
    # Only the supported static subset has been investigated, even when all files were opened.
    return EvidenceSet(task_id=request.task_id, source_id=request.source_id, snapshot_id=src.commit,
                       coverage="partial", gaps=([reason] if reason else []) + ["static_subset"],
                       items=list(items.values()), analysis=analysis)


def propose(request, evidence):
    analysis = evidence["analysis"]
    if analysis["reason"]:
        return AnswerProposal(status="insufficient", claims=[], reason=analysis["reason"])
    return AnswerProposal(status="answer", claims=[dict(text=o["text"], anchors=o["anchors"])
                          for o in analysis["observations"]])


class Host:
    """The deployment binds one logical source to one authorized profile; questions cannot switch it."""
    def __init__(self, *, baseline=False, opener=open_profile):
        self.baseline = baseline
        self.opener = opener
        self.session = None
        self.lock = Lock()

    def task(self, question, *, source_id=SOURCE_ID):
        return Task(question, source_id)

    def retrieve(self, request):
        if request.source_id != SOURCE_ID or request.kind != "explain_code":
            raise Rejected("unsupported_source")
        with self.lock:
            if self.session is None:
                self.session = self.opener(self.baseline)
            src, ground = self.session
        if src.commit != lab.SOURCE or set(src.raw) != (lab.BASE if self.baseline else lab.SCOPE):
            raise Rejected("snapshot_policy")
        return collect(request, src, ground)

    def verify(self, request, evidence, draft, delivered):
        if request.source_id != SOURCE_ID:
            raise Rejected("unsupported_source")
        src, _ = self.session
        return verify_snapshot(src, request, evidence, draft, delivered)

    def run(self, task):
        return task.run(self.retrieve, propose, self.verify)


def verify_snapshot(src, request, evidence, draft, delivered):
    src.current()
    if ((request.task_id, request.source_id, src.commit) !=
            (evidence["task_id"], evidence["source_id"], evidence["snapshot_id"])):
        raise Rejected("evidence_binding")
    by_id = {}
    for item in evidence["items"]:
        if checked_item(src, item["locator"]) != item or item["ref_id"] in by_id:
            raise Rejected("invalid_reference")
        by_id[item["ref_id"]] = item
    if list(by_id) != delivered:
        raise Rejected("delivery_mismatch")
    analysis = evidence["analysis"]
    if not isinstance(draft, dict) or not isinstance(draft.get("claims"), list):
        raise Rejected("invalid_proposal")
    if draft.get("status") == "answer":
        if set(draft) != {"status","claims"} or analysis["reason"] or not draft["claims"]:
            raise Rejected("invalid_proposal")
        for c in draft["claims"]:
            if (not isinstance(c, dict) or set(c) != {"text", "anchors"} or not isinstance(c["text"], str)
                    or not isinstance(c["anchors"], list) or not c["anchors"]):
                raise Rejected("invalid_proposal")
            for a in c["anchors"]:
                if (not isinstance(a, dict) or set(a) != {"ref_id", "lines"}
                        or not isinstance(a["ref_id"], str) or not isinstance(a["lines"], list)
                        or len(a["lines"]) != 2 or any(type(n) is not int for n in a["lines"])):
                    raise Rejected("invalid_anchor")
                item = by_id.get(a["ref_id"])
                if item is None or a["lines"] != [item["locator"]["start"], item["locator"]["end"]]:
                    raise Rejected("invalid_anchor")
        # This provider can publish only the trusted static tool's complete claim/anchor pairs.
        # Even a genuine excerpt from the same task cannot be substituted for another claim.
        expected = [{"text":o["text"], "anchors":o["anchors"]} for o in analysis["observations"]]
        if draft["claims"] != expected:
            raise Rejected("claim_binding")
    elif (not analysis["reason"] or
          draft != {"status":"insufficient", "claims":[], "reason":analysis["reason"]}):
        raise Rejected("invalid_proposal")
    return dict(references="checked" if by_id else "none", static_relations=len(analysis["relations"]),
                answer_completeness="partial" if analysis["reason"] == "partial_trace" else "not_assessed",
                semantic_review="not_independently_reviewed", execution_observed=False)


class WorkspaceHost:
    """One fresh capture per task. The caller configures the root, never the question or provider."""
    def __init__(self, mode, root):
        if mode not in ("working-tree", "git-head"):
            raise ValueError("Unknown workspace profile")
        self.mode = mode
        self.root = Path(root)
        self.source_id = SOURCE_ID + "." + mode

    def task(self, question):
        return Task(question, self.source_id)

    def run(self, task, provider=propose):
        src = None
        with ExitStack() as until_decision:
            def retrieve(req):
                nonlocal src
                if req.source_id != self.source_id or req.kind != "explain_code":
                    raise Rejected("unsupported_source")
                with _runtime_lock:
                    core, launch, ground = _runtime()
                if self.mode == "working-tree":
                    from skynet_working_tree import WorkingSources
                    src = WorkingSources(self.root)
                else:
                    reader = lab.Objects(launch, root=self.root, at_head=True)
                    src = lab.Sources(reader, core, reader.scope)
                evidence = collect(req, src, ground)
                if self.mode == "working-tree":
                    evidence["analysis"]["file_hashes"] = dict(src.hashes)
                return evidence

            def verify(req, evidence, draft, delivered):
                if self.mode == "working-tree":
                    until_decision.enter_context(src.publication_guard())
                return verify_snapshot(src, req, evidence, draft, delivered)

            return task.run(retrieve, provider, verify)


def display(result):
    print("Состояние:", result["state"])
    if "evidence_set" not in result:
        print("Причина:", result["reason"])
        return
    evidence, draft = result["evidence_set"], result["answer_proposal"]
    analysis = evidence["analysis"]
    print("Снимок:", evidence["snapshot_id"], "· файлов в области:", len(analysis["allowed_paths"]))
    print(analysis["message"])
    if draft["status"] == "insufficient":
        if draft["reason"] == "partial_trace":
            print("Трассировка оборвалась. Оснований для полного ответа недостаточно.")
        print("Причина:", draft["reason"])
        return
    items = {item["ref_id"]:item["locator"] for item in evidence["items"]}
    for claim in draft["claims"]:
        print(claim["text"])
        for anchor in claim["anchors"]:
            print(" ", items[anchor["ref_id"]]["url"])
    print("Ссылки сверены со снимком. Выводы статические. Полнота отдельно не оценивалась.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Вывести решение хоста и контракты задачи.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--working-tree", dest="mode", action="store_const", const="working-tree",
                      help="Исследовать пять сохранённых файлов рабочего проекта.")
    mode.add_argument("--git-head", dest="mode", action="store_const", const="git-head",
                      help="Исследовать те же пять файлов из Git HEAD на начало задачи.")
    mode.add_argument("--changes", dest="mode", action="store_const", const="changes",
                      help="Сравнить сохранённый код с HEAD и показать связанные места и проверки.")
    parser.add_argument("question", nargs="?")
    args = parser.parse_args()
    is_review_question = (args.question or "").strip().rstrip("?").casefold() == REVIEW_QUESTION.rstrip("?").casefold()
    if args.mode == "changes" or (not args.mode and is_review_question):
        from skynet_change_review import review, display as display_changes
        if args.question and not is_review_question:
            parser.error("--changes выполняет фиксированный обзор пяти файлов. Запустите без дополнительного вопроса.")
        try:
            report = review(lab.cli.pilot.ROOT)
            if args.json:
                print(json.dumps(report, ensure_ascii=False, indent=2))
            else:
                display_changes(report)
        except (ValueError, RuntimeError, OSError, SyntaxError) as exc:
            reason = str(exc) if isinstance(exc, Rejected) else "review_unavailable"
            print(json.dumps(dict(state="failed",reason=reason)) if args.json else f"Обзор удержан: {reason}")
            return 1
        return 0
    if not args.question:
        parser.error("Укажите вопрос или --changes.")
    host = WorkspaceHost(args.mode, lab.cli.pilot.ROOT) if args.mode else Host()
    task = host.task(args.question)
    try:
        result = host.run(task)
    except KeyboardInterrupt:
        task.cancel(task.request.task_id)
        result = task.result
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        display(result)
    return int(result["state"] in ("failed", "cancelled"))


if __name__ == "__main__":
    if not sys.stdout.isatty():
        sys.stdout.reconfigure(encoding="utf8")
    sys.exit(main())
