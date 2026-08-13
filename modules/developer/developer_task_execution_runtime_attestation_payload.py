from __future__ import annotations

"""Deterministic V1B4C runtime-attestation payloads. This module never launches code."""

import hashlib
import html
import json
import re

from datetime import datetime, timezone
from typing import Any

from modules.developer.developer_task_execution_backend_policy import (
    WINDOWS_SANDBOX_EXECUTION_POLICY_V1,
)
from modules.developer.developer_task_execution_boundary_worker_payload import (
    WORKER_NATIVE_HELPER_BYTES,
)
from modules.developer.developer_task_execution_runtime_attestation_contract import (
    DeveloperTaskRuntimeAttestationDocument,
    RUNTIME_ATTESTATION_AUTHORIZE_MAX_BYTES,
    RUNTIME_ATTESTATION_REQUEST_MAX_BYTES,
    parse_runtime_attestation_authorize,
    parse_runtime_attestation_request,
)
from modules.developer.developer_task_execution_runtime_attestation_policy import (
    RUNTIME_ATTESTATION_AUTHORIZATION_TIMEOUT_SECONDS,
    RUNTIME_ATTESTATION_CONTROL_ROOT,
    RUNTIME_ATTESTATION_EXPECTED_RUNTIME_FILES,
    RUNTIME_ATTESTATION_ID,
    RUNTIME_ATTESTATION_INPUT_ROOT,
    RUNTIME_ATTESTATION_OUTPUT_ROOT,
    RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
    RUNTIME_ATTESTATION_READY_TIMEOUT_SECONDS,
    RUNTIME_ATTESTATION_RUNTIME_ROOT,
    RUNTIME_ATTESTATION_RUNTIME_TIMEOUT_SECONDS,
    RUNTIME_ATTESTATION_SHUTDOWN_GRACE_SECONDS,
    RUNTIME_ATTESTATION_TRUSTED_SCOPE,
    RUNTIME_ATTESTATION_WORKER_RESULT_FILE,
    RUNTIME_ATTESTATION_WORKER_RESULT_ROOT,
    TRUSTED_PYTHON_RUNTIME_ATTESTATION_POLICY_V1,
)
from modules.developer.developer_task_execution_runtime_policy import (
    RUNTIME_BUNDLE_FILE_COUNT,
    RUNTIME_BUNDLE_FINGERPRINT,
    RUNTIME_BUNDLE_POLICY_FINGERPRINT,
    RUNTIME_BUNDLE_TOTAL_BYTES,
    RUNTIME_LAUNCH_CONTRACT_FINGERPRINT,
    RUNTIME_LOCKED_PTH_SHA256,
    RUNTIME_MANIFEST_SHA256,
    RUNTIME_PROBE_SHA256,
    RUNTIME_RUNNER_SHA256,
    RUNTIME_SOURCE_FINGERPRINT,
    RUNTIME_SOURCE_PROVENANCE_POLICY_FINGERPRINT,
    RUNTIME_SOURCE_PYTHON_DLL_SHA256,
    RUNTIME_SOURCE_PYTHON_EXE_SHA256,
    RUNTIME_SOURCE_SHA256,
    RUNTIME_SOURCE_STDLIB_SHA256,
    RUNTIME_TREE_MANIFEST_SHA256,
)


RUNTIME_ATTESTATION_PAYLOAD_SCHEMA_VERSION = 1
RUNTIME_ATTESTATION_TASK_PREFIX = "SkynetVS-V1B4C-"
RUNTIME_ATTESTATION_POLICY_FILE_NAME = "runtime_attestation_policy.json"
RUNTIME_ATTESTATION_BOOTSTRAP_FILE_NAME = "bootstrap.ps1"
RUNTIME_ATTESTATION_CONTROLLER_FILE_NAME = "controller.ps1"
RUNTIME_ATTESTATION_NATIVE_HELPER_FILE_NAME = "SkynetVS_V1B4C_native_helper.cs"
RUNTIME_ATTESTATION_WSB_FILE_NAME = "SkynetVS_V1B4C.wsb"
RUNTIME_ATTESTATION_REQUEST_FILE_NAME = "request.json"
RUNTIME_ATTESTATION_READY_FILE_NAME = "ready.json"
RUNTIME_ATTESTATION_AUTHORIZE_FILE_NAME = "authorize.json"
RUNTIME_ATTESTATION_AUTHORIZE_COMMIT_FILE_NAME = "authorize.sha256"
RUNTIME_ATTESTATION_RESULT_FILE_NAME = "runtime_result.json"
RUNTIME_ATTESTATION_TERMINAL_FILE_NAME = "terminal_payload.json"
RUNTIME_ATTESTATION_SIGNATURE_FILE_NAME = "terminal_signature.bin"
RUNTIME_ATTESTATION_BOOTSTRAP_FAILURE_FILE_NAME = "bootstrap_failure.json"
RUNTIME_ATTESTATION_CONTROLLER_FAILURE_FILE_NAME = "controller_failure.json"

RUNTIME_ATTESTATION_WSB_TEMPLATE_INPUT_TOKEN = "@@SKYNETVS_INPUT_HOST@@"
RUNTIME_ATTESTATION_WSB_TEMPLATE_RUNTIME_TOKEN = "@@SKYNETVS_RUNTIME_HOST@@"
RUNTIME_ATTESTATION_WSB_TEMPLATE_CONTROL_TOKEN = "@@SKYNETVS_CONTROL_HOST@@"
RUNTIME_ATTESTATION_WSB_TEMPLATE_OUTPUT_TOKEN = "@@SKYNETVS_OUTPUT_HOST@@"

_HEX_32 = re.compile(r"^[0-9a-f]{32}$")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:\\")


