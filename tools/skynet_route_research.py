"""Search for one site-bound static explanation inside the existing five-file profile."""
import ast
from collections import deque
from dataclasses import dataclass
import re

import skynet_argument_flow as arguments
import skynet_causal_query as causal
import skynet_control_conditions as control
import skynet_diagnostic_path as diagnostic
import skynet_route_facts as facts

NAME = arguments.NAME
PAIR = re.compile(rf"({NAME})\s*(?:->|→)\s*({NAME}(?:@[1-9]\d{{0,5}})?)")
CAP = 48


class Message(str):
    """A quoted diagnostic can have the same spelling as a function."""


def goal(question, endpoints):
    plain = question.strip().rstrip("?.!").replace("`", "")
    match = PAIR.fullmatch(plain)
    if match:
        return match.groups()
    symptom = diagnostic.interpret(question)
    if symptom and symptom.origin:
        return symptom.origin, Message(symptom.message)
    if symptom is False:
        return None
    coord = causal.POSITION.search(plain)
    pair = endpoints(plain if coord is None else plain[:coord.start()] + coord[1] + plain[coord.end():])
    if pair and coord:
        return (pair[0], coord[0]) if pair[1] == coord[1] and plain.endswith(coord[0]) else None
    return pair


@dataclass
class Outcome:
    function: object
    statement: object
    fact: dict


