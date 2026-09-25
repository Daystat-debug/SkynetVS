"""HWA02-A portable source/in-memory evaluator. No host executor is registered.

Run with -I -S -B. Runtime audit hook rejects effectful filesystem operations,
subprocess/socket/ctypes loads during the measured suite, not ordinary source reads.
PID/fork rejection is simulated; real child/native/Windows acceptance is NOT RUN.
"""
from __future__ import annotations

import ast
import copy
import gc
import hashlib
import json
import os
from pathlib import Path
import pickle
import sys
import threading
import unittest
from contextlib import contextmanager
from dataclasses import FrozenInstanceError, replace
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from modules import action_authority as authority_module
from modules.action_authority import ActionAuthority, ActionAuthorityError, ActionGrant
from modules.action_broker import ActionBroker, ExecutorRegistration, compose_action_boundary
from modules.action_contract import (
    ActionContractError, ActionEffectClass, ActionRequest, ActionResult, ActionRiskClass,
    ActionSpec, ActionStatus, ActionVerification, EffectState, ExecutorOutcome,
    ExecutorStatus, ParameterRule, VerificationStatus, canonical, parameters_from_dict,
)

EXPECTED_TESTS = 94
NEW_MODULES = ("modules/action_contract.py", "modules/action_authority.py", "modules/action_broker.py")


def request(number: int = 1, **changes) -> ActionRequest:
    values = dict(request_id=f"{number:032x}", scope_id="2" * 32, action="ECHO", version=1,
                  parameters=(("text", "пример"),))
    values.update(changes)
    return ActionRequest(**values)


def spec(**changes) -> ActionSpec:
    values = dict(action="ECHO", version=1, executor_id="memory.echo", policy_revision="v1",
                  risk=ActionRiskClass.READ_ONLY, effect=ActionEffectClass.MEMORY,
                  parameters=(ParameterRule("text", "string"),),
                  max_grant_ms=10000, max_execution_ms=1000)
    values.update(changes)
    return ActionSpec(**values)


class MemoryExecutor:
    def __init__(self):
        self.calls = 0
        self.requests = []
        self.deadlines = []
        self.hook = None

    def execute(self, value, *, deadline_ns):
        self.calls += 1
        self.requests.append(value)
        self.deadlines.append(deadline_ns)
        if self.hook is not None:
            return self.hook(value)
        return ExecutorOutcome(ExecutorStatus.SUCCEEDED, value.parameters)


class MemoryVerifier:
    def __init__(self, policy):
        self.policy = policy
        self.calls = 0
        self.hook = None

    def verify(self, value, outcome):
        self.calls += 1
        if self.hook is not None:
            return self.hook(value, outcome)
        # Predicate recomputes expected output; does not just echo outcome status.
        state = VerificationStatus.VERIFIED if outcome.output == value.parameters else VerificationStatus.REJECTED
        return ActionVerification(value.fingerprint(), self.policy.fingerprint(), outcome.fingerprint(), state)


def domain(policy=None):
    policy = policy or spec()
    executor = MemoryExecutor()
    verifier = MemoryVerifier(policy)
    issuer, broker = compose_action_boundary((ExecutorRegistration(policy, executor, verifier),))
    return issuer, broker, executor, verifier


class Clock:
    def __init__(self, now=1000000000):
        self.value = now

    def monotonic_ns(self):
        return self.value


@contextmanager
def fixture(module, name, value):
    original = getattr(module, name)
    setattr(module, name, value)
    try:
        yield value
    finally:
        setattr(module, name, original)


