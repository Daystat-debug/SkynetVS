"""Supervisor algorithm and gated live entry. It never opens guest Output directly.
The I/O worker is polled nonblocking; all launch/auth budgets are consumed before calls.
"""
from dataclasses import dataclass, replace
from .benign_contract import need, sha, canonical, parse_json, uint, BenignError
from .benign_state import new_state, HostEvent, transition_benign
from .benign_evidence import (ExpectedTranscript, validate_ready, build_authorization,
                             TranscriptExpectation, validate_terminal, snapshot_digest,
                             finalize_lab, NativeReceipts)
from .benign_windows_session import RetirementObservation
from .benign_runtime_gate import require_benign_run_authority


@dataclass(frozen=True)
class LabOutcome:
    result: str
    launch_attempts: int
    worker_attempts: int
    authorization_attempts: int
    retired: bool
    failure_sticky: bool
    reason: str
    evidence_domain: str = 'OFFLINE_MODEL'
    runtime_authorized: bool = False


def orchestrate_benign(bound_context, permit=None):
    require_benign_run_authority(permit)
    # No source-delivery constructor issues a live permit; native binding source stays gated.
    need(type(bound_context) is _NativeBoundContext, 'native_context_required')
    return _run_engine(bound_context, native=True)


def _orchestrate(ctx):
    return _run_engine(ctx, native=False)


