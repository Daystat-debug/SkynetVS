"""Fixed OFFLINE_MODEL policy. No Windows calls, configuration reads or authority."""
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib
import json

PROFILE = "SCM01-WSB01"
SCHEMA = "SKYNETVS_SCM01_WSB01_CLOSED_CORE_V1"
DOMAIN = "OFFLINE_MODEL"
GUARD_BYTES = 882176
GUARD_SHA256 = "66736793b396c1c5682ce149df199db34d63499c916d299aa6106f11b3f68fdb"
SERVICE_NAME = "SkynetVSGuard"
ACCOUNT = "NT SERVICE\\SkynetVSGuard"
REFUSAL = (16, 1, 0, 1066, 78, 0, 0)
SIGNING_DOMAIN = b"SKYNETVS/SCM01-WSB01/OFFLINE_MODEL/TERMINAL/V1\x00"
SUCCESS_NAMES = ("ready.json", "journal.jsonl", "terminal.json", "terminal.sig")
ALLOWED_NAMES = SUCCESS_NAMES + ("failure.json",)


class CoreError(ValueError):
    """Rejected model data; never a request to repair or retry a live operation."""


class ModelExperiment(str, Enum):
    BENIGN = "benign_model"
    SCM_REFUSAL = "scm_refusal_model"


class ModelResult(str, Enum):
    BENIGN = "MODEL_BENIGN_TRACE_VALID"
    REFUSAL = "MODEL_SCM_REFUSAL_TRACE_VALID"
    FAILURE = "MODEL_FAILURE_TRACE_VALID"
    INVALID = "MODEL_TRACE_INVALID"


@dataclass(frozen=True)
class CorePolicy:
    request_bytes: int = 32768
    ready_bytes: int = 65536
    authorization_spec_bytes: int = 16384
    terminal_bytes: int = 1048576
    journal_bytes: int = 8388608
    journal_record_bytes: int = 262144
    journal_records: int = 2048
    failure_bytes: int = 65536
    signature_bytes: int = 64
    public_key_blob_bytes: int = 72
    accepted_raw_bytes: int = 16777216
    json_max_depth: int = 16
    json_fields_per_object: int = 64
    json_max_string_characters: int = 32768
    json_array_items: int = 2048
    json_max_integer_digits: int = 20


DEFAULT_POLICY = CorePolicy()


def need(condition: bool, code: str) -> None:
    if not condition:
        raise CoreError(code)


def validate_policy(policy: CorePolicy) -> None:
    need(type(policy) is CorePolicy, "policy_type")
    # This version has one fixed protocol, not a runtime policy-override facility.
    for key, value in asdict(DEFAULT_POLICY).items():
        actual = getattr(policy, key)
        need(type(actual) is int and actual == value, "policy_fixed:" + key)


def budget(experiment: ModelExperiment) -> dict:
    need(type(experiment) is ModelExperiment, "experiment_type")
    n = 0 if experiment is ModelExperiment.BENIGN else 1
    return {"create": n, "start": n, "delete": n,
            "control_service": 0, "manual_guard_spawn": 0}


def guard_descriptor(experiment: ModelExperiment, run_id: str):
    if experiment is ModelExperiment.BENIGN:
        return None
    return {"bytes": GUARD_BYTES, "sha256": GUARD_SHA256,
            "guest_path": "C:\\SkynetVSLab\\" + run_id + "\\Guard.exe"}


def policy_definition(policy: CorePolicy = DEFAULT_POLICY) -> dict:
    validate_policy(policy)
    return {"schema": SCHEMA, "profile": PROFILE, "evidence_domain": DOMAIN,
            "limits": asdict(policy), "output_names": list(ALLOWED_NAMES),
            "required_success_names": list(SUCCESS_NAMES),
            "budgets": {m.value: budget(m) for m in ModelExperiment},
            "runtime_authorized": False, "disk_quota_claimed": False}


def policy_sha256(policy: CorePolicy = DEFAULT_POLICY) -> str:
    raw = (json.dumps(policy_definition(policy), ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False) + "\n").encode("ascii")
    return hashlib.sha256(raw).hexdigest()


class ModelOnly:
    """Labels, not an in-process security boundary or OS attestation."""
    __slots__ = ()

    @property
    def evidence_domain(self):
        return DOMAIN

    @property
    def runtime_authorized(self):
        return False

    @property
    def crypto_verified(self):
        return False
