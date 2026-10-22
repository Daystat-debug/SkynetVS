"""M139: presentation-only AST definition-span correlation for existing M136/M137 reports.

Old M136 correlation remains unmodified. This layer adds one narrowly grounded relation:
a long_function rule at the beginning of the SAME M131 FunctionDef/AsyncFunctionDef
may cover a selected window inside that function. Scope overlap is NOT a bug,
exact-line match, tested fix, permission, or proof of a task-specific defect.

No Git/disk/network/process access, no source text or goal in receipts, no patch APIs.
"""
from __future__ import annotations

from typing import Any

SCHEMA = "SKYNETVS_M139_SCOPE_AWARE_CONTEXT_FINDINGS_V1"
LEGACY_SCHEMA = "SKYNETVS_M136_CONTEXT_FINDING_CORRELATION_V1"
EXACT = "LINE_INSIDE_SELECTED_WINDOW"
SCOPE = "LONG_FUNCTION_SCOPE_OVERLAP_NOT_LOCALIZED"
FILE = "SAME_FILE_ONLY_NOT_LOCALIZED"
OTHER = "NO_RELATION_TO_CONTEXT"
ORDER = (EXACT, SCOPE, FILE, OTHER)


class ScopeBridgeRefusal(ValueError):
    """Invalid, mismatched, or untrusted structural metadata."""


def _ensure(ok: bool, msg: str) -> None:
    if not ok:
        raise ScopeBridgeRefusal(msg)


def _scoped_window(w: Any, row: dict) -> bool:
    """Strictly scoped: ONLY long_function at definition start can match function body.

    A warning at the definition line is NOT evidence for a particular body window.
    Avoid counting arbitrary rule anchors and module-level warnings as localized.
    """
    if not isinstance(w, dict) or w.get('path') != row['path']:
        return False
    if row['rule_id'] != 'long_function' or w.get('kind') not in ('FunctionDef', 'AsyncFunctionDef'):
        return False
    start, end = w.get('start'), w.get('end')
    scope_start, scope_end = w.get('scope_start'), w.get('scope_end')
    if not all(type(i) is int for i in (start, end, scope_start, scope_end)):
        return False
    return (1 <= scope_start == row['line'] < start <= end <= scope_end <= 1_000_000
            and isinstance(w.get('qualname'), str) and bool(w['qualname'])
            and len(w['qualname']) <= 300)


