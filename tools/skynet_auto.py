"""Dispatch supported Russian questions to one static reader. No provider or file I/O."""
import ast
import re

import skynet_call_sites as calls
import skynet_data_flow as flow


IDENT = re.compile(r"\b[A-Za-z_]\w*\b")
QUOTED = re.compile(r'«([^»]+)»|"([^"]+)"|“([^”]+)”')
CALLER = re.compile(
    r"\b(?:кто|откуда|где|кто именно|каки\w* функци\w*|из как\w+ (?:мест|функци|модул)\w*)\s+"
    r"(?:\w+\s+){0,3}(?:вызыва\w*|вызвал\w*|обраща\w*|переда[еёю]т\w*)\b"
    r"|\b(?:мест[ао]?|точк\w*|список|цепочк\w*)\s+(?:прям\w*\s+)?вызов\w*"
    r"|\b(?:аргумент\w*|параметр\w*)\s+(?:\w+\s+){0,2}переда\w*\s+(?:в|при)\b")
ORIGIN = re.compile(
    r"\b(?:откуда|источник\w*|происхожд\w*|происход\w*|бер[её]тся|берутся|"
    r"заполня\w*|формиру\w*|вычисля\w*|прослед\w*|попада\w*|содерж\w*|"
    r"записыва\w*|хран\w*|лежит|доходит|значение поля)\b")
EVENT = re.compile(
    r"\b(?:сейчас|вчера\w*|сегодня|только что|в реальном времени|на мо[её]м (?:пк|компьютере)|"
    r"сколько раз|(?:последн|прошл|текущ)\w*\s+(?:запуск|сеанс|прогон)\w*)\b")
OTHER = re.compile(
    r"\b(?:почему|зачем|исправ\w*|оптимиз\w*|перепиш\w*|измени\w*|замени\w*|"
    r"удали\w*|добавь|придум\w*|ускор\w*|стоимост\w*|сложност\w*|медлен\w*)\b"
    r"|\b(?:вызыва\w*|вызвал\w*)\s+(?:ошибк|исключени|сбой)\w*"
    r"|\b(?:кого|что|какие функции)\s+вызывает\s+[a-z_]")  # outgoing calls


def literals(q):
    return [next(s for s in match if s) for match in QUOTED.findall(q)]


def base_clarification(refuse, text, pending=None, options=()):
    if options:
        text += "\n" + "\n".join(f"{i}. {label}" for i, (_, _, label) in enumerate(options, 1))
    return dict(refuse("ambiguous"), text=text, auto_route="clarify",
                clarification={"intent":pending, "options":list(options)})


def labels(index):
    return {key: readers[0][1] for key,readers in index.users.items()
            if key in index.producers and readers}


def field_options(q, index):
    names = set(IDENT.findall(q))
    words = set(flow.stems(q))
    found = set(names & index.producers.keys())
    for key, readers in index.users.items():
        if key not in index.producers:
            continue
        for _,label,_ in readers:
            stems = flow.stems(label)
            if stems and stems[0] in words:
                found.add(key)
    return sorted(found)


def top_functions(index):
    return [(path,fn) for path,tree in index.trees.items() for fn in tree.body
            if isinstance(fn,(ast.FunctionDef,ast.AsyncFunctionDef))]


def string_sites(fn, needle):
    nodes = list(fn.body)
    while nodes:
        n = nodes.pop()
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.Lambda,ast.ClassDef)):
            continue
        if isinstance(n,ast.Constant) and type(n.value) is str and needle in n.value:
            yield n
        nodes.extend(ast.iter_child_nodes(n))


