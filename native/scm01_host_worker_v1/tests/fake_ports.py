"""In-memory OS port. Executes production WindowsOwner/controller branches, never Win32."""
from dataclasses import replace
from pathlib import PureWindowsPath
from types import SimpleNamespace
from native.scm01_host_worker_v1.contract import *
from native.scm01_host_worker_v1.bootstrap_data import MEMBERS,SourceBundle
from native.scm01_host_worker_v1.protocol import *
from native.scm01_host_worker_v1.windows_api import Operation,NativeError,WinApi


def fixture():
    raws={name:('# '+name+'\n').encode() for name in MEMBERS}
    bundle=SourceBundle(tuple((n,len(raws[n]),digest(raws[n])) for n in MEMBERS))
    exe=b'model exe';dll=b'model dll'
    runtime=RuntimeSelection(FilePin(r'C:\Python312\python.exe',len(exe),digest(exe)),
                             FilePin(r'C:\Python312\python312.dll',len(dll),digest(dll)))
    entry=FilePin(r'C:\HWA01\host_worker_entry.py',len(raws['host_worker_entry.py']),digest(raws['host_worker_entry.py']))
    plan=Plan('1'*32,'2'*64,runtime,entry,bundle.fingerprint()).validate()
    allraw={str(PureWindowsPath(r'C:\HWA01') / n):b for n,b in raws.items()}
    allraw[runtime.executable.path]=exe;allraw[runtime.python_dll.path]=dll
    return plan,bundle,allraw


class Clock:
    def __init__(self):self.value=1000
    def __call__(self):self.value+=1;return self.value
    def pause(self,s):self.value+=max(1,int(s*1e9))


class Journal:
    def __init__(self,fail=None):self.events=[];self.fail=fail;self.reserved=False
    def reserve(self):
        if self.fail=='RESERVE':raise OSError('fixture journal reserve failure')
        if self.reserved:raise OSError('fixture once reused')
        self.reserved=True;self.events.append('RESERVE')
    def record(self,name,data=None):
        if name==self.fail:raise OSError('fixture journal failure '+name)
        self.events.append(name)


