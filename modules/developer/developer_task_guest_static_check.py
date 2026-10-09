from __future__ import annotations

"""Explicit V2 static checks over a freshly verified, privately reconstructed candidate.

This is the host-side non-executing py_compile gate: compile exact candidate bytes
in memory, discard the code object, never exec/import the target or write a .pyc.
The observed host compiler is NOT an accepted guest Python runtime bundle.
No caller-supplied preflight report is accepted in place of fresh observations.
"""

import os
import sys
import tempfile
import uuid
import warnings
from dataclasses import dataclass
from pathlib import Path
from types import CodeType
from typing import Any

from modules.developer import developer_task_guest_preflight as source_preflight
from modules.developer import developer_task_guest_preflight_git as native
from modules.developer.developer_task_guest_preflight_contract import (
    DeveloperTaskGuestPreflightError, DeveloperTaskGuestPreflightResult,
    GuestPreflightFactsV2, canonical, object_oid, require, sha,
)
from modules.developer.developer_task_guest_proposal_intake import (
    DeveloperTaskGuestProposalError, parse_developer_task_guest_manifest_v2,
    parse_developer_task_guest_proposal_v2,
)
from modules.developer.developer_task_guest_request import DeveloperTaskGuestRequestV2

STATIC_CHECK_KIND = "DTR_GUEST_STATIC_CHECK_V2"
STATIC_CHECK_POLICY = "skynetvs-v1c6-host-static-one-python-modify-v2"
STATIC_CHECK_PASS = "STATIC_CHECKS_VERIFIED_NOT_AUTHORIZED"
STATIC_CHECK_REJECTED = "GUEST_STATIC_CHECK_REJECTED"
MAX_CANDIDATE_BYTES = 192 * 1024  # Matches the landed V2 source-preflight result bound.
STATIC_STAGES = (
    "fresh_source_preflight", "request_response_manifest_revalidation",
    "candidate_reconstructed_and_bound", "in_memory_python_compile",
    "source_and_compiler_unchanged", "owned_temporary_cleanup",
)
ALL_CHECKS = ("git_diff_check", "py_compile", "pipeline:check_guest_source_v1")


@dataclass(frozen=True, slots=True)
class GuestStaticCompilerObservationV2:
    implementation: str
    version: str
    cache_tag: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "HOST_CPYTHON_IN_PROCESS_COMPILE_OBSERVATION",
            "implementation": self.implementation, "version": self.version,
            "cache_tag": self.cache_tag, "mode": "exec", "flags": 0,
            "dont_inherit": True, "optimize": 0, "warnings": "SUPPRESSED_NOT_A_PASS_CRITERION",
            "runtime_bundle_accepted": False, "executable_identity_attested": False,
            "guest_target_interpreter_used": False,
        }


def _compiler_observation() -> GuestStaticCompilerObservationV2:
    require(sys.implementation.name == "cpython" and sys.version_info[:2] in ((3, 12), (3, 13)),
            "unsupported_static_host_compiler")
    require(type(sys.version) is str and type(sys.implementation.cache_tag) is str,
            "invalid_static_host_compiler")
    return GuestStaticCompilerObservationV2(sys.implementation.name, sys.version, sys.implementation.cache_tag)


@dataclass(frozen=True, slots=True)
class GuestStaticCheckFactsV2:
    observation_id: str
    preflight: GuestPreflightFactsV2
    compiler: GuestStaticCompilerObservationV2

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "accepted_preflight_binding": self.preflight.fingerprint,
            "source_preflight_facts": self.preflight.to_dict(),
            "compiler": self.compiler.to_dict(),
            "compiled_path": self.preflight.target_path,
            "compiled_blob_oid": self.preflight.candidate_blob_oid,
            "compiled_sha256": self.preflight.candidate_content_sha256,
            "compiled_bytes": self.preflight.candidate_content_bytes,
            "candidate_tree": self.preflight.candidate_tree,
            "completed_task_checks": list(ALL_CHECKS[:2]),
        }

    @property
    def fingerprint(self) -> str:
        return sha(canonical({"kind": STATIC_CHECK_KIND, "policy_id": STATIC_CHECK_POLICY, **self.to_dict()}))


