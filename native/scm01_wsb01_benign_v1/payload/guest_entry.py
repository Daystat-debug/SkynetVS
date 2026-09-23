"""Fixed benign guest source. This revision has NO live guest capability issuer.
The standalone entrypoint is CLOSED before reading files or loading native libraries.
The exchange body is retained as source; no test imports or executes this payload.
"""
if __name__ == '__main__':
    import json
    print(json.dumps({'result': 'RUNTIME_CLOSED_SOURCE_ONLY', 'runtime_authorized': False,
                      'guest_bootstrap': False, 'real_scm': False, 'guard': False}))
    raise SystemExit(92)


def _early_decode(raw, cap):
    """Bounded canonical data parser for a first process BEFORE project imports."""
    import json
    def check(ok, code):
        if not ok: raise ValueError(code)
    check(type(raw) is bytes and 0 < len(raw) <= cap, 'ingress_size')
    depth = 0; quoted = escaped = False
    for ch in raw:
        if quoted:
            if escaped: escaped = False
            elif ch == 92: escaped = True
            elif ch == 34: quoted = False
        elif ch == 34: quoted = True
        elif ch in (91, 123):
            depth += 1; check(depth <= 16, 'ingress_depth')
        elif ch in (93, 125):
            depth -= 1; check(depth >= 0, 'ingress_unbalanced')
    check(not quoted and not escaped and depth == 0, 'ingress_unbalanced')
    def pairs(rows):
        out = {}
        for key, val in rows:
            check(key not in out, 'ingress_duplicate'); out[key] = val
        return out
    def integer(s):
        check(len(s.lstrip('-')) <= 20, 'ingress_integer'); value = int(s)
        check(-(1 << 64) < value < (1 << 64), 'ingress_integer'); return value
    def reject(_s): raise ValueError('ingress_noninteger')
    obj = json.loads(raw.decode('ascii'), object_pairs_hook=pairs, parse_int=integer,
                     parse_float=reject, parse_constant=reject)
    def shape(value):
        if type(value) is dict:
            check(len(value) <= 1024, 'ingress_fields')
            for key, val in value.items(): shape(key); shape(val)
        elif type(value) is list:
            check(len(value) <= 1024, 'ingress_items')
            for val in value: shape(val)
        elif type(value) is str:
            check(len(value) <= 65536 and not any(0xd800 <= ord(c) <= 0xdfff for c in value), 'ingress_string')
    shape(obj)
    canonical = (json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(',', ':'), allow_nan=False)+'\n').encode('ascii')
    check(raw == canonical, 'ingress_noncanonical')
    return obj


def _early_read(path, cap, expected_sha=None, expected_size=None):
    """Read-only first-image bootstrap recipe; parent pins source files across launch.
    Checks ancestors and the same fd before/after read. Not a hostile-host FS boundary.
    """
    import os, stat, hashlib
    from pathlib import Path
    path = Path(path)
    for ancestor in tuple(reversed(path.parents)) + (path,):
        st = os.lstat(ancestor)
        if stat.S_ISLNK(st.st_mode) or getattr(st, 'st_file_attributes', 0) & 0x400:
            raise ValueError('ingress_reparse')
    initial = os.lstat(path)
    if not stat.S_ISREG(initial.st_mode) or initial.st_nlink != 1 or not 0 <= initial.st_size <= cap:
        raise ValueError('ingress_regular_size')
    def stamp(st):
        return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_nlink,
                getattr(st, 'st_file_attributes', 0))
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(path, flags)
    try:
        if stamp(os.fstat(fd)) != stamp(initial): raise ValueError('ingress_open_changed')
        result = bytearray()
        while len(result) <= cap:
            chunk = os.read(fd, min(65536, cap + 1 - len(result)))
            if not chunk: break
            result.extend(chunk)
        if stamp(os.fstat(fd)) != stamp(initial) or len(result) != initial.st_size:
            raise ValueError('ingress_read_changed')
    finally:
        os.close(fd)
    data = bytes(result)
    if expected_size is not None and len(data) != expected_size: raise ValueError('ingress_exact_size')
    if expected_sha is not None and hashlib.sha256(data).hexdigest() != expected_sha:
        raise ValueError('ingress_hash')
    return data

