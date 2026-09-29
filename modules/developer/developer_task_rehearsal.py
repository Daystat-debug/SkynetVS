from __future__ import annotations

import secrets

from pathlib import Path
from typing import Any

from modules.developer.developer_task_check_static import (
    DeveloperTaskStaticCheckReport,
    run_developer_task_static_checks,
)
from modules.developer.developer_task_patch_apply import (
    DeveloperTaskPatchApplyReport,
    apply_developer_task_patch,
)
from modules.developer.developer_task_preflight_composition import (
    DeveloperTaskPreflightReport,
    run_developer_task_preflight,
)
from modules.developer.developer_task_proposal_contract import (
    DTR_PROPOSAL_SUCCESS_STATUS,
    DeveloperTaskProposalPlan,
)
from modules.developer.developer_task_proposal_intake import (
    intake_developer_task_proposal,
)
from modules.developer.developer_task_rehearsal_contract import (
    DTRB_BEHAVIORAL_NOT_EVALUATED,
    DTRB_FAILED_CLEAN_STATUS,
    DTRB_POLICY_ID,
    DTRB_REJECTED_CLEAN_STATUS,
    DTRB_STOP_REVIEW_STATUS,
    DTRB_SUCCESS_STATUS,
    DeveloperTaskRehearsalArtifactLayout,
    DeveloperTaskRehearsalIssue,
    DeveloperTaskRehearsalStageEvidence,
    DeveloperTaskStaticRehearsalReport,
    canonical_rehearsal_json_bytes,
    rehearsal_sha256,
    stage_evidence,
)
from modules.developer.developer_task_rehearsal_fs import (
    DeveloperTaskRehearsalFileSystemError,
    create_rehearsal_artifact_layout,
    materialize_rehearsal_patch,
    validate_rehearsal_artifact_parent,
    write_rehearsal_result,
)
from modules.developer.developer_task_workspace import (
    DeveloperTaskWorkspaceReport,
    create_developer_task_workspace,
)
from modules.developer.developer_task_workspace_cleanup import (
    DeveloperTaskWorkspaceCleanupReport,
    cleanup_developer_task_workspace,
)
from modules.developer.developer_task_workspace_source import (
    DeveloperTaskSourceRepositorySnapshot,
    snapshot_developer_task_source_repository,
)


class _RehearsalContext:
    def __init__(
        self,
        plan: DeveloperTaskProposalPlan,
        *,
        project_root: Path,
        artifact_parent: Path,
    ) -> None:
        self.plan = plan
        self.project_root = project_root
        self.artifact_parent = artifact_parent
        self.run_id = secrets.token_hex(16)
        self.task_fingerprint = ""
        self.layout: DeveloperTaskRehearsalArtifactLayout | None = None
        self.stage_evidence: list[DeveloperTaskRehearsalStageEvidence] = []
        self.completed_checks: tuple[str, ...] = ()
        self.pending_executable_checks = ()
        self.source_before: DeveloperTaskSourceRepositorySnapshot | None = None
        self.source_after: DeveloperTaskSourceRepositorySnapshot | None = None
        self.preflight_report: DeveloperTaskPreflightReport | None = None
        self.workspace_report: DeveloperTaskWorkspaceReport | None = None
        self.patch_apply_report: DeveloperTaskPatchApplyReport | None = None
        self.static_report: DeveloperTaskStaticCheckReport | None = None
        self.cleanup_report: DeveloperTaskWorkspaceCleanupReport | None = None
        self.patch_materialized = False
        self.patch_applied = False
        self.result_recorded = False
        self.workspace_removed = False
        self.terminal_stage = "VALIDATE_PLAN"
        self.issues: list[DeveloperTaskRehearsalIssue] = []

    def add(self, code: str, stage: str, message: str, *, actual: str = "") -> None:
        self.issues.append(
            DeveloperTaskRehearsalIssue(
                code=code,
                stage=stage,
                message=message,
                actual=actual[:500],
            )
        )


def _compact_exception(exc: Exception) -> str:
    value = f"{type(exc).__name__}: {exc}".replace("\x00", "\\0")
    value = " ".join(value.split())
    return value[:497] + "..." if len(value) > 500 else value


def _plan_fingerprint(plan: DeveloperTaskProposalPlan) -> str:
    payload = {
        "request_fingerprint": plan.request.request_fingerprint,
        "raw_response_sha256": plan.proposal.raw_response_sha256,
        "patch_sha256": plan.proposal.patch_sha256,
        "manifest_fingerprint": plan.manifest_fingerprint,
    }
    return rehearsal_sha256(canonical_rehearsal_json_bytes(payload))


