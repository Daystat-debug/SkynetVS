"""Closed operator entry and prepared trusted host-only composition.
_native_root is source for a future separately authorized fixed launcher. There
is no CLI switch, report field or serialized approval that calls it here.
"""
import json
from dataclasses import asdict, is_dataclass
from .contract import (TOTAL_NS, EXCHANGE_NS, CLEANUP_NS, need, ContractError)
from .lifecycle import Lifecycle
from .protocol import encode, request_payload, DIRECTIONS
from .admission import _issue_at_reviewed_root
from .windows_owner import WindowsOwner


def _report_value(value):
    """Diagnostic data only: no live owner, native handle object or permit."""
    if is_dataclass(value):
        return {'type':type(value).__name__, 'fields':_report_value(asdict(value))}
    if type(value) is bytes:
        return {'bytes_hex':value.hex()}
    if type(value) is tuple:
        return {'tuple':[_report_value(item) for item in value]}
    if type(value) is dict:
        need(all(type(k) is str for k in value), 'report_key_type')
        return {k:_report_value(v) for k,v in value.items()}
    need(type(value) in (type(None), bool, int, str), 'report_value_type')
    return value


def _execute_with_owner(owner,journal,clock):
    """Algorithm shared with fake-port tests; returns observations, never a capability."""
    try:
        return _execute_owner_body(owner,journal,clock)
    finally:
        # Covers setup, failure recording and final diagnostic serialization too.
        owner._retain_unresolved()


def _execute_owner_body(owner,journal,clock):
    """Existing composition body, enclosed by the owner retention boundary above."""
    plan=owner.plan
    started=clock();deadline=started+TOTAL_NS
    life=None
    result={'kind':'HWA01_PREPARED_COMPOSITION_V1','result':'INCOMPLETE',
            'runtime_authorized':False,'source119_native_admission':False,
            'run_id':plan.run_id,'errors':[],'create_attempted':False,
            'plan':plan.descriptor(),'observations':[]}
    def observe(event, data=None):
        at=clock()
        life.observe(event,at,data)
        result['observations'].append({'event':event,'at_ns':at,
                                      'data':_report_value({} if data is None else data)})
    try:
        # Journal initialized by root before opening native APIs. Reserve before owned work.
        journal.reserve()
        identity=owner.retain(deadline)
        result['supervisor_identity']=_report_value(identity)
        result['started_ns']=started
        life=Lifecycle(plan,identity,started)
        observe('RESERVE')
        observe('PINS_RETAINED',{'plan_sha256':plan.fingerprint()})
        data=owner.job_ready(deadline)
        observe('JOB_READY',data)
        owner.prepare_channels(deadline)
        lease=_issue_at_reviewed_root(owner,plan,owner.api.identity(),clock())
        owner.claim_launch(lease,deadline)
        life.tick(clock())
        journal.record('CREATE_INTENT',{'plan_sha256':plan.fingerprint()})
        observe('CREATE_INTENT')
        data=owner.create(lease,deadline)
        observe('CREATED_SUSPENDED_IN_JOB',data)
        data=owner.verify_before_resume(deadline)
        observe('PRE_RESUME_VERIFIED',data)
        life.tick(clock())
        journal.record('RESUME_INTENT')
        observe('RESUME_INTENT')
        data=owner.resume(life.step_deadline_ns)
        observe('RESUMED',data)
        events=(('INIT_SENT','INIT_ACK'),('PROBE_SENT','PROBE_REPLY'),('STOP_SENT','STOP_ACK'))
        for seq,(sent,reply) in enumerate(events):
            # Budget starts BEFORE sending, not after a possibly slow write completes.
            step=min(life.deadline_ns,life.step_deadline_ns if seq==0 else clock()+EXCHANGE_NS)
            packet=encode(plan,DIRECTIONS[0],seq,request_payload(seq))
            life.tick(clock())
            owner.send(packet,step)
            observe(sent,{'packet':packet})
            data=owner.receive(step)
            observe(reply,data)
        data=owner.retire(min(deadline,life.step_deadline_ns))
        observe('RETIRED',data)
        data=owner.quiescent()
        observe('IO_QUIESCENT',data)
        data=owner.release(deadline)
        observe('RESOURCES_RELEASED',data)
        journal.record('COMPLETE',{'normal_exit':True,'job_empty':True,'resources_released':True})
        result['result']='HWA01_FIXED_WORKER_RETIRED_OBSERVED'
    except BaseException as exc:
        code=type(exc).__name__+':'+str(exc)[:180]
        result['errors'].append(code)
        result['result']='HWA01_UNKNOWN'
        try:
            failed_at=clock()
            need(type(failed_at) is int and failed_at>=owner.last_ns and
                 (life is None or failed_at>=life.last_ns),
                 'failure_clock_regression_or_type')
            # Carry this valid observation into cleanup's first monotonic check.
            owner.last_ns=failed_at
            if life is not None and life.phase not in ('FAILED','CLOSED'):
                life.fail(code,failed_at)
            cleanup=owner.cleanup(failed_at+CLEANUP_NS)
            result['cleanup']=cleanup
            if life is not None and life.phase=='FAILED':
                life.resolve_failure(clock(),**{k:cleanup[k] for k in (
                    'no_child_created','child_exited','job_empty','io_quiescent','handles_released','forced')})
            result['result']='HWA01_FAILED_RETIRED' if cleanup['cleanup_confirmed'] else 'HWA01_UNKNOWN'
        except BaseException as ce:
            result['errors'].append('cleanup:'+type(ce).__name__+':'+str(ce)[:180])
            result['result']='HWA01_UNKNOWN'
        try:journal.record('FAILED',{'result':result['result'],'errors':result['errors']})
        except BaseException as je:
            result['errors'].append('journal:'+type(je).__name__+':'+str(je)[:180])
    # Reflect retention in diagnostics; the outer finally also covers their failure.
    owner._retain_unresolved()
    result['create_attempted']=owner.create_attempted
    result['resume_attempted']=owner.resume_attempted
    result['forced_cleanup']=owner.forced
    result['owner_phase']=owner.phase
    result['resources']=owner.resources.summary()
    result['resource_events']=owner.resources.events
    result['stderr_hex']=owner.stderr_bytes.hex()
    if life is not None:result['lifecycle']=life.report()
    return result


