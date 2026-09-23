"""Artifact-only worker. No Sandbox launch/kill API. Standalone entrypoint is CLOSED."""
if __name__ == '__main__':
    import json
    print(json.dumps({'result': 'RUNTIME_CLOSED_SOURCE_ONLY', 'runtime_authorized': False}))
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

def _require_local_worker_ingress(_permit):
    # Process-local issuer intentionally absent. No deserialized parent object/flag is a permit.
    raise RuntimeError('BEN01_FIRST_WORKER_ISSUER_NOT_IMPLEMENTED')


def _load_worker_byte_graph(startup, script_path, executable_path, local_permit=None):
    """First pinned worker script reads only its fixed sibling graph before imports.
    Startup arrived through its inherited pipe; hashes describe data, not authority.
    This loader is SOURCE ONLY and is not invoked by offline/fake validation.
    """
    _require_local_worker_ingress(local_permit)
    import hashlib, sys, types, importlib, importlib.abc, importlib.util
    from pathlib import PureWindowsPath
    def check(value, code):
        if not value: raise ValueError(code)
    def digest(raw): return hashlib.sha256(raw).hexdigest()
    obj = _early_decode(startup, 262144)
    check(type(obj) is dict and obj.get('kind') == 'BEN01_WORKER_INGRESS_V1' and
          obj.get('role') == 'ARTIFACT_WORKER', 'worker_first_role')
    root = str(PureWindowsPath(script_path).parent)
    check(obj.get('source_root') == root and PureWindowsPath(script_path).name == 'benign_worker.py' and
          obj.get('executable') == executable_path, 'worker_first_path')
    rows = obj.get('source_files')
    check(type(rows) is list and len(rows) == 32 and all(type(r) is dict and
          set(r) == {'path', 'bytes', 'sha256'} for r in rows), 'worker_first_rows')
    names = [r['path'] for r in rows]
    check(all(type(n) is str for n in names) and names == sorted(set(names)), 'worker_first_row_order')
    allowed = ('__init__.py', 'benign_capsule.py', 'benign_contract.py', 'benign_evidence.py',
               'benign_layout.py', 'benign_runtime_gate.py', 'benign_windows_crypto.py',
               'benign_windows_fs.py', 'benign_windows_session.py', 'benign_worker.py')
    by_name = {r['path']: r for r in rows}; check(set(allowed) <= set(by_name), 'worker_first_graph')
    for r in rows:
        check(type(r['bytes']) is int and 0 <= r['bytes'] <= 262144 and type(r['sha256']) is str and
              len(r['sha256']) == 64 and all(c in '0123456789abcdef' for c in r['sha256']), 'worker_first_pin')
    check(type(obj.get('executable_bytes')) is int and 0 < obj['executable_bytes'] <= 32*1024**2 and
          type(obj.get('executable_sha256')) is str, 'worker_first_interpreter_pin')
    _early_read(executable_path, 32*1024**2, obj['executable_sha256'], obj['executable_bytes'])
    context = obj.get('context'); check(type(context) is dict, 'worker_first_context')
    text = context.get('request_hex')
    check(type(text) is str and 0 < len(text) <= 65536 and len(text)%2 == 0 and
          all(c in '0123456789abcdef' for c in text), 'worker_first_request')
    req = _early_decode(bytes.fromhex(text), 32768)
    import json
    manifest = (json.dumps([r for r in rows if r['path'].endswith(('.py', '.ps1'))],
                 sort_keys=True, ensure_ascii=True, separators=(',', ':')) + '\n').encode('ascii')
    check(type(req) is dict and req.get('source_sha256') == digest(manifest), 'worker_first_source_hash')
    sources = {}
    prefix = 'native.scm01_wsb01_benign_v1'
    for name in allowed:
        r = by_name[name]; data = _early_read(root+'\\'+name, 262144, r['sha256'], r['bytes'])
        module = prefix if name == '__init__.py' else prefix + '.' + name[:-3]
        sources[module] = (name, data, name == '__init__.py')
    check(sum(len(v[1]) for v in sources.values()) <= 2097152, 'worker_first_graph_size')
    check(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode, 'worker_first_flags')
    check(not any(n == 'native' or n.startswith('native.') for n in sys.modules), 'worker_preloaded_project')
    class Loader(importlib.abc.MetaPathFinder, importlib.abc.Loader):
        def find_spec(self, fullname, path=None, target=None):
            if fullname in sources:
                return importlib.util.spec_from_loader(fullname, self, is_package=sources[fullname][2])
            if fullname.startswith('native.'): raise ImportError('Outside worker byte graph: '+fullname)
            return None
        def create_module(self, spec): return None
        def exec_module(self, module):
            name, data, _package = sources[module.__name__]
            module.__file__ = root+'\\'+name
            exec(compile(data, module.__file__, 'exec', dont_inherit=True), module.__dict__)
    finder = Loader(); sys.meta_path.insert(0, finder)
    try:
        native = types.ModuleType('native'); native.__path__=[]; native.__package__='native'
        native.__spec__=importlib.util.spec_from_loader('native',None,is_package=True);sys.modules['native']=native
        entry = importlib.import_module(prefix+'.benign_worker')
        plan = entry.parse_worker_ingress(startup)  # Full schema after the pinned codec is installed.
        check(plan.source_root == root and plan.executable == executable_path, 'worker_loaded_binding')
        return entry, plan, finder
    except Exception:
        for name in tuple(sys.modules):
            if name == 'native' or name.startswith('native.'): sys.modules.pop(name, None)
        if finder in sys.meta_path: sys.meta_path.remove(finder)
        raise


