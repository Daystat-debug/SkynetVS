from __future__ import annotations

"""Canonical trusted payloads and strict result validation for Sandbox lifecycle V1B2."""

import hashlib
import json
import os
import re
import stat

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from modules.developer.developer_task_execution_backend_policy import (
    DeveloperTaskExecutionBackendPolicy,
)
from modules.developer.developer_task_workspace_cleanup_fs import (
    is_reparse_or_symlink,
)


LIFECYCLE_REQUEST_SCHEMA_VERSION = 1
LIFECYCLE_RESULT_SCHEMA_VERSION = 1
LIFECYCLE_REQUEST_NAME = "request.json"
LIFECYCLE_GUEST_SCRIPT_NAME = "guest_lifecycle_probe.ps1"
LIFECYCLE_WSB_NAME = "SkynetVS_Lifecycle.wsb"
LIFECYCLE_RESULT_NAME = "result.json"
LIFECYCLE_SHUTDOWN_DELAY_SECONDS = 5
_HEX_32 = re.compile(r"^[0-9a-f]{32}$")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_READ_CHUNK_BYTES = 64 * 1024


@dataclass(frozen=True)
class DeveloperTaskExecutionBackendLifecycleRequest:
    schema_version: int
    backend_id: str
    policy_fingerprint: str
    request_id: str
    nonce: str = field(repr=False)
    generated_at_epoch: int
    guest_script_sha256: str
    wsb_sha256: str
    launch_timeout_seconds: int
    shutdown_grace_seconds: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "backend_id": self.backend_id,
            "policy_fingerprint": self.policy_fingerprint,
            "request_id": self.request_id,
            "nonce": self.nonce,
            "generated_at_epoch": self.generated_at_epoch,
            "guest_script_sha256": self.guest_script_sha256,
            "wsb_sha256": self.wsb_sha256,
            "launch_timeout_seconds": self.launch_timeout_seconds,
            "shutdown_grace_seconds": self.shutdown_grace_seconds,
        }

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


@dataclass(frozen=True)
class DeveloperTaskExecutionBackendLifecycleGuestEvidence:
    schema_version: int
    backend_id: str
    policy_fingerprint: str
    request_id: str
    nonce: str = field(repr=False)
    request_sha256: str
    guest_script_sha256: str
    wsb_sha256: str
    completed_at: str
    guest_computer_name: str
    guest_user_name: str
    guest_architecture: str
    guest_os_description: str
    guest_powershell_version: str
    shutdown_scheduled: bool
    shutdown_exit_code: int
    shutdown_delay_seconds: int
    input_mapping_present: bool
    input_mapping_read_only_enforced: bool
    output_mapping_present: bool
    output_mapping_writable: bool
    ipv4_default_route_present: bool
    ipv4_external_tcp_reachable: bool
    ipv6_default_route_present: bool
    ipv6_external_tcp_reachable: bool
    input_write_error: str
    output_write_error: str
    ipv4_route_error: str
    ipv6_route_error: str
    ipv4_tcp_error: str
    ipv6_tcp_error: str
    result_size_bytes: int
    result_sha256: str

    @property
    def ok(self) -> bool:
        return (
            self.schema_version == LIFECYCLE_RESULT_SCHEMA_VERSION
            and bool(self.backend_id)
            and len(self.policy_fingerprint) == 64
            and bool(_HEX_32.fullmatch(self.request_id))
            and bool(_HEX_64.fullmatch(self.nonce))
            and len(self.request_sha256) == 64
            and len(self.guest_script_sha256) == 64
            and len(self.wsb_sha256) == 64
            and bool(self.completed_at)
            and self.guest_user_name.casefold().endswith(r"\wdagutilityaccount")
            and self.guest_architecture.casefold() == "x64"
            and self.shutdown_scheduled
            and self.shutdown_exit_code == 0
            and self.shutdown_delay_seconds == LIFECYCLE_SHUTDOWN_DELAY_SECONDS
            and self.input_mapping_present
            and self.input_mapping_read_only_enforced
            and self.output_mapping_present
            and self.output_mapping_writable
            and not self.ipv4_default_route_present
            and not self.ipv4_external_tcp_reachable
            and not self.ipv6_default_route_present
            and not self.ipv6_external_tcp_reachable
            and bool(self.input_write_error)
            and not self.output_write_error
            and not self.ipv4_route_error
            and not self.ipv6_route_error
            and 0 < self.result_size_bytes
            and len(self.result_sha256) == 64
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "schema_version": self.schema_version,
            "backend_id": self.backend_id,
            "policy_fingerprint": self.policy_fingerprint,
            "request_id": self.request_id,
            "nonce": self.nonce,
            "request_sha256": self.request_sha256,
            "guest_script_sha256": self.guest_script_sha256,
            "wsb_sha256": self.wsb_sha256,
            "completed_at": self.completed_at,
            "guest": {
                "computer_name": self.guest_computer_name,
                "user_name": self.guest_user_name,
                "process_architecture": self.guest_architecture,
                "os_description": self.guest_os_description,
                "powershell_version": self.guest_powershell_version,
            },
            "shutdown": {
                "scheduled": self.shutdown_scheduled,
                "exit_code": self.shutdown_exit_code,
                "delay_seconds": self.shutdown_delay_seconds,
            },
            "controls": {
                "input_mapping_present": self.input_mapping_present,
                "input_mapping_read_only_enforced": (
                    self.input_mapping_read_only_enforced
                ),
                "output_mapping_present": self.output_mapping_present,
                "output_mapping_writable": self.output_mapping_writable,
                "ipv4_default_route_present": self.ipv4_default_route_present,
                "ipv4_external_tcp_reachable": self.ipv4_external_tcp_reachable,
                "ipv6_default_route_present": self.ipv6_default_route_present,
                "ipv6_external_tcp_reachable": self.ipv6_external_tcp_reachable,
            },
            "diagnostics": {
                "input_write_error": self.input_write_error,
                "output_write_error": self.output_write_error,
                "ipv4_route_error": self.ipv4_route_error,
                "ipv6_route_error": self.ipv6_route_error,
                "ipv4_tcp_error": self.ipv4_tcp_error,
                "ipv6_tcp_error": self.ipv6_tcp_error,
            },
            "result_size_bytes": self.result_size_bytes,
            "result_sha256": self.result_sha256,
        }


