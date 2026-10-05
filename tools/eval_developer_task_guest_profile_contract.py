from __future__ import annotations

"""Standalone passive-contract regressions; never executes guest profile steps."""

import ast
import copy
import hashlib
import inspect
import json
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from unittest.mock import patch

from modules.developer import developer_task_guest_profile_contract as contract
from modules.developer import developer_task_guest_profile_document as document
from modules.developer import developer_task_guest_profile_policy as policy
from modules.developer.developer_task_contract import developer_task_manifest_fingerprint
from modules.developer.developer_task_validator import validate_developer_task_manifest


def _encoded(data: object) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode() + b"\n"


class GuestProfileContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = contract.canonical_developer_task_guest_profile_document()
        self.profile = contract.parse_developer_task_guest_profile(self.raw)
        self.spec = contract.build_developer_task_guest_check_specification_v2(
            profile_document=self.raw,
        )
        self.data = self.spec.to_dict()

    def assert_rejected(self, data: object, code: str | None = None) -> None:
        result = contract.validate_developer_task_guest_check_specification_v2(
            _encoded(data), profile_document=self.raw,
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.status, policy.GUEST_CONTRACT_REJECTED_STATUS)
        if code:
            self.assertIn(code, result.issue_codes)
        self.assert_no_authority(result.to_dict())

    def assert_no_authority(self, value: dict) -> None:
        for key in (
            "task_validated", "execution_plan_validated", "runtime_authorized",
            "promotion_authorized", "capability_issued", "guest_profile_executed",
            "required_profile_checks_passed", "all_required_checks_passed",
            "ready_to_promote", "legacy_full_check_equivalent",
        ):
            self.assertIs(value[key], False, key)
        self.assertEqual(value["legacy_full_check_status"], "NOT_SATISFIED_BY_GUEST_PROFILE")
        self.assertEqual(value["behavioral_correctness"], "NOT_EVALUATED")

    def test_profile_document_exact_bytes_and_digest(self) -> None:
        self.assertEqual(len(self.raw), 55390)
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(),
                         "94ad59f6812b8ebd74bd7718f5ff37f0fbee85383f9198a2a22e8f527d7caa6b")

    def test_all_101_ordinals_in_reviewed_order(self) -> None:
        self.assertEqual(tuple(x.source_ordinal for x in self.profile.steps),
                         tuple(x for x in range(1, 104) if x not in (31, 93)))
        self.assertEqual(len({x.path for x in self.profile.steps}), 101)

    def test_exclusions_explicit_not_satisfied(self) -> None:
        self.assertEqual(self.profile.excluded_ordinals, (31, 93))
        data = json.loads(self.raw)
        self.assertTrue(all(x["coverage_state"] == "NOT_SATISFIED" for x in data["excluded_steps"]))

    def test_profile_parsing_carries_git_not_physical_pins(self) -> None:
        data = json.loads(self.raw)
        for actual, source in zip(self.profile.steps, data["steps"]):
            self.assertEqual(actual.content_sha256, source["snapshot_entrypoint_identity"]["sha256"])
            self.assertEqual(actual.content_bytes, source["snapshot_entrypoint_identity"]["bytes"])
            self.assertEqual(actual.git_blob_oid, source["git_blob_oid"])
            self.assertEqual(actual.git_mode, "100644")
        self.assertNotEqual(self.profile.steps[0].content_sha256,
                            data["steps"][0]["review_physical_identity"]["sha256"])

    def test_historical_review_base_not_rewritten(self) -> None:
        self.assertEqual(self.profile.review_base_commit,
                         "bb764434a0b1644f2e0d789dae06fccdd8f85c45")
        self.assertEqual(self.profile.review_base_tree,
                         "28e4edb214f28e551c1a364dff3bc52dc214656b")
        self.assertNotIn("base_commit", self.data)
        self.assertNotIn("candidate_tree", self.data)

    def test_profile_validation_no_authority(self) -> None:
        result = contract.validate_developer_task_guest_profile(self.raw)
        self.assertTrue(result.ok)
        self.assertEqual(result.status, policy.GUEST_PROFILE_VALID_STATUS)
        self.assert_no_authority(result.to_dict())
        self.assert_no_authority(self.profile.to_dict())

    def test_profile_rejects_non_bytes(self) -> None:
        for value in (self.raw.decode(), bytearray(self.raw), memoryview(self.raw), None, {}):
            with self.subTest(value_type=type(value).__name__):
                result = contract.validate_developer_task_guest_profile(value)
                self.assertFalse(result.ok)
                self.assertEqual(result.issue_codes, ("profile_bytes_required",))

    def test_profile_rejects_size_changes(self) -> None:
        for raw in (b"", self.raw[:-1], self.raw+b" ", b"\xef\xbb\xbf"+self.raw):
            self.assertEqual(contract.validate_developer_task_guest_profile(raw).issue_codes,
                             ("profile_size_mismatch",))

    def test_profile_rejects_one_byte_change(self) -> None:
        bad = bytes([self.raw[0] ^ 1]) + self.raw[1:]
        self.assertEqual(contract.validate_developer_task_guest_profile(bad).issue_codes,
                         ("profile_digest_mismatch",))

    def test_profile_rejects_semantic_reordering(self) -> None:
        data = json.loads(self.raw)
        data["steps"][0], data["steps"][1] = data["steps"][1], data["steps"][0]
        self.assertFalse(contract.validate_developer_task_guest_profile(_encoded(data)).ok)

    def test_profile_rejects_semantic_hash_replacement(self) -> None:
        data = json.loads(self.raw)
        data["steps"][0]["snapshot_entrypoint_identity"]["sha256"] = "0" * 64
        self.assertFalse(contract.validate_developer_task_guest_profile(_encoded(data)).ok)

    def test_profile_rejects_authority_and_legacy_equivalence(self) -> None:
        for key in ("runtime_authorized", "promotion_authorized"):
            data = json.loads(self.raw); data[key] = True
            self.assertFalse(contract.validate_developer_task_guest_profile(_encoded(data)).ok)
        data = json.loads(self.raw); data["coverage"]["legacy_full_check_equivalent"] = True
        self.assertFalse(contract.validate_developer_task_guest_profile(_encoded(data)).ok)

    def test_profile_is_deeply_immutable(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            self.profile.flow = "check"
        with self.assertRaises(FrozenInstanceError):
            self.profile.steps[0].path = "other.py"
        self.assertIsInstance(self.profile.steps, tuple)
        self.assertIsInstance(self.profile.steps[0].python_args, tuple)
        detached = self.profile.to_dict()
        detached["required_steps"][0]["python_args"].append("--unexpected")
        self.assertNotEqual(detached["required_steps"][0]["python_args"],
                            self.profile.steps[0].to_dict()["python_args"])

    def test_embedded_literal_independent_of_source_eol(self) -> None:
        # Syntax/data inspection only: do not execute reconstructed source.
        text = inspect.getsource(document)
        for source in (text, text.replace("\n", "\r\n")):
            tree = ast.parse(source)
            node = next(x for x in tree.body if isinstance(x, ast.AnnAssign))
            self.assertEqual(ast.literal_eval(node.value), self.raw)
        self.assertFalse(contract.validate_developer_task_guest_profile(
            self.raw.replace(b"\n", b"\r\n")).ok)

    def test_exact_v2_check_sequence(self) -> None:
        self.assertEqual([x.to_dict() for x in self.spec.checks], [
            {"type": "git_diff_check"},
            {"type": "py_compile", "scope": "changed_python_files"},
            {"type": "pipeline", "flow": "check_guest_source_v1",
             "profile_sha256": policy.GUEST_PROFILE_DOCUMENT_SHA256},
        ])

    def test_v2_roundtrip_and_stable_fingerprint(self) -> None:
        raw = contract.canonical_developer_task_guest_check_specification_v2(self.spec)
        rebuilt = contract.parse_developer_task_guest_check_specification_v2(
            raw, profile_document=self.raw)
        self.assertEqual(rebuilt, self.spec)
        self.assertEqual(rebuilt.fingerprint,
                         "d0c5a003e0b791c297be90a09a30c78649d898ba2f0359b868c9cf701ea929a4")
        self.assertTrue(raw.endswith(b"\n"))

    def test_v2_accepts_json_key_order_and_whitespace(self) -> None:
        reordered = dict(reversed(list(self.data.items())))
        raw = json.dumps(reordered, indent=2).encode()
        result = contract.validate_developer_task_guest_check_specification_v2(
            raw, profile_document=self.raw)
        self.assertTrue(result.ok)
        self.assertEqual(result.specification.fingerprint, self.spec.fingerprint)

    def test_v2_result_is_not_task_plan_or_profile_success(self) -> None:
        result = contract.validate_developer_task_guest_check_specification_v2(
            _encoded(self.data), profile_document=self.raw)
        self.assertTrue(result.ok)
        self.assertEqual(result.to_dict()["profile_sha256"], policy.GUEST_PROFILE_DOCUMENT_SHA256)
        self.assert_no_authority(result.to_dict())

    def test_v2_rejects_schema1_unknown_bool_float_string(self) -> None:
        for value in (1, 3, True, False, 2.0, "2", None):
            with self.subTest(schema=value):
                data = copy.deepcopy(self.data); data["schema_version"] = value
                self.assert_rejected(data, "unsupported_check_schema_version")

    def test_v2_rejects_profile_revision_coercion(self) -> None:
        for value in (0, 2, True, 1.0, "1", None):
            data = copy.deepcopy(self.data); data["profile_revision"] = value
            self.assert_rejected(data, "unsupported_profile_revision")

    def test_v2_rejects_each_missing_top_field(self) -> None:
        for key in self.data:
            data = copy.deepcopy(self.data); del data[key]
            self.assert_rejected(data, "check_specification_fields_invalid")

    def test_v2_rejects_extra_and_authority_fields(self) -> None:
        for key in ("runtime_authorized", "promotion_authorized", "base_commit",
                    "patch_sha256", "candidate_tree", "argv", "environment", "task_id"):
            data = copy.deepcopy(self.data); data[key] = True
            self.assert_rejected(data, "check_specification_fields_invalid")

    def test_v2_rejects_contract_id_and_kind(self) -> None:
        for key in ("kind", "check_contract_id"):
            data = copy.deepcopy(self.data); data[key] = "V1"
            self.assert_rejected(data)

    def test_v2_rejects_profile_id_or_digest(self) -> None:
        for key in ("profile_id", "profile_sha256"):
            data = copy.deepcopy(self.data); data[key] = "different"
            self.assert_rejected(data, "check_profile_reference_mismatch")

    def test_v2_rejects_legacy_flow_alias(self) -> None:
        data = copy.deepcopy(self.data); data["checks"][-1]["flow"] = "check"
        self.assert_rejected(data, "check_sequence_mismatch")

    def test_v2_rejects_extra_missing_duplicate_or_reordered_steps(self) -> None:
        for checks in (self.data["checks"][:-1], self.data["checks"]*2,
                       list(reversed(self.data["checks"])), []):
            data = copy.deepcopy(self.data); data["checks"] = checks
            self.assert_rejected(data, "check_sequence_mismatch")

    def test_v2_rejects_malicious_arguments_or_nested_fields(self) -> None:
        for key in ("argv", "shell", "module", "runtime_authorized"):
            data = copy.deepcopy(self.data); data["checks"][-1][key] = "injected"
            self.assert_rejected(data, "check_sequence_mismatch")
        data = copy.deepcopy(self.data); data["checks"][1]["scope"] = "all_files"
        self.assert_rejected(data, "check_sequence_mismatch")

    def test_v2_rejects_pipeline_profile_binding_mismatch(self) -> None:
        data = copy.deepcopy(self.data); data["checks"][-1]["profile_sha256"] = "0"*64
        self.assert_rejected(data, "check_sequence_mismatch")

    def test_v2_rejects_wrong_fingerprint(self) -> None:
        for value in ("0"*64, self.spec.fingerprint.upper(), 1, None, "\ud800"):
            data = copy.deepcopy(self.data); data["contract_fingerprint"] = value
            self.assert_rejected(data, "check_specification_fingerprint_mismatch")

    def test_v2_hash_does_not_authorize_altered_contract(self) -> None:
        forged = replace(self.spec, checks=(contract.DeveloperTaskGuestCheck("pipeline", flow="check"),))
        self.assertNotEqual(forged.fingerprint, self.spec.fingerprint)
        self.assert_rejected(forged.to_dict(), "check_sequence_mismatch")

    def test_v2_rejects_invalid_descriptor_even_with_valid_spec(self) -> None:
        result = contract.validate_developer_task_guest_check_specification_v2(
            _encoded(self.data), profile_document=self.raw[:-1])
        self.assertFalse(result.ok)
        self.assertEqual(result.issue_codes, ("profile_size_mismatch",))

    def test_v2_rejects_duplicate_json_keys(self) -> None:
        raw = _encoded(self.data).rstrip()
        raw = raw[:-1] + b',"schema_version":2}'
        result = contract.validate_developer_task_guest_check_specification_v2(raw, profile_document=self.raw)
        self.assertEqual(result.issue_codes, ("duplicate_json_key",))

    def test_v2_rejects_duplicate_nested_json_keys(self) -> None:
        raw = _encoded(self.data).replace(b'"type":"git_diff_check"',
                                         b'"type":"git_diff_check","type":"git_diff_check"')
        result = contract.validate_developer_task_guest_check_specification_v2(raw, profile_document=self.raw)
        self.assertEqual(result.issue_codes, ("duplicate_json_key",))

    def test_v2_rejects_nan_infinity_and_unbounded_depth(self) -> None:
        for raw in (b'{"x":NaN}', b'{"x":Infinity}', b'{"x":-Infinity}',
                    b'{"x":'+b'['*20+b'0'+b']'*20+b'}'):
            result = contract.validate_developer_task_guest_check_specification_v2(raw, profile_document=self.raw)
            self.assertFalse(result.ok)
            self.assert_no_authority(result.to_dict())

    def test_v2_rejects_malformed_nonobject_utf8_and_oversize(self) -> None:
        for raw in (b'[]', b'null', b'{', b'{}{}', b'\xff', b'\xef\xbb\xbf{}',
                    b' '*17000, b''):
            result = contract.validate_developer_task_guest_check_specification_v2(raw, profile_document=self.raw)
            self.assertFalse(result.ok)

    def test_v2_rejects_non_bytes_without_coercion(self) -> None:
        for raw in (self.data, _encoded(self.data).decode(), None, bytearray(_encoded(self.data))):
            result = contract.validate_developer_task_guest_check_specification_v2(raw, profile_document=self.raw)
            self.assertFalse(result.ok)
            self.assertEqual(result.issue_codes, ("bytes_required",))

    def test_serialized_v2_objects_do_not_mutate_immutable_spec(self) -> None:
        original = self.spec.fingerprint
        detached = self.spec.to_dict(); detached["checks"][-1]["flow"] = "check"
        self.assertEqual(self.spec.fingerprint, original)
        with self.assertRaises(FrozenInstanceError):
            self.spec.schema_version = 1
        with self.assertRaises(FrozenInstanceError):
            self.spec.checks[-1].flow = "check"

    def test_serialization_rejects_foreign_dto(self) -> None:
        with self.assertRaises(contract.DeveloperTaskGuestProfileError):
            contract.canonical_developer_task_guest_check_specification_v2(self.data)

    def test_v1_still_accepts_unchanged_full_check(self) -> None:
        v1 = self.valid_v1()
        result = validate_developer_task_manifest(v1)
        self.assertTrue(result.ok)
        first = developer_task_manifest_fingerprint(result.manifest)
        contract.validate_developer_task_guest_check_specification_v2(_encoded(self.data), profile_document=self.raw)
        self.assertEqual(first, developer_task_manifest_fingerprint(validate_developer_task_manifest(v1).manifest))
        self.assertEqual(result.manifest.checks[-1].flow, "check")

    def test_v1_does_not_accept_new_flow_or_version(self) -> None:
        v1 = self.valid_v1(); v1["schema_version"] = 2
        result = validate_developer_task_manifest(v1)
        self.assertFalse(result.ok)
        self.assertIn("unsupported_schema_version", result.issue_codes)
        v1 = self.valid_v1(); v1["checks"][-1]["flow"] = "check_guest_source_v1"
        self.assertFalse(validate_developer_task_manifest(v1).ok)
        self.assertFalse(validate_developer_task_manifest(self.data).ok)

    def test_v1_document_is_not_v2_check_specification(self) -> None:
        self.assert_rejected(self.valid_v1(), "check_specification_fields_invalid")

    def test_pure_contract_operations_have_no_io(self) -> None:
        raw = _encoded(self.data)
        with patch("builtins.open", side_effect=AssertionError("file I/O")), \
             patch.object(Path, "read_bytes", side_effect=AssertionError("file read")), \
             patch.object(Path, "write_bytes", side_effect=AssertionError("file write")), \
             patch("builtins.eval", side_effect=AssertionError("eval")), \
             patch("builtins.exec", side_effect=AssertionError("exec")):
            self.assertTrue(contract.validate_developer_task_guest_profile(self.raw).ok)
            self.assertTrue(contract.validate_developer_task_guest_check_specification_v2(raw, profile_document=self.raw).ok)

    def test_production_source_has_bounded_dependency_surface(self) -> None:
        allowed = {"__future__", "hashlib", "json", "dataclasses", "typing",
                   "modules.developer.developer_task_guest_profile_policy",
                   "modules.developer.developer_task_guest_profile_document"}
        banned_calls = {"open", "exec", "eval", "compile", "__import__", "system",
                        "read_bytes", "write_bytes", "read_text", "write_text", "Popen", "run"}
        for module in (contract, document, policy):
            tree = ast.parse(inspect.getsource(module))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertTrue(all(x.name in allowed for x in node.names))
                elif isinstance(node, ast.ImportFrom):
                    self.assertIn(node.module, allowed)
                elif isinstance(node, ast.Call):
                    name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
                    self.assertNotIn(name, banned_calls)

    @staticmethod
    def valid_v1() -> dict:
        return {
            "schema_version": 1, "task_kind": "patch", "task_id": "guest-contract-v1-regression",
            "title": "Preserve existing V1", "project": "SkynetVS", "origin": "manual",
            "source_ref": "manual:guest-contract-test", "source_sha256": "a"*64,
            "base_commit": "0123456789abcdef0123456789abcdef01234567",
            "patch_file": "changes.patch", "patch_sha256": "b"*64,
            "allowed_files": ["modules/example.py"],
            "checks": [{"type": "git_diff_check"},
                       {"type": "py_compile", "scope": "changed_python_files"},
                       {"type": "pipeline", "flow": "check"}],
            "install_policy": "manual_confirmation",
        }


def main() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(GuestProfileContractTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({
        "kind": "V1C6_GUEST_PROFILE_PASSIVE_CONTRACT_EVALUATION_V1",
        "tests_run": result.testsRun, "failures": len(result.failures),
        "errors": len(result.errors), "skipped": len(result.skipped),
        "result": "PASS_NON_EXECUTING_CONTRACT" if result.wasSuccessful() and not result.skipped else "FAIL",
        "guest_profile_executed": False, "runtime_authorized": False,
        "promotion_authorized": False,
    }, sort_keys=True))
    return 0 if result.wasSuccessful() and not result.skipped else 1


if __name__ == "__main__":
    raise SystemExit(main())
