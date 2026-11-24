"""Bind a verified call site and check only immutable scalar facts in its own frame."""
import ast
import operator

import skynet_argument_flow as arguments
from skynet_control_conditions import Gap

UNKNOWN = object()
TYPES = {"int": int, "bool": bool, "str": str, "NoneType": type(None)}
COMPARE = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
           ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge}


def scalar(node):
    if isinstance(node, ast.Constant) and type(node.value) in TYPES.values():
        return node.value
    if (isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub)
            and isinstance(node.operand, ast.Constant) and type(node.operand.value) is int):
        return -node.operand.value
    return UNKNOWN


def formals(fn):
    args = fn.node.args
    return [*args.posonlyargs, *args.args, *args.kwonlyargs]


def stable(fn, name):
    definitions = [a for a in formals(fn) if a.arg == name]
    return bool(definitions and arguments.cli.calls.bindings(fn.node, name) == definitions)


def value(node, env):
    return env.get(node.id, UNKNOWN) if isinstance(node, ast.Name) else scalar(node)


def boolean(node, fn, env):
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        v = boolean(node.operand, fn, env)
        return UNKNOWN if v is UNKNOWN else not v
    if isinstance(node, ast.BoolOp):
        outcomes = [boolean(n, fn, env) for n in node.values]
        decisive = isinstance(node.op, ast.Or)
        if any(v is decisive for v in outcomes):
            return decisive
        return UNKNOWN if any(v is UNKNOWN for v in outcomes) else not decisive
    if isinstance(node, ast.Compare) and len(node.ops) == 1:
        compare = COMPARE.get(type(node.ops[0]))
        a, b = value(node.left, env), value(node.comparators[0], env)
        if compare and type(a) is type(b) and a is not UNKNOWN:
            try:
                return compare(a, b)
            except TypeError:
                return UNKNOWN
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "isinstance"
            and not node.keywords and len(node.args) == 2 and isinstance(node.args[1], ast.Name)):
        typename = node.args[1].id
        val = value(node.args[0], env)
        if typename in ("int", "bool", "str") and val is not UNKNOWN:
            for name in ("isinstance", typename):
                if arguments.cli.calls.bindings(fn.node, name) or not arguments.cli.calls.unique_binding(fn.tree, name, None):
                    return UNKNOWN
            return isinstance(val, TYPES[typename])
    v = value(node, env)
    return UNKNOWN if v is UNKNOWN else bool(v)


def verdict(term, fn, env, tests):
    if type(term) is bool:
        return term
    op, *parts = term
    if op == "test":
        node = tests.get(tuple(parts))
        return UNKNOWN if node is None else boolean(node, fn, env)
    if op == "not":
        v = verdict(parts[0], fn, env, tests)
        return UNKNOWN if v is UNKNOWN else not v
    if op == "and":
        a, b = (verdict(p, fn, env, tests) for p in parts)
        return False if a is False or b is False else True if a is True and b is True else UNKNOWN
    if op == "if":
        test, yes, no = (verdict(p, fn, env, tests) for p in parts)
        return yes if test is True else no if test is False else yes if yes is no else UNKNOWN
    # An iteration may not exist; a universal condition may be vacuously true.
    return UNKNOWN


def call_statement(site):
    # Reaching a statement does not imply evaluating a call under 'and', a
    # conditional expression, comprehension, lambda, or default argument.
    if arguments.cli.calls.bindings(site.caller.node, site.call.func.id):
        raise Gap("argument_unproven")
    for stmt in site.caller.node.body:
        for node in arguments.cli.flow.local_nodes(stmt):
            if isinstance(node, (ast.Expr, ast.Return, ast.Assign, ast.AnnAssign)) and node.value is site.call:
                return node
    raise Gap("conditional_expression")


def bind(site, env):
    call, fn = site.call, site.callee
    params = fn.node.args
    if (params.vararg or params.kwarg or any(isinstance(v, ast.Starred) for v in call.args)
            or any(v.arg is None for v in call.keywords) or len({v.arg for v in call.keywords}) != len(call.keywords)):
        raise Gap("argument_unproven")
    try:
        supplied = arguments.cli.calls.signature(fn.node).bind(
            *call.args, **{kw.arg:kw.value for kw in call.keywords}).arguments
    except (TypeError, ValueError) as exc:
        raise Gap("argument_unproven") from exc
    positional = params.posonlyargs + params.args
    defaults = {p.arg:v for p,v in zip(reversed(positional), reversed(params.defaults))}
    defaults.update({p.arg:v for p,v in zip(params.kwonlyargs, params.kw_defaults) if v is not None})
    rows, child_env = [], {}
    for p in formals(fn):
        default = p.arg not in supplied
        expr = defaults[p.arg] if default else supplied[p.arg]
        known = scalar(expr) if default else value(expr, env)
        rows.append((p.arg, ast.unparse(expr), default))
        if known is not UNKNOWN and stable(fn, p.arg):
            child_env[p.arg] = known
    return rows, child_env
