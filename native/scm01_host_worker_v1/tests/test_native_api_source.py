import ast
import io
import json
from pathlib import Path
from types import SimpleNamespace as NS
import sys
import unittest
from native.scm01_host_worker_v1 import winabi,windows_api,host_worker_entry,controller,journal
from native.scm01_host_worker_v1.resources import Resources
from native.scm01_host_worker_v1.contract import ContractError,CREATE_FLAGS
from native.scm01_host_worker_v1.bootstrap_data import MEMBERS,CHILD_MEMBERS
from .fake_ports import fixture


def abi_model():
    # Arithmetic only: does not import ctypes or load shared libraries.
    class TM(type):
        def __mul__(cls,n):return TM('Array',(object,),{'size':cls.size*n,'align':cls.align})
    def scalar(n,s,a):return TM(n,(object,),{'size':s,'align':a})
    class SM(TM):
        def __new__(meta,n,b,attrs):
            at=0;align=1
            for field,typ in attrs.get('_fields_',[]):
                at=(at+typ.align-1)//typ.align*typ.align
                attrs[field]=NS(offset=at);at+=typ.size;align=max(align,typ.align)
            attrs['size']=(at+align-1)//align*align;attrs['align']=align
            return super().__new__(meta,n,b,attrs)
    class S(metaclass=SM):pass
    c=NS(Structure=S)
    for n,size,align in [('c_uint32',4,4),('c_uint64',8,8),('c_void_p',8,8),('c_wchar_p',8,8),
                         ('c_int32',4,4),('c_uint16',2,2),('c_size_t',8,8),('c_int64',8,8),('c_wchar',2,2)]:
        setattr(c,n,scalar(n,size,align))
    c.POINTER=lambda t:scalar('Pointer',8,8)
    c.sizeof=lambda t:t.size
    return c


class Value:
    def __init__(self,v=0):self.value=v


class Buffer:
    def __init__(self,data):
        self.value=data
        self.raw=(bytes(data) if isinstance(data,int) else data) if not isinstance(data,str) else b''
        self.size=len(self.raw)


class HM(type):
    def __mul__(cls,n):
        return lambda *args:NS(values=args,size=8*n)


class H(Value,metaclass=HM):pass


class RawC:
    c_size_t=Value
    def __init__(self):self.error=0
    def get_last_error(self):return self.error
    def byref(self,x):return x
    def cast(self,x,t):return x
    def sizeof(self,x):return x.size
    def create_string_buffer(self,value,n=None):return Buffer(value)
    def create_unicode_buffer(self,value):return Buffer(value)


class AbiTests(unittest.TestCase):
    def test_actual_declaration_function_arithmetic_layout(self):
        c=abi_model();t=winabi.make_types(c)
        sizes=winabi.check_win64_layout(c,t)
        self.assertEqual(len(sizes),14);self.assertEqual(t['SX'].attributes.offset,104)
        self.assertEqual(t['OL'].event.offset,24)
    def test_bad_win64_width_rejected(self):
        c=abi_model();t=winabi.make_types(c);c.c_wchar.size=4
        with self.assertRaisesRegex(RuntimeError,'widths'):winabi.check_win64_layout(c,t)
    def test_native_exports_separated_by_role(self):
        c=abi_model();t=winabi.make_types(c);common,owner=winabi.signatures(c,t)
        self.assertIn('CreateProcessW',owner);self.assertNotIn('CreateProcessW',common)
        self.assertNotIn('OpenProcess',set(common)|set(owner))
        for n in ('CreateServiceW','OpenSCManagerW','AdjustTokenPrivileges','AssignProcessToJobObject',
                  'CreateToolhelp32Snapshot','ShellExecuteW','WinExec','SetNamedSecurityInfoW'):
            self.assertNotIn(n,set(common)|set(owner))
        self.assertEqual(len(common['ReadFile'][2]),5)
        self.assertEqual(len(owner['CreateProcessW'][2]),10)
        self.assertEqual(len(owner['UpdateProcThreadAttribute'][2]),7)
    def test_syscall_role_rejects_unknown_exports(self):
        a=windows_api.WinApi(None,None,{},'channel')
        with self.assertRaisesRegex(windows_api.NativeError,'not_in_role'):a.call('CreateProcessW')
    def test_linux_loader_refuses_before_ctypes(self):
        original=windows_api.sys.platform
        try:
            windows_api.sys.platform='linux'
            with self.assertRaises(ContractError):windows_api.open_owner(None)
        finally:windows_api.sys.platform=original
        self.assertNotIn('ctypes',sys.modules);self.assertNotIn('_ctypes',sys.modules)
    def test_closed_controller(self):
        import contextlib
        out=io.StringIO()
        with contextlib.redirect_stdout(out):code=controller.main()
        self.assertEqual(code,92);self.assertFalse(json.loads(out.getvalue())['native_admission'])
    def test_closed_worker_main(self):
        import contextlib
        out=io.StringIO()
        with contextlib.redirect_stdout(out):code=host_worker_entry.main()
        self.assertEqual(code,92)
    def test_private_bootstrap_refuses_linux_before_source_or_native(self):
        original=sys.platform
        try:
            sys.platform='linux'
            with self.assertRaisesRegex(ValueError,'environment'):host_worker_entry._fixed_child('')
        finally:sys.platform=original
        self.assertNotIn('ctypes',sys.modules)