def _run_engine(ctx, native=False):
    """Offline fixture seam. Production binding/issuer remains a separate reviewed step.
    Required ports: clock, session, worker (nonblocking), ledger, fixed capsule/launch pins.
    A caller-created context can never yield BENIGN_SANDBOX_TRANSPORT_PASS_LAB_ONLY.
    """
    request = ctx.descriptor.fields(); started = ctx.clock.now_ns()
    state = new_state(request['run_id'], request['nonce'], request['boot_binding'], started)
    grant = binding = launch = None; worker_attempts = launch_attempts = auth_attempts = 0
    ready = expectation = before = after = retirement = None
    crypto_pre = crypto_post = material_pre = material_post = None
    peer_before = peer_after = None; verdict = None
    if native:
        need(type(ctx) is _NativeBoundContext and ctx._seal is _CONTEXT_SEAL, 'sealed_native_context')
    outstanding = None; count = 0; successful = False

    def event(kind, payload=None, session_sha=None):
        nonlocal state
        e = HostEvent(kind, ctx.clock.now_ns(), state.run_id, state.nonce, state.boot_binding,
                      session_sha if session_sha is not None else state.session_sha256, payload)
        state = transition_benign(state, e).state
        # A delayed observation must not allow a later publication/launch in this turn.
        if state.failure_sticky and kind not in ('FAILURE', 'UNKNOWN'):
            raise BenignError('state_refused:' + state.reason)
        return state

    def send(command):
        nonlocal outstanding, count
        from .benign_worker import FRAME_COUNT_LIMIT
        limit = FRAME_COUNT_LIMIT - 2 if native else FRAME_COUNT_LIMIT
        need(outstanding is None and count < limit, 'single_outstanding_frame')
        # send_nonblocking must only enqueue; it must not call mapping reads in supervisor.
        ctx.worker.send_nonblocking(command, {}); outstanding = command; count += 1

    try:
        grant = ctx.ledger.reserve(ctx.descriptor); event('RESERVE')
        baseline = ctx.session.snapshot_complete()
        need(baseline.complete and not baseline.processes and baseline.boot_binding == state.boot_binding,
             'baseline_unproven')
        worker_attempts += 1; ctx.worker.start_once()
        if native:
            _await_worker_initialization(ctx.worker, ctx.clock, state.deadline_ns, lambda: event('TICK'))
        ctx.ledger.launch_intent(grant); event('LAUNCH')
        launch_attempts += 1
        launch = ctx.session.launch(ctx.executable, ctx.config_path, ctx.config_bytes, sha(ctx.config_bytes))
        while True:
            event('TICK')
            if state.failure_sticky:
                break
            if binding is None:
                scan = ctx.session.snapshot_complete()
                need(scan.boot_binding == state.boot_binding, 'boot_changed')
                if scan.processes:
                    binding = ctx.session.bind(launch, scan, state.run_id, state.nonce, request['request_sha256'])
                    event('BIND', session_sha=binding.binding_sha256)
                    ctx.worker.bind_expected(ExpectedTranscript(ctx.descriptor.request, binding.binding_sha256,
                                                               state.boot_binding, ctx.materialization_sha256))
                    send('READY')
            else:
                # Does not read Output; the session observer rejects foreign/replacement identities.
                obs = ctx.session.observe(binding)
                if obs is not None:
                    retirement = obs
                    if state.phase == 'TERMINAL_PENDING' and outstanding is None:
                        event('RETIRE', obs)
                        if not state.failure_sticky:
                            send('POSTEXIT')
                    elif state.phase == 'AUTH_PUBLISHED' and outstanding == 'TERMINAL':
                        pass  # Save retirement; terminal IPC may legitimately arrive later.
                    elif state.phase not in ('RETIRED', 'POSTEXIT_CHECKED', 'RECORDED'):
                        raise BenignError('guest_retired_before_terminal')
            reply = ctx.worker.poll_nonblocking()
            if reply is not None:
                need(outstanding == reply.command, 'worker_reply_sequence')
                command = outstanding; outstanding = None
                if reply.status == 'PENDING':
                    send(command)
                elif command == 'READY':
                    ready = validate_ready(ctx.worker.expected, dict(reply.artifacts))
                    # Fake receipt is usable for a fake trace, not for native finalization.
                    need(len(reply.crypto_receipts) == 1, 'ready_crypto_receipt')
                    if native:
                        need(is_admitted_peer(reply.crypto_receipts[0], 'READY', ctx.worker), 'ready_peer_required')
                    event('READY')
                    auth, marker = build_authorization(ready)
                    ctx.ledger.authorization_intent(grant, auth, marker); event('AUTH_INTENT')
                    auth_attempts += 1; send('PUBLISH')
                elif command == 'PUBLISH':
                    need(reply.status == 'PUBLISHED', 'publication_unknown')
                    if native:
                        need(len(reply.publication_receipts) == 1 and
                             is_admitted_peer(reply.publication_receipts[0], 'PUBLISH', ctx.worker),
                             'publication_peer_required')
                    event('AUTH_PUBLISHED')
                    expectation = TranscriptExpectation(ready, *build_authorization(ready)); send('TERMINAL')
                elif command == 'TERMINAL':
                    candidate = validate_terminal(expectation, dict(reply.artifacts))
                    before = reply.snapshot; crypto_pre = reply.crypto_receipts; material_pre = reply.materialization
                    event('TERMINAL', (candidate.result, candidate.snapshot_sha256))
                    if native:
                        peer_before = ctx.worker.last_admitted
                        need(is_admitted_peer(peer_before, 'TERMINAL', ctx.worker), 'terminal_peer_required')
                    if retirement is not None:
                        event('RETIRE', retirement)
                        if not state.failure_sticky: send('POSTEXIT')
                elif command == 'POSTEXIT':
                    candidate = validate_terminal(expectation, dict(reply.artifacts))
                    after = reply.snapshot; crypto_post = reply.crypto_receipts; material_post = reply.materialization
                    event('POSTEXIT', candidate.snapshot_sha256)
                    need(not state.failure_sticky, 'postexit_failure')
                    # Reconstruct no local native seals from wire data. Admission remains tied to our own worker.
                    if native:
                        peer_after = ctx.worker.last_admitted
                        verdict = finalize_peer_lab(expectation, peer_before, peer_after, retirement, ctx.worker)
                    event('RECORD'); successful = True; break
                else:
                    raise BenignError('worker_reply_unknown')
            ctx.clock.sleep_ns(250_000_000)
    except Exception as exc:
        event('FAILURE', str(exc))
        if grant is not None and auth_attempts and expectation is None:
            try:
                ctx.ledger.publication_failed(grant)
            except Exception:
                # Persisting an unknown result can fail too; cleanup still must run.
                event('UNKNOWN')
    finally:
        # Stop only the one own worker. A timeout never starts a replacement.
        if worker_attempts:
            try:
                ctx.worker.stop_once()
            except Exception:
                event('UNKNOWN')
        if state.failure_sticky and binding is not None:
            try:
                ctx.session.cleanup(binding, 10000)
                # A successful kill call is not retirement; no fake normal receipt minted here.
            except Exception:
                pass
        if binding is not None or launch is not None:
            try:
                ctx.session.release(binding if binding is not None else launch)
            except Exception:
                event('UNKNOWN')
        if grant is not None:
            try:
                # Fake outcomes never write a positive live outcome.
                ctx.ledger.outcome(grant, (('PASS_LAB_ONLY' if native else 'OFFLINE_FAKE_COMPLETED')
                          if successful and not state.failure_sticky else 'FAILED_RETIRED') if state.retired else 'UNKNOWN', state.retired)
            except Exception:
                event('UNKNOWN')
                ctx.ledger.close()
        if native:
            if not worker_attempts:
                try: ctx.worker.program_pins.close()
                except Exception: event('UNKNOWN')
            try: ctx.ledger.store.root.close()
            except Exception: event('UNKNOWN')
    result = ('BENIGN_SANDBOX_TRANSPORT_PASS_LAB_ONLY' if native else 'OFFLINE_FAKE_TRACE_VALID_NO_AUTHORITY')
    if not successful or state.failure_sticky:
        result = 'BENIGN_SANDBOX_TRANSPORT_FAILED' if native else 'OFFLINE_FAKE_TRACE_FAILED'
    return LabOutcome(result, launch_attempts, worker_attempts, auth_attempts,
                      state.retired, state.failure_sticky, state.reason,
                      'BENIGN_SANDBOX_LAB' if native else 'OFFLINE_MODEL')


