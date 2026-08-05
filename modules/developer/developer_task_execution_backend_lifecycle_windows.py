from __future__ import annotations

"""Windows process and launch primitives for the trusted Sandbox lifecycle gate."""

import ctypes
import ntpath
import os
import subprocess
import time

from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Any


_SANDBOX_PROCESS_NAMES = {
    "windowssandbox.exe",
    "windowssandboxclient.exe",
    "windowssandboxremotesession.exe",
}
_PROCESS_TERMINATE = 0x0001
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_SYNCHRONIZE = 0x00100000
_TH32CS_SNAPPROCESS = 0x00000002
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
_ERROR_INVALID_PARAMETER = 87
_ERROR_NOT_FOUND = 1168
_WAIT_OBJECT_0 = 0x00000000
_WAIT_TIMEOUT = 0x00000102
_WAIT_FAILED = 0xFFFFFFFF
_FILETIME_UNIX_EPOCH_100NS = 116444736000000000
_PROCESS_SNAPSHOT_TIMEOUT_SECONDS = 10.0
_PROCESS_METADATA_RETRY_DELAYS_SECONDS = (0.02, 0.05)
_TERMINATION_POLL_SECONDS = 0.10


@dataclass(frozen=True)
class DeveloperTaskExecutionBackendProcessEvidence:
    name: str
    pid: int
    created_epoch_ns: int
    executable_path: str

    @property
    def identity_key(self) -> tuple[str, int, int]:
        return (self.name.casefold(), self.pid, self.created_epoch_ns)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "pid": self.pid,
            "created_epoch_ns": self.created_epoch_ns,
            "executable_path": self.executable_path,
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionBackendTerminationResult:
    attempted: bool
    succeeded: bool
    targeted_processes: tuple[DeveloperTaskExecutionBackendProcessEvidence, ...]
    remaining_processes: tuple[DeveloperTaskExecutionBackendProcessEvidence, ...]
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempted": self.attempted,
            "succeeded": self.succeeded,
            "targeted_processes": [item.to_dict() for item in self.targeted_processes],
            "remaining_processes": [item.to_dict() for item in self.remaining_processes],
            "errors": list(self.errors),
        }


class DeveloperTaskExecutionBackendLifecycleWindowsError(RuntimeError):
    def __init__(self, code: str, message: str, *, actual: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.actual = actual


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


class _FILETIME(ctypes.Structure):
    _fields_ = [
        ("dwLowDateTime", wintypes.DWORD),
        ("dwHighDateTime", wintypes.DWORD),
    ]


def _require_windows() -> None:
    if os.name != "nt":
        raise DeveloperTaskExecutionBackendLifecycleWindowsError(
            "sandbox_lifecycle_platform_unsupported",
            "Windows Sandbox lifecycle primitives require Windows.",
            actual=os.name,
        )


def _kernel32() -> Any:
    _require_windows()
    library = ctypes.WinDLL("kernel32", use_last_error=True)

    library.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    library.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    library.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]
    library.Process32FirstW.restype = wintypes.BOOL
    library.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]
    library.Process32NextW.restype = wintypes.BOOL
    library.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    library.OpenProcess.restype = wintypes.HANDLE
    library.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    library.QueryFullProcessImageNameW.restype = wintypes.BOOL
    library.GetProcessTimes.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_FILETIME),
        ctypes.POINTER(_FILETIME),
        ctypes.POINTER(_FILETIME),
        ctypes.POINTER(_FILETIME),
    ]
    library.GetProcessTimes.restype = wintypes.BOOL
    library.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    library.TerminateProcess.restype = wintypes.BOOL
    library.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    library.WaitForSingleObject.restype = wintypes.DWORD
    library.CloseHandle.argtypes = [wintypes.HANDLE]
    library.CloseHandle.restype = wintypes.BOOL
    return library


def _winerror_text(prefix: str, code: int) -> str:
    return f"{prefix}: winerror={code}; {ctypes.FormatError(code).strip()}"


def _last_error_text(prefix: str) -> str:
    return _winerror_text(prefix, ctypes.get_last_error())