def _parse_initial_worker_frame(raw):
    """Pure first-frame binding before project byte imports and process observation.
    This returns startup data, never a permit. The complete pinned codec rechecks it.
    """
    import json
    def check(value, code):
        if not value: raise ValueError(code)
    frame = _early_decode(raw, 262144)
    check(type(frame) is dict and set(frame) == {'command', 'payload', 'run_id', 'sequence'},
          'worker_startup_first_frame')
    check(frame['command'] == 'INIT' and type(frame['sequence']) is int and frame['sequence'] == 0,
          'worker_startup_first_frame')
    rid = frame['run_id']
    check(type(rid) is str and len(rid) == 32 and all(c in '0123456789abcdef' for c in rid),
          'worker_startup_run_id')
    payload = frame['payload']
    check(type(payload) is dict and payload.get('kind') == 'BEN01_WORKER_INGRESS_V1' and
          payload.get('role') == 'ARTIFACT_WORKER', 'worker_startup_payload')
    context = payload.get('context')
    check(type(context) is dict, 'worker_startup_context')
    text = context.get('request_hex')
    check(type(text) is str and 0 < len(text) <= 65536 and len(text) % 2 == 0 and
          all(c in '0123456789abcdef' for c in text), 'worker_startup_request_hex')
    request = _early_decode(bytes.fromhex(text), 32768)
    check(type(request) is dict and request.get('run_id') == rid, 'worker_startup_run')
    startup = (json.dumps(payload, ensure_ascii=True, sort_keys=True,
                          separators=(',', ':'), allow_nan=False) + '\n').encode('ascii')
    return startup, rid


def _worker_first_process(local_permit=None):
    """Complete fixed first-process route kept unreachable by the local issuer barrier.
    No argv selects handles, code, paths, command, or a permit. This body is not tested live.
    """
    _require_local_worker_ingress(local_permit)
    import ctypes as c, sys
    if sys.platform != 'win32' or sys.version_info[:2] != (3,12) or sys.maxsize <= 2**32:
        raise RuntimeError('worker_host_interpreter')
    k = c.WinDLL('C:\\Windows\\System32\\kernel32.dll', use_last_error=True, winmode=0x800)
    H, U = c.c_void_p, c.c_uint32
    for name, ret, args in [('GetStdHandle',H,[U]),('GetFileType',U,[H]),
                          ('ReadFile',c.c_int,[H,H,U,c.POINTER(U),H])]:
        f=getattr(k,name);f.restype=ret;f.argtypes=args
    read_handle=k.GetStdHandle((-10)&0xffffffff);write_handle=k.GetStdHandle((-11)&0xffffffff)
    if read_handle in (None, c.c_void_p(-1).value) or write_handle in (None, c.c_void_p(-1).value) or read_handle==write_handle:
        raise RuntimeError('worker_inherited_handles')
    if k.GetFileType(read_handle)!=3 or k.GetFileType(write_handle)!=3:
        raise RuntimeError('worker_inherited_not_pipes')
    def take(n):
        data=bytearray()
        while len(data)<n:
            want=min(65536,n-len(data));buf=(c.c_ubyte*want)();got=U()
            if not k.ReadFile(read_handle,buf,want,c.byref(got),None):raise c.WinError(c.get_last_error())
            if not 0<got.value<=want:raise RuntimeError('worker_startup_eof')
            data.extend(bytes(buf[:got.value]))
        return bytes(data)
    size=int.from_bytes(take(4),'little')
    if not 0<size<=262144:raise RuntimeError('worker_startup_frame_size')
    startup, initial_run_id = _parse_initial_worker_frame(take(size))
    entry, plan, _finder = _load_worker_byte_graph(startup, __file__, sys.executable, local_permit)
    # The process-local permit did not arrive on the pipe and is checked again before native assembly.
    from native.scm01_wsb01_benign_v1.benign_runtime_gate import require_benign_run_authority
    require_benign_run_authority(local_permit)
    from native.scm01_wsb01_benign_v1.benign_windows_session import _WinProcessApi, _BlockingPipeChannel
    api=_WinProcessApi(local_permit);pid=int(api.k.GetCurrentProcessId());handle=api.open_process(pid)
    try: observation=api.identity(handle,pid)
    finally: api.close(handle)
    entry.validate_worker_ingress_observation(plan,observation,sys.executable,__file__)
    req=entry._early_decode(plan.context.request,32768)
    if initial_run_id!=req['run_id']:raise RuntimeError('worker_startup_run')
    channel=_BlockingPipeChannel(api,read_handle,write_handle)
    # GetStdHandle borrows process table handles; no separate CloseHandle/reopening by PID/name.
    channel.send_bounded(entry.encode_frame(0,req['run_id'],'INIT',entry.startup_ack(plan)))
    decoder=entry.FrameDecoder(req['run_id']);decoder.expected=1
    return entry.serve_native_worker(channel,plan.context,local_permit,_startup_decoder=decoder)


from dataclasses import dataclass
import struct
if __package__:
    from .benign_contract import (need, uint, hexstr, parse_json, canonical, sha,
                                  FILE_CAPS, SUCCESS_FILES, READY_DOMAIN, TERMINAL_DOMAIN)
    from .benign_evidence import (ExpectedTranscript, TranscriptExpectation, validate_ready,
                                 validate_terminal, build_authorization)
    from .benign_windows_fs import (read_bounded, publish_once, PendingArtifact, capture_snapshot,
                                   verify_static_members, PublicationUnknown, list_bounded)
    from .benign_runtime_gate import require_benign_run_authority

FRAME_LIMIT = 1048576
FRAME_COUNT_LIMIT = 1200
COMMANDS = ('INIT', 'BIND', 'READY', 'PUBLISH', 'TERMINAL', 'POSTEXIT', 'STOP')


