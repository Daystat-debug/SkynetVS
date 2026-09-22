import unittest
from dataclasses import replace
from ..wsb01_policy import CoreError, ModelExperiment as M, ModelResult as R, SIGNING_DOMAIN
from ..wsb01_contract import MessageKind as K, parse_message, serialize_message
from ..wsb01_ports import ArtifactBytes, ModelObservations
from ..wsb01_transcript import (pin_ready_model, validate_scm_trace_model, validate_transcript_model)
from .test_contract import (expectation, request_fields, ready_bytes, model_bundle, journal_bytes,
                            normal_rows, unsafe_json, status_bytes, h)


def modified_artifacts(entries, name, data):
    return tuple(replace(x, data=data) if x.name == name else x for x in entries)


class TranscriptTests(unittest.TestCase):
    def test_TRA01_identity_bindings(self):
        exp = expectation(M.SCM_REFUSAL)
        ready = parse_message(K.READY, ready_bytes(exp)).as_dict()
        for field in ("run_id", "nonce", "profile", "policy_sha256", "schema_sha256", "source_sha256",
                      "runtime_sha256", "payload_sha256", "layout_sha256", "request_sha256"):
            changed = dict(ready)
            changed[field] = "bad-profile" if field == "profile" else "0" * len(ready[field])
            with self.subTest(field=field), self.assertRaises(CoreError):
                pin_ready_model(exp, unsafe_json(changed))
        obj = request_fields(M.SCM_REFUSAL); obj["guard"]["sha256"] = "0" * 64
        with self.assertRaises(CoreError):
            serialize_message(K.REQUEST, obj)

    def test_TRA02_ready_pin_mutation(self):
        pin, snap, obs = model_bundle()
        ready = parse_message(K.READY, pin.ready_bytes).as_dict()
        ready["public_key_blob_hex"] = ready["public_key_blob_hex"][:-2] + "ff"
        altered = serialize_message(K.READY, ready)
        files = modified_artifacts(snap.before_retirement, "ready.json", altered)
        self.assertFalse(validate_transcript_model(pin, replace(snap, before_retirement=files, after_retirement=files), obs).valid)
        self.assertFalse(validate_transcript_model(replace(pin, public_key_sha256="0" * 64), snap, obs).valid)

    def test_TRA03_output_cannot_authorize(self):
        pin, snap, obs = model_bundle()
        terminal = parse_message(K.TERMINAL, dict((x.name, x.data) for x in snap.before_retirement)["terminal.json"]).as_dict()
        for key, value in (("approved", True), ("action", "LaunchSandbox"), ("runtime_authorized", True), ("crypto_verified", True)):
            with self.subTest(key=key):
                files = modified_artifacts(snap.before_retirement, "terminal.json", unsafe_json({**terminal, key: value}))
                self.assertFalse(validate_transcript_model(pin, replace(snap, before_retirement=files, after_retirement=files), obs).valid)
        self.assertFalse(validate_transcript_model(pin, replace(snap, before_retirement=snap.before_retirement +
                          (ArtifactBytes("failure.json", b"{}\n"),)), obs).valid)

    def test_TRA04_authorization_binding(self):
        pin, snap, obs = model_bundle()
        auth = parse_message(K.AUTHORIZATION, snap.authorization).as_dict()
        for key in ("request_sha256", "ready_sha256", "public_key_sha256", "session_binding_sha256"):
            with self.subTest(key=key):
                changed = {**auth, key: "0" * 64}
                self.assertFalse(validate_transcript_model(pin, replace(snap, authorization=unsafe_json(changed)), obs).valid)
        self.assertFalse(validate_transcript_model(pin, replace(snap, authorization_commit=snap.authorization_commit * 2), obs).valid)
        raw = snap.authorization_commit.replace(b'"version":1', b'"version":1,"version":1')
        self.assertFalse(validate_transcript_model(pin, replace(snap, authorization_commit=raw), obs).valid)

    def test_TRA05_hash_dag_all_artifacts(self):
        pin, snap, obs = model_bundle()
        for entry in snap.before_retirement:
            changed = bytearray(entry.data)
            changed[len(changed) // 2] ^= 1
            files = modified_artifacts(snap.before_retirement, entry.name, bytes(changed))
            with self.subTest(artifact=entry.name):
                self.assertFalse(validate_transcript_model(pin, replace(snap, before_retirement=files, after_retirement=files), obs).valid)
        terminal = parse_message(K.TERMINAL, dict((x.name, x.data) for x in snap.before_retirement)["terminal.json"]).as_dict()
        self.assertNotIn("terminal_sha256", terminal)
        self.assertNotIn("signature", terminal)
        self.assertNotIn("signature_sha256", terminal)

    def test_TRA06_sequence_and_partial(self):
        exp = expectation()
        raw = journal_bytes(exp)
        lines = raw.splitlines(keepends=True)
        for changed in (lines[1] + lines[0] + lines[2], lines[0] + lines[0] + lines[1] + lines[2],
                        lines[0] + lines[2], raw[:-1], raw + lines[-1]):
            with self.subTest(length=len(changed)):
                self.assertFalse(validate_scm_trace_model(changed, exp).valid)

    def test_TRA07_budgets_and_unknown(self):
        exp = expectation(M.SCM_REFUSAL)
        rows = normal_rows(exp)
        for altered in (rows[:3] + [rows[2]] + rows[3:], rows[:2] + rows[3:],
                        rows[:6] + [rows[7], rows[6]] + rows[8:]):
            self.assertFalse(validate_scm_trace_model(journal_bytes(exp, altered), exp).valid)
        failed = rows[:3] + [("ERROR", {"code": "create_result_unknown"}), ("FINAL", {"result": R.FAILURE.value})]
        check = validate_scm_trace_model(journal_bytes(exp, failed), exp)
        self.assertEqual(check.result, R.FAILURE)
        self.assertEqual(dict(check.attempts)["create"], 1)
        self.assertFalse(check.successful)
        self.assertFalse(validate_scm_trace_model(journal_bytes(exp, failed[:-1] + rows[2:]), exp).valid)

    def test_TRA08_owned_cleanup(self):
        exp = expectation(M.SCM_REFUSAL)
        rows = normal_rows(exp)
        existing = rows.copy(); existing[1] = ("INITIAL_NAME_PROBE", {"ok": True, "winerror": 0})
        self.assertFalse(validate_scm_trace_model(journal_bytes(exp, existing), exp).valid)
        failure = existing[:2] + [("ERROR", {"code": "existing_service"}), ("FINAL", {"result": R.FAILURE.value})]
        self.assertEqual(validate_scm_trace_model(journal_bytes(exp, failure), exp).result, R.FAILURE)
        drift = rows.copy(); cfg = rows[9][1]
        drift[9] = ("CLEANUP_CONFIG", {**cfg, "config": {**cfg["config"], "sid_type": 1}})
        self.assertFalse(validate_scm_trace_model(journal_bytes(exp, drift), exp).valid)
        running = rows.copy(); running[10] = ("CLEANUP_STATUS", {**rows[10][1], "raw_hex": status_bytes((16, 4, 0, 0, 0, 0, 0))})
        self.assertFalse(validate_scm_trace_model(journal_bytes(exp, running), exp).valid)
        unowned = rows.copy(); unowned[11] = ("DELETE_INTENT", {"attempt": 1, "owned_handle_id": "9" * 32})
        self.assertFalse(validate_scm_trace_model(journal_bytes(exp, unowned), exp).valid)

    def test_TRA09_raw_status(self):
        exp = expectation(M.SCM_REFUSAL)
        rows = normal_rows(exp)
        self.assertTrue(validate_scm_trace_model(journal_bytes(exp), exp).successful)
        for pos, value in ((0, 32), (1, 4), (2, 1), (3, 0), (4, 79), (5, 1), (6, 1)):
            bad = [16, 1, 0, 1066, 78, 0, 0]; bad[pos] = value
            altered = rows.copy(); altered[8] = ("STATUS", {**rows[8][1], "raw_hex": status_bytes(bad)})
            with self.subTest(field=pos):
                self.assertFalse(validate_scm_trace_model(journal_bytes(exp, altered), exp).valid)
        bad = rows.copy(); bad[8] = ("STATUS", {**rows[8][1], "raw_hex": "00" * 35})
        with self.assertRaises(CoreError):
            journal_bytes(exp, bad)

    def test_TRA10_signature_domain_is_model(self):
        pin, snap, obs = model_bundle()
        check = validate_transcript_model(pin, snap, obs)
        self.assertTrue(check.successful)
        self.assertFalse(check.crypto_verified)
        self.assertFalse(check.runtime_authorized)
        for patch in ({"claimed_valid": False}, {"signing_domain": b"LIVE_GUEST"},
                      {"signed_data_sha256": "0" * 64}, {"public_key_sha256": "0" * 64},
                      {"signature_sha256": "0" * 64}):
            with self.subTest(patch=patch):
                self.assertFalse(validate_transcript_model(pin, snap, replace(obs, crypto=replace(obs.crypto, **patch))).valid)

    def test_TRA11_cross_scope_replay(self):
        benign = expectation()
        scm = expectation(M.SCM_REFUSAL)
        with self.assertRaises(CoreError):
            pin_ready_model(scm, ready_bytes(benign))
        with self.assertRaises(CoreError):
            pin_ready_model(benign, ready_bytes(benign).replace(b'SKYNETVS_SCM01_WSB01_CLOSED_CORE_V1', b'V1B4_LEGACY'))
        self.assertFalse(validate_scm_trace_model(journal_bytes(scm), benign).valid)
        self.assertFalse(validate_scm_trace_model(journal_bytes(benign), scm).valid)

    def test_TRA12_post_exit_stability(self):
        pin, snap, obs = model_bundle()
        for item in snap.after_retirement:
            changed = item.data[:-1] + bytes([item.data[-1] ^ 1])
            after = modified_artifacts(snap.after_retirement, item.name, changed)
            with self.subTest(file=item.name):
                self.assertFalse(validate_transcript_model(pin, replace(snap, after_retirement=after), obs).valid)
        for retire in (replace(obs.retirement, normal=False, unknown=True),
                       replace(obs.retirement, normal=False, forced=True),
                       replace(obs.retirement, session_binding_sha256="0" * 64)):
            self.assertFalse(validate_transcript_model(pin, snap, replace(obs, retirement=retire)).valid)

    def test_REG04_pending_and_deletion_not_absence(self):
        exp = expectation(M.SCM_REFUSAL); rows = normal_rows(exp)
        pending = ("STATUS", {**rows[8][1], "raw_hex": status_bytes((16, 2, 0, 0, 0, 1, 1000))})
        delay = ("ABSENCE_PROBE", {"ok": False, "winerror": 1072})
        good = rows[:8] + [pending] + rows[8:14] + [delay] + rows[14:]
        self.assertTrue(validate_scm_trace_model(journal_bytes(exp, good), exp).successful)
        bad = rows[:14] + [delay] + rows[15:]
        self.assertFalse(validate_scm_trace_model(journal_bytes(exp, bad), exp).valid)

    def test_REG05_failure_transcript_stays_failure(self):
        exp = expectation()
        rows = [("BEGIN", {}), ("ERROR", {"code": "offline_failure"}), ("FINAL", {"result": R.FAILURE.value})]
        pin, snap, obs = model_bundle(exp, rows)
        check = validate_transcript_model(pin, snap, obs)
        self.assertTrue(check.valid)
        self.assertFalse(check.successful)
        self.assertEqual(check.result, R.FAILURE)

    def test_REG06_forged_final_claims(self):
        pin, snap, obs = model_bundle(expectation(M.SCM_REFUSAL))
        terminal = parse_message(K.TERMINAL, dict((x.name, x.data) for x in snap.before_retirement)["terminal.json"]).as_dict()
        for key in ("guard_process_exit_claimed", "guest_retirement_claimed"):
            files = modified_artifacts(snap.before_retirement, "terminal.json", unsafe_json({**terminal, key: True}))
            self.assertFalse(validate_transcript_model(pin, replace(snap, before_retirement=files, after_retirement=files), obs).valid)

    def test_REG13_crypto_domain_must_be_bytes(self):
        pin, snap, obs = model_bundle()
        crypto = replace(obs.crypto, signing_domain=bytearray(SIGNING_DOMAIN))
        self.assertFalse(validate_transcript_model(pin, snap, replace(obs, crypto=crypto)).valid)

    def test_REG14_failed_create_never_owns_other_handle(self):
        exp = expectation(M.SCM_REFUSAL)
        rows = normal_rows(exp)
        rows[3] = ("CREATE_RESULT", {"ok": False, "winerror": 5, "owned_handle_id": "9" * 32})
        self.assertFalse(validate_scm_trace_model(journal_bytes(exp, rows), exp).valid)

    def test_REG15_absence_requires_closed_handles(self):
        exp = expectation(M.SCM_REFUSAL)
        rows = normal_rows(exp)
        no_close = rows[:13] + rows[14:]
        self.assertFalse(validate_scm_trace_model(journal_bytes(exp, no_close), exp).valid)

    def test_REG16_poll_budgets(self):
        exp = expectation(M.SCM_REFUSAL)
        rows = normal_rows(exp)
        pending = ("STATUS", {**rows[8][1], "raw_hex": status_bytes((16, 2, 0, 0, 0, 0, 0))})
        too_many_status = rows[:8] + [pending] * 301 + rows[8:]
        self.assertFalse(validate_scm_trace_model(journal_bytes(exp, too_many_status), exp).valid)
        delay = ("ABSENCE_PROBE", {"ok": False, "winerror": 1072})
        too_many_absence = rows[:14] + [delay] * 101 + rows[14:]
        self.assertFalse(validate_scm_trace_model(journal_bytes(exp, too_many_absence), exp).valid)
