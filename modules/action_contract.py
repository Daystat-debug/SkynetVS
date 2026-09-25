"""HWA02-A data contracts. Data/fingerprints are never execution authority.

V1 deliberately supports bounded flat scalar arguments, not legacy command meta.
No runtime/host/native imports or implicit target resolution are performed here.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re

MAX_PARAMETERS = 32
MAX_TEXT_BYTES = 4096
MAX_DOCUMENT_BYTES = 32768
MIN_INTEGER = -(2 ** 63)
MAX_INTEGER = 2 ** 63 - 1
Scalar = str | int | bool | None
Parameters = tuple[tuple[str, Scalar], ...]


class ActionContractError(ValueError):
    """Stable non-sensitive contract error code; no raw argument rendering."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ActionContractError(code)


def _text(value: object, limit: int = MAX_TEXT_BYTES) -> None:
    require(type(value) is str, "text_type")
    try:
        encoded = value.encode("utf-8")
    except UnicodeError as exc:
        raise ActionContractError("text_unicode") from exc
    require(len(encoded) <= limit and "\x00" not in value, "text_bounds")


def _identifier(value: object, pattern: str) -> None:
    require(type(value) is str and re.fullmatch(pattern, value) is not None, "identifier")


def _integer(value: object, low: int, high: int) -> None:
    require(type(value) is int and low <= value <= high, "integer_bounds")


def _scalar(value: object) -> None:
    require(type(value) in (str, int, bool, type(None)), "scalar_type")
    if type(value) is str:
        _text(value)
    elif type(value) is int:
        _integer(value, MIN_INTEGER, MAX_INTEGER)


def validate_parameters(rows: object) -> Parameters:
    require(type(rows) is tuple and len(rows) <= MAX_PARAMETERS, "parameters_type_or_size")
    names = []
    for row in rows:
        require(type(row) is tuple and len(row) == 2, "parameter_row")
        key, value = row
        _identifier(key, r"[a-z][a-z0-9_]{0,63}")
        _scalar(value)
        names.append(key)
    require(names == sorted(set(names)), "parameters_order_or_duplicates")
    return rows


def parameters_from_dict(value: object) -> Parameters:
    require(type(value) is dict and len(value) <= MAX_PARAMETERS, "parameters_dict")
    for key in value:
        _identifier(key, r"[a-z][a-z0-9_]{0,63}")
    return validate_parameters(tuple((key, value[key]) for key in sorted(value)))


def canonical(document: dict) -> bytes:
    """For already validated contract documents only, not an untrusted-object gateway."""
    return json.dumps(document, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":"), allow_nan=False).encode("ascii")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _hex(value: object) -> None:
    _identifier(value, r"[0-9a-f]{64}")


def _unique_pairs(rows: list) -> dict:
    result = {}
    for key, value in rows:
        require(key not in result, "json_duplicate_key")
        result[key] = value
    return result


def _reject_number(_: str) -> None:
    raise ActionContractError("json_number")


def _parse_integer(value: str) -> int:
    require(len(value) <= 20, "json_integer_size")
    result = int(value)
    _integer(result, MIN_INTEGER, MAX_INTEGER)
    return result


def _decode(raw: object) -> dict:
    require(type(raw) is bytes and 0 < len(raw) <= MAX_DOCUMENT_BYTES, "json_size_or_type")
    # Bound nesting before the JSON parser; strings/escapes do not affect depth.
    depth = 0
    quoted = False
    escaped = False
    for byte in raw:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted = True
        elif byte in (91, 123):
            depth += 1
            require(depth <= 4, "json_depth")
        elif byte in (93, 125):
            depth -= 1
            require(depth >= 0, "json_depth")
    try:
        result = json.loads(raw.decode("ascii"), object_pairs_hook=_unique_pairs,
                            parse_int=_parse_integer, parse_float=_reject_number,
                            parse_constant=_reject_number)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ActionContractError("json_invalid") from exc
    require(type(result) is dict, "json_document")
    require(canonical(result) == raw, "json_noncanonical")
    return result