@dataclass(frozen=True, slots=True)
class DeveloperTaskGuestStaticCheckResult:
    facts: GuestStaticCheckFactsV2 | None
    source_preflight_result: DeveloperTaskGuestPreflightResult | None
    completed_stages: tuple[str, ...]
    issue_codes: tuple[str, ...]
    compilation_attempted: bool = False
    compilation_observed_success: bool = False
    repository_unchanged_verified: bool = False
    temporary_cleanup_verified: bool = False
    compiler_unchanged_verified: bool = False
    syntax_error_line: int | None = None
    syntax_error_column: int | None = None
    reconstruction_git_command_count: int = 0

    @property
    def ok(self) -> bool:
        pre = self.source_preflight_result
        return (type(self.facts) is GuestStaticCheckFactsV2
                and type(pre) is DeveloperTaskGuestPreflightResult and pre.ok
                and type(self.facts.compiler) is GuestStaticCompilerObservationV2
                and self.facts.preflight == pre.facts
                and not self.issue_codes and self.completed_stages == STATIC_STAGES
                and self.compilation_attempted and self.compilation_observed_success
                and self.repository_unchanged_verified and self.temporary_cleanup_verified
                and self.compiler_unchanged_verified)

    @property
    def status(self) -> str:
        return STATIC_CHECK_PASS if self.ok else STATIC_CHECK_REJECTED

    def to_dict(self) -> dict[str, Any]:
        pre = self.source_preflight_result
        return {
            "kind": STATIC_CHECK_KIND, "schema_version": 2, "policy_id": STATIC_CHECK_POLICY,
            "ok": self.ok, "status": self.status, "issue_codes": list(self.issue_codes),
            "completed_stages": list(self.completed_stages),
            "facts": self.facts.to_dict() if self.ok else None,
            "static_check_fingerprint": self.facts.fingerprint if self.ok else "",
            "accepted_preflight_binding": self.facts.preflight.fingerprint if self.ok else "",
            "source_preflight": pre.to_dict() if type(pre) is DeveloperTaskGuestPreflightResult else None,
            "validation_scope": "FRESH_V2_SOURCE_GATE_AND_IN_MEMORY_HOST_COMPILATION_OF_EXACT_CANDIDATE_BLOB",
            "static_checks_passed": self.ok, "py_compile_check_passed": self.ok,
            "completed_task_checks": list(ALL_CHECKS[:2]) if self.ok else [],
            "pending_task_checks": list(ALL_CHECKS[2:]) if self.ok else list(ALL_CHECKS),
            "compilation_attempted": self.compilation_attempted,
            "compilation_observed_success": self.compilation_observed_success,
            "syntax_error_location": {"line": self.syntax_error_line, "column": self.syntax_error_column}
            if self.syntax_error_line is not None else None,
            "repository_unchanged_verified": self.repository_unchanged_verified,
            "temporary_cleanup_verified": self.temporary_cleanup_verified,
            "compiler_unchanged_verified": self.compiler_unchanged_verified,
            "reconstruction_git_command_count": self.reconstruction_git_command_count,
            "preflight_report_from_caller_accepted": False,
            "candidate_written_to_worktree": False, "pyc_written": False,
            "candidate_module_imported": False, "code_object_executed": False,
            "code_object_retained": False, "changed_task_code_executed": False,
            "guest_profile_executed": False, "full_check_executed": False,
            "protected_helper_closure_verified": False, "execution_plan_validated": False,
            "compiler_runtime_bundle_accepted": False, "git_runtime_bundle_accepted": False,
            "guest_target_interpreter_used": False, "capability_issued": False,
            "replay_prevention_verified": False, "provider_authenticated": False,
            "required_profile_checks_passed": False, "all_required_checks_passed": False,
            "ready_to_promote": False, "runtime_authorized": False, "promotion_authorized": False,
            "legacy_full_check_equivalent": False, "behavioral_correctness": "NOT_EVALUATED",
            "live_repository_write_attempted": False, "network_requested": False,
            "sandbox_launched": False, "once_marker_created": False,
            "threat_model": "quiescent trusted host; compiler runs in process without OS resource isolation; not same-user attacker protection",
        }


