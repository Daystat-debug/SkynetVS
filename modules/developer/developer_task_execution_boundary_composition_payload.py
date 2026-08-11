from __future__ import annotations

"""Deterministic payloads and exact-byte file helpers for V1B3D composition."""

import hashlib
import html
import json
import os
import re
import stat

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from modules.developer.developer_task_execution_backend_policy import (
    DeveloperTaskExecutionBackendPolicy,
)
from modules.developer.developer_task_execution_boundary_contract import (
    BOUNDARY_AUTHORIZE_MAX_BYTES,
    BOUNDARY_READY_MAX_BYTES,
    BOUNDARY_REQUEST_MAX_BYTES,
    BOUNDARY_SIGNATURE_BYTES,
    BOUNDARY_TERMINAL_PAYLOAD_MAX_BYTES,
    BOUNDARY_WORKER_RESULT_MAX_BYTES,
    DeveloperTaskExecutionBoundaryDocument,
    parse_boundary_authorize,
    parse_boundary_ready,
    parse_boundary_request,
)
from modules.developer.developer_task_execution_boundary_policy import (
    DeveloperTaskExecutionBoundaryPolicy,
)
from modules.developer.developer_task_execution_boundary_worker import (
    DeveloperTaskExecutionBoundaryWorkerBundle,
)
from modules.developer.developer_task_workspace_cleanup_fs import (
    is_reparse_or_symlink,
)


COMPOSITION_SCHEMA_VERSION = 1
COMPOSITION_ID = "v1b3d_active_signed_boundary_composition_v1"
COMPOSITION_ARTIFACT_PREFIX = "skynetvs-boundary-composition-"
COMPOSITION_TASK_PREFIX = "SkynetVS-V1B3D-"
COMPOSITION_TRUSTED_SCOPE = "benign_system_controller_worker_probe_only"
COMPOSITION_CONTROL_SANDBOX_PATH = r"C:\SkynetVS\Control"
COMPOSITION_REQUEST_NAME = "request.json"
COMPOSITION_BOOTSTRAP_NAME = "bootstrap.ps1"
COMPOSITION_CONTROLLER_NAME = "controller.ps1"
COMPOSITION_WSB_NAME = "SkynetVS_V1B3D.wsb"
COMPOSITION_POLICY_NAME = "boundary_policy.json"
COMPOSITION_AUTHORIZE_NAME = "authorize.json"
COMPOSITION_AUTHORIZE_COMMIT_NAME = "authorize.sha256"
COMPOSITION_READY_NAME = "ready.json"
COMPOSITION_WORKER_RESULT_NAME = "worker_result.json"
COMPOSITION_TERMINAL_PAYLOAD_NAME = "terminal_payload.json"
COMPOSITION_TERMINAL_SIGNATURE_NAME = "terminal_signature.bin"
COMPOSITION_BOOTSTRAP_FAILURE_NAME = "bootstrap_failure.json"
COMPOSITION_CONTROLLER_FAILURE_NAME = "controller_failure.json"
COMPOSITION_READY_TIMEOUT_SECONDS = 120
COMPOSITION_AUTHORIZATION_TIMEOUT_SECONDS = 90
COMPOSITION_WORKER_TIMEOUT_SECONDS = 60
COMPOSITION_SHUTDOWN_GRACE_SECONDS = 45
COMPOSITION_FAILURE_MAX_BYTES = 16 * 1024
_READ_CHUNK_BYTES = 64 * 1024
_HEX_32 = re.compile(r"^[0-9a-f]{32}$")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")


