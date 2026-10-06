from __future__ import annotations

"""Portable data-only regression suite; does not run source content or a profile."""

import ast
import copy
import hashlib
import json
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from unittest.mock import patch

from modules.developer import developer_task_guest_request as c
from modules.developer import developer_task_guest_request_binding as binding
from modules.developer.developer_task_guest_profile_document import GUEST_PROFILE_DOCUMENT
from modules.developer.developer_task_proposal_contract import (
    DeveloperTaskProposalContextInput, DeveloperTaskProposalRequest,
)
from modules.developer.developer_task_proposal_intake import prepare_developer_task_proposal_request

HEAD = "e10d0ccf056171cbbe8cd26a945940158d22c48f"
TREE = "1a4a55d003c2b25ff58b5d874f4768d402c5db82"
CONTENT = b'"""Unexecuted request fixture."""\nVALUE = 1\n'
TARGET = "modules/text_normalizer.py"


def encode(data):
    return (json.dumps(data, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()


def oid(raw):
    return hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()


def source(path=TARGET, raw=CONTENT, **kwargs):
    return c.DeveloperTaskGuestContextInputV2(path, kwargs.get("mode", "100644"),
                                             kwargs.get("git_blob_oid", oid(raw)), raw)


def inputs(**changes):
    value = dict(task_id="dtr-v2-fixture", title="Bound request fixture", request_id="request-v2-fixture",
                 instruction="Change only the selected docstring.\n", task_base_commit=HEAD,
                 task_base_tree=TREE, target_path=TARGET, context_entries=(source(),),
                 profile_document=GUEST_PROFILE_DOCUMENT)
    value.update(changes)
    return value


class GuestRequestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request = c.prepare_developer_task_guest_request_v2(**inputs())
        cls.raw = c.canonical_developer_task_guest_request_v2(cls.request, profile_document=GUEST_PROFILE_DOCUMENT)
        cls.data = cls.request.to_dict()

    def check(self, raw, expected=None):
        return c.validate_developer_task_guest_request_v2(
            raw, expected_request=self.request if expected is None else expected,
            profile_document=GUEST_PROFILE_DOCUMENT)

    def refuse(self, raw, expected=None):
        result = self.check(raw, expected)
        self.assertFalse(result.ok)
        out = result.to_dict()
        self.assertFalse(out["request_envelope_validated"])
        self.assertFalse(out["request_binding_validated"])
        self.assertEqual(out["request_fingerprint"], "")
        self.assertEqual(len(result.issue_codes), 1)
        return result

    def build_refuses(self, **changes):
        with self.assertRaises(c.DeveloperTaskGuestRequestError):
            c.prepare_developer_task_guest_request_v2(**inputs(**changes))

    def test_01_roundtrip(self):
        self.assertEqual(self.check(self.raw).request, self.request)

    def test_02_fingerprint_covers_whole_envelope(self):
        body = self.request.to_dict(include_fingerprint=False)
        expected = hashlib.sha256(encode(body).rstrip(b"\n")).hexdigest()
        self.assertEqual(self.request.fingerprint, expected)
        self.assertEqual(len(expected), 64)

    def test_03_fixed_manual_policy(self):
        self.assertEqual((self.request.origin, self.request.transport_mode, self.request.install_policy),
                         ("manual", "manual_import", "manual_confirmation"))
        self.assertEqual(self.request.schema_version, 2)

    def test_04_nested_semantics_preserved(self):
        b = self.request.binding
        self.assertEqual(set(b.binding_payload()), {"schema_version", "check_contract_id", "profile_id",
                         "profile_revision", "profile_sha256", "task_base_commit", "task_base_tree", "target_preimage"})
        self.assertEqual(b.task_base_commit, HEAD)
        self.assertEqual(b.task_base_tree, TREE)
        self.assertEqual(b.target_preimage.git_blob_oid, oid(CONTENT))

    def test_05_exact_check_order(self):
        spec = self.request.check_specification
        self.assertEqual([x.type for x in spec.checks], ["git_diff_check", "py_compile", "pipeline"])
        self.assertEqual(spec.checks[-1].flow, "check_guest_source_v1")
        self.assertEqual(spec.checks[-1].profile_sha256, self.request.binding.profile_sha256)

    def test_06_context_sorted_deterministically(self):
        ctx = (source(), source("modules/helper.py", b"helper"))
        one = c.prepare_developer_task_guest_request_v2(**inputs(context_entries=ctx))
        two = c.prepare_developer_task_guest_request_v2(**inputs(context_entries=tuple(reversed(ctx))))
        self.assertEqual(one, two)
        self.assertEqual(one.fingerprint, two.fingerprint)

    def test_07_context_bytes_not_serialized(self):
        self.assertNotIn(CONTENT, self.raw)
        self.assertNotIn("content", self.data["context"][0])
        self.assertEqual(self.request.context[0].content, CONTENT)
        self.assertEqual(self.request.context[0].content_sha256, hashlib.sha256(CONTENT).hexdigest())

    def test_08_frozen_dtos(self):
        with self.assertRaises(FrozenInstanceError):
            self.request.title = "changed"
        with self.assertRaises(FrozenInstanceError):
            self.request.context[0].path = "modules/other.py"

    def test_09_to_dict_is_detached(self):
        data = self.request.to_dict()
        data["context"][0]["path"] = "modules/changed.py"
        data["check_specification"]["checks"].clear()
        self.assertEqual(self.request.to_dict(), self.data)

    def test_10_non_authority_success_and_failure(self):
        for result in (self.check(self.raw), self.refuse(b"{}")):
            for key in ("task_validated", "proposal_validated", "manifest_validated", "patch_validated",
                        "preflight_validated", "execution_plan_validated", "repository_observed",
                        "source_membership_verified", "model_provider_called", "capability_issued",
                        "guest_profile_executed", "required_profile_checks_passed", "all_required_checks_passed",
                        "ready_to_promote", "runtime_authorized", "promotion_authorized"):
                self.assertIs(result.to_dict()[key], False, key)
            self.assertEqual(result.to_dict()["behavioral_correctness"], "NOT_EVALUATED")

    def test_11_instruction_is_fingerprint_bound(self):
        other = c.prepare_developer_task_guest_request_v2(**inputs(instruction="Different instruction"))
        self.assertNotEqual(self.request.fingerprint, other.fingerprint)
        self.refuse(c.canonical_developer_task_guest_request_v2(other, profile_document=GUEST_PROFILE_DOCUMENT))

    def test_12_identity_fields_are_bound(self):
        for key, value in (("task_id", "other-task"), ("request_id", "other-request"), ("title", "Other title")):
            with self.subTest(key=key):
                req = c.prepare_developer_task_guest_request_v2(**inputs(**{key: value}))
                self.assertNotEqual(req.fingerprint, self.request.fingerprint)
                self.refuse(encode(req.to_dict()))

    def test_13_base_substitution_even_rehashed(self):
        for key in ("task_base_commit", "task_base_tree"):
            req = c.prepare_developer_task_guest_request_v2(**inputs(**{key: "b" * 40}))
            self.refuse(encode(req.to_dict()))

    def test_14_target_substitution_even_rehashed(self):
        path = "modules/alternative.py"
        req = c.prepare_developer_task_guest_request_v2(**inputs(target_path=path, context_entries=(source(path),)))
        self.refuse(encode(req.to_dict()))

    def test_15_context_substitution_even_rehashed(self):
        req = c.prepare_developer_task_guest_request_v2(**inputs(context_entries=(source(raw=b"DIFFERENT"),)))
        self.refuse(encode(req.to_dict()))

    def test_16_extra_context_is_bound(self):
        req = c.prepare_developer_task_guest_request_v2(**inputs(context_entries=(source(), source("modules/helper.py", b"data"))))
        self.refuse(encode(req.to_dict()))

    def test_17_context_exact_limits(self):
        ctx = tuple(source(TARGET if n == 0 else f"modules/source_{n}.py", b"x" * (64 * 1024)) for n in range(4))
        req = c.prepare_developer_task_guest_request_v2(**inputs(context_entries=ctx))
        self.assertEqual(sum(x.content_bytes for x in req.context), 256 * 1024)
        self.assertLess(len(c.canonical_developer_task_guest_request_v2(req, profile_document=GUEST_PROFILE_DOCUMENT)), 64 * 1024)

    def test_18_context_count_refusals(self):
        for ctx in ((), tuple(source(f"modules/a{n}.py") for n in range(5))):
            self.build_refuses(context_entries=ctx)

    def test_19_context_type_refusals(self):
        for ctx in ([source()], "data", b"data", (object(),)):
            self.build_refuses(context_entries=ctx)
        self.build_refuses(context_entries=(replace(source(), content=bytearray(CONTENT)),))

    def test_20_context_file_bound(self):
        self.build_refuses(context_entries=(source(raw=b"x" * (64 * 1024 + 1)),))

    def test_21_context_case_duplicate(self):
        self.build_refuses(context_entries=(source(), source("modules/TEXT_NORMALIZER.py")))

    def test_22_target_required_exactly(self):
        self.build_refuses(context_entries=(source("modules/other.py"),))
        self.build_refuses(target_path="modules/Text_Normalizer.py")

    def test_23_bad_context_oid_and_mode(self):
        for change in ({"git_blob_oid": "b" * 40}, {"git_blob_oid": "A" * 40}, {"mode": "120000"}, {"mode": "100755"}):
            self.build_refuses(context_entries=(replace(source(), **change),))

    def test_24_protected_targets_preserved(self):
        for path in ("main.py", "modules/core/x.py", "modules/runtime/x.py", "modules/developer/x.py",
                     "modules/action_broker.py", "modules/__init__.py", "modules/test_x.py", "modules/eval_x.py",
                     "modules/a_test.py", "tools/x.py", "native/x.py"):
            with self.subTest(path=path):
                self.build_refuses(target_path=path, context_entries=(source(path),))

    def test_25_disclosure_denials(self):
        for path in (".env", "requirements.txt", "pyproject.toml", "setup.py", "data/x", "models/x", "native/x", ".git/config", "venv/x"):
            with self.subTest(path=path):
                self.build_refuses(context_entries=(source(), source(path)))

    def test_26_path_alias_refusals(self):
        for path in ("modules/a:stream.py", "modules/a*/x.py", "modules//x.py", "modules/../x.py",
                     "modules/a./x.py", "modules/a /x.py", "modules/nul.py", "modules/COM1.py",
                     "modules/\tx.py", "modules/\nx.py", "modules/.private/x.py", "/modules/x.py",
                     "modules\\x.py", " modules/x.py", "modules/x.py ", "modules/" + "x" * 121 + ".py"):
            with self.subTest(path=path):
                self.build_refuses(context_entries=(source(), source(path)))

    def test_27_instruction_and_title_boundaries(self):
        c.prepare_developer_task_guest_request_v2(**inputs(instruction="x" * (16 * 1024), title="x" * 160))
        self.build_refuses(instruction="x" * (16 * 1024 + 1))
        self.build_refuses(instruction="я" * (8 * 1024 + 1))
        self.build_refuses(title="x" * 161)
        for value in ("", "   ", "x\x00y", "\ud800"):
            self.build_refuses(instruction=value)
        for value in (" x", "x ", "x\ny", "x\x7fy"):
            self.build_refuses(title=value)

    def test_28_bad_task_request_ids(self):
        for key, values in (("task_id", ("a", "Upper", "a.b", True, "x" * 65)),
                            ("request_id", ("a", "spaces here", True, "x" * 97))):
            for value in values:
                self.build_refuses(**{key: value})

    def test_29_profile_and_base_refusals(self):
        self.build_refuses(profile_document=GUEST_PROFILE_DOCUMENT + b" ")
        for value in ("short", "A" * 40, True, "f" * 41):
            self.build_refuses(task_base_commit=value)
            self.build_refuses(task_base_tree=value)

    def test_30_missing_extra_top_fields(self):
        for key in self.data:
            data = copy.deepcopy(self.data); del data[key]; self.refuse(encode(data))
        for key in ("runtime_authorized", "candidate_tree", "patch_sha256", "unknown"):
            self.refuse(encode({**self.data, key: False}))

    def test_31_nested_tampering_rejected(self):
        for name in ("binding", "check_specification", "context"):
            data = copy.deepcopy(self.data)
            if name == "context": data[name][0]["content_bytes"] = True
            else: data[name]["profile_revision"] = True
            self.refuse(encode(data))

    def test_32_old_check_and_reordered_checks_rejected(self):
        data = copy.deepcopy(self.data); data["check_specification"]["checks"][-1]["flow"] = "check"
        self.refuse(encode(data))
        data = copy.deepcopy(self.data); data["check_specification"]["checks"].reverse()
        self.refuse(encode(data))

    def test_33_write_allowlist_and_policy_tampering(self):
        for key, value in (("target_write_allowlist", [TARGET, "modules/helper.py"]), ("install_policy", "automatic"),
                           ("origin", "browser_bridge"), ("transport_mode", "network"), ("policy_id", "V1"),
                           ("context_digest", "0" * 64), ("request_fingerprint", "0" * 64)):
            self.refuse(encode({**self.data, key: value}))

    def test_34_strict_schema_dispatch(self):
        for val in (1, 3, True, "2", 2.0):
            self.refuse(encode({**self.data, "schema_version": val}))
        self.refuse(encode({**self.data, "kind": "DTR_PATCH_PROPOSAL_V1"}))

    def test_35_duplicate_top_and_nested_json(self):
        self.refuse(self.raw.replace(b'"schema_version":2', b'"schema_version":2,"schema_version":2', 1))
        self.refuse(self.raw.replace(b'"content_bytes":', b'"content_bytes":0,"content_bytes":', 1))

    def test_36_nonfinite_and_invalid_utf8_json(self):
        for raw in (b"\xff", b"{", b"[]", b"null", b"true", b"", b'{}garbage', b'\xef\xbb\xbf{}'):
            self.refuse(raw)
        for literal in (b"NaN", b"Infinity", b"-Infinity", b"1e999"):
            self.refuse(self.raw.replace(b'"schema_version":2', b'"schema_version":' + literal, 1))

    def test_37_json_limits_and_surrogates(self):
        self.refuse(b" " * (64 * 1024 + 1))
        data = copy.deepcopy(self.data); data["extra"] = [[[[[[[[[0]]]]]]]]]
        self.refuse(encode(data))
        self.refuse(self.raw.replace(b'Bound request fixture', b'\\ud800'))
        self.refuse(bytearray(self.raw))
        self.refuse(self.raw.decode())

    def test_38_whitespace_and_key_order_allowed(self):
        raw = json.dumps(self.data, ensure_ascii=False, indent=4).encode()
        self.assertEqual(self.check(raw).request, self.request)

    def test_39_crlf_wire_not_source_normalization(self):
        raw = json.dumps(self.data, indent=2).replace("\n", "\r\n").encode()
        self.assertTrue(self.check(raw).ok)
        req = c.prepare_developer_task_guest_request_v2(**inputs(context_entries=(source(raw=CONTENT.replace(b"\n", b"\r\n")),)))
        self.assertNotEqual(req.fingerprint, self.request.fingerprint)
        self.refuse(encode(req.to_dict()))

    def test_40_expected_type_and_forged_nested(self):
        for obj in (object(), self.data, replace(self.request, binding=None), replace(self.request, check_specification=None),
                    replace(self.request, context=[]), replace(self.request, context=(object(),)),
                    replace(self.request, binding=replace(self.request.binding, target_preimage=None))):
            self.refuse(self.raw, expected=obj)

    def test_41_expected_object_revalidated(self):
        for obj in (replace(self.request, schema_version=True), replace(self.request, origin="automatic"),
                    replace(self.request, context_digest="0" * 64),
                    replace(self.request, context=(replace(self.request.context[0], content_sha256="0" * 64),)),
                    replace(self.request, check_specification=replace(self.request.check_specification, checks=())),
                    replace(self.request, binding=replace(self.request.binding, profile_revision=True))):
            self.refuse(self.raw, expected=obj)
            with self.assertRaises(c.DeveloperTaskGuestRequestError):
                c.canonical_developer_task_guest_request_v2(obj, profile_document=GUEST_PROFILE_DOCUMENT)

    def test_42_error_does_not_echo_instruction_or_content(self):
        secret = "UNTRUSTED_PRIVATE_VALUE_FOR_TEST"
        data = copy.deepcopy(self.data); data["instruction"] = secret
        result = self.refuse(encode(data))
        self.assertNotIn(secret, json.dumps(result.to_dict()))
        self.assertNotIn(CONTENT.decode(), repr(self.request))

    def test_43_no_io_in_request_operations(self):
        with patch("builtins.open", side_effect=AssertionError("file access")), \
             patch("subprocess.run", side_effect=AssertionError("process")), \
             patch("socket.socket", side_effect=AssertionError("network")):
            req = c.prepare_developer_task_guest_request_v2(**inputs())
            raw = c.canonical_developer_task_guest_request_v2(req, profile_document=GUEST_PROFILE_DOCUMENT)
            self.assertTrue(self.check(raw).ok)

    def test_44_production_import_surface(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "modules/developer/developer_task_guest_request.py").read_text(encoding="utf-8")
        tree = ast.parse(text)
        imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        imported |= {alias.name for n in ast.walk(tree) if isinstance(n, ast.Import) for alias in n.names}
        self.assertEqual(imported, {"__future__", "hashlib", "json", "re", "dataclasses", "typing",
                         "modules.developer.developer_task_guest_profile_contract",
                         "modules.developer.developer_task_guest_request_binding"})
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, ("open", "eval", "exec", "compile", "__import__"))

    def test_45_report_flag_fix_reject_and_success(self):
        for raw in (b"{}", b"not json"):
            out = binding.validate_developer_task_guest_request_binding_v2(
                raw, profile_document=GUEST_PROFILE_DOCUMENT, target_content=CONTENT).to_dict()
            self.assertFalse(out["ok"])
            self.assertFalse(out["request_binding_validated"])
        raw = binding.canonical_developer_task_guest_request_binding_v2(self.request.binding)
        out = binding.validate_developer_task_guest_request_binding_v2(
            raw, profile_document=GUEST_PROFILE_DOCUMENT, target_content=CONTENT).to_dict()
        self.assertTrue(out["ok"])
        self.assertTrue(out["request_binding_validated"])
        self.assertFalse(out["runtime_authorized"])

    def test_46_v1_producer_stays_v1(self):
        req = prepare_developer_task_proposal_request(
            task_id="legacy-test", title="Legacy task", request_id="legacy-request",
            instruction="Legacy check", base_commit=HEAD, base_tree=TREE, target_path=TARGET,
            context_entries=(DeveloperTaskProposalContextInput(TARGET, "100644", oid(CONTENT), CONTENT),))
        self.assertIs(type(req), DeveloperTaskProposalRequest)
        self.assertEqual(req.schema_version, 1)
        self.assertEqual(req.checks[-1].flow, "check")
        self.refuse(encode(req.binding_dict()))
        self.refuse(self.raw, expected=req)

    def test_47_no_candidate_or_runtime_fabrication(self):
        for key in ("candidate_tree", "patch_sha256", "manifest_fingerprint", "runtime_bundle_id",
                    "dependency_bundle_id", "git_bundle_id", "capability", "accepted_preflight_binding"):
            self.assertNotIn(key, self.data)
        self.assertFalse(self.check(self.raw).to_dict()["source_membership_verified"])

    def test_48_untrusted_code_bytes_remain_data(self):
        dangerous = b'raise RuntimeError("NOT TO BE EXECUTED")\n'
        req = c.prepare_developer_task_guest_request_v2(**inputs(context_entries=(source(raw=dangerous),)))
        raw = c.canonical_developer_task_guest_request_v2(req, profile_document=GUEST_PROFILE_DOCUMENT)
        self.assertTrue(self.check(raw, expected=req).ok)


def main() -> int:
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(GuestRequestTests))
    print(json.dumps({"status": "PASS_NON_EXECUTING_REQUEST_ENVELOPE" if result.wasSuccessful() else "FAIL",
                      "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
                      "candidate_request_code_executed_for_tests": True,
                      "guest_profile_executed": False, "changed_task_code_executed": False,
                      "runtime_authorized": False, "promotion_authorized": False}, sort_keys=True))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