class ContractTests(unittest.TestCase):
    def test_request_roundtrip_unicode(self):
        r = request()
        self.assertEqual(ActionRequest.from_bytes(r.to_bytes()), r)
        self.assertTrue(r.to_bytes().isascii())
        self.assertEqual(r.fingerprint(), hashlib.sha256(r.to_bytes()).hexdigest())

    def test_request_tuple_is_immutable(self):
        r = request()
        with self.assertRaises(FrozenInstanceError):
            r.action = "OTHER"
        with self.assertRaises(TypeError):
            r.parameters[0] = ("text", "changed")

    def test_input_dict_is_detached(self):
        original = {"text": "before"}
        r = request(parameters=parameters_from_dict(original))
        original["text"] = "after"
        self.assertEqual(r.parameters, (("text", "before"),))

    def test_fingerprint_covers_every_request_field(self):
        r = request()
        variants = (request(2), request(scope_id="3" * 32), request(action="OTHER"),
                    request(version=2), request(parameters=(("text", "different"),)))
        for other in variants:
            with self.subTest(field=other):
                self.assertNotEqual(r.fingerprint(), other.fingerprint())

    def test_ids_and_action_strict(self):
        for field, value in (("request_id", "A" * 32), ("scope_id", "x"), ("action", "echo"),
                             ("action", "*"), ("action", "A" * 65), ("request_id", 1)):
            with self.subTest(field=field, value=value), self.assertRaises(ActionContractError):
                request(**{field: value})

    def test_version_no_boolean_or_float(self):
        for value in (True, 1.0, 0, -1, 65536, "1"):
            with self.subTest(value=value), self.assertRaises(ActionContractError):
                request(version=value)

    def test_parameter_shapes(self):
        for value in ({}, [], [["text", "x"]], (("text", []),), (("text", {}),),
                      (("text", b"x"),), (("text", 1.5),), (("text", object()),)):
            with self.subTest(value=value), self.assertRaises(ActionContractError):
                request(parameters=value)

    def test_parameter_order_duplicates(self):
        for value in ((("z", 1), ("a", 2)), (("x", 1), ("x", 2))):
            with self.subTest(value=value), self.assertRaises(ActionContractError):
                request(parameters=value)

    def test_parameter_bounds(self):
        for value in ("x" * 4097, "\x00", "\ud800", 2 ** 63, -(2 ** 63) - 1):
            with self.subTest(value=repr(value)[:24]), self.assertRaises(ActionContractError):
                request(parameters=(("text", value),))
        with self.assertRaises(ActionContractError):
            request(parameters=tuple((f"p{i:02d}", 1) for i in range(33)))

    def test_integer_edges(self):
        r = request(parameters=(("a", -(2 ** 63)), ("b", 2 ** 63 - 1)))
        self.assertEqual(ActionRequest.from_bytes(r.to_bytes()), r)

    def test_bounded_overall_request(self):
        with self.assertRaises(ActionContractError):
            request(parameters=tuple((f"p{i:02d}", "x" * 4096) for i in range(10)))

    def test_json_wrong_kind_or_extra_key(self):
        for field, value in (("schema", "OTHER"), ("authorized", True), ("approved", True)):
            d = request().document()
            d[field] = value
            with self.subTest(field=field), self.assertRaises(ActionContractError):
                ActionRequest.from_bytes(canonical(d))

    def test_json_missing_fields(self):
        for field in request().document():
            d = request().document()
            del d[field]
            with self.subTest(field=field), self.assertRaises(ActionContractError):
                ActionRequest.from_bytes(canonical(d))

    def test_json_duplicates_and_noncanonical(self):
        raw = request().to_bytes()
        for candidate in (raw + b"\n", b" " + raw, raw.replace(b'"action":"ECHO"', b'"action":"ECHO","action":"ECHO"'),
                          raw.replace(b'"version":1', b'"version":1.0')):
            with self.subTest(candidate=candidate[:50]), self.assertRaises(ActionContractError):
                ActionRequest.from_bytes(candidate)

    def test_json_nonfinite_and_large_integer(self):
        for token in (b"NaN", b"Infinity", b"-Infinity", b"9" * 1000):
            with self.subTest(token=token[:10]), self.assertRaises(ActionContractError):
                ActionRequest.from_bytes(request().to_bytes().replace(b'"version":1', b'"version":' + token))

    def test_json_depth_size_and_nonbytes(self):
        for value in (b"[" * 1000 + b"]" * 1000, b" " * 32769, b"", "{}", bytearray(b"{}"), b"{}", b"null"):
            with self.subTest(value=str(value)[:30]), self.assertRaises(ActionContractError):
                ActionRequest.from_bytes(value)

    def test_brackets_inside_string_are_not_depth(self):
        r = request(parameters=(("text", '"\\[[[[{{{{'),))
        self.assertEqual(ActionRequest.from_bytes(r.to_bytes()), r)

    def test_request_subclass_rejected(self):
        class Other(ActionRequest):
            pass
        with self.assertRaises(ActionContractError):
            Other("1" * 32, "2" * 32, "ECHO", 1)

    def test_spec_fingerprint_covers_effect_and_policy(self):
        s = spec()
        for field, value in (("risk", ActionRiskClass.DESTRUCTIVE), ("effect", ActionEffectClass.PROCESS),
                             ("executor_id", "other"), ("policy_revision", "v2"), ("max_grant_ms", 9999),
                             ("max_execution_ms", 999), ("version", 2), ("action", "OTHER"),
                             ("parameters", (ParameterRule("text", "string", max_bytes=10),))):
            with self.subTest(field=field):
                self.assertNotEqual(s.fingerprint(), replace(s, **{field: value}).fingerprint())

    def test_spec_invalid_types(self):
        for field, value in (("risk", "READ_ONLY"), ("effect", "MEMORY"), ("parameters", []),
                             ("max_grant_ms", True), ("max_execution_ms", 0), ("max_grant_ms", 60001),
                             ("executor_id", "*"), ("policy_revision", "")):
            with self.subTest(field=field), self.assertRaises(ActionContractError):
                spec(**{field: value})

    def test_spec_duplicate_and_unsorted_rules(self):
        for rows in ((ParameterRule("x", "string"),) * 2,
                     (ParameterRule("z", "string"), ParameterRule("a", "string"))):
            with self.subTest(rows=rows), self.assertRaises(ActionContractError):
                spec(parameters=rows)

    def test_rules_types_and_caps(self):
        for kind, bad in (("integer", True), ("boolean", 1), ("null", ""), ("string", 1)):
            with self.subTest(kind=kind), self.assertRaises(ActionContractError):
                spec(parameters=(ParameterRule("text", kind),)).check_request(request(parameters=(("text", bad),)))
        for value in (-1, 11):
            with self.subTest(value=value), self.assertRaises(ActionContractError):
                ParameterRule("n", "integer", minimum=0, maximum=10).check(value)

    def test_rule_invalid_schema(self):
        for values in ({"kind": "any"}, {"required": 1}, {"maximum": -5, "minimum": 0}, {"max_bytes": 4097}):
            with self.subTest(values=values), self.assertRaises(ActionContractError):
                ParameterRule(**dict({"name": "x", "kind": "string"}, **values))

    def test_unknown_and_missing_parameters(self):
        for rows in ((), (("approved", True), ("text", "x"))):
            with self.subTest(rows=rows), self.assertRaises(ActionContractError):
                spec().check_request(request(parameters=rows))

    def test_optional_parameters_no_hidden_default(self):
        s = spec(parameters=(ParameterRule("text", "string", required=False),))
        r = request(parameters=())
        s.check_request(r)
        self.assertEqual(r.parameters, ())

    def test_output_contract_invalid(self):
        for status, rows in (("SUCCEEDED", ()), (ExecutorStatus.SUCCEEDED, (("x", []),))):
            with self.subTest(status=status), self.assertRaises(ActionContractError):
                ExecutorOutcome(status, rows)

    def test_result_cannot_claim_unverified_success(self):
        with self.assertRaises(ActionContractError):
            ActionResult(ActionStatus.SUCCEEDED, "fake")
        with self.assertRaises(ActionContractError):
            ActionResult(ActionStatus.DENIED, "fake", effect=EffectState.VERIFIED)


