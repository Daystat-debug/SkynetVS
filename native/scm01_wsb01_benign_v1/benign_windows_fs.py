"""Source-only Win32 same-handle I/O. No native import or FS operation at import time.
Absolute ancestor chain is held and rechecked; not protection against a hostile OS/admin.
"""
from dataclasses import dataclass
from pathlib import PureWindowsPath
from .benign_contract import need, uint, sha, BenignError
from .benign_layout import winpath, component
from .benign_runtime_gate import require_native_authority


class PendingArtifact(BenignError):
    """Only missing leaf or sharing violation, never malformed completed content."""


class PublicationUnknown(BenignError):
    pass


@dataclass(frozen=True)
class FileMeta:
    volume: int
    file_id: int
    links: int
    size: int
    write_time: int
    attributes: int
    final_path: str
    disk_file: bool = True


@dataclass(frozen=True)
class FileSnapshot:
    name: str
    data: bytes
    metadata: FileMeta
    evidence_domain: str


@dataclass(frozen=True)
class PublicationReceipt:
    name: str
    bytes: int
    sha256: str
    evidence_domain: str


def _clean(meta, path, directory):
    need(type(meta) is FileMeta and meta.disk_file is True, 'regular_disk_file')
    need(not meta.attributes & 0x400, 'reparse')
    need(bool(meta.attributes & 0x10) == directory, 'file_kind')
    need(meta.final_path.casefold() == path.casefold(), 'final_path')
    need(meta.links == 1 or directory, 'hardlink')
    uint(meta.size); uint(meta.volume); uint(meta.file_id); uint(meta.write_time)
    return meta


class _FsEngine:
    def __init__(self, api):
        self.api = api
        self.attempts = set()
        self.domain = 'NATIVE_WIN32_LAB' if type(api) is _WinFsApi else 'OFFLINE_MODEL'

    def open_root(self, path):
        path = winpath(path)
        p = PureWindowsPath(path)
        chain = [str(a) for a in reversed(p.parents)] + [str(p)]
        held = []
        try:
            for part in chain:
                h = self.api.open(part, directory=True, create=False)
                try:
                    m = _clean(self.api.info(h), part, True)
                except Exception:
                    self.api.close(h); raise
                held.append((h, m))
            return RootHandle(self, path, tuple(held))
        except Exception:
            for h, _m in reversed(held):
                self.api.close(h)
            raise


class RootHandle:
    def __init__(self, engine, path, held):
        self.engine, self.path, self.held = engine, path, held
        self.closed = False

    def check(self):
        need(not self.closed, 'root_closed')
        for h, m in self.held:
            current = self.engine.api.info(h)
            # Directory size/times may legitimately change after CREATE_NEW of a child.
            need((current.volume, current.file_id, current.links, current.attributes,
                  current.final_path.casefold(), current.disk_file) ==
                 (m.volume, m.file_id, m.links, m.attributes, m.final_path.casefold(), m.disk_file),
                 'ancestor_identity_changed')

    def close(self):
        if not self.closed:
            self.closed = True
            errors = []
            for h, _ in reversed(self.held):
                try:
                    self.engine.api.close(h)
                except Exception as exc:
                    errors.append(exc)
            if errors:
                raise BenignError('root_close_unknown') from errors[0]

    def __enter__(self):
        self.check(); return self

    def __exit__(self, *_args):
        self.close()


def _pending(exc):
    return getattr(exc, 'winerror', None) in (2, 32)


def read_bounded(root, name, cap):
    need(type(root) is RootHandle, 'root_type'); component(name); uint(cap, 32 * 1024 * 1024)
    need(cap > 0, 'read_cap'); root.check()
    api = root.engine.api; path = root.path + '\\' + name
    try:
        h = api.open(path, directory=False, create=False)
    except OSError as exc:
        if _pending(exc):
            raise PendingArtifact('MISSING_OR_SHARING') from exc
        raise BenignError('open_failed') from exc
    try:
        before = _clean(api.info(h), path, False)
        need(before.size <= cap, 'file_too_large')
        data = bytearray()
        while len(data) <= cap:
            b = api.read(h, min(65536, cap + 1 - len(data)))
            need(type(b) is bytes, 'read_bytes')
            if not b:
                break
            data.extend(b)
            need(len(data) <= cap, 'read_growth')
        after = _clean(api.info(h), path, False)
        need(after == before and len(data) == before.size, 'same_handle_version')
        root.check()
    finally:
        api.close(h)
    return FileSnapshot(name, bytes(data), before, root.engine.domain)


