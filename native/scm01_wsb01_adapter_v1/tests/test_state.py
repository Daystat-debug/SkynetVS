import unittest
from dataclasses import replace
from ..wsb01_policy import ModelExperiment as M, ModelResult as R
from ..wsb01_ports import (ModelEvent, ModelEventKind as E, ModelEffectKind as F,
                           PostExitModelData)
from ..wsb01_state import initial_model, reduce_model, ModelPhase
from .test_contract import model_bundle, expectation


def event(expected, kind, at_ns=20, payload=None):
    return ModelEvent(kind, at_ns, expected.run_id, expected.nonce, expected.experiment, payload)


def happy_sequence(expected):
    pin, snap, obs = model_bundle(expected)
    return [(E.INPUTS_VALIDATED, None), (E.RESERVATION_INTENT, None), (E.RESERVATION_CONFIRMED, None),
            (E.LAUNCH_INTENT, None), (E.SESSION_BOUND, expected.session_binding_sha256),
            (E.READY_RECEIVED, pin.ready_bytes), (E.AUTHORIZATION_INTENT, None),
            (E.AUTHORIZATION_PUBLISHED, snap.authorization_commit),
            (E.TERMINAL_RECEIVED, snap.before_retirement), (E.NORMAL_RETIREMENT, obs.retirement),
            (E.POST_EXIT_BYTES, PostExitModelData(snap.after_retirement, obs.crypto)), (E.FINALIZE, None)]


def drive(expected, sequence=None):
    state = initial_model(expected)
    effects = []
    for i, (kind, payload) in enumerate(happy_sequence(expected) if sequence is None else sequence):
        result = reduce_model(state, event(expected, kind, 20 + i, payload))
        state = result.state; effects.extend(result.planned_effects)
    return state, tuple(effects)