def _source_test_with_ports(plan,bundle,api,journal,clock,pause):
    """Test seam is always marked SOURCE_FAKE and never mints native root authority."""
    r=_execute_with_owner(WindowsOwner(api,plan,bundle,clock,pause),journal,clock)
    return {**r,'evidence_domain':'SOURCE_FAKE','native_acceptance':False}


def _native_root(plan,bundle,directory,once_path):
    """Prepared execution root, not called by main or any delivery script.
    Invocation of THIS trusted fixed code is the future operator-authorized effect.
    Plan/Bundle are data: they never open WinApi themselves. A separately reviewed
    delivery must bind exact module bytes/manifest AND fresh Git/runtime observations.
    The external source launcher is closed by default and authorizes no run.
    """
    import sys
    import time
    from .admission import _enter_explicit_native_root
    from .journal import DurableJournal
    from .windows_api import open_owner
    need(sys.platform=='win32','windows_only')
    bundle.validate(plan)
    # Opening report storage is before native resources / child effect.
    journal=DurableJournal(directory,once_path,plan)
    try:
        root=_enter_explicit_native_root()
        api=open_owner(root)
        owner=WindowsOwner(api,plan,bundle,time.monotonic_ns,time.sleep)
        result=_execute_with_owner(owner,journal,time.monotonic_ns)
        return {**result,'evidence_domain':'HOST_ONLY_NATIVE_OBSERVATION',
                'native_acceptance':False,'native_trace':api.trace}
    except BaseException as exc:
        # Includes failures before _execute_with_owner exists. Keep early diagnostics.
        try:journal.record('EARLY_FAILURE',{'type':type(exc).__name__,'error':str(exc)[:180]})
        except BaseException:pass  # Original exception still propagates to the future wrapper.
        raise
    finally:
        journal.close()


def _native_quarantine_present():
    """Dedicated outer controller must terminate without Python finalization if true.
    This reports unresolved ownership, not retirement or authority. In a fresh native
    controller the quarantine contains only that controller's one execution attempt.
    """
    from .windows_owner import _QUARANTINED
    return bool(_QUARANTINED)


def main():
    print(json.dumps({'kind':'HWA01_NATIVE_SOURCE_CANDIDATE_V1',
        'result':'HOST_WORKER_EXECUTION_CLOSED','runtime_authorized':False,
        'native_admission':False},sort_keys=True))
    return 92


if __name__=='__main__':
    raise SystemExit(main())
