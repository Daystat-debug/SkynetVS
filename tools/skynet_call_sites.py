"""Describe explicit calls to top-level Python functions using only the committed source."""
import ast
import inspect
import re
from pathlib import PurePosixPath


def signature(fn):
    args = fn.args
    pos = args.posonlyargs + args.args
    default = [None] * (len(pos) - len(args.defaults)) + args.defaults
    param = inspect.Parameter
    values = []
    for arg, expr in zip(pos, default):
        kind = param.POSITIONAL_ONLY if arg in args.posonlyargs else param.POSITIONAL_OR_KEYWORD
        values.append(param(arg.arg, kind, default=param.empty if expr is None else ast.unparse(expr)))
    if args.vararg:
        values.append(param(args.vararg.arg, param.VAR_POSITIONAL))
    for arg, expr in zip(args.kwonlyargs, args.kw_defaults):
        values.append(param(arg.arg, param.KEYWORD_ONLY, default=param.empty if expr is None else ast.unparse(expr)))
    if args.kwarg:
        values.append(param(args.kwarg.arg, param.VAR_KEYWORD))
    return inspect.Signature(values)


def argument_text(fn, call):
    if any(isinstance(a, ast.Starred) for a in call.args) or any(k.arg is None for k in call.keywords):
        return "Аргументы разворачиваются при выполнении: " + ast.unparse(call) + "."
    sig = signature(fn)
    try:
        bound = sig.bind(*(ast.unparse(a) for a in call.args), **{k.arg:ast.unparse(k.value) for k in call.keywords})
    except TypeError:
        return "Запись вызова не согласуется с видимой сигнатурой: " + ast.unparse(call) + "."
    pairs = [f"`{k}` получает `{v}`" for k,v in bound.arguments.items()]
    defaults = [f"`{k}={p.default}`" for k,p in sig.parameters.items() if k not in bound.arguments and p.default is not p.empty]
    text = ", ".join(pairs) + "." if pairs else "Явных аргументов нет."
    if defaults:
        text += " По умолчанию используются " + ", ".join(defaults) + "."
    return text


def bindings(node, name):
    # Conservatively skip a scope if a name might be rebound, even on another branch.
    return [n for n in ast.walk(node)
            if (isinstance(n, ast.Name) and isinstance(n.ctx,(ast.Store,ast.Del)) and n.id == name
                or isinstance(n, ast.arg) and n.arg == name
                or isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef,ast.ExceptHandler)) and n.name == name
                or isinstance(n,(ast.MatchAs, ast.MatchStar)) and n.name == name
                or isinstance(n,ast.MatchMapping) and n.rest == name
                or isinstance(n, ast.alias) and (n.asname or n.name.split(".")[0]) in {name, "*"})]


def unique_binding(tree, name, binding):
    for n in ast.walk(tree):
        if isinstance(n, ast.Global) and name in n.names:
            return False
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in {"exec","eval","globals","locals","vars"}:
            return False
    others = []
    for stmt in tree.body:
        if isinstance(stmt,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
            if stmt.name == name:
                others.append(stmt)
            # Defaults, annotations, decorators and class bases may bind in the enclosing scope.
            for field, value in ast.iter_fields(stmt):
                if field != "body":
                    nodes = value if isinstance(value,list) else [value]
                    others.extend(n for node in nodes if isinstance(node,ast.AST) for n in ast.walk(node)
                                  if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Store) and n.id == name)
        else:
            others.extend(bindings(stmt,name))
    return others == ([] if binding is None else [binding])


def possible_attribute_write(trees, name):
    for tree in trees:
        for node in ast.walk(tree):
            if isinstance(node,ast.Attribute) and node.attr == name and isinstance(node.ctx,(ast.Store,ast.Del)):
                return True
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in {"setattr","delattr"}:
                if len(node.args) < 2 or not isinstance(node.args[1],ast.Constant) or node.args[1].value == name:
                    return True
    return False