def encode_frame(sequence, run_id, command, payload):
    uint(sequence, FRAME_COUNT_LIMIT - 1); hexstr(run_id, 32)
    need(command in COMMANDS and type(payload) is dict, 'frame_fields')
    raw = canonical({'sequence': sequence, 'run_id': run_id, 'command': command, 'payload': payload})
    need(0 < len(raw) <= FRAME_LIMIT, 'frame_size')
    if command == 'INIT': need(len(raw) <= STARTUP_CAP, 'startup_frame_size')
    return struct.pack('<I', len(raw)) + raw


class FrameDecoder:
    def __init__(self, run_id):
        hexstr(run_id, 32); self.run_id = run_id; self.expected = 0; self.buffer = b''; self.poisoned = False

    def feed(self, chunk):
        need(not self.poisoned and type(chunk) is bytes, 'frame_unusable')
        try:
            need(len(self.buffer) + len(chunk) <= FRAME_LIMIT + 4, 'frame_buffer_cap')
            self.buffer += chunk
            if len(self.buffer) < 4:
                return None
            n = struct.unpack('<I', self.buffer[:4])[0]
            need(0 < n <= FRAME_LIMIT, 'frame_length')
            if len(self.buffer) < n + 4:
                return None
            need(len(self.buffer) == n + 4, 'one_frame_per_exchange')
            obj = parse_json(self.buffer[4:], FRAME_LIMIT)
            need(type(obj) is dict and set(obj) == {'sequence', 'run_id', 'command', 'payload'}, 'frame_schema')
            uint(obj['sequence'], FRAME_COUNT_LIMIT - 1)
            need(obj['sequence'] == self.expected and obj['run_id'] == self.run_id and
                 obj['command'] in COMMANDS and type(obj['payload']) is dict, 'frame_binding')
            self.expected += 1; self.buffer = b''
            return obj
        except Exception:
            self.poisoned = True; raise


def pack_artifacts(raw):
    need(type(raw) is dict and set(raw).issubset(FILE_CAPS), 'artifact_set')
    need(all(type(v) is bytes and 0 < len(v) <= FILE_CAPS[k] for k, v in raw.items()), 'artifact_size')
    need(sum(len(v) for v in raw.values()) <= 262144, 'artifact_total')
    return {k: [v[i:i + 8192].hex() for i in range(0, len(v), 8192)] for k, v in raw.items()}


def unpack_artifacts(obj):
    need(type(obj) is dict and set(obj).issubset(FILE_CAPS), 'artifact_set')
    out = {}
    for k, parts in obj.items():
        need(type(parts) is list and 1 <= len(parts) <= 8, 'artifact_chunks')
        for p in parts:
            need(type(p) is str and 0 < len(p) <= 16384 and len(p) % 2 == 0, 'artifact_chunk')
            hexstr(p, len(p))
        data = bytes.fromhex(''.join(parts)); need(len(data) <= FILE_CAPS[k], 'artifact_size')
        out[k] = data
    need(sum(len(v) for v in out.values()) <= 262144, 'artifact_total')
    return out


@dataclass(frozen=True)
class WorkerReply:
    command: str
    status: str
    artifacts: tuple = ()
    crypto_receipts: tuple = ()
    materialization: object = None
    snapshot: object = None
    evidence_domain: str = 'OFFLINE_MODEL'
    publication_receipts: tuple = ()


class _ArtifactWorker:
    """Shared concrete artifact algorithm; construction via native gate in the future runner."""
    def __init__(self, expected, output, control, crypto, static_specs):
        need(type(expected) is ExpectedTranscript, 'worker_expected')
        self.expected, self.output, self.control = expected, output, control
        self.crypto, self.static_specs = crypto, static_specs
        self.ready = None; self.expectation = None; self.auth_attempted = False
        self.dead = False; self.calls = 0; self._protocol_phase = 'NEW'

    def handle(self, command, payload):
        need(not self.dead and command in COMMANDS[2:] and type(payload) is dict, 'worker_request')
        self.calls += 1; need(self.calls <= 1200, 'worker_poll_budget')
        try:
            if command == 'STOP':
                need(payload == {}, 'stop_payload'); self.dead = True
                return WorkerReply(command, 'STOPPED')
            need(payload == {}, 'worker_no_caller_bytes')
            if command == 'READY':
                need(self.ready is None, 'ready_already_pinned')
                # Marker first: only absent/sharing is PENDING, malformed completed bytes fail.
                marker = read_bounded(self.output, 'ready.commit.json', 4096).data
                data = {'ready.commit.json': marker,
                        'ready.json': read_bounded(self.output, 'ready.json', 65536).data,
                        'ready.sig': read_bounded(self.output, 'ready.sig', 64).data}
                ready = validate_ready(self.expected, data)
                receipt = self.crypto.verify(ready.key, READY_DOMAIN, ready.raw, ready.signature)
                material = verify_static_members(self.static_specs, 'before_retirement')
                self.ready = ready; self._protocol_phase = 'READY'
                return WorkerReply(command, 'READY', tuple(sorted(data.items())), (receipt,), material)
            need(self.ready is not None, 'ready_not_pinned')
            if command == 'PUBLISH':
                need(not self.auth_attempted, 'authorization_consumed'); self.auth_attempted = True
                auth, marker = build_authorization(self.ready)
                try:
                    data_receipt = publish_once(self.control, 'authorization.json', auth)
                    marker_receipt = publish_once(self.control, 'authorization.commit.json', marker)
                except Exception as exc:
                    self.dead = True
                    raise PublicationUnknown('PUBLICATION_UNKNOWN') from exc
                self.expectation = TranscriptExpectation(self.ready, auth, marker)
                self._protocol_phase = 'PUBLISHED'
                return WorkerReply(command, 'PUBLISHED', publication_receipts=(data_receipt, marker_receipt))
            need(self.expectation is not None, 'authorization_not_published')
            need(command in ('TERMINAL', 'POSTEXIT'), 'worker_command')
            need(self._protocol_phase == ('PUBLISHED' if command == 'TERMINAL' else 'TERMINAL'),
                 'worker_command_order')
            # No output acceptance until completed terminal marker is present.
            read_bounded(self.output, 'terminal.commit.json', 4096)
            phase = 'before_retirement' if command == 'TERMINAL' else 'after_retirement'
            snapshot = capture_snapshot(self.output, FILE_CAPS, phase)
            candidate = validate_terminal(self.expectation, snapshot.raw())
            receipts = (self.crypto.verify(self.ready.key, READY_DOMAIN, self.ready.raw, self.ready.signature),
                        self.crypto.verify(self.ready.key, TERMINAL_DOMAIN, candidate.terminal, candidate.signature))
            material = verify_static_members(self.static_specs, phase)
            # Control is reread as well; no rewrite of a published authorization.
            for n, b in (('authorization.json', self.expectation.authorization),
                         ('authorization.commit.json', self.expectation.authorization_commit)):
                need(read_bounded(self.control, n, 16384).data == b, 'control_changed')
            self._protocol_phase = command
            return WorkerReply(command, candidate.result, tuple(sorted(snapshot.raw().items())),
                               receipts, material, snapshot)
        except PendingArtifact:
            return WorkerReply(command, 'PENDING')
        except Exception:
            self.dead = True; raise


