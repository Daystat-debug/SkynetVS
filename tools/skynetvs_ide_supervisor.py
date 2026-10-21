"""PyCharm Run parent for SkynetVS voice restart (M104).

Choose this file as PyCharm Script path once. The parent retains the IDE Run
session; each child runs the normal project main.py in the project venv.
A confirmed voice restart exits the child with a reserved status (75) after
M103 shutdown. Exit and errors terminate this parent; no service or Git writes.
"""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
from pathlib import Path


RESTART_CODE = 75
SUPERVISOR_ENV = "SKYNETVS_IDE_SUPERVISOR"
RESTART_LIMIT = 4
RESTART_WINDOW_SECONDS = 60.0


def _make_windows_kill_job(process: subprocess.Popen) -> int | None:
    """Attach child to a kill-on-close Windows Job Object (no admin needed).

    PyCharm's Stop button terminates this parent; the Windows kernel then
    closes our Job handle and terminates the still-running main child.
    Child-created windows (such as Developer Task) may break away to preserve
    unsaved work, matching M103. If attachment fails, refuse unsafe launch.
    """
    if os.name != "nt":
        return None

    from ctypes import wintypes

    class BasicLimitInfo(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class IOCounters(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class ExtendedLimitInfo(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", BasicLimitInfo),
            ("IoInfo", IOCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
    kernel.CreateJobObjectW.restype = ctypes.c_void_p
    kernel.SetInformationJobObject.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD
    ]
    kernel.SetInformationJobObject.restype = wintypes.BOOL
    kernel.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel.CloseHandle.restype = wintypes.BOOL

    job = kernel.CreateJobObjectW(None, None)
    if not job:
        raise OSError(ctypes.get_last_error(), "M104_CREATE_JOB_FAILED")
    try:
        limits = ExtendedLimitInfo()
        # The supervised main dies when PyCharm stops this parent.
        # Subprocesses created by main (notably separate Developer Task GUI)
        # silently break away, retaining M103's no-force-close UI behavior.
        limits.BasicLimitInformation.LimitFlags = 0x00002000 | 0x00001000
        if not kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            raise OSError(ctypes.get_last_error(), "M104_CONFIGURE_JOB_FAILED")
        if not kernel.AssignProcessToJobObject(job, ctypes.c_void_p(int(process._handle))):
            raise OSError(ctypes.get_last_error(), "M104_ATTACH_CHILD_TO_JOB_FAILED")
    except BaseException:
        kernel.CloseHandle(job)
        raise
    return int(job)


def _close_job(job: int | None) -> None:
    if job is not None and os.name == "nt":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel.CloseHandle.restype = ctypes.c_int
        kernel.CloseHandle(ctypes.c_void_p(job))


def _validate(project: Path, interpreter: Path) -> Path:
    main = project / "main.py"
    if not main.is_file() or main.is_symlink():
        raise RuntimeError("M104_MAIN_MISSING_OR_LINK")
    if os.name == "nt":
        expected = project / ".venv" / "Scripts" / "python.exe"
        if os.path.normcase(os.path.abspath(str(interpreter))) != os.path.normcase(os.path.abspath(str(expected))):
            raise RuntimeError("M104_USE_PROJECT_VENV_INTERPRETER_IN_PYCHARM")
    return main


def run_supervised(*, project: Path, interpreter: Path, child: Path,
                   popen=subprocess.Popen, attach_job=_make_windows_kill_job,
                   close_job=_close_job, now=time.monotonic,
                   pause=time.sleep) -> int:
    """Never invokes arbitrary paths from STT; caller supplies pinned project main."""
    restarts: list[float] = []
    while True:
        env = os.environ.copy()
        env[SUPERVISOR_ENV] = "1"
        env["PYTHONUNBUFFERED"] = "1"
        print("[IDE] Starting SkynetVS in current Run tab", flush=True)
        proc = popen([str(interpreter), "-B", str(child)],
                     cwd=str(project), env=env,
                     stdin=None, stdout=None, stderr=None)
        job: int | None = None
        try:
            try:
                job = attach_job(proc)
            except BaseException:
                proc.terminate()
                proc.wait(timeout=10)
                raise
            code = proc.wait()
        finally:
            close_job(job)
        if code != RESTART_CODE:
            print(f"[IDE] SkynetVS stopped (exit={code})", flush=True)
            return int(code)
        current = now()
        restarts = [t for t in restarts if current - t < RESTART_WINDOW_SECONDS]
        restarts.append(current)
        if len(restarts) > RESTART_LIMIT:
            print("[IDE] Restart loop protection: too many restarts", flush=True)
            return 76
        print("[IDE] Confirmed voice restart — relaunching in this Run tab", flush=True)
        pause(0.5)


def main() -> int:
    if len(sys.argv) != 1:
        print("[IDE] This runner accepts no command-line arguments", flush=True)
        return 2
    project = Path(__file__).resolve().parents[1]
    try:
        child = _validate(project, Path(sys.executable))
        return run_supervised(project=project, interpreter=Path(sys.executable), child=child)
    except KeyboardInterrupt:
        print("[IDE] Stopped by user", flush=True)
        return 130
    except Exception as exc:
        print("[IDE] Supervisor failed: " + type(exc).__name__ + ": " + str(exc), flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
