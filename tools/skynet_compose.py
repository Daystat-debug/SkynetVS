"""Compose bounded static reads; join only identical, resolved AST call expressions."""
import re

import skynet_auto as auto
import skynet_call_sites as calls
import skynet_data_flow as flow


QUOTES = re.compile(r'«[^»]*»|"[^"]*"|`[^`]*`')
SEPARATOR = re.compile(r"[,;?!.]+|\s+(?:а также|затем|и|а)\s+", re.I)
DESTINATION = re.compile(
    r"(?:куда|во что|в какую переменную|в какие переменные)\s+(?:\w+\s+){0,3}"
    r"(?:результат|ответ|значение)(?:\s+(?:вызова|функции))?"
    r"|что (?:потом |дальше )?делают с (?:возвращ[её]нным )?(?:значением|результатом)"
    r"|какие (?:аргументы|параметры|значения) (?:им |ей |туда )?(?:переда\w+|доста\w+)"
    r"|с какими (?:аргументами|параметрами)", re.I)
RELATION = re.compile(r"(?:это|данное|такое) значение (?:пришло|получено|бер[её]тся) из "
                      r"(?:того|этого)(?: самого)? вызова", re.I)


def clauses(q):
    mask = QUOTES.sub(lambda m:"_"*len(m[0]), q)
    parts = []
    start = 0
    for match in SEPARATOR.finditer(mask):
        part = q[start:match.start()].strip()
        if part:
            parts.append(part)
        start = match.end()
    if q[start:].strip():
        parts.append(q[start:].strip())
    combined = []
    for part in parts:
        # A conjunction inside a list of source identifiers is not a new request.
        if combined and auto.IDENT.fullmatch(part):
            combined[-1] += " и " + part
        else:
            combined.append(part)
    return combined


def unique_refs(refs):
    return list({r["url"]:r for r in refs}.values())


def compose(steps, src, refuse, relation_requested):
    src.current()
    answers, sites, origins, selection = {}, {}, {}, []
    for kind,name,locations in steps:
        for path,a,b in locations:
            selection.append(calls.cited(src,path,a,b))
        if kind == "calls":
            sites[name] = {}
            result = calls.lookup(name,src,refuse,evidence=sites[name])
        else:
            origins[name] = {}
            result = flow.Slice(src,evidence=origins[name]).answer(name,refuse)
        answers[kind,name] = result
        src.current()

    relations, notes = [], []
    redundant = {field:set() for field in origins}
    for callee,found in sites.items():
        for field,trace in origins.items():
            shared = sorted(found.keys() & trace.keys())
            if not shared:
                notes.append(f"Связь конкретного места вызова `{callee}` с дальнейшей передачей "
                             f"поля `{field}` по этой трассе не установлена.")
            for site in shared:
                # Only the claim about this particular caller receives the join.
                claim = answers["calls",callee]["claims"][found[site]]
                claim["text"] += f" На прослеженном пути результат этого вызова участвует в формировании поля `{field}`."
                field_claim = answers["flow",field]["claims"][0]
                claim["evidence_blocks"] = unique_refs(claim["evidence_blocks"] + field_claim["evidence_blocks"])
                redundant[field].update(trace[site])
                relations.append(dict(function=callee,field=field,site=site.record(src)))
            if shared:
                for site in found.keys() - trace.keys():
                    claim = answers["calls",callee]["claims"][found[site]]
                    claim["text"] += f" Для этого места связь с полем `{field}` не установлена."
    claims = []
    for (kind,name),part in answers.items():
        if not part["claims"]:
            notes.append(part["text"])
            continue
        if kind == "calls":
            claims.extend(part["claims"])
        else:
            # Keep the trace in order; attach citations to small paragraphs instead
            # of interrupting each operation with a repeated URL.
            remaining = [c for i,c in enumerate(part["claims"]) if i not in redundant[name]]
            for i in range(0,len(remaining),3):
                group = remaining[i:i+3]
                claims.append({"text":" ".join(c["text"] for c in group), "anchors":[],
                               "evidence_blocks":unique_refs([r for c in group for r in c["evidence_blocks"]])})
    complete = all(r["status"] in {"flow","call_sites"} for r in answers.values())
    if relation_requested and not relations:
        complete = False
    result = {"status":"composed" if complete else "composed_limited", "auto_route":"compose",
            "completion_scope":"requested_static_steps",
            "text":"\n".join([getattr(src, "heading", "По разрешённому Git-снимку:"),*notes]), "claims":claims,
            "actions":[{"tool":k,"target":n,"status":r["status"]} for (k,n),r in answers.items()],
            "relations":relations, "commit":src.commit, "selection_evidence":unique_refs(selection)}
    if sites:
        result["call_coverage"] = calls.coverage(src.pages)
    return result


def decide(parts,index,refuse,overrides):
    steps, unresolved, check_relation = [], [], False
    for i,part in enumerate(parts):
        if steps and steps[-1][0] == "calls" and DESTINATION.fullmatch(part):
            continue
        if RELATION.fullmatch(part):
            check_relation = True
            continue
        if i in overrides:
            decision = overrides[i]
        else:
            decision = auto.routes(part,index,None,refuse)
        if isinstance(decision,dict):
            unresolved.append((i,decision))
        elif not any(s[:2] == decision[:2] for s in steps):
            steps.append(decision)
    if unresolved:
        i,result = unresolved[0]
        prompt = result.get("clarification")
        if prompt and prompt["intent"] and len(parts) > 1:
            updated = dict(prompt,parts=parts,slot=i,overrides=overrides)
            return dict(result,text=f"Уточнение к части «{parts[i]}». "+result["text"],clarification=updated)
        return result
    if not steps or (check_relation and {k for k,_,_ in steps} != {"calls","flow"}):
        return auto.base_clarification(refuse,"Укажите вызов функции и поле, для которых нужно проверить связь.")
    return steps


def answer(q,src,refuse,previous=None):
    plain = QUOTES.sub(" ",q).lower().replace("ё","е")
    if auto.EVENT.search(plain):
        return dict(refuse("live"),auto_route="observation")
    if auto.OTHER.search(plain) or ".py" in plain:
        return auto.base_clarification(refuse,"Для этой задачи доступны прямые вызовы и происхождение полей разрешённого снимка. Уточните требуемый статический разбор.")
    index = flow.Slice(src)
    overrides = {}
    if previous and "parts" in previous and not re.search(r"[?;!]|\b(?:кто|как|где|откуда|покажи)\b",plain):
        reply = auto.routes(q,index,previous,refuse)
        if isinstance(reply,dict):
            return dict(reply,clarification=previous)
        parts = previous["parts"]
        overrides = {**previous["overrides"],previous["slot"]:reply}
    else:
        parts = clauses(q)
        if len(parts) <= 1:
            return auto.answer(q,src,refuse,previous if previous and "parts" not in previous else None)
    if len(parts) > 8:
        return auto.base_clarification(refuse,"Разделите вопрос на две реплики: поддерживается до восьми коротких частей.")
    steps = decide(parts,index,refuse,overrides)
    if isinstance(steps,dict):
        return steps
    return compose(steps,src,refuse,any(RELATION.fullmatch(p) for p in parts))