def finalize_native_bound(expected, receipts, snapshots, permit=None):
    """Not reachable from fake orchestration; future trusted runner must separately issue a permit."""
    require_benign_run_authority(permit)
    return finalize_lab(expected, receipts, snapshots)


_PEER_SEAL = object()
_CONTEXT_SEAL = object()


@dataclass(frozen=True)
class _AdmittedPeerReply:
    """Parent-side own-channel receipt, not a deserialized CNG/FS receipt.
    These semantics trust pinned worker code and exclusive handle inheritance.
    They do not cover hostile same-process/admin mutation or authenticate a VM.
    """
    command: str
    sequence: int
    observation_bytes: bytes
    worker_binding_sha256: str
    _owner: object
    _seal: object


def is_admitted_peer(receipt, command, owner):
    return (type(owner) is _BoundWorkerPort and owner._native and
            type(receipt) is _AdmittedPeerReply and receipt._seal is _PEER_SEAL and
            receipt._owner is owner and receipt.command == command and
            owner._issued.get(receipt.sequence) is receipt and
            receipt.worker_binding_sha256 == owner.worker_binding)


class _BoundWorkerPort:
    """Concrete parent IPC controller. It never synchronously reads mappings/pipes.
    Only the gated exact native factory can supply its own native process/pump.
    Structural-only decoders/fake contexts cannot create admitted native receipts.
    """
    def __init__(self, owner, context_spec, program_pins, permit=None, *, startup_program=None):
        require_benign_run_authority(permit)
        from .benign_windows_session import _OwnedWorker, _WinProcessApi
        from .benign_worker import WorkerContextSpec
        need(type(owner) is _OwnedWorker and type(owner.api) is _WinProcessApi, 'own_native_worker')
        need(type(context_spec) is WorkerContextSpec, 'worker_context_spec')
        from .benign_windows_fs import _RetainedFiles, _WinFsApi
        need(type(program_pins) is _RetainedFiles and type(program_pins.engine.api) is _WinFsApi,
             'native_retained_program_required')
        program_pins.check(); self.program_pins = program_pins
        context_spec.validate()
        self.owner, self.context_spec, self.permit = owner, context_spec, permit
        self.expected = self.ready = self.pump = None
        self.binding_pending = False; self.deferred = None; self.last_admitted = None
        self.worker_binding = ''; self._issued = {}; self._native = True
        self.started = self.stopped = False
        need(type(startup_program) is tuple and len(startup_program) == 3, 'startup_program_parameters')
        self.startup_program = startup_program; self.startup_handshake = None

    def start_once(self):
        from .benign_worker import _NativePipePump
        from .benign_contract import parse_benign
        need(not self.started, 'worker_start_consumed'); self.started = True
        try:
            self.program_pins.check(); self.owner.start_once(); self.program_pins.check()
            self.worker_binding = sha(self.owner.binding_bytes())
            rid = parse_benign('request', self.context_spec.request).fields['run_id']
            self.pump = _NativePipePump(self.owner, rid, self.permit); self.pump.start_once()
            from .benign_worker import build_worker_ingress, parse_worker_ingress, _StartupHandshake
            root, rows, executable_bytes = self.startup_program
            raw = build_worker_ingress(self.context_spec, root, rows, self.owner.source_pin,
                                       executable_bytes, self.owner.binding_bytes())
            self.startup_handshake = _StartupHandshake(parse_worker_ingress(raw))
            self.pump.send_nonblocking('INIT', self.startup_handshake.payload_once())
        except Exception:
            if self.pump is None and not self.owner.stop_attempted:
                try: self.owner.stop_once()
                finally: self.owner.close_pipes()
            raise

    def initialization_complete(self):
        need(self.started and not self.stopped and self.startup_handshake is not None, 'worker_init_not_started')
        self.owner.check_live(); self.program_pins.check()
        need(sha(self.owner.binding_bytes()) == self.worker_binding, 'worker_initial_binding_changed')
        if self.startup_handshake.accepted: return True
        frame = self.pump.poll_nonblocking()
        if frame is None: return False
        self.startup_handshake.accept(frame)
        return True

    def bind_expected(self, expected):
        need(self.started and not self.stopped and self.expected is None and
             type(expected) is ExpectedTranscript and self.startup_handshake is not None and
             self.startup_handshake.accepted and not self.startup_handshake.failed, 'worker_bind_once')
        need(expected.request == self.context_spec.request and
             expected.boot_binding == self.context_spec.supervisor_binding and
             expected.materialization_sha256 == self.context_spec.materialization_sha256, 'worker_spec_binding')
        self.owner.check_live(); self.expected = expected; self.binding_pending = True
        self.pump.send_nonblocking('BIND', {'session_binding_sha256': expected.session_binding_sha256})

    def send_nonblocking(self, command, payload):
        need(self.expected is not None and not self.stopped and payload == {}, 'bound_worker_request')
        self.owner.check_live()
        if self.binding_pending:
            need(command == 'READY' and self.deferred is None, 'single_deferred_ready')
            self.deferred = (command, payload)
        else:
            self.pump.send_nonblocking(command, payload)

    def poll_nonblocking(self):
        from .benign_worker import decode_reply_observation, WorkerReply
        if self.stopped: raise BenignError('worker_stopped')
        self.owner.check_live()
        frame = self.pump.poll_nonblocking()
        if frame is None: return None
        self.owner.check_live()
        need(sha(self.owner.binding_bytes()) == self.worker_binding, 'worker_binding_changed')
        command, body = frame['command'], frame['payload']
        if self.binding_pending:
            need(frame['sequence'] == 1 and command == 'BIND' and
                 body == {'bound_request_sha256': sha(self.context_spec.request),
                          'session_binding_sha256': self.expected.session_binding_sha256}, 'worker_bind_ack')
            self.binding_pending = False
            need(self.deferred is not None, 'ready_deferred')
            request = self.deferred; self.deferred = None; self.pump.send_nonblocking(*request)
            return None
        decoded = decode_reply_observation(command, body, self.expected, self.ready)
        if decoded.status in ('PENDING', 'STOPPED'):
            return WorkerReply(command, decoded.status)
        # The label is checked in addition to own-channel provenance, never instead of it.
        need(body['producer'] == 'LOCAL_NATIVE_CHECKS', 'worker_did_not_run_native_checks')
        if command != 'PUBLISH':
            need(body['checks']['output_root'].casefold() == self.context_spec.output_path.casefold(), 'worker_output_binding')
        sequence = frame['sequence']; need(sequence not in self._issued, 'duplicate_admission')
        receipt = _AdmittedPeerReply(command, sequence, decoded.observation_bytes,
                                     self.worker_binding, self, _PEER_SEAL)
        self._issued[sequence] = receipt; self.last_admitted = receipt
        if command == 'READY': self.ready = validate_ready(self.expected, dict(decoded.artifacts))
        return WorkerReply(command, decoded.status, decoded.artifacts,
                           (receipt,) if command != 'PUBLISH' else (), receipt, receipt,
                           'OWNED_WORKER_CHANNEL', (receipt,) if command == 'PUBLISH' else ())

    def stop_once(self):
        need(not self.stopped, 'worker_stop_consumed'); self.stopped = True
        try:
            if self.pump is not None: return self.pump.stop_once()
            if self.owner.started and not self.owner.stop_attempted:
                try: return self.owner.stop_once()
                finally: self.owner.close_pipes()
        finally:
            self.program_pins.close()


