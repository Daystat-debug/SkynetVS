"""Immutable model inputs and effect descriptions. There is deliberately no executor."""
from dataclasses import dataclass
from enum import Enum
from .wsb01_policy import ModelOnly, ModelExperiment, need
from .wsb01_contract import MessageKind, parse_message, hex_string, uint


@dataclass(frozen=True)
class RunExpectation(ModelOnly):
    request: bytes
    session_binding_sha256: str
    host_started_ns: int
    host_deadline_ns: int

    def __post_init__(self):
        parse_message(MessageKind.REQUEST, self.request)
        hex_string(self.session_binding_sha256, 64, "session_binding_sha256")
        uint(self.host_started_ns, label="host_started_ns")
        uint(self.host_deadline_ns, label="host_deadline_ns")
        need(self.host_started_ns < self.host_deadline_ns, "model_deadline_order")

    @property
    def request_message(self):
        return parse_message(MessageKind.REQUEST, self.request)

    @property
    def experiment(self):
        return ModelExperiment(self.request_message.fields["experiment"])

    @property
    def run_id(self):
        return self.request_message.fields["run_id"]

    @property
    def nonce(self):
        return self.request_message.fields["nonce"]


@dataclass(frozen=True)
class ArtifactBytes:
    name: str
    data: bytes


@dataclass(frozen=True)
class TranscriptBytes:
    authorization: bytes
    authorization_commit: bytes
    before_retirement: tuple[ArtifactBytes, ...]
    after_retirement: tuple[ArtifactBytes, ...]


@dataclass(frozen=True)
class ModelCryptoObservation(ModelOnly):
    claimed_valid: bool
    signing_domain: bytes
    signed_data_sha256: str
    public_key_sha256: str
    signature_sha256: str


@dataclass(frozen=True)
class ModelRetirementObservation(ModelOnly):
    session_binding_sha256: str
    normal: bool
    forced: bool
    unknown: bool


@dataclass(frozen=True)
class ModelObservations(ModelOnly):
    crypto: ModelCryptoObservation
    retirement: ModelRetirementObservation


@dataclass(frozen=True)
class PostExitModelData:
    artifacts: tuple[ArtifactBytes, ...]
    crypto: ModelCryptoObservation


class ModelEventKind(str, Enum):
    INPUTS_VALIDATED = "INPUTS_VALIDATED"
    RESERVATION_INTENT = "RESERVATION_INTENT"
    RESERVATION_CONFIRMED = "RESERVATION_CONFIRMED"
    LAUNCH_INTENT = "LAUNCH_INTENT"
    SESSION_BOUND = "SESSION_BOUND"
    READY_RECEIVED = "READY_RECEIVED"
    AUTHORIZATION_INTENT = "AUTHORIZATION_INTENT"
    AUTHORIZATION_PUBLISHED = "AUTHORIZATION_PUBLISHED"
    TERMINAL_RECEIVED = "TERMINAL_RECEIVED"
    NORMAL_RETIREMENT = "NORMAL_RETIREMENT"
    POST_EXIT_BYTES = "POST_EXIT_BYTES"
    FINALIZE = "FINALIZE"
    FAILURE = "FAILURE"
    UNKNOWN = "UNKNOWN"
    FORCED_CLEANUP = "FORCED_CLEANUP"
    LAUNCHER_EXITED = "LAUNCHER_EXITED"
    TICK = "TICK"


@dataclass(frozen=True)
class ModelEvent(ModelOnly):
    kind: ModelEventKind
    at_ns: int
    run_id: str
    nonce: str
    experiment: ModelExperiment
    payload: object = None


class ModelEffectKind(str, Enum):
    RESERVE_HOST_MARKER = "PLAN_ONLY_RESERVE_HOST_MARKER"
    LAUNCH_SANDBOX = "PLAN_ONLY_LAUNCH_SANDBOX"
    PUBLISH_AUTHORIZATION = "PLAN_ONLY_PUBLISH_AUTHORIZATION"
    OBSERVE_RETIREMENT = "PLAN_ONLY_OBSERVE_RETIREMENT"
    PRESERVE_EVIDENCE = "PLAN_ONLY_PRESERVE_EVIDENCE"
    QUARANTINE_OUTPUT = "PLAN_ONLY_QUARANTINE_OUTPUT"
    RECORD_MODEL_ACCEPTANCE = "PLAN_ONLY_RECORD_MODEL_ACCEPTANCE"


@dataclass(frozen=True)
class PlannedEffect(ModelOnly):
    kind: ModelEffectKind
    run_id: str
    content_sha256: str | None = None