def serve_bound_channel(channel, context, permit=None):
    require_benign_run_authority(permit)
    # A future bound channel must prove its own exact worker handles; no CLI/JSON issuer here.
    return _serve(channel, context)


def _receive_one(channel, decoder):
    """Receive one frame including arbitrary header/body fragmentation. No pipelining."""
    while True:
        chunk = channel.receive_bounded(FRAME_LIMIT + 4 - len(decoder.buffer))
        need(type(chunk) is bytes and bool(chunk), 'truncated_frame')
        frame = decoder.feed(chunk)
        if frame is not None:
            return frame


def _serve(channel, context):
    """Already-bound fixture/source body. A frame is never a native receipt object."""
    decoder = FrameDecoder(context.expected.fields()['run_id']); sequence = 0
    while not context.dead:
        frame = _receive_one(channel, decoder)
        reply = context.handle(frame['command'], frame['payload'])
        body = encode_reply_observation(context, reply)
        channel.send_bounded(encode_frame(sequence, frame['run_id'], frame['command'], body))
        sequence += 1
    return 'WORKER_STOPPED'


IPC_SCHEMA = 'BEN01_OWNED_WORKER_IPC_V1'


def _base_observation(context, reply):
    expected = context.expected
    return {'schema': IPC_SCHEMA, 'status': reply.status,
            'request_sha256': sha(expected.request),
            'session_binding_sha256': expected.session_binding_sha256,
            'boot_binding': expected.boot_binding,
            'artifacts': pack_artifacts(dict(reply.artifacts)),
            'checks': {}, 'producer': 'OFFLINE_MODEL'}


def encode_reply_observation(context, reply):
    """Serialize checked local observations, NOT private seals and NOT a grant.
    Native classification requires the actual local providers on the producer side;
    the consumer still needs the separately owned worker channel before admission.
    """
    from .benign_windows_crypto import is_native_receipt
    from .benign_windows_fs import (is_native_snapshot, is_native_materialization,
                                   _WinFsApi, PublicationReceipt)
    need(type(reply) is WorkerReply, 'worker_reply_type')
    body = _base_observation(context, reply)
    expected = context.expected
    if reply.status in ('PENDING', 'STOPPED'):
        need(not reply.artifacts and not reply.crypto_receipts and reply.materialization is None
             and reply.snapshot is None and not reply.publication_receipts, 'empty_reply')
        return body
    if reply.command == 'READY':
        ready = validate_ready(expected, dict(reply.artifacts))
        checks = [{'domain_hex': READY_DOMAIN.hex(), 'payload_sha256': sha(ready.raw),
                   'key_sha256': sha(ready.key), 'signature_sha256': sha(ready.signature)}]
        native = (len(reply.crypto_receipts) == 1 and
                  is_native_receipt(reply.crypto_receipts[0], READY_DOMAIN, ready.raw, ready.key, ready.signature))
        phase = 'before_retirement'
    elif reply.command == 'PUBLISH':
        auth, commit = build_authorization(context.ready)
        rows = [('authorization.json', auth), ('authorization.commit.json', commit)]
        need(len(reply.publication_receipts) == 2, 'publication_receipts')
        for receipt, (name, raw) in zip(reply.publication_receipts, rows):
            need(type(receipt) is PublicationReceipt and
                 (receipt.name, receipt.bytes, receipt.sha256) == (name, len(raw), sha(raw)), 'publication_binding')
        body['checks'] = {'authorization_sha256': sha(auth), 'authorization_commit_sha256': sha(commit)}
        if type(context.control.engine.api) is _WinFsApi and all(
                r.evidence_domain == 'NATIVE_WIN32_LAB' for r in reply.publication_receipts):
            body['producer'] = 'LOCAL_NATIVE_CHECKS'
        return body
    else:
        need(reply.command in ('TERMINAL', 'POSTEXIT'), 'reply_command')
        candidate = validate_terminal(context.expectation, dict(reply.artifacts))
        ready = context.ready
        values = ((READY_DOMAIN, ready.raw, ready.signature),
                  (TERMINAL_DOMAIN, candidate.terminal, candidate.signature))
        checks = [{'domain_hex': d.hex(), 'payload_sha256': sha(b),
                   'key_sha256': sha(ready.key), 'signature_sha256': sha(sig)} for d, b, sig in values]
        native = len(reply.crypto_receipts) == 2 and all(
            is_native_receipt(r, d, b, ready.key, sig) for r, (d, b, sig) in zip(reply.crypto_receipts, values))
        phase = 'before_retirement' if reply.command == 'TERMINAL' else 'after_retirement'
        native = native and is_native_snapshot(reply.snapshot, phase)
    need(reply.materialization is not None, 'materialization_observation')
    body['checks'] = {'crypto': checks, 'phase': phase,
                      'materialization_sha256': reply.materialization.manifest_sha256,
                      'output_root': context.output.path}
    if reply.snapshot is not None:
        # Identity and write metadata, not raw native pointers/handles.
        body['checks']['files'] = [dict(name=x.name, volume=x.metadata.volume,
            file_id=x.metadata.file_id, links=x.metadata.links, size=x.metadata.size,
            write_time=x.metadata.write_time, attributes=x.metadata.attributes,
            final_path=x.metadata.final_path, disk_file=x.metadata.disk_file)
            for x in reply.snapshot.artifacts]
    native = native and is_native_materialization(reply.materialization, phase,
                                                   expected.materialization_sha256)
    if native:
        body['producer'] = 'LOCAL_NATIVE_CHECKS'
    return body