def finalize_peer_lab(expected, before, after, retirement, owner):
    """No local receipt seals are reconstructed. Both observations must be issued by
    the same exact native owned-worker channel with ordered pre/post-exit exchanges.
    """
    from .benign_worker import decode_reply_observation
    from .benign_windows_session import is_native_retirement
    from .benign_evidence import LabVerdict
    need(is_admitted_peer(before, 'TERMINAL', owner) and is_admitted_peer(after, 'POSTEXIT', owner),
         'admitted_peer_receipts_required')
    need(before.sequence < after.sequence, 'postexit_sequence')
    pre = parse_json(before.observation_bytes, 1048576); post = parse_json(after.observation_bytes, 1048576)
    e = expected.ready.expected; r = e.fields()
    b = decode_reply_observation('TERMINAL', pre, e, expected.ready)
    a = decode_reply_observation('POSTEXIT', post, e, expected.ready)
    need(pre['producer'] == post['producer'] == 'LOCAL_NATIVE_CHECKS', 'native_checks_required')
    need(b.artifacts == a.artifacts and pre['checks']['output_root'] == post['checks']['output_root']
         and pre['checks']['files'] == post['checks']['files'], 'postexit_bytes_or_identity_changed')
    need(validate_terminal(expected, dict(a.artifacts)).completed, 'failed_terminal')
    need(is_native_retirement(retirement, r['run_id'], r['nonce'], e.session_binding_sha256, e.boot_binding),
         'native_retirement_required')
    return LabVerdict('BENIGN_SANDBOX_TRANSPORT_PASS_LAB_ONLY', sha(dict(a.artifacts)['terminal.json']))