def _process_has_exited(
    kernel32: Any,
    *,
    pid: int,
) -> bool:
    handle = kernel32.OpenProcess(_SYNCHRONIZE, False, pid)
    if not handle:
        error = ctypes.get_last_error()
        if error in {_ERROR_INVALID_PARAMETER, _ERROR_NOT_FOUND}:
            return True
        raise DeveloperTaskExecutionBackendLifecycleWindowsError(
            "sandbox_process_metadata_failed",
            "Sandbox process termination state could not be opened.",
            actual=_winerror_text(f"pid={pid};OpenProcess(SYNCHRONIZE)", error),
        )

    try:
        wait_result = int(kernel32.WaitForSingleObject(handle, 0))
        if wait_result == _WAIT_OBJECT_0:
            return True
        if wait_result == _WAIT_TIMEOUT:
            return False
        if wait_result == _WAIT_FAILED:
            raise DeveloperTaskExecutionBackendLifecycleWindowsError(
                "sandbox_process_metadata_failed",
                "Sandbox process termination state could not be read.",
                actual=_last_error_text(f"pid={pid};WaitForSingleObject"),
            )
        raise DeveloperTaskExecutionBackendLifecycleWindowsError(
            "sandbox_process_metadata_failed",
            "Sandbox process termination state returned an unexpected result.",
            actual=f"pid={pid};wait_result={wait_result}",
        )
    finally:
        kernel32.CloseHandle(handle)


def _filetime_value(value: _FILETIME) -> int:
    return (int(value.dwHighDateTime) << 32) | int(value.dwLowDateTime)


def _query_process_evidence_from_handle(
    kernel32: Any,
    handle: Any,
    pid: int,
    executable_name: str,
) -> DeveloperTaskExecutionBackendProcessEvidence | None:
    path_buffer = ctypes.create_unicode_buffer(32768)
    path_length = wintypes.DWORD(len(path_buffer))
    if not kernel32.QueryFullProcessImageNameW(
        handle,
        0,
        path_buffer,
        ctypes.byref(path_length),
    ):
        error = ctypes.get_last_error()
        if error in {_ERROR_INVALID_PARAMETER, _ERROR_NOT_FOUND}:
            return None
        if _process_has_exited(kernel32, pid=pid):
            return None
        raise DeveloperTaskExecutionBackendLifecycleWindowsError(
            "sandbox_process_metadata_failed",
            "Sandbox process executable path could not be read.",
            actual=_winerror_text(f"pid={pid}", error),
        )

    creation = _FILETIME()
    exit_time = _FILETIME()
    kernel_time = _FILETIME()
    user_time = _FILETIME()
    if not kernel32.GetProcessTimes(
        handle,
        ctypes.byref(creation),
        ctypes.byref(exit_time),
        ctypes.byref(kernel_time),
        ctypes.byref(user_time),
    ):
        error = ctypes.get_last_error()
        if error in {_ERROR_INVALID_PARAMETER, _ERROR_NOT_FOUND}:
            return None
        if _process_has_exited(kernel32, pid=pid):
            return None
        raise DeveloperTaskExecutionBackendLifecycleWindowsError(
            "sandbox_process_metadata_failed",
            "Sandbox process creation time could not be read.",
            actual=_winerror_text(f"pid={pid}", error),
        )

    executable_path = path_buffer.value
    if Path(executable_path).name.casefold() != executable_name.casefold():
        raise DeveloperTaskExecutionBackendLifecycleWindowsError(
            "sandbox_process_identity_invalid",
            "Sandbox process executable name does not match its process entry.",
            actual=f"pid={pid};name={executable_name};path={executable_path}",
        )

    created_100ns = _filetime_value(creation)
    created_epoch_ns = max(
        0,
        (created_100ns - _FILETIME_UNIX_EPOCH_100NS) * 100,
    )
    return DeveloperTaskExecutionBackendProcessEvidence(
        name=executable_name,
        pid=pid,
        created_epoch_ns=created_epoch_ns,
        executable_path=executable_path,
    )


def _query_process_evidence(
    kernel32: Any,
    pid: int,
    executable_name: str,
) -> DeveloperTaskExecutionBackendProcessEvidence | None:
    handle = kernel32.OpenProcess(
        _PROCESS_QUERY_LIMITED_INFORMATION,
        False,
        pid,
    )
    if not handle:
        error = ctypes.get_last_error()
        if error in {_ERROR_INVALID_PARAMETER, _ERROR_NOT_FOUND}:
            return None
        raise DeveloperTaskExecutionBackendLifecycleWindowsError(
            "sandbox_process_metadata_failed",
            "Sandbox process metadata could not be opened.",
            actual=_last_error_text(f"pid={pid}"),
        )

    try:
        return _query_process_evidence_from_handle(
            kernel32,
            handle,
            pid,
            executable_name,
        )
    finally:
        kernel32.CloseHandle(handle)


