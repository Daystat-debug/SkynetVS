"""WINDOWS_BINDINGS01-08: Win32-shaped fake calls; no ctypes/DLL initialization."""
from dataclasses import replace
from pathlib import PureWindowsPath
import unittest
from . import test_contract as f
from .. import benign_contract as c
from .. import benign_windows_fs as fs
from .. import benign_windows_crypto as crypto
from .. import benign_windows_session as ps


def winerr(number):
    exc = OSError('fake Windows error'); exc.winerror = number; return exc


class FakeFs:
    def __init__(self):
        self.files = {}; self.metas = {}; self.handles = {}; self.cursor = {}; self.next_h = 1
        self.fail = ''; self.closed = []; self.read_change = False; self.calls = []

    def directory(self, path):
        for name in list(map(str, reversed(PureWindowsPath(path).parents))) + [path]:
            if name not in self.metas:
                self.metas[name] = fs.FileMeta(1, len(self.metas) + 1, 1, 0, 0, 0x10, name)

    def put(self, path, data):
        self.directory(str(PureWindowsPath(path).parent))
        self.files[path] = data
        self.metas[path] = fs.FileMeta(1, len(self.metas) + 1, 1, len(data), 0, 0, path)

    def open(self, path, directory, create):
        self.calls.append(('open', path, directory, create))
        if self.fail == 'sharing': raise winerr(32)
        if self.fail == 'access': raise winerr(5)
        if create:
            if path in self.metas: raise winerr(80)
            self.put(path, b'')
        if path not in self.metas: raise winerr(2)
        h = self.next_h; self.next_h += 1; self.handles[h] = path; self.cursor[h] = 0
        return h

    def info(self, h): return self.metas[self.handles[h]]

    def read(self, h, n):
        path = self.handles[h]; pos = self.cursor[h]
        out = self.files[path][pos:pos + n]; self.cursor[h] += len(out)
        if self.read_change:
            self.metas[path] = replace(self.metas[path], write_time=self.metas[path].write_time + 1)
        return out

    def write(self, h, data):
        count = max(0, len(data) - 1) if self.fail == 'short' else len(data)
        path = self.handles[h]; self.files[path] = data[:count]
        self.metas[path] = replace(self.metas[path], size=count)
        return count

    def flush(self, h):
        if self.fail == 'flush': raise winerr(5)

    def close(self, h):
        self.closed.append(h); del self.handles[h]
        if self.fail == 'close': raise winerr(5)

    def list_names(self, path, cap):
        names = tuple(sorted(str(PureWindowsPath(x).name) for x in self.files
                             if str(PureWindowsPath(x).parent) == path))
        c.need(len(names) <= cap, 'list_cap'); return names

    def open_lock(self, path):
        if path not in self.files: self.put(path, b'')
        return self.open(path, False, False)


def root_fs(path='C:\\Lab\\Output'):
    api = FakeFs(); api.directory(path); engine = fs._FsEngine(api)
    return api, engine, engine.open_root(path)


class FakeCrypto:
    def __init__(self, fail=''):
        self.calls = []; self.fail = fail
    def open_algorithm(self): self.calls.append('open'); return (-1 if self.fail == 'open' else 0), 1
    def import_public(self, alg, blob): self.calls.append(('import', blob)); return (-1 if self.fail == 'import' else 0), 2
    def verify(self, key, digest, sig): self.calls.append(('verify', digest, sig)); return -1 if self.fail == 'verify' else 0
    def destroy_key(self, key): self.calls.append('destroy'); return -1 if self.fail == 'destroy' else 0
    def close_algorithm(self, alg): self.calls.append('close'); return -1 if self.fail == 'close' else 0
    def generate(self, alg): self.calls.append('generate'); return 0, 2
    def finalize(self, key): self.calls.append('finalize'); return 0
    def export_public(self, key): self.calls.append('export_public'); return 0, f.KEY
    def sign(self, key, digest): self.calls.append(('sign', digest)); return 0, f.SIG


INVENTORY = (('WindowsSandbox.exe', 'C:\\Windows\\System32\\WindowsSandbox.exe'),
             ('WindowsSandboxRemoteSession.exe', 'C:\\Windows\\System32\\WindowsSandboxRemoteSession.exe'))
