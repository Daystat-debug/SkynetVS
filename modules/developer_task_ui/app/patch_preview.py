"""Strict one-file unified-diff preview. Never writes or executes proposed source.

This is a UI-only, in-memory text applicability + AST parse gate. It is NOT
Git apply/check, py_compile, DTR-B rehearsal, a sandbox or authorization.
"""
from __future__ import annotations

import ast
import hashlib
import re


class PatchPreviewError(ValueError):
    def __init__(self, code: str, explanation: str):
        super().__init__(explanation)
        self.code = code


_HUNK = re.compile(r"^@@ -(0|[1-9][0-9]*)(?:,([0-9]+))? \+(0|[1-9][0-9]*)(?:,([0-9]+))? @@(?: [^\r\n]{0,160})?\n$")
_INDEX = re.compile(r"^index [0-9a-f]{7,40}\.\.[0-9a-f]{7,40} 100644\n$")
_MAX_PATCH_BYTES = 65536
_MAX_LINES = 2500
_MAX_HUNKS = 32
_MAX_HUNK_LINES = 2200
_MAX_OUTPUT_BYTES = 65536


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _reject(code: str, detail: str) -> None:
    raise PatchPreviewError(code, detail)


def _reconstruct(original: bytes, patch_text: str, path: str) -> tuple[bytes, int, int, int]:
    if not isinstance(original, bytes) or not isinstance(patch_text, str) or not isinstance(path, str):
        _reject("INPUT_TYPE", "Неверный тип исходника, patch или пути.")
    # The accepted Git blob is the only preimage. Do not canonicalize its bytes.
    if not original or len(original) > _MAX_OUTPUT_BYTES or b'\0' in original or b'\r' in original or not original.endswith(b'\n') or original.startswith(b'\xef\xbb\xbf'):
        _reject("PREIMAGE_PROFILE", "Предпросмотр поддерживает UTF-8 Python с LF и завершающим LF, без BOM/NUL/CR; исходные байты не изменены.")
    try:
        original.decode('utf-8', 'strict')
        encoded = patch_text.encode('utf-8', 'strict')
    except UnicodeError:
        _reject("INVALID_UTF8", "Исходник или patch не являются корректным UTF-8.")
    if not (0 < len(encoded) <= _MAX_PATCH_BYTES) or b'\r' in encoded or b'\0' in encoded or not encoded.endswith(b'\n'):
        _reject("PATCH_ENCODING", "Нужен UTF-8 patch с LF и завершающим LF, без CR/NUL и не более 64 КиБ.")
    if not re.fullmatch(r'modules/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\.py', path):
        _reject("PATH_PROFILE", "Путь не соответствует узкому профилю интерфейса.")
    lines = patch_text.splitlines(keepends=True)
    if len(lines) > _MAX_LINES or len(lines) < 4:
        _reject("PATCH_SHAPE", "Неверное число строк в diff.")
    if lines[0] != f'diff --git a/{path} b/{path}\n':
        _reject("TARGET_MISMATCH", "diff --git обязан ссылаться ровно на выбранный файл в обеих частях.")
    i = 1
    if i < len(lines) and lines[i].startswith('index '):
        if not _INDEX.fullmatch(lines[i]):
            _reject("INDEX_PROFILE", "Допускается только обычная строка index ... 100644; её хеши не считаются проверенными.")
        i += 1
    if len(lines) < i + 3 or lines[i] != f'--- a/{path}\n' or lines[i+1] != f'+++ b/{path}\n':
        _reject("FILE_HEADERS", "Заголовки ---/+++ должны точно указывать выбранный файл.")
    i += 2
    old = original.splitlines(keepends=True)
    old_cursor = 0
    result: list[bytes] = []
    hunks = 0
    additions = removals = 0
    while i < len(lines):
        match = _HUNK.fullmatch(lines[i])
        if not match:
            _reject("HUNK_REQUIRED", f"Неожиданный заголовок/строка diff около строки {i + 1}.")
        i += 1
        hunks += 1
        if hunks > _MAX_HUNKS:
            _reject("HUNK_LIMIT", "Слишком много фрагментов для этого предварительного просмотра.")
        old_start = int(match[1]); old_count = int(match[2] if match[2] is not None else '1')
        new_start = int(match[3]); new_count = int(match[4] if match[4] is not None else '1')
        if old_start > len(old) + 1 or old_count > len(old) or old_count + new_count > _MAX_HUNK_LINES:
            _reject("HUNK_BOUNDS", "Фрагмент выходит за пределы исходного файла или лимита.")
        old_pos = old_start if old_count == 0 else old_start - 1
        if old_pos < old_cursor or old_pos > len(old) or (old_count and old_start == 0):
            _reject("HUNK_OVERLAP", "Пересекающиеся или неверно расположенные фрагменты.")
        result.extend(old[old_cursor:old_pos])
        expected_new_start = len(result) if new_count == 0 else len(result) + 1
        if expected_new_start != new_start:
            _reject("NEW_POSITION", "Неверная новая позиция фрагмента (hunk).")
        pos = old_pos
        old_seen = new_seen = 0
        while old_seen < old_count or new_seen < new_count:
            if i == len(lines):
                _reject("INCOMPLETE_HUNK", "Фрагмент оборван; строки не соответствуют счётчикам.")
            current = lines[i]
            i += 1
            if len(current) > 8192 or not current.endswith('\n'):
                _reject("HUNK_LINE_PROFILE", "Слишком длинная строка или нет завершающего LF.")
            kind = current[:1]
            payload = current[1:].encode('utf-8', 'strict')
            if kind in (' ', '-'):
                old_seen += 1
                if old_seen > old_count or pos >= len(old) or payload != old[pos]:
                    _reject("PREIMAGE_MISMATCH", "Строки удаления/контекста не совпадают побайтно с выбранным исходником.")
                pos += 1
                if kind == ' ':
                    new_seen += 1
                    if new_seen > new_count:
                        _reject("HUNK_COUNTS", "Неверный счётчик новых строк.")
                    result.append(payload)
                else:
                    removals += 1
            elif kind == '+':
                new_seen += 1
                if new_seen > new_count:
                    _reject("HUNK_COUNTS", "Слишком много добавленных строк.")
                result.append(payload)
                additions += 1
            else:
                _reject("HUNK_LINE", "Внутри hunk допускаются только пробел, '+' и '-' в начале строки; newline markers/метаданные не поддержаны.")
        old_cursor = pos
        if sum(len(x) for x in result) > _MAX_OUTPUT_BYTES:
            _reject("OUTPUT_LIMIT", "Результат превышает 64 КиБ.")
    if hunks == 0 or additions + removals == 0:
        _reject("NO_CHANGE", "Patch не содержит изменений.")
    result.extend(old[old_cursor:])
    updated = b''.join(result)
    if len(updated) > _MAX_OUTPUT_BYTES or not updated.endswith(b'\n') or b'\0' in updated or b'\r' in updated:
        _reject("OUTPUT_PROFILE", "Результат нарушает ограниченный UTF-8/LF профиль.")
    updated.decode('utf-8', 'strict')
    if updated == original:
        _reject("IDENTICAL_RESULT", "После разбора исходник не изменился.")
    return updated, hunks, additions, removals