class RegistryTests(unittest.TestCase):
    def test_empty_default_denies_data(self):
        broker = ActionBroker()
        for token in (None, True, {"approved": True}, b'{"authorized":true}', "permit"):
            with self.subTest(token=token):
                self.assertIs(broker.execute(request(), token).status, ActionStatus.DENIED)

    def test_empty_composition_cannot_issue(self):
        a, b = compose_action_boundary()
        with self.assertRaises(ActionAuthorityError):
            a.issue(request(), ttl_ms=100)
        self.assertIs(b.execute(request()).status, ActionStatus.DENIED)

    def test_registry_input_type(self):
        for rows in ([], {}, (object(),)):
            with self.subTest(rows=rows), self.assertRaises(ActionContractError):
                compose_action_boundary(rows)

    def test_missing_executor_or_verifier(self):
        s = spec()
        for e, v in ((object(), MemoryVerifier(s)), (MemoryExecutor(), object())):
            with self.subTest(e=e, v=v), self.assertRaises(ActionContractError):
                compose_action_boundary((ExecutorRegistration(s, e, v),))

    def test_duplicate_action_denied(self):
        s = spec()
        r = ExecutorRegistration(s, MemoryExecutor(), MemoryVerifier(s))
        with self.assertRaises(ActionContractError):
            compose_action_boundary((r, r))

    def test_executor_id_collision_denied(self):
        s1, s2 = spec(), spec(action="OTHER")
        with self.assertRaises(ActionContractError):
            compose_action_boundary((ExecutorRegistration(s1, MemoryExecutor(), MemoryVerifier(s1)),
                                     ExecutorRegistration(s2, MemoryExecutor(), MemoryVerifier(s2))))

    def test_bound_methods_captured_not_dynamically_replaced(self):
        a, b, e, v = domain()
        r = request()
        g = a.issue(r, ttl_ms=1000)
        e.execute = lambda *args, **kwargs: self.fail("replacement used")
        v.verify = lambda *args, **kwargs: self.fail("replacement used")
        self.assertIs(b.execute(r, g).status, ActionStatus.SUCCEEDED)
        self.assertEqual(e.calls, 1)

    def test_broker_has_no_issuance_or_registration_api(self):
        broker = ActionBroker()
        for name in ("issue", "approve", "authorize", "register", "replace", "issuer"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(broker, name))

    def test_consumer_domain_exposes_no_issue_method(self):
        a, b, _, _ = domain()
        self.assertFalse(hasattr(b._domain, "issue"))
        self.assertTrue(callable(a.issue))

    def test_composition_does_not_execute_callbacks(self):
        a, b, e, v = domain()
        self.assertEqual((e.calls, v.calls), (0, 0))
        a.issue(request(), ttl_ms=1000)
        self.assertEqual((e.calls, v.calls), (0, 0))


