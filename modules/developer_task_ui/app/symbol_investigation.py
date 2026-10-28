"""Bounded static Python symbol investigation over one committed Git snapshot.

Only definition locations and conservative syntactic call references are reported.
No project source is imported/executed, no runtime binding is proved, and no change
permission follows from a reference. Unsupported bindings stay explicitly unknown.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA = "SKYNETVS_CORE_SYMBOL_INVESTIGATION_V1"
MAX_FILES = 800
MAX_FILE_BYTES = 256 * 1024
MAX_SOURCE_BYTES = 8 * 1024 * 1024
MAX_AST_NODES_PER_FILE = 60000
MAX_AST_NODES = 600000
MAX_FUNCTIONS = 20000
MAX_CALL_SITES = 40000
MAX_RESULT_ROWS = 256
MAX_CANDIDATES = 64
_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_PATH = re.compile(r"(?:main\.py|modules/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\.py)\Z")
_QUALNAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*\Z")
_EXCLUDED = frozenset(("tests", "test", "vendor", "reference", "fixtures", "__pycache__"))
_NAMESPACE_CALLS = frozenset(("eval", "exec", "globals", "locals", "vars", "setattr", "delattr"))
_REASONS_RU = {
    "PARAMETER_OR_LOCAL_BINDING": "имя затенено параметром или локальной переменной",
    "REBOUND_OR_DUPLICATE_NAME": "имя имеет несколько определений или присваиваний",
    "MISSING_OR_REBOUND_TARGET": "целевое имя отсутствует или переопределено",
    "GLOBAL_OR_NONLOCAL_BINDING": "связь зависит от global/nonlocal",
    "CLOSURE_BINDING_NOT_RESOLVED": "связь через замыкание не разрешена",
    "TYPE_PARAMETER_BINDING": "имя относится к параметру обобщённого типа",
    "DYNAMIC_NAMESPACE": "код может динамически обращаться к пространству имён",
    "STAR_IMPORT": "импорт * не позволяет однозначно связать имена",
    "CONDITIONAL_BINDING": "имя определяется условно",
    "CONDITIONAL_DEFINITION": "целевая функция определяется условно",
    "DECORATED_TARGET": "декоратор может заменить вызываемую функцию",
    "TARGET_NOT_MODULE_FUNCTION": "цель не является устойчивым определением функции модуля",
    "EXTERNAL_OR_UNBOUND_NAME": "имя внешнее или не связано с определением в области поиска",
    "EXTERNAL_OR_AMBIGUOUS_MODULE": "модуль внешний, пропущен или неоднозначен",
    "RELATIVE_IMPORT_OUTSIDE_SCOPE": "относительный импорт выходит за известную область",
    "AMBIGUOUS_IMPORTED_ATTRIBUTE": "импорт может ссылаться на атрибут пакета",
    "DYNAMIC_SELF_OR_CLS_ATTRIBUTE": "динамический вызов через self/cls",
    "DYNAMIC_CALL_EXPRESSION": "вызываемый объект получен из выражения",
    "DYNAMIC_OR_UNSUPPORTED_ATTRIBUTE": "цепочка атрибутов не разрешена статически",
    "DYNAMIC_ATTRIBUTE": "атрибут объекта не разрешён статически",
    "ATTRIBUTE_REBINDING": "в коде изменяется атрибут этого объекта",
    "DEFINITION_TIME_CONTEXT": "вызов в декораторе, аннотации или значении по умолчанию",
    "CLASS_DEFINITION_CONTEXT": "вызов при определении класса",
    "CLASS_BODY_CONTEXT": "вызов в пространстве имён класса",
    "LAMBDA_SCOPE_NOT_RESOLVED": "контекст lambda отдельно не разрешён",
    "COMPREHENSION_SCOPE_NOT_RESOLVED": "контекст включения или генератора отдельно не разрешён",
    "TYPE_ALIAS_SCOPE_NOT_RESOLVED": "контекст обобщённого псевдонима типа отдельно не разрешён",
}


class InvestigationRefusal(ValueError):
    pass


def _require(value, reason):
    if not value:
        raise InvestigationRefusal(reason)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _identity(commit, path, qualname, start):
    return _sha(json.dumps([commit, path, qualname, start], separators=(",", ":")).encode("utf-8"))


def _names(expression):
    """Identifiers only; never render argument values, literals or arbitrary code."""
    if isinstance(expression, ast.Name):
        return [expression.id]
    if isinstance(expression, ast.Attribute):
        previous = _names(expression.value)
        if previous:
            return previous + [expression.attr]
    return None


def _display_callee(expression):
    names = _names(expression)
    return ".".join(names)[:300] if names else "<" + type(expression).__name__ + ">"


def _module_name(path):
    name = path[:-3].replace("/", ".")
    return name[:-9] if name.endswith(".__init__") else name


@dataclass
class _Binding:
    kind: str
    node: ast.AST
    direct: bool = False
    module: str | None = None
    imported: str | None = None
    level: int = 0
    prefix: tuple[str, ...] = ()


@dataclass
class _Scope:
    module: "_Module"
    node: ast.AST
    kind: str
    qualname: str
    parent: "_Scope | None"
    reference: dict
    bindings: dict[str, list[_Binding]] = field(default_factory=dict)
    globals: set[str] = field(default_factory=set)
    nonlocals: set[str] = field(default_factory=set)
    star_import: bool = False
    type_parameters: set[str] = field(default_factory=set)


@dataclass
class _Module:
    path: str
    text: str
    tree: ast.Module
    commit: str
    sha: str
    oid: str
    scopes: list[_Scope] = field(default_factory=list)
    definitions: dict[int, _Scope] = field(default_factory=dict)
    global_writes: set[str] = field(default_factory=set)
    nonlocal_writes: set[str] = field(default_factory=set)
    attribute_writes: set[str] = field(default_factory=set)
    dynamic_namespace: bool = False


def _reference(module, node, qualname, kind):
    start = getattr(node, "lineno", 1)
    end = getattr(node, "end_lineno", None) or max(1, len(module.text.splitlines()))
    return {"id": _identity(module.commit, module.path, qualname, start),
            "path": module.path, "qualname": qualname, "kind": kind,
            "start": start, "end": end, "source_sha256": module.sha,
            "blob_oid": module.oid}


class _Bindings(ast.NodeVisitor):
    def __init__(self, scope):
        self.scope = scope
        self.direct = {id(node) for node in scope.node.body}

    def add(self, name, kind, node, **kwargs):
        self.scope.bindings.setdefault(name, []).append(
            _Binding(kind, node, direct=id(node) in self.direct, **kwargs))

    def visit_Name(self, node):
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.add(node.id, "assignment", node)

    def _headers(self, node):
        for item in node.decorator_list:
            self.visit(item)
        for item in (*node.args.defaults, *node.args.kw_defaults):
            if item is not None:
                self.visit(item)
        for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs,
                    *([node.args.vararg] if node.args.vararg else []),
                    *([node.args.kwarg] if node.args.kwarg else [])):
            if arg.annotation is not None:
                self.visit(arg.annotation)
        if node.returns is not None:
            self.visit(node.returns)

    def visit_FunctionDef(self, node):
        self.add(node.name, "function", node)
        self._headers(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        self.add(node.name, "class", node)
        for item in (*node.bases, *node.decorator_list):
            self.visit(item)
        for item in node.keywords:
            self.visit(item.value)

    def visit_Import(self, node):
        for alias in node.names:
            name = alias.asname or alias.name.split(".")[0]
            prefix = (name,) if alias.asname else tuple(alias.name.split("."))
            self.add(name, "module_import", node, module=alias.name, prefix=prefix)

    def visit_ImportFrom(self, node):
        for alias in node.names:
            if alias.name == "*":
                self.scope.star_import = True
            else:
                self.add(alias.asname or alias.name, "from_import", node,
                         module=node.module, imported=alias.name, level=node.level)

    def visit_Global(self, node):
        self.scope.globals.update(node.names)

    def visit_Nonlocal(self, node):
        self.scope.nonlocals.update(node.names)

    def visit_ExceptHandler(self, node):
        if node.name:
            self.add(node.name, "assignment", node)
        self.generic_visit(node)

    def visit_MatchAs(self, node):
        if node.name:
            self.add(node.name, "assignment", node)
        self.generic_visit(node)

    def visit_MatchStar(self, node):
        if node.name:
            self.add(node.name, "assignment", node)

    def visit_MatchMapping(self, node):
        if node.rest:
            self.add(node.rest, "assignment", node)
        self.generic_visit(node)

    def visit_Lambda(self, node):
        for item in (*node.args.defaults, *node.args.kw_defaults):
            if item is not None:
                self.visit(item)

    def _comprehension(self, node):
        # Comprehension targets have a separate scope, but a walrus may bind the
        # enclosing scope. Treat every such target conservatively as a binding.
        for item in ast.walk(node):
            if isinstance(item, ast.NamedExpr):
                self.visit(item.target)

    visit_ListComp = _comprehension
    visit_SetComp = _comprehension
    visit_DictComp = _comprehension
    visit_GeneratorExp = _comprehension


def _new_scope(module, node, kind, qualname, parent):
    scope = _Scope(module, node, kind, qualname, parent,
                   _reference(module, node, qualname, kind))
    module.scopes.append(scope)
    if kind in ("FunctionDef", "AsyncFunctionDef"):
        module.definitions[id(node)] = scope
    binding = _Bindings(scope)
    for parameter in getattr(node, "type_params", []):
        if isinstance(getattr(parameter, "name", None), str):
            scope.type_parameters.add(parameter.name)
            binding.add(parameter.name, "type_parameter", parameter)
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs,
                    *([node.args.vararg] if node.args.vararg else []),
                    *([node.args.kwarg] if node.args.kwarg else [])):
            binding.add(arg.arg, "parameter", arg)
    for statement in node.body:
        binding.visit(statement)
    if kind in ("FunctionDef", "AsyncFunctionDef", "ClassDef"):
        # Even a declaration without a discovered store is not used to prove
        # that this module binding remains stable across runtime invocations.
        module.global_writes.update(scope.globals)
        module.nonlocal_writes.update(scope.nonlocals)
    return scope


class _Index(ast.NodeVisitor):
    def __init__(self, module):
        self.module = module
        self.scope = _new_scope(module, module.tree, "Module", "<module>", None)

    def _nested(self, node):
        parent = self.scope
        prefix = "" if parent.kind == "Module" else parent.qualname + "."
        self.scope = _new_scope(self.module, node, type(node).__name__, prefix + node.name, parent)
        for item in node.body:
            self.visit(item)
        self.scope = parent

    visit_FunctionDef = _nested
    visit_AsyncFunctionDef = _nested
    visit_ClassDef = _nested


def _index_module(commit, path, text, tree):
    raw = text.encode("utf-8")
    module = _Module(path, text, tree, commit, _sha(raw),
                     hashlib.sha1(f"blob {len(raw)}\0".encode("ascii") + raw).hexdigest())
    index = _Index(module)
    for item in tree.body:
        index.visit(item)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _NAMESPACE_CALLS:
            module.dynamic_namespace = True
        if isinstance(node, (ast.Attribute, ast.Subscript)) and isinstance(node.ctx, (ast.Store, ast.Del)):
            root = node.value
            while isinstance(root, (ast.Attribute, ast.Subscript)):
                root = root.value
            if isinstance(root, ast.Name):
                module.attribute_writes.add(root.id)
    return module


def _import_base(module, binding):
    if not binding.level:
        return binding.module or ""
    current = _module_name(module.path)
    package = current if module.path.endswith("/__init__.py") else current.rpartition(".")[0]
    parts = package.split(".") if package else []
    if binding.level > len(parts):
        return None
    prefix = parts[:len(parts) - binding.level + 1]
    if binding.module:
        prefix.extend(binding.module.split("."))
    return ".".join(prefix)


def _stable_function(module, name):
    scope = module.scopes[0]
    if module.dynamic_namespace:
        return None, "DYNAMIC_NAMESPACE"
    if scope.star_import:
        return None, "STAR_IMPORT"
    if name in module.global_writes:
        return None, "GLOBAL_OR_NONLOCAL_BINDING"
    bindings = scope.bindings.get(name, [])
    if len(bindings) != 1:
        return None, "MISSING_OR_REBOUND_TARGET"
    binding = bindings[0]
    if binding.kind != "function":
        return None, "TARGET_NOT_MODULE_FUNCTION"
    if not binding.direct:
        return None, "CONDITIONAL_DEFINITION"
    if binding.node.decorator_list:
        return None, "DECORATED_TARGET"
    return module.definitions[id(binding.node)], None


def _lookup(scope, name):
    module = scope.module
    if module.dynamic_namespace:
        return None, None, "DYNAMIC_NAMESPACE"
    if name in module.nonlocal_writes:
        return None, None, "GLOBAL_OR_NONLOCAL_BINDING"
    current = scope
    while current is not None:
        if name in current.type_parameters:
            return None, None, "TYPE_PARAMETER_BINDING"
        # A method body does not close over its class namespace.
        if current.kind == "ClassDef":
            current = current.parent
            continue
        if current.star_import:
            return None, None, "STAR_IMPORT"
        if name in current.globals or name in current.nonlocals:
            return None, None, "GLOBAL_OR_NONLOCAL_BINDING"
        found = current.bindings.get(name, [])
        if found:
            if len(found) != 1:
                return None, None, "REBOUND_OR_DUPLICATE_NAME"
            binding = found[0]
            if current.kind != "Module" and binding.kind not in ("module_import", "from_import"):
                return None, None, "PARAMETER_OR_LOCAL_BINDING"
            if current is not scope and current.kind != "Module":
                return None, None, "CLOSURE_BINDING_NOT_RESOLVED"
            if not binding.direct and binding.kind in ("function", "module_import", "from_import"):
                return None, None, "CONDITIONAL_BINDING"
            if current.kind == "Module" and name in module.global_writes:
                return None, None, "GLOBAL_OR_NONLOCAL_BINDING"
            return current, binding, None
        current = current.parent
    return None, None, "EXTERNAL_OR_UNBOUND_NAME"


def _target(modules, name, member):
    choices = modules.get(name, [])
    if len(choices) != 1:
        return None, "EXTERNAL_OR_AMBIGUOUS_MODULE"
    return _stable_function(choices[0], member)


def _resolve(scope, expression, modules):
    names = _names(expression)
    if not names:
        return None, None, "DYNAMIC_CALL_EXPRESSION"
    root = names[0]
    if len(names) > 1 and root in {"self", "cls"}:
        return None, None, "DYNAMIC_SELF_OR_CLS_ATTRIBUTE"
    owner, binding, reason = _lookup(scope, root)
    if reason:
        return None, None, reason
    if len(names) > 1 and root in scope.module.attribute_writes:
        return None, None, "ATTRIBUTE_REBINDING"
    if binding.kind == "function" and len(names) == 1:
        target, reason = _stable_function(owner.module, root)
        return target, "SAME_MODULE_NAME", reason
    if binding.kind == "module_import":
        prefix = list(binding.prefix)
        if names[:len(prefix)] != prefix or len(names) != len(prefix) + 1:
            return None, None, "DYNAMIC_OR_UNSUPPORTED_ATTRIBUTE"
        target, reason = _target(modules, binding.module, names[-1])
        return target, "EXPLICIT_IMPORT", reason
    if binding.kind == "from_import":
        base = _import_base(owner.module, binding)
        if base is None:
            return None, None, "RELATIVE_IMPORT_OUTSIDE_SCOPE"
        if len(names) == 1:
            target, reason = _target(modules, base, binding.imported)
            return target, "EXPLICIT_IMPORT", reason
        if len(names) == 2:
            # 'from package import submodule' may instead select a package
            # attribute. Only the unambiguous absent-attribute case is used.
            parents = modules.get(base, [])
            if len(parents) != 1 or any(
                    m.dynamic_namespace or m.scopes[0].star_import or
                    "__getattr__" in m.scopes[0].bindings or
                    binding.imported in m.scopes[0].bindings or
                    binding.imported in m.global_writes for m in parents):
                return None, None, "AMBIGUOUS_IMPORTED_ATTRIBUTE"
            target, reason = _target(modules, base + "." + binding.imported, names[1])
            return target, "EXPLICIT_IMPORT", reason
        return None, None, "DYNAMIC_OR_UNSUPPORTED_ATTRIBUTE"
    return None, None, ("DYNAMIC_ATTRIBUTE" if len(names) > 1 else "TARGET_NOT_MODULE_FUNCTION")


def _site(scope, node):
    return {"path": scope.module.path, "line": node.lineno, "column": node.col_offset,
            "end_line": node.end_lineno or node.lineno, "source_sha256": scope.module.sha,
            "blob_oid": scope.module.oid}


class _Calls(ast.NodeVisitor):
    def __init__(self, scope, emit):
        self.scope = scope
        self.emit = emit
        self.forced = "CLASS_BODY_CONTEXT" if scope.kind == "ClassDef" else None

    def visit_Call(self, node):
        self.emit(self.scope, node, self.forced)
        self.generic_visit(node)

    def _uncertain(self, nodes, reason):
        old = self.forced
        self.forced = reason
        for node in nodes:
            if node is not None:
                self.visit(node)
        self.forced = old

    def visit_FunctionDef(self, node):
        headers = [*node.decorator_list, *node.args.defaults, *node.args.kw_defaults, node.returns]
        headers.extend(getattr(node, "type_params", []))
        headers.extend(arg.annotation for arg in (*node.args.posonlyargs, *node.args.args,
                       *node.args.kwonlyargs, *([node.args.vararg] if node.args.vararg else []),
                       *([node.args.kwarg] if node.args.kwarg else [])))
        self._uncertain(headers, "DEFINITION_TIME_CONTEXT")

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        self._uncertain([*node.bases, *node.decorator_list, *(k.value for k in node.keywords),
                         *getattr(node, "type_params", [])],
                        "CLASS_DEFINITION_CONTEXT")

    def visit_TypeAlias(self, node):
        self._uncertain([*getattr(node, "type_params", []), node.value], "TYPE_ALIAS_SCOPE_NOT_RESOLVED")

    def visit_Lambda(self, node):
        self._uncertain([*node.args.defaults, *node.args.kw_defaults, node.body],
                        "LAMBDA_SCOPE_NOT_RESOLVED")

    def _comprehension(self, node):
        self._uncertain(list(ast.iter_child_nodes(node)), "COMPREHENSION_SCOPE_NOT_RESOLVED")

    visit_ListComp = _comprehension
    visit_SetComp = _comprehension
    visit_DictComp = _comprehension
    visit_GeneratorExp = _comprehension


def _selector(value):
    _require(isinstance(value, str) and 0 < len(value.strip()) <= 640, "SYMBOL_SELECTOR_INVALID")
    value = value.strip()
    path, name = (value.split("::", 1) if "::" in value else (None, value))
    if path is not None:
        _require(bool(_PATH.fullmatch(path)), "SYMBOL_SELECTOR_PATH_INVALID")
    line = None
    if "@" in name:
        name, number = name.rsplit("@", 1)
        _require(bool(re.fullmatch(r"[1-9][0-9]{0,6}", number)), "SYMBOL_SELECTOR_LINE_INVALID")
        line = int(number)
    _require(bool(_QUALNAME.fullmatch(name)), "SYMBOL_SELECTOR_NAME_INVALID")
    return value, path, name, line


def _validate_goal(goal):
    _require(isinstance(goal, str) and bool(goal.strip()) and len(goal) <= 1200 and
             len(goal.encode("utf-8", "surrogatepass")) <= 2500 and
             not any(0xD800 <= ord(c) <= 0xDFFF for c in goal), "SYMBOL_GOAL_INVALID")


def investigate_sources(commit, sources, scan, goal, selector):
    """Pure analysis of caller-supplied source bytes decoded as strict UTF-8.

    The wrapper, not this pure function, attests that Git HEAD was observed.
    Limits, failures and unsupported calls never become negative runtime claims.
    """
    _require(isinstance(commit, str) and bool(_SHA40.fullmatch(commit)), "SYMBOL_COMMIT_INVALID")
    _validate_goal(goal)
    selector, selected_path, selected_name, selected_line = _selector(selector)
    _require(isinstance(sources, dict) and 0 < len(sources) <= MAX_FILES, "SYMBOL_SOURCE_COUNT_INVALID")
    total = 0
    for path, source in sources.items():
        _require(isinstance(path, str) and bool(_PATH.fullmatch(path)) and len(path) <= 300 and
                 not any(p.casefold() in _EXCLUDED for p in path.split("/")) and
                 not path.rsplit("/", 1)[-1].startswith("test_"), "SYMBOL_SOURCE_PATH_INVALID")
        _require(isinstance(source, str) and "\0" not in source, "SYMBOL_SOURCE_TEXT_INVALID")
        try:
            size = len(source.encode("utf-8", "strict"))
        except UnicodeError as exc:
            raise InvestigationRefusal("SYMBOL_SOURCE_UTF8_INVALID") from exc
        _require(size <= MAX_FILE_BYTES, "SYMBOL_SOURCE_FILE_BUDGET")
        total += size
    _require(total <= MAX_SOURCE_BYTES, "SYMBOL_SOURCE_TOTAL_BUDGET")
    _require(scan is None or isinstance(scan, dict), "SYMBOL_SCAN_METADATA_INVALID")
    # Only known aggregate scanner fields enter evidence. Arbitrary caller data,
    # absolute paths or source text are not copied into the report.
    scan_info = {key: scan[key] for key in ("tracked_python_paths", "sources_read", "source_bytes", "scope", "partial")
                 if scan is not None and key in scan}
    if scan is not None and isinstance(scan.get("skipped"), dict):
        scan_info["skipped"] = {key: value for key, value in scan["skipped"].items()
                                if key in {"too_large", "total_budget", "not_utf8", "binary"} and
                                type(value) is int and value >= 0}
    indexed = []
    by_name = {}
    functions = []
    diagnostics = []
    ast_nodes = 0
    for path, source in sorted(sources.items()):
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always", SyntaxWarning)
                tree = ast.parse(source, filename=path)
            count = sum(1 for _ in ast.walk(tree))
            if count > MAX_AST_NODES_PER_FILE or ast_nodes + count > MAX_AST_NODES:
                diagnostics.append({"path": path, "reason": "AST_NODE_BUDGET", "partial": True})
                continue
            module = _index_module(commit, path, source, tree)
            found = [scope for scope in module.scopes if scope.kind in ("FunctionDef", "AsyncFunctionDef")]
            if len(functions) + len(found) > MAX_FUNCTIONS:
                diagnostics.append({"path": path, "reason": "FUNCTION_BUDGET", "partial": True})
                continue
            ast_nodes += count
            functions.extend(found)
            indexed.append(module)
            by_name.setdefault(_module_name(path), []).append(module)
            for warning in caught:
                diagnostics.append({"path": path, "reason": "SYNTAX_WARNING", "line": warning.lineno, "partial": False})
        except (SyntaxError, ValueError, RecursionError, MemoryError) as exc:
            diagnostics.append({"path": path, "reason": "AST_" + type(exc).__name__,
                                "line": getattr(exc, "lineno", None), "partial": True})
    matches = [scope for scope in functions if
               (selected_path is None or scope.module.path == selected_path) and
               (scope.qualname == selected_name or ("." not in selected_name and scope.node.name == selected_name)) and
               (selected_line is None or scope.reference["start"] == selected_line)]
    matches.sort(key=lambda scope: (scope.module.path, scope.reference["start"], scope.qualname))
    selected = matches[0] if len(matches) == 1 else None
    status = "COMPLETE" if selected else ("CHOICE_REQUIRED" if matches else "NOT_FOUND")
    outgoing, incoming, unknowns = [], [], []
    counts = {"call_sites": 0, "resolved_references": 0, "unresolved_calls": 0,
              "outgoing": 0, "incoming": 0, "selected_unknowns": 0, "call_sites_omitted": 0}
    unknown_reasons = {}

    def emit(scope, node, forced):
        counts["call_sites"] += 1
        if counts["call_sites"] > MAX_CALL_SITES:
            counts["call_sites_omitted"] += 1
            return
        target, resolution, reason = (None, None, forced) if forced else _resolve(scope, node.func, by_name)
        row = {"caller": dict(scope.reference), "call_site": _site(scope, node),
               "callee_name": _display_callee(node.func)}
        if target is None:
            reason = reason or "UNRESOLVED_STATIC_REFERENCE"
            counts["unresolved_calls"] += 1
            unknown_reasons[reason] = unknown_reasons.get(reason, 0) + 1
            if scope is selected:
                counts["selected_unknowns"] += 1
                if len(unknowns) < MAX_RESULT_ROWS:
                    unknowns.append({**row, "reason": reason})
        else:
            counts["resolved_references"] += 1
            edge = {**row, "callee": dict(target.reference), "resolution": resolution,
                    "runtime_execution": "NOT_PROVEN"}
            if scope is selected:
                counts["outgoing"] += 1
                if len(outgoing) < MAX_RESULT_ROWS:
                    outgoing.append(edge)
            if target is selected:
                counts["incoming"] += 1
                if len(incoming) < MAX_RESULT_ROWS:
                    incoming.append(edge)

    for module in indexed:
        for scope in module.scopes:
            calls = _Calls(scope, emit)
            for statement in scope.node.body:
                calls.visit(statement)
    sort_key = lambda row: (row["call_site"]["path"], row["call_site"]["line"], row["call_site"]["column"], row["callee_name"])
    outgoing.sort(key=sort_key)
    incoming.sort(key=sort_key)
    unknowns.sort(key=sort_key)
    truncated = {"candidates": max(0, len(matches) - MAX_CANDIDATES),
                 "outgoing": counts["outgoing"] - len(outgoing),
                 "incoming": counts["incoming"] - len(incoming),
                 "unknowns": counts["selected_unknowns"] - len(unknowns),
                 "call_sites": counts["call_sites_omitted"]}
    partial = bool(scan_info.get("partial")) or any(item.get("partial") for item in diagnostics) or any(truncated.values())
    return {"schema": SCHEMA, "status": status, "git_commit": commit,
            "goal_sha256": _sha(goal.encode("utf-8")), "selector": selector,
            "selected": dict(selected.reference) if selected else None,
            "candidates": [dict(scope.reference) for scope in matches[:MAX_CANDIDATES]],
            "outgoing": outgoing, "incoming": incoming, "unknown_outgoing": unknowns,
            "coverage": {"scan": scan_info, "source_files_supplied": len(sources),
                         "source_bytes_supplied": total, "parsed_files": len(indexed),
                         "functions_indexed": len(functions), "ast_nodes": ast_nodes,
                         "parse_diagnostics": diagnostics, "partial": partial,
                         "counts": counts, "unknown_reason_counts": dict(sorted(unknown_reasons.items())),
                         "candidate_matches": len(matches), "truncated": truncated,
                         "limits": {"files": MAX_FILES, "source_bytes": MAX_SOURCE_BYTES,
                                    "file_bytes": MAX_FILE_BYTES, "ast_nodes": MAX_AST_NODES,
                                    "ast_nodes_per_file": MAX_AST_NODES_PER_FILE,
                                    "functions": MAX_FUNCTIONS, "call_sites": MAX_CALL_SITES,
                                    "result_rows": MAX_RESULT_ROWS, "candidates": MAX_CANDIDATES},
                         "resolution_model": "STABLE_MODULE_FUNCTIONS_AND_EXPLICIT_IMPORTS_ONLY",
                         "limitations": ["STATIC_REFERENCES_DO_NOT_PROVE_RUNTIME_CALLS",
                                         "NO_FOUND_CALLERS_IS_NOT_PROOF_OF_NO_CALLERS",
                                         "DYNAMIC_DISPATCH_AND_EXTERNAL_BINDINGS_UNRESOLVED",
                                         "RUNTIME_AND_CROSS_MODULE_MONKEY_PATCHING_NOT_PROVEN_ABSENT",
                                         "DECORATOR_DEFAULT_CLASS_LAMBDA_COMPREHENSION_CONTEXTS_NOT_RESOLVED",
                                         "GENERIC_ANNOTATION_SCOPES_NOT_RESOLVED",
                                         "FUNCTION_AND_ASYNC_FUNCTION_SELECTION_ONLY"]},
            "source_binding": "PROVIDED_SOURCES_AT_DECLARED_COMMIT", "git_head_observed": False,
            "structural_only": True,
            "no_patch_or_apply": True, "repo_worktree_not_read": True,
            "source_code_executed": False, "source_text_included": False,
            "runtime_calls_proven": False}


def investigate_repository(repository: Path, goal: str, selector: str, notify=None, *, reader=None, expected_commit=None):
    """Read one bounded Git snapshot and recheck HEAD after static analysis."""
    _validate_goal(goal)
    _selector(selector)
    if expected_commit is not None:
        _require(isinstance(expected_commit, str) and bool(_SHA40.fullmatch(expected_commit)),
                 "SYMBOL_EXPECTED_COMMIT_INVALID")
    from .context_search import scan_head
    if reader is None:
        from .git_source import GitSourceReader, find_git
        reader = GitSourceReader(repository, find_git())
    commit, sources, scan = scan_head(reader, notify)
    _require(expected_commit is None or commit == expected_commit, "SYMBOL_EXPECTED_COMMIT_CHANGED")
    if notify:
        notify("Проверяю определения и прямые статические ссылки на одном Git HEAD…")
    report = investigate_sources(commit, sources, scan, goal, selector)
    _require(reader._sha("rev-parse", "--verify", "HEAD^{commit}") == commit,
             "SYMBOL_GIT_HEAD_CHANGED_DURING_ANALYSIS")
    report.update(source_binding="OBSERVED_GIT_HEAD_BLOBS", git_head_observed=True)
    return report


def format_investigation(report):
    _require(isinstance(report, dict) and report.get("schema") == SCHEMA, "SYMBOL_REPORT_SCHEMA_INVALID")
    lines = ["SkynetVS — исследование функции и её статических связей",
             "Git HEAD: " + report["git_commit"],
             "Область: committed main.py и modules/**/*.py в пределах сканирования.",
             "Связь в исходнике не доказывает исполнение вызова или причину ошибки."]
    if report["status"] == "CHOICE_REQUIRED":
        lines.append("Найдено несколько определений. Выбери точный путь, qualname и строку:")
        lines.extend(f"  {item['path']}::{item['qualname']}@{item['start']}" for item in report["candidates"])
    elif report["status"] == "NOT_FOUND":
        lines.append("Определение функции не найдено в прочитанной области. Классы сами по себе не выбираются.")
    else:
        item = report["selected"]
        lines += [f"Определение: {item['path']}::{item['qualname']} — строки {item['start']}–{item['end']}",
                  "SHA256 исходника: " + item["source_sha256"],
                  "Прямые статические ссылки из выбранной функции:"]
        lines += [f"  {row['call_site']['path']}:{row['call_site']['line']} → "
                  f"{row['callee']['path']}::{row['callee']['qualname']}:{row['callee']['start']}"
                  for row in report["outgoing"]] or ["  Разрешённых ссылок не найдено."]
        lines.append("Разрешённые ссылки на выбранную функцию:")
        lines += [f"  {row['caller']['path']}::{row['caller']['qualname']}:{row['call_site']['line']}"
                  for row in report["incoming"]] or ["  В прочитанной области не найдено. Это не доказывает отсутствие вызовов."]
        lines.append("Неразрешённые вызовы и контексты выбранной функции:")
        lines += [f"  {row['call_site']['path']}:{row['call_site']['line']} {row['callee_name']} — "
                  + _REASONS_RU.get(row['reason'], "статическая связь не установлена")
                  for row in report["unknown_outgoing"]] or ["  В учтённых AST-вызовах не обнаружены; динамические связи всё равно не доказаны."]
    coverage = report["coverage"]
    lines += [f"Прочитано файлов: {coverage['source_files_supplied']}; AST принят: {coverage['parsed_files']}; "
              f"определений функций: {coverage['functions_indexed']}.",
              f"Неразрешённых вызовов во всей прочитанной области: {coverage['counts']['unresolved_calls']}."]
    if coverage["partial"]:
        skipped = sum(coverage["scan"].get("skipped", {}).values())
        failed = [item for item in coverage["parse_diagnostics"] if item.get("partial")]
        clipped = sum(coverage["truncated"].values())
        lines.append(f"Результат неполный: пропущено источников {skipped}, файлов с непринятым AST {len(failed)}, "
                     f"строк или вызовов по лимиту {clipped}.")
        for item in failed[:5]:
            reason = ("превышен бюджет AST" if item["reason"] in {"AST_NODE_BUDGET", "FUNCTION_BUDGET"}
                      else "исходник не разобран в AST")
            lines.append(f"  {item['path']}:{item.get('line') or '?'} — {reason}")
    lines.append("Изменения и проверка поведения не выполнялись; применение не разрешено.")
    return "\n".join(lines)