def publish_once(root, name, data):
    need(type(root) is RootHandle, 'root_type'); component(name)
    need(type(data) is bytes and len(data) <= 32 * 1024 * 1024, 'publication_size')
    root.check(); path = root.path + '\\' + name; api = root.engine.api
    need(path.casefold() not in root.engine.attempts, 'publication_consumed')
    root.engine.attempts.add(path.casefold())  # No retry even if CREATE_NEW/flush has unknown outcome.
    h = None
    try:
        h = api.open(path, directory=False, create=True)
        _clean(api.info(h), path, False)
        count = api.write(h, data)
        need(type(count) is int and count == len(data), 'short_write')
        api.flush(h)
        meta = _clean(api.info(h), path, False)
        need(meta.size == len(data), 'write_size')
        root.check()
    except Exception as exc:
        raise PublicationUnknown('PUBLICATION_UNKNOWN') from exc
    finally:
        if h is not None:
            try:
                api.close(h)
            except Exception as exc:
                raise PublicationUnknown('CLOSE_UNKNOWN') from exc
    return PublicationReceipt(name, len(data), sha(data), root.engine.domain)


def list_bounded(root, allowed, cap=16):
    root.check()
    names = root.engine.api.list_names(root.path, cap)
    need(type(names) is tuple and len(names) <= cap and len(set(names)) == len(names), 'inventory')
    for n in names:
        component(n); need(n in allowed, 'unexpected_artifact')
    root.check()
    return names


def open_bound_root(path, permit=None):
    require_native_authority(permit)
    return _FsEngine(_WinFsApi(permit)).open_root(path)


