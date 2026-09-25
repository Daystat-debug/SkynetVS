"""HWA02-A process-local issuance and atomic single-use consumption.

Trusted composition retains ActionAuthority; command data and executors never
receive it. This is a cooperative Python boundary, NOT an OS sandbox. No module
singleton, environment switch, serialized permit or reusable native lease exists.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import threading
import time
import weakref

from modules.action_contract import ActionRequest, ActionSpec, require

MAX_PENDING_GRANTS = 128
MAX_ISSUED_REQUESTS = 4096
_NANOSECONDS_PER_MS = 1000000


class ActionAuthorityError(RuntimeError):
    """Stable refusal code without raw request/exception content."""


def _need(condition: bool, code: str) -> None:
    if not condition:
        raise ActionAuthorityError(code)


class _LocalOnly:
    __slots__ = ()

    def __copy__(self):
        raise TypeError("process_local_object")

    def __deepcopy__(self, memo):
        raise TypeError("process_local_object")

    def __reduce__(self):
        raise TypeError("process_local_object")

    def __reduce_ex__(self, protocol):
        raise TypeError("process_local_object")


class ActionGrant(_LocalOnly):
    """Opaque identity; only a live domain-ledger entry makes it usable."""
    __slots__ = ("__weakref__",)

    def __new__(cls):
        raise TypeError("grant_requires_issuer")

    def __init_subclass__(cls, **kwargs):
        raise TypeError("grant_subclass_forbidden")

    def __repr__(self) -> str:
        return "<ActionGrant process-local>"


@dataclass(frozen=True, slots=True)
class _Binding:
    spec: ActionSpec
    policy_fingerprint: str
    executor: object
    verifier: object
    execute: object
    verify: object


@dataclass(frozen=True, slots=True)
class _Claim:
    request_bytes: bytes
    request_fingerprint: str
    binding: _Binding
    issued_ns: int
    expires_ns: int


class _Domain:
    """One broker/issuer pair. Lock never encloses executor/verifier calls."""
    __slots__ = ("bindings", "broker", "pid", "lock", "grants", "issued", "closed", "last_ns")

    def __init__(self, bindings: tuple[_Binding, ...]) -> None:
        self.bindings = bindings
        self.broker = None
        self.pid = os.getpid()
        self.lock = threading.Lock()
        self.grants = weakref.WeakKeyDictionary()
        self.issued = set()
        self.closed = False
        self.last_ns = -1

    def _check_pid(self) -> None:
        # Check before lock: a forked child may inherit an acquired lock.
        _need(os.getpid() == self.pid, "foreign_process")

    def _time_locked(self) -> int:
        now = time.monotonic_ns()
        _need(type(now) is int and now >= 0 and now >= self.last_ns, "invalid_clock")
        self.last_ns = now
        return now

    def now(self) -> int:
        self._check_pid()
        with self.lock:
            return self._time_locked()

    def resolve(self, request: ActionRequest) -> _Binding:
        require(type(request) is ActionRequest, "request_exact_type")
        request.validate()
        for binding in self.bindings:
            if (request.action, request.version) == (binding.spec.action, binding.spec.version):
                binding.spec.check_request(request)
                _need(binding.spec.fingerprint() == binding.policy_fingerprint, "policy_changed")
                return binding
        raise ActionAuthorityError("action_not_registered")

    def claim(self, grant: object, broker: object) -> _Claim:
        self._check_pid()
        _need(type(grant) is ActionGrant, "grant_type")
        with self.lock:
            # Consume a recognised local grant even if following validation fails.
            claim = self.grants.pop(grant, None)
            _need(claim is not None, "grant_unavailable")
            _need(not self.closed, "authority_closed")
            _need(broker is self.broker, "wrong_broker")
            now = self._time_locked()
            _need(claim.issued_ns <= now < claim.expires_ns, "grant_expired")
            return claim

    def before_dispatch(self, claim: _Claim, broker: object) -> int:
        self._check_pid()
        with self.lock:
            _need(not self.closed, "authority_closed")
            _need(broker is self.broker, "wrong_broker")
            now = self._time_locked()
            _need(claim.issued_ns <= now < claim.expires_ns, "grant_expired")
            return min(claim.expires_ns, now + claim.binding.spec.max_execution_ms * _NANOSECONDS_PER_MS)

    def revoke(self, grant: object) -> bool:
        self._check_pid()
        _need(type(grant) is ActionGrant, "grant_type")
        with self.lock:
            return self.grants.pop(grant, None) is not None

    def close(self) -> None:
        self._check_pid()
        with self.lock:
            self.closed = True
            self.grants.clear()


class ActionAuthority(_LocalOnly):
    """Issuing role. Only the trusted composition root should hold this object."""
    __slots__ = ("_domain",)

    def __new__(cls):
        raise TypeError("authority_requires_composition")

    def __init_subclass__(cls, **kwargs):
        raise TypeError("authority_subclass_forbidden")

    def issue(self, request: ActionRequest, *, ttl_ms: int) -> ActionGrant:
        domain = self._domain
        domain._check_pid()
        binding = domain.resolve(request)
        _need(type(ttl_ms) is int and 1 <= ttl_ms <= binding.spec.max_grant_ms, "grant_ttl")
        request_bytes = request.to_bytes()
        fingerprint = request.fingerprint()
        key = (request.scope_id, request.request_id)
        with domain.lock:
            _need(not domain.closed, "authority_closed")
            now = domain._time_locked()
            # Expiry frees pending capacity, but never removes request tombstones.
            for token, claim in list(domain.grants.items()):
                if now >= claim.expires_ns:
                    domain.grants.pop(token, None)
            _need(key not in domain.issued, "request_already_issued")
            _need(len(domain.issued) < MAX_ISSUED_REQUESTS, "domain_capacity")
            _need(len(domain.grants) < MAX_PENDING_GRANTS, "pending_capacity")
            grant = object.__new__(ActionGrant)
            claim = _Claim(request_bytes, fingerprint, binding, now,
                           now + ttl_ms * _NANOSECONDS_PER_MS)
            domain.issued.add(key)
            domain.grants[grant] = claim
            return grant

    def revoke(self, grant: ActionGrant) -> bool:
        """Only pending grants can be revoked. A claimed operation is not cancelled."""
        return self._domain.revoke(grant)

    def close(self) -> None:
        """Stop future issues/claims; not a hard stop for in-flight callbacks."""
        self._domain.close()


def _issuer_for(domain: _Domain) -> ActionAuthority:
    authority = object.__new__(ActionAuthority)
    authority._domain = domain
    return authority
