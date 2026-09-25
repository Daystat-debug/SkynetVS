"""Ownership capabilities for a trusted fixed controller, NOT isolation from hostile Python.
The private issuer is called by the explicit reviewed execution root only. Neither a
Plan, a saved PASS, a JSON object nor a child frame is an invocation of that root.
"""
import os
import threading
from .contract import Plan, Identity, ContractError, need, uint, STARTUP_NS

_ISSUER_KEY = object()


class LaunchLease:
    __slots__ = ('_owner', '_plan', '_identity', '_pid', '_issued', '_deadline',
                 '_last', '_consumed', '_claimed', '_lock')

    def __init__(self, key, owner, plan, identity, now_ns):
        need(key is _ISSUER_KEY, 'lease_private_issuer')
        need(type(plan) is Plan and type(identity) is Identity, 'lease_binding_types')
        self._owner = owner
        self._plan = plan.validate().fingerprint()
        self._identity = identity.validate()
        self._pid = os.getpid()
        uint(now_ns)
        self._issued = self._last = now_ns
        self._deadline = now_ns + STARTUP_NS
        self._consumed = False
        self._claimed = False
        self._lock = threading.Lock()

    def claim(self, owner, plan, identity, now_ns):
        # Consume BEFORE all fallible binding checks. A wrong claim poisons this lease.
        with self._lock:
            need(not self._consumed, 'lease_consumed')
            self._consumed = True
            uint(now_ns)
            need(self._last <= now_ns < self._deadline, 'lease_deadline')
            need(os.getpid() == self._pid, 'lease_process_changed')
            need(owner is self._owner, 'lease_owner_changed')
            need(type(plan) is Plan and plan.fingerprint() == self._plan, 'lease_plan_changed')
            need(type(identity) is Identity and identity == self._identity, 'lease_identity_changed')
            self._last = now_ns
            self._claimed = True
        # No serialized permit, secret or transferable handle returned.

    def require_claim(self, owner, plan, identity, now_ns):
        """Recheck a successfully consumed claim before the single creation effect."""
        with self._lock:
            need(self._claimed and self._consumed, 'lease_not_successfully_claimed')
            uint(now_ns)
            need(self._last <= now_ns < self._deadline, 'lease_claim_expired')
            need(os.getpid() == self._pid and owner is self._owner, 'lease_claim_owner')
            need(type(plan) is Plan and plan.fingerprint() == self._plan and
                 type(identity) is Identity and identity == self._identity, 'lease_claim_binding')
            self._last = now_ns

    def __copy__(self):
        raise ContractError('lease_not_copyable')

    def __deepcopy__(self, memo):
        raise ContractError('lease_not_copyable')

    def __reduce_ex__(self, protocol):
        raise ContractError('lease_not_serializable')


def _issue_at_reviewed_root(owner, plan, identity, now_ns):
    """Trusted root operation, NOT a public factory taking an 'approved' dictionary.
    The root verifies retained bytes and native self identity before invoking it.
    Fake-port tests may invoke this internal mechanism; this does not admit Win32.
    """
    return LaunchLease(_ISSUER_KEY, owner, plan, identity, now_ns)

_NATIVE_LOCK = threading.Lock()
_NATIVE_ENTERED = False


class _NativeRoot:
    __slots__ = ('_key', '_pid')

    def __init__(self, key):
        need(key is _ISSUER_KEY, 'native_root_private')
        self._key, self._pid = key, os.getpid()

    def require_current(self):
        need(self._key is _ISSUER_KEY and self._pid == os.getpid(), 'native_root_not_current')

    def __reduce_ex__(self, protocol):
        raise ContractError('root_not_serializable')

    def __copy__(self):
        raise ContractError('root_not_copyable')

    def __deepcopy__(self, memo):
        raise ContractError('root_not_copyable')


def _enter_explicit_native_root():
    """Only for the future explicitly authorized fixed controller process.
    No entrypoint in this source-preparation delivery calls this automatically.
    Once entered, even a failure cannot start another root in the same process.
    """
    global _NATIVE_ENTERED
    with _NATIVE_LOCK:
        need(not _NATIVE_ENTERED, 'native_root_once')
        _NATIVE_ENTERED = True
        return _NativeRoot(_ISSUER_KEY)
