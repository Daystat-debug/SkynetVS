from __future__ import annotations

import hashlib
import inspect
import json
import shutil
import subprocess
import tempfile

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

from modules.developer.developer_task_execution_environment_inventory import (
    DeveloperTaskExecutionEnvironmentImportEvidence,
    DeveloperTaskExecutionEnvironmentInventoryIssue,
    inventory_developer_task_execution_environment,
)
from modules.developer.developer_task_execution_toolchain_observation import (
    DeveloperTaskExecutionHostDistributionEvidence,
    DeveloperTaskExecutionHostGitEvidence,
    DeveloperTaskExecutionHostPowerShellEvidence,
    DeveloperTaskExecutionHostPythonEvidence,
    DeveloperTaskExecutionImportDistributionEvidence,
    DeveloperTaskExecutionRequirementEntryEvidence,
    _ToolchainFailure,
    _build_git_environment,
    _inventory_fingerprint_payload,
    _hash_git_tree,
    _observe_import_distribution_mapping,
    _parse_requirement_line,
    observe_developer_task_execution_host_toolchain,
)
from modules.developer.developer_task_execution_toolchain_observation_policy import (
    DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY,
    DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY_ID,
    developer_task_execution_toolchain_observation_policy_fingerprint,
    validate_developer_task_execution_toolchain_observation_policy,
)
from modules.developer.developer_task_preflight import DeveloperTaskRepositoryPreflightReport


PIPELINE_SOURCE = '''from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class Step:
    name: str
    cmd: list[str]
    interactive: bool = False

def _python_cmd(*args: str) -> list[str]:
    return ["python", *args]

def available_flows() -> dict[str, list[Step]]:
    return {
        "check": [
            Step("Evaluate sample", _python_cmd("tools/check.py")),
        ],
        "sample": [
            Step("Evaluate sample", _python_cmd("tools/check.py")),
        ],
    }
'''


class EvalFailure(RuntimeError):
    pass