@dataclass(frozen=True)
class DecodedObservation:
    """Untrusted IPC data, regardless of any producer label. Cannot pass native predicates."""
    command: str
    status: str
    artifacts: tuple
    observation_bytes: bytes
    evidence_domain: str = 'OFFLINE_MODEL'


def decode_reply_observation(command, body, expected, ready=None):
    from .benign_contract import parse_benign
    from .benign_layout import winpath
    need(type(body) is dict and set(body) == {'schema', 'status', 'request_sha256',
         'session_binding_sha256', 'boot_binding', 'artifacts', 'checks', 'producer'}, 'reply_schema')
    need(body['schema'] == IPC_SCHEMA and body['request_sha256'] == sha(expected.request)
         and body['session_binding_sha256'] == expected.session_binding_sha256
         and body['boot_binding'] == expected.boot_binding, 'reply_context')
    need(body['producer'] in ('LOCAL_NATIVE_CHECKS', 'OFFLINE_MODEL'), 'reply_producer_label')
    need(type(body['checks']) is dict and command in COMMANDS[1:], 'reply_kind')
    raw = unpack_artifacts(body['artifacts']); status = body['status']; checks = body['checks']
    if status == 'PENDING':
        need(command in ('READY', 'TERMINAL') and not raw and not checks, 'invalid_pending_reply')
    elif command == 'STOP':
        need(status == 'STOPPED' and not raw and not checks, 'invalid_stop_reply')
    elif command == 'PUBLISH':
        need(status == 'PUBLISHED' and not raw and ready is not None, 'invalid_publish_reply')
        auth, completion = build_authorization(ready)
        need(checks == {'authorization_sha256': sha(auth), 'authorization_commit_sha256': sha(completion)},
             'publication_observation')
    else:
        need(command in ('READY', 'TERMINAL', 'POSTEXIT'), 'reply_command')
        keys = {'crypto', 'phase', 'materialization_sha256', 'output_root'}
        if command != 'READY':
            keys.add('files')
        need(set(checks) == keys, 'reply_checks_schema')
        phase = 'after_retirement' if command == 'POSTEXIT' else 'before_retirement'
        need(checks['phase'] == phase and checks['materialization_sha256'] == expected.materialization_sha256,
             'reply_materialization_binding')
        winpath(checks['output_root'])
        if command == 'READY':
            need(status == 'READY', 'ready_status')
            pinned = validate_ready(expected, raw)
            values = ((READY_DOMAIN, pinned.raw, pinned.signature),)
        else:
            need(ready is not None, 'reply_without_ready')
            pinned = ready; expectation = TranscriptExpectation(ready, *build_authorization(ready))
            candidate = validate_terminal(expectation, raw)
            need(status == candidate.result, 'terminal_status')
            values = ((READY_DOMAIN, ready.raw, ready.signature),
                      (TERMINAL_DOMAIN, candidate.terminal, candidate.signature))
            files = checks['files']
            need(type(files) is list and len(files) == len(raw), 'metadata_count')
            need([r.get('name') for r in files] == sorted(raw), 'metadata_inventory')
            for r in files:
                need(set(r) == {'name', 'volume', 'file_id', 'links', 'size', 'write_time',
                               'attributes', 'final_path', 'disk_file'}, 'metadata_fields')
                for k in ('volume', 'file_id', 'links', 'size', 'write_time', 'attributes'): uint(r[k])
                need(r['links'] == 1 and not r['attributes'] & (0x10 | 0x400) and r['disk_file'] is True
                     and r['size'] == len(raw[r['name']]), 'metadata_type_or_size')
                need(r['final_path'].casefold() == (checks['output_root'] + '\\' + r['name']).casefold(),
                     'metadata_path')
        expected_crypto = [{'domain_hex': d.hex(), 'payload_sha256': sha(b),
                            'key_sha256': sha(pinned.key), 'signature_sha256': sha(sig)} for d, b, sig in values]
        need(checks['crypto'] == expected_crypto, 'crypto_observation_binding')
    return DecodedObservation(command, status, tuple(sorted(raw.items())), canonical(body))


