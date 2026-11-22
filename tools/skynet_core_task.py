"""Experimental explain_code coordinator. No source reader, provider or UI imports."""
from copy import deepcopy
from dataclasses import asdict, dataclass
from threading import Lock
from time import monotonic
from typing import NotRequired, TypedDict
from uuid import uuid4


@dataclass(frozen=True)
class TaskRequest:
    task_id: str
    kind: str
    question: str
    source_id: str


class EvidenceSet(TypedDict):
    task_id: str
    source_id: str
    snapshot_id: str
    coverage: str
    gaps: list
    items: list
    analysis: NotRequired[dict]  # This static adapter's evidence annotations.


class AnswerProposal(TypedDict):
    status: str
    claims: list
    reason: NotRequired[str]


class Rejected(ValueError):
    """A controlled host reason safe to return to the caller."""


class Task:
    def __init__(self, question, source_id, *, timeout=30):
        self.request = TaskRequest(uuid4().hex, "explain_code", question, source_id)
        self.deadline = monotonic() + timeout
        self.lock = Lock()
        self.stage = "accepted"
        self.result = None

    def _finish(self, state, **data):
        # Caller holds the same lock for cancellation, expiry and publication.
        if self.result is None:
            self.result = dict(task_request=asdict(self.request), state=state, stage=self.stage, **data)
        return self.result

    def cancel(self, task_id):
        with self.lock:
            if task_id != self.request.task_id or self.result is not None:
                return False
            self._finish("cancelled", reason="cancelled")
            return True

    def _active(self):
        if self.result is None and monotonic() >= self.deadline:
            self._finish("failed", reason="deadline")
        return self.result is None

    def _step(self, stage):
        with self.lock:
            if not self._active():
                return False
            if stage == "retrieval" and self.stage != "accepted":
                raise RuntimeError("Task is already running")
            self.stage = stage
            return True

    def run(self, retrieve, propose, verify):
        if not self._step("retrieval"):
            return self.result
        try:
            evidence = retrieve(self.request)
            if (evidence["task_id"], evidence["source_id"]) != (self.request.task_id, self.request.source_id):
                raise Rejected("evidence_binding")
            delivered = []
            if evidence["items"]:
                if not self._step("generation"):
                    return self.result
                packet = deepcopy(evidence)
                delivered = [item["ref_id"] for item in packet["items"]]
                proposal = propose(self.request, packet)
            else:
                reason = evidence["gaps"][0] if evidence["gaps"] else "no_evidence"
                proposal = AnswerProposal(status="insufficient", claims=[], reason=reason)
            if not self._step("verification"):
                return self.result
            assessment = verify(self.request, evidence, proposal, delivered)
            with self.lock:
                if self._active():
                    self._finish("answered" if proposal["status"] == "answer" else "insufficient",
                                 evidence_set=evidence, answer_proposal=deepcopy(proposal),
                                 delivered_ref_ids=delivered, assessment=assessment)
        except Exception as exc:
            with self.lock:
                if self._active():
                    self._finish("failed", reason=str(exc) if isinstance(exc, Rejected) else "stage_error")
        return self.result
