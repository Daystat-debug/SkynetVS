"""Headless experimental host for the static Cognitive Core explain_code scenario."""
import argparse
import json
from pathlib import Path
import sys
from threading import Lock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skynet_scope_lab as lab
from skynet_core_task import AnswerProposal, EvidenceSet, Rejected, Task

SOURCE_ID = "skynetvs.retrieval"
WEB = "https://github.com/Daystat-debug/SkynetVS/blob/"


def open_profile(baseline):
    core, launch, ground = lab.trusted_tools()
    return lab.snapshot(core, launch, baseline=baseline), ground


def checked_item(src, locator):
    path, lo, hi = locator["path"], locator["start"], locator["end"]
    if path not in src.raw or type(lo) is not int or type(hi) is not int:
        raise Rejected("invalid_reference")
    try:
        span = src.span(path, lo, hi)
    except (ValueError, KeyError, IndexError):
        raise Rejected("invalid_reference") from None
    url = f"{WEB}{src.commit}/{path}#L{lo}-L{hi}"
    canonical = dict(span["ref"], url=url)
    if locator != canonical:
        raise Rejected("invalid_reference")
    return dict(ref_id=canonical["id"], text=span["text"], locator=canonical)


def collect(request, src, ground):
    # compose delegates single questions to auto; both dispatch calls and flow in-process.
    result = lab.ask("compose", request.question, src, ground)
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
                    relations=result.get("relations", []), message=result["text"],
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
        src, _ = self.session
        src.current()
        if ((request.task_id, SOURCE_ID, src.commit) !=
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
        if draft.get("status") == "answer":
            if set(draft) != {"status","claims"} or analysis["reason"] or not draft["claims"]:
                raise Rejected("invalid_proposal")
            for c in draft["claims"]:
                for a in c["anchors"]:
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

    def run(self, task):
        return task.run(self.retrieve, propose, self.verify)


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
    parser.add_argument("question")
    args = parser.parse_args()
    host = Host()
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