class Research:
    def __init__(self, search, origin, target, policy="adaptive"):
        self.s = search
        self.origin, self.target, self.policy = origin, target, policy
        self.proofs, self.tests = {}, {}
        self.decisions = []
        self.examined = 0
        self.attempts = 0
        self.best_conflict = None
        self.gap = "path_unproven"
        self.result = "unproven"

    def step(self, tool, target):
        self.s.check_budget()
        if len(self.s.trace) >= self.s.budget:
            raise arguments.Limit("step_budget")
        self.s.current(self.s.src)
        record = dict(tool=tool, target=target, status="started")
        self.s.trace.append(record)
        return record

    def anchor(self, fn, lo, hi):
        src = self.s.src
        ref = arguments.cli.calls.cited(src, fn.path, lo, hi)
        if (ref["commit"], ref["path"], ref["start"], ref["end"]) != (src.commit, fn.path, lo, hi):
            raise arguments.host.Rejected("endpoint_binding")
        item = arguments.host.checked_item(src, ref)
        self.s.items[item["ref_id"]] = item
        self.s.check_budget()
        return dict(ref_id=item["ref_id"], lines=[lo, hi])

    def outcome(self, fn, stmt, text, spans):
        anchors = [self.anchor(fn, lo, hi) for lo, hi in dict.fromkeys([(fn.node.lineno,fn.node.lineno), *spans])]
        return Outcome(fn,stmt,dict(text=text,anchors=anchors))

    def locate(self):
        step = self.step("resolve_outcome", self.target)
        if not self.s.unique(self.origin):
            raise control.Gap("clarification")
        coord = causal.POSITION.fullmatch(self.target)
        if coord:
            fn, stmt = causal.locate(self.s, causal.Subject(position=(coord[1],int(coord[2]))))
            targets = [self.outcome(fn,stmt,f"Ориентир — инструкция в {fn.node.name} на строке {stmt.lineno}.",
                                    [(stmt.lineno,stmt.end_lineno)])]
        elif isinstance(self.target, Message) or diagnostic.CODE.fullmatch(self.target):
            hits = diagnostic.origins(self.s, diagnostic.Question(self.target,None))
            if not hits:
                raise control.Gap("diagnostic_missing")
            targets = [self.outcome(h.function,h.node,f"В {h.function.node.name} записано `{ast.unparse(h.node)}`.",
                                    [(h.node.lineno,h.node.end_lineno)]) for h in hits]
        else:
            defs = self.s.functions.get(self.target, [])
            fields = self.s.index.producers.get(self.target, [])
            if len(defs)>1 or (defs and fields):
                raise control.Gap("clarification")
            targets = [self.outcome(fn,None,f"Целевое определение — {fn.node.name}.",[]) for fn in defs]
            for fn, key, val in fields:
                for ret, _ in arguments.cli.flow.returns(fn,lexical=True):
                    if arguments.cli.flow.fields(fn,ret.value).get(self.target) == (key,val):
                        fact = f"В {fn.node.name} поле {self.target} получает выражение `{ast.unparse(val)}`."
                        targets.append(self.outcome(fn,ret,fact,[(key.lineno,val.end_lineno)]))
            if not targets:
                raise control.Gap("no_match")
        if len(targets)>CAP:
            raise control.Gap("evidence_budget")
        step.update(status="located", candidates=len(targets))
        return targets

    def proof(self, fn, stmt):
        if stmt is None:
            return None
        key = (fn.path, stmt)
        if key not in self.proofs:
            step = self.step("prove_conditions", f"{fn.node.name}@{stmt.lineno}")
            try:
                self.proofs[key] = control.claim(self.s,fn,stmt)
                step["status"] = "proved"
            except control.Gap as exc:
                self.proofs[key] = str(exc)
                step["status"] = str(exc)
        result = self.proofs[key]
        if isinstance(result,str):
            raise control.Gap(result)
        return result

    def conflicts(self, fn, proof, env):
        if not proof or not env:
            return False
        if fn.node not in self.tests:
            self.tests[fn.node] = {(n.test.lineno,ast.unparse(n.test)):n.test for n in ast.walk(fn.node)
                                   if isinstance(n,ast.If)}
        term = proof["control"]["condition"]
        return facts.verdict(term,fn,env,self.tests[fn.node]) is False

    def certify(self, outcome, route):
        self.attempts += 1
        claims, env, previous = [], {}, []
        verdict = "conditional_route"
        for i in range(len(route)+1):
            final = i == len(route)
            site = None if final else route[i]
            fn = outcome.function if final else site.caller
            stmt = outcome.statement if final else facts.call_statement(site)
            proof = self.proof(fn,stmt)
            if proof:
                claims.append(proof)
                if verdict == "conditional_route" and self.conflicts(fn,proof,env):
                    values = ", ".join(f"{k}={v!r}" for k,v in env.items())
                    claims.append(dict(text=f"При привязке {values} условие для {fn.node.name}@{stmt.lineno} "
                                       "ложно. Этот вариант перехода исключён.", anchors=previous+proof["anchors"]))
                    verdict = "excluded_route"
            if final:
                claims.append(outcome.fact)
                return verdict, claims
            bindings, env = facts.bind(site, env)
            actual = ", ".join(f"{name} ← `{expr}`" + (" (по умолчанию)" if default else "")
                               for name,expr,default in bindings) or "явных параметров нет"
            previous = site.anchors
            claims.append(dict(text=f"В {fn.node.name} на строке {site.call.lineno} записан прямой вызов "
                               f"{site.callee.node.name}. Аргументы: {actual}.", anchors=previous,
                               edge=[fn.node.name,site.callee.node.name]))

    def screen(self, outcome, route, site):
        # Is the suffix already incompatible with literal arguments from this
        # site, before we spend an incoming-call lookup finding its ancestors?
        stmt = facts.call_statement(route[0]) if route else outcome.statement
        proof = self.proof(site.callee, stmt)
        _, env = facts.bind(site,{})
        return self.conflicts(site.callee,proof,env)

    def search(self, targets):
        pending = deque((t,()) for t in targets)
        deferred = deque()
        while pending or deferred:
            self.s.check_budget()
            outcome, route = (pending or deferred).popleft()
            fn = route[0].caller if route else outcome.function
            if (self.s.unique(fn.node.name) != fn or not isinstance(fn.node, ast.FunctionDef)
                    or fn.node.decorator_list or not arguments.cli.calls.unique_binding(fn.tree,fn.node.name,fn.node)
                    or any(isinstance(n, (ast.Yield, ast.YieldFrom))
                    for stmt in fn.node.body for n in arguments.cli.flow.local_nodes(stmt))):
                self.gap = "clarification"
                continue
            if fn.node.name == self.origin:
                if not route and outcome.statement is None:
                    raise control.Gap("clarification")
                try:
                    verdict, claims = self.certify(outcome, route)
                    if verdict == "conditional_route":
                        return verdict, claims
                    if self.best_conflict is None:
                        self.best_conflict = claims
                    self.gap = "no_verified_alternative"
                except control.Gap as exc:
                    self.gap = str(exc)
                if self.policy == "first":
                    break
                continue
            sites = self.s.incoming(fn.node.name)
            direct, direct_conflicts = [], []
            for site in sites:
                if self.examined >= CAP:
                    raise arguments.Limit("research_frontier_limit")
                self.examined += 1
                if site.caller.node in {outcome.function.node, *(s.caller.node for s in route)}:
                    continue
                child = outcome,(site,*route)
                if self.policy == "eager" or (self.policy == "adaptive" and len(sites)>1):
                    try:
                        blocked = self.screen(outcome, route, site)
                    except control.Gap as exc:
                        self.gap = str(exc)
                        self.decisions.append([site.caller.node.name,site.call.lineno,self.gap])
                        continue
                    if blocked:
                        self.decisions.append([site.caller.node.name,site.call.lineno,"literal_conflict"])
                        if site.caller.node.name == self.origin:
                            direct_conflicts.append(child)
                        else:
                            deferred.append(child)
                        continue
                if site.caller.node.name == self.origin:
                    direct.append(child)
                else:
                    pending.append(child)
            pending.extendleft(reversed(direct + direct_conflicts))
        return None

    def solve(self):
        try:
            solution = self.search(self.locate())
        except (control.Gap,arguments.Limit) as exc:
            self.gap, solution = str(exc), None
        if solution:
            self.result, claims = solution
        elif self.best_conflict:
            self.result, claims = "excluded_route", self.best_conflict
        else:
            return [], [], self.gap
        refs = dict.fromkeys(a["ref_id"] for c in claims for a in c["anchors"])
        return claims, [self.s.items[k] for k in refs], None