@dataclass(frozen=True, slots=True)
class ActionRequest:
    request_id: str
    scope_id: str
    action: str
    version: int
    parameters: Parameters = ()

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> ActionRequest:
        require(type(self) is ActionRequest, "request_exact_type")
        _identifier(self.request_id, r"[0-9a-f]{32}")
        _identifier(self.scope_id, r"[0-9a-f]{32}")
        _identifier(self.action, r"[A-Z][A-Z0-9_]{0,63}")
        _integer(self.version, 1, 65535)
        validate_parameters(self.parameters)
        require(len(canonical(self.document())) <= MAX_DOCUMENT_BYTES, "request_size")
        return self

    def document(self) -> dict:
        return {"schema": "HWA02_ACTION_REQUEST_V1", "request_id": self.request_id,
                "scope_id": self.scope_id, "action": self.action, "version": self.version,
                "parameters": dict(self.parameters)}

    def to_bytes(self) -> bytes:
        self.validate()
        return canonical(self.document())

    def fingerprint(self) -> str:
        return digest(self.to_bytes())

    @classmethod
    def from_bytes(cls, raw: bytes) -> ActionRequest:
        require(cls is ActionRequest, "request_exact_type")
        data = _decode(raw)
        require(set(data) == {"schema", "request_id", "scope_id", "action", "version", "parameters"}
                and data["schema"] == "HWA02_ACTION_REQUEST_V1", "request_schema")
        result = cls(data["request_id"], data["scope_id"], data["action"], data["version"],
                     parameters_from_dict(data["parameters"]))
        require(result.to_bytes() == raw, "request_noncanonical")
        return result


class ActionRiskClass(Enum):
    READ_ONLY = "READ_ONLY"
    REVERSIBLE = "REVERSIBLE"
    DESTRUCTIVE = "DESTRUCTIVE"


class ActionEffectClass(Enum):
    MEMORY = "MEMORY"
    HOST_UI = "HOST_UI"
    FILESYSTEM = "FILESYSTEM"
    NETWORK = "NETWORK"
    PROCESS = "PROCESS"


@dataclass(frozen=True, slots=True)
class ParameterRule:
    name: str
    kind: str
    required: bool = True
    max_bytes: int = MAX_TEXT_BYTES
    minimum: int = MIN_INTEGER
    maximum: int = MAX_INTEGER

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> ParameterRule:
        require(type(self) is ParameterRule, "rule_exact_type")
        _identifier(self.name, r"[a-z][a-z0-9_]{0,63}")
        require(type(self.kind) is str and self.kind in ("string", "integer", "boolean", "null"), "rule_kind")
        require(type(self.required) is bool, "rule_required")
        _integer(self.max_bytes, 0, MAX_TEXT_BYTES)
        _integer(self.minimum, MIN_INTEGER, MAX_INTEGER)
        _integer(self.maximum, self.minimum, MAX_INTEGER)
        return self

    def document(self) -> dict:
        return {"name": self.name, "kind": self.kind, "required": self.required,
                "max_bytes": self.max_bytes, "minimum": self.minimum, "maximum": self.maximum}

    def check(self, value: Scalar) -> None:
        expected = {"string": str, "integer": int, "boolean": bool, "null": type(None)}[self.kind]
        require(type(value) is expected, "parameter_type")
        if self.kind == "string":
            _text(value, self.max_bytes)
        elif self.kind == "integer":
            _integer(value, self.minimum, self.maximum)


@dataclass(frozen=True, slots=True)
class ActionSpec:
    action: str
    version: int
    executor_id: str
    policy_revision: str
    risk: ActionRiskClass
    effect: ActionEffectClass
    parameters: tuple[ParameterRule, ...] = ()
    max_grant_ms: int = 10000
    max_execution_ms: int = 1000

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> ActionSpec:
        require(type(self) is ActionSpec, "spec_exact_type")
        _identifier(self.action, r"[A-Z][A-Z0-9_]{0,63}")
        _integer(self.version, 1, 65535)
        _identifier(self.executor_id, r"[a-z][a-z0-9_.-]{0,63}")
        _identifier(self.policy_revision, r"[a-z0-9][a-z0-9_.-]{0,63}")
        require(type(self.risk) is ActionRiskClass and type(self.effect) is ActionEffectClass, "spec_classes")
        require(type(self.parameters) is tuple and len(self.parameters) <= MAX_PARAMETERS, "spec_parameters")
        names = []
        for item in self.parameters:
            require(type(item) is ParameterRule, "spec_rule_type")
            item.validate()
            names.append(item.name)
        require(names == sorted(set(names)), "spec_parameter_order_or_duplicates")
        _integer(self.max_grant_ms, 1, 60000)
        _integer(self.max_execution_ms, 1, 60000)
        return self

    def document(self) -> dict:
        self.validate()
        return {"schema": "HWA02_ACTION_SPEC_V1", "action": self.action, "version": self.version,
                "executor_id": self.executor_id, "policy_revision": self.policy_revision,
                "risk": self.risk.value, "effect": self.effect.value,
                "parameters": [p.document() for p in self.parameters],
                "max_grant_ms": self.max_grant_ms, "max_execution_ms": self.max_execution_ms}

    def fingerprint(self) -> str:
        return digest(canonical(self.document()))

    def check_request(self, request: ActionRequest) -> None:
        self.validate()
        require(type(request) is ActionRequest, "request_exact_type")
        request.validate()
        require((request.action, request.version) == (self.action, self.version), "action_not_registered")
        values = dict(request.parameters)
        require(set(values) <= {p.name for p in self.parameters}, "unknown_parameter")
        for rule in self.parameters:
            require(not rule.required or rule.name in values, "missing_parameter")
            if rule.name in values:
                rule.check(values[rule.name])