class GrantTests(unittest.TestCase):
    def test_success_and_replay(self):
        a, b, e, v = domain()
        r = request()
        g = a.issue(r, ttl_ms=1000)
        self.assertIs(b.execute(r, g).status, ActionStatus.SUCCEEDED)
        self.assertIs(b.execute(r, g).status, ActionStatus.DENIED)
        self.assertEqual((e.calls, v.calls), (1, 1))

    def test_request_reconstructed_with_real_token(self):
        a, b, e, v = domain()
        r = request()
        g = a.issue(r, ttl_ms=1000)
        result = b.execute(ActionRequest.from_bytes(r.to_bytes()), g)
        self.assertIs(result.status, ActionStatus.SUCCEEDED)

    def test_constructor_subclass_copy_and_pickle_forbidden(self):
        a, b, _, _ = domain()
        g = a.issue(request(), ttl_ms=1000)
        for obj in (g, a, b):
            for operation in (copy.copy, copy.deepcopy, pickle.dumps):
                with self.subTest(obj=type(obj).__name__, operation=operation.__name__), self.assertRaises(TypeError):
                    operation(obj)
        for cls in (ActionGrant, ActionAuthority, ActionBroker):
            with self.subTest(cls=cls), self.assertRaises(TypeError):
                type("Derived", (cls,), {})
        for cls in (ActionGrant, ActionAuthority):
            with self.subTest(cls=cls), self.assertRaises(TypeError):
                cls()

    def test_grant_has_no_serializable_state(self):
        a, _, _, _ = domain()
        g = a.issue(request(), ttl_ms=1000)
        self.assertFalse(hasattr(g, "__dict__"))
        with self.assertRaises(AttributeError):
            g.approved = True

    def test_forged_object_not_issued(self):
        a, b, e, _ = domain()
        forged = object.__new__(ActionGrant)
        self.assertIs(b.execute(request(), forged).status, ActionStatus.DENIED)
        self.assertEqual(e.calls, 0)

    def test_fake_token_never_calls_user_hash_or_eq(self):
        class Fake:
            def __hash__(self):
                raise AssertionError("untrusted hash")
            def __eq__(self, other):
                raise AssertionError("untrusted equality")
        self.assertEqual(ActionBroker().execute(request(), Fake()).code, "grant_type")

    def test_wrong_request_consumes(self):
        for change in ({"request_id": "3" * 32}, {"scope_id": "3" * 32},
                       {"parameters": (("text", "wrong"),)}, {"action": "OTHER"}, {"version": 2}):
            with self.subTest(change=change):
                a, b, e, _ = domain()
                r = request()
                g = a.issue(r, ttl_ms=1000)
                self.assertIs(b.execute(replace(r, **change), g).status, ActionStatus.DENIED)
                self.assertIs(b.execute(r, g).status, ActionStatus.DENIED)
                self.assertEqual(e.calls, 0)

    def test_invalid_request_consumes(self):
        for value in ({"approved": True}, None, object.__new__(ActionRequest)):
            with self.subTest(value_type=type(value).__name__):
                a, b, e, _ = domain()
                r = request()
                g = a.issue(r, ttl_ms=1000)
                self.assertIs(b.execute(value, g).status, ActionStatus.DENIED)
                self.assertIs(b.execute(r, g).status, ActionStatus.DENIED)
                self.assertEqual(e.calls, 0)

    def test_foreign_broker_cannot_consume_origin_grant(self):
        a, b, e, _ = domain()
        _, foreign, foreign_e, _ = domain()
        r = request()
        g = a.issue(r, ttl_ms=1000)
        self.assertIs(foreign.execute(r, g).status, ActionStatus.DENIED)
        self.assertEqual(foreign_e.calls, 0)
        self.assertIs(b.execute(r, g).status, ActionStatus.SUCCEEDED)
        self.assertEqual(e.calls, 1)

    def test_second_registered_executor_never_receives_wrong_grant(self):
        s1, s2 = spec(), spec(action="OTHER", executor_id="memory.other")
        e1, e2 = MemoryExecutor(), MemoryExecutor()
        a, b = compose_action_boundary((ExecutorRegistration(s1, e1, MemoryVerifier(s1)),
                                       ExecutorRegistration(s2, e2, MemoryVerifier(s2))))
        g = a.issue(request(), ttl_ms=1000)
        self.assertIs(b.execute(request(action="OTHER"), g).status, ActionStatus.DENIED)
        self.assertEqual((e1.calls, e2.calls), (0, 0))

    def test_expiry_exact_boundary(self):
        with fixture(authority_module, "time", Clock()) as clock:
            a, b, e, _ = domain()
            r = request()
            g = a.issue(r, ttl_ms=1)
            clock.value += 1000000
            self.assertEqual(b.execute(r, g).code, "grant_expired")
            self.assertEqual(e.calls, 0)
            self.assertEqual(b.execute(r, g).code, "grant_unavailable")

    def test_invalid_ttl(self):
        a, _, _, _ = domain()
        for value in (True, 0, -1, 1.0, 10001, None):
            with self.subTest(value=value), self.assertRaises(ActionAuthorityError):
                a.issue(request(), ttl_ms=value)

    def test_unknown_action_cannot_issue(self):
        a, _, _, _ = domain()
        for r in (request(action="OTHER"), request(version=2)):
            with self.subTest(r=r), self.assertRaises(ActionAuthorityError):
                a.issue(r, ttl_ms=1)

    def test_revoke_then_replay(self):
        a, b, e, _ = domain()
        r = request()
        g = a.issue(r, ttl_ms=1000)
        self.assertTrue(a.revoke(g))
        self.assertFalse(a.revoke(g))
        self.assertIs(b.execute(r, g).status, ActionStatus.DENIED)
        self.assertEqual(e.calls, 0)

    def test_close_is_idempotent_and_stops_future_work(self):
        a, b, e, _ = domain()
        r = request()
        g = a.issue(r, ttl_ms=1000)
        a.close()
        a.close()
        self.assertIs(b.execute(r, g).status, ActionStatus.DENIED)
        with self.assertRaises(ActionAuthorityError):
            a.issue(request(2), ttl_ms=1)
        self.assertEqual(e.calls, 0)

    def test_issued_id_never_reissued_in_domain(self):
        a, b, _, _ = domain()
        r = request()
        g = a.issue(r, ttl_ms=1000)
        a.revoke(g)
        for other in (r, replace(r, parameters=(("text", "changed"),))):
            with self.subTest(other=other), self.assertRaises(ActionAuthorityError):
                a.issue(other, ttl_ms=1)

    def test_issued_id_after_success(self):
        a, b, _, _ = domain()
        r = request()
        self.assertIs(b.execute(r, a.issue(r, ttl_ms=1000)).status, ActionStatus.SUCCEEDED)
        with self.assertRaises(ActionAuthorityError):
            a.issue(r, ttl_ms=1000)

    def test_same_id_different_scope_is_distinct_request(self):
        a, b, e, _ = domain()
        for r in (request(), request(scope_id="3" * 32)):
            self.assertIs(b.execute(r, a.issue(r, ttl_ms=1000)).status, ActionStatus.SUCCEEDED)
        self.assertEqual(e.calls, 2)

    def test_pending_capacity_then_revoke(self):
        with fixture(authority_module, "time", Clock()):
            a, _, _, _ = domain()
            grants = [a.issue(request(i + 1), ttl_ms=1000) for i in range(128)]
            with self.assertRaisesRegex(ActionAuthorityError, "pending_capacity"):
                a.issue(request(129), ttl_ms=1000)
            a.revoke(grants[0])
            self.assertIs(type(a.issue(request(129), ttl_ms=1000)), ActionGrant)

    def test_pending_expiry_does_not_remove_tombstone(self):
        with fixture(authority_module, "time", Clock()) as clock:
            a, _, _, _ = domain()
            grants = [a.issue(request(i + 1), ttl_ms=1) for i in range(128)]
            clock.value += 1000000
            self.assertIs(type(a.issue(request(129), ttl_ms=1)), ActionGrant)
            with self.assertRaisesRegex(ActionAuthorityError, "request_already_issued"):
                a.issue(request(1), ttl_ms=1)
            self.assertEqual(len(grants), 128)

    def test_gc_grant_frees_pending_not_request_id(self):
        a, _, _, _ = domain()
        a.issue(request(), ttl_ms=1000)
        gc.collect()
        self.assertEqual(len(a._domain.grants), 0)
        with self.assertRaises(ActionAuthorityError):
            a.issue(request(), ttl_ms=1)

    def test_domain_capacity_fail_closed(self):
        with fixture(authority_module, "MAX_ISSUED_REQUESTS", 2):
            a, _, _, _ = domain()
            a.issue(request(1), ttl_ms=1)
            a.issue(request(2), ttl_ms=1)
            with self.assertRaisesRegex(ActionAuthorityError, "domain_capacity"):
                a.issue(request(3), ttl_ms=1)

    def test_pid_change_refuses_before_inherited_lock(self):
        a, b, e, _ = domain()
        r = request()
        g = a.issue(r, ttl_ms=1000)
        a._domain.lock.acquire()
        try:
            with fixture(authority_module, "os", SimpleNamespace(getpid=lambda: a._domain.pid + 1)):
                self.assertEqual(b.execute(r, g).code, "foreign_process")
                with self.assertRaises(ActionAuthorityError):
                    a.issue(request(2), ttl_ms=1)
                with self.assertRaises(ActionAuthorityError):
                    a.revoke(g)
        finally:
            a._domain.lock.release()
        self.assertEqual(e.calls, 0)

    def test_clock_rollback_consumes(self):
        with fixture(authority_module, "time", Clock()) as clock:
            a, b, e, _ = domain()
            r = request()
            g = a.issue(r, ttl_ms=1000)
            clock.value -= 1
            self.assertEqual(b.execute(r, g).code, "invalid_clock")
            self.assertEqual(e.calls, 0)
            self.assertEqual(b.execute(r, g).code, "grant_unavailable")

    def test_clock_boolean_refused(self):
        with fixture(authority_module, "time", Clock(True)):
            a, _, _, _ = domain()
            with self.assertRaises(ActionAuthorityError):
                a.issue(request(), ttl_ms=1)

    def test_concurrent_submit_exactly_one_dispatch(self):
        with fixture(authority_module, "time", Clock()):
            a, b, e, _ = domain()
            r = request()
            g = a.issue(r, ttl_ms=1000)
            barrier = threading.Barrier(8)
            results = []
            def run():
                barrier.wait(timeout=5)
                results.append(b.execute(r, g))
            threads = [threading.Thread(target=run) for _ in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)
            self.assertTrue(all(not t.is_alive() for t in threads))
            self.assertEqual(len(results), 8)
            self.assertEqual(sum(x.status is ActionStatus.SUCCEEDED for x in results), 1)
            self.assertEqual(e.calls, 1)

    def test_callback_reentry_not_locked_and_no_replay(self):
        a, b, e, _ = domain()
        r = request()
        g = a.issue(r, ttl_ms=1000)
        def hook(value):
            self.assertFalse(a.revoke(g))
            self.assertIs(b.execute(value, g).status, ActionStatus.DENIED)
            return ExecutorOutcome(ExecutorStatus.SUCCEEDED, value.parameters)
        e.hook = hook
        self.assertIs(b.execute(r, g).status, ActionStatus.SUCCEEDED)
        self.assertEqual(e.calls, 1)


