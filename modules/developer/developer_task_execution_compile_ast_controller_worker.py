from __future__ import annotations

"""V1C2C1R2 deterministic fixed SYSTEM-controller/standard-user-worker payload bundle.

This module only constructs immutable bytes.  It does not claim a plan or runtime
lease, materialize task/runtime sources, launch Windows Sandbox or execute Python.
"""

import hashlib
import json

from dataclasses import dataclass
from typing import Any

from modules.developer.developer_task_execution_compile_ast_contract_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_ACTIVE_PROCESS_LIMIT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_AUTHORIZE_MAX_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_ID,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_JOB_MEMORY_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_MAX_FILE_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_MAX_FILE_COUNT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_MAX_TOTAL_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PROCESS_MEMORY_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_REQUEST_MAX_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RESULT_MAX_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_MANIFEST_MAX_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_ROOT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_WORKER_TIMEOUT_SECONDS,
)
from modules.developer.developer_task_execution_compile_ast_controller_worker_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_DECISION_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_DECISION_ID,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_SLICE,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_SLICE_IDENTITY,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BOOTSTRAP_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BUNDLE_ID,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_CONTROLLER_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_NATIVE_HELPER_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_BYTES_SHA256,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_ID,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_TASK_PREFIX,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_USERNAME_PREFIX,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_WSB_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_V1,
    developer_task_execution_compile_ast_controller_worker_policy_bytes,
    validate_developer_task_execution_compile_ast_controller_worker_policy,
)
from modules.developer.developer_task_execution_compile_ast_plan_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT,
)
from modules.developer.developer_task_execution_compile_ast_runner import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_SHA256,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_SHA256,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_BUNDLE_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_SHA256,
)
from modules.developer.developer_task_execution_compile_ast_runner_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROL_ROOT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_INPUT_ROOT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_OUTPUT_ROOT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_REQUEST_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RESULT_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_PATH,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_EXECUTABLE,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_FLAGS,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_ROOT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_MANIFEST_FILE_NAME,
)
from modules.developer.developer_task_execution_runtime_attestation import (
    RUNTIME_ATTESTATION_PAYLOAD_BUNDLE_FINGERPRINT,
)
from modules.developer.developer_task_execution_runtime_attestation_payload import (
    build_runtime_attestation_bootstrap_script,
    build_runtime_attestation_controller_script,
    build_runtime_attestation_native_helper_source,
    build_runtime_attestation_wsb_template,
)
from modules.developer.developer_task_execution_runtime_attestation_policy import (
    RUNTIME_ATTESTATION_EXPECTED_RUNTIME_FILES,
    RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
)
from modules.developer.developer_task_execution_runtime_lease_policy import (
    RUNTIME_LEASE_POLICY_FINGERPRINT,
)
from modules.developer.developer_task_execution_runtime_policy import (
    RUNTIME_BUNDLE_FILE_COUNT,
    RUNTIME_BUNDLE_FINGERPRINT,
    RUNTIME_BUNDLE_TOTAL_BYTES,
)