def preview_patch_in_memory(*, original: bytes, patch_text: str, target_path: str,
                            request_fingerprint: str, response_sha256: str) -> dict:
    """Never persists new source. Response binding must be accepted BEFORE this call."""
    response = {
        'schema': 'SKYNETVS_DTR_PATCH_PREVIEW_V1',
        'target_path': target_path,
        'request_fingerprint': request_fingerprint,
        'response_sha256': response_sha256,
        'original_sha256': _sha256(original),
        'preview_status': 'PREVIEW_REJECTED', 'issue_code': None, 'message': '',
        'text_applicability': 'NOT_PROVEN', 'python_ast_parse': 'NOT_RUN',
        'proposed_sha256': None, 'hunks': 0, 'added_lines': 0, 'removed_lines': 0,
        'project_file_written': False, 'changed_code_executed': False,
        'git_diff_check': 'NOT_RUN', 'py_compile': 'NOT_RUN', 'pipeline_check': 'NOT_RUN',
        'behavior': 'NOT_TESTED', 'runtime_authorized': False, 'promotion_authorized': False,
        'installation_authorized': False, 'dtrb_rehearsal_completed': False,
        'os_sandbox_claimed': False,
    }
    try:
        updated, hunks, added, removed = _reconstruct(original, patch_text, target_path)
        response['text_applicability'] = 'EXACT_BYTE_IN_MEMORY_PASS'
        response['proposed_sha256'] = _sha256(updated)
        response['hunks'] = hunks
        response['added_lines'] = added
        response['removed_lines'] = removed
        try:
            ast.parse(updated.decode('utf-8'), filename='<DTR_in_memory_preview>', mode='exec', type_comments=True)
        except (SyntaxError, ValueError, RecursionError, MemoryError) as exc:
            response['preview_status'] = 'TEXT_APPLICABLE_AST_REJECTED'
            response['issue_code'] = 'PYTHON_PARSE_ERROR'
            response['python_ast_parse'] = 'REJECTED'
            if isinstance(exc, SyntaxError):
                response['message'] = f'Python AST отказ: строка {exc.lineno}, столбец {exc.offset}; {exc.msg}'[:480]
            else:
                response['message'] = 'Python AST не смог разобрать исходник: ' + type(exc).__name__
        else:
            response['preview_status'] = 'TEXT_APPLICABLE_AST_PASS_NOT_EXECUTABLE_CHECKS'
            response['python_ast_parse'] = 'PASS'
            response['message'] = 'Patch точно совпал с исходными строками и разобран Python AST в памяти. Это НЕ git_diff_check/py_compile/тест поведения.'
    except PatchPreviewError as exc:
        response['issue_code'] = exc.code
        response['message'] = str(exc)[:480]
    return response
