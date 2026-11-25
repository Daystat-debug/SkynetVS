"""Bounded read-only investigation of static calls in the host's five-file Git HEAD."""
import argparse
from collections import defaultdict, deque
from contextlib import ExitStack
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from time import monotonic

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skynet_core_explain as host
import skynet_argument_flow as arguments
import skynet_diagnostic_path as diagnostic
import skynet_causal_query as causal
import skynet_route_research as research
import skynet_observed_route as observed
import skynet_requirements as requirements
import skynet_task_parts as task_parts

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
    "observation_missing": "Уточните текст или другой признак. Подходящее место в разрешённых функциях не найдено.",
    "observation_ambiguous": "Уточните, какую строку или проверку нужно исследовать и что о ней требуется узнать.",
    "caller_choice": "Обнаружено несколько вызывающих участков. Уточните точку входа.",
    "conditional_expression": "Вычисление вызова внутри выражения зависит от неподдерживаемого контекста.",
    "research_frontier_limit": "Исчерпан предел рассмотренных вариантов.",
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
                proof_type=causal.control.Proof, research_mode=False, research_policy="adaptive",
                discovery=None, select=observed.goals.local_select):
    task = host.Task(question, SOURCE, timeout=TIME_LIMIT)
    trace = []
    plan = "interpret"
    strategy = discovery
    object_catalog = None
    products = None
    suggestions = None
    src = None

    def retrieve(req):
        nonlocal src, plan, strategy, object_catalog, suggestions, products
        src, ground = opener(root)
        if set(src.raw) != host.lab.SCOPE or req.source_id != SOURCE:
            raise host.Rejected("snapshot_policy")
        if not ground._text(req.question, 600):
            return packet(req, src, reason="clarification")
        cli = host.lab.cli
        paths = cli.PY_PATH.findall(req.question)
        if any(not any(p == f or p.endswith("/" + f) for p in src.pages) for f in paths):
            return packet(req, src, reason="out_of_scope")
        learned = discovery in task_parts.experience.POLICIES
        if learned or discovery in task_parts.objects.POLICIES or discovery in task_parts.experience.LEARNERS or discovery in ("parts","parts_once","lexical_parts","residual","flat_residual","independent","memory_only","shared_evidence"):
            plan="task_parts"
            if paths:
                return packet(req,src,reason="clarification")
            if learned:
                strategy = task_parts.experience.select(discovery,req.question)
            search=arguments.Search(req,src,lookup or cli.calls.lookup,trace,min(MAX_STEPS,steps),
                                    task.deadline,head_current,site_anchors)
            allocation=task_parts.objects.scope.allocation
            if strategy in allocation.POLICIES and lookup is None:
                products=search.products=allocation.Products(search,cli.calls)
                search.lookup=search.products.lookup
            if strategy in task_parts.objects.POLICIES:
                if len(task_parts.split(req.question))>8:
                    return packet(req,src,reason="part_budget")
                try:
                    object_catalog=requirements.goals.effects(search)
                    suggestions=task_parts.objects.nominations(task_parts.split(req.question),object_catalog,
                                                               src.commit,strategy,select)
                except requirements.Gap as exc:
                    return packet(req,src,reason=str(exc))
            output,meta=task_parts.research(search,req.question,select,strategy,object_catalog,suggestions)
            evidence=packet(req,src,*output)
            evidence["analysis"]["task_parts"]=meta
            return evidence
        if cli.auto_reader.EVENT.search(req.question):
            return packet(req, src, reason="observation_required")
        if discovery in ("requirements","one_action","all_evidence","eager_projection"):
            plan = "requirement_research"
            if paths or observed.goals.unsupported(req.question):
                return packet(req,src,reason="clarification")
            search = arguments.Search(req,src,lookup or cli.calls.lookup,trace,min(MAX_STEPS,steps),
                                      task.deadline,head_current,site_anchors)
            output,meta = requirements.research(search,req.question,select,discovery)
            evidence = packet(req,src,*output)
            evidence["analysis"]["requirements"] = meta
            return evidence
        symptom = diagnostic.interpret(req.question)
        pair = research.goal(req.question, endpoints) if discovery or research_mode else None
        if research_mode or (discovery and pair):
            plan = "research_route"
            if paths or not pair:
                return packet(req, src, reason="clarification")
            search = arguments.Search(req, src, lookup or cli.calls.lookup, trace,
                                      min(MAX_STEPS, steps), task.deadline, head_current, site_anchors)
            planner = observed.ObservedRoute if discovery else research.Research
            controller = planner(search, *pair, policy=research_policy)
            evidence = packet(req, src, *controller.solve())
            evidence["analysis"]["research"] = dict(verdict=controller.result, attempts=controller.attempts,
                examined=controller.examined, decisions=controller.decisions, policy=research_policy)
            return evidence
        if discovery and not why:
            plain = req.question.strip().rstrip("?.!")
            explicit = (arguments.parse(plain) or OWNER_QUERY.fullmatch(plain) or causal.POSITION.fullmatch(plain)
                        or diagnostic.CODE.fullmatch(plain))
            # Existing named calls, fields and parameter goals keep their original dispatch.
            identifiers = diagnostic.IDENT.findall(observed.goals.QUOTES.sub(" ",plain))
            named = any("_" in w and not diagnostic.CODE.fullmatch(w) for w in identifiers)
            literal_hint = observed.goals.quoted(plain)
            previous_goal = False
            if not literal_hint and (cli.auto_reader.ORIGIN.search(plain) or cli.auto_reader.CALLER.search(plain)):
                index = cli.flow.Slice(src)
                previous_goal = (cli.auto_reader.field_options(plain,index) or
                                 any(fn.node.name in identifiers for fn in index.functions))
            if not explicit and not named and not previous_goal and not (symptom and not literal_hint):
                plan = "discover_observation"
                if paths or re.search(r"\b(?:исправь|удали|запусти|замени|перепиши)\b",plain,re.I):
                    return packet(req,src,reason="clarification")
                search = arguments.Search(req,src,lookup or cli.calls.lookup,trace,min(MAX_STEPS,steps),
                                          task.deadline,head_current,site_anchors)
                output, meta = observed.observe(search,req.question,discovery,select)
                evidence = packet(req,src,*output)
                evidence["analysis"]["discovery"] = meta
                return evidence
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
        if plan in ("callers_of_field_producer", "trace_argument", "explain_diagnostic", "local_control", "research_route", "discover_observation","requirement_research","task_parts"):
            head_current(src)
        assessment = host.verify_snapshot(src, req, evidence, draft, delivered)
        if "task_parts" in evidence["analysis"]:
            meta=evidence["analysis"]["task_parts"]
            task_parts.verify(req.question,meta,evidence["analysis"]["observations"],discovery=="flat_residual",
                              checked=strategy in ("independent","memory_only"),shared=strategy=="shared_evidence",
                              learner=strategy if strategy in task_parts.experience.LEARNERS else None)
            if strategy in task_parts.objects.POLICIES:
                task_parts.objects.verify(task_parts.split(req.question),meta,evidence["analysis"]["observations"],
                                          evidence["items"],object_catalog,src.commit,strategy,suggestions)
                if strategy in task_parts.objects.OFFLINE_FRAMES:
                    interpreter=(task_parts.objects.scope if strategy in task_parts.objects.scope.POLICIES
                                 else task_parts.objects.relation)
                    extra=(suggestions,) if strategy in task_parts.objects.scope.allocation.identity.POLICIES else ()
                    interpreter.verify(task_parts.split(req.question),meta,
                        evidence["analysis"]["observations"],object_catalog,src.commit,strategy,*extra)
                if products and not products.consistent(meta,evidence["analysis"]["observations"],requirements.argument_claim):
                    raise host.Rejected("claim_binding")
            if draft["status"]=="answer":
                assessment["answer_completeness"]=("interpreted_requirements_met" if all(
                    p["status"]=="established" for p in meta["parts"]) else "partial")
        if plan=="requirement_research" and "requirements" in evidence["analysis"]:
            meta = evidence["analysis"]["requirements"]
            requirements.verify_receipts(meta,evidence["analysis"]["observations"])
            if draft["status"]=="answer":
                assessment["answer_completeness"] = "partial" if meta["missing"] else "interpreted_requirements_met"
        return assessment

    result = task.run(retrieve, host.propose, verify)
    public = dict(state=result["state"], plan=plan, steps=trace, claims=[])
    if "evidence_set" not in result:
        return dict(public, reason=result["reason"])
    evidence = result["evidence_set"]
    public["snapshot"] = evidence["snapshot_id"]
    if "task_parts" in evidence["analysis"]:
        public["parts"]=evidence["analysis"]["task_parts"]["parts"]
        if discovery in task_parts.experience.POLICIES:
            public["strategy"]=strategy
    if "requirements" in evidence["analysis"]:
        public["requirements"] = evidence["analysis"]["requirements"]
    if "research" in evidence["analysis"]:
        public["research"] = evidence["analysis"]["research"]
    if "discovery" in evidence["analysis"]:
        info = dict(evidence["analysis"]["discovery"])
        if "options" in info:
            by_id = {i["ref_id"]:i["locator"] for i in evidence["items"]}
            info["options"] = [dict(label=o["label"],coordinate=o["coordinate"],ref=by_id[o["ref_id"]])
                               for o in info["options"]]
        public["discovery"] = info
    proposal = result["answer_proposal"]
    if proposal["status"] != "answer":
        return dict(public, reason=proposal["reason"])
    if plan=="task_parts":
        public.update(coverage="static_subset",execution_observed=False)
        if any(p["status"]!="established" for p in public["parts"]):
            public["state"]="partial"
    if plan=="requirement_research":
        public.update(execution_observed=False,coverage="static_subset")
        if public["requirements"]["missing"]:
            public["state"]="partial"
    if plan == "research_route":
        public.update(coverage="one_static_route", execution_observed=False, joint_feasibility="not_proved")
        if public["research"]["verdict"] in ("excluded_route","structural_only"):
            public["state"] = "partial"
    elif plan == "discover_observation":
        public.update(coverage="one_static_site",execution_observed=False)
        if public["discovery"]["verdict"] in ("conditional_route","excluded_route","direct_edge"):
            public.update(coverage="one_static_route",joint_feasibility="not_proved")
        if public["discovery"]["verdict"] in ("excluded_route","location_only"):
            public["state"] = "partial"
    elif plan == "explain_diagnostic":
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
        if plan in ("requirement_research","task_parts"):
            public["claims"][-1]["kind"] = obs["kind"]
        if plan in ("research_route","discover_observation","requirement_research","task_parts") and "control" in obs:
            public["claims"][-1]["control"] = obs["control"]
    return public