LAUNCHER = ps.ProcessIdentity(100, 1000, INVENTORY[0][1], 1, 50, 'S-1-5-21-100')
ANCHOR = ps.ProcessIdentity(101, 1001, INVENTORY[1][1], 1, 50, 'S-1-5-21-100')


class FakeProcess:
    def __init__(self, processes=(), end_error=18):
        self.processes = processes; self.end_error = end_error; self.tick = 0
        self.lookup = {p.pid: p for p in (LAUNCHER, ANCHOR)}; self.waits = {}; self.closed = []
        self.terminated = []; self.queries = []; self.pos = 0; self.boot = f.BOOT
    def snapshot(self): self.pos = 0; return 'snapshot'
    def boot_binding(self): return self.boot
    def now_ns(self): return self.tick
    def first(self, h): return self._row()
    def next(self, h): return self._row()
    def _row(self):
        if self.pos >= len(self.processes): return False, 0, '', self.end_error
        p = self.processes[self.pos]; self.pos += 1
        return True, p.pid, PureWindowsPath(p.path).name, 0
    def open_process(self, pid): return pid
    def identity(self, h, pid): self.queries.append(pid); return self.lookup[pid]
    def close(self, h): self.closed.append(h)
    def wait(self, h, ms): return self.waits.get(h, 258)
    def terminate(self, h): self.terminated.append(h)
    def launch(self, exe, cfg): return LAUNCHER.pid, LAUNCHER.pid


def binding():
    return ps.SessionBinding(f.RID, f.NONCE, f.BOOT, c.sha(f.request()), 'e' * 64,
                             (LAUNCHER, ANCHOR), (100, 101), f.SESSION)