class _WinFsApi:
    def __init__(self, permit):
        require_native_authority(permit)
        import ctypes as c
        import sys
        need(sys.platform == 'win32' and c.sizeof(c.c_void_p) == 8, 'win64')
        self.c = c; self.k = c.WinDLL('kernel32.dll', use_last_error=True, winmode=0x800)
        U = c.c_uint32; H = c.c_void_p; V = H; B = c.c_int32; W = c.c_wchar_p
        class Info(c.Structure):
            _fields_ = [('attrs', U), ('creation_lo', U), ('creation_hi', U),
                        ('access_lo', U), ('access_hi', U), ('write_lo', U), ('write_hi', U),
                        ('volume', U), ('size_hi', U), ('size_lo', U), ('links', U),
                        ('index_hi', U), ('index_lo', U)]
        class FindData(c.Structure):
            _fields_ = [('attrs', U), ('times', U * 6), ('size_hi', U), ('size_lo', U),
                        ('reserved', U * 2), ('name', c.c_wchar * 260), ('alternate', c.c_wchar * 14)]
        self.Info, self.FindData = Info, FindData
        need(c.sizeof(Info) == 52 and c.sizeof(FindData) == 592, 'file_abi')
        signatures = {
            'CreateFileW': (H, [W, U, U, V, U, U, H]),
            'GetFileType': (U, [H]), 'GetFileInformationByHandle': (B, [H, c.POINTER(Info)]),
            'GetFinalPathNameByHandleW': (U, [H, W, U, U]),
            'ReadFile': (B, [H, V, U, c.POINTER(U), V]),
            'WriteFile': (B, [H, V, U, c.POINTER(U), V]),
            'FlushFileBuffers': (B, [H]), 'CloseHandle': (B, [H]),
            'FindFirstFileW': (H, [W, c.POINTER(FindData)]),
            'FindNextFileW': (B, [H, c.POINTER(FindData)]), 'FindClose': (B, [H])}
        for n, (ret, args) in signatures.items():
            f = getattr(self.k, n); f.restype = ret; f.argtypes = args

    def _ok(self, value):
        if not value:
            raise self.c.WinError(self.c.get_last_error())
        return value

    def open(self, path, directory=False, create=False):
        access = 0x80 if directory else (0x40000000 if create else 0x80000000)
        flags = 0x200000 | (0x2000000 if directory else 0x80)
        h = self.k.CreateFileW(path, access, 0 if create else 1, None, 1 if create else 3, flags, None)
        if h in (None, self.c.c_void_p(-1).value):
            raise self.c.WinError(self.c.get_last_error())
        return h

    def info(self, handle):
        c = self.c; i = self.Info(); self._ok(self.k.GetFileInformationByHandle(handle, c.byref(i)))
        buf = c.create_unicode_buffer(1024)
        n = self.k.GetFinalPathNameByHandleW(handle, buf, len(buf), 0)
        self._ok(n); need(n < len(buf), 'final_path_limit')
        p = buf.value
        need(p.startswith('\\\\?\\') and not p.startswith('\\\\?\\UNC\\'), 'final_path_form')
        p = p[4:]
        return FileMeta(i.volume, (i.index_hi << 32) | i.index_lo, i.links,
                        (i.size_hi << 32) | i.size_lo, (i.write_hi << 32) | i.write_lo,
                        i.attrs, p, self.k.GetFileType(handle) == 1)

    def read(self, h, n):
        b = (self.c.c_ubyte * n)(); got = self.c.c_uint32()
        self._ok(self.k.ReadFile(h, b, n, self.c.byref(got), None))
        need(got.value <= n, 'read_return_count'); return bytes(b[:got.value])

    def write(self, h, data):
        b = (self.c.c_ubyte * len(data)).from_buffer_copy(data); n = self.c.c_uint32()
        self._ok(self.k.WriteFile(h, b, len(data), self.c.byref(n), None)); return n.value

    def flush(self, h):
        self._ok(self.k.FlushFileBuffers(h))

    def close(self, h):
        self._ok(self.k.CloseHandle(h))

    def list_names(self, path, cap):
        c = self.c; out = []; info = self.FindData()
        h = self.k.FindFirstFileW(path + '\\*', c.byref(info))
        if h == c.c_void_p(-1).value:
            error = c.get_last_error()
            if error == 2:
                return ()
            raise c.WinError(error)
        try:
            while True:
                if info.name not in ('.', '..'):
                    need(not info.attrs & (0x10 | 0x400), 'output_directory_or_reparse')
                    out.append(info.name); need(len(out) <= cap, 'inventory_cap')
                if not self.k.FindNextFileW(h, c.byref(info)):
                    error = c.get_last_error()
                    need(error == 18, 'incomplete_file_enumeration'); break
        finally:
            self._ok(self.k.FindClose(h))
        return tuple(sorted(out))

    def open_lock(self, path):
        # Lock is not an immutable evidence record. OPEN_ALWAYS + share=0; never truncate/delete it.
        h = self.k.CreateFileW(path, 0x80000000 | 0x40000000, 0, None, 4, 0x200000 | 0x80, None)
        if h in (None, self.c.c_void_p(-1).value):
            raise self.c.WinError(self.c.get_last_error())
        try:
            _clean(self.info(h), path, False)
        except Exception:
            self.close(h); raise
        return h


_SNAPSHOT_SEAL = object()


@dataclass(frozen=True)
class ArtifactSnapshot:
    artifacts: tuple[FileSnapshot, ...]
    root_path: str
    phase: str
    _seal: object = None

    def raw(self):
        return {f.name: f.data for f in self.artifacts}


def capture_snapshot(root, caps, phase):
    need(type(caps) is dict and phase in ('before_retirement', 'after_retirement'), 'snapshot_contract')
    names = list_bounded(root, set(caps))
    snapshots = tuple(read_bounded(root, n, caps[n]) for n in names)
    need(sum(len(x.data) for x in snapshots) <= 262144, 'snapshot_total')
    need(list_bounded(root, set(caps)) == names, 'snapshot_inventory_changed')
    seal = _SNAPSHOT_SEAL if root.engine.domain == 'NATIVE_WIN32_LAB' else None
    return ArtifactSnapshot(snapshots, root.path, phase, seal)


def is_native_snapshot(snapshot, phase):
    return (type(snapshot) is ArtifactSnapshot and snapshot._seal is _SNAPSHOT_SEAL and
            snapshot.phase == phase and all(x.evidence_domain == 'NATIVE_WIN32_LAB'
                                           for x in snapshot.artifacts))


