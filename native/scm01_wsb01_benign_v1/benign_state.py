"""Immutable event bookkeeping only. No event/dictionary is a grant or a native receipt."""
from dataclasses import dataclass, replace
from .benign_contract import need, uint, hexstr, BenignError
from .benign_windows_session import RetirementObservation, MIN_SCAN_NS

PHASES = ('NEW', 'RESERVED', 'LAUNCH_INTENT', 'SESSION_BOUND', 'READY_PINNED',
          'AUTH_INTENT', 'AUTH_PUBLISHED', 'TERMINAL_PENDING', 'RETIRED', 'POSTEXIT_CHECKED', 'RECORDED')
NORMAL = {'RESERVE': ('NEW', 'RESERVED'), 'LAUNCH': ('RESERVED', 'LAUNCH_INTENT'),
          'BIND': ('LAUNCH_INTENT', 'SESSION_BOUND'), 'READY': ('SESSION_BOUND', 'READY_PINNED'),
          'AUTH_INTENT': ('READY_PINNED', 'AUTH_INTENT'), 'AUTH_PUBLISHED': ('AUTH_INTENT', 'AUTH_PUBLISHED'),
          'TERMINAL': ('AUTH_PUBLISHED', 'TERMINAL_PENDING'),
          'RETIRE': ('TERMINAL_PENDING', 'RETIRED'), 'POSTEXIT': ('RETIRED', 'POSTEXIT_CHECKED'),
          'RECORD': ('POSTEXIT_CHECKED', 'RECORDED')}


@dataclass(frozen=True)
class BenignState:
    run_id: str
    nonce: str
    boot_binding: str
    started_ns: int
    deadline_ns: int
    last_ns: int
    phase: str = 'NEW'
    session_sha256: str = ''
    pending_sha256: str = ''
    failure_sticky: bool = False
    retired: bool = False
    forced: bool = False
    reason: str = ''
    phase_deadline_ns: int = 0


@dataclass(frozen=True)
class HostEvent:
    kind: str
    at_ns: int
    run_id: str
    nonce: str
    boot_binding: str
    session_sha256: str = ''
    payload: object = None


@dataclass(frozen=True)
class Transition:
    state: BenignState
    effects: tuple[str, ...] = ()
    runtime_authorized: bool = False


def new_state(run_id, nonce, boot_binding, started_ns):
    hexstr(run_id, 32); hexstr(nonce); hexstr(boot_binding); uint(started_ns, (1 << 64) - 300_000_000_001)
    return BenignState(run_id, nonce, boot_binding, started_ns,
                       started_ns + 300_000_000_000, started_ns)


def _fail(s, code):
    return replace(s, failure_sticky=True, reason=s.reason or code,
                   phase='FAILED_RETIRED' if s.retired else 'FAILED_ACTIVE_UNKNOWN')


def _retirement(s, r):
    need(type(r) is RetirementObservation and r.run_id == s.run_id and r.nonce == s.nonce and
         r.boot_binding == s.boot_binding and r.binding_sha256 == s.session_sha256 and
         s.session_sha256, 'retirement_binding')
    need(type(r.normal) is bool and type(r.forced) is bool and r.normal != r.forced and
         r.handles_signaled is True, 'retirement_flags')
    need(len(r.empty_scan_ticks) == 3 and
         all(type(x) is int and 0 <= x <= s.last_ns for x in r.empty_scan_ticks) and
         all(b - a >= MIN_SCAN_NS for a, b in zip(r.empty_scan_ticks, r.empty_scan_ticks[1:])),
         'retirement_scans')
    return r


def transition_benign(state, host_event):
    need(type(state) is BenignState, 'state_type')
    s = state
    try:
        e = host_event; need(type(e) is HostEvent, 'event_type'); uint(e.at_ns)
        need((e.run_id, e.nonce, e.boot_binding) == (s.run_id, s.nonce, s.boot_binding), 'event_scope')
        need(e.at_ns >= s.last_ns, 'clock_regression')
        if s.session_sha256:
            need(e.session_sha256 == s.session_sha256, 'session_event_binding')
        s = replace(s, last_ns=e.at_ns)
        if e.at_ns > s.deadline_ns or (s.phase_deadline_ns and e.at_ns > s.phase_deadline_ns):
            s = _fail(s, 'deadline')
        if e.kind in ('FAILURE', 'UNKNOWN'):
            return Transition(_fail(s, e.kind))
        if e.kind == 'RETIRE':
            r = _retirement(s, e.payload)
            s = replace(s, retired=True, forced=s.forced or r.forced)
            if r.forced:
                s = _fail(s, 'forced_cleanup')
            if s.failure_sticky:
                return Transition(_fail(s, s.reason))
        if s.failure_sticky:
            return Transition(_fail(s, s.reason))
        if e.kind in ('TICK', 'LAUNCHER_EXITED'):
            return Transition(s)
        need(e.kind in NORMAL, 'unknown_event')
        before, after = NORMAL[e.kind]
        need(s.phase == before, 'phase_order')
        if e.kind == 'LAUNCH':
            s = replace(s, phase_deadline_ns=min(s.deadline_ns, e.at_ns + 120_000_000_000))
        if e.kind == 'BIND':
            hexstr(e.session_sha256); s = replace(s, session_sha256=e.session_sha256)
        if e.kind == 'AUTH_PUBLISHED':
            s = replace(s, phase_deadline_ns=min(s.deadline_ns, e.at_ns + 60_000_000_000))
        if e.kind == 'TERMINAL':
            need(type(e.payload) is tuple and len(e.payload) == 2, 'terminal_payload')
            result, snapshot_sha = e.payload; hexstr(snapshot_sha)
            need(result in ('BENIGN_TASK_COMPLETED', 'BENIGN_TASK_FAILED'), 'terminal_result')
            s = replace(s, pending_sha256=snapshot_sha,
                        phase_deadline_ns=min(s.deadline_ns, e.at_ns + 45_000_000_000))
            if result == 'BENIGN_TASK_FAILED':
                return Transition(_fail(s, 'terminal_failure'))
        if e.kind == 'POSTEXIT':
            need(e.payload == s.pending_sha256 and s.retired and not s.forced, 'postexit_bytes')
        if e.kind == 'RECORD':
            need(s.retired and not s.forced, 'record_without_retirement')
        return Transition(replace(s, phase=after))
    except (BenignError, TypeError, AttributeError) as exc:
        return Transition(_fail(s, str(exc)))
