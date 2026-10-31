"""M159: one exact-source, deterministic repair proposal for unsafe nested JSONL meta.

No model, source execution, files, network, Git writes, or apply capability.  This
is a bounded code recipe, NOT general Python understanding or tested behavior.
"""
from __future__ import annotations

import ast
import difflib
import hashlib
import json
import re

SCHEMA = 'SKYNETVS_M159_BOUNDED_REPAIR_PROPOSAL_V1'
TARGET = 'modules/learning/feedback_analyzer.py'
BASE_COMMIT = 'bc7ebd1eada5098abb855e80be6198addc45fd66'
SOURCE_SHA256 = '29105239ae6b61631cc9ef7b3cfb9f22e53c81657c26acfbbc72872eab200b87'
OLD_SNIPPET = (
    '                    if isinstance(record, dict):\n'
    '                        rows.append(record)\n'
)
NEW_SNIPPET = (
    '                    if isinstance(record, dict):\n'
    '                        meta = record.get("meta")\n'
    '                        if meta is None or isinstance(meta, dict):\n'
    '                            rows.append(record)\n'
)


class RepairRefused(ValueError):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def require(value, reason):
    if not value:
        raise RepairRefused(reason)


def target_method(tree):
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'FeedbackAnalyzer']
    require(len(classes) == 1, 'M159_TARGET_CLASS_NOT_UNIQUE')
    methods = [n for n in classes[0].body if isinstance(n, ast.FunctionDef) and n.name == '_read_jsonl']
    require(len(methods) == 1, 'M159_TARGET_METHOD_NOT_UNIQUE')
    return methods[0]


def has_downstream_meta_get(tree):
    """The suspected schema error must have an independently visible consumer."""
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'FeedbackAnalyzer']
    if len(classes) != 1:
        return False
    for method in classes[0].body:
        if not isinstance(method, ast.FunctionDef) or method.name == '_read_jsonl':
            continue
        for node in ast.walk(method):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == 'get' and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == 'meta'):
                return True
    return False


