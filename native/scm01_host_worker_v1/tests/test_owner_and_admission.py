import copy
from dataclasses import replace
import json
import pickle
import unittest
from native.scm01_host_worker_v1.contract import *
from native.scm01_host_worker_v1.admission import LaunchLease,_issue_at_reviewed_root
from native.scm01_host_worker_v1.resources import Resources
from native.scm01_host_worker_v1.bootstrap_data import *
from native.scm01_host_worker_v1.controller import _source_test_with_ports
from native.scm01_host_worker_v1.windows_owner import WindowsOwner
from native.scm01_host_worker_v1.worker import serve_fixed
from native.scm01_host_worker_v1.protocol import *
from .fake_ports import fixture,Clock,Journal,Api


def run(scenario=None,fail_at=None,journal_fail=None,fragment=8196):
    plan,bundle,raws=fixture();clock=Clock();journal=Journal(journal_fail)
    api=Api(plan,bundle,raws,scenario=scenario,fail_at=fail_at,fragment=fragment)
    r=_source_test_with_ports(plan,bundle,api,journal,clock,clock.pause)
    return r,api,journal


class AdmissionTests(unittest.TestCase):
    def test_private_constructor_refuses_dict(self):
        p,_,_=fixture()
        with self.assertRaises(ContractError):LaunchLease({'approved':True},object(),p,None,0)
    def test_once_claim(self):
        p,b,raw=fixture();a=Api(p,b,raw);o=object()
        lease=_issue_at_reviewed_root(o,p,a.supervisor,0)
        lease.claim(o,p,a.supervisor,1)
        with self.assertRaisesRegex(ContractError,'consumed'):lease.claim(o,p,a.supervisor,2)
    def test_wrong_owner_poisoned(self):
        p,b,raw=fixture();a=Api(p,b,raw);o=object();l=_issue_at_reviewed_root(o,p,a.supervisor,0)
        with self.assertRaisesRegex(ContractError,'owner'):l.claim(object(),p,a.supervisor,1)
        with self.assertRaisesRegex(ContractError,'consumed'):l.claim(o,p,a.supervisor,2)
    def test_wrong_plan_identity_clock_refused(self):
        p,b,raw=fixture();a=Api(p,b,raw);o=object()
        cases=[(replace(p,nonce='9'*64),a.supervisor,1),(p,replace(a.supervisor,created=99),1),
               (p,a.supervisor,STARTUP_NS),(p,a.supervisor,-1),(p,a.supervisor,True)]
        for plan,identity,n in cases:
            with self.subTest(n=n,plan=plan),self.assertRaises(ContractError):
                _issue_at_reviewed_root(o,p,a.supervisor,0).claim(o,plan,identity,n)
    def test_copy_and_serialization_refused(self):
        p,b,raw=fixture();a=Api(p,b,raw);l=_issue_at_reviewed_root(object(),p,a.supervisor,0)
        for fn in (copy.copy,copy.deepcopy,pickle.dumps):
            with self.subTest(fn=fn),self.assertRaises(ContractError):fn(l)


    def test_failed_claim_is_not_successful_claim(self):
        p,b,raw=fixture();a=Api(p,b,raw);o=object()
        lease=_issue_at_reviewed_root(o,p,a.supervisor,0)
        with self.assertRaises(ContractError):lease.claim(object(),p,a.supervisor,1)
        with self.assertRaisesRegex(ContractError,'not_successfully_claimed'):
            lease.require_claim(o,p,a.supervisor,2)
    def test_unclaimed_lease_does_not_create_claim_by_recheck(self):
        p,b,raw=fixture();a=Api(p,b,raw);o=object()
        lease=_issue_at_reviewed_root(o,p,a.supervisor,0)
        with self.assertRaisesRegex(ContractError,'not_successfully_claimed'):
            lease.require_claim(o,p,a.supervisor,1)
    def test_claim_recheck_expiry_and_binding(self):
        p,b,raw=fixture();a=Api(p,b,raw);o=object()
        cases=[(o,p,a.supervisor,STARTUP_NS),(object(),p,a.supervisor,2),
               (o,replace(p,nonce='1'*64),a.supervisor,2),
               (o,p,replace(a.supervisor,created=99),2),(o,p,a.supervisor,0)]
        for owner,plan,identity,n in cases:
            with self.subTest(n=n):
                lease=_issue_at_reviewed_root(o,p,a.supervisor,0)
                lease.claim(o,p,a.supervisor,1)
                with self.assertRaises(ContractError):lease.require_claim(owner,plan,identity,n)


