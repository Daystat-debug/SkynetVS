"""In-memory model transcript checks. No CNG default, native API or file reader."""
from dataclasses import dataclass
import hashlib
import struct
from .wsb01_policy import (CoreError, DEFAULT_POLICY, ModelOnly, ModelExperiment, ModelResult,
                          SIGNING_DOMAIN, SUCCESS_NAMES, REFUSAL, SERVICE_NAME, ACCOUNT,
                          need, budget)
from .wsb01_contract import (MessageKind, parse_message, serialize_message, common_fields,
                            canonical_json_bytes, BINDINGS)
from .wsb01_ports import (RunExpectation, ArtifactBytes, TranscriptBytes, ModelObservations,
                         ModelCryptoObservation, ModelRetirementObservation)


def sha256(raw):
    need(type(raw) is bytes, "hash_bytes")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class ModelPin(ModelOnly):
    expected: RunExpectation
    ready_bytes: bytes
    ready_sha256: str
    public_key_sha256: str


@dataclass(frozen=True)
class ModelScmTraceCheck(ModelOnly):
    result: ModelResult
    reasons: tuple[str, ...]
    records: int = 0
    attempts: tuple[tuple[str, int], ...] = ()
    service_absence_observed: bool = False

    @property
    def valid(self):
        return self.result is not ModelResult.INVALID

    @property
    def successful(self):
        return self.result in (ModelResult.BENIGN, ModelResult.REFUSAL)


@dataclass(frozen=True)
class ModelTranscriptCheck(ModelOnly):
    result: ModelResult
    reasons: tuple[str, ...]
    terminal_sha256: str | None = None
    journal_records: int = 0

    @property
    def valid(self):
        return self.result is not ModelResult.INVALID

    @property
    def successful(self):
        return self.result in (ModelResult.BENIGN, ModelResult.REFUSAL)


def _expectation(expected):
    need(type(expected) is RunExpectation, "run_expectation_type")
    expected.__post_init__()
    return expected.request_message.as_dict()


def _identity(obj, request):
    for key in ("schema", "version", "profile", "evidence_domain", "experiment", "run_id", "nonce"):
        need(type(obj[key]) is type(request[key]) and obj[key] == request[key], "binding:" + key)
    for key in BINDINGS:
        if key in obj:
            need(obj[key] == request[key], "binding:" + key)


def pin_ready_model(expected: RunExpectation, ready: bytes) -> ModelPin:
    request = _expectation(expected)
    parsed = parse_message(MessageKind.READY, ready).as_dict()
    _identity(parsed, request)
    need(parsed["request_sha256"] == sha256(expected.request), "ready_request_binding")
    key = bytes.fromhex(parsed["public_key_blob_hex"])
    return ModelPin(expected, ready, sha256(ready), sha256(key))


def authorization_bytes_model(pin: ModelPin) -> tuple[bytes, bytes]:
    """Serialize OFFLINE_MODEL data only. Not a live permit or physical publication."""
    need(type(pin) is ModelPin, "model_pin_type")
    need(pin == pin_ready_model(pin.expected, pin.ready_bytes), "pin_modified")
    expected = pin.expected
    fields = common_fields(MessageKind.AUTHORIZATION, expected.experiment, expected.run_id, expected.nonce)
    fields.update(request_sha256=sha256(expected.request), ready_sha256=pin.ready_sha256,
                  public_key_sha256=pin.public_key_sha256,
                  session_binding_sha256=expected.session_binding_sha256,
                  budget=budget(expected.experiment))
    authorization = serialize_message(MessageKind.AUTHORIZATION, fields)
    commit = common_fields(MessageKind.COMMIT, expected.experiment, expected.run_id, expected.nonce)
    commit["authorization_sha256"] = sha256(authorization)
    return authorization, serialize_message(MessageKind.COMMIT, commit)


def parse_journal_model(journal: bytes):
    policy = DEFAULT_POLICY
    need(type(journal) is bytes and 0 < len(journal) <= policy.journal_bytes, "journal_bytes_limit")
    need(journal.endswith(b"\n"), "journal_partial_record")
    count = journal.count(b"\n")
    need(0 < count <= policy.journal_records, "journal_records_limit")
    offset = 0
    while offset < len(journal):
        end = journal.find(b"\n", offset)
        need(end >= 0, "journal_partial_record")
        size = end + 1 - offset
        need(1 < size <= policy.journal_record_bytes, "journal_record_bytes_limit")
        yield parse_message(MessageKind.JOURNAL, journal[offset:end + 1]).as_dict()
        offset = end + 1


