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
import skynet_argument_flow as arguments
import skynet_diagnostic_path as diagnostic
import skynet_causal_query as causal

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
# Direction and the operator are separate slots; a pair of identifiers alone is insufficient.
REACH = r"(?:дотягива[а-я]+|достига[а-я]+|достиг[а-я]+|доход[а-я]+|дойти|добра[а-я]+|добира[а-я]+|попа[а-я]+)"
VIA = r"(?:косвенно|через (?:промежуточн[а-я]+|другие) функци[а-я]+)"
ASK = r"(?:(?:покажи|найди|перечисли|укажи) )?"
INCOMING = (r"(?:кто (?:напрямую )?(?:вызывает|обращается к)|какие функции (?:напрямую )?"
            r"(?:вызывают|обращаются к)|(?:где|откуда) (?:напрямую )?"
            r"(?:вызывают|вызывается|обращаются к)|(?:места|точки|список) (?:прямых )?вызов[а-я]+)")
ACTIVE = r"(?:формирует|возвращает|заполняет|созда[её]т)"
PARTICIPLE = r"(?:формирующ|возвращающ|заполняющ|создающ)(?:ая|ую|ей)"
OWNER = rf"(?:функци[а-я]+,? (?:которая {ACTIVE}|{PARTICIPLE})|производител[а-я]+)"
OWNER_QUERY = re.compile(rf"{ASK}{INCOMING} {OWNER} (?:пол[ея] |ключ[а]? )?({NAME})", re.I)
OUTGOING_OWNER = re.compile(r"(?:какие функции|кого|что) (?:напрямую )?вызывает (?:функция|производитель)\b", re.I)
REASONS = {
    "control_unsupported": "Существенный участок пути содержит неподдерживаемое управление. Полная локальная причина не установлена.",
    "control_unreachable": "В поддерживаемой структуре управления до указанной инструкции нет перехода.",
    "statement_ambiguous": "Укажите строку с одной инструкцией внутри выбранной функции.",
    "caller_conditions_unproven": "Для объяснения от этого входа нужны условия нескольких функций. Подтверждения локальной причины недостаточно.",
    "interpretation_unavailable": "Не удалось проверить смысл вопроса локальной моделью. Можно передать точный код диагностики или функцию@строку.",
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
    "ambiguous_producer": "У поля или имени его производителя несколько подходящих определений в разрешённой области.",
    "missing_producer": "В поддерживаемых возвратах пяти файлов производитель этого поля не найден.",
    "stale_snapshot": "Во время исследования изменился Git HEAD. Повторите вопрос для нового снимка.",
    "outgoing_unsupported": "Вы спросили, какие функции вызывает сам производитель. Этот режим проверяет только входящие обращения к нему.",
    "argument_unproven": "В проверенных прямых вызовах не удалось проследить передачу аргумента из указанной функции.",
    "unknown_parameter": "У целевой функции не найден указанный обычный именованный параметр.",
    "diagnostic_missing": "В доступных функциях не найден явный raise с таким текстом или кодом. Уточните сообщение.",
    "diagnostic_ambiguous": "Эта диагностика встречается в нескольких местах. От какой функции проследить один путь?",
    "diagnostic_context": "Место сообщения найдено, но его контекст не поддерживается статической проверкой.",
}


def endpoints(question):
    plain = " ".join(question.strip().rstrip("?.!").replace("\x60", "").split())
    for pattern in PATHS:
        match = re.fullmatch(pattern, plain, re.I)  # group values preserve identifier case
        if match:
            return match.groups()
    # Locate the destination by its preposition and account for every remaining word.
    # Among others this covers both verb-first and source-first reachability questions.
    names = list(re.finditer(rf"\b{NAME}\b", plain))
    if len(names) == 2:
        first, second = names
        before = plain[:first.start()].strip()
        between = plain[first.end():second.start()].strip()
        after = plain[second.end():].strip()
        frames = ((rf"{REACH}(?: ли)?(?: (?:из|от))?", rf"(?:{VIA} )?(?:до|к)"),
                  (r"(?:(?:можно ли|как) )?(?:из|от)", rf"(?:{VIA} )?{REACH}(?: {VIA})? (?:до|к)"),
                  ("", rf"(?:{VIA} )?{REACH}(?: ли)?(?: {VIA})? (?:до|к)"))
        if not after:
            for prefix, link in frames:
                if re.fullmatch(prefix, before, re.I) and re.fullmatch(link, between, re.I):
                    return first.group(), second.group()
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


def head_current(src):
    if src.reader._run("rev-parse", "--verify", "HEAD^{commit}").decode("ascii").strip() != src.commit:
        raise host.Rejected("stale_snapshot")