class DeveloperTaskExecutionBoundaryCompositionPayloadError(ValueError):
    def __init__(self, code: str, message: str, *, actual: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.actual = actual


def _sha256(data: bytes) -> str:
    if not isinstance(data, bytes):
        raise TypeError("data must be bytes")
    return hashlib.sha256(data).hexdigest()


def _canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _utc_text(epoch_seconds: float) -> str:
    return datetime.fromtimestamp(epoch_seconds, timezone.utc).isoformat(
        timespec="microseconds"
    ).replace("+00:00", "Z")


def _require_hex(value: str, pattern: re.Pattern[str], name: str) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise DeveloperTaskExecutionBoundaryCompositionPayloadError(
            "boundary_composition_identifier_invalid",
            f"{name} is invalid.",
            actual=repr(value),
        )
    return value


def build_composition_request(
    *,
    backend_policy: DeveloperTaskExecutionBackendPolicy,
    boundary_policy: DeveloperTaskExecutionBoundaryPolicy,
    request_id: str,
    host_nonce: str,
    created_at_epoch_seconds: float,
    policy_sha256: str,
    bootstrap_sha256: str,
    controller_sha256: str,
    worker_source_sha256: str,
    wsb_sha256: str,
) -> DeveloperTaskExecutionBoundaryDocument:
    _require_hex(request_id, _HEX_32, "request_id")
    _require_hex(host_nonce, _HEX_64, "host_nonce")
    for name, value in (
        ("policy_sha256", policy_sha256),
        ("bootstrap_sha256", bootstrap_sha256),
        ("controller_sha256", controller_sha256),
        ("worker_source_sha256", worker_source_sha256),
        ("wsb_sha256", wsb_sha256),
    ):
        _require_hex(value, _HEX_64, name)
    payload = {
        "schema_version": COMPOSITION_SCHEMA_VERSION,
        "backend_id": backend_policy.backend_id,
        "base_policy_fingerprint": backend_policy.fingerprint,
        "boundary_id": boundary_policy.boundary_id,
        "boundary_fingerprint": boundary_policy.fingerprint,
        "request_id": request_id,
        "host_nonce": host_nonce,
        "task_name": COMPOSITION_TASK_PREFIX + request_id[:8],
        "created_at_utc": _utc_text(created_at_epoch_seconds),
        "ready_timeout_seconds": COMPOSITION_READY_TIMEOUT_SECONDS,
        "authorization_timeout_seconds": COMPOSITION_AUTHORIZATION_TIMEOUT_SECONDS,
        "worker_timeout_seconds": COMPOSITION_WORKER_TIMEOUT_SECONDS,
        "shutdown_grace_seconds": COMPOSITION_SHUTDOWN_GRACE_SECONDS,
        "policy_sha256": policy_sha256,
        "bootstrap_sha256": bootstrap_sha256,
        "controller_sha256": controller_sha256,
        "worker_source_sha256": worker_source_sha256,
        "wsb_sha256": wsb_sha256,
        "trusted_scope": COMPOSITION_TRUSTED_SCOPE,
        "execution_authorized": False,
    }
    raw = _canonical_json_bytes(payload)
    if len(raw) > BOUNDARY_REQUEST_MAX_BYTES:
        raise DeveloperTaskExecutionBoundaryCompositionPayloadError(
            "boundary_composition_request_size_invalid",
            "V1B3D request exceeds the signed-boundary size limit.",
            actual=str(len(raw)),
        )
    return parse_boundary_request(raw)


def build_composition_authorize(
    *,
    request: DeveloperTaskExecutionBoundaryDocument,
    ready: DeveloperTaskExecutionBoundaryDocument,
    authorization_nonce: str,
    authorization_deadline_epoch: int,
) -> DeveloperTaskExecutionBoundaryDocument:
    if not isinstance(request, DeveloperTaskExecutionBoundaryDocument):
        raise TypeError("request must be DeveloperTaskExecutionBoundaryDocument")
    if not isinstance(ready, DeveloperTaskExecutionBoundaryDocument):
        raise TypeError("ready must be DeveloperTaskExecutionBoundaryDocument")
    _require_hex(authorization_nonce, _HEX_64, "authorization_nonce")
    if type(authorization_deadline_epoch) is not int or authorization_deadline_epoch <= 0:
        raise DeveloperTaskExecutionBoundaryCompositionPayloadError(
            "boundary_composition_authorization_deadline_invalid",
            "Authorization deadline is invalid.",
            actual=repr(authorization_deadline_epoch),
        )
    request_payload = request.to_dict()
    ready_payload = ready.to_dict()
    payload = {
        "schema_version": COMPOSITION_SCHEMA_VERSION,
        "request_id": request_payload["request_id"],
        "host_nonce": request_payload["host_nonce"],
        "request_sha256": request.sha256,
        "ready_sha256": ready.sha256,
        "public_key_sha256": ready_payload["public_key_sha256"],
        "worker_source_sha256": request_payload["worker_source_sha256"],
        "authorization_nonce": authorization_nonce,
        "authorization_deadline_epoch": authorization_deadline_epoch,
        "allow_benign_worker": True,
        "execution_authorized": False,
    }
    raw = _canonical_json_bytes(payload)
    if len(raw) > BOUNDARY_AUTHORIZE_MAX_BYTES:
        raise DeveloperTaskExecutionBoundaryCompositionPayloadError(
            "boundary_composition_authorize_size_invalid",
            "V1B3D authorization exceeds the signed-boundary size limit.",
            actual=str(len(raw)),
        )
    return parse_boundary_authorize(raw)


def build_composition_bootstrap_script() -> bytes:
    script = r'''Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$inputRoot = "C:\SkynetVS\Input"
$outputRoot = "C:\SkynetVS\Output"
$requestPath = Join-Path $inputRoot "request.json"
$failurePath = Join-Path $outputRoot "bootstrap_failure.json"
$expectedTaskPrefix = "SkynetVS-V1B3D-"

function Write-Utf8Atomic {
    param([string]$Path, [string]$Text)
    $temporary = $Path + ".tmp." + [Guid]::NewGuid().ToString("N")
    [System.IO.File]::WriteAllText($temporary, $Text, [System.Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $temporary -Destination $Path -Force
}

function Schedule-Shutdown {
    try {
        $shutdownExe = Join-Path $env:SystemRoot "System32\shutdown.exe"
        Start-Process -FilePath $shutdownExe -ArgumentList @("/s", "/t", "8", "/f") -WindowStyle Hidden | Out-Null
    }
    catch { }
}

try {
    $requestBytes = [System.IO.File]::ReadAllBytes($requestPath)
    $requestText = [System.Text.UTF8Encoding]::new($false, $true).GetString($requestBytes)
    $request = $requestText | ConvertFrom-Json
    $requestId = [string]$request.request_id
    if ($requestId -notmatch '^[0-9a-f]{32}$') { throw "Request ID is invalid." }
    $expectedTaskName = $expectedTaskPrefix + $requestId.Substring(0, 8)
    if ([string]$request.task_name -ne $expectedTaskName) { throw "Scheduled task name is invalid." }

    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    $isAdministrator = $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
    $isWdag = ([string]$identity.Name).EndsWith("\WDAGUtilityAccount", [System.StringComparison]::OrdinalIgnoreCase)
    if (-not $isAdministrator) { throw "WDAG bootstrap is not administrator." }
    if (-not $isWdag) { throw "Unexpected bootstrap identity." }

    $service = New-Object -ComObject "Schedule.Service"
    $service.Connect()
    $root = $service.GetFolder("\")
    $definition = $service.NewTask(0)
    $definition.RegistrationInfo.Description = "SkynetVS V1B3D one-time SYSTEM controller"
    $definition.Settings.Enabled = $true
    $definition.Settings.Hidden = $true
    $definition.Settings.AllowDemandStart = $true
    $definition.Settings.StartWhenAvailable = $true
    $definition.Settings.ExecutionTimeLimit = "PT10M"
    $definition.Principal.UserId = "SYSTEM"
    $definition.Principal.LogonType = 5
    $definition.Principal.RunLevel = 1

    $action = $definition.Actions.Create(0)
    $action.Path = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
    $action.Arguments = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "C:\SkynetVS\Input\controller.ps1"'
    $action.WorkingDirectory = Join-Path $env:SystemRoot "System32"

    $registered = $root.RegisterTaskDefinition($expectedTaskName, $definition, 6, "SYSTEM", $null, 5, $null)
    $running = $registered.Run($null)
    if ($null -eq $registered -or $null -eq $running) { throw "SYSTEM controller task did not start." }
}
catch {
    $failure = [ordered]@{
        schema_version = 1
        request_id = ""
        stage = "bootstrap"
        error_type = $_.Exception.GetType().Name
        error_code = "bootstrap_failed"
        worker_account_created = $false
        worker_account_deleted = $false
        job_closed = $false
        completed_at_utc = (Get-Date).ToUniversalTime().ToString("o")
        execution_authorized = $false
    }
    try { Write-Utf8Atomic -Path $failurePath -Text ($failure | ConvertTo-Json -Depth 6 -Compress) } catch { }
    Schedule-Shutdown
}
'''
    if "\r" in script or not script.endswith("\n"):
        raise RuntimeError("V1B3D bootstrap script is not canonical UTF-8/LF text.")
    return script.encode("utf-8")


_CONTROLLER_TEMPLATE = r'''Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$BackendId = "@@BACKEND_ID@@"
$BasePolicyFingerprint = "@@BASE_POLICY_FINGERPRINT@@"
$BoundaryId = "@@BOUNDARY_ID@@"
$BoundaryFingerprint = "@@BOUNDARY_FINGERPRINT@@"
$ExpectedNativeHelperSha256 = "@@NATIVE_HELPER_SHA256@@"
$ExpectedWorkerSourceSha256 = "@@WORKER_SOURCE_SHA256@@"
$ExpectedWorkerBundleFingerprint = "@@WORKER_BUNDLE_FINGERPRINT@@"
$ExpectedTaskPrefix = "SkynetVS-V1B3D-"

$inputRoot = "C:\SkynetVS\Input"
$controlRoot = "C:\SkynetVS\Control"
$outputRoot = "C:\SkynetVS\Output"
$requestPath = Join-Path $inputRoot "request.json"
$policyPath = Join-Path $inputRoot "boundary_policy.json"
$bootstrapPath = Join-Path $inputRoot "bootstrap.ps1"
$controllerPath = Join-Path $inputRoot "controller.ps1"
$nativeHelperPath = Join-Path $inputRoot "@@NATIVE_HELPER_FILE_NAME@@"
$workerSourcePath = Join-Path $inputRoot "@@WORKER_SOURCE_FILE_NAME@@"
$wsbPath = Join-Path $inputRoot "SkynetVS_V1B3D.wsb"
$readyPath = Join-Path $outputRoot "ready.json"
$authorizeCommitPath = Join-Path $controlRoot "authorize.sha256"
$workerResultPublishedPath = Join-Path $outputRoot "worker_result.json"
$terminalPayloadPath = Join-Path $outputRoot "terminal_payload.json"
$terminalSignaturePath = Join-Path $outputRoot "terminal_signature.bin"
$failurePath = Join-Path $outputRoot "controller_failure.json"
$stage = "request_validation"

function Write-Utf8Atomic {
    param([string]$Path, [string]$Text)
    $temporary = $Path + ".tmp." + [Guid]::NewGuid().ToString("N")
    [System.IO.File]::WriteAllText($temporary, $Text, [System.Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $temporary -Destination $Path -Force
}

function Write-BytesAtomic {
    param([string]$Path, [byte[]]$Bytes)
    $temporary = $Path + ".tmp." + [Guid]::NewGuid().ToString("N")
    [System.IO.File]::WriteAllBytes($temporary, $Bytes)
    Move-Item -LiteralPath $temporary -Destination $Path -Force
}

function Get-BytesSha256 {
    param([byte[]]$Bytes)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try { return -join ($sha.ComputeHash($Bytes) | ForEach-Object { $_.ToString("x2") }) }
    finally { $sha.Dispose() }
}

function Get-FileSha256 {
    param([string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Test-WriteBlocked {
    param([string]$Root, [string]$Name)
    $path = Join-Path $Root $Name
    try {
        [System.IO.File]::WriteAllText($path, "blocked", [System.Text.UTF8Encoding]::new($false))
        Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
        return $false
    }
    catch { return $true }
}

function Test-OutputWritable {
    param([string]$Root)
    $path = Join-Path $Root "controller_output_probe.txt"
    try {
        [System.IO.File]::WriteAllText($path, "ok", [System.Text.UTF8Encoding]::new($false))
        $exists = Test-Path -LiteralPath $path -PathType Leaf
        Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
        return $exists
    }
    catch { return $false }
}

function Invoke-TcpProbe {
    param([System.Net.Sockets.AddressFamily]$AddressFamily, [string]$Address, [int]$Port)
    $client = [System.Net.Sockets.TcpClient]::new($AddressFamily)
    $reachable = $false
    try {
        $ip = [System.Net.IPAddress]::Parse($Address)
        $task = $client.ConnectAsync($ip, $Port)
        if ($task.Wait(3000)) { $reachable = $client.Connected }
    }
    catch { }
    finally { $client.Dispose() }
    return $reachable
}

function Test-DefaultRoute {
    param([ValidateSet("IPv4", "IPv6")][string]$Family)
    $prefix = if ($Family -eq "IPv4") { "0.0.0.0/0" } else { "::/0" }
    $routes = @(Get-NetRoute -AddressFamily $Family -ErrorAction Stop | Where-Object { $_.DestinationPrefix -eq $prefix })
    return $routes.Count -gt 0
}

function Remove-BootstrapTask {
    param([string]$TaskName)
    try {
        $service = New-Object -ComObject "Schedule.Service"
        $service.Connect()
        $service.GetFolder("\").DeleteTask($TaskName, 0)
        return $true
    }
    catch { return $false }
}

function Schedule-Shutdown {
    try {
        $shutdownExe = Join-Path $env:SystemRoot "System32\shutdown.exe"
        $process = Start-Process -FilePath $shutdownExe -ArgumentList @("/s", "/t", "8", "/f") -PassThru -WindowStyle Hidden
        return $null -ne $process
    }
    catch { return $false }
}

function Read-StrictUtf8Bytes {
    param([string]$Path, [int]$MaximumBytes)
    $item = Get-Item -LiteralPath $Path -Force
    if ($item.PSIsContainer) { throw "Artifact is not a regular file." }
    if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Artifact is a reparse point." }
    if ($item.Length -le 0 -or $item.Length -gt $MaximumBytes) { throw "Artifact size is invalid." }
    $bytes = [System.IO.File]::ReadAllBytes($Path)
    [System.Text.UTF8Encoding]::new($false, $true).GetString($bytes) | Out-Null
    return $bytes
}

$cryptoSource = @"
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Security.Principal;

public static class V1B3DCrypto
{
    private const int TokenIntegrityLevel = 25;

    [StructLayout(LayoutKind.Sequential)]
    private struct SID_AND_ATTRIBUTES
    {
        public IntPtr Sid;
        public uint Attributes;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct TOKEN_MANDATORY_LABEL
    {
        public SID_AND_ATTRIBUTES Label;
    }

    [DllImport("advapi32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetTokenInformation(
        IntPtr TokenHandle,
        int TokenInformationClass,
        IntPtr TokenInformation,
        int TokenInformationLength,
        out int ReturnLength
    );

    [DllImport("advapi32.dll", SetLastError = true)]
    private static extern IntPtr GetSidSubAuthorityCount(IntPtr pSid);

    [DllImport("advapi32.dll", SetLastError = true)]
    private static extern IntPtr GetSidSubAuthority(IntPtr pSid, uint nSubAuthority);

    public static int GetCurrentIntegrityRid()
    {
        using (WindowsIdentity identity = WindowsIdentity.GetCurrent())
        {
            int required = 0;
            GetTokenInformation(
                identity.Token,
                TokenIntegrityLevel,
                IntPtr.Zero,
                0,
                out required
            );
            if (required <= 0)
            {
                throw new Win32Exception(Marshal.GetLastWin32Error());
            }

            IntPtr buffer = Marshal.AllocHGlobal(required);
            try
            {
                if (!GetTokenInformation(
                    identity.Token,
                    TokenIntegrityLevel,
                    buffer,
                    required,
                    out required
                ))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error());
                }

                TOKEN_MANDATORY_LABEL label =
                    (TOKEN_MANDATORY_LABEL)Marshal.PtrToStructure(
                        buffer,
                        typeof(TOKEN_MANDATORY_LABEL)
                    );
                byte count = Marshal.ReadByte(GetSidSubAuthorityCount(label.Label.Sid));
                if (count == 0)
                {
                    throw new InvalidOperationException("Integrity SID has no subauthority.");
                }
                return Marshal.ReadInt32(
                    GetSidSubAuthority(label.Label.Sid, (uint)(count - 1))
                );
            }
            finally
            {
                Marshal.FreeHGlobal(buffer);
            }
        }
    }

    public static CngKey CreateEphemeralEcdsaP256SigningKey()
    {
        CngKeyCreationParameters creation = new CngKeyCreationParameters();
        creation.ExportPolicy = CngExportPolicies.None;
        creation.KeyUsage = CngKeyUsages.Signing;
        return CngKey.Create(CngAlgorithm.ECDsaP256, (string)null, creation);
    }
}
"@

$request = $null
$authorize = $null
$cngKey = $null
$ecdsa = $null
$tokenState = $null
$launchState = $null
$sentinelHandle = [IntPtr]::Zero
$childProcess = $null
$workerUser = ""
$workerSid = ""
$workerAccountCreated = $false
$workerAccountDeleted = $false
$jobClosed = $false
$workerSidProcessSetEmpty = $false
$childKilledByJobClose = $false
$stageRoot = ""
$shutdownScheduled = $false

try {
    $requestBytes = Read-StrictUtf8Bytes -Path $requestPath -MaximumBytes 16384
    $requestText = [System.Text.UTF8Encoding]::new($false, $true).GetString($requestBytes)
    $request = $requestText | ConvertFrom-Json
    $requestSha256 = Get-BytesSha256 -Bytes $requestBytes
    $requestId = [string]$request.request_id
    if ($requestId -notmatch '^[0-9a-f]{32}$') { throw "Request ID is invalid." }
    if ([string]$request.task_name -ne ($ExpectedTaskPrefix + $requestId.Substring(0, 8))) { throw "Task name is invalid." }
    if ([int]$request.schema_version -ne 1) { throw "Unsupported request schema." }
    if ([string]$request.backend_id -ne $BackendId) { throw "Backend mismatch." }
    if ([string]$request.base_policy_fingerprint -ne $BasePolicyFingerprint) { throw "Base policy mismatch." }
    if ([string]$request.boundary_id -ne $BoundaryId) { throw "Boundary ID mismatch." }
    if ([string]$request.boundary_fingerprint -ne $BoundaryFingerprint) { throw "Boundary fingerprint mismatch." }
    if ([string]$request.trusted_scope -ne "benign_system_controller_worker_probe_only") { throw "Trusted scope mismatch." }
    if ([bool]$request.execution_authorized) { throw "Request cannot authorize execution." }
    if ([string]$request.policy_sha256 -ne (Get-FileSha256 -Path $policyPath)) { throw "Boundary policy hash mismatch." }
    if ([string]$request.bootstrap_sha256 -ne (Get-FileSha256 -Path $bootstrapPath)) { throw "Bootstrap hash mismatch." }
    if ([string]$request.controller_sha256 -ne (Get-FileSha256 -Path $controllerPath)) { throw "Controller hash mismatch." }
    if ([string]$request.worker_source_sha256 -ne (Get-FileSha256 -Path $workerSourcePath)) { throw "Worker source hash mismatch." }
    if ([string]$request.wsb_sha256 -ne (Get-FileSha256 -Path $wsbPath)) { throw "WSB hash mismatch." }
    if ((Get-FileSha256 -Path $nativeHelperPath) -ne $ExpectedNativeHelperSha256) { throw "Native helper hash mismatch." }
    if ((Get-FileSha256 -Path $workerSourcePath) -ne $ExpectedWorkerSourceSha256) { throw "Locked worker source hash mismatch." }

    $bootstrapTaskDeleted = Remove-BootstrapTask -TaskName ([string]$request.task_name)
    if (-not $bootstrapTaskDeleted) { throw "Bootstrap task deletion failed." }

    $stage = "controller_identity"
    Add-Type -Path $nativeHelperPath -ErrorAction Stop
    Add-Type -TypeDefinition $cryptoSource -Language CSharp -ErrorAction Stop

    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    $controllerSid = [string]$identity.User.Value
    $controllerName = [string]$identity.Name
    $controllerIsSystem = $controllerSid -eq "S-1-5-18"
    $controllerIsAdmin = $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
    $controllerIntegrityRid = [V1B3DCrypto]::GetCurrentIntegrityRid()
    if (-not $controllerIsSystem -or -not $controllerIsAdmin -or $controllerIntegrityRid -lt 0x4000) { throw "Controller identity is not SYSTEM integrity." }

    $inputWriteBlocked = Test-WriteBlocked -Root $inputRoot -Name "controller_input_write_probe.txt"
    $controlWriteBlocked = Test-WriteBlocked -Root $controlRoot -Name "controller_control_write_probe.txt"
    $outputWritable = Test-OutputWritable -Root $outputRoot
    if (-not $inputWriteBlocked -or -not $controlWriteBlocked -or -not $outputWritable) { throw "Mapped-folder controls failed." }

    $stage = "ready"
    $cngKey = [V1B3DCrypto]::CreateEphemeralEcdsaP256SigningKey()
    $ecdsa = [System.Security.Cryptography.ECDsaCng]::new($cngKey)
    $publicBlob = $cngKey.Export([System.Security.Cryptography.CngKeyBlobFormat]::EccPublicBlob)
    $publicKeySha256 = Get-BytesSha256 -Bytes $publicBlob
    $keyName = ""
    $keyUniqueName = ""
    try { $keyName = [string]$cngKey.KeyName } catch { }
    try { $keyUniqueName = [string]$cngKey.UniqueName } catch { }
    $keyIsEphemeral = [bool]$cngKey.IsEphemeral

    $readyChecks = [ordered]@{
        controller_is_system = $controllerIsSystem
        controller_is_administrator = $controllerIsAdmin
        controller_integrity_is_system = ($controllerIntegrityRid -ge 0x4000)
        key_is_ephemeral = $keyIsEphemeral
        key_name_empty = [string]::IsNullOrEmpty($keyName)
        key_unique_name_empty = [string]::IsNullOrEmpty($keyUniqueName)
        input_write_blocked = $inputWriteBlocked
        control_write_blocked = $controlWriteBlocked
        output_writable = $outputWritable
    }
    $failedReadyChecks = @($readyChecks.Keys | Where-Object { -not [bool]$readyChecks[$_] })
    $ready = [ordered]@{
        schema_version = 1
        backend_id = $BackendId
        base_policy_fingerprint = $BasePolicyFingerprint
        boundary_id = $BoundaryId
        boundary_fingerprint = $BoundaryFingerprint
        request_id = $requestId
        host_nonce = [string]$request.host_nonce
        request_sha256 = $requestSha256
        policy_sha256 = Get-FileSha256 -Path $policyPath
        bootstrap_sha256 = Get-FileSha256 -Path $bootstrapPath
        controller_sha256 = Get-FileSha256 -Path $controllerPath
        worker_source_sha256 = Get-FileSha256 -Path $workerSourcePath
        wsb_sha256 = Get-FileSha256 -Path $wsbPath
        controller_sid = $controllerSid
        controller_name = $controllerName
        controller_is_system = $controllerIsSystem
        controller_is_administrator = $controllerIsAdmin
        controller_integrity_rid = $controllerIntegrityRid
        key_is_ephemeral = $keyIsEphemeral
        key_name_empty = [string]::IsNullOrEmpty($keyName)
        key_unique_name_empty = [string]::IsNullOrEmpty($keyUniqueName)
        public_key_format = "EccPublicBlob"
        public_key_blob_base64 = [Convert]::ToBase64String($publicBlob)
        public_key_sha256 = $publicKeySha256
        input_write_blocked = $inputWriteBlocked
        control_write_blocked = $controlWriteBlocked
        output_writable = $outputWritable
        bootstrap_task_deleted = $bootstrapTaskDeleted
        ready_checks = $readyChecks
        failed_ready_checks = $failedReadyChecks
        created_at_utc = (Get-Date).ToUniversalTime().ToString("o")
        overall_ok = ($failedReadyChecks.Count -eq 0)
        execution_authorized = $false
    }
    if (-not [bool]$ready.overall_ok) { throw "Ready evidence failed." }
    $readyText = $ready | ConvertTo-Json -Depth 10 -Compress
    Write-Utf8Atomic -Path $readyPath -Text $readyText
    $readySha256 = Get-FileSha256 -Path $readyPath

    $stage = "authorization"
    $authorizePath = Join-Path $controlRoot "authorize.json"
    $authorizationDeadline = (Get-Date).AddSeconds([int]$request.authorization_timeout_seconds)
    $authorizeBytes = $null
    $authorizeSha256 = ""
    $authorizationReadError = ""
    while ((Get-Date) -lt $authorizationDeadline) {
        if (Test-Path -LiteralPath $authorizeCommitPath -PathType Leaf) {
            try {
                $commitBytes = Read-StrictUtf8Bytes -Path $authorizeCommitPath -MaximumBytes 64
                if ($commitBytes.Length -ne 64) { throw "Authorization commit size is invalid." }
                $commitText = [System.Text.UTF8Encoding]::new($false, $true).GetString($commitBytes)
                if ($commitText -cnotmatch "^[0-9a-f]{64}$") { throw "Authorization commit hash is invalid." }
                if (-not (Test-Path -LiteralPath $authorizePath -PathType Leaf)) { throw "Authorization data is missing." }
                $candidateBytes = Read-StrictUtf8Bytes -Path $authorizePath -MaximumBytes 16384
                $candidateSha256 = Get-BytesSha256 -Bytes $candidateBytes
                if ($candidateSha256 -cne $commitText) { throw "Authorization commit hash mismatch." }
                $authorizeBytes = $candidateBytes
                $authorizeSha256 = $candidateSha256
                break
            }
            catch {
                $authorizationReadError = $_.Exception.Message
            }
        }
        Start-Sleep -Milliseconds 200
    }
    if ($null -eq $authorizeBytes) {
        if ([string]::IsNullOrWhiteSpace($authorizationReadError)) { throw "Authorization was not received." }
        throw ("Authorization was not committed: " + $authorizationReadError)
    }
    $authorizeText = [System.Text.UTF8Encoding]::new($false, $true).GetString($authorizeBytes)
    $authorize = $authorizeText | ConvertFrom-Json
    $nowEpoch = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    if ([int]$authorize.schema_version -ne 1) { throw "Authorization schema mismatch." }
    if ([string]$authorize.request_id -ne $requestId) { throw "Authorization request mismatch." }
    if ([string]$authorize.host_nonce -ne [string]$request.host_nonce) { throw "Authorization host nonce mismatch." }
    if ([string]$authorize.request_sha256 -ne $requestSha256) { throw "Authorization request hash mismatch." }
    if ([string]$authorize.ready_sha256 -ne $readySha256) { throw "Authorization ready hash mismatch." }
    if ([string]$authorize.public_key_sha256 -ne $publicKeySha256) { throw "Authorization public key mismatch." }
    if ([string]$authorize.worker_source_sha256 -ne $ExpectedWorkerSourceSha256) { throw "Authorization worker source mismatch." }
    if (-not [bool]$authorize.allow_benign_worker -or [bool]$authorize.execution_authorized) { throw "Authorization scope is invalid." }
    if ([int64]$authorize.authorization_deadline_epoch -lt $nowEpoch) { throw "Authorization expired." }

    $stage = "worker_staging"
    $stageRoot = Join-Path "C:\ProgramData\SkynetVS\V1B3D" $requestId
    if (Test-Path -LiteralPath $stageRoot) { throw "Worker staging root already exists." }
    $privateRoot = Join-Path $stageRoot "private"
    $workerRoot = Join-Path $stageRoot "worker"
    $resultRoot = Join-Path $stageRoot "result"
    New-Item -ItemType Directory -Path $privateRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $workerRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $resultRoot -Force | Out-Null
    $workerExe = Join-Path $workerRoot "@@WORKER_EXECUTABLE_FILE_NAME@@"
    Add-Type -Path $workerSourcePath -OutputAssembly $workerExe -OutputType ConsoleApplication -ErrorAction Stop
    if (-not (Test-Path -LiteralPath $workerExe -PathType Leaf)) { throw "Worker executable was not compiled." }

    $stage = "worker_account"
    $workerUser = [V1B3CNative]::BuildWorkerUserName($requestId)
    $tokenState = [V1B3CNative]::CreateFreshStandardUserAndLogon($workerUser)
    $workerAccountCreated = $true
    $workerSid = [string]$tokenState.UserSid
    [V1B3CNative]::PrepareWorkerReadExecuteDirectory($stageRoot, $workerSid)
    [V1B3CNative]::ProtectControllerPrivateDirectory($privateRoot)
    [V1B3CNative]::PrepareWorkerReadExecuteDirectory($workerRoot, $workerSid)
    [V1B3CNative]::PrepareWorkerResultDirectory($resultRoot, $workerSid)

    $localWorkerResultPath = Join-Path $resultRoot "worker_result.json"
    $sentinelHandle = [V1B3CNative]::CreateInheritableSentinelEvent()
    $env:SKYNETVS_CONTROLLER_SECRET = [Guid]::NewGuid().ToString("N")

    $stage = "worker_launch"
    $launchState = [V1B3CNative]::LaunchFixedWorkerSuspendedInJob(
        $tokenState.TokenHandle,
        $workerExe,
        $workerRoot,
        $localWorkerResultPath,
        $inputRoot,
        $controlRoot,
        $requestId,
        $PID,
        $sentinelHandle.ToInt64()
    )
    $resumePreviousCount = [V1B3CNative]::ResumeWorker($launchState.ThreadHandle)
    [V1B3CNative]::CloseHandle($launchState.ThreadHandle) | Out-Null
    $launchState.ThreadHandle = [IntPtr]::Zero

    $workerWait = [V1B3CNative]::WaitForSingleObject($launchState.ProcessHandle, [uint32]([int]$request.worker_timeout_seconds * 1000))
    if ($workerWait -ne [V1B3CNative]::WAIT_OBJECT_0) { throw "Worker did not exit within the bounded timeout." }
    [uint32]$workerExitCode = 0
    if (-not [V1B3CNative]::GetExitCodeProcess($launchState.ProcessHandle, [ref]$workerExitCode)) { throw "Worker exit code could not be read." }
    $workerResultBytes = Read-StrictUtf8Bytes -Path $localWorkerResultPath -MaximumBytes 16384
    $workerResultText = [System.Text.UTF8Encoding]::new($false, $true).GetString($workerResultBytes)
    $workerResult = $workerResultText | ConvertFrom-Json
    if ([string]$workerResult.request_id -ne $requestId) { throw "Worker result request mismatch." }
    if ([string]$workerResult.worker_sid -ne $workerSid) { throw "Worker result SID mismatch." }
    if (-not [bool]$workerResult.overall_ok -or $workerExitCode -ne 0) { throw "Benign worker evidence failed." }
    $workerResultSha256 = Get-BytesSha256 -Bytes $workerResultBytes
    Write-BytesAtomic -Path $workerResultPublishedPath -Bytes $workerResultBytes

    $childPid = [int]$workerResult.child_pid
    $childInSpecificJob = [V1B3CNative]::IsPidInSpecificJob($childPid, $launchState.JobHandle)
    if (-not $childInSpecificJob) { throw "Worker child is outside the expected Job Object." }
    $childProcess = [System.Diagnostics.Process]::GetProcessById($childPid)
    $childProcess.Handle | Out-Null

    [V1B3CNative]::CloseHandle($launchState.ProcessHandle) | Out-Null
    $launchState.ProcessHandle = [IntPtr]::Zero
    [V1B3CNative]::CloseHandle($sentinelHandle) | Out-Null
    $sentinelHandle = [IntPtr]::Zero
    [V1B3CNative]::CloseHandle($launchState.JobHandle) | Out-Null
    $launchState.JobHandle = [IntPtr]::Zero
    $jobClosed = $true
    $childKilledByJobClose = $childProcess.WaitForExit(15000)
    if (-not $childKilledByJobClose) { throw "Worker child survived Job close." }

    $sweep = [V1B3CNative]::WaitForWorkerSidQuiescence($workerSid)
    $workerSidProcessSetEmpty = ($sweep.MatchingProcessIds.Length -eq 0 -and $sweep.ConsecutiveEmptyScans -ge 3)
    if (-not $workerSidProcessSetEmpty) { throw "Worker SID process set is not empty." }
    [V1B3CNative]::DeleteLocalUserExact($workerUser, $workerSid)
    $workerAccountDeleted = $true

    $stage = "network_and_terminal"
    $ipv4DefaultRoutePresent = Test-DefaultRoute -Family IPv4
    $ipv6DefaultRoutePresent = Test-DefaultRoute -Family IPv6
    $ipv4TcpReachable = Invoke-TcpProbe -AddressFamily ([System.Net.Sockets.AddressFamily]::InterNetwork) -Address "1.1.1.1" -Port 443
    $ipv6TcpReachable = Invoke-TcpProbe -AddressFamily ([System.Net.Sockets.AddressFamily]::InterNetworkV6) -Address "2606:4700:4700::1111" -Port 443

    $workerEvidenceOk = (
        (-not [bool]$workerResult.worker_is_administrator) -and
        [int]$workerResult.worker_integrity_rid -eq 0x2000 -and
        [bool]$workerResult.controller_secret_absent -and
        (-not [bool]$workerResult.sentinel_handle_inherited) -and
        [bool]$workerResult.controller_vm_read_blocked -and
        [bool]$workerResult.input_write_blocked -and
        [bool]$workerResult.control_write_blocked -and
        [bool]$workerResult.output_writable -and
        [bool]$workerResult.worker_in_job -and
        [bool]$workerResult.child_in_job
    )
    if (-not $workerEvidenceOk) { throw "Worker result contract evidence is invalid." }

    $shutdownScheduled = Schedule-Shutdown
    if (-not $shutdownScheduled) { throw "Sandbox self-shutdown could not be scheduled." }

    $terminalPayload = [ordered]@{
        schema_version = 1
        backend_id = $BackendId
        base_policy_fingerprint = $BasePolicyFingerprint
        boundary_id = $BoundaryId
        boundary_fingerprint = $BoundaryFingerprint
        request_id = $requestId
        host_nonce = [string]$request.host_nonce
        authorization_nonce = [string]$authorize.authorization_nonce
        request_sha256 = $requestSha256
        ready_sha256 = $readySha256
        authorize_sha256 = $authorizeSha256
        policy_sha256 = Get-FileSha256 -Path $policyPath
        bootstrap_sha256 = Get-FileSha256 -Path $bootstrapPath
        controller_sha256 = Get-FileSha256 -Path $controllerPath
        worker_source_sha256 = Get-FileSha256 -Path $workerSourcePath
        wsb_sha256 = Get-FileSha256 -Path $wsbPath
        worker_result_sha256 = $workerResultSha256
        public_key_sha256 = $publicKeySha256
        controller = [ordered]@{
            sid = $controllerSid
            name = $controllerName
            is_system = $controllerIsSystem
            is_administrator = $controllerIsAdmin
            integrity_rid = $controllerIntegrityRid
            key_is_ephemeral = $keyIsEphemeral
            key_name_empty = [string]::IsNullOrEmpty($keyName)
            key_unique_name_empty = [string]::IsNullOrEmpty($keyUniqueName)
        }
        worker = [ordered]@{
            account_created = $workerAccountCreated
            sid = $workerSid
            created_suspended = [bool]$launchState.CreatedSuspended
            resume_previous_count = [int]$resumePreviousCount
            assigned_before_resume = [bool]$launchState.AssignedBeforeResume
            result_ok = $workerEvidenceOk
            exit_code = [int]$workerExitCode
            is_administrator = [bool]$workerResult.worker_is_administrator
            integrity_rid = [int]$workerResult.worker_integrity_rid
            controller_secret_absent = [bool]$workerResult.controller_secret_absent
            sentinel_handle_inherited = [bool]$workerResult.sentinel_handle_inherited
            controller_vm_read_blocked = [bool]$workerResult.controller_vm_read_blocked
            worker_in_job = [bool]$workerResult.worker_in_job
            child_pid = $childPid
            child_in_job = [bool]$workerResult.child_in_job
            child_in_specific_job = $childInSpecificJob
            job_closed = $jobClosed
            child_killed_by_job_close = $childKilledByJobClose
            sid_process_set_empty = $workerSidProcessSetEmpty
            account_deleted = $workerAccountDeleted
        }
        controls = [ordered]@{
            input_write_blocked = $inputWriteBlocked
            control_write_blocked = $controlWriteBlocked
            output_writable = $outputWritable
            ipv4_default_route_present = $ipv4DefaultRoutePresent
            ipv4_external_tcp_reachable = $ipv4TcpReachable
            ipv6_default_route_present = $ipv6DefaultRoutePresent
            ipv6_external_tcp_reachable = $ipv6TcpReachable
        }
        shutdown = [ordered]@{
            scheduled = $shutdownScheduled
            delay_seconds = 8
        }
        completed_at_utc = (Get-Date).ToUniversalTime().ToString("o")
        overall_ok = (
            $controllerIsSystem -and $controllerIsAdmin -and $keyIsEphemeral -and
            $workerAccountCreated -and $workerEvidenceOk -and $childInSpecificJob -and
            $jobClosed -and $childKilledByJobClose -and $workerSidProcessSetEmpty -and
            $workerAccountDeleted -and (-not $ipv4DefaultRoutePresent) -and
            (-not $ipv4TcpReachable) -and (-not $ipv6DefaultRoutePresent) -and
            (-not $ipv6TcpReachable) -and $shutdownScheduled
        )
        execution_authorized = $false
    }
    if (-not [bool]$terminalPayload.overall_ok) { throw "Terminal composition evidence failed." }
    $terminalText = $terminalPayload | ConvertTo-Json -Depth 12 -Compress
    $terminalBytes = [System.Text.UTF8Encoding]::new($false).GetBytes($terminalText)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try { $terminalDigest = $sha.ComputeHash($terminalBytes) }
    finally { $sha.Dispose() }
    $signatureBytes = $ecdsa.SignHash($terminalDigest)
    Write-Utf8Atomic -Path $terminalPayloadPath -Text $terminalText
    Write-BytesAtomic -Path $terminalSignaturePath -Bytes $signatureBytes
}
catch {
    $failure = [ordered]@{
        schema_version = 1
        request_id = if ($null -ne $request) { [string]$request.request_id } else { "" }
        stage = $stage
        error_type = $_.Exception.GetType().Name
        error_code = "controller_stage_failed"
        worker_account_created = $workerAccountCreated
        worker_account_deleted = $workerAccountDeleted
        job_closed = $jobClosed
        completed_at_utc = (Get-Date).ToUniversalTime().ToString("o")
        execution_authorized = $false
    }
    try { Write-Utf8Atomic -Path $failurePath -Text ($failure | ConvertTo-Json -Depth 8 -Compress) } catch { }

    try {
        if ($null -ne $launchState -and $launchState.JobHandle -ne [IntPtr]::Zero) {
            [V1B3CNative]::CloseHandle($launchState.JobHandle) | Out-Null
            $launchState.JobHandle = [IntPtr]::Zero
            $jobClosed = $true
        }
    }
    catch { }
    try {
        if (-not [string]::IsNullOrEmpty($workerSid)) {
            [V1B3CNative]::WaitForWorkerSidQuiescence($workerSid) | Out-Null
            $workerSidProcessSetEmpty = $true
        }
    }
    catch { }
    try {
        if ($workerAccountCreated -and $workerSidProcessSetEmpty -and -not $workerAccountDeleted) {
            [V1B3CNative]::DeleteLocalUserExact($workerUser, $workerSid)
            $workerAccountDeleted = $true
        }
    }
    catch { }
    Schedule-Shutdown | Out-Null
}
finally {
    try { Remove-Item Env:\SKYNETVS_CONTROLLER_SECRET -ErrorAction SilentlyContinue } catch { }
    try { if ($null -ne $childProcess) { $childProcess.Dispose() } } catch { }
    try { if ($sentinelHandle -ne [IntPtr]::Zero) { [V1B3CNative]::CloseHandle($sentinelHandle) | Out-Null } } catch { }
    try { if ($null -ne $launchState -and $launchState.ThreadHandle -ne [IntPtr]::Zero) { [V1B3CNative]::CloseHandle($launchState.ThreadHandle) | Out-Null } } catch { }
    try { if ($null -ne $launchState -and $launchState.ProcessHandle -ne [IntPtr]::Zero) { [V1B3CNative]::CloseHandle($launchState.ProcessHandle) | Out-Null } } catch { }
    try { if ($null -ne $launchState -and $launchState.JobHandle -ne [IntPtr]::Zero) { [V1B3CNative]::CloseHandle($launchState.JobHandle) | Out-Null } } catch { }
    try { if ($null -ne $tokenState -and $tokenState.TokenHandle -ne [IntPtr]::Zero) { [V1B3CNative]::CloseHandle($tokenState.TokenHandle) | Out-Null } } catch { }
    try { if ($null -ne $ecdsa) { $ecdsa.Dispose() } } catch { }
    try { if ($null -ne $cngKey) { $cngKey.Dispose() } } catch { }
    try { if (-not [string]::IsNullOrEmpty($stageRoot) -and (Test-Path -LiteralPath $stageRoot)) { Remove-Item -LiteralPath $stageRoot -Recurse -Force -ErrorAction Stop } } catch { }
}
'''


def build_composition_controller_script(
    *,
    backend_policy: DeveloperTaskExecutionBackendPolicy,
    boundary_policy: DeveloperTaskExecutionBoundaryPolicy,
    worker_bundle: DeveloperTaskExecutionBoundaryWorkerBundle,
) -> bytes:
    if not isinstance(worker_bundle, DeveloperTaskExecutionBoundaryWorkerBundle):
        raise TypeError("worker_bundle must be DeveloperTaskExecutionBoundaryWorkerBundle")
    if not worker_bundle.ok:
        raise DeveloperTaskExecutionBoundaryCompositionPayloadError(
            "boundary_composition_worker_bundle_invalid",
            "V1B3D requires the canonical V1B3C worker bundle.",
        )
    replacements = {
        "@@BACKEND_ID@@": backend_policy.backend_id,
        "@@BASE_POLICY_FINGERPRINT@@": backend_policy.fingerprint,
        "@@BOUNDARY_ID@@": boundary_policy.boundary_id,
        "@@BOUNDARY_FINGERPRINT@@": boundary_policy.fingerprint,
        "@@NATIVE_HELPER_FILE_NAME@@": worker_bundle.native_helper.file_name,
        "@@NATIVE_HELPER_SHA256@@": worker_bundle.native_helper.sha256,
        "@@WORKER_SOURCE_FILE_NAME@@": worker_bundle.worker_probe.file_name,
        "@@WORKER_SOURCE_SHA256@@": worker_bundle.worker_probe.sha256,
        "@@WORKER_EXECUTABLE_FILE_NAME@@": worker_bundle.worker_executable_file_name,
        "@@WORKER_BUNDLE_FINGERPRINT@@": worker_bundle.bundle_fingerprint,
    }
    script = _CONTROLLER_TEMPLATE
    for token, value in replacements.items():
        script = script.replace(token, value)
    if "@@" in script:
        raise RuntimeError("V1B3D controller script contains an unresolved token.")
    if "\r" in script or not script.endswith("\n"):
        raise RuntimeError("V1B3D controller script is not canonical UTF-8/LF text.")
    return script.encode("utf-8")


def build_composition_wsb_config(
    backend_policy: DeveloperTaskExecutionBackendPolicy,
    *,
    input_root: Path,
    control_root: Path,
    output_root: Path,
) -> bytes:
    for name, value in (
        ("input_root", input_root),
        ("control_root", control_root),
        ("output_root", output_root),
    ):
        if not isinstance(value, Path) or not value.is_absolute():
            raise TypeError(f"{name} must be an absolute pathlib.Path")
    def escaped(path: Path) -> str:
        return html.escape(str(path), quote=False)
    command = html.escape(
        'powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "C:\\SkynetVS\\Input\\bootstrap.ps1"',
        quote=False,
    )
    xml = f'''<Configuration>
  <VGpu>{backend_policy.vgpu}</VGpu>
  <Networking>{backend_policy.networking}</Networking>
  <AudioInput>{backend_policy.audio_input}</AudioInput>
  <VideoInput>{backend_policy.video_input}</VideoInput>
  <ProtectedClient>{backend_policy.protected_client}</ProtectedClient>
  <PrinterRedirection>{backend_policy.printer_redirection}</PrinterRedirection>
  <ClipboardRedirection>{backend_policy.clipboard_redirection}</ClipboardRedirection>
  <MemoryInMB>{backend_policy.memory_mb}</MemoryInMB>
  <MappedFolders>
    <MappedFolder>
      <HostFolder>{escaped(input_root)}</HostFolder>
      <SandboxFolder>{backend_policy.input_sandbox_path}</SandboxFolder>
      <ReadOnly>true</ReadOnly>
    </MappedFolder>
    <MappedFolder>
      <HostFolder>{escaped(control_root)}</HostFolder>
      <SandboxFolder>{COMPOSITION_CONTROL_SANDBOX_PATH}</SandboxFolder>
      <ReadOnly>true</ReadOnly>
    </MappedFolder>
    <MappedFolder>
      <HostFolder>{escaped(output_root)}</HostFolder>
      <SandboxFolder>{backend_policy.output_sandbox_path}</SandboxFolder>
      <ReadOnly>false</ReadOnly>
    </MappedFolder>
  </MappedFolders>
  <LogonCommand>
    <Command>{command}</Command>
  </LogonCommand>
</Configuration>
'''
    return xml.encode("utf-8")


def _file_version(value: os.stat_result) -> tuple[int, int, int, int]:
    return (
        int(value.st_dev),
        int(value.st_ino),
        int(value.st_size),
        int(value.st_mtime_ns),
    )


def read_composition_artifact_bytes(
    path: Path,
    *,
    max_bytes: int,
    artifact_name: str,
    expected_size: int | None = None,
) -> tuple[bytes, str]:
    if not isinstance(path, Path):
        raise TypeError("path must be pathlib.Path")
    if type(max_bytes) is not int or max_bytes <= 0:
        raise TypeError("max_bytes must be a positive integer")
    if not isinstance(artifact_name, str) or not artifact_name:
        raise TypeError("artifact_name must be a non-empty string")
    try:
        initial = os.lstat(path)
    except FileNotFoundError as exc:
        raise DeveloperTaskExecutionBoundaryCompositionPayloadError(
            "boundary_composition_artifact_missing",
            "V1B3D artifact is missing.",
            actual=f"{artifact_name}:{path}",
        ) from exc
    except OSError as exc:
        raise DeveloperTaskExecutionBoundaryCompositionPayloadError(
            "boundary_composition_artifact_metadata_failed",
            "V1B3D artifact metadata could not be read.",
            actual=f"{artifact_name}:{type(exc).__name__}:{exc}",
        ) from exc
    if not stat.S_ISREG(initial.st_mode):
        raise DeveloperTaskExecutionBoundaryCompositionPayloadError(
            "boundary_composition_artifact_not_regular",
            "V1B3D artifact must be a regular file.",
            actual=artifact_name,
        )
    if is_reparse_or_symlink(initial):
        raise DeveloperTaskExecutionBoundaryCompositionPayloadError(
            "boundary_composition_artifact_reparse_point",
            "V1B3D artifact must not be a symlink, junction, or reparse point.",
            actual=artifact_name,
        )
    if initial.st_size <= 0 or initial.st_size > max_bytes:
        raise DeveloperTaskExecutionBoundaryCompositionPayloadError(
            "boundary_composition_artifact_size_invalid",
            "V1B3D artifact size is outside the allowed limit.",
            actual=f"{artifact_name}:{initial.st_size}",
        )
    if expected_size is not None and initial.st_size != expected_size:
        raise DeveloperTaskExecutionBoundaryCompositionPayloadError(
            "boundary_composition_artifact_size_invalid",
            "V1B3D artifact size does not match the exact expected size.",
            actual=f"{artifact_name}:{initial.st_size}!={expected_size}",
        )
    flags = os.O_RDONLY | int(getattr(os, "O_BINARY", 0))
    flags |= int(getattr(os, "O_NOFOLLOW", 0))
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise DeveloperTaskExecutionBoundaryCompositionPayloadError(
            "boundary_composition_artifact_open_failed",
            "V1B3D artifact could not be opened safely.",
            actual=f"{artifact_name}:{type(exc).__name__}:{exc}",
        ) from exc
    content = bytearray()
    try:
        opened = os.fstat(descriptor)
        if _file_version(opened) != _file_version(initial):
            raise DeveloperTaskExecutionBoundaryCompositionPayloadError(
                "boundary_composition_artifact_changed_during_read",
                "V1B3D artifact changed before reading.",
                actual=artifact_name,
            )
        while True:
            chunk = os.read(
                descriptor,
                min(_READ_CHUNK_BYTES, max_bytes + 1 - len(content)),
            )
            if not chunk:
                break
            content.extend(chunk)
            if len(content) > max_bytes:
                raise DeveloperTaskExecutionBoundaryCompositionPayloadError(
                    "boundary_composition_artifact_size_invalid",
                    "V1B3D artifact exceeded the allowed limit while reading.",
                    actual=artifact_name,
                )
        completed = os.fstat(descriptor)
        if _file_version(completed) != _file_version(opened):
            raise DeveloperTaskExecutionBoundaryCompositionPayloadError(
                "boundary_composition_artifact_changed_during_read",
                "V1B3D artifact changed while reading.",
                actual=artifact_name,
            )
    except DeveloperTaskExecutionBoundaryCompositionPayloadError:
        raise
    except OSError as exc:
        raise DeveloperTaskExecutionBoundaryCompositionPayloadError(
            "boundary_composition_artifact_read_failed",
            "V1B3D artifact could not be read.",
            actual=f"{artifact_name}:{type(exc).__name__}:{exc}",
        ) from exc
    finally:
        os.close(descriptor)
    try:
        final = os.lstat(path)
    except OSError as exc:
        raise DeveloperTaskExecutionBoundaryCompositionPayloadError(
            "boundary_composition_artifact_changed_during_read",
            "V1B3D artifact disappeared after reading.",
            actual=f"{artifact_name}:{type(exc).__name__}:{exc}",
        ) from exc
    if _file_version(final) != _file_version(initial):
        raise DeveloperTaskExecutionBoundaryCompositionPayloadError(
            "boundary_composition_artifact_changed_during_read",
            "V1B3D artifact changed after reading.",
            actual=artifact_name,
        )
    raw = bytes(content)
    return raw, _sha256(raw)


COMPOSITION_ARTIFACT_LIMITS = {
    COMPOSITION_REQUEST_NAME: BOUNDARY_REQUEST_MAX_BYTES,
    COMPOSITION_READY_NAME: BOUNDARY_READY_MAX_BYTES,
    COMPOSITION_AUTHORIZE_NAME: BOUNDARY_AUTHORIZE_MAX_BYTES,
    COMPOSITION_AUTHORIZE_COMMIT_NAME: 64,
    COMPOSITION_WORKER_RESULT_NAME: BOUNDARY_WORKER_RESULT_MAX_BYTES,
    COMPOSITION_TERMINAL_PAYLOAD_NAME: BOUNDARY_TERMINAL_PAYLOAD_MAX_BYTES,
    COMPOSITION_TERMINAL_SIGNATURE_NAME: BOUNDARY_SIGNATURE_BYTES,
    COMPOSITION_BOOTSTRAP_FAILURE_NAME: COMPOSITION_FAILURE_MAX_BYTES,
    COMPOSITION_CONTROLLER_FAILURE_NAME: COMPOSITION_FAILURE_MAX_BYTES,
}
