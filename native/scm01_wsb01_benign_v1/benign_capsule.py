"""Immutable inventory calculations. No download, execution or recursive copying."""
from dataclasses import dataclass
import json
from .benign_contract import need, uint, sha, canonical, hexstr, parse_json
from .benign_layout import component

TARGET = 'native/scm01_wsb01_benign_v1/'
SOURCE_PATHS = ('.gitattributes', '.gitignore', 'BENIGN_PROTOCOL.json', 'README_RU.md', 'SCOPE.json', 'SOURCE_BINDINGS.json', 'TEST_PLAN.json', '__init__.py', 'benign_capsule.py', 'benign_contract.py', 'benign_evidence.py', 'benign_layout.py', 'benign_ledger.py', 'benign_main.py', 'benign_orchestrator.py', 'benign_runtime_gate.py', 'benign_state.py', 'benign_windows_crypto.py', 'benign_windows_fs.py', 'benign_windows_session.py', 'benign_worker.py', 'payload/guest_bootstrap.ps1', 'payload/guest_entry.py', 'tests/__init__.py', 'tests/test_closed_entrypoints.py', 'tests/test_contract.py', 'tests/test_evidence.py', 'tests/test_layout_capsule.py', 'tests/test_ledger.py', 'tests/test_orchestrator.py', 'tests/test_state.py', 'tests/test_windows_bindings.py')
GUEST_MODULES = ('__init__.py', 'benign_capsule.py', 'benign_contract.py', 'benign_layout.py',
                 'benign_windows_fs.py', 'benign_windows_crypto.py',
                 'benign_runtime_gate.py', 'payload/guest_entry.py')
CAPSULE_MEMBERS = tuple('app/' + TARGET + x for x in GUEST_MODULES)
RUNTIME_MANIFEST_SHA = '41503dc1b9c109b6cfb652e6ff320b5011c78f529f3559720ad1788f4787967d'
RUNTIME_TREE_SHA = 'ab35bf73bf387d28cd14bdcf85c545706ae7522212f466bf10afbaf1e14ac7ed'
RUNTIME_SOURCE_SHA = 'd1f04d990aee1253d8569e8e5104e30fa9f5fa830899f14843448872d936a2cf'
LOCKED_PTH = b'python313.zip\r\n.\r\n'
PYTHON_EXE_SHA = '85b71d8c6ec1905935f74be0c9869aae198d00e98f39df699ec66f9c5a84cecd'
PYTHON_DLL_SHA = 'e820bf024efd2b56bb2b82791e6b6ddc7303f070f8e72cba7637482a8a906238'
TOTAL_RUNTIME_BYTES = 21346903


@dataclass(frozen=True)
class RuntimePins:
    tree_sha256: str
    manifest_sha256: str
    files: tuple[tuple[str, int, str], ...]
    provenance: str  # PIN_CHECKED_BYTES or OFFLINE_MODEL; neither grants execution.


@dataclass(frozen=True)
class CapsulePlan:
    members: tuple[tuple[str, bytes], ...]
    manifest: bytes
    capsule_sha256: str
    source_sha256: str
    bootstrap: bytes
    bootstrap_sha256: str
    runtime: RuntimePins


def _inventory(files, count, total, manifest_sha, tree_sha, provenance):
    need(type(files) is dict and len(files) == count, 'runtime_inventory_count')
    folded = set()
    for name, data in files.items():
        component(name)
        need(name.casefold() not in folded, 'runtime_case_collision')
        folded.add(name.casefold())
        need(type(data) is bytes and len(data) <= 32 * 1024 * 1024, 'runtime_member_size')
    need(sum(map(len, files.values())) == total, 'runtime_total')
    need('runtime_manifest.json' in files and sha(files['runtime_manifest.json']) == manifest_sha,
         'retained_manifest_pin')
    rows = [{'path': n, 'size_bytes': len(b), 'sha256': sha(b)} for n, b in sorted(files.items())]
    # Historical tree manifest excludes trailing LF, unlike the new wire.
    old = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    need(sha(old) == tree_sha, 'retained_tree_pin')
    return RuntimePins(tree_sha, manifest_sha,
                       tuple((r['path'], r['size_bytes'], r['sha256']) for r in rows), provenance)


def validate_runtime_inventory(files, expected=None):
    need(expected is None or expected == RUNTIME_TREE_SHA, 'runtime_pin_override')
    pins = _inventory(files, 37, TOTAL_RUNTIME_BYTES, RUNTIME_MANIFEST_SHA,
                      RUNTIME_TREE_SHA, 'PIN_CHECKED_BYTES')
    need(files.get('python313._pth') == LOCKED_PTH, 'locked_pth')
    for n, h in [('python.exe', PYTHON_EXE_SHA), ('python313.dll', PYTHON_DLL_SHA)]:
        need(n in files and sha(files[n]) == h, 'runtime_executable_pin')
    need('_ctypes.pyd' in files and 'python313.zip' in files, 'guest_import_dependencies')
    return pins