def _require_local_guest_ingress(_permit):
    # This local bootstrap issuer does not exist in source delivery. Hashes/argv are not permits.
    raise RuntimeError('BEN01_FIRST_GUEST_ISSUER_NOT_IMPLEMENTED')


def _guest_first_process(argv, local_permit=None):
    """Fixed PS -> byte-loader -> checked context -> fixed exchange SOURCE route.
    Local authority is a separate absent issuer. No host Python execution of this body.
    """
    _require_local_guest_ingress(local_permit)
    import hashlib, json, sys, re
    def check(value, code):
        if not value: raise ValueError(code)
    check(type(argv) in (tuple,list) and len(argv)==4,'guest_first_argv')
    rid, request_sha, capsule_sha, bootstrap_sha = argv
    for value, n in ((rid,32),(request_sha,64),(capsule_sha,64),(bootstrap_sha,64)):
        check(type(value) is str and re.fullmatch('[0-9a-f]{%d}'%n,value) is not None,'guest_first_arg')
    check(sys.platform=='win32' and sys.version_info[:3]==(3,13,15) and sys.maxsize>2**32 and
          sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,'guest_first_interpreter_flags')
    input_root='C:\\SkynetVSBenignInput'; root='C:\\SkynetVSBenign\\'+rid
    runtime_root=root+'\\Runtime'; capsule_root=root+'\\Capsule'
    entry_path=capsule_root+'\\app\\native\\scm01_wsb01_benign_v1\\payload\\guest_entry.py'
    check(sys.executable==runtime_root+'\\python.exe' and __file__==entry_path,'guest_first_local_paths')
    request_raw=_early_read(input_root+'\\request.json',32768,request_sha)
    manifest_raw=_early_read(input_root+'\\capsule.manifest.json',32768,capsule_sha)
    bootstrap=_early_read(input_root+'\\guest_bootstrap.ps1',262144,bootstrap_sha)
    request=_early_decode(request_raw,32768); manifest=_early_decode(manifest_raw,32768)
    check(type(request) is dict and request.get('run_id')==rid and request.get('capsule_sha256')==capsule_sha,
          'guest_first_request')
    allowed=(
        'app/native/scm01_wsb01_benign_v1/__init__.py',
        'app/native/scm01_wsb01_benign_v1/benign_capsule.py',
        'app/native/scm01_wsb01_benign_v1/benign_contract.py',
        'app/native/scm01_wsb01_benign_v1/benign_layout.py',
        'app/native/scm01_wsb01_benign_v1/benign_runtime_gate.py',
        'app/native/scm01_wsb01_benign_v1/benign_windows_crypto.py',
        'app/native/scm01_wsb01_benign_v1/benign_windows_fs.py',
        'app/native/scm01_wsb01_benign_v1/payload/guest_entry.py')
    check(type(manifest) is dict and set(manifest)=={'kind','files'} and
          manifest['kind']=='BEN01_GUEST_CAPSULE_V1','guest_first_manifest')
    rows=manifest['files']
    check(type(rows) is list and len(rows)==8 and all(type(r) is dict and
          set(r)=={'path','bytes','sha256'} for r in rows),'guest_first_capsule_rows')
    check([r['path'] for r in rows]==list(allowed),'guest_first_capsule_paths')
    members={}
    for r in rows:
        check(type(r['bytes']) is int and 0<=r['bytes']<=262144 and type(r['sha256']) is str and
              re.fullmatch('[0-9a-f]{64}',r['sha256']) is not None,'guest_first_capsule_pin')
        members[r['path']]=_early_read(capsule_root+'\\'+r['path'].replace('/','\\'),
                                        262144,r['sha256'],r['bytes'])
    # Retained runtime's signed-off manifest bytes are pinned; parsing it does not issue authority.
    runtime_raw=_early_read(runtime_root+'\\runtime_manifest.json',65536,
        '41503dc1b9c109b6cfb652e6ff320b5011c78f529f3559720ad1788f4787967d')
    runtime_manifest=json.loads(runtime_raw.decode('utf-8'))
    runtime_rows=runtime_manifest.get('payload_files')
    check(type(runtime_rows) is list and len(runtime_rows)==36,'guest_first_runtime_count')
    runtime_files={'runtime_manifest.json':runtime_raw};total=len(runtime_raw)
    for r in runtime_rows:
        check(type(r) is dict and type(r.get('path')) is str and
              re.fullmatch('[A-Za-z0-9_.-]{1,100}',r['path']) is not None and
              r['path'] not in ('.','..') and r['path'] not in runtime_files,'guest_first_runtime_name')
        n=r.get('size_bytes');h=r.get('sha256')
        check(type(n) is int and 0<=n<=33554432 and type(h) is str and
              re.fullmatch('[0-9a-f]{64}',h) is not None,'guest_first_runtime_pin')
        total+=n;check(total<=21346903,'guest_first_runtime_total')
        runtime_files[r['path']]=_early_read(runtime_root+'\\'+r['path'],33554432,h,n)
    check(total==21346903,'guest_first_runtime_total')
    # No project import happens before member hashes. This returns canonical module objects.
    entry, _finder=_load_capsule_byte_graph(request_raw,manifest_raw,members,capsule_sha,local_permit)
    benign_capsule = sys.modules['native.scm01_wsb01_benign_v1.benign_capsule']
    benign_layout = sys.modules['native.scm01_wsb01_benign_v1.benign_layout']
    pins=benign_capsule.validate_runtime_inventory(runtime_files)
    plan=benign_capsule.prepare_guest_load(request_raw,manifest_raw,members,pins)
    benign_capsule.validate_guest_startup(plan,argv,bootstrap,sys.executable,__file__)
    # Data plan is separate from local permit; no parent process object is deserialized here.
    return entry.main_fixed_guest(input_root+'\\request.json',benign_layout.GUEST_ROOTS,
                                   local_permit,loader_plan=plan)