def _status(data):
    # A raw 36-byte model observation. PID/service flags are retained but never used as handles.
    raw = bytes.fromhex(data["raw_hex"])
    need(len(raw) == 36, "status_length")
    return struct.unpack("<9I", raw)


def _config_valid(config, request):
    expected = {"service_type": 16, "start_type": 3, "error_control": 0,
                "binary_path": '"' + request["guard"]["guest_path"] + '"',
                "account": ACCOUNT, "display_name": SERVICE_NAME, "dependencies": [],
                "load_order_group": "", "tag_id": 0, "failure_actions": [], "failure_command": "",
                "reboot_message": "", "trigger_count": 0, "delayed_auto_start": 0, "launch_protected": 0}
    return all(type(config[k]) is type(v) and config[k] == v for k, v in expected.items()) and config["failure_noncrash"] in (0, 1)


def validate_scm_trace_model(journal: bytes, expected: RunExpectation) -> ModelScmTraceCheck:
    """Validate a *new model format*, not the legacy SCM01 native journal format.

    Explicit failure traces may end with ERROR/FINAL without a mutation retry.
    Semantic refusal (existing service, wrong config/status) requires ERROR next.
    No mutation is allowed after ERROR. Failure cleanup remains a separate host-model
    observation, not synthetic success. Raw config buffers stay opaque (no pointer replay).
    """
    try:
        request = _expectation(expected)
        phase = "BEGIN"
        owned = None
        original_config = None
        attempts = {k: 0 for k in budget(expected.experiment)}
        absence = False
        failed = False
        record_count = 0
        last_guest_tick = -1
        status_polls = absence_polls = 0
        result = ModelResult.INVALID
        for row in parse_journal_model(journal):
            record_count += 1
            _identity(row, request)
            need(row["sequence"] == record_count, "journal_sequence")
            need(row["guest_monotonic_ns"] >= last_guest_tick, "journal_guest_time_order")
            last_guest_tick = row["guest_monotonic_ns"]
            event, data = row["event"], row["data"]
            need(phase != "DONE", "journal_after_final")
            if event == "ERROR":
                need(phase not in ("BEGIN", "FAILURE_FINAL"), "journal_error_order")
                failed = True
                phase = "FAILURE_FINAL"
                continue
            if phase == "FAILURE_FINAL":
                need(event == "FINAL" and data["result"] == ModelResult.FAILURE.value, "failure_final_required")
                result = ModelResult.FAILURE
                phase = "DONE"
                continue
            need(phase != "EXPECT_ERROR", "refused_observation_requires_error")
            need(event == phase, "journal_order:" + phase + ":" + event)
            if event == "BEGIN":
                phase = "BENIGN_COMPLETED" if expected.experiment is ModelExperiment.BENIGN else "INITIAL_NAME_PROBE"
            elif event == "BENIGN_COMPLETED":
                phase = "FINAL"
            elif event == "INITIAL_NAME_PROBE":
                phase = "CREATE_INTENT" if not data["ok"] and data["winerror"] == 1060 else "EXPECT_ERROR"
            elif event.endswith("_INTENT"):
                op = event.split("_")[0].lower()
                need(op in ("create", "start", "delete"), "mutation_operation")
                need(attempts[op] == 0 and budget(expected.experiment)[op] == 1, "mutation_budget")
                if op != "create":
                    need(owned is not None and data["owned_handle_id"] == owned, "mutation_owned_handle")
                attempts[op] = 1  # Never decremented by ERROR/failure processing.
                phase = event.replace("_INTENT", "_RESULT")
            elif event in ("CREATE_RESULT", "START_RESULT", "DELETE_RESULT"):
                if event == "CREATE_RESULT":
                    if data["ok"] and data["winerror"] == 0 and data["owned_handle_id"] is not None:
                        owned = data["owned_handle_id"]
                        phase = "PRESTART_CONFIG"
                    else:
                        need(not data["ok"] and data["owned_handle_id"] is None, "create_ownership_ambiguous")
                        phase = "EXPECT_ERROR"
                else:
                    need(data["owned_handle_id"] == owned, "result_owned_handle")
                    if not data["ok"] or data["winerror"] != 0:
                        phase = "EXPECT_ERROR"
                    else:
                        phase = "STATUS" if event == "START_RESULT" else "CLOSE_SERVICES"
            elif event in ("PRESTART_CONFIG", "CLEANUP_CONFIG"):
                need(owned is not None and data["owned_handle_id"] == owned, "config_owned_handle")
                config = data["config"]
                valid = _config_valid(config, request)
                if event == "PRESTART_CONFIG":
                    if valid:
                        original_config = canonical_json_bytes(config)
                    phase = "PRESTART_STATUS" if valid else "EXPECT_ERROR"
                else:
                    valid = valid and original_config is not None and canonical_json_bytes(config) == original_config
                    phase = "CLEANUP_STATUS" if valid else "EXPECT_ERROR"
            elif event in ("PRESTART_STATUS", "STATUS", "CLEANUP_STATUS"):
                need(owned is not None and data["owned_handle_id"] == owned, "status_owned_handle")
                status = _status(data)
                if event == "PRESTART_STATUS":
                    phase = "START_INTENT" if status[:3] == (16, 1, 0) and status[:7] != REFUSAL else "EXPECT_ERROR"
                elif event == "CLEANUP_STATUS":
                    phase = "DELETE_INTENT" if status[:3] == (16, 1, 0) else "EXPECT_ERROR"
                else:
                    status_polls += 1
                    need(status_polls <= 301, "status_poll_limit")
                    if status[:7] == REFUSAL:
                        phase = "CLEANUP_CONFIG"
                    elif status[:3] == (16, 2, 0):
                        phase = "STATUS"
                    else:
                        phase = "EXPECT_ERROR"
            elif event == "CLOSE_SERVICES":
                need(data["owned_handle_id"] == owned, "close_owned_handle")
                phase = "ABSENCE_PROBE" if data["ok"] else "EXPECT_ERROR"
            elif event == "ABSENCE_PROBE":
                absence_polls += 1
                need(absence_polls <= 101, "absence_poll_limit")
                if not data["ok"] and data["winerror"] == 1060:
                    absence = True
                    phase = "CLOSE_ALL"
                elif (not data["ok"] and data["winerror"] == 1072) or (data["ok"] and data["winerror"] == 0):
                    phase = "ABSENCE_PROBE"
                else:
                    phase = "EXPECT_ERROR"
            elif event == "CLOSE_ALL":
                phase = "FINAL" if data["ok"] else "EXPECT_ERROR"
            elif event == "FINAL":
                result = ModelResult.BENIGN if expected.experiment is ModelExperiment.BENIGN else ModelResult.REFUSAL
                need(data["result"] == result.value and not failed, "final_result_mode")
                need(attempts == budget(expected.experiment), "final_attempts")
                need(expected.experiment is ModelExperiment.BENIGN or absence, "final_absence")
                phase = "DONE"
        need(phase == "DONE", "journal_incomplete")
        return ModelScmTraceCheck(result, (), record_count, tuple(sorted(attempts.items())), absence)
    except CoreError as exc:
        return ModelScmTraceCheck(ModelResult.INVALID, (str(exc),))