class StateTests(unittest.TestCase):
    def test_STA01_benign_success(self):
        state, effects = drive(expectation())
        self.assertEqual(state.phase, ModelPhase.MODEL_TRACE_VALID)
        self.assertEqual(state.result, R.BENIGN)
        self.assertFalse(state.runtime_authorized)
        self.assertFalse(state.crypto_verified)
        self.assertEqual([x.kind for x in effects].count(F.LAUNCH_SANDBOX), 1)
        self.assertEqual([x.kind for x in effects].count(F.PUBLISH_AUTHORIZATION), 1)
        self.assertTrue(all(x.evidence_domain == "OFFLINE_MODEL" for x in effects))

    def test_STA02_refusal_success(self):
        state, _ = drive(expectation(M.SCM_REFUSAL))
        self.assertEqual(state.phase, ModelPhase.MODEL_TRACE_VALID)
        self.assertEqual(state.result, R.REFUSAL)
        self.assertTrue(state.retirement_confirmed)
        self.assertFalse(state.transcript_check.runtime_authorized)

    def test_STA03_failed_consume(self):
        exp = expectation(); sequence = happy_sequence(exp)
        state, _ = drive(exp, sequence[:2])
        self.assertTrue(state.reservation_attempted)
        self.assertFalse(state.reservation_confirmed)
        state = reduce_model(state, event(exp, E.UNKNOWN, 50, "reservation_unknown")).state
        out = reduce_model(state, event(exp, E.LAUNCH_INTENT, 51))
        self.assertTrue(out.state.failure_sticky)
        self.assertFalse(out.state.launch_attempted)
        self.assertNotIn(F.LAUNCH_SANDBOX, [x.kind for x in out.planned_effects])

    def test_STA04_launch_failure(self):
        exp = expectation(); state, _ = drive(exp, happy_sequence(exp)[:4])
        self.assertTrue(state.launch_attempted)
        state = reduce_model(state, event(exp, E.FAILURE, 50, "launch_failed")).state
        out = reduce_model(state, event(exp, E.LAUNCH_INTENT, 51))
        self.assertTrue(out.state.launch_attempted)
        self.assertEqual(out.state.phase, ModelPhase.FAILED_ACTIVE_UNKNOWN)
        self.assertNotIn(F.LAUNCH_SANDBOX, [x.kind for x in out.planned_effects])

    def test_STA05_publication_consumed_before_attempt(self):
        exp = expectation(); state, _ = drive(exp, happy_sequence(exp)[:7])
        self.assertTrue(state.authorization_attempted)
        self.assertFalse(state.authorization_published)
        state = reduce_model(state, event(exp, E.UNKNOWN, 60, "publication_unknown")).state
        out = reduce_model(state, event(exp, E.AUTHORIZATION_INTENT, 61))
        self.assertTrue(out.state.authorization_attempted)
        self.assertNotIn(F.PUBLISH_AUTHORIZATION, [x.kind for x in out.planned_effects])
        self.assertFalse(out.state.authorization_published)

    def test_STA06_host_deadline(self):
        exp = expectation(); state = initial_model(exp)
        timed = reduce_model(state, event(exp, E.INPUTS_VALIDATED, exp.host_deadline_ns + 1))
        self.assertTrue(timed.state.failure_sticky)
        self.assertEqual(timed.state.reason, "host_deadline")
        state, _ = drive(exp, happy_sequence(exp)[:5])
        regressed = reduce_model(state, event(exp, E.TICK, 10))
        self.assertTrue(regressed.state.failure_sticky)
        bad = reduce_model(state, event(exp, E.TICK, True))
        self.assertTrue(bad.state.failure_sticky)

    def test_STA07_forced_cleanup_sticky(self):
        exp = expectation(); state, _ = drive(exp, happy_sequence(exp)[:9])
        _, _, obs = model_bundle(exp)
        forced = replace(obs.retirement, normal=False, forced=True)
        out = reduce_model(state, event(exp, E.FORCED_CLEANUP, 60, forced))
        self.assertTrue(out.state.failure_sticky)
        self.assertTrue(out.state.retirement_confirmed)
        self.assertEqual(out.state.phase, ModelPhase.FAILED_RETIRED)
        next_out = reduce_model(out.state, event(exp, E.FINALIZE, 61))
        self.assertNotIn(F.RECORD_MODEL_ACCEPTANCE, [x.kind for x in next_out.planned_effects])
        self.assertEqual(next_out.state.result, R.INVALID)

    def test_STA08_launcher_exit_not_session(self):
        exp = expectation(); state, _ = drive(exp, happy_sequence(exp)[:4])
        state = reduce_model(state, event(exp, E.LAUNCHER_EXITED, 40)).state
        self.assertTrue(state.launcher_exited)
        self.assertFalse(state.retirement_confirmed)
        self.assertEqual(state.phase, ModelPhase.LAUNCH_INTENT_RECORDED)
        _, _, obs = model_bundle(exp)
        out = reduce_model(state, event(exp, E.NORMAL_RETIREMENT, 41, obs.retirement))
        self.assertTrue(out.state.failure_sticky)
        self.assertFalse(out.state.retirement_confirmed)

    def test_STA09_unknown_retirement(self):
        exp = expectation(); state, _ = drive(exp, happy_sequence(exp)[:9])
        _, _, obs = model_bundle(exp)
        unknown = replace(obs.retirement, normal=False, unknown=True)
        state = reduce_model(state, event(exp, E.NORMAL_RETIREMENT, 70, unknown)).state
        self.assertEqual(state.phase, ModelPhase.FAILED_ACTIVE_UNKNOWN)
        out = reduce_model(state, event(exp, E.NORMAL_RETIREMENT, 71, obs.retirement))
        self.assertEqual(out.state.phase, ModelPhase.FAILED_RETIRED)
        self.assertTrue(out.state.failure_sticky)
        self.assertNotIn(F.RECORD_MODEL_ACCEPTANCE, [x.kind for x in out.planned_effects])

    def test_STA10_order_and_duplicates(self):
        exp = expectation(); sequence = happy_sequence(exp)
        for i in range(len(sequence)):
            state, _ = drive(exp, sequence[:i + 1])
            kind, payload = sequence[i]
            out = reduce_model(state, event(exp, kind, 100, payload))
            with self.subTest(kind=kind):
                self.assertTrue(out.state.failure_sticky)
                self.assertNotIn(F.RECORD_MODEL_ACCEPTANCE, [x.kind for x in out.planned_effects])
        state = initial_model(exp)
        self.assertTrue(reduce_model(state, event(exp, E.AUTHORIZATION_INTENT)).state.failure_sticky)

    def test_REG07_event_cross_scope(self):
        exp = expectation()
        e = event(exp, E.INPUTS_VALIDATED)
        for bad in (replace(e, run_id="0" * 32), replace(e, nonce="0" * 64),
                    replace(e, experiment=M.SCM_REFUSAL)):
            self.assertTrue(reduce_model(initial_model(exp), bad).state.failure_sticky)

    def test_REG08_cannot_publish_wrong_commit(self):
        exp = expectation(); state, _ = drive(exp, happy_sequence(exp)[:7])
        out = reduce_model(state, event(exp, E.AUTHORIZATION_PUBLISHED, 60, b"{}\n"))
        self.assertTrue(out.state.failure_sticky)
        self.assertTrue(out.state.authorization_attempted)
        self.assertFalse(out.state.authorization_published)

