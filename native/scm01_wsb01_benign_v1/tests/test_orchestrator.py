"""ORCHESTRATOR01-08: nonblocking fake I/O, one launch, no native calls."""
import unittest
from types import SimpleNamespace
from . import test_contract as f
from . import test_ledger as ledger
from . import test_windows_bindings as w
from .. import benign_contract as c
from .. import benign_orchestrator as o
from .. import benign_worker as worker
from .. import benign_windows_session as ps
from .. import benign_evidence as e


class Clock:
    def __init__(self): self.tick = 0
    def now_ns(self): return self.tick
    def sleep_ns(self, n): self.tick += n


class Session:
    def __init__(self, ctx): self.ctx = ctx; self.launches = 0; self.cleanups = 0
    def snapshot_complete(self):
        procs = (w.ANCHOR,) if self.launches or self.ctx.mode == 'nonempty' else ()
        return ps.ProcessSnapshot(procs, True, self.ctx.clock.now_ns(), f.BOOT, 'OFFLINE_MODEL')
    def launch(self, exe, cfg, raw, wanted):
        self.launches += 1
        if self.ctx.mode == 'launch_unknown': raise OSError('unknown launch return')
        return ps.LaunchReceipt(w.LAUNCHER, 100, c.sha(raw), 'OFFLINE_MODEL')
    def bind(self, launch, scan, rid, nonce, request_sha): return w.binding()
    def observe(self, bound):
        if self.ctx.mode == 'foreign': raise c.BenignError('foreign_or_replacement_anchor')
        if self.ctx.worker.terminal_delivered:
            t = self.ctx.clock.now_ns()
            return ps.RetirementObservation(f.RID, f.NONCE, f.BOOT, f.SESSION, True, False,
                                           True, (t - 500000000, t - 250000000, t))
        return None
    def release(self, bound): pass
    def cleanup(self, bound, budget): self.cleanups += 1; return ps.CleanupOutcome((100, 101), (), ('fake_unconfirmed',))


class Worker:
    def __init__(self, ctx):
        self.ctx = ctx; self.started = self.stopped = 0; self.queue = []; self.terminal_delivered = False
        self.expected = None; self.commands = []
    def start_once(self): self.started += 1; c.need(self.started == 1, 'worker_consumed')
    def bind_expected(self, expected): self.expected = expected
    def send_nonblocking(self, command, payload):
        c.need(payload == {}, 'worker_payload'); self.queue.append(command); self.commands.append(command)
    def poll_nonblocking(self):
        if not self.queue or self.ctx.mode == 'hung': return None
        command = self.queue.pop(0)
        exp, raw = f.full_fixture(self.expected)
        if command == 'READY':
            subset = {n: raw[n] for n in ('ready.json', 'ready.sig', 'ready.commit.json')}
            return worker.WorkerReply(command, 'READY', tuple(subset.items()), (object(),))
        if command == 'PUBLISH':
            if self.ctx.mode == 'publication_unknown': raise OSError('unknown publication')
            return worker.WorkerReply(command, 'PUBLISHED')
        if command == 'TERMINAL': self.terminal_delivered = True
        if command == 'POSTEXIT' and self.ctx.mode == 'postexit_changed':
            raw['terminal.sig'] = (2).to_bytes(32, 'big') * 2
        return worker.WorkerReply(command, 'BENIGN_TASK_COMPLETED', tuple(raw.items()))
    def stop_once(self): self.stopped += 1; c.need(self.stopped == 1, 'worker_stop_consumed')


def context(mode='normal'):
    ctx = SimpleNamespace(mode=mode, descriptor=ledger.descriptor(), clock=Clock(),
                          executable=w.INVENTORY[0][1], config_path='C:\\Lab\\session.wsb',
                          config_bytes=b'<fixed/>', materialization_sha256='f' * 64)
    ctx.store = ledger.FakeStore(); ctx.ledger = ledger.l._LedgerEngine(ctx.store)
    if mode == 'outcome_failure': ctx.store.fail = '.outcome.json'
    ctx.worker = Worker(ctx); ctx.session = Session(ctx)
    return ctx


class JobApi:
    def __init__(self, extra=False, assign_failure=False): self.calls = []; self.extra = extra; self.assign_failure = assign_failure
    def create_job(self, *args): self.calls.append(('job', args)); return 9
    def create_suspended_worker(self, descriptor): self.calls.append('suspended'); return 10, 11, 12
    def assign(self, job, process):
        self.calls.append('assign')
        if self.assign_failure: raise OSError('assign failed')
    def job_processes(self, job): self.calls.append('pids'); return (12, 13) if self.extra else (12,)
    def resume(self, thread): self.calls.append('resume')
    def close(self, h): self.calls.append(('close', h))
    def terminate(self, h): self.calls.append(('terminate', h))
    def wait(self, h, ms): self.calls.append(('wait', h, ms)); return 0


def job_descriptor(): return {'flags': ps.WORKER_FLAGS, 'active_process_limit': 1, 'role': 'ARTIFACT_WORKER'}


