from __future__ import annotations

"""V1C2A2 deterministic fixed guest compile/AST runner payload bundle."""

import hashlib
import json

from dataclasses import dataclass
from typing import Any

from modules.developer.developer_task_execution_compile_ast_contract_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION,
    canonical_developer_task_execution_compile_ast_contract_policy_json,
)
from modules.developer.developer_task_execution_compile_ast_runner_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_INPUT_ROOT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_OUTPUT_ROOT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_MAX_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_REQUEST_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RESULT_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_BUNDLE_ID,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_FILE_NAME,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_MAX_BYTES,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_PATH,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_ID,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_V1,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_EXECUTABLE,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_FLAGS,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_SOURCE_MANIFEST_FILE_NAME,
    developer_task_execution_compile_ast_runner_policy_fingerprint,
    validate_developer_task_execution_compile_ast_runner_policy,
)
from modules.developer.developer_task_execution_runtime_policy import (
    RUNTIME_BUNDLE_FINGERPRINT,
)


DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_SHA256 = (
    "f280f9c564dd1cfd780cd5465a3ecd98244e0f00f10827a295b3709b2d8b0ed2"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_SHA256 = (
    "6f4ec0085cfa45c7d9242850d570b6a723c3a051338fc3c0bbd2e78dc1c43ec9"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_SHA256 = (
    "730d4108aab8246d1e6ff030a4d5a64ad25a89adf888e2b10c64ec63d56f60b6"
)
DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_BUNDLE_FINGERPRINT = (
    "b1f182ca4ee1a9e83cb6a32ca54e45d4511c81faa27d8dd4be7817883affb9f3"
)


class DeveloperTaskExecutionCompileAstRunnerBundleError(ValueError):
    pass


@dataclass(frozen=True)
class DeveloperTaskExecutionCompileAstRunnerPayload:
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
            "DeveloperTaskExecutionCompileAstRunnerPayload("
            f"kind={self.kind!r}, file_name={self.file_name!r}, "
            f"size_bytes={self.size_bytes!r}, sha256={self.sha256!r})"
        )


@dataclass(frozen=True)
class DeveloperTaskExecutionCompileAstRunnerBundle:
    bundle_id: str
    bundle_fingerprint: str
    policy_id: str
    policy_fingerprint: str
    contract_policy_fingerprint: str
    runtime_bundle_fingerprint: str
    operation: str
    contract_policy: DeveloperTaskExecutionCompileAstRunnerPayload
    runner: DeveloperTaskExecutionCompileAstRunnerPayload
    payload_manifest: DeveloperTaskExecutionCompileAstRunnerPayload
    runtime_executable: str
    runtime_flags: tuple[str, ...]
    runner_path: str
    working_directory: str
    sandbox_launched: bool
    runtime_lease_issued: bool
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "bundle_fingerprint": self.bundle_fingerprint,
            "policy_id": self.policy_id,
            "policy_fingerprint": self.policy_fingerprint,
            "contract_policy_fingerprint": self.contract_policy_fingerprint,
            "runtime_bundle_fingerprint": self.runtime_bundle_fingerprint,
            "operation": self.operation,
            "contract_policy": self.contract_policy.to_dict(),
            "runner": self.runner.to_dict(),
            "payload_manifest": self.payload_manifest.to_dict(),
            "launch": {
                "runtime_executable": self.runtime_executable,
                "runtime_flags": list(self.runtime_flags),
                "runner_path": self.runner_path,
                "working_directory": self.working_directory,
                "shell": False,
                "caller_arguments": False,
                "caller_environment": False,
            },
            "boundary": {
                "sandbox_launched": self.sandbox_launched,
                "runtime_lease_issued": self.runtime_lease_issued,
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


_RUNNER_SOURCE_TEMPLATE = r'''from __future__ import annotations

"""Fixed V1C2A2 compile/AST guest runner. It never executes the compiled code object."""

import ast
import hashlib
import json
import os
import platform
import struct
import sys


CONTRACT_POLICY_FINGERPRINT = "@@CONTRACT_POLICY_FINGERPRINT@@"
RUNNER_POLICY_FINGERPRINT = "@@RUNNER_POLICY_FINGERPRINT@@"
RUNTIME_BUNDLE_FINGERPRINT = "@@RUNTIME_BUNDLE_FINGERPRINT@@"
OPERATION = "compile_ast_changed_python_v1"
SOURCE_ROOT = r"C:\SkynetVSInput\sources"
REQUEST_PATH = r"C:\SkynetVSInput\request.json"
SOURCE_MANIFEST_PATH = r"C:\SkynetVSInput\source_manifest.json"
PAYLOAD_PATH = r"C:\SkynetVSInput\compile_ast_payload.json"
CONTRACT_POLICY_PATH = r"C:\SkynetVSInput\compile_ast_contract_policy.json"
RESULT_PATH = r"C:\SkynetVSOutput\result.json"
MAX_REQUEST_BYTES = 64 * 1024
MAX_SOURCE_MANIFEST_BYTES = 64 * 1024
MAX_PAYLOAD_BYTES = 64 * 1024
MAX_POLICY_BYTES = 64 * 1024
MAX_FILE_COUNT = 20
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 8 * 1024 * 1024
MAX_ERROR_MESSAGE_CHARS = 512
RUNTIME_VERSION = (3, 13, 15)
RUNTIME_MACHINES = ("AMD64", "X86_64")

_REQUEST_FIELDS = (
    "schema_version", "backend_id", "backend_policy_fingerprint",
    "contract_policy_id", "contract_policy_fingerprint", "operation",
    "request_id", "host_nonce", "created_at_utc", "ready_timeout_seconds",
    "authorization_timeout_seconds", "worker_timeout_seconds",
    "shutdown_grace_seconds", "policy_sha256", "bootstrap_sha256",
    "controller_sha256", "native_helper_sha256", "runner_sha256",
    "payload_sha256", "wsb_sha256", "runtime_attestation_policy_fingerprint",
    "runtime_bundle_fingerprint", "runtime_lease_policy_fingerprint",
    "runtime_lease_fingerprint", "plan_policy_fingerprint", "plan_fingerprint",
    "source_manifest_sha256", "selected_file_count", "selected_total_bytes",
    "trusted_scope", "execution_authorized",
)
_SOURCE_MANIFEST_FIELDS = (
    "schema_version", "contract_policy_id", "contract_policy_fingerprint",
    "operation", "request_id", "host_nonce", "plan_policy_fingerprint",
    "plan_fingerprint", "snapshot_fingerprint", "plan_source_manifest_sha256",
    "source_strategy", "source_root", "original_path_used_as_guest_filesystem_path",
    "read_only_mapping", "selected_file_count", "selected_total_bytes", "sources",
    "execution_authorized",
)
_SOURCE_FIELDS = (
    "ordinal", "guest_file_name", "original_path", "virtual_filename", "git_mode",
    "size_bytes", "sha256", "encoding", "line_endings",
)
_RESULT_FIELDS = (
    "schema_version", "contract_policy_id", "contract_policy_fingerprint", "operation",
    "request_id", "plan_fingerprint", "source_manifest_sha256",
    "runtime_bundle_fingerprint", "implementation", "version_info",
    "architecture_bits", "machine", "selected_file_count", "processed_file_count",
    "passed_file_count", "failed_file_count", "check_passed", "files",
    "trusted_interpreter_executed", "changed_source_processed",
    "changed_source_ast_parsed", "changed_source_compiled", "changed_code_executed",
    "imports_executed", "top_level_executed", "bytecode_written",
    "execution_authorized",
)
_RESULT_FILE_FIELDS = (
    "ordinal", "guest_file_name", "original_path", "virtual_filename", "git_mode",
    "size_bytes", "sha256", "decode_ok", "ast_parse_ok", "compile_ok", "error",
)
_ERROR_FIELDS = ("type", "message", "line", "offset", "end_line", "end_offset")
_PAYLOAD_FIELDS = (
    "bundle_id", "contract_policy", "contract_policy_fingerprint", "execution_authorized", "launch",
    "operation", "payload_policy_fingerprint", "runner",
    "runtime_bundle_fingerprint", "schema_version",
)
_PAYLOAD_CONTRACT_POLICY_FIELDS = ("file_name", "sha256", "size_bytes")
_PAYLOAD_LAUNCH_FIELDS = (
    "caller_arguments", "caller_environment", "runtime_executable", "runtime_flags",
    "runner_path", "shell", "working_directory",
)
_PAYLOAD_RUNNER_FIELDS = ("file_name", "sha256", "size_bytes")


class RunnerInputError(ValueError):
    pass


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise RunnerInputError("duplicate_json_field")
        result[key] = value
    return result


def _reject_float(value):
    raise RunnerInputError("float_json_number")


def _reject_constant(value):
    raise RunnerInputError("nonfinite_json_number")


def _canonical_json_bytes(value, *, trailing_lf=False):
    data = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if trailing_lf:
        data += b"\n"
    return data


def _read_bytes(path, maximum, *, allow_empty=False):
    with open(path, "rb") as stream:
        data = stream.read(maximum + 1)
    if len(data) > maximum or (not allow_empty and not data):
        raise RunnerInputError("artifact_size_invalid")
    return data


def _load_canonical_json(path, maximum, *, trailing_lf=False):
    data = _read_bytes(path, maximum)
    if data.startswith(b"\xef\xbb\xbf"):
        raise RunnerInputError("json_bom_forbidden")
    body = data
    if trailing_lf:
        if not data.endswith(b"\n") or data.endswith(b"\r\n") or data.endswith(b"\n\n"):
            raise RunnerInputError("json_line_ending_invalid")
        body = data[:-1]
    text = body.decode("utf-8", errors="strict")
    value = json.loads(
        text,
        object_pairs_hook=_strict_object,
        parse_float=_reject_float,
        parse_constant=_reject_constant,
    )
    if type(value) is not dict:
        raise RunnerInputError("json_not_object")
    if _canonical_json_bytes(value, trailing_lf=trailing_lf) != data:
        raise RunnerInputError("json_not_canonical")
    return value, data


def _require_fields(value, fields):
    if tuple(value.keys()) != fields:
        raise RunnerInputError("fields_invalid")


def _require_hex(value, length):
    if type(value) is not str or len(value) != length or any(ch not in "0123456789abcdef" for ch in value):
        raise RunnerInputError("hex_invalid")
    return value


def _require_int(value, minimum=None, maximum=None):
    if type(value) is not int:
        raise RunnerInputError("integer_invalid")
    if minimum is not None and value < minimum:
        raise RunnerInputError("integer_invalid")
    if maximum is not None and value > maximum:
        raise RunnerInputError("integer_invalid")
    return value


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _verify_runtime():
    if platform.python_implementation() != "CPython":
        raise RunnerInputError("runtime_implementation_invalid")
    if tuple(sys.version_info[:3]) != RUNTIME_VERSION:
        raise RunnerInputError("runtime_version_invalid")
    if struct.calcsize("P") * 8 != 64:
        raise RunnerInputError("runtime_bitness_invalid")
    if platform.machine().upper() not in RUNTIME_MACHINES:
        raise RunnerInputError("runtime_machine_invalid")
    if not sys.flags.isolated or not sys.flags.ignore_environment or not sys.flags.no_user_site:
        raise RunnerInputError("runtime_flags_invalid")
    if not bool(getattr(sys.flags, "safe_path", False)) or not sys.flags.dont_write_bytecode or not sys.flags.utf8_mode:
        raise RunnerInputError("runtime_flags_invalid")
    if "site" in sys.modules:
        raise RunnerInputError("runtime_site_loaded")
    forbidden = [
        key for key in os.environ
        if key.upper().startswith(("PYTHON", "PIP_", "PYLAUNCHER_")) or key.upper() == "VIRTUAL_ENV"
    ]
    if forbidden:
        raise RunnerInputError("runtime_environment_invalid")


def _verify_payload(request):
    payload, payload_bytes = _load_canonical_json(PAYLOAD_PATH, MAX_PAYLOAD_BYTES)
    _require_fields(payload, _PAYLOAD_FIELDS)
    if payload["schema_version"] != 1:
        raise RunnerInputError("payload_schema_invalid")
    if payload["bundle_id"] != "v1c2a2_fixed_compile_ast_guest_runner_bundle_v1":
        raise RunnerInputError("payload_id_invalid")
    if payload["payload_policy_fingerprint"] != RUNNER_POLICY_FINGERPRINT:
        raise RunnerInputError("payload_policy_invalid")
    if payload["contract_policy_fingerprint"] != CONTRACT_POLICY_FINGERPRINT:
        raise RunnerInputError("payload_contract_invalid")
    if payload["runtime_bundle_fingerprint"] != RUNTIME_BUNDLE_FINGERPRINT:
        raise RunnerInputError("payload_runtime_invalid")
    if payload["operation"] != OPERATION or payload["execution_authorized"] is not False:
        raise RunnerInputError("payload_scope_invalid")
    contract_policy = payload["contract_policy"]
    runner = payload["runner"]
    launch = payload["launch"]
    if type(contract_policy) is not dict or type(runner) is not dict or type(launch) is not dict:
        raise RunnerInputError("payload_structure_invalid")
    _require_fields(contract_policy, _PAYLOAD_CONTRACT_POLICY_FIELDS)
    _require_fields(runner, _PAYLOAD_RUNNER_FIELDS)
    _require_fields(launch, _PAYLOAD_LAUNCH_FIELDS)
    own_bytes = _read_bytes(__file__, 128 * 1024)
    if runner["file_name"] != os.path.basename(__file__) or runner["size_bytes"] != len(own_bytes) or runner["sha256"] != _sha256(own_bytes):
        raise RunnerInputError("runner_identity_invalid")
    if request["runner_sha256"] != _sha256(own_bytes) or request["payload_sha256"] != _sha256(payload_bytes):
        raise RunnerInputError("request_payload_identity_invalid")
    policy_bytes = _read_bytes(CONTRACT_POLICY_PATH, MAX_POLICY_BYTES)
    if (
        contract_policy["file_name"] != "compile_ast_contract_policy.json"
        or contract_policy["size_bytes"] != len(policy_bytes)
        or contract_policy["sha256"] != _sha256(policy_bytes)
        or request["policy_sha256"] != _sha256(policy_bytes)
    ):
        raise RunnerInputError("contract_policy_file_identity_invalid")
    if launch != {
        "caller_arguments": False,
        "caller_environment": False,
        "runtime_executable": r"C:\SkynetVSRuntime\python.exe",
        "runtime_flags": ["-I", "-S", "-B", "-E", "-s", "-P", "-X", "utf8"],
        "runner_path": r"C:\SkynetVSInput\SkynetVS_V1C2A2_runner.py",
        "shell": False,
        "working_directory": r"C:\SkynetVSOutput",
    }:
        raise RunnerInputError("payload_launch_invalid")


def _validate_request(request, request_bytes, manifest_bytes):
    _require_fields(request, _REQUEST_FIELDS)
    if request["schema_version"] != 1:
        raise RunnerInputError("request_schema_invalid")
    if request["contract_policy_fingerprint"] != CONTRACT_POLICY_FINGERPRINT:
        raise RunnerInputError("request_contract_invalid")
    if request["operation"] != OPERATION or request["execution_authorized"] is not False:
        raise RunnerInputError("request_scope_invalid")
    if request["runtime_bundle_fingerprint"] != RUNTIME_BUNDLE_FINGERPRINT:
        raise RunnerInputError("request_runtime_invalid")
    _require_hex(request["request_id"], 32)
    _require_hex(request["host_nonce"], 64)
    _require_hex(request["plan_fingerprint"], 64)
    if request["source_manifest_sha256"] != _sha256(manifest_bytes):
        raise RunnerInputError("source_manifest_identity_invalid")
    selected = _require_int(request["selected_file_count"], 1, MAX_FILE_COUNT)
    total = _require_int(request["selected_total_bytes"], 0, MAX_TOTAL_BYTES)
    if selected <= 0 or total < 0:
        raise RunnerInputError("request_counts_invalid")
    return selected, total


def _validate_manifest(manifest, request, selected, total):
    _require_fields(manifest, _SOURCE_MANIFEST_FIELDS)
    if manifest["schema_version"] != 1:
        raise RunnerInputError("manifest_schema_invalid")
    if manifest["contract_policy_fingerprint"] != CONTRACT_POLICY_FINGERPRINT or manifest["operation"] != OPERATION:
        raise RunnerInputError("manifest_contract_invalid")
    if manifest["request_id"] != request["request_id"] or manifest["host_nonce"] != request["host_nonce"]:
        raise RunnerInputError("manifest_run_identity_invalid")
    if manifest["plan_fingerprint"] != request["plan_fingerprint"]:
        raise RunnerInputError("manifest_plan_identity_invalid")
    if manifest["source_strategy"] != "flat_sorted_ordinal_files_v1" or manifest["source_root"] != SOURCE_ROOT:
        raise RunnerInputError("manifest_materialization_invalid")
    if manifest["original_path_used_as_guest_filesystem_path"] is not False or manifest["read_only_mapping"] is not True:
        raise RunnerInputError("manifest_materialization_invalid")
    if manifest["execution_authorized"] is not False:
        raise RunnerInputError("manifest_scope_invalid")
    if manifest["selected_file_count"] != selected or manifest["selected_total_bytes"] != total:
        raise RunnerInputError("manifest_counts_invalid")
    sources = manifest["sources"]
    if type(sources) is not list or len(sources) != selected:
        raise RunnerInputError("manifest_sources_invalid")
    previous = ""
    computed_total = 0
    for ordinal, source in enumerate(sources, start=1):
        if type(source) is not dict:
            raise RunnerInputError("source_entry_invalid")
        _require_fields(source, _SOURCE_FIELDS)
        if source["ordinal"] != ordinal or source["guest_file_name"] != f"source-{ordinal:04d}.py":
            raise RunnerInputError("source_ordinal_invalid")
        original = source["original_path"]
        if type(original) is not str or not original or original.startswith(("/", "\\")) or "\\" in original or ".." in original.split("/"):
            raise RunnerInputError("source_path_invalid")
        if previous and original <= previous:
            raise RunnerInputError("source_order_invalid")
        previous = original
        if source["virtual_filename"] != "skynetvs://changed/" + original:
            raise RunnerInputError("source_virtual_filename_invalid")
        if source["git_mode"] != "100644" or source["encoding"] != "utf-8" or source["line_endings"] not in ("lf", "none"):
            raise RunnerInputError("source_policy_invalid")
        size = _require_int(source["size_bytes"], 0, MAX_FILE_BYTES)
        _require_hex(source["sha256"], 64)
        computed_total += size
    if computed_total != total:
        raise RunnerInputError("source_total_invalid")
    return sources


def _read_verified_source(source):
    guest_name = source["guest_file_name"]
    if os.path.basename(guest_name) != guest_name:
        raise RunnerInputError("source_guest_name_invalid")
    path = os.path.join(SOURCE_ROOT, guest_name)
    data = _read_bytes(path, MAX_FILE_BYTES, allow_empty=True)
    if len(data) != source["size_bytes"] or _sha256(data) != source["sha256"]:
        raise RunnerInputError("source_bytes_identity_invalid")
    if b"\x00" in data or b"\r" in data:
        raise RunnerInputError("source_bytes_policy_invalid")
    text = data.decode("utf-8", errors="strict")
    return text


def _bounded_syntax_error(error):
    message = str(getattr(error, "msg", "invalid syntax"))
    message = message.replace("\r", " ").replace("\n", " ")
    if not message:
        message = "invalid syntax"
    message = message[:MAX_ERROR_MESSAGE_CHARS]
    line = getattr(error, "lineno", None)
    offset = getattr(error, "offset", None)
    end_line = getattr(error, "end_lineno", None)
    end_offset = getattr(error, "end_offset", None)
    if type(line) is not int or line < 1 or type(offset) is not int or offset < 0:
        line = None
        offset = None
        end_line = None
        end_offset = None
    elif type(end_line) is not int or end_line < 1:
        end_line = None
        end_offset = None
    elif type(end_offset) is not int or end_offset < 0:
        end_offset = None
    result = {}
    for key, value in zip(_ERROR_FIELDS, ("SyntaxError", message, line, offset, end_line, end_offset)):
        result[key] = value
    return result


def _file_result(source, *, decode_ok, ast_ok, compile_ok, error):
    values = (
        source["ordinal"], source["guest_file_name"], source["original_path"],
        source["virtual_filename"], source["git_mode"], source["size_bytes"],
        source["sha256"], decode_ok, ast_ok, compile_ok, error,
    )
    return {key: value for key, value in zip(_RESULT_FILE_FIELDS, values)}


def _build_result(request, manifest_bytes, sources):
    files = []
    passed = 0
    all_ast = True
    all_compile = True
    for source in sources:
        text = _read_verified_source(source)
        ast_ok = False
        compile_ok = False
        error_payload = None
        try:
            tree = ast.parse(
                text,
                filename=source["virtual_filename"],
                mode="exec",
                type_comments=False,
                feature_version=(3, 13),
                optimize=0,
            )
            ast_ok = True
            code = compile(
                tree,
                source["virtual_filename"],
                "exec",
                flags=0,
                dont_inherit=True,
                optimize=0,
            )
            compile_ok = True
            del code
            passed += 1
        except SyntaxError as error:
            error_payload = _bounded_syntax_error(error)
        files.append(_file_result(source, decode_ok=True, ast_ok=ast_ok, compile_ok=compile_ok, error=error_payload))
        all_ast = all_ast and ast_ok
        all_compile = all_compile and compile_ok
    selected = len(sources)
    failed = selected - passed
    values = (
        1,
        "skynetvs-v1c2a1-compile-ast-contract-cpython-3.13.15-v1",
        CONTRACT_POLICY_FINGERPRINT,
        OPERATION,
        request["request_id"],
        request["plan_fingerprint"],
        _sha256(manifest_bytes),
        RUNTIME_BUNDLE_FINGERPRINT,
        platform.python_implementation(),
        list(sys.version_info[:3]),
        struct.calcsize("P") * 8,
        platform.machine(),
        selected,
        selected,
        passed,
        failed,
        failed == 0,
        files,
        True,
        True,
        all_ast,
        all_compile,
        False,
        False,
        False,
        False,
        False,
    )
    return {key: value for key, value in zip(_RESULT_FIELDS, values)}


def _write_result_exclusive(payload):
    data = _canonical_json_bytes(payload, trailing_lf=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | int(getattr(os, "O_BINARY", 0))
    descriptor = os.open(RESULT_PATH, flags, 0o600)
    try:
        total = 0
        while total < len(data):
            written = os.write(descriptor, data[total:])
            if written <= 0:
                raise OSError("result_write_failed")
            total += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def main():
    try:
        _verify_runtime()
        request, request_bytes = _load_canonical_json(REQUEST_PATH, MAX_REQUEST_BYTES)
        manifest, manifest_bytes = _load_canonical_json(SOURCE_MANIFEST_PATH, MAX_SOURCE_MANIFEST_BYTES)
        selected, total = _validate_request(request, request_bytes, manifest_bytes)
        _verify_payload(request)
        sources = _validate_manifest(manifest, request, selected, total)
        result = _build_result(request, manifest_bytes, sources)
        _write_result_exclusive(result)
        return 0
    except Exception:
        return 70


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _canonical_source_bytes(source: str) -> bytes:
    if not isinstance(source, str):
        raise TypeError("source must be str")
    if "\r" in source or not source.endswith("\n"):
        raise DeveloperTaskExecutionCompileAstRunnerBundleError(
            "runner_source_not_canonical"
        )
    data = source.encode("utf-8")
    if data.startswith(b"\xef\xbb\xbf"):
        raise DeveloperTaskExecutionCompileAstRunnerBundleError(
            "runner_source_bom_forbidden"
        )
    return data


def build_developer_task_execution_compile_ast_runner_source() -> bytes:
    """Return the exact standalone guest runner bytes without executing them."""
    replacements = {
        "@@CONTRACT_POLICY_FINGERPRINT@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT,
        "@@RUNNER_POLICY_FINGERPRINT@@": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_FINGERPRINT,
        "@@RUNTIME_BUNDLE_FINGERPRINT@@": RUNTIME_BUNDLE_FINGERPRINT,
    }
    source = _RUNNER_SOURCE_TEMPLATE
    for token, value in replacements.items():
        source = source.replace(token, value)
    if "@@" in source:
        raise DeveloperTaskExecutionCompileAstRunnerBundleError(
            "runner_source_token_unresolved"
        )
    data = _canonical_source_bytes(source)
    if len(data) > DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_MAX_BYTES:
        raise DeveloperTaskExecutionCompileAstRunnerBundleError(
            "runner_source_too_large"
        )
    return data


def _launch_contract() -> dict[str, Any]:
    return {
        "caller_arguments": False,
        "caller_environment": False,
        "runtime_executable": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_EXECUTABLE,
        "runtime_flags": list(DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_FLAGS),
        "runner_path": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_PATH,
        "shell": False,
        "working_directory": DEVELOPER_TASK_EXECUTION_COMPILE_AST_OUTPUT_ROOT,
    }


def _contract_policy_bytes() -> bytes:
    data = canonical_developer_task_execution_compile_ast_contract_policy_json(
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY
    ).encode("utf-8")
    if not data or len(data) > 64 * 1024 or data.startswith(b"\xef\xbb\xbf") or b"\r" in data:
        raise DeveloperTaskExecutionCompileAstRunnerBundleError("contract_policy_bytes_invalid")
    return data


def _payload_manifest_bytes(runner_bytes: bytes, contract_policy_bytes: bytes) -> bytes:
    payload = {
        "bundle_id": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_BUNDLE_ID,
        "contract_policy": {
            "file_name": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FILE_NAME,
            "sha256": hashlib.sha256(contract_policy_bytes).hexdigest(),
            "size_bytes": len(contract_policy_bytes),
        },
        "contract_policy_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT,
        "execution_authorized": False,
        "launch": _launch_contract(),
        "operation": DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION,
        "payload_policy_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_FINGERPRINT,
        "runner": {
            "file_name": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_FILE_NAME,
            "sha256": hashlib.sha256(runner_bytes).hexdigest(),
            "size_bytes": len(runner_bytes),
        },
        "runtime_bundle_fingerprint": RUNTIME_BUNDLE_FINGERPRINT,
        "schema_version": 1,
    }
    data = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    if len(data) > DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_MAX_BYTES:
        raise DeveloperTaskExecutionCompileAstRunnerBundleError(
            "payload_manifest_too_large"
        )
    return data


def _bundle_fingerprint(contract_policy_bytes: bytes, runner_bytes: bytes, payload_bytes: bytes) -> str:
    value = {
        "bundle_id": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_BUNDLE_ID,
        "contract_policy_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT,
        "contract_policy_sha256": hashlib.sha256(contract_policy_bytes).hexdigest(),
        "operation": DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION,
        "payload_sha256": hashlib.sha256(payload_bytes).hexdigest(),
        "policy_fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_FINGERPRINT,
        "runner_sha256": hashlib.sha256(runner_bytes).hexdigest(),
        "runtime_bundle_fingerprint": RUNTIME_BUNDLE_FINGERPRINT,
    }
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _payload(kind: str, file_name: str, data: bytes) -> DeveloperTaskExecutionCompileAstRunnerPayload:
    return DeveloperTaskExecutionCompileAstRunnerPayload(
        kind=kind,
        file_name=file_name,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        _bytes=bytes(data),
    )


def build_developer_task_execution_compile_ast_runner_bundle() -> DeveloperTaskExecutionCompileAstRunnerBundle:
    """Build the fixed V1C2A2 payload bundle without launching any interpreter or Sandbox."""
    policy_errors = validate_developer_task_execution_compile_ast_runner_policy()
    if policy_errors:
        raise DeveloperTaskExecutionCompileAstRunnerBundleError(
            "runner_policy_invalid:" + ",".join(policy_errors)
        )
    if (
        developer_task_execution_compile_ast_runner_policy_fingerprint(
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_V1
        )
        != DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_FINGERPRINT
    ):
        raise DeveloperTaskExecutionCompileAstRunnerBundleError(
            "runner_policy_fingerprint_invalid"
        )
    contract_policy_bytes = _contract_policy_bytes()
    runner_bytes = build_developer_task_execution_compile_ast_runner_source()
    payload_bytes = _payload_manifest_bytes(runner_bytes, contract_policy_bytes)
    bundle = DeveloperTaskExecutionCompileAstRunnerBundle(
        bundle_id=DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_BUNDLE_ID,
        bundle_fingerprint=_bundle_fingerprint(contract_policy_bytes, runner_bytes, payload_bytes),
        policy_id=DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_ID,
        policy_fingerprint=DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_FINGERPRINT,
        contract_policy_fingerprint=DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT,
        runtime_bundle_fingerprint=RUNTIME_BUNDLE_FINGERPRINT,
        operation=DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION,
        contract_policy=_payload(
            "compile_ast_contract_policy",
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FILE_NAME,
            contract_policy_bytes,
        ),
        runner=_payload(
            "compile_ast_runner",
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_FILE_NAME,
            runner_bytes,
        ),
        payload_manifest=_payload(
            "compile_ast_payload_manifest",
            DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_FILE_NAME,
            payload_bytes,
        ),
        runtime_executable=DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_EXECUTABLE,
        runtime_flags=DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_FLAGS,
        runner_path=DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_PATH,
        working_directory=DEVELOPER_TASK_EXECUTION_COMPILE_AST_OUTPUT_ROOT,
        sandbox_launched=False,
        runtime_lease_issued=False,
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
        raise DeveloperTaskExecutionCompileAstRunnerBundleError(
            "runner_bundle_invalid:" + ",".join(errors)
        )
    return bundle


def _bundle_errors(bundle: DeveloperTaskExecutionCompileAstRunnerBundle) -> tuple[str, ...]:
    if not isinstance(bundle, DeveloperTaskExecutionCompileAstRunnerBundle):
        return ("bundle_type_invalid",)
    errors: list[str] = []
    if bundle.bundle_id != DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_BUNDLE_ID:
        errors.append("bundle_id_invalid")
    if bundle.policy_id != DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_ID:
        errors.append("policy_id_invalid")
    if bundle.policy_fingerprint != DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_POLICY_FINGERPRINT:
        errors.append("policy_fingerprint_invalid")
    if bundle.contract_policy_fingerprint != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FINGERPRINT:
        errors.append("contract_policy_invalid")
    if bundle.runtime_bundle_fingerprint != RUNTIME_BUNDLE_FINGERPRINT:
        errors.append("runtime_bundle_invalid")
    if bundle.operation != DEVELOPER_TASK_EXECUTION_COMPILE_AST_OPERATION:
        errors.append("operation_invalid")
    contract_policy_bytes = bundle.contract_policy.exact_bytes()
    runner_bytes = bundle.runner.exact_bytes()
    payload_bytes = bundle.payload_manifest.exact_bytes()
    if bundle.contract_policy.file_name != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_FILE_NAME:
        errors.append("contract_policy_file_name_invalid")
    if bundle.contract_policy.size_bytes != len(contract_policy_bytes) or bundle.contract_policy.sha256 != hashlib.sha256(contract_policy_bytes).hexdigest():
        errors.append("contract_policy_identity_invalid")
    if bundle.contract_policy.sha256 != DEVELOPER_TASK_EXECUTION_COMPILE_AST_CONTRACT_POLICY_SHA256:
        errors.append("contract_policy_hash_not_pinned")
    if bundle.runner.file_name != DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_FILE_NAME:
        errors.append("runner_file_name_invalid")
    if bundle.payload_manifest.file_name != DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_FILE_NAME:
        errors.append("payload_file_name_invalid")
    if bundle.runner.size_bytes != len(runner_bytes) or bundle.runner.sha256 != hashlib.sha256(runner_bytes).hexdigest():
        errors.append("runner_identity_invalid")
    if bundle.payload_manifest.size_bytes != len(payload_bytes) or bundle.payload_manifest.sha256 != hashlib.sha256(payload_bytes).hexdigest():
        errors.append("payload_identity_invalid")
    if bundle.runner.sha256 != DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_SHA256:
        errors.append("runner_hash_not_pinned")
    if bundle.payload_manifest.sha256 != DEVELOPER_TASK_EXECUTION_COMPILE_AST_PAYLOAD_SHA256:
        errors.append("payload_hash_not_pinned")
    if bundle.bundle_fingerprint != DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_BUNDLE_FINGERPRINT:
        errors.append("bundle_fingerprint_not_pinned")
    if bundle.bundle_fingerprint != _bundle_fingerprint(contract_policy_bytes, runner_bytes, payload_bytes):
        errors.append("bundle_fingerprint_invalid")
    if bundle.runtime_executable != DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_EXECUTABLE or bundle.runtime_flags != DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNTIME_FLAGS or bundle.runner_path != DEVELOPER_TASK_EXECUTION_COMPILE_AST_RUNNER_PATH or bundle.working_directory != DEVELOPER_TASK_EXECUTION_COMPILE_AST_OUTPUT_ROOT:
        errors.append("launch_contract_invalid")
    if any((
        bundle.sandbox_launched,
        bundle.runtime_lease_issued,
        bundle.runtime_lease_claimed,
        bundle.candidate_interpreter_executed,
        bundle.changed_source_processed,
        bundle.changed_source_ast_parsed,
        bundle.changed_source_compiled,
        bundle.changed_code_executed,
        bundle.reusable_lease_issued,
        bundle.execution_authorized,
    )):
        errors.append("execution_boundary_invalid")
    return tuple(errors)