class Review107RegressionTests(unittest.TestCase):
    """Source-review regressions; supplied events remain OFFLINE_MODEL only."""

    def test_REG17_failure_terminal_is_immediately_sticky(self):
        for mode in M:
            with self.subTest(mode=mode):
                exp = expectation(mode)
                rows = [("BEGIN", {}), ("ERROR", {"code": "known_model_failure"}),
                        ("FINAL", {"result": R.FAILURE.value})]
                _, snap, _ = model_bundle(exp, rows)
                state, _ = drive(exp, happy_sequence(exp)[:8])
                out = reduce_model(state, event(exp, E.TERMINAL_RECEIVED, 100, snap.before_retirement))
                self.assertTrue(out.state.failure_sticky)
                self.assertEqual(out.state.phase, ModelPhase.FAILED_ACTIVE_UNKNOWN)
                self.assertEqual(out.state.reason, "terminal_reports_model_failure")
                self.assertEqual(out.state.pending_artifacts, snap.before_retirement)
                self.assertFalse(out.state.retirement_confirmed)
                self.assertEqual(out.state.result, R.INVALID)
                self.assertFalse(out.state.runtime_authorized)
                self.assertFalse(any(x.kind in (F.LAUNCH_SANDBOX, F.PUBLISH_AUTHORIZATION,
                                               F.RECORD_MODEL_ACCEPTANCE) for x in out.planned_effects))

    def test_REG18_late_normal_retirement_recorded_as_failure(self):
        for mode in M:
            with self.subTest(mode=mode):
                exp = expectation(mode)
                state, _ = drive(exp, happy_sequence(exp)[:9])
                _, _, obs = model_bundle(exp)
                out = reduce_model(state, event(exp, E.NORMAL_RETIREMENT,
                                               exp.host_deadline_ns + 1, obs.retirement))
                self.assertTrue(out.state.failure_sticky)
                self.assertTrue(out.state.retirement_confirmed)
                self.assertEqual(out.state.phase, ModelPhase.FAILED_RETIRED)
                self.assertFalse(out.state.forced_cleanup)
                self.assertEqual(out.state.reason, "host_deadline")
                self.assertEqual(out.state.result, R.INVALID)
                final = reduce_model(out.state, event(exp, E.FINALIZE, exp.host_deadline_ns + 2))
                self.assertTrue(final.state.failure_sticky)
                self.assertNotIn(F.RECORD_MODEL_ACCEPTANCE, [x.kind for x in final.planned_effects])

    def test_REG19_late_forced_retirement_recorded_as_failure(self):
        for mode in M:
            with self.subTest(mode=mode):
                exp = expectation(mode)
                state, _ = drive(exp, happy_sequence(exp)[:9])
                _, _, obs = model_bundle(exp)
                forced = replace(obs.retirement, normal=False, forced=True)
                out = reduce_model(state, event(exp, E.FORCED_CLEANUP,
                                               exp.host_deadline_ns + 1, forced))
                self.assertTrue(out.state.failure_sticky)
                self.assertTrue(out.state.forced_cleanup)
                self.assertTrue(out.state.retirement_confirmed)
                self.assertEqual(out.state.phase, ModelPhase.FAILED_RETIRED)
                self.assertEqual(out.state.result, R.INVALID)
                self.assertFalse(out.state.runtime_authorized)
                self.assertNotIn(F.RECORD_MODEL_ACCEPTANCE, [x.kind for x in out.planned_effects])

    def test_REG20_late_unbound_or_unknown_retirement_rejected(self):
        exp = expectation()
        state, _ = drive(exp, happy_sequence(exp)[:9])
        _, _, obs = model_bundle(exp)
        wrongs = (replace(obs.retirement, session_binding_sha256="0" * 64),
                  replace(obs.retirement, normal=False, unknown=True),
                  replace(obs.retirement, normal=1), None)
        for wrong in wrongs:
            with self.subTest(observation=wrong):
                out = reduce_model(state, event(exp, E.NORMAL_RETIREMENT,
                                               exp.host_deadline_ns + 1, wrong))
                self.assertTrue(out.state.failure_sticky)
                self.assertFalse(out.state.retirement_confirmed)
                self.assertEqual(out.state.phase, ModelPhase.FAILED_ACTIVE_UNKNOWN)
                self.assertNotIn(F.RECORD_MODEL_ACCEPTANCE, [x.kind for x in out.planned_effects])
        unbound, _ = drive(exp, happy_sequence(exp)[:4])
        out = reduce_model(unbound, event(exp, E.NORMAL_RETIREMENT,
                                         exp.host_deadline_ns + 1, obs.retirement))
        self.assertFalse(out.state.retirement_confirmed)
        self.assertTrue(out.state.failure_sticky)

    def test_REG21_failed_terminal_never_recovers_to_success(self):
        for mode in M:
            with self.subTest(mode=mode):
                exp = expectation(mode)
                rows = [("BEGIN", {}), ("ERROR", {"code": "known_model_failure"}),
                        ("FINAL", {"result": R.FAILURE.value})]
                _, snap, obs = model_bundle(exp, rows)
                state, _ = drive(exp, happy_sequence(exp)[:8])
                state = reduce_model(state, event(exp, E.TERMINAL_RECEIVED,
                                                 100, snap.before_retirement)).state
                steps = ((E.NORMAL_RETIREMENT, obs.retirement),
                         (E.POST_EXIT_BYTES, PostExitModelData(snap.after_retirement, obs.crypto)),
                         (E.FINALIZE, None), (E.AUTHORIZATION_INTENT, None), (E.LAUNCH_INTENT, None))
                for i, (kind, payload) in enumerate(steps, 101):
                    out = reduce_model(state, event(exp, kind, i, payload))
                    state = out.state
                    # Once valid retirement is observed, failure is still final.
                    self.assertTrue(state.failure_sticky)
                    self.assertTrue(state.retirement_confirmed)
                    self.assertEqual(state.phase, ModelPhase.FAILED_RETIRED)
                    self.assertEqual(state.result, R.INVALID)
                    self.assertFalse(any(x.kind in (F.LAUNCH_SANDBOX, F.PUBLISH_AUTHORIZATION,
                                                   F.RECORD_MODEL_ACCEPTANCE) for x in out.planned_effects))
