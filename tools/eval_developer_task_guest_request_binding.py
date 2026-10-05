from __future__ import annotations

import copy
import hashlib
import json
import unittest
from dataclasses import FrozenInstanceError, replace

from modules.developer import developer_task_guest_request_binding as contract
from modules.developer.developer_task_guest_profile_document import GUEST_PROFILE_DOCUMENT
from modules.developer.developer_task_guest_profile_policy import (
    GUEST_CHECK_CONTRACT_ID,
    GUEST_PROFILE_DOCUMENT_SHA256,
    GUEST_PROFILE_ID,
    GUEST_PROFILE_REVISION,
)


BASE_COMMIT = "76bf218bc30481847298c97b69e7cad09bdb8812"
BASE_TREE = "37faa4ba8a203fdb26f1fb13447f7daf1510caad"
TARGET_PATH = "modules/text_normalizer.py"
TARGET_CONTENT = b'"""fixture only; request binding does not execute target code."""\nVALUE = 1\n'
TARGET_BLOB = hashlib.sha1(
    f"blob {len(TARGET_CONTENT)}\0".encode("ascii") + TARGET_CONTENT
).hexdigest()


def _encoded(value) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8") + b"\n"


class GuestRequestBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.binding = contract.build_developer_task_guest_request_binding_v2(
            profile_document=GUEST_PROFILE_DOCUMENT,
            task_base_commit=BASE_COMMIT,
            task_base_tree=BASE_TREE,
            target_path=TARGET_PATH,
            target_mode="100644",
            target_git_blob_oid=TARGET_BLOB,
            target_content=TARGET_CONTENT,
        )
        cls.raw = contract.canonical_developer_task_guest_request_binding_v2(cls.binding)
        cls.data = cls.binding.to_dict()

    def assert_rejected(self, data, code: str | None = None, *, content=TARGET_CONTENT) -> None:
        result = contract.validate_developer_task_guest_request_binding_v2(
            _encoded(data),
            profile_document=GUEST_PROFILE_DOCUMENT,
            target_content=content,
        )
        self.assertFalse(result.ok)
        if code is not None:
            self.assertEqual(result.issue_codes, (code,))

    def assert_no_authority(self, value: dict) -> None:
        for key in (
            "task_validated", "proposal_validated", "manifest_validated",
            "patch_validated", "preflight_validated", "execution_plan_validated",
            "capability_issued", "guest_profile_executed",
            "required_profile_checks_passed", "all_required_checks_passed",
            "ready_to_promote", "runtime_authorized", "promotion_authorized",
        ):
            self.assertIs(value[key], False)
        self.assertEqual(value["behavioral_correctness"], "NOT_EVALUATED")

    def test_exact_binding_field_set(self) -> None:
        self.assertEqual(set(self.binding.binding_payload()), {
            "schema_version", "check_contract_id", "profile_id", "profile_revision",
            "profile_sha256", "task_base_commit", "task_base_tree", "target_preimage",
        })

    def test_binding_pins_guest_contract(self) -> None:
        self.assertEqual(self.binding.schema_version, 2)
        self.assertEqual(self.binding.check_contract_id, GUEST_CHECK_CONTRACT_ID)
        self.assertEqual(self.binding.profile_id, GUEST_PROFILE_ID)
        self.assertEqual(self.binding.profile_revision, GUEST_PROFILE_REVISION)
        self.assertEqual(self.binding.profile_sha256, GUEST_PROFILE_DOCUMENT_SHA256)

    def test_target_preimage_is_exact(self) -> None:
        p = self.binding.target_preimage
        self.assertEqual(p.path, TARGET_PATH)
        self.assertEqual(p.mode, "100644")
        self.assertEqual(p.git_blob_oid, TARGET_BLOB)
        self.assertEqual(p.content_sha256, hashlib.sha256(TARGET_CONTENT).hexdigest())
        self.assertEqual(p.content_bytes, len(TARGET_CONTENT))

    def test_roundtrip_and_stable_fingerprint(self) -> None:
        rebuilt = contract.parse_developer_task_guest_request_binding_v2(
            self.raw,
            profile_document=GUEST_PROFILE_DOCUMENT,
            target_content=TARGET_CONTENT,
        )
        self.assertEqual(rebuilt, self.binding)
        self.assertEqual(rebuilt.fingerprint, "396e0a01bf1156d73989b9e156562c190bb2a7398601db14c262af6ad2d16425")

    def test_result_is_request_binding_only(self) -> None:
        result = contract.validate_developer_task_guest_request_binding_v2(
            self.raw,
            profile_document=GUEST_PROFILE_DOCUMENT,
            target_content=TARGET_CONTENT,
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.status, "REQUEST_BINDING_VALIDATED_NOT_AUTHORIZED")
        self.assertTrue(result.to_dict()["request_binding_validated"])
        self.assert_no_authority(result.to_dict())

    def test_binding_is_deeply_immutable(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            self.binding.task_base_commit = "0" * 40
        with self.assertRaises(FrozenInstanceError):
            self.binding.target_preimage.path = "modules/other.py"

    def test_builder_requires_exact_profile_document(self) -> None:
        with self.assertRaises(contract.DeveloperTaskGuestRequestBindingError):
            contract.build_developer_task_guest_request_binding_v2(
                profile_document=GUEST_PROFILE_DOCUMENT[:-1],
                task_base_commit=BASE_COMMIT, task_base_tree=BASE_TREE,
                target_path=TARGET_PATH, target_mode="100644",
                target_git_blob_oid=TARGET_BLOB, target_content=TARGET_CONTENT,
            )

    def test_builder_rejects_bad_base_commit(self) -> None:
        for value in ("", "A"*40, "0"*39, "0"*41, True, None):
            with self.subTest(value=value):
                with self.assertRaises(contract.DeveloperTaskGuestRequestBindingError):
                    contract.build_developer_task_guest_request_binding_v2(
                        profile_document=GUEST_PROFILE_DOCUMENT,
                        task_base_commit=value, task_base_tree=BASE_TREE,
                        target_path=TARGET_PATH, target_mode="100644",
                        target_git_blob_oid=TARGET_BLOB, target_content=TARGET_CONTENT,
                    )

    def test_builder_rejects_bad_base_tree(self) -> None:
        for value in ("", "A"*40, "0"*39, "0"*41, True, None):
            with self.subTest(value=value):
                with self.assertRaises(contract.DeveloperTaskGuestRequestBindingError):
                    contract.build_developer_task_guest_request_binding_v2(
                        profile_document=GUEST_PROFILE_DOCUMENT,
                        task_base_commit=BASE_COMMIT, task_base_tree=value,
                        target_path=TARGET_PATH, target_mode="100644",
                        target_git_blob_oid=TARGET_BLOB, target_content=TARGET_CONTENT,
                    )

    def test_builder_rejects_non_bytes_target_content(self) -> None:
        for value in (bytearray(TARGET_CONTENT), memoryview(TARGET_CONTENT), "x", None):
            with self.subTest(kind=type(value).__name__):
                with self.assertRaises(contract.DeveloperTaskGuestRequestBindingError):
                    contract.build_developer_task_guest_request_binding_v2(
                        profile_document=GUEST_PROFILE_DOCUMENT,
                        task_base_commit=BASE_COMMIT, task_base_tree=BASE_TREE,
                        target_path=TARGET_PATH, target_mode="100644",
                        target_git_blob_oid=TARGET_BLOB, target_content=value,
                    )

    def test_builder_rejects_blob_content_mismatch(self) -> None:
        with self.assertRaises(contract.DeveloperTaskGuestRequestBindingError) as cm:
            contract.build_developer_task_guest_request_binding_v2(
                profile_document=GUEST_PROFILE_DOCUMENT,
                task_base_commit=BASE_COMMIT, task_base_tree=BASE_TREE,
                target_path=TARGET_PATH, target_mode="100644",
                target_git_blob_oid="0"*40, target_content=TARGET_CONTENT,
            )
        self.assertEqual(cm.exception.code, "target_blob_content_mismatch")

    def test_builder_rejects_wrong_mode(self) -> None:
        for mode in ("100755", "120000", "", 100644, None):
            with self.subTest(mode=mode):
                with self.assertRaises(contract.DeveloperTaskGuestRequestBindingError):
                    contract.build_developer_task_guest_request_binding_v2(
                        profile_document=GUEST_PROFILE_DOCUMENT,
                        task_base_commit=BASE_COMMIT, task_base_tree=BASE_TREE,
                        target_path=TARGET_PATH, target_mode=mode,
                        target_git_blob_oid=TARGET_BLOB, target_content=TARGET_CONTENT,
                    )

    def test_target_path_requires_modules_python(self) -> None:
        for path in ("README.md", "tools/x.py", "modules/x.txt", "/modules/x.py", "C:/x.py"):
            with self.subTest(path=path):
                with self.assertRaises(contract.DeveloperTaskGuestRequestBindingError):
                    contract.build_developer_task_guest_request_binding_v2(
                        profile_document=GUEST_PROFILE_DOCUMENT,
                        task_base_commit=BASE_COMMIT, task_base_tree=BASE_TREE,
                        target_path=path, target_mode="100644",
                        target_git_blob_oid=TARGET_BLOB, target_content=TARGET_CONTENT,
                    )

    def test_target_path_rejects_noncanonical_and_traversal(self) -> None:
        for path in (
            " modules/x.py", "modules/x.py ", r"modules\x.py", "modules/../x.py",
            "modules/./x.py", "modules//x.py", "modules/.hidden.py",
        ):
            with self.subTest(path=path):
                with self.assertRaises(contract.DeveloperTaskGuestRequestBindingError):
                    contract.build_developer_task_guest_request_binding_v2(
                        profile_document=GUEST_PROFILE_DOCUMENT,
                        task_base_commit=BASE_COMMIT, task_base_tree=BASE_TREE,
                        target_path=path, target_mode="100644",
                        target_git_blob_oid=TARGET_BLOB, target_content=TARGET_CONTENT,
                    )

    def test_protected_target_surface_matches_current_first_task_policy(self) -> None:
        for path in (
            "modules/developer/x.py", "modules/core/x.py", "modules/runtime/x.py",
            "modules/action_contract.py", "modules/action_authority.py",
            "modules/action_broker.py", "modules/timer_action_runtime.py",
            "modules/volume_action_runtime.py", "modules/__init__.py",
            "modules/test_x.py", "modules/eval_x.py", "modules/x_test.py",
        ):
            with self.subTest(path=path):
                with self.assertRaises(contract.DeveloperTaskGuestRequestBindingError) as cm:
                    contract.build_developer_task_guest_request_binding_v2(
                        profile_document=GUEST_PROFILE_DOCUMENT,
                        task_base_commit=BASE_COMMIT, task_base_tree=BASE_TREE,
                        target_path=path, target_mode="100644",
                        target_git_blob_oid=TARGET_BLOB, target_content=TARGET_CONTENT,
                    )
                self.assertEqual(cm.exception.code, "protected_target")

    def test_parser_rejects_schema1_and_coercions(self) -> None:
        for value in (1, 3, True, False, 2.0, "2", None):
            data=copy.deepcopy(self.data);data["schema_version"]=value
            self.assert_rejected(data, "request_binding_schema_version_unsupported")

    def test_parser_rejects_profile_revision_coercions(self) -> None:
        for value in (0, 2, True, 1.0, "1", None):
            data=copy.deepcopy(self.data);data["profile_revision"]=value
            self.assert_rejected(data, "request_binding_profile_revision_unsupported")

    def test_parser_rejects_each_missing_top_field(self) -> None:
        for key in self.data:
            data=copy.deepcopy(self.data);del data[key]
            self.assert_rejected(data, "request_binding_fields_invalid")

    def test_parser_rejects_extra_future_stage_fields(self) -> None:
        for key in (
            "request_id", "instruction", "context", "proposal", "manifest",
            "manifest_fingerprint", "patch_sha256", "candidate_tree",
            "runtime_bundle_id", "dependency_bundle_id", "git_bundle_id",
            "runtime_authorized", "promotion_authorized",
        ):
            data=copy.deepcopy(self.data);data[key]=True
            self.assert_rejected(data, "request_binding_fields_invalid")

    def test_parser_rejects_contract_profile_reference_changes(self) -> None:
        for key,value in (
            ("check_contract_id","DTR_ONE_PYTHON_MODIFY_V1"),
            ("profile_id","other"),
            ("profile_sha256","0"*64),
        ):
            data=copy.deepcopy(self.data);data[key]=value
            self.assert_rejected(data, "request_binding_guest_contract_reference_mismatch")

    def test_parser_rejects_target_preimage_field_changes(self) -> None:
        for key in self.data["target_preimage"]:
            data=copy.deepcopy(self.data);del data["target_preimage"][key]
            self.assert_rejected(data, "target_preimage_fields_invalid")

    def test_parser_rejects_target_content_sha_type_and_shape(self) -> None:
        for value in ("A"*64, "0"*63, 1, True, None):
            data=copy.deepcopy(self.data);data["target_preimage"]["content_sha256"]=value
            self.assert_rejected(data, "target_content_sha256_invalid")

    def test_parser_rejects_target_content_bytes_coercion(self) -> None:
        for value in (True, False, 1.0, "1", None):
            data=copy.deepcopy(self.data);data["target_preimage"]["content_bytes"]=value
            self.assert_rejected(data, "target_content_bytes_invalid")

    def test_parser_rejects_external_target_content_change(self) -> None:
        result = contract.validate_developer_task_guest_request_binding_v2(
            self.raw,
            profile_document=GUEST_PROFILE_DOCUMENT,
            target_content=TARGET_CONTENT+b"x",
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.issue_codes, ("target_blob_content_mismatch",))

    def test_parser_rejects_fingerprint_change(self) -> None:
        for value in ("0"*64, self.binding.fingerprint.upper(), 1, True, None):
            data=copy.deepcopy(self.data);data["request_binding_fingerprint"]=value
            self.assert_rejected(data, "request_binding_fingerprint_mismatch")

    def test_fingerprint_changes_with_each_binding_dimension(self) -> None:
        base=self.binding.fingerprint
        variants=[
            replace(self.binding, task_base_commit="0"*40),
            replace(self.binding, task_base_tree="1"*40),
            replace(self.binding, check_contract_id="other"),
            replace(self.binding, profile_id="other"),
            replace(self.binding, profile_revision=2),
            replace(self.binding, profile_sha256="0"*64),
            replace(self.binding, target_preimage=replace(self.binding.target_preimage, path="modules/other.py")),
        ]
        self.assertTrue(all(v.fingerprint != base for v in variants))

    def test_fingerprint_does_not_include_envelope_kind(self) -> None:
        payload=self.binding.binding_payload()
        self.assertNotIn("kind", payload)
        self.assertNotIn("request_binding_fingerprint", payload)

    def test_parser_rejects_duplicate_top_key(self) -> None:
        raw=self.raw.rstrip()
        raw=raw[:-1]+b',"schema_version":2}'
        result=contract.validate_developer_task_guest_request_binding_v2(
            raw,profile_document=GUEST_PROFILE_DOCUMENT,target_content=TARGET_CONTENT)
        self.assertEqual(result.issue_codes, ("duplicate_json_key",))

    def test_parser_rejects_duplicate_nested_key(self) -> None:
        raw=self.raw.replace(
            b'"content_bytes":'+str(len(TARGET_CONTENT)).encode(),
            b'"content_bytes":'+str(len(TARGET_CONTENT)).encode()+b',"content_bytes":1',
            1,
        )
        result=contract.validate_developer_task_guest_request_binding_v2(
            raw,profile_document=GUEST_PROFILE_DOCUMENT,target_content=TARGET_CONTENT)
        self.assertEqual(result.issue_codes, ("duplicate_json_key",))

    def test_parser_rejects_non_object_and_invalid_utf8(self) -> None:
        for raw in (b"[]", b"null", b"\xff", b"", b"{}"):
            result=contract.validate_developer_task_guest_request_binding_v2(
                raw,profile_document=GUEST_PROFILE_DOCUMENT,target_content=TARGET_CONTENT)
            self.assertFalse(result.ok)

    def test_parser_rejects_nonfinite_json(self) -> None:
        raw=self.raw.replace(b'"content_bytes":',b'"content_bytes":NaN,"unused":',1)
        result=contract.validate_developer_task_guest_request_binding_v2(
            raw,profile_document=GUEST_PROFILE_DOCUMENT,target_content=TARGET_CONTENT)
        self.assertFalse(result.ok)

    def test_canonical_serializer_requires_exact_type(self) -> None:
        with self.assertRaises(contract.DeveloperTaskGuestRequestBindingError):
            contract.canonical_developer_task_guest_request_binding_v2(self.binding.to_dict())

    def test_validator_rejects_non_bytes_raw(self) -> None:
        for raw in (bytearray(self.raw), memoryview(self.raw), self.raw.decode(), None):
            result=contract.validate_developer_task_guest_request_binding_v2(
                raw,profile_document=GUEST_PROFILE_DOCUMENT,target_content=TARGET_CONTENT)
            self.assertFalse(result.ok)

    def test_no_io_or_authority_surface(self) -> None:
        names=set(vars(contract))
        for forbidden in (
            "subprocess", "socket", "requests", "Path", "open", "run", "Popen",
            "runtime_authorized", "promotion_authorized",
        ):
            self.assertNotIn(forbidden, names)


if __name__ == "__main__":
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(GuestRequestBindingTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({
        "kind":"V1C6_GUEST_REQUEST_BINDING_EVALUATION_V1",
        "tests_run":result.testsRun,
        "failures":len(result.failures),
        "errors":len(result.errors),
        "skipped":len(result.skipped),
        "result":"PASS_NON_EXECUTING_REQUEST_BINDING" if result.wasSuccessful() else "FAIL",
        "guest_profile_executed":False,
        "patch_executed":False,
        "runtime_authorized":False,
        "promotion_authorized":False,
    },sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