def _artifact_map(entries):
    need(type(entries) is tuple and len(entries) == 4, "snapshot_exact_four_files")
    limits = {"ready.json": DEFAULT_POLICY.ready_bytes, "journal.jsonl": DEFAULT_POLICY.journal_bytes,
              "terminal.json": DEFAULT_POLICY.terminal_bytes, "terminal.sig": DEFAULT_POLICY.signature_bytes}
    result = {}
    total = 0
    for entry in entries:
        need(type(entry) is ArtifactBytes, "snapshot_entry_type")
        need(type(entry.name) is str and entry.name in SUCCESS_NAMES and entry.name not in result, "snapshot_name")
        need(type(entry.data) is bytes and 0 < len(entry.data) <= limits[entry.name], "snapshot_file_limit")
        total += len(entry.data)
        need(total <= DEFAULT_POLICY.accepted_raw_bytes, "snapshot_total_limit")
        if entry.name == "terminal.sig":
            need(len(entry.data) == 64, "signature_size")
        result[entry.name] = entry.data
    need(set(result) == set(SUCCESS_NAMES), "snapshot_names")
    return result


def _check_bundle(pin, authorization, authorization_commit, artifacts):
    need(type(pin) is ModelPin and pin == pin_ready_model(pin.expected, pin.ready_bytes), "pin_modified")
    request = _expectation(pin.expected)
    files = _artifact_map(artifacts)
    need(files["ready.json"] == pin.ready_bytes, "ready_mutated")
    expected_authorization, expected_commit = authorization_bytes_model(pin)
    # Parse separately so duplicate/noncanonical/oversized authorization is rejected.
    parse_message(MessageKind.AUTHORIZATION, authorization)
    parse_message(MessageKind.COMMIT, authorization_commit)
    need(authorization == expected_authorization, "authorization_binding")
    need(authorization_commit == expected_commit, "publication_commit_binding")
    terminal = parse_message(MessageKind.TERMINAL, files["terminal.json"]).as_dict()
    _identity(terminal, request)
    checks = {"request_sha256": sha256(pin.expected.request), "ready_sha256": pin.ready_sha256,
              "public_key_sha256": pin.public_key_sha256,
              "session_binding_sha256": pin.expected.session_binding_sha256,
              "authorization_sha256": sha256(authorization),
              "authorization_commit_sha256": sha256(authorization_commit)}
    for key, value in checks.items():
        need(terminal[key] == value, "terminal_binding:" + key)
    journal = files["journal.jsonl"]
    need(terminal["journal"]["bytes"] == len(journal) and terminal["journal"]["sha256"] == sha256(journal), "journal_hash_binding")
    trace = validate_scm_trace_model(journal, pin.expected)
    need(trace.valid, "journal_invalid:" + ",".join(trace.reasons))
    need(terminal["journal"]["records"] == trace.records, "journal_count_binding")
    need(terminal["result"] == trace.result.value and terminal["attempts"] == dict(trace.attempts), "terminal_trace_binding")
    need(terminal["service_absence_observed"] == trace.service_absence_observed, "terminal_absence_binding")
    return files, trace


