"""M100: narrow source-grounded patch proposal recipes (not a generative LLM).

No model, network, source execution or filesystem writes. A proposal is only
structured data bound to a checked Git HEAD snapshot. It is NOT approval to apply.
"""
from __future__ import annotations

import ast
import difflib
import hashlib
from typing import Any

from .core import SourceSnapshot, validate_target
from .own_analyzer import SCHEMA as ANALYZER_SCHEMA


class ProposalUnavailable(ValueError):
    pass


def _require(condition: bool, explanation: str) -> None:
    if not condition:
        raise ProposalUnavailable(explanation)


def _qualname(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _qualname(node.value)
        return base + "." + node.attr if base else None
    return None


def _call(node: ast.AST, name: str) -> bool:
    return isinstance(node, ast.Call) and _qualname(node.func) == name and not node.keywords


def _get_mute_fail_closed(source: bytes, lineno: int) -> tuple[bytes, str]:
    """Match nested GetMute->pass->GetMasterVolume guard, change one PASS to CONTINUE.

    No other except blocks or arbitrary source files are rewritten. Source is
    treated as data and parsed by ast.parse, never executed.
    """
    _require(source.endswith(b'\n') and b'\0' not in source and
             b'\r' not in source.replace(b'\r\n', b''),
             'Нужен UTF-8 исходник с завершающим LF/CRLF и без смешанных CR.')
    _require(len(source) <= 65536, 'Один исходный файл должен быть не больше 64 КиБ.')
    text = source.decode('utf-8', 'strict')
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text)
    matches: list[ast.Pass] = []

    for loop in ast.walk(tree):
        if not isinstance(loop, (ast.For, ast.AsyncFor)):
            continue
        for index, stmt in enumerate(loop.body[:-1]):
            if not isinstance(stmt, ast.Try) or len(stmt.handlers) != 1 or len(stmt.body) != 1:
                continue
            handler = stmt.handlers[0]
            if (handler.lineno != lineno or handler.name is not None or
                    not isinstance(handler.type, ast.Name) or handler.type.id != 'Exception' or
                    len(handler.body) != 1 or not isinstance(handler.body[0], ast.Pass)):
                continue
            cond = stmt.body[0]
            if (not isinstance(cond, ast.If) or len(cond.body) != 1 or
                    not isinstance(cond.body[0], ast.Continue) or cond.orelse or
                    not _call(cond.test, 'bool') or len(cond.test.args) != 1 or
                    not _call(cond.test.args[0], 'control.GetMute') or
                    cond.test.args[0].args):
                continue
            after = loop.body[index + 1]
            if not isinstance(after, ast.Try) or not any(
                    isinstance(x, ast.Call) and _call(x, 'control.GetMasterVolume') and not x.args
                    for s in after.body for x in ast.walk(s)):
                continue
            if not any(isinstance(x, ast.Call) and _qualname(x.func) == 'control.SetMasterVolume'
                       for x in ast.walk(loop)):
                continue
            matches.append(handler.body[0])
    _require(len(matches) == 1, 'Для выбранной находки не обнаружен один однозначный безопасный рецепт.')
    line = matches[0].lineno
    _require(1 <= line <= len(lines) and lines[line-1].lstrip().strip() == 'pass',
             'Исходная строка не содержит ожидаемый pass.')
    indent = lines[line-1][:-len(lines[line-1].lstrip())]
    modified = list(lines)
    modified[line-1] = indent + ('continue\r\n' if lines[line-1].endswith('\r\n') else 'continue\n')
    result = ''.join(modified).encode('utf-8')
    ast.parse(result.decode('utf-8'))
    _require(len(result) <= 65536 and result != source, 'Рецепт не привёл к допустимому изменению.')
    return result, 'skip_audio_session_if_mute_status_unavailable'


def propose_from_finding(report: dict[str, Any], finding: dict[str, Any],
                         source: SourceSnapshot) -> dict[str, str]:
    """Return a bounded proposal; never writes it or grants execution authority."""
    _require(isinstance(report, dict) and report.get('schema') == ANALYZER_SCHEMA,
             'Сначала выполни анализ собственным AST-движком.')
    _require(isinstance(finding, dict) and finding in report.get('findings', []),
             'Находка отсутствует в отчёте текущей сессии.')
    _require(report.get('git_commit') == source.base_commit and
             report.get('git_tree') == source.base_tree,
             'HEAD или дерево Git изменились с момента анализа. Повтори анализ.')
    _require(source.provenance.get('kind') == 'OBSERVED_COMMITTED_FILE' and
             source.provenance.get('current_git_head_observed') is True,
             'Нужен заново проверенный исходник Git, не восстановленный из внешнего файла.')
    path = finding.get('file')
    _require(isinstance(path, str), 'Неверный путь исходника.')
    validate_target(path)
    _require(path == source.path, 'Путь исходника не соответствует выбранной находке.')
    _require(finding.get('rule_id') == 'silent_broad_except',
             'Для этой категории пока нет проверенного рецепта автоматического изменения.')
    line = finding.get('line')
    _require(type(line) is int and line > 0, 'Неверный номер строки.')
    lines = source.content.decode('utf-8', 'strict').splitlines()
    _require(line <= len(lines), 'Строка вне исходника.')
    quote = lines[line-1].strip()[:180]
    _require(finding.get('quote') == quote and quote == 'except Exception:',
             'Цитата AST не совпадает с исходным кодом.')
    binding = (source.base_commit + '\0' + finding['rule_id'] + '\0' +
               path + '\0' + str(line) + '\0' + quote).encode('utf-8')
    _require(hashlib.sha256(binding).hexdigest() == finding.get('id'),
             'Идентификатор находки не соответствует закреплённому Git HEAD.')

    updated, recipe = _get_mute_fail_closed(source.content, line)
    before_lines = source.content.decode('utf-8').splitlines(keepends=True)
    after_lines = updated.decode('utf-8').splitlines(keepends=True)
    patch = ('diff --git a/' + path + ' b/' + path + '\n' +
             ''.join(difflib.unified_diff(before_lines, after_lines,
                    fromfile='a/'+path, tofile='b/'+path, n=3)))
    explanation = (
        'Собственный ограниченный рецепт SkynetVS (не LLM). При сбое GetMute() '
        'предлагается пропустить эту аудиосессию вместо продолжения к GetMasterVolume()/SetMasterVolume(). '
        'Плюс: не меняет громкость при неизвестном статусе mute. Минус: некоторые сессии '
        'перестанут приглушаться, если GetMute() недоступен. Это изменение поведения; '
        'Windows audio не тестировалось. Diff подготовлен как данные, код не применялся. '
        'Не разрешает execution, privileged boundary, promotion или автоматический rollback.')
    return {
        'recipe_id': recipe,
        'title': 'Консервативная обработка сбоя GetMute',
        'instruction': 'Рассмотреть консервативную обработку сбоя GetMute() у аудиосессии. '
                       'Оценить побочные эффекты для TTS и ducking. Не применять без решения пользователя.',
        'explanation': explanation,
        'patch_text': patch.replace('\r\n','\n'),
        'finding_id': finding['id'],
        'source_sha256': hashlib.sha256(source.content).hexdigest(),
        'proposed_sha256': hashlib.sha256(updated).hexdigest(),
        'approval_state': 'NOT_APPROVED',
        'semantic_claim_verified': 'false',
        'preview_kind': 'IN_MEMORY_AST_ONLY_NOT_DTRA',
        'line_ending_profile': ('CRLF' if b'\r\n' in source.content else 'LF'),
    }
