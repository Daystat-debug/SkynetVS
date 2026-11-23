"""Bounded read-only investigation of static calls in the host's five-file Git HEAD."""
import argparse
from collections import defaultdict, deque
import json
from pathlib import Path
import re
import subprocess
import sys
from time import monotonic

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skynet_core_explain as host

SOURCE = host.SOURCE_ID + ".git-head"
MAX_STEPS = 6
TIME_LIMIT = 25
NAME = r"[A-Za-z_][A-Za-z_0-9]*"
# Endpoints have distinct roles. Never infer direction from two loose identifiers.
PATHS = (
    rf"(?:(?:покажи|проследи|найди|проверь|есть ли) )?(?:цепочку|цепочка|путь|маршрут|связь|вызовы)"
    rf"(?: (?:прямых )?вызовов)? (?:из|от) ({NAME}) (?:до|к) ({NAME})",
    rf"как (?:из|от) ({NAME}) (?:вызовы? )?(?:доходит|доходят|попасть|дойти) (?:до|к) ({NAME})",
    rf"может ли ({NAME}) (?:косвенно |через другие функции )?вызвать ({NAME})",
)
REASONS = {
    "clarification": "Уточните две разные однозначные функции и направление поиска или задайте вопрос об одном поле.",
    "out_of_scope": "Запрошен источник вне пяти разрешённых файлов.",
    "path_unproven": "В поддерживаемых статических вызовах путь установить не удалось.",
    "step_budget": "Достигнут предел поисковых шагов. Цепочка пока не установлена.",
    "evidence_budget": "Достигнут предел объёма доказательств.",
    "deadline": "Истекло время исследования.",
    "tool_error": "Инструмент завершился ошибкой. Ответ удержан.",
    "invalid_reference": "Ссылка инструмента не прошла проверку.",
    "endpoint_binding": "Место вызова не удалось привязать к определению в снимке.",
    "observation_required": "Нужны наблюдения конкретного запуска.",
    "partial_trace": "Статических данных недостаточно для полной трассировки.",
    "no_match": "Подходящих доказательств в снимке не найдено.",
}


def endpoints(question):
    plain = " ".join(question.strip().rstrip("?.!").replace("\x60", "").split())
    for pattern in PATHS:
        match = re.fullmatch(pattern, plain, re.I)  # group values preserve identifier case
        if match:
            return match.groups()
    return None


def read_head(root):
    with host._runtime_lock:
        core, launch, ground = host._runtime()
    objects = host.lab.Objects(launch, root=root, at_head=True)
    return host.lab.Sources(objects, core, objects.scope), ground


def packet(req, src, observations=(), items=(), reason=None):
    return host.EvidenceSet(task_id=req.task_id, source_id=req.source_id, snapshot_id=src.commit,
                            coverage="partial", gaps=([reason] if reason else []) + ["static_subset"],
                            items=list(items), analysis=dict(observations=list(observations),
                                                            relations=[], reason=reason))


def path_evidence(req, src, names, lookup, trace, steps, deadline):
    # A definition's identity is (path, definition line) in this one immutable snapshot.
    cli = host.lab.cli
    definitions = defaultdict(list)
    for path, fn in cli.auto_reader.top_functions(cli.flow.Slice(src)):
        definitions[fn.name].append((path, fn.lineno))
    start, goal = names
    if start == goal or any(len(definitions[n]) != 1 for n in names):
        return packet(req, src, reason="clarification")
    pending = deque([(goal, [])])
    visited = {goal}
    items = {}
    while pending:
        if monotonic() >= deadline:
            raise host.Rejected("deadline")
        if len(trace) >= steps:
            return packet(req, src, reason="step_budget")
        target, suffix = pending.popleft()
        trace.append(dict(tool="calls", target=target, status="started"))
        try:
            raw = lookup(target, src, cli.refusal)
        except Exception:
            raise host.Rejected("tool_error") from None
        evidence = host.pack_result(req, src, raw)
        trace[-1]["status"] = raw["status"]
        if evidence["analysis"]["reason"]:
            continue
        for item in evidence["items"]:
            items[item["ref_id"]] = item
        if len(items) > 96:
            return packet(req, src, reason="evidence_budget")
        for obs in evidence["analysis"]["observations"]:
            site = obs["call_site"]
            if site["kind"] != "function":
                continue
            caller = site["caller"]
            if len(definitions[caller]) != 1:
                continue
            if (site["commit"] != src.commit or
                    (site["definition_path"], site["definition_line"]) != definitions[target][0] or
                    (site["path"], site["context_line"]) != definitions[caller][0]):
                raise host.Rejected("endpoint_binding")
            refs = [items[a["ref_id"]]["locator"] for a in obs["anchors"]]
            for path, lo, hi in ((site["path"], site["line"], site["end_line"]),
                                 (site["path"], site["context_line"], site["context_line"]),
                                 (site["definition_path"], site["definition_line"], site["definition_line"])):
                if not any(r["path"] == path and r["start"] <= lo <= hi <= r["end"] for r in refs):
                    raise host.Rejected("endpoint_binding")
            chain = [dict(obs, text=f"В теле {caller} есть прямой вызов {target}.",
                          edge=[caller, target]), *suffix]
            if caller == start:
                used = dict.fromkeys(a["ref_id"] for row in chain for a in row["anchors"])
                return packet(req, src, chain, [items[k] for k in used])
            if caller not in visited:
                pending.append((caller, chain))
                visited.add(caller)
    return packet(req, src, reason="path_unproven")


