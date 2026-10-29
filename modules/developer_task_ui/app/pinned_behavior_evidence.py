"""M157: read-only correlation of the *exact* accepted M155/M156 pilot artifacts.

This is NOT an attestation, test executor, generic evidence validator, patch approval
or permission check. Incoming ZIP entries must match the exact previously-reviewed
artifact hashes; new trials need independent acceptance and a new protocol.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import stat
import zipfile

SCHEMA = 'SKYNETVS_M157_PINNED_PILOT_EVIDENCE_V1'
BASE_COMMIT = 'acdc176e6b064b44fd5cdd59bb95cecd66952f5e'
TARGET_PATH = 'modules/learning/voice_learning_phrase_lookup.py'
SOURCE_SHA256 = 'ff8d8cf6a2ac554196c9f9d75e0d36777ddbfd66236d53b8172ad6a4531266af'
CANDIDATE_SHA256 = 'd55b47aef89600fd7b69816cf82630ce7ffa5398c23d2659f83200c7435a703d'
DTR_RESPONSE_SHA256 = '60c072a9be030f7d918daa713a689402d3203f0f3b5838e6d2f7f2115a15cdcf'
EXPECTED = {
    'Core_BehaviorPlan.json': ('37c601b8b8a36f6b9ad94eef8fcd4994d8741232dd2d6d569888baa31f05afc4', 3814),
    'M156_Behavior_Result.json': ('3986cefba2d3694ba15ce7321ad3b6eecef674aa8a5d40ab280661cad2cf1df0', 6533),
    'M156_Callsite_Result.json': ('1b3929c498bc65771ab92089ebcd35db14472355817ace0662450861bf214d2c', 10206),
}
CASE_COUNTS = {'T001': 28, 'T002': 3, 'T003': 4, 'T004': 6}
CALLSITE_LINES = {'T002': ('load_approved_greetings', 83),
                  'T003': ('load_approved_greetings', 137),
                  'T004': ('ApprovedPhraseLookup.match', 177)}
MAX_ZIP_BYTES = 128 * 1024
MAX_RECEIPT_BYTES = 16 * 1024


class EvidenceRefused(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _require(ok, code):
    if not ok:
        raise EvidenceRefused(code)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            _require(key not in result, 'M157_JSON_DUPLICATE_KEY')
            result[key] = value
        return result
    def const(value):
        raise EvidenceRefused('M157_JSON_NONFINITE')
    try:
        value = json.loads(raw.decode('utf-8', 'strict'), object_pairs_hook=unique, parse_constant=const)
    except (ValueError, UnicodeError, TypeError, RecursionError) as exc:
        if isinstance(exc, EvidenceRefused):
            raise
        raise EvidenceRefused('M157_JSON_INVALID') from exc
    _require(type(value) is dict, 'M157_JSON_OBJECT_REQUIRED')
    return value


def _read_exact_bundle(blob):
    _require(type(blob) is bytes and 0 < len(blob) <= MAX_ZIP_BYTES, 'M157_ZIP_SIZE_OR_TYPE')
    try:
        with zipfile.ZipFile(io.BytesIO(blob), 'r') as archive:
            records = archive.infolist()
            _require(len(records) == len(EXPECTED), 'M157_ZIP_ENTRY_COUNT')
            _require(set(row.filename for row in records) == set(EXPECTED), 'M157_ZIP_ENTRY_SET')
            result = {}
            for row in records:
                expected_sha, expected_size = EXPECTED[row.filename]
                mode = (row.external_attr >> 16) & 0xffff
                _require(not row.is_dir() and not (row.flag_bits & 1) and not stat.S_ISLNK(mode),
                         'M157_ZIP_UNSAFE_MEMBER')
                _require(row.file_size == expected_size and row.compress_size <= MAX_ZIP_BYTES,
                         'M157_ZIP_MEMBER_SIZE')
                data = archive.read(row)
                _require(len(data) == expected_size and _sha(data) == expected_sha,
                         'M157_EVIDENCE_HASH_MISMATCH_' + row.filename)
                result[row.filename] = _json(data)
            return result
    except (zipfile.BadZipFile, RuntimeError, OSError, EOFError, ValueError, KeyError, MemoryError) as exc:
        if isinstance(exc, EvidenceRefused):
            raise
        raise EvidenceRefused('M157_ZIP_READ_REFUSED') from exc


def _validate_plan(plan):
    _require(plan.get('schema') == 'SKYNETVS_CORE_BEHAVIOR_PLAN_V1' and
             plan.get('status') == 'HYPOTHESES_AND_TEST_OBLIGATIONS_ONLY' and
             plan.get('base_commit') == BASE_COMMIT and
             plan.get('target_path') == TARGET_PATH and
             plan.get('selected_qualname') == 'normalize' and
             plan.get('response_sha256') == DTR_RESPONSE_SHA256 and
             plan.get('candidate_selected_ast_changed') is True and
             plan.get('changes_outside_selected') is False and
             plan.get('tests_executed') is False and
             plan.get('behavior_proven') is False and
             plan.get('apply_authorized') is False and
             plan.get('promotion_authorized') is False, 'M157_PLAN_BINDING_MISMATCH')
    rows = plan.get('test_obligations')
    _require(type(rows) is list and len(rows) == 4 and
             [r.get('case_id') for r in rows if type(r) is dict] == list(CASE_COUNTS),
             'M157_PLAN_OBLIGATIONS_MISMATCH')
    for row in rows:
        _require(row.get('execution') == 'NOT_RUN' and row.get('expected_result') is None and
                 row.get('result') == 'UNKNOWN', 'M157_PLAN_FALSE_EXECUTION')
    for row in rows[1:]:
        identifier = row['case_id']
        historical = row.get('historical_reference')
        _require(type(historical) is dict and
                 row.get('target') == CALLSITE_LINES[identifier][0] and
                 historical.get('line') == CALLSITE_LINES[identifier][1] and
                 historical.get('path') == TARGET_PATH and
                 historical.get('commit') == BASE_COMMIT and
                 historical.get('runtime_call_proven') is False,
                 'M157_PLAN_CALLSITE_BINDING_MISMATCH')


def _validate_fixed(fixed):
    _require(fixed.get('schema') == 'SKYNETVS_M156_BOUNDED_BEHAVIOR_EVIDENCE_V1' and
             fixed.get('status') == 'PILOT_FIXED_PAIR_BEHAVIOR_PASS' and
             fixed.get('base_commit') == BASE_COMMIT and
             fixed.get('target_path') == TARGET_PATH and
             fixed.get('scope') == 'EXACT_PINNED_NORMALIZE_PAIR_ONLY' and
             fixed.get('sha256', {}).get('source_sha256') == SOURCE_SHA256 and
             fixed.get('sha256', {}).get('candidate_sha256') == CANDIDATE_SHA256 and
             fixed.get('sha256', {}).get('response_sha256') == DTR_RESPONSE_SHA256 and
             fixed.get('sha256', {}).get('plan_sha256') == EXPECTED['Core_BehaviorPlan.json'][0] and
             fixed.get('git_writes') == 0 and fixed.get('patch_applied') is False and
             fixed.get('promotion_authorized') is False and
             fixed.get('general_behavior_equivalence_proven') is False,
             'M157_FIXED_BINDING_MISMATCH')
    oracle = fixed.get('independent_oracle')
    _require(type(oracle) is dict and oracle.get('fixture_count') == 28 and
             oracle.get('passed') == 28 and oracle.get('failed') == 0 and
             oracle.get('expected_values_authored_separately') is True,
             'M157_FIXED_ORACLE_MISMATCH')
    rows = oracle.get('cases')
    _require(type(rows) is list and len(rows) == 28 and
             len({r.get('case_id') for r in rows if type(r) is dict}) == 28 and
             all(type(r) is dict and r.get('passed') is True and
                 r.get('candidate') == r.get('expected') == r.get('original') for r in rows),
             'M157_FIXED_CASE_FAILURE')
    obligations = fixed.get('m155_obligations')
    _require(type(obligations) is list and len(obligations) == 4 and
             obligations[0].get('case_id') == 'T001' and
             obligations[0].get('fixtures') == 28 and
             obligations[0].get('status') == 'FIXED_PAIR_CASE_MATRIX_PASS' and
             all(r.get('status') == 'NOT_RUN' for r in obligations[1:]),
             'M157_FIXED_OBLIGATION_CLAIM_INVALID')


def _validate_calls(calls):
    _require(calls.get('schema') == 'SKYNETVS_M156_CALLSITE_BEHAVIOR_EVIDENCE_V1' and
             calls.get('status') == 'FIXED_CALLSITE_CASES_PASS' and
             calls.get('base_commit') == BASE_COMMIT and
             calls.get('target_path') == TARGET_PATH and
             calls.get('source_sha256') == SOURCE_SHA256 and
             calls.get('candidate_sha256') == CANDIDATE_SHA256 and
             calls.get('dtr_response_sha256') == DTR_RESPONSE_SHA256 and
             calls.get('m155_plan_sha256') == EXPECTED['Core_BehaviorPlan.json'][0] and
             calls.get('count_total') == 13 and calls.get('count_passed') == 13 and
             calls.get('count_failed') == 0 and
             calls.get('independent_expected_results_defined_before_execution') is True,
             'M157_CALLS_BINDING_MISMATCH')
    execution = calls.get('execution')
    _require(type(execution) is dict and execution.get('production_source_writes') == 0 and
             execution.get('git_write_commands') == 0 and
             execution.get('patch_applied') is False and
             execution.get('approval_or_promotion_authorized') is False and
             execution.get('user_training_or_inbox_read') is False and
             execution.get('whole_module_imported') is False,
             'M157_CALLS_EXECUTION_BOUNDARY_MISMATCH')
    obligations = calls.get('m155_obligations')
    _require(type(obligations) is dict and set(obligations) == set(CALLSITE_LINES),
             'M157_CALLS_OBLIGATIONS_MISSING')
    rows = calls.get('cases')
    _require(type(rows) is list and len(rows) == 13 and
             len({r.get('case_id') for r in rows if type(r) is dict}) == 13,
             'M157_CALLS_CASE_SET_INVALID')
    for cid, (qualname, line) in CALLSITE_LINES.items():
        selected = [r for r in rows if r.get('obligation') == cid]
        required = CASE_COUNTS[cid]
        _require(len(selected) == required and
                 obligations[cid].get('cases') == required and
                 obligations[cid].get('passed') == required and
                 obligations[cid].get('target_callsite') == qualname.split('.')[-1] + ':' + str(line),
                 'M157_CALLS_COUNT_OR_TARGET_MISMATCH_' + cid)
        for r in selected:
            a = r.get('original'); b = r.get('candidate')
            _require(type(a) is dict and type(b) is dict and
                     r.get('passed') is True and
                     a.get('matched_independent_oracle') is True and
                     b.get('matched_independent_oracle') is True and
                     a.get('result') == b.get('result') == r.get('expected') and
                     type(r.get('min_callsite_hits')) is int and r['min_callsite_hits'] > 0 and
                     type(a.get('target_callsite_hits')) is int and
                     type(b.get('target_callsite_hits')) is int and
                     a['target_callsite_hits'] >= r['min_callsite_hits'] and
                     b['target_callsite_hits'] >= r['min_callsite_hits'],
                     'M157_CALLS_CASE_FAILED_' + cid)


def reconcile_pinned_bundle(blob):
    """Verify *identity and self-consistency*, not authenticity of test execution."""
    docs = _read_exact_bundle(blob)
    plan, fixed, calls = (docs['Core_BehaviorPlan.json'],
                          docs['M156_Behavior_Result.json'], docs['M156_Callsite_Result.json'])
    _validate_plan(plan)
    _validate_fixed(fixed)
    _validate_calls(calls)
    obligations = [
        {'case_id': cid, 'reported_passed': CASE_COUNTS[cid],
         'reported_total': CASE_COUNTS[cid], 'status': 'PINNED_PILOT_CASES_PASS'}
        for cid in CASE_COUNTS
    ]
    result = {
        'schema': SCHEMA,
        'status': 'PINNED_PILOT_EVIDENCE_CORRELATED',
        'source': 'USER_IMPORTED_M155_M156_ARTIFACTS',
        'trust': 'EXACT_PREVIOUSLY_REVIEWED_BYTES_NOT_ATTESTED_EXECUTION',
        'base_commit': BASE_COMMIT, 'target_path': TARGET_PATH,
        'request_id': plan['request_id'],
        'request_fingerprint': plan['request_fingerprint'],
        'dtr_response_sha256': DTR_RESPONSE_SHA256,
        'm155_plan_sha256': EXPECTED['Core_BehaviorPlan.json'][0],
        'candidate_sha256': CANDIDATE_SHA256,
        'source_sha256': SOURCE_SHA256,
        'evidence_member_sha256': {k:v[0] for k,v in sorted(EXPECTED.items())},
        'obligations': obligations,
        'reported_cases_passed': 41, 'reported_cases_total': 41,
        'test_code_executed_during_import': False,
        'actual_execution_independently_attested': False,
        'unseen_cases': 'UNKNOWN',
        'behavior_generalized': False, 'fix_verified': False,
        'full_runtime_regression': 'NOT_RUN',
        'git_diff_check': 'NOT_RUN', 'py_compile': 'NOT_RUN', 'pipeline_check': 'NOT_RUN',
        'patch_applied': False, 'apply_authorized': False, 'promotion_authorized': False,
        'limitations': [
            'KNOWN_M155_M156_PILOT_ARTIFACTS_ONLY',
            'EXACT_ARTIFACT_HASHES_DO_NOT_AUTHENTICATE_EXECUTING_MACHINE',
            'FINITE_SYNTHETIC_CASES_NOT_GENERAL_EQUIVALENCE',
            'NEVER_USE_IMPORTED_REPORT_AS_PERMISSION_TO_APPLY_CODE',
        ],
    }
    _require(len(json.dumps(result, ensure_ascii=True).encode('utf-8')) < MAX_RECEIPT_BYTES,
             'M157_RECEIPT_TOO_LARGE')
    return result


def format_pinned_evidence(result):
    _require(type(result) is dict and result.get('schema') == SCHEMA and
             result.get('status') == 'PINNED_PILOT_EVIDENCE_CORRELATED',
             'M157_RECEIPT_INVALID')
    rows = [
        'M157: ранее проверенные свидетельства M155 → M156 сопоставлены',
        'Источник: точные закреплённые JSON-файлы; подлинность запуска не аттестована.',
        'Git commit: ' + result['base_commit'],
        'Обязательства исходного плана: T001–T004 (пилотные сценарии)',
    ]
    for rec in result['obligations']:
        rows.append('• ' + rec['case_id'] + ': ' + str(rec['reported_passed']) + '/' +
                    str(rec['reported_total']) + ' ранее зарегистрированных PASS')
    rows += [
        'ИТОГО: 41/41 ранее зарегистрированных PASS; новый запуск тестов: НЕТ.',
        'Не доказаны: общая эквивалентность, исправление дефекта, полный runtime, DTR-B.',
        'Применение / публикация patch: НЕ РАЗРЕШЕНЫ.',
        'Этот просмотр не относится к новой задаче или новому DTR-запросу.',
    ]
    return '\n'.join(rows) + '\n'
