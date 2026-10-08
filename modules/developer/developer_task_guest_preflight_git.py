from __future__ import annotations

"""Bounded native Git observations and a private index for explicit V2 preflight.

No V1 manifest adapter. Only allowlisted Git builtins run; no task code is imported,
compiled or executed. Not an OS security boundary against a hostile same-user writer.
"""

import json
import os
import re
import stat
import subprocess
import time
from pathlib import Path
from typing import Any

from modules.developer.developer_task_guest_preflight_contract import (
    DeveloperTaskGuestPreflightError, canonical, object_oid, require, sha,
)

MAX_TRACKED = 20000
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_TRACKED_TOTAL = 128 * 1024 * 1024
MAX_GIT_OUTPUT = 24 * 1024 * 1024
MAX_GIT_STDERR = 256 * 1024
GIT_TIMEOUT_SECONDS = 15.0
MAX_METADATA_ENTRIES = 100000
_GIT_OID = re.compile(r"[0-9a-f]{40}\Z")
_RESERVED = re.compile(r"(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?\Z", re.I)


def extended(path: Path) -> str:
    value = os.path.abspath(os.fspath(path))
    if os.name != "nt" or value.startswith("\\\\?\\"):
        return value
    if value.startswith("\\\\"):
        return "\\\\?\\UNC\\" + value[2:]
    return "\\\\?\\" + value


def indirect(s: os.stat_result) -> bool:
    return stat.S_ISLNK(s.st_mode) or bool(getattr(s, "st_file_attributes", 0) & 0x400)


def absolute_path(value: Any) -> Path:
    require(isinstance(value, Path) and value.is_absolute(), "absolute_path_required")
    require(".." not in value.parts, "path_parent_component")
    return Path(os.path.abspath(value))


def directory_chain(path: Path) -> None:
    p = absolute_path(path)
    for item in (*reversed(p.parents), p):
        s = os.lstat(extended(item))
        require(stat.S_ISDIR(s.st_mode) and not indirect(s), "unsafe_directory")


def _version(s: os.stat_result) -> tuple:
    return (s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns, s.st_nlink,
            getattr(s, "st_file_attributes", 0))


def _path_handle_match(path: Path, before: os.stat_result, opened: os.stat_result, *, windows: bool) -> bool:
    """Admit only CPython's Windows path-stat executable-suffix mode synthesis.

    Path stat adds 0111 for these suffixes; fstat does not. All other metadata
    must match. Same-API before/after checks keep the complete _version.
    """
    a, b = _version(before), _version(opened)
    if a == b:
        return True
    return (windows and path.suffix.casefold() in (".exe", ".bat", ".cmd", ".com")
            and stat.S_ISREG(before.st_mode) and stat.S_ISREG(opened.st_mode)
            and a[:2] == b[:2] and a[3:] == b[3:]
            and opened.st_mode & 0o111 == 0
            and before.st_mode == (opened.st_mode | 0o111))


