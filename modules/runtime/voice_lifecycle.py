"""Local, unprivileged voice lifecycle for this SkynetVS process only.

No OS shutdown, no arbitrary command/path from STT. Restart starts the project
main.py using the current interpreter *after the current process exits*.
"""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys
from pathlib import Path


EXIT = "exit"
RESTART = "restart"
_ALLOWED = frozenset({EXIT, RESTART})


class VoiceLifecycle:
    def __init__(self) -> None:
        self._requested: str | None = None

    @property
    def requested(self) -> str | None:
        return self._requested

    def request(self, action: str) -> None:
        if action not in _ALLOWED or type(action) is not str:
            raise ValueError("LIFECYCLE_ACTION_INVALID")
        if self._requested is not None:
            raise RuntimeError("LIFECYCLE_REQUEST_ALREADY_PENDING")
        self._requested = action


def _project_paths() -> tuple[Path, Path]:
    root = Path(__file__).resolve().parents[2]
    main = root / "main.py"
    if not main.is_file() or main.is_symlink():
        raise RuntimeError("LIFECYCLE_MAIN_NOT_FOUND_OR_LINK")
    return root, main


def schedule_restart_after_exit(*, parent_pid: int) -> None:
    """Run a short-lived helper, never start the second assistant now."""
    if os.name != "nt":
        raise RuntimeError("LIFECYCLE_RESTART_WINDOWS_ONLY")
    if type(parent_pid) is not int or parent_pid != os.getpid():
        raise ValueError("LIFECYCLE_PARENT_PID_MISMATCH")
    root, _ = _project_paths()
    helper = Path(__file__).resolve()
    interpreter = Path(sys.executable).resolve()
    if not interpreter.is_file():
        raise RuntimeError("LIFECYCLE_PYTHON_MISSING")
    # Child helper is stdlib-only; project code is not imported in isolated mode.
    subprocess.Popen(
        [str(interpreter), "-I", "-S", "-B", str(helper), "--wait-and-restart", str(parent_pid)],
        cwd=str(root),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )


def _wait_parent_exit(parent_pid: int) -> bool:
    """Wait on kernel process handle: PID checks alone are insufficient."""
    if os.name != "nt" or type(parent_pid) is not int or parent_pid <= 0:
        return False
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    kernel.WaitForSingleObject.restype = ctypes.c_ulong
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel.CloseHandle.restype = ctypes.c_int
    handle = kernel.OpenProcess(0x00100000, 0, parent_pid)
    if not handle:
        # OpenProcess fails with ERROR_INVALID_PARAMETER for an already exited PID.
        return ctypes.get_last_error() == 87
    try:
        return kernel.WaitForSingleObject(handle, 30000) == 0
    finally:
        kernel.CloseHandle(handle)


def _restart_helper(args: list[str]) -> int:
    if os.name != "nt" or len(args) != 2 or args[0] != "--wait-and-restart":
        return 4
    try:
        parent_pid = int(args[1])
        if parent_pid <= 0 or not _wait_parent_exit(parent_pid):
            return 5
        root, main_path = _project_paths()
        interpreter = Path(sys.executable).resolve()
        if not interpreter.is_file():
            return 6
        # A visible console makes restart failures observable to the user.
        subprocess.Popen(
            [str(interpreter), "-B", str(main_path)],
            cwd=str(root),
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            close_fds=True,
        )
        return 0
    except Exception:
        return 7


def _helper_failure_log(exit_code: int) -> None:
    """Best-effort local diagnostic if detached restart cannot happen."""
    if exit_code == 0:
        return
    try:
        base = os.environ.get("LOCALAPPDATA")
        if not base:
            return
        log_dir = Path(base) / "SkynetVS" / "Lifecycle"
        log_dir.mkdir(parents=True, exist_ok=True)
        from datetime import datetime, timezone
        with (log_dir / "restart_failures.log").open("a", encoding="utf-8") as f:
            f.write(datetime.now(timezone.utc).isoformat() + " restart_helper_exit=" + str(exit_code) + "\n")
    except Exception:
        pass


if __name__ == "__main__":
    result = _restart_helper(sys.argv[1:])
    _helper_failure_log(result)
    sys.exit(result)