def assert_pending_model(pin, authorization, authorization_commit, artifacts) -> None:
    """Structural check only: returns no success, signature or retirement receipt."""
    _check_bundle(pin, authorization, authorization_commit, artifacts)


def validate_transcript_model(pin: ModelPin, snapshot: TranscriptBytes,
                              observations: ModelObservations) -> ModelTranscriptCheck:
    try:
        need(type(snapshot) is TranscriptBytes and type(observations) is ModelObservations, "transcript_inputs_type")
        before, _ = _check_bundle(pin, snapshot.authorization, snapshot.authorization_commit, snapshot.before_retirement)
        after, trace = _check_bundle(pin, snapshot.authorization, snapshot.authorization_commit, snapshot.after_retirement)
        need(before == after, "post_exit_bytes_changed")
        retirement = observations.retirement
        need(type(retirement) is ModelRetirementObservation, "retirement_model_type")
        need(retirement.session_binding_sha256 == pin.expected.session_binding_sha256, "retirement_session")
        need(retirement.normal is True and retirement.forced is False and retirement.unknown is False, "normal_retirement_required")
        crypto = observations.crypto
        need(type(crypto) is ModelCryptoObservation, "crypto_model_type")
        need(crypto.claimed_valid is True and type(crypto.signing_domain) is bytes and
             crypto.signing_domain == SIGNING_DOMAIN, "model_signature_outcome_or_domain")
        need(crypto.signed_data_sha256 == sha256(SIGNING_DOMAIN + after["terminal.json"]), "signature_payload_binding")
        need(crypto.public_key_sha256 == pin.public_key_sha256 and
             crypto.signature_sha256 == sha256(after["terminal.sig"]), "signature_key_or_bytes_binding")
        return ModelTranscriptCheck(trace.result, (), sha256(after["terminal.json"]), trace.records)
    except CoreError as exc:
        return ModelTranscriptCheck(ModelResult.INVALID, (str(exc),))