def _fake_runtime_inventory(files):
    """Offline fixture only; cannot carry PIN_CHECKED_BYTES provenance."""
    rows = [{'path': n, 'size_bytes': len(b), 'sha256': sha(b)} for n, b in sorted(files.items())]
    h = sha(json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode())
    return _inventory(files, 37, sum(map(len, files.values())), sha(files['runtime_manifest.json']),
                      h, 'OFFLINE_MODEL')


def build_capsule(source_bytes, runtime_manifest):
    need(type(runtime_manifest) is RuntimePins, 'runtime_pins')
    need(type(source_bytes) is dict and set(source_bytes) == set(SOURCE_PATHS), 'exact_source_count')
    for rel in source_bytes:
        need(type(rel) is str and not rel.startswith('/') and '\\' not in rel, 'source_path')
        for part in rel.split('/'):
            component(part)
        need(type(source_bytes[rel]) is bytes, 'source_bytes')
    selected = []
    for rel in GUEST_MODULES:
        need(rel in source_bytes, 'capsule_member_missing')
        selected.append(('app/' + TARGET + rel, source_bytes[rel]))
    need('payload/guest_bootstrap.ps1' in source_bytes, 'bootstrap_missing')
    rows = [{'path': n, 'bytes': len(b), 'sha256': sha(b)} for n, b in sorted(selected)]
    manifest = canonical({'kind': 'BEN01_GUEST_CAPSULE_V1', 'files': rows})
    executable_rows = [{'path': n, 'bytes': len(b), 'sha256': sha(b)}
                       for n, b in sorted(source_bytes.items()) if n.endswith(('.py', '.ps1'))]
    bootstrap = source_bytes['payload/guest_bootstrap.ps1']
    return CapsulePlan(tuple(sorted(selected)), manifest, sha(manifest),
                       sha(canonical(executable_rows)), bootstrap, sha(bootstrap), runtime_manifest)


@dataclass(frozen=True)
class GuestLoadPlan:
    """Verified bytes and deterministic import names. NOT a permit, launch or OS attestation."""
    request: bytes
    capsule_manifest: bytes
    members: tuple[tuple[str, bytes], ...]
    runtime: RuntimePins
    run_root: str
    runtime_root: str
    capsule_root: str
    module_names: tuple[str, ...]
    evidence_domain: str


def guest_module_name(path):
    need(path in CAPSULE_MEMBERS, 'guest_member_name')
    prefix = 'app/'
    rel = path[len(prefix):]
    need(rel.endswith('.py'), 'guest_python_member')
    if rel.endswith('/__init__.py'):
        return rel[:-len('/__init__.py')].replace('/', '.')
    return rel[:-3].replace('/', '.')


def prepare_guest_load(request_raw, manifest_raw, members, runtime):
    """Pure validation before importing ANY capsule module. The source byte graph is
    finite, no recursive directory discovery, metadata/self-reference or path fallback.
    """
    from .benign_contract import parse_benign
    req = parse_benign('request', request_raw).fields
    need(type(runtime) is RuntimePins and runtime.provenance in ('PIN_CHECKED_BYTES', 'OFFLINE_MODEL'),
         'runtime_plan_type')
    need(req['runtime_sha256'] == runtime.tree_sha256, 'runtime_request_binding')
    need(type(manifest_raw) is bytes and len(manifest_raw) <= 32768 and
         sha(manifest_raw) == req['capsule_sha256'], 'guest_manifest_binding')
    manifest = parse_json(manifest_raw, 32768)
    need(type(manifest) is dict and set(manifest) == {'kind', 'files'} and
         manifest['kind'] == 'BEN01_GUEST_CAPSULE_V1', 'capsule_schema')
    need(type(members) is dict and set(members) == set(CAPSULE_MEMBERS), 'guest_exact_members')
    rows = manifest['files']; need(type(rows) is list and len(rows) == len(CAPSULE_MEMBERS), 'capsule_rows')
    need(all(type(r) is dict and set(r) == {'path', 'bytes', 'sha256'} for r in rows), 'capsule_row_schema')
    need([r['path'] for r in rows] == sorted(CAPSULE_MEMBERS), 'capsule_paths_order')
    need(sum(len(b) for b in members.values() if type(b) is bytes) <= 1048576, 'guest_capsule_total')
    for r in rows:
        need(type(r) is dict and set(r) == {'path', 'bytes', 'sha256'}, 'capsule_row_schema')
        uint(r['bytes'], 262144); hexstr(r['sha256'])
        b = members[r['path']]
        need(type(b) is bytes and len(b) == r['bytes'] and sha(b) == r['sha256'], 'guest_member_pin')
    root = 'C:\\SkynetVSBenign\\' + req['run_id']
    names = tuple(guest_module_name(n) for n in sorted(CAPSULE_MEMBERS))
    need(len(set(names)) == len(names), 'module_name_collision')
    return GuestLoadPlan(request_raw, manifest_raw, tuple(sorted(members.items())), runtime,
                         root, root + '\\Runtime', root + '\\Capsule', names,
                         'PIN_CHECKED_BYTES' if runtime.provenance == 'PIN_CHECKED_BYTES' else 'OFFLINE_MODEL')