class OrchestratorTests(unittest.TestCase):
    def test_ORCHESTRATOR01_one_worker_launch_fake_only(self):
        ctx = context(); outcome = o._orchestrate(ctx)
        self.assertEqual(outcome.result, 'OFFLINE_FAKE_TRACE_VALID_NO_AUTHORITY')
        self.assertEqual((ctx.worker.started, ctx.worker.stopped, ctx.session.launches), (1, 1, 1))
        self.assertEqual(outcome.authorization_attempts, 1); self.assertFalse(outcome.runtime_authorized)
        self.assertEqual(outcome.evidence_domain, 'OFFLINE_MODEL')

    def test_ORCHESTRATOR02_job_before_resume(self):
        api = JobApi(); self.assertEqual(ps.spawn_artifact_worker(api, job_descriptor()), (10, 9, 12))
        self.assertLess(api.calls.index('assign'), api.calls.index('resume'))
        api = JobApi(assign_failure=True)
        with self.assertRaises(OSError): ps.spawn_artifact_worker(api, job_descriptor())
        self.assertNotIn('resume', api.calls); self.assertIn(('terminate', 10), api.calls)

    def test_ORCHESTRATOR03_flags_and_extra_pid_refusal(self):
        self.assertEqual(ps.WORKER_FLAGS, 0x4 | 0x8 | 0x400); self.assertFalse(ps.WORKER_FLAGS & 0x08000000)
        with self.assertRaises(c.BenignError): ps.spawn_artifact_worker(JobApi(extra=True), job_descriptor())
        with self.assertRaises(c.BenignError):
            ps.spawn_artifact_worker(JobApi(), dict(job_descriptor(), flags=0x08000404))

    def test_ORCHESTRATOR04_hung_io_watchdog_no_restart(self):
        ctx = context('hung'); outcome = o._orchestrate(ctx)
        self.assertTrue(outcome.failure_sticky); self.assertLessEqual(ctx.clock.tick, 300250000000)
        self.assertEqual(ctx.worker.started, 1); self.assertEqual(ctx.worker.stopped, 1)
        self.assertEqual(ctx.session.launches, 1); self.assertEqual(outcome.authorization_attempts, 0)

    def test_ORCHESTRATOR05_bounded_frames_identity_sequence(self):
        decoder = worker.FrameDecoder(f.RID); raw = worker.encode_frame(0, f.RID, 'READY', {})
        self.assertIsNone(decoder.feed(raw[:3])); self.assertEqual(decoder.feed(raw[3:])['command'], 'READY')
        with self.assertRaises(c.BenignError): decoder.feed(raw)
        for raw in ((worker.FRAME_LIMIT + 1).to_bytes(4, 'little'),
                    worker.encode_frame(0, 'f' * 32, 'READY', {})):
            with self.subTest(raw=raw[:4]), self.assertRaises(c.BenignError): worker.FrameDecoder(f.RID).feed(raw)
        with self.assertRaises(c.BenignError): worker.unpack_artifacts({'unknown': ['00']})

    def test_ORCHESTRATOR06_empty_baseline_anchor_required(self):
        ctx = context('nonempty'); out = o._orchestrate(ctx)
        self.assertEqual(out.launch_attempts, 0); self.assertEqual(ctx.worker.started, 0)
        api = w.FakeProcess(); engine = ps._ProcessEngine(api, w.INVENTORY)
        launch = ps.LaunchReceipt(w.LAUNCHER, 100, 'e' * 64, 'OFFLINE_MODEL')
        with self.assertRaises(c.BenignError):
            engine.bind(launch, ps.ProcessSnapshot((), True, 0, f.BOOT, 'OFFLINE_MODEL'), f.RID, f.NONCE, 'a' * 64)

    def test_ORCHESTRATOR07_foreign_anchor_abort(self):
        ctx = context('foreign'); out = o._orchestrate(ctx)
        self.assertTrue(out.failure_sticky); self.assertFalse(out.retired)
        self.assertEqual(ctx.session.cleanups, 1); self.assertEqual(ctx.session.launches, 1)

    def test_ORCHESTRATOR08_unknown_crash_and_outcome_failure_no_retry(self):
        for mode in ('launch_unknown', 'publication_unknown', 'outcome_failure', 'postexit_changed'):
            ctx = context(mode); out = o._orchestrate(ctx)
            with self.subTest(mode=mode):
                self.assertTrue(out.failure_sticky)
                self.assertLessEqual(out.launch_attempts, 1); self.assertLessEqual(out.authorization_attempts, 1)
                self.assertEqual(ctx.worker.started, 1); self.assertEqual(ctx.worker.stopped, 1)
                self.assertFalse(out.runtime_authorized)