@dataclass(frozen=True)
class _NativeBoundContext:
    descriptor: object
    clock: object
    session: object
    worker: object
    ledger: object
    executable: str
    config_path: str
    config_bytes: bytes
    materialization_sha256: str
    _seal: object


@dataclass(frozen=True)
class NativeContextSpec:
    """Finite data bound by the future operator issuer; not a permit by itself."""
    descriptor: object
    layout: object
    wsb_bytes: bytes
    source_root: str
    source_files: tuple
    executable_bytes: int
    worker_pin: object
    worker_spec: object
    image_inventory: tuple

    def validate(self):
        from .benign_layout import BoundLayout, winpath, render_wsb, overlaps
        from .benign_ledger import GrantDescriptor
        from .benign_capsule import SOURCE_PATHS
        from .benign_windows_session import WorkerSourcePin
        from .benign_worker import WorkerContextSpec
        from .benign_contract import parse_benign, hexstr
        need(type(self.descriptor) is GrantDescriptor and type(self.layout) is BoundLayout, 'native_context_data')
        need(type(self.worker_pin) is WorkerSourcePin and type(self.worker_spec) is WorkerContextSpec,
             'native_program_and_worker_spec')
        self.worker_pin.validate(); self.worker_spec.validate(); winpath(self.source_root)
        req = parse_benign('request', self.descriptor.request).fields
        need(self.layout.run_id == req['run_id'] and
             self.worker_spec.request == self.descriptor.request and
             self.worker_spec.supervisor_binding == self.descriptor.boot_binding, 'native_context_binding')
        need(self.worker_spec.output_path == self.layout.host_roles[3] and
             self.worker_spec.control_path == self.layout.host_roles[2], 'native_role_paths')
        need(not overlaps(self.source_root, self.layout.lab_root), 'program_not_mapping')
        need(self.worker_pin.script == self.source_root + '\\benign_worker.py', 'program_script_location')
        need(type(self.source_files) is tuple and len(self.source_files) == len(SOURCE_PATHS), 'source_pin_rows')
        need([x[0] for x in self.source_files] == sorted(SOURCE_PATHS), 'program_exact_source_set')
        uint(self.executable_bytes, 32 * 1024**2); need(self.executable_bytes > 0, 'python_executable_size')
        executable = []; bootstrap_sha = None
        for path, size, expected in self.source_files:
            # Match first-process and full ingress source-member limits before any
            # future grant reservation or worker creation. Interpreter cap is separate.
            uint(size, 262144); hexstr(expected)
            if path.endswith(('.py', '.ps1')): executable.append(dict(path=path, bytes=size, sha256=expected))
            if path == 'payload/guest_bootstrap.ps1': bootstrap_sha = expected
        source_sha = sha(canonical(executable))
        need(source_sha == req['source_sha256'] == self.worker_pin.source_sha256, 'program_source_digest')
        need(self.wsb_bytes == render_wsb(self.layout, bootstrap_sha) and sha(self.wsb_bytes) == req['wsb_sha256'],
             'fixed_wsb_bytes')
        need(sha(canonical(self.layout.descriptor(self.wsb_bytes))) == req['layout_sha256'], 'layout_pin')
        need(type(self.image_inventory) is tuple and self.image_inventory, 'image_inventory')
        return self