def guest_dependency_check(plan):
    """Static import closure including relative from-imports for this exact capsule.
    Dynamic execution is NOT inferred from AST. This validator does not import guest.
    """
    import ast
    import importlib.util
    need(type(plan) is GuestLoadPlan, 'guest_load_plan')
    by_name = {guest_module_name(n): (n, b) for n, b in plan.members}
    packages = {'native', 'native.scm01_wsb01_benign_v1', 'native.scm01_wsb01_benign_v1.payload'}
    edges = []
    for name, (path, source) in sorted(by_name.items()):
        tree = ast.parse(source.decode('utf-8'), filename=path, feature_version=(3, 12))
        package = name if path.endswith('/__init__.py') else name.rsplit('.', 1)[0]
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level:
                target = importlib.util.resolve_name('.' * node.level + (node.module or ''), package)
                need(target in by_name or target in packages, 'guest_import_outside_capsule:' + target)
                # from . import module includes the named child when it is a module.
                if not node.module:
                    for alias in node.names:
                        child = target + '.' + alias.name
                        need(child in by_name or alias.name == '*', 'guest_relative_member:' + child)
                edges.append((name, target))
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                candidates = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or '']
                for target in candidates:
                    need(not target.startswith(('modules.', 'tools.', 'native.')), 'guest_absolute_project_import')
    return tuple(edges)



def checked_guest_descriptor(plan):
    """Pure descriptor to the fixed standalone loader. No module execution/authority."""
    need(type(plan) is GuestLoadPlan, 'guest_load_plan')
    checked = prepare_guest_load(plan.request, plan.capsule_manifest, dict(plan.members), plan.runtime)
    need(checked == plan, 'guest_plan_changed'); guest_dependency_check(plan)
    return {'request_sha256': sha(plan.request), 'capsule_sha256': sha(plan.capsule_manifest),
            'runtime_sha256': plan.runtime.tree_sha256, 'module_names': list(plan.module_names),
            'run_root': plan.run_root, 'runtime_root': plan.runtime_root, 'capsule_root': plan.capsule_root,
            'scope': 'VERIFIED_BYTE_PLAN_NOT_AUTHORITY'}


def load_checked_guest_modules(plan, permit=None):
    """No host-side guest executor. The first-process guest admission must invoke the
    reviewed standalone byte loader in payload/guest_entry.py after a separate grant.
    Kept closed rather than importing that payload during offline validation.
    """
    from .benign_runtime_gate import require_benign_run_authority
    require_benign_run_authority(permit)
    raise RuntimeError('USE_SEPARATELY_ADMITTED_STANDALONE_GUEST_LOADER')


@dataclass(frozen=True)
class GuestStartupData:
    """Bootstrap arguments bind bytes only. This is deliberately NOT a guest permit."""
    run_id: str
    request_sha256: str
    capsule_sha256: str
    bootstrap_sha256: str

    def argv(self):
        hexstr(self.run_id, 32)
        for h in (self.request_sha256, self.capsule_sha256, self.bootstrap_sha256): hexstr(h)
        return (self.run_id, self.request_sha256, self.capsule_sha256, self.bootstrap_sha256)


def parse_guest_startup_args(argv):
    need(type(argv) in (tuple, list) and len(argv) == 4, 'guest_startup_argument_count')
    value = GuestStartupData(*argv); value.argv()
    return value


def build_guest_startup(plan, bootstrap):
    """Data-only plan for the fixed PS -> interpreter handoff; no filesystem or imports."""
    checked_guest_descriptor(plan)
    need(type(bootstrap) is bytes and 0 < len(bootstrap) <= 262144, 'bootstrap_source_size')
    from .benign_contract import parse_benign
    req = parse_benign('request', plan.request).fields
    return GuestStartupData(req['run_id'], sha(plan.request), sha(plan.capsule_manifest), sha(bootstrap))


def validate_guest_startup(plan, args, bootstrap, executable, script):
    """Checks source/data identity and fixed local paths. Does not execute the guest."""
    data = parse_guest_startup_args(args)
    need(data == build_guest_startup(plan, bootstrap), 'guest_startup_pin_mismatch')
    need(executable == plan.runtime_root + '\\python.exe', 'guest_startup_interpreter_path')
    need(script == plan.capsule_root + '\\app\\native\\scm01_wsb01_benign_v1\\payload\\guest_entry.py',
         'guest_startup_entry_path')
    return {'scope': 'CHECKED_DATA_NOT_AUTHORITY', 'run_id': data.run_id,
            'request_sha256': data.request_sha256, 'capsule_sha256': data.capsule_sha256,
            'bootstrap_sha256': data.bootstrap_sha256, 'runtime_sha256': plan.runtime.tree_sha256}
