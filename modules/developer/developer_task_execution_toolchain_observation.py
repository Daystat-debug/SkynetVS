from __future__ import annotations

import hashlib
import importlib.metadata as importlib_metadata
import json
import os
import platform
import re
import shutil
import struct
import subprocess
import sys
import sysconfig

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from modules.developer.developer_task_execution_environment_inventory import (
    DeveloperTaskExecutionEnvironmentFileEvidence,
    DeveloperTaskExecutionEnvironmentImportEvidence,
    DeveloperTaskExecutionEnvironmentInventoryReport,
    inventory_developer_task_execution_environment,
)
from modules.developer.developer_task_execution_environment_inventory_policy import (
    DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_POLICY_ID,
)
from modules.developer.developer_task_preflight import DeveloperTaskRepositoryPreflightReport
from modules.developer.developer_task_execution_toolchain_observation_policy import (
    DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY,
    DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY_ID,
    DeveloperTaskExecutionToolchainObservationPolicy,
    developer_task_execution_toolchain_observation_policy_fingerprint,
    validate_developer_task_execution_toolchain_observation_policy,
)


_HEX_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_HEX_OBJECT_RE = re.compile(r"^[0-9a-f]{40,64}$")
_REQUIREMENT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_REQUIREMENT_SPEC_RE = re.compile(
    r"^(?P<op>===|==|~=|!=|<=|>=|<|>)(?P<version>[A-Za-z0-9][A-Za-z0-9._+!*-]*)$"
)
_GIT_VERSION_RE = re.compile(r"^git version (?P<version>[^\s]+)$")
_FILE_ATTRIBUTE_REPARSE_POINT = 0x0400
_GIT_ENV_KEYS_TO_CLEAR = {
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_ASKPASS",
    "GIT_CEILING_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_CONFIG",
    "GIT_CONFIG_COUNT",
    "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_NOSYSTEM",
    "GIT_DIR",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_OPTIONAL_LOCKS",
    "GIT_PREFIX",
    "GIT_SSH",
    "GIT_SSH_COMMAND",
    "GIT_TERMINAL_PROMPT",
    "GIT_WORK_TREE",
}
_GIT_ENV_PREFIXES_TO_CLEAR = (
    "GIT_CONFIG_KEY_",
    "GIT_CONFIG_VALUE_",
)


@dataclass(frozen=True)
class DeveloperTaskExecutionHostToolchainIssue:
    code: str
    check: str
    message: str
    expected: str = ""
    actual: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "check": self.check,
            "message": self.message,
            "expected": self.expected,
            "actual": self.actual,
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionRequirementEntryEvidence:
    name: str
    normalized_name: str
    specifier: str
    exact_pin: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "normalized_name": self.normalized_name,
            "specifier": self.specifier,
            "exact_pin": self.exact_pin,
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionRequirementFileEvidence:
    path: str
    kind: str
    git_mode: str
    git_object_id: str
    size_bytes: int
    sha256: str
    entries: tuple[DeveloperTaskExecutionRequirementEntryEvidence, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "kind": self.kind,
            "git_mode": self.git_mode,
            "git_object_id": self.git_object_id,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "entries": [item.to_dict() for item in self.entries],
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionHostDistributionEvidence:
    name: str
    normalized_name: str
    version: str
    installer: str
    direct_url_present: bool
    wheel_tags: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "normalized_name": self.normalized_name,
            "version": self.version,
            "installer": self.installer,
            "direct_url_present": self.direct_url_present,
            "wheel_tags": list(self.wheel_tags),
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionImportDistributionEvidence:
    root: str
    category: str
    distributions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "category": self.category,
            "distributions": list(self.distributions),
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionHostPythonEvidence:
    implementation: str
    version: str
    version_info: tuple[int, int, int]
    architecture_bits: int
    machine: str
    executable: str
    executable_size_bytes: int
    executable_sha256: str
    executable_file_version: str
    executable_product_version: str
    prefix: str
    venv_active: bool
    cache_tag: str
    ext_suffix: str
    soabi: str
    pip_version: str
    distribution_count: int
    distributions: tuple[DeveloperTaskExecutionHostDistributionEvidence, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "implementation": self.implementation,
            "version": self.version,
            "version_info": list(self.version_info),
            "architecture_bits": self.architecture_bits,
            "machine": self.machine,
            "executable": self.executable,
            "executable_size_bytes": self.executable_size_bytes,
            "executable_sha256": self.executable_sha256,
            "executable_file_version": self.executable_file_version,
            "executable_product_version": self.executable_product_version,
            "prefix": self.prefix,
            "venv_active": self.venv_active,
            "cache_tag": self.cache_tag,
            "ext_suffix": self.ext_suffix,
            "soabi": self.soabi,
            "pip_version": self.pip_version,
            "distribution_count": self.distribution_count,
            "distributions": [item.to_dict() for item in self.distributions],
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionHostGitEvidence:
    version: str
    build_options: tuple[str, ...]
    executable: str
    executable_size_bytes: int
    executable_sha256: str
    executable_file_version: str
    executable_product_version: str
    exec_path: str
    install_root: str
    install_tree_file_count: int
    install_tree_total_bytes: int
    install_tree_manifest_sha256: str
    host_installation_is_authority: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "build_options": list(self.build_options),
            "executable": self.executable,
            "executable_size_bytes": self.executable_size_bytes,
            "executable_sha256": self.executable_sha256,
            "executable_file_version": self.executable_file_version,
            "executable_product_version": self.executable_product_version,
            "exec_path": self.exec_path,
            "install_root": self.install_root,
            "install_tree_file_count": self.install_tree_file_count,
            "install_tree_total_bytes": self.install_tree_total_bytes,
            "install_tree_manifest_sha256": self.install_tree_manifest_sha256,
            "host_installation_is_authority": self.host_installation_is_authority,
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionHostPowerShellEvidence:
    edition: str
    version: str
    executable: str
    executable_size_bytes: int
    executable_sha256: str
    executable_file_version: str
    executable_product_version: str
    portable_bundle_selected: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "edition": self.edition,
            "version": self.version,
            "executable": self.executable,
            "executable_size_bytes": self.executable_size_bytes,
            "executable_sha256": self.executable_sha256,
            "executable_file_version": self.executable_file_version,
            "executable_product_version": self.executable_product_version,
            "portable_bundle_selected": self.portable_bundle_selected,
        }


@dataclass(frozen=True)
class DeveloperTaskExecutionHostToolchainReport:
    policy_id: str
    policy_fingerprint: str
    repository_root: str
    head_commit: str
    inventory_policy_fingerprint: str
    inventory_fingerprint: str
    requirement_files: tuple[DeveloperTaskExecutionRequirementFileEvidence, ...]
    host_python: DeveloperTaskExecutionHostPythonEvidence | None
    import_distributions: tuple[DeveloperTaskExecutionImportDistributionEvidence, ...]
    host_git: DeveloperTaskExecutionHostGitEvidence | None
    host_powershell: DeveloperTaskExecutionHostPowerShellEvidence | None
    observation_fingerprint: str
    issues: tuple[DeveloperTaskExecutionHostToolchainIssue, ...]
    source_authority_selected: bool = False
    artifact_download_attempted: bool = False
    dependency_install_attempted: bool = False
    sandbox_launched: bool = False
    candidate_interpreter_executed: bool = False
    reusable_lease_issued: bool = False
    execution_authorized: bool = False

    @property
    def ok(self) -> bool:
        return not self.issues

    @property
    def issue_codes(self) -> tuple[str, ...]:
        return tuple(item.code for item in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "policy_id": self.policy_id,
            "policy_fingerprint": self.policy_fingerprint,
            "repository_root": self.repository_root,
            "head_commit": self.head_commit,
            "inventory_policy_fingerprint": self.inventory_policy_fingerprint,
            "inventory_fingerprint": self.inventory_fingerprint,
            "requirement_files": [item.to_dict() for item in self.requirement_files],
            "host_python": self.host_python.to_dict() if self.host_python is not None else None,
            "import_distributions": [item.to_dict() for item in self.import_distributions],
            "host_git": self.host_git.to_dict() if self.host_git is not None else None,
            "host_powershell": self.host_powershell.to_dict() if self.host_powershell is not None else None,
            "observation_fingerprint": self.observation_fingerprint,
            "issues": [item.to_dict() for item in self.issues],
            "source_authority_selected": self.source_authority_selected,
            "artifact_download_attempted": self.artifact_download_attempted,
            "dependency_install_attempted": self.dependency_install_attempted,
            "sandbox_launched": self.sandbox_launched,
            "candidate_interpreter_executed": self.candidate_interpreter_executed,
            "reusable_lease_issued": self.reusable_lease_issued,
            "execution_authorized": self.execution_authorized,
        }


class _ToolchainFailure(RuntimeError):
    def __init__(self, code: str, check: str, message: str, *, expected: str = "", actual: str = "") -> None:
        self.code = code
        self.check = check
        self.expected = expected
        self.actual = actual
        super().__init__(message)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_distribution_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).casefold()