class DeveloperTaskExecutionBackendLifecyclePayloadError(RuntimeError):
    def __init__(self, code: str, message: str, *, actual: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.actual = actual


def canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def build_lifecycle_guest_script(
    policy: DeveloperTaskExecutionBackendPolicy,
) -> bytes:
    template = r'''Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Utf8NoBom {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$Text
    )
    [System.IO.File]::WriteAllText(
        $Path,
        $Text,
        [System.Text.UTF8Encoding]::new($false)
    )
}

function Invoke-TcpProbe {
    param(
        [Parameter(Mandatory = $true)]
        [System.Net.Sockets.AddressFamily]$AddressFamily,
        [Parameter(Mandatory = $true)]
        [string]$Address,
        [Parameter(Mandatory = $true)]
        [int]$Port
    )

    $reachable = $false
    $errorText = ""
    $client = [System.Net.Sockets.TcpClient]::new($AddressFamily)
    try {
        $ipAddress = [System.Net.IPAddress]::Parse($Address)
        $connectTask = $client.ConnectAsync($ipAddress, $Port)
        if ($connectTask.Wait(3000)) {
            $reachable = $client.Connected
        }
    }
    catch {
        $errorText = $_.Exception.Message
    }
    finally {
        $client.Dispose()
    }

    return [pscustomobject][ordered]@{
        reachable = $reachable
        error = $errorText
    }
}

$inputRoot = "__INPUT_PATH__"
$outputRoot = "__OUTPUT_PATH__"
$requestPath = Join-Path $inputRoot "request.json"
$guestScriptPath = Join-Path $inputRoot "guest_lifecycle_probe.ps1"
$wsbPath = Join-Path $inputRoot "SkynetVS_Lifecycle.wsb"
$resultPath = Join-Path $outputRoot "result.json"

$request = Get-Content -LiteralPath $requestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$requestSha256 = (Get-FileHash -LiteralPath $requestPath -Algorithm SHA256).Hash.ToLowerInvariant()
$guestScriptSha256 = (Get-FileHash -LiteralPath $guestScriptPath -Algorithm SHA256).Hash.ToLowerInvariant()
$wsbSha256 = (Get-FileHash -LiteralPath $wsbPath -Algorithm SHA256).Hash.ToLowerInvariant()

$inputWriteBlocked = $false
$inputWriteError = ""
$inputWriteProbe = Join-Path $inputRoot "guest_write_probe.txt"
try {
    [System.IO.File]::WriteAllText(
        $inputWriteProbe,
        "this write must be blocked",
        [System.Text.UTF8Encoding]::new($false)
    )
    Remove-Item -LiteralPath $inputWriteProbe -Force -ErrorAction SilentlyContinue
}
catch {
    $inputWriteBlocked = $true
    $inputWriteError = $_.Exception.Message
}

$outputWritable = $false
$outputWriteError = ""
$outputWriteProbe = Join-Path $outputRoot "guest_output_probe.txt"
try {
    [System.IO.File]::WriteAllText(
        $outputWriteProbe,
        "output mapping is writable",
        [System.Text.UTF8Encoding]::new($false)
    )
    $outputWritable = Test-Path -LiteralPath $outputWriteProbe -PathType Leaf
    Remove-Item -LiteralPath $outputWriteProbe -Force -ErrorAction SilentlyContinue
}
catch {
    $outputWriteError = $_.Exception.Message
}

$ipv4DefaultRoutePresent = $false
$ipv4RouteError = ""
try {
    $ipv4Routes = @(
        Get-NetRoute -AddressFamily IPv4 -ErrorAction Stop |
            Where-Object { $_.DestinationPrefix -eq "0.0.0.0/0" }
    )
    $ipv4DefaultRoutePresent = $ipv4Routes.Count -gt 0
}
catch {
    $ipv4RouteError = $_.Exception.Message
}

$ipv6DefaultRoutePresent = $false
$ipv6RouteError = ""
try {
    $ipv6Routes = @(
        Get-NetRoute -AddressFamily IPv6 -ErrorAction Stop |
            Where-Object { $_.DestinationPrefix -eq "::/0" }
    )
    $ipv6DefaultRoutePresent = $ipv6Routes.Count -gt 0
}
catch {
    $ipv6RouteError = $_.Exception.Message
}

$ipv4Tcp = Invoke-TcpProbe -AddressFamily ([System.Net.Sockets.AddressFamily]::InterNetwork) -Address "1.1.1.1" -Port 443
$ipv6Tcp = Invoke-TcpProbe -AddressFamily ([System.Net.Sockets.AddressFamily]::InterNetworkV6) -Address "2606:4700:4700::1111" -Port 443

$requestValid = (
    [int]$request.schema_version -eq 1 -and
    [string]$request.backend_id -eq "__BACKEND_ID__" -and
    [string]$request.policy_fingerprint -eq "__POLICY_FINGERPRINT__" -and
    ([string]$request.request_id) -match "^[0-9a-f]{32}$" -and
    ([string]$request.nonce) -match "^[0-9a-f]{64}$" -and
    [string]$request.guest_script_sha256 -eq $guestScriptSha256 -and
    [string]$request.wsb_sha256 -eq $wsbSha256
)

$shutdownExe = Join-Path $env:SystemRoot "System32\shutdown.exe"
$shutdownExitCode = -1
$shutdownError = ""
try {
    $shutdownProcess = Start-Process -FilePath $shutdownExe -ArgumentList @("/s", "/t", "5", "/f") -PassThru -Wait -WindowStyle Hidden
    $shutdownExitCode = [int]$shutdownProcess.ExitCode
}
catch {
    $shutdownError = $_.Exception.Message
}

$overallOk = (
    $requestValid -and
    $inputWriteBlocked -and
    $outputWritable -and
    (-not $ipv4DefaultRoutePresent) -and
    (-not $ipv6DefaultRoutePresent) -and
    (-not [bool]$ipv4Tcp.reachable) -and
    (-not [bool]$ipv6Tcp.reachable) -and
    $ipv4RouteError -eq "" -and
    $ipv6RouteError -eq "" -and
    $shutdownExitCode -eq 0
)

$result = [ordered]@{
    schema_version = 1
    backend_id = [string]$request.backend_id
    policy_fingerprint = [string]$request.policy_fingerprint
    request_id = [string]$request.request_id
    nonce = [string]$request.nonce
    request_sha256 = $requestSha256
    guest_script_sha256 = $guestScriptSha256
    wsb_sha256 = $wsbSha256
    completed_at = (Get-Date).ToUniversalTime().ToString("o")
    overall_ok = $overallOk
    shutdown = [ordered]@{
        scheduled = $shutdownExitCode -eq 0
        exit_code = $shutdownExitCode
        error = $shutdownError
        delay_seconds = 5
    }
    guest = [ordered]@{
        computer_name = $env:COMPUTERNAME
        user_name = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
        process_architecture = [System.Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture.ToString()
        os_description = [System.Runtime.InteropServices.RuntimeInformation]::OSDescription
        powershell_version = $PSVersionTable.PSVersion.ToString()
    }
    controls = [ordered]@{
        input_mapping_present = Test-Path -LiteralPath $inputRoot -PathType Container
        input_mapping_read_only_enforced = $inputWriteBlocked
        output_mapping_present = Test-Path -LiteralPath $outputRoot -PathType Container
        output_mapping_writable = $outputWritable
        ipv4_default_route_present = $ipv4DefaultRoutePresent
        ipv4_external_tcp_reachable = [bool]$ipv4Tcp.reachable
        ipv6_default_route_present = $ipv6DefaultRoutePresent
        ipv6_external_tcp_reachable = [bool]$ipv6Tcp.reachable
    }
    diagnostics = [ordered]@{
        input_write_error = $inputWriteError
        output_write_error = $outputWriteError
        ipv4_route_error = $ipv4RouteError
        ipv6_route_error = $ipv6RouteError
        ipv4_tcp_error = [string]$ipv4Tcp.error
        ipv6_tcp_error = [string]$ipv6Tcp.error
    }
}

$tempResultPath = Join-Path $outputRoot ("result.{0}.{1}.tmp" -f $PID, [Guid]::NewGuid().ToString("N"))
$resultJson = $result | ConvertTo-Json -Depth 12 -Compress
$resultBytes = [System.Text.UTF8Encoding]::new($false).GetBytes($resultJson)
$fileStream = [System.IO.FileStream]::new(
    $tempResultPath,
    [System.IO.FileMode]::CreateNew,
    [System.IO.FileAccess]::Write,
    [System.IO.FileShare]::None,
    4096,
    [System.IO.FileOptions]::WriteThrough
)
try {
    $fileStream.Write($resultBytes, 0, $resultBytes.Length)
    $fileStream.Flush($true)
}
finally {
    $fileStream.Dispose()
}
Move-Item -LiteralPath $tempResultPath -Destination $resultPath -Force
Start-Sleep -Milliseconds 750
'''
    text = (
        template
        .replace("__INPUT_PATH__", policy.input_sandbox_path)
        .replace("__OUTPUT_PATH__", policy.output_sandbox_path)
        .replace("__BACKEND_ID__", policy.backend_id)
        .replace("__POLICY_FINGERPRINT__", policy.fingerprint)
    )
    return text.replace("\n", "\r\n").encode("ascii")


def build_lifecycle_wsb_config(
    policy: DeveloperTaskExecutionBackendPolicy,
    *,
    input_root: Path,
    output_root: Path,
) -> bytes:
    input_host = xml_escape(str(input_root), {'"': "&quot;", "'": "&apos;"})
    output_host = xml_escape(str(output_root), {'"': "&quot;", "'": "&apos;"})
    command = (
        r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe "
        r"-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass "
        rf"-File {policy.input_sandbox_path}\{LIFECYCLE_GUEST_SCRIPT_NAME}"
    )
    xml = f"""<Configuration>
  <vGPU>{policy.vgpu}</vGPU>
  <Networking>{policy.networking}</Networking>
  <AudioInput>{policy.audio_input}</AudioInput>
  <VideoInput>{policy.video_input}</VideoInput>
  <ProtectedClient>{policy.protected_client}</ProtectedClient>
  <PrinterRedirection>{policy.printer_redirection}</PrinterRedirection>
  <ClipboardRedirection>{policy.clipboard_redirection}</ClipboardRedirection>
  <MemoryInMB>{policy.memory_mb}</MemoryInMB>
  <MappedFolders>
    <MappedFolder>
      <HostFolder>{input_host}</HostFolder>
      <SandboxFolder>{policy.input_sandbox_path}</SandboxFolder>
      <ReadOnly>{str(policy.input_read_only).lower()}</ReadOnly>
    </MappedFolder>
    <MappedFolder>
      <HostFolder>{output_host}</HostFolder>
      <SandboxFolder>{policy.output_sandbox_path}</SandboxFolder>
      <ReadOnly>{str(policy.output_read_only).lower()}</ReadOnly>
    </MappedFolder>
  </MappedFolders>
  <LogonCommand>
    <Command>{xml_escape(command)}</Command>
  </LogonCommand>
</Configuration>
"""
    return xml.replace("\n", "\r\n").encode("utf-8")


def build_lifecycle_request(
    policy: DeveloperTaskExecutionBackendPolicy,
    *,
    request_id: str,
    nonce: str,
    generated_at_epoch: int,
    guest_script_sha256: str,
    wsb_sha256: str,
) -> DeveloperTaskExecutionBackendLifecycleRequest:
    request = DeveloperTaskExecutionBackendLifecycleRequest(
        schema_version=LIFECYCLE_REQUEST_SCHEMA_VERSION,
        backend_id=policy.backend_id,
        policy_fingerprint=policy.fingerprint,
        request_id=request_id,
        nonce=nonce,
        generated_at_epoch=generated_at_epoch,
        guest_script_sha256=guest_script_sha256,
        wsb_sha256=wsb_sha256,
        launch_timeout_seconds=policy.launch_timeout_seconds,
        shutdown_grace_seconds=policy.shutdown_grace_seconds,
    )
    if not _HEX_32.fullmatch(request_id):
        raise DeveloperTaskExecutionBackendLifecyclePayloadError(
            "lifecycle_request_id_invalid",
            "Lifecycle request ID must be 32 lowercase hexadecimal characters.",
            actual=request_id,
        )
    if not _HEX_64.fullmatch(nonce):
        raise DeveloperTaskExecutionBackendLifecyclePayloadError(
            "lifecycle_nonce_invalid",
            "Lifecycle nonce must be 64 lowercase hexadecimal characters.",
            actual=nonce,
        )
    if not _HEX_64.fullmatch(guest_script_sha256):
        raise DeveloperTaskExecutionBackendLifecyclePayloadError(
            "lifecycle_guest_script_hash_invalid",
            "Guest script SHA-256 is invalid.",
            actual=guest_script_sha256,
        )
    if not _HEX_64.fullmatch(wsb_sha256):
        raise DeveloperTaskExecutionBackendLifecyclePayloadError(
            "lifecycle_wsb_hash_invalid",
            "WSB configuration SHA-256 is invalid.",
            actual=wsb_sha256,
        )
    return request


def _file_version(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        stat.S_IFMT(value.st_mode),
        int(getattr(value, "st_dev", 0)),
        int(getattr(value, "st_ino", 0)),
        int(value.st_size),
        int(getattr(value, "st_mtime_ns", int(value.st_mtime * 1_000_000_000))),
    )


def read_lifecycle_result_bytes(path: Path, max_bytes: int) -> tuple[bytes, str]:
    try:
        initial = os.lstat(path)
    except FileNotFoundError as exc:
        raise DeveloperTaskExecutionBackendLifecyclePayloadError(
            "lifecycle_result_missing",
            "Lifecycle result file is missing.",
            actual=str(path),
        ) from exc
    except OSError as exc:
        raise DeveloperTaskExecutionBackendLifecyclePayloadError(
            "lifecycle_result_metadata_failed",
            "Lifecycle result metadata could not be read.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc

    if not stat.S_ISREG(initial.st_mode):
        raise DeveloperTaskExecutionBackendLifecyclePayloadError(
            "lifecycle_result_not_regular",
            "Lifecycle result must be a regular file.",
            actual=str(path),
        )
    if is_reparse_or_symlink(initial):
        raise DeveloperTaskExecutionBackendLifecyclePayloadError(
            "lifecycle_result_reparse_point",
            "Lifecycle result must not be a symlink, junction, or reparse point.",
            actual=str(path),
        )
    if initial.st_size <= 0 or initial.st_size > max_bytes:
        raise DeveloperTaskExecutionBackendLifecyclePayloadError(
            "lifecycle_result_size_invalid",
            "Lifecycle result size is outside the policy limit.",
            actual=str(initial.st_size),
        )

    flags = os.O_RDONLY | int(getattr(os, "O_BINARY", 0))
    flags |= int(getattr(os, "O_NOFOLLOW", 0))
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise DeveloperTaskExecutionBackendLifecyclePayloadError(
            "lifecycle_result_open_failed",
            "Lifecycle result could not be opened safely.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc

    content = bytearray()
    try:
        opened = os.fstat(descriptor)
        if _file_version(opened) != _file_version(initial):
            raise DeveloperTaskExecutionBackendLifecyclePayloadError(
                "lifecycle_result_changed_during_read",
                "Lifecycle result changed before reading.",
                actual=str(path),
            )
        while True:
            chunk = os.read(descriptor, min(_READ_CHUNK_BYTES, max_bytes + 1 - len(content)))
            if not chunk:
                break
            content.extend(chunk)
            if len(content) > max_bytes:
                raise DeveloperTaskExecutionBackendLifecyclePayloadError(
                    "lifecycle_result_size_invalid",
                    "Lifecycle result exceeded the policy limit while reading.",
                    actual=str(len(content)),
                )
        completed = os.fstat(descriptor)
        if _file_version(completed) != _file_version(opened):
            raise DeveloperTaskExecutionBackendLifecyclePayloadError(
                "lifecycle_result_changed_during_read",
                "Lifecycle result changed while reading.",
                actual=str(path),
            )
    except DeveloperTaskExecutionBackendLifecyclePayloadError:
        raise
    except OSError as exc:
        raise DeveloperTaskExecutionBackendLifecyclePayloadError(
            "lifecycle_result_read_failed",
            "Lifecycle result could not be read.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc
    finally:
        os.close(descriptor)

    try:
        final = os.lstat(path)
    except OSError as exc:
        raise DeveloperTaskExecutionBackendLifecyclePayloadError(
            "lifecycle_result_changed_during_read",
            "Lifecycle result disappeared after reading.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc
    if _file_version(final) != _file_version(initial):
        raise DeveloperTaskExecutionBackendLifecyclePayloadError(
            "lifecycle_result_changed_during_read",
            "Lifecycle result changed after reading.",
            actual=str(path),
        )

    raw = bytes(content)
    return raw, hashlib.sha256(raw).hexdigest()


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DeveloperTaskExecutionBackendLifecyclePayloadError(
                "lifecycle_result_duplicate_field",
                "Lifecycle result contains a duplicate JSON field.",
                actual=key,
            )
        result[key] = value
    return result


def _parse_iso_datetime(value: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DeveloperTaskExecutionBackendLifecyclePayloadError(
            "lifecycle_result_value_invalid",
            "Lifecycle result completed_at is invalid.",
            actual=value,
        ) from exc
    if parsed.tzinfo is None:
        raise DeveloperTaskExecutionBackendLifecyclePayloadError(
            "lifecycle_result_value_invalid",
            "Lifecycle result completed_at must include timezone information.",
            actual=value,
        )


def _require_exact_fields(payload: dict[str, Any], expected: set[str], section: str) -> None:
    actual = set(payload)
    if actual != expected:
        raise DeveloperTaskExecutionBackendLifecyclePayloadError(
            "lifecycle_result_fields_invalid",
            "Lifecycle result fields do not match the schema.",
            actual=(
                f"section={section};missing={sorted(expected - actual)};"
                f"unknown={sorted(actual - expected)}"
            ),
        )


def _require_type(value: Any, expected: type[Any], field_name: str) -> Any:
    if type(value) is not expected:
        raise DeveloperTaskExecutionBackendLifecyclePayloadError(
            "lifecycle_result_type_invalid",
            "Lifecycle result field has an invalid type.",
            actual=f"field={field_name};type={type(value).__name__}",
        )
    return value


def validate_lifecycle_guest_result(
    raw: bytes,
    *,
    result_sha256: str,
    request: DeveloperTaskExecutionBackendLifecycleRequest,
    request_sha256: str,
) -> DeveloperTaskExecutionBackendLifecycleGuestEvidence:
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise DeveloperTaskExecutionBackendLifecyclePayloadError(
            "lifecycle_result_encoding_invalid",
            "Lifecycle result must be strict UTF-8.",
            actual=str(exc),
        ) from exc

    try:
        payload = json.loads(text, object_pairs_hook=_strict_object)
    except DeveloperTaskExecutionBackendLifecyclePayloadError:
        raise
    except (json.JSONDecodeError, TypeError) as exc:
        raise DeveloperTaskExecutionBackendLifecyclePayloadError(
            "lifecycle_result_json_invalid",
            "Lifecycle result is not valid JSON.",
            actual=str(exc),
        ) from exc

    if type(payload) is not dict:
        raise DeveloperTaskExecutionBackendLifecyclePayloadError(
            "lifecycle_result_type_invalid",
            "Lifecycle result must be a JSON object.",
            actual=type(payload).__name__,
        )

    _require_exact_fields(payload, {
        "schema_version", "backend_id", "policy_fingerprint", "request_id",
        "nonce", "request_sha256", "guest_script_sha256", "wsb_sha256",
        "completed_at", "overall_ok", "shutdown", "guest", "controls",
        "diagnostics",
    }, "root")
    shutdown = _require_type(payload["shutdown"], dict, "shutdown")
    guest = _require_type(payload["guest"], dict, "guest")
    controls = _require_type(payload["controls"], dict, "controls")
    diagnostics = _require_type(payload["diagnostics"], dict, "diagnostics")

    _require_exact_fields(shutdown, {"scheduled", "exit_code", "error", "delay_seconds"}, "shutdown")
    _require_exact_fields(guest, {"computer_name", "user_name", "process_architecture", "os_description", "powershell_version"}, "guest")
    _require_exact_fields(controls, {
        "input_mapping_present", "input_mapping_read_only_enforced",
        "output_mapping_present", "output_mapping_writable",
        "ipv4_default_route_present", "ipv4_external_tcp_reachable",
        "ipv6_default_route_present", "ipv6_external_tcp_reachable",
    }, "controls")
    _require_exact_fields(diagnostics, {
        "input_write_error", "output_write_error", "ipv4_route_error",
        "ipv6_route_error", "ipv4_tcp_error", "ipv6_tcp_error",
    }, "diagnostics")

    values = {
        "schema_version": _require_type(payload["schema_version"], int, "schema_version"),
        "backend_id": _require_type(payload["backend_id"], str, "backend_id"),
        "policy_fingerprint": _require_type(payload["policy_fingerprint"], str, "policy_fingerprint"),
        "request_id": _require_type(payload["request_id"], str, "request_id"),
        "nonce": _require_type(payload["nonce"], str, "nonce"),
        "request_sha256": _require_type(payload["request_sha256"], str, "request_sha256"),
        "guest_script_sha256": _require_type(payload["guest_script_sha256"], str, "guest_script_sha256"),
        "wsb_sha256": _require_type(payload["wsb_sha256"], str, "wsb_sha256"),
        "completed_at": _require_type(payload["completed_at"], str, "completed_at"),
        "overall_ok": _require_type(payload["overall_ok"], bool, "overall_ok"),
    }
    _parse_iso_datetime(values["completed_at"])

    expected_pairs = {
        "schema_version": (values["schema_version"], LIFECYCLE_RESULT_SCHEMA_VERSION),
        "backend_id": (values["backend_id"], request.backend_id),
        "policy_fingerprint": (values["policy_fingerprint"], request.policy_fingerprint),
        "request_id": (values["request_id"], request.request_id),
        "nonce": (values["nonce"], request.nonce),
        "request_sha256": (values["request_sha256"], request_sha256),
        "guest_script_sha256": (values["guest_script_sha256"], request.guest_script_sha256),
        "wsb_sha256": (values["wsb_sha256"], request.wsb_sha256),
        "overall_ok": (values["overall_ok"], True),
    }
    mismatches = [
        name
        for name, (actual, expected) in expected_pairs.items()
        if actual != expected
    ]
    if mismatches:
        raise DeveloperTaskExecutionBackendLifecyclePayloadError(
            "lifecycle_result_evidence_mismatch",
            "Lifecycle result does not match the trusted request evidence.",
            actual=",".join(mismatches),
        )

    evidence = DeveloperTaskExecutionBackendLifecycleGuestEvidence(
        schema_version=values["schema_version"],
        backend_id=values["backend_id"],
        policy_fingerprint=values["policy_fingerprint"],
        request_id=values["request_id"],
        nonce=values["nonce"],
        request_sha256=values["request_sha256"],
        guest_script_sha256=values["guest_script_sha256"],
        wsb_sha256=values["wsb_sha256"],
        completed_at=values["completed_at"],
        guest_computer_name=_require_type(guest["computer_name"], str, "guest.computer_name"),
        guest_user_name=_require_type(guest["user_name"], str, "guest.user_name"),
        guest_architecture=_require_type(guest["process_architecture"], str, "guest.process_architecture"),
        guest_os_description=_require_type(guest["os_description"], str, "guest.os_description"),
        guest_powershell_version=_require_type(guest["powershell_version"], str, "guest.powershell_version"),
        shutdown_scheduled=_require_type(shutdown["scheduled"], bool, "shutdown.scheduled"),
        shutdown_exit_code=_require_type(shutdown["exit_code"], int, "shutdown.exit_code"),
        shutdown_delay_seconds=_require_type(shutdown["delay_seconds"], int, "shutdown.delay_seconds"),
        input_mapping_present=_require_type(controls["input_mapping_present"], bool, "controls.input_mapping_present"),
        input_mapping_read_only_enforced=_require_type(controls["input_mapping_read_only_enforced"], bool, "controls.input_mapping_read_only_enforced"),
        output_mapping_present=_require_type(controls["output_mapping_present"], bool, "controls.output_mapping_present"),
        output_mapping_writable=_require_type(controls["output_mapping_writable"], bool, "controls.output_mapping_writable"),
        ipv4_default_route_present=_require_type(controls["ipv4_default_route_present"], bool, "controls.ipv4_default_route_present"),
        ipv4_external_tcp_reachable=_require_type(controls["ipv4_external_tcp_reachable"], bool, "controls.ipv4_external_tcp_reachable"),
        ipv6_default_route_present=_require_type(controls["ipv6_default_route_present"], bool, "controls.ipv6_default_route_present"),
        ipv6_external_tcp_reachable=_require_type(controls["ipv6_external_tcp_reachable"], bool, "controls.ipv6_external_tcp_reachable"),
        input_write_error=_require_type(diagnostics["input_write_error"], str, "diagnostics.input_write_error"),
        output_write_error=_require_type(diagnostics["output_write_error"], str, "diagnostics.output_write_error"),
        ipv4_route_error=_require_type(diagnostics["ipv4_route_error"], str, "diagnostics.ipv4_route_error"),
        ipv6_route_error=_require_type(diagnostics["ipv6_route_error"], str, "diagnostics.ipv6_route_error"),
        ipv4_tcp_error=_require_type(diagnostics["ipv4_tcp_error"], str, "diagnostics.ipv4_tcp_error"),
        ipv6_tcp_error=_require_type(diagnostics["ipv6_tcp_error"], str, "diagnostics.ipv6_tcp_error"),
        result_size_bytes=len(raw),
        result_sha256=result_sha256,
    )

    shutdown_error = _require_type(shutdown["error"], str, "shutdown.error")
    if shutdown_error:
        raise DeveloperTaskExecutionBackendLifecyclePayloadError(
            "lifecycle_result_shutdown_failed",
            "Guest self-shutdown request failed.",
            actual=shutdown_error,
        )
    if not evidence.ok:
        raise DeveloperTaskExecutionBackendLifecyclePayloadError(
            "lifecycle_result_controls_failed",
            "Lifecycle result did not prove all required trusted controls.",
            actual=json.dumps(evidence.to_dict(), sort_keys=True)[:1000],
        )
    return evidence
