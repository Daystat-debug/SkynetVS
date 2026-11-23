"""Windows-only, closed Working Tree profile. Source bytes are data throughout."""
from contextlib import contextmanager, ExitStack
from dataclasses import dataclass
import ctypes
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tokenize
from types import MappingProxyType

import skynet_scope_lab as lab
from skynet_core_task import Rejected


def digest(data):
    return hashlib.sha256(data).hexdigest()


def identity(info):
    return info.st_dev, info.st_ino, info.st_birthtime_ns


def stamp(info):
    return identity(info), info.st_size, info.st_mtime_ns


def open_plain(stack, path, directory):
    import _winapi
    import msvcrt
    # OPEN_REPARSE_POINT applies to the final component. Its ancestors are already pinned.
    flags = 0x00200000 | (0x02000000 if directory else 0)  # BACKUP_SEMANTICS for directories.
    handle = _winapi.CreateFile(str(path), _winapi.GENERIC_READ, 1, 0, _winapi.OPEN_EXISTING, flags, 0)
    try:
        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except BaseException:
        _winapi.CloseHandle(handle)
        raise
    stack.callback(os.close, fd)
    info = os.fstat(fd)
    if info.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        raise Rejected("working_reparse_point")
    final = ctypes.create_unicode_buffer(32768)
    count = ctypes.windll.kernel32.GetFinalPathNameByHandleW(ctypes.c_void_p(handle), final, len(final), 0)
    if not 0 < count < len(final) or final.value.casefold() != ("\\\\?\\" + str(path)).casefold():
        raise Rejected("working_path_mismatch")
    if directory:
        if not stat.S_ISDIR(info.st_mode):
            raise Rejected("working_directory")
    elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise Rejected("working_file_type")
    if not info.st_ino or identity(os.lstat(path)) != identity(info):
        raise Rejected("working_identity_changed")
    return fd, info


def checked_path(root, name):
    if name not in lab.SCOPE:
        raise Rejected("working_path_outside_profile")
    return root / name


@contextmanager
def locked_files(root):
    if os.name != "nt" or not root.is_absolute() or len(root.drive) != 2 or ".." in root.parts:
        raise Rejected("working_root")
    with ExitStack() as stack:
        try:
            paths = {name:checked_path(root, name) for name in sorted(lab.SCOPE)}
            parents = {parent for path in paths.values() for parent in path.parents}
            for parent in sorted(parents, key=lambda p:(len(p.parts), str(p))):
                open_plain(stack, parent, True)
            files = {name:open_plain(stack, path, False) for name,path in paths.items()}
        except OSError as exc:
            raise Rejected("working_busy" if exc.winerror == 32 else "working_unavailable") from exc
        yield files


def read_files(root, files):
    raw, stamps = {}, {}
    for name, (fd, before) in files.items():
        if not 0 < before.st_size <= 256 * 1024:
            raise Rejected("working_size")
        with os.fdopen(os.dup(fd), "rb") as stream:
            data = stream.read(before.st_size + 1)
        after = os.fstat(fd)
        named = os.lstat(checked_path(root, name))
        if (len(data) != before.st_size or stamp(before) != stamp(after) or stamp(after) != stamp(named)
                or named.st_nlink != 1 or named.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            raise Rejected("working_changed")
        raw[name], stamps[name] = data, stamp(after)
    return raw, stamps


@dataclass(frozen=True)
class TextSnapshot:
    sources: MappingProxyType


class WorkingSources:
    working_tree = True
    lexical_flows = True
    heading = "По сохранённым файлам рабочего снимка:"

    def __init__(self, root):
        self.root = Path(root)
        with locked_files(self.root) as files:
            raw, stamps = read_files(self.root, files)
        self.raw = MappingProxyType(raw)
        self.stamps = MappingProxyType(stamps)
        self.hashes = MappingProxyType({p:digest(data) for p,data in raw.items()})
        manifest = json.dumps(dict(self.hashes), sort_keys=True, separators=(",", ":")).encode()
        # The legacy AST readers call this opaque same-snapshot key "commit" internally.
        self.commit = "wt-sha256-" + digest(manifest)
        try:
            texts = {}
            for path, data in raw.items():
                encoding, _ = tokenize.detect_encoding(io.BytesIO(data).readline)
                if encoding not in ("utf-8", "utf-8-sig"):
                    raise Rejected("working_encoding")
                texts[path] = data.decode(encoding)
            self.pages = {p:lab.cli.page(source) for p,source in texts.items()}
        except Rejected:
            raise
        except (UnicodeError, SyntaxError, ValueError) as exc:
            raise Rejected("working_invalid_python") from exc
        self.snapshot = TextSnapshot(MappingProxyType(texts))

    def current(self):
        # Analyzer calls refer only to the immutable capture. The host revalidates on publication.
        pass

    @contextmanager
    def publication_guard(self):
        with locked_files(self.root) as files:
            raw, stamps = read_files(self.root, files)
            if stamps != self.stamps or raw != self.raw:
                raise Rejected("working_changed")
            yield  # Keep all file and directory handles pinned through Task's terminal decision.

    def span(self, path, start, end):
        location = checked_path(self.root, path)
        lines = self.raw[path].splitlines(keepends=True)
        if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines):
            raise Rejected("invalid_reference")
        excerpt = b"".join(lines[start-1:end])
        key = json.dumps([self.commit,path,start,end]).encode()
        ref = dict(id="W"+digest(key), source_kind="working_tree", snapshot_id=self.commit,
                   path=path, start=start, end=end, source_sha256=self.hashes[path],
                   excerpt_sha256=digest(excerpt), source_code_executed=False,
                   url=f"{location.as_uri()}#L{start}-L{end}&snapshot={self.commit}")
        return {"ref":ref, "text":excerpt.decode("utf8")}
