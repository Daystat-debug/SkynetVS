from __future__ import annotations

"""Fail-closed composition of all read-only developer-task preflight gates."""

import hashlib

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TypeVar

from modules.developer.developer_task_contract import (
    DeveloperTaskManifest,
    developer_task_manifest_fingerprint,
)
from modules.developer.developer_task_patch_index import (
    DeveloperTaskPatchIndexPreflightReport,
    run_developer_task_patch_index_preflight,
)
from modules.developer.developer_task_patch_integrity import (
    DeveloperTaskPatchIntegrityPreflightReport,
    DeveloperTaskPatchSnapshot,
    run_developer_task_patch_integrity_preflight,
)
from modules.developer.developer_task_patch_scope import (
    DeveloperTaskPatchScopePreflightReport,
    run_developer_task_patch_scope_preflight,
)
from modules.developer.developer_task_preflight import (
    DeveloperTaskPreflightIssue,
    DeveloperTaskRepositoryPreflightReport,
    run_developer_task_repository_preflight,
)
from modules.developer.developer_task_validator import (
    validate_developer_task_manifest,
)


_STAGE_MANIFEST = "manifest"
_STAGE_REPOSITORY = "repository"
_STAGE_PATCH_INTEGRITY = "patch_integrity"
_STAGE_PATCH_INDEX = "patch_index"
_STAGE_PATCH_SCOPE = "patch_scope"
_STAGE_COMPOSITION = "composition"
_COMPLETE_STAGE_ORDER = (
    _STAGE_MANIFEST,
    _STAGE_REPOSITORY,
    _STAGE_PATCH_INTEGRITY,
    _STAGE_PATCH_INDEX,
    _STAGE_PATCH_SCOPE,
    _STAGE_COMPOSITION,
)
_MAX_ERROR_LENGTH = 500


@dataclass(frozen=True)
class DeveloperTaskPreflightReport:
    """Immutable end-to-end proof for the complete read-only preflight."""

    manifest_fingerprint: str
    failed_stage: str
    completed_stages: tuple[str, ...]
    repository_report: DeveloperTaskRepositoryPreflightReport | None
    patch_integrity_report: DeveloperTaskPatchIntegrityPreflightReport | None
    patch_index_report: DeveloperTaskPatchIndexPreflightReport | None
    patch_scope_report: DeveloperTaskPatchScopePreflightReport | None
    issues: tuple[DeveloperTaskPreflightIssue, ...]

    @property
    def ok(self) -> bool:
        return (
            not self.failed_stage
            and self.completed_stages == _COMPLETE_STAGE_ORDER
            and not self.issues
            and _report_evidence_is_consistent(self)
        )

    @property
    def issue_codes(self) -> tuple[str, ...]:
        codes = [item.code for item in self.issues]

        for report in (
            self.repository_report,
            self.patch_integrity_report,
            self.patch_index_report,
            self.patch_scope_report,
        ):
            if report is not None:
                codes.extend(report.issue_codes)

        return tuple(codes)

    @property
    def repository_root(self) -> str:
        if not self.ok or self.repository_report is None:
            return ""

        return self.repository_report.repository_root

    @property
    def base_commit(self) -> str:
        if not self.ok or self.repository_report is None:
            return ""

        return self.repository_report.resolved_base_commit

    @property
    def changed_files(self) -> tuple[str, ...]:
        if not self.ok or self.patch_scope_report is None:
            return ()

        return self.patch_scope_report.changed_files

    @property
    def patch(self) -> DeveloperTaskPatchSnapshot | None:
        if not self.ok or self.patch_integrity_report is None:
            return None

        return self.patch_integrity_report.patch

    def to_dict(self) -> dict[str, Any]:
        patch = self.patch
        return {
            "ok": self.ok,
            "manifest_fingerprint": self.manifest_fingerprint,
            "failed_stage": self.failed_stage,
            "completed_stages": list(self.completed_stages),
            "repository_root": self.repository_root,
            "base_commit": self.base_commit,
            "changed_files": list(self.changed_files),
            "patch": patch.to_dict() if patch is not None else None,
            "repository_report": (
                self.repository_report.to_dict()
                if self.repository_report is not None
                else None
            ),
            "patch_integrity_report": (
                self.patch_integrity_report.to_dict()
                if self.patch_integrity_report is not None
                else None
            ),
            "patch_index_report": (
                self.patch_index_report.to_dict()
                if self.patch_index_report is not None
                else None
            ),
            "patch_scope_report": (
                self.patch_scope_report.to_dict()
                if self.patch_scope_report is not None
                else None
            ),
            "issues": [item.to_dict() for item in self.issues],
            "issue_codes": list(self.issue_codes),
        }


