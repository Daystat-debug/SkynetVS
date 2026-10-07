from __future__ import annotations

"""Portable tests of passive V2 proposal/manifest data; no guest profile execution."""

import ast
import copy
import hashlib
import json
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from unittest.mock import patch

from modules.developer import developer_task_guest_proposal_intake as c
from modules.developer import developer_task_guest_request as r
from modules.developer.developer_task_guest_profile_document import GUEST_PROFILE_DOCUMENT
from modules.developer.developer_task_proposal_contract import DeveloperTaskProposalContextInput
from modules.developer.developer_task_proposal_intake import (
    intake_developer_task_proposal, prepare_developer_task_proposal_request,
)
from modules.developer.developer_task_validator import validate_developer_task_manifest

HEAD = "3949bdab50106484e1832d42dcb554dbc4691131"
TREE = "45ed23e54f5fdf3ca2253fcee5c133e6ac47f46b"
TARGET = "modules/text_normalizer.py"
# Synthetic fixture content, not a claim of membership in HEAD/TREE.
CONTENT = b'"""Not executed."""\nVALUE = 1\n'
PATCH = ("diff --git a/modules/text_normalizer.py b/modules/text_normalizer.py\n"
         "--- a/modules/text_normalizer.py\n+++ b/modules/text_normalizer.py\n"
         "@@ -1,2 +1,2 @@\n \"\"\"Not executed.\"\"\"\n-VALUE = 1\n+VALUE = 2\n")


