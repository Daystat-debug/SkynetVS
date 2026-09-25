"""Contract/transition tests only. No Win32, process/thread creation or project worktree access."""
import unittest
from dataclasses import replace
import json
import struct
from native.scm01_host_worker_v1.contract import *
from native.scm01_host_worker_v1.protocol import *
from native.scm01_host_worker_v1.lifecycle import Lifecycle, ORDER


def fixture():
    runtime = RuntimeSelection(FilePin(r'C:\Python312\python.exe', 104952, 'a'*64),
                               FilePin(r'C:\Python312\python312.dll', 6945272, 'b'*64))
    plan = Plan('1'*32, '2'*64, runtime,
                FilePin(r'C:\HWA01\host_worker_entry.py', 1234, 'c'*64), 'd'*64)
    supervisor = Identity(100, 10000, r'C:\Python312\python.exe', 1, 77, 'S-1-5-21-1')
    child = Identity(101, 10001, r'C:\Python312\python.exe', 1, 77, 'S-1-5-21-1')
    return plan, supervisor, child


def data_for(plan, child):
    data = {
        'RESERVE': {}, 'PINS_RETAINED': {'plan_sha256': plan.fingerprint()},
        'JOB_READY': {'limits': JobLimits(), 'members': (), 'complete': True},
        'CREATE_INTENT': {},
        'CREATED_SUSPENDED_IN_JOB': {'identity': child, 'flags': CREATE_FLAGS, 'job_list_applied': True},
        'PRE_RESUME_VERIFIED': {'identity': child, 'members': (child.pid,), 'complete': True,
            'limits': JobLimits(), 'child_handle_roles': ('stdin', 'stdout', 'stderr'),
            'parent_child_ends_closed': True, 'all_parent_handles_noninheritable': True,
            'program_pins_unchanged': True},
        'RESUME_INTENT': {}, 'RESUMED': {'previous_suspend_count': 1},
        'RETIRED': {'signaled': True, 'exit_code': 0, 'members': (), 'complete': True},
        'IO_QUIESCENT': {'pending_io': 0, 'threads_alive': 0, 'stderr_bytes': 0},
        'RESOURCES_RELEASED': {'unreleased_handles': 0, 'uncertain_closes': 0, 'program_pins_unchanged': True},
    }
    for seq, (sent, reply) in enumerate((('INIT_SENT', 'INIT_ACK'), ('PROBE_SENT', 'PROBE_REPLY'), ('STOP_SENT', 'STOP_ACK'))):
        data[sent] = {'packet': encode(plan, DIRECTIONS[0], seq, request_payload(seq))}
        data[reply] = {'packet': encode(plan, DIRECTIONS[1], seq, response_payload(plan, seq, child)), 'identity': child}
    return data


def run_until(stop, alteration=None):
    plan, supervisor, child = fixture()
    life, data = Lifecycle(plan, supervisor, 0), data_for(plan, child)
    if alteration:
        event, values = alteration
        data[event] = {**data[event], **values}
    for index, event in enumerate(ORDER):
        if event == stop:
            break
        life.observe(event, index+1, data[event])
    return life, data