def _git(repo: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise EvalFailure(completed.stderr.decode("utf-8", errors="replace"))
    return completed.stdout


def _write(repo: Path, relative: str, text: str) -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _make_repo() -> tuple[tempfile.TemporaryDirectory[str], Path, str]:
    temp = tempfile.TemporaryDirectory(prefix="skynetvs-v1c0b1-eval-")
    repo = Path(temp.name) / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "skynetvs-eval@example.invalid")
    _git(repo, "config", "user.name", "SkynetVS Eval")
    _write(repo, "tools/pipeline.py", PIPELINE_SOURCE)
    _write(repo, "tools/check.py", "import json\nimport numpy\nfrom modules import helper\n")
    _write(repo, "modules/__init__.py", "")
    _write(repo, "modules/helper.py", "VALUE = 1\n")
    _write(repo, "requirements.txt", "# base\nnumpy>=1.24\npython-dotenv>=1.0.1\n")
    _write(repo, "requirements-train.txt", "scikit-learn>=1.3.0\njoblib>=1.3.2\n")
    _write(repo, "requirements-whisper.txt", "# optional\nfaster-whisper==1.2.1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "baseline")
    head = _git(repo, "rev-parse", "HEAD").decode("ascii").strip()
    return temp, repo, head


def _inventory(repo: Path, head: str):
    preflight = DeveloperTaskRepositoryPreflightReport(
        manifest_fingerprint="a" * 64,
        project_root=str(repo.resolve()),
        repository_root=str(repo.resolve()),
        head_commit=head,
        resolved_base_commit=head,
        dirty_categories=(),
        issues=(),
    )
    return inventory_developer_task_execution_environment(preflight, project_root=repo)


def _fake_python() -> DeveloperTaskExecutionHostPythonEvidence:
    distributions = (
        DeveloperTaskExecutionHostDistributionEvidence(
            name="NumPy",
            normalized_name="numpy",
            version="2.4.1",
            installer="pip",
            direct_url_present=False,
            wheel_tags=("cp312-cp312-win_amd64",),
        ),
        DeveloperTaskExecutionHostDistributionEvidence(
            name="python-dotenv",
            normalized_name="python-dotenv",
            version="1.2.1",
            installer="pip",
            direct_url_present=False,
            wheel_tags=("py3-none-any",),
        ),
    )
    return DeveloperTaskExecutionHostPythonEvidence(
        implementation="CPython",
        version="3.12.10",
        version_info=(3, 12, 10),
        architecture_bits=64,
        machine="AMD64",
        executable=r"C:\Project\SkynetVS\.venv\Scripts\python.exe",
        executable_size_bytes=274424,
        executable_sha256="1" * 64,
        executable_file_version="3.12.10",
        executable_product_version="3.12.10",
        prefix=r"C:\Project\SkynetVS\.venv",
        venv_active=True,
        cache_tag="cpython-312",
        ext_suffix=".cp312-win_amd64.pyd",
        soabi="",
        pip_version="25.3",
        distribution_count=len(distributions),
        distributions=distributions,
    )


def _fake_git() -> DeveloperTaskExecutionHostGitEvidence:
    return DeveloperTaskExecutionHostGitEvidence(
        version="2.45.1.windows.1",
        build_options=("git version 2.45.1.windows.1", "cpu: x86_64"),
        executable=r"C:\Program Files\Git\cmd\git.exe",
        executable_size_bytes=45032,
        executable_sha256="2" * 64,
        executable_file_version="2.45.1.windows.1",
        executable_product_version="2.45.1.windows.1",
        exec_path=r"C:\Program Files\Git\mingw64\libexec\git-core",
        install_root=r"C:\Program Files\Git",
        install_tree_file_count=6356,
        install_tree_total_bytes=419125157,
        install_tree_manifest_sha256="3" * 64,
        host_installation_is_authority=False,
    )


def _fake_powershell() -> DeveloperTaskExecutionHostPowerShellEvidence:
    return DeveloperTaskExecutionHostPowerShellEvidence(
        edition="Desktop",
        version="5.1.26100.9168",
        executable=r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        executable_size_bytes=454656,
        executable_sha256="4" * 64,
        executable_file_version="10.0.26100.8875",
        executable_product_version="10.0.26100.8875",
        portable_bundle_selected=False,
    )


def main() -> int:
    case_count = 0
    fail_count = 0

    def check(name: str, actual: Any, expected: Any) -> None:
        nonlocal case_count, fail_count
        case_count += 1
        ok = actual == expected
        print()
        print(f"=== {name} ===")
        print(json.dumps({"actual": actual, "expected": expected, "ok": ok}, ensure_ascii=False, indent=2, default=str))
        if ok:
            print(f"[OK] {name}")
        else:
            fail_count += 1
            print(f"[FAIL] {name}")

    check(
        "V1C0B1 PINNED TOOLCHAIN OBSERVATION POLICY SELF CHECKS",
        {
            "errors": list(validate_developer_task_execution_toolchain_observation_policy()),
            "policy_id": DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY.policy_id,
            "fingerprint": developer_task_execution_toolchain_observation_policy_fingerprint(),
            "source_authority_selected": DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY.source_authority_selected,
            "authorized": DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY.execution_authorized,
        },
        {
            "errors": [],
            "policy_id": DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY_ID,
            "fingerprint": DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY_FINGERPRINT,
            "source_authority_selected": False,
            "authorized": False,
        },
    )

    parameters = inspect.signature(observe_developer_task_execution_host_toolchain).parameters
    check(
        "V1C0B1 PUBLIC API ACCEPTS ONLY INVENTORY REPORT AND PROJECT ROOT",
        {
            name: {"kind": item.kind.name, "default": None if item.default is inspect.Parameter.empty else item.default}
            for name, item in parameters.items()
        },
        {
            "inventory_report": {"kind": "POSITIONAL_OR_KEYWORD", "default": None},
            "project_root": {"kind": "KEYWORD_ONLY", "default": None},
        },
    )

    temp, repo, head = _make_repo()
    try:
        inventory = _inventory(repo, head)
        git_path = Path(shutil.which("git") or "git").resolve(strict=True)
        git_root = git_path.parent.parent
        mapping = (
            DeveloperTaskExecutionImportDistributionEvidence("json", "stdlib", ()),
            DeveloperTaskExecutionImportDistributionEvidence("modules", "project", ()),
            DeveloperTaskExecutionImportDistributionEvidence("numpy", "distribution", ("numpy",)),
        )
        with (
            patch("modules.developer.developer_task_execution_toolchain_observation._require_windows", return_value=None),
            patch("modules.developer.developer_task_execution_toolchain_observation._discover_git_executable", return_value=(git_path, git_root)),
            patch("modules.developer.developer_task_execution_toolchain_observation._observe_host_python", return_value=_fake_python()),
            patch("modules.developer.developer_task_execution_toolchain_observation._observe_import_distribution_mapping", return_value=mapping),
            patch("modules.developer.developer_task_execution_toolchain_observation._observe_git", return_value=_fake_git()),
            patch("modules.developer.developer_task_execution_toolchain_observation._observe_powershell", return_value=_fake_powershell()),
        ):
            result = observe_developer_task_execution_host_toolchain(inventory, project_root=repo)
            repeated = observe_developer_task_execution_host_toolchain(inventory, project_root=repo)

        check(
            "V1C0B1 EXACT INVENTORY BINDS CANONICAL NON AUTHORIZING HOST OBSERVATION",
            {
                "ok": result.ok,
                "issues": list(result.issue_codes),
                "head": result.head_commit == head,
                "requirements": [item.path for item in result.requirement_files],
                "base_entries": [item.normalized_name for item in result.requirement_files[-1].entries],
                "python": None if result.host_python is None else result.host_python.version,
                "git": None if result.host_git is None else result.host_git.version,
                "powershell": None if result.host_powershell is None else result.host_powershell.version,
                "fingerprint_len": len(result.observation_fingerprint),
                "source_authority": result.source_authority_selected,
                "download": result.artifact_download_attempted,
                "install": result.dependency_install_attempted,
                "sandbox": result.sandbox_launched,
                "candidate": result.candidate_interpreter_executed,
                "lease": result.reusable_lease_issued,
                "authorized": result.execution_authorized,
            },
            {
                "ok": True,
                "issues": [],
                "head": True,
                "requirements": ["requirements-train.txt", "requirements-whisper.txt", "requirements.txt"],
                "base_entries": ["numpy", "python-dotenv"],
                "python": "3.12.10",
                "git": "2.45.1.windows.1",
                "powershell": "5.1.26100.9168",
                "fingerprint_len": 64,
                "source_authority": False,
                "download": False,
                "install": False,
                "sandbox": False,
                "candidate": False,
                "lease": False,
                "authorized": False,
            },
        )

        check(
            "V1C0B1 REPEATED EXACT HOST OBSERVATION IS DETERMINISTIC",
            {
                "same_report": result == repeated,
                "same_fingerprint": result.observation_fingerprint == repeated.observation_fingerprint,
            },
            {"same_report": True, "same_fingerprint": True},
        )

        immutable = {"report": False, "requirement": False, "python": False, "git": False}
        try:
            result.head_commit = "x"  # type: ignore[misc]
        except FrozenInstanceError:
            immutable["report"] = True
        try:
            result.requirement_files[0].path = "x"  # type: ignore[misc]
        except FrozenInstanceError:
            immutable["requirement"] = True
        try:
            assert result.host_python is not None
            result.host_python.version = "x"  # type: ignore[misc]
        except FrozenInstanceError:
            immutable["python"] = True
        try:
            assert result.host_git is not None
            result.host_git.version = "x"  # type: ignore[misc]
        except FrozenInstanceError:
            immutable["git"] = True
        check("V1C0B1 REPORT AND NESTED EVIDENCE ARE IMMUTABLE", immutable, {k: True for k in immutable})

        serialized = json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True)
        check(
            "V1C0B1 SERIALIZATION EXPOSES HASHED IDENTITIES BUT NO SOURCE OR CREDENTIAL VALUES",
            {
                "requirements_source_absent": "# base" not in serialized,
                "password_absent": "password" not in serialized.casefold(),
                "token_absent": "token=" not in serialized.casefold(),
                "sha_present": "1" * 64 in serialized and "2" * 64 in serialized,
            },
            {
                "requirements_source_absent": True,
                "password_absent": True,
                "token_absent": True,
                "sha_present": True,
            },
        )

        raw_types: dict[str, str] = {}
        try:
            observe_developer_task_execution_host_toolchain({}, project_root=repo)  # type: ignore[arg-type]
        except Exception as exc:
            raw_types["report"] = type(exc).__name__
        try:
            observe_developer_task_execution_host_toolchain(inventory, project_root=str(repo))  # type: ignore[arg-type]
        except Exception as exc:
            raw_types["root"] = type(exc).__name__
        check("V1C0B1 RAW PUBLIC INPUT TYPES ARE REJECTED", raw_types, {"report": "TypeError", "root": "TypeError"})

        failed_inventory = replace(
            inventory,
            issues=(
                DeveloperTaskExecutionEnvironmentInventoryIssue(
                    code="fixture_failed",
                    check="fixture",
                    message="fixture failure",
                ),
            ),
        )
        failed_result = observe_developer_task_execution_host_toolchain(failed_inventory, project_root=repo)
        check(
            "V1C0B1 FAILED INVENTORY CANNOT BECOME HOST AUTHORITY",
            list(failed_result.issue_codes),
            ["toolchain_observation_inventory_report_failed"],
        )

        tampered = replace(inventory, inventory_fingerprint="0" * 64)
        with patch("modules.developer.developer_task_execution_toolchain_observation._require_windows", return_value=None):
            tampered_result = observe_developer_task_execution_host_toolchain(tampered, project_root=repo)
        check(
            "V1C0B1 INVENTORY FINGERPRINT TAMPER FAILS CLOSED",
            list(tampered_result.issue_codes),
            ["toolchain_observation_inventory_report_invalid"],
        )

        policy_tampered = replace(inventory, policy_fingerprint="0" * 64)
        policy_result = observe_developer_task_execution_host_toolchain(policy_tampered, project_root=repo)
        check(
            "V1C0B1 V1C0A POLICY LINEAGE TAMPER FAILS CLOSED",
            list(policy_result.issue_codes),
            ["toolchain_observation_inventory_report_invalid"],
        )

        fabricated = replace(inventory, import_roots=inventory.import_roots[:-1], inventory_fingerprint="")
        fabricated_fingerprint = hashlib.sha256(
            json.dumps(
                _inventory_fingerprint_payload(fabricated),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        fabricated = replace(fabricated, inventory_fingerprint=fabricated_fingerprint)
        git_path = Path(shutil.which("git") or "git").resolve(strict=True)
        git_root = git_path.parent.parent
        with (
            patch("modules.developer.developer_task_execution_toolchain_observation._require_windows", return_value=None),
            patch("modules.developer.developer_task_execution_toolchain_observation._discover_git_executable", return_value=(git_path, git_root)),
        ):
            fabricated_result = observe_developer_task_execution_host_toolchain(fabricated, project_root=repo)
        check(
            "V1C0B1 SELF CONSISTENT BUT FABRICATED V1C0A REPORT FAILS CANONICAL REBUILD",
            list(fabricated_result.issue_codes),
            ["toolchain_observation_inventory_report_noncanonical"],
        )

        other = Path(temp.name) / "other"
        other.mkdir()
        root_result = observe_developer_task_execution_host_toolchain(inventory, project_root=other)
        check(
            "V1C0B1 PROJECT ROOT MISMATCH FAILS CLOSED",
            list(root_result.issue_codes),
            ["toolchain_observation_repository_root_mismatch"],
        )

        _write(repo, "untracked.txt", "dirty")
        # HEAD is unchanged and worktree bytes are not an authority for V1C0B1.
        git_path = Path(shutil.which("git") or "git").resolve(strict=True)
        git_root = git_path.parent.parent
        with (
            patch("modules.developer.developer_task_execution_toolchain_observation._require_windows", return_value=None),
            patch("modules.developer.developer_task_execution_toolchain_observation._discover_git_executable", return_value=(git_path, git_root)),
            patch("modules.developer.developer_task_execution_toolchain_observation._observe_host_python", return_value=_fake_python()),
            patch("modules.developer.developer_task_execution_toolchain_observation._observe_import_distribution_mapping", return_value=mapping),
            patch("modules.developer.developer_task_execution_toolchain_observation._observe_git", return_value=_fake_git()),
            patch("modules.developer.developer_task_execution_toolchain_observation._observe_powershell", return_value=_fake_powershell()),
        ):
            dirty_result = observe_developer_task_execution_host_toolchain(inventory, project_root=repo)
        check(
            "V1C0B1 DIRTY WORKTREE CANNOT SUBSTITUTE PINNED DEPENDENCY BLOBS",
            {
                "ok": dirty_result.ok,
                "requirements_sha": [item.sha256 for item in dirty_result.requirement_files],
            },
            {
                "ok": True,
                "requirements_sha": [item.sha256 for item in result.requirement_files],
            },
        )

        _git(repo, "add", "untracked.txt")
        _git(repo, "commit", "-m", "head changed")
        new_head = _git(repo, "rev-parse", "HEAD").decode("ascii").strip()
        with (
            patch("modules.developer.developer_task_execution_toolchain_observation._require_windows", return_value=None),
            patch("modules.developer.developer_task_execution_toolchain_observation._discover_git_executable", return_value=(git_path, git_root)),
        ):
            changed = observe_developer_task_execution_host_toolchain(inventory, project_root=repo)
        check(
            "V1C0B1 HEAD CHANGE RELATIVE TO INVENTORY FAILS CLOSED",
            {"head_changed": new_head != head, "issues": list(changed.issue_codes)},
            {"head_changed": True, "issues": ["toolchain_observation_repository_changed"]},
        )
    finally:
        temp.cleanup()

    parser_cases = [
        ("numpy>=1.24", ("numpy", ">=1.24", False)),
        ("faster-whisper==1.2.1", ("faster-whisper", "==1.2.1", True)),
        ("scikit_learn>=1.3,<2", ("scikit-learn", ">=1.3,<2", False)),
    ]
    parsed_cases = []
    for index, (line, expected) in enumerate(parser_cases, start=1):
        entry = _parse_requirement_line(line, path="requirements.txt", line_number=index)
        assert entry is not None
        parsed_cases.append((entry.normalized_name, entry.specifier, entry.exact_pin))
    check(
        "V1C0B1 STRICT REQUIREMENT PARSER ACCEPTS RANGE AND EXACT PINS",
        parsed_cases,
        [item[1] for item in parser_cases],
    )

    rejected: list[str] = []
    for line in (
        "--extra-index-url https://example.invalid/simple",
        "pkg @ https://example.invalid/pkg.whl",
        "git+https://example.invalid/repo.git",
        "pkg; python_version<'3.13'",
        "../local-package",
        "pkg",
    ):
        try:
            _parse_requirement_line(line, path="requirements.txt", line_number=1)
        except _ToolchainFailure as exc:
            rejected.append(exc.code)
    check(
        "V1C0B1 REQUIREMENT OPTIONS URLS MARKERS LOCAL PATHS AND UNBOUNDED NAMES FAIL CLOSED",
        rejected,
        [
            "toolchain_observation_requirement_syntax_unsupported",
            "toolchain_observation_requirement_syntax_unsupported",
            "toolchain_observation_requirement_syntax_unsupported",
            "toolchain_observation_requirement_syntax_unsupported",
            "toolchain_observation_requirement_syntax_unsupported",
            "toolchain_observation_requirement_unbounded",
        ],
    )

    mapping_imports = (
        DeveloperTaskExecutionEnvironmentImportEvidence(root="json", files=("a.py",)),
        DeveloperTaskExecutionEnvironmentImportEvidence(root="modules", files=("b.py",)),
        DeveloperTaskExecutionEnvironmentImportEvidence(root="numpy", files=("c.py",)),
        DeveloperTaskExecutionEnvironmentImportEvidence(root="mystery", files=("d.py",)),
    )
    with patch(
        "modules.developer.developer_task_execution_toolchain_observation.importlib_metadata.packages_distributions",
        return_value={"numpy": ["NumPy"]},
    ):
        mapped = _observe_import_distribution_mapping(mapping_imports, _fake_python().distributions)
    check(
        "V1C0B1 IMPORT ROOT MAPPING DISTINGUISHES STDLIB PROJECT DISTRIBUTION AND UNRESOLVED",
        [item.to_dict() for item in mapped],
        [
            {"root": "json", "category": "stdlib", "distributions": []},
            {"root": "modules", "category": "project", "distributions": []},
            {"root": "mystery", "category": "unresolved", "distributions": []},
            {"root": "numpy", "category": "distribution", "distributions": ["numpy"]},
        ],
    )

    with patch.dict(
        "os.environ",
        {
            "GIT_DIR": "poison",
            "GIT_CONFIG_GLOBAL": "secret",
            "AWS_SECRET_ACCESS_KEY": "secret",
            "MY_TOKEN": "secret",
            "SystemRoot": r"C:\Windows",
        },
        clear=True,
    ):
        git_env = _build_git_environment(Path(r"C:\Program Files\Git"))
    check(
        "V1C0B1 GIT SUBPROCESS ENVIRONMENT EXCLUDES CALLER CONFIG AND CREDENTIAL VARIABLES",
        {
            "git_dir_absent": "GIT_DIR" not in git_env,
            "aws_absent": "AWS_SECRET_ACCESS_KEY" not in git_env,
            "token_absent": "MY_TOKEN" not in git_env,
            "no_system": git_env.get("GIT_CONFIG_NOSYSTEM"),
            "global_null": bool(git_env.get("GIT_CONFIG_GLOBAL")),
            "prompt": git_env.get("GIT_TERMINAL_PROMPT"),
            "lazy_fetch": git_env.get("GIT_NO_LAZY_FETCH"),
        },
        {
            "git_dir_absent": True,
            "aws_absent": True,
            "token_absent": True,
            "no_system": "1",
            "global_null": True,
            "prompt": "0",
            "lazy_fetch": "1",
        },
    )

    tree_temp = tempfile.TemporaryDirectory(prefix="skynetvs-v1c0b1-tree-")
    try:
        root = Path(tree_temp.name)
        (root / "bin").mkdir()
        (root / "bin" / "git.exe").write_bytes(b"git")
        (root / "lib.txt").write_bytes(b"library")
        first = _hash_git_tree(root)
        second = _hash_git_tree(root)
        check(
            "V1C0B1 GIT INSTALL TREE HASH IS DETERMINISTIC",
            {"same": first == second, "files": first[0], "bytes": first[1], "fingerprint_len": len(first[2])},
            {"same": True, "files": 2, "bytes": 10, "fingerprint_len": 64},
        )
        (root / "lib.txt").write_bytes(b"changed")
        changed = _hash_git_tree(root)
        check(
            "V1C0B1 GIT INSTALL TREE CONTENT CHANGE CHANGES FINGERPRINT",
            first[2] != changed[2],
            True,
        )
        symlink_code = "unsupported"
        try:
            (root / "link.txt").symlink_to(root / "lib.txt")
            try:
                _hash_git_tree(root)
            except _ToolchainFailure as exc:
                symlink_code = exc.code
        except (OSError, NotImplementedError):
            pass
        check(
            "V1C0B1 GIT INSTALL TREE REPARSE OR SYMLINK FAILS CLOSED",
            symlink_code,
            "toolchain_observation_git_tree_reparse" if symlink_code != "unsupported" else "unsupported",
        )
    finally:
        tree_temp.cleanup()

    source = Path(__file__).resolve().parent.parent / "modules" / "developer" / "developer_task_execution_toolchain_observation.py"
    source_text = source.read_text(encoding="utf-8")
    forbidden_markers = (
        "WindowsSandbox.exe",
        "pip install",
        "files.pythonhosted.org",
        "pypi.org",
        "urllib.request",
        "requests.get",
        "shell=True",
        "CreateProcess",
    )
    check(
        "V1C0B1 PRODUCTION OBSERVATION HAS NO DOWNLOAD INSTALL SANDBOX CANDIDATE OR SHELL SURFACE",
        {marker: marker in source_text for marker in forbidden_markers},
        {marker: False for marker in forbidden_markers},
    )

    policy_text = (
        Path(__file__).resolve().parent.parent
        / "modules"
        / "developer"
        / "developer_task_execution_toolchain_observation_policy.py"
    ).read_text(encoding="utf-8")
    check(
        "V1C0B1 POLICY FORBIDS CALLER CONTROLLED TOOLCHAIN SOURCE AND EXECUTION OVERRIDES",
        {
            "caller_python": "caller_python_executable_allowed\": False" in policy_text,
            "caller_git": "caller_git_executable_allowed\": False" in policy_text,
            "caller_source": "caller_source_authority_allowed\": False" in policy_text,
            "caller_env": "caller_environment_additions_allowed\": False" in policy_text,
            "network": "runtime_network_allowed\": False" in policy_text,
            "authorized": DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY.execution_authorized,
        },
        {
            "caller_python": True,
            "caller_git": True,
            "caller_source": True,
            "caller_env": True,
            "network": True,
            "authorized": False,
        },
    )

    # Policy mutation must never silently preserve the historical fingerprint.
    mutated = replace(DEVELOPER_TASK_EXECUTION_TOOLCHAIN_OBSERVATION_POLICY, max_git_tree_files=1)
    check(
        "V1C0B1 POLICY MUTATION INVALIDATES PINNED FINGERPRINT",
        "policy_fingerprint_invalid" in validate_developer_task_execution_toolchain_observation_policy(mutated),
        True,
    )

    check(
        "V1C0B1 HOST EVIDENCE OBJECTS DO NOT CLAIM AUTHORITY",
        {
            "git_authority": _fake_git().host_installation_is_authority,
            "powershell_portable": _fake_powershell().portable_bundle_selected,
        },
        {"git_authority": False, "powershell_portable": False},
    )

    # Exact pin semantics must not classify wildcard pins as immutable pins.
    wildcard = _parse_requirement_line("package==1.*", path="requirements.txt", line_number=1)
    check(
        "V1C0B1 WILDCARD VERSION IS NOT AN EXACT PIN",
        None if wildcard is None else wildcard.exact_pin,
        False,
    )

    print()
    print("=== SUMMARY ===")
    print(json.dumps({"case_count": case_count, "fail_count": fail_count}, indent=2))
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
