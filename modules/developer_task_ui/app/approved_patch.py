"""M101: one user-approved, reversible tts_edge.py edit.

Strictly one previously reviewed AST recipe, one plain file, one-line replacement.
Not a generic git-apply mechanism, not DTR-B, not privileged execution.
The mock test executes an AST-extracted, *exactly pinned* method under fake audio
sessions in the UI process. This is not an OS sandbox or real Windows audio test.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import platform
import stat
import sys
import tempfile
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from .core import blob_oid, check_plain_path, read_plain
from .git_source import GitSourceReader, find_git
from .proposals import propose_from_finding, _get_mute_fail_closed

TARGET = 'modules/tts_edge.py'
RECIPE = 'skip_audio_session_if_mute_status_unavailable'
# Pinned exact M095/M100 committed tts_edge.py text, normalized to LF.
EXPECTED_LF_SHA256 = '634dfcaeae7119300ff49736b3b95e7696f5e2e22a8edc2b27686a9a3baff2a6'
SCHEMA = 'SKYNETVS_M101_ONE_FILE_APPROVED_EDIT_V1'
MAX_SOURCE = 65536


class ApprovalRefused(ValueError):
    pass


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _plain(path: Path, is_dir: bool = False) -> None:
    st = path.lstat()
    if stat.S_ISLNK(st.st_mode) or (getattr(st, 'st_file_attributes', 0) & 0x400):
        raise ApprovalRefused('M101_LINK_OR_REPARSE: ' + path.name)
    if is_dir:
        if not stat.S_ISDIR(st.st_mode):
            raise ApprovalRefused('M101_NOT_DIRECTORY: ' + path.name)
    elif not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
        raise ApprovalRefused('M101_NOT_PLAIN_FILE: ' + path.name)


def _verified_source(raw: bytes) -> bytes:
    if len(raw) > MAX_SOURCE or b'\0' in raw or raw.count(b'\n') == 0:
        raise ApprovalRefused('M101_SOURCE_BOUND')
    lf = raw.replace(b'\r\n', b'\n')
    if b'\r' in lf or _sha(lf) != EXPECTED_LF_SHA256:
        raise ApprovalRefused('M101_ONLY_EXACT_REVIEWED_TTS_VERSION')
    return lf


def _in_worktree_eol(source: bytes, work: bytes, after: bytes) -> bytes:
    """The Git file and worktree may differ only in one consistent LF/CRLF convention."""
    if work == source:
        return after
    if b'\r' not in source and work == source.replace(b'\n', b'\r\n'):
        return after.replace(b'\n', b'\r\n')
    if b'\r' not in work and b'\r' not in source.replace(b'\r\n', b'\n') and work == source.replace(b'\r\n', b'\n'):
        return after.replace(b'\r\n', b'\n')
    raise ApprovalRefused('M101_WORKTREE_DIFFERS_FROM_GIT')


def _mock_audio_scenarios(original: bytes, updated: bytes) -> list[str]:
    """Mock-run only known pinned duck/restore AST, not full user module/imports."""
    _verified_source(original)
    names = []

    def instantiate(raw: bytes):
        tree = ast.parse(raw.decode('utf-8'))
        cls = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == '_AudioDucker'), None)
        if cls is None:
            raise ApprovalRefused('M101_DUCKER_CLASS_MISSING')
        methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in ('__init__', 'duck', 'restore')]
        if len(methods) != 3 or len(cls.decorator_list) != 0:
            raise ApprovalRefused('M101_DUCKER_SHAPE_CHANGED')
        extracted = ast.Module(body=[ast.ClassDef(name='_AudioDucker', bases=[], keywords=[], body=methods,
                                                   decorator_list=[])], type_ignores=[])
        compiled = compile(ast.fix_missing_locations(extracted), '<pinned_m101_ducker_mock>', 'exec')
        class Ducked:
            def __init__(self, session, original_volume):
                self.session, self.original_volume = session, original_volume
        scope = {'__name__': '__m101_mock__', 'platform': SimpleNamespace(system=lambda: 'Windows'),
                 '_DuckedSession': Ducked}
        exec(compiled, scope)  # Exact pinned source fragment only, fake audio sessions.
        return scope['_AudioDucker']

    # A temporary sys.modules shim lets the original trusted method import fake pycaw.
    import types
    class Audio:
        def __init__(self, *, mute=False, volume=.72, fail_mute=False,
                     fail_get=False, fail_set=False, fail_restore=False):
            self.mute, self.volume, self.fail_mute = mute, volume, fail_mute
            self.fail_get, self.fail_set, self.fail_restore = fail_get, fail_set, fail_restore
            self.mute_calls = self.get_calls = self.set_calls = 0
        def GetMute(self):
            self.mute_calls += 1
            if self.fail_mute:
                raise RuntimeError('fake GetMute error')
            return self.mute
        def GetMasterVolume(self):
            self.get_calls += 1
            if self.fail_get:
                raise RuntimeError('fake GetMasterVolume error')
            return self.volume
        def SetMasterVolume(self, value, context):
            self.set_calls += 1
            if self.fail_set or (self.fail_restore and value > .3):
                raise RuntimeError('fake SetMasterVolume error')
            self.volume = value

    class Session:
        def __init__(self, audio):
            self.SimpleAudioVolume = audio
    audio_api = types.ModuleType('pycaw.pycaw')
    pkg = types.ModuleType('pycaw')
    audio_api.AudioUtilities = types.SimpleNamespace(GetAllSessions=lambda: sessions)
    pkg.pycaw = audio_api
    old_package = sys.modules.get('pycaw')
    old_sub = sys.modules.get('pycaw.pycaw')
    sessions = []
    sys.modules['pycaw'] = pkg
    sys.modules['pycaw.pycaw'] = audio_api
    try:
        old_cls, cls = instantiate(original), instantiate(updated)
        # Demonstrate that the rule actually changes the failure branch.
        x = Audio(fail_mute=True)
        sessions[:] = [Session(x)]
        original_ducker = old_cls(enabled=True, level=.25)
        original_ducker.duck()
        if x.volume != .25:
            raise ApprovalRefused('M101_OLD_BRANCH_NOT_REPRODUCED')
        original_ducker.restore()
        names.append('baseline_getmute_exception_was_ducked')

        x = Audio(mute=True)
        sessions[:] = [Session(x)]
        obj = cls(enabled=True, level=.25)
        obj.duck(); obj.restore()
        assert x.volume == .72 and x.get_calls == 0 and x.set_calls == 0
        names.append('muted_untouched')

        x = Audio(mute=False)
        sessions[:] = [Session(x)]
        obj = cls(enabled=True, level=.25)
        obj.duck(); assert x.volume == .25 and len(obj._sessions) == 1
        obj.restore(); assert x.volume == .72 and not obj._sessions
        names.append('unmuted_duck_and_restore')

        x = Audio(fail_mute=True)
        sessions[:] = [Session(x)]
        obj = cls(enabled=True, level=.25)
        obj.duck(); obj.restore()
        assert x.volume == .72 and x.get_calls == 0 and x.set_calls == 0
        names.append('getmute_failure_skips_session')

        x = Audio(fail_get=True)
        sessions[:] = [Session(x)]
        obj = cls(enabled=True, level=.25)
        obj.duck(); obj.restore()
        assert x.volume == .72 and x.set_calls == 0
        names.append('getvolume_failure_skips_session')

        x = Audio(fail_set=True)
        sessions[:] = [Session(x)]
        obj = cls(enabled=True, level=.25)
        obj.duck(); obj.restore()
        assert x.volume == .72 and obj._sessions == []
        names.append('setvolume_failure_no_record')

        x = Audio()
        sessions[:] = [Session(x)]
        obj = cls(enabled=False, level=.25)
        obj.duck(); obj.restore()
        assert x.volume == .72 and x.get_calls == 0
        names.append('disabled_ducker_no_change')

        x, y = Audio(fail_restore=True), Audio(volume=.82)
        sessions[:] = [Session(x), Session(y)]
        obj = cls(enabled=True, level=.25)
        obj.duck(); obj.restore()
        assert x.volume == .25 and y.volume == .82 and obj._sessions == []
        names.append('restore_failure_does_not_block_other_session')
    except AssertionError as exc:
        raise ApprovalRefused('M101_MOCK_AUDIO_ASSERTION_FAILED') from exc
    finally:
        if old_package is None: sys.modules.pop('pycaw', None)
        else: sys.modules['pycaw'] = old_package
        if old_sub is None: sys.modules.pop('pycaw.pycaw', None)
        else: sys.modules['pycaw.pycaw'] = old_sub
    return names


def verify_candidate(repository: Path, report: dict[str, Any], finding: dict[str, Any],
                     proposal: dict[str, Any]) -> dict[str, Any]:
    """Re-read HEAD, index and worktree. Never trust preview alone."""
    if not isinstance(proposal, dict) or proposal.get('recipe_id') != RECIPE:
        raise ApprovalRefused('M101_NOT_ALLOWED_RECIPE')
    if finding.get('file') != TARGET or finding.get('id') != proposal.get('finding_id'):
        raise ApprovalRefused('M101_NOT_THIS_FINDING')
    reader = GitSourceReader(repository, find_git())
    snapshot = reader.capture(repository / TARGET, allow_proposal_lf_worktree=True)
    _verified_source(snapshot.content)
    index_oid = reader._sha('rev-parse', '--verify', ':' + TARGET)
    if index_oid != blob_oid(snapshot.content):
        raise ApprovalRefused('M101_INDEX_STAGED_TARGET_REFUSED')
    fresh = propose_from_finding(report, finding, snapshot)
    for key in ('recipe_id', 'finding_id', 'source_sha256', 'proposed_sha256', 'patch_text', 'line_ending_profile'):
        if proposal.get(key) != fresh.get(key):
            raise ApprovalRefused('M101_PROPOSAL_NOT_CURRENT:' + key)
    if fresh.get('approval_state') != 'NOT_APPROVED':
        raise ApprovalRefused('M101_BAD_PREVIEW_STATE')
    updated, recipe = _get_mute_fail_closed(snapshot.content, finding['line'])
    if recipe != RECIPE or _sha(updated) != fresh['proposed_sha256']:
        raise ApprovalRefused('M101_MODIFIED_BYTES_INVALID')
    target = repository / TARGET
    _plain(repository, True)
    _plain(repository / 'modules', True)
    _plain(target)
    before = read_plain(target, MAX_SOURCE)
    if _sha(before) != snapshot.provenance['working_copy_sha256']:
        raise ApprovalRefused('M101_WORKTREE_CHANGED_SINCE_CAPTURE')
    after = _in_worktree_eol(snapshot.content, before, updated)
    if after == before:
        raise ApprovalRefused('M101_NO_CHANGE')
    if _sha(after.replace(b'\r\n', b'\n')) != _sha(updated.replace(b'\r\n', b'\n')):
        raise ApprovalRefused('M101_EOL_CONVERSION_BAD')
    if len(after) > MAX_SOURCE:
        raise ApprovalRefused('M101_MODIFIED_SIZE_BOUND')
    ast.parse(after.decode('utf-8'))
    scenarios = _mock_audio_scenarios(snapshot.content, updated)
    return {'path': TARGET, 'base_commit': snapshot.base_commit, 'before_sha256': _sha(before),
            'after_sha256': _sha(after), 'before_bytes': before, 'after_bytes': after,
            'scenarios': scenarios, 'finding_id': finding['id'], 'recipe_id': recipe}


def _write_exclusive(path: Path, raw: bytes) -> None:
    with path.open('xb') as f:
        f.write(raw); f.flush(); os.fsync(f.fileno())


def _json_exclusive(path: Path, data: dict[str, Any]) -> None:
    _write_exclusive(path, (json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8'))


def _atomic_write(target: Path, after: bytes) -> None:
    mode = stat.S_IMODE(target.stat().st_mode)
    temp = target.parent / ('.m101_' + uuid.uuid4().hex + '.tmp')
    try:
        _write_exclusive(temp, after)
        os.chmod(temp, mode)
        os.replace(temp, target)
    finally:
        if temp.exists():
            temp.unlink()


def _changes_root() -> Path:
    raw = os.environ.get('LOCALAPPDATA')
    if not raw or not Path(raw).is_absolute():
        raise ApprovalRefused('M101_LOCALAPPDATA_REQUIRED')
    root = Path(raw)
    _plain(root, True)
    for child in ('SkynetVS', 'DeveloperTask', 'Changes'):
        root = root / child
        root.mkdir(exist_ok=True)
        _plain(root, True)
    return root


def apply_approved(repository: Path, report: dict[str, Any], finding: dict[str, Any],
                   proposal: dict[str, Any], approval: str) -> Path:
    """Only exact typed confirmation permits one guarded file replacement."""
    if approval != 'ПРИМЕНИТЬ M101':
        raise ApprovalRefused('M101_EXPLICIT_APPROVAL_REQUIRED')
    checked = verify_candidate(repository, report, finding, proposal)
    root = _changes_root()
    state = root / ('m101_' + uuid.uuid4().hex)
    state.mkdir(mode=0o700)
    _plain(state, True)
    backup = state / 'tts_edge.py.original'
    _write_exclusive(backup, checked['before_bytes'])
    meta = {k: checked[k] for k in ('path','base_commit','before_sha256','after_sha256','scenarios','finding_id','recipe_id')}
    meta.update({'schema': SCHEMA, 'status': 'PREPARED', 'project': str(repository.absolute()),
                 'backup': backup.name, 'user_approval': 'TYPED_IN_UI',
                 'git_modified': False, 'models_modified': False})
    _json_exclusive(state / 'M101_Prepared.json', meta)
    target = repository / TARGET
    _plain(target)
    if _sha(read_plain(target, MAX_SOURCE)) != checked['before_sha256']:
        raise ApprovalRefused('M101_WORKTREE_CHANGED_BEFORE_WRITE')
    try:
        _atomic_write(target, checked['after_bytes'])
        _plain(target)
        if _sha(read_plain(target, MAX_SOURCE)) != checked['after_sha256']:
            raise ApprovalRefused('M101_WRITTEN_CONTENT_MISMATCH')
        # No imported/compiled code executed here. AST only.
        ast.parse(target.read_text(encoding='utf-8'))
        meta['status'] = 'APPLIED_RESTART_REQUIRED'
        _json_exclusive(state / 'M101_Applied.json', meta)
    except Exception:
        # Can only restore the exact bytes that this attempt wrote.
        try:
            _plain(target)
            if _sha(read_plain(target, MAX_SOURCE)) == checked['after_sha256']:
                _atomic_write(target, checked['before_bytes'])
        except Exception:
            pass  # PREPARED + backup survive for explicit recovery review.
        raise
    return state / 'M101_Applied.json'


def rollback_approved(repository: Path, receipt_path: Path, approval: str) -> Path:
    """Restore only our own unchanged output. Never Git reset/clean/stash."""
    if approval != 'ОТКАТ M101':
        raise ApprovalRefused('M101_EXPLICIT_ROLLBACK_APPROVAL_REQUIRED')
    root = _changes_root()
    receipt_path = Path(os.path.abspath(receipt_path))
    if receipt_path.name != 'M101_Applied.json' or receipt_path.parent.parent != root or not receipt_path.parent.name.startswith('m101_'):
        raise ApprovalRefused('M101_RECEIPT_OUTSIDE_PRIVATE_STATE')
    _plain(receipt_path.parent, True)
    _plain(receipt_path)
    _plain(repository, True)
    _plain(repository / 'modules', True)
    obj = json.loads(receipt_path.read_text(encoding='utf-8'))
    if (obj.get('schema') != SCHEMA or obj.get('status') != 'APPLIED_RESTART_REQUIRED' or
        obj.get('path') != TARGET or obj.get('project') != str(repository.absolute()) or
        obj.get('backup') != 'tts_edge.py.original' or obj.get('recipe_id') != RECIPE or
        not all(isinstance(obj.get(k), str) and len(obj[k]) == 64 for k in ('before_sha256','after_sha256'))):
        raise ApprovalRefused('M101_RECEIPT_INVALID')
    if (receipt_path.parent / 'M101_RolledBack.json').exists():
        raise ApprovalRefused('M101_ALREADY_ROLLED_BACK')
    backup = receipt_path.parent / 'tts_edge.py.original'
    _plain(backup)
    b = backup.read_bytes()
    if _sha(b) != obj['before_sha256'] or len(b) > MAX_SOURCE:
        raise ApprovalRefused('M101_BACKUP_TAMPERED')
    # Never trust a locally editable receipt as authority for arbitrary bytes.
    # It may restore only the pinned original of the one M101 recipe.
    try:
        _verified_source(b)
        known_after, known_recipe = _get_mute_fail_closed(b, 91)
    except (ValueError, SyntaxError, UnicodeError) as exc:
        raise ApprovalRefused('M101_ROLLBACK_BACKUP_NOT_REVIEWED_VERSION') from exc
    if known_recipe != RECIPE or _sha(known_after) != obj['after_sha256']:
        raise ApprovalRefused('M101_ROLLBACK_NOT_M101_PATCH')
    target = repository / TARGET
    _plain(target)
    if _sha(read_plain(target, MAX_SOURCE)) != obj['after_sha256']:
        raise ApprovalRefused('M101_ROLLBACK_REFUSE_USER_EDITS')
    _atomic_write(target, b)
    if _sha(read_plain(target, MAX_SOURCE)) != obj['before_sha256']:
        raise ApprovalRefused('M101_ROLLBACK_CHECK_FAILED')
    _json_exclusive(receipt_path.parent / 'M101_RolledBack.json', {'schema': SCHEMA, 'status': 'ROLLED_BACK',
                                                                  'from_receipt': receipt_path.name,
                                                                  'restored_sha256': obj['before_sha256']})
    return receipt_path.parent / 'M101_RolledBack.json'
