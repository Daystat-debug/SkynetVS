"""SCM01 one-shot state machine, exercised only with fakes in this delivery.

No DLL loading/import occurs here. Production entrypoint and native constructor
remain closed. A future approved capsule runner is required to reach real SCM.
"""
from __future__ import annotations
from dataclasses import asdict
import time
from scm01_contract import (ContractError, LabCapsule, Reply, need, verify_config,
    prestart_status, terminal_decision, status_tuple, OBSERVE_SECONDS, DELETE_SECONDS,
    POLL_SECONDS, MAX_STATUS_POLLS, MAX_DELETE_POLLS)


class Clock:
    now = staticmethod(time.monotonic)
    sleep = staticmethod(time.sleep)


class Controller:
    def __init__(self, api, journal, clock=None):
        self.api, self.journal, self.clock = api, journal, clock or Clock()
        self.used = False
        self.budget = dict(create=0, start=0, delete=0)

    def _record_reply(self, op, reply):
        need(type(reply) is Reply, 'backend Reply required')
        self.journal.record(op + '_RESULT', ok=reply.ok, winerror=reply.winerror,
                            observation=reply.observation)
        return reply.check(op)

    def _mutate(self, op, call, retain=None):
        need(self.budget[op] == 0, op + ': one-shot budget exhausted')
        self.budget[op] = 1  # Never restored, even on intent-write or RPC failure.
        self.journal.record(op.upper() + '_INTENT', attempt=1)
        reply = call()
        # Ownership precedes any fallible serialization. Backend also tracks all handles.
        if retain is not None and type(reply) is Reply and reply.ok:
            retain(reply.value)
        return self._record_reply(op.upper(), reply)

    def run_once(self, capsule: LabCapsule):
        need(not self.used, 'controller instance already consumed')
        self.used = True
        capsule.validate_shape()
        out = {'kind': 'SCM01_OBSERVATION', 'result': 'SCM01_ERROR', 'run_id': capsule.run_id,
               'mutation_budget_claims': self.budget, 'terminal_refusal_observed': False,
               'service_absence_confirmed': False, 'process_exit_confirmed': False,
               'guest_retirement_confirmed': False, 'external_guest_recovery_required': True,
               'real_handler_accepted': False, 'full_transition_history_accepted': False,
               'production_callback_runtime_accepted': False, 'B02': 'NOT_ACCEPTED',
               'P00': 'NOT_ACCEPTED', 'P01': 'NOT_IMPLEMENTED', 'acquisition': 'BLOCKED',
               'native_factory_enabled': False, 'errors': [], 'cleanup_errors': []}
        manager = None
        owned = None
        original_config = None
        delete_succeeded = False

        def retain(h):
            nonlocal owned
            owned = h

        try:
            self.journal.record('BEGIN', capsule=asdict(capsule), runtime_authority_not_minted=True)
            manager = self._record_reply('OPEN_MANAGER', self.api.open_manager())
            probe = self.api.probe(manager)
            self.journal.record('INITIAL_NAME_PROBE', ok=probe.ok, winerror=probe.winerror, observation=probe.observation)
            need(not probe.ok and probe.winerror == 1060, 'name not proven absent; never adopt existing service')
            self._mutate('create', lambda: self.api.create_service(manager, capsule), retain)
            need(owned is not None, 'create returned no owned handle')
            original_config = self._record_reply('PRESTART_CONFIG', self.api.config(owned))
            verify_config(original_config, capsule)
            initial = self._record_reply('PRESTART_STATUS', self.api.status(owned))
            prestart_status(initial)
            # Capsule image binding is rechecked by the future external runtime issuer,
            # not implemented as trust in this source-only state machine.
            self._mutate('start', lambda: self.api.start_service(owned))
            deadline = self.clock.now() + OBSERVE_SECONDS
            for _ in range(MAX_STATUS_POLLS):
                need(self.clock.now() < deadline, 'status deadline; blocking RPC not forcibly cancelled')
                current = self._record_reply('STATUS', self.api.status(owned))
                need(self.clock.now() < deadline, 'status RPC returned after deadline')
                decision = terminal_decision(current)
                if decision == 'REFUSAL_OBSERVED':
                    out['terminal_refusal_observed'] = True
                    out['terminal'] = current
                    break
                self.clock.sleep(POLL_SECONDS)
            need(out['terminal_refusal_observed'], 'status poll budget exhausted')
        except BaseException as exc:
            out['errors'].append(type(exc).__name__ + ': ' + str(exc))
        finally:
            if owned is not None:
                try:
                    # No reopening by name and no deletion based on a display name/PID.
                    cfg = self._record_reply('CLEANUP_CONFIG', self.api.config(owned))
                    verify_config(cfg, capsule)
                    need(original_config is not None and cfg == original_config, 'config drift/unknown initial config: leave for guest recovery')
                    st = self._record_reply('CLEANUP_STATUS', self.api.status(owned))
                    need(status_tuple(st)[0:3] == (16, 1, 0), 'not stopped: no ControlService/taskkill; external guest recovery')
                    self._mutate('delete', lambda: self.api.delete_service(owned))
                    delete_succeeded = True
                except BaseException as exc:
                    out['cleanup_errors'].append(type(exc).__name__ + ': ' + str(exc))
            # Always attempt owned-handle closure even if journaling/config/RPC failed.
            try:
                closed = self.api.close_services()
                out['known_service_handles_closed'] = self._record_reply('CLOSE_SERVICES', closed) is True
            except BaseException as exc:
                out['known_service_handles_closed'] = False
                out['cleanup_errors'].append(type(exc).__name__ + ': ' + str(exc))
            if delete_succeeded and out.get('known_service_handles_closed') and manager is not None:
                try:
                    deadline = self.clock.now() + DELETE_SECONDS
                    for _ in range(MAX_DELETE_POLLS):
                        need(self.clock.now() < deadline, 'service deletion deadline')
                        r = self.api.probe(manager)
                        self.journal.record('ABSENCE_PROBE', ok=r.ok, winerror=r.winerror, observation=r.observation)
                        need(self.clock.now() < deadline, 'absence RPC returned after deadline')
                        if not r.ok and r.winerror == 1060:
                            out['service_absence_confirmed'] = True
                            break
                        need(r.ok or r.winerror == 1072, 'absence probe failed; not evidence of deletion')
                        self.clock.sleep(POLL_SECONDS)
                    need(out['service_absence_confirmed'], 'service deletion poll budget exhausted')
                except BaseException as exc:
                    out['cleanup_errors'].append(type(exc).__name__ + ': ' + str(exc))
            try:
                out['all_known_scm_handles_closed'] = self._record_reply('CLOSE_ALL', self.api.close_all()) is True
            except BaseException as exc:
                out['all_known_scm_handles_closed'] = False
                out['cleanup_errors'].append(type(exc).__name__ + ': ' + str(exc))
        if not out['errors'] and not out['cleanup_errors'] and out['terminal_refusal_observed'] and out['service_absence_confirmed']:
            out['result'] = 'SCM01_REFUSAL_OBSERVED_PENDING_GUEST_RETIREMENT_NOT_PRODUCTION'
        try:
            self.journal.record('FINAL', result=out)
        except BaseException as exc:
            out['errors'].append('final evidence unavailable: ' + type(exc).__name__ + ': ' + str(exc))
            out['result'] = 'SCM01_ERROR'
        return out
