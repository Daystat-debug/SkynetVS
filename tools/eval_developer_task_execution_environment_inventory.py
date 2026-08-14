from __future__ import annotations

import copy
import inspect
import json
import os
import pickle
import subprocess
import tempfile

from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

from modules.developer.developer_task_execution_environment_inventory import (
    DeveloperTaskExecutionEnvironmentInventoryReport,
    _GitTreeEntry,
    _build_git_environment,
    _candidate_blob_entries,
    inventory_developer_task_execution_environment,
)
from modules.developer.developer_task_execution_environment_inventory_policy import (
    DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_POLICY,
    DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_POLICY_ID,
    developer_task_execution_environment_inventory_policy_fingerprint,
    validate_developer_task_execution_environment_inventory_policy,
)
from modules.developer.developer_task_preflight import (
    DeveloperTaskPreflightIssue,
    DeveloperTaskRepositoryPreflightReport,
)


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
            Step("Interactive sample", _python_cmd("tools/interactive.py", "--flag"), interactive=True),
        ],
        "sample": [
            Step("Evaluate sample", _python_cmd("tools/check.py")),
        ],
    }
'''

SAMPLE_SOURCE = '''from __future__ import annotations
import ctypes
import json
import subprocess
from modules import local_helper

VALUE = 7
subprocess.run(["tool.exe", "--version"], check=False)
'''


class EvalFailure(RuntimeError):
    pass


def _git(repo: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    command = ["git", "-C", str(repo), *args]
    completed = subprocess.run(
        command,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise EvalFailure(
            f"git failed: {' '.join(args)}: {completed.stderr.decode('utf-8', errors='replace')}"
        )
    return completed.stdout


def _commit(repo: Path, message: str = "baseline") -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD").decode("ascii").strip()


def _commit_case_collision_tree(repo: Path) -> str:
    upper_blob = _git(repo, "hash-object", "-w", "--stdin", input_bytes=b"X = 1\n").decode("ascii").strip()
    lower_blob = _git(repo, "hash-object", "-w", "--stdin", input_bytes=b"X = 2\n").decode("ascii").strip()
    tree_input = (
        f"100644 blob {upper_blob}\tFoo.py\0"
        f"100644 blob {lower_blob}\tfoo.py\0"
    ).encode("utf-8")
    tree = _git(repo, "mktree", "-z", input_bytes=tree_input).decode("ascii").strip()
    commit = _git(repo, "commit-tree", tree, "-m", "case collision").decode("ascii").strip()
    _git(repo, "update-ref", "HEAD", commit)
    return commit


def _write(repo: Path, relative: str, data: str | bytes) -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(data, encoding="utf-8", newline="\n")


def _make_repo() -> tuple[tempfile.TemporaryDirectory[str], Path, str]:
    temp = tempfile.TemporaryDirectory(prefix="skynetvs-v1c0a-eval-")
    repo = Path(temp.name) / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "skynetvs-eval@example.invalid")
    _git(repo, "config", "user.name", "SkynetVS Eval")
    _write(repo, "tools/pipeline.py", PIPELINE_SOURCE)
    _write(repo, "tools/check.py", "import os\n")
    _write(repo, "tools/interactive.py", "import winreg\n")
    _write(repo, "modules/__init__.py", "")
    _write(repo, "modules/local_helper.py", "VALUE = 1\n")
    _write(repo, "modules/example.py", SAMPLE_SOURCE)
    _write(repo, "requirements.txt", "requests>=2\n")
    _write(repo, "requirements-train.txt", "scikit-learn>=1\n")
    _write(repo, "constraints-win.txt", "numpy==2.0\n")
    _write(repo, "uv.lock", "version = 1\n")
    _write(repo, "vendor/example.whl", b"wheel-bytes")
    head = _commit(repo)
    return temp, repo, head


def _report(repo: Path, head: str, *, issues: tuple[DeveloperTaskPreflightIssue, ...] = (), dirty: tuple[str, ...] = ()) -> DeveloperTaskRepositoryPreflightReport:
    return DeveloperTaskRepositoryPreflightReport(
        manifest_fingerprint="a" * 64,
        project_root=str(repo.resolve()),
        repository_root=str(repo.resolve()),
        head_commit=head,
        resolved_base_commit=head,
        dirty_categories=dirty,
        issues=issues,
    )


def _inventory(repo: Path, head: str) -> DeveloperTaskExecutionEnvironmentInventoryReport:
    return inventory_developer_task_execution_environment(_report(repo, head), project_root=repo)


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
        "V1C0A PINNED INVENTORY POLICY SELF CHECKS",
        {
            "errors": list(validate_developer_task_execution_environment_inventory_policy()),
            "policy_id": DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_POLICY.policy_id,
            "fingerprint": developer_task_execution_environment_inventory_policy_fingerprint(),
            "execution_authorized": DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_POLICY.execution_authorized,
            "reusable_lease_issued": DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_POLICY.reusable_lease_issued,
        },
        {
            "errors": [],
            "policy_id": DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_POLICY_ID,
            "fingerprint": DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_POLICY_FINGERPRINT,
            "execution_authorized": False,
            "reusable_lease_issued": False,
        },
    )

    parameters = inspect.signature(inventory_developer_task_execution_environment).parameters
    check(
        "V1C0A PUBLIC API ACCEPTS ONLY PINNED REPOSITORY REPORT AND PROJECT ROOT",
        {
            name: {"kind": item.kind.name, "default": None if item.default is inspect.Parameter.empty else item.default}
            for name, item in parameters.items()
        },
        {
            "repository_report": {"kind": "POSITIONAL_OR_KEYWORD", "default": None},
            "project_root": {"kind": "KEYWORD_ONLY", "default": None},
        },
    )

    temp, repo, head = _make_repo()
    try:
        result = _inventory(repo, head)
        check(
            "V1C0A EXACT COMMIT TREE BUILDS CANONICAL NON AUTHORIZING INVENTORY",
            {
                "ok": result.ok,
                "issue_codes": list(result.issue_codes),
                "tracked": result.tracked_file_count,
                "python": result.tracked_python_file_count,
                "dependency_paths": [item.path for item in result.dependency_files],
                "flow_count": result.pipeline_flow_count,
                "step_count": result.pipeline_step_count,
                "sandbox": result.sandbox_launched,
                "interpreter": result.candidate_interpreter_executed,
                "install": result.dependency_install_attempted,
                "lease": result.reusable_lease_issued,
                "authorized": result.execution_authorized,
                "fingerprint_len": len(result.inventory_fingerprint),
            },
            {
                "ok": True,
                "issue_codes": [],
                "tracked": 11,
                "python": 6,
                "dependency_paths": [
                    "constraints-win.txt",
                    "requirements-train.txt",
                    "requirements.txt",
                    "uv.lock",
                    "vendor/example.whl",
                ],
                "flow_count": 2,
                "step_count": 3,
                "sandbox": False,
                "interpreter": False,
                "install": False,
                "lease": False,
                "authorized": False,
                "fingerprint_len": 64,
            },
        )

        imports = {item.root: list(item.files) for item in result.import_roots}
        check(
            "V1C0A IMPORT ROOT INVENTORY IS AST DERIVED AND DETERMINISTIC",
            {
                "ctypes": imports.get("ctypes"),
                "subprocess": imports.get("subprocess"),
                "modules": imports.get("modules"),
                "winreg": imports.get("winreg"),
            },
            {
                "ctypes": ["modules/example.py"],
                "subprocess": ["modules/example.py"],
                "modules": ["modules/example.py"],
                "winreg": ["tools/interactive.py"],
            },
        )

        check(
            "V1C0A PROCESS CALL INVENTORY CAPTURES ONLY FIXED PROCESS SURFACES",
            [item.to_dict() for item in result.process_calls],
            [
                {
                    "path": "modules/example.py",
                    "line": 8,
                    "call": "subprocess.run",
                    "literal_args": ['["tool.exe","--version"]'],
                }
            ],
        )

        sensitive = {item.path: list(item.reasons) for item in result.host_sensitive_files}
        check(
            "V1C0A DIRECT HOST SENSITIVE MARKERS ARE INVENTORIED WITHOUT AUTHORIZATION",
            sensitive,
            {
                "modules/example.py": ["import:ctypes"],
                "tools/interactive.py": ["import:winreg"],
            },
        )

        steps = [item.to_dict() for item in result.pipeline_steps]
        check(
            "V1C0A PIPELINE FLOWS AND INTERACTIVE STEPS ARE INVENTORIED WITHOUT IMPORTING PIPELINE",
            {
                "flows": sorted({item["flow"] for item in steps}),
                "check_steps": [item for item in steps if item["flow"] == "check"],
            },
            {
                "flows": ["check", "sample"],
                "check_steps": [
                    {
                        "flow": "check",
                        "index": 0,
                        "name": "Evaluate sample",
                        "python_args": ["tools/check.py"],
                        "interactive": False,
                        "direct_host_sensitive": False,
                        "host_sensitive_reasons": [],
                    },
                    {
                        "flow": "check",
                        "index": 1,
                        "name": "Interactive sample",
                        "python_args": ["tools/interactive.py", "--flag"],
                        "interactive": True,
                        "direct_host_sensitive": True,
                        "host_sensitive_reasons": ["import:winreg"],
                    },
                ],
            },
        )

        first = result.to_dict()
        second = _inventory(repo, head).to_dict()
        check(
            "V1C0A REPEATED EXACT COMMIT INVENTORY IS DETERMINISTIC",
            {
                "same_report": first == second,
                "same_fingerprint": first["inventory_fingerprint"] == second["inventory_fingerprint"],
            },
            {"same_report": True, "same_fingerprint": True},
        )

        committed_hash = next(item.sha256 for item in result.dependency_files if item.path == "requirements.txt")
        _write(repo, "requirements.txt", "host-worktree-poison==999\n")
        _write(repo, "untracked.py", "raise RuntimeError('must not be inventoried')\n")
        dirty_result = _inventory(repo, head)
        check(
            "V1C0A DIRTY WORKTREE CANNOT SUBSTITUTE PINNED HEAD BLOBS",
            {
                "ok": dirty_result.ok,
                "tracked_python": dirty_result.tracked_python_file_count,
                "untracked_present": any("untracked.py" in item.files for item in dirty_result.import_roots),
                "requirements_hash_unchanged": next(item.sha256 for item in dirty_result.dependency_files if item.path == "requirements.txt") == committed_hash,
            },
            {
                "ok": True,
                "tracked_python": 6,
                "untracked_present": False,
                "requirements_hash_unchanged": True,
            },
        )
        _git(repo, "restore", "requirements.txt")
        (repo / "untracked.py").unlink()

        check(
            "V1C0A REPORT AND NESTED EVIDENCE ARE IMMUTABLE",
            {
                "report": _mutation_blocked(result),
                "dependency": _mutation_blocked(result.dependency_files[0]),
                "import": _mutation_blocked(result.import_roots[0]),
                "process": _mutation_blocked(result.process_calls[0]),
                "pipeline": _mutation_blocked(result.pipeline_steps[0]),
            },
            {"report": True, "dependency": True, "import": True, "process": True, "pipeline": True},
        )

        serialized = json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True)
        check(
            "V1C0A SERIALIZATION EXPOSES HASHED EVIDENCE BUT NO SOURCE BYTES",
            {
                "json": bool(serialized),
                "sample_source_absent": "VALUE = 7" not in serialized,
                "wheel_bytes_absent": "wheel-bytes" not in serialized,
                "sha_present": committed_hash in serialized,
            },
            {"json": True, "sample_source_absent": True, "wheel_bytes_absent": True, "sha_present": True},
        )

        latin = b"# -*- coding: latin-1 -*-\nNAME = 'caf\xe9'\n"
        _write(repo, "modules/latin.py", latin)
        head_latin = _commit(repo, "latin")
        latin_result = _inventory(repo, head_latin)
        check(
            "V1C0A PYTHON ENCODING COOKIE IS PARSED WITHOUT EXECUTION",
            {"ok": latin_result.ok, "latin_present": latin_result.tracked_python_file_count == 7},
            {"ok": True, "latin_present": True},
        )

        _write(repo, "modules/sentinel.py", "from pathlib import Path\nPath('EXECUTED').write_text('bad')\n")
        head_sentinel = _commit(repo, "sentinel")
        sentinel_result = _inventory(repo, head_sentinel)
        check(
            "V1C0A AST INVENTORY NEVER EXECUTES PYTHON TOP LEVEL",
            {"ok": sentinel_result.ok, "sentinel_exists": (repo / "EXECUTED").exists()},
            {"ok": True, "sentinel_exists": False},
        )

        old_report = _report(repo, head_sentinel)
        _write(repo, "new.txt", "new\n")
        _commit(repo, "move head")
        changed = inventory_developer_task_execution_environment(old_report, project_root=repo)
        check(
            "V1C0A HEAD CHANGE RELATIVE TO PINNED REPORT FAILS CLOSED",
            list(changed.issue_codes),
            ["environment_inventory_repository_changed"],
        )
    finally:
        temp.cleanup()

    temp, repo, head = _make_repo()
    try:
        issue = DeveloperTaskPreflightIssue("dirty_worktree", "worktree", "dirty")
        failed = inventory_developer_task_execution_environment(_report(repo, head, issues=(issue,)), project_root=repo)
        check(
            "V1C0A FAILED REPOSITORY REPORT BLOCKS INVENTORY",
            list(failed.issue_codes),
            ["environment_inventory_repository_report_failed"],
        )

        forged_dirty = inventory_developer_task_execution_environment(_report(repo, head, dirty=("unstaged",)), project_root=repo)
        check(
            "V1C0A INCONSISTENT SUCCESS REPORT IS REJECTED",
            list(forged_dirty.issue_codes),
            ["environment_inventory_repository_report_invalid"],
        )

        other = Path(temp.name) / "other"
        other.mkdir()
        mismatch = inventory_developer_task_execution_environment(_report(repo, head), project_root=other)
        check(
            "V1C0A PROJECT ROOT MISMATCH IS REJECTED",
            list(mismatch.issue_codes),
            ["environment_inventory_repository_root_mismatch"],
        )

        raw_types = {}
        try:
            inventory_developer_task_execution_environment({}, project_root=repo)  # type: ignore[arg-type]
            raw_types["report"] = "accepted"
        except TypeError:
            raw_types["report"] = "TypeError"
        try:
            inventory_developer_task_execution_environment(_report(repo, head), project_root=str(repo))  # type: ignore[arg-type]
            raw_types["root"] = "accepted"
        except TypeError:
            raw_types["root"] = "TypeError"
        check(
            "V1C0A RAW PUBLIC INPUT TYPES ARE REJECTED",
            raw_types,
            {"report": "TypeError", "root": "TypeError"},
        )
    finally:
        temp.cleanup()

    temp, repo, _head = _make_repo()
    try:
        _write(repo, "modules/broken.py", "def broken(:\n")
        broken_head = _commit(repo, "broken syntax")
        broken = _inventory(repo, broken_head)
        check(
            "V1C0A PYTHON AST FAILURE FAILS CLOSED",
            list(broken.issue_codes),
            ["environment_inventory_python_parse_failed"],
        )
    finally:
        temp.cleanup()

    temp, repo, _head = _make_repo()
    try:
        _write(repo, "tools/pipeline.py", "def no_flows():\n    return {}\n")
        bad_head = _commit(repo, "bad pipeline")
        bad = _inventory(repo, bad_head)
        check(
            "V1C0A NONCANONICAL PIPELINE CONTRACT FAILS CLOSED",
            list(bad.issue_codes),
            ["environment_inventory_pipeline_contract_invalid"],
        )
    finally:
        temp.cleanup()

    temp, repo, _head = _make_repo()
    try:
        _write(repo, "tools/pipeline.py", "def available_flows():\n    return {'x': [Step('bad', ['cmd.exe'])]}\n")
        bad_head = _commit(repo, "alternate command")
        bad = _inventory(repo, bad_head)
        check(
            "V1C0A PIPELINE ALTERNATE COMMAND SURFACE FAILS CLOSED",
            list(bad.issue_codes),
            ["environment_inventory_pipeline_contract_invalid"],
        )
    finally:
        temp.cleanup()

    temp, repo, _head = _make_repo()
    try:
        collision_head = _commit_case_collision_tree(repo)
        collision = _inventory(repo, collision_head)
        check(
            "V1C0A WINDOWS CASE COLLISION FAILS CLOSED",
            list(collision.issue_codes),
            ["environment_inventory_windows_path_collision"],
        )
    finally:
        temp.cleanup()

    if os.name != "nt":
        temp, repo, _head = _make_repo()
        try:
            target = repo / "modules" / "target.txt"
            target.write_text("target", encoding="utf-8")
            link = repo / "modules" / "link.py"
            link.symlink_to(target)
            symlink_head = _commit(repo, "symlink")
            symlink = _inventory(repo, symlink_head)
            check(
                "V1C0A PYTHON SYMLINK TREE ENTRY FAILS CLOSED",
                list(symlink.issue_codes),
                ["environment_inventory_candidate_not_regular"],
            )
        finally:
            temp.cleanup()
    else:
        check("V1C0A PYTHON SYMLINK TREE ENTRY FAILS CLOSED", "unsupported", "unsupported")

    policy = DEVELOPER_TASK_EXECUTION_ENVIRONMENT_INVENTORY_POLICY
    oversized = _GitTreeEntry(
        mode="100644",
        object_type="blob",
        object_id="a" * 40,
        size_bytes=policy.max_python_file_bytes + 1,
        path="oversized.py",
    )
    try:
        _candidate_blob_entries((oversized,), policy)
        oversized_code = "accepted"
    except Exception as exc:
        oversized_code = getattr(exc, "code", type(exc).__name__)
    check(
        "V1C0A PYTHON SIZE LIMIT FAILS CLOSED BEFORE BLOB READ",
        oversized_code,
        "environment_inventory_python_file_too_large",
    )

    environment = _build_git_environment()
    check(
        "V1C0A GIT ENVIRONMENT CLEARS REDIRECTION AND DISABLES NETWORK PROMPTS",
        {
            "git_dir_absent": "GIT_DIR" not in environment,
            "object_dir_absent": "GIT_OBJECT_DIRECTORY" not in environment,
            "no_lazy_fetch": environment.get("GIT_NO_LAZY_FETCH"),
            "no_replace": environment.get("GIT_NO_REPLACE_OBJECTS"),
            "terminal_prompt": environment.get("GIT_TERMINAL_PROMPT"),
        },
        {
            "git_dir_absent": True,
            "object_dir_absent": True,
            "no_lazy_fetch": "1",
            "no_replace": "1",
            "terminal_prompt": "0",
        },
    )

    source = Path(__file__).resolve().parents[1] / "modules" / "developer" / "developer_task_execution_environment_inventory.py"
    source_text = source.read_text(encoding="utf-8")
    check(
        "V1C0A PRODUCTION INVENTORY HAS NO SANDBOX CANDIDATE PYTHON INSTALL OR HOST FALLBACK SURFACE",
        {
            "WindowsSandbox.exe": "WindowsSandbox.exe" in source_text,
            "python.exe": "python.exe" in source_text,
            "pip install": "pip install" in source_text,
            "shell=True": "shell=True" in source_text,
            "CreateProcess": "CreateProcess" in source_text,
            "os.system(": "os.system(" in source_text,
            "Popen(": "Popen(" in source_text,
        },
        {
            "WindowsSandbox.exe": False,
            "python.exe": False,
            "pip install": False,
            "shell=True": False,
            "CreateProcess": False,
            "os.system(": False,
            "Popen(": False,
        },
    )

    check(
        "V1C0A POLICY HAS NO CALLER CONTROLLED EXECUTION OR CLASSIFICATION OVERRIDES",
        {
            "caller_file_list": "caller_file_list_allowed" in json.dumps(policy.to_dict()),
            "caller_plan": "caller_execution_plan_allowed" in json.dumps(policy.to_dict()),
            "classification_override": "caller_classification_override_allowed" in json.dumps(policy.to_dict()),
            "execution_authorized": policy.execution_authorized,
        },
        {
            "caller_file_list": True,
            "caller_plan": True,
            "classification_override": True,
            "execution_authorized": False,
        },
    )

    print()
    print("=== SUMMARY ===")
    print(json.dumps({"case_count": case_count, "fail_count": fail_count}, indent=2))
    return 0 if fail_count == 0 else 1


def _mutation_blocked(value: Any) -> bool:
    try:
        if not hasattr(value, "__dataclass_fields__"):
            return False
        field = next(iter(value.__dataclass_fields__))
        setattr(value, field, getattr(value, field))
    except (AttributeError, TypeError):
        return True
    return False


if __name__ == "__main__":
    raise SystemExit(main())
