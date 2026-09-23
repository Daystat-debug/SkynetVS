"""STATE01-08, including R107-style sticky failure and late retirement regressions."""
import unittest
from dataclasses import replace
from . import test_contract as f
from .. import benign_state as s
from ..benign_windows_session import RetirementObservation


def event(state, kind, payload=None, tick=None, session=None):
    return s.HostEvent(kind, state.last_ns + 1 if tick is None else tick,
                       state.run_id, state.nonce, state.boot_binding,
                       state.session_sha256 if session is None else session, payload)


def advance(state, kind, payload=None, tick=None, session=None):
    return s.transition_benign(state, event(state, kind, payload, tick, session)).state


def authorization_state():
    state = s.new_state(f.RID, f.NONCE, f.BOOT, 0)
    for kind in ('RESERVE', 'LAUNCH', 'BIND', 'READY', 'AUTH_INTENT', 'AUTH_PUBLISHED'):
        state = advance(state, kind, session=f.SESSION if kind == 'BIND' else None)
    return state


def retirement(state, forced=False, at=1_000_000_000):
    return RetirementObservation(state.run_id, state.nonce, state.boot_binding, state.session_sha256,
                                 not forced, forced, True, (at - 500_000_000, at - 250_000_000, at))


class StateTests(unittest.TestCase):
    def test_STATE01_ordered_trace(self):
        state = authorization_state(); self.assertFalse(state.failure_sticky)
        state = advance(state, 'TERMINAL', ('BENIGN_TASK_COMPLETED', 'a' * 64))
        state = advance(state, 'RETIRE', retirement(state), tick=1_000_000_000)
        state = advance(state, 'POSTEXIT', 'a' * 64); state = advance(state, 'RECORD')
        self.assertEqual(state.phase, 'RECORDED'); self.assertTrue(state.retired)

    def test_STATE02_failure_terminal_sticky(self):
        state = advance(authorization_state(), 'TERMINAL', ('BENIGN_TASK_FAILED', 'a' * 64))
        self.assertTrue(state.failure_sticky)
        state = advance(state, 'RETIRE', retirement(state), tick=1_000_000_000)
        self.assertTrue(state.retired); self.assertEqual(state.phase, 'FAILED_RETIRED')
        self.assertTrue(advance(state, 'RECORD').failure_sticky)

    def test_STATE03_late_retirement_is_retained_not_pass(self):
        state = advance(authorization_state(), 'TERMINAL', ('BENIGN_TASK_COMPLETED', 'a' * 64))
        at = state.phase_deadline_ns + 1
        state = advance(state, 'RETIRE', retirement(state, at=at), tick=at)
        self.assertTrue(state.failure_sticky); self.assertTrue(state.retired)
        self.assertEqual(state.reason, 'deadline')

    def test_STATE04_launcher_exit_is_not_retirement(self):
        state = advance(authorization_state(), 'LAUNCHER_EXITED')
        self.assertFalse(state.retired); self.assertEqual(state.phase, 'AUTH_PUBLISHED')
        self.assertTrue(advance(state, 'POSTEXIT', 'a' * 64).failure_sticky)

    def test_STATE05_forced_is_failure(self):
        state = advance(authorization_state(), 'TERMINAL', ('BENIGN_TASK_COMPLETED', 'a' * 64))
        state = advance(state, 'RETIRE', retirement(state, forced=True), tick=1_000_000_000)
        self.assertTrue(state.failure_sticky); self.assertTrue(state.forced); self.assertTrue(state.retired)

    def test_STATE06_cross_scope_clock_and_anchor(self):
        state = authorization_state(); valid = event(state, 'TICK')
        for field, value in (('run_id', 'a' * 32), ('nonce', 'a' * 64), ('boot_binding', 'a' * 64),
                             ('session_sha256', 'a' * 64), ('at_ns', 0)):
            with self.subTest(field=field):
                self.assertTrue(s.transition_benign(state, replace(valid, **{field: value})).state.failure_sticky)

    def test_STATE07_guest_tick_cannot_extend_deadline(self):
        state = authorization_state(); deadline = state.deadline_ns
        state = advance(state, 'TICK', tick=state.phase_deadline_ns + 1)
        self.assertTrue(state.failure_sticky); self.assertEqual(state.deadline_ns, deadline)
        state = advance(state, 'TICK', tick=deadline + 1)
        self.assertTrue(state.failure_sticky)

    def test_STATE08_no_relaunch_after_unknown(self):
        state = advance(authorization_state(), 'UNKNOWN')
        for kind in s.NORMAL:
            out = s.transition_benign(state, event(state, kind))
            with self.subTest(kind=kind):
                self.assertTrue(out.state.failure_sticky); self.assertEqual(out.effects, ())
                self.assertFalse(out.runtime_authorized)