class RawCreateTests(unittest.TestCase):
    def make_api(self,fail=None):
        c=RawC();calls=[]
        t={'D':Value,'H':H,'SA':object,'SI':object,'P':lambda x:object,
           'SX':lambda:NS(startup=NS(),attributes=None,size=112),
           'PI':lambda:NS(process=0,thread=0,pid=0)}
        def init(storage,count,flags,size):
            calls.append(('init',storage is None,count))
            if storage is None:size.value=256;c.error=122;return 0
            return 1
        def update(storage,flags,key,value,size,prev,ret):
            calls.append(('attr',key,value.values,size))
            if fail==key:c.error=87;return 0
            return 1
        def create(app,cmd,pa,ta,inherit,flags,env,cwd,si,pi):
            calls.append(('create',app,cmd.value,inherit,flags,cwd,si.startup.cb,
                          (si.startup.stdin,si.startup.stdout,si.startup.stderr)))
            if fail=='create':c.error=5;return 0
            pi.process=300;pi.thread=301;pi.pid=101
            return 1
        def delete(p):
            calls.append(('delete',))
            if fail=='delete':raise RuntimeError('delete fixture')
        exports={'InitializeProcThreadAttributeList':init,'UpdateProcThreadAttribute':update,
                 'CreateProcessW':create,'DeleteProcThreadAttributeList':delete,'CloseHandle':lambda h:1}
        return windows_api.WinApi(c,t,exports,'owner'),calls
    def invoke(self,fail=None):
        a,calls=self.make_api(fail);p,b,_=fixture();resources=Resources()
        # Only explicit environment read is stubbed; no native code/OS mutation.
        original=windows_api.os.environ.get('SystemRoot')
        windows_api.os.environ['SystemRoot']=r'C:\Windows'
        try:
            result=a.create_process(100,(101,102,103),p,'aabb',resources)
            return result,resources,calls
        finally:
            if original is None:windows_api.os.environ.pop('SystemRoot',None)
            else:windows_api.os.environ['SystemRoot']=original
    def test_job_handle_lists_and_explicit_application(self):
        r,res,calls=self.invoke()
        self.assertEqual(r,(300,301,101))
        attrs=[x for x in calls if x[0]=='attr']
        self.assertEqual(attrs,[('attr',0x20002,(101,102,103),24),('attr',0x2000d,(100,),8)])
        create=next(x for x in calls if x[0]=='create')
        self.assertEqual(create[3:5],(True,CREATE_FLAGS));self.assertEqual(create[6],112)
        self.assertIn('-I -S -B -X utf8',create[2]);self.assertEqual(calls[-1],('delete',))
        self.assertEqual([r.name for r in res.items],['process','thread'])
    def test_joblist_failure_has_no_create_fallback(self):
        a,calls=self.make_api(0x2000d);p,b,_=fixture();res=Resources()
        old=windows_api.os.environ.get('SystemRoot');windows_api.os.environ['SystemRoot']=r'C:\Windows'
        try:
            with self.assertRaises(windows_api.NativeError):a.create_process(100,(101,102,103),p,'aa',res)
        finally:
            if old is None:windows_api.os.environ.pop('SystemRoot',None)
            else:windows_api.os.environ['SystemRoot']=old
        self.assertFalse(any(x[0]=='create' for x in calls));self.assertFalse(res.items)
        self.assertEqual(calls[-1],('delete',))
    def test_create_failure_is_once_and_attribute_list_released(self):
        with self.assertRaises(windows_api.NativeError):self.invoke('create')
    def test_handles_registered_before_attribute_teardown(self):
        a,calls=self.make_api('delete');p,b,_=fixture();res=Resources()
        old=windows_api.os.environ.get('SystemRoot');windows_api.os.environ['SystemRoot']=r'C:\Windows'
        try:
            with self.assertRaisesRegex(RuntimeError,'delete'):a.create_process(100,(101,102,103),p,'aa',res)
        finally:
            if old is None:windows_api.os.environ.pop('SystemRoot',None)
            else:windows_api.os.environ['SystemRoot']=old
        self.assertEqual([r.value for r in res.items],[300,301])
        self.assertTrue(all(r.state=='OPEN' for r in res.items))


