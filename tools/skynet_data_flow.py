"""Backwards slice of named fields in returned Python dictionaries. No source execution."""
import ast
from collections import defaultdict
from dataclasses import dataclass
import re

import skynet_call_sites as sites


@dataclass(frozen=True)
class Function:
    path: str
    tree: ast.Module
    node: ast.FunctionDef


def fields(fn, expr):
    if isinstance(expr, ast.Dict):
        if any(not isinstance(k, ast.Constant) or type(k.value) is not str for k in expr.keys):
            return {}
        pairs = [(k.value, (k, v)) for k,v in zip(expr.keys, expr.values)]
    elif (isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name) and expr.func.id == "dict"
          and not expr.args and all(k.arg for k in expr.keywords)
          and not sites.bindings(fn.node, "dict") and sites.unique_binding(fn.tree, "dict", None)):
        pairs = [(k.arg, (k, k.value)) for k in expr.keywords]
    else:
        return {}
    return dict(pairs) if len({k for k,_ in pairs}) == len(pairs) else {}


def local_name(node, name):
    return isinstance(node, ast.Name) and node.id == name


def literal_key(node):
    if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant) and type(node.slice.value) is str:
        return node.slice.value
    return None


def returns(fn):
    """Only a final return and optional single, top-level guarded early returns."""
    result = []
    for stmt in fn.node.body:
        if isinstance(stmt, ast.If) and not stmt.orelse and len(stmt.body) == 1 and isinstance(stmt.body[0], ast.Return):
            result.append((stmt.body[0], stmt.test))
        elif isinstance(stmt, ast.Return) and stmt is fn.node.body[-1]:
            result.append((stmt, None))
        elif any(isinstance(n, ast.Return) for n in ast.walk(stmt)):
            return []
    return result if result and result[-1][1] is None else []


def assigned(fn, name, use):
    """A single dominating assignment. Reject aliases, mutations and escapes before the read."""
    writes = sites.bindings(fn.node, name)
    if len(writes) != 1 or not isinstance(writes[0], ast.Name):
        return None
    for stmt in fn.node.body:
        if not isinstance(stmt,ast.Assign) or len(stmt.targets) != 1 or stmt.end_lineno >= use.lineno:
            continue
        target = stmt.targets[0]
        index = None
        if isinstance(target,(ast.Tuple,ast.List)) and all(isinstance(n,ast.Name) for n in target.elts):
            if writes[0] not in target.elts:
                continue
            index = target.elts.index(writes[0])
        elif target is not writes[0]:
            continue
        for n in ast.walk(fn.node):
            if not stmt.end_lineno < getattr(n,"lineno",0) <= use.lineno:
                continue
            for child in ast.iter_child_nodes(n):
                if local_name(child, name) and child is not use:
                    # A literal-key read cannot overwrite the binding or its mapping entry.
                    if not (isinstance(n, ast.Subscript) and child is n.value and literal_key(n) is not None
                            and isinstance(n.ctx,ast.Load)):
                        return None
        return stmt, index
    return None


def labels(fn):
    """UI labels directly adjacent to formatted reads from an unshadowed parameter."""
    params = {a.arg for a in fn.node.args.args if sites.bindings(fn.node,a.arg) == [a]}
    pending = list(fn.node.body)
    while pending:
        node = pending.pop()
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef,ast.Lambda)):
            continue
        pending.extend(ast.iter_child_nodes(node))
        if not isinstance(node,ast.JoinedStr):
            continue
        for prefix, item in zip(node.values, node.values[1:]):
            if not (isinstance(prefix,ast.Constant) and isinstance(prefix.value,str) and isinstance(item,ast.FormattedValue)):
                continue
            key = literal_key(item.value)
            if key and isinstance(item.value.value,ast.Name) and item.value.value.id in params:
                label = re.search(r"([А-Яа-яЁё -]+):\s*$",prefix.value)
                if label:
                    yield key, label[1].strip(), item.value


def stems(text):
    return [w[:4] for w in re.findall(r"[а-яё]+",text.lower()) if len(w) >= 4]