def _path_key(path: Path) -> str:
    return os.path.normcase(os.path.normpath(os.fspath(path)))


def _absolute_resolved_directory(path: Path) -> Path:
    try:
        resolved = Path(os.path.abspath(os.fspath(path.expanduser()))).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise _ToolchainFailure(
            "toolchain_observation_project_root_invalid",
            "project_root",
            "Project root could not be resolved.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc
    if not resolved.is_dir():
        raise _ToolchainFailure(
            "toolchain_observation_project_root_invalid",
            "project_root",
            "Project root must be a directory.",
            actual=str(resolved),
        )
    return resolved


def _inventory_fingerprint_payload(report: DeveloperTaskExecutionEnvironmentInventoryReport) -> dict[str, Any]:
    return {
        "policy_id": report.policy_id,
        "policy_fingerprint": report.policy_fingerprint,
        "repository_root": report.repository_root,
        "head_commit": report.head_commit,
        "tracked_file_count": report.tracked_file_count,
        "tracked_python_file_count": report.tracked_python_file_count,
        "python_total_bytes": report.python_total_bytes,
        "python_tree_fingerprint": report.python_tree_fingerprint,
        "dependency_files": [item.to_dict() for item in report.dependency_files],
        "import_roots": [item.to_dict() for item in report.import_roots],
        "process_calls": [item.to_dict() for item in report.process_calls],
        "pipeline_flow_count": report.pipeline_flow_count,
        "pipeline_step_count": report.pipeline_step_count,
        "pipeline_steps": [item.to_dict() for item in report.pipeline_steps],
        "host_sensitive_files": [item.to_dict() for item in report.host_sensitive_files],
        "sandbox_launched": False,
        "candidate_interpreter_executed": False,
        "dependency_install_attempted": False,
        "reusable_lease_issued": False,
        "execution_authorized": False,
    }


def _validate_inventory_report(
    inventory_report: DeveloperTaskExecutionEnvironmentInventoryReport,
    project_root: Path,
) -> tuple[Path, str]:
    if not isinstance(inventory_report, DeveloperTaskExecutionEnvironmentInventoryReport):
        raise TypeError("inventory_report must be DeveloperTaskExecutionEnvironmentInventoryReport")
    if not isinstance(project_root, Path):
        raise TypeError("project_root must be pathlib.Path")
    if not inventory_report.ok:
        raise _ToolchainFailure(
            "toolchain_observation_inventory_report_failed",
            "inventory_report",
            "Executable environment inventory report is not successful.",
            actual=",".join(inventory_report.issue_codes),
        )
    if inventory_report.policy_id != DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_POLICY_ID:
        raise _ToolchainFailure(
            "toolchain_observation_inventory_report_invalid",
            "inventory_report",
            "Executable environment inventory policy identifier changed.",
            expected=DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_POLICY_ID,
            actual=inventory_report.policy_id,
        )
    if inventory_report.policy_fingerprint != DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_POLICY_FINGERPRINT:
        raise _ToolchainFailure(
            "toolchain_observation_inventory_report_invalid",
            "inventory_report",
            "Executable environment inventory policy fingerprint changed.",
            expected=DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_POLICY_FINGERPRINT,
            actual=inventory_report.policy_fingerprint,
        )
    if not _HEX_OBJECT_RE.fullmatch(inventory_report.head_commit):
        raise _ToolchainFailure(
            "toolchain_observation_inventory_report_invalid",
            "inventory_report",
            "Executable environment inventory HEAD identity is invalid.",
            actual=inventory_report.head_commit,
        )
    if not _HEX_SHA256_RE.fullmatch(inventory_report.inventory_fingerprint):
        raise _ToolchainFailure(
            "toolchain_observation_inventory_report_invalid",
            "inventory_report",
            "Executable environment inventory fingerprint is invalid.",
            actual=inventory_report.inventory_fingerprint,
        )
    if not _HEX_SHA256_RE.fullmatch(inventory_report.python_tree_fingerprint):
        raise _ToolchainFailure(
            "toolchain_observation_inventory_report_invalid",
            "inventory_report",
            "Executable environment Python-tree fingerprint is invalid.",
            actual=inventory_report.python_tree_fingerprint,
        )
    if any(
        (
            inventory_report.sandbox_launched,
            inventory_report.candidate_interpreter_executed,
            inventory_report.dependency_install_attempted,
            inventory_report.reusable_lease_issued,
            inventory_report.execution_authorized,
        )
    ):
        raise _ToolchainFailure(
            "toolchain_observation_inventory_report_invalid",
            "inventory_report",
            "Executable environment inventory report contains execution authority.",
        )
    try:
        expected_fingerprint = _sha256(
            _canonical_json(_inventory_fingerprint_payload(inventory_report)).encode("utf-8")
        )
    except Exception as exc:
        raise _ToolchainFailure(
            "toolchain_observation_inventory_report_invalid",
            "inventory_report",
            "Executable environment inventory nested evidence is invalid.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc
    if inventory_report.inventory_fingerprint != expected_fingerprint:
        raise _ToolchainFailure(
            "toolchain_observation_inventory_report_invalid",
            "inventory_report",
            "Executable environment inventory canonical fingerprint does not match its evidence.",
            expected=expected_fingerprint,
            actual=inventory_report.inventory_fingerprint,
        )

    root = _absolute_resolved_directory(project_root)
    try:
        report_root = Path(inventory_report.repository_root).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise _ToolchainFailure(
            "toolchain_observation_inventory_report_invalid",
            "inventory_report",
            "Executable environment inventory repository root could not be resolved.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc
    if _path_key(root) != _path_key(report_root):
        raise _ToolchainFailure(
            "toolchain_observation_repository_root_mismatch",
            "inventory_report",
            "Project root does not match the executable environment inventory report.",
            expected=str(root),
            actual=str(report_root),
        )
    return root, inventory_report.head_commit



def _rebuild_canonical_inventory_report(
    inventory_report: DeveloperTaskExecutionEnvironmentInventoryReport,
    repository_root: Path,
    head_commit: str,
) -> None:
    synthetic_preflight = DeveloperTaskRepositoryPreflightReport(
        manifest_fingerprint="0" * 64,
        project_root=str(repository_root),
        repository_root=str(repository_root),
        head_commit=head_commit,
        resolved_base_commit=head_commit,
        dirty_categories=(),
        issues=(),
    )
    rebuilt = inventory_developer_task_execution_environment(
        synthetic_preflight,
        project_root=repository_root,
    )
    if not rebuilt.ok:
        raise _ToolchainFailure(
            "toolchain_observation_inventory_revalidation_failed",
            "inventory_revalidation",
            "Canonical V1C0A inventory could not be rebuilt from the pinned commit.",
            actual=",".join(rebuilt.issue_codes),
        )
    if rebuilt != inventory_report:
        raise _ToolchainFailure(
            "toolchain_observation_inventory_report_noncanonical",
            "inventory_revalidation",
            "Provided V1C0A report does not equal a fresh canonical inventory of the pinned commit.",
            expected=rebuilt.inventory_fingerprint,
            actual=inventory_report.inventory_fingerprint,
        )

def _require_windows() -> None:
    if sys.platform != DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY.required_platform:
        raise _ToolchainFailure(
            "toolchain_observation_windows_required",
            "platform",
            "Canonical host toolchain observation requires Windows.",
            expected=DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY.required_platform,
            actual=sys.platform,
        )


def _is_reparse(stat_result: os.stat_result) -> bool:
    attributes = int(getattr(stat_result, "st_file_attributes", 0) or 0)
    return bool(attributes & _FILE_ATTRIBUTE_REPARSE_POINT)


def _require_regular_non_reparse_file(path: Path, *, check: str) -> os.stat_result:
    try:
        stat_result = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise _ToolchainFailure(
            "toolchain_observation_file_unavailable",
            check,
            "Observed executable or toolchain file is unavailable.",
            actual=f"{path}: {type(exc).__name__}: {exc}",
        ) from exc
    if path.is_symlink() or _is_reparse(stat_result) or not path.is_file():
        raise _ToolchainFailure(
            "toolchain_observation_file_identity_invalid",
            check,
            "Observed executable or toolchain file must be a regular non-reparse file.",
            actual=str(path),
        )
    return stat_result


def _windows_file_version_strings(path: Path) -> tuple[str, str]:
    if sys.platform != "win32":
        return "", ""
    try:
        import ctypes
        from ctypes import wintypes

        version = ctypes.WinDLL("version", use_last_error=True)
        get_size = version.GetFileVersionInfoSizeW
        get_size.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
        get_size.restype = wintypes.DWORD
        get_info = version.GetFileVersionInfoW
        get_info.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID]
        get_info.restype = wintypes.BOOL
        query = version.VerQueryValueW
        query.argtypes = [wintypes.LPCVOID, wintypes.LPCWSTR, ctypes.POINTER(wintypes.LPVOID), ctypes.POINTER(wintypes.UINT)]
        query.restype = wintypes.BOOL

        ignored = wintypes.DWORD(0)
        size = int(get_size(str(path), ctypes.byref(ignored)))
        if size <= 0:
            return "", ""
        buffer = ctypes.create_string_buffer(size)
        if not get_info(str(path), 0, size, buffer):
            return "", ""

        translation_ptr = wintypes.LPVOID()
        translation_len = wintypes.UINT(0)
        translations: list[tuple[int, int]] = []
        if query(buffer, r"\VarFileInfo\Translation", ctypes.byref(translation_ptr), ctypes.byref(translation_len)):
            raw = ctypes.string_at(translation_ptr, int(translation_len.value))
            for offset in range(0, len(raw) - 3, 4):
                lang, codepage = struct.unpack_from("<HH", raw, offset)
                translations.append((lang, codepage))
        if not translations:
            translations.append((0x0409, 0x04B0))

        def _query_string(name: str) -> str:
            for lang, codepage in translations:
                pointer = wintypes.LPVOID()
                length = wintypes.UINT(0)
                subblock = rf"\StringFileInfo\{lang:04x}{codepage:04x}\{name}"
                if query(buffer, subblock, ctypes.byref(pointer), ctypes.byref(length)) and length.value:
                    return ctypes.wstring_at(pointer, int(length.value)).rstrip("\x00")
            return ""

        return _query_string("FileVersion"), _query_string("ProductVersion")
    except Exception:
        return "", ""


def _discover_git_executable() -> tuple[Path, Path]:
    located = shutil.which("git.exe") or shutil.which("git")
    if not located:
        raise _ToolchainFailure(
            "toolchain_observation_git_unavailable",
            "git_discovery",
            "Git executable is unavailable on the host PATH.",
        )
    try:
        executable = Path(located).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise _ToolchainFailure(
            "toolchain_observation_git_identity_invalid",
            "git_discovery",
            "Git executable path could not be resolved.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc
    _require_regular_non_reparse_file(executable, check="git_discovery")
    if executable.name.casefold() != "git.exe" or executable.parent.name.casefold() not in {"cmd", "bin"}:
        raise _ToolchainFailure(
            "toolchain_observation_git_identity_invalid",
            "git_discovery",
            "Git executable must resolve to the Git for Windows cmd/bin launcher surface.",
            actual=str(executable),
        )
    install_root = executable.parent.parent.resolve(strict=True)
    if not install_root.is_dir():
        raise _ToolchainFailure(
            "toolchain_observation_git_identity_invalid",
            "git_discovery",
            "Git installation root is invalid.",
            actual=str(install_root),
        )
    return executable, install_root


def _build_git_environment(install_root: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for key in ("SystemRoot", "WINDIR", "COMSPEC"):
        value = os.environ.get(key)
        if value:
            env[key] = value
    system_root = env.get("SystemRoot") or env.get("WINDIR") or r"C:\Windows"
    path_parts = [
        install_root / "cmd",
        install_root / "mingw64" / "bin",
        install_root / "usr" / "bin",
        Path(system_root) / "System32",
    ]
    env["PATH"] = os.pathsep.join(str(path) for path in path_parts)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_COUNT"] = "0"
    env["GIT_NO_LAZY_FETCH"] = "1"
    env["GIT_NO_REPLACE_OBJECTS"] = "1"
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = ""
    env["SSH_ASKPASS"] = ""
    env["GCM_INTERACTIVE"] = "Never"
    env["GIT_PAGER"] = "cat"
    return env


def _run_process(
    command: list[str],
    *,
    check: str,
    env: dict[str, str],
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            timeout=DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY.process_timeout_seconds,
            check=False,
            env=env,
            cwd=str(cwd) if cwd is not None else None,
        )
    except subprocess.TimeoutExpired as exc:
        raise _ToolchainFailure(
            "toolchain_observation_process_timeout",
            check,
            "Host toolchain observation process timed out.",
            actual=command[0],
        ) from exc
    except OSError as exc:
        raise _ToolchainFailure(
            "toolchain_observation_process_failed",
            check,
            "Host toolchain observation process could not be started.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc


def _decode_process_text(result: subprocess.CompletedProcess[bytes], *, check: str) -> str:
    if result.returncode != 0:
        text = (result.stderr or result.stdout).decode("utf-8", errors="replace").strip()
        if len(text) > 1000:
            text = text[:997] + "..."
        raise _ToolchainFailure(
            "toolchain_observation_process_nonzero",
            check,
            "Host toolchain observation process returned a nonzero status.",
            actual=text,
        )
    try:
        return result.stdout.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise _ToolchainFailure(
            "toolchain_observation_process_output_invalid",
            check,
            "Host toolchain observation process returned non-UTF-8 output.",
            actual=str(exc),
        ) from exc


def _git_command(
    executable: Path,
    install_root: Path,
    *args: str,
    repository_root: Path | None = None,
) -> str:
    command = [str(executable)]
    if repository_root is not None:
        command.extend(["--no-optional-locks", "--no-replace-objects", "-c", "core.fsmonitor=false", "-C", str(repository_root)])
    command.extend(args)
    result = _run_process(
        command,
        check="git_command",
        env=_build_git_environment(install_root),
    )
    return _decode_process_text(result, check="git_command")


def _require_current_head(executable: Path, install_root: Path, repository_root: Path, expected_head: str) -> None:
    actual = _git_command(
        executable,
        install_root,
        "rev-parse",
        "--verify",
        "HEAD^{commit}",
        repository_root=repository_root,
    ).strip().casefold()
    if actual != expected_head:
        raise _ToolchainFailure(
            "toolchain_observation_repository_changed",
            "head",
            "Repository HEAD changed relative to the executable environment inventory report.",
            expected=expected_head,
            actual=actual,
        )


def _read_committed_blob(
    executable: Path,
    install_root: Path,
    repository_root: Path,
    evidence: DeveloperTaskExecutionEnvironmentFileEvidence,
) -> bytes:
    if evidence.kind not in DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY.allowed_dependency_kinds:
        raise _ToolchainFailure(
            "toolchain_observation_dependency_kind_invalid",
            "dependency_declarations",
            "Executable environment inventory contains an unsupported dependency metadata kind.",
            actual=f"{evidence.path}:{evidence.kind}",
        )
    if not _HEX_OBJECT_RE.fullmatch(evidence.git_object_id) or not _HEX_SHA256_RE.fullmatch(evidence.sha256):
        raise _ToolchainFailure(
            "toolchain_observation_dependency_identity_invalid",
            "dependency_declarations",
            "Committed dependency declaration identity is invalid.",
            actual=evidence.path,
        )
    command = [
        str(executable),
        "--no-optional-locks",
        "--no-replace-objects",
        "-c",
        "core.fsmonitor=false",
        "-C",
        str(repository_root),
        "cat-file",
        "blob",
        evidence.git_object_id,
    ]
    result = _run_process(command, check="dependency_blob", env=_build_git_environment(install_root))
    if result.returncode != 0:
        _decode_process_text(result, check="dependency_blob")
    data = result.stdout
    if len(data) != evidence.size_bytes or _sha256(data) != evidence.sha256:
        raise _ToolchainFailure(
            "toolchain_observation_dependency_identity_changed",
            "dependency_declarations",
            "Committed dependency declaration bytes do not match V1C0A evidence.",
            expected=f"{evidence.size_bytes}:{evidence.sha256}",
            actual=f"{len(data)}:{_sha256(data)}",
        )
    return data


def _parse_requirement_line(line: str, *, path: str, line_number: int) -> DeveloperTaskExecutionRequirementEntryEvidence | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if "#" in stripped:
        stripped = stripped.split("#", 1)[0].rstrip()
    if not stripped:
        return None
    if stripped.startswith("-") or " @ " in stripped or stripped.startswith(("git+", "http://", "https://", "file:")):
        raise _ToolchainFailure(
            "toolchain_observation_requirement_syntax_unsupported",
            "requirements_parser",
            "Dependency declarations may not contain options, direct URLs, VCS references, or local paths.",
            actual=f"{path}:{line_number}:{stripped}",
        )
    if ";" in stripped or "\\" in stripped or "/" in stripped:
        raise _ToolchainFailure(
            "toolchain_observation_requirement_syntax_unsupported",
            "requirements_parser",
            "Dependency declaration syntax is outside strict_simple_requirements_v1.",
            actual=f"{path}:{line_number}:{stripped}",
        )

    match = re.fullmatch(r"(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)(?P<spec>.*)", stripped)
    if match is None or not _REQUIREMENT_NAME_RE.fullmatch(match.group("name")):
        raise _ToolchainFailure(
            "toolchain_observation_requirement_syntax_invalid",
            "requirements_parser",
            "Dependency declaration package name is invalid.",
            actual=f"{path}:{line_number}:{stripped}",
        )
    name = match.group("name")
    specifier = match.group("spec").replace(" ", "")
    if not specifier:
        raise _ToolchainFailure(
            "toolchain_observation_requirement_unbounded",
            "requirements_parser",
            "Dependency declaration must include at least one explicit version constraint.",
            actual=f"{path}:{line_number}:{stripped}",
        )
    parts = specifier.split(",")
    if any(not part for part in parts):
        raise _ToolchainFailure(
            "toolchain_observation_requirement_syntax_invalid",
            "requirements_parser",
            "Dependency declaration contains an invalid version specifier list.",
            actual=f"{path}:{line_number}:{specifier}",
        )
    parsed_parts: list[tuple[str, str]] = []
    for part in parts:
        spec_match = _REQUIREMENT_SPEC_RE.fullmatch(part)
        if spec_match is None:
            raise _ToolchainFailure(
                "toolchain_observation_requirement_syntax_invalid",
                "requirements_parser",
                "Dependency declaration contains an unsupported version specifier.",
                actual=f"{path}:{line_number}:{part}",
            )
        parsed_parts.append((spec_match.group("op"), spec_match.group("version")))
    exact_pin = len(parsed_parts) == 1 and parsed_parts[0][0] in {"==", "==="} and "*" not in parsed_parts[0][1]
    return DeveloperTaskExecutionRequirementEntryEvidence(
        name=name,
        normalized_name=_normalize_distribution_name(name),
        specifier=specifier,
        exact_pin=exact_pin,
    )


def _parse_requirement_file(evidence: DeveloperTaskExecutionEnvironmentFileEvidence, data: bytes) -> tuple[DeveloperTaskExecutionRequirementEntryEvidence, ...]:
    if evidence.kind not in {"requirements", "constraints"}:
        return ()
    try:
        text = data.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        raise _ToolchainFailure(
            "toolchain_observation_requirement_encoding_invalid",
            "requirements_parser",
            "Dependency declaration must be valid UTF-8.",
            actual=f"{evidence.path}:{exc}",
        ) from exc
    entries: list[DeveloperTaskExecutionRequirementEntryEvidence] = []
    seen: set[str] = set()
    for line_number, line in enumerate(text.splitlines(), start=1):
        entry = _parse_requirement_line(line, path=evidence.path, line_number=line_number)
        if entry is None:
            continue
        if entry.normalized_name in seen:
            raise _ToolchainFailure(
                "toolchain_observation_requirement_duplicate",
                "requirements_parser",
                "Dependency declaration contains a duplicate normalized package name.",
                actual=f"{evidence.path}:{entry.normalized_name}",
            )
        seen.add(entry.normalized_name)
        entries.append(entry)
    if len(entries) > DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY.max_requirements_per_file:
        raise _ToolchainFailure(
            "toolchain_observation_requirement_limit_exceeded",
            "requirements_parser",
            "Dependency declaration contains too many requirement entries.",
            actual=f"{evidence.path}:{len(entries)}",
        )
    return tuple(entries)


def _observe_requirement_files(
    inventory_report: DeveloperTaskExecutionEnvironmentInventoryReport,
    executable: Path,
    install_root: Path,
    repository_root: Path,
) -> tuple[DeveloperTaskExecutionRequirementFileEvidence, ...]:
    files = tuple(sorted(inventory_report.dependency_files, key=lambda item: item.path))
    if len(files) > DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY.max_requirement_files:
        raise _ToolchainFailure(
            "toolchain_observation_requirement_file_limit_exceeded",
            "dependency_declarations",
            "Too many committed dependency metadata files are present.",
            actual=str(len(files)),
        )
    result: list[DeveloperTaskExecutionRequirementFileEvidence] = []
    for item in files:
        data = _read_committed_blob(executable, install_root, repository_root, item)
        entries = _parse_requirement_file(item, data)
        result.append(
            DeveloperTaskExecutionRequirementFileEvidence(
                path=item.path,
                kind=item.kind,
                git_mode=item.git_mode,
                git_object_id=item.git_object_id,
                size_bytes=item.size_bytes,
                sha256=item.sha256,
                entries=entries,
            )
        )
    return tuple(result)


def _distribution_wheel_tags(distribution: importlib_metadata.Distribution) -> tuple[str, ...]:
    wheel_text = distribution.read_text("WHEEL") or ""
    tags = sorted(
        {
            line.split(":", 1)[1].strip()
            for line in wheel_text.splitlines()
            if line.casefold().startswith("tag:") and ":" in line and line.split(":", 1)[1].strip()
        }
    )
    if len(tags) > DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY.max_wheel_tags_per_distribution:
        raise _ToolchainFailure(
            "toolchain_observation_distribution_metadata_invalid",
            "python_distributions",
            "Installed distribution exposes too many wheel tags.",
            actual=str(len(tags)),
        )
    return tuple(tags)


def _observe_distributions() -> tuple[DeveloperTaskExecutionHostDistributionEvidence, ...]:
    rows: list[DeveloperTaskExecutionHostDistributionEvidence] = []
    seen: set[str] = set()
    try:
        distributions = list(importlib_metadata.distributions())
    except Exception as exc:
        raise _ToolchainFailure(
            "toolchain_observation_distribution_scan_failed",
            "python_distributions",
            "Installed Python distributions could not be enumerated.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc
    if len(distributions) > DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY.max_distributions:
        raise _ToolchainFailure(
            "toolchain_observation_distribution_limit_exceeded",
            "python_distributions",
            "Installed distribution count exceeds the observation policy limit.",
            actual=str(len(distributions)),
        )
    for distribution in distributions:
        name = str(distribution.metadata.get("Name") or "").strip()
        version = str(distribution.version or "").strip()
        if not name or not version:
            raise _ToolchainFailure(
                "toolchain_observation_distribution_metadata_invalid",
                "python_distributions",
                "Installed distribution is missing its canonical name or version.",
            )
        normalized = _normalize_distribution_name(name)
        if normalized in seen:
            raise _ToolchainFailure(
                "toolchain_observation_distribution_duplicate",
                "python_distributions",
                "Installed environment contains duplicate normalized distribution names.",
                actual=normalized,
            )
        seen.add(normalized)
        installer = (distribution.read_text("INSTALLER") or "").strip()
        direct_url_present = bool(distribution.read_text("direct_url.json"))
        rows.append(
            DeveloperTaskExecutionHostDistributionEvidence(
                name=name,
                normalized_name=normalized,
                version=version,
                installer=installer,
                direct_url_present=direct_url_present,
                wheel_tags=_distribution_wheel_tags(distribution),
            )
        )
    return tuple(sorted(rows, key=lambda item: (item.normalized_name, item.version, item.name.casefold())))


def _observe_host_python() -> DeveloperTaskExecutionHostPythonEvidence:
    executable = Path(sys.executable).resolve(strict=True)
    stat_result = _require_regular_non_reparse_file(executable, check="python_executable")
    file_version, product_version = _windows_file_version_strings(executable)
    distributions = _observe_distributions()
    try:
        pip_version = importlib_metadata.version("pip")
    except importlib_metadata.PackageNotFoundError:
        pip_version = ""
    return DeveloperTaskExecutionHostPythonEvidence(
        implementation=platform.python_implementation(),
        version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        version_info=(sys.version_info.major, sys.version_info.minor, sys.version_info.micro),
        architecture_bits=struct.calcsize("P") * 8,
        machine=platform.machine(),
        executable=str(executable),
        executable_size_bytes=int(stat_result.st_size),
        executable_sha256=_hash_file(executable),
        executable_file_version=file_version,
        executable_product_version=product_version,
        prefix=str(Path(sys.prefix).resolve(strict=True)),
        venv_active=sys.prefix != sys.base_prefix,
        cache_tag=str(getattr(sys.implementation, "cache_tag", "") or ""),
        ext_suffix=str(sysconfig.get_config_var("EXT_SUFFIX") or ""),
        soabi=str(sysconfig.get_config_var("SOABI") or ""),
        pip_version=str(pip_version),
        distribution_count=len(distributions),
        distributions=distributions,
    )


def _observe_import_distribution_mapping(
    import_roots: tuple[DeveloperTaskExecutionEnvironmentImportEvidence, ...],
    distributions: tuple[DeveloperTaskExecutionHostDistributionEvidence, ...],
) -> tuple[DeveloperTaskExecutionImportDistributionEvidence, ...]:
    installed = {item.normalized_name for item in distributions}
    try:
        package_map = importlib_metadata.packages_distributions()
    except Exception as exc:
        raise _ToolchainFailure(
            "toolchain_observation_distribution_mapping_failed",
            "import_distribution_mapping",
            "Import-root to distribution mapping could not be enumerated.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc
    stdlib_roots = set(getattr(sys, "stdlib_module_names", ()))
    project_roots = set(DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY.project_import_roots)
    rows: list[DeveloperTaskExecutionImportDistributionEvidence] = []
    seen: set[str] = set()
    for evidence in sorted(import_roots, key=lambda item: item.root):
        root = evidence.root
        if root in seen:
            raise _ToolchainFailure(
                "toolchain_observation_import_root_duplicate",
                "import_distribution_mapping",
                "Executable environment inventory contains duplicate import roots.",
                actual=root,
            )
        seen.add(root)
        mapped = tuple(
            sorted(
                {
                    _normalize_distribution_name(name)
                    for name in package_map.get(root, ())
                    if _normalize_distribution_name(name) in installed
                }
            )
        )
        if mapped:
            category = "distribution"
        elif root in stdlib_roots:
            category = "stdlib"
        elif root in project_roots:
            category = "project"
        else:
            category = "unresolved"
        rows.append(
            DeveloperTaskExecutionImportDistributionEvidence(
                root=root,
                category=category,
                distributions=mapped,
            )
        )
    return tuple(rows)


def _relative_under(root: Path, path: Path) -> str:
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise _ToolchainFailure(
            "toolchain_observation_git_identity_invalid",
            "git_identity",
            "Git exec-path escapes the discovered Git installation root.",
            expected=str(root),
            actual=str(path),
        ) from exc
    return relative.as_posix()


def _tree_metadata_snapshot(root: Path) -> tuple[tuple[str, int, int], ...]:
    rows: list[tuple[str, int, int]] = []
    stack = [root]
    seen_case: dict[str, str] = {}
    policy = DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY
    while stack:
        directory = stack.pop()
        try:
            entries = sorted(os.scandir(directory), key=lambda item: (item.name.casefold(), item.name))
        except OSError as exc:
            raise _ToolchainFailure(
                "toolchain_observation_git_tree_scan_failed",
                "git_tree",
                "Git installation tree could not be enumerated.",
                actual=f"{directory}: {type(exc).__name__}: {exc}",
            ) from exc
        for entry in entries:
            path = Path(entry.path)
            relative = _relative_under(root, path)
            key = relative.casefold()
            previous = seen_case.get(key)
            if previous is not None and previous != relative:
                raise _ToolchainFailure(
                    "toolchain_observation_git_tree_case_collision",
                    "git_tree",
                    "Git installation tree contains a Windows case-insensitive path collision.",
                    expected=previous,
                    actual=relative,
                )
            seen_case[key] = relative
            try:
                stat_result = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise _ToolchainFailure(
                    "toolchain_observation_git_tree_scan_failed",
                    "git_tree",
                    "Git installation tree entry could not be stat-ed.",
                    actual=f"{relative}: {type(exc).__name__}: {exc}",
                ) from exc
            if entry.is_symlink() or _is_reparse(stat_result):
                raise _ToolchainFailure(
                    "toolchain_observation_git_tree_reparse",
                    "git_tree",
                    "Git installation tree may not contain reparse points or symlinks.",
                    actual=relative,
                )
            if entry.is_dir(follow_symlinks=False):
                stack.append(path)
                continue
            if not entry.is_file(follow_symlinks=False):
                raise _ToolchainFailure(
                    "toolchain_observation_git_tree_entry_invalid",
                    "git_tree",
                    "Git installation tree contains a non-file non-directory entry.",
                    actual=relative,
                )
            size = int(stat_result.st_size)
            if size < 0 or size > policy.max_git_file_bytes:
                raise _ToolchainFailure(
                    "toolchain_observation_git_file_limit_exceeded",
                    "git_tree",
                    "Git installation file exceeds the observation size limit.",
                    actual=f"{relative}:{size}",
                )
            rows.append((relative, size, int(stat_result.st_mtime_ns)))
            if len(rows) > policy.max_git_tree_files:
                raise _ToolchainFailure(
                    "toolchain_observation_git_tree_file_limit_exceeded",
                    "git_tree",
                    "Git installation tree file count exceeds the observation policy limit.",
                    actual=str(len(rows)),
                )
    return tuple(sorted(rows, key=lambda item: item[0]))


def _hash_git_tree(root: Path) -> tuple[int, int, str]:
    before = _tree_metadata_snapshot(root)
    total = 0
    manifest_rows: list[dict[str, Any]] = []
    for relative, size, mtime_ns in before:
        total += size
        if total > DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY.max_git_tree_total_bytes:
            raise _ToolchainFailure(
                "toolchain_observation_git_tree_size_limit_exceeded",
                "git_tree",
                "Git installation tree exceeds the observation total-size limit.",
                actual=str(total),
            )
        path = root / Path(*relative.split("/"))
        digest = _hash_file(path)
        try:
            after_stat = path.stat(follow_symlinks=False)
        except OSError as exc:
            raise _ToolchainFailure(
                "toolchain_observation_git_tree_changed",
                "git_tree",
                "Git installation tree changed while it was being hashed.",
                actual=f"{relative}: {type(exc).__name__}: {exc}",
            ) from exc
        if int(after_stat.st_size) != size or int(after_stat.st_mtime_ns) != mtime_ns or _is_reparse(after_stat):
            raise _ToolchainFailure(
                "toolchain_observation_git_tree_changed",
                "git_tree",
                "Git installation tree changed while it was being hashed.",
                actual=relative,
            )
        manifest_rows.append({"path": relative, "size_bytes": size, "sha256": digest})
    after = _tree_metadata_snapshot(root)
    if before != after:
        raise _ToolchainFailure(
            "toolchain_observation_git_tree_changed",
            "git_tree",
            "Git installation tree changed during observation.",
        )
    return len(manifest_rows), total, _sha256(_canonical_json(manifest_rows).encode("utf-8"))


def _observe_git(executable: Path, install_root: Path) -> DeveloperTaskExecutionHostGitEvidence:
    stat_before = _require_regular_non_reparse_file(executable, check="git_executable")
    executable_sha_before = _hash_file(executable)
    version_text = _git_command(executable, install_root, "--version").strip()
    version_match = _GIT_VERSION_RE.fullmatch(version_text)
    if version_match is None:
        raise _ToolchainFailure(
            "toolchain_observation_git_version_invalid",
            "git_identity",
            "Git version output is not canonical.",
            actual=version_text,
        )
    build_options = tuple(
        line.strip()
        for line in _git_command(executable, install_root, "version", "--build-options").splitlines()
        if line.strip()
    )
    exec_path_text = _git_command(executable, install_root, "--exec-path").strip()
    try:
        exec_path = Path(exec_path_text).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise _ToolchainFailure(
            "toolchain_observation_git_identity_invalid",
            "git_identity",
            "Git exec-path could not be resolved.",
            actual=f"{exec_path_text}: {type(exc).__name__}: {exc}",
        ) from exc
    _relative_under(install_root, exec_path)
    file_count, total_bytes, manifest_sha256 = _hash_git_tree(install_root)
    stat_after = _require_regular_non_reparse_file(executable, check="git_executable")
    executable_sha_after = _hash_file(executable)
    if (
        int(stat_before.st_size) != int(stat_after.st_size)
        or int(stat_before.st_mtime_ns) != int(stat_after.st_mtime_ns)
        or executable_sha_before != executable_sha_after
    ):
        raise _ToolchainFailure(
            "toolchain_observation_git_identity_changed",
            "git_identity",
            "Git executable changed during observation.",
        )
    file_version, product_version = _windows_file_version_strings(executable)
    return DeveloperTaskExecutionHostGitEvidence(
        version=version_match.group("version"),
        build_options=build_options,
        executable=str(executable),
        executable_size_bytes=int(stat_after.st_size),
        executable_sha256=executable_sha_after,
        executable_file_version=file_version,
        executable_product_version=product_version,
        exec_path=str(exec_path),
        install_root=str(install_root),
        install_tree_file_count=file_count,
        install_tree_total_bytes=total_bytes,
        install_tree_manifest_sha256=manifest_sha256,
        host_installation_is_authority=False,
    )


def _get_windows_directory() -> Path:
    if sys.platform != "win32":
        raise _ToolchainFailure(
            "toolchain_observation_windows_required",
            "powershell_identity",
            "Windows directory discovery requires Windows.",
        )
    try:
        import ctypes

        buffer = ctypes.create_unicode_buffer(32768)
        length = int(ctypes.windll.kernel32.GetWindowsDirectoryW(buffer, len(buffer)))
        if length <= 0 or length >= len(buffer):
            raise OSError("GetWindowsDirectoryW failed")
        return Path(buffer.value).resolve(strict=True)
    except Exception as exc:
        raise _ToolchainFailure(
            "toolchain_observation_windows_directory_failed",
            "powershell_identity",
            "Windows directory could not be resolved from the operating system.",
            actual=f"{type(exc).__name__}: {exc}",
        ) from exc


def _observe_powershell() -> DeveloperTaskExecutionHostPowerShellEvidence:
    windows_directory = _get_windows_directory()
    executable = (windows_directory / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe").resolve(strict=True)
    stat_result = _require_regular_non_reparse_file(executable, check="powershell_executable")
    env = {
        "SystemRoot": str(windows_directory),
        "WINDIR": str(windows_directory),
        "PATH": os.pathsep.join((str(executable.parent), str(windows_directory / "System32"))),
    }
    command = [
        str(executable),
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; Write-Output ($PSVersionTable.PSEdition + '|' + $PSVersionTable.PSVersion.ToString())",
    ]
    text = _decode_process_text(
        _run_process(command, check="powershell_version", env=env),
        check="powershell_version",
    ).strip()
    if "|" not in text:
        raise _ToolchainFailure(
            "toolchain_observation_powershell_version_invalid",
            "powershell_version",
            "Windows PowerShell version output is not canonical.",
            actual=text,
        )
    edition, version = (part.strip() for part in text.split("|", 1))
    if not edition or not version:
        raise _ToolchainFailure(
            "toolchain_observation_powershell_version_invalid",
            "powershell_version",
            "Windows PowerShell version output is incomplete.",
            actual=text,
        )
    file_version, product_version = _windows_file_version_strings(executable)
    return DeveloperTaskExecutionHostPowerShellEvidence(
        edition=edition,
        version=version,
        executable=str(executable),
        executable_size_bytes=int(stat_result.st_size),
        executable_sha256=_hash_file(executable),
        executable_file_version=file_version,
        executable_product_version=product_version,
        portable_bundle_selected=False,
    )


def _observation_fingerprint_payload(report: DeveloperTaskExecutionHostToolchainReport) -> dict[str, Any]:
    return {
        "policy_id": report.policy_id,
        "policy_fingerprint": report.policy_fingerprint,
        "repository_root": report.repository_root,
        "head_commit": report.head_commit,
        "inventory_policy_fingerprint": report.inventory_policy_fingerprint,
        "inventory_fingerprint": report.inventory_fingerprint,
        "requirement_files": [item.to_dict() for item in report.requirement_files],
        "host_python": report.host_python.to_dict() if report.host_python is not None else None,
        "import_distributions": [item.to_dict() for item in report.import_distributions],
        "host_git": report.host_git.to_dict() if report.host_git is not None else None,
        "host_powershell": report.host_powershell.to_dict() if report.host_powershell is not None else None,
        "issues": [item.to_dict() for item in report.issues],
        "source_authority_selected": False,
        "artifact_download_attempted": False,
        "dependency_install_attempted": False,
        "sandbox_launched": False,
        "candidate_interpreter_executed": False,
        "reusable_lease_issued": False,
        "execution_authorized": False,
    }


def _build_report(
    *,
    repository_root: Path,
    head_commit: str,
    inventory_fingerprint: str,
    requirement_files: tuple[DeveloperTaskExecutionRequirementFileEvidence, ...] = (),
    host_python: DeveloperTaskExecutionHostPythonEvidence | None = None,
    import_distributions: tuple[DeveloperTaskExecutionImportDistributionEvidence, ...] = (),
    host_git: DeveloperTaskExecutionHostGitEvidence | None = None,
    host_powershell: DeveloperTaskExecutionHostPowerShellEvidence | None = None,
    issues: tuple[DeveloperTaskExecutionHostToolchainIssue, ...] = (),
) -> DeveloperTaskExecutionHostToolchainReport:
    provisional = DeveloperTaskExecutionHostToolchainReport(
        policy_id=DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY_ID,
        policy_fingerprint=developer_task_execution_toolchain_observation_policy_fingerprint(),
        repository_root=str(repository_root),
        head_commit=head_commit,
        inventory_policy_fingerprint=DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_POLICY_FINGERPRINT,
        inventory_fingerprint=inventory_fingerprint,
        requirement_files=requirement_files,
        host_python=host_python,
        import_distributions=import_distributions,
        host_git=host_git,
        host_powershell=host_powershell,
        observation_fingerprint="",
        issues=issues,
    )
    fingerprint = _sha256(_canonical_json(_observation_fingerprint_payload(provisional)).encode("utf-8"))
    return DeveloperTaskExecutionHostToolchainReport(
        **{
            **provisional.__dict__,
            "observation_fingerprint": fingerprint,
        }
    )


def observe_developer_task_execution_host_toolchain(
    inventory_report: DeveloperTaskExecutionEnvironmentInventoryReport,
    *,
    project_root: Path,
) -> DeveloperTaskExecutionHostToolchainReport:
    policy_errors = validate_developer_task_execution_toolchain_observation_policy()
    if policy_errors:
        raise RuntimeError(
            "Developer task execution host toolchain observation policy is invalid: " + ",".join(policy_errors)
        )

    repository_root = Path(os.path.abspath(os.fspath(project_root))) if isinstance(project_root, Path) else Path(".")
    head_commit = ""
    inventory_fingerprint = ""
    try:
        repository_root, head_commit = _validate_inventory_report(inventory_report, project_root)
        inventory_fingerprint = inventory_report.inventory_fingerprint
        _require_windows()
        git_executable, git_install_root = _discover_git_executable()
        _require_current_head(git_executable, git_install_root, repository_root, head_commit)
        _rebuild_canonical_inventory_report(inventory_report, repository_root, head_commit)
        requirement_files = _observe_requirement_files(
            inventory_report,
            git_executable,
            git_install_root,
            repository_root,
        )
        host_python = _observe_host_python()
        import_distributions = _observe_import_distribution_mapping(
            inventory_report.import_roots,
            host_python.distributions,
        )
        host_git = _observe_git(git_executable, git_install_root)
        host_powershell = _observe_powershell()
        _require_current_head(git_executable, git_install_root, repository_root, head_commit)
        return _build_report(
            repository_root=repository_root,
            head_commit=head_commit,
            inventory_fingerprint=inventory_fingerprint,
            requirement_files=requirement_files,
            host_python=host_python,
            import_distributions=import_distributions,
            host_git=host_git,
            host_powershell=host_powershell,
        )
    except _ToolchainFailure as failure:
        issue = DeveloperTaskExecutionHostToolchainIssue(
            code=failure.code,
            check=failure.check,
            message=str(failure),
            expected=failure.expected,
            actual=failure.actual,
        )
        return _build_report(
            repository_root=repository_root,
            head_commit=head_commit,
            inventory_fingerprint=inventory_fingerprint,
            issues=(issue,),
        )
