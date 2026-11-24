"""Single-observation research with a source-independent evidence contract."""
import ast

import skynet_observed_route as observed
import skynet_source_language as language

goals = observed.goals
Gap = observed.route.control.Gap
KINDS = ("site", "condition", "caller", "arguments", "caller_condition")
PROMPT = """Определи, какие доказательства запрашивает разработчик о конкретном месте в коде.
Это классификация вопроса без доступа к коду. Верни только JSON {"need":["..."]}.
Метки: site — местоположение; condition — условия достижения строки в самой функции;
caller — непосредственно вызывающая функция; arguments — фактические аргументы вызова;
caller_condition — условия в вызывающей функции для достижения вызова.
Выбирай все явно запрошенные аспекты. Вопрос о том, что должно быть верно для появления сообщения,
просит condition. Упоминание условия внутри описания искомой строки само по себе не запрос его объяснить.
Если пользователь предлагает альтернативы без выбора, не сформулировал задачу, просит факты о реальном
запуске, изменения, либо хотя бы одна часть запроса вне этих возможностей, верни {"need":[]}.
Метка ОБЪЕКТ обозначает дословный ориентир. Не отвечай на сам вопрос."""


def closure(labels):
    if not labels:
        return ()
    needs = {"site", *labels}
    if needs.intersection(("arguments","caller_condition")):
        needs.add("caller")
    return tuple(k for k in KINDS if k in needs)


def interpret(question, select):
    masked = goals.QUOTES.sub("ОБЪЕКТ",question)
    obj = goals.read_selection(select,PROMPT,masked)
    if type(obj) is not dict or set(obj)!={"need"}:
        raise Gap("invalid_requirements")
    labels = obj["need"]
    if type(labels) is not list or len(labels)>len(KINDS) or any(type(v) is not str or v not in KINDS for v in labels):
        raise Gap("invalid_requirements")
    return closure(labels)


def research(search, question, select, policy):
    ctl = observed.ObservedRoute(search,None,None)
    claims = {}
    needs = ()
    gaps = {}
    meta = {}
    try:
        step = ctl.step("interpret_requirements","question")
        if policy=="requirements":
            needs = interpret(question,select)
        elif policy=="all_evidence":
            needs = KINDS
        elif policy=="one_action":
            needs = closure({"when":["condition"],"via":["arguments","condition","caller_condition"],
                             "where":["site"]}.get(language.operation(question),[]))
        else:
            raise ValueError(policy)
        step.update(status="interpreted",need=list(needs))
        if not needs:
            raise Gap("clarification")
        locate = ctl.step("locate_observation","Git HEAD")
        catalog = goals.effects(search)
        quotes = goals.quoted(question)
        if quotes:
            if len(quotes)!=1:
                raise Gap("observation_ambiguous")
            hits = language.candidates("«"+quotes[0]+"»",catalog,"explore")
            if len(hits)!=1:
                raise Gap("observation_ambiguous")
            effect = hits[0]
        else:
            effect,_,_ = language.choose("Где "+question,catalog,"explore")
        fn,expr = effect.fn,effect.expr
        meta.update(owner=fn.node.name,line=expr.lineno,interpretation=effect.label)
        fact = ctl.outcome(fn,effect.stmt,f"В {fn.node.name} на строке {expr.lineno} записано выражение "
                           f"`{ast.unparse(expr)}`.",[(expr.lineno,expr.end_lineno)])
        claims["site"] = fact.fact
        locate.update(status="located",owner=fn.node.name,line=expr.lineno)
        site = None
        for need in needs[1:]:
            try:
                if need=="condition":
                    claims[need] = ctl.proof(fn,effect.stmt)
                elif need=="caller":
                    sites = search.incoming(fn.node.name)
                    if len(sites)!=1:
                        raise Gap("caller_choice" if sites else "path_unproven")
                    site = sites[0]
                    claims[need] = dict(text=f"В {site.caller.node.name} на строке {site.call.lineno} записан "
                            f"прямой вызов {fn.node.name}.",anchors=site.anchors,edge=[site.caller.node.name,fn.node.name])
                elif site is None:
                    raise Gap(gaps["caller"])
                elif need=="caller_condition":
                    claims[need] = ctl.proof(site.caller,ctl.call_statement(site))
                else:
                    step = ctl.step("bind_arguments",fn.node.name)
                    bindings,_ = observed.route.facts.bind(site,{})
                    detail = ", ".join(f"{name} ← `{value}`" + (" (по умолчанию)" if default else "")
                                       for name,value,default in bindings)
                    claims[need] = dict(text="Привязка аргументов: "+(detail or "явных параметров нет")+".",
                                        anchors=site.anchors)
                    step["status"]="bound"
            except (Gap,observed.route.arguments.Limit) as exc:
                if str(exc)=="evidence_budget":
                    raise
                gaps[need]=str(exc)
        search.check_budget()
    except (Gap,observed.route.arguments.Limit) as exc:
        return ([],[],str(exc)),dict(meta,required=list(needs),supported=[],missing=list(needs))
    # A receipt exists only after the corresponding source-bound tool produced a claim.
    receipts = [dict(c,kind=k) for k,c in claims.items()]
    missing = [k for k in needs if k not in claims]
    refs = dict.fromkeys(a["ref_id"] for c in receipts for a in c["anchors"])
    return (receipts,[search.items[k] for k in refs],None),dict(meta,required=list(needs),
             supported=list(claims),missing=missing,gaps=gaps)