class IntegrationRegressionTests(unittest.TestCase):
    def _artifact_worker(self):
        from .. import benign_windows_fs as fs
        from .. import benign_windows_crypto as crypto
        expected, raw = f.full_fixture()
        api = w.FakeFs()
        for path in ('C:\\Lab\\Input', 'C:\\Lab\\Control', 'C:\\Lab\\Output'): api.directory(path)
        engine = fs._FsEngine(api)
        input_root, control, output = [engine.open_root('C:\\Lab\\' + x) for x in ('Input', 'Control', 'Output')]
        api.put(input_root.path + '\\request.json', expected.ready.expected.request)
        for name, data in raw.items(): api.put(output.path + '\\' + name, data)
        static = (('Input', input_root, (('request.json', len(expected.ready.expected.request),
                                         c.sha(expected.ready.expected.request)),)),)
        artifact = worker._ArtifactWorker(expected.ready.expected, output, control,
                                          crypto._CryptoEngine(w.FakeCrypto()), static)
        return artifact, api, (input_root, control, output)

    def test_REG01_real_artifact_algorithm_fake_fs_and_cng(self):
        artifact, api, roots = self._artifact_worker()
        try:
            self.assertEqual(artifact.handle('READY', {}).status, 'READY')
            self.assertEqual(artifact.handle('PUBLISH', {}).status, 'PUBLISHED')
            before = artifact.handle('TERMINAL', {}); after = artifact.handle('POSTEXIT', {})
            self.assertEqual(before.artifacts, after.artifacts)
            self.assertEqual(before.status, 'BENIGN_TASK_COMPLETED')
            self.assertEqual(before.evidence_domain, 'OFFLINE_MODEL')
            self.assertEqual(len(after.crypto_receipts), 2)
            self.assertFalse(e.finalize_lab is None)
            with self.assertRaises(c.BenignError):
                e.finalize_lab(artifact.expectation, e.NativeReceipts(before.crypto_receipts + after.crypto_receipts,
                    object(), (before.materialization, after.materialization)), (before.snapshot, after.snapshot))
            calls = [row[1] for row in api.calls if row[0] == 'open' and row[3]]
            self.assertEqual(calls, ['C:\\Lab\\Control\\authorization.json',
                                     'C:\\Lab\\Control\\authorization.commit.json'])
        finally:
            for root in roots: root.close()
        self.assertFalse(api.handles)

    def test_REG02_uncertain_control_write_worker_poisoned(self):
        from .. import benign_windows_fs as fs
        artifact, api, roots = self._artifact_worker()
        try:
            artifact.handle('READY', {}); api.fail = 'flush'
            with self.assertRaises(fs.PublicationUnknown): artifact.handle('PUBLISH', {})
            api.fail = ''
            self.assertTrue(artifact.dead); self.assertTrue(artifact.auth_attempted)
            with self.assertRaises(c.BenignError): artifact.handle('PUBLISH', {})
        finally:
            api.fail = ''
            for root in roots: root.close()

    def test_REG03_frame_budget_matches_supervisor_poll_budget(self):
        decoder = worker.FrameDecoder(f.RID)
        for sequence in range(worker.FRAME_COUNT_LIMIT):
            self.assertEqual(decoder.feed(worker.encode_frame(sequence, f.RID, 'READY', {}))['sequence'], sequence)
        with self.assertRaises(c.BenignError): worker.encode_frame(worker.FRAME_COUNT_LIMIT, f.RID, 'READY', {})

    def test_REG04_partial_frames_and_chunk_roundtrip(self):
        exp, raw = f.full_fixture(); packed = worker.pack_artifacts(raw)
        self.assertEqual(worker.unpack_artifacts(packed), raw)
        encoded = worker.encode_frame(0, f.RID, 'TERMINAL', {'artifacts': packed})
        decoder = worker.FrameDecoder(f.RID)
        for i in range(0, len(encoded), 17): result = decoder.feed(encoded[i:i + 17])
        self.assertEqual(result['payload']['artifacts'], packed)
        with self.assertRaises(c.BenignError): worker.pack_artifacts({'ready.sig': b''})
        with self.assertRaises(c.BenignError): worker.pack_artifacts({'ready.sig': 'not bytes'})

    def test_REG05_boot_query_failure_closes_enumeration_handle(self):
        class BrokenBoot(w.FakeProcess):
            def boot_binding(self): raise OSError('boot query failed')
        api = BrokenBoot()
        with self.assertRaises(OSError): ps._ProcessEngine(api, w.INVENTORY).snapshot_complete()
        self.assertEqual(api.closed, ['snapshot'])

    def test_REG06_foreign_token_anchor_not_bound(self):
        from dataclasses import replace
        api = w.FakeProcess(); engine = ps._ProcessEngine(api, w.INVENTORY)
        foreign = replace(w.ANCHOR, authentication_id=77)
        scan = ps.ProcessSnapshot((foreign,), True, 0, f.BOOT, 'OFFLINE_MODEL')
        with self.assertRaises(c.BenignError): engine.bind(ps.LaunchReceipt(w.LAUNCHER, 100, 'e' * 64,
                                    'OFFLINE_MODEL'), scan, f.RID, f.NONCE, 'a' * 64)

    def test_REG07_released_handles_are_not_reused(self):
        api = w.FakeProcess(); engine = ps._ProcessEngine(api, w.INVENTORY); bound = w.binding()
        engine.release(bound); self.assertEqual(api.closed, [100, 101])
        with self.assertRaises(c.BenignError): engine.release(bound)
        with self.assertRaises(c.BenignError): engine.observe(bound)
        with self.assertRaises(c.BenignError): engine.cleanup(bound)

    def test_REG08_unexpected_ledger_files_fail_closed(self):
        store = ledger.FakeStore(); store.data['unexpected.tmp'] = b'x'
        with self.assertRaises(c.BenignError): ledger.l._LedgerEngine(store).reserve(ledger.descriptor())
        self.assertFalse(store.locked)

    def test_REG09_inheritance_reset_failure_keeps_child_cleanup(self):
        class Api:
            def __init__(self): self.calls = []
            def set_inherit(self, h, value):
                self.calls.append(('inherit', h, value))
                if not value and h == 2: raise OSError('reset failed')
            def create_worker_raw(self, descriptor): self.calls.append('created'); return (10, 11, 12)
            def terminate(self, h): self.calls.append(('terminate', h))
            def wait(self, h, ms): self.calls.append(('wait', h, ms)); return 0
            def close(self, h): self.calls.append(('close', h))
        api = Api()
        with self.assertRaises(c.BenignError): ps._create_worker_with_inheritance(api, {'child_handles': (1, 2)})
        self.assertIn(('inherit', 1, False), api.calls)
        self.assertIn(('terminate', 10), api.calls)
        self.assertIn(('wait', 10, 10000), api.calls)
        self.assertEqual(api.calls[-2:], [('close', 11), ('close', 10)])