class WindowsBindingTests(unittest.TestCase):
    def test_WINDOWS_BINDINGS01_first_false_requires_no_more_files(self):
        api = FakeProcess(); engine = ps._ProcessEngine(api, INVENTORY)
        self.assertEqual(engine.snapshot_complete().processes, ())
        api.end_error = 5
        with self.assertRaises(c.BenignError): engine.snapshot_complete()
        self.assertEqual(api.closed, ['snapshot', 'snapshot'])

    def test_WINDOWS_BINDINGS02_partial_next_is_not_empty(self):
        api = FakeProcess((ANCHOR,), 5)
        with self.assertRaises(c.BenignError): ps._ProcessEngine(api, INVENTORY).snapshot_complete()
        self.assertIn(101, api.closed); self.assertIn('snapshot', api.closed)

    def test_WINDOWS_BINDINGS03_token_metadata_mandatory(self):
        for bad in (replace(ANCHOR, authentication_id=0), replace(ANCHOR, user_sid=''),
                    replace(ANCHOR, created=0), replace(ANCHOR, path='C:\\Other\\WindowsSandboxRemoteSession.exe')):
            api = FakeProcess((ANCHOR,)); api.lookup[101] = bad
            with self.subTest(bad=bad), self.assertRaises(c.BenignError):
                ps._ProcessEngine(api, INVENTORY).snapshot_complete()

    def test_WINDOWS_BINDINGS04_stale_identity_not_terminated(self):
        api = FakeProcess(); api.lookup[101] = replace(ANCHOR, created=9999)
        out = ps._ProcessEngine(api, INVENTORY).cleanup(binding())
        self.assertNotIn(101, api.terminated); self.assertTrue(out.errors)

    def test_WINDOWS_BINDINGS05_terminate_return_not_retirement(self):
        api = FakeProcess(); out = ps._ProcessEngine(api, INVENTORY).cleanup(binding())
        self.assertEqual(out.confirmed, ()); self.assertEqual(out.attempted, (100, 101))
        self.assertTrue(out.failure); self.assertFalse(out.hypervisor_disposal_proven)
        api = FakeProcess(); api.waits = {100: 0, 101: 0}
        engine = ps._ProcessEngine(api, INVENTORY)
        for i in range(3): api.tick = i * ps.MIN_SCAN_NS; obs = engine.observe(binding())
        self.assertTrue(obs.normal); self.assertEqual(api.queries, [])
        self.assertFalse(ps.is_native_retirement(obs, f.RID, f.NONCE, f.SESSION, f.BOOT))

    def test_WINDOWS_BINDINGS06_cng_prehash_cleanup_and_fake_receipt(self):
        api = FakeCrypto(); engine = crypto._CryptoEngine(api)
        receipt = engine.verify(f.KEY, c.READY_DOMAIN, b'data', f.SIG)
        self.assertIn(('verify', crypto.prehash(c.READY_DOMAIN, b'data'), f.SIG), api.calls)
        self.assertEqual(api.calls[-2:], ['destroy', 'close'])
        self.assertFalse(crypto.is_native_receipt(receipt, c.READY_DOMAIN, b'data', f.KEY, f.SIG))
        for fail in ('open', 'import', 'verify', 'destroy', 'close'):
            with self.subTest(fail=fail), self.assertRaises(c.BenignError):
                crypto._CryptoEngine(FakeCrypto(fail)).verify(f.KEY, c.READY_DOMAIN, b'data', f.SIG)
        with self.assertRaises(c.BenignError): crypto.prehash(b'OTHER', b'data')
        with self.assertRaises(c.BenignError): crypto.validate_signature(b'x' * 63)
        with self.assertRaises(c.BenignError): crypto.validate_public(b'x' * 72)
        api = FakeCrypto(); signer = crypto._CryptoEngine(api).signer()
        signer.sign(c.READY_DOMAIN, b'x')
        with self.assertRaises(c.BenignError): signer.sign(c.READY_DOMAIN, b'x')
        signer.close(); self.assertNotIn('export_private', api.calls)

    def test_WINDOWS_BINDINGS07_ancestor_and_same_handle_read(self):
        api, engine, root = root_fs(); api.put(root.path + '\\a', b'abc')
        self.assertEqual(fs.read_bounded(root, 'a', 3).data, b'abc')
        api.read_change = True
        with self.assertRaises(c.BenignError): fs.read_bounded(root, 'a', 3)
        root.close(); self.assertFalse(api.handles)
        api = FakeFs(); api.directory('C:\\Lab\\Output')
        api.metas['C:\\Lab'] = replace(api.metas['C:\\Lab'], attributes=0x410)
        with self.assertRaises(c.BenignError): fs._FsEngine(api).open_root('C:\\Lab\\Output')
        self.assertFalse(api.handles)

    def test_WINDOWS_BINDINGS08_publication_failure_never_retry(self):
        for fail in ('short', 'flush', 'close'):
            api, engine, root = root_fs(); api.fail = fail
            with self.subTest(fail=fail), self.assertRaises(fs.PublicationUnknown): fs.publish_once(root, 'a', b'abc')
            api.fail = ''
            with self.assertRaises(c.BenignError): fs.publish_once(root, 'a', b'abc')
            root.close()
        api, engine, root = root_fs()
        with self.assertRaises(fs.PendingArtifact): fs.read_bounded(root, 'missing', 3)
        api.fail = 'sharing'
        with self.assertRaises(fs.PendingArtifact): fs.read_bounded(root, 'missing', 3)
        api.fail = 'access'
        with self.assertRaises(c.BenignError) as result: fs.read_bounded(root, 'missing', 3)
        self.assertNotIsInstance(result.exception, fs.PendingArtifact)
        api.fail = ''; root.close()


class OwnWorkerApi117:
    def __init__(self, fail='', extra=False):
        self.fail = fail; self.extra = extra; self.next_pipe = 1; self.closed = []; self.calls = []
        self.exited = False; self.boot = f.BOOT
    def boot_binding(self): return self.boot
    def now_ns(self): return 0
    def create_pipe(self):
        pair = (self.next_pipe, self.next_pipe + 1); self.next_pipe += 2; return pair
    def set_inherit(self, h, enabled): self.calls.append(('inherit', h, enabled))
    def create_job(self, *args): self.calls.append('job'); return 30
    def create_suspended_worker(self, descriptor): self.calls.append('create'); return 20, 21, 22
    def assign(self, j, h): self.calls.append('assign')
    def resume(self, h): self.calls.append('resume')
    def job_processes(self, j): return (22, 99) if self.extra else (22,)
    def identity(self, h, pid):
        if self.fail == 'identity': raise OSError('no identity')
        return ps.ProcessIdentity(22, 100, 'C:\\Python\\python.exe', 1, 2, 'S-1-5-21-1')
    def wait(self, h, ms): return 0 if self.exited else 258
    def terminate(self, h): self.calls.append(('terminate', h)); self.exited = True
    def close(self, h): self.closed.append(h)