def _compile_candidate(raw: bytes, path: str) -> None:
    """No import, eval, exec, .pyc, module loader, or arbitrary compiler callback."""
    require(type(raw) is bytes and 0 <= len(raw) <= MAX_CANDIDATE_BYTES, "static_candidate_size")
    native.safe_repo_path(path)
    require(path.casefold().endswith(".py") and b"\0" not in raw, "static_candidate_type")
    # Prevent warning machinery from printing untrusted source text. Warnings are
    # not correctness/acceptance evidence; only success of the compiler is checked.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        code = compile(raw, path, "exec", flags=0, dont_inherit=True, optimize=0)
    require(type(code) is CodeType, "unexpected_static_compiler_result")
    del code


def _bound_preflight(pre: DeveloperTaskGuestPreflightResult, plan: Any, manifest: Any, repository: Path) -> GuestPreflightFactsV2:
    require(type(pre) is DeveloperTaskGuestPreflightResult and pre.ok, "fresh_source_preflight_required")
    f = pre.facts
    r = plan.request
    target = r.binding.target_preimage
    require(f.repository_root == str(repository)
            and f.task_base_commit == r.binding.task_base_commit and f.task_base_tree == r.binding.task_base_tree
            and f.request_fingerprint == r.fingerprint and f.manifest_fingerprint == manifest.fingerprint
            and f.source_sha256 == sha(plan.proposal.raw_response) == manifest.source_sha256
            and f.patch_sha256 == sha(plan.proposal.patch_bytes) == manifest.patch_sha256
            and f.profile_sha256 == r.binding.profile_sha256 and f.target_path == target.path
            and f.target_preimage_oid == target.git_blob_oid,
            "fresh_preflight_input_binding_mismatch")
    return f