def _query_process_evidence_with_retry(
    kernel32: Any,
    pid: int,
    executable_name: str,
) -> DeveloperTaskExecutionBackendProcessEvidence | None:
    for attempt in range(len(_PROCESS_METADATA_RETRY_DELAYS_SECONDS) + 1):
        try:
            return _query_process_evidence(
                kernel32,
                pid,
                executable_name,
            )
        except DeveloperTaskExecutionBackendLifecycleWindowsError as exc:
            if (
                exc.code != "sandbox_process_metadata_failed"
                or attempt >= len(_PROCESS_METADATA_RETRY_DELAYS_SECONDS)
            ):
                raise
            time.sleep(_PROCESS_METADATA_RETRY_DELAYS_SECONDS[attempt])

    raise AssertionError("unreachable process metadata retry state")


def snapshot_windows_sandbox_processes(
) -> tuple[DeveloperTaskExecutionBackendProcessEvidence, ...]:
    """Return complete identities for all known Windows Sandbox host processes."""

    kernel32 = _kernel32()
    snapshot = kernel32.CreateToolhelp32Snapshot(_TH32CS_SNAPPROCESS, 0)
    if snapshot == _INVALID_HANDLE_VALUE:
        raise DeveloperTaskExecutionBackendLifecycleWindowsError(
            "sandbox_process_probe_failed",
            "Windows process snapshot could not be created.",
            actual=_last_error_text("CreateToolhelp32Snapshot"),
        )

    found: list[DeveloperTaskExecutionBackendProcessEvidence] = []
    started = time.monotonic()

    try:
        entry = _PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
        has_entry = bool(kernel32.Process32FirstW(snapshot, ctypes.byref(entry)))

        while has_entry:
            if time.monotonic() - started > _PROCESS_SNAPSHOT_TIMEOUT_SECONDS:
                raise DeveloperTaskExecutionBackendLifecycleWindowsError(
                    "sandbox_process_probe_timeout",
                    "Windows Sandbox process inspection timed out.",
                )

            executable_name = str(entry.szExeFile)
            if executable_name.casefold() in _SANDBOX_PROCESS_NAMES:
                evidence = _query_process_evidence_with_retry(
                    kernel32,
                    int(entry.th32ProcessID),
                    executable_name,
                )
                if evidence is not None:
                    found.append(evidence)

            has_entry = bool(kernel32.Process32NextW(snapshot, ctypes.byref(entry)))
    finally:
        kernel32.CloseHandle(snapshot)

    return tuple(sorted(found, key=lambda item: (item.name.casefold(), item.pid)))


def _normalized_windows_path(path: str | Path) -> str:
    return ntpath.normcase(ntpath.abspath(os.fspath(path)))


def _is_trusted_sandbox_process_path(
    evidence: DeveloperTaskExecutionBackendProcessEvidence,
    sandbox_executable: Path,
) -> bool:
    name = evidence.name.casefold()
    path = PureWindowsPath(evidence.executable_path)
    if name == "windowssandbox.exe":
        return _normalized_windows_path(path) == _normalized_windows_path(sandbox_executable)

    if name not in {"windowssandboxclient.exe", "windowssandboxremotesession.exe"}:
        return False

    parts = tuple(part.casefold() for part in path.parts)
    try:
        windows_apps_index = parts.index("windowsapps")
    except ValueError:
        return False
    if (
        windows_apps_index < 1
        or parts[windows_apps_index - 1] != "program files"
        or windows_apps_index + 1 >= len(parts)
    ):
        return False

    package = parts[windows_apps_index + 1]
    return (
        package.startswith("microsoftwindows.windowssandbox_")
        and package.endswith("__cw5n1h2txyewy")
        and path.name.casefold() == name
    )


def _terminate_exact_process(
    kernel32: Any,
    expected: DeveloperTaskExecutionBackendProcessEvidence,
    *,
    timeout_seconds: float,
) -> tuple[bool, str]:
    access = _PROCESS_QUERY_LIMITED_INFORMATION | _PROCESS_TERMINATE | _SYNCHRONIZE
    handle = kernel32.OpenProcess(access, False, expected.pid)
    if not handle:
        error = ctypes.get_last_error()
        if error in {_ERROR_INVALID_PARAMETER, _ERROR_NOT_FOUND}:
            return False, ""
        return False, _last_error_text(f"OpenProcess pid={expected.pid}")

    try:
        current = _query_process_evidence_from_handle(
            kernel32,
            handle,
            expected.pid,
            expected.name,
        )
        if current is None:
            return False, ""
        if (
            current.identity_key != expected.identity_key
            or _normalized_windows_path(current.executable_path)
            != _normalized_windows_path(expected.executable_path)
        ):
            return False, (
                "identity_changed="
                f"{expected.name}:{expected.pid}:{expected.created_epoch_ns}"
            )

        if not kernel32.TerminateProcess(handle, 1):
            wait_state = int(kernel32.WaitForSingleObject(handle, 0))
            if wait_state == _WAIT_OBJECT_0:
                return False, ""
            return False, _last_error_text(f"TerminateProcess pid={expected.pid}")

        wait_ms = max(1, min(int(timeout_seconds * 1000), 10_000))
        wait_state = int(kernel32.WaitForSingleObject(handle, wait_ms))
        if wait_state not in {_WAIT_OBJECT_0, _WAIT_TIMEOUT}:
            return True, f"WaitForSingleObject pid={expected.pid};state={wait_state}"
        return True, ""
    finally:
        kernel32.CloseHandle(handle)

