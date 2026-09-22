"""Bounded canonical model messages. No I/O, clocks, keys or native dependencies."""
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re
from .wsb01_policy import (CoreError, CorePolicy, DEFAULT_POLICY, DOMAIN, PROFILE,
                          SCHEMA, ModelExperiment, ModelResult, ModelOnly, need,
                          budget, guard_descriptor, policy_sha256, validate_policy)


class MessageKind(str, Enum):
    REQUEST = "request"
    READY = "ready"
    AUTHORIZATION = "authorization_spec"
    COMMIT = "authorization_commit"
    TERMINAL = "terminal"
    FAILURE = "failure"
    JOURNAL = "journal_record"


COMMON = ("schema", "version", "kind", "profile", "evidence_domain", "experiment", "run_id", "nonce")
BINDINGS = ("policy_sha256", "schema_sha256", "source_sha256", "runtime_sha256",
            "payload_sha256", "layout_sha256")
EXTRA = {
    "request": BINDINGS + ("guard", "budget"),
    "ready": BINDINGS + ("request_sha256", "public_key_blob_hex"),
    "authorization_spec": ("request_sha256", "ready_sha256", "public_key_sha256",
                           "session_binding_sha256", "budget"),
    "authorization_commit": ("authorization_sha256",),
    "terminal": BINDINGS + ("request_sha256", "ready_sha256", "public_key_sha256",
                            "session_binding_sha256", "authorization_sha256",
                            "authorization_commit_sha256", "journal", "result", "attempts",
                            "service_absence_observed", "guard_process_exit_claimed",
                            "guest_retirement_claimed", "crypto_verified", "runtime_authorized"),
    "failure": ("code", "message", "runtime_authorized"),
    "journal_record": ("sequence", "guest_monotonic_ns", "event", "data"),
}
EVENT_DATA_FIELDS = {
    "BEGIN": (), "BENIGN_COMPLETED": (),
    "INITIAL_NAME_PROBE": ("ok", "winerror"),
    "CREATE_INTENT": ("attempt",),
    "CREATE_RESULT": ("ok", "winerror", "owned_handle_id"),
    "PRESTART_CONFIG": ("owned_handle_id", "config", "raw_queries"),
    "PRESTART_STATUS": ("owned_handle_id", "raw_hex"),
    "START_INTENT": ("attempt", "owned_handle_id"),
    "START_RESULT": ("ok", "winerror", "owned_handle_id"),
    "STATUS": ("owned_handle_id", "raw_hex"),
    "CLEANUP_CONFIG": ("owned_handle_id", "config", "raw_queries"),
    "CLEANUP_STATUS": ("owned_handle_id", "raw_hex"),
    "DELETE_INTENT": ("attempt", "owned_handle_id"),
    "DELETE_RESULT": ("ok", "winerror", "owned_handle_id"),
    "CLOSE_SERVICES": ("ok", "owned_handle_id"),
    "ABSENCE_PROBE": ("ok", "winerror"), "CLOSE_ALL": ("ok",),
    "ERROR": ("code",), "FINAL": ("result",),
}
CONFIG_FIELDS = ("service_type", "start_type", "error_control", "binary_path", "account",
                 "display_name", "dependencies", "load_order_group", "tag_id", "failure_actions",
                 "failure_command", "reboot_message", "trigger_count", "delayed_auto_start",
                 "launch_protected", "sid_type", "required_privileges", "failure_noncrash",
                 "security_sha256")
CONFIG_INTS = ("service_type", "start_type", "error_control", "tag_id", "trigger_count",
               "delayed_auto_start", "launch_protected", "sid_type", "failure_noncrash")
QUERY_SHAPES = (("QueryServiceConfigW", None),) + tuple(
    ("QueryServiceConfig2W", level) for level in (2, 3, 4, 5, 6, 8, 12)
) + (("QueryServiceObjectSecurity", 7),)


def _canonical_unchecked(value) -> bytes:
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("ascii")


