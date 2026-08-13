from __future__ import annotations

"""V1B4C1 deterministic trusted-runtime attestation contract/payload bundle."""

import hashlib
import json

from dataclasses import dataclass, field
from typing import Any

from modules.developer.developer_task_execution_boundary_policy import (
    WINDOWS_SANDBOX_SIGNED_BOUNDARY_POLICY_V1,
)
from modules.developer.developer_task_execution_runtime_attestation_payload import (
    RUNTIME_ATTESTATION_BOOTSTRAP_FILE_NAME,
    RUNTIME_ATTESTATION_CONTROLLER_FILE_NAME,
    RUNTIME_ATTESTATION_NATIVE_HELPER_FILE_NAME,
    RUNTIME_ATTESTATION_POLICY_FILE_NAME,
    RUNTIME_ATTESTATION_WSB_FILE_NAME,
    build_runtime_attestation_bootstrap_script,
    build_runtime_attestation_controller_script,
    build_runtime_attestation_native_helper_source,
    build_runtime_attestation_wsb_template,
    runtime_attestation_policy_bytes,
)
from modules.developer.developer_task_execution_runtime_attestation_policy import (
    RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
    RUNTIME_ATTESTATION_POLICY_ID,
    TRUSTED_PYTHON_RUNTIME_ATTESTATION_POLICY_V1,
    validate_trusted_python_runtime_attestation_policy,
)
from modules.developer.developer_task_execution_runtime_policy import (
    RUNTIME_BUNDLE_FINGERPRINT,
    RUNTIME_LAUNCH_CONTRACT_FINGERPRINT,
)


RUNTIME_ATTESTATION_PAYLOAD_BUNDLE_SCHEMA_VERSION = 1
RUNTIME_ATTESTATION_PAYLOAD_BUNDLE_ID = "v1b4c1_runtime_attestation_contract_payload_bundle_v1"
RUNTIME_ATTESTATION_POLICY_BYTES_SHA256 = "31c4f8de17e999db2d064a8aca4e95d3e2400f21a229317e83b1d5700d1e3c48"
RUNTIME_ATTESTATION_BOOTSTRAP_SHA256 = "73b65b3731f94bc6b0042848e93721877fc2f0f8a70c861e08b17e4303a534bc"
RUNTIME_ATTESTATION_NATIVE_HELPER_SHA256 = "bb9e98675e742b8693da8fee270d045ef9bfa51d4440f461d19cc5b22ee4ca2e"
RUNTIME_ATTESTATION_CONTROLLER_SHA256 = "3ccf95e6ace6c14bb9fb697592202655da4579e76bfaf9e3a704b83cc92b7b2e"
RUNTIME_ATTESTATION_WSB_TEMPLATE_SHA256 = "81861905167211b29fbff7179878b6b671c31b731af482166913b5e20416375f"
RUNTIME_ATTESTATION_PAYLOAD_BUNDLE_FINGERPRINT = "47820f76e8fb0c5542592057c8a4258f968841b12aff6d1c3ee9d69a3e4c1e13"