def supervised(question, *, timeout=TIME_LIMIT, why=False, research_mode=False, discovery=False, explore=False, offline=False, requirements_mode=False, requirements_version="0.10"):
    if len(question) > 600:
        return dict(state="insufficient", reason="clarification", claims=[], steps=[])
    worker = ("--requirements-worker" if requirements_mode else "--offline-worker" if offline else "--explore-worker" if explore else "--research-worker" if research_mode else
              "--why-worker" if why else "--ask-worker" if discovery else "--worker")
    cmd = [sys.executable, "-I", "-S", "-B", str(Path(__file__).resolve()), worker]
    if requirements_mode:
        cmd.append(requirements_version)
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
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--requirements", action="store_true", help="Проверить требования по частям и показать, что осталось неизвестным.")
    parser.add_argument("--requirements-version",choices=("0.9","0.10","0.11","0.11-hybrid","0.12","0.13","0.13-offline","0.13-model","0.14","0.15","0.16","0.17","0.17-offline","0.17-rank"),help="0.17 сопоставляет описания объектов с конкурирующими гипотезами. По умолчанию 0.10.")
    modes.add_argument("--explore", action="store_true", help="Исследовать по признакам. Для сложного пересказа возможна локальная интерпретация.")
    modes.add_argument("--indexed", action="store_true", help="Только подготовленный индекс для поиска по наблюдаемым признакам.")
    modes.add_argument("--why", action="store_true", help="Проверить локальные условия по сообщению или функции@строке; свободная формулировка может потребовать локальную модель.")
    modes.add_argument("--research", action="store_true", help="Один статический маршрут от функции до функции, поля, сообщения или инструкции. Формат: вход -> ориентир.")
    args = parser.parse_args()
    if args.requirements_version and not args.requirements:
        parser.error("--requirements-version требует --requirements")
    out = supervised(args.question, why=args.why, research_mode=args.research, discovery=True, explore=args.explore, offline=args.indexed, requirements_mode=args.requirements, requirements_version=args.requirements_version or "0.10")
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        if out.get("snapshot"):
            print("Git-снимок", out["snapshot"])
        if out["steps"]:
            print("Ход поиска:", " → ".join(f'{s["tool"]}({s["target"]})' for s in out["steps"]))
        for part in out.get("parts",[]):
            status={"unknown":"Не установлено","partial":"Установлено частично","established":"Установлено"}
            cited=", ".join(str(i+1) for i in part.get("relation",{}).get("direct",part["claims"]))
            print(status[part["status"]], "—",part["text"].strip(),f"[{cited}]" if cited else "")
            binding=part.get("binding",{})
            if binding.get("object") and part["need"]:
                obj=binding["object"]
                print(f'  Цель поиска: {obj["path"]} · {obj["owner"]}, строка {obj["line"]}.')
                if binding["via"] in ("nomination","contrast"):
                    print("  Модель сопоставила описание с этим объектом. Ссылки подтверждают статические факты о нём.")
            if part.get("residual") and part["status"]!="established":
                print("  Осталось проверить:",part["residual"]["text"])
            for issue in part["issues"]:
                print(" ",REASONS.get(issue,{"runtime":"Нужны наблюдения запуска.","external":"Нужны внешние данные.",
                      "unsupported":"Для этой части нет статического инструмента.","ambiguous":"Нужно уточнение.",
                      "uninterpreted":"Требование не удалось распознать.",
                      "unverified_meaning":"Не подтверждено, что факты отвечают на эту просьбу.",
                      "semantic_candidate":"Соответствие описания выбранному выражению требует подтверждения.",
                      "part_budget":"Запрос содержит больше восьми частей."}.get(issue,issue)))
        if out["state"] not in ("answered", "partial"):
            print(REASONS.get(out["reason"], "Ответ удержан."), "(" + out["reason"] + ")")
            for opt in out.get("discovery",{}).get("options",[]):
                print(f'Возможный ориентир: {opt["label"]} — {opt["coordinate"]}',opt["ref"]["url"])
        else:
            if "requirements" in out:
                labels = dict(site="место", condition="условия в самой функции", caller="прямой вызов",
                              arguments="привязка аргументов", caller_condition="условия в вызывающей функции")
                info = out["requirements"]
                print("В вопросе распознаны:",", ".join(labels[k] for k in info["required"]))
                for k in info["missing"]:
                    reason = info["gaps"][k]
                    print("Не подтверждено:", labels[k], "—", REASONS.get(reason,reason))
                if "caller_condition" in info["supported"] and "condition" in info["supported"]:
                    print("Условия проверены отдельно в каждой функции. Совместная достижимость не установлена.")
            if out["plan"] == "research_route":
                if out["research"]["verdict"] == "excluded_route":
                    print("Для одного конкретного маршрута доказано противоречие. Другие пути остаются открытым вопросом.")
                elif out["research"]["verdict"] == "structural_only":
                    print("Найдены места прямых вызовов. Бюджет исчерпан до проверки всех условий и аргументов.")
                else:
                    print("Условия одного статического маршрута. Совместная выполнимость условий на реальных входах не установлена.")
            if out["plan"] == "explain_diagnostic":
                print("Подтверждены места вызовов и локальная ветвь. Объяснение причины от входа частичное.")
            if out["plan"] == "discover_observation":
                detail = out["discovery"]
                if args.explore or args.indexed:
                    meanings = dict(where="место в коде", when="локальные условия", via="входящий вызов",
                                    connect="прямой вызов между функциями")
                    print("Вопрос понят как запрос на", meanings[detail["action"]]+".",
                          "Ссылки подтверждают факты о выбранном участке.")
                print("Выбранный признак:",detail["interpretation"])
                if detail["verdict"]=="location_only":
                    print("Установлено только место записи.",REASONS.get(detail["gap"],detail["gap"]))
            for number,claim in enumerate(out["claims"],1):
                print((f"[{number}] " if "parts" in out else "")+claim["text"])
                for ref in claim["refs"]:
                    print(" ", ref["url"])
            print("Область вывода — статические связи пяти файлов. Выполнение не наблюдалось.")
    return int(out["state"] == "failed")