class ClosedAssembly117Tests(unittest.TestCase):
    def artifact(self):
        from dataclasses import replace
        fixture = IntegrationRegressionTests()
        artifact, api, roots = fixture._artifact_worker()
        rows = [dict(role='Input', name='request.json', bytes=len(artifact.expected.request),
                     sha256=c.sha(artifact.expected.request))]
        artifact.expected = replace(artifact.expected, materialization_sha256=c.sha(c.canonical(rows)))
        return artifact, api, roots

    def test_REG10_fragmented_serve_complete_stop_frame(self):
        class StopContext:
            expected = f.full_fixture()[0].ready.expected
            dead = False
            def handle(self, command, payload):
                c.need(command == 'STOP' and payload == {}, 'fake_stop')
                self.dead = True; return worker.WorkerReply('STOP', 'STOPPED')
        class Channel:
            def __init__(self):
                raw = worker.encode_frame(0, f.RID, 'STOP', {})
                self.parts = [raw[:2], raw[2:4], raw[4:13], raw[13:]]; self.sent = []
            def receive_bounded(self, cap): return self.parts.pop(0)
            def send_bounded(self, raw): self.sent.append(raw)
        channel = Channel()
        self.assertEqual(worker._serve(channel, StopContext()), 'WORKER_STOPPED')
        out = worker.FrameDecoder(f.RID).feed(channel.sent[0])
        self.assertEqual(out['payload']['status'], 'STOPPED')
        self.assertEqual(out['payload']['producer'], 'OFFLINE_MODEL')

    def test_REG11_fragmented_exchange_eof_rejected(self):
        class Channel:
            def send_bounded(self, raw): pass
            def receive_bounded(self, cap): return b''
        with self.assertRaises(c.BenignError):
            worker._exchange(Channel(), worker.encode_frame(0, f.RID, 'READY', {}), worker.FrameDecoder(f.RID))

    def test_REG12_worker_postexit_not_before_terminal(self):
        artifact, api, roots = self.artifact()
        try:
            artifact.handle('READY', {}); artifact.handle('PUBLISH', {})
            with self.assertRaises(c.BenignError): artifact.handle('POSTEXIT', {})
            self.assertTrue(artifact.dead)
        finally:
            for root in roots: root.close()

    def test_REG13_full_artifact_ipc_roundtrip_fake_cannot_admit(self):
        artifact, api, roots = self.artifact()
        try:
            pinned = None
            for command in ('READY', 'PUBLISH', 'TERMINAL', 'POSTEXIT'):
                reply = artifact.handle(command, {})
                packet = worker.encode_reply_observation(artifact, reply)
                encoded = worker.encode_frame(0, f.RID, command, packet)
                decoded_packet = worker.FrameDecoder(f.RID).feed(encoded)['payload']
                decoded = worker.decode_reply_observation(command, decoded_packet, artifact.expected, pinned)
                self.assertEqual(decoded.artifacts, reply.artifacts)
                self.assertEqual(decoded.evidence_domain, 'OFFLINE_MODEL')
                self.assertEqual(packet['producer'], 'OFFLINE_MODEL')
                if command == 'READY': pinned = artifact.ready
                self.assertFalse(o.is_admitted_peer(decoded, command, object()))
        finally:
            for root in roots: root.close()
        self.assertFalse(api.handles)

    def test_REG14_native_label_is_still_untrusted(self):
        artifact, api, roots = self.artifact()
        try:
            reply = artifact.handle('READY', {})
            packet = worker.encode_reply_observation(artifact, reply)
            packet['producer'] = 'LOCAL_NATIVE_CHECKS'
            decoded = worker.decode_reply_observation('READY', packet, artifact.expected)
            self.assertEqual(decoded.evidence_domain, 'OFFLINE_MODEL')
            with self.assertRaises(c.BenignError):
                o.finalize_peer_lab(artifact.expectation, decoded, decoded, object(), object())
        finally:
            for root in roots: root.close()

    def test_REG15_mismatched_ipc_hashes_fail(self):
        import copy
        artifact, api, roots = self.artifact()
        try:
            packet = worker.encode_reply_observation(artifact, artifact.handle('READY', {}))
            for key in ('request_sha256', 'session_binding_sha256', 'boot_binding'):
                bad = copy.deepcopy(packet); bad[key] = '0' * 64
                with self.subTest(key=key), self.assertRaises(c.BenignError):
                    worker.decode_reply_observation('READY', bad, artifact.expected)
            bad = copy.deepcopy(packet); bad['checks']['crypto'][0]['key_sha256'] = '0' * 64
            with self.assertRaises(c.BenignError): worker.decode_reply_observation('READY', bad, artifact.expected)
        finally:
            for root in roots: root.close()

    def test_REG16_ipc_metadata_and_completion_binding(self):
        import copy
        artifact, api, roots = self.artifact()
        try:
            artifact.handle('READY', {}); artifact.handle('PUBLISH', {})
            packet = worker.encode_reply_observation(artifact, artifact.handle('TERMINAL', {}))
            for key, value in (('links', 2), ('attributes', 0x400), ('size', True), ('final_path', 'C:\\Foreign\\x')):
                bad = copy.deepcopy(packet); bad['checks']['files'][0][key] = value
                with self.subTest(key=key), self.assertRaises(c.BenignError):
                    worker.decode_reply_observation('TERMINAL', bad, artifact.expected, artifact.ready)
        finally:
            for root in roots: root.close()

    def test_REG17_mailbox_pending_is_nonblocking_single_slot(self):
        slot = worker._ExchangeSlot(f.RID)
        raw = slot.submit('READY', {})
        for _ in range(100): self.assertIsNone(slot.poll())
        with self.assertRaises(c.BenignError): slot.submit('READY', {})
        frame = worker.FrameDecoder(f.RID).feed(raw)
        slot.complete(frame); self.assertEqual(slot.poll()['sequence'], 0)
        self.assertIsNone(slot.poll()); self.assertEqual(slot.sequence, 1)

    def test_REG18_poisoned_mailbox_cannot_retry(self):
        slot = worker._ExchangeSlot(f.RID); slot.submit('PUBLISH', {})
        slot.fail(OSError('uncertain write'))
        with self.assertRaises(c.BenignError): slot.poll()
        with self.assertRaises(c.BenignError): slot.submit('PUBLISH', {})
        self.assertTrue(slot.poisoned)

    def test_REG19_worker_context_assembly_fake_roots_closed(self):
        from .. import benign_windows_fs as fs
        from .. import benign_windows_crypto as cr
        raw = f.request(); rows = [dict(role='Input', name='request.json', bytes=len(raw), sha256=c.sha(raw))]
        spec = worker.WorkerContextSpec(raw, 'C:\\Lab\\Output', 'C:\\Lab\\Control',
            (('Input', 'C:\\Lab\\Input', (('request.json', len(raw), c.sha(raw)),)),),
            c.sha(c.canonical(rows)), f.BOOT)
        api = w.FakeFs()
        for path in ('C:\\Lab\\Input', 'C:\\Lab\\Output', 'C:\\Lab\\Control'): api.directory(path)
        owner = worker._WorkerContextOwner(spec, fs._FsEngine(api), cr._CryptoEngine(w.FakeCrypto()), f.SESSION)
        self.assertEqual(owner.worker.expected.boot_binding, f.BOOT)
        self.assertEqual(owner.worker.output.engine.domain, 'OFFLINE_MODEL')
        owner.close(); self.assertFalse(api.handles)

    def test_REG20_context_assembly_failure_releases_prior_roots(self):
        from .. import benign_windows_fs as fs
        from .. import benign_windows_crypto as cr
        raw = f.request(); rows = [dict(role='Input', name='request.json', bytes=len(raw), sha256=c.sha(raw))]
        spec = worker.WorkerContextSpec(raw, 'C:\\Lab\\Output', 'C:\\Lab\\Control',
            (('Input', 'C:\\Lab\\Missing', (('request.json', len(raw), c.sha(raw)),)),), c.sha(c.canonical(rows)), f.BOOT)
        api = w.FakeFs(); api.directory('C:\\Lab\\Output'); api.directory('C:\\Lab\\Control')
        with self.assertRaises(OSError):
            worker._WorkerContextOwner(spec, fs._FsEngine(api), cr._CryptoEngine(w.FakeCrypto()), f.SESSION)
        self.assertFalse(api.handles)

    def test_REG21_retirement_before_terminal_reply_not_lost(self):
        ctx = context()
        prior_observe = ctx.session.observe
        def observe(bound):
            if 'TERMINAL' in ctx.worker.commands:
                tick = ctx.clock.now_ns()
                return ps.RetirementObservation(f.RID, f.NONCE, f.BOOT, f.SESSION, True, False, True,
                                               (tick - 500000000, tick - 250000000, tick))
            return prior_observe(bound)
        ctx.session.observe = observe
        result = o._orchestrate(ctx)
        self.assertEqual(result.result, 'OFFLINE_FAKE_TRACE_VALID_NO_AUTHORITY')
        self.assertTrue(result.retired); self.assertEqual(ctx.worker.commands.count('POSTEXIT'), 1)
        self.assertEqual(ctx.worker.started, 1); self.assertEqual(result.authorization_attempts, 1)

    def test_REG22_new_native_factories_still_closed(self):
        from .. import benign_runtime_gate as gate
        for call in (lambda: o.bind_native_context(object(), {'approved': True}),
                     lambda: worker.serve_native_worker(object(), object(), True),
                     lambda: worker._NativePipePump(object(), f.RID, True),
                     lambda: o._BoundWorkerPort(object(), object(), object(), True),
                     lambda: ps.create_owned_worker(object(), True)):
            with self.assertRaises(gate.RuntimeClosed): call()