def protocol_definition() -> dict:
    return {"schema": SCHEMA, "version": 1, "profile": PROFILE, "evidence_domain": DOMAIN,
            "message_fields": {k: sorted(COMMON + v) for k, v in EXTRA.items()},
            "journal_event_fields": {k: sorted(v) for k, v in EVENT_DATA_FIELDS.items()},
            "config_fields": sorted(CONFIG_FIELDS),
            "raw_query_fields": ["allocated_bytes", "api", "level", "raw_hex"],
            "query_shapes": [[a, b] for a, b in QUERY_SHAPES],
            "policy_sha256": policy_sha256(),
            "serializer": "ensure_ascii=True; sort_keys=True recursively; compact; exactly one LF",
            "message_byte_limits": {k.value: message_limit(k, DEFAULT_POLICY) for k in MessageKind},
            "parser_limits": {"depth": 16, "fields_per_object": 64, "string_characters": 32768,
                              "array_items": 2048, "integer_decimal_digits": 20},
            "journal_limits": {"bytes": 8388608, "records": 2048, "record_bytes": 262144},
            "scalar_rules": {"run_id": "lowercase_hex_32", "nonce": "lowercase_hex_64",
                             "sha256": "lowercase_hex_64", "booleans": "exact_bool_not_int",
                             "dword": "exact_int_0_to_4294967295", "ticks": "exact_uint64",
                             "version": "exact_int_1", "guard": "null_in_benign_exact_V3_in_scm"},
            "model_result_by_experiment": {"benign_model": "MODEL_BENIGN_TRACE_VALID",
                                           "scm_refusal_model": "MODEL_SCM_REFUSAL_TRACE_VALID"},
            "failure_result": "MODEL_FAILURE_TRACE_VALID",
            "output_required": ["ready.json", "journal.jsonl", "terminal.json", "terminal.sig"],
            "failure_file_blocks_success": True,
            "signature": {"size_bytes": 64, "public_key_blob_bytes": 72,
                          "public_key_header_hex": "4543533120000000",
                          "domain_hex": "534b594e455456532f53434d30312d57534230312f4f46464c494e455f4d4f44454c2f5445524d494e414c2f563100",
                          "signed_message": "domain_bytes + exact_terminal_bytes",
                          "verification": "model observation only; no cryptographic verification"},
            "raw_configuration": "nine opaque 8192-byte buffers; typed model claims not native pointer decoding",
            "failure_trace": "explicit ERROR then FINAL; no further model SCM mutation",
            "compatibility": "new model format; not legacy SCM01 journal or V1B4 protocol",
            "hash_graph": ["request", "ready", "authorization_spec", "authorization_commit",
                           "journal", "terminal", "detached_signature"],
            "runtime_authorized": False}


def schema_sha256() -> str:
    return hashlib.sha256(_canonical_unchecked(protocol_definition())).hexdigest()


def hex_string(value, chars, label):
    need(type(value) is str and len(value) == chars and
         re.fullmatch(r"[0-9a-f]+", value) is not None, label)


def uint(value, bits=64, label="unsigned_integer"):
    need(type(value) is int and 0 <= value < (1 << bits), label)


def exact_fields(obj, keys, label="fields_invalid"):
    need(type(obj) is dict and set(obj) == set(keys), label)


def _shape(value, policy, depth=0):
    need(depth <= policy.json_max_depth, "json_depth")
    t = type(value)
    if t is dict:
        need(len(value) <= policy.json_fields_per_object, "json_fields_limit")
        for k, v in value.items():
            need(type(k) is str, "json_key_type")
            _shape(k, policy, depth + 1)
            _shape(v, policy, depth + 1)
    elif t in (list, tuple):
        need(t is list, "json_array_type")
        need(len(value) <= policy.json_array_items, "json_array_limit")
        for v in value:
            _shape(v, policy, depth + 1)
    elif t is str:
        need(len(value) <= policy.json_max_string_characters, "json_string_limit")
        need(not any(0xD800 <= ord(c) <= 0xDFFF for c in value), "json_surrogate")
    elif t is int:
        need(abs(value) < 10 ** policy.json_max_integer_digits, "json_integer_digits")
    else:
        need(t is bool or value is None, "json_type")


def canonical_json_bytes(value, policy=DEFAULT_POLICY):
    validate_policy(policy)
    _shape(value, policy)
    return _canonical_unchecked(value)


def _reject_number(_value):
    raise CoreError("json_noninteger")


def _pairs(rows):
    result = {}
    for k, v in rows:
        need(k not in result, "json_duplicate_key")
        result[k] = v
    return result


def _pre_scan(raw, policy):
    # Bound recursive parser depth before json.loads, respecting escaped quotes.
    quoted = escaped = False
    depth = 0
    for ch in raw:
        if quoted:
            if escaped:
                escaped = False
            elif ch == 92:
                escaped = True
            elif ch == 34:
                quoted = False
        elif ch == 34:
            quoted = True
        elif ch in (123, 91):
            depth += 1
            need(depth <= policy.json_max_depth, "json_depth")
        elif ch in (125, 93):
            depth -= 1
            need(depth >= 0, "json_unbalanced")
    need(not quoted and not escaped and depth == 0, "json_unbalanced")