class OutcomeTests(unittest.TestCase):
    def test_verification_rejects_wrong_output(self):
        a, b, e, v = domain()
        e.hook = lambda r: ExecutorOutcome(ExecutorStatus.SUCCEEDED, (("text", "wrong"),))
        r = request()
        result = b.execute(r, a.issue(r, ttl_ms=1000))
        self.assertIs(result.status, ActionStatus.UNKNOWN)
        self.assertIs(result.verification, VerificationStatus.REJECTED)
        self.assertIs(result.effect, EffectState.MAY_HAVE_OCCURRED)

    def test_executor_exception_unknown_no_retry_or_secret(self):
        a, b, e, _ = domain()
        def fail(r):
            raise RuntimeError("DO_NOT_LEAK_SECRET")
        e.hook = fail
        r = request()
        g = a.issue(r, ttl_ms=1000)
        result = b.execute(r, g)
        self.assertIs(result.status, ActionStatus.UNKNOWN)
        self.assertIs(result.effect, EffectState.MAY_HAVE_OCCURRED)
        self.assertNotIn("DO_NOT_LEAK_SECRET", str(result.document()))
        self.assertIs(b.execute(r, g).status, ActionStatus.DENIED)
        self.assertEqual(e.calls, 1)

    def test_reported_failure_not_no_effect(self):
        a, b, e, v = domain()
        e.hook = lambda r: ExecutorOutcome(ExecutorStatus.FAILED)
        r = request()
        result = b.execute(r, a.issue(r, ttl_ms=1000))
        self.assertIs(result.status, ActionStatus.FAILED)
        self.assertIs(result.effect, EffectState.MAY_HAVE_OCCURRED)
        self.assertEqual(v.calls, 0)

    def test_invalid_executor_reply(self):
        for value in (None, True, {"ok": True}, object.__new__(ExecutorOutcome)):
            with self.subTest(value_type=type(value).__name__):
                a, b, e, v = domain()
                e.hook = lambda r: value
                r = request()
                self.assertIs(b.execute(r, a.issue(r, ttl_ms=1000)).status, ActionStatus.UNKNOWN)
                self.assertEqual(v.calls, 0)

    def test_verifier_exception_unknown(self):
        a, b, _, v = domain()
        def fail(r, o):
            raise RuntimeError("SECRET")
        v.hook = fail
        r = request()
        result = b.execute(r, a.issue(r, ttl_ms=1000))
        self.assertEqual(result.code, "verifier_exception")
        self.assertNotIn("SECRET", str(result.document()))

    def test_invalid_verifier_reply(self):
        for value in (True, {}, None, object.__new__(ActionVerification)):
            with self.subTest(value_type=type(value).__name__):
                a, b, _, v = domain()
                v.hook = lambda r, o: value
                r = request()
                self.assertEqual(b.execute(r, a.issue(r, ttl_ms=1000)).code, "verification_invalid")

    def test_verification_binds_request_policy_and_output(self):
        for field in ("request_fingerprint", "policy_fingerprint", "outcome_fingerprint"):
            with self.subTest(field=field):
                a, b, _, v = domain()
                v.hook = lambda r, o: ActionVerification(**dict(
                    request_fingerprint="0" * 64 if field == "request_fingerprint" else r.fingerprint(),
                    policy_fingerprint="0" * 64 if field == "policy_fingerprint" else spec().fingerprint(),
                    outcome_fingerprint="0" * 64 if field == "outcome_fingerprint" else o.fingerprint(),
                    status=VerificationStatus.VERIFIED))
                r = request()
                self.assertEqual(b.execute(r, a.issue(r, ttl_ms=1000)).code, "verification_invalid")

    def test_not_run_verification_not_success(self):
        a, b, _, v = domain()
        v.hook = lambda r, o: ActionVerification(r.fingerprint(), spec().fingerprint(), o.fingerprint(), VerificationStatus.NOT_RUN)
        r = request()
        self.assertIs(b.execute(r, a.issue(r, ttl_ms=1000)).status, ActionStatus.UNKNOWN)

    def test_executor_deadline_is_observed_not_hard_timeout(self):
        with fixture(authority_module, "time", Clock()) as clock:
            a, b, e, v = domain(spec(max_execution_ms=10))
            def slow(r):
                clock.value += 10000000
                return ExecutorOutcome(ExecutorStatus.SUCCEEDED, r.parameters)
            e.hook = slow
            r = request()
            result = b.execute(r, a.issue(r, ttl_ms=1000))
            self.assertEqual(result.code, "execution_deadline")
            self.assertEqual(v.calls, 0)
            self.assertEqual(e.deadlines, [1010000000])

    def test_execution_deadline_capped_by_grant(self):
        with fixture(authority_module, "time", Clock()):
            a, b, e, _ = domain()
            r = request()
            self.assertIs(b.execute(r, a.issue(r, ttl_ms=1)).status, ActionStatus.SUCCEEDED)
            self.assertEqual(e.deadlines, [1001000000])

    def test_verification_deadline(self):
        with fixture(authority_module, "time", Clock()) as clock:
            a, b, _, v = domain()
            def slow(r, o):
                clock.value += 1000000000
                return ActionVerification(r.fingerprint(), spec().fingerprint(), o.fingerprint(), VerificationStatus.VERIFIED)
            v.hook = slow
            r = request()
            self.assertEqual(b.execute(r, a.issue(r, ttl_ms=1000)).code, "verification_deadline")

    def test_baseexception_propagates_grant_consumed(self):
        for exception in (KeyboardInterrupt, SystemExit):
            with self.subTest(exception=exception):
                a, b, e, _ = domain()
                def stop(r):
                    raise exception()
                e.hook = stop
                r = request()
                g = a.issue(r, ttl_ms=1000)
                with self.assertRaises(exception):
                    b.execute(r, g)
                self.assertIs(b.execute(r, g).status, ActionStatus.DENIED)
                self.assertEqual(e.calls, 1)

    def test_result_exports_no_request_parameters_on_failure(self):
        a, b, e, _ = domain()
        e.hook = lambda r: None
        r = request(parameters=(("text", "PRIVATE_INPUT"),))
        result = b.execute(r, a.issue(r, ttl_ms=1000))
        self.assertNotIn("PRIVATE_INPUT", str(result.document()))


