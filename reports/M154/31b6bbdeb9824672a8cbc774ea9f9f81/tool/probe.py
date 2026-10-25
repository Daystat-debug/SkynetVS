"""Read-only M154 workspace metadata; no runtime contents captured or Git writes."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from urllib.parse import urlsplit

BASE = "3cd5a06b3b17ce2e6b9b25351a1b455289974dfb"
PROBES = (
    ".gitignore", ".env", ".idea/misc.xml", ".idea/SkynetVS.iml",
    "__pycache__/main.cpython-312.pyc", ".venv/pyvenv.cfg", "venv/pyvenv.cfg",
    "models/nlu_intent.joblib", "data/inbox_labeled.jsonl", "data/inbox_unlabeled.jsonl",
    "data/learning/alias_suggestions.jsonl", "data/learning/command_history.jsonl",
)
KNOWN_ROOTS = {".gitignore", ".gitattributes", ".env.example", "modules", "tools", "data", "native", "reports", "tests", "train", "main.py", "README.md"}


class ProbeError(RuntimeError):
    def __init__(self, operation: str, code: int | None, reason: str = "GIT_QUERY_FAILED"):
        super().__init__(f"{reason}: {operation}; exit={code}")
        self.operation, self.returncode, self.reason = operation, code, reason


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(repo: Path, *args: str, input: bytes | None = None, allowed=(0,)):
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env.update(GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="Never", GIT_NO_LAZY_FETCH="1", GIT_OPTIONAL_LOCKS="0")
    command = ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=" + os.devnull,
               "-c", "protocol.allow=never", "-c", "core.untrackedCache=false", "-C", str(repo), *args]
    try:
        result = subprocess.run(command, input=input, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=env, timeout=40, shell=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProbeError(args[0], None, type(exc).__name__) from exc
    if result.returncode not in allowed:
        reason = "DUBIOUS_OWNERSHIP" if b"dubious ownership" in result.stderr else "GIT_QUERY_FAILED"
        raise ProbeError(args[0], result.returncode, reason)
    return result


def _text(data: bytes) -> str:
    return data.decode("utf-8", "replace").strip()


def _display(path: Path) -> str:
    value, home = str(path), str(Path.home())
    return "<HOME>" + value[len(home):] if (os.path.normcase(value) == os.path.normcase(home)
            or os.path.normcase(value).startswith(os.path.normcase(home + os.sep))) else value


def _is_project(url: str) -> bool:
    if re.fullmatch(r"(?:git@)?github\.com:Daystat-debug/SkynetVS(?:\.git)?/?", url, re.I):
        return True
    try:
        parsed = urlsplit(url)
        return (parsed.scheme.lower() in {"https", "http", "ssh", "git"}
                and (parsed.hostname or "").lower() == "github.com"
                and parsed.path.rstrip("/").lower().removesuffix(".git") == "/daystat-debug/skynetvs")
    except ValueError:
        return False


def _metadata(path: Path, *, inspect_ignore: bool = False) -> dict:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return {"kind": "missing"}
    if not stat.S_ISREG(info.st_mode):
        return {"kind": "symlink" if stat.S_ISLNK(info.st_mode) else "other", "content_read": False}
    result = {"kind": "file", "size_bytes": info.st_size}
    if info.st_size > 16 * 1024 * 1024:
        return {**result, "content_read": False, "reason": "METADATA_FILE_EXCEEDS_16_MIB"}
    data = path.read_bytes()
    result["sha256"] = sha(data)
    if inspect_ignore:
        bom = "UTF8_BOM" if data.startswith(b"\xef\xbb\xbf") else "UTF16_LE_BOM" if data.startswith(b"\xff\xfe") else "UTF16_BE_BOM" if data.startswith(b"\xfe\xff") else "NONE"
        result.update(bom=bom, nul_byte_count=data.count(b"\x00"), line_count=len(data.splitlines()), raw_content_published=False)
    return result


def _blob(repo: Path, spec: str) -> dict:
    result = _git(repo, "rev-parse", "--verify", spec, allowed=(0, 128))
    if result.returncode:
        return {"present": False}
    oid = _text(result.stdout)
    size = int(_git(repo, "cat-file", "-s", oid).stdout)
    if size > 1024 * 1024:
        return {"present": True, "oid": oid, "size_bytes": size, "sha256": None, "reason": "IGNORE_BLOB_EXCEEDS_1_MIB"}
    data = _git(repo, "cat-file", "blob", oid).stdout
    return {"present": True, "oid": oid, "size_bytes": len(data), "sha256": sha(data)}


def _category(path: str) -> str:
    path = path.replace("\\", "/")
    if path == ".env" or path.startswith(".env."):
        return "environment_files"
    if path.startswith((".venv/", "venv/", "env/")):
        return "virtual_environments"
    if path.startswith((".idea/", ".vscode/")):
        return "ide_settings"
    if "__pycache__" in path.split("/") or path.endswith((".pyc", ".pyo")):
        return "python_cache"
    if path.startswith("models/"):
        return "models"
    if path.startswith("data/learning/") or path in {"data/inbox_labeled.jsonl", "data/inbox_unlabeled.jsonl"}:
        return "runtime_learning"
    if path.startswith("data/logs/") or path.endswith(".log"):
        return "logs"
    if path.startswith("reports/"):
        return "reports"
    if path == ".gitignore":
        return "root_gitignore"
    return "other"


def _status(repo: Path) -> tuple[bytes, list[tuple[str, str]]]:
    raw = _git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignore-submodules=all").stdout
    fields, entries, index = raw.split(b"\x00"), [], 0
    while index < len(fields) and fields[index]:
        field = fields[index]
        xy, path = field[:2].decode("ascii"), field[3:].decode("utf-8", "replace")
        entries.append((xy, path))
        index += 2 if "R" in xy or "C" in xy else 1
    return raw, entries


def _snapshot(repo: Path, gitdir: Path, common: Path) -> tuple[dict, list]:
    raw, entries = _status(repo)
    head = _git(repo, "rev-parse", "--verify", "HEAD", allowed=(0, 128))
    symbolic = _git(repo, "symbolic-ref", "--quiet", "HEAD", allowed=(0, 1))
    refs = _git(repo, "for-each-ref", "--format=%(refname) %(objectname)").stdout
    return {"head": _text(head.stdout) if head.returncode == 0 else None,
            "symbolic_head": _text(symbolic.stdout) if symbolic.returncode == 0 else None, "status_sha256": sha(raw),
            "refs_sha256": sha(refs), "index": _metadata(gitdir / "index"), "config": _metadata(common / "config")}, entries


def _ignore_source(source: str, repo: Path, gitdir: Path) -> str:
    if not source:
        return ""
    path = Path(source)
    if not path.is_absolute():
        # Only the fixed tested paths can contribute a project ignore file.
        return source[:256] if source in {".gitignore", ".idea/.gitignore", ".venv/.gitignore", "venv/.gitignore", "models/.gitignore", "data/.gitignore", "data/learning/.gitignore", "__pycache__/.gitignore"} else "<PROJECT_IGNORE_FILE>"
    try:
        relative = path.relative_to(repo).as_posix()
        return "<REPO>/" + relative if relative == ".gitignore" else "<PROJECT_IGNORE_FILE>"
    except ValueError:
        return "<GIT_DIR>/info/exclude" if path == gitdir / "info" / "exclude" else "<EXTERNAL_IGNORE_FILE>"


def resolve_root(repo: Path | str) -> Path:
    """Resolve an explicit selected directory to its Git root without writes."""
    selected = Path(repo).resolve()
    return Path(_text(_git(selected, "rev-parse", "--show-toplevel").stdout)).resolve()


def collect(repo: Path | str, *, expected_base: str = BASE) -> dict:
    """Return public metadata only. No checkout, fetch, staging, or file writes."""
    selected = Path(repo).resolve()
    root = resolve_root(selected)
    origin = _git(root, "remote", "get-url", "origin", allowed=(0, 2, 128))
    identity = origin.returncode == 0 and _is_project(_text(origin.stdout))
    result = {"schema": "SKYNETVS_M154_WORKSPACE_PROBE_V1", "selected_path": _display(selected), "repository_root": _display(root),
              "repository_root_path_sha256": sha(os.path.normcase(str(root)).encode()), "project_verified": identity,
              "project_identity_basis": "expected GitHub origin URL; credentials and URL are not published"}
    if not identity:
        return {**result, "status": "UNVERIFIED_PROJECT", "details_collected": False}
    if not re.fullmatch(r"[0-9a-f]{40}", expected_base):
        raise ValueError("Expected base must be a full lowercase commit SHA")
    gitdir = Path(_text(_git(root, "rev-parse", "--absolute-git-dir").stdout)).resolve()
    common_value = Path(_text(_git(root, "rev-parse", "--git-common-dir").stdout))
    common = (common_value if common_value.is_absolute() else root / common_value).resolve()
    before, entries = _snapshot(root, gitdir, common)
    branch = _git(root, "symbolic-ref", "--quiet", "--short", "HEAD", allowed=(0, 1))
    refs = {}
    for name in ("main", "sandbox/m154", "reports/m154"):
        found = _git(root, "show-ref", "--verify", "--hash", "refs/heads/" + name, allowed=(0, 1, 128))
        refs[name] = _text(found.stdout) if found.returncode == 0 else None
    base_available = _git(root, "cat-file", "-e", expected_base + "^{commit}", allowed=(0, 1, 128)).returncode == 0
    root_names = []
    if before["head"]:
        root_names = [part.decode("utf-8", "replace") for part in _git(root, "ls-tree", "-z", "--name-only", "HEAD").stdout.split(b"\x00") if part]
    tracked_raw = _git(root, "ls-files", "--cached", "-z").stdout
    tracked = {part.decode("utf-8", "replace") for part in tracked_raw.split(b"\x00") if part}
    ignored_raw = _git(root, "ls-files", "--cached", "--ignored", "--exclude-standard", "-z").stdout
    tracked_ignored = {part.decode("utf-8", "replace") for part in ignored_raw.split(b"\x00") if part}
    check = _git(root, "check-ignore", "--no-index", "--verbose", "--non-matching", "-z", "--stdin",
                 input=b"\x00".join(p.encode() for p in PROBES) + b"\x00", allowed=(0, 1))
    fields = check.stdout.split(b"\x00")
    if fields[-1] == b"":
        fields.pop()
    if len(fields) != 4 * len(PROBES):
        raise ProbeError("check-ignore", check.returncode, "UNEXPECTED_IGNORE_RECORDS")
    ignore_checks = []
    for index in range(0, len(fields), 4):
        source, line, pattern, path = (p.decode("utf-8", "replace") for p in fields[index:index + 4])
        if path not in PROBES:
            raise ProbeError("check-ignore", check.returncode, "UNEXPECTED_PROBE_PATH")
        try:
            exists = (root / path).lstat()
            kind = "symlink" if stat.S_ISLNK(exists.st_mode) else "file" if stat.S_ISREG(exists.st_mode) else "other"
        except FileNotFoundError:
            kind = "missing"
        ignore_checks.append({"path": path, "kind": kind, "tracked_in_index": path in tracked,
                              "matched": bool(source), "ignored_by_rules": bool(source) and not pattern.startswith("!"),
                              "rule_source": _ignore_source(source, root, gitdir), "rule_line": int(line) if line else None,
                              "pattern": pattern[:256], "pattern_truncated": len(pattern) > 256})
    root_ignore = _metadata(root / ".gitignore", inspect_ignore=True)
    head_ignore = _blob(root, "HEAD:.gitignore") if before["head"] else {"present": False}
    index_ignore = _blob(root, ":.gitignore")
    base_ignore = _blob(root, expected_base + ":.gitignore") if base_available else {"present": False}
    after, _ = _snapshot(root, gitdir, common)
    layout = "REPORTS_ONLY_TREE" if root_names == ["reports"] else "SOURCE_TREE" if {"modules", "tools"}.issubset(root_names) else "OTHER_OR_MIXED_TREE"
    return {**result, "status": "COLLECTED", "git_directory": _display(gitdir), "branch": _text(branch.stdout) if branch.returncode == 0 else None,
            "detached_head": branch.returncode == 1, "head": before["head"], "local_branch_refs": refs,
            "expected_base": expected_base, "expected_base_object_available": base_available,
            "head_layout": {"classification": layout, "root_entry_count": len(root_names),
                            "known_root_entries": sorted(set(root_names) & KNOWN_ROOTS), "other_root_entry_count": len(set(root_names) - KNOWN_ROOTS)},
            "root_gitignore": {"worktree": root_ignore, "index": index_ignore, "head": head_ignore, "expected_base": base_ignore,
                               "worktree_matches_head": root_ignore.get("sha256") == head_ignore.get("sha256") if root_ignore.get("sha256") and head_ignore.get("sha256") else None},
            "status_counts": dict(sorted(Counter(xy for xy, _ in entries).items())), "changed_path_count": len(entries),
            "changed_path_categories": dict(sorted(Counter(_category(p) for _, p in entries).items())),
            "tracked_ignored_count": len(tracked_ignored), "tracked_ignored_categories": dict(sorted(Counter(_category(p) for p in tracked_ignored).items())),
            "ignore_probes": ignore_checks, "inherited_git_environment_names": sorted(k for k in os.environ if k.upper().startswith("GIT_")),
            "git_snapshot_before": before, "git_snapshot_after": after, "source_git_state_unchanged": before == after,
            "snapshot_scope": "HEAD, symbolic HEAD, refs, index, repository config, porcelain. Git may inspect tracked files for status; no runtime contents are captured or published. No complete filesystem byte audit.",
            "raw_status_names_published": False, "runtime_files_opened_directly_by_probe": False,
            "runtime_contents_captured_or_published": False, "repairs_attempted": False}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", type=Path)
    args = parser.parse_args()
    print(json.dumps(collect(args.repo), ensure_ascii=False, indent=2, sort_keys=True))