def run_developer_task_guest_static_checks_v2(
    raw_manifest: bytes, *, raw_response: bytes, expected_request: DeveloperTaskGuestRequestV2,
    profile_document: bytes, repository_root: Path, git_executable: Path,
    expected_git_sha256: str, scratch_parent: Path,
) -> DeveloperTaskGuestStaticCheckResult:
    """Revalidate V2 inputs/source, reconstruct exact candidate, compile bytes in memory.

    Caller selects/retains request, response, manifest and the installed Git pin.
    This function accepts no persisted preflight "PASS" as evidence. It calls the
    landed source-preflight API afresh, then reconstructs its result in a new private
    index, and checks every resulting candidate identity before compiling. The extra
    reconstruction is required because source-preflight deletes its owned Git store.
    Host-compiler PASS is not accepted guest-runtime/profile execution or promotion.
    """
    pre = None
    root = git = before = executable_before = compiler_before = None
    facts = None
    attempted = compiled = unchanged = cleanup = compiler_unchanged = False
    line = column = None
    stages: list[str] = []
    issues: list[str] = []
    try:
        compiler_before = _compiler_observation()
        pre = source_preflight.run_developer_task_guest_preflight_v2(
            raw_manifest, raw_response=raw_response, expected_request=expected_request,
            profile_document=profile_document, repository_root=repository_root,
            git_executable=git_executable, expected_git_sha256=expected_git_sha256,
            scratch_parent=scratch_parent,
        )
        require(type(pre) is DeveloperTaskGuestPreflightResult, "invalid_source_preflight_result")
        if not pre.ok:
            issues.extend("source_preflight:" + x for x in pre.issue_codes)
            require(False, "fresh_source_preflight_rejected")
        stages.append("fresh_source_preflight")
        manifest = parse_developer_task_guest_manifest_v2(
            raw_manifest, expected_request=expected_request, raw_response=raw_response, profile_document=profile_document,
        )
        plan = parse_developer_task_guest_proposal_v2(
            raw_response, expected_request=expected_request, profile_document=profile_document,
        )
        repository = native.absolute_path(repository_root)
        executable = native.absolute_path(git_executable)
        parent = native.absolute_path(scratch_parent)
        for p in (repository, repository / ".git", parent):
            native.directory_chain(p)
        require(parent != repository and not parent.is_relative_to(repository), "scratch_inside_repository")
        require(not executable.is_relative_to(repository), "git_executable_inside_repository")
        f = _bound_preflight(pre, plan, manifest, repository)
        stages.append("request_response_manifest_revalidation")
        executable_before = native.git_identity(executable, expected_git_sha256)
        require(executable_before["sha256"] == f.git_executable_sha256, "reconstruction_git_mismatch")
        root = Path(tempfile.mkdtemp(prefix="gsc2_", dir=parent))
        require(not root.is_relative_to(repository) and not repository.is_relative_to(root), "scratch_repository_overlap")
        git = native.GuestPreflightGit(repository, executable, root)
        before = git.snapshot(f.task_base_commit, f.task_base_tree)
        require(sha(canonical(before)) == f.repository_snapshot_sha256, "source_changed_since_fresh_preflight")
        require(git.run(["version"]).decode("utf-8", "strict").strip() == f.git_version,
                "reconstruction_git_version_mismatch")
        git.apply_patch(f.task_base_commit, plan.proposal.patch_bytes)
        candidate = git.candidate(f.task_base_commit, before["entries"], f.target_path, f.target_preimage_oid)
        require(candidate == {key: getattr(f, key) for key in (
            "candidate_tree", "candidate_blob_oid", "candidate_content_sha256", "candidate_content_bytes",
        )}, "reconstructed_candidate_mismatch")
        content = git.blobs([f.candidate_blob_oid], temporary=True)[f.candidate_blob_oid]
        require(len(content) == f.candidate_content_bytes and sha(content) == f.candidate_content_sha256
                and object_oid("blob", content) == f.candidate_blob_oid, "compiled_content_identity_mismatch")
        stages.append("candidate_reconstructed_and_bound")
        attempted = True
        _compile_candidate(content, f.target_path)
        compiled = True
        stages.append("in_memory_python_compile")
        facts = GuestStaticCheckFactsV2(uuid.uuid4().hex, f, compiler_before)
    except SyntaxError as exc:
        # No source line, compiler message or patch text is copied to the report.
        line = exc.lineno if type(exc.lineno) is int and 0 < exc.lineno <= MAX_CANDIDATE_BYTES else None
        column = exc.offset if type(exc.offset) is int and 0 < exc.offset <= MAX_CANDIDATE_BYTES else None
        issues.append("candidate_python_syntax_error")
    except (DeveloperTaskGuestProposalError, DeveloperTaskGuestPreflightError) as exc:
        issues.append(exc.code)
    except (OSError, ValueError, TypeError, AttributeError, UnicodeError, RuntimeError, MemoryError) as exc:
        issues.append("static_check_operation_" + type(exc).__name__)
    finally:
        if git is not None and before is not None:
            try:
                after = git.snapshot(f.task_base_commit, f.task_base_tree)
                require(before == after and sha(canonical(after)) == f.repository_snapshot_sha256,
                        "repository_changed_during_static_check")
                require(executable_before == native.git_identity(executable, expected_git_sha256),
                        "git_executable_changed_during_static_check")
                unchanged = True
                compiler_unchanged = compiler_before == _compiler_observation()
                require(compiler_unchanged, "static_compiler_changed_during_check")
                if not issues:
                    stages.append("source_and_compiler_unchanged")
            except (OSError, ValueError, TypeError, AttributeError, RuntimeError, MemoryError) as exc:
                issues.append(exc.code if isinstance(exc, DeveloperTaskGuestPreflightError)
                              else "static_after_observation_failed")
        if root is not None:
            try:
                native.directory_chain(root)
                native.remove_private_tree(root)
                cleanup = not os.path.lexists(native.extended(root))
                require(cleanup, "static_temporary_cleanup_incomplete")
                if not issues:
                    stages.append("owned_temporary_cleanup")
            except (OSError, ValueError, TypeError, RuntimeError) as exc:
                issues.append(exc.code if isinstance(exc, DeveloperTaskGuestPreflightError)
                              else "static_temporary_cleanup_failed")
    return DeveloperTaskGuestStaticCheckResult(
        facts if not issues else None, pre if type(pre) is DeveloperTaskGuestPreflightResult else None,
        tuple(stages), tuple(issues), attempted, compiled, unchanged, cleanup, compiler_unchanged,
        line, column, git.command_count if git is not None else 0,
    )