class Api:
    def __init__(self,plan,bundle,raws,*,scenario=None,fail_at=None,fragment=8196):
        self.plan,self.bundle,self.raws=plan,bundle,raws
        self.scenario,self.fail_at=scenario,fail_at
        self.fragment=fragment;self.serial=10;self.handles={};self.operations=[]
        self.calls=[];self.did_fail=False;self.resume_calls=0;self.create_calls=0
        self.terminated=0;self.exited=False;self.incoming=b'';self.outgoing=b'';self.seq=0
        self.supervisor=Identity(100,1000,plan.runtime.executable.path,1,77,'S-1-5-21-1')
        self.child=Identity(101,1001,plan.runtime.executable.path,1,77,'S-1-5-21-1')
        self.job=None;self.process=None;self.stderr=b''

    def hit(self,name):
        self.calls.append(name)
        if self.fail_at==name and not self.did_fail:
            self.did_fail=True;raise NativeError('fault:'+name)

    def new(self,label,inherit=False):
        self.serial+=1;h=self.serial;self.handles[h]={'label':label,'open':True,'inherit':inherit}
        return h

    def close(self,h):
        self.hit('close:'+self.handles[h]['label'])
        need(self.handles[h]['open'],'fake_double_close')
        self.handles[h]['open']=False
        if self.handles[h]['label']=='host_stdin' and self.seq==3 and self.scenario!='never_exit':
            self.exited=True
        if h==self.job and self.process:self.exited=True

    def inheritable(self,h):return self.handles[h]['inherit']
    def set_inheritable(self,h,state):self.hit('inherit');self.handles[h]['inherit']=state

    def identity(self,h=None):
        self.hit('identity:self' if h is None else 'identity:child')
        if h is None:return self.supervisor
        if self.scenario=='wrong_child_image':return replace(self.child,image=r'C:\Other\python.exe')
        if self.scenario=='wrong_child_auth':return replace(self.child,authentication_id=78)
        if self.scenario=='identity_drift' and len([n for n in self.calls if n=='identity:child'])>1:
            return replace(self.child,created=1002)
        return self.child

    def open_pin(self,path,directory,resources,name):
        self.hit('open_pin:'+('directory' if directory else 'file'))
        h=self.new(name);resources.add(name,h,self.close)
        self.handles[h]['path']=path;self.handles[h]['directory']=directory
        return h,self.file_info(h)

    def file_info(self,h):
        self.hit('file_info')
        d=self.handles[h];path=d['path'];directory=d['directory']
        return {'path':path,'identity':(1,0,h),'attributes':0x10 if directory else 0x20,
                'links':1,'size':0 if directory else len(self.raws[path]),'written':0}

    def read_pin(self,h,size):
        self.hit('read_pin')
        if self.scenario=='changed_pin':return b'wrong'
        return self.raws[self.handles[h]['path']]

    def create_job(self,resources):
        self.hit('create_job');self.job=self.new('job');resources.add('job',self.job,self.close);return self.job
    def job_limits(self,h):
        self.hit('job_limits')
        return JobLimits(active_processes=2) if self.scenario=='wrong_limit' else JobLimits()
    def job_members(self,h):
        self.hit('job_members')
        need(self.handles[h]['open'],'fake_closed_job_query')
        if self.scenario=='job_foreign':return (999,)
        if self.process and not self.exited:
            return (self.child.pid,102) if self.scenario=='extra_pid' else (self.child.pid,)
        return ()
    def process_in_job(self,h,j):self.hit('is_process_in_job');return self.scenario!='not_in_job'
    def process_exited(self,h):
        self.hit('process_exited');need(self.handles[h]['open'],'fake_closed_process_query');return self.exited
    def exit_code(self,h):self.hit('exit_code');return 7 if self.scenario=='bad_exit' else 0
    def terminate_job(self,h):
        self.hit('terminate_job');self.terminated+=1
        if self.scenario!='cannot_retire':self.exited=True
    def resume(self,h):
        self.hit('resume');self.resume_calls+=1
        if self.scenario=='stderr':self.stderr=b'bounded fixture failure\n'
        return 2 if self.scenario=='wrong_suspend_count' else 1
    def logon_sid(self):self.hit('logon_sid');return 'S-1-5-5-1-1'
    def pipe_client_pid(self,h):self.hit('pipe_client_pid');return 999 if self.scenario=='foreign_pipe' else 100

    def create_pipe_pair(self,run_id,label,logon,resources):
        self.hit('pipe:'+label)
        host=self.new('host_'+label);child=self.new('child_'+label,True)
        resources.add('host_'+label,host,self.close);resources.add('child_'+label,child,self.close)
        return host,child,self.start_io(host,0,'connect',resources)

    def create_process(self,j,ends,p,context,resources):
        self.hit('create_process');self.create_calls+=1
        need(tuple(self.handles[h]['label'] for h in ends)==('child_stdin','child_stdout','child_stderr'),
             'fake_handle_list_wrong')
        self.process=self.new('process');thread=self.new('thread')
        resources.add('process',self.process,self.close);resources.add('thread',thread,self.close)
        self.hit('after_create_handles')
        return self.process,thread,101

    def start_io(self,h,size,kind,resources,data=None):
        label=self.handles[h]['label']
        self.hit('io:'+kind+':'+label)
        ev=self.new('event');name='io_event_'+str(ev);resources.add(name,ev,self.close)
        op=Operation(h,ev,None,data,size,kind,name,pending=True)
        self.operations.append(op)
        if kind=='connect':op.result=0;op.pending=False;op.done=True
        if kind=='write' and self.scenario!='blocked_write':
            n=min(len(data),self.fragment);self.incoming+=data[:n]
            op.result=n;op.pending=False;op.done=True
            if len(self.incoming)>=4:
                total=int.from_bytes(self.incoming[:4],'little')+4
                if len(self.incoming)==total:
                    decode(self.plan,DIRECTIONS[0],self.seq,self.incoming)
                    reply=encode(self.plan,DIRECTIONS[1],self.seq,response_payload(self.plan,self.seq,self.child))
                    if self.scenario=='bad_nonce':reply=reply.replace(b'"nonce":"2',b'"nonce":"3',1)
                    self.outgoing+=reply;self.incoming=b'';self.seq+=1
        return op

    def poll_io(self,op):
        self.hit('poll_io')
        if op.done:return True
        if op.cancelled:
            if self.scenario=='cancel_never_completes':return False
            op.error=995;op.done=True;op.pending=False;return True
        label=self.handles[op.handle]['label']
        if op.kind=='read' and label=='host_stderr':
            if self.stderr:op.result=self.stderr
            elif self.exited:op.result=b'';op.error=109
            else:return False
        elif op.kind=='read' and label=='host_stdout':
            if self.scenario=='no_reply' and not self.exited:return False
            if self.outgoing:
                n=min(op.size,len(self.outgoing),self.fragment)
                op.result,self.outgoing=self.outgoing[:n],self.outgoing[n:]
            elif self.exited:
                op.result=b'x' if self.scenario=='trailing_stdout' else b'';op.error=109
            else:return False
        else:return False
        op.done=True;op.pending=False;return True

    def cancel_io(self,op):
        self.hit('cancel_io')
        if not op.done:op.cancelled=True
    def dispose_io(self,op,resources):
        # Actual disposal implementation; close failure is not silently discarded.
        return WinApi.dispose_io(self,op,resources)