def _load_capsule_byte_graph(request_raw, manifest_raw, members, approved_capsule_sha, local_permit=None):
    """Standalone source recipe for future first-process admission; NOT invoked in this revision.
    Called only by the future reviewed guest issuer. Same-user hostile code is out of scope.
    All member bytes are checked before any package import, then imported from those bytes,
    never re-opened by SourceFileLoader. No pyc or sys.path modification.
    """
    _require_local_guest_ingress(local_permit)
    import hashlib
    import json
    import sys
    import importlib
    import importlib.abc
    import importlib.util
    import types
    def require(value, code):
        if not value: raise RuntimeError(code)
    def digest(data): return hashlib.sha256(data).hexdigest()
    def pairs(rows):
        out = {}
        for key, value in rows:
            require(key not in out, 'duplicate_loader_key'); out[key] = value
        return out
    def number(text):
        require(len(text.lstrip('-')) <= 20, 'loader_integer_digits')
        return int(text)
    def reject_number(_text):
        raise RuntimeError('loader_noninteger')
    def shape(obj, depth=0):
        require(depth <= 16, 'loader_depth')
        if type(obj) is dict:
            require(len(obj) <= 128, 'loader_object_limit')
            for key, value in obj.items():
                require(type(key) is str and len(key) <= 128, 'loader_key')
                shape(value, depth + 1)
        elif type(obj) is list:
            require(len(obj) <= 128, 'loader_array_limit')
            for value in obj: shape(value, depth + 1)
        elif type(obj) is str:
            require(len(obj) <= 8192 and not any(0xD800 <= ord(c) <= 0xDFFF for c in obj), 'loader_string')
        elif type(obj) is int:
            require(abs(obj) < 10 ** 20, 'loader_integer_digits')
        else:
            require(type(obj) is bool or obj is None, 'loader_value_type')
    def decode(raw, cap):
        require(type(raw) is bytes and 0 < len(raw) <= cap, 'loader_size')
        # Bound recursion before json.loads; quoted/escaped delimiters do not count.
        depth = 0; quoted = escaped = False
        for char in raw:
            if quoted:
                if escaped: escaped = False
                elif char == 92: escaped = True
                elif char == 34: quoted = False
            elif char == 34: quoted = True
            elif char in (91, 123):
                depth += 1; require(depth <= 16, 'loader_depth')
            elif char in (93, 125):
                depth -= 1; require(depth >= 0, 'loader_unbalanced')
        require(not quoted and not escaped and depth == 0, 'loader_unbalanced')
        # Exact equality rejects whitespace, CRLF and duplicate keys.
        obj = json.loads(raw.decode('ascii'), object_pairs_hook=pairs, parse_int=number,
                         parse_float=reject_number, parse_constant=reject_number)
        shape(obj)
        require((json.dumps(obj, ensure_ascii=True, sort_keys=True, separators=(',', ':'),
                            allow_nan=False) + '\n').encode('ascii') == raw, 'loader_noncanonical')
        return obj
    expected_paths = (
        'app/native/scm01_wsb01_benign_v1/__init__.py',
        'app/native/scm01_wsb01_benign_v1/benign_capsule.py',
        'app/native/scm01_wsb01_benign_v1/benign_contract.py',
        'app/native/scm01_wsb01_benign_v1/benign_layout.py',
        'app/native/scm01_wsb01_benign_v1/benign_runtime_gate.py',
        'app/native/scm01_wsb01_benign_v1/benign_windows_crypto.py',
        'app/native/scm01_wsb01_benign_v1/benign_windows_fs.py',
        'app/native/scm01_wsb01_benign_v1/payload/guest_entry.py')
    require(sys.dont_write_bytecode and sys.flags.isolated and sys.flags.no_site, 'loader_python_flags')
    require(type(manifest_raw) is bytes and 0 < len(manifest_raw) <= 32768 and
            type(approved_capsule_sha) is str and len(approved_capsule_sha) == 64 and
            all(c in '0123456789abcdef' for c in approved_capsule_sha) and
            digest(manifest_raw) == approved_capsule_sha, 'loader_manifest_pin')
    request = decode(request_raw, 32768); manifest = decode(manifest_raw, 32768)
    require(type(request) is dict and request.get('capsule_sha256') == approved_capsule_sha,
            'loader_request_pin')
    require(type(manifest) is dict and set(manifest) == {'kind', 'files'} and
            manifest['kind'] == 'BEN01_GUEST_CAPSULE_V1', 'loader_manifest_schema')
    require(type(members) is dict and set(members) == set(expected_paths), 'loader_member_set')
    rows = manifest['files']; require(type(rows) is list and len(rows) == len(expected_paths), 'loader_rows')
    require(all(type(r) is dict and set(r) == {'path', 'bytes', 'sha256'} for r in rows), 'loader_row_type')
    require([r['path'] for r in rows] == list(expected_paths), 'loader_member_order')
    sources = {}
    for row in rows:
        raw = members[row['path']]
        require(type(row['bytes']) is int and 0 <= row['bytes'] <= 262144 and type(raw) is bytes and
                len(raw) == row['bytes'] and digest(raw) == row['sha256'], 'loader_member_pin')
        name = row['path'][4:]
        package = name.endswith('/__init__.py')
        name = (name[:-len('/__init__.py')] if package else name[:-3]).replace('/', '.')
        sources[name] = (row['path'], raw, package)
    require(sum(len(b) for b in members.values()) <= 1048576, 'loader_total')
    require(not any(n == 'native' or n.startswith('native.') for n in sys.modules), 'loader_preloaded_project')
    class Loader(importlib.abc.MetaPathFinder, importlib.abc.Loader):
        def find_spec(self, fullname, path=None, target=None):
            if fullname in sources:
                return importlib.util.spec_from_loader(fullname, self, is_package=sources[fullname][2])
            if fullname.startswith('native.'):
                raise ImportError('Outside verified capsule: ' + fullname)
            return None
        def create_module(self, spec): return None
        def exec_module(self, module):
            path, raw, _ = sources[module.__name__]
            module.__file__ = 'skynetvs://BEN01/Capsule/' + path
            exec(compile(raw, module.__file__, 'exec', dont_inherit=True), module.__dict__)
    finder = Loader(); prefix = 'native.scm01_wsb01_benign_v1'
    sys.meta_path.insert(0, finder)
    try:
        native = types.ModuleType('native'); native.__path__ = []; native.__package__ = 'native'
        native.__spec__ = importlib.util.spec_from_loader('native', None, is_package=True)
        sys.modules['native'] = native
        package = importlib.import_module(prefix)
        payload = types.ModuleType(prefix + '.payload'); payload.__path__ = []; payload.__package__ = payload.__name__
        payload.__spec__ = importlib.util.spec_from_loader(payload.__name__, None, is_package=True)
        sys.modules[payload.__name__] = payload; package.payload = payload
        # Membership in the byte graph does not import a module. The first-process
        # caller immediately needs both helpers; load them through this pinned finder.
        importlib.import_module(prefix + '.benign_capsule')
        importlib.import_module(prefix + '.benign_layout')
        entry = importlib.import_module(prefix + '.payload.guest_entry')
        # The complete protocol validation is now executed by the byte-pinned codec.
        codec = sys.modules[prefix + '.benign_contract']
        codec.parse_benign('request', request_raw)
        return entry, finder
    except Exception:
        for name in tuple(sys.modules):
            if name == 'native' or name.startswith('native.'):
                sys.modules.pop(name, None)
        if finder in sys.meta_path: sys.meta_path.remove(finder)
        raise


