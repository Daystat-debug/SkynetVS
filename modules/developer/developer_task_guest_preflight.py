from __future__ import annotations

"""Explicit V2 source-preflight: trusted request -> proposal/manifest -> private Git index.

Import is inert. Invocation observes a caller-selected repository and runs only a
caller-pinned Git executable. No V1 reinterpretation, runtime admission or task-code
execution. Returned evidence is unsigned data, not a lease or reusable capability.
"""

import json
import os
import tempfile
import uuid
from pathlib import Path

from modules.developer.developer_task_guest_profile_contract import (
    parse_developer_task_guest_profile,
)
from modules.developer.developer_task_guest_proposal_intake import (
    DeveloperTaskGuestProposalError, parse_developer_task_guest_manifest_v2,
    parse_developer_task_guest_proposal_v2,
)
from modules.developer.developer_task_guest_request import DeveloperTaskGuestRequestV2
from modules.developer.developer_task_guest_preflight_contract import (
    DeveloperTaskGuestPreflightError, DeveloperTaskGuestPreflightResult,
    GuestPreflightFactsV2, PROTECTED_PIPELINE_BYTES, PROTECTED_PIPELINE_OID,
    PROTECTED_PIPELINE_PATH, PROTECTED_PIPELINE_SHA256, canonical, require, sha,
    validate_guest_patch_format,
)
from modules.developer.developer_task_guest_preflight_git import (
    GuestPreflightGit, absolute_path, directory_chain, extended, git_identity, remove_private_tree,
)


def _source_membership(git: GuestPreflightGit, snapshot: dict, request: DeveloperTaskGuestRequestV2,
                       profile_document: bytes) -> tuple[int, int]:
    entries = {x["path"]: x for x in snapshot["entries"]}
    profile = parse_developer_task_guest_profile(profile_document)
    pins: dict[str, tuple[str, int, str]] = {}
    for item in request.context:
        row = entries.get(item.path)
        require(row is not None and row["mode"] == item.mode
                and row["oid"] == item.git_blob_oid, "context_not_in_base_tree")
        pins[item.path] = (item.git_blob_oid, item.content_bytes, item.content_sha256)
    target = request.binding.target_preimage
    require(target.path in pins and pins[target.path] == (target.git_blob_oid, target.content_bytes, target.content_sha256),
            "target_preimage_not_in_base_tree")
    blobs = git.blobs([p[0] for p in pins.values()])
    for item in request.context:
        require(blobs[item.git_blob_oid] == item.content, "context_content_not_in_base_tree")
    require(b"\0" not in blobs[target.git_blob_oid], "target_preimage_binary")
    try:
        blobs[target.git_blob_oid].decode("utf-8", "strict")
    except UnicodeError as exc:
        raise DeveloperTaskGuestPreflightError("target_preimage_not_utf8") from exc
    return len(request.context), len(profile.steps)


def _profile_entrypoints(git: GuestPreflightGit, snapshot: dict, profile_document: bytes) -> None:
    entries = {x["path"]: x for x in snapshot["entries"]}
    profile = parse_developer_task_guest_profile(profile_document)
    required = [(s.path, s.git_mode, s.git_blob_oid, s.content_bytes, s.content_sha256) for s in profile.steps]
    # Exclusions remain excluded; preserving their bytes is not running their checks.
    document = json.loads(profile_document)
    for row in document["excluded_steps"]:
        pin = row["git_blob_material"]
        required.append((row["path"], pin["mode"], pin["oid"], pin["bytes"], pin["sha256"]))
    required.append((PROTECTED_PIPELINE_PATH, "100644", PROTECTED_PIPELINE_OID,
                     PROTECTED_PIPELINE_BYTES, PROTECTED_PIPELINE_SHA256))
    for path, mode, oid, _size, _digest in required:
        require(entries.get(path) == {"path": path, "mode": mode, "oid": oid}, "protected_profile_entrypoint_changed")
    blobs = git.blobs([row[2] for row in required])
    for _path, _mode, oid, size, digest in required:
        require(len(blobs[oid]) == size and sha(blobs[oid]) == digest, "protected_profile_content_changed")


