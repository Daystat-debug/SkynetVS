"""Lazy Win64 syscall adapter. Source candidate only; no automatic activation.
COMMON exports support the fixed child channel role; OWNER exports require a
process-local native root from the trusted controller. Neither role is a hostile
same-user security boundary. OS installation and stdlib remain trusted.
"""
import os
import sys
from dataclasses import dataclass
from .contract import Identity, JobLimits, CREATE_FLAGS, FRAME_LIMIT, need, digest
from .winabi import make_types, signatures, check_win64_layout


class NativeError(RuntimeError):
    pass


@dataclass(slots=True, eq=False)
class Operation:
    handle: int
    event: int
    overlapped: object
    buffer: object
    size: int
    kind: str
    resource: str
    pending: bool = False
    done: bool = False
    cancelled: bool = False
    error: int = 0
    result: bytes | int | None = None
    disposed: bool = False


class WinApi:
    """Do not instantiate directly. Factories below choose a fixed export allowlist."""
    def __init__(self, c, t, exports, role):
        self.c, self.t, self.exports, self.role = c, t, exports, role
        self.operations = []
        self.serial = 0
        self.trace = []

    def call(self, name, *args):
        if name not in self.exports:
            raise NativeError('export_not_in_role:'+name)
        # Trace records names only, never raw token material or channel bytes.
        self.trace.append(name)
        return self.exports[name](*args)

    def checked(self, name, *args):
        result = self.call(name, *args)
        if not result:
            raise NativeError(name+':'+str(self.c.get_last_error()))
        return result

    def handle(self, name, *args):
        value = self.call(name, *args)
        if value is None or value == 0 or value == (1 << 64) - 1:
            raise NativeError(name+':'+str(self.c.get_last_error()))
        return int(value)

    def close(self, h):
        self.checked('CloseHandle', h)

    def local_free(self, p):
        if self.call('LocalFree', p):
            raise NativeError('LocalFree_failed')

    def inheritable(self, h):
        v = self.t['D']()
        self.checked('GetHandleInformation', h, self.c.byref(v))
        return bool(v.value & 1)

    def set_inheritable(self, h, state):
        self.checked('SetHandleInformation', h, 1, int(state))
        need(self.inheritable(h) is state, 'inheritance_readback')

    def _token_buffer(self, token, kind):
        c,t=self.c,self.t
        size=t['D']()
        ok=self.call('GetTokenInformation', token, kind, None, 0, c.byref(size))
        need(not ok and c.get_last_error()==122 and 0<size.value<=65536, 'token_buffer_size')
        raw=c.create_string_buffer(size.value)
        n=size.value
        self.checked('GetTokenInformation', token, kind, raw, n, c.byref(size))
        need(0<size.value<=n, 'token_buffer_returned')
        return raw,size.value

    def _sid(self, ptr, raw, size):
        c,t=self.c,self.t
        base=c.addressof(raw)
        need(type(ptr) is int and base<=ptr<=base+size-8, 'sid_pointer_range')
        need(bool(self.call('IsValidSid', ptr)), 'sid_invalid')
        n=self.call('GetLengthSid',ptr)
        need(8<=n<=184 and ptr+n<=base+size,'sid_pointer_length')
        output=t['H']()
        self.checked('ConvertSidToStringSidW',ptr,c.byref(output))
        try:
            value=c.wstring_at(output.value)
            need(len(value)<=184,'sid_string_length')
            return value
        finally:
            self.local_free(output.value)

    def identity(self, handle=None):
        c,t=self.c,self.t
        own=handle is None
        h=self.call('GetCurrentProcess') if own else handle
        pid=self.call('GetCurrentProcessId') if own else self.call('GetProcessId',h)
        need(pid>0,'process_id')
        times=[t['FT']() for _ in range(4)]
        self.checked('GetProcessTimes',h,*(c.byref(x) for x in times))
        image=c.create_unicode_buffer(32768); n=t['D'](32768)
        self.checked('QueryFullProcessImageNameW',h,0,image,c.byref(n))
        need(0<n.value<32768,'process_image_length')
        session=t['D'](); self.checked('ProcessIdToSessionId',pid,c.byref(session))
        token=t['H'](); self.checked('OpenProcessToken',h,0x0008,c.byref(token))
        try:
            raw,size=self._token_buffer(token.value,1)
            need(size>=c.sizeof(t['SIDAttr']),'token_user_size')
            user=c.cast(raw,t['P'](t['SIDAttr'])).contents
            sid=self._sid(user.sid,raw,size)
            stats,ssize=self._token_buffer(token.value,10)
            need(ssize>=c.sizeof(t['TokenStats']),'token_stats_size')
            st=c.cast(stats,t['P'](t['TokenStats'])).contents
            auth=(st.auth.high<<32)|st.auth.low
        finally:
            self.close(token.value)
        return Identity(pid,(times[0].high<<32)|times[0].low,image.value,
                        session.value,auth,sid).validate()

    def logon_sid(self):
        c,t=self.c,self.t
        token=t['H']()
        self.checked('OpenProcessToken',self.call('GetCurrentProcess'),0x8,c.byref(token))
        try:
            raw,size=self._token_buffer(token.value,28)
            need(size>=c.sizeof(t['TokenGroup']),'logon_sid_buffer')
            g=c.cast(raw,t['P'](t['TokenGroup'])).contents
            need(g.count==1 and (g.group[0].attributes & 0xc0000000)==0xc0000000,'logon_sid_group')
            sid=self._sid(g.group[0].sid,raw,size)
            import re
            need(re.fullmatch(r'S-1-5-5-\d+-\d+',sid) is not None,'logon_sid_shape')
            return sid
        finally:
            self.close(token.value)

    def open_pin(self, path, directory, resources, name):
        # Directory metadata: share READ/WRITE but NOT DELETE; regular code: share READ only.
        h=self.handle('CreateFileW',path,0x80 if directory else 0x80000000,
                      3 if directory else 1,None,3,0x02200000,None)
        resources.add(name,h,self.close)
        self.set_inheritable(h,False)
        info=self.file_info(h)
        need(bool(info['attributes']&0x10) is directory,'pin_file_type')
        need(not (info['attributes']&0x400),'pin_reparse')
        need(info['path'].casefold()==path.casefold(),'pin_final_path')
        need(directory or info['links']==1,'pin_hardlinks')
        return h,info

    def file_info(self,h):
        c,t=self.c,self.t
        info=t['Info'](); self.checked('GetFileInformationByHandle',h,c.byref(info))
        text=c.create_unicode_buffer(32768)
        n=self.call('GetFinalPathNameByHandleW',h,text,32768,0)
        need(0<n<32768,'final_path_length')
        path=text.value
        need(path.startswith('\\\\?\\') and not path.startswith('\\\\?\\UNC\\'),'final_path_dos')
        need(self.call('GetFileType',h)==1,'pin_disk_file')
        return dict(path=path[4:],attributes=info.attributes,links=info.links,
                    identity=(info.volume,info.indexhigh,info.indexlow),
                    size=(info.sizehigh<<32)|info.sizelow,
                    written=(info.written.high<<32)|info.written.low)

    def read_pin(self,h,size):
        c,t=self.c,self.t
        self.checked('SetFilePointerEx',h,0,None,0)
        output=bytearray()
        while len(output)<=size:
            count=min(65536,size+1-len(output))
            if count==0:break
            buf=c.create_string_buffer(count); n=t['D']()
            self.checked('ReadFile',h,buf,count,c.byref(n),None)
            need(n.value<=count,'pin_read_count')
            if n.value==0:break
            output.extend(buf.raw[:n.value])
        need(len(output)==size,'pin_size_changed')
        return bytes(output)

    def create_job(self,resources):
        h=self.handle('CreateJobObjectW',None,None)
        resources.add('job',h,self.close)
        self.set_inheritable(h,False)
        c,t=self.c,self.t
        ext=t['Ext'](); ext.limits.flags=0x2308;ext.limits.active=1
        ext.processmem=512*1024**2;ext.jobmem=768*1024**2
        self.checked('SetInformationJobObject',h,9,c.byref(ext),c.sizeof(ext))
        return h

    def job_limits(self,h):
        c,t=self.c,self.t
        ext=t['Ext'](); n=t['D']()
        self.checked('QueryInformationJobObject',h,9,c.byref(ext),c.sizeof(ext),c.byref(n))
        need(n.value==c.sizeof(ext) and ext.limits.flags==0x2308,'job_flags_or_size')
        return JobLimits(ext.limits.active,ext.processmem,ext.jobmem).validate()

    def job_members(self,h):
        c,t=self.c,self.t
        p=t['JobPids'](); n=t['D']()
        self.checked('QueryInformationJobObject',h,3,c.byref(p),c.sizeof(p),c.byref(n))
        need(p.count<=2 and p.count==p.assigned and 8+8*p.count<=n.value<=c.sizeof(p),
             'job_incomplete_members')
        return tuple(int(p.pids[i]) for i in range(p.count))

    def process_in_job(self,h,job):
        v=self.t['B']()
        self.checked('IsProcessInJob',h,job,self.c.byref(v))
        return bool(v.value)

    def process_exited(self,h):
        r=self.call('WaitForSingleObject',h,0)
        need(r in (0,258),'process_wait_failed')
        return r==0

    def exit_code(self,h):
        v=self.t['D'](); self.checked('GetExitCodeProcess',h,self.c.byref(v))
        return v.value

    def terminate_job(self,h):
        self.checked('TerminateJobObject',h,93)

    def resume(self,h):
        v=self.call('ResumeThread',h)
        if v==0xffffffff:raise NativeError('ResumeThread:'+str(self.c.get_last_error()))
        return v

    def _operation(self,h,size,kind,resources,data=None):
        c,t=self.c,self.t
        self.serial+=1
        name='io_event_'+str(self.serial)
        event=self.handle('CreateEventW',None,True,False,None)
        resources.add(name,event,self.close)
        self.set_inheritable(event,False)
        ov=t['OL']();ov.event=event
        buf=c.create_string_buffer(data, len(data)) if data is not None else c.create_string_buffer(max(1,size))
        op=Operation(h,event,ov,buf,size,kind,name)
        self.operations.append(op)  # Keep all native buffers alive BEFORE issuing I/O.
        op.pending=True
        return op

    def start_io(self,h,size,kind,resources,data=None):
        need(kind in ('read','write','connect'),'io_kind')
        need(0<=size<=FRAME_LIMIT+4+1,'io_size')
        if kind=='write':need(type(data) is bytes and len(data)==size and size>0,'write_data')
        op=self._operation(h,size,kind,resources,data)
        c,t=self.c,self.t
        n=t['D']()
        if kind=='connect':ok=self.call('ConnectNamedPipe',h,c.byref(op.overlapped))
        else:ok=self.call('ReadFile' if kind=='read' else 'WriteFile',h,op.buffer,size,
                          c.byref(n),c.byref(op.overlapped))
        err=0 if ok else c.get_last_error()
        if err==997:return op  # ERROR_IO_PENDING is NOT completion.
        if kind=='connect' and err==535:err=0  # Connected before ConnectNamedPipe.
        self._finish_operation(op,err,n.value)
        return op

    def _finish_operation(self,op,err,n):
        op.pending=False;op.done=True;op.error=err
        if err:
            op.result=b'' if err==109 and op.kind=='read' else None
        elif op.kind=='connect':op.result=0  # Byte count is undefined for connect.
        else:
            need(0<=n<=op.size,'io_completion_count')
            op.result=op.buffer.raw[:n] if op.kind=='read' else n

    def poll_io(self,op):
        need(not op.disposed,'io_disposed')
        if not op.done:
            n=self.t['D']()
            ok=self.call('GetOverlappedResult',op.handle,self.c.byref(op.overlapped),self.c.byref(n),False)
            err=0 if ok else self.c.get_last_error()
            if err==996:return False  # ERROR_IO_INCOMPLETE keeps all storage retained.
            if err not in (0, 109, 995, 234):
                # Invalid handles/unknown failures are NOT proof that the OS released buffers.
                raise NativeError('io_completion_unconfirmed:'+str(err))
            self._finish_operation(op,err,n.value)
        return True

    def cancel_io(self,op):
        need(not op.disposed,'io_disposed')
        if op.done or op.cancelled:return
        op.cancelled=True
        if not self.call('CancelIoEx',op.handle,self.c.byref(op.overlapped)):
            err=self.c.get_last_error()
            if err!=1168:raise NativeError('CancelIoEx:'+str(err))
        # Including ERROR_NOT_FOUND: do not mark done; poll final completion.

    def dispose_io(self,op,resources):
        need(op.done and not op.pending and not op.disposed,'io_not_completed')
        op.disposed=True
        try:
            resources.close_one(op.resource)
        finally:
            # Completion is already observed; a close failure stays in Resources, not as pending I/O.
            self.operations.remove(op)

    def create_pipe_pair(self,run_id,label,logon,resources):
        c,t=self.c,self.t
        need(label in ('stdin','stdout','stderr'),'pipe_role')
        name='\\\\.\\pipe\\SkynetVS.HWA01.'+run_id+'.'+label
        ptr=t['H'](); n=t['D']()
        sddl='D:P(A;;GA;;;'+logon+')'
        self.checked('ConvertStringSecurityDescriptorToSecurityDescriptorW',sddl,1,c.byref(ptr),c.byref(n))
        try:
            sa=t['SA'](c.sizeof(t['SA']),ptr,False)
            direction=2 if label=='stdin' else 1
            host=self.handle('CreateNamedPipeW',name,direction|0x40000000|0x00080000,
                             8,1,8192,8192,0,c.byref(sa))
            resources.add('host_'+label,host,self.close)
        finally:
            self.local_free(ptr.value)
        self.set_inheritable(host,False)
        op=self.start_io(host,0,'connect',resources)
        child=self.handle('CreateFileW',name,0x80000000 if label=='stdin' else 0x40000000,
                          0,None,3,0x00100000,None)
        resources.add('child_'+label,child,self.close)
        self.set_inheritable(child,True)
        return host,child,op

    def pipe_client_pid(self,h):
        p=self.t['D']();self.checked('GetNamedPipeClientProcessId',h,self.c.byref(p))
        return p.value

    def create_process(self,job,ends,plan,context_hex,resources):
        c,t=self.c,self.t
        need(type(context_hex) is str and all(ch in '0123456789abcdef' for ch in context_hex),
             'launch_context_hex')
        command='"'+plan.runtime.executable.path+'" -I -S -B -X utf8 "'+plan.entrypoint.path+'" --hwa01-fixed-child '+context_hex
        need(len(command)<30000,'command_line_limit')
        # No PATH, PYTHONPATH, credentials, user environment or shell interpolation.
        system=os.environ.get('SystemRoot','')
        from .contract import windows_path
        windows_path(system)
        env=c.create_unicode_buffer('SystemRoot='+system+'\0WINDIR='+system+'\0\0')
        from pathlib import PureWindowsPath
        cwd=str(PureWindowsPath(plan.entrypoint.path).parent)
        size=c.c_size_t()
        ok=self.call('InitializeProcThreadAttributeList',None,2,0,c.byref(size))
        need(not ok and c.get_last_error()==122 and 0<size.value<=1048576,'attribute_size')
        storage=c.create_string_buffer(size.value)
        self.checked('InitializeProcThreadAttributeList',storage,2,0,c.byref(size))
        try:
            handles=(t['H']*3)(*ends); jobs=(t['H']*1)(job)
            self.checked('UpdateProcThreadAttribute',storage,0,0x00020002,handles,c.sizeof(handles),None,None)
            self.checked('UpdateProcThreadAttribute',storage,0,0x0002000d,jobs,c.sizeof(jobs),None,None)
            si=t['SX']();si.startup.cb=c.sizeof(si);si.startup.flags=0x100
            si.startup.stdin,si.startup.stdout,si.startup.stderr=ends
            si.attributes=c.cast(storage,t['H'])
            pi=t['PI'](); cmd=c.create_unicode_buffer(command)
            self.checked('CreateProcessW',plan.runtime.executable.path,cmd,None,None,True,
                         CREATE_FLAGS,env,cwd,c.cast(c.byref(si),t['P'](t['SI'])),c.byref(pi))
            # Own returned handles before ANY identity query or attribute-list teardown.
            process=resources.add('process',int(pi.process),self.close)
            thread=resources.add('thread',int(pi.thread),self.close)
            return process,thread,int(pi.pid)
        finally:
            self.call('DeleteProcThreadAttributeList',storage)