def resolved_names(tree, path, target_path, fn, target_tree):
    if fn.decorator_list or not unique_binding(target_tree,fn.name,fn):
        return {}
    names = {}
    for stmt in tree.body:
        if stmt is fn and path == target_path:
            names[fn.name] = (stmt, stmt)
        if isinstance(stmt, ast.ImportFrom) and stmt.module:
            if stmt.level:
                parents = PurePosixPath(path).parents
                if stmt.level > len(parents):
                    continue
                base = parents[stmt.level-1]
            else:
                base = PurePosixPath()
            imported = (base / PurePosixPath(*stmt.module.split("."))).with_suffix(".py")
            if str(imported) == target_path:
                for alias in stmt.names:
                    if alias.name == fn.name:
                        names[alias.asname or alias.name] = (alias, stmt)
    return {name:definition for name,(binding,definition) in names.items() if unique_binding(tree,name,binding)}


def destination(parent, call):
    if isinstance(parent,(ast.Assign,ast.AnnAssign)) and parent.value is call:
        targets = parent.targets if isinstance(parent,ast.Assign) else [parent.target]
        return "Результат присваивается " + " и ".join(f"`{ast.unparse(t)}`" for t in targets) + "."
    if isinstance(parent, ast.Return):
        return "Результат возвращается вызывающей функцией."
    if isinstance(parent, ast.Expr):
        return "Возвращённое значение не сохраняется."
    return "Результат используется внутри выражения."


def lookup(q, src, refuse, paths=None):
    src.current()
    paths = sorted(src.pages if paths is None else paths)
    if not set(paths) <= src.pages.keys():
        return refuse("external")
    trees = {p:ast.parse(src.snapshot.sources[p]) for p in paths}
    functions = [(p,n) for p,tree in trees.items() for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
    words = set(re.findall(r"\b[A-Za-z_]\w*\b", q))
    targets = [(p,n) for p,n in functions if n.name in words]
    if len(targets) != 1:
        return dict(refuse("ambiguous"), text="Укажите одно имя функции верхнего уровня из доступных файлов.")
    target_path, fn = targets[0]
    if possible_attribute_write(trees.values(),fn.name):
        return dict(refuse("incomplete"),text=f"В доступном коде возможна замена атрибута `{fn.name}`. Цель вызова не установлена.")
    found = []
    for p, tree in trees.items():
        names = resolved_names(tree, p, target_path, fn, trees[target_path])
        for caller in tree.body:
            if not isinstance(caller,(ast.FunctionDef,ast.AsyncFunctionDef)):
                continue
            allowed = {name for name in names if all(n is caller for n in bindings(caller,name))}
            pending = [(stmt,caller) for stmt in caller.body]
            while pending:
                call, parent = pending.pop()
                if isinstance(call,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef,ast.Lambda,
                                    ast.ListComp,ast.SetComp,ast.DictComp,ast.GeneratorExp)):
                    continue
                pending.extend((child,call) for child in ast.iter_child_nodes(call))
                if not (isinstance(call,ast.Call) and isinstance(call.func,ast.Name) and call.func.id in allowed):
                    continue
                assigned = destination(parent, call)
                statement = parent if isinstance(parent,(ast.Assign,ast.AnnAssign,ast.Return,ast.Expr)) else call
                locations = [(target_path, fn.lineno, fn.body[0].lineno-1), (p,caller.lineno,caller.lineno),
                             (p,statement.lineno,statement.end_lineno)]
                if p != target_path:
                    locations.append((p,names[call.func.id].lineno,names[call.func.id].end_lineno))
                text = f"`{caller.name}` вызывает `{fn.name}`: {argument_text(fn,call)} {assigned}"
                found.append((p,call.lineno,text,locations))
    claims = []
    for _, _, text, loc in sorted(found):
        refs = []
        for p, a, b in dict.fromkeys(loc):
            # The suite can start on the signature line for a one-line function.
            ref = src.span(p,a,max(a,b))["ref"]
            refs.append(dict(ref, url=f"https://github.com/Daystat-debug/SkynetVS/blob/{src.commit}/{p}#L{a}-L{ref['end']}"))
        claims.append({"text":text,"anchors":[], "evidence_blocks":refs})
    src.current()
    if not claims:
        return dict(refuse("incomplete"), text=f"В проверенных файлах не найден прямой вызов `{fn.name}` по статически разрешённому имени внутри функции верхнего уровня. Вызовы через другие файлы, методы и динамические ссылки этим поиском не охвачены.")
    return {"status":"call_sites", "text":"Прямые вызовы в функциях верхнего уровня проверенных файлов:",
            "claims":claims, "commit":src.commit}