if __package__:
    from ..benign_runtime_gate import require_benign_run_authority
    from ..benign_contract import (need, parse_benign, message, sha, expected_response, RUNTIME_FLAGS,
                                    READY_DOMAIN, TERMINAL_DOMAIN)
    from ..benign_windows_fs import read_bounded, publish_once, PendingArtifact


def main_fixed_guest(request_path, fixed_roots, permit=None, *, loader_plan=None):
    require_benign_run_authority(permit)
    context = build_checked_guest_context(request_path, fixed_roots, permit, loader_plan=loader_plan)
    try:
        return _fixed_exchange(context.input_root, context.control_root, context.output_root,
                               context.signer, context.clock, context.runtime_observation, context.pins)
    finally:
        context.close()


def _publish_pair(root, stem, raw, sig, completion):
    # Completion is last. A failed/uncertain create/flush is never retried.
    publish_once(root, stem + '.json', raw)
    publish_once(root, stem + '.sig', sig)
    publish_once(root, stem + '.commit.json', completion)


def _fixed_exchange(input_root, control_root, output_root, signer, clock, runtime_observation, pins):
    try:
        return _fixed_exchange_body(input_root, control_root, output_root, signer, clock,
                                    runtime_observation, pins)
    finally:
        signer.close()


def _fixed_exchange_body(input_root, control_root, output_root, signer, clock, runtime_observation, pins):
    """Fixed request -> digest response; no commands, imports, services or child processes.
    The one signer is closed in every path. Roots are already sealed by the capsule loader.
    This source body is NOT invoked during source/fake validation.
    """
    request_raw = read_bounded(input_root, 'request.json', 32768).data
    request = parse_benign('request', request_raw).fields
    need(runtime_observation == RUNTIME_FLAGS, 'guest_runtime_prelaunch')
    for key in ('capsule_sha256', 'layout_sha256', 'policy_sha256', 'runtime_sha256',
                'schema_sha256', 'source_sha256', 'wsb_sha256'):
        need(request[key] == pins[key], 'guest_pin:' + key)
    run_id, nonce = request['run_id'], request['nonce']
    auth_raw = auth_commit = None
    records = []
    started = clock.now_ns()

    def row(event, data):
        tick = clock.now_ns()
        need(tick >= started, 'guest_clock_regression')
        records.append(message('journal_record', run_id, nonce, event=event, data=data,
                               sequence=len(records), guest_monotonic_ns=tick))

    try:
        static = {key: request[key] for key in ('capsule_sha256', 'layout_sha256', 'policy_sha256',
                  'runtime_sha256', 'schema_sha256', 'source_sha256', 'wsb_sha256')}
        key_blob = signer.public_blob
        ready = message('ready', run_id, nonce, **static, request_sha256=sha(request_raw),
                        guest_runtime=dict(runtime_observation), public_key_blob_hex=key_blob.hex())
        ready_sig = signer.sign(READY_DOMAIN, ready)
        ready_commit = message('ready_commit', run_id, nonce, ready_sha256=sha(ready),
                               ready_signature_sha256=sha(ready_sig))
        _publish_pair(output_root, 'ready', ready, ready_sig, ready_commit)
        deadline = clock.now_ns() + 90_000_000_000
        while True:
            need(clock.now_ns() <= deadline, 'authorization_timeout')
            try:
                auth_commit = read_bounded(control_root, 'authorization.commit.json', 4096).data
                auth_raw = read_bounded(control_root, 'authorization.json', 16384).data
                break
            except PendingArtifact:
                clock.sleep_ns(250_000_000)
        auth = parse_benign('authorization', auth_raw).fields
        ac = parse_benign('authorization_commit', auth_commit).fields
        for doc in (auth, ac):
            need(doc['run_id'] == run_id and doc['nonce'] == nonce, 'authorization_identity')
        need(ac['authorization_sha256'] == sha(auth_raw), 'authorization_commit')
        expected = {'grant_id': request['grant_id'], 'request_sha256': sha(request_raw),
                    'ready_sha256': sha(ready), 'ready_signature_sha256': sha(ready_sig),
                    'public_key_sha256': sha(key_blob), 'scenario': request['scenario'],
                    'scm_budget': request['scm_budget']}
        for k, value in expected.items():
            need(auth[k] == value, 'authorization_binding:' + k)
        row('BEGIN', {})
        row('AUTHORIZATION_OBSERVED', {'authorization_sha256': sha(auth_raw),
                                     'authorization_commit_sha256': sha(auth_commit)})
        response = expected_response(request_raw)
        row('BENIGN_COMPLETED', {'response_sha256': response})
        row('FINAL', {'result': 'BENIGN_TASK_COMPLETED'})
        journal = b''.join(records)
        need(len(journal) <= 65536, 'journal_bound')
        terminal = message('terminal', run_id, nonce, **static,
                           request_sha256=sha(request_raw), ready_sha256=sha(ready),
                           public_key_sha256=sha(key_blob), authorization_sha256=sha(auth_raw),
                           authorization_commit_sha256=sha(auth_commit),
                           session_binding_sha256=auth['session_binding_sha256'],
                           journal_sha256=sha(journal), journal_records=len(records), journal_bytes=len(journal),
                           response_sha256=response, result='BENIGN_TASK_COMPLETED')
        signature = signer.sign(TERMINAL_DOMAIN, terminal)
        completion = message('terminal_commit', run_id, nonce, journal_sha256=sha(journal),
                             terminal_sha256=sha(terminal), terminal_signature_sha256=sha(signature))
        publish_once(output_root, 'journal.jsonl', journal)
        _publish_pair(output_root, 'terminal', terminal, signature, completion)
        return 0
    except Exception:
        # A failure artifact blocks success. No retry of a possibly published terminal/key.
        failure = message('failure', run_id, nonce, code='BENIGN_EXCHANGE_FAILED',
                          message='Fixed benign exchange failed; preserve partial evidence.')
        try:
            publish_once(output_root, 'failure.json', failure)
        except Exception:
            pass
        return 1