class RawIoTests(unittest.TestCase):
    def setup_api(self):
        c=RawC();t={'D':Value,'OL':lambda:NS(event=0),'H':H}
        states={'count':0,'last':996,'cancel':1168,'start':997}
        closes=[]
        def info(h,out):out.value=0;return 1
        def start(*args):
            c.error=states['start']
            if states['start']==0:args[-2].value=states['count'];return 1
            return 0
        def poll(h,ov,n,wait):
            self.assertIs(wait,False);c.error=states['last'];n.value=states['count']
            return int(states['last']==0)
        def cancel(*args):c.error=states['cancel'];return int(states['cancel']==0)
        exports={'CreateEventW':lambda *x:55,'GetHandleInformation':info,'SetHandleInformation':lambda *x:1,
                 'ReadFile':start,'WriteFile':start,'GetOverlappedResult':poll,'CancelIoEx':cancel,
                 'CloseHandle':lambda h:closes.append(h) or 1}
        return windows_api.WinApi(c,t,exports,'owner'),states,closes
    def test_cancel_not_found_is_not_completion(self):
        a,s,closes=self.setup_api();r=Resources();op=a.start_io(7,4,'read',r)
        self.assertTrue(op.pending);a.cancel_io(op)
        self.assertFalse(op.done);self.assertFalse(a.poll_io(op));self.assertFalse(closes)
        with self.assertRaises(ContractError):a.dispose_io(op,r)
        s['last']=995;self.assertTrue(a.poll_io(op));self.assertEqual(op.error,995)
        a.dispose_io(op,r);self.assertEqual(closes,[55]);self.assertFalse(a.operations)
    def test_cancel_racing_normal_completion(self):
        a,s,closes=self.setup_api();r=Resources();op=a.start_io(7,4,'read',r)
        a.cancel_io(op);s['last']=0;s['count']=4
        self.assertTrue(a.poll_io(op));self.assertEqual(op.result,b'\0'*4)
        a.dispose_io(op,r);self.assertEqual(closes,[55])
    def test_immediate_success_and_disposal_once(self):
        a,s,closes=self.setup_api();s['start']=0;s['count']=3;r=Resources()
        op=a.start_io(7,3,'write',r,b'abc');self.assertTrue(op.done);self.assertEqual(op.result,3)
        a.dispose_io(op,r)
        with self.assertRaises(ContractError):a.dispose_io(op,r)
        self.assertEqual(closes,[55])
    def test_broken_pipe_terminal_read(self):
        a,s,closes=self.setup_api();s['start']=109;r=Resources()
        op=a.start_io(7,4,'read',r);self.assertTrue(op.done);self.assertEqual(op.result,b'')
        a.dispose_io(op,r);self.assertEqual(closes,[55])
    def test_unexpected_cancel_error_keeps_buffers(self):
        a,s,closes=self.setup_api();r=Resources();op=a.start_io(7,4,'read',r);s['cancel']=5
        with self.assertRaises(windows_api.NativeError):a.cancel_io(op)
        self.assertTrue(op.pending);self.assertIn(op,a.operations);self.assertFalse(closes)
    def test_bad_transfer_count_cannot_be_success(self):
        a,s,_=self.setup_api();r=Resources();op=a.start_io(7,4,'read',r);s['last']=0;s['count']=5
        with self.assertRaises(ContractError):a.poll_io(op)


    def test_unknown_completion_error_retains_pending_storage(self):
        for error in (5,6,87,1168):
            with self.subTest(error=error):
                a,s,closes=self.setup_api();r=Resources();op=a.start_io(7,4,'read',r)
                buffer,overlapped=op.buffer,op.overlapped
                s['last']=error
                with self.assertRaisesRegex(windows_api.NativeError,'unconfirmed'):a.poll_io(op)
                self.assertTrue(op.pending);self.assertFalse(op.done)
                self.assertIs(op.buffer,buffer);self.assertIs(op.overlapped,overlapped)
                self.assertIn(op,a.operations);self.assertFalse(closes)
                with self.assertRaises(ContractError):a.dispose_io(op,r)
                s['last']=995;self.assertTrue(a.poll_io(op));a.dispose_io(op,r)
                self.assertEqual(closes,[55])
    def test_completed_io_close_error_is_not_pending_or_retried(self):
        a,s,closes=self.setup_api();r=Resources();op=a.start_io(7,4,'read',r)
        s['last']=995;self.assertTrue(a.poll_io(op))
        def bad_close(h):closes.append(h);raise OSError('close failed')
        r.items[-1].close=bad_close
        with self.assertRaises(OSError):a.dispose_io(op,r)
        self.assertTrue(op.disposed);self.assertFalse(a.operations)
        self.assertEqual(r.summary()['uncertain_closes'],1)
        r.close_all();self.assertEqual(closes,[55])


