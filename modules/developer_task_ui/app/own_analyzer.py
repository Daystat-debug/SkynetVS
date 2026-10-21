"""SkynetVS own code analyzer M098: precise AST control flow, local feedback and ranker.

No third-party model/weights, network, source execution, proposed patch execution,
Git writes, or code mutation. The ranker only changes the ordering of findings.
An AST warning is NOT proof of a bug; the user must inspect each hypothesis.
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
import os
import re
import stat
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from .core import blob_oid, check_plain_path
from .self_review import GitHeadCatalog, MAX_FILE_BYTES, SelfReviewError

SCHEMA = 'SKYNETVS_OWN_ANALYZER_M097_V1'
FEEDBACK_SCHEMA = 'SKYNETVS_OWN_ANALYZER_FEEDBACK_V1'
RANKER_SCHEMA = 'SKYNETVS_OWN_ANALYZER_RANKER_V1'
MAX_SCAN_BYTES = 12 * 1024 * 1024
MAX_SCAN_FILES = 350
MAX_FINDINGS = 16
MAX_FEEDBACK_BYTES = 1024 * 1024
RULE_SCORES = {
    'mutable_default': .80, 'bare_except': .60, 'silent_broad_except': .57,
    'dynamic_eval': .92, 'shell_true': .91, 'blocking_async': .85,
    'tempfile_mktemp': .83, 'finally_control': .69, 'long_function': .38, 'large_module': .33,
}
SEVERITY = {
    'mutable_default': 'medium', 'bare_except': 'medium',
    'silent_broad_except': 'medium', 'dynamic_eval': 'high',
    'shell_true': 'high', 'blocking_async': 'high',
    'tempfile_mktemp': 'high', 'finally_control': 'medium', 'long_function': 'low', 'large_module': 'low',
}
RULE_EXPLANATIONS = {
    'mutable_default': ('Изменяемый объект в значении по умолчанию может сохранять состояние между вызовами.',
                        'Проверить контракт функции и при необходимости заменить аргумент на None с созданием объекта внутри.'),
    'bare_except': ('Перехват всех исключений, включая KeyboardInterrupt/SystemExit, может мешать корректному завершению.',
                    'Проверить ожидаемые ошибки и ограничить список перехватываемых исключений.'),
    'silent_broad_except': ('Широкое исключение подавляется без объяснения прямо в обработчике. Это может скрыть отказ.',
                            'Проверить, намеренный ли это отказ; добавить диагностический результат или ограничить перехват.'),
    'dynamic_eval': ('Исполнение выражений/текста как Python-кода создаёт риск при недоверенном входе.',
                     'Проверить происхождение аргумента и по возможности заменить на явный парсер данных.'),
    'shell_true': ('Запуск shell=True требует проверки всех аргументов и границы доверия.',
                   'Предпочесть массив аргументов и shell=False; проверить, нет ли данных пользователя в команде.'),
    'blocking_async': ('Синхронная блокирующая операция внутри async-функции может задерживать event loop.',
                       'Проверить маршрут исполнения; рассмотреть асинхронный API или отдельный worker.'),
    'tempfile_mktemp': ('tempfile.mktemp возвращает имя без атомарного резервирования; возможна гонка.',
                        'Использовать tempfile.NamedTemporaryFile или mkstemp с подходящими ограничениями.'),
    'finally_control': ('Оператор return/break/continue в finally может перекрыть ожидаемое исключение или поток управления.',
                        'Проверить ожидаемое поведение при сбое и перестроить завершение блока при необходимости.'),
    'long_function': ('Большая функция затрудняет адресное тестирование и анализ отдельных ветвей.',
                      'Выделить независимые части, не меняя контракт, и покрыть их регрессионными тестами.'),
    'large_module': ('Очень большой модуль усложняет навигацию и изоляцию регрессионных тестов.',
                     'Проверить естественные границы ответственности, не разбивая код ради размера.'),
}
FEATURES = tuple(['severity_high', 'severity_medium', 'goal_related',
                  'area_runtime', 'area_developer', 'area_voice', 'area_ui',
                  'large_function'] + ['rule_' + name for name in RULE_SCORES])
LABELS = {'confirmed', 'false_positive', 'low_priority'}


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _area(path: str) -> str:
    if path == 'main.py' or path.startswith('modules/runtime') or path.startswith('modules/action') or path.startswith('modules/command'):
        return 'runtime'
    if path.startswith('modules/developer_task_ui/'):
        return 'ui'
    if path.startswith('modules/developer/'):
        return 'developer'
    if any(token in path for token in ('voice', 'audio', 'nlu', 'learning', 'speech', 'tts', 'stt')) or path.startswith('train/'):
        return 'voice'
    return 'other'


def _goal_related(path: str, goal: str) -> bool:
    goal = goal.casefold()
    domain = _area(path)
    if any(w in goal for w in ('голос', 'реч', 'nlu', 'обучен', 'звук')):
        return domain in {'voice', 'runtime'}
    if any(w in goal for w in ('developer', 'разработ', 'код', 'patch', 'изменен')):
        return domain in {'developer', 'ui'}
    if any(w in goal for w in ('интерфейс', 'окно', 'вкладк')):
        return domain == 'ui'
    return False


def _feature_vector(finding: dict[str, Any]) -> dict[str, float]:
    area = _area(finding['file'])
    return {key: float(
        (key == 'severity_high' and finding['severity'] == 'high') or
        (key == 'severity_medium' and finding['severity'] == 'medium') or
        (key == 'goal_related' and finding.get('goal_related') is True) or
        (key.startswith('area_') and key[5:] == area) or
        (key == 'large_function' and finding['rule_id'] == 'long_function') or
        (key == 'rule_' + finding['rule_id'])
    ) for key in FEATURES}


def _plain(path: Path, *, directory: bool) -> None:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0):
        raise SelfReviewError('Недопустимая ссылка в локальном хранилище анализатора.')
    if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        raise SelfReviewError('Неожиданный тип локального файла анализатора.')
    if not directory and info.st_nlink != 1:
        raise SelfReviewError('Неожиданная жёсткая ссылка в локальном хранилище анализатора.')


def user_analyzer_directory() -> Path:
    base = os.environ.get('LOCALAPPDATA', '')
    if not base or not Path(base).is_absolute():
        raise SelfReviewError('LOCALAPPDATA отсутствует: локальный ранжировщик недоступен.')
    root = Path(base)
    _plain(root, directory=True)
    for name in ('SkynetVS', 'DeveloperTask', 'Analyzer'):
        root = root / name
        root.mkdir(exist_ok=True)
        _plain(root, directory=True)
    return root


def _check_store(folder: Path) -> None:
    _plain(folder, directory=True)
    for name in ('feedback.jsonl', 'ranker.json'):
        p = folder / name
        if p.exists() or p.is_symlink():
            _plain(p, directory=False)


def _read_ranker(folder: Path) -> dict[str, Any] | None:
    _check_store(folder)
    p = folder / 'ranker.json'
    if not p.is_file():
        return None
    if p.stat().st_size > 32 * 1024:
        raise SelfReviewError('Повреждён файл ранжирования (размер).')
    try:
        obj = json.loads(p.read_text(encoding='utf-8'))
    except (UnicodeError, ValueError) as exc:
        raise SelfReviewError('Повреждён JSON ранжирования.') from exc
    weights = obj.get('weights') if isinstance(obj, dict) else None
    if not isinstance(obj, dict):
        raise SelfReviewError('Некорректный формат ранжировщика.')
    if obj.get('schema') != RANKER_SCHEMA or not isinstance(weights, dict) or set(weights) != set(FEATURES):
        raise SelfReviewError('Неверный формат обученных весов ранжировщика.')
    if any(type(v) not in (float, int) or not math.isfinite(v) or abs(v) > 10 for v in weights.values()):
        raise SelfReviewError('Некорректные веса ранжировщика.')
    if type(obj.get('bias')) not in (float, int) or not math.isfinite(obj['bias']) or abs(obj['bias']) > 10:
        raise SelfReviewError('Некорректное смещение ранжировщика.')
    return obj


def _predict(finding: dict[str, Any], model: dict[str, Any] | None) -> float:
    base = RULE_SCORES[finding['rule_id']] + (.14 if finding.get('goal_related') else 0)
    if model is None:
        return min(.99, base)
    x = _feature_vector(finding)
    z = model['bias'] + sum(model['weights'][key] * x[key] for key in FEATURES)
    z = max(-20, min(20, z))
    probability = 1. / (1. + math.exp(-z))
    # Conservative blending: fewer labels do not let the ranker dominate AST evidence.
    return round(.75 * min(.99, base) + .25 * probability, 5)


def _is_broad(typ: ast.AST | None) -> bool:
    if typ is None:
        return False
    if isinstance(typ, ast.Name):
        return typ.id in {'Exception', 'BaseException'}
    if isinstance(typ, ast.Attribute):
        return typ.attr in {'Exception', 'BaseException'}
    if isinstance(typ, ast.Tuple):
        return any(_is_broad(x) for x in typ.elts)
    return False


def _qualname(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _qualname(node.value)
        return (base + '.' + node.attr) if base else None
    return None


def _direct_async_calls(node: ast.AsyncFunctionDef):
    """Iterate async function body, ignoring nested function and class bodies."""
    pending = list(node.body)
    while pending:
        current = pending.pop()
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        if isinstance(current, ast.Call):
            yield current
        pending.extend(ast.iter_child_nodes(current))



def _controls_exiting_finally(statements: list[ast.stmt]) -> list[ast.stmt]:
    """Find only control transfers crossing this particular finally boundary.

    A break/continue targeting a loop *declared inside* the finally suite
    does not exit that finally. Loops' else suites do not belong to their
    break/continue target. Nested functions/classes are distinct scopes.
    Nested finally suites are checked independently, avoiding duplicate rows.
    """
    found: list[ast.stmt] = []

    def walk(node: ast.AST, local_loops: int) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            return
        if isinstance(node, ast.Return):
            found.append(node)
            return
        if isinstance(node, (ast.Break, ast.Continue)):
            if local_loops == 0:
                found.append(node)
            return
        if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            for field, value in ast.iter_fields(node):
                if field == 'body':
                    for child in value:
                        walk(child, local_loops + 1)
                elif field == 'orelse':
                    # 'for ... else' executes after the for-loop has exited.
                    for child in value:
                        walk(child, local_loops)
                elif isinstance(value, ast.AST):
                    walk(value, local_loops)
            return
        if isinstance(node, (ast.Try, ast.TryStar)):
            for field, value in ast.iter_fields(node):
                if field == 'finalbody':
                    # The nested finally is evaluated by its own Try node.
                    continue
                if isinstance(value, list):
                    for child in value:
                        if isinstance(child, ast.AST):
                            walk(child, local_loops)
                elif isinstance(value, ast.AST):
                    walk(value, local_loops)
            return
        for child in ast.iter_child_nodes(node):
            walk(child, local_loops)

    for statement in statements:
        walk(statement, 0)
    return found


def _next_statement(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> ast.stmt | None:
    """Return next statement in the same lexical suite, if any."""
    parent = parents.get(node)
    if parent is None:
        return None
    for _, value in ast.iter_fields(parent):
        if isinstance(value, list):
            for index, candidate in enumerate(value[:-1]):
                if candidate is node and isinstance(value[index + 1], ast.stmt):
                    return value[index + 1]
    return None


def _owner_function(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> str:
    while node in parents:
        node = parents[node]
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return node.name
        if isinstance(node, ast.ClassDef):
            return ''
    return ''


def _contextual_broad_except_reason(
    node: ast.Try | ast.TryStar, parents: dict[ast.AST, ast.AST]
) -> str | None:
    """Conservatively recognize three explicit best-effort patterns.

    An unfamiliar handler is still reported. No source code is executed.
    Context exclusions are counted in the report for transparency.
    """
    after = _next_statement(node, parents)
    fn = _owner_function(node, parents).casefold()
    if isinstance(after, ast.Return) and isinstance(after.value, ast.Constant):
        message = after.value.value
        if isinstance(message, str) and any(term in message.casefold() for term in (
            'не получилось', 'не удалось', 'ошиб', 'недоступ',
            'failed', 'failure', 'error', 'unavailable', 'unable', 'could not'
        )):
            return 'explicit_failure_response'
    if len(node.body) != 1 or not isinstance(node.body[0], ast.Expr):
        return None
    call = node.body[0].value
    if not isinstance(call, ast.Call):
        return None
    qual = (_qualname(call.func) or '').casefold()
    if (fn.startswith('_safe_') and ('log' in fn or 'telemetry' in fn or 'event' in fn)
            and 'logger' in qual and qual.rsplit('.', 1)[-1] in {'event', 'log', 'info', 'warning', 'error'}):
        return 'best_effort_diagnostics'
    if (fn.startswith('_safe_') and isinstance(call.func, ast.Name)
            and qual.endswith('_func') and any(part in qual for part in ('print', 'event', 'log', 'telemetry'))):
        return 'best_effort_diagnostics_callback'
    if not (fn.startswith('cancel_') or '_cancel_' in fn) or not qual.endswith('.cancel'):
        return None
    subject = _qualname(call.func.value) if isinstance(call.func, ast.Attribute) else None
    if (isinstance(after, ast.Assign) and isinstance(after.value, ast.Constant)
            and after.value.value is None and subject is not None
            and any(_qualname(t) == subject for t in after.targets)):
        return 'best_effort_cancel_with_state_reset'
    return None


def _issue(issues: list[dict[str, Any]], rule: str, path: str, line: int,
           lines: list[str], goal: str, commit: str, detail: str = '') -> None:
    if not 1 <= line <= len(lines):
        return
    quote = lines[line - 1].strip()
    if not quote:
        return
    quote = quote[:180]
    identification = f'{commit}\x00{rule}\x00{path}\x00{line}\x00{quote}'.encode('utf-8')
    issue_id = _digest(identification)
    problem, improvement = RULE_EXPLANATIONS[rule]
    if detail:
        problem += ' ' + detail
    issues.append({
        'id': issue_id, 'rule_id': rule, 'file': path, 'line': line,
        'quote': quote, 'severity': SEVERITY[rule], 'problem': problem,
        'improvement': improvement, 'goal_related': _goal_related(path, goal),
        'line_anchor_checked': True, 'semantic_claim_verified': False,
        'features': {},
    })


def _inspect_file(issues: list[dict[str, Any]], path: str, text: str,
                  tree: ast.Module, goal: str, commit: str) -> tuple[int, int, list[dict[str, Any]]]:
    lines = text.splitlines()
    function_count = 0
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    contextual_exclusions: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function_count += 1
            for default in node.args.defaults + [x for x in node.args.kw_defaults if x is not None]:
                if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    _issue(issues, 'mutable_default', path, node.lineno, lines, goal, commit)
                    break
            length = getattr(node, 'end_lineno', node.lineno) - node.lineno + 1
            if length >= 190 and not node.name.startswith('build_'):
                _issue(issues, 'long_function', path, node.lineno, lines, goal, commit,
                       f'Длина по AST: {length} строк.')
            if isinstance(node, ast.AsyncFunctionDef):
                for call in _direct_async_calls(node):
                    qual = _qualname(call.func)
                    if qual in {'time.sleep', 'subprocess.run', 'subprocess.check_call',
                                'subprocess.check_output', 'urllib.request.urlopen', 'requests.get',
                                'requests.post'}:
                        _issue(issues, 'blocking_async', path, call.lineno, lines, goal, commit)
        elif isinstance(node, ast.ExceptHandler):
            if node.type is None:
                _issue(issues, 'bare_except', path, node.lineno, lines, goal, commit)
        elif isinstance(node, ast.Call):
            qual = _qualname(node.func)
            if qual in {'eval', 'exec', 'builtins.eval', 'builtins.exec'}:
                _issue(issues, 'dynamic_eval', path, node.lineno, lines, goal, commit)
            if qual in {'tempfile.mktemp'}:
                _issue(issues, 'tempfile_mktemp', path, node.lineno, lines, goal, commit)
            if qual in {'subprocess.run', 'subprocess.Popen', 'subprocess.call',
                        'subprocess.check_output', 'subprocess.check_call'}:
                if any(k.arg == 'shell' and isinstance(k.value, ast.Constant)
                       and k.value.value is True for k in node.keywords):
                    _issue(issues, 'shell_true', path, node.lineno, lines, goal, commit)
        elif isinstance(node, (ast.Try, ast.TryStar)):
            reason = _contextual_broad_except_reason(node, parents)
            for handler in node.handlers:
                if (_is_broad(handler.type) and len(handler.body) == 1
                        and isinstance(handler.body[0], ast.Pass)):
                    if reason:
                        contextual_exclusions.append({'file': path, 'line': handler.lineno, 'reason': reason})
                    else:
                        _issue(issues, 'silent_broad_except', path, handler.lineno, lines, goal, commit)
            if node.finalbody:
                for control in _controls_exiting_finally(node.finalbody):
                    _issue(issues, 'finally_control', path, control.lineno, lines, goal, commit)
    if len(lines) >= 1200:
        first = next((i + 1 for i, line in enumerate(lines) if line.strip().startswith(('class ', 'def ', 'async def '))), 1)
        _issue(issues, 'large_module', path, first, lines, goal, commit,
               f'Объём модуля: {len(lines)} строк.')
    return len(lines), function_count, contextual_exclusions


def _module_key(path: str) -> str:
    parts = path[:-3].split('/')
    if parts[-1] == '__init__':
        parts.pop()
    return '.'.join(parts)


def _imports(path: str, tree: ast.Module, known: set[str]) -> set[str]:
    own = _module_key(path)
    package = own if path.endswith('/__init__.py') else own.rsplit('.', 1)[0] if '.' in own else ''
    results: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in known and alias.name != own:
                    results.add(alias.name)
        if isinstance(node, ast.ImportFrom):
            if node.level:
                ancestors = package.split('.') if package else []
                if node.level > len(ancestors):
                    continue
                anchor = '.'.join(ancestors[:len(ancestors) - node.level + 1])
                mod = '.'.join(x for x in (anchor, node.module or '') if x)
            else:
                mod = node.module or ''
            variants = [mod] + [mod + '.' + alias.name for alias in node.names if alias.name != '*']
            for value in variants:
                if value in known and value != own:
                    results.add(value)
    return results


def _feature_ideas(report: dict[str, Any], large_functions: list[dict[str, Any]]) -> list[dict[str, str]]:
    ideas = []
    matches = [f for f in report['findings'] if f['rule_id'] == 'silent_broad_except']
    if matches:
        issue = matches[0]
        ideas.append({'title': 'Диагностика подавленных ошибок без изменения логики команд',
                      'evidence': f"{issue['file']}:{issue['line']} — {issue['quote']}",
                      'why': 'Есть широкие обработчики, которые не сообщают о причине отказа; часть может быть намеренной.',
                      'first_step': 'Выбрать один путь ошибки, описать ожидаемый отказ и добавить проверяемую телеметрию.'})
    if large_functions:
        f = large_functions[0]
        ideas.append({'title': 'Уменьшение сложности критичных обработчиков',
                      'evidence': f"{f['file']}:{f['line']} — {f['quote']}",
                      'why': 'Выявлена крупная функция; изменение отдельных ветвей сложнее проверять регрессией.',
                      'first_step': 'Построить карту ветвей, закрепить тесты и выделить один изолируемый компонент.'})
    if report['metrics']['internal_import_edges'] >= 10:
        ideas.append({'title': 'Карта влияния изменений для Developer Task',
                      'evidence': f"AST: {report['metrics']['internal_import_edges']} внутренних импортов в {report['metrics']['parsed_files']} файлах", 
                      'why': 'Карта зависимостей помогает выбирать регрессионные тесты при будущих одобренных патчах.',
                      'first_step': 'Построить read-only список непосредственных зависимостей выбранного файла и его пользователей.'})
    return ideas[:3]


def analyze_repository(repository: Path, goal: str, *,
                       notify: Callable[[str], None] | None = None,
                       data_directory: Path | None = None) -> dict[str, Any]:
    if not isinstance(goal, str) or not 12 <= len(goal.strip()) <= 600:
        raise SelfReviewError('Опиши цель анализа (12–600 символов).')
    goal = goal.strip()
    notify = notify or (lambda _: None)
    notify('Читаю закреплённый Git HEAD и строю AST без запуска кода…')
    catalog = GitHeadCatalog(repository)
    paths = catalog.paths()
    if len(paths) > MAX_SCAN_FILES:
        raise SelfReviewError('Для собственного анализатора слишком много файлов (лимит 350).')
    total = 0
    issues: list[dict[str, Any]] = []
    trees: dict[str, ast.Module] = {}
    meta: list[dict[str, str]] = []
    skipped = []
    total_functions = 0
    total_lines = 0
    contextual_exclusions: list[dict[str, Any]] = []
    for path in paths:
        oid = catalog.blobs[path]
        content = catalog.reader._run('cat-file', 'blob', oid, limit=MAX_FILE_BYTES + 1)
        if len(content) > MAX_FILE_BYTES or b'\x00' in content or blob_oid(content) != oid:
            skipped.append({'path': path, 'reason': 'binary_or_size_limit'})
            continue
        total += len(content)
        if total > MAX_SCAN_BYTES:
            raise SelfReviewError('Общий лимит чтения Git-исходников превышен.')
        try:
            source = content.decode('utf-8', 'strict')
            tree = ast.parse(source, filename=path)
        except (UnicodeError, SyntaxError):
            skipped.append({'path': path, 'reason': 'utf8_or_syntax'})
            continue
        lines, functions, explained = _inspect_file(issues, path, source, tree, goal, catalog.commit)
        contextual_exclusions.extend(explained)
        total_lines += lines
        total_functions += functions
        trees[path] = tree
        meta.append({'path': path, 'blob_oid': oid, 'sha256': _digest(content)})
    if not trees:
        raise SelfReviewError('Нет исходников Python, которые можно прочитать и разобрать.')
    known = {_module_key(p): p for p in trees}
    graph = {key: sorted(_imports(path, trees[path], set(known))) for key, path in known.items()}
    edges = sum(len(v) for v in graph.values())
    catalog.verify_head()
    notify('AST построен, проверяю привязки к строкам и приоритеты…')
    folder = data_directory if data_directory is not None else user_analyzer_directory()
    model = _read_ranker(folder)
    for finding in issues:
        finding['priority_score'] = round(_predict(finding, model), 5)
        finding['ranking_mode'] = 'feedback_model_blended' if model else 'fixed_ast_baseline'
        finding['features'] = _feature_vector(finding)
    issues.sort(key=lambda x: (-x['priority_score'], x['file'], x['line'], x['rule_id']))
    chosen = []
    per_file = Counter()
    per_rule = Counter()
    quotas = {'silent_broad_except': 4, 'long_function': 5, 'large_module': 3,
              'finally_control': 4}
    for f in issues:
        if per_file[f['file']] >= 2 or per_rule[f['rule_id']] >= quotas.get(f['rule_id'], 5):
            continue
        chosen.append(f)
        per_file[f['file']] += 1
        per_rule[f['rule_id']] += 1
        if len(chosen) >= MAX_FINDINGS:
            break
    findings = chosen
    report = {
        'schema': SCHEMA,
        'status': 'AST_ANALYSIS_COMPLETE_FINDINGS_REQUIRE_REVIEW',
        'git_commit': catalog.commit, 'git_tree': catalog.tree,
        'engine': 'SkynetVS AST + local feedback ranking',
        'model_trained': model is not None,
        'goal': goal,
        'metrics': {'indexed_paths': len(paths), 'parsed_files': len(trees),
                    'scanned_source_bytes': total, 'scanned_source_lines': total_lines,
                    'functions': total_functions, 'internal_import_edges': edges,
                    'candidates_total': len(issues), 'shown_findings': len(findings),
                    'contextual_exclusions': len(contextual_exclusions),
                    'skipped_files': skipped[:30], 'unreported_skipped_count': max(0, len(skipped) - 30)},
        'findings': findings,
        'feature_ideas': [],
        'contextual_exclusions': contextual_exclusions[:30],
        'no_patch_applied': True, 'git_writes': False, 'source_code_executed': False,
        'source_files_written': 0, 'network_requests': 0, 'neural_language_model_used': False,
        'semantic_claims_not_proven': True,
    }
    report['feature_ideas'] = _feature_ideas(report, [f for f in issues if f['rule_id'] == 'long_function'])
    catalog.verify_head()
    notify('Анализ завершён; изменения кода и сетевые запросы не выполнялись.')
    return report


def format_own_report(report: dict[str, Any]) -> str:
    if report.get('schema') != SCHEMA:
        raise SelfReviewError('Неверный формат отчёта собственного анализатора.')
    m = report['metrics']
    out = ['SkynetVS — собственный анализатор кода (M098: контекстные правила)',
           'Это AST + правила + обучаемое ранжирование, не генеративная LLM.',
           'Git HEAD: ' + report['git_commit'], 'Цель: ' + report['goal'],
           f"Прочитано: {m['parsed_files']} файлов, {m['scanned_source_lines']} строк, {m['functions']} функций.",
           f"Внутренние импорты: {m['internal_import_edges']}; потенциальных замечаний: {m['candidates_total']}.",
           f"Контекстно объяснённых и снятых широких перехватов: {m.get('contextual_exclusions', 0)}.",
           'Ранжирование: ' + ('обученные оценки + AST baseline' if report['model_trained'] else 'только AST baseline'),
           'ВАЖНО: находки являются гипотезами; наличие строки не доказывает ошибку.', '', 'Замечания:']
    for index, f in enumerate(report['findings'], 1):
        out.extend([f"{index}. [{f['severity']}, приоритет={f['priority_score']:.2f}] {f['file']}:{f['line']} ({f['rule_id']})",
                    '   Основание: ' + f['quote'], '   Возможная проблема: ' + f['problem'],
                    '   Что проверить: ' + f['improvement']])
    if not report['findings']:
        out.append('По включённым AST-правилам замечаний не найдено.')
    out.append('')
    out.append('Предложения для дальнейшей проверки (не сгенерированы языковой моделью):')
    for index, f in enumerate(report['feature_ideas'], 1):
        out.extend([f"{index}. {f['title']}", '   Основание: ' + f['evidence'],
                    '   Возможная польза: ' + f['why'], '   Первый шаг: ' + f['first_step']])
    if not report['feature_ideas']:
        out.append('Нет обоснованных предложений по включённым признакам.')
    out.append('Ничего не применено, не выполнено, не обучено автоматически и не отправлено в сеть.')
    return '\n'.join(out) + '\n'


def save_own_report(store: Any, report: dict[str, Any]) -> Path:
    folder = store._folder('own_analysis_')
    store.write(folder, 'M097_OwnAnalysis.json',
                (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    store.write(folder, 'M097_OwnAnalysis.txt', format_own_report(report).encode('utf-8'))
    return folder


def save_feedback(folder: Path, report: dict[str, Any], finding_id: str, label: str) -> Path:
    if report.get('schema') != SCHEMA or label not in LABELS or not re.fullmatch('[0-9a-f]{64}', finding_id):
        raise SelfReviewError('Некорректное подтверждение находки.')
    finding = next((row for row in report.get('findings', []) if row.get('id') == finding_id), None)
    if not finding or set(finding.get('features', {})) != set(FEATURES):
        raise SelfReviewError('Находка не принадлежит открытому отчёту.')
    _check_store(folder)
    path = folder / 'feedback.jsonl'
    if path.exists() and path.stat().st_size > MAX_FEEDBACK_BYTES - 4096:
        raise SelfReviewError('Локальная история оценок достигла ограничения по размеру.')
    row = {
        'schema': FEEDBACK_SCHEMA, 'id': finding['id'], 'label': label,
        'file': finding['file'], 'rule_id': finding['rule_id'], 'features': finding['features'],
        'git_commit': report['git_commit'], 'timestamp': int(time.time()),
    }
    encoded = (json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n').encode('utf-8')
    # Writes only to the fixed user-data file. No project changes. Refuse links.
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
    if hasattr(os, 'O_NOFOLLOW'):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        _plain(path, directory=False)
        with os.fdopen(fd, 'ab', closefd=False) as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(fd)
    return path


def _load_feedback(folder: Path) -> list[dict[str, Any]]:
    _check_store(folder)
    p = folder / 'feedback.jsonl'
    if not p.exists():
        return []
    if p.stat().st_size > MAX_FEEDBACK_BYTES:
        raise SelfReviewError('История оценок превышает разрешённый объём.')
    newest = {}
    try:
        for line in p.read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            if (row.get('schema') != FEEDBACK_SCHEMA or row.get('label') not in LABELS
                or not re.fullmatch('[0-9a-f]{64}', row.get('id', ''))
                or not isinstance(row.get('file'), str) or not isinstance(row.get('features'), dict)
                or set(row['features']) != set(FEATURES)
                or any(type(row['features'][k]) not in (int, float) or row['features'][k] not in (0, 1)
                       for k in FEATURES)):
                raise ValueError('Invalid feedback record')
            newest[row['id']] = row
    except (UnicodeError, ValueError, AttributeError, TypeError) as exc:
        raise SelfReviewError('История оценок повреждена: обучение остановлено без записи.') from exc
    return list(newest.values())


def train_ranker(folder: Path) -> dict[str, Any]:
    """Tiny logistic ranker trained from scratch. Never claimed as a code LLM."""
    rows = _load_feedback(folder)
    positives = [x for x in rows if x['label'] == 'confirmed']
    negatives = [x for x in rows if x['label'] != 'confirmed']
    distinct_files = len({x['file'] for x in rows})
    distinct_rules = len({x['rule_id'] for x in rows})
    if len(rows) < 20 or len(positives) < 5 or len(negatives) < 5 or distinct_files < 3 or distinct_rules < 2:
        return {'status': 'NOT_ENOUGH_HUMAN_FEEDBACK', 'total': len(rows),
                'confirmed': len(positives), 'not_confirmed': len(negatives),
                'files': distinct_files, 'rules': distinct_rules, 'weights_written': False,
                'needed': '>=20 unique, >=5 each class, >=3 files, >=2 rules'}
    weights = {name: 0. for name in FEATURES}
    bias = 0.
    # Deterministic full-batch gradient descent with L2 regularization.
    ordered = sorted(rows, key=lambda r: r['id'])
    for _ in range(320):
        gradients = {key: 0. for key in FEATURES}
        gb = 0.
        for row in ordered:
            features = row['features']
            z = max(-20, min(20, bias + sum(weights[k] * features[k] for k in FEATURES)))
            error = (1 / (1 + math.exp(-z))) - float(row['label'] == 'confirmed')
            gb += error
            for k in FEATURES:
                gradients[k] += error * features[k]
        bias -= .18 * gb / len(ordered)
        for k in FEATURES:
            weights[k] -= .18 * (gradients[k] / len(ordered) + .12 * weights[k])
    model = {'schema': RANKER_SCHEMA, 'weights': {k: round(v, 6) for k, v in weights.items()},
             'bias': round(bias, 6), 'unique_labels': len(rows), 'positive_labels': len(positives),
             'source': 'user-confirmed feedback only; zero-initialized weights',
             'evaluation': 'No independent held-out accuracy claimed',
             'neural_language_model': False}
    raw = (json.dumps(model, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    _check_store(folder)
    dest = folder / 'ranker.json'
    temporary = folder / ('.ranker_' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('xb') as f:
            f.write(raw); f.flush(); os.fsync(f.fileno())
        # Refuse replacing a link even if it was swapped after the first check.
        _check_store(folder)
        os.replace(temporary, dest)
    finally:
        if temporary.exists():
            temporary.unlink()
    return {'status': 'OWN_RANKER_TRAINED_LOCAL', 'total': len(rows),
            'confirmed': len(positives), 'not_confirmed': len(negatives),
            'files': distinct_files, 'rules': distinct_rules, 'weights_written': True,
            'neural_language_model': False, 'holdout_accuracy_measured': False}
