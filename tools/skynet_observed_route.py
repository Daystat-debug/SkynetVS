"""Normal evaluation on a direct expression spine and honest use of an unfinished route."""
import ast

import skynet_route_research as route
import skynet_observation_goal as goals
import skynet_source_language as language
import skynet_goal_facets as facets


def statement(site):
    try:
        return route.facts.call_statement(site)
    except route.control.Gap as error:
        if str(error) != "conditional_expression":
            raise
    parents = {n:parent for parent in ast.walk(site.caller.node) for n in ast.iter_child_nodes(parent)}
    node = site.call
    while node in parents:
        parent = parents[node]
        if isinstance(parent,ast.If) and node is parent.test:
            return parent
        if isinstance(parent,(ast.Assign,ast.AnnAssign,ast.Return,ast.Expr)) and node is parent.value:
            return parent
        # Every ordinary argument is evaluated if evaluation of the surrounding
        # call completes normally. No implication through lazy or short-circuit nodes.
        if isinstance(parent,ast.Call) and node in [*parent.args,*parent.keywords]:
            node = parent
        elif isinstance(parent,ast.keyword) and parent.arg and node is parent.value:
            node = parent
        else:
            break
    raise route.control.Gap("conditional_expression")


class ObservedRoute(route.Research):
    call_statement = staticmethod(statement)
    candidate_route = None

    def certify(self, outcome, sites):
        self.candidate_route = (outcome, sites)
        return super().certify(outcome, sites)

    def solve(self):
        claims, items, reason = super().solve()
        if reason != "step_budget" or not self.candidate_route:
            return claims, items, reason
        # Project already delivered observations. No extra proof or lookup after the limit.
        outcome, sites = self.candidate_route
        claims = [dict(text=f"В {site.caller.node.name}@{site.call.lineno} записан прямой вызов "
                       f"{site.callee.node.name}.", anchors=site.anchors,
                       edge=[site.caller.node.name,site.callee.node.name]) for site in sites]
        claims.append(outcome.fact)
        refs = dict.fromkeys(a["ref_id"] for c in claims for a in c["anchors"])
        self.result = "structural_only"
        return claims, [self.s.items[k] for k in refs], None


def observe(search, question, policy, select):
    controller = ObservedRoute(search,None,None)
    meta = dict(verdict="unproven")
    try:
        step = controller.step("index_observations","Git HEAD")
        catalog = goals.effects(search)
        step.update(status="indexed",count=len(catalog))
        pick = controller.step("select_goal","question")
        try:
            if policy in ("syntax", "captions", "explore", "facets", "pooled", "grounded", "english_pool"):
                parts = language.relation(question) if policy != "captions" else None
                try:
                    if parts:
                        pick.update(status="two_observations", target="connect")
                        return language.connect(controller, parts, catalog, policy)
                    effect,action,method = language.choose(question,catalog,policy)
                except goals.NeedChoice:
                    raise
                except route.control.Gap as first:
                    split_literal = str(first)=="observation_missing" and len(goals.quoted(question))==2
                    if policy not in ("facets","pooled","grounded","english_pool") or (str(first)!="observation_ambiguous" and not split_literal):
                        raise
                    hits, action = facets.ground(controller,question,catalog,select,policy)
                    if action in ("between","forward"):
                        return language.join(controller,*hits,directed=action=="forward")
                    if len(hits)!=1:
                        raise goals.NeedChoice(hits[:3])
                    effect,method = hits[0],"translated_"+policy
            else:
                effect,action,method = goals.choose(question,catalog,policy,select)
        except route.control.Gap as exc:
            pick["status"] = str(exc)
            raise
        pick.update(status=method,target=action)
        search.current(search.src)
        search.check_budget()
        fn,stmt,expr = effect.fn,effect.stmt,effect.expr
        meta.update(action=action,owner=fn.node.name,line=expr.lineno,interpretation=effect.label)
        fact = controller.outcome(fn,stmt,
            f"В {fn.node.name} на строке {expr.lineno} записано выражение `{ast.unparse(expr)}`.",
            [(expr.lineno,expr.end_lineno)])
        claims = [fact.fact]
        meta["verdict"] = "location"
        if action == "when":
            claims.append(controller.proof(fn,stmt))
            meta["verdict"] = "local_conditions"
        elif action == "via":
            sites = search.incoming(fn.node.name)
            if len(sites)!=1:
                raise route.control.Gap("caller_choice" if sites else "path_unproven")
            if not isinstance(sites[0].caller.node,ast.FunctionDef):
                raise route.control.Gap("control_unsupported")
            meta["verdict"],claims = controller.certify(fact,sites)
    except goals.NeedChoice as exc:
        options = []
        for effect in exc.options:
            fn,expr = effect.fn,effect.expr
            anchor = controller.anchor(fn,expr.lineno,expr.end_lineno)
            options.append(dict(coordinate=f"{fn.node.name}@{effect.stmt.lineno}",label=effect.label,
                                ref_id=anchor["ref_id"]))
        return ([],list(search.items.values()),str(exc)),dict(verdict="clarify",options=options)
    except (route.control.Gap,route.arguments.Limit) as exc:
        if meta["verdict"]!="location" or str(exc)=="evidence_budget":
            return ([],[],str(exc)),dict(verdict="unproven")
        meta.update(verdict="location_only",gap=str(exc))
    refs = dict.fromkeys(a["ref_id"] for c in claims for a in c["anchors"])
    return (claims,[search.items[k] for k in refs],None),meta