class ExecutorStatus(Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class ExecutorOutcome:
    status: ExecutorStatus
    output: Parameters = ()

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> ExecutorOutcome:
        require(type(self) is ExecutorOutcome and type(self.status) is ExecutorStatus, "outcome_type")
        validate_parameters(self.output)
        require(len(canonical(self.document())) <= MAX_DOCUMENT_BYTES, "outcome_size")
        return self

    def document(self) -> dict:
        return {"schema": "HWA02_EXECUTOR_OUTCOME_V1", "status": self.status.value, "output": dict(self.output)}

    def fingerprint(self) -> str:
        self.validate()
        return digest(canonical(self.document()))


class VerificationStatus(Enum):
    NOT_RUN = "NOT_RUN"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class ActionVerification:
    request_fingerprint: str
    policy_fingerprint: str
    outcome_fingerprint: str
    status: VerificationStatus

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> ActionVerification:
        require(type(self) is ActionVerification and type(self.status) is VerificationStatus, "verification_type")
        _hex(self.request_fingerprint)
        _hex(self.policy_fingerprint)
        _hex(self.outcome_fingerprint)
        return self


class ActionStatus(Enum):
    DENIED = "DENIED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class EffectState(Enum):
    NOT_STARTED = "NOT_STARTED"
    MAY_HAVE_OCCURRED = "MAY_HAVE_OCCURRED"
    VERIFIED = "VERIFIED"


@dataclass(frozen=True, slots=True)
class ActionResult:
    status: ActionStatus
    code: str
    request_fingerprint: str = ""
    policy_fingerprint: str = ""
    verification: VerificationStatus = VerificationStatus.NOT_RUN
    effect: EffectState = EffectState.NOT_STARTED
    output: Parameters = ()

    def __post_init__(self) -> None:
        require(type(self) is ActionResult and type(self.status) is ActionStatus, "result_type")
        require(type(self.verification) is VerificationStatus and type(self.effect) is EffectState, "result_classes")
        _identifier(self.code, r"[a-z][a-z0-9_]{0,63}")
        for value in (self.request_fingerprint, self.policy_fingerprint):
            require(type(value) is str, "result_fingerprint_type")
            if value != "":
                _hex(value)
        validate_parameters(self.output)
        if self.status is ActionStatus.DENIED:
            require(self.effect is EffectState.NOT_STARTED and self.verification is VerificationStatus.NOT_RUN
                    and self.output == (), "denied_invariants")
        elif self.status is ActionStatus.SUCCEEDED:
            require(self.verification is VerificationStatus.VERIFIED and self.effect is EffectState.VERIFIED,
                    "success_invariants")
            _hex(self.request_fingerprint)
            _hex(self.policy_fingerprint)
        else:
            require(self.effect is EffectState.MAY_HAVE_OCCURRED and self.output == (), "failure_invariants")
            _hex(self.request_fingerprint)
            _hex(self.policy_fingerprint)
            if self.status is ActionStatus.FAILED:
                require(self.verification is VerificationStatus.NOT_RUN, "failure_verification")
            else:
                require(self.verification is not VerificationStatus.VERIFIED, "unknown_verification")

    def document(self) -> dict:
        return {"schema": "HWA02_ACTION_RESULT_V1", "status": self.status.value, "code": self.code,
                "request_fingerprint": self.request_fingerprint, "policy_fingerprint": self.policy_fingerprint,
                "verification": self.verification.value, "effect": self.effect.value,
                "output": dict(self.output)}