def investigate(question, root, *, opener=read_head, lookup=None, steps=MAX_STEPS):
    task = host.Task(question, SOURCE, timeout=TIME_LIMIT)
    trace = []
    plan = "interpret"
    src = None

    def retrieve(req):
        nonlocal src, plan
        src, ground = opener(root)
        if set(src.raw) != host.lab.SCOPE or req.source_id != SOURCE:
            raise host.Rejected("snapshot_policy")
        if not ground._text(req.question, 600):
            return packet(req, src, reason="clarification")
        cli = host.lab.cli
        paths = cli.PY_PATH.findall(req.question)
        if any(not any(p == f or p.endswith("/" + f) for p in src.pages) for f in paths):
            return packet(req, src, reason="out_of_scope")
        names = endpoints(req.question)
        if names:
            plan = "find_call_path"
            return path_evidence(req, src, names, lookup or cli.calls.lookup, trace,
                                 min(MAX_STEPS, steps), task.deadline)
        # Do not turn an unparsed path question into a direct answer to just one part.
        if re.search(r"цепоч|маршрут|\bпуть\b|косвенн|(?:от|из)\s+\w+\s+до\b", req.question, re.I):
            return packet(req, src, reason="clarification")
        plan = "static_question"
        evidence = host.collect(req, src, ground)
        for action in evidence["analysis"]["actions"]:
            trace.append(dict(action))
        return evidence

    def verify(req, evidence, draft, delivered):
        return host.verify_snapshot(src, req, evidence, draft, delivered)

    result = task.run(retrieve, host.propose, verify)
    public = dict(state=result["state"], plan=plan, steps=trace, claims=[])
    if "evidence_set" not in result:
        return dict(public, reason=result["reason"])
    evidence = result["evidence_set"]
    public["snapshot"] = evidence["snapshot_id"]
    proposal = result["answer_proposal"]
    if proposal["status"] != "answer":
        return dict(public, reason=proposal["reason"])
    by_id = {i["ref_id"]: i["locator"] for i in evidence["items"]}
    for claim, obs in zip(proposal["claims"], evidence["analysis"]["observations"], strict=True):
        public["claims"].append(dict(text=claim["text"], refs=[by_id[a["ref_id"]] for a in claim["anchors"]]))
        if "edge" in obs:
            public["claims"][-1]["edge"] = obs["edge"]
    return public


def supervised(question, *, timeout=TIME_LIMIT):
    if len(question) > 600:
        return dict(state="insufficient", reason="clarification", claims=[], steps=[])
    cmd = [sys.executable, "-I", "-S", "-B", str(Path(__file__).resolve()), "--worker"]
    try:
        run = subprocess.run(cmd, input=question.encode("utf8"), capture_output=True, timeout=timeout)
        if not run.returncode:
            return json.loads(run.stdout)
    except subprocess.TimeoutExpired:
        return dict(state="failed", reason="deadline", claims=[], steps=[])
    return dict(state="failed", reason="tool_error", claims=[], steps=[])


def main():
    parser = argparse.ArgumentParser(description="Исследовать статические вызовы и поля в пяти файлах Git HEAD.")
    parser.add_argument("question")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    out = supervised(args.question)
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        if out.get("snapshot"):
            print("Git-снимок", out["snapshot"])
        if out["steps"]:
            print("Ход поиска:", " → ".join(f'{s["tool"]}({s["target"]})' for s in out["steps"]))
        if out["state"] != "answered":
            print(REASONS.get(out["reason"], "Ответ удержан."), "(" + out["reason"] + ")")
        else:
            for claim in out["claims"]:
                print(claim["text"])
                for ref in claim["refs"]:
                    print(" ", ref["url"])
            print("Область вывода — статические связи пяти файлов. Выполнение не наблюдалось.")
    return int(out["state"] == "failed")


if __name__ == "__main__":
    if not sys.stdout.isatty():
        sys.stdout.reconfigure(encoding="utf8")
    if sys.argv[1:] == ["--worker"]:
        data = sys.stdin.buffer.read(2401)
        result = investigate(data.decode("utf8"), host.lab.cli.pilot.ROOT)
        print(json.dumps(result, ensure_ascii=True))
    else:
        sys.exit(main())