def build_windows_sandbox_environment(executable: Path) -> dict[str, str]:
    system32 = executable.parent
    windows = system32.parent
    return {
        "SystemRoot": str(windows),
        "WINDIR": str(windows),
        "ComSpec": str(system32 / "cmd.exe"),
        "PATH": str(system32),
        "PATHEXT": ".COM;.EXE;.BAT;.CMD",
        "PSModulePath": str(
            windows / "System32" / "WindowsPowerShell" / "v1.0" / "Modules"
        ),
    }


def launch_windows_sandbox(
    executable: Path,
    config_path: Path,
) -> subprocess.Popen[bytes]:
    """Launch the fixed WindowsSandbox.exe without shell or PATH resolution."""

    _require_windows()
    try:
        return subprocess.Popen(
            [str(executable), str(config_path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=build_windows_sandbox_environment(executable),
            close_fds=True,
            shell=False,
        )
    except OSError as exc:
        raise DeveloperTaskExecutionBackendLifecycleWindowsError(
            "sandbox_launch_failed",
            "Windows Sandbox could not be launched.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc


def launcher_has_exited(launcher: subprocess.Popen[bytes]) -> bool:
    return launcher.poll() is not None


def terminate_observed_windows_sandbox_processes(
    observed_processes: tuple[DeveloperTaskExecutionBackendProcessEvidence, ...],
    *,
    sandbox_executable: Path,
    timeout_seconds: float,
) -> DeveloperTaskExecutionBackendTerminationResult:
    """Best-effort cleanup for reverified trusted process identities only.

    Forced cleanup is never success evidence for lifecycle attestation. It uses
    exact process handles, rechecks creation time and executable path, and does
    not invoke a PATH-resolved shell or process-tree utility.
    """

    _require_windows()
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if sandbox_executable.name.casefold() != "windowssandbox.exe":
        raise ValueError("sandbox_executable must be WindowsSandbox.exe")

    errors: list[str] = []
    observed_by_key: dict[
        tuple[str, int, int],
        DeveloperTaskExecutionBackendProcessEvidence,
    ] = {}
    for item in observed_processes:
        if _is_trusted_sandbox_process_path(item, sandbox_executable):
            observed_by_key[item.identity_key] = item
        else:
            errors.append(
                f"untrusted_path={item.name}:{item.pid}:{item.executable_path}"
            )

    current = snapshot_windows_sandbox_processes()
    targets = tuple(
        item
        for item in current
        if item.identity_key in observed_by_key
        and _normalized_windows_path(item.executable_path)
        == _normalized_windows_path(
            observed_by_key[item.identity_key].executable_path
        )
    )

    deadline = time.monotonic() + timeout_seconds
    kernel32 = _kernel32()
    attempted_targets: list[DeveloperTaskExecutionBackendProcessEvidence] = []

    for item in targets:
        remaining_seconds = max(0.0, deadline - time.monotonic())
        if remaining_seconds <= 0:
            errors.append("forced_cleanup_timeout_before_all_targets")
            break
        attempted, error = _terminate_exact_process(
            kernel32,
            observed_by_key[item.identity_key],
            timeout_seconds=remaining_seconds,
        )
        if attempted:
            attempted_targets.append(item)
        if error:
            errors.append(error)

    remaining: tuple[DeveloperTaskExecutionBackendProcessEvidence, ...] = ()
    while time.monotonic() < deadline:
        remaining = tuple(
            item
            for item in snapshot_windows_sandbox_processes()
            if item.identity_key in observed_by_key
        )
        if not remaining:
            break
        time.sleep(_TERMINATION_POLL_SECONDS)

    if remaining:
        errors.append(
            "remaining=" + ",".join(
                f"{item.name}:{item.pid}:{item.created_epoch_ns}"
                for item in remaining
            )
        )

    return DeveloperTaskExecutionBackendTerminationResult(
        attempted=bool(attempted_targets),
        succeeded=not remaining and not errors,
        targeted_processes=tuple(attempted_targets),
        remaining_processes=remaining,
        errors=tuple(errors),
    )
