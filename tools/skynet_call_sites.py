"""Describe explicit calls to top-level Python functions using only the committed source."""
import ast
import inspect
import re
from dataclasses import asdict, dataclass
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


@dataclass(frozen=True, order=True)
class CallSite:
    commit: str
    path: str
    line: int
    column: int
    end_line: int
    end_column: int
    definition_path: str
    definition_line: int

    @classmethod
    def resolved(cls, src, path, call, target_path, fn):
        return cls(src.commit,path,call.lineno,call.col_offset,call.end_lineno,call.end_col_offset,
                   target_path,fn.lineno)


def main_guard(node):
    if not isinstance(node, ast.If):
        return False
    test = node.test
    if not isinstance(test, ast.Compare) or len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
        return False
    left, right = test.left, test.comparators[0]
    if isinstance(right, ast.Name):
        left, right = right, left
    return (isinstance(left, ast.Name) and left.id == "__name__"
            and isinstance(right, ast.Constant) and right.value == "__main__")


def call_roots(tree, names):
    for block in tree.body:
        if isinstance(block, (ast.FunctionDef, ast.AsyncFunctionDef)):
            allowed = {name for name in names if all(n is block for n in bindings(block,name))}
            yield block, allowed, [(stmt, block) for stmt in block.body]
        elif (main_guard(block) and unique_binding(tree, "__name__", None)
              and not possible_attribute_write([tree], "__name__")):
            # The target must already be bound when module-level execution reaches the guard.
            allowed = {name for name, binding in names.items() if binding.end_lineno < block.lineno}
            roots = [(stmt.value, stmt) for stmt in block.body
                     if isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.Expr)) and stmt.value is not None]
            yield block, allowed, roots


def coverage(paths):
    return {"paths":sorted(paths), "contexts":["top_level_function", "module_entry_direct_statement"],
            "project_exhaustive":False, "execution_observed":False}


COVERAGE_TEXT = ("Проверены прямые вызовы по имени внутри функций верхнего уровня и в теле "
                 "if __name__ == '__main__' (значения присваиваний и отдельные выражения). "
                 "Вложенные ветви блока запуска, методы и динамические вызовы вне охвата. "
                 "Факт выполнения неизвестен.")


def lookup(q, src, refuse, paths=None, *, evidence=None):
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
        return dict(refuse("incomplete"),call_coverage=coverage(paths),
                    text=f"В доступном коде возможна замена атрибута `{fn.name}`. Цель вызова не установлена.")
    found = []
    for p, tree in trees.items():
        names = resolved_names(tree, p, target_path, fn, trees[target_path])
        for caller, allowed, pending in call_roots(tree, names):
            entry = isinstance(caller, ast.If)
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
                locations = [(target_path, fn.lineno, fn.body[0].lineno-1),
                             (p,caller.lineno,caller.test.end_lineno if entry else caller.lineno),
                             (p,statement.lineno,statement.end_lineno)]
                if p != target_path:
                    locations.append((p,names[call.func.id].lineno,names[call.func.id].end_lineno))
                origin = (f"При запуске модуля как программы, если выполнение дойдёт до выражения "
                          f"`{ast.unparse(call)}`, возможен вызов `{fn.name}`" if entry
                          else f"`{caller.name}` вызывает `{fn.name}`")
                text = f"{origin}: {argument_text(fn,call)} {assigned}"
                site = CallSite.resolved(src,p,call,target_path,fn)
                context = dict(kind="module_entry" if entry else "function",
                               caller=None if entry else caller.name, context_line=caller.lineno)
                found.append((site,context,text,locations))
    claims = []
    for site, context, text, loc in sorted(found, key=lambda row:row[0]):
        refs = []
        for p, a, b in dict.fromkeys(loc):
            # The suite can start on the signature line for a one-line function.
            ref = src.span(p,a,max(a,b))["ref"]
            refs.append(dict(ref, url=f"https://github.com/Daystat-debug/SkynetVS/blob/{src.commit}/{p}#L{a}-L{ref['end']}"))
        claims.append({"text":text,"anchors":[], "evidence_blocks":refs, "call_site":dict(asdict(site), **context)})
        if evidence is not None:
            evidence[site] = len(claims)-1
    src.current()
    if not claims:
        return dict(refuse("incomplete"), call_coverage=coverage(paths), commit=src.commit,
                    text=f"В поддерживаемых контекстах выбранных файлов прямой вызов `{fn.name}` не установлен.")
    return {"status":"call_sites", "text":"Статически разрешённые места вызова в выбранных файлах:",
            "claims":claims, "commit":src.commit, "call_coverage":coverage(paths)}