# Filled after the exact builders below are frozen.  The module self-checks them
# every time the public bundle is constructed.
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BOOTSTRAP_SHA256 = (
    "7aafbabe34256c0360994b4f07b03fd809b89397f60688eb224f48f6f26bbc1d"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_NATIVE_HELPER_SHA256 = (
    "550c1d009ffcbb0ea25ad609d215237f2e5a66a20f48edc7278c314e84d7677a"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_CONTROLLER_SHA256 = (
    "335fbed28b001bcd4f11975b520d9d1e5feaec698a7a5836d946c132bebe5e23"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_WSB_TEMPLATE_SHA256 = (
    "81861905167211b29fbff7179878b6b671c31b731af482166913b5e20416375f"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BUNDLE_FINGERPRINT = (
    "449240db944a60ed51a1914f36d6c981a9579cd72e9c0e3802b6b9f3382c458c"
)


class DeveloperTaskExecutionCompileAstControllerWorkerBundleError(ValueError):
    pass


@dataclass(frozen=True)
class DeveloperTaskExecutionCompileAstControllerWorkerPayload:
    kind: str
    file_name: str
    size_bytes: int
    sha256: str
    _bytes: bytes

    def exact_bytes(self) -> bytes:
        return bytes(self._bytes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "file_name": self.file_name,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }

    def __repr__(self) -> str:
        return (
            "DeveloperTaskExecutionCompileAstControllerWorkerPayload("
            f"kind={self.kind!r}, file_name={self.file_name!r}, "
            f"size_bytes={self.size_bytes!r}, sha256={self.sha256!r})"
        )


@dataclass(frozen=True)
class DeveloperTaskExecutionCompileAstControllerWorkerBundle:
    bundle_id: str
    bundle_fingerprint: str
    policy_id: str
    policy_fingerprint: str
    architecture_decision_id: str
    architecture_decision_fingerprint: str
    architecture_slice: str
    architecture_slice_identity: str
    operation: str
    policy: DeveloperTaskExecutionCompileAstControllerWorkerPayload
    bootstrap: DeveloperTaskExecutionCompileAstControllerWorkerPayload
    native_helper: DeveloperTaskExecutionCompileAstControllerWorkerPayload
    controller: DeveloperTaskExecutionCompileAstControllerWorkerPayload
    wsb_template: DeveloperTaskExecutionCompileAstControllerWorkerPayload
    runtime_executable: str
    runtime_flags: tuple[str, ...]
    runner_path: str
    working_directory: str
    active_process_limit: int
    process_memory_bytes: int
    job_memory_bytes: int
    kill_on_close: bool
    inherit_handles: bool
    create_suspended: bool
    assign_before_resume: bool
    environment_scrub_prefixes: tuple[str, ...]
    environment_scrub_exact: tuple[str, ...]
    sandbox_launched: bool
    claim_transaction_consumed: bool
    runtime_lease_claimed: bool
    candidate_interpreter_executed: bool
    changed_source_processed: bool
    changed_source_ast_parsed: bool
    changed_source_compiled: bool
    changed_code_executed: bool
    reusable_lease_issued: bool
    execution_authorized: bool

    @property
    def ok(self) -> bool:
        return _bundle_errors(self) == ()

    @property
    def payloads(self) -> tuple[DeveloperTaskExecutionCompileAstControllerWorkerPayload, ...]:
        return (
            self.policy,
            self.bootstrap,
            self.native_helper,
            self.controller,
            self.wsb_template,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "bundle_fingerprint": self.bundle_fingerprint,
            "policy_id": self.policy_id,
            "policy_fingerprint": self.policy_fingerprint,
            "architecture_lock": {
                "decision_id": self.architecture_decision_id,
                "decision_fingerprint": self.architecture_decision_fingerprint,
                "slice": self.architecture_slice,
                "slice_identity": self.architecture_slice_identity,
            },
            "operation": self.operation,
            "payloads": [payload.to_dict() for payload in self.payloads],
            "launch": {
                "runtime_executable": self.runtime_executable,
                "runtime_flags": list(self.runtime_flags),
                "runner_path": self.runner_path,
                "working_directory": self.working_directory,
                "inherit_handles": self.inherit_handles,
                "create_suspended": self.create_suspended,
                "assign_before_resume": self.assign_before_resume,
                "shell": False,
                "caller_arguments": False,
                "caller_environment": False,
            },
            "job": {
                "active_process_limit": self.active_process_limit,
                "process_memory_bytes": self.process_memory_bytes,
                "job_memory_bytes": self.job_memory_bytes,
                "kill_on_close": self.kill_on_close,
                "breakaway_allowed": False,
                "silent_breakaway_allowed": False,
            },
            "environment": {
                "source": "CreateEnvironmentBlock_false",
                "inherit_controller_environment": False,
                "scrub_prefixes": list(self.environment_scrub_prefixes),
                "scrub_exact": list(self.environment_scrub_exact),
            },
            "boundary": {
                "sandbox_launched": self.sandbox_launched,
                "claim_transaction_consumed": self.claim_transaction_consumed,
                "runtime_lease_claimed": self.runtime_lease_claimed,
                "candidate_interpreter_executed": self.candidate_interpreter_executed,
                "changed_source_processed": self.changed_source_processed,
                "changed_source_ast_parsed": self.changed_source_ast_parsed,
                "changed_source_compiled": self.changed_source_compiled,
                "changed_code_executed": self.changed_code_executed,
                "reusable_lease_issued": self.reusable_lease_issued,
                "execution_authorized": self.execution_authorized,
            },
        }


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _canonical_source_bytes(source: str, *, label: str) -> bytes:
    if not isinstance(source, str):
        raise TypeError(f"{label} source must be text")
    source = source.replace("\r\n", "\n").replace("\r", "\n")
    if not source.endswith("\n"):
        source += "\n"
    data = source.encode("utf-8")
    if data.startswith(b"\xef\xbb\xbf") or b"\r" in data:
        raise DeveloperTaskExecutionCompileAstControllerWorkerBundleError(
            f"{label}_canonical_text_invalid"
        )
    return data


def build_developer_task_execution_compile_ast_controller_worker_bootstrap_script() -> bytes:
    source = build_runtime_attestation_bootstrap_script().decode("utf-8", errors="strict")
    replacements = {
        "SkynetVS-V1B4C-": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_TASK_PREFIX,
        "SkynetVS V1B4C one-time SYSTEM runtime controller": (
            "SkynetVS V1C2C1 one-time SYSTEM compile AST controller"
        ),
        "SYSTEM runtime controller task did not start.": (
            "SYSTEM compile AST controller task did not start."
        ),
        "runtime_attestation_bootstrap_failed": (
            "compile_ast_controller_worker_bootstrap_failed"
        ),
    }
    for old, new in replacements.items():
        source = source.replace(old, new)
    if "V1B4C" in source or "runtime_attestation_bootstrap_failed" in source:
        raise DeveloperTaskExecutionCompileAstControllerWorkerBundleError(
            "bootstrap_transformation_incomplete"
        )
    return _canonical_source_bytes(source, label="bootstrap")


def _replace_source_section(
    source: str,
    start_marker: str,
    end_marker: str,
    replacement: str,
) -> str:
    start = source.find(start_marker)
    if start < 0:
        raise DeveloperTaskExecutionCompileAstControllerWorkerBundleError(
            "native_helper_start_marker_missing"
        )
    end = source.find(end_marker, start)
    if end < 0:
        raise DeveloperTaskExecutionCompileAstControllerWorkerBundleError(
            "native_helper_end_marker_missing"
        )
    return source[:start] + replacement + source[end:]


def build_developer_task_execution_compile_ast_controller_worker_native_helper_source() -> bytes:
    source = build_runtime_attestation_native_helper_source().decode(
        "utf-8", errors="strict"
    )
    source = source.replace("V1B4CNative", "V1C2C1Native")
    source = source.replace(
        '"svb4c"',
        '"' + DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_USERNAME_PREFIX + '"',
    )
    source = source.replace(
        'info.usri1_comment = "SkynetVS V1B4C trusted runtime worker";',
        'info.usri1_comment = "SkynetVS V1C2C1 compile AST worker";',
    )
    source = source.replace(
        "public const uint JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000;",
        "\n".join(
            (
                "public const uint JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008;",
                "    public const uint JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100;",
                "    public const uint JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200;",
                "    public const uint JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000;",
                "    public const uint COMPILE_AST_ACTIVE_PROCESS_LIMIT = 1;",
                "    public const ulong COMPILE_AST_PROCESS_MEMORY_BYTES = 536870912UL;",
                "    public const ulong COMPILE_AST_JOB_MEMORY_BYTES = 805306368UL;",
            )
        ),
    )
    source = source.replace(
        "    public bool ProcessInJob;\n}",
        """    public bool ProcessInJob;
    public bool InheritHandles;
    public uint ActiveProcessLimit;
    public ulong ProcessMemoryBytes;
    public ulong JobMemoryBytes;
}
""",
    )


    shared_output_public_anchor = r'''    public static void PrepareWorkerResultDirectory(string path, string workerSid)
    {
        ApplyProtectedDirectoryAcl(
            path,
            workerSid,
            FileSystemRights.Write | FileSystemRights.ReadAttributes | FileSystemRights.ReadPermissions | FileSystemRights.Synchronize
        );
    }
'''
    shared_output_public_replacement = shared_output_public_anchor + r'''

    public static void PrepareSharedWorkerOutputDirectory(string path, string workerSid)
    {
        if (String.IsNullOrEmpty(path) || !Path.IsPathRooted(path)) throw new ArgumentException("Directory path must be absolute.", "path");
        if (!Directory.Exists(path)) throw new DirectoryNotFoundException(path);
        if (String.IsNullOrEmpty(workerSid)) throw new ArgumentException("Worker SID is required.", "workerSid");

        SecurityIdentifier worker = new SecurityIdentifier(workerSid);
        DirectorySecurity before = Directory.GetAccessControl(path, AccessControlSections.Access | AccessControlSections.Owner);
        SecurityIdentifier ownerBefore = (SecurityIdentifier)before.GetOwner(typeof(SecurityIdentifier));
        bool protectionBefore = before.AreAccessRulesProtected;
        Dictionary<string, int> rulesBefore = GetAccessRuleMultiset(before);
        if (CountRulesForSid(before, worker.Value) != 0) throw new InvalidOperationException("Fresh worker SID already has shared-output ACL entries.");

        FileSystemRights workerRights =
            FileSystemRights.Write |
            FileSystemRights.ReadAttributes |
            FileSystemRights.ReadPermissions |
            FileSystemRights.Synchronize;
        FileSystemAccessRule workerRule = new FileSystemAccessRule(
            worker,
            workerRights,
            InheritanceFlags.ContainerInherit | InheritanceFlags.ObjectInherit,
            PropagationFlags.None,
            AccessControlType.Allow
        );
        string workerRuleSignature = BuildAccessRuleSignature(workerRule);
        before.AddAccessRule(workerRule);
        Directory.SetAccessControl(path, before);

        DirectorySecurity after = Directory.GetAccessControl(path, AccessControlSections.Access | AccessControlSections.Owner);
        SecurityIdentifier ownerAfter = (SecurityIdentifier)after.GetOwner(typeof(SecurityIdentifier));
        if (!String.Equals(ownerBefore.Value, ownerAfter.Value, StringComparison.Ordinal)) throw new InvalidOperationException("Shared-output owner changed.");
        if (protectionBefore != after.AreAccessRulesProtected) throw new InvalidOperationException("Shared-output access-rule protection changed.");

        Dictionary<string, int> rulesAfterWithoutWorker = GetAccessRuleMultiset(after);
        if (!RemoveSingleRule(rulesAfterWithoutWorker, workerRuleSignature)) throw new InvalidOperationException("Exact shared-output worker ACE was not observed after ACL write.");
        if (!RuleMultisetsEqual(rulesBefore, rulesAfterWithoutWorker)) throw new InvalidOperationException("Pre-existing shared-output ACL rules changed.");
        if (CountRulesForSid(after, worker.Value) != 1) throw new InvalidOperationException("Shared-output worker SID must have exactly one ACL entry.");
    }
'''
    if shared_output_public_anchor not in source:
        raise DeveloperTaskExecutionCompileAstControllerWorkerBundleError(
            "shared_output_public_acl_anchor_missing"
        )
    source = source.replace(
        shared_output_public_anchor,
        shared_output_public_replacement,
        1,
    )

    shared_output_private_anchor = "    private static void ApplyProtectedDirectoryAcl(string path, string workerSid, FileSystemRights workerRights)\n"
    shared_output_private_helpers = r'''    private static string BuildAccessRuleSignature(FileSystemAccessRule rule)
    {
        SecurityIdentifier identity = rule.IdentityReference as SecurityIdentifier;
        if (identity == null) throw new InvalidOperationException("ACL identity is not a SecurityIdentifier.");
        return identity.Value + "|" +
            ((long)rule.FileSystemRights).ToString() + "|" +
            ((int)rule.InheritanceFlags).ToString() + "|" +
            ((int)rule.PropagationFlags).ToString() + "|" +
            ((int)rule.AccessControlType).ToString() + "|" +
            (rule.IsInherited ? "1" : "0");
    }

    private static Dictionary<string, int> GetAccessRuleMultiset(DirectorySecurity security)
    {
        Dictionary<string, int> result = new Dictionary<string, int>(StringComparer.Ordinal);
        AuthorizationRuleCollection rules = security.GetAccessRules(true, true, typeof(SecurityIdentifier));
        foreach (AuthorizationRule authorizationRule in rules)
        {
            FileSystemAccessRule rule = authorizationRule as FileSystemAccessRule;
            if (rule == null) throw new InvalidOperationException("Unexpected non-filesystem ACL rule.");
            string signature = BuildAccessRuleSignature(rule);
            int count;
            result.TryGetValue(signature, out count);
            result[signature] = count + 1;
        }
        return result;
    }

    private static int CountRulesForSid(DirectorySecurity security, string sid)
    {
        int count = 0;
        AuthorizationRuleCollection rules = security.GetAccessRules(true, true, typeof(SecurityIdentifier));
        foreach (AuthorizationRule authorizationRule in rules)
        {
            FileSystemAccessRule rule = authorizationRule as FileSystemAccessRule;
            if (rule == null) throw new InvalidOperationException("Unexpected non-filesystem ACL rule.");
            SecurityIdentifier identity = rule.IdentityReference as SecurityIdentifier;
            if (identity == null) throw new InvalidOperationException("ACL identity is not a SecurityIdentifier.");
            if (String.Equals(identity.Value, sid, StringComparison.Ordinal)) count++;
        }
        return count;
    }

    private static bool RemoveSingleRule(Dictionary<string, int> rules, string signature)
    {
        int count;
        if (!rules.TryGetValue(signature, out count) || count <= 0) return false;
        if (count == 1) rules.Remove(signature);
        else rules[signature] = count - 1;
        return true;
    }

    private static bool RuleMultisetsEqual(Dictionary<string, int> left, Dictionary<string, int> right)
    {
        if (left.Count != right.Count) return false;
        foreach (KeyValuePair<string, int> pair in left)
        {
            int rightCount;
            if (!right.TryGetValue(pair.Key, out rightCount) || rightCount != pair.Value) return false;
        }
        return true;
    }

'''
    if shared_output_private_anchor not in source:
        raise DeveloperTaskExecutionCompileAstControllerWorkerBundleError(
            "shared_output_private_acl_anchor_missing"
        )
    source = source.replace(
        shared_output_private_anchor,
        shared_output_private_helpers + shared_output_private_anchor,
        1,
    )

    launch_replacement = r'''public static WorkerLaunchState LaunchFixedCompileAstWorkerSuspendedInJob(IntPtr token)
    {
        const string runtimeExecutablePath = @"C:\SkynetVSRuntime\python.exe";
        const string runnerPath = @"C:\SkynetVSInput\SkynetVS_V1C2A2_runner.py";
        const string resultRoot = @"C:\SkynetVSOutput";
        if (!File.Exists(runtimeExecutablePath)) throw new FileNotFoundException("Pinned runtime executable is missing.", runtimeExecutablePath);
        if (!File.Exists(runnerPath)) throw new FileNotFoundException("Pinned compile AST runner is missing.", runnerPath);
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
            limits.BasicLimitInformation.LimitFlags =
                JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE |
                JOB_OBJECT_LIMIT_ACTIVE_PROCESS |
                JOB_OBJECT_LIMIT_PROCESS_MEMORY |
                JOB_OBJECT_LIMIT_JOB_MEMORY;
            limits.BasicLimitInformation.ActiveProcessLimit = COMPILE_AST_ACTIVE_PROCESS_LIMIT;
            limits.ProcessMemoryLimit = new UIntPtr(COMPILE_AST_PROCESS_MEMORY_BYTES);
            limits.JobMemoryLimit = new UIntPtr(COMPILE_AST_JOB_MEMORY_BYTES);
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
            StringBuilder commandLine = new StringBuilder(BuildFixedCompileAstCommandLine(runtimeExecutablePath, runnerPath));
            const bool inheritHandles = false;
            if (!CreateProcessAsUserW(
                token,
                runtimeExecutablePath,
                commandLine,
                IntPtr.Zero,
                IntPtr.Zero,
                inheritHandles,
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
            if (!inJob) throw new InvalidOperationException("Compile AST worker process is not in the expected Job Object.");

            state = new WorkerLaunchState
            {
                ProcessHandle = processInformation.hProcess,
                ThreadHandle = processInformation.hThread,
                JobHandle = job,
                ProcessId = processInformation.dwProcessId,
                ThreadId = processInformation.dwThreadId,
                CreatedSuspended = true,
                AssignedBeforeResume = true,
                ProcessInJob = true,
                InheritHandles = inheritHandles,
                ActiveProcessLimit = COMPILE_AST_ACTIVE_PROCESS_LIMIT,
                ProcessMemoryBytes = COMPILE_AST_PROCESS_MEMORY_BYTES,
                JobMemoryBytes = COMPILE_AST_JOB_MEMORY_BYTES
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

    public static uint ResumeCompileAstWorker(IntPtr threadHandle)
    {
        uint previous = ResumeThread(threadHandle);
        if (previous == 0xFFFFFFFF) throw new Win32Exception(Marshal.GetLastWin32Error(), "ResumeThread failed.");
        if (previous != 1) throw new InvalidOperationException("Compile AST worker primary thread was not suspended exactly once.");
        return previous;
    }

    '''
    source = _replace_source_section(
        source,
        "public static WorkerLaunchState LaunchFixedRuntimeProbeSuspendedInJob(",
        "public static bool IsPidInSpecificJob(",
        launch_replacement + "public static bool IsPidInSpecificJob(",
    )

    source = source.replace(
        "private static string BuildFixedRuntimeCommandLine(",
        "private static string BuildFixedCompileAstCommandLine(",
    )
    source = source.replace(
        "public static bool IsPidInSpecificJob(public static bool IsPidInSpecificJob(",
        "public static bool IsPidInSpecificJob(",
    )
    forbidden = (
        "V1B4CNative",
        "svb4c",
        "LaunchFixedRuntimeProbeSuspendedInJob",
        "ResumeRuntimeWorker",
        "BuildFixedRuntimeCommandLine",
    )
    if any(marker in source for marker in forbidden):
        raise DeveloperTaskExecutionCompileAstControllerWorkerBundleError(
            "native_helper_transformation_incomplete"
        )
    if (
        "PrepareSharedWorkerOutputDirectory" not in source
        or "Pre-existing shared-output ACL rules changed." not in source
        or "Shared-output owner changed." not in source
    ):
        raise DeveloperTaskExecutionCompileAstControllerWorkerBundleError(
            "shared_output_acl_transformation_incomplete"
        )
    return _canonical_source_bytes(source, label="native_helper")


def _runtime_files_powershell_literal() -> str:
    rows: list[str] = []
    for item in RUNTIME_ATTESTATION_EXPECTED_RUNTIME_FILES:
        rows.append(
            '    [ordered]@{ path = "'
            + item.path
            + '"; size_bytes = '
            + str(item.size_bytes)
            + '; sha256 = "'
            + item.sha256
            + '" }'
        )
    return ",\n".join(rows)


def _controller_common_functions() -> str:
    source = build_runtime_attestation_controller_script().decode(
        "utf-8", errors="strict"
    )
    start = source.find("function Write-Utf8Atomic {")
    end = source.find("$cngKey = $null", start)
    if start < 0 or end < 0:
        raise DeveloperTaskExecutionCompileAstControllerWorkerBundleError(
            "controller_common_functions_missing"
        )
    return source[start:end]


def build_developer_task_execution_compile_ast_controller_worker_controller_script(
    *,
    native_helper_sha256: str,
) -> bytes:
    if not isinstance(native_helper_sha256, str) or len(native_helper_sha256) != 64:
        raise TypeError("native_helper_sha256 must be a lowercase SHA-256 string")

    expected_runtime_files = _runtime_files_powershell_literal()
    runtime_flags_literal = " ".join(DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_FLAGS)
    common = _controller_common_functions()
    script = r'''Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$BackendId = "@@BACKEND_ID@@"
$BackendPolicyFingerprint = "@@BACKEND_POLICY_FINGERPRINT@@"
$ContractPolicyId = "@@CONTRACT_POLICY_ID@@"
$ContractPolicyFingerprint = "@@CONTRACT_POLICY_FINGERPRINT@@"
$Operation = "@@OPERATION@@"
$ExpectedControllerWorkerPolicySha256 = "@@CONTROLLER_WORKER_POLICY_SHA256@@"
$ExpectedNativeHelperSha256 = "@@NATIVE_HELPER_SHA256@@"
$ExpectedContractPolicySha256 = "@@CONTRACT_POLICY_SHA256@@"
$ExpectedRunnerSha256 = "@@RUNNER_SHA256@@"
$ExpectedPayloadSha256 = "@@PAYLOAD_SHA256@@"
$ExpectedRunnerPolicyFingerprint = "@@RUNNER_POLICY_FINGERPRINT@@"
$ExpectedRunnerBundleFingerprint = "@@RUNNER_BUNDLE_FINGERPRINT@@"
$ExpectedRuntimeAttestationPolicyFingerprint = "@@RUNTIME_ATTESTATION_POLICY_FINGERPRINT@@"
$ExpectedRuntimeAttestationPayloadFingerprint = "@@RUNTIME_ATTESTATION_PAYLOAD_FINGERPRINT@@"
$ExpectedRuntimeBundleFingerprint = "@@RUNTIME_BUNDLE_FINGERPRINT@@"
$ExpectedRuntimeLeasePolicyFingerprint = "@@RUNTIME_LEASE_POLICY_FINGERPRINT@@"
$ExpectedPlanPolicyFingerprint = "@@PLAN_POLICY_FINGERPRINT@@"
$ExpectedRuntimeFileCount = @@RUNTIME_FILE_COUNT@@
$ExpectedRuntimeTotalBytes = @@RUNTIME_TOTAL_BYTES@@
$ExpectedTaskPrefix = "@@TASK_PREFIX@@"
$ExpectedActiveProcessLimit = @@ACTIVE_PROCESS_LIMIT@@
$ExpectedProcessMemoryBytes = @@PROCESS_MEMORY_BYTES@@
$ExpectedJobMemoryBytes = @@JOB_MEMORY_BYTES@@
$ExpectedRuntimeFlags = "@@RUNTIME_FLAGS@@"

$inputRoot = "@@INPUT_ROOT@@"
$sourceRoot = "@@SOURCE_ROOT@@"
$runtimeRoot = "@@RUNTIME_ROOT@@"
$controlRoot = "@@CONTROL_ROOT@@"
$outputRoot = "@@OUTPUT_ROOT@@"
$requestPath = Join-Path $inputRoot "@@REQUEST_FILE@@"
$sourceManifestPath = Join-Path $inputRoot "@@SOURCE_MANIFEST_FILE@@"
$controllerWorkerPolicyPath = Join-Path $inputRoot "@@CONTROLLER_WORKER_POLICY_FILE@@"
$contractPolicyPath = Join-Path $inputRoot "@@CONTRACT_POLICY_FILE@@"
$bootstrapPath = Join-Path $inputRoot "@@BOOTSTRAP_FILE@@"
$controllerPath = Join-Path $inputRoot "@@CONTROLLER_FILE@@"
$nativeHelperPath = Join-Path $inputRoot "@@NATIVE_HELPER_FILE@@"
$runnerPath = Join-Path $inputRoot "@@RUNNER_FILE@@"
$payloadPath = Join-Path $inputRoot "@@PAYLOAD_FILE@@"
$wsbPath = Join-Path $inputRoot "@@WSB_FILE@@"
$readyPath = Join-Path $outputRoot "ready.json"
$authorizeCommitPath = Join-Path $controlRoot "authorize.sha256"
$resultPath = Join-Path $outputRoot "@@RESULT_FILE@@"
$terminalPayloadPath = Join-Path $outputRoot "terminal_payload.json"
$terminalSignaturePath = Join-Path $outputRoot "terminal_signature.bin"
$failurePath = Join-Path $outputRoot "controller_failure.json"
$stage = "request_validation"

$ExpectedRuntimeFiles = @(
@@EXPECTED_RUNTIME_FILES@@
)

@@COMMON_FUNCTIONS@@
function Assert-CompileAstStaticPayload {
    param([object]$Request)
    if ((Get-FileSha256 -Path $controllerWorkerPolicyPath) -cne $ExpectedControllerWorkerPolicySha256) { throw "Controller-worker policy hash mismatch." }
    if ($ExpectedContractPolicySha256 -cne [string]$Request.policy_sha256) { throw "Compile AST contract request policy hash mismatch." }
    if ((Get-FileSha256 -Path $bootstrapPath) -cne [string]$Request.bootstrap_sha256) { throw "Bootstrap file hash mismatch." }
    if ((Get-FileSha256 -Path $controllerPath) -cne [string]$Request.controller_sha256) { throw "Controller file hash mismatch." }
    if ((Get-FileSha256 -Path $nativeHelperPath) -cne $ExpectedNativeHelperSha256) { throw "Native helper hash mismatch." }
    if ($ExpectedNativeHelperSha256 -cne [string]$Request.native_helper_sha256) { throw "Native helper request hash mismatch." }
    if ((Get-FileSha256 -Path $contractPolicyPath) -cne $ExpectedContractPolicySha256) { throw "Compile AST contract policy hash mismatch." }
    if ((Get-FileSha256 -Path $runnerPath) -cne $ExpectedRunnerSha256) { throw "Compile AST runner hash mismatch." }
    if ($ExpectedRunnerSha256 -cne [string]$Request.runner_sha256) { throw "Compile AST runner request hash mismatch." }
    if ((Get-FileSha256 -Path $payloadPath) -cne $ExpectedPayloadSha256) { throw "Compile AST payload hash mismatch." }
    if ($ExpectedPayloadSha256 -cne [string]$Request.payload_sha256) { throw "Compile AST payload request hash mismatch." }
    if ((Get-FileSha256 -Path $wsbPath) -cne [string]$Request.wsb_sha256) { throw "WSB file hash mismatch." }
    return $true
}

function Assert-SourceManifestAndTree {
    param([object]$Request, [byte[]]$ManifestBytes)
    $manifestSha256 = Get-BytesSha256 -Bytes $ManifestBytes
    if ($manifestSha256 -cne [string]$Request.source_manifest_sha256) { throw "Source manifest hash mismatch." }
    $manifestText = [System.Text.UTF8Encoding]::new($false, $true).GetString($ManifestBytes)
    $manifest = $manifestText | ConvertFrom-Json
    if ([int]$manifest.schema_version -ne 1) { throw "Source manifest schema mismatch." }
    if ([string]$manifest.contract_policy_id -cne $ContractPolicyId) { throw "Source manifest contract policy mismatch." }
    if ([string]$manifest.contract_policy_fingerprint -cne $ContractPolicyFingerprint) { throw "Source manifest contract fingerprint mismatch." }
    if ([string]$manifest.operation -cne $Operation) { throw "Source manifest operation mismatch." }
    if ([string]$manifest.request_id -cne [string]$Request.request_id) { throw "Source manifest request ID mismatch." }
    if ([string]$manifest.host_nonce -cne [string]$Request.host_nonce) { throw "Source manifest host nonce mismatch." }
    if ([string]$manifest.plan_policy_fingerprint -cne $ExpectedPlanPolicyFingerprint) { throw "Source manifest plan policy mismatch." }
    if ([string]$manifest.plan_fingerprint -cne [string]$Request.plan_fingerprint) { throw "Source manifest plan fingerprint mismatch." }
    if ([string]$manifest.source_strategy -cne "flat_sorted_ordinal_files_v1") { throw "Source strategy mismatch." }
    if ([string]$manifest.source_root -cne $sourceRoot) { throw "Source root mismatch." }
    if ([bool]$manifest.original_path_used_as_guest_filesystem_path) { throw "Original path cannot be a guest filesystem path." }
    if (-not [bool]$manifest.read_only_mapping) { throw "Source mapping must be read-only." }
    [int]$selectedCount = [int]$manifest.selected_file_count
    [int64]$selectedTotal = [int64]$manifest.selected_total_bytes
    if ($selectedCount -lt 1 -or $selectedCount -gt @@MAX_FILE_COUNT@@) { throw "Selected source count is invalid." }
    if ($selectedCount -ne [int]$Request.selected_file_count) { throw "Selected source count does not match request." }
    if ($selectedTotal -lt 0 -or $selectedTotal -gt @@MAX_TOTAL_BYTES@@) { throw "Selected source total is invalid." }
    if ($selectedTotal -ne [int64]$Request.selected_total_bytes) { throw "Selected source total does not match request." }
    $sources = @($manifest.sources)
    if ($sources.Count -ne $selectedCount) { throw "Source list count mismatch." }
    $actualItems = @(Get-ChildItem -LiteralPath $sourceRoot -Force)
    if ($actualItems.Count -ne $selectedCount) { throw "Source root file count mismatch." }
    [int64]$actualTotal = 0
    for ($index = 0; $index -lt $sources.Count; $index++) {
        $source = $sources[$index]
        $ordinal = $index + 1
        $expectedName = "source-{0:D4}.py" -f $ordinal
        if ([int]$source.ordinal -ne $ordinal) { throw "Source ordinal mismatch." }
        if ([string]$source.guest_file_name -cne $expectedName) { throw "Guest source name mismatch." }
        if ([string]$source.git_mode -cne "100644") { throw "Source mode mismatch." }
        if ([string]$source.encoding -cne "utf-8") { throw "Source encoding mismatch." }
        if ([string]$source.line_endings -cnotin @("lf", "none")) { throw "Source line endings mismatch." }
        [int64]$sizeBytes = [int64]$source.size_bytes
        if ($sizeBytes -lt 0 -or $sizeBytes -gt @@MAX_FILE_BYTES@@) { throw "Source size limit mismatch." }
        $path = Join-Path $sourceRoot $expectedName
        $item = Get-Item -LiteralPath $path -Force
        if ($item.PSIsContainer) { throw "Source tree contains a directory." }
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw "Source tree contains a reparse point." }
        if ([int64]$item.Length -ne $sizeBytes) { throw "Source file size mismatch." }
        if ((Get-FileSha256 -Path $path) -cne [string]$source.sha256) { throw "Source file hash mismatch." }
        $actualTotal += [int64]$item.Length
    }
    if ($actualTotal -ne $selectedTotal) { throw "Source tree total mismatch." }
    return $manifest
}

function Read-TrustedCompileAstResult {
    param([object]$Request, [object]$Manifest)
    if (-not (Test-Path -LiteralPath $resultPath -PathType Leaf)) { return $null }
    $bytes = Read-StrictUtf8Bytes -Path $resultPath -MaximumBytes @@RESULT_MAX_BYTES@@
    if ($bytes.Length -lt 2 -or $bytes[$bytes.Length - 1] -ne 10 -or $bytes[$bytes.Length - 2] -eq 13) { throw "Compile AST result does not have the exact LF terminator." }
    $text = [System.Text.UTF8Encoding]::new($false, $true).GetString($bytes)
    $result = $text | ConvertFrom-Json
    if ([int]$result.schema_version -ne 1) { throw "Compile AST result schema mismatch." }
    if ([string]$result.contract_policy_id -cne $ContractPolicyId) { throw "Compile AST result policy mismatch." }
    if ([string]$result.contract_policy_fingerprint -cne $ContractPolicyFingerprint) { throw "Compile AST result fingerprint mismatch." }
    if ([string]$result.operation -cne $Operation) { throw "Compile AST result operation mismatch." }
    if ([string]$result.request_id -cne [string]$Request.request_id) { throw "Compile AST result request mismatch." }
    if ([string]$result.plan_fingerprint -cne [string]$Request.plan_fingerprint) { throw "Compile AST result plan mismatch." }
    if ([string]$result.source_manifest_sha256 -cne [string]$Request.source_manifest_sha256) { throw "Compile AST result source manifest mismatch." }
    if ([string]$result.runtime_bundle_fingerprint -cne $ExpectedRuntimeBundleFingerprint) { throw "Compile AST result runtime mismatch." }
    if ([string]$result.implementation -cne "CPython") { throw "Compile AST result implementation mismatch." }
    if (@($result.version_info).Count -ne 3 -or [int]$result.version_info[0] -ne 3 -or [int]$result.version_info[1] -ne 13 -or [int]$result.version_info[2] -ne 15) { throw "Compile AST result version mismatch." }
    if ([int]$result.architecture_bits -ne 64) { throw "Compile AST result architecture mismatch." }
    if (([string]$result.machine).ToUpperInvariant() -notin @("AMD64", "X86_64")) { throw "Compile AST result machine mismatch." }
    [int]$selected = [int]$result.selected_file_count
    [int]$processed = [int]$result.processed_file_count
    [int]$passed = [int]$result.passed_file_count
    [int]$failed = [int]$result.failed_file_count
    if ($selected -ne [int]$Request.selected_file_count -or $selected -ne [int]$Manifest.selected_file_count) { throw "Compile AST result selected count mismatch." }
    if ($processed -ne $selected -or ($passed + $failed) -ne $selected) { throw "Compile AST result counts mismatch." }
    if (@($result.files).Count -ne $selected) { throw "Compile AST result file list mismatch." }
    if (-not [bool]$result.trusted_interpreter_executed -or -not [bool]$result.changed_source_processed) { throw "Compile AST result interpreter evidence is invalid." }
    if ([bool]$result.changed_code_executed -or [bool]$result.imports_executed -or [bool]$result.top_level_executed -or [bool]$result.bytecode_written -or [bool]$result.execution_authorized) { throw "Compile AST result contains forbidden execution evidence." }
    $expectedPassed = ($failed -eq 0)
    if ([bool]$result.check_passed -ne $expectedPassed) { throw "Compile AST result pass state mismatch." }
    return [pscustomobject]@{ Document = $result; Bytes = $bytes; Sha256 = (Get-BytesSha256 -Bytes $bytes) }
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
$authorize = $null
$readySha256 = ""
$authorizeSha256 = ""
$resumePreviousCount = 0
$workerExitCode = [uint32]70
$resultEvidence = $null
$manifest = $null

try {
    $requestBytes = Read-StrictUtf8Bytes -Path $requestPath -MaximumBytes @@REQUEST_MAX_BYTES@@
    $requestSha256 = Get-BytesSha256 -Bytes $requestBytes
    $requestText = [System.Text.UTF8Encoding]::new($false, $true).GetString($requestBytes)
    $request = $requestText | ConvertFrom-Json
    $requestId = [string]$request.request_id
    if ($requestId -cnotmatch "^[0-9a-f]{32}$") { throw "Request ID is invalid." }
    if ([string]$request.host_nonce -cnotmatch "^[0-9a-f]{64}$") { throw "Host nonce is invalid." }
    if ([int]$request.schema_version -ne 1) { throw "Request schema mismatch." }
    if ([string]$request.backend_id -cne $BackendId) { throw "Backend ID mismatch." }
    if ([string]$request.backend_policy_fingerprint -cne $BackendPolicyFingerprint) { throw "Backend policy mismatch." }
    if ([string]$request.contract_policy_id -cne $ContractPolicyId) { throw "Contract policy mismatch." }
    if ([string]$request.contract_policy_fingerprint -cne $ContractPolicyFingerprint) { throw "Contract policy fingerprint mismatch." }
    if ([string]$request.operation -cne $Operation) { throw "Operation mismatch." }
    if ([int]$request.ready_timeout_seconds -ne 120 -or [int]$request.authorization_timeout_seconds -ne 90 -or [int]$request.worker_timeout_seconds -ne 60 -or [int]$request.shutdown_grace_seconds -ne 45) { throw "Request timeout policy mismatch." }
    if ([string]$request.runtime_attestation_policy_fingerprint -cne $ExpectedRuntimeAttestationPolicyFingerprint) { throw "Runtime attestation policy mismatch." }
    if ([string]$request.runtime_bundle_fingerprint -cne $ExpectedRuntimeBundleFingerprint) { throw "Runtime bundle mismatch." }
    if ([string]$request.runtime_lease_policy_fingerprint -cne $ExpectedRuntimeLeasePolicyFingerprint) { throw "Runtime lease policy mismatch." }
    if ([string]$request.runtime_lease_fingerprint -cnotmatch "^[0-9a-f]{64}$") { throw "Runtime lease fingerprint is invalid." }
    if ([string]$request.plan_policy_fingerprint -cne $ExpectedPlanPolicyFingerprint) { throw "Plan policy mismatch." }
    if ([string]$request.plan_fingerprint -cnotmatch "^[0-9a-f]{64}$") { throw "Plan fingerprint is invalid." }
    if ([string]$request.source_manifest_sha256 -cnotmatch "^[0-9a-f]{64}$") { throw "Source manifest identity is invalid." }
    if ([int]$request.selected_file_count -lt 1 -or [int]$request.selected_file_count -gt @@MAX_FILE_COUNT@@) { throw "Selected file count is invalid." }
    if ([int64]$request.selected_total_bytes -lt 0 -or [int64]$request.selected_total_bytes -gt @@MAX_TOTAL_BYTES@@) { throw "Selected byte total is invalid." }
    if ([string]$request.trusted_scope -cne "compile_ast_changed_python_only_v1" -or [bool]$request.execution_authorized) { throw "Request scope is invalid." }

    $requestIdentityVerified = Assert-CompileAstStaticPayload -Request $request
    $sourceManifestBytes = Read-StrictUtf8Bytes -Path $sourceManifestPath -MaximumBytes @@SOURCE_MANIFEST_MAX_BYTES@@
    $manifest = Assert-SourceManifestAndTree -Request $request -ManifestBytes $sourceManifestBytes

    $stage = "controller_identity"
    Add-Type -Path $nativeHelperPath -ErrorAction Stop
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    $controllerSid = [string]$identity.User.Value
    $controllerName = [string]$identity.Name
    $controllerIsSystem = ($controllerSid -eq "S-1-5-18")
    $controllerIsAdmin = $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
    $controllerIntegrityRid = [V1C2C1Native]::GetCurrentIntegrityRid()
    $expectedTaskName = $ExpectedTaskPrefix + $requestId.Substring(0, 8)
    $bootstrapTaskDeleted = Remove-BootstrapTask -TaskName $expectedTaskName

    $cngKey = [V1C2C1Native]::CreateEphemeralEcdsaP256SigningKey()
    $ecdsa = [System.Security.Cryptography.ECDsaCng]::new($cngKey)
    $publicBlob = $cngKey.Export([System.Security.Cryptography.CngKeyBlobFormat]::EccPublicBlob)
    $publicKeySha256 = Get-BytesSha256 -Bytes $publicBlob
    $keyIsEphemeral = [bool]$cngKey.IsEphemeral
    $keyName = [string]$cngKey.KeyName
    $keyUniqueName = [string]$cngKey.UniqueName

    $stage = "ready_identity"
    $runtimeIdentityVerified = Assert-RuntimeTree
    $inputWriteBlocked = Test-WriteBlocked -Root $inputRoot -Name "controller_input_write_probe.txt"
    $sourceWriteBlocked = Test-WriteBlocked -Root $sourceRoot -Name "controller_source_write_probe.py"
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
        request_identity_verified = $requestIdentityVerified
        source_manifest_verified = $true
        runtime_identity_verified = $runtimeIdentityVerified
        input_write_blocked = $inputWriteBlocked
        source_write_blocked = $sourceWriteBlocked
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
        contract_policy_id = $ContractPolicyId
        contract_policy_fingerprint = $ContractPolicyFingerprint
        operation = $Operation
        request_id = $requestId
        host_nonce = [string]$request.host_nonce
        request_sha256 = $requestSha256
        source_manifest_sha256 = [string]$request.source_manifest_sha256
        policy_sha256 = Get-FileSha256 -Path $contractPolicyPath
        bootstrap_sha256 = Get-FileSha256 -Path $bootstrapPath
        controller_sha256 = Get-FileSha256 -Path $controllerPath
        native_helper_sha256 = Get-FileSha256 -Path $nativeHelperPath
        runner_sha256 = Get-FileSha256 -Path $runnerPath
        payload_sha256 = Get-FileSha256 -Path $payloadPath
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
        runtime_attestation_policy_fingerprint = $ExpectedRuntimeAttestationPolicyFingerprint
        runtime_bundle_fingerprint = $ExpectedRuntimeBundleFingerprint
        runtime_lease_policy_fingerprint = $ExpectedRuntimeLeasePolicyFingerprint
        runtime_lease_fingerprint = [string]$request.runtime_lease_fingerprint
        plan_policy_fingerprint = $ExpectedPlanPolicyFingerprint
        plan_fingerprint = [string]$request.plan_fingerprint
        input_write_blocked = $inputWriteBlocked
        source_write_blocked = $sourceWriteBlocked
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
    $authorizationReadError = ""
    while ((Get-Date) -lt $authorizationDeadline) {
        if (Test-Path -LiteralPath $authorizeCommitPath -PathType Leaf) {
            try {
                $commitBytes = Read-StrictUtf8Bytes -Path $authorizeCommitPath -MaximumBytes 64
                if ($commitBytes.Length -ne 64) { throw "Authorization commit size is invalid." }
                $commitText = [System.Text.UTF8Encoding]::new($false, $true).GetString($commitBytes)
                if ($commitText -cnotmatch "^[0-9a-f]{64}$") { throw "Authorization commit hash is invalid." }
                if (-not (Test-Path -LiteralPath $authorizePath -PathType Leaf)) { throw "Authorization data is missing." }
                $candidateBytes = Read-StrictUtf8Bytes -Path $authorizePath -MaximumBytes @@AUTHORIZE_MAX_BYTES@@
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
    if ([string]$authorize.runtime_lease_fingerprint -cne [string]$request.runtime_lease_fingerprint) { throw "Authorization runtime lease mismatch." }
    if ([string]$authorize.plan_fingerprint -cne [string]$request.plan_fingerprint) { throw "Authorization plan mismatch." }
    if ([string]$authorize.source_manifest_sha256 -cne [string]$request.source_manifest_sha256) { throw "Authorization source manifest mismatch." }
    if (-not [bool]$authorize.allow_compile_ast -or [bool]$authorize.execution_authorized) { throw "Authorization scope is invalid." }
    if ([int64]$authorize.authorization_deadline_epoch -lt $nowEpoch) { throw "Authorization expired." }

    $stage = "post_authorization_revalidation"
    Assert-CompileAstStaticPayload -Request $request | Out-Null
    Assert-RuntimeTree | Out-Null
    # Source changes after ready are deliberately left for the fixed runner to
    # reject so V1C2C3 can obtain a signed boundary-failure transcript after the
    # standard-user/Job/account cleanup boundary has also been proved.

    $stage = "compile_ast_worker"
    if (Test-Path -LiteralPath $resultPath) { throw "Compile AST result path already exists." }
    $workerUser = [V1C2C1Native]::BuildWorkerUserName($requestId)
    $tokenState = [V1C2C1Native]::CreateFreshStandardUserAndLogon($workerUser)
    $workerAccountCreated = $true
    $workerSid = [string]$tokenState.UserSid
    [V1C2C1Native]::PrepareSharedWorkerOutputDirectory($outputRoot, $workerSid)

    $launchState = [V1C2C1Native]::LaunchFixedCompileAstWorkerSuspendedInJob($tokenState.TokenHandle)
    if ($launchState.InheritHandles) { throw "Compile AST worker inherited handles." }
    if ([uint32]$launchState.ActiveProcessLimit -ne [uint32]$ExpectedActiveProcessLimit -or [uint64]$launchState.ProcessMemoryBytes -ne [uint64]$ExpectedProcessMemoryBytes -or [uint64]$launchState.JobMemoryBytes -ne [uint64]$ExpectedJobMemoryBytes) { throw "Compile AST Job limits mismatch." }
    $resumePreviousCount = [V1C2C1Native]::ResumeCompileAstWorker($launchState.ThreadHandle)
    [V1C2C1Native]::CloseHandle($launchState.ThreadHandle) | Out-Null
    $launchState.ThreadHandle = [IntPtr]::Zero
    $workerWait = [V1C2C1Native]::WaitForSingleObject($launchState.ProcessHandle, [uint32](@@WORKER_TIMEOUT_SECONDS@@ * 1000))
    if ($workerWait -eq [V1C2C1Native]::WAIT_TIMEOUT) {
        [V1C2C1Native]::CloseHandle($launchState.JobHandle) | Out-Null
        $launchState.JobHandle = [IntPtr]::Zero
        $jobClosed = $true
        [V1C2C1Native]::WaitForSingleObject($launchState.ProcessHandle, 5000) | Out-Null
    }
    elseif ($workerWait -ne [V1C2C1Native]::WAIT_OBJECT_0) { throw "Compile AST worker wait failed." }
    if (-not [V1C2C1Native]::GetExitCodeProcess($launchState.ProcessHandle, [ref]$workerExitCode)) { throw "Compile AST worker exit code could not be read." }
    if ($workerWait -eq [V1C2C1Native]::WAIT_OBJECT_0 -and $workerExitCode -eq 0) {
        try { $resultEvidence = Read-TrustedCompileAstResult -Request $request -Manifest $manifest }
        catch { $resultEvidence = $null }
    }

    [V1C2C1Native]::CloseHandle($launchState.ProcessHandle) | Out-Null
    $launchState.ProcessHandle = [IntPtr]::Zero
    if (-not $jobClosed) {
        [V1C2C1Native]::CloseHandle($launchState.JobHandle) | Out-Null
        $launchState.JobHandle = [IntPtr]::Zero
        $jobClosed = $true
    }
    $sweep = [V1C2C1Native]::WaitForWorkerSidQuiescence($workerSid)
    $workerSidProcessSetEmpty = ($sweep.MatchingProcessIds.Length -eq 0 -and $sweep.ConsecutiveEmptyScans -ge 3)
    if (-not $workerSidProcessSetEmpty) { throw "Compile AST worker SID process set is not empty." }
    [V1C2C1Native]::DeleteLocalUserExact($workerUser, $workerSid)
    $workerAccountDeleted = $true

    $stage = "network_and_terminal"
    $ipv4DefaultRoutePresent = Test-DefaultRoute -Family IPv4
    $ipv6DefaultRoutePresent = Test-DefaultRoute -Family IPv6
    $ipv4TcpReachable = Invoke-TcpProbe -AddressFamily ([System.Net.Sockets.AddressFamily]::InterNetwork) -Address "1.1.1.1" -Port 443
    $ipv6TcpReachable = Invoke-TcpProbe -AddressFamily ([System.Net.Sockets.AddressFamily]::InterNetworkV6) -Address "2606:4700:4700::1111" -Port 443
    $shutdownScheduled = Schedule-Shutdown
    if (-not $shutdownScheduled) { throw "Sandbox self-shutdown could not be scheduled." }

    $resultReceived = ($null -ne $resultEvidence)
    $resultDocument = if ($resultReceived) { $resultEvidence.Document } else { $null }
    $resultSha256 = if ($resultReceived) { [string]$resultEvidence.Sha256 } else { $null }
    $processedCount = if ($resultReceived) { [int]$resultDocument.processed_file_count } else { 0 }
    $passedCount = if ($resultReceived) { [int]$resultDocument.passed_file_count } else { 0 }
    $failedCount = if ($resultReceived) { [int]$resultDocument.failed_file_count } else { 0 }
    $boundaryOk = $resultReceived -and ($workerExitCode -eq 0)
    $checkPassed = $boundaryOk -and [bool]$resultDocument.check_passed
    $status = if (-not $boundaryOk) { "compile_ast_boundary_failed" } elseif ($checkPassed) { "compile_ast_attested_passed" } else { "compile_ast_attested_failed" }

    $terminalPayload = [ordered]@{
        schema_version = 1
        backend_id = $BackendId
        backend_policy_fingerprint = $BackendPolicyFingerprint
        contract_policy_id = $ContractPolicyId
        contract_policy_fingerprint = $ContractPolicyFingerprint
        operation = $Operation
        request_id = $requestId
        host_nonce = [string]$request.host_nonce
        authorization_nonce = [string]$authorize.authorization_nonce
        request_sha256 = $requestSha256
        ready_sha256 = $readySha256
        authorize_sha256 = $authorizeSha256
        source_manifest_sha256 = [string]$request.source_manifest_sha256
        result_sha256 = $resultSha256
        policy_sha256 = Get-FileSha256 -Path $contractPolicyPath
        bootstrap_sha256 = Get-FileSha256 -Path $bootstrapPath
        controller_sha256 = Get-FileSha256 -Path $controllerPath
        native_helper_sha256 = Get-FileSha256 -Path $nativeHelperPath
        runner_sha256 = Get-FileSha256 -Path $runnerPath
        payload_sha256 = Get-FileSha256 -Path $payloadPath
        wsb_sha256 = Get-FileSha256 -Path $wsbPath
        public_key_sha256 = $publicKeySha256
        runtime_attestation_policy_fingerprint = $ExpectedRuntimeAttestationPolicyFingerprint
        runtime_bundle_fingerprint = $ExpectedRuntimeBundleFingerprint
        runtime_lease_policy_fingerprint = $ExpectedRuntimeLeasePolicyFingerprint
        runtime_lease_fingerprint = [string]$request.runtime_lease_fingerprint
        plan_policy_fingerprint = $ExpectedPlanPolicyFingerprint
        plan_fingerprint = [string]$request.plan_fingerprint
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
            result_received = $resultReceived
            exit_code = [uint32]$workerExitCode
            is_administrator = [bool]$tokenState.IsAdministrator
            integrity_rid = [int]$tokenState.IntegrityRid
            worker_in_job = [bool]$launchState.ProcessInJob
            active_process_limit = [uint32]$launchState.ActiveProcessLimit
            process_memory_bytes = [uint64]$launchState.ProcessMemoryBytes
            job_memory_bytes = [uint64]$launchState.JobMemoryBytes
            job_closed = $jobClosed
            sid_process_set_empty = $workerSidProcessSetEmpty
            account_deleted = $workerAccountDeleted
        }
        controls = [ordered]@{
            input_write_blocked = $inputWriteBlocked
            source_write_blocked = $sourceWriteBlocked
            runtime_write_blocked = $runtimeWriteBlocked
            control_write_blocked = $controlWriteBlocked
            output_writable = $outputWritable
            ipv4_default_route_present = $ipv4DefaultRoutePresent
            ipv4_external_tcp_reachable = $ipv4TcpReachable
            ipv6_default_route_present = $ipv6DefaultRoutePresent
            ipv6_external_tcp_reachable = $ipv6TcpReachable
        }
        runtime = [ordered]@{
            implementation = "CPython"
            version = @(3, 13, 15)
            architecture_bits = 64
            machine = "AMD64"
            bundle_fingerprint = $ExpectedRuntimeBundleFingerprint
            environment_clean = $true
            pip_absent = $true
            ensurepip_absent = $true
            site_absent = $true
            sys_path_exact = $true
            dont_write_bytecode = $true
        }
        check = [ordered]@{
            result_received = $resultReceived
            result_sha256 = $resultSha256
            selected_file_count = [int]$request.selected_file_count
            processed_file_count = $processedCount
            passed_file_count = $passedCount
            failed_file_count = $failedCount
            trusted_interpreter_executed = $resultReceived
            changed_source_processed = $resultReceived
            changed_source_ast_parsed = $(if ($resultReceived) { [bool]$resultDocument.changed_source_ast_parsed } else { $false })
            changed_source_compiled = $(if ($resultReceived) { [bool]$resultDocument.changed_source_compiled } else { $false })
            changed_code_executed = $false
            imports_executed = $false
            top_level_executed = $false
            bytecode_written = $false
        }
        shutdown = [ordered]@{
            scheduled = $shutdownScheduled
            delay_seconds = 8
        }
        completed_at_utc = (Get-Date).ToUniversalTime().ToString("o")
        status = $status
        boundary_ok = $boundaryOk
        check_passed = $checkPassed
        reusable_lease_issued = $false
        execution_authorized = $false
    }
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
        error_code = "compile_ast_controller_worker_stage_failed"
        worker_account_created = $workerAccountCreated
        worker_account_deleted = $workerAccountDeleted
        job_closed = $jobClosed
        completed_at_utc = (Get-Date).ToUniversalTime().ToString("o")
        execution_authorized = $false
    }
    try { Write-Utf8Atomic -Path $failurePath -Text ($failure | ConvertTo-Json -Depth 8 -Compress) } catch { }
    try {
        if ($null -ne $launchState -and $launchState.JobHandle -ne [IntPtr]::Zero) {
            [V1C2C1Native]::CloseHandle($launchState.JobHandle) | Out-Null
            $launchState.JobHandle = [IntPtr]::Zero
            $jobClosed = $true
        }
    }
    catch { }
    try {
        if (-not [string]::IsNullOrEmpty($workerSid)) {
            [V1C2C1Native]::WaitForWorkerSidQuiescence($workerSid) | Out-Null
            $workerSidProcessSetEmpty = $true
        }
    }
    catch { }
    try {
        if ($workerAccountCreated -and $workerSidProcessSetEmpty -and -not $workerAccountDeleted) {
            [V1C2C1Native]::DeleteLocalUserExact($workerUser, $workerSid)
            $workerAccountDeleted = $true
        }
    }
    catch { }
    Schedule-Shutdown | Out-Null
}
finally {
    try { if ($null -ne $launchState -and $launchState.ThreadHandle -ne [IntPtr]::Zero) { [V1C2C1Native]::CloseHandle($launchState.ThreadHandle) | Out-Null } } catch { }
    try { if ($null -ne $launchState -and $launchState.ProcessHandle -ne [IntPtr]::Zero) { [V1C2C1Native]::CloseHandle($launchState.ProcessHandle) | Out-Null } } catch { }
    try { if ($null -ne $launchState -and $launchState.JobHandle -ne [IntPtr]::Zero) { [V1C2C1Native]::CloseHandle($launchState.JobHandle) | Out-Null } } catch { }
    try { if ($null -ne $tokenState -and $tokenState.TokenHandle -ne [IntPtr]::Zero) { [V1C2C1Native]::CloseHandle($tokenState.TokenHandle) | Out-Null } } catch { }
    try { if ($null -ne $ecdsa) { $ecdsa.Dispose() } } catch { }
    try { if ($null -ne $cngKey) { $cngKey.Dispose() } } catch { }
}
'''
    replacements = {
        "@@BACKEND_ID@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_V1.to_dict()["dependencies"]["backend"]["backend_id"],
        "@@BACKEND_POLICY_FINGERPRINT@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_V1.to_dict()["dependencies"]["backend"]["policy_fingerprint"],
        "@@CONTRACT_POLICY_ID@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_ID,
        "@@CONTRACT_POLICY_FINGERPRINT@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT,
        "@@OPERATION@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION,
        "@@CONTROLLER_WORKER_POLICY_SHA256@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_BYTES_SHA256,
        "@@NATIVE_HELPER_SHA256@@": native_helper_sha256,
        "@@CONTRACT_POLICY_SHA256@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_SHA256,
        "@@RUNNER_SHA256@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_SHA256,
        "@@PAYLOAD_SHA256@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_SHA256,
        "@@RUNNER_POLICY_FINGERPRINT@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_FINGERPRINT,
        "@@RUNNER_BUNDLE_FINGERPRINT@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_BUNDLE_FINGERPRINT,
        "@@RUNTIME_ATTESTATION_POLICY_FINGERPRINT@@": RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
        "@@RUNTIME_ATTESTATION_PAYLOAD_FINGERPRINT@@": RUNTIME_ATTESTATION_PAYLOAD_BUNDLE_FINGERPRINT,
        "@@RUNTIME_BUNDLE_FINGERPRINT@@": RUNTIME_BUNDLE_FINGERPRINT,
        "@@RUNTIME_LEASE_POLICY_FINGERPRINT@@": RUNTIME_LEASE_POLICY_FINGERPRINT,
        "@@PLAN_POLICY_FINGERPRINT@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT,
        "@@RUNTIME_FILE_COUNT@@": str(RUNTIME_BUNDLE_FILE_COUNT),
        "@@RUNTIME_TOTAL_BYTES@@": str(RUNTIME_BUNDLE_TOTAL_BYTES),
        "@@TASK_PREFIX@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_TASK_PREFIX,
        "@@ACTIVE_PROCESS_LIMIT@@": str(DEVELOPER_TASK_EXECUTION_COMPILE_AST_ACTIVE_PROCESS_LIMIT),
        "@@PROCESS_MEMORY_BYTES@@": str(DEVELOPER_TASK_EXECUTION_COMPILE_AST_PROCESS_MEMORY_BYTES),
        "@@JOB_MEMORY_BYTES@@": str(DEVELOPER_TASK_EXECUTION_COMPILE_AST_JOB_MEMORY_BYTES),
        "@@RUNTIME_FLAGS@@": runtime_flags_literal,
        "@@INPUT_ROOT@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_INPUT_ROOT,
        "@@SOURCE_ROOT@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_ROOT,
        "@@RUNTIME_ROOT@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_ROOT,
        "@@CONTROL_ROOT@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROL_ROOT,
        "@@OUTPUT_ROOT@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_OUTPUT_ROOT,
        "@@REQUEST_FILE@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_REQUEST_FILE_NAME,
        "@@SOURCE_MANIFEST_FILE@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_MANIFEST_FILE_NAME,
        "@@CONTROLLER_WORKER_POLICY_FILE@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_FILE_NAME,
        "@@CONTRACT_POLICY_FILE@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FILE_NAME,
        "@@BOOTSTRAP_FILE@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BOOTSTRAP_FILE_NAME,
        "@@CONTROLLER_FILE@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_CONTROLLER_FILE_NAME,
        "@@NATIVE_HELPER_FILE@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_NATIVE_HELPER_FILE_NAME,
        "@@RUNNER_FILE@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_FILE_NAME,
        "@@PAYLOAD_FILE@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_FILE_NAME,
        "@@WSB_FILE@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_WSB_FILE_NAME,
        "@@RESULT_FILE@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RESULT_FILE_NAME,
        "@@EXPECTED_RUNTIME_FILES@@": expected_runtime_files,
        "@@COMMON_FUNCTIONS@@": common,
        "@@MAX_FILE_COUNT@@": str(DEVELOPER_TASK_EXECUTION_COMPILE_AST_MAX_FILE_COUNT),
        "@@MAX_FILE_BYTES@@": str(DEVELOPER_TASK_EXECUTION_COMPILE_AST_MAX_FILE_BYTES),
        "@@MAX_TOTAL_BYTES@@": str(DEVELOPER_TASK_EXECUTION_COMPILE_AST_MAX_TOTAL_BYTES),
        "@@REQUEST_MAX_BYTES@@": str(DEVELOPER_TASK_EXECUTION_COMPILE_AST_REQUEST_MAX_BYTES),
        "@@SOURCE_MANIFEST_MAX_BYTES@@": str(DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_MANIFEST_MAX_BYTES),
        "@@AUTHORIZE_MAX_BYTES@@": str(DEVELOPER_TASK_EXECUTION_COMPILE_AST_AUTHORIZE_MAX_BYTES),
        "@@RESULT_MAX_BYTES@@": str(DEVELOPER_TASK_EXECUTION_COMPILE_AST_RESULT_MAX_BYTES),
        "@@WORKER_TIMEOUT_SECONDS@@": str(DEVELOPER_TASK_EXECUTION_COMPILE_AST_WORKER_TIMEOUT_SECONDS),
    }
    for token, value in replacements.items():
        script = script.replace(token, value)
    if "@@" in script:
        raise DeveloperTaskExecutionCompileAstControllerWorkerBundleError(
            "controller_template_token_unresolved"
        )
    if "WindowsSandbox.exe" in script:
        raise DeveloperTaskExecutionCompileAstControllerWorkerBundleError(
            "controller_contains_host_sandbox_launcher"
        )
    return _canonical_source_bytes(script, label="controller")


def build_developer_task_execution_compile_ast_controller_worker_wsb_template() -> bytes:
    data = build_runtime_attestation_wsb_template()
    text = data.decode("utf-8", errors="strict")
    if DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BOOTSTRAP_FILE_NAME != "bootstrap.ps1":
        text = text.replace(
            r'\bootstrap.ps1"',
            "\\" + DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BOOTSTRAP_FILE_NAME + '"',
        )
    return _canonical_source_bytes(text, label="wsb_template")


def _payload(
    kind: str,
    file_name: str,
    data: bytes,
) -> DeveloperTaskExecutionCompileAstControllerWorkerPayload:
    return DeveloperTaskExecutionCompileAstControllerWorkerPayload(
        kind=kind,
        file_name=file_name,
        size_bytes=len(data),
        sha256=_sha256(data),
        _bytes=bytes(data),
    )


def _bundle_fingerprint(
    payloads: tuple[DeveloperTaskExecutionCompileAstControllerWorkerPayload, ...],
) -> str:
    value = {
        "schema_version": 1,
        "bundle_id": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BUNDLE_ID,
        "policy_id": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_ID,
        "policy_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_FINGERPRINT,
        "architecture_decision_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_DECISION_FINGERPRINT,
        "architecture_slice_identity": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_SLICE_IDENTITY,
        "operation": DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION,
        "payloads": [payload.to_dict() for payload in payloads],
        "runner_bundle_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_BUNDLE_FINGERPRINT,
        "runtime_bundle_fingerprint": RUNTIME_BUNDLE_FINGERPRINT,
        "active_process_limit": DEVELOPER_TASK_EXECUTION_COMPILE_AST_ACTIVE_PROCESS_LIMIT,
        "process_memory_bytes": DEVELOPER_TASK_EXECUTION_COMPILE_AST_PROCESS_MEMORY_BYTES,
        "job_memory_bytes": DEVELOPER_TASK_EXECUTION_COMPILE_AST_JOB_MEMORY_BYTES,
        "kill_on_close": True,
        "inherit_handles": False,
        "create_suspended": True,
        "assign_before_resume": True,
        "execution_authorized": False,
    }
    return _sha256(_canonical_json_bytes(value))


def build_developer_task_execution_compile_ast_controller_worker_bundle(
) -> DeveloperTaskExecutionCompileAstControllerWorkerBundle:
    policy_errors = validate_developer_task_execution_compile_ast_controller_worker_policy()
    if policy_errors:
        raise DeveloperTaskExecutionCompileAstControllerWorkerBundleError(
            "controller_worker_policy_invalid:" + ",".join(policy_errors)
        )
    policy_bytes = developer_task_execution_compile_ast_controller_worker_policy_bytes()
    bootstrap_bytes = build_developer_task_execution_compile_ast_controller_worker_bootstrap_script()
    native_helper_bytes = build_developer_task_execution_compile_ast_controller_worker_native_helper_source()
    controller_bytes = build_developer_task_execution_compile_ast_controller_worker_controller_script(
        native_helper_sha256=_sha256(native_helper_bytes),
    )
    wsb_template_bytes = build_developer_task_execution_compile_ast_controller_worker_wsb_template()
    payloads = (
        _payload(
            "compile_ast_controller_worker_policy",
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_FILE_NAME,
            policy_bytes,
        ),
        _payload(
            "trusted_bootstrap",
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BOOTSTRAP_FILE_NAME,
            bootstrap_bytes,
        ),
        _payload(
            "trusted_native_helper",
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_NATIVE_HELPER_FILE_NAME,
            native_helper_bytes,
        ),
        _payload(
            "trusted_system_controller",
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_CONTROLLER_FILE_NAME,
            controller_bytes,
        ),
        _payload(
            "windows_sandbox_template",
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_WSB_FILE_NAME,
            wsb_template_bytes,
        ),
    )
    bundle = DeveloperTaskExecutionCompileAstControllerWorkerBundle(
        bundle_id=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BUNDLE_ID,
        bundle_fingerprint=_bundle_fingerprint(payloads),
        policy_id=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_ID,
        policy_fingerprint=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_FINGERPRINT,
        architecture_decision_id=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_DECISION_ID,
        architecture_decision_fingerprint=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_DECISION_FINGERPRINT,
        architecture_slice=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_SLICE,
        architecture_slice_identity=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_SLICE_IDENTITY,
        operation=DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION,
        policy=payloads[0],
        bootstrap=payloads[1],
        native_helper=payloads[2],
        controller=payloads[3],
        wsb_template=payloads[4],
        runtime_executable=DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_EXECUTABLE,
        runtime_flags=DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_FLAGS,
        runner_path=DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_PATH,
        working_directory=DEVELOPER_TASK_EXECUTION_COMPILE_AST_OUTPUT_ROOT,
        active_process_limit=DEVELOPER_TASK_EXECUTION_COMPILE_AST_ACTIVE_PROCESS_LIMIT,
        process_memory_bytes=DEVELOPER_TASK_EXECUTION_COMPILE_AST_PROCESS_MEMORY_BYTES,
        job_memory_bytes=DEVELOPER_TASK_EXECUTION_COMPILE_AST_JOB_MEMORY_BYTES,
        kill_on_close=True,
        inherit_handles=False,
        create_suspended=True,
        assign_before_resume=True,
        environment_scrub_prefixes=("PYTHON", "PIP_", "PYLAUNCHER_"),
        environment_scrub_exact=("VIRTUAL_ENV",),
        sandbox_launched=False,
        claim_transaction_consumed=False,
        runtime_lease_claimed=False,
        candidate_interpreter_executed=False,
        changed_source_processed=False,
        changed_source_ast_parsed=False,
        changed_source_compiled=False,
        changed_code_executed=False,
        reusable_lease_issued=False,
        execution_authorized=False,
    )
    errors = _bundle_errors(bundle)
    if errors:
        raise DeveloperTaskExecutionCompileAstControllerWorkerBundleError(
            "controller_worker_bundle_invalid:" + ",".join(errors)
        )
    return bundle


def _bundle_errors(
    bundle: DeveloperTaskExecutionCompileAstControllerWorkerBundle,
) -> tuple[str, ...]:
    if not isinstance(bundle, DeveloperTaskExecutionCompileAstControllerWorkerBundle):
        return ("bundle_type_invalid",)
    errors: list[str] = []
    if bundle.bundle_id != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BUNDLE_ID:
        errors.append("bundle_id_invalid")
    if bundle.policy_id != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_ID:
        errors.append("policy_id_invalid")
    if bundle.policy_fingerprint != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_FINGERPRINT:
        errors.append("policy_fingerprint_invalid")
    if bundle.architecture_decision_id != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_DECISION_ID or bundle.architecture_decision_fingerprint != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_DECISION_FINGERPRINT or bundle.architecture_slice != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_SLICE or bundle.architecture_slice_identity != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_ARCHITECTURE_SLICE_IDENTITY:
        errors.append("architecture_lock_invalid")
    if bundle.operation != DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION:
        errors.append("operation_invalid")

    expected_hashes = (
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_POLICY_BYTES_SHA256,
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BOOTSTRAP_SHA256,
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_NATIVE_HELPER_SHA256,
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_CONTROLLER_SHA256,
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_WSB_TEMPLATE_SHA256,
    )
    for payload, expected_hash in zip(bundle.payloads, expected_hashes, strict=True):
        data = payload.exact_bytes()
        if payload.size_bytes != len(data) or payload.sha256 != _sha256(data):
            errors.append(payload.kind + "_identity_invalid")
        if payload.sha256 != expected_hash:
            errors.append(payload.kind + "_hash_not_pinned")
        try:
            text = data.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            errors.append(payload.kind + "_utf8_invalid")
        else:
            if data.startswith(b"\xef\xbb\xbf") or b"\r" in data or not text.endswith("\n"):
                errors.append(payload.kind + "_canonical_text_invalid")
    if bundle.bundle_fingerprint != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTROLLER_WORKER_BUNDLE_FINGERPRINT:
        errors.append("bundle_fingerprint_not_pinned")
    if bundle.bundle_fingerprint != _bundle_fingerprint(bundle.payloads):
        errors.append("bundle_fingerprint_invalid")
    if bundle.runtime_executable != DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_EXECUTABLE or bundle.runtime_flags != DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_FLAGS or bundle.runner_path != DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_PATH or bundle.working_directory != DEVELOPER_TASK_EXECUTION_COMPILE_AST_OUTPUT_ROOT:
        errors.append("launch_contract_invalid")
    if (
        bundle.active_process_limit != 1
        or bundle.process_memory_bytes != 512 * 1024 * 1024
        or bundle.job_memory_bytes != 768 * 1024 * 1024
        or not bundle.kill_on_close
        or bundle.inherit_handles
        or not bundle.create_suspended
        or not bundle.assign_before_resume
    ):
        errors.append("worker_boundary_invalid")
    if bundle.environment_scrub_prefixes != ("PYTHON", "PIP_", "PYLAUNCHER_") or bundle.environment_scrub_exact != ("VIRTUAL_ENV",):
        errors.append("environment_boundary_invalid")
    if any(
        (
            bundle.sandbox_launched,
            bundle.claim_transaction_consumed,
            bundle.runtime_lease_claimed,
            bundle.candidate_interpreter_executed,
            bundle.changed_source_processed,
            bundle.changed_source_ast_parsed,
            bundle.changed_source_compiled,
            bundle.changed_code_executed,
            bundle.reusable_lease_issued,
            bundle.execution_authorized,
        )
    ):
        errors.append("execution_boundary_invalid")
    return tuple(errors)
