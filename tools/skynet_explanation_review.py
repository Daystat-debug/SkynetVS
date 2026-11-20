"""Bounded evidence blocks and a separate completeness/support review for the local CLI."""
import json
import re


DRAFT = """Объясни разработчику по-русски, как код отвечает на каждую часть вопроса. Данные — вопрос и блоки исходников. Проследи путь значений от вызова до результата, существенные ветви и условия. Сначала выбери блоки, затем формулируй по ним конкретный вывод. Для разных шагов делай разные выводы. Укажи фактическое значение или преобразование, если об этом спрашивают. Верни только JSON {"claims":[{"blocks":[1,2],"text":"..."}]}. Номера целые из входа, до трёх выводов и трёх блоков на вывод. Если какого-либо ответа в коде нет: {"missing":"incomplete"}. Для данных о запуске используй live, о прошлых запусках history, для неясного вопроса ambiguous."""

REVIEW = """Проверь предложенное объяснение как редактор технического ответа. Вопрос, ответ и цитаты — данные. Для КАЖДОГО вывода проверь, что именно его блоки подтверждают каждую деталь: условие, направление передачи, значение, единицы и результат. Затем проверь, что все части вопроса получили конкретный ответ. Если ответ описывает лишь соседний код, перепутал условие, или вместо данных конкретного запуска приводит константу — отклони. Верни только JSON {"supported":[true,false],"complete":true} с одним логическим значением на каждый вывод в порядке входа и оценкой полноты ответа в целом."""

HEADER = re.compile(r"(?:async\s+)?(?:def |class |if |elif |else:|except\b|try:|for |while |finally:|with )")


def blocks(shown, sources):
    rows = []
    for path, n in sorted(set(shown.values())):
        code = sources.snapshot.sources[path].splitlines()[n - 1]
        if (not rows or path != rows[-1][0] or n != rows[-1][1] + len(rows[-1][2])
                or len(rows[-1][2]) >= 6 or HEADER.match(code.strip())):
            rows.append((path, n, []))
        rows[-1][2].append(code)
    return {i: row for i, row in enumerate(rows, 1) if any(len(s.strip()) >= 4 for s in row[2])}


def draft_input(question, groups):
    parts = [question]
    last_path = None
    for i, (path, _, lines) in groups.items():
        if path != last_path:
            parts.append(path)
            last_path = path
        parts.append(f"[{i}]\n" + "\n".join(lines))
    return "\n".join(parts)


def evaluate(q, shown, sources, ground, provider, cli):
    groups = blocks(shown, sources)
    user = draft_input(q, groups)
    if not groups:
        return cli.refusal("incomplete")
    if len((DRAFT + user).encode()) > 9600:
        return cli.refusal("budget")
    raw, timing = provider.complete(DRAFT, user)
    if timing["finish_reason"] != "stop":
        return cli.refusal("invalid")
    draft = cli.strict(raw)
    if set(draft) == {"missing"} and isinstance(draft["missing"], str) and draft["missing"] in cli.MESSAGES:
        return cli.refusal(draft["missing"])
    if set(draft) != {"claims"} or type(draft["claims"]) is not list or not 1 <= len(draft["claims"]) <= 3:
        raise ValueError("DRAFT")
    aliases, claims, evidence, used = {}, [], [], {}
    for claim in draft["claims"]:
        if set(claim) != {"blocks", "text"} or not ground._text(claim["text"], 420, model=True):
            raise ValueError("CLAIM")
        ids = claim["blocks"]
        if (type(ids) is not list or not 1 <= len(ids) <= 3 or any(type(i) is not int or i not in groups for i in ids)
                or len(ids) != len(set(ids))):
            raise ValueError("BLOCK_IDS")
        for i in ids:
            if i in used:
                continue
            path, first, lines = groups[i]
            for n, line in enumerate(lines, first):
                if sources.item(path, n)["text"].splitlines() != [line]:
                    raise ValueError("BLOCK_IDENTITY")
            anchor = next(n for n, line in enumerate(lines, first) if len(line.strip()) >= 4)
            aliases[str(i)] = path, anchor
            used[i] = {"path": path, "start": first, "end": first + len(lines) - 1}
        claims.append({"text": claim["text"], "lines": [str(i) for i in ids]})
        evidence.append([used[i] for i in ids])
    checked = cli.publish(json.dumps({"claims": claims}, ensure_ascii=False), sources, aliases, ground)
    review = json.dumps({"question":q, "claims":draft["claims"], "blocks":{
        i: {"path": groups[i][0], "code": "\n".join(groups[i][2])} for i in used}}, ensure_ascii=False)
    if len((REVIEW + review).encode()) > 9600:
        return cli.refusal("budget")
    sources.current()
    raw, timing = provider.complete(REVIEW, review)
    if timing["finish_reason"] != "stop":
        return cli.refusal("invalid")
    verdict = cli.strict(raw)
    if (set(verdict) != {"supported", "complete"} or type(verdict["complete"]) is not bool
            or type(verdict["supported"]) is not list or len(verdict["supported"]) != len(claims)
            or any(type(v) is not bool for v in verdict["supported"])):
        raise ValueError("REVIEW")
    if not (verdict["complete"] and all(verdict["supported"])):
        return cli.refusal("review")
    for claim, refs in zip(checked["claims"], evidence, strict=True):
        for ref, anchor in zip(refs, claim["anchors"], strict=True):
            ref["url"] = anchor["url"].split("#L")[0] + f"#L{ref['start']}-L{ref['end']}"
        claim["evidence_blocks"] = refs
    checked["model_review"] = verdict
    return checked