class NativeContextSpec117Tests(unittest.TestCase):
    def spec(self):
        from pathlib import Path
        from .. import benign_capsule as cap
        from .. import benign_layout as ly
        from .test_layout_capsule import spec as layout_spec
        root = Path(__file__).resolve().parents[1]
        data = {n: (root / n).read_bytes() for n in cap.SOURCE_PATHS}
        files = tuple((n, len(b), c.sha(b)) for n, b in sorted(data.items()))
        executable = [dict(path=n, bytes=len(b), sha256=c.sha(b)) for n, b in sorted(data.items())
                      if n.endswith(('.py', '.ps1'))]
        source_sha = c.sha(c.canonical(executable)); layout = ly.plan_layout(layout_spec())
        config = ly.render_wsb(layout, c.sha(data['payload/guest_bootstrap.ps1']))
        req = c.parse_benign('request', f.request()).fields
        req.update(source_sha256=source_sha, wsb_sha256=c.sha(config),
                   layout_sha256=c.sha(c.canonical(layout.descriptor(config))))
        raw = c.serialize_benign('request', req)
        rows = [dict(role='Input', name='request.json', bytes=len(raw), sha256=c.sha(raw))]
        worker_spec = worker.WorkerContextSpec(raw, layout.host_roles[3], layout.host_roles[2],
            (('Input', layout.host_roles[0], (('request.json', len(raw), c.sha(raw)),)),),
            c.sha(c.canonical(rows)), f.BOOT)
        pin = ps.WorkerSourcePin('C:\\Python\\python.exe', 'a' * 64, 'C:\\Source\\benign_worker.py', source_sha)
        return o.NativeContextSpec(ledger.l.GrantDescriptor(raw, f.BOOT), layout, config, 'C:\\Source', files,
                                   12, pin, worker_spec, w.INVENTORY)

    def test_REG37_native_context_data_has_exact_program_sources(self):
        spec = self.spec(); self.assertIs(spec.validate(), spec)
        self.assertEqual(len(spec.source_files), 32)
        # This is structural data, not an admitted native context; no providers are created.
        with self.assertRaises(c.BenignError): o._check_native_static_plan(spec)

    def test_REG38_partial_program_source_manifest_refused(self):
        from dataclasses import replace
        spec = self.spec()
        with self.assertRaises(c.BenignError): replace(spec, source_files=spec.source_files[:-1]).validate()
        with self.assertRaises(c.BenignError): replace(spec, source_files=tuple(reversed(spec.source_files))).validate()

    def test_REG39_runtime_layout_override_not_admitted(self):
        from dataclasses import replace
        spec = self.spec()
        with self.assertRaises(c.BenignError): replace(spec, wsb_bytes=b'<other/>').validate()
        bad = replace(spec.worker_spec, output_path=spec.layout.host_roles[0])
        with self.assertRaises(c.BenignError): replace(spec, worker_spec=bad).validate()

    def test_REG40_spec_does_not_open_native_constructor(self):
        from ..benign_runtime_gate import RuntimeClosed
        with self.assertRaises(RuntimeClosed): o.bind_native_context(self.spec(), {'approved': True})


class FailurePersistence117Tests(unittest.TestCase):
    def test_REG41_publication_failure_record_error_keeps_cleanup(self):
        ctx = context('publication_unknown')
        def broken_record(grant): raise OSError('outcome store unavailable')
        ctx.ledger.publication_failed = broken_record
        result = o._orchestrate(ctx)
        self.assertTrue(result.failure_sticky)
        self.assertEqual((ctx.worker.started, ctx.worker.stopped), (1, 1))
        self.assertEqual(ctx.session.cleanups, 1)
        self.assertEqual(ctx.worker.commands.count('PUBLISH'), 1)
        self.assertFalse(result.runtime_authorized)

    def test_REG42_late_ready_does_not_publish_authorization(self):
        ctx = context(); original = ctx.worker.poll_nonblocking
        def late_ready():
            reply = original()
            if reply is not None and reply.command == 'READY':
                ctx.clock.tick = 301_000_000_000
            return reply
        ctx.worker.poll_nonblocking = late_ready
        result = o._orchestrate(ctx)
        self.assertTrue(result.failure_sticky)
        self.assertEqual(result.authorization_attempts, 0)
        self.assertEqual(ctx.worker.commands, ['READY'])
        self.assertEqual((ctx.worker.started, ctx.worker.stopped), (1, 1))