def site_anchors(site, obs, items):
    refs = [items[a["ref_id"]]["locator"] for a in obs["anchors"]]
    for path, lo, hi in ((site["path"], site["line"], site["end_line"]),
                         (site["path"], site["context_line"], site["context_line"]),
                         (site["definition_path"], site["definition_line"], site["definition_line"])):
        if not any(r["path"] == path and r["start"] <= lo <= hi <= r["end"] for r in refs):
            raise host.Rejected("endpoint_binding")


def producer_callers(req, src, field, lookup, trace, steps, deadline):
    cli = host.lab.cli

    def step(tool, target):
        if monotonic() >= deadline:
            raise host.Rejected("deadline")
        if len(trace) >= steps:
            return False
        head_current(src)
        trace.append(dict(tool=tool, target=target, status="started"))
        return True

    if not step("flow", field):
        return packet(req, src, reason="step_budget")
    # Use the producer projection of flow rather than tracing an unrelated downstream value.
    index = cli.flow.Slice(src)
    owners = index.producers.get(field, ())
    if len(owners) != 1:
        reason = "ambiguous_producer" if owners else "missing_producer"
        trace[-1]["status"] = reason
        return packet(req, src, reason=reason)
    fn, key, value = owners[0]
    name = fn.node.name
    definitions = cli.auto_reader.top_functions(index)
    if sum(node.name == name for _, node in definitions) != 1:
        trace[-1]["status"] = "ambiguous_producer"
        return packet(req, src, reason="ambiguous_producer")
    expected = (src.commit, fn.path, fn.node.lineno)
    refs = []
    for lo, hi in ((fn.node.lineno, fn.node.lineno), (key.lineno, value.end_lineno)):
        ref = cli.calls.cited(src, fn.path, lo, hi)
        if (ref["commit"], ref["path"], ref["start"], ref["end"]) != (src.commit, fn.path, lo, hi):
            raise host.Rejected("endpoint_binding")
        refs.append(ref)
    owner = dict(text=f"Функция {name} формирует поле {field} в возвращаемом словаре.", evidence_blocks=refs)
    evidence = host.pack_result(req, src, dict(status="flow", claims=[owner], text=""))
    observations = evidence["analysis"]["observations"]
    items = {item["ref_id"]: item for item in evidence["items"]}
    trace[-1]["status"] = "producer_verified"
    if not step("calls", name):
        return packet(req, src, reason="step_budget")
    try:
        result = lookup(name, src, cli.refusal)
    except Exception:
        raise host.Rejected("tool_error") from None
    calls = host.pack_result(req, src, result)
    trace[-1]["status"] = result["status"]
    if calls["analysis"]["reason"]:
        return packet(req, src, reason=calls["analysis"]["reason"])
    if result.get("commit") != src.commit or result["status"] != "call_sites":
        raise host.Rejected("endpoint_binding")
    items.update((i["ref_id"], i) for i in calls["items"])
    if len(items) > 96:
        return packet(req, src, reason="evidence_budget")
    for obs in calls["analysis"]["observations"]:
        site = obs["call_site"]
        if (site["commit"], site["definition_path"], site["definition_line"]) != expected:
            raise host.Rejected("endpoint_binding")
        site_anchors(site, obs, items)
        if site["kind"] == "module_entry":
            text = f"В блоке запуска модуля как программы возможен прямой вызов {name}."
        elif site["kind"] == "function" and any(
                (p, node.lineno, node.name) == (site["path"], site["context_line"], site["caller"])
                for p, node in definitions):
            text = f"В теле {site['caller']} есть прямой вызов {name}."
        else:
            raise host.Rejected("endpoint_binding")
        observations.append(dict(obs, text=text))
    return packet(req, src, observations, items.values())


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
            site_anchors(site, obs, items)
            chain = [dict(obs, text=f"В теле {caller} есть прямой вызов {target}.",
                          edge=[caller, target]), *suffix]
            if caller == start:
                used = dict.fromkeys(a["ref_id"] for row in chain for a in row["anchors"])
                return packet(req, src, chain, [items[k] for k in used])
            if caller not in visited:
                pending.append((caller, chain))
                visited.add(caller)
    return packet(req, src, reason="path_unproven")