def _validate_plan(context: _RehearsalContext) -> bool:
    plan = context.plan

    if type(plan) is not DeveloperTaskProposalPlan:
        context.add(
            "invalid_plan_type",
            "VALIDATE_PLAN",
            "plan must be an exact DeveloperTaskProposalPlan.",
        )
        return False

    if (
        plan.status != DTR_PROPOSAL_SUCCESS_STATUS
        or plan.authority_granted
        or plan.runtime_authorized
        or plan.promotion_authorized
    ):
        context.add(
            "plan_authority_invalid",
            "VALIDATE_PLAN",
            "DTR-B admits only the non-authorizing DTR-A success plan.",
        )
        return False

    try:
        canonical = intake_developer_task_proposal(
            plan.request,
            plan.proposal.raw_response_bytes,
        )
    except Exception as exc:
        context.add(
            "plan_reintake_exception",
            "VALIDATE_PLAN",
            "DTR-A canonical re-intake raised an unexpected exception.",
            actual=_compact_exception(exc),
        )
        return False

    if not canonical.ok or canonical.plan is None:
        context.add(
            "plan_reintake_rejected",
            "VALIDATE_PLAN",
            "DTR-A canonical re-intake rejected the supplied plan evidence.",
            actual=",".join(canonical.issue_codes),
        )
        return False

    if canonical.plan != plan:
        context.add(
            "plan_canonical_mismatch",
            "VALIDATE_PLAN",
            "Supplied plan differs from canonical DTR-A re-intake output.",
        )
        return False

    context.task_fingerprint = _plan_fingerprint(plan)
    context.stage_evidence.append(
        stage_evidence(
            "DTRA_PLAN",
            ok=True,
            payload=plan.evidence_dict(),
        )
    )
    return True


def _capture_source(
    context: _RehearsalContext,
    *,
    after: bool,
) -> bool:
    stage = "SOURCE_AFTER" if after else "SOURCE_BEFORE"
    try:
        snapshot = snapshot_developer_task_source_repository(context.project_root)
    except Exception as exc:
        context.add(
            "source_snapshot_failed",
            stage,
            "Source repository snapshot failed.",
            actual=_compact_exception(exc),
        )
        return False

    if after:
        context.source_after = snapshot
    else:
        context.source_before = snapshot

    context.stage_evidence.append(
        stage_evidence(
            stage,
            ok=True,
            payload={
                "repository_root": snapshot.repository_root,
                "head_commit": snapshot.head_commit,
                "clean_worktree": snapshot.clean_worktree,
                "fingerprint": snapshot.fingerprint,
            },
        )
    )
    return True


def _add_report_evidence(
    context: _RehearsalContext,
    stage: str,
    report: Any,
) -> None:
    context.stage_evidence.append(
        stage_evidence(
            stage,
            ok=bool(report.ok),
            payload=report.to_dict(),
        )
    )


def _source_unchanged(context: _RehearsalContext) -> bool:
    return bool(
        context.source_before is not None
        and context.source_after is not None
        and context.source_before.fingerprint == context.source_after.fingerprint
    )


def _workspace_residue(context: _RehearsalContext) -> bool:
    report = context.workspace_report
    if report is None or not report.workspace_root:
        return False
    try:
        return Path(report.workspace_root).exists()
    except OSError:
        return True


def _determine_status(context: _RehearsalContext) -> str:
    source_unchanged = _source_unchanged(context)

    if not source_unchanged:
        return DTRB_STOP_REVIEW_STATUS

    if context.workspace_report is not None and context.workspace_report.ok:
        if context.cleanup_report is None or not context.cleanup_report.ok or not context.cleanup_report.removed:
            return DTRB_STOP_REVIEW_STATUS
        if _workspace_residue(context):
            return DTRB_STOP_REVIEW_STATUS

    if (
        context.preflight_report is not None
        and context.preflight_report.ok
        and context.workspace_report is None
        and context.issues
    ):
        return DTRB_STOP_REVIEW_STATUS

    if context.static_report is not None and context.static_report.ok:
        pending = context.static_report.pending_executable_checks
        if not (
            len(pending) == 1
            and pending[0].type == "pipeline"
            and pending[0].flow == "check"
        ):
            return DTRB_STOP_REVIEW_STATUS
        return DTRB_SUCCESS_STATUS

    if context.preflight_report is not None and not context.preflight_report.ok:
        return DTRB_REJECTED_CLEAN_STATUS

    if context.workspace_report is not None and not context.workspace_report.ok:
        return DTRB_STOP_REVIEW_STATUS if _workspace_residue(context) else DTRB_FAILED_CLEAN_STATUS

    if context.layout is None:
        return DTRB_REJECTED_CLEAN_STATUS

    return DTRB_FAILED_CLEAN_STATUS


