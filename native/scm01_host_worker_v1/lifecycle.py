"""Deterministic observation/ordering model, not a native owner, issuer or sandbox.
A future native dispatcher must perform pre-effect checks before the corresponding
intent, then submit handle-derived observations. Caller dictionaries are not proof.
"""
from .contract import (ContractError, Plan, Identity, JobLimits, CREATE_FLAGS, TOTAL_NS,
                       STARTUP_NS, EXCHANGE_NS, CLEANUP_NS, need, uint)
from .protocol import decode, DIRECTIONS

ORDER = ('RESERVE', 'PINS_RETAINED', 'JOB_READY', 'CREATE_INTENT', 'CREATED_SUSPENDED_IN_JOB',
         'PRE_RESUME_VERIFIED', 'RESUME_INTENT', 'RESUMED', 'INIT_SENT', 'INIT_ACK',
         'PROBE_SENT', 'PROBE_REPLY', 'STOP_SENT', 'STOP_ACK', 'RETIRED',
         'IO_QUIESCENT', 'RESOURCES_RELEASED')


class Lifecycle:
    """Single-owner source model. All outputs remain SOURCE_MODEL / non-authorizing."""
    def __init__(self, plan: Plan, supervisor: Identity, now_ns: int):
        need(type(plan) is Plan and type(supervisor) is Identity, 'lifecycle_types')
        self.plan, self.supervisor = plan.validate(), supervisor.validate()
        self.started_ns = self.last_ns = uint(now_ns)
        self.deadline_ns = now_ns + TOTAL_NS
        self.step_deadline_ns = self.deadline_ns
        self.phase = 'PREPARED'
        self.position = 0
        self.child = None
        self.create_attempted = self.resume_attempted = False
        self.first_error = None
        self.failure_at_ns = None
        self.resolution = None
        self.trace = []

    @property
    def expected_event(self):
        if self.phase in ('FAILED', 'CLOSED'):
            return None
        return ORDER[self.position]

    def _clock(self, now_ns):
        uint(now_ns)
        need(now_ns >= self.last_ns, 'clock_regression')
        self.last_ns = now_ns
        need(now_ns < min(self.deadline_ns, self.step_deadline_ns), 'deadline_expired')

    def _same_peer(self, identity):
        need(type(identity) is Identity and self.child is not None, 'peer_type')
        identity.validate()
        need(identity == self.child, 'peer_identity_changed')

    def _first_peer(self, identity):
        need(type(identity) is Identity, 'peer_type')
        identity.validate()
        need(identity.pid != self.supervisor.pid, 'child_not_supervisor')
        need(identity.image.casefold() == self.plan.runtime.executable.path.casefold(), 'child_image')
        need((identity.session_id, identity.authentication_id, identity.user_sid) ==
             (self.supervisor.session_id, self.supervisor.authentication_id, self.supervisor.user_sid),
             'child_security_identity')
        self.child = identity

    @staticmethod
    def _keys(data, names):
        need(type(data) is dict and set(data) == set(names), 'event_schema')

    def observe(self, event: str, now_ns: int, data: dict | None = None) -> str:
        # Completed model records are immutable; a new call cannot erase the original result.
        need(self.phase not in ('CLOSED', 'FAILED'), 'lifecycle_terminal')
        data = {} if data is None else data
        try:
            self._clock(now_ns)
            need(type(event) is str and event == self.expected_event, 'event_order')
            if event in ('RESERVE', 'CREATE_INTENT', 'RESUME_INTENT'):
                self._keys(data, ())
                if event == 'CREATE_INTENT':
                    need(not self.create_attempted, 'create_consumed')
                    self.create_attempted = True
                elif event == 'RESUME_INTENT':
                    need(not self.resume_attempted, 'resume_consumed')
                    self.resume_attempted = True
                    self.step_deadline_ns = min(self.deadline_ns, now_ns + STARTUP_NS)
            elif event == 'PINS_RETAINED':
                self._keys(data, ('plan_sha256',))
                need(data['plan_sha256'] == self.plan.fingerprint(), 'retained_plan_mismatch')
            elif event == 'JOB_READY':
                self._keys(data, ('limits', 'members', 'complete'))
                need(type(data['limits']) is JobLimits, 'job_limits_type')
                data['limits'].validate()
                need(type(data['members']) is tuple and data['members'] == () and
                     data['complete'] is True, 'job_not_proven_empty')
            elif event == 'CREATED_SUSPENDED_IN_JOB':
                self._keys(data, ('identity', 'flags', 'job_list_applied'))
                need(type(data['flags']) is int and data['flags'] == CREATE_FLAGS, 'create_flags')
                need(data['job_list_applied'] is True, 'job_list_required_no_postcreate_fallback')
                self._first_peer(data['identity'])
            elif event == 'PRE_RESUME_VERIFIED':
                self._keys(data, ('identity', 'members', 'complete', 'limits', 'child_handle_roles',
                                  'parent_child_ends_closed', 'all_parent_handles_noninheritable',
                                  'program_pins_unchanged'))
                self._same_peer(data['identity'])
                need(type(data['members']) is tuple and all(type(p) is int for p in data['members']) and
                     data['members'] == (self.child.pid,) and data['complete'] is True, 'job_exact_child')
                need(type(data['limits']) is JobLimits, 'job_limits_type')
                data['limits'].validate()
                need(type(data['child_handle_roles']) is tuple and
                     data['child_handle_roles'] == ('stdin', 'stdout', 'stderr'), 'inheritance_roles')
                need(data['parent_child_ends_closed'] is True and
                     data['all_parent_handles_noninheritable'] is True, 'inheritance_restoration')
                need(data['program_pins_unchanged'] is True, 'program_changed_before_resume')
            elif event == 'RESUMED':
                self._keys(data, ('previous_suspend_count',))
                need(type(data['previous_suspend_count']) is int and
                     data['previous_suspend_count'] == 1, 'resume_count')
            elif event in ('INIT_SENT', 'PROBE_SENT', 'STOP_SENT'):
                self._keys(data, ('packet',))
                seq = {'INIT_SENT': 0, 'PROBE_SENT': 1, 'STOP_SENT': 2}[event]
                decode(self.plan, DIRECTIONS[0], seq, data['packet'])
                if seq:
                    self.step_deadline_ns = min(self.deadline_ns, now_ns + EXCHANGE_NS)
            elif event in ('INIT_ACK', 'PROBE_REPLY', 'STOP_ACK'):
                self._keys(data, ('packet', 'identity'))
                self._same_peer(data['identity'])
                seq = {'INIT_ACK': 0, 'PROBE_REPLY': 1, 'STOP_ACK': 2}[event]
                frame = decode(self.plan, DIRECTIONS[1], seq, data['packet'])
                if seq == 0:
                    need(frame['payload']['pid'] == self.child.pid and
                         frame['payload']['created'] == self.child.created, 'ack_not_owned_peer')
                    self.step_deadline_ns = self.deadline_ns
            elif event == 'RETIRED':
                self._keys(data, ('signaled', 'exit_code', 'members', 'complete'))
                need(data['signaled'] is True, 'exit_not_observed')
                need(type(data['exit_code']) is int and data['exit_code'] == 0, 'nonzero_exit')
                need(type(data['members']) is tuple and data['members'] == () and
                     data['complete'] is True, 'job_not_proven_retired')
            elif event == 'IO_QUIESCENT':
                self._keys(data, ('pending_io', 'threads_alive', 'stderr_bytes'))
                for key in data:
                    uint(data[key], 0)
            elif event == 'RESOURCES_RELEASED':
                self._keys(data, ('unreleased_handles', 'uncertain_closes', 'program_pins_unchanged'))
                uint(data['unreleased_handles'], 0)
                uint(data['uncertain_closes'], 0)
                need(data['program_pins_unchanged'] is True, 'program_changed')
            else:
                raise ContractError('unknown_event')
            self.position += 1
            self.phase = 'CLOSED' if self.position == len(ORDER) else event
            self.trace.append({'event': event, 'at_ns': now_ns, 'phase': self.phase})
            return self.phase
        except ContractError as exc:
            self.fail(str(exc), self.last_ns)
            raise

    def tick(self, now_ns: int) -> None:
        need(self.phase not in ('FAILED', 'CLOSED'), 'lifecycle_terminal')
        try:
            self._clock(now_ns)
        except ContractError as exc:
            self.fail(str(exc), self.last_ns)
            raise

    def fail(self, code: str, now_ns: int) -> None:
        need(self.phase != 'CLOSED', 'lifecycle_terminal')
        need(type(code) is str and 0 < len(code) <= 256, 'failure_code')
        uint(now_ns)
        if self.first_error is None:
            self.first_error = code
            self.failure_at_ns = max(now_ns, self.last_ns)
            self.phase = 'FAILED'
            self.trace.append({'event': 'FAILURE', 'at_ns': self.failure_at_ns, 'reason': code})

    def resolve_failure(self, now_ns: int, *, no_child_created: bool, child_exited: bool,
                        job_empty: bool, io_quiescent: bool, handles_released: bool,
                        forced: bool) -> str:
        """Records model cleanup observations; never changes failure to success or retries."""
        need(self.phase == 'FAILED' and self.resolution is None, 'resolution_consumed_or_not_failed')
        uint(now_ns)
        need(now_ns >= self.failure_at_ns, 'cleanup_clock_regression')
        fields = (no_child_created, child_exited, job_empty, io_quiescent, handles_released, forced)
        need(all(type(v) is bool for v in fields), 'cleanup_boolean_type')
        need(not (no_child_created and (self.child is not None or child_exited or forced)),
             'contradictory_no_child')
        need(self.create_attempted or no_child_created, 'cleanup_no_create_intent')
        retired = no_child_created or (child_exited and job_empty)
        complete = retired and job_empty and io_quiescent and handles_released
        in_budget = now_ns < self.failure_at_ns + CLEANUP_NS
        self.resolution = {'status': 'FAILED_RETIRED_MODEL' if complete and in_budget else 'UNKNOWN_MODEL',
                           'forced': forced, 'cleanup_confirmed': complete and in_budget,
                           'runtime_authorized': False}
        return self.resolution['status']

    def report(self) -> dict:
        result = ('HWA01_MODEL_TRACE_VALID_NO_AUTHORITY' if self.phase == 'CLOSED' else
                  (self.resolution['status'] if self.resolution else
                   ('FAILED_MODEL' if self.phase == 'FAILED' else 'INCOMPLETE_MODEL')))
        return {'kind': 'HWA01_LIFECYCLE_SOURCE_MODEL_V1', 'result': result,
                'phase': self.phase, 'plan_sha256': self.plan.fingerprint(),
                'create_attempted': self.create_attempted, 'resume_attempted': self.resume_attempted,
                'first_error': self.first_error, 'runtime_authorized': False,
                'native_admission': False, 'sandbox_authorized': False,
                'evidence_domain': 'SOURCE_MODEL', 'trace': [dict(row) for row in self.trace]}