def parse_json_bytes(raw, limit, policy=DEFAULT_POLICY):
    validate_policy(policy)
    need(type(raw) is bytes, "raw_bytes_type")
    need(0 < len(raw) <= limit, "raw_size_limit")
    need(raw.endswith(b"\n") and not raw.endswith(b"\n\n"), "json_final_lf")
    need(not raw.startswith(b"\xef\xbb\xbf") and b"\r" not in raw, "json_bom_or_crlf")
    _pre_scan(raw, policy)

    def integer(text):
        need(len(text.lstrip("-")) <= policy.json_max_integer_digits, "json_integer_digits")
        return int(text)
    try:
        value = json.loads(raw.decode("ascii"), object_pairs_hook=_pairs,
                           parse_int=integer, parse_float=_reject_number,
                           parse_constant=_reject_number)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise CoreError("json_encoding_or_syntax") from exc
    _shape(value, policy)
    need(raw == _canonical_unchecked(value), "json_noncanonical")
    return value


@dataclass(frozen=True)
class FrozenObject(Mapping):
    items_tuple: tuple

    def __getitem__(self, key):
        for k, v in self.items_tuple:
            if k == key:
                return v
        raise KeyError(key)

    def __iter__(self):
        return (k for k, _ in self.items_tuple)

    def __len__(self):
        return len(self.items_tuple)


def _freeze(value):
    if type(value) is dict:
        return FrozenObject(tuple((k, _freeze(v)) for k, v in sorted(value.items())))
    if type(value) is list:
        return tuple(_freeze(v) for v in value)
    return value


def _thaw(value):
    if type(value) is FrozenObject:
        return {k: _thaw(v) for k, v in value.items_tuple}
    if type(value) is tuple:
        return [_thaw(v) for v in value]
    return value


@dataclass(frozen=True)
class FrozenMessage(ModelOnly):
    kind: MessageKind
    raw: bytes
    fields: FrozenObject

    @property
    def sha256(self):
        return hashlib.sha256(self.raw).hexdigest()

    def as_dict(self):
        return _thaw(self.fields)


def message_limit(kind, policy):
    return {MessageKind.REQUEST: policy.request_bytes, MessageKind.READY: policy.ready_bytes,
            MessageKind.AUTHORIZATION: policy.authorization_spec_bytes,
            MessageKind.COMMIT: policy.authorization_spec_bytes,
            MessageKind.TERMINAL: policy.terminal_bytes, MessageKind.FAILURE: policy.failure_bytes,
            MessageKind.JOURNAL: policy.journal_record_bytes}[kind]


def _budget_fields(value, experiment, exact_budget=True):
    expected = budget(experiment)
    exact_fields(value, expected, "budget_fields")
    for k, max_value in expected.items():
        need(type(value[k]) is int and 0 <= value[k] <= max_value, "budget_value:" + k)
    if exact_budget:
        need(value == expected, "budget_mode")


def _journal_data(event, data):
    need(type(event) is str and event in EVENT_DATA_FIELDS, "journal_event")
    exact_fields(data, EVENT_DATA_FIELDS[event], "journal_data_fields:" + event)
    for k in ("ok",):
        if k in data:
            need(type(data[k]) is bool, "journal_bool")
    if "winerror" in data:
        uint(data["winerror"], 32, "winerror")
    if "owned_handle_id" in data:
        if not (event == "CREATE_RESULT" and data["owned_handle_id"] is None):
            hex_string(data["owned_handle_id"], 32, "owned_handle_shape")
    if "attempt" in data:
        need(type(data["attempt"]) is int and data["attempt"] == 1, "attempt_one")
    if "raw_hex" in data:
        hex_string(data["raw_hex"], 72, "status_36_bytes")
    if event in ("PRESTART_CONFIG", "CLEANUP_CONFIG"):
        config = data["config"]
        exact_fields(config, CONFIG_FIELDS, "config_fields")
        for k in CONFIG_INTS:
            uint(config[k], 32, "config_integer:" + k)
        for k in ("dependencies", "failure_actions", "required_privileges"):
            need(type(config[k]) is list and all(type(x) is str for x in config[k]), "config_array:" + k)
        for k in set(CONFIG_FIELDS) - set(CONFIG_INTS) - {"dependencies", "failure_actions", "required_privileges"}:
            need(type(config[k]) is str, "config_string:" + k)
        hex_string(config["security_sha256"], 64, "config_security_sha256")
        queries = data["raw_queries"]
        need(type(queries) is list and len(queries) == 9, "nine_raw_queries")
        for query, (api, level) in zip(queries, QUERY_SHAPES):
            exact_fields(query, ("api", "level", "allocated_bytes", "raw_hex"), "query_fields")
            need(query["api"] == api and type(query["api"]) is str, "query_api")
            need(type(query["level"]) is type(level) and query["level"] == level, "query_level")
            need(type(query["allocated_bytes"]) is int and query["allocated_bytes"] == 8192, "query_capacity")
            hex_string(query["raw_hex"], 16384, "raw_query_8192_bytes")
    if event == "ERROR":
        need(type(data["code"]) is str and 1 <= len(data["code"]) <= 128, "error_code")
    if event == "FINAL":
        need(data["result"] in (ModelResult.BENIGN.value, ModelResult.REFUSAL.value,
                                ModelResult.FAILURE.value), "final_result")


