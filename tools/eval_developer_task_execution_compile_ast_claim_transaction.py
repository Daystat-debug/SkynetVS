from __future__ import annotations

import ast
import copy
import gc
import hashlib
import inspect
import json
import pickle
import time
import weakref

from contextlib import ExitStack
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

import modules.developer.developer_task_execution_compile_ast_claim_transaction as transaction_module
import modules.developer.developer_task_execution_compile_ast_plan as plan_module
import modules.developer.developer_task_execution_runtime_lease as lease_module

from modules.developer.developer_task_execution_compile_ast_claim_transaction import (
    COMPILE_AST_CLAIM_TRANSACTION_STATE_CLAIMED,
    COMPILE_AST_CLAIM_TRANSACTION_STATE_EXPIRED,
    COMPILE_AST_CLAIM_TRANSACTION_STATE_INVALIDATED,
    COMPILE_AST_CLAIM_TRANSACTION_STATE_PLAN_CLAIM_FAILED,
    COMPILE_AST_CLAIM_TRANSACTION_STATE_RUNTIME_LEASE_CLAIM_FAILED,
    DeveloperTaskExecutionCompileAstClaimTransaction,
    DeveloperTaskExecutionCompileAstClaimTransactionError,
    issue_developer_task_execution_compile_ast_claim_transaction,
)
from modules.developer.developer_task_execution_compile_ast_claim_transaction_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_CLOCK_ID,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_OPERATION,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY_ID,
    canonical_developer_task_execution_compile_ast_claim_transaction_policy_json,
    developer_task_execution_compile_ast_claim_transaction_policy_fingerprint,
    validate_developer_task_execution_compile_ast_claim_transaction_policy,
)
from modules.developer.developer_task_execution_compile_ast_plan import (
    COMPILE_AST_PLAN_STATE_CLAIMED_FOR_GATE,
    COMPILE_AST_PLAN_STATE_ISSUED,
    DeveloperTaskExecutionCompileAstPlan,
    DeveloperTaskExecutionCompileAstPlanError,
    DeveloperTaskExecutionCompileAstPlanReport,
    DeveloperTaskExecutionCompileAstPlanSource,
)
from modules.developer.developer_task_execution_compile_ast_plan_policy import (
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_OPERATION,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT,
    DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_ID,
)
from modules.developer.developer_task_execution_runtime_bundle import (
    DeveloperTaskPythonRuntimeBundle,
)
from modules.developer.developer_task_execution_runtime_lease import (
    LEASE_STATE_CLAIMED,
    LEASE_STATE_ISSUED,
    DeveloperTaskExecutionRuntimeLease,
    DeveloperTaskExecutionRuntimeLeaseError,
)
from modules.developer.developer_task_execution_runtime_lease_policy import (
    RUNTIME_LEASE_POLICY_FINGERPRINT,
)
from modules.developer.developer_task_execution_runtime_policy import (
    RUNTIME_BUNDLE_FINGERPRINT,
)
from tools.eval_developer_task_execution_runtime_lease import (
    _FakeServices as _FakeLeaseServices,
    _bundle,
    _host,
    _issue as _issue_runtime_lease,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class _FakeTransactionServices:
    def __init__(
        self,
        *,
        now_ns: int | list[int] | tuple[int, ...] | Any | None = None,
        tokens: list[bytes | Exception] | tuple[bytes | Exception, ...] | None = None,
    ) -> None:
        self.now_ns = time.monotonic_ns() if now_ns is None else now_ns
        self.tokens = list(tokens or (b"T" * 32, b"N" * 32))
        self.token_calls = 0
        self.clock_calls = 0

    def monotonic_ns(self) -> Any:
        self.clock_calls += 1
        if callable(self.now_ns):
            return self.now_ns()
        if isinstance(self.now_ns, list):
            if not self.now_ns:
                raise RuntimeError("fake transaction clock exhausted")
            return self.now_ns.pop(0)
        if isinstance(self.now_ns, tuple):
            values = list(self.now_ns)
            self.now_ns = values
            return self.monotonic_ns()
        return self.now_ns

    def token_bytes(self, size: int) -> bytes:
        self.token_calls += 1
        if not self.tokens:
            raise RuntimeError("fake transaction token source exhausted")
        value = self.tokens.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def _reset_registries() -> None:
    global_sequence = 0
    with transaction_module._REGISTRY_LOCK:
        transaction_module._REGISTRY.clear()
        transaction_module._PLAN_RESERVATIONS.clear()
        transaction_module._RUNTIME_LEASE_RESERVATIONS.clear()
        transaction_module._ISSUANCE_SEQUENCE = global_sequence
    with plan_module._REGISTRY_LOCK:
        plan_module._REGISTRY.clear()
    with lease_module._REGISTRY_LOCK:
        lease_module._REGISTRY.clear()


def _synthetic_plan(
    *,
    content: bytes = b"value = 2\n",
    path: str = "module.py",
    plan_fingerprint: str = "e" * 64,
) -> DeveloperTaskExecutionCompileAstPlan:
    now_ns = time.monotonic_ns()
    source = DeveloperTaskExecutionCompileAstPlanSource(
        path=path,
        mode="100644",
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        encoding="utf-8",
        line_endings="lf" if b"\n" in content else "none",
    )
    sources = (source,)
    source_manifest_sha256 = plan_module._sha256(
        plan_module._source_manifest_bytes(sources)
    )
    report = DeveloperTaskExecutionCompileAstPlanReport(
        policy_id=DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_ID,
        policy_fingerprint=DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_POLICY_FINGERPRINT,
        operation=DEVELOPER_TASK_EXECUTION_COMPILE_AST_PLAN_OPERATION,
        snapshot_policy_fingerprint=(
            "601c727e9b725f1f868a144fa7b975bbb7a35a878c74c2d25bda0a7677a6cd55"
        ),
        snapshot_fingerprint="a" * 64,
        manifest_fingerprint="b" * 64,
        workspace_id="v1c2c0-synthetic-workspace",
        base_commit="c" * 40,
        patch_sha256="d" * 64,
        result_tree="f" * 40,
        changed_files=(path,),
        selected_python_files=(path,),
        deleted_python_files=(),
        changed_non_python_files=(),
        selected_file_count=1,
        selected_total_bytes=len(content),
        sources=sources,
        source_manifest_sha256=source_manifest_sha256,
        plan_fingerprint=plan_fingerprint,
        snapshot_consumed=True,
    )
    if not report.ok:
        raise AssertionError("synthetic V1C1B plan report is invalid")
    secret = b"P" * 32
    binding_fingerprint = plan_module._binding_fingerprint(report)
    plan = DeveloperTaskExecutionCompileAstPlan(
        plan_module._CONSTRUCTOR_KEY,
        plan_module._claim_guard(secret, binding_fingerprint),
        report,
    )
    state = plan_module._PlanState(
        state=COMPILE_AST_PLAN_STATE_ISSUED,
        sources=sources,
        exact_sources={path: content},
        issued_at_ns=now_ns,
        expires_at_ns=now_ns + 300_000_000_000,
        secret=secret,
        binding_fingerprint=binding_fingerprint,
        issuer_id=plan_module._ISSUER_ID,
    )
    with plan_module._REGISTRY_LOCK:
        plan_module._REGISTRY[plan] = state
    return plan


def _synthetic_runtime_lease() -> tuple[
    DeveloperTaskExecutionRuntimeLease,
    DeveloperTaskPythonRuntimeBundle,
    _FakeLeaseServices,
]:
    host = _host()
    bundle = _bundle()
    services = _FakeLeaseServices(host, now_ns=time.monotonic_ns())
    lease = _issue_runtime_lease(host, bundle, services)
    return lease, bundle, services


def _lease_claim_context(
    services: _FakeLeaseServices,
    *,
    validate_transaction_material: bool = False,
) -> ExitStack:
    stack = ExitStack()
    stack.enter_context(patch.object(lease_module, "_SERVICES", services))
    stack.enter_context(
        patch.object(lease_module, "_runtime_bundle_differences", return_value=())
    )
    if not validate_transaction_material:
        stack.enter_context(
            patch.object(transaction_module, "_validate_claimed_material", return_value=None)
        )
    return stack


def _error_code(callback: Any) -> str:
    try:
        callback()
    except DeveloperTaskExecutionCompileAstClaimTransactionError as exc:
        return exc.code
    except TypeError:
        return "TypeError"
    return ""


def _raises_type_error(callback: Any) -> bool:
    try:
        callback()
    except TypeError:
        return True
    return False


def _raises_frozen(callback: Any) -> bool:
    try:
        callback()
    except FrozenInstanceError:
        return True
    return False


def main() -> int:
    case_count = 0
    fail_count = 0

    def check(name: str, actual: Any, expected: Any) -> None:
        nonlocal case_count, fail_count
        case_count += 1
        ok = actual == expected
        if not ok:
            fail_count += 1
        print()
        print(f"=== {name} ===")
        print(
            json.dumps(
                {"actual": actual, "expected": expected, "ok": ok},
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )
        print(f"[{'OK' if ok else 'FAIL'}] {name}")

    _reset_registries()
    policy = DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY
    check(
        "V1C2C0 PINNED CLAIM TRANSACTION POLICY SELF CHECKS",
        {
            "errors": list(
                validate_developer_task_execution_compile_ast_claim_transaction_policy()
            ),
            "policy_id": policy.policy_id,
            "fingerprint": policy.policy_fingerprint,
            "recomputed": (
                developer_task_execution_compile_ast_claim_transaction_policy_fingerprint()
            ),
            "operation": policy.operation,
            "clock": policy.clock,
            "ttl": policy.transaction_ttl_seconds,
            "claim_order": list(policy.claim_order),
            "authorized": policy.execution_authorized_before_claim,
        },
        {
            "errors": [],
            "policy_id": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY_ID,
            "fingerprint": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY_FINGERPRINT,
            "recomputed": "092f17cbbdac961c6be254fbed196d9ff3c639c47957882f6fbbdaa9624b8caa",
            "operation": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_OPERATION,
            "clock": DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_CLOCK_ID,
            "ttl": 300,
            "claim_order": ["plan", "runtime_lease"],
            "authorized": False,
        },
    )

    policy_json = canonical_developer_task_execution_compile_ast_claim_transaction_policy_json()
    check(
        "V1C2C0 POLICY JSON IS CANONICAL AND ARCHITECTURE PINNED",
        {
            "roundtrip": json.loads(policy_json) == policy.to_dict(),
            "fingerprint": developer_task_execution_compile_ast_claim_transaction_policy_fingerprint(),
            "binding_algorithm": json.loads(policy_json)[
                "runtime_lease_fingerprint_semantics"
            ]["algorithm"],
        },
        {
            "roundtrip": True,
            "fingerprint": "092f17cbbdac961c6be254fbed196d9ff3c639c47957882f6fbbdaa9624b8caa",
            "binding_algorithm": "sha256_canonical_process_local_binding_v1",
        },
    )

    check(
        "V1C2C0 PUBLIC ISSUANCE API ACCEPTS ONLY TYPED PLAN AND RUNTIME LEASE",
        {
            name: parameter.kind.name
            for name, parameter in inspect.signature(
                issue_developer_task_execution_compile_ast_claim_transaction
            ).parameters.items()
        },
        {
            "plan": "POSITIONAL_OR_KEYWORD",
            "runtime_lease": "POSITIONAL_OR_KEYWORD",
        },
    )
    check(
        "V1C2C0 PUBLIC CLAIM API ACCEPTS NO CALLER INPUT",
        list(inspect.signature(DeveloperTaskExecutionCompileAstClaimTransaction.claim).parameters),
        ["self"],
    )

    _reset_registries()
    plan = _synthetic_plan()
    lease, _, _ = _synthetic_runtime_lease()
    check(
        "V1C2C0 RAW INPUT TYPES ARE REJECTED",
        {
            "plan": _error_code(
                lambda: issue_developer_task_execution_compile_ast_claim_transaction(
                    {}, lease  # type: ignore[arg-type]
                )
            ),
            "lease": _error_code(
                lambda: issue_developer_task_execution_compile_ast_claim_transaction(
                    plan, {}  # type: ignore[arg-type]
                )
            ),
        },
        {"plan": "TypeError", "lease": "TypeError"},
    )

    _reset_registries()
    plan = _synthetic_plan()
    lease, _, _ = _synthetic_runtime_lease()
    transaction = issue_developer_task_execution_compile_ast_claim_transaction(plan, lease)
    report = transaction.report
    check(
        "V1C2C0 ISSUANCE RESERVES EXACT CAPABILITIES WITHOUT CLAIMING",
        {
            "ok": report.ok,
            "state": transaction.status().state,
            "plan_state": plan.status().state,
            "lease_state": lease.status().state,
            "plan_reserved": report.plan_reserved,
            "lease_reserved": report.runtime_lease_reserved,
            "fingerprint_length": len(report.runtime_lease_fingerprint),
            "sandbox": report.sandbox_launched,
            "candidate": report.candidate_interpreter_executed,
            "processed": report.changed_source_processed,
            "changed_exec": report.changed_code_executed,
            "authorized": report.execution_authorized,
        },
        {
            "ok": True,
            "state": "issued",
            "plan_state": "issued",
            "lease_state": "issued",
            "plan_reserved": True,
            "lease_reserved": True,
            "fingerprint_length": 64,
            "sandbox": False,
            "candidate": False,
            "processed": False,
            "changed_exec": False,
            "authorized": False,
        },
    )

    serialized = json.dumps(report.to_dict(), ensure_ascii=False, sort_keys=True)
    check(
        "V1C2C0 DURABLE REPORT REDACTS OBJECT IDS NONCES SECRETS AND SOURCE BYTES",
        {
            "json": bool(serialized),
            "source_absent": "value = 2" not in serialized,
            "secret_absent": ("T" * 32) not in serialized,
            "nonce_absent": ("N" * 32) not in serialized,
            "object_id_absent": str(id(plan)) not in serialized
            and str(id(lease)) not in serialized,
            "runtime_fingerprint_present": report.runtime_lease_fingerprint in serialized,
        },
        {
            "json": True,
            "source_absent": True,
            "secret_absent": True,
            "nonce_absent": True,
            "object_id_absent": True,
            "runtime_fingerprint_present": True,
        },
    )
    check(
        "V1C2C0 REPORT IS IMMUTABLE",
        _raises_frozen(lambda: setattr(report, "operation", "other")),
        True,
    )
    check(
        "V1C2C0 TRANSACTION IS NON COPYABLE NON PICKLEABLE AND NON AUTHORIZING",
        {
            "copy": _raises_type_error(lambda: copy.copy(transaction)),
            "deepcopy": _raises_type_error(lambda: copy.deepcopy(transaction)),
            "pickle": _raises_type_error(lambda: pickle.dumps(transaction)),
            "authorized": transaction.execution_authorized,
        },
        {"copy": True, "deepcopy": True, "pickle": True, "authorized": False},
    )

    _reset_registries()
    plan = _synthetic_plan()
    lease, bundle, lease_services = _synthetic_runtime_lease()
    transaction = issue_developer_task_execution_compile_ast_claim_transaction(plan, lease)
    with _lease_claim_context(lease_services):
        material = transaction.claim()
    check(
        "V1C2C0 SINGLE CLAIM RETURNS EXACT PLAN MATERIAL AND EXACT RUNTIME BUNDLE",
        {
            "transaction_state": transaction.status().state,
            "plan_state": plan.status().state,
            "lease_state": lease.status().state,
            "same_plan_report": material.plan_material.report is plan.report,
            "exact_source": material.plan_material.exact_source_bytes("module.py").decode(
                "utf-8"
            ),
            "same_runtime_bundle": material.runtime_bundle is bundle,
            "same_runtime_fingerprint": (
                material.runtime_lease_fingerprint
                == transaction.report.runtime_lease_fingerprint
            ),
            "plan_claimed": material.plan_claimed,
            "lease_claimed": material.runtime_lease_claimed,
            "authorized": material.execution_authorized,
        },
        {
            "transaction_state": COMPILE_AST_CLAIM_TRANSACTION_STATE_CLAIMED,
            "plan_state": COMPILE_AST_PLAN_STATE_CLAIMED_FOR_GATE,
            "lease_state": LEASE_STATE_CLAIMED,
            "same_plan_report": True,
            "exact_source": "value = 2\n",
            "same_runtime_bundle": True,
            "same_runtime_fingerprint": True,
            "plan_claimed": True,
            "lease_claimed": True,
            "authorized": False,
        },
    )
    check(
        "V1C2C0 CLAIM REPLAY FAILS CLOSED",
        _error_code(transaction.claim),
        "compile_ast_claim_transaction_already_claimed",
    )
    check(
        "V1C2C0 CLAIMED MATERIAL IS NON COPYABLE AND NON SERIALIZABLE",
        {
            "copy": _raises_type_error(lambda: copy.copy(material)),
            "deepcopy": _raises_type_error(lambda: copy.deepcopy(material)),
            "pickle": _raises_type_error(lambda: pickle.dumps(material)),
        },
        {"copy": True, "deepcopy": True, "pickle": True},
    )
    with transaction_module._REGISTRY_LOCK:
        claimed_state = transaction_module._REGISTRY[transaction]
    check(
        "V1C2C0 TERMINAL CLAIM RELEASES PRIVATE CAPABILITIES SECRETS AND RESERVATIONS",
        {
            "plan_released": claimed_state.plan is None,
            "lease_released": claimed_state.runtime_lease is None,
            "secret_released": claimed_state.secret == b"",
            "nonce_released": claimed_state.binding_nonce == b"",
            "anchors_released": claimed_state.issued_at_ns == 0
            and claimed_state.expires_at_ns == 0,
            "plan_reservations": len(transaction_module._PLAN_RESERVATIONS),
            "lease_reservations": len(transaction_module._RUNTIME_LEASE_RESERVATIONS),
        },
        {
            "plan_released": True,
            "lease_released": True,
            "secret_released": True,
            "nonce_released": True,
            "anchors_released": True,
            "plan_reservations": 0,
            "lease_reservations": 0,
        },
    )

    _reset_registries()
    events: list[str] = []
    plan = _synthetic_plan()
    lease, _, lease_services = _synthetic_runtime_lease()
    transaction = issue_developer_task_execution_compile_ast_claim_transaction(plan, lease)
    original_plan_claim = DeveloperTaskExecutionCompileAstPlan.claim_for_compile_ast_gate
    original_lease_claim = DeveloperTaskExecutionRuntimeLease.claim

    def observed_plan_claim(self):
        events.append("plan")
        return original_plan_claim(self)

    def observed_lease_claim(self):
        events.append("runtime_lease")
        return original_lease_claim(self)

    with _lease_claim_context(lease_services), patch.object(
        DeveloperTaskExecutionCompileAstPlan,
        "claim_for_compile_ast_gate",
        observed_plan_claim,
    ), patch.object(
        DeveloperTaskExecutionRuntimeLease,
        "claim",
        observed_lease_claim,
    ):
        transaction.claim()
    check(
        "V1C2C0 IRREVERSIBLE CLAIM ORDER IS PLAN FIRST RUNTIME LEASE SECOND",
        events,
        ["plan", "runtime_lease"],
    )

    _reset_registries()
    plan = _synthetic_plan()
    lease, _, _ = _synthetic_runtime_lease()
    transaction = issue_developer_task_execution_compile_ast_claim_transaction(plan, lease)
    with patch.object(
        DeveloperTaskExecutionCompileAstPlan,
        "claim_for_compile_ast_gate",
        side_effect=DeveloperTaskExecutionCompileAstPlanError(
            "synthetic_plan_failure", "synthetic"
        ),
    ):
        code = _error_code(transaction.claim)
    check(
        "V1C2C0 PLAN CLAIM FAILURE IS TERMINAL AND RELEASES RESERVATIONS",
        {
            "code": code,
            "transaction_state": transaction.status().state,
            "plan_state": plan.status().state,
            "lease_state": lease.status().state,
            "plan_reservations": len(transaction_module._PLAN_RESERVATIONS),
            "lease_reservations": len(transaction_module._RUNTIME_LEASE_RESERVATIONS),
        },
        {
            "code": "compile_ast_claim_transaction_plan_claim_failed",
            "transaction_state": COMPILE_AST_CLAIM_TRANSACTION_STATE_PLAN_CLAIM_FAILED,
            "plan_state": COMPILE_AST_PLAN_STATE_ISSUED,
            "lease_state": LEASE_STATE_ISSUED,
            "plan_reservations": 0,
            "lease_reservations": 0,
        },
    )
    replacement = issue_developer_task_execution_compile_ast_claim_transaction(plan, lease)
    check(
        "V1C2C0 TERMINAL PLAN FAILURE ALLOWS NEW RESERVATION OF STILL ISSUED INPUTS",
        replacement.status().state,
        "issued",
    )

    _reset_registries()
    plan = _synthetic_plan()
    lease, _, _ = _synthetic_runtime_lease()
    transaction = issue_developer_task_execution_compile_ast_claim_transaction(plan, lease)
    with patch.object(
        DeveloperTaskExecutionRuntimeLease,
        "claim",
        side_effect=DeveloperTaskExecutionRuntimeLeaseError(
            "synthetic_lease_failure", "synthetic"
        ),
    ):
        code = _error_code(transaction.claim)
    check(
        "V1C2C0 RUNTIME LEASE CLAIM FAILURE LEAVES PLAN CONSUMED AND TRANSACTION TERMINAL",
        {
            "code": code,
            "transaction_state": transaction.status().state,
            "plan_state": plan.status().state,
            "lease_state": lease.status().state,
            "plan_reservations": len(transaction_module._PLAN_RESERVATIONS),
            "lease_reservations": len(transaction_module._RUNTIME_LEASE_RESERVATIONS),
        },
        {
            "code": "compile_ast_claim_transaction_runtime_lease_claim_failed",
            "transaction_state": (
                COMPILE_AST_CLAIM_TRANSACTION_STATE_RUNTIME_LEASE_CLAIM_FAILED
            ),
            "plan_state": COMPILE_AST_PLAN_STATE_CLAIMED_FOR_GATE,
            "lease_state": LEASE_STATE_ISSUED,
            "plan_reservations": 0,
            "lease_reservations": 0,
        },
    )

    _reset_registries()
    plan = _synthetic_plan()
    lease, _, _ = _synthetic_runtime_lease()
    transaction = issue_developer_task_execution_compile_ast_claim_transaction(plan, lease)
    plan.claim_for_compile_ast_gate()
    check(
        "V1C2C0 EXTERNALLY CONSUMED PLAN FAILS BEFORE RUNTIME LEASE CLAIM",
        {
            "code": _error_code(transaction.claim),
            "transaction_state": transaction.status().state,
            "lease_state": lease.status().state,
        },
        {
            "code": "compile_ast_claim_transaction_plan_claim_failed",
            "transaction_state": COMPILE_AST_CLAIM_TRANSACTION_STATE_PLAN_CLAIM_FAILED,
            "lease_state": LEASE_STATE_ISSUED,
        },
    )

    _reset_registries()
    plan = _synthetic_plan()
    lease, _, lease_services = _synthetic_runtime_lease()
    transaction = issue_developer_task_execution_compile_ast_claim_transaction(plan, lease)
    with _lease_claim_context(lease_services):
        lease.claim()
    check(
        "V1C2C0 EXTERNALLY CONSUMED RUNTIME LEASE FAILS WITHOUT CONSUMING PLAN",
        {
            "code": _error_code(transaction.claim),
            "transaction_state": transaction.status().state,
            "plan_state": plan.status().state,
        },
        {
            "code": "compile_ast_claim_transaction_runtime_lease_claim_failed",
            "transaction_state": (
                COMPILE_AST_CLAIM_TRANSACTION_STATE_RUNTIME_LEASE_CLAIM_FAILED
            ),
            "plan_state": COMPILE_AST_PLAN_STATE_ISSUED,
        },
    )

    _reset_registries()
    plan = _synthetic_plan()
    lease, _, _ = _synthetic_runtime_lease()
    first = issue_developer_task_execution_compile_ast_claim_transaction(plan, lease)
    second_lease, _, _ = _synthetic_runtime_lease()
    check(
        "V1C2C0 DUPLICATE LIVE PLAN RESERVATION FAILS CLOSED",
        _error_code(
            lambda: issue_developer_task_execution_compile_ast_claim_transaction(
                plan, second_lease
            )
        ),
        "compile_ast_claim_transaction_plan_reserved",
    )
    second_plan = _synthetic_plan(plan_fingerprint="9" * 64)
    check(
        "V1C2C0 DUPLICATE LIVE RUNTIME LEASE RESERVATION FAILS CLOSED",
        _error_code(
            lambda: issue_developer_task_execution_compile_ast_claim_transaction(
                second_plan, lease
            )
        ),
        "compile_ast_claim_transaction_runtime_lease_reserved",
    )
    check(
        "V1C2C0 FIRST LIVE RESERVATION REMAINS INTACT AFTER DUPLICATE ATTEMPTS",
        first.status().state,
        "issued",
    )

    _reset_registries()
    plan_one = _synthetic_plan(plan_fingerprint="1" * 64)
    lease_one, _, _ = _synthetic_runtime_lease()
    plan_two = _synthetic_plan(plan_fingerprint="1" * 64)
    lease_two, _, _ = _synthetic_runtime_lease()
    fake_services_one = _FakeTransactionServices(tokens=[b"S" * 32, b"B" * 32])
    fake_services_two = _FakeTransactionServices(tokens=[b"S" * 32, b"B" * 32])
    with patch.object(transaction_module, "_SERVICES", fake_services_one):
        tx_one = issue_developer_task_execution_compile_ast_claim_transaction(
            plan_one, lease_one
        )
    with patch.object(transaction_module, "_SERVICES", fake_services_two):
        tx_two = issue_developer_task_execution_compile_ast_claim_transaction(
            plan_two, lease_two
        )
    check(
        "V1C2C0 RUNTIME LEASE FINGERPRINT IS UNIQUE PER EXACT TRANSACTION",
        {
            "first_length": len(tx_one.report.runtime_lease_fingerprint),
            "second_length": len(tx_two.report.runtime_lease_fingerprint),
            "different": (
                tx_one.report.runtime_lease_fingerprint
                != tx_two.report.runtime_lease_fingerprint
            ),
        },
        {"first_length": 64, "second_length": 64, "different": True},
    )

    _reset_registries()
    plan = _synthetic_plan()
    lease, _, _ = _synthetic_runtime_lease()
    fake_services = _FakeTransactionServices(
        now_ns=1000,
        tokens=[b"T" * 32, b"N" * 32, b"U" * 32, b"M" * 32],
    )
    with patch.object(transaction_module, "_SERVICES", fake_services):
        transaction = issue_developer_task_execution_compile_ast_claim_transaction(
            plan, lease
        )
        with transaction_module._REGISTRY_LOCK:
            state = transaction_module._REGISTRY[transaction]
            expires_at_ns = state.expires_at_ns
        fake_services.now_ns = expires_at_ns
        expired_status = transaction.status()
    check(
        "V1C2C0 EXPIRY IS TERMINAL AND RELEASES RESERVATIONS",
        {
            "state": expired_status.state,
            "plan_state": plan.status().state,
            "lease_state": lease.status().state,
            "plan_reservations": len(transaction_module._PLAN_RESERVATIONS),
            "lease_reservations": len(transaction_module._RUNTIME_LEASE_RESERVATIONS),
        },
        {
            "state": COMPILE_AST_CLAIM_TRANSACTION_STATE_EXPIRED,
            "plan_state": COMPILE_AST_PLAN_STATE_ISSUED,
            "lease_state": LEASE_STATE_ISSUED,
            "plan_reservations": 0,
            "lease_reservations": 0,
        },
    )
    fake_services.now_ns = expires_at_ns + 1
    with patch.object(transaction_module, "_SERVICES", fake_services):
        replacement = issue_developer_task_execution_compile_ast_claim_transaction(
            plan, lease
        )
        replacement_state = replacement.status().state
    check(
        "V1C2C0 EXPIRED RESERVATION DOES NOT BLOCK NEW TRANSACTION",
        replacement_state,
        "issued",
    )

    _reset_registries()
    plan = _synthetic_plan()
    lease, _, _ = _synthetic_runtime_lease()
    transaction = issue_developer_task_execution_compile_ast_claim_transaction(plan, lease)
    with transaction_module._REGISTRY_LOCK:
        del transaction_module._PLAN_RESERVATIONS[plan]
    check(
        "V1C2C0 RESERVATION TAMPER INVALIDATES TRANSACTION",
        {
            "code": _error_code(transaction.claim),
            "state": transaction.status().state,
        },
        {
            "code": "compile_ast_claim_transaction_reservation_invalid",
            "state": COMPILE_AST_CLAIM_TRANSACTION_STATE_INVALIDATED,
        },
    )

    _reset_registries()
    plan = _synthetic_plan()
    lease, _, _ = _synthetic_runtime_lease()
    transaction = issue_developer_task_execution_compile_ast_claim_transaction(plan, lease)
    transaction._guard = b"X" * 32
    check(
        "V1C2C0 GUARD TAMPER INVALIDATES TRANSACTION",
        {
            "code": _error_code(transaction.claim),
            "state": transaction.status().state,
        },
        {
            "code": "compile_ast_claim_transaction_issuer_binding_invalid",
            "state": COMPILE_AST_CLAIM_TRANSACTION_STATE_INVALIDATED,
        },
    )

    _reset_registries()
    plan = _synthetic_plan()
    lease, _, _ = _synthetic_runtime_lease()
    transaction = issue_developer_task_execution_compile_ast_claim_transaction(plan, lease)
    with transaction_module._REGISTRY_LOCK:
        transaction_module._REGISTRY[transaction].binding_nonce = b"Z" * 32
    check(
        "V1C2C0 PRIVATE BINDING NONCE TAMPER INVALIDATES TRANSACTION",
        _error_code(transaction.claim),
        "compile_ast_claim_transaction_issuer_binding_invalid",
    )

    _reset_registries()
    plan = _synthetic_plan()
    lease, _, _ = _synthetic_runtime_lease()
    transaction = issue_developer_task_execution_compile_ast_claim_transaction(plan, lease)
    object.__setattr__(transaction.report, "plan_fingerprint", "0" * 64)
    check(
        "V1C2C0 DURABLE REPORT TAMPER INVALIDATES PRIVATE OBJECT BINDING",
        _error_code(transaction.claim),
        "compile_ast_claim_transaction_issuer_binding_invalid",
    )

    _reset_registries()
    plan = _synthetic_plan()
    lease, _, _ = _synthetic_runtime_lease()
    transaction = issue_developer_task_execution_compile_ast_claim_transaction(plan, lease)
    mutated_policy = replace(
        DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY,
        transaction_ttl_seconds=1,
    )
    with patch.object(
        transaction_module,
        "DEVELOPER_TASK_EXECUTION_COMPILE_AST_CLAIM_TRANSACTION_POLICY",
        mutated_policy,
    ):
        code = _error_code(transaction.claim)
    check(
        "V1C2C0 POLICY MUTATION FAILS CLOSED",
        {
            "code": code,
            "state": transaction.status().state,
            "policy_errors": list(
                validate_developer_task_execution_compile_ast_claim_transaction_policy(
                    mutated_policy
                )
            ),
        },
        {
            "code": "compile_ast_claim_transaction_policy_invalid",
            "state": COMPILE_AST_CLAIM_TRANSACTION_STATE_INVALIDATED,
            "policy_errors": [
                "capability_limits_invalid",
                "policy_values_changed",
                "policy_fingerprint_mismatch",
            ],
        },
    )

    _reset_registries()
    plan = _synthetic_plan()
    lease, _, _ = _synthetic_runtime_lease()
    invalid_clock = _FakeTransactionServices(now_ns=-1)
    with patch.object(transaction_module, "_SERVICES", invalid_clock):
        issue_clock_code = _error_code(
            lambda: issue_developer_task_execution_compile_ast_claim_transaction(
                plan, lease
            )
        )
    check(
        "V1C2C0 INVALID ISSUANCE CLOCK FAILS CLOSED",
        issue_clock_code,
        "compile_ast_claim_transaction_clock_invalid",
    )

    _reset_registries()
    plan = _synthetic_plan()
    lease, _, _ = _synthetic_runtime_lease()
    transaction = issue_developer_task_execution_compile_ast_claim_transaction(plan, lease)
    invalid_claim_clock = _FakeTransactionServices(now_ns=-1)
    with patch.object(transaction_module, "_SERVICES", invalid_claim_clock):
        claim_clock_code = _error_code(transaction.claim)
    check(
        "V1C2C0 INVALID CLAIM CLOCK INVALIDATES TRANSACTION",
        {
            "code": claim_clock_code,
            "state": transaction.status().state,
        },
        {
            "code": "compile_ast_claim_transaction_clock_invalid",
            "state": COMPILE_AST_CLAIM_TRANSACTION_STATE_INVALIDATED,
        },
    )

    _reset_registries()
    plan = _synthetic_plan()
    lease, _, _ = _synthetic_runtime_lease()
    bad_secret_services = _FakeTransactionServices(tokens=[b"short", b"N" * 32])
    with patch.object(transaction_module, "_SERVICES", bad_secret_services):
        bad_secret_code = _error_code(
            lambda: issue_developer_task_execution_compile_ast_claim_transaction(
                plan, lease
            )
        )
    check(
        "V1C2C0 INVALID SECRET GENERATOR FAILS CLOSED",
        bad_secret_code,
        "compile_ast_claim_transaction_secret_generation_failed",
    )

    _reset_registries()
    plan = _synthetic_plan()
    lease, _, _ = _synthetic_runtime_lease()
    bad_nonce_services = _FakeTransactionServices(tokens=[b"S" * 32, b"short"])
    with patch.object(transaction_module, "_SERVICES", bad_nonce_services):
        bad_nonce_code = _error_code(
            lambda: issue_developer_task_execution_compile_ast_claim_transaction(
                plan, lease
            )
        )
    check(
        "V1C2C0 INVALID BINDING NONCE GENERATOR FAILS CLOSED",
        bad_nonce_code,
        "compile_ast_claim_transaction_binding_nonce_generation_failed",
    )

    _reset_registries()
    plan = _synthetic_plan()
    lease, _, _ = _synthetic_runtime_lease()
    transaction = issue_developer_task_execution_compile_ast_claim_transaction(plan, lease)
    reference = weakref.ref(transaction)
    del transaction
    gc.collect()
    replacement = issue_developer_task_execution_compile_ast_claim_transaction(plan, lease)
    check(
        "V1C2C0 DEAD TRANSACTION DOES NOT LEAK LIVE RESERVATIONS",
        {
            "collected": reference() is None,
            "replacement_state": replacement.status().state,
        },
        {"collected": True, "replacement_state": "issued"},
    )

    _reset_registries()
    plan = _synthetic_plan()
    lease, _, _ = _synthetic_runtime_lease()
    transaction = issue_developer_task_execution_compile_ast_claim_transaction(plan, lease)
    forged = DeveloperTaskExecutionCompileAstClaimTransaction(
        transaction_module._CONSTRUCTOR_KEY,
        transaction._guard,
        transaction.report,
    )
    check(
        "V1C2C0 FORGED BUT UNREGISTERED CAPABILITY CANNOT CLAIM",
        _error_code(forged.claim),
        "compile_ast_claim_transaction_unregistered",
    )

    production_path = (
        PROJECT_ROOT
        / "modules"
        / "developer"
        / "developer_task_execution_compile_ast_claim_transaction.py"
    )
    source = production_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(production_path))
    imported_roots = {
        node.names[0].name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import) and node.names
    }
    active_calls = [
        ast.unparse(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and ast.unparse(node.func)
        in {
            "subprocess.run",
            "subprocess.Popen",
            "ast.parse",
            "compile",
            "exec",
            "eval",
            "open",
        }
    ]
    check(
        "V1C2C0 PRODUCTION MODULE HAS NO FILESYSTEM SANDBOX NETWORK OR SOURCE PROCESSING SURFACE",
        {
            "forbidden_imports": sorted(
                imported_roots
                & {"pathlib", "subprocess", "socket", "urllib", "requests", "ast"}
            ),
            "WindowsSandbox.exe": "WindowsSandbox.exe" in source,
            "pip install": "pip install" in source,
            "active_calls": active_calls,
        },
        {
            "forbidden_imports": [],
            "WindowsSandbox.exe": False,
            "pip install": False,
            "active_calls": [],
        },
    )

    check(
        "V1C2C0 POLICY BINDS EXACT VERIFIED PLAN LEASE AND RUNTIME IDENTITIES",
        {
            "plan_policy": policy.plan_policy_fingerprint,
            "runtime_lease_policy": policy.runtime_lease_policy_fingerprint,
            "runtime_bundle": policy.runtime_bundle_fingerprint,
            "operation": policy.operation,
        },
        {
            "plan_policy": "f017f401254647002347802c5deba6397bdddf27eaa08d02640dc8389fe80865",
            "runtime_lease_policy": "76ceaaf139af10814a403d24fca7455a61db78f095e80d390b360417354e8c18",
            "runtime_bundle": RUNTIME_BUNDLE_FINGERPRINT,
            "operation": "compile_ast_changed_python_v1",
        },
    )

    print()
    print("=== SUMMARY ===")
    print(
        json.dumps(
            {"case_count": case_count, "fail_count": fail_count},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