class JournalTests(unittest.TestCase):
    def test_write_all_handles_partial_writes_and_fsync(self):
        writes=[];flush=[]
        class Stream:
            def write(self,b):writes.append(b[:2]);return min(2,len(b))
            def flush(self):flush.append('flush')
            def fileno(self):return 321
        old=journal.os.fsync;journal.os.fsync=lambda n:flush.append(n)
        try:journal.DurableJournal._write_all(Stream(),b'abcde')
        finally:journal.os.fsync=old
        self.assertEqual(b''.join(writes),b'abcde');self.assertEqual(flush,['flush',321])
    def test_zero_write_fails(self):
        class Stream:
            def write(self,b):return 0
        with self.assertRaises(ContractError):journal.DurableJournal._write_all(Stream(),b'x')
    def test_initial_record_failure_closes_log_and_preserves_original(self):
        events=[]
        class Stream:
            def write(self,b):raise OSError('initial write failure')
            def close(self):events.append('close')
        class FakePath:
            def __init__(self,value):self.value=value
            @property
            def parent(self):return FakePath('root')
            @property
            def parents(self):return ()
            def __eq__(self,other):return self.value==other.value
            def lstat(self):return NS(st_mode=0o40700,st_file_attributes=0)
            def exists(self):return False
            def mkdir(self,mode):events.append('mkdir')
            def __truediv__(self,name):return FakePath(name)
            def open(self,mode,buffering):events.append(mode);return Stream()
        original=journal.Path;journal.Path=FakePath
        p,_,_=fixture()
        try:
            with self.assertRaisesRegex(OSError,'initial write failure'):
                journal.DurableJournal('new','once',p)
        finally:journal.Path=original
        self.assertEqual(events,['mkdir','xb','close'])
    def test_no_journal_overwrite_delete_or_retry_source(self):
        source=Path(journal.__file__).read_text()
        self.assertIn("open('xb'",source)
        for banned in ('unlink(','.replace(','.rename(',"open('wb'"):
            self.assertNotIn(banned,source)


class GraphBoundaryTests(unittest.TestCase):
    def test_fixed_graph_matches_all_candidate_files(self):
        root=Path(controller.__file__).parent
        self.assertEqual(tuple(sorted(p.name for p in root.glob('*.py'))),MEMBERS)
        self.assertNotIn('controller.py',CHILD_MEMBERS);self.assertNotIn('admission.py',CHILD_MEMBERS)
    def test_no_process_launch_outside_single_syscall_site(self):
        root=Path(controller.__file__).parent;sites=[]
        for f in root.glob('*.py'):
            tr=ast.parse(f.read_bytes())
            for n in ast.walk(tr):
                if isinstance(n,ast.Call):
                    if isinstance(n.func,ast.Attribute):self.assertNotIn(n.func.attr,('Popen','system','spawn','execv'))
                    if n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value=='CreateProcessW':
                        sites.append((f.name,n.lineno))
        self.assertEqual(len(sites),1);self.assertEqual(sites[0][0],'windows_api.py')
    def test_only_pinned_worker_loader_executes_code_bytes(self):
        root=Path(controller.__file__).parent;sites=[]
        for f in root.glob('*.py'):
            for n in ast.walk(ast.parse(f.read_bytes())):
                if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in ('exec','eval'):
                    sites.append((f.name,n.func.id))
        self.assertEqual(sites,[('host_worker_entry.py','exec')])
    def test_native_root_not_called_by_public_main(self):
        tr=ast.parse(Path(controller.__file__).read_bytes())
        main=next(n for n in tr.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        self.assertFalse(any(isinstance(n,ast.Name) and n.id=='_native_root' for n in ast.walk(main)))
    def test_no_native_loaded_during_preparation(self):
        self.assertNotIn('ctypes',sys.modules);self.assertNotIn('_ctypes',sys.modules)
