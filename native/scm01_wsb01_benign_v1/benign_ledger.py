"""Persistent one-shot workflow source. A descriptor is data, never a permit.
Live entrypoints require the closed gate. Fake stores are in-memory tests only.
"""
from dataclasses import dataclass
import re
from .benign_contract import need, canonical, parse_json, parse_benign, sha, hexstr, BenignError
from .benign_runtime_gate import require_benign_run_authority
from .benign_windows_fs import RootHandle, publish_once, read_bounded, list_bounded


@dataclass(frozen=True)
class GrantDescriptor:
    request: bytes
    boot_binding: str

    def fields(self):
        obj = parse_benign('request', self.request).fields
        hexstr(self.boot_binding)
        return {'grant_id': obj['grant_id'], 'run_id': obj['run_id'], 'nonce': obj['nonce'],
                'request_sha256': sha(self.request), 'boot_binding': self.boot_binding,
                'source_sha256': obj['source_sha256'], 'capsule_sha256': obj['capsule_sha256'],
                'runtime_sha256': obj['runtime_sha256'], 'wsb_sha256': obj['wsb_sha256']}


@dataclass
class ReservedGrant:
    descriptor: GrantDescriptor
    evidence_domain: str
    launch_attempted: bool = False
    authorization_attempted: bool = False
    publication_unknown: bool = False
    outcome_attempted: bool = False
    poisoned: bool = False


class _FsStore:
    """Sealed FS port adapter for a prevalidated host-state root, never a mapping."""
    def __init__(self, root):
        need(type(root) is RootHandle, 'ledger_root')
        self.root = root; self.domain = root.engine.domain; self.lock_handle = None

    def acquire(self):
        need(self.lock_handle is None, 'ledger_lock_reentry'); self.root.check()
        self.lock_handle = self.root.engine.api.open_lock(self.root.path + '\\supervisor.lock')

    def release(self):
        if self.lock_handle is not None:
            h = self.lock_handle; self.lock_handle = None; self.root.engine.api.close(h)

    def names(self):
        self.root.check()
        return self.root.engine.api.list_names(self.root.path, 256)

    def read(self, name):
        return read_bounded(self.root, name, 131072).data

    def create(self, name, raw):
        return publish_once(self.root, name, raw)