@dataclass(frozen=True)
class WorkerContextSpec:
    """Prelaunch binding data; no authority and no caller-selected executable/callback."""
    request: bytes
    output_path: str
    control_path: str
    static_roots: tuple
    materialization_sha256: str
    supervisor_binding: str

    def validate(self):
        from .benign_layout import winpath
        from .benign_contract import parse_benign
        parse_benign('request', self.request); hexstr(self.materialization_sha256)
        hexstr(self.supervisor_binding); winpath(self.output_path); winpath(self.control_path)
        need(self.output_path.casefold() != self.control_path.casefold(), 'worker_root_overlap')
        rows = []
        need(type(self.static_roots) is tuple and self.static_roots, 'static_roots')
        paths = {self.output_path.casefold(), self.control_path.casefold()}
        for role, path, specs in self.static_roots:
            winpath(path); need(type(role) is str and type(specs) is tuple and specs, 'static_spec')
            need(path.casefold() not in paths, 'static_role_overlap'); paths.add(path.casefold())
            for name, size, expected in specs:
                from .benign_layout import component
                component(name); uint(size, 32 * 1024**2); hexstr(expected)
                rows.append(dict(role=role, name=name, bytes=size, sha256=expected))
        rows.sort(key=lambda r: (r['role'], r['name']))
        need(len({(r['role'], r['name'].casefold()) for r in rows}) == len(rows), 'static_duplicates')
        need(sha(canonical(rows)) == self.materialization_sha256, 'static_manifest_pin')
        return self


class _WorkerContextOwner:
    """Concrete resource assembly. Fake APIs can test assembly; do not issue native receipts."""
    def __init__(self, spec, fs_engine, crypto, session_sha):
        spec.validate(); hexstr(session_sha)
        self.roots = []; self.worker = None
        try:
            def root(path):
                value = fs_engine.open_root(path); self.roots.append(value); return value
            output, control = root(spec.output_path), root(spec.control_path)
            static = tuple((role, root(path), entries) for role, path, entries in spec.static_roots)
            expected = ExpectedTranscript(spec.request, session_sha, spec.supervisor_binding,
                                          spec.materialization_sha256)
            self.worker = _ArtifactWorker(expected, output, control, crypto, static)
        except Exception:
            self.close(); raise

    def close(self):
        errors = []
        while self.roots:
            r = self.roots.pop()
            try: r.close()
            except Exception as exc: errors.append(exc)
        if errors:
            from .benign_contract import BenignError
            raise BenignError('worker_roots_close_unknown') from errors[0]


def serve_native_worker(channel, spec, permit=None, *, _startup_decoder=None):
    """Closed concrete child path. A future issuer must bind the inherited channel/spec.
    No JSON reconstruction of permit is present in this delivery.
    """
    require_benign_run_authority(permit)
    from .benign_windows_fs import _FsEngine, _WinFsApi
    from .benign_windows_crypto import _CryptoEngine, _BcryptApi
    from .benign_contract import parse_benign
    spec.validate(); req = parse_benign('request', spec.request).fields
    need(type(_startup_decoder) is FrameDecoder and _startup_decoder.run_id == req['run_id'] and
         _startup_decoder.expected == 1 and not _startup_decoder.poisoned and not _startup_decoder.buffer,
         'checked_first_process_required')
    decoder = _startup_decoder
    frame = _receive_one(channel, decoder)
    need(frame['command'] == 'BIND' and set(frame['payload']) == {'session_binding_sha256'}, 'bind_first')
    session_sha = hexstr(frame['payload']['session_binding_sha256'])
    owner = _WorkerContextOwner(spec, _FsEngine(_WinFsApi(permit)), _CryptoEngine(_BcryptApi(permit)), session_sha)
    try:
        channel.send_bounded(encode_frame(1, req['run_id'], 'BIND',
            {'bound_request_sha256': sha(spec.request), 'session_binding_sha256': session_sha}))
        sequence = 2
        while not owner.worker.dead:
            f = _receive_one(channel, decoder)
            reply = owner.worker.handle(f['command'], f['payload'])
            body = encode_reply_observation(owner.worker, reply)
            channel.send_bounded(encode_frame(sequence, req['run_id'], f['command'], body)); sequence += 1
    finally:
        owner.close()


class _ExchangeSlot:
    """Bounded deterministic mailbox. poll has no I/O/wait; exactly one exchange at a time."""
    def __init__(self, run_id):
        hexstr(run_id, 32); self.run_id = run_id
        self.sequence = 0; self.pending = self.response = self.error = None; self.poisoned = False

    def submit(self, command, payload):
        need(not self.poisoned and self.pending is None and self.response is None and self.error is None,
             'single_exchange_slot')
        raw = encode_frame(self.sequence, self.run_id, command, payload)
        self.pending = (self.sequence, command, raw)
        return raw

    def complete(self, frame):
        need(not self.poisoned and self.pending is not None, 'unexpected_response')
        sequence, command, _ = self.pending
        need(frame['run_id'] == self.run_id and frame['sequence'] == sequence and frame['command'] == command,
             'reply_sequence_command')
        self.response = frame; self.pending = None; self.sequence += 1

    def fail(self, exc):
        self.poisoned = True; self.error = str(exc); self.pending = self.response = None

    def poll(self):
        if self.error is not None:
            from .benign_contract import BenignError
            raise BenignError('pipe_exchange_failed:' + self.error)
        out = self.response; self.response = None
        return out


def _exchange(channel, raw, decoder):
    channel.send_bounded(raw)
    return _receive_one(channel, decoder)