def encode(data):
    return (json.dumps(data, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()


def canonical(data):
    return encode(data)[:-1]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def oid(raw):
    return hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()


def request(**changes):
    args = dict(task_id="v2-proposal-fixture", title="Bound proposal fixture",
                request_id="request-v2-proposal-fixture", instruction="Change only VALUE.",
                task_base_commit=HEAD, task_base_tree=TREE, target_path=TARGET,
                context_entries=(r.DeveloperTaskGuestContextInputV2(TARGET, "100644", oid(CONTENT), CONTENT),),
                profile_document=GUEST_PROFILE_DOCUMENT)
    args.update(changes)
    return r.prepare_developer_task_guest_request_v2(**args)


class GuestProposalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.req = request()
        cls.raw = c.encode_developer_task_guest_proposal_v2(
            expected_request=cls.req, patch_text=PATCH, explanation="Data-only fixture.",
            profile_document=GUEST_PROFILE_DOCUMENT)
        cls.data = json.loads(cls.raw)
        cls.plan = c.parse_developer_task_guest_proposal_v2(
            cls.raw, expected_request=cls.req, profile_document=GUEST_PROFILE_DOCUMENT)
        cls.manifest_raw = c.canonical_developer_task_guest_manifest_v2(
            cls.plan.manifest, expected_request=cls.req, raw_response=cls.raw,
            profile_document=GUEST_PROFILE_DOCUMENT)
        cls.manifest_data = json.loads(cls.manifest_raw)

    def check(self, raw, *, expected=None, profile=GUEST_PROFILE_DOCUMENT):
        return c.intake_developer_task_guest_proposal_v2(
            raw, expected_request=self.req if expected is None else expected, profile_document=profile)

    def refuse(self, raw, *, expected=None, profile=GUEST_PROFILE_DOCUMENT):
        result = self.check(raw, expected=expected, profile=profile)
        self.assertFalse(result.ok)
        self.assertIsNone(result.plan)
        self.assertEqual(len(result.issue_codes), 1)
        out = result.to_dict()
        self.assertFalse(out["proposal_data_bound"])
        self.assertFalse(out["manifest_data_bound"])
        self.assertEqual(result.status, c.GUEST_PROPOSAL_REJECTED_STATUS)
        return result

    def change(self, **kwargs):
        data = copy.deepcopy(self.data); data.update(kwargs)
        return encode(data)

    def mcheck(self, raw, *, response=None, expected=None):
        return c.validate_developer_task_guest_manifest_v2(
            raw, expected_request=self.req if expected is None else expected,
            raw_response=self.raw if response is None else response, profile_document=GUEST_PROFILE_DOCUMENT)

    def mrefuse(self, data):
        result = self.mcheck(encode(data) if type(data) is dict else data)
        self.assertFalse(result.ok)
        self.assertIsNone(result.manifest)
        self.assertFalse(result.to_dict()["manifest_data_bound"])
        self.assertEqual(result.to_dict()["manifest_fingerprint"], "")
        return result

    def test_01_roundtrip(self):
        self.assertEqual(self.check(self.raw).plan, self.plan)
        self.assertEqual(self.plan.request, self.req)

    def test_02_explicit_v2_and_manual_policy(self):
        d = self.manifest_data
        self.assertEqual((d["kind"], d["schema_version"]), (c.GUEST_MANIFEST_KIND, 2))
        self.assertEqual((d["origin"], d["transport_mode"], d["install_policy"]),
                         ("manual", "manual_import", "manual_confirmation"))
        self.assertEqual(d["patch_file"], "changes.patch")

    def test_03_exact_patch_and_raw_identities(self):
        p = self.plan.proposal
        self.assertEqual(p.patch_bytes, PATCH.encode())
        self.assertEqual(p.raw_response, self.raw)
        self.assertEqual(p.patch_sha256, sha(PATCH.encode()))
        self.assertEqual(p.raw_response_sha256, sha(self.raw))
        self.assertEqual(self.manifest_data["source_sha256"], sha(self.raw))
        self.assertEqual(self.manifest_data["patch_sha256"], sha(PATCH.encode()))

    def test_04_eight_semantic_fields_propagate(self):
        b = self.req.binding
        keys = set(b.binding_payload())
        self.assertEqual(keys, {"schema_version", "check_contract_id", "profile_id", "profile_revision",
                               "profile_sha256", "task_base_commit", "task_base_tree", "target_preimage"})
        self.assertEqual(self.data["binding"], b.to_dict())
        self.assertEqual(self.manifest_data["binding"], b.to_dict())

    def test_05_exact_checks_and_order(self):
        checks = self.manifest_data["check_specification"]
        self.assertEqual(checks, self.req.check_specification.to_dict())
        self.assertEqual([x["type"] for x in checks["checks"]], ["git_diff_check", "py_compile", "pipeline"])
        self.assertEqual(checks["checks"][-1]["flow"], "check_guest_source_v1")

    def test_06_manifest_fingerprint_covers_all_data(self):
        self.assertEqual(self.plan.manifest.fingerprint, sha(canonical(self.plan.manifest.to_dict(include_fingerprint=False))))
        self.assertEqual(self.manifest_data["manifest_fingerprint"], self.plan.manifest.fingerprint)

    def test_07_manifest_roundtrip(self):
        self.assertEqual(self.mcheck(self.manifest_raw).manifest, self.plan.manifest)

    def test_08_frozen_dtos(self):
        for obj, field, val in ((self.plan, "request", None), (self.plan.proposal, "patch_bytes", b"x"),
                                (self.plan.manifest, "patch_sha256", "0" * 64)):
            with self.assertRaises(FrozenInstanceError):
                setattr(obj, field, val)

    def test_09_detached_json_views(self):
        d = self.plan.evidence_dict(); d["manifest"]["binding"]["profile_revision"] = 5
        d["manifest"]["check_specification"]["checks"].clear()
        self.assertEqual(self.plan.manifest.to_dict(), self.manifest_data)

    def test_10_raw_and_context_not_in_report(self):
        out = json.dumps(self.check(self.raw).to_dict())
        for secret in (CONTENT.decode(), "Change only VALUE.", "Data-only fixture.", PATCH):
            self.assertNotIn(secret, out)
            self.assertNotIn(secret, repr(self.plan))

    def test_11_no_authority_on_success_or_failure(self):
        outputs = (self.check(self.raw).to_dict(), self.refuse(b"{}").to_dict(),
                   self.mcheck(self.manifest_raw).to_dict(), self.mrefuse(b"{}").to_dict())
        for out in outputs:
            for key in ("task_validated", "patch_validated", "patch_scope_validated", "patch_applicability_verified",
                        "preflight_validated", "execution_plan_validated", "repository_observed", "source_membership_verified",
                        "provider_authenticated", "model_provider_called", "capability_issued", "authority_granted",
                        "candidate_tree_computed", "guest_profile_executed", "changed_task_code_executed",
                        "required_profile_checks_passed", "all_required_checks_passed", "ready_to_promote",
                        "runtime_authorized", "promotion_authorized"):
                self.assertIs(out[key], False, key)
            self.assertEqual(out["behavioral_correctness"], "NOT_EVALUATED")

    def test_12_no_circular_or_future_ids(self):
        for key in ("candidate_tree", "accepted_preflight_binding", "runtime_bundle_id", "dependency_bundle_id",
                    "git_bundle_id", "environment_asset_manifest_id", "fresh_check_identity", "capability"):
            self.assertNotIn(key, self.manifest_data)
        self.assertNotIn("patch_sha256", self.req.to_dict())
        self.assertNotIn("manifest_fingerprint", self.req.to_dict())

    def test_13_schema_v1_and_unknown_rejected(self):
        for v in (0, 1, 3, -1, True, False, "2", None):
            self.refuse(self.change(schema_version=v))

    def test_14_kind_v1_or_other_rejected(self):
        for kind in ("DTR_PATCH_PROPOSAL_V1", "DTR_GUEST_REQUEST_V2", "", None, 2):
            self.refuse(self.change(kind=kind))

    def test_15_every_missing_field_rejected(self):
        for field in self.data:
            d = copy.deepcopy(self.data); d.pop(field); self.refuse(encode(d))

    def test_16_authority_or_transport_fields_rejected(self):
        for key, value in (("runtime_authorized", True), ("promotion_authorized", True), ("checks", []),
                           ("candidate_tree", "b" * 40), ("patch_file", "../../x.py"),
                           ("install_policy", "automatic"), ("origin", "browser_bridge")):
            self.refuse(self.change(**{key: value}))

    def test_17_request_id_and_fingerprint_mismatch(self):
        for key, value in (("request_id", "other-request"), ("request_fingerprint", "f" * 64),
                           ("request_id", 3), ("request_fingerprint", None)):
            self.refuse(self.change(**{key: value}))

    def test_18_all_binding_fields_even_rehashed(self):
        for key in self.req.binding.binding_payload():
            d = copy.deepcopy(self.data)
            if key == "target_preimage": d["binding"][key]["content_sha256"] = "e" * 64
            elif key in ("schema_version", "profile_revision"): d["binding"][key] = 7
            else: d["binding"][key] = "x" * 40
            payload = {k: d["binding"][k] for k in self.req.binding.binding_payload()}
            d["binding"]["request_binding_fingerprint"] = sha(canonical(payload))
            self.refuse(encode(d))

    def test_19_binding_scalar_types(self):
        for key in ("schema_version", "profile_revision"):
            d = copy.deepcopy(self.data); d["binding"][key] = True; self.refuse(encode(d))

    def test_20_check_order_and_flow_refused(self):
        d = copy.deepcopy(self.data); d["check_specification"]["checks"].reverse(); self.refuse(encode(d))
        d = copy.deepcopy(self.data); d["check_specification"]["checks"][-1]["flow"] = "check"; self.refuse(encode(d))
        d = copy.deepcopy(self.data); d["check_specification"]["checks"].pop(); self.refuse(encode(d))

    def test_21_nested_extra_field_refused(self):
        d = copy.deepcopy(self.data); d["binding"]["allow"] = True; self.refuse(encode(d))
        d = copy.deepcopy(self.data); d["check_specification"]["checks"][0]["command"] = "calc"; self.refuse(encode(d))

    def test_22_other_instruction_even_valid_new_request(self):
        other = request(instruction="Different instruction")
        raw = c.encode_developer_task_guest_proposal_v2(expected_request=other, patch_text=PATCH,
              explanation="data", profile_document=GUEST_PROFILE_DOCUMENT)
        self.refuse(raw)
        self.assertTrue(self.check(raw, expected=other).ok)

    def test_23_other_base_or_target_even_valid_new_request(self):
        other = request(task_base_commit="b" * 40)
        raw = c.encode_developer_task_guest_proposal_v2(expected_request=other, patch_text=PATCH,
              explanation="data", profile_document=GUEST_PROFILE_DOCUMENT)
        self.refuse(raw)
        target = "modules/other.py"
        other = request(target_path=target, context_entries=(r.DeveloperTaskGuestContextInputV2(target, "100644", oid(CONTENT), CONTENT),))
        raw = c.encode_developer_task_guest_proposal_v2(expected_request=other, patch_text=PATCH,
              explanation="data", profile_document=GUEST_PROFILE_DOCUMENT)
        self.refuse(raw)

    def test_24_wrong_expected_request_type(self):
        for expected in ({}, self.req.to_dict(), "request", 1, True):
            self.refuse(self.raw, expected=expected)

    def test_25_corrupt_expected_request_revalidated(self):
        for bad in (replace(self.req, schema_version=1), replace(self.req, origin="automatic"),
                    replace(self.req, context_digest="0" * 64), replace(self.req, binding=None),
                    replace(self.req, context=(replace(self.req.context[0], content=b"changed"),)),
                    replace(self.req, check_specification=replace(self.req.check_specification, checks=()))):
            self.refuse(self.raw, expected=bad)

    def test_26_profile_pin_is_not_bypassed(self):
        for doc in (GUEST_PROFILE_DOCUMENT + b" ", b"{}", bytearray(GUEST_PROFILE_DOCUMENT)):
            self.refuse(self.raw, profile=doc)

    def test_27_raw_immutable_bytes_only(self):
        for raw in (self.raw.decode(), bytearray(self.raw), memoryview(self.raw), None, 3):
            self.refuse(raw)

    def test_28_empty_and_oversized_raw(self):
        self.refuse(b"")
        self.refuse(b" " * (c.GUEST_PROPOSAL_MAX_RESPONSE_BYTES + 1))
        raw = self.raw + b" " * (c.GUEST_PROPOSAL_MAX_RESPONSE_BYTES - len(self.raw))
        self.assertTrue(self.check(raw).ok)

    def test_29_invalid_utf8_and_bom(self):
        self.refuse(b"\xff")
        self.refuse(b"\xef\xbb\xbf" + self.raw)

    def test_30_duplicate_keys_top_and_nested(self):
        self.refuse(self.raw.replace(b'"schema_version":2', b'"schema_version":2,"schema_version":2', 1))
        self.refuse(self.raw.replace(b'"target_preimage":{', b'"target_preimage":{"path":"hidden",', 1))

    def test_31_nonfinite_and_float_numbers(self):
        for value in (b"NaN", b"Infinity", b"-Infinity", b"2.0", b"1e9999"):
            self.refuse(self.raw.replace(b'"schema_version":2', b'"schema_version":' + value, 1))

    def test_32_one_object_only_no_markdown(self):
        for raw in (self.raw + b"{}", b"```json\n" + self.raw + b"```", b"[]", b"null", b"2", b'"text"'):
            self.refuse(raw)

    def test_33_deep_json_and_big_integer(self):
        self.refuse(b'{"x":' + b'[' * 1000 + b'0' + b']' * 1000 + b'}')
        self.refuse(b'{"x":' + b'9' * 10000 + b'}')

    def test_34_surrogates_key_and_patch(self):
        self.refuse(b'{"\\ud800":1}')
        self.refuse(self.raw.replace(b'"explanation":"Data-only fixture."', b'"explanation":"\\ud800"'))

    def test_35_patch_type_empty_and_nul(self):
        for value in (None, [], 7, "", " \n\t", "x\x00y"):
            self.refuse(self.change(patch_text=value))

    def test_36_patch_byte_limit(self):
        self.assertTrue(self.check(self.change(patch_text="x" * c.GUEST_PROPOSAL_MAX_PATCH_BYTES)).ok)
        self.refuse(self.change(patch_text="x" * (c.GUEST_PROPOSAL_MAX_PATCH_BYTES + 1)))
        self.refuse(self.change(patch_text="я" * (c.GUEST_PROPOSAL_MAX_PATCH_BYTES // 2 + 1)))

    def test_37_explanation_type_empty_and_nul(self):
        for value in (None, [], True, "", " \n\t", "x\x00y"):
            self.refuse(self.change(explanation=value))

    def test_38_explanation_byte_limit(self):
        self.assertTrue(self.check(self.change(explanation="x" * c.GUEST_PROPOSAL_MAX_EXPLANATION_BYTES)).ok)
        self.refuse(self.change(explanation="x" * (c.GUEST_PROPOSAL_MAX_EXPLANATION_BYTES + 1)))

    def test_39_patch_whitespace_and_eol_not_normalized(self):
        text = "  patch\r\nline\t\r\n\r\n"
        p = self.check(self.change(patch_text=text)).plan.proposal
        self.assertEqual(p.patch_bytes, text.encode())
        self.assertEqual(p.patch_sha256, sha(text.encode()))

    def test_40_unicode_escapes_preserve_patch_bytes_not_response_hash(self):
        d = copy.deepcopy(self.data); d["patch_text"] = "строка\n"
        a = encode(d); b = json.dumps(d, ensure_ascii=True).encode()
        x, y = self.check(a).plan, self.check(b).plan
        self.assertEqual(x.proposal.patch_bytes, y.proposal.patch_bytes)
        self.assertNotEqual(x.proposal.raw_response_sha256, y.proposal.raw_response_sha256)
        self.assertNotEqual(x.manifest.fingerprint, y.manifest.fingerprint)

    def test_41_response_formatting_changes_source_identity(self):
        raw = json.dumps(self.data, indent=4).encode()
        other = self.check(raw).plan
        self.assertEqual(other.proposal.patch_sha256, self.plan.proposal.patch_sha256)
        self.assertNotEqual(other.manifest.fingerprint, self.plan.manifest.fingerprint)
        self.assertFalse(self.mcheck(self.manifest_raw, response=raw).ok)

    def test_42_explanation_changes_source_identity(self):
        raw = self.change(explanation="Different explanation")
        other = self.check(raw).plan
        self.assertEqual(other.manifest.patch_sha256, self.plan.manifest.patch_sha256)
        self.assertNotEqual(other.manifest.source_sha256, self.plan.manifest.source_sha256)
        self.assertFalse(self.mcheck(self.manifest_raw, response=raw).ok)

    def test_43_patch_changes_manifest_and_does_not_change_request(self):
        before = self.req.to_dict()
        other = self.check(self.change(patch_text=PATCH + "\n")).plan
        self.assertNotEqual(other.manifest.patch_sha256, self.plan.manifest.patch_sha256)
        self.assertNotEqual(other.manifest.fingerprint, self.plan.manifest.fingerprint)
        self.assertEqual(before, self.req.to_dict())

    def test_44_patch_is_explicitly_opaque_at_this_stage(self):
        for text in ("NOT A DIFF", "diff --git a/main.py b/main.py\n", "raise RuntimeError('DO NOT EXECUTE')\n"):
            out = self.check(self.change(patch_text=text)).to_dict()
            self.assertTrue(out["proposal_data_bound"])
            self.assertFalse(out["patch_validated"])
            self.assertFalse(out["patch_scope_validated"])
            self.assertFalse(out["patch_applicability_verified"])

    def test_45_response_cannot_override_manifest_source(self):
        for key in ("source_sha256", "source_ref", "patch_sha256", "manifest_fingerprint", "allowed_files"):
            self.refuse(self.change(**{key: "untrusted"}))

    def test_46_manifest_schema_kind_strict(self):
        for value in (1, 3, True, "2", None):
            d = copy.deepcopy(self.manifest_data); d["schema_version"] = value; self.mrefuse(d)
        d = copy.deepcopy(self.manifest_data); d["kind"] = "DTR_PATCH_PROPOSAL_V1"; self.mrefuse(d)

    def test_47_manifest_missing_or_unknown_fields(self):
        for key in self.manifest_data:
            d = copy.deepcopy(self.manifest_data); d.pop(key); self.mrefuse(d)
        d = copy.deepcopy(self.manifest_data); d["runtime_authorized"] = True; self.mrefuse(d)

    def test_48_manifest_rehashed_tampering(self):
        for key, value in (("patch_sha256", "a" * 64), ("source_sha256", "b" * 64),
                           ("source_bytes", 1), ("patch_bytes", True), ("origin", "automatic"),
                           ("task_id", "other-task"), ("source_ref", "other"), ("patch_file", "../x.py"),
                           ("allowed_files", ["main.py"]), ("install_policy", "automatic"),
                           ("request_fingerprint", "c" * 64), ("context_digest", "d" * 64)):
            d = copy.deepcopy(self.manifest_data); d[key] = value; d.pop("manifest_fingerprint")
            d["manifest_fingerprint"] = sha(canonical(d)); self.mrefuse(d)

    def test_49_manifest_checks_or_binding_tampering(self):
        d = copy.deepcopy(self.manifest_data); d["binding"]["task_base_tree"] = "a" * 40; self.mrefuse(d)
        d = copy.deepcopy(self.manifest_data); d["check_specification"]["checks"][-1]["flow"] = "check"; self.mrefuse(d)

    def test_50_manifest_other_response_or_request(self):
        self.assertFalse(self.mcheck(self.manifest_raw, response=self.change(patch_text="other")).ok)
        self.assertFalse(self.mcheck(self.manifest_raw, expected=request(instruction="Other")).ok)
        self.assertFalse(self.mcheck(self.manifest_raw, response=b"{}").ok)

    def test_51_manifest_json_guards(self):
        for raw in (b"", b"[]", b"\xff", b"\xef\xbb\xbf" + self.manifest_raw,
                    self.manifest_raw + b"{}", b" " * (c.GUEST_MANIFEST_MAX_JSON_BYTES + 1),
                    self.manifest_raw.replace(b'"source_bytes":', b'"source_bytes":0,"source_bytes":', 1)):
            self.mrefuse(raw)

    def test_52_canonical_manifest_revalidates_object(self):
        for bad in ({}, replace(self.plan.manifest, patch_sha256="a" * 64),
                    replace(self.plan.manifest, source_bytes=True),
                    replace(self.plan.manifest, request=replace(self.req, context_digest="a" * 64))):
            with self.assertRaises(c.DeveloperTaskGuestProposalError):
                c.canonical_developer_task_guest_manifest_v2(bad, expected_request=self.req,
                    raw_response=self.raw, profile_document=GUEST_PROFILE_DOCUMENT)

    def test_53_serializer_rejects_invalid_input(self):
        for text in (None, "", "x\x00y", "\ud800"):
            with self.assertRaises(c.DeveloperTaskGuestProposalError):
                c.encode_developer_task_guest_proposal_v2(expected_request=self.req, patch_text=text,
                    explanation="data", profile_document=GUEST_PROFILE_DOCUMENT)

    def test_54_error_diagnostics_do_not_echo_untrusted_text(self):
        secret = "UNTRUSTED_PRIVATE_PAYLOAD"
        result = self.refuse(self.change(**{secret: secret}))
        self.assertNotIn(secret, json.dumps(result.to_dict()))
        self.assertNotIn(secret, str(result.issue_codes))

    def test_55_no_io_process_or_network_during_operations(self):
        with patch("builtins.open", side_effect=AssertionError("I/O")), \
             patch("subprocess.run", side_effect=AssertionError("process")), \
             patch("socket.socket", side_effect=AssertionError("network")):
            raw = c.encode_developer_task_guest_proposal_v2(expected_request=self.req, patch_text=PATCH,
                    explanation="data", profile_document=GUEST_PROFILE_DOCUMENT)
            plan = self.check(raw).plan
            out = c.canonical_developer_task_guest_manifest_v2(plan.manifest, expected_request=self.req,
                    raw_response=raw, profile_document=GUEST_PROFILE_DOCUMENT)
            self.assertTrue(self.mcheck(out, response=raw).ok)

    def test_56_production_import_surface_is_passive_and_v2_only(self):
        src = (Path(__file__).resolve().parents[1] / "modules/developer/developer_task_guest_proposal_intake.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        imports |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        self.assertEqual(imports, {"__future__", "hashlib", "json", "dataclasses", "typing",
                                  "modules.developer.developer_task_guest_request"})
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, ("open", "eval", "exec", "compile", "__import__"))

    def test_57_v1_producer_and_intake_still_v1(self):
        req = prepare_developer_task_proposal_request(task_id="v1-fixture", title="Legacy",
            request_id="v1-request", instruction="Legacy task", base_commit=HEAD, base_tree=TREE,
            target_path=TARGET, context_entries=(DeveloperTaskProposalContextInput(TARGET, "100644", oid(CONTENT), CONTENT),))
        data = {"kind": "DTR_PATCH_PROPOSAL_V1", "schema_version": 1, "request_id": req.request_id,
                "request_fingerprint": req.request_fingerprint, "patch_text": PATCH, "explanation": "data"}
        result = intake_developer_task_proposal(req, encode(data))
        self.assertTrue(result.ok)
        self.assertEqual(result.plan.manifest.schema_version, 1)
        self.assertEqual(result.plan.manifest.checks[-1].flow, "check")
        self.refuse(encode(data))
        self.refuse(self.raw, expected=req)
        self.assertFalse(intake_developer_task_proposal(req, self.raw).ok)

    def test_58_v1_manifest_validator_rejects_v2(self):
        self.assertFalse(validate_developer_task_manifest(self.manifest_data).ok)

    def test_59_target_content_remains_data(self):
        text = b'raise RuntimeError("TARGET NEVER EXECUTED")\n'
        req = request(context_entries=(r.DeveloperTaskGuestContextInputV2(TARGET, "100644", oid(text), text),))
        raw = c.encode_developer_task_guest_proposal_v2(expected_request=req, patch_text=PATCH,
               explanation="data", profile_document=GUEST_PROFILE_DOCUMENT)
        self.assertTrue(self.check(raw, expected=req).ok)

    def test_60_selected_target_and_context_stay_request_bound(self):
        self.assertEqual(self.manifest_data["allowed_files"], [TARGET])
        self.assertEqual(self.manifest_data["context_digest"], self.req.context_digest)
        ctx = self.req.context[0]
        self.assertEqual(self.manifest_data["binding"]["target_preimage"]["git_blob_oid"], ctx.git_blob_oid)
        self.assertNotIn("content", self.manifest_data["binding"]["target_preimage"])

    def test_61_response_and_manifest_source_are_distinct_hashes(self):
        self.assertNotEqual(self.manifest_data["source_sha256"], self.manifest_data["patch_sha256"])
        self.assertNotEqual(self.manifest_data["manifest_fingerprint"], self.manifest_data["source_sha256"])
        self.assertEqual(self.manifest_data["source_bytes"], len(self.raw))
        self.assertEqual(self.manifest_data["patch_bytes"], len(PATCH.encode()))

    def test_62_manifest_serializer_rejects_detached_request_content_forgery(self):
        fake = replace(self.plan.manifest, request=replace(self.req,
               context=(replace(self.req.context[0], content=b"forged"),)))
        with self.assertRaises(c.DeveloperTaskGuestProposalError):
            c.canonical_developer_task_guest_manifest_v2(fake, expected_request=self.req,
                raw_response=self.raw, profile_document=GUEST_PROFILE_DOCUMENT)

    def test_63_forged_context_self_consistent_still_wrong_expected_request(self):
        text = b"different context"
        req = request(context_entries=(r.DeveloperTaskGuestContextInputV2(TARGET, "100644", oid(text), text),))
        raw = c.encode_developer_task_guest_proposal_v2(expected_request=req, patch_text=PATCH,
               explanation="data", profile_document=GUEST_PROFILE_DOCUMENT)
        self.refuse(raw)

    def test_64_canonical_fingerprint_fixture(self):
        # Frozen data-only vector. Any intentional wire change must update its documented fixture.
        self.assertEqual(self.plan.manifest.fingerprint, sha(canonical({k: v for k, v in self.manifest_data.items()
                                                                      if k != "manifest_fingerprint"})))
        self.assertEqual(self.plan.manifest.fingerprint, "56ea5be43c6c5fcc52ce91e3d235e8b9d33ce7f91f6c808c74b91f29dd47d20e")


def main() -> int:
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(GuestProposalTests))
    print(json.dumps({"status": "PASS_NON_EXECUTING_GUEST_PROPOSAL_INTAKE" if result.wasSuccessful() else "FAIL",
        "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
        "candidate_intake_code_executed_for_tests": True, "guest_profile_executed": False,
        "changed_task_code_executed": False, "runtime_authorized": False, "promotion_authorized": False}, sort_keys=True))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
