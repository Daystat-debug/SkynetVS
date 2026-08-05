from __future__ import annotations

"""Read-only host capability gate for the traditional Windows Sandbox backend."""

import csv
import ctypes
import hashlib
import io
import locale
import os
import platform
import shutil
import stat
import subprocess
import sys
import time

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from modules.developer.developer_task_execution_backend_policy import (
    DeveloperTaskExecutionBackendPolicy,
    WINDOWS_SANDBOX_EXECUTION_POLICY_V1,
    validate_execution_backend_policy,
)
from modules.developer.developer_task_preflight import DeveloperTaskPreflightIssue
from modules.developer.developer_task_workspace_cleanup_fs import (
    is_reparse_or_symlink,
)


_MAX_SANDBOX_EXECUTABLE_BYTES = 128 * 1024 * 1024
_HOST_PROBE_TIMEOUT_SECONDS = 10.0
_FEATURE_NAME = "Containers-DisposableClientVM"
_SANDBOX_PROCESS_NAMES = {
    "windowssandbox.exe",
    "windowssandboxclient.exe",
    "windowssandboxremotesession.exe",
}


@dataclass(frozen=True)
class DeveloperTaskExecutionBackendExecutableEvidence:
    path: str
    version: str
    size_bytes: int
    mtime_ns: int
    sha256: str

    @property
    def ok(self) -> bool:
        return (
            bool(self.path)
            and bool(self.version)
            and self.size_bytes > 0
            and self.mtime_ns > 0
            and len(self.sha256) == 64
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "version": self.version,
            "size_bytes": self.size_bytes,
            "mtime_ns": self.mtime_ns,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionBackendHostReport:
    """Immutable host evidence; this report does not authorize code execution."""

    backend_id: str
    policy: DeveloperTaskExecutionBackendPolicy
    policy_fingerprint: str
    host_platform: str
    host_architecture: str
    process_bitness: int
    windows_build: int
    host_boot_epoch_seconds: int
    feature_state: str
    feature_probe_error: str
    executable: DeveloperTaskExecutionBackendExecutableEvidence | None
    wsb_cli_found: bool
    wsb_cli_path: str
    wsb_cli_probe_error: str
    running_sandbox_processes: tuple[str, ...]
    issues: tuple[DeveloperTaskPreflightIssue, ...]

    @property
    def ok(self) -> bool:
        return (
            self.backend_id == self.policy.backend_id
            and self.policy_fingerprint == self.policy.fingerprint
            and self.host_platform == "win32"
            and self.host_architecture in self.policy.supported_architectures
            and self.process_bitness == self.policy.required_process_bitness
            and self.windows_build >= self.policy.minimum_windows_build
            and self.host_boot_epoch_seconds > 0
            and self.feature_state not in {
                "disabled",
                "disable_pending",
                "enable_pending",
            }
            and self.executable is not None
            and self.executable.ok
            and _version_build(self.executable.version)
            >= self.policy.minimum_sandbox_executable_build
            and not self.running_sandbox_processes
            and not self.issues
        )

    @property
    def issue_codes(self) -> tuple[str, ...]:
        return tuple(item.code for item in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "backend_id": self.backend_id,
            "policy": self.policy.to_dict(),
            "policy_fingerprint": self.policy_fingerprint,
            "host_platform": self.host_platform,
            "host_architecture": self.host_architecture,
            "process_bitness": self.process_bitness,
            "windows_build": self.windows_build,
            "host_boot_epoch_seconds": self.host_boot_epoch_seconds,
            "feature_state": self.feature_state,
            "feature_probe_error": self.feature_probe_error,
            "executable": (
                self.executable.to_dict()
                if self.executable is not None
                else None
            ),
            "wsb_cli_found": self.wsb_cli_found,
            "wsb_cli_path": self.wsb_cli_path,
            "wsb_cli_probe_error": self.wsb_cli_probe_error,
            "running_sandbox_processes": list(self.running_sandbox_processes),
            "execution_authorized": False,
            "issues": [item.to_dict() for item in self.issues],
            "issue_codes": list(self.issue_codes),
        }


class DeveloperTaskExecutionBackendHostError(RuntimeError):
    def __init__(self, code: str, message: str, *, actual: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.actual = actual


class _HostContext:
    def __init__(self, policy: DeveloperTaskExecutionBackendPolicy) -> None:
        self.policy = policy
        self.host_platform = ""
        self.host_architecture = ""
        self.process_bitness = 0
        self.windows_build = 0
        self.host_boot_epoch_seconds = 0
        self.feature_state = "unknown"
        self.feature_probe_error = ""
        self.executable: DeveloperTaskExecutionBackendExecutableEvidence | None = None
        self.wsb_cli_found = False
        self.wsb_cli_path = ""
        self.wsb_cli_probe_error = ""
        self.running_sandbox_processes: tuple[str, ...] = ()
        self.issues: list[DeveloperTaskPreflightIssue] = []

    def add(
        self,
        code: str,
        check: str,
        message: str,
        *,
        expected: str = "",
        actual: str = "",
    ) -> None:
        self.issues.append(
            DeveloperTaskPreflightIssue(
                code=code,
                check=check,
                message=message,
                expected=expected,
                actual=actual,
            )
        )

    def report(self) -> DeveloperTaskExecutionBackendHostReport:
        return DeveloperTaskExecutionBackendHostReport(
            backend_id=self.policy.backend_id,
            policy=self.policy,
            policy_fingerprint=self.policy.fingerprint,
            host_platform=self.host_platform,
            host_architecture=self.host_architecture,
            process_bitness=self.process_bitness,
            windows_build=self.windows_build,
            host_boot_epoch_seconds=self.host_boot_epoch_seconds,
            feature_state=self.feature_state,
            feature_probe_error=self.feature_probe_error,
            executable=self.executable,
            wsb_cli_found=self.wsb_cli_found,
            wsb_cli_path=self.wsb_cli_path,
            wsb_cli_probe_error=self.wsb_cli_probe_error,
            running_sandbox_processes=self.running_sandbox_processes,
            issues=tuple(self.issues),
        )


def _version_build(version: str) -> int:
    parts = version.strip().split(".")
    if len(parts) < 3 or any(not item.isdigit() for item in parts[:3]):
        return 0
    return int(parts[2])


def _current_platform() -> str:
    return sys.platform


def _current_architecture() -> str:
    return platform.machine().strip().upper()


def _current_process_bitness() -> int:
    return int(ctypes.sizeof(ctypes.c_void_p) * 8)


def _current_windows_build() -> int:
    getter = getattr(sys, "getwindowsversion", None)
    if getter is None:
        return 0
    return int(getter().build)


def _current_boot_epoch_seconds() -> int:
    if sys.platform != "win32":
        return 0

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    get_tick_count = kernel32.GetTickCount64
    get_tick_count.argtypes = []
    get_tick_count.restype = ctypes.c_ulonglong
    uptime_seconds = int(get_tick_count() // 1000)
    return max(1, int(time.time()) - uptime_seconds)


def _read_windows_directory(function_name: str) -> Path:
    if sys.platform != "win32":
        value = os.environ.get("WINDIR") or os.environ.get("SystemRoot")
        if not value:
            raise DeveloperTaskExecutionBackendHostError(
                "windows_directory_missing",
                "Windows directory is unavailable.",
            )
        return Path(value).resolve(strict=False)

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    function = getattr(kernel32, function_name)
    function.argtypes = [ctypes.POINTER(ctypes.c_wchar), ctypes.c_uint32]
    function.restype = ctypes.c_uint32

    buffer = ctypes.create_unicode_buffer(32768)
    length = int(function(buffer, len(buffer)))
    if length <= 0 or length >= len(buffer):
        raise DeveloperTaskExecutionBackendHostError(
            "windows_directory_missing",
            "Windows system directory could not be resolved.",
            actual=str(ctypes.get_last_error()),
        )
    return Path(buffer.value)


def _windows_directory() -> Path:
    return _read_windows_directory("GetWindowsDirectoryW")


def _system_directory() -> Path:
    return _read_windows_directory("GetSystemDirectoryW")


def _sandbox_executable_path(policy: DeveloperTaskExecutionBackendPolicy) -> Path:
    return _system_directory() / policy.sandbox_executable_name


def _path_identity(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        stat.S_IFMT(value.st_mode),
        int(getattr(value, "st_dev", 0)),
        int(getattr(value, "st_ino", 0)),
        int(value.st_size),
        int(value.st_mtime_ns),
    )


def _read_regular_file_sha256(path: Path) -> tuple[int, int, str]:
    try:
        before = os.lstat(path)
    except FileNotFoundError as exc:
        raise DeveloperTaskExecutionBackendHostError(
            "sandbox_executable_missing",
            "Windows Sandbox executable is missing.",
            actual=str(path),
        ) from exc
    except OSError as exc:
        raise DeveloperTaskExecutionBackendHostError(
            "sandbox_executable_metadata_failed",
            "Windows Sandbox executable metadata could not be read.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc

    if is_reparse_or_symlink(before):
        raise DeveloperTaskExecutionBackendHostError(
            "sandbox_executable_reparse_point",
            "Windows Sandbox executable must not be a reparse point.",
            actual=str(path),
        )
    if not stat.S_ISREG(before.st_mode):
        raise DeveloperTaskExecutionBackendHostError(
            "sandbox_executable_not_regular",
            "Windows Sandbox executable must be a regular file.",
            actual=str(path),
        )
    if before.st_size <= 0 or before.st_size > _MAX_SANDBOX_EXECUTABLE_BYTES:
        raise DeveloperTaskExecutionBackendHostError(
            "sandbox_executable_size_invalid",
            "Windows Sandbox executable size is outside the allowed range.",
            actual=str(before.st_size),
        )

    digest = hashlib.sha256()

    try:
        with path.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            if _path_identity(opened) != _path_identity(before):
                raise DeveloperTaskExecutionBackendHostError(
                    "sandbox_executable_changed_during_read",
                    "Windows Sandbox executable changed before hashing.",
                )

            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)

            finished = os.fstat(stream.fileno())
    except DeveloperTaskExecutionBackendHostError:
        raise
    except OSError as exc:
        raise DeveloperTaskExecutionBackendHostError(
            "sandbox_executable_read_failed",
            "Windows Sandbox executable could not be hashed.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc

    try:
        after = os.lstat(path)
    except OSError as exc:
        raise DeveloperTaskExecutionBackendHostError(
            "sandbox_executable_changed_during_read",
            "Windows Sandbox executable metadata changed after hashing.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc

    identity = _path_identity(before)
    if _path_identity(finished) != identity or _path_identity(after) != identity:
        raise DeveloperTaskExecutionBackendHostError(
            "sandbox_executable_changed_during_read",
            "Windows Sandbox executable changed while being hashed.",
        )

    return int(before.st_size), int(before.st_mtime_ns), digest.hexdigest()


def _read_windows_file_version(path: Path) -> str:
    if sys.platform != "win32":
        raise DeveloperTaskExecutionBackendHostError(
            "sandbox_executable_version_failed",
            "Windows version resources are unavailable on this platform.",
        )

    windows = _windows_directory()
    powershell = (
        windows
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    )
    if not powershell.is_file():
        raise DeveloperTaskExecutionBackendHostError(
            "sandbox_executable_version_failed",
            "Trusted Windows PowerShell is unavailable.",
            actual=str(powershell),
        )

    import base64

    encoded_path = base64.b64encode(str(path).encode("utf-8")).decode("ascii")
    script = (
        "$ErrorActionPreference='Stop';"
        "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false);"
        "$p=[System.Text.Encoding]::UTF8.GetString("
        f"[Convert]::FromBase64String('{encoded_path}'));"
        "$item=Get-Item -LiteralPath $p -Force;"
        "[Console]::Out.Write([string]$item.VersionInfo.FileVersion)"
    )

    try:
        result = subprocess.run(
            [
                str(powershell),
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=_fixed_host_environment(),
            timeout=_HOST_PROBE_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise DeveloperTaskExecutionBackendHostError(
            "sandbox_executable_version_timeout",
            "Windows Sandbox executable version probe timed out.",
        ) from exc
    except OSError as exc:
        raise DeveloperTaskExecutionBackendHostError(
            "sandbox_executable_version_failed",
            "Windows Sandbox executable version probe could not start.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc

    if result.returncode != 0:
        raise DeveloperTaskExecutionBackendHostError(
            "sandbox_executable_version_failed",
            "Windows Sandbox executable version probe failed.",
            actual=(
                result.stderr.decode("utf-8", errors="replace").strip()
                or f"exit_code={result.returncode}"
            ),
        )

    version = result.stdout.decode("utf-8", errors="strict").strip()
    if _version_build(version) <= 0:
        raise DeveloperTaskExecutionBackendHostError(
            "sandbox_executable_version_invalid",
            "Windows Sandbox executable version is invalid.",
            actual=version,
        )
    return version


def _inspect_sandbox_executable(
    policy: DeveloperTaskExecutionBackendPolicy,
) -> DeveloperTaskExecutionBackendExecutableEvidence:
    path = _sandbox_executable_path(policy)
    size_bytes, mtime_ns, sha256 = _read_regular_file_sha256(path)
    version = _read_windows_file_version(path)
    return DeveloperTaskExecutionBackendExecutableEvidence(
        path=str(path),
        version=version,
        size_bytes=size_bytes,
        mtime_ns=mtime_ns,
        sha256=sha256,
    )


def _fixed_host_environment() -> dict[str, str]:
    windows = _windows_directory()
    system32 = _system_directory()
    environment = {
        "SystemRoot": str(windows),
        "WINDIR": str(windows),
        "ComSpec": str(system32 / "cmd.exe"),
        "PATH": str(system32),
        "PATHEXT": ".COM;.EXE;.BAT;.CMD",
        "PSModulePath": str(
            windows / "System32" / "WindowsPowerShell" / "v1.0" / "Modules"
        ),
    }
    return environment


def _probe_optional_feature_state() -> tuple[str, str]:
    windows = _windows_directory()
    powershell = windows / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    if not powershell.is_file():
        return "unknown", "powershell_unavailable"

    script = (
        "$ErrorActionPreference='Stop';"
        f"$feature=Get-WindowsOptionalFeature -Online -FeatureName '{_FEATURE_NAME}';"
        "[Console]::Out.Write([string]$feature.State)"
    )

    try:
        result = subprocess.run(
            [
                str(powershell),
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=_fixed_host_environment(),
            timeout=_HOST_PROBE_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return "unknown", f"{type(exc).__name__}: {exc}"

    if result.returncode != 0:
        error = result.stderr.decode("utf-8", errors="replace").strip()
        return "unknown", error or f"exit_code={result.returncode}"

    raw = result.stdout.decode("utf-8", errors="replace").strip().casefold()
    normalized = {
        "enabled": "enabled",
        "disabled": "disabled",
        "enablepending": "enable_pending",
        "disablepending": "disable_pending",
    }.get(raw.replace("_", "").replace(" ", ""), "unknown")
    return normalized, "" if normalized != "unknown" else raw


def _probe_running_sandbox_processes() -> tuple[str, ...]:
    tasklist = _system_directory() / "tasklist.exe"
    if not tasklist.is_file():
        raise DeveloperTaskExecutionBackendHostError(
            "sandbox_process_probe_unavailable",
            "tasklist.exe is unavailable.",
            actual=str(tasklist),
        )

    try:
        result = subprocess.run(
            [str(tasklist), "/FO", "CSV", "/NH"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=_fixed_host_environment(),
            timeout=_HOST_PROBE_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise DeveloperTaskExecutionBackendHostError(
            "sandbox_process_probe_timeout",
            "Sandbox process inspection timed out.",
        ) from exc
    except OSError as exc:
        raise DeveloperTaskExecutionBackendHostError(
            "sandbox_process_probe_failed",
            "Sandbox process inspection could not be started.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc

    if result.returncode != 0:
        raise DeveloperTaskExecutionBackendHostError(
            "sandbox_process_probe_failed",
            "Sandbox process inspection failed.",
            actual=(
                result.stderr.decode("utf-8", errors="replace").strip()
                or f"exit_code={result.returncode}"
            ),
        )

    encoding = locale.getpreferredencoding(False) or "utf-8"
    text = result.stdout.decode(encoding, errors="replace")
    found: set[str] = set()
    for row in csv.reader(io.StringIO(text)):
        if not row:
            continue
        name = row[0].strip().casefold()
        if name in _SANDBOX_PROCESS_NAMES:
            pid = row[1].strip() if len(row) > 1 else ""
            found.add(f"{name}:{pid}" if pid else name)
    return tuple(sorted(found))


def _probe_wsb_cli() -> tuple[bool, str]:
    windows = _windows_directory()
    candidates = [
        _system_directory() / "wsb.exe",
    ]

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.append(
            Path(local_app_data) / "Microsoft" / "WindowsApps" / "wsb.exe"
        )

    fixed = shutil.which("wsb.exe", path=str(_system_directory()))
    if fixed:
        candidates.insert(0, Path(fixed))

    for candidate in candidates:
        try:
            metadata = os.lstat(candidate)
        except OSError:
            continue
        if stat.S_ISREG(metadata.st_mode) and not is_reparse_or_symlink(metadata):
            return True, str(candidate.resolve(strict=False))
    return False, ""


def inspect_developer_task_execution_backend_host(
) -> DeveloperTaskExecutionBackendHostReport:
    """Inspect host capability without launching Sandbox or task code."""

    policy = WINDOWS_SANDBOX_EXECUTION_POLICY_V1
    context = _HostContext(policy)

    policy_errors = validate_execution_backend_policy(policy)
    if policy_errors:
        context.add(
            "execution_backend_policy_invalid",
            "backend_policy",
            "Canonical execution backend policy is invalid.",
            actual=",".join(policy_errors),
        )
        return context.report()

    context.host_platform = _current_platform()
    context.host_architecture = _current_architecture()
    context.process_bitness = _current_process_bitness()

    if context.host_platform != "win32":
        context.add(
            "execution_backend_platform_unsupported",
            "backend_host",
            "Windows Sandbox backend requires Windows.",
            expected="win32",
            actual=context.host_platform,
        )
        return context.report()

    if context.host_architecture not in policy.supported_architectures:
        context.add(
            "execution_backend_architecture_unsupported",
            "backend_host",
            "Host architecture is unsupported.",
            expected=",".join(policy.supported_architectures),
            actual=context.host_architecture,
        )

    if context.process_bitness != policy.required_process_bitness:
        context.add(
            "execution_backend_process_bitness_unsupported",
            "backend_host",
            "The backend requires a 64-bit host Python process.",
            expected=str(policy.required_process_bitness),
            actual=str(context.process_bitness),
        )

    context.windows_build = _current_windows_build()
    if context.windows_build < policy.minimum_windows_build:
        context.add(
            "execution_backend_windows_build_unsupported",
            "backend_host",
            "Windows build is below the backend policy minimum.",
            expected=str(policy.minimum_windows_build),
            actual=str(context.windows_build),
        )

    try:
        context.host_boot_epoch_seconds = _current_boot_epoch_seconds()
    except (OSError, RuntimeError, ValueError) as exc:
        context.add(
            "execution_backend_boot_identity_failed",
            "backend_host",
            "Host boot identity could not be determined.",
            actual=f"{type(exc).__name__}: {exc}",
        )

    try:
        context.executable = _inspect_sandbox_executable(policy)
    except DeveloperTaskExecutionBackendHostError as exc:
        context.add(exc.code, "backend_executable", exc.message, actual=exc.actual)

    if (
        context.executable is not None
        and _version_build(context.executable.version)
        < policy.minimum_sandbox_executable_build
    ):
        context.add(
            "sandbox_executable_version_unsupported",
            "backend_executable",
            "Windows Sandbox executable version is below policy minimum.",
            expected=str(policy.minimum_sandbox_executable_build),
            actual=context.executable.version,
        )

    context.feature_state, context.feature_probe_error = (
        _probe_optional_feature_state()
    )
    if context.feature_state in {"disabled", "disable_pending"}:
        context.add(
            "sandbox_feature_disabled",
            "backend_feature",
            "Windows Sandbox optional feature is disabled.",
            actual=context.feature_state,
        )
    elif context.feature_state == "enable_pending":
        context.add(
            "sandbox_feature_restart_required",
            "backend_feature",
            "Windows Sandbox optional feature requires a restart.",
            actual=context.feature_state,
        )

    try:
        context.running_sandbox_processes = _probe_running_sandbox_processes()
    except DeveloperTaskExecutionBackendHostError as exc:
        context.add(exc.code, "backend_processes", exc.message, actual=exc.actual)

    if context.running_sandbox_processes:
        context.add(
            "sandbox_instance_running",
            "backend_processes",
            "A Windows Sandbox instance is already running.",
            actual=",".join(context.running_sandbox_processes),
        )

    try:
        context.wsb_cli_found, context.wsb_cli_path = _probe_wsb_cli()
    except (OSError, RuntimeError, ValueError) as exc:
        context.wsb_cli_found = False
        context.wsb_cli_path = ""
        context.wsb_cli_probe_error = f"{type(exc).__name__}: {exc}"

    return context.report()