@dataclass(frozen=True)
class MaterializationReceipt:
    manifest_sha256: str
    phase: str
    evidence_domain: str
    _seal: object = None


def verify_static_members(root_specs, phase):
    """Read exact flat members of prebound roots; no recursive discovery or execution."""
    from .benign_contract import canonical
    need(type(root_specs) is tuple and root_specs and phase in ('before_retirement', 'after_retirement'),
         'static_member_specs')
    rows = []; native = True
    for role, root, specs in root_specs:
        need(type(root) is RootHandle and type(specs) is tuple, 'static_root')
        native = native and root.engine.domain == 'NATIVE_WIN32_LAB'
        for name, size, expected in specs:
            s = read_bounded(root, name, max(size, 1))
            need(len(s.data) == size and sha(s.data) == expected, 'static_bytes_changed')
            rows.append({'role': role, 'name': name, 'bytes': size, 'sha256': expected})
    rows.sort(key=lambda r: (r['role'], r['name']))
    return MaterializationReceipt(sha(canonical(rows)), phase,
                                  'NATIVE_WIN32_LAB' if native else 'OFFLINE_MODEL',
                                  _SNAPSHOT_SEAL if native else None)


def is_native_materialization(r, phase, expected):
    return (type(r) is MaterializationReceipt and r._seal is _SNAPSHOT_SEAL and
            r.phase == phase and r.evidence_domain == 'NATIVE_WIN32_LAB' and r.manifest_sha256 == expected)


class _RetainedFiles:
    """Own read handles retained after hash validation. Source/host fixture only,
    not an authority token and not intended for the writable guest Output mapping.
    """
    def __init__(self, engine):
        self.engine = engine; self.files = []; self.roots = []; self.closed = False

    def add(self, path, size, expected_sha):
        from .benign_contract import hexstr
        winpath(path); uint(size, 32 * 1024**2); hexstr(expected_sha)
        need(not self.closed and path.casefold() not in {x[0].casefold() for x in self.files}, 'retained_duplicate')
        parent = str(PureWindowsPath(path).parent)
        root = self.engine.open_root(parent); self.roots.append(root)
        handle = None
        try:
            handle = self.engine.api.open(path, directory=False, create=False)
            meta = _clean(self.engine.api.info(handle), path, False)
            need(meta.size == size, 'retained_file_size')
            data = bytearray()
            while True:
                chunk = self.engine.api.read(handle, min(65536, size + 1 - len(data)))
                need(type(chunk) is bytes, 'retained_read_bytes')
                if not chunk: break
                data.extend(chunk); need(len(data) <= size, 'retained_growth')
            need(len(data) == size and sha(bytes(data)) == expected_sha, 'retained_hash')
            need(_clean(self.engine.api.info(handle), path, False) == meta, 'retained_version')
            root.check(); self.files.append((path, handle, meta, expected_sha))
        except Exception:
            if handle is not None: self.engine.api.close(handle)
            raise

    def check(self):
        need(not self.closed, 'retained_program_closed')
        for root in self.roots: root.check()
        for path, h, meta, _ in self.files:
            need(_clean(self.engine.api.info(h), path, False) == meta, 'retained_program_changed')
        return True

    def close(self):
        if self.closed: return
        self.closed = True; errors = []
        while self.files:
            _path, handle, _meta, _sha = self.files.pop()
            try: self.engine.api.close(handle)
            except Exception as exc: errors.append(exc)
        while self.roots:
            root = self.roots.pop()
            try: root.close()
            except Exception as exc: errors.append(exc)
        if errors: raise BenignError('retained_program_close_unknown') from errors[0]


def retain_exact_files(engine, rows):
    """Fault-injectable, finite same-handle algorithm; fake engine stays OFFLINE_MODEL."""
    need(type(engine) is _FsEngine and type(rows) is tuple and 0 < len(rows) <= 128, 'retained_file_list')
    owned = _RetainedFiles(engine)
    try:
        for path, size, expected_sha in rows: owned.add(path, size, expected_sha)
        owned.check(); return owned
    except Exception:
        owned.close(); raise