class FirstProcessIngress118Tests(unittest.TestCase):
    def inputs(self):
        spec = NativeContextSpec117Tests().spec()
        proc = ps.ProcessIdentity(321, 555, spec.worker_pin.executable, 1, 50, 'S-1-5-21-123')
        bound = c.canonical(dict(kind='BEN01_OWNED_WORKER_V1',
            supervisor_incarnation=spec.worker_spec.supervisor_binding, process=proc.descriptor(),
            script=spec.worker_pin.script, executable_sha256=spec.worker_pin.executable_sha256,
            source_sha256=spec.worker_pin.source_sha256))
        raw = worker.build_worker_ingress(spec.worker_spec, spec.source_root, spec.source_files,
                                         spec.worker_pin, spec.executable_bytes, bound)
        return spec, proc, raw, worker.parse_worker_ingress(raw)

    def test_REG45_startup_roundtrip_preserves_exact_context(self):
        spec, _proc, raw, plan = self.inputs()
        self.assertEqual(plan.context, spec.worker_spec)
        self.assertEqual(plan.source_files, spec.source_files)
        self.assertEqual(plan.raw, raw); self.assertEqual(plan.evidence_domain, 'OFFLINE_MODEL')
        self.assertFalse(o.is_admitted_peer(plan, 'READY', object()))

    def test_REG46_startup_not_a_permit_even_with_native_label(self):
        from .. import benign_runtime_gate as gate
        _spec, _proc, raw, plan = self.inputs()
        for value in (plan, c.parse_json(raw), {'approved': True}):
            with self.subTest(value=type(value).__name__), self.assertRaises(gate.RuntimeClosed):
                gate.require_benign_run_authority(value)
        bad = c.parse_json(raw); bad['permit'] = 'NATIVE_WIN32_LAB'
        with self.assertRaises(c.BenignError): worker.parse_worker_ingress(c.canonical(bad))

    def test_REG47_startup_source_edit_rejected(self):
        _s, _p, raw, _plan = self.inputs()
        for change in ('hash', 'extra', 'order', 'bool_size', 'bad_row'):
            bad = c.parse_json(raw)
            if change == 'hash': bad['source_files'][8]['sha256'] = '0'*64
            elif change == 'extra': bad['source_files'].append(bad['source_files'][0])
            elif change == 'order': bad['source_files'].reverse()
            elif change == 'bool_size': bad['source_files'][0]['bytes'] = True
            else: bad['source_files'][0] = []
            with self.subTest(change=change), self.assertRaises(c.BenignError):
                worker.parse_worker_ingress(c.canonical(bad))

    def test_REG48_context_unknown_nested_fields_and_duplicates_rejected(self):
        _s, _p, raw, _plan = self.inputs()
        for field in ('request_hex', 'static_roots', 'materialization_sha256'):
            bad = c.parse_json(raw)
            if field == 'request_hex': bad['context'][field] = '00'
            elif field == 'static_roots': bad['context'][field][0]['files'][0]['callback'] = 'x'
            else: bad['context'][field] = '0'*64
            with self.subTest(field=field), self.assertRaises(c.BenignError):
                worker.parse_worker_ingress(c.canonical(bad))
        bad = raw.replace(b'{', b'{"kind":"x",', 1)
        with self.assertRaises(c.BenignError): worker.parse_worker_ingress(bad)

    def test_REG49_wrong_first_process_identity_fails(self):
        from dataclasses import replace
        spec, proc, _raw, plan = self.inputs()
        check = worker.validate_worker_ingress_observation(plan, proc, spec.worker_pin.executable, spec.worker_pin.script)
        self.assertEqual(check['scope'], 'CHECKED_DATA_NOT_AUTHORITY')
        for bad in (replace(proc, pid=322), replace(proc, created=556), replace(proc, authentication_id=51),
                    replace(proc, session_id=2), replace(proc, user_sid='S-1-5-21-other')):
            with self.subTest(bad=bad), self.assertRaises(c.BenignError):
                worker.validate_worker_ingress_observation(plan, bad, spec.worker_pin.executable, spec.worker_pin.script)

    def test_REG50_wrong_first_executable_or_script_fails(self):
        spec, proc, _raw, plan = self.inputs()
        for exe, script in (('C:\\Other\\python.exe', spec.worker_pin.script),
                            (spec.worker_pin.executable, 'C:\\Other\\benign_worker.py')):
            with self.subTest(exe=exe, script=script), self.assertRaises(c.BenignError):
                worker.validate_worker_ingress_observation(plan, proc, exe, script)

    def test_REG51_INIT_ACK_before_BIND_and_one_attempt(self):
        _s, _p, _raw, plan = self.inputs(); handshake = worker._StartupHandshake(plan)
        data = handshake.payload_once(); decoder = worker.FrameDecoder(f.RID)
        init = decoder.feed(worker.encode_frame(0, f.RID, 'INIT', data))
        self.assertEqual(init['sequence'], 0)
        ack = dict(sequence=0, run_id=f.RID, command='INIT', payload=worker.startup_ack(plan))
        self.assertTrue(handshake.accept(ack)); self.assertTrue(handshake.accepted)
        self.assertEqual(decoder.feed(worker.encode_frame(1,f.RID,'BIND',{'session_binding_sha256':f.SESSION}))['sequence'],1)
        with self.assertRaises(c.BenignError): handshake.payload_once()
        with self.assertRaises(c.BenignError): handshake.accept(ack)
        self.assertTrue(handshake.failed)

    def test_REG52_bad_startup_ACK_poisoned_no_retry(self):
        _s, _p, _raw, plan = self.inputs()
        for field, value in (('sequence', True), ('sequence', 1), ('run_id','0'*32),('command','BIND')):
            handshake=worker._StartupHandshake(plan);handshake.payload_once()
            ack=dict(sequence=0,run_id=f.RID,command='INIT',payload=worker.startup_ack(plan));ack[field]=value
            with self.subTest(field=field,value=value), self.assertRaises(c.BenignError):handshake.accept(ack)
            self.assertTrue(handshake.failed)
            with self.assertRaises(c.BenignError):handshake.payload_once()

    def test_REG53_startup_ACK_hashes_exact(self):
        _s, _p, _raw, plan = self.inputs()
        for key in ('startup_sha256','worker_binding_sha256','request_sha256'):
            handshake=worker._StartupHandshake(plan);handshake.payload_once()
            ack=worker.startup_ack(plan);ack[key]='0'*64
            with self.subTest(key=key), self.assertRaises(c.BenignError):
                handshake.accept(dict(sequence=0,run_id=f.RID,command='INIT',payload=ack))

    def test_REG54_startup_fragmentation_preserves_full_data(self):
        _s, _p, _raw, plan = self.inputs();raw=worker.encode_frame(0,f.RID,'INIT',c.parse_json(plan.raw))
        for n in (1,3,17,65536):
            decoder=worker.FrameDecoder(f.RID);value=None
            for i in range(0,len(raw),n):value=decoder.feed(raw[i:i+n])
            self.assertEqual(worker.parse_worker_ingress(c.canonical(value['payload'])),plan)
        with self.assertRaises(c.BenignError):worker.FrameDecoder(f.RID).feed(raw+raw)

    def test_REG55_early_codec_matches_main_codec(self):
        _s,_p,raw,_plan=self.inputs()
        self.assertEqual(worker._early_decode(raw,worker.STARTUP_CAP),c.parse_json(raw))
        for bad in (raw+b'\n', raw.replace(b'\n',b'\r\n'), b'{}\n'*2,
                    b'{"a":1,"a":2}\n', b'{"a":1.1}\n', b'{"a":NaN}\n',b'['*17+b']'*17+b'\n'):
            with self.subTest(bad=bad[:32]),self.assertRaises(ValueError):worker._early_decode(bad,worker.STARTUP_CAP)

    def test_REG56_worker_first_entry_denies_before_IO(self):
        for fake in (None,True,object(),{'approved':True,'role':'ARTIFACT_WORKER'}):
            with self.subTest(fake=type(fake).__name__),self.assertRaisesRegex(RuntimeError,'ISSUER_NOT_IMPLEMENTED'):
                worker._worker_first_process(fake)
            with self.subTest(loader=type(fake).__name__),self.assertRaisesRegex(RuntimeError,'ISSUER_NOT_IMPLEMENTED'):
                worker._load_worker_byte_graph(b'{}\n','invalid','invalid',fake)

    def test_REG57_worker_init_wait_nonblocking_fake_completion(self):
        clock=Clock();worker_port=SimpleNamespace(initialization_complete=lambda:clock.tick>=500_000_000)
        ticks=[]
        o._await_worker_initialization(worker_port,clock,300_000_000_000,lambda:ticks.append(clock.tick))
        self.assertEqual(clock.tick,500_000_000);self.assertEqual(len(ticks),3)

    def test_REG58_hung_startup_stops_before_launch(self):
        clock=Clock();worker_port=SimpleNamespace(initialization_complete=lambda:False)
        with self.assertRaises(c.BenignError):o._await_worker_initialization(worker_port,clock,1_000_000_000,lambda:None)
        self.assertLessEqual(clock.tick,1_250_000_000)
        # This helper contains no launch method. Production call order is checked by REG60.

    def test_REG59_late_ack_and_clock_regression_refused(self):
        for kind in ('late','regress','nonbool'):
            clock=Clock()
            def poll():
                if kind=='late':clock.tick=2_000_000_000;return True
                if kind=='regress':clock.tick=-1;return True
                return 1
            with self.subTest(kind=kind),self.assertRaises(c.BenignError):
                o._await_worker_initialization(SimpleNamespace(initialization_complete=poll),clock,1_000_000_000,lambda:None)

    def test_REG60_native_source_initialization_precedes_sandbox(self):
        import inspect
        src=inspect.getsource(o._run_engine)
        self.assertLess(src.index('_await_worker_initialization('),src.index('ctx.ledger.launch_intent('))
        self.assertLess(src.index('ctx.ledger.launch_intent('),src.index('ctx.session.launch('))
        src=inspect.getsource(worker.serve_native_worker)
        self.assertIn('_startup_decoder.expected == 1',src)
        self.assertLess(src.index('checked_first_process_required'),src.index('_WorkerContextOwner('))
        self.assertIn("encode_frame(1, req['run_id'], 'BIND'",src)

    def test_REG61_worker_byte_graph_exact_source_only(self):
        import ast,inspect
        text=inspect.getsource(worker._load_worker_byte_graph)
        for name in worker.WORKER_MODULES:self.assertIn(repr(name),text)
        self.assertIn('exec(compile(data, module.__file__',text)
        self.assertNotIn('sys.path.insert',text);self.assertNotIn('SourceFileLoader(',text)
        self.assertLess(text.index("'worker_first_source_hash'"),text.index('sys.meta_path.insert'))
        self.assertLess(text.index('_early_read(root+'),text.index('sys.meta_path.insert'))
        tree=ast.parse(inspect.getsource(worker._worker_first_process))
        expr=next(n for n in tree.body[0].body if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call))
        self.assertEqual(expr.value.func.id,'_require_local_worker_ingress')

    def test_REG62_no_wire_protocol_or_native_seal_from_startup(self):
        _s,_p,raw,plan=self.inputs()
        self.assertNotIn('permit',c.parse_json(raw));self.assertNotIn('_seal',raw.decode())
        self.assertEqual(worker.decode_reply_observation.__name__,'decode_reply_observation')
        self.assertFalse(o.is_admitted_peer(plan,'INIT',object()))
        with self.assertRaises(c.BenignError):
            bad=c.parse_json(raw);bad['role']='GUEST';worker.parse_worker_ingress(c.canonical(bad))