class Slice:
    def __init__(self, src, *, evidence=None):
        self.src = src
        self.evidence = evidence
        self.functions = []
        self.producers = defaultdict(list)
        self.users = defaultdict(list)
        self.trees = {}
        self.claims = []
        self.limited = False
        for path in sorted(src.pages):
            tree = ast.parse(src.snapshot.sources[path])
            self.trees[path] = tree
            for node in tree.body:
                if not isinstance(node,ast.FunctionDef):
                    continue
                fn = Function(path,tree,node)
                self.functions.append(fn)
                if node.decorator_list or not sites.unique_binding(tree,node.name,node):
                    continue
                exits = returns(fn)
                if len(exits) == 1:
                    for key, pair in fields(fn,exits[0][0].value).items():
                        self.producers[key].append((fn,*pair))
                for key,label,read in labels(fn):
                    self.users[key].append((fn,label,read))

    def say(self, text, fn, start, last=None):
        first = start.lineno
        if last is None:
            last = start.end_lineno
        ref = self.src.span(fn.path,first,last)["ref"]
        link = f"https://github.com/Daystat-debug/SkynetVS/blob/{self.src.commit}/{fn.path}#L{first}-L{last}"
        self.claims.append({"text":text, "anchors":[], "evidence_blocks":[dict(ref,url=link)]})

    def stop(self, why, fn, node):
        self.limited = True
        self.say(why,fn,node)

    def choose(self, q):
        explicit = set(re.findall(r"\b[A-Za-z_]\w*\b",q))
        if explicit:
            keys = explicit & self.producers.keys()
            return next(iter(keys)) if len(keys) == 1 and len(explicit) == 1 else None
        words = set(stems(q))
        scores = {}
        for key, readers in self.users.items():
            for _,label,_ in readers:
                names = stems(label)
                if key in self.producers and names and names[0] in words:
                    scores[key] = max(scores.get(key,0), len(words.intersection(names)))
        best = [k for k in scores if scores[k] == max(scores.values())]
        return best[0] if len(best) == 1 else None

    def walk(self, fn, value, projections=(), depth=0):
        expr = ast.unparse(value)
        if depth >= 16 or len(self.claims) >= 64:
            return self.stop("Достигнута граница глубины трассировки.",fn,value)
        if isinstance(value,ast.Constant) and not projections:
            return self.say(f"Значение задано литералом `{expr}`.",fn,value)
        key = literal_key(value)
        if key is not None:
            self.say(f"Читается значение по ключу: `{expr}`.",fn,value)
            return self.walk(fn,value.value,(key,*projections),depth+1)
        if isinstance(value,ast.Name):
            origin = assigned(fn,value.id,value)
            if origin is None:
                return self.stop(f"Для `{expr}` единственный неизменённый источник до чтения не установлен.",fn,value)
            stmt, index = origin
            self.say(f"В `{fn.node.name}` выполнено присваивание `{ast.unparse(stmt)}`.",fn,stmt)
            if projections and isinstance(stmt.value, ast.Name):
                return self.stop("Присвоена ссылка на другой объект. Изменения через связанные имена не исключены.",fn,stmt)
            return self.walk(fn,stmt.value,projections if index is None else (index,*projections),depth+1)
        if projections and isinstance(projections[0], int) and isinstance(value,(ast.Tuple,ast.List)):
            idx = projections[0]
            if idx < len(value.elts) and not any(isinstance(n,ast.Starred) for n in value.elts):
                selected = value.elts[idx]
                self.say(f"Элемент {idx+1} возвращаемой последовательности — `{ast.unparse(selected)}`.",fn,selected)
                return self.walk(fn,selected,projections[1:],depth+1)
        if projections and isinstance(projections[0],str):
            entry = fields(fn,value).get(projections[0])
            if entry:
                start, selected = entry
                self.say(f"`{fn.node.name}` возвращает поле `{projections[0]}` со значением `{ast.unparse(selected)}`.",fn,start,selected.end_lineno)
                return self.walk(fn,selected,projections[1:],depth+1)
        if not (isinstance(value,ast.Call) and isinstance(value.func,ast.Name)):
            return self.stop(f"Ближайшее выражение — `{expr}`. Более раннее происхождение статически не установлено.",fn,value)
        name = value.func.id
        if (name == "len" and not projections and not sites.bindings(fn.node,name)
                and sites.unique_binding(fn.tree,name,None)):
            return self.say(f"Итог вычисляется как длина: `{expr}`.",fn,value)
        candidates = []
        if not sites.bindings(fn.node,name):
            for target in self.functions:
                resolved = sites.resolved_names(fn.tree,fn.path,target.path,target.node,target.tree)
                if name in resolved and not sites.possible_attribute_write(self.trees.values(),target.node.name):
                    candidates.append((target,resolved[name]))
        if len(candidates) != 1:
            for imp in fn.tree.body:
                if not isinstance(imp,ast.ImportFrom) or sites.bindings(fn.node,name):
                    continue
                for alias in imp.names:
                    if (alias.asname or alias.name) == name and sites.unique_binding(fn.tree,name,alias):
                        return self.stop(f"Источник вызова `{expr}` импортирован из `{'.'*imp.level}{imp.module or ''}`. Его реализация не установлена в разрешённом снимке.",fn,imp)
            return self.stop(f"Цель вызова `{expr}` статически не установлена.",fn,value)
        target, binding = candidates[0]
        if any(isinstance(a,ast.Starred) for a in value.args) or any(k.arg is None for k in value.keywords):
            return self.stop(f"В `{expr}` набор аргументов определяется при выполнении.",fn,value)
        try:
            sites.signature(target.node).bind(*value.args,**{k.arg:k.value for k in value.keywords})
        except TypeError:
            return self.stop(f"Аргументы `{expr}` не соответствуют видимой сигнатуре.",fn,value)
        if self.evidence is not None:
            self.evidence.add(sites.CallSite.resolved(self.src,fn.path,value,target.path,target.node))
        if target.path != fn.path:
            self.say(f"Импорт связывает `{name}` с `{target.node.name}` в {target.path.rsplit('/',1)[-1]}.",fn,binding)
        self.say(f"При вызове `{target.node.name}` {sites.argument_text(target.node,value)}",
                 target,target.node,max(target.node.lineno,target.node.body[0].lineno-1))
        exits = returns(target)
        if not exits:
            return self.stop(f"Структура возвратов `{name}` вне поддерживаемого подмножества.",fn,value)
        for ret, guard in exits:
            if len(self.claims) >= 64:
                return self.stop("Достигнут лимит доказательных шагов; остальные пути не проверены.",fn,value)
            if guard:
                self.say(f"Ранний возврат при `{ast.unparse(guard)}`.",target,guard)
            elif len(exits) > 1:
                self.say("Если выполнение дошло до заключительного возврата:",target,ret)
            if ret.value is None:
                self.stop("Этот возврат не содержит значения для дальнейшего чтения.",target,ret)
            else:
                self.walk(target,ret.value,projections,depth+1)

    def answer(self,q,refuse):
        if re.search(r"последн\w*\s+запуск|сейчас|мо[её]м компьютере",q,re.I):
            return refuse("live")
        key = self.choose(q)
        if key is None or len(self.producers[key]) != 1:
            named = [f.node.name for f in self.functions if re.search(r"\b"+re.escape(f.node.name)+r"\b",q)]
            if len(named) == 1 and re.search("переда[её]т|вызыва",q,re.I):
                result = sites.lookup(named[0],self.src,refuse)
                if not result["claims"]:
                    return result
            options = ", ".join(sorted(self.producers.keys() & self.users.keys()))
            return dict(refuse("ambiguous"),text="Уточните одно поле возвращаемого словаря. Поля с подписью в выводе: " + options)
        fn,start,value = self.producers[key][0]
        self.say(f"`{fn.node.name}` формирует поле `{key}` из `{ast.unparse(value)}`.",fn,start,value.end_lineno)
        self.walk(fn,value)
        for consumer,label,read in self.users[key]:
            self.say(f"В `{consumer.node.name}` подпись «{label}» сопровождает чтение `{ast.unparse(read)}`. Это потребитель поля, если ему передан этот отчёт и достигнута данная строка. Факт передачи не установлен.",consumer,read)
        self.src.current()
        return {"status":"flow_limited" if self.limited else "flow", "field":key, "commit":self.src.commit,
                "text":"Статическая цепочка на путях, где функция вернула словарь:",
                "claims":self.claims}