class NativeSourceRegression117Tests(unittest.TestCase):
    def pin(self):
        return ps.WorkerSourcePin('C:\\Python\\python.exe', 'a' * 64,
                                 'C:\\Source\\benign_worker.py', 'b' * 64)

    def test_REG23_owned_worker_job_and_parent_pipe_lifetime(self):
        api = OwnWorkerApi117(); owned = ps._OwnedWorker(api, self.pin()); owned.start_once()
        self.assertEqual(owned.domain, 'OFFLINE_MODEL'); owned.check_live()
        self.assertIn(1, api.closed); self.assertIn(4, api.closed)
        self.assertNotIn(2, api.closed); self.assertNotIn(3, api.closed)
        self.assertLess(api.calls.index('assign'), api.calls.index('resume'))
        with self.assertRaises(c.BenignError): owned.start_once()
        owned.stop_once(); owned.close_pipes()
        self.assertEqual(sorted(api.closed), [1, 2, 3, 4, 20, 21, 30])

    def test_REG24_owned_worker_identity_failure_cleanup(self):
        api = OwnWorkerApi117('identity'); owned = ps._OwnedWorker(api, self.pin())
        with self.assertRaises(OSError): owned.start_once()
        self.assertIn(('terminate', 20), api.calls)
        self.assertEqual(sorted(api.closed), [1, 2, 3, 4, 20, 21, 30])
        self.assertTrue(owned.closed)

    def test_REG25_owned_worker_extra_pid_never_resumes(self):
        api = OwnWorkerApi117(extra=True); owned = ps._OwnedWorker(api, self.pin())
        with self.assertRaises(c.BenignError): owned.start_once()
        self.assertNotIn('resume', api.calls); self.assertIn(('terminate', 20), api.calls)
        self.assertEqual(sorted(api.closed), [1, 2, 3, 4, 20, 21, 30])

    def test_REG26_own_worker_incarnation_change_is_failure(self):
        api = OwnWorkerApi117(); owned = ps._OwnedWorker(api, self.pin()); owned.start_once()
        api.boot = '0' * 64
        with self.assertRaises(c.BenignError): owned.check_live()
        owned.stop_once(); owned.close_pipes()

    def test_REG27_retained_program_handles_release(self):
        api = FakeFs(); api.put('C:\\Code\\a.py', b'fixed'); api.put('C:\\Code\\b.py', b'')
        owned = fs.retain_exact_files(fs._FsEngine(api), (('C:\\Code\\a.py', 5, c.sha(b'fixed')),
                                                       ('C:\\Code\\b.py', 0, c.sha(b''))))
        self.assertTrue(owned.check()); self.assertTrue(api.handles)
        api.metas['C:\\Code\\a.py'] = replace(api.metas['C:\\Code\\a.py'], write_time=9)
        with self.assertRaises(c.BenignError): owned.check()
        owned.close(); self.assertFalse(api.handles)

    def test_REG28_retained_program_bad_hash_closes_every_handle(self):
        api = FakeFs(); api.put('C:\\Code\\a.py', b'fixed')
        with self.assertRaises(c.BenignError):
            fs.retain_exact_files(fs._FsEngine(api), (('C:\\Code\\a.py', 5, '0' * 64),))
        self.assertFalse(api.handles)

    def test_REG29_host_ticks_use_one_monotonic_clock_source(self):
        import inspect
        text = inspect.getsource(ps._WinProcessApi.now_ns)
        self.assertIn('time.monotonic_ns()', text); self.assertNotIn('GetTickCount64()', text)
        # Source-level clock origin assertion, NOT a call of the native API.