class ContractTests(unittest.TestCase):
    def test_valid_plan_no_authority(self):
        p, _, _ = fixture()
        self.assertEqual(p.fingerprint(), p.fingerprint())
        self.assertFalse(p.descriptor()['native_authority'])
        self.assertFalse(p.descriptor()['sandbox_authority'])

    def test_identity_types(self):
        _, _, child = fixture()
        for field, value in [('pid', True), ('created', False), ('session_id', -1),
                             ('authentication_id', 2**64), ('user_sid', 'admin')]:
            with self.subTest(field=field), self.assertRaises(ContractError):
                replace(child, **{field: value}).validate()

    def test_local_path_policy(self):
        for value in [r'C:\A\x.py', r'C:\Program Files\Python312\python.exe']:
            self.assertEqual(windows_path(value), value)
        for value in [r'c:\a', r'\\server\a', r'C:a', r'C:\a\..\b', r'C:\a.\b',
                      r'C:\a\b:stream', r'C:\NUL.txt', 'C:\\a\\', 'C:\\a\\b\n', r'C:\a\\b',
                      r'\\?\C:\a', 'C:/a', r'C:\COM1\file']:
            with self.subTest(value=value), self.assertRaises(ContractError):
                windows_path(value)

    def test_runtime_redirector_rejected(self):
        p, _, _ = fixture()
        for root in (r'C:\Project\.venv\Scripts', r'C:\venv', r'C:\Scripts'):
            rt = RuntimeSelection(FilePin(root+r'\python.exe', 10, 'a'*64),
                                  FilePin(root+r'\python312.dll', 10, 'b'*64))
            with self.subTest(root=root), self.assertRaises(ContractError):
                rt.validate()

    def test_runtime_version_directory_trust(self):
        p, _, _ = fixture()
        cases = [replace(p.runtime, version='3.14.0'), replace(p.runtime, trust_model='ATTESTED_RUNTIME'),
                 replace(p.runtime, python_dll=FilePin(r'C:\Other\python312.dll', 10, 'b'*64))]
        for item in cases:
            with self.subTest(item=item), self.assertRaises(ContractError): item.validate()

    def test_fixed_profile_and_hashes(self):
        p, _, _ = fixture()
        for field, val in [('run_id', 'A'*32), ('nonce', 'x'*64), ('source_manifest_sha256', '0'),
                           ('base_commit', 'f'*40), ('profile', 'BEN01'),
                           ('entrypoint', FilePin(r'C:\HWA01\other.py', 1, 'c'*64))]:
            with self.subTest(field=field), self.assertRaises(ContractError):
                replace(p, **{field: val}).validate()

    def test_size_bool_and_limits(self):
        for size in (True, False, 0, -1, 32*1024*1024+1):
            with self.subTest(size=size), self.assertRaises(ContractError):
                FilePin(r'C:\p\python.exe', size, 'a'*64).validate()
        for field,val in [('active_processes', True), ('active_processes', 2), ('process_memory', 1),
                          ('job_memory', 1), ('kill_on_close', 1), ('breakaway', True), ('silent_breakaway', True)]:
            with self.subTest(field=field), self.assertRaises(ContractError):
                replace(JobLimits(), **{field:val}).validate()


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.plan, self.supervisor, self.child = fixture()

    def packet(self, seq=0, direction=DIRECTIONS[1]):
        payload = response_payload(self.plan, seq, self.child) if direction == DIRECTIONS[1] else request_payload(seq)
        return encode(self.plan, direction, seq, payload)

    def raw(self, value):
        raw = canonical(value)
        return struct.pack('<I',len(raw))+raw

    def test_six_frame_roundtrip(self):
        for direction in DIRECTIONS:
            decoder = Decoder(self.plan, direction)
            for seq in range(3):
                with self.subTest(direction=direction, seq=seq):
                    self.assertEqual(decoder.feed(self.packet(seq, direction))['sequence'], seq)
            decoder.eof()
            with self.assertRaises(ContractError): decoder.feed(self.packet(0,direction))

    def test_every_fragment_boundary(self):
        packet = self.packet()
        for offset in range(1, len(packet)):
            with self.subTest(offset=offset):
                decoder = Decoder(self.plan, DIRECTIONS[1])
                self.assertIsNone(decoder.feed(packet[:offset]))
                self.assertEqual(decoder.feed(packet[offset:])['sequence'], 0)

    def test_bytes_one_at_a_time(self):
        decoder = Decoder(self.plan, DIRECTIONS[1])
        out = None
        for byte in self.packet(): out = decoder.feed(bytes([byte]))
        self.assertEqual(out['command'], 'INIT')

    def test_wrong_binding_poisoned(self):
        value = json.loads(self.packet()[4:])
        changes = [('kind','BEN01_WORKER_INGRESS_V1'), ('run_id','9'*32), ('nonce','8'*64),
                   ('plan_sha256','7'*64), ('direction',DIRECTIONS[0]), ('sequence',True),
                   ('sequence',1), ('command','BIND'), ('approved',True)]
        for key,val in changes:
            with self.subTest(key=key,val=val):
                decoder = Decoder(self.plan, DIRECTIONS[1])
                with self.assertRaises(ContractError): decoder.feed(self.raw({**value,key:val}))
                self.assertTrue(decoder.poisoned)
                with self.assertRaises(ContractError): decoder.feed(self.packet())

    def test_frame_limits_and_trailing(self):
        for packet in [b'\0\0\0\0', struct.pack('<I', FRAME_LIMIT+1),
                       self.packet()+self.packet(), self.packet()+b'x']:
            with self.subTest(size=len(packet)), self.assertRaises(ContractError):
                Decoder(self.plan,DIRECTIONS[1]).feed(packet)

    def test_eof_missing_and_partial(self):
        for packet in [b'', self.packet()[:3], self.packet()[:-1], self.packet()]:
            decoder = Decoder(self.plan,DIRECTIONS[1])
            if packet: decoder.feed(packet)
            with self.subTest(size=len(packet)), self.assertRaises(ContractError): decoder.eof()

    def test_replay_and_opposite_direction(self):
        decoder = Decoder(self.plan,DIRECTIONS[1])
        decoder.feed(self.packet())
        with self.assertRaises(ContractError): decoder.feed(self.packet())
        with self.assertRaises(ContractError):
            decode(self.plan,DIRECTIONS[0],0,self.packet())

    def test_json_depth_duplicates_floats(self):
        value = self.packet()[4:]
        cases = [b'{"sequence":0,"sequence":0}\n', b'{"x":NaN}\n', b'{"x":1.0}\n',
                 b'['*9+b'0'+b']'*9, value.replace(b'"sequence":0',b'"sequence":-0'),
                 b' '+value, value+b'\n', b'\xff', b'{"x":'+b'9'*21+b'}\n']
        for raw in cases:
            with self.subTest(raw=raw[:50]), self.assertRaises(ContractError):
                decode(self.plan,DIRECTIONS[1],0,struct.pack('<I',len(raw))+raw)

    def test_fixed_probe_cannot_be_code_or_paths(self):
        for payload in [{'data_hex':b'import os'.hex()}, {'command':'calc.exe'}, {'path':r'C:\file'},
                        {'data_hex': FIXED_PAYLOAD.hex(), 'permit':True}]:
            with self.subTest(payload=payload), self.assertRaises(ContractError):
                encode(self.plan,DIRECTIONS[0],1,payload)

    def test_response_types_and_digest(self):
        for payload in [{'pid':True,'created':1,'executable_sha256':'a'*64,'source_manifest_sha256':'d'*64},
                        {'pid':1,'created':1,'executable_sha256':'f'*64,'source_manifest_sha256':'d'*64}]:
            with self.subTest(payload=payload), self.assertRaises(ContractError):
                encode(self.plan,DIRECTIONS[1],0,payload)
        with self.assertRaises(ContractError):
            encode(self.plan,DIRECTIONS[1],1,{'bytes':len(FIXED_PAYLOAD),'sha256':'f'*64})