def function_options(q, functions):
    """Resolve exact names, listed signature arguments, or an attributed source literal."""
    words = set(IDENT.findall(QUOTED.sub(" ",q)))
    names = words & {fn.name for _,fn in functions}
    params = words - names
    signature_hint = bool(re.search(r"параметр|аргумент",q,re.I) and params)
    quotes = literals(q)
    if (not names and not signature_hint and not quotes) or (params and not signature_hint):
        return []
    matches = []
    for path, fn in functions:
        if names and fn.name not in names:
            continue
        refs = []
        if signature_hint:
            if not params <= calls.signature(fn).parameters.keys():
                continue
            refs.append((path,fn.lineno,max(fn.lineno,fn.body[0].lineno-1)))
        for quote in quotes:
            n = next(string_sites(fn,quote),None)
            if n is None:
                break
            refs.append((path,n.lineno,n.end_lineno))
        else:
            matches.append((fn.name,refs))
    return matches


def routes(q, index, previous, refuse):
    plain = QUOTED.sub(" ",q).lower().replace("ё","е")
    ask = lambda msg, intent=None, opts=(): base_clarification(refuse,msg,intent,opts)
    if EVENT.search(plain):
        return dict(refuse("live"),auto_route="observation")
    if OTHER.search(plain) or ".py" in plain:
        return ask("Я могу проследить происхождение поля отчёта или найти прямые места вызова функции в доступном снимке. Какую операцию проверить?")
    call = bool(CALLER.search(plain))
    origin = bool(ORIGIN.search(re.sub(r"откуда\s+вызыва\w*","",plain)))
    if previous and not (call or origin):
        options = previous["options"]
        if q.isascii() and q.isdigit() and len(q) <= 3 and 1 <= int(q) <= len(options):
            kind,name,_ = options[int(q)-1]
            return kind,name,[]
        if (IDENT.fullmatch(q) or QUOTED.fullmatch(q)
                or any(flow.stems(q) == flow.stems(label) for label in labels(index).values())):
            call = previous["intent"] == "calls"
            origin = previous["intent"] == "flow"
            if not (call or origin):
                for kind,name,label in options:
                    if q.casefold() in (name.casefold(),label.casefold()):
                        return kind,name,[]
    if not (call or origin):
        return ask("Вас интересует, кто вызывает функцию, или откуда берётся значение поля отчёта? Укажите функцию либо подпись в отчёте.")
    functions = top_functions(index)
    fn_matches = function_options(q,functions) if call else []
    keys = field_options(q,index) if origin else []
    fields = labels(index)
    opts = [("flow",k,fields.get(k,k)) for k in keys]
    if call and origin:
        return ask("В вопросе есть признаки поиска вызовов и трассировки значения. С чего начать?", opts=[
            ("calls",name,"Вызовы "+name) for name,_ in fn_matches] + opts)
    if call:
        if len(fn_matches) == 1:
            name,refs = fn_matches[0]
            return "calls",name,refs
        return ask("Какую функцию искать? Можно указать имя, её параметры или уникальный текст сообщения в кавычках.",
                   "calls",[("calls",n,n) for n in sorted({n for n,_ in fn_matches}) if sum(m == n for m,_ in fn_matches) == 1])
    unknown = set(IDENT.findall(QUOTED.sub(" ",q))) - index.producers.keys()
    if len(keys) == 1 and not unknown and len(index.producers[keys[0]]) == 1:
        return "flow",keys[0],[]
    if not opts:
        opts = [("flow",k,label) for k,label in sorted(fields.items()) if len(index.producers[k]) == 1]
    return ask("Какое одно поле проследить? Укажите название или подпись в отчёте.", "flow", opts)


def answer(q,src,refuse,previous=None):
    index = flow.Slice(src)
    decision = routes(q,index,previous,refuse)
    if isinstance(decision,dict):
        return decision
    route,name,locations = decision
    result = calls.lookup(name,src,refuse) if route == "calls" else index.answer(name,refuse)
    refs = []
    for path,a,b in dict.fromkeys(locations):
        ref = src.span(path,a,b)["ref"]
        refs.append(dict(ref,url=f"https://github.com/Daystat-debug/SkynetVS/blob/{src.commit}/{path}#L{a}-L{b}"))
    return dict(result,auto_route=route,auto_target=name,selection_evidence=refs)