def enrich_relationships(context: dict, base: dict) -> dict:
    """Enrich a *verified M136 result*. No additional source code is read.

    Only selected windows produced by M134/M131 are used. No text contents or
    match tokens are copied from the context into the result.
    """
    _ensure(isinstance(context, dict) and context.get('schema') ==
            'SKYNETVS_M134_READONLY_PROJECT_CONTEXT_V1', 'M139_CONTEXT_SCHEMA')
    _ensure(isinstance(base, dict) and base.get('schema') == LEGACY_SCHEMA,
            'M139_BASE_SCHEMA')
    _ensure(context.get('git_commit') == base.get('git_commit') and
            context.get('goal_sha256') == base.get('goal_sha256'), 'M139_STALE_CONTEXT')
    _ensure(context.get('no_patch_or_apply') is True and
            context.get('repo_worktree_not_read') is True and
            base.get('no_patch_or_apply') is True and
            base.get('approval_status') == 'NOT_AUTHORIZED', 'M139_PATCH_GATE')
    _ensure(base.get('current_head_rechecked') is False and
            base.get('source_text_included') is False,
            'M139_BASE_SAFETY_FLAGS')
    metadata = context.get('contexts_metadata')
    _ensure(isinstance(metadata, dict) and isinstance(metadata.get('8192'), dict),
            'M139_METADATA_SCHEMA')
    windows = metadata['8192'].get('ranges')
    _ensure(isinstance(windows, list) and len(windows) <= 24 and
            len(windows) == base.get('contexts_considered'), 'M139_WINDOW_COUNT')
    findings = base.get('findings')
    _ensure(isinstance(findings, list) and len(findings) <= 1000 and
            len(findings) == base.get('findings_considered'), 'M139_FINDING_COUNT')
    legacy = base.get('counts')
    _ensure(isinstance(legacy, dict) and sum(legacy.get(k, -10000) for k in
            (EXACT, FILE, OTHER)) == len(findings), 'M139_BASE_COUNTS')
    # No false scope match if the same path is attributed to different blobs.
    source_by_path = {}
    for w in windows:
        _ensure(isinstance(w, dict) and isinstance(w.get('path'), str) and
                isinstance(w.get('source_sha256'), str), 'M139_WINDOW_INVALID')
        path, source = w['path'], w['source_sha256']
        _ensure(path not in source_by_path or source_by_path[path] == source,
                'M139_INCONSISTENT_SOURCE')
        source_by_path[path] = source
    results = []
    seen = set()
    for row in findings:
        _ensure(isinstance(row, dict) and row.get('relationship') in (EXACT, FILE, OTHER)
                and type(row.get('line')) is int and isinstance(row.get('path'), str)
                and isinstance(row.get('rule_id'), str) and
                isinstance(row.get('finding_id'), str), 'M139_BASE_FINDING_INVALID')
        fid = row['finding_id']
        _ensure(fid not in seen, 'M139_FINDING_DUPLICATE')
        seen.add(fid)
        entry = dict(row)
        if row['relationship'] == FILE:
            indices = [i for i, w in enumerate(windows) if _scoped_window(w, row)]
            if indices:
                entry['relationship'] = SCOPE
                entry['window_indices'] = indices
        results.append(entry)
    counts = {key: sum(row['relationship'] == key for row in results) for key in ORDER}
    _ensure(sum(counts.values()) == len(results) and counts[EXACT] == legacy[EXACT]
            and counts[SCOPE] + counts[FILE] == legacy[FILE], 'M139_COUNT_DRIFT')
    results.sort(key=lambda row: (ORDER.index(row['relationship']), row['finding_index']))
    out = {k: v for k, v in base.items() if k not in ('schema', 'counts', 'findings')}
    out.update(schema=SCHEMA, counts=counts, legacy_line_only_counts=dict(legacy),
               findings=results, confidence='EXACT_LINE_OR_DEFINITION_SCOPE_HINT_NOT_BUG_PROOF',
               scope_restriction='LONG_FUNCTION_DEFINITION_ONLY',
               current_head_rechecked=False, no_patch_or_apply=True,
               source_text_included=False, approval_status='NOT_AUTHORIZED')
    return out


def format_task_summary(result: dict) -> str:
    _ensure(isinstance(result, dict) and result.get('schema') == SCHEMA and
            result.get('no_patch_or_apply') is True and
            result.get('approval_status') == 'NOT_AUTHORIZED', 'M139_SUMMARY_SCHEMA')
    c = result['counts']
    lines = [
        'SkynetVS — AST-находки относительно цели (только чтение)',
        'Git HEAD: ' + result['git_commit'],
        'Строка находки внутри окна: ' + str(c[EXACT]),
        'Предупреждение о ВСЕЙ функции, окно внутри неё: ' + str(c[SCOPE]),
        'Совпадает только файл: ' + str(c[FILE]),
        'Другие файлы / участки: ' + str(c[OTHER]),
        'Важно: предупреждение о длинной функции НЕ доказывает дефект в найденном окне.',
        'Обнаружение AST-правила НЕ доказывает баг и НЕ подтверждает исправление.',
        'Diff НЕ создан. Проверка и применение исправлений НЕ разрешены.',
    ]
    rows = result['findings']
    if c[EXACT] + c[SCOPE] + c[FILE] == 0:
        lines.append('Связанных AST-находок нет; найденный код может быть корректен.')
    # Prioritize relevant scope, don't bury the results in unrelated generic warnings.
    chosen = [r for r in rows if r['relationship'] != OTHER][:16]
    for row in chosen:
        line = f"{row['path']}:{row['line']} — {row['rule_id']} — {row['relationship']}"
        lines.append(line)
    if len(chosen) < c[EXACT] + c[SCOPE] + c[FILE]:
        lines.append('Дополнительные находки в тех же файлах не показаны.')
    if c[OTHER]:
        lines.append(f'Ещё {c[OTHER]} глобальных AST-предупреждений не относятся к выбранным окнам.')
    if result.get('analysis_goal_binding') != 'MATCHED_SHA256':
        lines.append('ВНИМАНИЕ: AST-отчёт не удостоверяет хеш цели; связь только вспомогательная.')
    return '\n'.join(lines)