def _report_evidence_is_consistent(report: DeveloperTaskPreflightReport) -> bool:
    repository = report.repository_report
    integrity = report.patch_integrity_report
    patch_index = report.patch_index_report
    scope = report.patch_scope_report

    if (
        not report.manifest_fingerprint
        or repository is None
        or integrity is None
        or patch_index is None
        or scope is None
        or not repository.ok
        or not integrity.ok
        or not patch_index.ok
        or not scope.ok
        or repository.manifest_fingerprint != report.manifest_fingerprint
        or integrity.manifest_fingerprint != report.manifest_fingerprint
        or patch_index.manifest_fingerprint != report.manifest_fingerprint
        or scope.manifest_fingerprint != report.manifest_fingerprint
        or not repository.repository_root
        or integrity.repository_root != repository.repository_root
        or patch_index.repository_root != repository.repository_root
        or scope.repository_root != repository.repository_root
        or not repository.head_commit
        or repository.head_commit != repository.resolved_base_commit
        or repository.dirty_categories
        or patch_index.base_commit != repository.resolved_base_commit
        or scope.base_commit != patch_index.base_commit
        or integrity.patch is None
        or integrity.patch_path != integrity.patch.path
        or integrity.patch_size_bytes != integrity.patch.size_bytes
        or integrity.actual_patch_sha256 != integrity.patch.sha256
        or len(integrity.patch.content) != integrity.patch.size_bytes
        or hashlib.sha256(integrity.patch.content).hexdigest() != integrity.patch.sha256
        or patch_index.changed_files != tuple(item.path for item in patch_index.changes)
        or scope.changed_files != patch_index.changed_files
        or scope.unauthorized_files
        or scope.case_mismatch_files
        or scope.symlink_files
        or scope.gitlink_files
        or scope.type_change_files
        or scope.changed_path_collisions
        or scope.result_index_collisions
    ):
        return False

    return True


class _PreflightCompositionContext:
    def __init__(self, manifest: DeveloperTaskManifest) -> None:
        self.manifest = manifest
        self.manifest_fingerprint = ""
        self.failed_stage = ""
        self.completed_stages: list[str] = []
        self.repository_report: DeveloperTaskRepositoryPreflightReport | None = None
        self.patch_integrity_report: DeveloperTaskPatchIntegrityPreflightReport | None = None
        self.patch_index_report: DeveloperTaskPatchIndexPreflightReport | None = None
        self.patch_scope_report: DeveloperTaskPatchScopePreflightReport | None = None
        self.issues: list[DeveloperTaskPreflightIssue] = []

    def add(
        self,
        code: str,
        check: str,
        message: str,
        *,
        expected: str = "",
        actual: str = "",
    ) -> None:
        self.issues.append(
            DeveloperTaskPreflightIssue(
                code=code,
                check=check,
                message=message,
                expected=expected,
                actual=actual,
            )
        )

    def fail(self, stage: str) -> None:
        if not self.failed_stage:
            self.failed_stage = stage

    def complete(self, stage: str) -> None:
        self.completed_stages.append(stage)

    def report(self) -> DeveloperTaskPreflightReport:
        return DeveloperTaskPreflightReport(
            manifest_fingerprint=self.manifest_fingerprint,
            failed_stage=self.failed_stage,
            completed_stages=tuple(self.completed_stages),
            repository_report=self.repository_report,
            patch_integrity_report=self.patch_integrity_report,
            patch_index_report=self.patch_index_report,
            patch_scope_report=self.patch_scope_report,
            issues=tuple(self.issues),
        )