class BundleTests(unittest.TestCase):
    def test_bootstrap_roundtrip(self):
        p,b,_=fixture();p2,b2=deserialize(serialize(p,b))
        self.assertEqual(p,p2);self.assertEqual(b,b2)
    def test_source_graph_is_exact(self):
        p,b,_=fixture()
        for rows in [b.rows[:-1],b.rows[::-1],(('x.py',1,'a'*64),)+b.rows[1:]]:
            with self.subTest(rows=rows),self.assertRaises(ContractError):SourceBundle(rows).validate(p)
    def test_unknown_plan_flag_not_permit(self):
        p,b,_=fixture();value=json.loads(serialize(p,b));value['plan']['approved']=True
        with self.assertRaises(ContractError):deserialize(canonical(value))
    def test_native_authority_boolean_exact(self):
        p,b,_=fixture()
        for v in (True,0,1):
            value=json.loads(serialize(p,b));value['plan']['native_authority']=v
            with self.subTest(v=v),self.assertRaises(ContractError):deserialize(canonical(value))
    def test_manifest_path_or_size_refused(self):
        p,b,_=fixture()
        for val in ('../contract.py','C:\\evil.py'):
            d=json.loads(serialize(p,b));d['source']['files'][1]['name']=val
            with self.assertRaises(ContractError):deserialize(canonical(d))
        for val in (True,0,262145):
            d=json.loads(serialize(p,b));d['source']['files'][1]['bytes']=val
            with self.assertRaises(ContractError):deserialize(canonical(d))
    def test_noncanonical_duplicates_and_depth(self):
        p,b,_=fixture()
        for raw in [serialize(p,b)+b' ',b'{"x":0,"x":0}\n',b'['*9+b'0'+b']'*9,b'{"x":NaN}\n']:
            with self.subTest(raw=raw[:30]),self.assertRaises(ContractError):deserialize(raw)
    def test_plan_pin_tied_to_entrypoint(self):
        p,b,_=fixture()
        with self.assertRaises(ContractError):b.validate(replace(p,entrypoint=replace(p.entrypoint,sha256='f'*64)))


class ResourceTests(unittest.TestCase):
    def test_lifo_and_once(self):
        calls=[];r=Resources();r.add('a',1,calls.append);r.add('b',2,calls.append)
        self.assertEqual(r.close_all(),[]);self.assertEqual(calls,[2,1]);self.assertTrue(r.all_closed())
        self.assertEqual(r.close_all(),[]);self.assertEqual(calls,[2,1])
        with self.assertRaises(ContractError):r.close_one('a')
    def test_error_does_not_prevent_other_closes(self):
        calls=[];r=Resources()
        def close(h):
            calls.append(h)
            if h==2:raise OSError('close')
        for h in (1,2,3):r.add(str(h),h,close)
        self.assertEqual(len(r.close_all()),1);self.assertEqual(calls,[3,2,1])
        self.assertFalse(r.all_closed());self.assertEqual(r.summary()['uncertain_closes'],1)
        r.close_all();self.assertEqual(calls,[3,2,1])
    def test_invalid_duplicate_and_alias(self):
        r=Resources()
        for h in (0,-1,(1<<64)-1,True,None):
            with self.subTest(h=h),self.assertRaises(ContractError):r.add('bad',h,lambda _:None)
        r.add('x',1,lambda _:None)
        with self.assertRaises(ContractError):r.add('y',1,lambda _:None)
        with self.assertRaises(ContractError):r.add('x',2,lambda _:None)