class Channel:
    def __init__(self,api):
        self.api=api
        self.ends=[]
        for code in (-10,-11,-12):
            h=api.handle('GetStdHandle',code & 0xffffffff)
            need(api.call('GetFileType',h)==3,'worker_std_handle_not_pipe')
            need(h not in self.ends,'worker_std_handle_alias')
            self.ends.append(h)
            api.set_inheritable(h,False)
        # These standard handles belong to CPython's standard streams; not double-closed here.

    def read(self,n):
        c,t=self.api.c,self.api.t
        need(type(n) is int and 0<n<=FRAME_LIMIT+4,'channel_read_size')
        buf=c.create_string_buffer(n);got=t['D']()
        ok=self.api.call('ReadFile',self.ends[0],buf,n,c.byref(got),None)
        if not ok:
            err=c.get_last_error()
            if err==109:return b''
            raise NativeError('child_ReadFile:'+str(err))
        need(got.value<=n,'channel_read_count')
        return buf.raw[:got.value]

    def write(self,data):
        c,t=self.api.c,self.api.t
        need(type(data) is bytes and 0<len(data)<=FRAME_LIMIT+4,'channel_write_size')
        buf=c.create_string_buffer(data,len(data));sent=t['D']()
        self.api.checked('WriteFile',self.ends[1],buf,len(data),c.byref(sent),None)
        need(sent.value<=len(data),'channel_write_count')
        return sent.value


def _load(role,root=None):
    need(sys.platform=='win32' and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
         'win32_isolated_no_site_no_bytecode_required')
    need(sys.version_info[:3]==(3,12,10),'exact_python31210_required')
    if role=='owner':
        from .admission import _NativeRoot
        need(type(root) is _NativeRoot,'native_root_type')
        root.require_current()
    else:need(role=='channel','native_role')
    import ctypes as c
    t=make_types(c);check_win64_layout(c,t)
    common,owner=signatures(c,t)
    specs={**common,**owner} if role=='owner' else common
    dlls={n:c.WinDLL(n,use_last_error=True,winmode=0x00000800) for n in sorted({s[0] for s in specs.values()})}
    exports={}
    for name,(dll,result,args) in specs.items():
        fn=getattr(dlls[dll],name);fn.restype=result;fn.argtypes=args;exports[name]=fn
    return WinApi(c,t,exports,role)


def open_owner(root):
    return _load('owner',root)


def open_fixed_channel():
    # Only the fixed child bootstrap calls this. It grants no controller or Job role.
    api=_load('channel')
    return api,Channel(api)