_ReportT = TypeVar("_ReportT")


def _compact_exception(exc: Exception) -> str:
    value = f"{type(exc).__name__}: {exc}".replace("\x00", "\\0")

    if len(value) > _MAX_ERROR_LENGTH:
        return value[: _MAX_ERROR_LENGTH - 3] + "..."

    return value


def _validate_manifest(context: _PreflightCompositionContext) -> bool:
    try:
        payload = context.manifest.to_dict()
        fingerprint = developer_task_manifest_fingerprint(context.manifest)
    except (AttributeError, TypeError, ValueError) as exc:
        context.add(
            "manifest_invalid",
            _STAGE_MANIFEST,
            "Developer task manifest could not be serialized for validation.",
            actual=_compact_exception(exc),
        )
        context.fail(_STAGE_MANIFEST)
        return False

    try:
        validation = validate_developer_task_manifest(payload)
    except Exception as exc:
        context.add(
            "manifest_validation_failed",
            _STAGE_MANIFEST,
            "Developer task manifest validator raised an unexpected error.",
            actual=_compact_exception(exc),
        )
        context.fail(_STAGE_MANIFEST)
        return False

    if validation.manifest is None:
        context.add(
            "manifest_invalid",
            _STAGE_MANIFEST,
            "Developer task manifest does not satisfy the validated contract.",
            actual=",".join(validation.issue_codes) or "invalid",
        )
        context.fail(_STAGE_MANIFEST)
        return False

    try:
        canonical_fingerprint = developer_task_manifest_fingerprint(validation.manifest)
    except (AttributeError, TypeError, ValueError) as exc:
        context.add(
            "manifest_validation_failed",
            _STAGE_MANIFEST,
            "Canonical developer task manifest could not be fingerprinted.",
            actual=_compact_exception(exc),
        )
        context.fail(_STAGE_MANIFEST)
        return False

    if (
        validation.manifest != context.manifest
        or canonical_fingerprint != fingerprint
    ):
        context.add(
            "manifest_invalid",
            _STAGE_MANIFEST,
            "Developer task manifest changed during canonical validation.",
            actual="canonical manifest mismatch",
        )
        context.fail(_STAGE_MANIFEST)
        return False

    context.manifest_fingerprint = fingerprint
    context.complete(_STAGE_MANIFEST)
    return True


def _invoke_stage(
    context: _PreflightCompositionContext,
    stage: str,
    function: Callable[[], _ReportT],
    expected_type: type[_ReportT],
) -> _ReportT | None:
    try:
        report = function()
    except Exception as exc:
        context.add(
            f"{stage}_execution_failed",
            stage,
            "Developer task preflight stage raised an unexpected error.",
            actual=_compact_exception(exc),
        )
        context.fail(stage)
        return None

    if not isinstance(report, expected_type):
        context.add(
            f"{stage}_report_invalid",
            stage,
            "Developer task preflight stage returned an invalid report type.",
            expected=expected_type.__name__,
            actual=type(report).__name__,
        )
        context.fail(stage)
        return None

    try:
        stage_ok = report.ok
    except Exception as exc:
        context.add(
            f"{stage}_report_invalid",
            stage,
            "Developer task preflight stage report could not be evaluated.",
            expected="stable boolean ok property",
            actual=_compact_exception(exc),
        )
        context.fail(stage)
        return None

    if stage_ok is not True:
        context.fail(stage)
        return report

    context.complete(stage)
    return report