class OwnerFlowTests(unittest.TestCase):
    def test_happy_path_actual_owner_fake_syscalls(self):
        r,a,j=run()
        self.assertEqual(r['result'],'HWA01_FIXED_WORKER_RETIRED_OBSERVED',r['errors'])
        self.assertEqual(r['evidence_domain'],'SOURCE_FAKE');self.assertFalse(r['native_acceptance'])
        self.assertEqual(j.events,['RESERVE','CREATE_INTENT','RESUME_INTENT','COMPLETE'])
        self.assertEqual(a.create_calls,1);self.assertEqual(a.resume_calls,1);self.assertEqual(a.terminated,0)
        self.assertFalse(a.operations);self.assertFalse(any(h['open'] for h in a.handles.values()))
        self.assertEqual(len(r['lifecycle']['trace']),17)
    def test_fragmented_os_transfers(self):
        for size in (1,3,17,2048):
            with self.subTest(size=size):
                r,a,_=run(fragment=size)
                self.assertEqual(r['result'],'HWA01_FIXED_WORKER_RETIRED_OBSERVED',r['errors'])
                self.assertFalse(a.operations)
    def test_all_before_create_faults_no_child(self):
        names=['identity:self','open_pin:directory','open_pin:file','file_info','read_pin','create_job',
               'job_limits','job_members','logon_sid','pipe:stdin','pipe:stdout','pipe:stderr','pipe_client_pid']
        for name in names:
            with self.subTest(name=name):
                r,a,_=run(fail_at=name)
                self.assertNotEqual(r['result'],'HWA01_FIXED_WORKER_RETIRED_OBSERVED')
                self.assertEqual(a.create_calls,0);self.assertEqual(a.resume_calls,0)
                self.assertEqual(r['result'],'HWA01_FAILED_RETIRED',r['errors'])
    def test_creation_failure_never_retries(self):
        r,a,j=run(fail_at='create_process')
        self.assertNotEqual(r['result'],'HWA01_FIXED_WORKER_RETIRED_OBSERVED')
        self.assertTrue(r['create_attempted']);self.assertEqual(a.resume_calls,0)
        self.assertEqual(a.calls.count('create_process'),1)
    def test_failure_after_create_handles_is_owned(self):
        r,a,j=run(fail_at='after_create_handles')
        self.assertEqual(a.create_calls,1);self.assertEqual(a.resume_calls,0)
        self.assertEqual(a.terminated,1);self.assertTrue(r['forced_cleanup'])
        self.assertFalse(any(h['open'] for h in a.handles.values()))
        self.assertEqual(r['result'],'HWA01_FAILED_RETIRED',r['errors'])
    def test_security_or_membership_failure_never_resumes(self):
        for scenario in ('wrong_child_image','wrong_child_auth','identity_drift','not_in_job','extra_pid'):
            with self.subTest(scenario=scenario):
                r,a,_=run(scenario=scenario)
                self.assertEqual(a.resume_calls,0);self.assertEqual(a.terminated,1)
                self.assertNotEqual(r['result'],'HWA01_FIXED_WORKER_RETIRED_OBSERVED')
    def test_journal_reserve_before_owned_resources(self):
        r,a,_=run(journal_fail='RESERVE')
        self.assertFalse(a.calls);self.assertFalse(r['create_attempted'])
    def test_create_intent_failure_no_create(self):
        r,a,_=run(journal_fail='CREATE_INTENT')
        self.assertEqual(a.create_calls,0);self.assertEqual(a.resume_calls,0)
    def test_resume_intent_failure_kills_suspended_worker(self):
        r,a,_=run(journal_fail='RESUME_INTENT')
        self.assertEqual(a.create_calls,1);self.assertEqual(a.resume_calls,0);self.assertEqual(a.terminated,1)
        self.assertNotEqual(r['result'],'HWA01_FIXED_WORKER_RETIRED_OBSERVED')
    def test_postclose_journal_failure_not_success(self):
        r,a,_=run(journal_fail='COMPLETE')
        self.assertNotEqual(r['result'],'HWA01_FIXED_WORKER_RETIRED_OBSERVED')
        self.assertEqual(a.create_calls,1);self.assertEqual(a.terminated,0)
    def test_reply_stderr_or_suspend_fault_not_success(self):
        for s in ('bad_nonce','stderr','wrong_suspend_count','bad_exit','trailing_stdout'):
            with self.subTest(s=s):
                r,a,_=run(scenario=s)
                self.assertNotEqual(r['result'],'HWA01_FIXED_WORKER_RETIRED_OBSERVED')
                self.assertFalse(r['runtime_authorized']);self.assertLessEqual(a.terminated,1)
    def test_write_and_read_timeouts_cleanup(self):
        for s in ('blocked_write','no_reply','never_exit'):
            with self.subTest(s=s):
                r,a,_=run(scenario=s)
                self.assertEqual(a.create_calls,1);self.assertEqual(a.terminated,1)
                self.assertTrue(r['forced_cleanup']);self.assertEqual(r['result'],'HWA01_FAILED_RETIRED',r['errors'])
    def test_pins_and_foreign_pipe_block_creation(self):
        for s in ('changed_pin','foreign_pipe','job_foreign','wrong_limit'):
            with self.subTest(s=s):
                r,a,_=run(scenario=s)
                self.assertEqual(a.create_calls,0)
                self.assertNotEqual(r['result'],'HWA01_FIXED_WORKER_RETIRED_OBSERVED')
    def test_close_failure_never_claims_resources_released(self):
        for name in ('close:child_stdout','close:process','close:job','close:pin_0','close:event'):
            with self.subTest(name=name):
                r,a,_=run(fail_at=name)
                self.assertNotEqual(r['result'],'HWA01_FIXED_WORKER_RETIRED_OBSERVED')
                self.assertLessEqual(a.terminated,1)
                self.assertGreaterEqual(r['resources']['uncertain_closes'],1)
    def test_pending_io_is_quarantined_not_freed(self):
        p,b,raws=fixture();clock=Clock();a=Api(p,b,raws,scenario='cancel_never_completes')
        owner=WindowsOwner(a,p,b,clock,clock.pause)
        owner.retain(clock()+TOTAL_NS);owner.job_ready(clock()+TOTAL_NS);owner.prepare_channels(clock()+TOTAL_NS)
        op=a.start_io(owner.ends['stderr'][0],8193,'read',owner.resources)
        result=owner.cleanup(clock()+3_000_000)
        self.assertFalse(result['cleanup_confirmed']);self.assertTrue(result['quarantined'])
        self.assertIn(op,a.operations);self.assertFalse(op.done)
        self.assertTrue(a.handles[op.event]['open']);self.assertTrue(a.handles[op.handle]['open'])
    def test_no_lease_cannot_call_create(self):
        p,b,raw=fixture();c=Clock();a=Api(p,b,raw);o=WindowsOwner(a,p,b,c,c.pause)
        o.retain(c()+TOTAL_NS);o.job_ready(c()+TOTAL_NS);o.prepare_channels(c()+TOTAL_NS)
        with self.assertRaises(ContractError):o.create({'approved':True},c()+TOTAL_NS)
        self.assertEqual(a.create_calls,0)
        o.cleanup(c()+CLEANUP_NS)


    def test_claim_precedes_durable_create_intent(self):
        p,b,raw=fixture();c=Clock();a=Api(p,b,raw);o=WindowsOwner(a,p,b,c,c.pause)
        class CheckedJournal(Journal):
            def record(self,event,data=None):
                if event=='CREATE_INTENT':
                    self_test.assertEqual(o.phase,'CLAIMED')
                    self_test.assertTrue(o._claimed_lease._claimed)
                    self_test.assertEqual(a.create_calls,0)
                super().record(event,data)
        self_test=self
        from native.scm01_host_worker_v1.controller import _execute_with_owner
        result=_execute_with_owner(o,CheckedJournal(),c)
        self.assertEqual(result['result'],'HWA01_FIXED_WORKER_RETIRED_OBSERVED')
    def test_expired_claim_cannot_reach_creation(self):
        p,b,raw=fixture();c=Clock();a=Api(p,b,raw);o=WindowsOwner(a,p,b,c,c.pause)
        deadline=c()+TOTAL_NS
        o.retain(deadline);o.job_ready(deadline);o.prepare_channels(deadline)
        lease=_issue_at_reviewed_root(o,p,a.supervisor,c());o.claim_launch(lease,deadline)
        c.pause(10)
        with self.assertRaisesRegex(ContractError,'expired'):o.create(lease,deadline)
        self.assertEqual(a.create_calls,0);self.assertFalse(o.create_attempted)
        o.cleanup(c()+CLEANUP_NS)
    def test_complete_journal_failure_uses_retirement_not_closed_handles(self):
        r,a,_=run(journal_fail='COMPLETE')
        self.assertEqual(r['result'],'HWA01_FAILED_RETIRED',r['errors'])
        self.assertTrue(r['cleanup']['cleanup_confirmed'])
        self.assertEqual(r['cleanup']['errors'],[])
        self.assertFalse(r['forced_cleanup']);self.assertEqual(a.terminated,0)
        self.assertFalse(any(h['open'] for h in a.handles.values()))


    def test_claim_expiring_during_precreate_checks_never_creates(self):
        p,b,raw=fixture();c=Clock();a=Api(p,b,raw);o=WindowsOwner(a,p,b,c,c.pause)
        deadline=c()+TOTAL_NS
        o.retain(deadline);o.job_ready(deadline);o.prepare_channels(deadline)
        lease=_issue_at_reviewed_root(o,p,a.supervisor,c());o.claim_launch(lease,deadline)
        original=a.job_limits
        def late_job(h):
            result=original(h);c.pause(10);return result
        a.job_limits=late_job
        with self.assertRaisesRegex(ContractError,'expired'):o.create(lease,deadline)
        self.assertEqual(a.create_calls,0);self.assertFalse(o.create_attempted)
        o.cleanup(c()+CLEANUP_NS)
    def test_late_stderr_setup_does_not_resume(self):
        p,b,raw=fixture();c=Clock();a=Api(p,b,raw);original=a.start_io
        def slow_start(h,size,kind,res,data=None):
            op=original(h,size,kind,res,data)
            if kind=='read' and a.handles[h]['label']=='host_stderr':c.pause(11)
            return op
        a.start_io=slow_start
        result=_source_test_with_ports(p,b,a,Journal(),c,c.pause)
        self.assertEqual(a.create_calls,1);self.assertEqual(a.resume_calls,0)
        self.assertNotEqual(result['result'],'HWA01_FIXED_WORKER_RETIRED_OBSERVED')
        self.assertEqual(a.terminated,1)