class FirstProcessReview119Tests(unittest.TestCase):
    """REG77-REG86: pure data and source ordering; no first-process/native execution."""
    def inputs(self):
        spec, proc, startup, plan = FirstProcessIngress118Tests().inputs()
        frame = worker.encode_frame(0, f.RID, 'INIT', c.parse_json(startup))[4:]
        return spec, plan, frame

    def test_REG77_initial_frame_preserves_exact_payload(self):
        _spec, plan, frame = self.inputs()
        startup, rid = worker._parse_initial_worker_frame(frame)
        self.assertEqual((startup, rid), (plan.raw, f.RID))
        self.assertEqual(worker.parse_worker_ingress(startup), plan)

    def test_REG78_cross_run_initial_frame_refused_early(self):
        _spec, _plan, frame = self.inputs()
        outer = c.parse_json(frame); outer['run_id'] = 'f' * 32
        with self.assertRaisesRegex(ValueError, 'worker_startup_run'):
            worker._parse_initial_worker_frame(c.canonical(outer))
        inner = c.parse_json(frame)
        request = c.parse_json(bytes.fromhex(inner['payload']['context']['request_hex']))
        request['run_id'] = 'e' * 32
        inner['payload']['context']['request_hex'] = c.canonical(request).hex()
        with self.assertRaisesRegex(ValueError, 'worker_startup_run'):
            worker._parse_initial_worker_frame(c.canonical(inner))

    def test_REG79_initial_run_id_exact_string(self):
        _spec, _plan, frame = self.inputs()
        for value in (True, 1, None, 'A' * 32, f.RID[:-1], ''):
            obj = c.parse_json(frame); obj['run_id'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                worker._parse_initial_worker_frame(c.canonical(obj))

    def test_REG80_initial_envelope_fields_and_sequence(self):
        _spec, _plan, frame = self.inputs()
        variants = []
        for field, value in (('sequence', True), ('sequence', 1), ('sequence', -1),
                             ('command', 'BIND'), ('command', 'UNKNOWN'), ('extra', True)):
            obj = c.parse_json(frame); obj[field] = value; variants.append(obj)
        obj = c.parse_json(frame); del obj['payload']; variants.append(obj)
        for obj in variants:
            with self.subTest(obj_keys=sorted(obj)), self.assertRaises(ValueError):
                worker._parse_initial_worker_frame(c.canonical(obj))

    def test_REG81_initial_context_hex_and_payload(self):
        _spec, _plan, frame = self.inputs()
        for field, value in (('payload', []), ('context', None), ('kind', 'OTHER'),
                             ('role', 'GUEST'), ('request_hex', ''), ('request_hex', '0'),
                             ('request_hex', 'GG'), ('request_hex', '00'), ('request_hex', True)):
            obj = c.parse_json(frame)
            if field == 'payload': obj['payload'] = value
            elif field in ('context', 'kind', 'role'): obj['payload'][field] = value
            else: obj['payload']['context'][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                worker._parse_initial_worker_frame(c.canonical(obj))

    def test_REG82_initial_parser_bounds_canonical_and_duplicates(self):
        _spec, _plan, frame = self.inputs()
        for raw in (b'', frame + b'\n', frame.replace(b'\n', b'\r\n'),
                    b' ' * 262144 + b'\n', b'{"a":1,"a":2}\n', b'{"sequence":0.0}\n',
                    b'[' * 17 + b']' * 17 + b'\n', b'{"a":NaN}\n'):
            with self.subTest(length=len(raw)), self.assertRaises(ValueError):
                worker._parse_initial_worker_frame(raw)

    def test_REG83_initial_run_binding_precedes_loader_source(self):
        import ast, inspect
        tree = ast.parse(inspect.getsource(worker._worker_first_process))
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
        early = next(n.lineno for n in calls if isinstance(n.func, ast.Name) and
                     n.func.id == '_parse_initial_worker_frame')
        loader = next(n.lineno for n in calls if isinstance(n.func, ast.Name) and
                      n.func.id == '_load_worker_byte_graph')
        observe = next(n.lineno for n in calls if isinstance(n.func, ast.Attribute) and n.func.attr == 'identity')
        recheck = next(n.lineno for n in ast.walk(tree) if isinstance(n, ast.Raise) and
                       isinstance(n.exc, ast.Call) and any(isinstance(a, ast.Constant) and
                       a.value == 'worker_startup_run' for a in n.exc.args))
        ack = next(n.lineno for n in calls if isinstance(n.func, ast.Attribute) and n.func.attr == 'send_bounded')
        self.assertLess(early, loader); self.assertLess(loader, observe)
        self.assertLess(observe, recheck); self.assertLess(recheck, ack)

    def test_REG84_initial_parser_is_data_not_authority(self):
        import ast, inspect
        from .. import benign_runtime_gate as gate
        _spec, _plan, frame = self.inputs()
        data = worker._parse_initial_worker_frame(frame)
        with self.assertRaises(gate.RuntimeClosed): gate.require_benign_run_authority(data)
        tree = ast.parse(inspect.getsource(worker._parse_initial_worker_frame))
        imported = [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
        self.assertEqual(imported, ['json'])
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
                self.assertNotIn(n.func.id, ('open', 'exec', 'eval', '__import__', '_early_read'))

    def test_REG85_context_source_size_boundary_before_reservation(self):
        from dataclasses import replace
        spec, _plan, _frame = self.inputs()
        for size, accepted in ((262144, True), (262145, False), (True, False), (-1, False)):
            rows = tuple((n, size if n == 'README_RU.md' else length, h)
                         for n, length, h in spec.source_files)
            candidate = replace(spec, source_files=rows)
            with self.subTest(size=size):
                if accepted: self.assertIs(candidate.validate(), candidate)
                else:
                    with self.assertRaises(c.BenignError): candidate.validate()

    def test_REG86_context_and_ingress_source_caps_agree(self):
        from dataclasses import replace
        spec, plan, _frame = self.inputs()
        for size, accepted in ((262143, True), (262144, True), (262145, False)):
            rows = tuple((n, size if n == 'README_RU.md' else length, h)
                         for n, length, h in spec.source_files)
            candidate = replace(spec, source_files=rows)
            def ingress():
                return worker.build_worker_ingress(candidate.worker_spec, candidate.source_root,
                    candidate.source_files, candidate.worker_pin, candidate.executable_bytes, plan.worker_binding)
            with self.subTest(size=size):
                if accepted:
                    candidate.validate(); self.assertIsInstance(ingress(), bytes)
                else:
                    with self.assertRaises(c.BenignError): candidate.validate()
                    with self.assertRaises(c.BenignError): ingress()