def task_interpreter(resources):
    provider=None
    def select(system,user):
        nonlocal provider
        if provider is None:
            import runtime289
            tmp=resources.enter_context(tempfile.TemporaryDirectory(prefix="skynet-parts-"))
            provider=resources.enter_context(runtime289.LocalProvider(Path(tmp)))
        return provider.complete(system,user)
    return select


if __name__ == "__main__":
    if not sys.stdout.isatty():
        sys.stdout.reconfigure(encoding="utf8")
    policies = {"0.9":"requirements","0.10":"residual","0.11":"memory_only","0.11-hybrid":"independent","0.12":"experience_release",
                "0.13":"object_assisted","0.13-offline":"object_offline","0.13-model":"object_graph","0.14":"relation_frame",
                "0.15":"scope_graph","0.16":"joint_plan","0.17":"identity_contrast",
                "0.17-offline":"identity_lexical","0.17-rank":"identity_rank"}
    versioned = len(sys.argv)==3 and sys.argv[1]=="--requirements-worker" and sys.argv[2] in policies
    if versioned or sys.argv[1:] in (["--worker"], ["--why-worker"], ["--research-worker"], ["--ask-worker"], ["--explore-worker"], ["--offline-worker"], ["--requirements-worker"]):
        data = sys.stdin.buffer.read(2401)
        version = sys.argv[2] if versioned else "0.10"
        with ExitStack() as resources:
            result = investigate(data.decode("utf8"), host.lab.cli.pilot.ROOT, why=sys.argv[1] == "--why-worker",
                                 research_mode=sys.argv[1] == "--research-worker",
                                 select=task_interpreter(resources) if sys.argv[1]=="--requirements-worker" and version!="0.9" else observed.goals.local_select,
                                 discovery={"--ask-worker":"checked","--explore-worker":"grounded","--offline-worker":"explore","--requirements-worker":policies[version]}.get(sys.argv[1]))
        print(json.dumps(result, ensure_ascii=True))
    else:
        sys.exit(main())
