"""New offline fixtures; no historical project imports or native verification."""
import json
import hashlib
import struct
import unittest
from dataclasses import replace, FrozenInstanceError
from ..wsb01_policy import (CoreError, DEFAULT_POLICY, ModelExperiment, ModelResult, PROFILE,
                            DOMAIN, SIGNING_DOMAIN, REFUSAL, ACCOUNT, SERVICE_NAME,
                            budget, guard_descriptor, policy_sha256)
from ..wsb01_contract import (MessageKind as K, common_fields, parse_message, serialize_message,
                              canonical_json_bytes, parse_json_bytes, schema_sha256, BINDINGS,
                              QUERY_SHAPES)
from ..wsb01_ports import (RunExpectation, ArtifactBytes, TranscriptBytes, ModelCryptoObservation,
                           ModelRetirementObservation, ModelObservations)
from ..wsb01_transcript import (pin_ready_model, authorization_bytes_model, validate_scm_trace_model,
                                validate_transcript_model, parse_journal_model)


def h(raw):
    return hashlib.sha256(raw).hexdigest()


def unsafe_json(obj):
    return (json.dumps(obj, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


def request_fields(experiment=ModelExperiment.BENIGN):
    run, nonce = "1" * 32, "2" * 64
    obj = common_fields(K.REQUEST, experiment, run, nonce)
    obj.update(policy_sha256=policy_sha256(), schema_sha256=schema_sha256(),
               source_sha256=h(b"model-source"), runtime_sha256=h(b"model-runtime"),
               payload_sha256=h(b"model-payload"), layout_sha256=h(b"model-layout"),
               guard=guard_descriptor(experiment, run), budget=budget(experiment))
    return obj


def expectation(experiment=ModelExperiment.BENIGN):
    return RunExpectation(serialize_message(K.REQUEST, request_fields(experiment)),
                          h(b"model-host-session"), 10, 1_000_000)


def ready_bytes(expected):
    fields = common_fields(K.READY, expected.experiment, expected.run_id, expected.nonce)
    request = expected.request_message.as_dict()
    fields.update({k: request[k] for k in BINDINGS})
    # Structurally shaped ECCPUBLICBLOB, deliberately NOT a real cryptographic key proof.
    fields.update(request_sha256=h(expected.request),
                  public_key_blob_hex=(b"ECS1" + struct.pack("<I", 32) + bytes(range(64))).hex())
    return serialize_message(K.READY, fields)


def raw_queries():
    return [{"api": api, "level": level, "allocated_bytes": 8192,
             "raw_hex": (bytes([i + 1]) * 8192).hex()} for i, (api, level) in enumerate(QUERY_SHAPES)]


def config_fields(expected):
    return {"service_type": 16, "start_type": 3, "error_control": 0,
            "binary_path": '"' + expected.request_message.as_dict()["guard"]["guest_path"] + '"',
            "account": ACCOUNT, "display_name": SERVICE_NAME, "dependencies": [],
            "load_order_group": "", "tag_id": 0, "failure_actions": [], "failure_command": "",
            "reboot_message": "", "trigger_count": 0, "delayed_auto_start": 0, "launch_protected": 0,
            "sid_type": 0, "required_privileges": [], "failure_noncrash": 0,
            "security_sha256": h(b"model-security-descriptor")}


def status_bytes(values=REFUSAL):
    return struct.pack("<9I", *(tuple(values) + (1234, 0))).hex()


def normal_rows(expected):
    if expected.experiment is ModelExperiment.BENIGN:
        return [("BEGIN", {}), ("BENIGN_COMPLETED", {}), ("FINAL", {"result": ModelResult.BENIGN.value})]
    owned = "3" * 32
    cfg = {"owned_handle_id": owned, "config": config_fields(expected), "raw_queries": raw_queries()}
    status = {"owned_handle_id": owned, "raw_hex": status_bytes()}
    return [
        ("BEGIN", {}), ("INITIAL_NAME_PROBE", {"ok": False, "winerror": 1060}),
        ("CREATE_INTENT", {"attempt": 1}),
        ("CREATE_RESULT", {"ok": True, "winerror": 0, "owned_handle_id": owned}),
        ("PRESTART_CONFIG", cfg),
        ("PRESTART_STATUS", {"owned_handle_id": owned, "raw_hex": status_bytes((16, 1, 0, 0, 0, 0, 0))}),
        ("START_INTENT", {"attempt": 1, "owned_handle_id": owned}),
        ("START_RESULT", {"ok": True, "winerror": 0, "owned_handle_id": owned}),
        ("STATUS", status), ("CLEANUP_CONFIG", cfg), ("CLEANUP_STATUS", status),
        ("DELETE_INTENT", {"attempt": 1, "owned_handle_id": owned}),
        ("DELETE_RESULT", {"ok": True, "winerror": 0, "owned_handle_id": owned}),
        ("CLOSE_SERVICES", {"ok": True, "owned_handle_id": owned}),
        ("ABSENCE_PROBE", {"ok": False, "winerror": 1060}), ("CLOSE_ALL", {"ok": True}),
        ("FINAL", {"result": ModelResult.REFUSAL.value}),
    ]


def journal_bytes(expected, rows=None):
    result = []
    for index, (event, data) in enumerate(normal_rows(expected) if rows is None else rows, 1):
        row = common_fields(K.JOURNAL, expected.experiment, expected.run_id, expected.nonce)
        row.update(sequence=index, guest_monotonic_ns=index, event=event, data=data)
        result.append(serialize_message(K.JOURNAL, row))
    return b"".join(result)


def model_bundle(expected=None, rows=None):
    expected = expected or expectation()
    ready = ready_bytes(expected)
    pin = pin_ready_model(expected, ready)
    auth, commit = authorization_bytes_model(pin)
    journal = journal_bytes(expected, rows)
    trace = validate_scm_trace_model(journal, expected)
    assert trace.valid, trace.reasons
    fields = common_fields(K.TERMINAL, expected.experiment, expected.run_id, expected.nonce)
    fields.update({k: expected.request_message.as_dict()[k] for k in BINDINGS})
    fields.update(request_sha256=h(expected.request), ready_sha256=h(ready),
                  public_key_sha256=pin.public_key_sha256, session_binding_sha256=expected.session_binding_sha256,
                  authorization_sha256=h(auth), authorization_commit_sha256=h(commit),
                  journal={"bytes": len(journal), "sha256": h(journal), "records": trace.records},
                  result=trace.result.value, attempts=dict(trace.attempts),
                  service_absence_observed=trace.service_absence_observed,
                  guard_process_exit_claimed=False, guest_retirement_claimed=False,
                  crypto_verified=False, runtime_authorized=False)
    terminal = serialize_message(K.TERMINAL, fields)
    signature = bytes(range(64))  # Fake model data, never a generated or verified signature.
    artifacts = tuple(ArtifactBytes(name, data) for name, data in
                      (("ready.json", ready), ("journal.jsonl", journal), ("terminal.json", terminal), ("terminal.sig", signature)))
    snapshot = TranscriptBytes(auth, commit, artifacts, artifacts)
    crypto = ModelCryptoObservation(True, SIGNING_DOMAIN, h(SIGNING_DOMAIN + terminal),
                                    pin.public_key_sha256, h(signature))
    retirement = ModelRetirementObservation(expected.session_binding_sha256, True, False, False)
    return pin, snapshot, ModelObservations(crypto, retirement)


class ContractTests(unittest.TestCase):
    def test_CON01_roundtrip(self):
        for mode in ModelExperiment:
            exp = expectation(mode)
            pin, snapshot, _ = model_bundle(exp)
            cases = ((K.REQUEST, exp.request), (K.READY, pin.ready_bytes),
                     (K.AUTHORIZATION, snapshot.authorization), (K.COMMIT, snapshot.authorization_commit),
                     (K.TERMINAL, dict((x.name, x.data) for x in snapshot.before_retirement)["terminal.json"]))
            for kind, raw in cases:
                with self.subTest(mode=mode, kind=kind):
                    parsed = parse_message(kind, raw)
                    self.assertEqual(serialize_message(kind, parsed.as_dict()), raw)
                    with self.assertRaises((FrozenInstanceError, TypeError)):
                        parsed.fields.items_tuple = ()

    def test_CON02_duplicates(self):
        raw = expectation().request
        for altered in (raw.replace(b'"version":1', b'"version":1,"version":1'),
                        raw.replace(b'"create":0', b'"create":0,"create":0')):
            with self.assertRaisesRegex(CoreError, "duplicate"):
                parse_message(K.REQUEST, altered)

    def test_CON03_field_sets(self):
        base = request_fields()
        for field in list(base):
            with self.subTest(missing=field), self.assertRaises(CoreError):
                obj = dict(base); del obj[field]
                parse_message(K.REQUEST, unsafe_json(obj))
        for key, value in (("approved", True), ("action", "LaunchSandbox"), ("extra", {})):
            with self.subTest(extra=key), self.assertRaises(CoreError):
                parse_message(K.REQUEST, unsafe_json({**base, key: value}))

    def test_CON04_sorted_recursive_and_array_order(self):
        obj = {"z": {"z": 2, "a": 1}, "a": [3, 1, 2]}
        self.assertEqual(canonical_json_bytes(obj), b'{"a":[3,1,2],"z":{"a":1,"z":2}}\n')
        obj = request_fields()
        raw = (json.dumps(obj, sort_keys=False, separators=(",", ":")) + "\n").encode()
        with self.assertRaisesRegex(CoreError, "noncanonical"):
            parse_message(K.REQUEST, raw)

    def test_CON05_encoding_surrogates(self):
        raw = expectation().request
        for bad in (b"\xef\xbb\xbf" + raw, raw.replace(b"SCM01-WSB01", b"\xff"),
                    raw.replace(b'"version":1', b'"version":"\\ud800"'),
                    raw.replace(b'"version":1', b'"version":"\\x41"')):
            with self.subTest(bad=bad[:20]), self.assertRaises(CoreError):
                parse_message(K.REQUEST, bad)
        self.assertEqual(parse_json_bytes(canonical_json_bytes({"v": "🙂"}), 100), {"v": "🙂"})
        with self.assertRaises(CoreError):
            canonical_json_bytes({"bad": "\udfff"})

    def test_CON06_numbers(self):
        for value in (True, 1.0, float("nan"), float("inf"), -(10 ** 21), 10 ** 21):
            with self.subTest(value=value), self.assertRaises(CoreError):
                obj = request_fields(); obj["version"] = value
                parse_message(K.REQUEST, unsafe_json(obj))
        for literal in (b"NaN", b"Infinity", b"-Infinity", b"1e0", b"-0"):
            with self.subTest(literal=literal), self.assertRaises(CoreError):
                parse_message(K.REQUEST, expectation().request.replace(b'"version":1', b'"version":' + literal))
        obj = request_fields(); obj["budget"]["create"] = False
        with self.assertRaises(CoreError):
            parse_message(K.REQUEST, unsafe_json(obj))

    def test_CON07_depth_allocation(self):
        with self.assertRaisesRegex(CoreError, "depth"):
            parse_json_bytes(b"[" * 17 + b"0" + b"]" * 17 + b"\n", 100)
        with self.assertRaisesRegex(CoreError, "fields_limit"):
            parse_json_bytes(unsafe_json({str(i): i for i in range(65)}), 10000)
        with self.assertRaisesRegex(CoreError, "array_limit"):
            parse_json_bytes(unsafe_json([0] * 2049), 10000)
        with self.assertRaisesRegex(CoreError, "string_limit"):
            parse_json_bytes(unsafe_json({"v": "a" * 32769}), 40000)

    def test_CON08_final_lf(self):
        raw = expectation().request
        for bad in (raw[:-1], raw + b"\n", raw[:-1] + b"\r\n", raw[:-1] + b" \n"):
            with self.subTest(tail=bad[-10:]), self.assertRaises(CoreError):
                parse_message(K.REQUEST, bad)

    def test_CON09_realistic_config_buffer(self):
        expected = expectation(ModelExperiment.SCM_REFUSAL)
        raw = journal_bytes(expected).splitlines(keepends=True)[4]
        data = parse_message(K.JOURNAL, raw).as_dict()["data"]
        self.assertEqual(sum(len(q["raw_hex"]) for q in data["raw_queries"]), 147456)
        self.assertLess(len(raw), 262144)
        self.assertGreater(len(raw), 147456)
        self.assertEqual(serialize_message(K.JOURNAL, parse_message(K.JOURNAL, raw).as_dict()), raw)
        self.assertTrue(validate_scm_trace_model(journal_bytes(expected), expected).successful)

    def test_CON10_oversize(self):
        expected = expectation()
        with self.assertRaises(CoreError):
            parse_message(K.REQUEST, b" " * 32769)
        for bad in (b"x" * (DEFAULT_POLICY.journal_bytes + 1), b"x" * 262144 + b"\n",
                    b"{}\n" * 2049):
            with self.subTest(size=len(bad)), self.assertRaises(CoreError):
                tuple(parse_journal_model(bad))
        pin, snap, obs = model_bundle(expected)
        entries = tuple(replace(x, data=b"x" * (16777216 + 1)) if x.name == "journal.jsonl" else x
                        for x in snap.before_retirement)
        self.assertFalse(validate_transcript_model(pin, replace(snap, before_retirement=entries), obs).valid)

    def test_REG01_policy_cannot_widen(self):
        with self.assertRaises(CoreError):
            parse_message(K.REQUEST, expectation().request, replace(DEFAULT_POLICY, request_bytes=65536))

    def test_REG02_model_only_schema(self):
        obj = request_fields(); obj["evidence_domain"] = "LIVE_GUEST"
        with self.assertRaises(CoreError):
            parse_message(K.REQUEST, unsafe_json(obj))
        obj = request_fields(); obj["guard"] = {"bytes": 882176, "sha256": "0" * 64}
        with self.assertRaises(CoreError):
            serialize_message(K.REQUEST, obj)

    def test_REG03_no_mutable_aliases(self):
        obj = request_fields()
        msg = parse_message(K.REQUEST, serialize_message(K.REQUEST, obj))
        obj["budget"]["create"] = 1
        copied = msg.as_dict(); copied["budget"]["create"] = 1
        self.assertEqual(msg.fields["budget"]["create"], 0)
        with self.assertRaises(TypeError):
            msg.fields["budget"]["create"] = 9

    def test_REG11_huge_python_integer_bounded_before_string_conversion(self):
        with self.assertRaisesRegex(CoreError, "integer_digits"):
            canonical_json_bytes({"integer": 1 << 20000})

    def test_REG12_exact_input_types(self):
        for raw in (bytearray(expectation().request), memoryview(expectation().request), expectation().request.decode()):
            with self.subTest(type=type(raw)), self.assertRaises(CoreError):
                parse_message(K.REQUEST, raw)