class WorkerTests(unittest.TestCase):
    def test_fixed_protocol_entire_worker_loop_in_memory(self):
        p,b,raw=fixture();a=Api(p,b,raw)
        requests=b''.join(encode(p,DIRECTIONS[0],i,request_payload(i)) for i in range(3))
        class Channel:
            def __init__(self):self.data=requests;self.out=b''
            def read(self,n):
                n=min(n,3);out,self.data=self.data[:n],self.data[n:];return out
            def write(self,raw):self.out+=raw[:5];return min(5,len(raw))
        ch=Channel();self.assertEqual(serve_fixed(p,a.child,ch),0)
        raw=ch.out
        for seq in range(3):
            n=int.from_bytes(raw[:4],'little')+4
            decode(p,DIRECTIONS[1],seq,raw[:n]);raw=raw[n:]
        self.assertFalse(raw)
    def test_eof_oversize_and_corrupt_request(self):
        p,b,raw=fixture();a=Api(p,b,raw)
        for data in (b'',b'\0'*4,(8193).to_bytes(4,'little'),b'\x01\0\0\0X'):
            class Ch:
                def read(self,n):
                    nonlocal data
                    part,data=data[:n],data[n:];return part
                def write(self,raw):return len(raw)
            with self.subTest(data=data),self.assertRaises(ContractError):serve_fixed(p,a.child,Ch())