def _validate_message(kind, obj):
    exact_fields(obj, COMMON + EXTRA[kind.value])
    need(obj["schema"] == SCHEMA and obj["profile"] == PROFILE, "schema_or_profile")
    need(type(obj["version"]) is int and obj["version"] == 1, "version")
    need(obj["kind"] == kind.value and obj["evidence_domain"] == DOMAIN, "kind_or_domain")
    need(type(obj["experiment"]) is str and obj["experiment"] in tuple(x.value for x in ModelExperiment), "experiment")
    experiment = ModelExperiment(obj["experiment"])
    hex_string(obj["run_id"], 32, "run_id")
    hex_string(obj["nonce"], 64, "nonce")
    for key in obj:
        if key.endswith("_sha256"):
            hex_string(obj[key], 64, key)
    if "policy_sha256" in obj:
        need(obj["policy_sha256"] == policy_sha256(), "policy_binding")
    if "schema_sha256" in obj:
        need(obj["schema_sha256"] == schema_sha256(), "schema_binding")
    if kind is MessageKind.REQUEST:
        expected = guard_descriptor(experiment, obj["run_id"])
        if expected is None:
            need(obj["guard"] is None, "benign_guard_forbidden")
        else:
            exact_fields(obj["guard"], expected, "guard_fields")
            need(type(obj["guard"]["bytes"]) is int and obj["guard"] == expected, "immutable_guard")
        _budget_fields(obj["budget"], experiment)
    elif kind is MessageKind.READY:
        hex_string(obj["public_key_blob_hex"], 144, "public_key_72_bytes")
        need(obj["public_key_blob_hex"].startswith("4543533120000000"), "public_key_header_shape")
    elif kind is MessageKind.AUTHORIZATION:
        _budget_fields(obj["budget"], experiment)
    elif kind is MessageKind.TERMINAL:
        exact_fields(obj["journal"], ("bytes", "sha256", "records"), "journal_identity")
        for k, maximum in (("bytes", DEFAULT_POLICY.journal_bytes), ("records", DEFAULT_POLICY.journal_records)):
            need(type(obj["journal"][k]) is int and 0 < obj["journal"][k] <= maximum, "journal_identity_limit")
        hex_string(obj["journal"]["sha256"], 64, "journal_sha256")
        _budget_fields(obj["attempts"], experiment, exact_budget=False)
        need(obj["result"] in (ModelResult.BENIGN.value, ModelResult.REFUSAL.value, ModelResult.FAILURE.value), "terminal_result")
        need(type(obj["service_absence_observed"]) is bool, "absence_type")
        for k in ("guard_process_exit_claimed", "guest_retirement_claimed", "runtime_authorized", "crypto_verified"):
            need(obj[k] is False, "forbidden_claim:" + k)
    elif kind is MessageKind.FAILURE:
        need(type(obj["code"]) is str and 1 <= len(obj["code"]) <= 128, "failure_code")
        need(type(obj["message"]) is str and obj["runtime_authorized"] is False, "failure_fields")
    elif kind is MessageKind.JOURNAL:
        need(type(obj["sequence"]) is int and 1 <= obj["sequence"] <= DEFAULT_POLICY.journal_records, "journal_sequence_range")
        uint(obj["guest_monotonic_ns"], label="guest_monotonic_ns")
        _journal_data(obj["event"], obj["data"])


def parse_message(kind, raw: bytes, policy: CorePolicy = DEFAULT_POLICY) -> FrozenMessage:
    need(type(kind) is MessageKind, "message_kind_type")
    value = parse_json_bytes(raw, message_limit(kind, policy), policy)
    _validate_message(kind, value)
    return FrozenMessage(kind, raw, _freeze(value))


def serialize_message(kind, fields, policy: CorePolicy = DEFAULT_POLICY) -> bytes:
    need(type(kind) is MessageKind, "message_kind_type")
    raw = canonical_json_bytes(fields, policy)
    return parse_message(kind, raw, policy).raw


def common_fields(kind, experiment, run_id, nonce):
    need(type(kind) is MessageKind and type(experiment) is ModelExperiment, "common_enum_type")
    return {"schema": SCHEMA, "version": 1, "kind": kind.value, "profile": PROFILE,
            "evidence_domain": DOMAIN, "experiment": experiment.value,
            "run_id": run_id, "nonce": nonce}