class LifecycleTests(unittest.TestCase):
    def test_complete_trace_non_authorizing(self):
        life,_ = run_until(None)
        report = life.report()
        self.assertEqual(report['result'],'HWA01_MODEL_TRACE_VALID_NO_AUTHORITY')
        self.assertFalse(report['native_admission'])
        self.assertFalse(report['runtime_authorized'])
        self.assertEqual(len(report['trace']),len(ORDER))
        self.assertEqual(report['evidence_domain'],'SOURCE_MODEL')
        with self.assertRaises(ContractError): life.observe('RESERVE',100)
        self.assertEqual(life.report(), report)

    def test_each_out_of_order_transition(self):
        for position,expected in enumerate(ORDER):
            for other in ORDER:
                if other == expected: continue
                with self.subTest(expected=expected,other=other):
                    life,data = run_until(expected)
                    with self.assertRaises(ContractError): life.observe(other,position+1,data[other])
                    self.assertEqual(life.first_error,'event_order')
                    self.assertEqual(life.report()['result'],'FAILED_MODEL')

    def test_no_resume_before_identity_check(self):
        life,_ = run_until('PRE_RESUME_VERIFIED')
        with self.assertRaises(ContractError): life.observe('RESUME_INTENT',10)
        self.assertFalse(life.resume_attempted)

    def test_job_list_required(self):
        life,data = run_until('CREATED_SUSPENDED_IN_JOB')
        data['CREATED_SUSPENDED_IN_JOB']['job_list_applied'] = False
        with self.assertRaisesRegex(ContractError,'job_list_required'):
            life.observe('CREATED_SUSPENDED_IN_JOB',10,data['CREATED_SUSPENDED_IN_JOB'])
        self.assertFalse(life.resume_attempted)

    def test_presume_checks(self):
        _,_,child = fixture()
        changes = [('members',()), ('members',(child.pid,102)), ('complete',False),
                   ('identity',replace(child,created=999)), ('limits',JobLimits(active_processes=2)),
                   ('child_handle_roles',('stdin','stdout','job')), ('parent_child_ends_closed',False),
                   ('all_parent_handles_noninheritable',False), ('program_pins_unchanged',False)]
        for key,val in changes:
            with self.subTest(key=key):
                life,data = run_until('PRE_RESUME_VERIFIED')
                with self.assertRaises(ContractError):
                    life.observe('PRE_RESUME_VERIFIED',10,{**data['PRE_RESUME_VERIFIED'],key:val})
                self.assertFalse(life.resume_attempted)

    def test_creation_identity(self):
        _,supervisor,child = fixture()
        for identity in [replace(child,pid=supervisor.pid),replace(child,image=r'C:\Other\python.exe'),
                         replace(child,user_sid='S-1-5-18'),replace(child,session_id=2),replace(child,authentication_id=80)]:
            with self.subTest(identity=identity):
                life,data = run_until('CREATED_SUSPENDED_IN_JOB')
                with self.assertRaises(ContractError):
                    life.observe('CREATED_SUSPENDED_IN_JOB',10,{**data['CREATED_SUSPENDED_IN_JOB'],'identity':identity})

    def test_bad_resume_count(self):
        for count in [0,2,0xffffffff,True]:
            with self.subTest(count=count):
                life,_ = run_until('RESUMED')
                with self.assertRaises(ContractError): life.observe('RESUMED',10,{'previous_suspend_count':count})

    def test_late_ack_and_clock_regression(self):
        life,data = run_until('INIT_ACK')
        with self.assertRaisesRegex(ContractError,'deadline_expired'):
            life.observe('INIT_ACK',life.step_deadline_ns,data['INIT_ACK'])
        life,_ = run_until('JOB_READY')
        with self.assertRaisesRegex(ContractError,'clock_regression'): life.tick(0)

    def test_clock_types(self):
        for now in [True,1.5,-1]:
            p,s,_=fixture(); life=Lifecycle(p,s,0)
            with self.subTest(now=now), self.assertRaises(ContractError): life.tick(now)

    def test_ack_self_report_not_enough(self):
        life,data = run_until('INIT_ACK')
        p,_,child=fixture()
        fake = replace(child,pid=888)
        packet = encode(p,DIRECTIONS[1],0,response_payload(p,0,fake))
        with self.assertRaisesRegex(ContractError,'ack_not_owned_peer'):
            life.observe('INIT_ACK',20,{'packet':packet,'identity':child})

    def test_peer_mismatch_at_every_reply(self):
        for event in ('INIT_ACK','PROBE_REPLY','STOP_ACK'):
            life,data=run_until(event)
            _,_,child=fixture()
            with self.subTest(event=event), self.assertRaises(ContractError):
                life.observe(event,20,{**data[event],'identity':replace(child,created=9999)})

    def test_retirement_is_more_than_signaled(self):
        for key,val in [('signaled',False),('exit_code',1),('exit_code',False),('exit_code',259),
                        ('members',(101,)),('complete',False)]:
            life,data=run_until('RETIRED')
            with self.subTest(key=key,val=val), self.assertRaises(ContractError):
                life.observe('RETIRED',20,{**data['RETIRED'],key:val})

    def test_io_and_cleanup_mandatory(self):
        for event,key in [('IO_QUIESCENT','pending_io'),('IO_QUIESCENT','threads_alive'),
                          ('IO_QUIESCENT','stderr_bytes'),('RESOURCES_RELEASED','uncertain_closes'),
                          ('RESOURCES_RELEASED','unreleased_handles')]:
            life,data=run_until(event)
            with self.subTest(event=event,key=key), self.assertRaises(ContractError):
                life.observe(event,20,{**data[event],key:1})

    def test_report_snapshot_cannot_mutate_trace(self):
        life,_=run_until('JOB_READY'); before=life.report()
        report=life.report();report['trace'][0]['phase']='HACK'
        self.assertEqual(before,life.report())

    def test_failure_sticky_and_forced_never_pass(self):
        life,_=run_until('INIT_ACK');life.fail('timeout',20);life.fail('secondary',21)
        self.assertEqual(life.first_error,'timeout')
        result=life.resolve_failure(30,no_child_created=False,child_exited=True,job_empty=True,
                                    io_quiescent=True,handles_released=True,forced=True)
        self.assertEqual(result,'FAILED_RETIRED_MODEL')
        with self.assertRaises(ContractError):life.observe('RESERVE',40)
        with self.assertRaises(ContractError):
            life.resolve_failure(40,no_child_created=False,child_exited=True,job_empty=True,
                                 io_quiescent=True,handles_released=True,forced=False)

    def test_uncertain_cleanup_and_late_cleanup(self):
        for field in ('child_exited','job_empty','io_quiescent','handles_released'):
            life,_=run_until('INIT_ACK');life.fail('timeout',20)
            args=dict(no_child_created=False,child_exited=True,job_empty=True,
                      io_quiescent=True,handles_released=True,forced=True);args[field]=False
            with self.subTest(field=field):self.assertEqual(life.resolve_failure(30,**args),'UNKNOWN_MODEL')
        life,_=run_until('INIT_ACK');life.fail('timeout',20)
        self.assertEqual(life.resolve_failure(20+CLEANUP_NS,no_child_created=False,child_exited=True,
                          job_empty=True,io_quiescent=True,handles_released=True,forced=True),'UNKNOWN_MODEL')

    def test_prelaunch_failure_without_child(self):
        life,_=run_until('CREATE_INTENT');life.fail('precheck',20)
        self.assertEqual(life.resolve_failure(21,no_child_created=True,child_exited=False,
                          job_empty=True,io_quiescent=True,handles_released=True,forced=False),'FAILED_RETIRED_MODEL')

    def test_false_no_child_refused(self):
        life,_=run_until('INIT_ACK');life.fail('error',20)
        with self.assertRaises(ContractError):
            life.resolve_failure(21,no_child_created=True,child_exited=False,job_empty=True,
                                 io_quiescent=True,handles_released=True,forced=False)

    def test_unknown_field_poisoned(self):
        p,s,_=fixture();life=Lifecycle(p,s,0)
        with self.assertRaises(ContractError):life.observe('RESERVE',1,{'approved':True})
        self.assertEqual(life.report()['result'],'FAILED_MODEL')


if __name__ == '__main__': unittest.main()
