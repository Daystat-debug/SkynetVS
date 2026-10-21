"""Open the version-pinned in-project Developer Task UI.

No Downloads runtime dependency, no user-supplied paths or shell arguments.
M101 permits only one hash-pinned user-confirmed audio fix; no generic apply, privileged action or promotion.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
import threading
import uuid
from pathlib import Path

_BUNDLE_MANIFEST_SHA256 = "30fcd0d85e9ac4cde7238290a809154964e51f3b5bf6ff50ab457d9015aea05b"
_BUNDLE_DIRECTORY = "developer_task_ui"


class DeveloperTaskUiLaunchError(RuntimeError):
    pass


def _plain(path: Path, *, directory: bool = False) -> os.stat_result:
    try:
        st = path.lstat()
    except OSError as exc:
        raise DeveloperTaskUiLaunchError("M092_MISSING:" + path.name) from exc
    if stat.S_ISLNK(st.st_mode) or getattr(st, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
        raise DeveloperTaskUiLaunchError("M092_LINK_OR_REPARSE:" + path.name)
    if directory:
        if not stat.S_ISDIR(st.st_mode):
            raise DeveloperTaskUiLaunchError("M092_NOT_DIRECTORY:" + path.name)
    elif not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
        raise DeveloperTaskUiLaunchError("M092_NOT_PLAIN_FILE:" + path.name)
    return st


def _data_variants(path: Path) -> list[bytes]:
    raw = path.read_bytes()
    variants = [raw]
    # Git may check out LF or CRLF; accept ONLY byte-identical content
    # except for that newline convention. Some M092 vendor files use CRLF.
    if path.suffix.lower() in {".py", ".json"}:
        lf = raw.replace(b"\r\n", b"\n")
        crlf = lf.replace(b"\n", b"\r\n")
        for option in (lf, crlf):
            if option not in variants:
                variants.append(option)
    return variants


def _matches_bytes(path: Path, size: int, sha256: str) -> bool:
    return any(len(b) == size and hashlib.sha256(b).hexdigest() == sha256
               for b in _data_variants(path))


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_bundle(root: Path) -> None:
    _plain(root, directory=True)
    manifest_path = root / "BUNDLE_MANIFEST.json"
    _plain(manifest_path)
    if not any(hashlib.sha256(data).hexdigest() == _BUNDLE_MANIFEST_SHA256
               for data in _data_variants(manifest_path)):
        raise DeveloperTaskUiLaunchError("M092_BUNDLE_MANIFEST_CHANGED")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "SKYNETVS_M092_UI_BUNDLE_V1":
        raise DeveloperTaskUiLaunchError("M092_BUNDLE_SCHEMA")
    records = manifest.get("files")
    if not isinstance(records, dict):
        raise DeveloperTaskUiLaunchError("M092_BUNDLE_RECORDS")
    found = set()
    for p in root.rglob("*"):
        if p.is_dir():
            _plain(p, directory=True)
        else:
            _plain(p)
            found.add(p.relative_to(root).as_posix())
    if found != set(records) | {"BUNDLE_MANIFEST.json"}:
        raise DeveloperTaskUiLaunchError("M092_BUNDLE_ENTRY_SET_CHANGED")
    for name, record in records.items():
        # Already covered by entry-set verification. Never follow a filename from voice/NLU.
        if (not isinstance(name, str) or name.startswith("/") or ".." in name.split("/")
                or "\\" in name or not isinstance(record, dict)):
            raise DeveloperTaskUiLaunchError("M092_MANIFEST_PATH_INVALID")
        file = root / name
        st = _plain(file)
        if not _matches_bytes(file, record.get("bytes"), record.get("sha256")):
            raise DeveloperTaskUiLaunchError("M092_BUNDLE_FILE_CHANGED:" + name)


def _get_runs_root() -> Path:
    local = os.environ.get("LOCALAPPDATA", "")
    if not local or not Path(local).is_absolute():
        raise DeveloperTaskUiLaunchError("LOCALAPPDATA_REQUIRED")
    base = Path(local)
    _plain(base, directory=True)
    # Persistent per-user data, intentionally outside the Git repository and Downloads.
    one, two, three = base / "SkynetVS", base / "SkynetVS" / "DeveloperTask", base / "SkynetVS" / "DeveloperTask" / "Runs"
    for path in (one, two, three):
        path.mkdir(exist_ok=True)
        _plain(path, directory=True)
    return three


def _is_windows() -> bool:
    return os.name == "nt"


class DeveloperTaskUiLauncher:
    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._process: subprocess.Popen | None = None

    def open(self) -> str:
        with self._guard:
            if self._process is not None and self._process.poll() is None:
                return "ALREADY_RUNNING"
            if not _is_windows():
                raise DeveloperTaskUiLaunchError("WINDOWS_ONLY")
            root = Path(__file__).absolute().parent / _BUNDLE_DIRECTORY
            _verify_bundle(root)
            python = Path(sys.executable)
            if not python.is_absolute():
                raise DeveloperTaskUiLaunchError("PYTHON_NOT_ABSOLUTE")
            _plain(python)
            runs = _get_runs_root()
            run = runs / ("dtr_ui_" + uuid.uuid4().hex)
            run.mkdir(mode=0o700)
            _plain(run, directory=True)
            output = run / "m092_voice_launch.log"
            command = [str(python), "-I", "-S", "-B", str(root / "launch.py"), "--run", str(run)]
            try:
                with output.open("xb") as log:
                    self._process = subprocess.Popen(
                        command, cwd=str(run), shell=False, stdin=subprocess.DEVNULL,
                        stdout=log, stderr=subprocess.STDOUT,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
            except OSError as exc:
                raise DeveloperTaskUiLaunchError("M092_SPAWN_FAILED:" + type(exc).__name__) from exc
            return "STARTED"