def bind_native_context(spec, permit=None):
    """Closed assembly; the initial delivery has no live issuer. Native factories
    never accept this descriptor as authority. Same-process hostility is out of scope.
    """
    require_benign_run_authority(permit)
    from .benign_ledger import _LedgerEngine, _FsStore
    from .benign_windows_fs import _FsEngine, _WinFsApi, retain_exact_files
    from .benign_windows_session import _ProcessEngine, _WinProcessApi, _OwnedWorker
    need(type(spec) is NativeContextSpec, 'native_context_spec'); spec.validate()
    _check_native_static_plan(spec)
    api = _WinProcessApi(permit); fs = _FsEngine(_WinFsApi(permit))
    need(api.boot_binding() == spec.descriptor.boot_binding, 'supervisor_incarnation')
    rows = tuple((spec.source_root + '\\' + path.replace('/', '\\'), size, h)
                 for path, size, h in spec.source_files)
    rows += ((spec.worker_pin.executable, spec.executable_bytes, spec.worker_pin.executable_sha256),)
    program = retain_exact_files(fs, rows); root = None
    try:
        root = fs.open_root(spec.layout.host_state)
        session = _ProcessEngine(api, spec.image_inventory)
        executable = dict((n.casefold(), p) for n, p in spec.image_inventory)['windowssandbox.exe']
        worker = _BoundWorkerPort(_OwnedWorker(api, spec.worker_pin), spec.worker_spec, program, permit,
                                  startup_program=(spec.source_root, spec.source_files, spec.executable_bytes))
        ledger = _LedgerEngine(_FsStore(root))
        return _NativeBoundContext(spec.descriptor, _HostClock(), session, worker, ledger,
            executable, spec.layout.lab_root + '\\session.wsb', spec.wsb_bytes,
            spec.worker_spec.materialization_sha256, _CONTEXT_SEAL)
    except Exception:
        if root is not None: root.close()
        program.close(); raise


class _HostClock:
    def now_ns(self):
        import time
        return time.monotonic_ns()

    def sleep_ns(self, value):
        import time
        uint(value, 250_000_000); time.sleep(value / 1_000_000_000)