class DeveloperTaskRuntimeAttestationPayloadError(ValueError):
    def __init__(self, code: str, message: str, *, actual: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.actual = actual


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _utc_text(epoch_seconds: float) -> str:
    return datetime.fromtimestamp(epoch_seconds, timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _require_hex(value: str, pattern: re.Pattern[str], name: str) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise DeveloperTaskRuntimeAttestationPayloadError(
            "runtime_attestation_identifier_invalid",
            f"{name} is invalid.",
            actual=repr(value),
        )
    return value


def runtime_attestation_policy_bytes() -> bytes:
    policy = TRUSTED_PYTHON_RUNTIME_ATTESTATION_POLICY_V1
    if not policy.ok:
        raise RuntimeError("V1B4C runtime-attestation policy failed its canonical self-check.")
    return json.dumps(
        policy.to_dict(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def build_runtime_attestation_request(
    *,
    request_id: str,
    host_nonce: str,
    created_at_epoch_seconds: float,
    policy_sha256: str,
    bootstrap_sha256: str,
    controller_sha256: str,
    native_helper_sha256: str,
    wsb_sha256: str,
) -> DeveloperTaskRuntimeAttestationDocument:
    _require_hex(request_id, _HEX_32, "request_id")
    _require_hex(host_nonce, _HEX_64, "host_nonce")
    for name, value in (
        ("policy_sha256", policy_sha256),
        ("bootstrap_sha256", bootstrap_sha256),
        ("controller_sha256", controller_sha256),
        ("native_helper_sha256", native_helper_sha256),
        ("wsb_sha256", wsb_sha256),
    ):
        _require_hex(value, _HEX_64, name)
    if type(created_at_epoch_seconds) not in (int, float) or created_at_epoch_seconds <= 0:
        raise DeveloperTaskRuntimeAttestationPayloadError(
            "runtime_attestation_created_at_invalid",
            "created_at_epoch_seconds must be positive.",
            actual=repr(created_at_epoch_seconds),
        )

    payload = {
        "schema_version": RUNTIME_ATTESTATION_PAYLOAD_SCHEMA_VERSION,
        "backend_id": WINDOWS_SANDBOX_EXECUTION_POLICY_V1.backend_id,
        "backend_policy_fingerprint": WINDOWS_SANDBOX_EXECUTION_POLICY_V1.fingerprint,
        "runtime_attestation_id": RUNTIME_ATTESTATION_ID,
        "runtime_attestation_policy_fingerprint": RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
        "request_id": request_id,
        "host_nonce": host_nonce,
        "created_at_utc": _utc_text(float(created_at_epoch_seconds)),
        "ready_timeout_seconds": RUNTIME_ATTESTATION_READY_TIMEOUT_SECONDS,
        "authorization_timeout_seconds": RUNTIME_ATTESTATION_AUTHORIZATION_TIMEOUT_SECONDS,
        "runtime_timeout_seconds": RUNTIME_ATTESTATION_RUNTIME_TIMEOUT_SECONDS,
        "shutdown_grace_seconds": RUNTIME_ATTESTATION_SHUTDOWN_GRACE_SECONDS,
        "policy_sha256": policy_sha256,
        "bootstrap_sha256": bootstrap_sha256,
        "controller_sha256": controller_sha256,
        "native_helper_sha256": native_helper_sha256,
        "wsb_sha256": wsb_sha256,
        "runtime_source_sha256": RUNTIME_SOURCE_SHA256,
        "runtime_source_fingerprint": RUNTIME_SOURCE_FINGERPRINT,
        "runtime_source_provenance_policy_fingerprint": RUNTIME_SOURCE_PROVENANCE_POLICY_FINGERPRINT,
        "runtime_bundle_policy_fingerprint": RUNTIME_BUNDLE_POLICY_FINGERPRINT,
        "runtime_tree_manifest_sha256": RUNTIME_TREE_MANIFEST_SHA256,
        "runtime_manifest_sha256": RUNTIME_MANIFEST_SHA256,
        "runtime_bundle_fingerprint": RUNTIME_BUNDLE_FINGERPRINT,
        "runtime_file_count": RUNTIME_BUNDLE_FILE_COUNT,
        "runtime_total_bytes": RUNTIME_BUNDLE_TOTAL_BYTES,
        "python_executable_sha256": RUNTIME_SOURCE_PYTHON_EXE_SHA256,
        "python_dll_sha256": RUNTIME_SOURCE_PYTHON_DLL_SHA256,
        "python_pth_sha256": RUNTIME_LOCKED_PTH_SHA256,
        "stdlib_sha256": RUNTIME_SOURCE_STDLIB_SHA256,
        "runtime_probe_sha256": RUNTIME_PROBE_SHA256,
        "runtime_runner_sha256": RUNTIME_RUNNER_SHA256,
        "launch_contract_fingerprint": RUNTIME_LAUNCH_CONTRACT_FINGERPRINT,
        "trusted_scope": RUNTIME_ATTESTATION_TRUSTED_SCOPE,
        "execution_authorized": False,
    }
    raw = _canonical_json_bytes(payload)
    if len(raw) > RUNTIME_ATTESTATION_REQUEST_MAX_BYTES:
        raise DeveloperTaskRuntimeAttestationPayloadError(
            "runtime_attestation_request_size_invalid",
            "V1B4C request exceeds its contract size limit.",
            actual=str(len(raw)),
        )
    return parse_runtime_attestation_request(raw)


def build_runtime_attestation_authorize(
    *,
    request: DeveloperTaskRuntimeAttestationDocument,
    ready: DeveloperTaskRuntimeAttestationDocument,
    authorization_nonce: str,
    authorization_deadline_epoch: int,
) -> DeveloperTaskRuntimeAttestationDocument:
    if not isinstance(request, DeveloperTaskRuntimeAttestationDocument) or request.kind != "request":
        raise TypeError("request must be a V1B4C request document")
    if not isinstance(ready, DeveloperTaskRuntimeAttestationDocument) or ready.kind != "ready":
        raise TypeError("ready must be a V1B4C ready document")
    _require_hex(authorization_nonce, _HEX_64, "authorization_nonce")
    if type(authorization_deadline_epoch) is not int or authorization_deadline_epoch <= 0:
        raise DeveloperTaskRuntimeAttestationPayloadError(
            "runtime_attestation_authorization_deadline_invalid",
            "Authorization deadline is invalid.",
            actual=repr(authorization_deadline_epoch),
        )
    request_payload = request.to_dict()
    ready_payload = ready.to_dict()
    payload = {
        "schema_version": RUNTIME_ATTESTATION_PAYLOAD_SCHEMA_VERSION,
        "request_id": request_payload["request_id"],
        "host_nonce": request_payload["host_nonce"],
        "request_sha256": request.sha256,
        "ready_sha256": ready.sha256,
        "public_key_sha256": ready_payload["public_key_sha256"],
        "runtime_bundle_fingerprint": RUNTIME_BUNDLE_FINGERPRINT,
        "launch_contract_fingerprint": RUNTIME_LAUNCH_CONTRACT_FINGERPRINT,
        "authorization_nonce": authorization_nonce,
        "authorization_deadline_epoch": authorization_deadline_epoch,
        "allow_benign_runtime_probe": True,
        "execution_authorized": False,
    }
    raw = _canonical_json_bytes(payload)
    if len(raw) > RUNTIME_ATTESTATION_AUTHORIZE_MAX_BYTES:
        raise DeveloperTaskRuntimeAttestationPayloadError(
            "runtime_attestation_authorize_size_invalid",
            "V1B4C authorization exceeds its contract size limit.",
            actual=str(len(raw)),
        )
    return parse_runtime_attestation_authorize(raw)


def build_runtime_attestation_bootstrap_script() -> bytes:
    script = r'''Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$inputRoot = "C:\SkynetVSInput"
$outputRoot = "C:\SkynetVSOutput"
$requestPath = Join-Path $inputRoot "request.json"
$failurePath = Join-Path $outputRoot "bootstrap_failure.json"
$expectedTaskPrefix = "SkynetVS-V1B4C-"

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
    if ($requestId -cnotmatch '^[0-9a-f]{32}$') { throw "Request ID is invalid." }
    $expectedTaskName = $expectedTaskPrefix + $requestId.Substring(0, 8)

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
    $definition.RegistrationInfo.Description = "SkynetVS V1B4C one-time SYSTEM runtime controller"
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
    $action.Arguments = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "C:\SkynetVSInput\controller.ps1"'
    $action.WorkingDirectory = Join-Path $env:SystemRoot "System32"

    $registered = $root.RegisterTaskDefinition($expectedTaskName, $definition, 6, "SYSTEM", $null, 5, $null)
    $running = $registered.Run($null)
    if ($null -eq $registered -or $null -eq $running) { throw "SYSTEM runtime controller task did not start." }
}
catch {
    $failure = [ordered]@{
        schema_version = 1
        request_id = ""
        stage = "bootstrap"
        error_type = $_.Exception.GetType().Name
        error_code = "runtime_attestation_bootstrap_failed"
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
        raise RuntimeError("V1B4C bootstrap script is not canonical UTF-8/LF text.")
    return script.encode("utf-8")


def _replace_section(source: str, start_marker: str, end_marker: str, replacement: str) -> str:
    start = source.find(start_marker)
    end = source.find(end_marker, start + len(start_marker))
    if start < 0 or end < 0 or end <= start:
        raise RuntimeError(f"V1B4C native-helper source marker mismatch: {start_marker!r}")
    return source[:start] + replacement + source[end:]


def build_runtime_attestation_native_helper_source() -> bytes:
    source = WORKER_NATIVE_HELPER_BYTES.decode("utf-8", errors="strict")
    source = source.replace("public static class V1B3CNative", "public static class V1B4CNative", 1)
    source = source.replace(
        "public static class V1B4CNative\n{\n",
        r'''public static class V1B4CNative
{
    public static CngKey CreateEphemeralEcdsaP256SigningKey()
    {
        CngKeyCreationParameters creation = new CngKeyCreationParameters();
        creation.ExportPolicy = CngExportPolicies.None;
        creation.KeyUsage = CngKeyUsages.Signing;
        return CngKey.Create(
            CngAlgorithm.ECDsaP256,
            (string)null,
            creation
        );
    }

''',
        1,
    )
    source = source.replace('public const string WORKER_EXECUTABLE_FILE_NAME = "SkynetVS_V1B3C_worker_probe.exe";', 'public const string RUNTIME_EXECUTABLE_FILE_NAME = "python.exe";', 1)
    source = source.replace('return "svb3c" + requestId.Substring(0, 12);', 'return "svb4c" + requestId.Substring(0, 12);', 1)
    source = source.replace('info.usri1_comment = "SkynetVS V1B3C benign worker";', 'info.usri1_comment = "SkynetVS V1B4C trusted runtime worker";', 1)
    source = source.replace('if (!username.StartsWith("svb3c", StringComparison.Ordinal))', 'if (!username.StartsWith("svb4c", StringComparison.Ordinal))', 1)

    launch_replacement = r'''public static int GetCurrentIntegrityRid()
    {
        using (WindowsIdentity identity = WindowsIdentity.GetCurrent())
        {
            return GetTokenIntegrityRid(identity.Token);
        }
    }

    public static WorkerLaunchState LaunchFixedRuntimeProbeSuspendedInJob(IntPtr token)
    {
        const string runtimeRoot = @"C:\SkynetVSRuntime";
        const string resultRoot = @"C:\ProgramData\SkynetVS\V1B4C\worker-result";
        string runtimeExecutablePath = Path.Combine(runtimeRoot, "python.exe");
        string runnerPath = Path.Combine(runtimeRoot, "skynetvs_runtime_runner.py");
        if (!File.Exists(runtimeExecutablePath)) throw new FileNotFoundException("Pinned runtime executable is missing.", runtimeExecutablePath);
        if (!File.Exists(runnerPath)) throw new FileNotFoundException("Pinned runtime runner is missing.", runnerPath);
        if (!Directory.Exists(resultRoot)) throw new DirectoryNotFoundException(resultRoot);

        IntPtr originalEnvironment = IntPtr.Zero;
        IntPtr sanitizedEnvironment = IntPtr.Zero;
        int sanitizedEnvironmentBytes = 0;
        IntPtr job = IntPtr.Zero;
        PROCESS_INFORMATION processInformation = new PROCESS_INFORMATION();
        WorkerLaunchState state = null;
        Exception launchError = null;
        int destroyEnvironmentError = 0;
        try
        {
            sanitizedEnvironment = BuildSanitizedEnvironmentBlock(token, out originalEnvironment, out sanitizedEnvironmentBytes);
            job = CreateJobObjectW(IntPtr.Zero, null);
            if (job == IntPtr.Zero) throw new Win32Exception(Marshal.GetLastWin32Error(), "CreateJobObjectW failed.");

            JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits = new JOBOBJECT_EXTENDED_LIMIT_INFORMATION();
            limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
            int limitsSize = Marshal.SizeOf(typeof(JOBOBJECT_EXTENDED_LIMIT_INFORMATION));
            IntPtr limitsBuffer = Marshal.AllocHGlobal(limitsSize);
            try
            {
                Marshal.StructureToPtr(limits, limitsBuffer, false);
                if (!SetInformationJobObject(job, JobObjectExtendedLimitInformation, limitsBuffer, (uint)limitsSize))
                {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "SetInformationJobObject failed.");
                }
            }
            finally
            {
                Marshal.FreeHGlobal(limitsBuffer);
            }

            STARTUPINFO startup = new STARTUPINFO();
            startup.cb = Marshal.SizeOf(typeof(STARTUPINFO));
            uint creationFlags = CREATE_SUSPENDED | CREATE_DEFAULT_ERROR_MODE | CREATE_NO_WINDOW | CREATE_UNICODE_ENVIRONMENT;
            StringBuilder commandLine = new StringBuilder(BuildFixedRuntimeCommandLine(runtimeExecutablePath, runnerPath));
            if (!CreateProcessAsUserW(
                token,
                runtimeExecutablePath,
                commandLine,
                IntPtr.Zero,
                IntPtr.Zero,
                false,
                creationFlags,
                sanitizedEnvironment,
                resultRoot,
                ref startup,
                out processInformation))
            {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "CreateProcessAsUserW failed.");
            }

            if (!AssignProcessToJobObject(job, processInformation.hProcess)) throw new Win32Exception(Marshal.GetLastWin32Error(), "AssignProcessToJobObject failed.");
            bool inJob;
            if (!IsProcessInJob(processInformation.hProcess, job, out inJob)) throw new Win32Exception(Marshal.GetLastWin32Error(), "IsProcessInJob failed.");
            if (!inJob) throw new InvalidOperationException("Runtime worker process is not in the expected Job Object.");

            state = new WorkerLaunchState
            {
                ProcessHandle = processInformation.hProcess,
                ThreadHandle = processInformation.hThread,
                JobHandle = job,
                ProcessId = processInformation.dwProcessId,
                ThreadId = processInformation.dwThreadId,
                CreatedSuspended = true,
                AssignedBeforeResume = true,
                ProcessInJob = true
            };
        }
        catch (Exception error)
        {
            launchError = error;
        }
        finally
        {
            ZeroAndFreeEnvironmentBlock(sanitizedEnvironment, sanitizedEnvironmentBytes);
            if (originalEnvironment != IntPtr.Zero && !DestroyEnvironmentBlock(originalEnvironment)) destroyEnvironmentError = Marshal.GetLastWin32Error();
        }

        if (launchError != null || destroyEnvironmentError != 0)
        {
            if (processInformation.hProcess != IntPtr.Zero)
            {
                TerminateProcess(processInformation.hProcess, 0xEE);
                WaitForSingleObject(processInformation.hProcess, 5000);
            }
            if (processInformation.hThread != IntPtr.Zero) CloseHandle(processInformation.hThread);
            if (processInformation.hProcess != IntPtr.Zero) CloseHandle(processInformation.hProcess);
            if (job != IntPtr.Zero) CloseHandle(job);
            if (launchError != null) throw launchError;
            throw new Win32Exception(destroyEnvironmentError, "DestroyEnvironmentBlock failed.");
        }

        return state;
    }

    public static uint ResumeRuntimeWorker(IntPtr threadHandle)
    {
        uint previous = ResumeThread(threadHandle);
        if (previous == 0xFFFFFFFF) throw new Win32Exception(Marshal.GetLastWin32Error(), "ResumeThread failed.");
        if (previous != 1) throw new InvalidOperationException("Runtime worker primary thread was not suspended exactly once.");
        return previous;
    }

    '''
    source = _replace_section(
        source,
        "public static WorkerLaunchState LaunchFixedWorkerSuspendedInJob(",
        "public static bool IsPidInSpecificJob(",
        launch_replacement + "public static bool IsPidInSpecificJob(",
    )

    private_replacement = r'''private static string BuildFixedRuntimeCommandLine(string runtimeExecutablePath, string runnerPath)
    {
        return QuoteArgument(runtimeExecutablePath) +
            " -I -S -B -E -s -P -X utf8 " + QuoteArgument(runnerPath);
    }

    private static List<string> ReadEnvironmentBlock(IntPtr environment)
    {
        List<string> result = new List<string>();
        int charOffset = 0;
        while (true)
        {
            string entry = Marshal.PtrToStringUni(IntPtr.Add(environment, charOffset * 2));
            if (String.IsNullOrEmpty(entry)) break;
            result.Add(entry);
            charOffset += entry.Length + 1;
        }
        return result;
    }

    private static bool IsForbiddenRuntimeEnvironmentEntry(string entry)
    {
        if (String.IsNullOrEmpty(entry) || entry[0] == '=') return false;
        int separator = entry.IndexOf('=');
        string name = separator < 0 ? entry : entry.Substring(0, separator);
        string upper = name.ToUpperInvariant();
        return upper.StartsWith("PYTHON", StringComparison.Ordinal) ||
            upper.StartsWith("PIP_", StringComparison.Ordinal) ||
            upper.StartsWith("PYLAUNCHER_", StringComparison.Ordinal) ||
            String.Equals(upper, "VIRTUAL_ENV", StringComparison.Ordinal);
    }

    private static IntPtr BuildSanitizedEnvironmentBlock(IntPtr token, out IntPtr originalEnvironment, out int byteCount)
    {
        originalEnvironment = IntPtr.Zero;
        byteCount = 0;
        if (!CreateEnvironmentBlock(out originalEnvironment, token, false)) throw new Win32Exception(Marshal.GetLastWin32Error(), "CreateEnvironmentBlock failed.");
        List<string> entries = ReadEnvironmentBlock(originalEnvironment);
        List<string> sanitized = new List<string>();
        foreach (string entry in entries)
        {
            if (!IsForbiddenRuntimeEnvironmentEntry(entry)) sanitized.Add(entry);
        }
        string blockText = String.Join("\0", sanitized.ToArray()) + "\0\0";
        byte[] bytes = Encoding.Unicode.GetBytes(blockText);
        IntPtr block = Marshal.AllocHGlobal(bytes.Length);
        try
        {
            Marshal.Copy(bytes, 0, block, bytes.Length);
            byteCount = bytes.Length;
            return block;
        }
        catch
        {
            for (int index = 0; index < bytes.Length; index++) Marshal.WriteByte(block, index, 0);
            Marshal.FreeHGlobal(block);
            throw;
        }
        finally
        {
            Array.Clear(bytes, 0, bytes.Length);
        }
    }

    private static void ZeroAndFreeEnvironmentBlock(IntPtr block, int byteCount)
    {
        if (block == IntPtr.Zero) return;
        for (int index = 0; index < byteCount; index++) Marshal.WriteByte(block, index, 0);
        Marshal.FreeHGlobal(block);
    }

    private static string QuoteArgument(string value)
    {
        if (value == null) throw new ArgumentNullException("value");
        StringBuilder quoted = new StringBuilder();
        quoted.Append('"');
        int backslashes = 0;
        foreach (char character in value)
        {
            if (character == '\\')
            {
                backslashes++;
                continue;
            }
            if (character == '"')
            {
                quoted.Append('\\', (backslashes * 2) + 1);
                quoted.Append('"');
                backslashes = 0;
                continue;
            }
            if (backslashes > 0)
            {
                quoted.Append('\\', backslashes);
                backslashes = 0;
            }
            quoted.Append(character);
        }
        if (backslashes > 0) quoted.Append('\\', backslashes * 2);
        quoted.Append('"');
        return quoted.ToString();
    }

    '''
    source = _replace_section(
        source,
        "private static string BuildFixedWorkerCommandLine(",
        "private static void ValidateWorkerUserName(",
        private_replacement,
    )
    source = source.replace("public static bool IsPidInSpecificJob(public static bool IsPidInSpecificJob(", "public static bool IsPidInSpecificJob(")
    if "svb3c" in source or "LaunchFixedWorkerSuspendedInJob" in source or "BuildFixedWorkerCommandLine" in source:
        raise RuntimeError("V1B4C native-helper transformation left V1B3C launch markers.")
    if "\r" in source or not source.endswith("\n"):
        raise RuntimeError("V1B4C native helper is not canonical UTF-8/LF text.")
    return source.encode("utf-8")


def _runtime_files_powershell_literal() -> str:
    rows = []
    for item in RUNTIME_ATTESTATION_EXPECTED_RUNTIME_FILES:
        rows.append(
            '    [ordered]@{ path = "' + item.path + '"; size_bytes = ' + str(item.size_bytes) + '; sha256 = "' + item.sha256 + '" }'
        )
    return ",\n".join(rows)


def build_runtime_attestation_controller_script() -> bytes:
    expected_files = _runtime_files_powershell_literal()
    script = r'''Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$BackendId = "@@BACKEND_ID@@"
$BackendPolicyFingerprint = "@@BACKEND_POLICY_FINGERPRINT@@"
$RuntimeAttestationId = "@@ATTESTATION_ID@@"
$RuntimeAttestationPolicyFingerprint = "@@ATTESTATION_POLICY_FINGERPRINT@@"
$ExpectedNativeHelperSha256 = "@@NATIVE_HELPER_SHA256@@"
$ExpectedRuntimeSourceSha256 = "@@RUNTIME_SOURCE_SHA256@@"
$ExpectedRuntimeSourceFingerprint = "@@RUNTIME_SOURCE_FINGERPRINT@@"
$ExpectedRuntimeSourceProvenancePolicyFingerprint = "@@RUNTIME_SOURCE_PROVENANCE_POLICY_FINGERPRINT@@"
$ExpectedRuntimeBundlePolicyFingerprint = "@@RUNTIME_BUNDLE_POLICY_FINGERPRINT@@"
$ExpectedRuntimeTreeManifestSha256 = "@@RUNTIME_TREE_MANIFEST_SHA256@@"
$ExpectedRuntimeManifestSha256 = "@@RUNTIME_MANIFEST_SHA256@@"
$ExpectedRuntimeBundleFingerprint = "@@RUNTIME_BUNDLE_FINGERPRINT@@"
$ExpectedPythonExeSha256 = "@@PYTHON_EXE_SHA256@@"
$ExpectedPythonDllSha256 = "@@PYTHON_DLL_SHA256@@"
$ExpectedPythonPthSha256 = "@@PYTHON_PTH_SHA256@@"
$ExpectedStdlibSha256 = "@@STDLIB_SHA256@@"
$ExpectedRuntimeProbeSha256 = "@@RUNTIME_PROBE_SHA256@@"
$ExpectedRuntimeRunnerSha256 = "@@RUNTIME_RUNNER_SHA256@@"
$ExpectedLaunchContractFingerprint = "@@LAUNCH_CONTRACT_FINGERPRINT@@"
$ExpectedRuntimeFileCount = @@RUNTIME_FILE_COUNT@@
$ExpectedRuntimeTotalBytes = @@RUNTIME_TOTAL_BYTES@@
$ExpectedTaskPrefix = "SkynetVS-V1B4C-"

$inputRoot = "C:\SkynetVSInput"
$runtimeRoot = "C:\SkynetVSRuntime"
$controlRoot = "C:\SkynetVSControl"
$outputRoot = "C:\SkynetVSOutput"
$requestPath = Join-Path $inputRoot "request.json"
$policyPath = Join-Path $inputRoot "runtime_attestation_policy.json"
$bootstrapPath = Join-Path $inputRoot "bootstrap.ps1"
$controllerPath = Join-Path $inputRoot "controller.ps1"
$nativeHelperPath = Join-Path $inputRoot "SkynetVS_V1B4C_native_helper.cs"
$wsbPath = Join-Path $inputRoot "SkynetVS_V1B4C.wsb"
$readyPath = Join-Path $outputRoot "ready.json"
$authorizeCommitPath = Join-Path $controlRoot "authorize.sha256"
$runtimeResultPublishedPath = Join-Path $outputRoot "runtime_result.json"
$terminalPayloadPath = Join-Path $outputRoot "terminal_payload.json"
$terminalSignaturePath = Join-Path $outputRoot "terminal_signature.bin"
$failurePath = Join-Path $outputRoot "controller_failure.json"
$localStageRoot = "C:\ProgramData\SkynetVS\V1B4C"
$workerResultRoot = Join-Path $localStageRoot "worker-result"
$workerResultPath = Join-Path $workerResultRoot "skynetvs_runtime_probe_result.json"
$stage = "request_validation"

$ExpectedRuntimeFiles = @(
@@EXPECTED_RUNTIME_FILES@@
)

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

function Assert-RuntimeTree {
    $actualItems = @(Get-ChildItem -LiteralPath $runtimeRoot -Force)
    if ($actualItems.Count -ne $ExpectedRuntimeFileCount) { throw "Runtime file count mismatch." }
    $actualNameSet = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    foreach ($actualItem in $actualItems) {
        if (-not $actualNameSet.Add([string]$actualItem.Name)) { throw "Runtime file name collision." }
    }
    foreach ($expected in $ExpectedRuntimeFiles) {
        if (-not $actualNameSet.Contains([string]$expected.path)) { throw ("Runtime file name mismatch: " + $expected.path) }
    }
    [int64]$totalBytes = 0
    foreach ($expected in $ExpectedRuntimeFiles) {
        $path = Join-Path $runtimeRoot ([string]$expected.path)
        $item = Get-Item -LiteralPath $path -Force
        if ($item.PSIsContainer) { throw "Runtime tree contains a directory." }
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Runtime tree contains a reparse point." }
        if ([int64]$item.Length -ne [int64]$expected.size_bytes) { throw ("Runtime file size mismatch: " + $expected.path) }
        $hash = Get-FileSha256 -Path $path
        if ($hash -cne [string]$expected.sha256) { throw ("Runtime file hash mismatch: " + $expected.path) }
        $totalBytes += [int64]$item.Length
    }
    if ($totalBytes -ne $ExpectedRuntimeTotalBytes) { throw "Runtime total byte count mismatch." }
    return $true
}

$cngKey = $null
$ecdsa = $null
$tokenState = $null
$launchState = $null
$workerUser = ""
$workerSid = ""
$workerAccountCreated = $false
$workerAccountDeleted = $false
$workerSidProcessSetEmpty = $false
$jobClosed = $false
$request = $null

try {
    $requestBytes = Read-StrictUtf8Bytes -Path $requestPath -MaximumBytes 32768
    $requestSha256 = Get-BytesSha256 -Bytes $requestBytes
    $requestText = [System.Text.UTF8Encoding]::new($false, $true).GetString($requestBytes)
    $request = $requestText | ConvertFrom-Json
    $requestId = [string]$request.request_id
    if ($requestId -cnotmatch "^[0-9a-f]{32}$") { throw "Request ID is invalid." }
    if ([int]$request.schema_version -ne 1) { throw "Request schema mismatch." }
    if ([string]$request.backend_id -cne $BackendId) { throw "Backend ID mismatch." }
    if ([string]$request.backend_policy_fingerprint -cne $BackendPolicyFingerprint) { throw "Backend policy mismatch." }
    if ([string]$request.runtime_attestation_id -cne $RuntimeAttestationId) { throw "Attestation ID mismatch." }
    if ([string]$request.runtime_attestation_policy_fingerprint -cne $RuntimeAttestationPolicyFingerprint) { throw "Attestation policy mismatch." }
    if ([string]$request.runtime_source_sha256 -cne $ExpectedRuntimeSourceSha256) { throw "Runtime source hash mismatch." }
    if ([string]$request.runtime_source_fingerprint -cne $ExpectedRuntimeSourceFingerprint) { throw "Runtime source fingerprint mismatch." }
    if ([string]$request.runtime_source_provenance_policy_fingerprint -cne $ExpectedRuntimeSourceProvenancePolicyFingerprint) { throw "Runtime provenance policy mismatch." }
    if ([string]$request.runtime_bundle_policy_fingerprint -cne $ExpectedRuntimeBundlePolicyFingerprint) { throw "Runtime bundle policy mismatch." }
    if ([string]$request.runtime_tree_manifest_sha256 -cne $ExpectedRuntimeTreeManifestSha256) { throw "Runtime tree manifest mismatch." }
    if ([string]$request.runtime_manifest_sha256 -cne $ExpectedRuntimeManifestSha256) { throw "Runtime manifest mismatch." }
    if ([string]$request.runtime_bundle_fingerprint -cne $ExpectedRuntimeBundleFingerprint) { throw "Runtime bundle fingerprint mismatch." }
    if ([int]$request.runtime_file_count -ne $ExpectedRuntimeFileCount) { throw "Runtime file count identity mismatch." }
    if ([int64]$request.runtime_total_bytes -ne $ExpectedRuntimeTotalBytes) { throw "Runtime total byte identity mismatch." }
    if ([string]$request.python_executable_sha256 -cne $ExpectedPythonExeSha256) { throw "Python executable identity mismatch." }
    if ([string]$request.python_dll_sha256 -cne $ExpectedPythonDllSha256) { throw "Python DLL identity mismatch." }
    if ([string]$request.python_pth_sha256 -cne $ExpectedPythonPthSha256) { throw "Python _pth identity mismatch." }
    if ([string]$request.stdlib_sha256 -cne $ExpectedStdlibSha256) { throw "Stdlib identity mismatch." }
    if ([string]$request.runtime_probe_sha256 -cne $ExpectedRuntimeProbeSha256) { throw "Runtime probe identity mismatch." }
    if ([string]$request.runtime_runner_sha256 -cne $ExpectedRuntimeRunnerSha256) { throw "Runtime runner identity mismatch." }
    if ([string]$request.launch_contract_fingerprint -cne $ExpectedLaunchContractFingerprint) { throw "Launch contract mismatch." }
    if ([string]$request.trusted_scope -cne "benign_trusted_runtime_probe_only" -or [bool]$request.execution_authorized) { throw "Request scope is invalid." }

    if ((Get-FileSha256 -Path $policyPath) -cne [string]$request.policy_sha256) { throw "Policy file hash mismatch." }
    if ((Get-FileSha256 -Path $bootstrapPath) -cne [string]$request.bootstrap_sha256) { throw "Bootstrap file hash mismatch." }
    if ((Get-FileSha256 -Path $controllerPath) -cne [string]$request.controller_sha256) { throw "Controller file hash mismatch." }
    if ((Get-FileSha256 -Path $nativeHelperPath) -cne $ExpectedNativeHelperSha256) { throw "Native helper hash mismatch." }
    if ($ExpectedNativeHelperSha256 -cne [string]$request.native_helper_sha256) { throw "Native helper request hash mismatch." }
    if ((Get-FileSha256 -Path $wsbPath) -cne [string]$request.wsb_sha256) { throw "WSB file hash mismatch." }

    $stage = "controller_identity"
    Add-Type -Path $nativeHelperPath -ErrorAction Stop
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    $controllerSid = [string]$identity.User.Value
    $controllerName = [string]$identity.Name
    $controllerIsSystem = ($controllerSid -eq "S-1-5-18")
    $controllerIsAdmin = $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
    $controllerIntegrityRid = [V1B4CNative]::GetCurrentIntegrityRid()
    $expectedTaskName = $ExpectedTaskPrefix + $requestId.Substring(0, 8)
    $bootstrapTaskDeleted = Remove-BootstrapTask -TaskName $expectedTaskName

    $cngKey = [V1B4CNative]::CreateEphemeralEcdsaP256SigningKey()
    $ecdsa = [System.Security.Cryptography.ECDsaCng]::new($cngKey)
    $publicBlob = $cngKey.Export([System.Security.Cryptography.CngKeyBlobFormat]::EccPublicBlob)
    $publicKeySha256 = Get-BytesSha256 -Bytes $publicBlob
    $keyIsEphemeral = [bool]$cngKey.IsEphemeral
    $keyName = [string]$cngKey.KeyName
    $keyUniqueName = [string]$cngKey.UniqueName

    $stage = "runtime_identity"
    $runtimeIdentityVerified = Assert-RuntimeTree
    $inputWriteBlocked = Test-WriteBlocked -Root $inputRoot -Name "controller_input_write_probe.txt"
    $runtimeWriteBlocked = Test-WriteBlocked -Root $runtimeRoot -Name ".skynetvs_controller_runtime_write_probe"
    $controlWriteBlocked = Test-WriteBlocked -Root $controlRoot -Name "controller_control_write_probe.txt"
    $outputWritable = Test-OutputWritable -Root $outputRoot

    $readyChecks = [ordered]@{
        controller_is_system = $controllerIsSystem
        controller_is_administrator = $controllerIsAdmin
        controller_integrity_is_system = ($controllerIntegrityRid -ge 0x4000)
        key_is_ephemeral = $keyIsEphemeral
        key_name_empty = [string]::IsNullOrEmpty($keyName)
        key_unique_name_empty = [string]::IsNullOrEmpty($keyUniqueName)
        runtime_identity_verified = $runtimeIdentityVerified
        input_write_blocked = $inputWriteBlocked
        runtime_write_blocked = $runtimeWriteBlocked
        control_write_blocked = $controlWriteBlocked
        output_writable = $outputWritable
    }
    $failedReadyChecks = @($readyChecks.GetEnumerator() | Where-Object { -not [bool]$_.Value } | ForEach-Object { [string]$_.Key })
    if (-not $bootstrapTaskDeleted) { $failedReadyChecks += "bootstrap_task_deleted" }

    $ready = [ordered]@{
        schema_version = 1
        backend_id = $BackendId
        backend_policy_fingerprint = $BackendPolicyFingerprint
        runtime_attestation_id = $RuntimeAttestationId
        runtime_attestation_policy_fingerprint = $RuntimeAttestationPolicyFingerprint
        request_id = $requestId
        host_nonce = [string]$request.host_nonce
        request_sha256 = $requestSha256
        policy_sha256 = Get-FileSha256 -Path $policyPath
        bootstrap_sha256 = Get-FileSha256 -Path $bootstrapPath
        controller_sha256 = Get-FileSha256 -Path $controllerPath
        native_helper_sha256 = Get-FileSha256 -Path $nativeHelperPath
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
        runtime_source_sha256 = $ExpectedRuntimeSourceSha256
        runtime_source_fingerprint = $ExpectedRuntimeSourceFingerprint
        runtime_source_provenance_policy_fingerprint = $ExpectedRuntimeSourceProvenancePolicyFingerprint
        runtime_bundle_policy_fingerprint = $ExpectedRuntimeBundlePolicyFingerprint
        runtime_tree_manifest_sha256 = $ExpectedRuntimeTreeManifestSha256
        runtime_manifest_sha256 = $ExpectedRuntimeManifestSha256
        runtime_bundle_fingerprint = $ExpectedRuntimeBundleFingerprint
        runtime_file_count = $ExpectedRuntimeFileCount
        runtime_total_bytes = $ExpectedRuntimeTotalBytes
        python_executable_sha256 = $ExpectedPythonExeSha256
        python_dll_sha256 = $ExpectedPythonDllSha256
        python_pth_sha256 = $ExpectedPythonPthSha256
        stdlib_sha256 = $ExpectedStdlibSha256
        runtime_probe_sha256 = $ExpectedRuntimeProbeSha256
        runtime_runner_sha256 = $ExpectedRuntimeRunnerSha256
        launch_contract_fingerprint = $ExpectedLaunchContractFingerprint
        input_write_blocked = $inputWriteBlocked
        runtime_write_blocked = $runtimeWriteBlocked
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
    $readyText = $ready | ConvertTo-Json -Depth 12 -Compress
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
            catch { $authorizationReadError = $_.Exception.Message }
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
    if ([string]$authorize.request_id -cne $requestId) { throw "Authorization request mismatch." }
    if ([string]$authorize.host_nonce -cne [string]$request.host_nonce) { throw "Authorization host nonce mismatch." }
    if ([string]$authorize.request_sha256 -cne $requestSha256) { throw "Authorization request hash mismatch." }
    if ([string]$authorize.ready_sha256 -cne $readySha256) { throw "Authorization ready hash mismatch." }
    if ([string]$authorize.public_key_sha256 -cne $publicKeySha256) { throw "Authorization public key mismatch." }
    if ([string]$authorize.runtime_bundle_fingerprint -cne $ExpectedRuntimeBundleFingerprint) { throw "Authorization runtime bundle mismatch." }
    if ([string]$authorize.launch_contract_fingerprint -cne $ExpectedLaunchContractFingerprint) { throw "Authorization launch contract mismatch." }
    if (-not [bool]$authorize.allow_benign_runtime_probe -or [bool]$authorize.execution_authorized) { throw "Authorization scope is invalid." }
    if ([int64]$authorize.authorization_deadline_epoch -lt $nowEpoch) { throw "Authorization expired." }

    $stage = "runtime_worker"
    if (Test-Path -LiteralPath $localStageRoot) { throw "Runtime worker staging root already exists." }
    New-Item -ItemType Directory -Path $workerResultRoot -Force | Out-Null
    $workerUser = [V1B4CNative]::BuildWorkerUserName($requestId)
    $tokenState = [V1B4CNative]::CreateFreshStandardUserAndLogon($workerUser)
    $workerAccountCreated = $true
    $workerSid = [string]$tokenState.UserSid
    [V1B4CNative]::PrepareWorkerResultDirectory($workerResultRoot, $workerSid)

    $launchState = [V1B4CNative]::LaunchFixedRuntimeProbeSuspendedInJob($tokenState.TokenHandle)
    $resumePreviousCount = [V1B4CNative]::ResumeRuntimeWorker($launchState.ThreadHandle)
    [V1B4CNative]::CloseHandle($launchState.ThreadHandle) | Out-Null
    $launchState.ThreadHandle = [IntPtr]::Zero
    $runtimeWait = [V1B4CNative]::WaitForSingleObject($launchState.ProcessHandle, [uint32]([int]$request.runtime_timeout_seconds * 1000))
    if ($runtimeWait -ne [V1B4CNative]::WAIT_OBJECT_0) { throw "Runtime worker did not exit within the bounded timeout." }
    [uint32]$runtimeExitCode = 0
    if (-not [V1B4CNative]::GetExitCodeProcess($launchState.ProcessHandle, [ref]$runtimeExitCode)) { throw "Runtime worker exit code could not be read." }
    $runtimeResultBytes = Read-StrictUtf8Bytes -Path $workerResultPath -MaximumBytes 32768
    $runtimeResultText = [System.Text.UTF8Encoding]::new($false, $true).GetString($runtimeResultBytes)
    $runtimeResult = $runtimeResultText | ConvertFrom-Json
    if ([int]$runtimeResult.schema_version -ne 1) { throw "Runtime result schema mismatch." }
    if ([string]$runtimeResult.probe_id -cne "skynetvs-v1b4-runtime-probe-v1") { throw "Runtime result probe identity mismatch." }
    if ([string]$runtimeResult.implementation -cne "CPython") { throw "Runtime implementation mismatch." }
    if (@($runtimeResult.version_info).Count -ne 3 -or [int]$runtimeResult.version_info[0] -ne 3 -or [int]$runtimeResult.version_info[1] -ne 13 -or [int]$runtimeResult.version_info[2] -ne 15) { throw "Runtime version mismatch." }
    if ([int]$runtimeResult.architecture_bits -ne 64) { throw "Runtime architecture bitness mismatch." }
    if (([string]$runtimeResult.machine).ToUpperInvariant() -notin @("AMD64", "X86_64")) { throw "Runtime machine mismatch." }
    if ([string]$runtimeResult.executable_name -cne "python.exe") { throw "Runtime executable mismatch." }
    if ([string]$runtimeResult.runtime_root_name -cne "SkynetVSRuntime") { throw "Runtime root mismatch." }
    if ([int]$runtimeResult.flags.isolated -ne 1 -or [int]$runtimeResult.flags.ignore_environment -ne 1 -or [int]$runtimeResult.flags.no_user_site -ne 1 -or -not [bool]$runtimeResult.flags.safe_path -or [int]$runtimeResult.flags.dont_write_bytecode -ne 1 -or [int]$runtimeResult.flags.utf8_mode -ne 1) { throw "Runtime flags mismatch." }
    if ([bool]$runtimeResult.site_imported -or [bool]$runtimeResult.pip_available -or [bool]$runtimeResult.ensurepip_available) { throw "Forbidden runtime import/package surface detected." }
    if (@($runtimeResult.python_environment_keys).Count -ne 0) { throw "Forbidden runtime environment keys detected." }
    if (-not [bool]$runtimeResult.runtime_root_write_blocked) { throw "Runtime root write was not blocked." }
    if ([bool]$runtimeResult.execution_authorized) { throw "Runtime result claims execution authorization." }
    $expectedSysPath = @("C:\SkynetVSRuntime\python313.zip", "C:\SkynetVSRuntime")
    if (@($runtimeResult.sys_path).Count -ne 2 -or [string]$runtimeResult.sys_path[0] -cne $expectedSysPath[0] -or [string]$runtimeResult.sys_path[1] -cne $expectedSysPath[1]) { throw "Runtime sys.path mismatch." }
    if ($runtimeExitCode -ne 0) { throw "Runtime worker exited unsuccessfully." }
    $runtimeResultSha256 = Get-BytesSha256 -Bytes $runtimeResultBytes
    Write-BytesAtomic -Path $runtimeResultPublishedPath -Bytes $runtimeResultBytes

    [V1B4CNative]::CloseHandle($launchState.ProcessHandle) | Out-Null
    $launchState.ProcessHandle = [IntPtr]::Zero
    [V1B4CNative]::CloseHandle($launchState.JobHandle) | Out-Null
    $launchState.JobHandle = [IntPtr]::Zero
    $jobClosed = $true
    $sweep = [V1B4CNative]::WaitForWorkerSidQuiescence($workerSid)
    $workerSidProcessSetEmpty = ($sweep.MatchingProcessIds.Length -eq 0 -and $sweep.ConsecutiveEmptyScans -ge 3)
    if (-not $workerSidProcessSetEmpty) { throw "Runtime worker SID process set is not empty." }
    [V1B4CNative]::DeleteLocalUserExact($workerUser, $workerSid)
    $workerAccountDeleted = $true

    $stage = "network_and_terminal"
    $ipv4DefaultRoutePresent = Test-DefaultRoute -Family IPv4
    $ipv6DefaultRoutePresent = Test-DefaultRoute -Family IPv6
    $ipv4TcpReachable = Invoke-TcpProbe -AddressFamily ([System.Net.Sockets.AddressFamily]::InterNetwork) -Address "1.1.1.1" -Port 443
    $ipv6TcpReachable = Invoke-TcpProbe -AddressFamily ([System.Net.Sockets.AddressFamily]::InterNetworkV6) -Address "2606:4700:4700::1111" -Port 443
    $shutdownScheduled = Schedule-Shutdown
    if (-not $shutdownScheduled) { throw "Sandbox self-shutdown could not be scheduled." }

    $terminalPayload = [ordered]@{
        schema_version = 1
        backend_id = $BackendId
        backend_policy_fingerprint = $BackendPolicyFingerprint
        runtime_attestation_id = $RuntimeAttestationId
        runtime_attestation_policy_fingerprint = $RuntimeAttestationPolicyFingerprint
        request_id = $requestId
        host_nonce = [string]$request.host_nonce
        authorization_nonce = [string]$authorize.authorization_nonce
        request_sha256 = $requestSha256
        ready_sha256 = $readySha256
        authorize_sha256 = $authorizeSha256
        policy_sha256 = Get-FileSha256 -Path $policyPath
        bootstrap_sha256 = Get-FileSha256 -Path $bootstrapPath
        controller_sha256 = Get-FileSha256 -Path $controllerPath
        native_helper_sha256 = Get-FileSha256 -Path $nativeHelperPath
        wsb_sha256 = Get-FileSha256 -Path $wsbPath
        runtime_result_sha256 = $runtimeResultSha256
        public_key_sha256 = $publicKeySha256
        runtime_bundle_fingerprint = $ExpectedRuntimeBundleFingerprint
        runtime_tree_manifest_sha256 = $ExpectedRuntimeTreeManifestSha256
        runtime_manifest_sha256 = $ExpectedRuntimeManifestSha256
        python_executable_sha256 = $ExpectedPythonExeSha256
        python_pth_sha256 = $ExpectedPythonPthSha256
        runtime_probe_sha256 = $ExpectedRuntimeProbeSha256
        runtime_runner_sha256 = $ExpectedRuntimeRunnerSha256
        launch_contract_fingerprint = $ExpectedLaunchContractFingerprint
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
            result_ok = $true
            exit_code = [int]$runtimeExitCode
            is_administrator = [bool]$tokenState.IsAdministrator
            integrity_rid = [int]$tokenState.IntegrityRid
            worker_in_job = [bool]$launchState.ProcessInJob
            job_closed = $jobClosed
            sid_process_set_empty = $workerSidProcessSetEmpty
            account_deleted = $workerAccountDeleted
        }
        controls = [ordered]@{
            input_write_blocked = $inputWriteBlocked
            runtime_write_blocked = $runtimeWriteBlocked
            control_write_blocked = $controlWriteBlocked
            output_writable = $outputWritable
            ipv4_default_route_present = $ipv4DefaultRoutePresent
            ipv4_external_tcp_reachable = $ipv4TcpReachable
            ipv6_default_route_present = $ipv6DefaultRoutePresent
            ipv6_external_tcp_reachable = $ipv6TcpReachable
        }
        runtime = [ordered]@{
            result_ok = $true
            probe_id = [string]$runtimeResult.probe_id
            implementation = [string]$runtimeResult.implementation
            version = @([int]$runtimeResult.version_info[0], [int]$runtimeResult.version_info[1], [int]$runtimeResult.version_info[2])
            architecture_bits = [int]$runtimeResult.architecture_bits
            machine = [string]$runtimeResult.machine
            runtime_root_write_blocked = [bool]$runtimeResult.runtime_root_write_blocked
            environment_clean = (@($runtimeResult.python_environment_keys).Count -eq 0)
            pip_absent = (-not [bool]$runtimeResult.pip_available)
            ensurepip_absent = (-not [bool]$runtimeResult.ensurepip_available)
            site_absent = (-not [bool]$runtimeResult.site_imported)
            sys_path_exact = $true
        }
        shutdown = [ordered]@{
            scheduled = $shutdownScheduled
            delay_seconds = 8
        }
        completed_at_utc = (Get-Date).ToUniversalTime().ToString("o")
        overall_ok = (
            $controllerIsSystem -and $controllerIsAdmin -and $keyIsEphemeral -and
            $runtimeIdentityVerified -and $workerAccountCreated -and $workerSidProcessSetEmpty -and
            $workerAccountDeleted -and $jobClosed -and (-not $ipv4DefaultRoutePresent) -and
            (-not $ipv4TcpReachable) -and (-not $ipv6DefaultRoutePresent) -and
            (-not $ipv6TcpReachable) -and $shutdownScheduled
        )
        execution_authorized = $false
    }
    if (-not [bool]$terminalPayload.overall_ok) { throw "Terminal runtime-attestation evidence failed." }
    $terminalText = $terminalPayload | ConvertTo-Json -Depth 14 -Compress
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
        error_code = "runtime_attestation_controller_stage_failed"
        worker_account_created = $workerAccountCreated
        worker_account_deleted = $workerAccountDeleted
        job_closed = $jobClosed
        completed_at_utc = (Get-Date).ToUniversalTime().ToString("o")
        execution_authorized = $false
    }
    try { Write-Utf8Atomic -Path $failurePath -Text ($failure | ConvertTo-Json -Depth 8 -Compress) } catch { }
    try {
        if ($null -ne $launchState -and $launchState.JobHandle -ne [IntPtr]::Zero) {
            [V1B4CNative]::CloseHandle($launchState.JobHandle) | Out-Null
            $launchState.JobHandle = [IntPtr]::Zero
            $jobClosed = $true
        }
    }
    catch { }
    try {
        if (-not [string]::IsNullOrEmpty($workerSid)) {
            [V1B4CNative]::WaitForWorkerSidQuiescence($workerSid) | Out-Null
            $workerSidProcessSetEmpty = $true
        }
    }
    catch { }
    try {
        if ($workerAccountCreated -and $workerSidProcessSetEmpty -and -not $workerAccountDeleted) {
            [V1B4CNative]::DeleteLocalUserExact($workerUser, $workerSid)
            $workerAccountDeleted = $true
        }
    }
    catch { }
    Schedule-Shutdown | Out-Null
}
finally {
    try { if ($null -ne $launchState -and $launchState.ThreadHandle -ne [IntPtr]::Zero) { [V1B4CNative]::CloseHandle($launchState.ThreadHandle) | Out-Null } } catch { }
    try { if ($null -ne $launchState -and $launchState.ProcessHandle -ne [IntPtr]::Zero) { [V1B4CNative]::CloseHandle($launchState.ProcessHandle) | Out-Null } } catch { }
    try { if ($null -ne $launchState -and $launchState.JobHandle -ne [IntPtr]::Zero) { [V1B4CNative]::CloseHandle($launchState.JobHandle) | Out-Null } } catch { }
    try { if ($null -ne $tokenState -and $tokenState.TokenHandle -ne [IntPtr]::Zero) { [V1B4CNative]::CloseHandle($tokenState.TokenHandle) | Out-Null } } catch { }
    try { if ($null -ne $ecdsa) { $ecdsa.Dispose() } } catch { }
    try { if ($null -ne $cngKey) { $cngKey.Dispose() } } catch { }
    try { if (Test-Path -LiteralPath $localStageRoot) { Remove-Item -LiteralPath $localStageRoot -Recurse -Force -ErrorAction Stop } } catch { }
}
'''
    replacements = {
        "@@BACKEND_ID@@": WINDOWS_SANDBOX_EXECUTION_POLICY_V1.backend_id,
        "@@BACKEND_POLICY_FINGERPRINT@@": WINDOWS_SANDBOX_EXECUTION_POLICY_V1.fingerprint,
        "@@ATTESTATION_ID@@": RUNTIME_ATTESTATION_ID,
        "@@ATTESTATION_POLICY_FINGERPRINT@@": RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
        "@@NATIVE_HELPER_SHA256@@": _sha256(build_runtime_attestation_native_helper_source()),
        "@@RUNTIME_SOURCE_SHA256@@": RUNTIME_SOURCE_SHA256,
        "@@RUNTIME_SOURCE_FINGERPRINT@@": RUNTIME_SOURCE_FINGERPRINT,
        "@@RUNTIME_SOURCE_PROVENANCE_POLICY_FINGERPRINT@@": RUNTIME_SOURCE_PROVENANCE_POLICY_FINGERPRINT,
        "@@RUNTIME_BUNDLE_POLICY_FINGERPRINT@@": RUNTIME_BUNDLE_POLICY_FINGERPRINT,
        "@@RUNTIME_TREE_MANIFEST_SHA256@@": RUNTIME_TREE_MANIFEST_SHA256,
        "@@RUNTIME_MANIFEST_SHA256@@": RUNTIME_MANIFEST_SHA256,
        "@@RUNTIME_BUNDLE_FINGERPRINT@@": RUNTIME_BUNDLE_FINGERPRINT,
        "@@PYTHON_EXE_SHA256@@": RUNTIME_SOURCE_PYTHON_EXE_SHA256,
        "@@PYTHON_DLL_SHA256@@": RUNTIME_SOURCE_PYTHON_DLL_SHA256,
        "@@PYTHON_PTH_SHA256@@": RUNTIME_LOCKED_PTH_SHA256,
        "@@STDLIB_SHA256@@": RUNTIME_SOURCE_STDLIB_SHA256,
        "@@RUNTIME_PROBE_SHA256@@": RUNTIME_PROBE_SHA256,
        "@@RUNTIME_RUNNER_SHA256@@": RUNTIME_RUNNER_SHA256,
        "@@LAUNCH_CONTRACT_FINGERPRINT@@": RUNTIME_LAUNCH_CONTRACT_FINGERPRINT,
        "@@RUNTIME_FILE_COUNT@@": str(RUNTIME_BUNDLE_FILE_COUNT),
        "@@RUNTIME_TOTAL_BYTES@@": str(RUNTIME_BUNDLE_TOTAL_BYTES),
        "@@EXPECTED_RUNTIME_FILES@@": expected_files,
    }
    for token, value in replacements.items():
        script = script.replace(token, value)
    if "@@" in script:
        raise RuntimeError("V1B4C controller template contains unresolved tokens.")
    if "\r" in script or not script.endswith("\n"):
        raise RuntimeError("V1B4C controller script is not canonical UTF-8/LF text.")
    return script.encode("utf-8")


def build_runtime_attestation_wsb_template() -> bytes:
    return _build_wsb_xml(
        RUNTIME_ATTESTATION_WSB_TEMPLATE_INPUT_TOKEN,
        RUNTIME_ATTESTATION_WSB_TEMPLATE_RUNTIME_TOKEN,
        RUNTIME_ATTESTATION_WSB_TEMPLATE_CONTROL_TOKEN,
        RUNTIME_ATTESTATION_WSB_TEMPLATE_OUTPUT_TOKEN,
        escape_host_paths=False,
    )


def _validate_host_mapping_path(value: str, name: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value or not _WINDOWS_ABSOLUTE.match(value):
        raise DeveloperTaskRuntimeAttestationPayloadError(
            "runtime_attestation_wsb_host_path_invalid",
            f"{name} must be an absolute Windows path.",
            actual=repr(value),
        )
    if value.endswith("\\") and len(value) <= 3:
        raise DeveloperTaskRuntimeAttestationPayloadError(
            "runtime_attestation_wsb_host_path_invalid",
            f"{name} must not be a drive root.",
            actual=value,
        )
    return value.rstrip("\\")


def build_runtime_attestation_wsb_config(
    *,
    input_host_path: str,
    runtime_host_path: str,
    control_host_path: str,
    output_host_path: str,
) -> bytes:
    return _build_wsb_xml(
        _validate_host_mapping_path(input_host_path, "input_host_path"),
        _validate_host_mapping_path(runtime_host_path, "runtime_host_path"),
        _validate_host_mapping_path(control_host_path, "control_host_path"),
        _validate_host_mapping_path(output_host_path, "output_host_path"),
        escape_host_paths=True,
    )


def _build_wsb_xml(input_host: str, runtime_host: str, control_host: str, output_host: str, *, escape_host_paths: bool) -> bytes:
    def host(value: str) -> str:
        return html.escape(value, quote=True) if escape_host_paths else value

    xml = f'''<Configuration>
  <VGpu>Disable</VGpu>
  <Networking>Disable</Networking>
  <AudioInput>Disable</AudioInput>
  <VideoInput>Disable</VideoInput>
  <ProtectedClient>Enable</ProtectedClient>
  <PrinterRedirection>Disable</PrinterRedirection>
  <ClipboardRedirection>Disable</ClipboardRedirection>
  <MemoryInMB>4096</MemoryInMB>
  <MappedFolders>
    <MappedFolder>
      <HostFolder>{host(input_host)}</HostFolder>
      <SandboxFolder>{RUNTIME_ATTESTATION_INPUT_ROOT}</SandboxFolder>
      <ReadOnly>true</ReadOnly>
    </MappedFolder>
    <MappedFolder>
      <HostFolder>{host(runtime_host)}</HostFolder>
      <SandboxFolder>{RUNTIME_ATTESTATION_RUNTIME_ROOT}</SandboxFolder>
      <ReadOnly>true</ReadOnly>
    </MappedFolder>
    <MappedFolder>
      <HostFolder>{host(control_host)}</HostFolder>
      <SandboxFolder>{RUNTIME_ATTESTATION_CONTROL_ROOT}</SandboxFolder>
      <ReadOnly>true</ReadOnly>
    </MappedFolder>
    <MappedFolder>
      <HostFolder>{host(output_host)}</HostFolder>
      <SandboxFolder>{RUNTIME_ATTESTATION_OUTPUT_ROOT}</SandboxFolder>
      <ReadOnly>false</ReadOnly>
    </MappedFolder>
  </MappedFolders>
  <LogonCommand>
    <Command>powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{RUNTIME_ATTESTATION_INPUT_ROOT}\\{RUNTIME_ATTESTATION_BOOTSTRAP_FILE_NAME}"</Command>
  </LogonCommand>
</Configuration>
'''
    if "\r" in xml or not xml.endswith("\n"):
        raise RuntimeError("V1B4C WSB config is not canonical UTF-8/LF text.")
    return xml.encode("utf-8")