def _validate_final_chain(context: _PreflightCompositionContext) -> bool:
    repository = context.repository_report
    integrity = context.patch_integrity_report
    patch_index = context.patch_index_report
    scope = context.patch_scope_report

    if (
        repository is None
        or integrity is None
        or patch_index is None
        or scope is None
        or not repository.ok
        or not integrity.ok
        or not patch_index.ok
        or not scope.ok
        or repository.manifest_fingerprint != context.manifest_fingerprint
        or integrity.manifest_fingerprint != context.manifest_fingerprint
        or patch_index.manifest_fingerprint != context.manifest_fingerprint
        or scope.manifest_fingerprint != context.manifest_fingerprint
        or not repository.repository_root
        or integrity.repository_root != repository.repository_root
        or patch_index.repository_root != repository.repository_root
        or scope.repository_root != repository.repository_root
        or not repository.head_commit
        or repository.head_commit != repository.resolved_base_commit
        or repository.dirty_categories
        or patch_index.base_commit != repository.resolved_base_commit
        or scope.base_commit != patch_index.base_commit
        or integrity.patch is None
        or integrity.patch_path != integrity.patch.path
        or integrity.patch_size_bytes != integrity.patch.size_bytes
        or integrity.actual_patch_sha256 != integrity.patch.sha256
        or integrity.patch.sha256 != context.manifest.patch_sha256
        or len(integrity.patch.content) != integrity.patch.size_bytes
        or hashlib.sha256(integrity.patch.content).hexdigest() != integrity.patch.sha256
        or patch_index.changed_files != tuple(item.path for item in patch_index.changes)
        or scope.allowed_files != context.manifest.allowed_files
        or scope.changed_files != patch_index.changed_files
        or scope.unauthorized_files
        or scope.case_mismatch_files
        or scope.symlink_files
        or scope.gitlink_files
        or scope.type_change_files
        or scope.changed_path_collisions
        or scope.result_index_collisions
    ):
        context.add(
            "preflight_chain_invalid",
            _STAGE_COMPOSITION,
            "Developer task preflight evidence chain is internally inconsistent.",
            actual="incomplete or mismatched gate evidence",
        )
        context.fail(_STAGE_COMPOSITION)
        return False

    context.complete(_STAGE_COMPOSITION)
    return True


def run_developer_task_preflight(
    manifest: DeveloperTaskManifest,
    *,
    project_root: Path,
    task_root: Path,
) -> DeveloperTaskPreflightReport:
    """Run the complete fail-closed read-only developer-task preflight."""
    if not isinstance(manifest, DeveloperTaskManifest):
        raise TypeError("manifest must be DeveloperTaskManifest")

    if not isinstance(project_root, Path):
        raise TypeError("project_root must be pathlib.Path")

    if not isinstance(task_root, Path):
        raise TypeError("task_root must be pathlib.Path")

    context = _PreflightCompositionContext(manifest)

    if not _validate_manifest(context):
        return context.report()

    repository_report = _invoke_stage(
        context,
        _STAGE_REPOSITORY,
        lambda: run_developer_task_repository_preflight(
            manifest,
            project_root=project_root,
        ),
        DeveloperTaskRepositoryPreflightReport,
    )
    context.repository_report = repository_report

    if repository_report is None or not repository_report.ok:
        return context.report()

    patch_integrity_report = _invoke_stage(
        context,
        _STAGE_PATCH_INTEGRITY,
        lambda: run_developer_task_patch_integrity_preflight(
            manifest,
            repository_report=repository_report,
            task_root=task_root,
        ),
        DeveloperTaskPatchIntegrityPreflightReport,
    )
    context.patch_integrity_report = patch_integrity_report

    if patch_integrity_report is None or not patch_integrity_report.ok:
        return context.report()

    patch_index_report = _invoke_stage(
        context,
        _STAGE_PATCH_INDEX,
        lambda: run_developer_task_patch_index_preflight(
            manifest,
            repository_report=repository_report,
            patch_integrity_report=patch_integrity_report,
        ),
        DeveloperTaskPatchIndexPreflightReport,
    )
    context.patch_index_report = patch_index_report

    if patch_index_report is None or not patch_index_report.ok:
        return context.report()

    patch_scope_report = _invoke_stage(
        context,
        _STAGE_PATCH_SCOPE,
        lambda: run_developer_task_patch_scope_preflight(
            manifest,
            patch_index_report=patch_index_report,
        ),
        DeveloperTaskPatchScopePreflightReport,
    )
    context.patch_scope_report = patch_scope_report

    if patch_scope_report is None or not patch_scope_report.ok:
        return context.report()

    _validate_final_chain(context)
    return context.report()