def make_repair_proposal(*, path, content, base_commit, provenance):
    """Propose ONLY the exact M158-followup schema guard on the captured Git blob."""
    require(path == TARGET, 'M159_TARGET_PATH_REFUSED')
    require(type(base_commit) is str and re.fullmatch(r'[0-9a-f]{40}', base_commit) is not None,
            'M159_BASE_COMMIT_INVALID')
    require(type(provenance) is dict and provenance.get('kind') == 'OBSERVED_COMMITTED_FILE'
            and provenance.get('current_git_head_observed') is True,
            'M159_CURRENT_OBSERVED_GIT_SOURCE_REQUIRED')
    require(type(content) is bytes and len(content) < 32768 and content.endswith(b'\n')
            and b'\0' not in content and b'\r' not in content,
            'M159_SOURCE_PROFILE_REFUSED')
    require(hashlib.sha256(content).hexdigest() == SOURCE_SHA256, 'M159_SOURCE_SHA_CHANGED')
    text = content.decode('utf-8', 'strict')
    require(text.count(OLD_SNIPPET) == 1 and NEW_SNIPPET not in text,
            'M159_ANCHORED_PATTERN_NOT_UNIQUE')
    before_ast = ast.parse(text, filename='<pinned_feedback_before>')
    before_method = target_method(before_ast)
    require(has_downstream_meta_get(before_ast), 'M159_META_CONSUMER_NOT_CONFIRMED')
    # The fixture is the only allowed preimage.  No dynamic location, code search,
    # untrusted task instruction or model output controls the replacement.
    modified = text.replace(OLD_SNIPPET, NEW_SNIPPET, 1)
    after_ast = ast.parse(modified, filename='<bounded_feedback_candidate>')
    after_method = target_method(after_ast)
    before_ast_copy = ast.parse(text)
    after_ast_copy = ast.parse(modified)
    c1 = next(n for n in before_ast_copy.body if isinstance(n, ast.ClassDef) and n.name == 'FeedbackAnalyzer')
    c2 = next(n for n in after_ast_copy.body if isinstance(n, ast.ClassDef) and n.name == 'FeedbackAnalyzer')
    # Removing precisely the targeted method must leave every other AST node
    # completely unchanged, including module-level definitions and attributes.
    c1.body = [n for n in c1.body
               if not (isinstance(n, ast.FunctionDef) and n.name == '_read_jsonl')]
    c2.body = [n for n in c2.body
               if not (isinstance(n, ast.FunctionDef) and n.name == '_read_jsonl')]
    require(ast.dump(before_ast_copy, include_attributes=False) ==
            ast.dump(after_ast_copy, include_attributes=False),
            'M159_OUTSIDE_TARGET_AST_CHANGED')
    require(ast.dump(before_method, include_attributes=False) !=
            ast.dump(after_method, include_attributes=False),
            'M159_TARGET_AST_NOT_CHANGED')
    result = modified.encode('utf-8')
    require(len(result) < 32768, 'M159_CANDIDATE_TOO_LARGE')
    diff = ('diff --git a/' + path + ' b/' + path + '\n' +
            ''.join(difflib.unified_diff(text.splitlines(keepends=True),
                       modified.splitlines(keepends=True),
                       fromfile='a/'+path, tofile='b/'+path, n=3)))
    require(diff.count('@@ -') == 1 and len(diff.encode('utf-8')) < 8192,
            'M159_PATCH_SHAPE_INVALID')
    return {
        'schema': SCHEMA,
        'status': 'BOUNDED_PATCH_PROPOSAL_NOT_TESTED',
        'recipe': 'FEEDBACK_META_DICT_GUARD_EXACT_M158_FOLLOWUP',
        'generator': 'OWN_DETERMINISTIC_AST_RECIPE',
        'base_commit': base_commit,
        'target_path': TARGET,
        'target_method': 'FeedbackAnalyzer._read_jsonl',
        'defect_hypothesis': 'Non-dict JSONL meta can reach downstream meta.get calls',
        'source_sha256': SOURCE_SHA256,
        'candidate_sha256': hashlib.sha256(result).hexdigest(),
        'patch_sha256': hashlib.sha256(diff.encode('utf-8')).hexdigest(),
        'patch_text': diff,
        'test_obligations': [
            'Non-dict meta input must not crash analyze()',
            'Valid dictionary meta must preserve all analyzed output',
            'Correction pairs from valid history must be preserved',
            'No model or production source execution during proposal',
        ],
        'source_executed': False,
        'candidate_executed': False,
        'tests_executed': False,
        'behavior_verified': False,
        'model_generated': False,
        'apply_authorized': False,
        'promotion_authorized': False,
        'scope_claim': 'SINGLE_EXACT_PINNED_METHOD',
        'limitations': ['ONE_PINNED_GIT_BLOB_ONLY',
                        'NOT_A_GENERAL_JSONL_SCHEMA_FIX',
                        'OTHER_NESTED_FIELD_TYPES_REMAIN_UNCHECKED',
                        'DTR_A_AND_BEHAVIOR_CHECKS_SEPARATE'],
    }


def format_repair_proposal(proposal):
    require(type(proposal) is dict and proposal.get('schema') == SCHEMA,
            'M159_REPORT_INVALID')
    return ('M159 | Собственный детерминированный рецепт (НЕ нейросеть)\n'
            'Конкретный случай: JSONL-строка с meta не-словарём.\n'
            'Исходник Git: '+ proposal['base_commit'] + '\n'
            'Метод: ' + proposal['target_method'] + '\n'
            'Итог: кандидат patch создан; тесты ещё НЕ запущены.\n'
            'Применение и promotion НЕ разрешены.\n'
            'Ограничения: другие вложенные поля не проверены, модель не обучалась.\n\n'
            + proposal['patch_text'])