def run_developer_task_guest_preflight_v2(
    raw_manifest: bytes, *, raw_response: bytes, expected_request: DeveloperTaskGuestRequestV2,
    profile_document: bytes, repository_root: Path, git_executable: Path,
    expected_git_sha256: str, scratch_parent: Path,
) -> DeveloperTaskGuestPreflightResult:
    """Verify one V2 text MODIFY without changing source worktree/index/refs.

    Caller retains/selects the trusted expected request, exact response and manifest,
    and the trusted Git executable hash. Checks run against the request's exact HEAD;
    no descendant wildcard. Patch is applied only to an external temporary index.
    No py_compile or guest pipeline invocation occurs. Source helpers/dependencies,
    toolchain provenance and executable admission remain separate requirements.
    """
    completed: list[str] = []
    issues: list[str] = []
    facts = None
    before = None
    git = None
    root = None
    observed = unchanged = cleanup = False
    try:
        manifest = parse_developer_task_guest_manifest_v2(
            raw_manifest, expected_request=expected_request, raw_response=raw_response,
            profile_document=profile_document,
        )
        plan = parse_developer_task_guest_proposal_v2(
            raw_response, expected_request=expected_request, profile_document=profile_document,
        )
        request = plan.request
        completed.append("manifest_response_request")
        target = request.binding.target_preimage
        shape = validate_guest_patch_format(plan.proposal.patch_bytes, target.path, target.git_blob_oid)
        completed.append("patch_format")
        repository = absolute_path(repository_root)
        executable = absolute_path(git_executable)
        parent = absolute_path(scratch_parent)
        directory_chain(repository)
        directory_chain(repository / ".git")
        directory_chain(parent)
        require(parent != repository and not parent.is_relative_to(repository), "scratch_inside_repository")
        require(not executable.is_relative_to(repository), "git_executable_inside_repository")
        observer_before = git_identity(executable, expected_git_sha256)
        root = Path(tempfile.mkdtemp(prefix="gpv2_", dir=parent))
        require(not root.is_relative_to(repository) and not repository.is_relative_to(root), "scratch_repository_overlap")
        git = GuestPreflightGit(repository, executable, root)
        observed = True
        before = git.snapshot(request.binding.task_base_commit, request.binding.task_base_tree)
        completed.append("repository")
        context_count, step_count = _source_membership(git, before, request, profile_document)
        completed.append("source_membership")
        _profile_entrypoints(git, before, profile_document)
        completed.append("profile_entrypoints")
        git.apply_patch(request.binding.task_base_commit, plan.proposal.patch_bytes)
        completed.append("patch_applicability")
        candidate = git.candidate(request.binding.task_base_commit, before["entries"], target.path, target.git_blob_oid)
        require(not shape.new_oid_prefix or candidate["candidate_blob_oid"].startswith(shape.new_oid_prefix),
                "patch_new_oid_mismatch")
        completed.extend(("patch_scope", "candidate_tree"))
        version = git.run(["version"]).decode("utf-8", "strict").strip()
        facts = GuestPreflightFactsV2(
            observation_id=uuid.uuid4().hex, repository_root=str(repository),
            task_base_commit=request.binding.task_base_commit, task_base_tree=request.binding.task_base_tree,
            request_fingerprint=request.fingerprint, manifest_fingerprint=manifest.fingerprint,
            source_sha256=manifest.source_sha256, patch_sha256=manifest.patch_sha256,
            profile_sha256=request.binding.profile_sha256, target_path=target.path,
            target_preimage_oid=target.git_blob_oid, **candidate,
            git_executable_sha256=observer_before["sha256"], git_version=version,
            repository_snapshot_sha256=sha(canonical(before)), tracked_paths=len(before["entries"]),
            protected_entrypoints=step_count, pipeline_blob_oid=PROTECTED_PIPELINE_OID,
            context_files=context_count,
        )
    except (DeveloperTaskGuestProposalError, DeveloperTaskGuestPreflightError) as exc:
        issues.append(exc.code)
    except (OSError, ValueError, TypeError, AttributeError, UnicodeError, RuntimeError) as exc:
        # Do not disclose source paths, raw response or subprocess stderr in failures.
        issues.append("preflight_operation_" + type(exc).__name__)
    finally:
        if git is not None and before is not None:
            try:
                after = git.snapshot(request.binding.task_base_commit, request.binding.task_base_tree)
                require(before == after, "repository_changed_during_preflight")
                require(observer_before == git_identity(executable, expected_git_sha256), "git_executable_changed_during_preflight")
                unchanged = True
                if not issues:
                    completed.append("repository_unchanged")
            except (OSError, ValueError, TypeError, AttributeError, RuntimeError) as exc:
                issues.append(exc.code if isinstance(exc, DeveloperTaskGuestPreflightError) else "repository_after_observation_failed")
        if root is not None:
            try:
                # Only the fresh private directory allocated by this invocation.
                directory_chain(root)
                remove_private_tree(root)
                cleanup = not os.path.lexists(extended(root))
                require(cleanup, "temporary_cleanup_incomplete")
                if not issues:
                    completed.append("temporary_cleanup")
            except (OSError, ValueError) as exc:
                issues.append(exc.code if isinstance(exc, DeveloperTaskGuestPreflightError) else "temporary_cleanup_failed")
    return DeveloperTaskGuestPreflightResult(
        facts if not issues else None, tuple(completed), tuple(issues), observed, unchanged,
        cleanup, git.command_count if git is not None else 0,
    )