def _check_native_static_plan(spec):
    """Data-only comparison of the complete before/after materialization inventory.
    Version strings or the request alone cannot replace retained runtime/capsule pins.
    The 37-file historical runtime tree format has no trailing LF.
    """
    import json
    from pathlib import PurePosixPath
    from .benign_capsule import (GUEST_MODULES, TARGET, RUNTIME_TREE_SHA,
                                RUNTIME_MANIFEST_SHA, TOTAL_RUNTIME_BYTES, LOCKED_PTH,
                                PYTHON_EXE_SHA, PYTHON_DLL_SHA)
    from .benign_contract import parse_benign, hexstr
    req = parse_benign('request', spec.descriptor.request).fields
    source = {n: (size, h) for n, size, h in spec.source_files}
    capsule_rows = [dict(path='app/' + TARGET + name, bytes=source[name][0], sha256=source[name][1])
                    for name in sorted(GUEST_MODULES)]
    capsule_manifest = canonical({'kind': 'BEN01_GUEST_CAPSULE_V1', 'files': capsule_rows})
    need(req['capsule_sha256'] == sha(capsule_manifest), 'native_capsule_manifest_pin')
    need(req['runtime_sha256'] == RUNTIME_TREE_SHA, 'native_retained_runtime_pin')
    specs = spec.worker_spec.static_roots
    need(len({role for role, _, _ in specs}) == len(specs), 'duplicate_static_role')
    supplied = {role: (path, tuple(sorted(rows))) for role, path, rows in specs}
    need('Runtime' in supplied and supplied['Runtime'][0] == spec.layout.host_roles[1], 'runtime_root_required')
    runtime = supplied['Runtime'][1]
    need(len(runtime) == 37 and sum(size for _, size, _ in runtime) == TOTAL_RUNTIME_BYTES, 'runtime_static_inventory')
    old_rows = [dict(path=n, size_bytes=size, sha256=h) for n, size, h in runtime]
    old_raw = json.dumps(old_rows, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    need(sha(old_raw) == RUNTIME_TREE_SHA, 'runtime_static_tree')
    runtime_map = {n: (size, h) for n, size, h in runtime}
    need(runtime_map['runtime_manifest.json'][1] == RUNTIME_MANIFEST_SHA and
         runtime_map['python313._pth'] == (len(LOCKED_PTH), sha(LOCKED_PTH)) and
         runtime_map['python.exe'][1] == PYTHON_EXE_SHA and
         runtime_map['python313.dll'][1] == PYTHON_DLL_SHA, 'runtime_static_executables')
    groups = {}
    for row in capsule_rows:
        parent = str(PurePosixPath(row['path']).parent); name = PurePosixPath(row['path']).name
        groups.setdefault(parent, []).append((name, row['bytes'], row['sha256']))
    wanted = {'Input': (spec.layout.host_roles[0], tuple(sorted((
        ('request.json', len(spec.descriptor.request), sha(spec.descriptor.request)),
        ('capsule.manifest.json', len(capsule_manifest), sha(capsule_manifest)),
        ('guest_bootstrap.ps1', *source['payload/guest_bootstrap.ps1']))))),
        'Runtime': (spec.layout.host_roles[1], runtime),
        'Config': (spec.layout.lab_root, (('session.wsb', len(spec.wsb_bytes), sha(spec.wsb_bytes)),))}
    for parent, rows in groups.items():
        wanted['Capsule:' + parent] = (spec.layout.host_roles[0] + '\\Capsule\\' + parent.replace('/', '\\'),
                                      tuple(sorted(rows)))
    need(supplied == wanted, 'exact_native_static_roots_and_files')
    return True


def _await_worker_initialization(worker, clock, absolute_deadline_ns, on_tick):
    """Private deterministic/fake-testable admission wait. No pipe I/O in this loop.
    The real caller supplies its owned nonblocking worker port, never a guest predicate.
    """
    uint(absolute_deadline_ns)
    start = clock.now_ns(); uint(start)
    deadline = min(absolute_deadline_ns, start + 120_000_000_000)
    last = start
    while True:
        now = clock.now_ns(); uint(now)
        need(last <= now <= deadline, 'worker_initialization_deadline_or_clock')
        last = now; on_tick()
        done = worker.initialization_complete()
        need(type(done) is bool, 'worker_initialization_observation')
        now = clock.now_ns(); uint(now)
        need(last <= now <= deadline, 'worker_initialization_deadline_or_clock')
        last = now
        if done: return
        clock.sleep_ns(min(250_000_000, max(1, deadline - now + 1)))