class AdditionalRegressionTests(unittest.TestCase):
    def test_future_host_category_is_only_spec_data_not_default_execution(self):
        # No host implementation is used. A spec/registry descriptor alone is not a grant.
        s = spec(effect=ActionEffectClass.FILESYSTEM, risk=ActionRiskClass.DESTRUCTIVE)
        e = MemoryExecutor()
        _, b = compose_action_boundary((ExecutorRegistration(s, e, MemoryVerifier(s)),))
        self.assertIs(b.execute(request(), s.document()).status, ActionStatus.DENIED)
        self.assertEqual(e.calls, 0)

    def test_request_unknown_parameter_consumes_owned_grant(self):
        a, b, e, _ = domain()
        r = request()
        g = a.issue(r, ttl_ms=1000)
        wrong = replace(r, parameters=(("approved", True), ("text", "пример")))
        self.assertIs(b.execute(wrong, g).status, ActionStatus.DENIED)
        self.assertIs(b.execute(r, g).status, ActionStatus.DENIED)
        self.assertEqual(e.calls, 0)

    def test_foreign_issuer_cannot_revoke(self):
        a, b, e, _ = domain()
        other, _, _, _ = domain()
        r = request()
        g = a.issue(r, ttl_ms=1000)
        self.assertFalse(other.revoke(g))
        self.assertIs(b.execute(r, g).status, ActionStatus.SUCCEEDED)

    def test_close_after_claim_does_not_claim_to_undo_effect(self):
        a, b, e, _ = domain()
        def close_in_callback(r):
            a.close()
            return ExecutorOutcome(ExecutorStatus.SUCCEEDED, r.parameters)
        e.hook = close_in_callback
        r = request()
        self.assertIs(b.execute(r, a.issue(r, ttl_ms=1000)).status, ActionStatus.SUCCEEDED)
        self.assertEqual(e.calls, 1)
        with self.assertRaises(ActionAuthorityError):
            a.issue(request(2), ttl_ms=1)

    def test_second_clock_check_before_dispatch(self):
        # Issue at t, claim at t, deadline reached before dispatch: no callback.
        readings = iter((1000000000, 1000000000, 1001000000))
        with fixture(authority_module, "time", SimpleNamespace(monotonic_ns=lambda: next(readings))):
            a, b, e, _ = domain()
            r = request()
            g = a.issue(r, ttl_ms=1)
            self.assertEqual(b.execute(r, g).code, "grant_expired")
            self.assertEqual(e.calls, 0)

    def test_clock_failure_after_dispatch_never_success(self):
        with fixture(authority_module, "time", Clock()) as clock:
            a, b, e, _ = domain()
            def corrupt_clock(r):
                clock.value = -1
                return ExecutorOutcome(ExecutorStatus.SUCCEEDED, r.parameters)
            e.hook = corrupt_clock
            r = request()
            result = b.execute(r, a.issue(r, ttl_ms=1000))
            self.assertIs(result.status, ActionStatus.UNKNOWN)
            self.assertIs(result.effect, EffectState.MAY_HAVE_OCCURRED)

    def test_concurrent_issuance_same_request_one_grant(self):
        with fixture(authority_module, "time", Clock()):
            a, b, e, _ = domain()
            r = request()
            barrier = threading.Barrier(8)
            grants, refused = [], []
            def issue():
                barrier.wait(timeout=5)
                try:
                    grants.append(a.issue(r, ttl_ms=1000))
                except ActionAuthorityError as exc:
                    refused.append(str(exc))
            threads = [threading.Thread(target=issue) for _ in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)
            self.assertTrue(all(not t.is_alive() for t in threads))
            self.assertEqual(len(grants), 1)
            self.assertEqual(refused, ["request_already_issued"] * 7)
            self.assertIs(b.execute(r, grants[0]).status, ActionStatus.SUCCEEDED)
            self.assertEqual(e.calls, 1)

    def test_policy_drift_detected_without_claiming_python_sandbox(self):
        s = spec()
        a, b, e, _ = domain(s)
        r = request()
        g = a.issue(r, ttl_ms=1000)
        # Deliberate internal mutation to exercise drift guard, not an OS-security claim.
        object.__setattr__(s, "policy_revision", "v2")
        self.assertEqual(b.execute(r, g).code, "policy_changed")
        self.assertEqual(e.calls, 0)
        self.assertIs(b.execute(r, g).status, ActionStatus.DENIED)

    def test_mutated_outcome_after_verifier_cannot_be_success(self):
        a, b, _, v = domain()
        def mutate(r, o):
            evidence = ActionVerification(r.fingerprint(), spec().fingerprint(), o.fingerprint(), VerificationStatus.VERIFIED)
            object.__setattr__(o, "output", (("text", "changed"),))
            return evidence
        v.hook = mutate
        r = request()
        self.assertEqual(b.execute(r, a.issue(r, ttl_ms=1000)).code, "verification_invalid")

    def test_failed_and_unknown_cannot_claim_verified(self):
        for state in (ActionStatus.FAILED, ActionStatus.UNKNOWN):
            with self.subTest(state=state), self.assertRaises(ActionContractError):
                ActionResult(state, "bad", "0" * 64, "1" * 64,
                             VerificationStatus.VERIFIED, EffectState.MAY_HAVE_OCCURRED)

    def test_registry_cannot_rebind_by_replacing_descriptor(self):
        s = spec()
        e1, e2 = MemoryExecutor(), MemoryExecutor()
        registration = ExecutorRegistration(s, e1, MemoryVerifier(s))
        a, b = compose_action_boundary((registration,))
        replacement = replace(registration, executor=e2)
        r = request()
        self.assertIs(b.execute(r, a.issue(r, ttl_ms=1000)).status, ActionStatus.SUCCEEDED)
        self.assertEqual((e1.calls, e2.calls), (1, 0))
        self.assertIs(replacement.executor, e2)

    def test_separate_domain_is_not_durable_replay_protection(self):
        # Explicitly document the limit: same logical ID can be authorised in a NEW domain.
        r = request()
        for _ in range(2):
            a, b, e, _ = domain()
            self.assertIs(b.execute(r, a.issue(r, ttl_ms=1000)).status, ActionStatus.SUCCEEDED)
            self.assertEqual(e.calls, 1)


