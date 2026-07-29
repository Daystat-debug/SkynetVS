from __future__ import annotations

import hashlib
import json

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


DEVELOPER_TASK_SCHEMA_VERSION = 1
DEVELOPER_TASK_PROJECT = "SkynetVS"
DEVELOPER_TASK_KIND_PATCH = "patch"
DEVELOPER_TASK_ORIGIN_MANUAL = "manual"
DEVELOPER_TASK_ORIGIN_BROWSER_BRIDGE = "browser_bridge"
DEVELOPER_TASK_ALLOWED_ORIGINS = frozenset({
    DEVELOPER_TASK_ORIGIN_MANUAL,
    DEVELOPER_TASK_ORIGIN_BROWSER_BRIDGE,
})
DEVELOPER_TASK_INSTALL_MANUAL_CONFIRMATION = "manual_confirmation"

DEVELOPER_CHECK_GIT_DIFF = "git_diff_check"
DEVELOPER_CHECK_PY_COMPILE = "py_compile"
DEVELOPER_CHECK_PYTHON_MODULE = "python_module"
DEVELOPER_CHECK_PIPELINE = "pipeline"


@dataclass(frozen=True)
class DeveloperTaskCheck:
    type: str
    scope: str = ""
    module: str = ""
    flow: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": self.type,
        }

        if self.scope:
            payload["scope"] = self.scope

        if self.module:
            payload["module"] = self.module

        if self.flow:
            payload["flow"] = self.flow

        return payload


@dataclass(frozen=True)
class DeveloperTaskManifest:
    schema_version: int
    task_kind: str
    task_id: str
    title: str
    project: str
    origin: str
    source_ref: str
    source_sha256: str
    base_commit: str
    patch_file: str
    patch_sha256: str
    allowed_files: tuple[str, ...]
    checks: tuple[DeveloperTaskCheck, ...]
    install_policy: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "task_kind": self.task_kind,
            "task_id": self.task_id,
            "title": self.title,
            "project": self.project,
            "origin": self.origin,
            "source_ref": self.source_ref,
            "source_sha256": self.source_sha256,
            "base_commit": self.base_commit,
            "patch_file": self.patch_file,
            "patch_sha256": self.patch_sha256,
            "allowed_files": list(self.allowed_files),
            "checks": [item.to_dict() for item in self.checks],
            "install_policy": self.install_policy,
        }


@dataclass(frozen=True)
class DeveloperTaskValidationIssue:
    code: str
    field: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "field": self.field,
            "message": self.message,
        }


@dataclass(frozen=True)
class DeveloperTaskValidationResult:
    manifest: DeveloperTaskManifest | None
    issues: tuple[DeveloperTaskValidationIssue, ...]

    @property
    def ok(self) -> bool:
        return self.manifest is not None and not self.issues

    @property
    def issue_codes(self) -> tuple[str, ...]:
        return tuple(item.code for item in self.issues)


class DeveloperTaskValidationError(ValueError):
    def __init__(
        self,
        issues: Sequence[DeveloperTaskValidationIssue],
    ) -> None:
        self.issues = tuple(issues)
        preview = "; ".join(
            f"{item.field}: {item.code}"
            for item in self.issues[:5]
        )

        if len(self.issues) > 5:
            preview = f"{preview}; +{len(self.issues) - 5} more"

        super().__init__(
            f"Developer task manifest is invalid: {preview or 'unknown validation error'}"
        )


def canonical_developer_task_manifest_json(
    manifest: DeveloperTaskManifest,
) -> str:
    return json.dumps(
        manifest.to_dict(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def developer_task_manifest_fingerprint(
    manifest: DeveloperTaskManifest,
) -> str:
    canonical = canonical_developer_task_manifest_json(manifest)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()