def _build_report(
    context: _RehearsalContext,
    *,
    status: str,
    result_recorded: bool,
) -> DeveloperTaskStaticRehearsalReport:
    plan = context.plan if type(context.plan) is DeveloperTaskProposalPlan else None
    source_before = context.source_before.fingerprint if context.source_before else ""
    source_after = context.source_after.fingerprint if context.source_after else ""

    return DeveloperTaskStaticRehearsalReport(
        policy_id=DTRB_POLICY_ID,
        run_id=context.run_id,
        status=status,
        terminal_stage=context.terminal_stage,
        task_fingerprint=context.task_fingerprint,
        request_fingerprint=(plan.request.request_fingerprint if plan else ""),
        raw_response_sha256=(plan.proposal.raw_response_sha256 if plan else ""),
        patch_sha256=(plan.proposal.patch_sha256 if plan else ""),
        manifest_fingerprint=(plan.manifest_fingerprint if plan else ""),
        base_commit=(plan.manifest.base_commit if plan else ""),
        target_path=(plan.request.target_path if plan else ""),
        artifact=context.layout,
        stage_evidence=tuple(context.stage_evidence),
        completed_checks=context.completed_checks,
        pending_executable_checks=context.pending_executable_checks,
        source_snapshot_before=source_before,
        source_snapshot_after=source_after,
        source_repository_unchanged=bool(source_before and source_before == source_after),
        workspace_removed=context.workspace_removed,
        patch_materialized=context.patch_materialized,
        patch_applied_in_isolated_workspace=context.patch_applied,
        result_recorded=result_recorded,
        all_required_checks_passed=False,
        behavioral_correctness=DTRB_BEHAVIORAL_NOT_EVALUATED,
        ready_to_promote=False,
        authority_granted=False,
        runtime_authorized=False,
        promotion_authorized=False,
        model_provider_called=False,
        network=False,
        sandbox=False,
        native_worker_launched=False,
        changed_code_executed=False,
        issues=tuple(context.issues),
    )


def _record_result(
    context: _RehearsalContext,
    *,
    status: str,
) -> DeveloperTaskStaticRehearsalReport:
    if context.layout is None:
        return _build_report(context, status=status, result_recorded=False)

    provisional = _build_report(context, status=status, result_recorded=True)
    raw = canonical_rehearsal_json_bytes(provisional.to_dict())

    try:
        result_evidence = write_rehearsal_result(context.layout, raw)
    except DeveloperTaskRehearsalFileSystemError as exc:
        context.add(exc.code, "RESULT_RECORD", str(exc), actual=exc.actual)
        context.terminal_stage = "RESULT_RECORD"
        return _build_report(
            context,
            status=DTRB_STOP_REVIEW_STATUS,
            result_recorded=False,
        )
    except Exception as exc:
        context.add(
            "result_record_failed",
            "RESULT_RECORD",
            "Could not persist the aggregate rehearsal result.",
            actual=_compact_exception(exc),
        )
        context.terminal_stage = "RESULT_RECORD"
        return _build_report(
            context,
            status=DTRB_STOP_REVIEW_STATUS,
            result_recorded=False,
        )

    context.result_recorded = bool(result_evidence.get("recorded"))
    if not context.result_recorded:
        context.add(
            "result_record_unverified",
            "RESULT_RECORD",
            "Result writer did not verify the persisted aggregate report.",
        )
        return _build_report(
            context,
            status=DTRB_STOP_REVIEW_STATUS,
            result_recorded=False,
        )

    # Return the exact logical report that was persisted. The result file
    # identity is verified by the filesystem helper but is not recursively
    # embedded into its own JSON payload.
    return provisional