class _GuestClock:
    def now_ns(self):
        import time
        return time.monotonic_ns()
    def sleep_ns(self, amount):
        import time
        need(type(amount) is int and 0 < amount <= 250000000, 'guest_poll_budget')
        time.sleep(amount / 1000000000)


class _GuestContext:
    def __init__(self, roots, signer, observation, pins):
        self.input_root, self.control_root, self.output_root = roots
        self.signer, self.runtime_observation, self.pins = signer, observation, pins
        self.clock = _GuestClock(); self.closed = False
    def close(self):
        if self.closed: return
        self.closed = True; errors = []
        try: self.signer.close()
        except Exception as exc: errors.append(exc)
        for root in (self.output_root, self.control_root, self.input_root):
            try: root.close()
            except Exception as exc: errors.append(exc)
        if errors: raise RuntimeError('guest_resources_close_unknown') from errors[0]


def build_checked_guest_context(request_path, fixed_roots, permit=None, *, loader_plan=None):
    """Closed native assembly; a plan/request/JSON is never a guest capability issuer.
    Called only after the byte-closed loader has installed canonical package names.
    """
    require_benign_run_authority(permit)
    import sys
    from ..benign_layout import GUEST_ROOTS
    from ..benign_capsule import RUNTIME_TREE_SHA
    from ..benign_windows_fs import open_bound_root
    from ..benign_windows_crypto import create_ephemeral_signer
    need(type(fixed_roots) is tuple and fixed_roots == GUEST_ROOTS, 'fixed_guest_roots')
    need(request_path == GUEST_ROOTS[0] + '\\request.json', 'fixed_guest_request')
    observation = dict(major=sys.version_info.major, minor=sys.version_info.minor,
                       micro=sys.version_info.micro, pointer_bits=64 if sys.maxsize > 2**32 else 32,
                       isolated=bool(sys.flags.isolated), no_site=bool(sys.flags.no_site),
                       dont_write_bytecode=bool(sys.dont_write_bytecode))
    need(observation == RUNTIME_FLAGS, 'guest_runtime_flags')
    roots = []; signer = None
    try:
        for path in (GUEST_ROOTS[0], GUEST_ROOTS[2], GUEST_ROOTS[3]):
            roots.append(open_bound_root(path, permit))
        request_raw = read_bounded(roots[0], 'request.json', 32768).data
        request = parse_benign('request', request_raw).fields
        need(request['runtime_sha256'] == RUNTIME_TREE_SHA, 'retained_runtime_pin')
        # The checked data plan and local authority are separate; the plan is NOT a serialized permit.
        from ..benign_capsule import GuestLoadPlan, prepare_guest_load
        plan = loader_plan
        need(type(plan) is GuestLoadPlan and plan.evidence_domain == 'PIN_CHECKED_BYTES' and
             plan.request == request_raw, 'guest_loader_context_binding')
        need(prepare_guest_load(plan.request, plan.capsule_manifest, dict(plan.members), plan.runtime) == plan,
             'guest_loader_recheck')
        pins = {k: request[k] for k in ('capsule_sha256', 'layout_sha256', 'policy_sha256',
                'runtime_sha256', 'schema_sha256', 'source_sha256', 'wsb_sha256')}
        signer = create_ephemeral_signer(permit)
        return _GuestContext(tuple(roots), signer, observation, pins)
    except Exception:
        if signer is not None: signer.close()
        for root in reversed(roots): root.close()
        raise