@dataclass(frozen=True)
class DeveloperTaskRuntimeAttestationPayloadFile:
    file_name: str
    kind: str
    size_bytes: int
    sha256: str
    _bytes: bytes = field(repr=False, compare=False)

    @property
    def ok(self) -> bool:
        return (
            bool(self.file_name)
            and bool(self.kind)
            and self.size_bytes == len(self._bytes)
            and self.sha256 == _sha256(self._bytes)
        )

    def exact_bytes(self) -> bytes:
        return self._bytes

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_name": self.file_name,
            "kind": self.kind,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class DeveloperTaskRuntimeAttestationPayloadBundle:
    schema_version: int
    bundle_id: str
    runtime_attestation_policy_id: str
    runtime_attestation_policy_fingerprint: str
    parent_signed_boundary_fingerprint: str
    runtime_bundle_fingerprint: str
    launch_contract_fingerprint: str
    payload_fingerprint: str
    policy: DeveloperTaskRuntimeAttestationPayloadFile
    bootstrap: DeveloperTaskRuntimeAttestationPayloadFile
    native_helper: DeveloperTaskRuntimeAttestationPayloadFile
    controller: DeveloperTaskRuntimeAttestationPayloadFile
    wsb_template: DeveloperTaskRuntimeAttestationPayloadFile
    sandbox_launched: bool = False
    interpreter_executed: bool = False
    execution_authorized: bool = False

    @property
    def files(self) -> tuple[DeveloperTaskRuntimeAttestationPayloadFile, ...]:
        return (
            self.policy,
            self.bootstrap,
            self.native_helper,
            self.controller,
            self.wsb_template,
        )

    @property
    def ok(self) -> bool:
        return (
            self.schema_version == RUNTIME_ATTESTATION_PAYLOAD_BUNDLE_SCHEMA_VERSION
            and self.bundle_id == RUNTIME_ATTESTATION_PAYLOAD_BUNDLE_ID
            and self.runtime_attestation_policy_id == RUNTIME_ATTESTATION_POLICY_ID
            and self.runtime_attestation_policy_fingerprint == RUNTIME_ATTESTATION_POLICY_FINGERPRINT
            and self.parent_signed_boundary_fingerprint == WINDOWS_SANDBOX_SIGNED_BOUNDARY_POLICY_V1.fingerprint
            and self.runtime_bundle_fingerprint == RUNTIME_BUNDLE_FINGERPRINT
            and self.launch_contract_fingerprint == RUNTIME_LAUNCH_CONTRACT_FINGERPRINT
            and tuple(item.file_name for item in self.files)
            == (
                RUNTIME_ATTESTATION_POLICY_FILE_NAME,
                RUNTIME_ATTESTATION_BOOTSTRAP_FILE_NAME,
                RUNTIME_ATTESTATION_NATIVE_HELPER_FILE_NAME,
                RUNTIME_ATTESTATION_CONTROLLER_FILE_NAME,
                RUNTIME_ATTESTATION_WSB_FILE_NAME,
            )
            and all(item.ok for item in self.files)
            and self.policy.sha256 == RUNTIME_ATTESTATION_POLICY_BYTES_SHA256
            and self.bootstrap.sha256 == RUNTIME_ATTESTATION_BOOTSTRAP_SHA256
            and self.native_helper.sha256 == RUNTIME_ATTESTATION_NATIVE_HELPER_SHA256
            and self.controller.sha256 == RUNTIME_ATTESTATION_CONTROLLER_SHA256
            and self.wsb_template.sha256 == RUNTIME_ATTESTATION_WSB_TEMPLATE_SHA256
            and self.payload_fingerprint == RUNTIME_ATTESTATION_PAYLOAD_BUNDLE_FINGERPRINT
            and self.payload_fingerprint == _payload_fingerprint(self)
            and not self.sandbox_launched
            and not self.interpreter_executed
            and not self.execution_authorized
        )

    def exact_bytes(self, file_name: str) -> bytes:
        for item in self.files:
            if item.file_name == file_name:
                return item.exact_bytes()
        raise KeyError(file_name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "schema_version": self.schema_version,
            "bundle_id": self.bundle_id,
            "runtime_attestation_policy_id": self.runtime_attestation_policy_id,
            "runtime_attestation_policy_fingerprint": self.runtime_attestation_policy_fingerprint,
            "parent_signed_boundary_fingerprint": self.parent_signed_boundary_fingerprint,
            "runtime_bundle_fingerprint": self.runtime_bundle_fingerprint,
            "launch_contract_fingerprint": self.launch_contract_fingerprint,
            "payload_fingerprint": self.payload_fingerprint,
            "files": [item.to_dict() for item in self.files],
            "sandbox_launched": self.sandbox_launched,
            "interpreter_executed": self.interpreter_executed,
            "execution_authorized": self.execution_authorized,
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


def _payload_file(file_name: str, kind: str, data: bytes) -> DeveloperTaskRuntimeAttestationPayloadFile:
    return DeveloperTaskRuntimeAttestationPayloadFile(
        file_name=file_name,
        kind=kind,
        size_bytes=len(data),
        sha256=_sha256(data),
        _bytes=data,
    )


def _payload_fingerprint(bundle: DeveloperTaskRuntimeAttestationPayloadBundle) -> str:
    payload = {
        "schema_version": bundle.schema_version,
        "bundle_id": bundle.bundle_id,
        "runtime_attestation_policy_id": bundle.runtime_attestation_policy_id,
        "runtime_attestation_policy_fingerprint": bundle.runtime_attestation_policy_fingerprint,
        "parent_signed_boundary_fingerprint": bundle.parent_signed_boundary_fingerprint,
        "runtime_bundle_fingerprint": bundle.runtime_bundle_fingerprint,
        "launch_contract_fingerprint": bundle.launch_contract_fingerprint,
        "files": [item.to_dict() for item in bundle.files],
        "sandbox_launched": False,
        "interpreter_executed": False,
        "execution_authorized": False,
    }
    return _sha256(_canonical_json_bytes(payload))


def _canonical_text_payload(data: bytes, name: str) -> None:
    if not data or data.startswith(b"\xef\xbb\xbf") or b"\r" in data or not data.endswith(b"\n"):
        raise RuntimeError(f"V1B4C1 {name} payload is not canonical UTF-8/LF text.")
    data.decode("utf-8", errors="strict")


def build_developer_task_execution_runtime_attestation_payload() -> DeveloperTaskRuntimeAttestationPayloadBundle:
    validate_trusted_python_runtime_attestation_policy()
    if not TRUSTED_PYTHON_RUNTIME_ATTESTATION_POLICY_V1.ok:
        raise RuntimeError("V1B4C1 runtime-attestation policy self-check failed.")

    policy_bytes = runtime_attestation_policy_bytes()
    bootstrap_bytes = build_runtime_attestation_bootstrap_script()
    native_helper_bytes = build_runtime_attestation_native_helper_source()
    controller_bytes = build_runtime_attestation_controller_script()
    wsb_template_bytes = build_runtime_attestation_wsb_template()

    for name, data in (
        ("bootstrap", bootstrap_bytes),
        ("native helper", native_helper_bytes),
        ("controller", controller_bytes),
        ("WSB template", wsb_template_bytes),
    ):
        _canonical_text_payload(data, name)
    if policy_bytes.startswith(b"\xef\xbb\xbf") or b"\r" in policy_bytes:
        raise RuntimeError("V1B4C1 runtime-attestation policy bytes are not canonical UTF-8 JSON.")
    policy_bytes.decode("utf-8", errors="strict")

    bundle = DeveloperTaskRuntimeAttestationPayloadBundle(
        schema_version=RUNTIME_ATTESTATION_PAYLOAD_BUNDLE_SCHEMA_VERSION,
        bundle_id=RUNTIME_ATTESTATION_PAYLOAD_BUNDLE_ID,
        runtime_attestation_policy_id=RUNTIME_ATTESTATION_POLICY_ID,
        runtime_attestation_policy_fingerprint=RUNTIME_ATTESTATION_POLICY_FINGERPRINT,
        parent_signed_boundary_fingerprint=WINDOWS_SANDBOX_SIGNED_BOUNDARY_POLICY_V1.fingerprint,
        runtime_bundle_fingerprint=RUNTIME_BUNDLE_FINGERPRINT,
        launch_contract_fingerprint=RUNTIME_LAUNCH_CONTRACT_FINGERPRINT,
        payload_fingerprint="",
        policy=_payload_file(RUNTIME_ATTESTATION_POLICY_FILE_NAME, "policy", policy_bytes),
        bootstrap=_payload_file(RUNTIME_ATTESTATION_BOOTSTRAP_FILE_NAME, "bootstrap", bootstrap_bytes),
        native_helper=_payload_file(RUNTIME_ATTESTATION_NATIVE_HELPER_FILE_NAME, "native_helper", native_helper_bytes),
        controller=_payload_file(RUNTIME_ATTESTATION_CONTROLLER_FILE_NAME, "controller", controller_bytes),
        wsb_template=_payload_file(RUNTIME_ATTESTATION_WSB_FILE_NAME, "wsb_template", wsb_template_bytes),
    )
    fingerprint = _payload_fingerprint(bundle)
    bundle = DeveloperTaskRuntimeAttestationPayloadBundle(
        schema_version=bundle.schema_version,
        bundle_id=bundle.bundle_id,
        runtime_attestation_policy_id=bundle.runtime_attestation_policy_id,
        runtime_attestation_policy_fingerprint=bundle.runtime_attestation_policy_fingerprint,
        parent_signed_boundary_fingerprint=bundle.parent_signed_boundary_fingerprint,
        runtime_bundle_fingerprint=bundle.runtime_bundle_fingerprint,
        launch_contract_fingerprint=bundle.launch_contract_fingerprint,
        payload_fingerprint=fingerprint,
        policy=bundle.policy,
        bootstrap=bundle.bootstrap,
        native_helper=bundle.native_helper,
        controller=bundle.controller,
        wsb_template=bundle.wsb_template,
    )
    if not bundle.ok:
        raise RuntimeError("V1B4C1 runtime-attestation payload bundle failed its canonical self-check.")
    return bundle