def run_developer_task_static_rehearsal(
    plan: DeveloperTaskProposalPlan,
    *,
    project_root: Path,
    artifact_parent: Path,
) -> DeveloperTaskStaticRehearsalReport:
    """Compose existing safe developer-task stages without executable checks or promotion."""

    if not isinstance(project_root, Path):
        raise TypeError("project_root must be pathlib.Path")
    if not isinstance(artifact_parent, Path):
        raise TypeError("artifact_parent must be pathlib.Path")

    context = _RehearsalContext(
        plan,
        project_root=project_root,
        artifact_parent=artifact_parent,
    )

    if not _validate_plan(context):
        context.terminal_stage = "VALIDATE_PLAN"
        return _build_report(
            context,
            status=DTRB_REJECTED_CLEAN_STATUS,
            result_recorded=False,
        )

    context.terminal_stage = "SOURCE_BEFORE"
    if not _capture_source(context, after=False):
        return _build_report(
            context,
            status=DTRB_STOP_REVIEW_STATUS,
            result_recorded=False,
        )

    try:
        validate_rehearsal_artifact_parent(
            artifact_parent,
            project_root=project_root,
        )
        context.layout = create_rehearsal_artifact_layout(
            artifact_parent,
            project_root=project_root,
            run_id=context.run_id,
            patch_file=plan.manifest.patch_file,
        )
        context.stage_evidence.append(
            stage_evidence(
                "ARTIFACT_LAYOUT",
                ok=True,
                payload=context.layout.to_dict(),
            )
        )
        materialization = materialize_rehearsal_patch(
            context.layout,
            plan.proposal.patch_bytes,
        )
        if materialization.get("patch_sha256") != plan.proposal.patch_sha256:
            context.add(
                "materialized_patch_hash_mismatch",
                "PATCH_MATERIALIZE",
                "Materialized patch hash differs from DTR-A proposal evidence.",
            )
        else:
            context.patch_materialized = True
        context.stage_evidence.append(
            stage_evidence(
                "PATCH_MATERIALIZE",
                ok=context.patch_materialized,
                payload=materialization,
            )
        )
    except DeveloperTaskRehearsalFileSystemError as exc:
        context.add(exc.code, "ARTIFACT_MATERIALIZE", str(exc), actual=exc.actual)
    except Exception as exc:
        context.add(
            "artifact_materialization_failed",
            "ARTIFACT_MATERIALIZE",
            "Rehearsal artifact materialization failed.",
            actual=_compact_exception(exc),
        )

    if not context.patch_materialized or context.layout is None:
        context.terminal_stage = "ARTIFACT_MATERIALIZE"
        _capture_source(context, after=True)
        status = _determine_status(context)
        return _record_result(context, status=status)

    workspace_created = False

    try:
        context.terminal_stage = "PREFLIGHT"
        context.preflight_report = run_developer_task_preflight(
            plan.manifest,
            project_root=project_root,
            task_root=Path(context.layout.task_root),
        )
        _add_report_evidence(context, "PREFLIGHT", context.preflight_report)

        if context.preflight_report.ok:
            context.terminal_stage = "WORKSPACE"
            context.workspace_report = create_developer_task_workspace(
                plan.manifest,
                preflight_report=context.preflight_report,
                workspace_parent=Path(context.layout.workspace_parent),
            )
            _add_report_evidence(context, "WORKSPACE", context.workspace_report)
            workspace_created = context.workspace_report.ok

        if context.preflight_report.ok and context.workspace_report is not None and context.workspace_report.ok:
            context.terminal_stage = "PATCH_APPLY"
            context.patch_apply_report = apply_developer_task_patch(
                plan.manifest,
                preflight_report=context.preflight_report,
                workspace_report=context.workspace_report,
                workspace_parent=Path(context.layout.workspace_parent),
            )
            _add_report_evidence(context, "PATCH_APPLY", context.patch_apply_report)
            context.patch_applied = context.patch_apply_report.ok

        if (
            context.preflight_report.ok
            and context.workspace_report is not None
            and context.workspace_report.ok
            and context.patch_apply_report is not None
            and context.patch_apply_report.ok
        ):
            context.terminal_stage = "STATIC_CHECKS"
            context.static_report = run_developer_task_static_checks(
                plan.manifest,
                preflight_report=context.preflight_report,
                workspace_report=context.workspace_report,
                patch_apply_report=context.patch_apply_report,
                workspace_parent=Path(context.layout.workspace_parent),
            )
            _add_report_evidence(context, "STATIC_CHECKS", context.static_report)
            context.completed_checks = context.static_report.completed_checks
            context.pending_executable_checks = context.static_report.pending_executable_checks

    except Exception as exc:
        context.add(
            "rehearsal_stage_exception",
            context.terminal_stage,
            "Trusted rehearsal stage raised an unexpected exception.",
            actual=_compact_exception(exc),
        )

    finally:
        if workspace_created and context.workspace_report is not None and context.preflight_report is not None:
            context.terminal_stage = "WORKSPACE_CLEANUP"
            try:
                context.cleanup_report = cleanup_developer_task_workspace(
                    plan.manifest,
                    preflight_report=context.preflight_report,
                    workspace_report=context.workspace_report,
                    workspace_parent=Path(context.layout.workspace_parent),
                )
                _add_report_evidence(context, "WORKSPACE_CLEANUP", context.cleanup_report)
                context.workspace_removed = bool(
                    context.cleanup_report.ok
                    and context.cleanup_report.removed
                )
            except Exception as exc:
                context.add(
                    "workspace_cleanup_exception",
                    "WORKSPACE_CLEANUP",
                    "Verified workspace cleanup raised an unexpected exception.",
                    actual=_compact_exception(exc),
                )

    context.terminal_stage = "SOURCE_AFTER"
    _capture_source(context, after=True)

    if context.source_before is not None and context.source_after is not None:
        if context.source_before.fingerprint != context.source_after.fingerprint:
            context.add(
                "source_repository_changed",
                "SOURCE_AFTER",
                "Source repository changed during DTR-B rehearsal.",
            )

    context.terminal_stage = "RESULT_RECORD"
    status = _determine_status(context)
    return _record_result(context, status=status)