def investigate(question, root, *, opener=read_head, lookup=None, steps=MAX_STEPS,
                diagnostic_planner=diagnostic.witness, why=False, classifier=causal.classify,
                proof_type=causal.control.Proof):
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
        if cli.auto_reader.EVENT.search(req.question):
            return packet(req, src, reason="observation_required")
        symptom = diagnostic.interpret(req.question)
        if why or (symptom and not symptom.origin) or (not symptom and causal.unbound_subject(req.question)):
            plan = "local_control"
            if paths:
                return packet(req, src, reason="clarification")
            try:
                if steps < 2:
                    return packet(req, src, reason="step_budget")
                subject = causal.select(req.question, symptom, trace, classifier)
                search = arguments.Search(req, src, lookup or cli.calls.lookup, trace,
                                          min(MAX_STEPS, steps), task.deadline, head_current, site_anchors)
                return packet(req, src, *causal.solve(search, subject, proof_type))
            except (causal.control.Gap, arguments.Limit) as exc:
                return packet(req, src, reason=str(exc))
        if symptom is not None:
            plan = "explain_diagnostic"
            if not symptom or paths:
                return packet(req, src, reason="clarification")
            search = arguments.Search(req, src, lookup or cli.calls.lookup, trace,
                                      min(MAX_STEPS, steps), task.deadline, head_current, site_anchors)
            return packet(req, src, *diagnostic.solve(search, symptom, diagnostic_planner))
        plain = " ".join(req.question.strip().rstrip("?.!").replace("\x60", "").split())
        goal = arguments.parse(plain)
        if goal:
            plan = "trace_argument"
            search = arguments.Search(req, src, lookup or cli.calls.lookup, trace,
                                      min(MAX_STEPS, steps), task.deadline, head_current, site_anchors)
            return packet(req, src, *search.solve(*goal))
        if arguments.QUALIFIED.search(plain) and re.search(r"аргумент|параметр|переда[её]тся",plain,re.I):
            return packet(req, src, reason="clarification")
        if OUTGOING_OWNER.match(plain):
            return packet(req, src, reason="outgoing_unsupported")
        owner = OWNER_QUERY.fullmatch(plain)
        if owner:
            plan = "callers_of_field_producer"
            return producer_callers(req, src, owner[1], lookup or cli.calls.lookup, trace,
                                    min(MAX_STEPS, steps), task.deadline)
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
        if plan in ("callers_of_field_producer", "trace_argument", "explain_diagnostic", "local_control"):
            head_current(src)
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
    if plan == "explain_diagnostic":
        public["state"] = "partial"
        public["coverage"] = "one_static_site"
        public["execution_observed"] = False
    elif plan == "local_control":
        public["coverage"] = "explicit_control_in_one_function"
        public["execution_observed"] = False
        public["control"] = evidence["analysis"]["observations"][0]["control"]
    by_id = {i["ref_id"]: i["locator"] for i in evidence["items"]}
    for claim, obs in zip(proposal["claims"], evidence["analysis"]["observations"], strict=True):
        public["claims"].append(dict(text=claim["text"], refs=[by_id[a["ref_id"]] for a in claim["anchors"]]))
        if "edge" in obs:
            public["claims"][-1]["edge"] = obs["edge"]
    return public


def supervised(question, *, timeout=TIME_LIMIT, why=False):
    if len(question) > 600:
        return dict(state="insufficient", reason="clarification", claims=[], steps=[])
    cmd = [sys.executable, "-I", "-S", "-B", str(Path(__file__).resolve()), "--why-worker" if why else "--worker"]
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
    parser.add_argument("--why", action="store_true", help="Проверить локальные условия по сообщению или функции@строке; свободная формулировка может потребовать локальную модель.")
    args = parser.parse_args()
    out = supervised(args.question, why=args.why)
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        if out.get("snapshot"):
            print("Git-снимок", out["snapshot"])
        if out["steps"]:
            print("Ход поиска:", " → ".join(f'{s["tool"]}({s["target"]})' for s in out["steps"]))
        if out["state"] not in ("answered", "partial"):
            print(REASONS.get(out["reason"], "Ответ удержан."), "(" + out["reason"] + ")")
        else:
            if out["plan"] == "explain_diagnostic":
                print("Подтверждены места вызовов и локальная ветвь. Объяснение причины от входа частичное.")
            for claim in out["claims"]:
                print(claim["text"])
                for ref in claim["refs"]:
                    print(" ", ref["url"])
            print("Область вывода — статические связи пяти файлов. Выполнение не наблюдалось.")
    return int(out["state"] == "failed")


if __name__ == "__main__":
    if not sys.stdout.isatty():
        sys.stdout.reconfigure(encoding="utf8")
    if sys.argv[1:] in (["--worker"], ["--why-worker"]):
        data = sys.stdin.buffer.read(2401)
        result = investigate(data.decode("utf8"), host.lab.cli.pilot.ROOT, why=sys.argv[1] == "--why-worker")
        print(json.dumps(result, ensure_ascii=True))
    else:
        sys.exit(main())
