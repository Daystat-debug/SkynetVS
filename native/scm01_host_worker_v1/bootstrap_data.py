"""Bounded bootstrap DATA. A matching manifest is not an execution capability."""
import json
from dataclasses import dataclass
from pathlib import PureWindowsPath
from .contract import (Plan, FilePin, RuntimeSelection, ContractError, need, canonical,
                       digest, hex_digest, uint)

# An exact source graph. Changing a member is a new source bundle, not an import fallback.
MEMBERS = ('__init__.py', 'admission.py', 'bootstrap_data.py', 'contract.py', 'controller.py',
           'host_worker_entry.py', 'journal.py', 'lifecycle.py', 'protocol.py', 'resources.py',
           'winabi.py', 'windows_api.py', 'windows_owner.py', 'worker.py')
CHILD_MEMBERS = ('__init__.py', 'contract.py', 'protocol.py', 'bootstrap_data.py',
                 'worker.py', 'winabi.py', 'windows_api.py')
BOOT_LIMIT = 14000  # Hex command argument < 28000 chars; CreateProcess command line checked too.


def _pairs(rows):
    out = {}
    for k, v in rows:
        need(k not in out, 'bootstrap_duplicate_key')
        out[k] = v
    return out


def _reject(_):
    raise ContractError('bootstrap_number')


def _integer(s):
    need(len(s) <= 20, 'bootstrap_integer_length')
    return int(s)


def _decode(raw):
    need(type(raw) is bytes and 0 < len(raw) <= BOOT_LIMIT, 'bootstrap_size')
    from .protocol import _depth
    _depth(raw)
    try:
        value = json.loads(raw.decode('ascii'), object_pairs_hook=_pairs, parse_int=_integer,
                           parse_float=_reject, parse_constant=_reject)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ContractError('bootstrap_json') from exc
    need(canonical(value) == raw, 'bootstrap_noncanonical')
    return value


def _file(data):
    need(type(data) is dict and set(data) == {'path', 'size', 'sha256'}, 'bootstrap_file_schema')
    return FilePin(**data).validate()


def plan_from_descriptor(d):
    need(type(d) is dict and set(d) == {'kind', 'run_id', 'nonce', 'runtime', 'entrypoint',
        'source_manifest_sha256', 'base_commit', 'profile', 'operation', 'probe_sha256',
        'probe_bytes', 'native_authority', 'sandbox_authority'}, 'bootstrap_plan_schema')
    r = d['runtime']
    need(type(r) is dict and set(r) == {'executable', 'python_dll', 'version', 'trust_model'},
         'bootstrap_runtime_schema')
    p = Plan(d['run_id'], d['nonce'], RuntimeSelection(_file(r['executable']),
        _file(r['python_dll']), r['version'], r['trust_model']), _file(d['entrypoint']),
        d['source_manifest_sha256'], d['base_commit'], d['profile']).validate()
    need(canonical(d) == canonical(p.descriptor()), 'bootstrap_descriptor_mismatch')
    return p


@dataclass(frozen=True, slots=True)
class SourceBundle:
    """Manifest order is canonical, paths derive only from the entrypoint parent."""
    rows: tuple

    def validate(self, plan):
        plan.validate()
        need(type(self.rows) is tuple and len(self.rows) == len(MEMBERS), 'source_member_count')
        names = []
        for row in self.rows:
            need(type(row) is tuple and len(row) == 3, 'source_row')
            name, size, sha = row
            need(type(name) is str, 'source_name')
            uint(size, 262144, 1)
            hex_digest(sha)
            names.append(name)
        need(tuple(names) == MEMBERS, 'source_exact_graph')
        need(self.fingerprint() == plan.source_manifest_sha256, 'source_manifest_pin')
        r = dict((n, (s, h)) for n, s, h in self.rows)
        need(r['host_worker_entry.py'] == (plan.entrypoint.size, plan.entrypoint.sha256), 'entry_pin')
        return self

    def document(self):
        return {'kind': 'HWA01_SOURCE_GRAPH_V1', 'files': [
            {'name': n, 'bytes': s, 'sha256': h} for n, s, h in self.rows]}

    def fingerprint(self):
        return digest(canonical(self.document()))

    def file_pins(self, plan):
        self.validate(plan)
        parent = PureWindowsPath(plan.entrypoint.path).parent
        return tuple(FilePin(str(parent / n), s, h) for n, s, h in self.rows)


def serialize(plan, bundle):
    bundle.validate(plan)
    raw = canonical({'plan': plan.descriptor(), 'source': bundle.document()})
    need(len(raw) <= BOOT_LIMIT, 'bootstrap_size')
    return raw


def deserialize(raw):
    d = _decode(raw)
    need(type(d) is dict and set(d) == {'plan', 'source'}, 'bootstrap_envelope')
    plan = plan_from_descriptor(d['plan'])
    s = d['source']
    need(type(s) is dict and set(s) == {'kind', 'files'} and
         s['kind'] == 'HWA01_SOURCE_GRAPH_V1' and type(s['files']) is list,
         'bootstrap_manifest_schema')
    rows = []
    for r in s['files']:
        need(type(r) is dict and set(r) == {'name', 'bytes', 'sha256'}, 'bootstrap_member_schema')
        rows.append((r['name'], r['bytes'], r['sha256']))
    bundle = SourceBundle(tuple(rows)).validate(plan)
    return plan, bundle