def read_regular(path: Path, *, maximum: int = MAX_FILE_BYTES, hardlinks: bool = False) -> bytes:
    directory_chain(path.parent)
    s = os.lstat(extended(path))
    require(stat.S_ISREG(s.st_mode) and not indirect(s), "unsafe_file")
    require(s.st_nlink >= 1 if hardlinks else s.st_nlink == 1, "hardlinked_source_file")
    require(0 <= s.st_size <= maximum, "file_size_limit")
    fd = os.open(extended(path), os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(fd)
        require(_path_handle_match(path, s, opened, windows=os.name == "nt"), "file_identity_race")
        parts = []
        remaining = s.st_size + 1
        while remaining:
            block = os.read(fd, min(65536, remaining))
            if not block:
                break
            parts.append(block)
            remaining -= len(block)
        raw = b"".join(parts)
        require(_version(os.fstat(fd)) == _version(opened), "file_handle_race")
    finally:
        os.close(fd)
    require(_version(os.lstat(extended(path))) == _version(s) and len(raw) == s.st_size,
            "file_changed_during_read")
    return raw


def git_identity(path: Path, expected_sha256: str) -> dict:
    require(type(expected_sha256) is str and re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is not None,
            "git_expected_digest_invalid")
    data = read_regular(path, maximum=32 * 1024 * 1024, hardlinks=True)
    require(sha(data) == expected_sha256, "git_executable_digest_mismatch")
    return {"path": str(path), "bytes": len(data), "sha256": sha(data),
            "file_version": list(_version(os.lstat(extended(path))))}


def safe_repo_path(value: str) -> None:
    require(type(value) is str and 0 < len(value) <= 240 and value == value.strip(), "repository_path_invalid")
    require(not value.startswith("/") and "\\" not in value, "repository_path_invalid")
    require(not any(ord(c) < 32 or ord(c) == 127 or c in '<>:"|?*' for c in value), "repository_path_invalid")
    parts = value.split("/")
    require(all(p not in ("", ".", "..") and not p.endswith((".", " "))
                and len(p) <= 120 and not _RESERVED.fullmatch(p) for p in parts), "repository_path_invalid")
    require(parts[0].casefold() != ".git", "git_metadata_tree_path")


def check_entries(entries: list[dict]) -> None:
    require(0 < len(entries) <= MAX_TRACKED, "repository_entry_limit")
    seen: dict[str, str] = {}
    leaves: set[str] = set()
    for row in entries:
        require(set(row) == {"path", "mode", "oid"}, "index_entry_fields")
        path = row["path"]
        safe_repo_path(path)
        require(row["mode"] in ("100644", "100755"), "repository_special_mode")
        require(type(row["oid"]) is str and _GIT_OID.fullmatch(row["oid"]) is not None, "repository_oid_invalid")
        parts = path.split("/")
        for k in range(1, len(parts) + 1):
            prefix = "/".join(parts[:k])
            key = prefix.casefold()
            require(key not in seen or seen[key] == prefix, "repository_case_collision")
            require(key not in leaves, "repository_path_collision")
            seen[key] = prefix
        leaves.add(path.casefold())


def tree_oid(entries: list[dict]) -> str:
    check_entries(entries)
    root: dict = {}
    for row in entries:
        node = root
        parts = row["path"].split("/")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
            require(type(node) is dict, "repository_path_collision")
        require(parts[-1] not in node, "repository_path_collision")
        node[parts[-1]] = (row["mode"], row["oid"])
    def build(node):
        out = bytearray()
        for name, item in sorted(node.items(), key=lambda kv: (kv[0] + ("/" if type(kv[1]) is dict else "")).encode("utf-8")):
            mode, oid = ("40000", build(item)) if type(item) is dict else item
            out += (mode + " " + name).encode("utf-8") + b"\0" + bytes.fromhex(oid)
        return object_oid("tree", bytes(out))
    return build(root)


def parse_index(raw: bytes) -> list[dict]:
    out = []
    try:
        for record in raw.split(b"\0"):
            if not record:
                continue
            header, path = record.split(b"\t", 1)
            mode, oid, stage = header.decode("ascii").split(" ")
            require(stage == "0", "index_not_stage_zero")
            out.append({"mode": mode, "oid": oid, "path": path.decode("utf-8")})
    except (ValueError, UnicodeError) as exc:
        if isinstance(exc, DeveloperTaskGuestPreflightError):
            raise
        raise DeveloperTaskGuestPreflightError("index_output_invalid") from exc
    check_entries(out)
    return out


def parse_tree(raw: bytes) -> list[dict]:
    out = []
    try:
        for record in raw.split(b"\0"):
            if not record:
                continue
            header, path = record.split(b"\t", 1)
            mode, kind, oid = header.decode("ascii").split(" ")
            require(kind == "blob", "repository_special_mode")
            out.append({"mode": mode, "oid": oid, "path": path.decode("utf-8")})
    except (ValueError, UnicodeError) as exc:
        if isinstance(exc, DeveloperTaskGuestPreflightError):
            raise
        raise DeveloperTaskGuestPreflightError("tree_output_invalid") from exc
    check_entries(out)
    return out


def metadata_snapshot(gitdir: Path) -> dict:
    directory_chain(gitdir)
    forbidden = ("commondir", "shallow", "info/grafts", "objects/info/alternates", "objects/info/http-alternates",
                 "MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-apply", "rebase-merge", "sequencer",
                 "index.lock", "HEAD.lock", "config.lock", "packed-refs.lock")
    for rel in forbidden:
        require(not os.path.lexists(extended(gitdir / rel)), "unsupported_repository_state")
    files = {}
    for rel in ("index", "config", "HEAD", "packed-refs", "info/attributes", "info/exclude"):
        p = gitdir / rel
        files[rel] = sha(read_regular(p)) if os.path.lexists(extended(p)) else None
    require(all(files[x] is not None for x in ("index", "config", "HEAD")), "repository_metadata_missing")
    objects = []
    for subtree in ("objects", "refs", "logs"):
        parent = gitdir / subtree
        if not os.path.lexists(extended(parent)):
            continue
        directory_chain(parent)
        todo = [parent]
        while todo:
            directory = todo.pop()
            with os.scandir(extended(directory)) as it:
                names = sorted(e.name for e in it)
            for name in names:
                p = directory / name
                rel = p.relative_to(gitdir).as_posix()
                s = os.lstat(extended(p))
                require(not indirect(s), "indirect_git_metadata")
                require(not rel.endswith(".lock"), "repository_metadata_locked")
                require(not rel.startswith("refs/replace/"), "replace_ref_forbidden")
                if stat.S_ISDIR(s.st_mode):
                    objects.append([rel + "/", s.st_dev, s.st_ino])
                    todo.append(p)
                else:
                    require(stat.S_ISREG(s.st_mode), "special_git_metadata")
                    objects.append([rel, s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns])
                    if subtree != "objects":
                        files[rel] = sha(read_regular(p))
                require(len(objects) <= MAX_METADATA_ENTRIES, "git_metadata_limit")
    return {"files": files, "objects_refs_logs_metadata_sha256": sha(canonical(sorted(objects)))}


def remove_private_tree(root: Path) -> None:
    """Remove only the caller-owned fresh temporary tree, including Windows readonly blobs.

    Walk and validate first; never follow reparses or change attributes of hardlinks.
    The coordinator passes only its own mkdtemp return value, not a request field.
    """
    directory_chain(root)
    directories = [root]
    files: list[Path] = []
    todo = [root]
    while todo:
        parent = todo.pop()
        with os.scandir(extended(parent)) as it:
            names = sorted(e.name for e in it)
        for name in names:
            p = parent / name
            st = os.lstat(extended(p))
            require(not indirect(st), "temporary_cleanup_indirect_path")
            if stat.S_ISDIR(st.st_mode):
                directories.append(p)
                todo.append(p)
            else:
                require(stat.S_ISREG(st.st_mode) and st.st_nlink == 1, "temporary_cleanup_unsafe_file")
                files.append(p)
            require(len(files) + len(directories) <= MAX_METADATA_ENTRIES, "temporary_cleanup_entry_limit")
    for p in files:
        directory_chain(p.parent)
        st = os.lstat(extended(p))
        require(stat.S_ISREG(st.st_mode) and not indirect(st) and st.st_nlink == 1,
                "temporary_cleanup_unsafe_file")
        if os.name == "nt" and (getattr(st, "st_file_attributes", 0) & 1):
            os.chmod(extended(p), stat.S_IREAD | stat.S_IWRITE)
        os.unlink(extended(p))
    for p in reversed(directories):
        directory_chain(p)
        os.rmdir(extended(p))
    require(not os.path.lexists(extended(root)), "temporary_cleanup_incomplete")


class GuestPreflightGit:
    def __init__(self, repository: Path, executable: Path, root: Path):
        self.repository, self.executable, self.root = repository, executable, root
        self.gitdir = repository / ".git"
        self.command_count = 0
        self.checked_config = False
        self.last_returncode: int | None = None
        for name in ("io", "objects", "home", "hooks"):
            (root / name).mkdir()
        env = {k: os.environ[k] for k in ("SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT") if k in os.environ}
        system = Path(env.get("SYSTEMROOT", r"C:\Windows"))
        path = [str(executable.parent)] + ([str(system / "System32"), str(system)] if os.name == "nt" else ["/usr/bin", "/bin"])
        env.update({
            "PATH": os.pathsep.join(path), "HOME": str(root / "home"), "USERPROFILE": str(root / "home"),
            "APPDATA": str(root / "home"), "LOCALAPPDATA": str(root / "home"),
            "TMPDIR": str(root), "TEMP": str(root), "TMP": str(root),
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_SYSTEM": os.devnull, "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_ATTR_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0",
            "GIT_NO_LAZY_FETCH": "1", "GCM_INTERACTIVE": "never", "GIT_ALLOW_PROTOCOL": "",
            "LANG": "C", "LC_ALL": "C",
        })
        self.environment = env

    def run(self, args: list[str], *, data: bytes = b"", temporary: bool = False,
            ok: tuple[int, ...] = (0,)) -> bytes:
        require(type(args) is list and args and all(type(a) is str and "\0" not in a for a in args), "git_arguments_invalid")
        allowed = {"version", "config", "rev-parse", "symbolic-ref", "ls-tree", "ls-files", "check-attr", "cat-file"}
        temp_only = {"read-tree", "apply", "diff", "write-tree", "update-index"}
        require(args[0] in allowed or temporary and args[0] in temp_only, "git_command_forbidden")
        if args[0] == "config":
            require(args == ["config", "--no-includes", "--local", "--null", "--list"], "git_config_write_forbidden")
        elif args[0] != "version":
            require(self.checked_config, "git_configuration_not_checked")
        if args[0] == "symbolic-ref":
            require(args == ["symbolic-ref", "--quiet", "HEAD"], "git_ref_write_forbidden")
        if args[0] == "cat-file":
            require(args[1] in ("blob", "commit", "--batch", "--batch-check"), "git_cat_file_mode_forbidden")
        if args[0] == "diff":
            require("--no-ext-diff" in args and "--no-textconv" in args, "git_diff_execution_forbidden")
        if args[0] == "apply":
            require(temporary and "--cached" in args and args[-1] == "-", "live_patch_apply_forbidden")
        if args[0] == "update-index":
            require(temporary and args == ["update-index", "--refresh"], "live_index_write_forbidden")
        if args[0] == "read-tree":
            require(temporary and "-i" in args, "live_index_write_forbidden")
        env = dict(self.environment)
        if temporary:
            env.update({"GIT_INDEX_FILE": str(self.root / "index"), "GIT_OBJECT_DIRECTORY": str(self.root / "objects"),
                        "GIT_ALTERNATE_OBJECT_DIRECTORIES": json.dumps(str(self.gitdir / "objects"), ensure_ascii=False)})
        cmd = [str(self.executable), "--no-pager", "--no-optional-locks", "--no-replace-objects", "--literal-pathspecs",
               "-c", "core.fsmonitor=false", "-c", "diff.autoRefreshIndex=" + ("true" if temporary and args[0] == "diff" else "false"),
               "-c", "core.untrackedCache=false",
               "-c", "core.hooksPath=" + str(self.root / "hooks"), "-c", "core.attributesFile=" + os.devnull,
               "-c", "gc.auto=0", "-c", "maintenance.auto=false", "-c", "submodule.recurse=false",
               "-c", "apply.ignoreWhitespace=no", "--git-dir=" + str(self.gitdir), "--work-tree=" + str(self.repository), *args]
        self.command_count += 1
        tag = str(self.command_count)
        paths = [self.root / "io" / (tag + ext) for ext in (".in", ".out", ".err")]
        paths[0].write_bytes(data)
        cp = None
        with paths[0].open("rb") as inp, paths[1].open("xb") as out, paths[2].open("xb") as err:
            try:
                cp = subprocess.Popen(cmd, cwd=self.repository, env=env, stdin=inp, stdout=out, stderr=err, shell=False)
                deadline = time.monotonic() + GIT_TIMEOUT_SECONDS
                while cp.poll() is None:
                    require(time.monotonic() <= deadline, "git_command_timeout")
                    require(os.fstat(out.fileno()).st_size <= MAX_GIT_OUTPUT
                            and os.fstat(err.fileno()).st_size <= MAX_GIT_STDERR, "git_output_limit")
                    time.sleep(0.01)
                require(os.fstat(out.fileno()).st_size <= MAX_GIT_OUTPUT
                        and os.fstat(err.fileno()).st_size <= MAX_GIT_STDERR, "git_output_limit")
                self.last_returncode = cp.returncode
                require(cp.returncode in ok, "git_" + args[0].replace("-", "_") + "_failed")
            finally:
                if cp is not None and cp.poll() is None:
                    cp.kill()
                    cp.wait(timeout=5)
        return read_regular(paths[1], maximum=MAX_GIT_OUTPUT)

    def config(self) -> str:
        self.checked_config = False
        raw = self.run(["config", "--no-includes", "--local", "--null", "--list"])
        for item in raw.split(b"\0"):
            if not item:
                continue
            key, _, value = item.partition(b"\n")
            key = key.decode("utf-8").lower()
            value = value.decode("utf-8").lower()
            require(not key.startswith(("include.", "includeif.", "extensions.", "filter.", "hook.")), "unsafe_git_config")
            require(key not in ("core.worktree", "core.fsmonitor", "core.attributesfile", "diff.external", "core.sshcommand"), "unsafe_git_config")
            require(not (key.startswith("diff.") and key.endswith((".command", ".textconv"))), "unsafe_git_config")
            require(not (key.startswith("remote.") and key.endswith((".promisor", ".vcs"))), "unsafe_git_config")
            if key in ("core.bare", "core.sparsecheckout", "core.splitindex", "core.ignorestat", "core.skipworktree"):
                require(value in ("false", "no", "off", "0"), "unsupported_git_config")
        self.checked_config = True
        return sha(raw)

    def snapshot(self, base_commit: str, base_tree: str) -> dict:
        # All type/path checks precede Git operations which might inspect worktree bytes.
        md = metadata_snapshot(self.gitdir)
        cfg = self.config()
        require(self.run(["rev-parse", "--show-object-format"]).strip() == b"sha1", "repository_object_format")
        for args, expected in ((["rev-parse", "--absolute-git-dir"], self.gitdir),
                               (["rev-parse", "--show-toplevel"], self.repository)):
            actual = self.run(args).decode("utf-8").strip()
            require(os.path.normcase(os.path.abspath(actual)) == os.path.normcase(str(expected)), "repository_redirection")
        require(self.run(["rev-parse", "HEAD^{commit}"]).strip().decode() == base_commit, "repository_head_mismatch")
        commit = self.run(["cat-file", "commit", base_commit])
        require(object_oid("commit", commit) == base_commit, "base_commit_oid_mismatch")
        header = commit.split(b"\n\n", 1)[0]
        require([x for x in header.splitlines() if x.startswith(b"tree ")] == [("tree " + base_tree).encode()], "repository_base_tree_mismatch")
        rows = parse_tree(self.run(["ls-tree", "-r", "-z", "--full-tree", base_commit]))
        idx = parse_index(self.run(["ls-files", "--stage", "-z"]))
        require(idx == rows and tree_oid(rows) == base_tree, "repository_index_mismatch")
        flags = self.run(["ls-files", "-v", "-z"]).split(b"\0")[:-1]
        require(flags == [b"H " + x["path"].encode() for x in idx], "repository_index_flags")
        physical = {}
        total = 0
        known = {x["path"] for x in rows}
        for row in rows:
            data = read_regular(self.repository / row["path"])
            total += len(data)
            require(total <= MAX_TRACKED_TOTAL, "repository_bytes_limit")
            physical[row["path"]] = {"bytes": len(data), "sha256": sha(data)}
        # Refuse untracked or indirect per-directory attribute sources before check-attr/status.
        attribute_paths = {".gitattributes"}
        for path in known:
            parts = path.split("/")
            attribute_paths.update("/".join(parts[:i]) + "/.gitattributes" for i in range(1, len(parts)))
        for rel in sorted(attribute_paths):
            p = self.repository / rel
            if os.path.lexists(extended(p)):
                require(rel in known, "untracked_attribute_file")
                read_regular(p)
        attr_names = ("filter", "working-tree-encoding", "ident", "text", "eol")
        attrs = self.run(["check-attr", "-z", "--stdin", *attr_names],
                         data=b"\0".join(x["path"].encode() for x in rows) + b"\0")
        cells = attrs.split(b"\0")
        require(cells.pop() == b"" and len(cells) == 15 * len(rows), "git_attributes_output")
        seen = set()
        for i in range(0, len(cells), 3):
            path, key, value = (x.decode("utf-8") for x in cells[i:i+3])
            require(path in known and key in attr_names and (path, key) not in seen, "git_attributes_output")
            seen.add((path, key))
            if key in ("filter", "working-tree-encoding", "ident"):
                require(value in ("unspecified", "unset"), "external_or_transforming_attribute")
        # Refresh stat data only on a private copy. LF->CRLF checkout with a stale
        # index stat cache can otherwise produce a phantom porcelain modification.
        # Semantic entries/flags above still came from the untouched live index.
        live_index = read_regular(self.gitdir / "index")
        (self.root / "index").write_bytes(live_index)
        self.run(["update-index", "--refresh"], temporary=True, ok=(0, 1))
        diff = self.run(["diff", "--no-ext-diff", "--no-textconv", "--exit-code", "--"],
                        temporary=True, ok=(0, 1))
        require(self.last_returncode == 0 and diff == b"", "repository_not_clean")
        # Porcelain can keep reporting a size-only CRLF stat-cache difference even
        # when Git's full diff proves equality. Check untracked paths separately;
        # never discard a real diff or alter the live index to make status green.
        require(self.run(["ls-files", "--others", "--exclude-standard", "-z"], temporary=True) == b"",
                "repository_not_clean")
        require(parse_index(self.run(["ls-files", "--stage", "-z"], temporary=True)) == rows,
                "snapshot_refresh_changed_entries")
        require(read_regular(self.gitdir / "index") == live_index, "live_index_changed_during_snapshot")
        require(metadata_snapshot(self.gitdir) == md, "repository_metadata_changed_during_snapshot")
        return {"head": base_commit, "tree": base_tree, "entries": rows, "physical": physical,
                "metadata": md, "config_sha256": cfg, "attributes_sha256": sha(attrs)}

    def blobs(self, oids: list[str], *, temporary: bool = False) -> dict[str, bytes]:
        oids = sorted(set(oids))
        require(oids and all(_GIT_OID.fullmatch(x) for x in oids), "blob_oid_invalid")
        query = ("\n".join(oids) + "\n").encode("ascii")
        checks = self.run(["cat-file", "--batch-check"], data=query, temporary=temporary).splitlines()
        require(len(checks) == len(oids), "blob_metadata_invalid")
        sizes = []
        for oid, row in zip(oids, checks):
            parts = row.decode("ascii").split(" ")
            require(len(parts) == 3 and parts[:2] == [oid, "blob"] and parts[2].isdigit(), "blob_missing_or_wrong_type")
            size = int(parts[2])
            require(size <= MAX_FILE_BYTES, "blob_size_limit")
            sizes.append(size)
        require(sum(sizes) + 100 * len(sizes) <= MAX_GIT_OUTPUT, "blob_total_limit")
        raw = self.run(["cat-file", "--batch"], data=query, temporary=temporary)
        out = {}
        pos = 0
        for oid, size in zip(oids, sizes):
            header = (oid + " blob " + str(size) + "\n").encode("ascii")
            require(raw[pos:pos+len(header)] == header, "blob_header_invalid")
            pos += len(header)
            data = raw[pos:pos+size]
            pos += size
            require(raw[pos:pos+1] == b"\n" and object_oid("blob", data) == oid, "blob_oid_mismatch")
            pos += 1
            out[oid] = data
        require(pos == len(raw), "blob_output_trailer")
        return out

    def apply_patch(self, base_commit: str, patch: bytes) -> None:
        self.run(["read-tree", "--reset", "-i", "--no-sparse-checkout", base_commit], temporary=True)
        self.run(["apply", "--cached", "--check", "--whitespace=error-all", "-"], data=patch, temporary=True)
        self.run(["apply", "--cached", "--whitespace=error-all", "-"], data=patch, temporary=True)

    def candidate(self, base_commit: str, rows: list[dict], target: str, preimage: str) -> dict:
        raw = self.run(["diff", "--cached", "--raw", "-z", "--no-renames", "--no-abbrev", "--no-ext-diff",
                        "--no-textconv", "--ignore-submodules=none", base_commit, "--"], temporary=True)
        cells = raw.split(b"\0")
        require(len(cells) == 3 and cells[-1] == b"" and cells[1] == target.encode(), "patch_scope_mismatch")
        header = cells[0].decode("ascii").split(" ")
        require(len(header) == 5 and header[:3] == [":100644", "100644", preimage]
                and _GIT_OID.fullmatch(header[3]) is not None and header[4] == "M", "patch_must_modify_one_regular_file")
        oid = header[3]
        require(oid != preimage, "patch_no_effect")
        result = parse_index(self.run(["ls-files", "--stage", "-z"], temporary=True))
        expected = [({**x, "oid": oid} if x["path"] == target else x) for x in rows]
        require(result == expected, "candidate_index_scope_mismatch")
        self.run(["diff", "--cached", "--no-ext-diff", "--no-textconv", "--check", base_commit, "--"], temporary=True)
        tree = self.run(["write-tree"], temporary=True).strip().decode("ascii")
        require(_GIT_OID.fullmatch(tree) is not None and tree_oid(result) == tree, "candidate_tree_reconstruction_mismatch")
        content = self.blobs([oid], temporary=True)[oid]
        require(len(content) <= 192 * 1024 and b"\0" not in content, "candidate_target_size_or_binary")
        try:
            content.decode("utf-8", "strict")
        except UnicodeError as exc:
            raise DeveloperTaskGuestPreflightError("candidate_target_not_utf8") from exc
        return {"candidate_tree": tree, "candidate_blob_oid": oid, "candidate_content_sha256": sha(content),
                "candidate_content_bytes": len(content)}
