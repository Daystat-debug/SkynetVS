"""Find one witnessed transfer from a source expression to a formal parameter."""
import ast
from collections import defaultdict, deque
from dataclasses import dataclass
import re
from time import monotonic

import skynet_core_explain as host

cli = host.lab.cli
NAME = r"[A-Za-z_][A-Za-z_0-9]*"
QUALIFIED = re.compile(rf"\b({NAME})\.({NAME})\b")
SOURCE = rf"(?:из|в) (?:функции )?(?P<origin>{NAME})"
DEST = rf"(?:в |до |для )(?:параметр(?:а)? |аргумент(?:а)? )?(?P<target>{NAME})\.(?P<formal>{NAME})"
QUESTIONS = (
    rf"(?:что|какое (?:значение|выражение)) {SOURCE} (?:доходит|попадает|переда[её]тся) {DEST}",
    rf"(?:проследи|покажи) (?:передачу|значение|аргумент) {SOURCE} {DEST}",
)


def parse(question):
    for pattern in QUESTIONS:
        match = re.fullmatch(pattern, question, re.I)
        if match:
            return match.group("origin","target","formal")
    return None


class Limit(Exception):
    """Insufficient evidence within the common search budget."""


@dataclass
class Site:
    caller: object
    callee: object
    call: ast.Call
    anchors: list


class Search:
    def __init__(self, req, src, lookup, trace, budget, deadline, current, check_site):
        self.req, self.src, self.lookup = req, src, lookup
        self.trace, self.budget, self.deadline = trace, budget, deadline
        self.current, self.check_site = current, check_site
        self.index = cli.flow.Slice(src)
        self.functions = defaultdict(list)
        for path, node in cli.auto_reader.top_functions(self.index):
            self.functions[node.name].append(cli.flow.Function(path,self.index.trees[path],node))
        self.cache = {}
        self.items = {}

    def unique(self, name):
        matches = self.functions.get(name, ())
        return matches[0] if len(matches) == 1 else None

    def check_budget(self):
        if monotonic() >= self.deadline:
            raise host.Rejected("deadline")
        if len(self.items) > 96:
            raise Limit("evidence_budget")

    def incoming(self, target):
        self.check_budget()
        if target in self.cache:
            return self.cache[target]
        if len(self.trace) >= self.budget:
            raise Limit("step_budget")
        self.current(self.src)
        self.trace.append(dict(tool="calls",target=target,status="started"))
        try:
            raw = self.lookup(target,self.src,cli.refusal)
        except Exception:
            raise host.Rejected("tool_error") from None
        evidence = host.pack_result(self.req,self.src,raw)
        self.trace[-1]["status"] = raw["status"]
        sites = []
        if not evidence["analysis"]["reason"]:
            if raw["status"] != "call_sites" or raw.get("commit") != self.src.commit:
                raise host.Rejected("endpoint_binding")
            self.items.update((i["ref_id"],i) for i in evidence["items"])
            self.check_budget()
            callee = self.unique(target)
            for obs in evidence["analysis"]["observations"]:
                s = obs["call_site"]
                if (s["commit"],s["definition_path"],s["definition_line"]) != (
                        self.src.commit,callee.path,callee.node.lineno):
                    raise host.Rejected("endpoint_binding")
                self.check_site(s,obs,self.items)
                if s["kind"] != "function":
                    continue
                caller = self.unique(s["caller"])
                if caller is None:
                    continue
                if (caller.path,caller.node.lineno) != (s["path"],s["context_line"]):
                    raise host.Rejected("endpoint_binding")
                coordinates = s["line"],s["column"],s["end_line"],s["end_column"]
                matches = [n for n in ast.walk(caller.node) if isinstance(n,ast.Call)
                           and (n.lineno,n.col_offset,n.end_lineno,n.end_col_offset) == coordinates]
                if len(matches) != 1 or not isinstance(matches[0].func,ast.Name):
                    raise host.Rejected("endpoint_binding")
                call = matches[0]
                bindings = cli.calls.resolved_names(caller.tree,caller.path,callee.path,callee.node,callee.tree)
                if call.func.id not in bindings:
                    raise host.Rejected("endpoint_binding")
                if caller.path != callee.path:
                    imp = bindings[call.func.id]
                    locs = [self.items[a["ref_id"]]["locator"] for a in obs["anchors"]]
                    if not any(r["path"] == caller.path and r["start"] <= imp.lineno <= imp.end_lineno <= r["end"]
                               for r in locs):
                        raise host.Rejected("endpoint_binding")
                sites.append(Site(caller,callee,call,obs["anchors"]))
        self.cache[target] = sites
        return sites

    def bind(self, site, parameter, origin):
        """Return the next required formal (or the origin) and the proved argument edge."""
        call = site.call
        if any(isinstance(a,ast.Starred) for a in call.args) or any(k.arg is None for k in call.keywords):
            return None
        try:
            bound = cli.calls.signature(site.callee.node).bind(*call.args,**{k.arg:k.value for k in call.keywords})
        except (TypeError,ValueError):
            return None
        expr = bound.arguments.get(parameter)
        if not isinstance(expr,ast.expr):
            return None  # Omitted defaults and variadics have no single supplied source expression.
        caller = site.caller
        rendered = ast.unparse(expr)
        anchors = list(site.anchors)
        text = f"В {caller.node.name} выражение «{rendered}» передаётся в {site.callee.node.name}.{parameter}."
        next_formal = None
        if caller.node.name != origin:
            formals = {a.arg:a for a in (*caller.node.args.posonlyargs,*caller.node.args.args,*caller.node.args.kwonlyargs)}
            while isinstance(expr,ast.Name):
                if expr.id in formals and cli.calls.bindings(caller.node,expr.id) == [formals[expr.id]]:
                    next_formal = expr.id
                    break
                assignment = cli.flow.assigned(caller,expr.id,expr)
                if assignment is None:
                    return None
                stmt, position = assignment
                if position is not None or not isinstance(stmt.value,ast.Name):
                    return None
                ref = cli.calls.cited(self.src,caller.path,stmt.lineno,stmt.end_lineno)
                item = host.checked_item(self.src,ref)
                self.items[item["ref_id"]] = item
                self.check_budget()
                anchors.append(dict(ref_id=item["ref_id"],lines=[stmt.lineno,stmt.end_lineno]))
                text += f" Привязка {expr.id} получена из {stmt.value.id}."
                expr = stmt.value
            if next_formal is None:
                return None
        return next_formal, dict(text=text, anchors=anchors)

    def witness(self, origin, target, formal):
        pending = deque([(target,formal,[])])
        seen = {(target,formal)}
        while pending:
            target,formal,suffix = pending.popleft()
            for site in self.incoming(target):
                transfer = self.bind(site,formal,origin)
                if transfer is None:
                    continue
                previous, claim = transfer
                chain = [claim,*suffix]
                if previous is None:
                    return chain
                state = site.caller.node.name,previous
                if state not in seen:
                    pending.append((*state,chain))
                    seen.add(state)
        return []

    def solve(self, origin, target, formal):
        if origin == target or not self.unique(origin) or not self.unique(target):
            return [],[], "clarification"
        params = self.unique(target).node.args
        if formal not in {a.arg for a in (*params.posonlyargs,*params.args,*params.kwonlyargs)}:
            return [],[], "unknown_parameter"
        try:
            chain = self.witness(origin,target,formal)
        except Limit as limit:
            return [],[],str(limit)
        if not chain:
            return [],[], "argument_unproven"
        used = dict.fromkeys(a["ref_id"] for claim in chain for a in claim["anchors"])
        return chain,[self.items[k] for k in used],None