class SourceTests(unittest.TestCase):
    def test_new_module_import_allowlist(self):
        allowed = {
            NEW_MODULES[0]: {"__future__", "dataclasses", "enum", "hashlib", "json", "re"},
            NEW_MODULES[1]: {"__future__", "dataclasses", "os", "threading", "time", "weakref", "modules.action_contract"},
            NEW_MODULES[2]: {"__future__", "dataclasses", "typing", "modules.action_contract", "modules.action_authority"},
        }
        for path, imports in allowed.items():
            tree = ast.parse((PROJECT_ROOT / path).read_text(encoding="utf-8"))
            actual = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    actual.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    self.assertEqual(node.level, 0)
                    actual.add(node.module)
            with self.subTest(path=path):
                self.assertEqual(actual, imports)

    def test_new_module_no_effectful_calls(self):
        forbidden = {"open", "exec", "eval", "compile", "__import__"}
        constrained = {"os": {"getpid"}, "time": {"monotonic_ns"}, "threading": {"Lock"}, "weakref": {"WeakKeyDictionary"}}
        for path in NEW_MODULES:
            tree = ast.parse((PROJECT_ROOT / path).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        self.assertNotIn(node.func.id, forbidden)
                    elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                        module = node.func.value.id
                        if module in constrained:
                            self.assertIn(node.func.attr, constrained[module])

    def test_production_runtime_wiring_is_exact_hwa02b1_timer_bridge(self):
        names = {path[:-3].replace("/", ".") for path in NEW_MODULES}
        files = [PROJECT_ROOT / "main.py", *sorted((PROJECT_ROOT / "modules").rglob("*.py"))]
        wiring = {}
        for path in files:
            relative = path.relative_to(PROJECT_ROOT).as_posix()
            if relative in NEW_MODULES:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imported.add(node.module or "")
                    if node.module == "modules":
                        imported.update("modules." + alias.name for alias in node.names)
            used = sorted(imported & names)
            if used:
                wiring[relative] = used
        self.assertEqual(wiring, {
            "modules/timer_action_runtime.py": [
                "modules.action_authority",
                "modules.action_broker",
                "modules.action_contract",
            ],
        })
        main_tree = ast.parse((PROJECT_ROOT / "main.py").read_text(encoding="utf-8-sig"))
        main_imports = [node.module for node in ast.walk(main_tree)
                        if isinstance(node, ast.ImportFrom)]
        self.assertEqual(main_imports.count("modules.timer_action_runtime"), 1)

    def test_no_static_modules_native_import(self):
        for path in (PROJECT_ROOT / "modules").rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                self.assertFalse(any(n == "native" or n.startswith("native.") for n in names), str(path))

    def test_pipeline_source_only_wiring(self):
        tree = ast.parse((PROJECT_ROOT / "tools/pipeline.py").read_text(encoding="utf-8-sig"))
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "available_flows")
        expr = fn.body[0].value
        flows = {k.value: v.elts for k, v in zip(expr.keys, expr.values)}
        marker = "tools/eval_action_execution_boundary.py"
        occurrences = {}
        for key, nodes in flows.items():
            count = sum(any(isinstance(x, ast.Constant) and x.value == marker for x in ast.walk(n)) for n in nodes)
            if count:
                occurrences[key] = count
        self.assertEqual(occurrences, {"check": 1, "action_execution_boundary": 1})
        self.assertEqual(len(flows["action_execution_boundary"]), 1)
        text = ast.unparse(flows["action_execution_boundary"][0])
        for flag in ("-I", "-S", "-B"):
            self.assertIn(flag, text)


class CountedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.subtests = 0

    def addSubTest(self, test, subtest, err):
        self.subtests += 1
        return super().addSubTest(test, subtest, err)


def main() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    discovered = suite.countTestCases()
    expected = EXPECTED_TESTS
    counters = {"filesystem_mutation": 0, "subprocess": 0, "network": 0, "native_load": 0}
    measured = True

    def audit(event, args):
        if not measured:
            return
        category = None
        if event == "open":
            mode, flags = args[1], args[2]
            if (type(mode) is str and any(x in mode for x in "wax+")) or (type(flags) is int and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
                category = "filesystem_mutation"
        elif event in {"os.remove", "os.rename", "os.mkdir", "os.rmdir", "os.chmod", "os.link", "os.symlink", "os.truncate", "os.utime", "os.chown"}:
            category = "filesystem_mutation"
        elif event in {"subprocess.Popen", "os.system", "os.fork", "os.posix_spawn"}:
            category = "subprocess"
        elif event.startswith("socket."):
            category = "network"
        elif event.startswith("ctypes.dlopen"):
            category = "native_load"
        if category:
            counters[category] += 1
            raise RuntimeError("HWA02_A_FORBIDDEN_EFFECT:" + category)

    sys.addaudithook(audit)
    try:
        result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2, resultclass=CountedResult).run(suite)
    finally:
        measured = False
    ok = result.wasSuccessful() and result.testsRun == expected and not result.skipped and not any(counters.values())
    summary = {"kind": "HWA02_ACTION_EXECUTION_BOUNDARY_EVAL_V1", "result": "PASS" if ok else "FAIL",
               "tests_run": result.testsRun, "expected_tests": expected, "discovered_tests": discovered, "subtests": result.subtests,
               "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
               "audit_measured_suite": counters, "runtime_wired": True,
               "runtime_wiring_profile": "HWA02B1_TIMER_PAIR_ONLY",
               "runtime_actions": ["SET_TIMER", "CANCEL_TIMER"],
               "native_execution_authorized": False, "host_executor_registered": False,
               "real_cross_process_test": False}
    print("\n=== HWA02-A SUMMARY ===")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
