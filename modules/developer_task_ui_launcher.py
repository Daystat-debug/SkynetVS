"""Open the version-pinned in-project Developer Task UI.

No Downloads runtime dependency, no user-supplied paths or shell arguments.
The UI has no authority to apply patches, run modified code or promote a release.
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

_BUNDLE_MANIFEST_SHA256 = "af82a04c66b9a7d2307aa119154ea132c75829ae3cadb12c6756b3ab5d5f92a1"
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


def _sha256_file(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(65536), b""):
            result.update(chunk)
    return result.hexdigest()


def _verify_bundle(root: Path) -> None:
    _plain(root, directory=True)
    manifest_path = root / "BUNDLE_MANIFEST.json"
    _plain(manifest_path)
    if _sha256_file(manifest_path) != _BUNDLE_MANIFEST_SHA256:
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
        if st.st_size != record.get("bytes") or _sha256_file(file) != record.get("sha256"):
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