class _LedgerEngine:
    """Private binding seam; no live API accepts caller-selected implementations."""
    def __init__(self, store):
        self.store = store; self.grant = None; self.locked = False
        # Native classification only for the exact sealed store, never caller-provided strings.
        self.domain = store.domain if type(store) is _FsStore else 'OFFLINE_MODEL'

    def reserve(self, descriptor):
        need(type(descriptor) is GrantDescriptor and self.grant is None, 'grant_descriptor')
        fields = descriptor.fields()
        self.store.acquire(); self.locked = True
        try:
            names = tuple(self.store.names())
            need(len(names) <= 256 and len(set(names)) == len(names), 'ledger_inventory')
            # Every unresolved/malformed previous launch blocks a different new grant too.
            for n in names:
                need(n == 'supervisor.lock' or (type(n) is str and
                     re.fullmatch(r'[0-9a-f]{32}\.(consumed|launch\.intent|authorization\.intent|outcome)\.json', n)),
                     'unexpected_ledger_file')
                if n.endswith('.launch.intent.json'):
                    outcome = n.replace('.launch.intent.json', '.outcome.json')
                    need(outcome in names, 'unresolved_prior_launch')
                    saved = parse_json(self.store.read(outcome), 131072)
                    need(saved.get('kind') == 'BEN01_OUTCOME_V1' and saved.get('retirement_confirmed') is True
                         and saved.get('run_id') == n[:32],
                         'unresolved_prior_outcome')
                if n.endswith('.consumed.json'):
                    saved = parse_json(self.store.read(n), 131072)
                    need(type(saved) is dict and saved.get('kind') == 'BEN01_CONSUMED_V1', 'partial_consumed_record')
            grant = ReservedGrant(descriptor, self.domain)
            self.grant = grant  # A failed/unknown write poisons this object before any launch.
            raw = canonical(dict(fields, kind='BEN01_CONSUMED_V1', rerun_allowed=False))
            self.store.create(fields['grant_id'] + '.consumed.json', raw)
            return grant
        except Exception:
            if self.grant is not None:
                self.grant.poisoned = True
            self.close(); raise

    def _check(self, grant):
        need(self.locked and self.grant is grant and type(grant) is ReservedGrant and not grant.poisoned,
             'grant_unusable')
        return grant.descriptor.fields()

    def launch_intent(self, grant):
        fields = self._check(grant)
        need(not grant.launch_attempted, 'launch_consumed')
        grant.launch_attempted = True
        try:
            self.store.create(fields['run_id'] + '.launch.intent.json',
                              canonical(dict(fields, kind='BEN01_LAUNCH_INTENT_V1')))
        except Exception:
            grant.poisoned = True; raise

    def authorization_intent(self, grant, raw, completion):
        fields = self._check(grant)
        need(grant.launch_attempted and not grant.authorization_attempted, 'authorization_consumed_or_prelaunch')
        authorization = parse_benign('authorization', raw).fields
        marker = parse_benign('authorization_commit', completion).fields
        need(authorization['run_id'] == fields['run_id'] and authorization['grant_id'] == fields['grant_id'] and
             authorization['nonce'] == fields['nonce'] and marker['authorization_sha256'] == sha(raw),
             'authorization_binding')
        grant.authorization_attempted = True
        try:
            self.store.create(fields['run_id'] + '.authorization.intent.json',
                              canonical(dict(fields, kind='BEN01_AUTH_INTENT_V1',
                                             authorization_hex=raw.hex(), commit_hex=completion.hex())))
        except Exception:
            grant.poisoned = True; grant.publication_unknown = True; raise

    def publication_failed(self, grant):
        need(self.grant is grant and grant.authorization_attempted, 'no_publication_intent')
        grant.publication_unknown = True; grant.poisoned = True

    def outcome(self, grant, result, retirement_confirmed):
        need(self.grant is grant and self.locked and not grant.outcome_attempted, 'outcome_consumed')
        need(type(retirement_confirmed) is bool, 'retirement_type')
        need(result in ('PASS_LAB_ONLY', 'FAILED_RETIRED', 'UNKNOWN', 'OFFLINE_FAKE_COMPLETED'), 'outcome_result')
        if result == 'OFFLINE_FAKE_COMPLETED':
            need(self.domain == 'OFFLINE_MODEL' and retirement_confirmed, 'fake_outcome_only')
        if result == 'PASS_LAB_ONLY':
            need(not grant.poisoned and not grant.publication_unknown and retirement_confirmed and
                 grant.launch_attempted and grant.authorization_attempted and self.domain != 'OFFLINE_MODEL',
                 'fake_or_failed_outcome')
        grant.outcome_attempted = True
        fields = grant.descriptor.fields()
        try:
            self.store.create(fields['run_id'] + '.outcome.json',
                              canonical(dict(fields, kind='BEN01_OUTCOME_V1', result=result,
                                             retirement_confirmed=retirement_confirmed,
                                             evidence_domain=self.domain, runtime_authorized=False)))
        finally:
            self.close()

    def close(self):
        if self.locked:
            self.locked = False; self.store.release()


def reserve_grant(descriptor, fs, permit=None):
    require_benign_run_authority(permit)
    engine = _LedgerEngine(_FsStore(fs))
    return engine.reserve(descriptor)


def record_launch_intent(grant, fs, permit=None):
    require_benign_run_authority(permit)
    return permit.ledger.launch_intent(grant)


def record_outcome(grant, observation, fs, permit=None):
    require_benign_run_authority(permit)
    return permit.ledger.outcome(grant, observation.result, observation.retirement_confirmed)