class _NativePipePump:
    """All synchronous Win32 pipe calls run on ONE dedicated thread.
    The watchdog only uses try-lock mailbox operations. Cancellation is not completion;
    if the pump cannot be joined within budget its handles are quarantined, not reused.
    """
    def __init__(self, owner, run_id, permit=None):
        from .benign_runtime_gate import require_native_authority
        require_native_authority(permit)
        from .benign_windows_session import _OwnedWorker, _WinProcessApi, _BlockingPipeChannel
        need(type(owner) is _OwnedWorker and type(owner.api) is _WinProcessApi, 'native_owned_worker')
        import threading
        self.owner = owner; self.slot = _ExchangeSlot(run_id); self.decoder = FrameDecoder(run_id)
        self.channel = _BlockingPipeChannel(owner.api, owner.output_read, owner.input_write)
        self.lock = threading.Lock(); self.wake = threading.Event(); self.stopping = threading.Event()
        self.thread = threading.Thread(target=self._loop, name='BEN01-ArtifactPipe', daemon=True)
        self.started = False; self.thread_started = False; self.stop_attempted = False; self.quarantined = False

    def start_once(self):
        need(not self.started, 'pump_start_consumed'); self.started = True; self.thread.start(); self.thread_started = True

    def send_nonblocking(self, command, payload):
        need(self.started and not self.stopping.is_set(), 'pump_not_running')
        need(self.lock.acquire(blocking=False), 'pump_mailbox_busy')
        try: self.slot.submit(command, payload)
        finally: self.lock.release()
        self.wake.set()

    def poll_nonblocking(self):
        need(self.started and not self.stopping.is_set(), 'pump_not_running')
        if not self.lock.acquire(blocking=False): return None
        try: return self.slot.poll()
        finally: self.lock.release()

    def _loop(self):
        while True:
            self.wake.wait(); self.wake.clear()
            if self.stopping.is_set(): return
            with self.lock:
                pending = self.slot.pending
            if pending is None: continue
            try:
                frame = _exchange(self.channel, pending[2], self.decoder)
                with self.lock: self.slot.complete(frame)
            except Exception as exc:
                with self.lock: self.slot.fail(exc)
                return

    def stop_once(self, budget_ms=10000):
        need(not self.stop_attempted, 'pump_stop_consumed'); self.stop_attempted = True
        uint(budget_ms, 10000); need(budget_ms > 0, 'pump_stop_budget')
        self.stopping.set(); self.wake.set()
        started = self.owner.api.now_ns(); errors = []
        if self.thread.is_alive() and self.thread.native_id:
            try: self.owner.api.cancel_thread_io(self.thread.native_id)
            except Exception as exc: errors.append(exc)
        # Closing the peer process releases inherited pipe ends; it does not justify PASS.
        try:
            remaining = max(1, budget_ms - (self.owner.api.now_ns() - started) // 1_000_000)
            self.owner.stop_once(int(remaining))
        except Exception as exc: errors.append(exc)
        remaining = max(0, budget_ms - (self.owner.api.now_ns() - started) // 1_000_000)
        if self.thread_started: self.thread.join(remaining / 1000)
        if self.thread.is_alive():
            self.quarantined = True
            from .benign_contract import BenignError
            raise BenignError('pump_join_unknown_keep_handles')
        self.owner.close_pipes()
        if errors:
            from .benign_contract import BenignError
            raise BenignError('pump_cleanup_unknown') from errors[0]


STARTUP_KIND = 'BEN01_WORKER_INGRESS_V1'
STARTUP_CAP = 262144
WORKER_MODULES = ('__init__.py', 'benign_capsule.py', 'benign_contract.py',
                  'benign_evidence.py', 'benign_layout.py', 'benign_runtime_gate.py',
                  'benign_windows_crypto.py', 'benign_windows_fs.py',
                  'benign_windows_session.py', 'benign_worker.py')


def _context_fields(spec):
    need(type(spec) is WorkerContextSpec, 'startup_context_type'); spec.validate()
    return dict(request_hex=spec.request.hex(), output_path=spec.output_path,
                control_path=spec.control_path, supervisor_binding=spec.supervisor_binding,
                materialization_sha256=spec.materialization_sha256,
                static_roots=[{'role': role, 'path': path,
                               'files': [dict(name=n, bytes=size, sha256=h) for n, size, h in rows]}
                              for role, path, rows in spec.static_roots])


def _context_from_fields(value):
    need(type(value) is dict and set(value) == {'request_hex', 'output_path', 'control_path',
         'supervisor_binding', 'materialization_sha256', 'static_roots'}, 'startup_context_schema')
    text = value['request_hex']
    need(type(text) is str and 0 < len(text) <= 65536 and len(text) % 2 == 0, 'startup_request_size')
    hexstr(text, len(text)); roots = value['static_roots']
    need(type(roots) is list and 1 <= len(roots) <= 16, 'startup_static_roots')
    decoded = []
    for row in roots:
        need(type(row) is dict and set(row) == {'role', 'path', 'files'}, 'startup_static_row')
        files = row['files']; need(type(files) is list and 0 < len(files) <= 128, 'startup_static_files')
        need(all(type(f) is dict and set(f) == {'name', 'bytes', 'sha256'} for f in files),
             'startup_static_file_schema')
        decoded.append((row['role'], row['path'], tuple((f['name'], f['bytes'], f['sha256']) for f in files)))
    return WorkerContextSpec(bytes.fromhex(text), value['output_path'], value['control_path'],
                             tuple(decoded), value['materialization_sha256'], value['supervisor_binding']).validate()


@dataclass(frozen=True)
class WorkerIngressPlan:
    """Checked data only. No local permit, peer seal, PID handle or native provenance."""
    raw: bytes
    context: WorkerContextSpec
    source_root: str
    source_files: tuple
    executable: str
    executable_bytes: int
    executable_sha256: str
    worker_binding: bytes
    evidence_domain: str = 'OFFLINE_MODEL'


def parse_worker_ingress(raw):
    from .benign_capsule import SOURCE_PATHS
    from .benign_layout import winpath
    from .benign_contract import parse_benign
    need(type(raw) is bytes and len(raw) <= STARTUP_CAP, 'startup_size')
    obj = parse_json(raw, STARTUP_CAP)
    fields = {'kind', 'role', 'context', 'source_root', 'source_files', 'executable',
              'executable_bytes', 'executable_sha256', 'worker_binding'}
    need(type(obj) is dict and set(obj) == fields and obj['kind'] == STARTUP_KIND and
         obj['role'] == 'ARTIFACT_WORKER', 'startup_schema_or_role')
    spec = _context_from_fields(obj['context'])
    req = parse_benign('request', spec.request).fields
    source_root = winpath(obj['source_root']); executable = winpath(obj['executable'])
    need(source_root == obj['source_root'] and executable == obj['executable'], 'startup_path_canonical')
    uint(obj['executable_bytes'], 32 * 1024**2); need(obj['executable_bytes'] > 0, 'startup_python_size')
    hexstr(obj['executable_sha256'])
    rows = obj['source_files']
    need(type(rows) is list and len(rows) == len(SOURCE_PATHS) and
         all(type(r) is dict and set(r) == {'path', 'bytes', 'sha256'} for r in rows), 'startup_source_rows')
    need([r['path'] for r in rows] == sorted(SOURCE_PATHS), 'startup_exact_source_set')
    for row in rows:
        uint(row['bytes'], 262144); hexstr(row['sha256'])
    calculated = sha(canonical([r for r in rows if r['path'].endswith(('.py', '.ps1'))]))
    need(calculated == req['source_sha256'], 'startup_source_pin')
    bound = obj['worker_binding']
    need(type(bound) is dict and set(bound) == {'kind', 'supervisor_incarnation', 'process',
         'script', 'executable_sha256', 'source_sha256'} and bound['kind'] == 'BEN01_OWNED_WORKER_V1',
         'startup_binding_schema')
    need(bound['supervisor_incarnation'] == spec.supervisor_binding and
         bound['script'] == source_root + '\\benign_worker.py' and
         bound['executable_sha256'] == obj['executable_sha256'] and
         bound['source_sha256'] == calculated, 'startup_binding_pins')
    proc = bound['process']
    need(type(proc) is dict and set(proc) == {'pid', 'created', 'path', 'session_id',
         'authentication_id', 'user_sid'}, 'startup_process_schema')
    for field in ('pid', 'created', 'session_id', 'authentication_id'): uint(proc[field])
    need(0 < proc['pid'] <= 0xffffffff and proc['created'] > 0 and proc['authentication_id'] > 0,
         'startup_process_values')
    need(winpath(proc['path']) == executable and type(proc['user_sid']) is str and
         proc['user_sid'].startswith('S-1-') and len(proc['user_sid']) <= 184, 'startup_process_image_or_user')
    return WorkerIngressPlan(raw, spec, source_root,
          tuple((r['path'], r['bytes'], r['sha256']) for r in rows), executable,
          obj['executable_bytes'], obj['executable_sha256'], canonical(bound))


def build_worker_ingress(spec, source_root, source_files, pin, executable_bytes, binding):
    from .benign_windows_session import WorkerSourcePin
    need(type(pin) is WorkerSourcePin and type(source_files) is tuple, 'startup_program_type')
    pin.validate()
    need(pin.script == source_root + '\\benign_worker.py', 'startup_program_location')
    obj = dict(kind=STARTUP_KIND, role='ARTIFACT_WORKER', context=_context_fields(spec),
               source_root=source_root, source_files=[dict(path=p, bytes=n, sha256=h) for p, n, h in source_files],
               executable=pin.executable, executable_bytes=executable_bytes,
               executable_sha256=pin.executable_sha256, worker_binding=parse_json(binding, 8192))
    raw = canonical(obj); plan = parse_worker_ingress(raw)
    need(parse_json(plan.worker_binding)['source_sha256'] == pin.source_sha256, 'startup_program_source')
    return raw


def validate_worker_ingress_observation(plan, observed_process, executable, script):
    """Pure comparison. A matching ProcessIdentity is still data, not native admission."""
    from .benign_windows_session import ProcessIdentity
    need(type(plan) is WorkerIngressPlan and parse_worker_ingress(plan.raw) == plan, 'startup_plan_recheck')
    need(type(observed_process) is ProcessIdentity and
         observed_process.descriptor() == parse_json(plan.worker_binding)['process'], 'startup_own_process_mismatch')
    need(executable == plan.executable and script == plan.source_root + '\\benign_worker.py',
         'startup_first_image_mismatch')
    return {'startup_sha256': sha(plan.raw), 'worker_binding_sha256': sha(plan.worker_binding),
            'request_sha256': sha(plan.context.request), 'scope': 'CHECKED_DATA_NOT_AUTHORITY'}


def startup_ack(plan):
    need(type(plan) is WorkerIngressPlan, 'startup_plan')
    return {'startup_sha256': sha(plan.raw), 'worker_binding_sha256': sha(plan.worker_binding),
            'request_sha256': sha(plan.context.request)}


class _StartupHandshake:
    """One INIT/ACK before BIND. This pure helper cannot admit a native peer."""
    def __init__(self, plan):
        need(type(plan) is WorkerIngressPlan and parse_worker_ingress(plan.raw) == plan, 'startup_plan')
        self.plan = plan; self.attempted = self.accepted = self.failed = False

    def payload_once(self):
        need(not self.attempted and not self.failed, 'startup_consumed'); self.attempted = True
        return parse_json(self.plan.raw, STARTUP_CAP)

    def accept(self, frame):
        try:
            need(self.attempted and not self.failed and not self.accepted, 'startup_ack_order')
            from .benign_contract import parse_benign
            rid = parse_benign('request', self.plan.context.request).fields['run_id']
            need(type(frame) is dict and set(frame) == {'sequence', 'run_id', 'command', 'payload'},
                 'startup_ack_frame')
            need(type(frame['sequence']) is int and frame['sequence'] == 0 and
                 frame['run_id'] == rid and frame['command'] == 'INIT' and frame['payload'] == startup_ack(self.plan),
                 'startup_ack_mismatch')
            self.accepted = True
        except Exception:
            self.failed = True; raise
        return True
