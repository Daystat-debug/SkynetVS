"""Lazy Win64 declarations. No DLL or ctypes import during module import.
Explicit 32-bit Win32 integers avoid accidental dependence on host C long width.
"""

def make_types(c):
    D, Q, H, W, B = c.c_uint32, c.c_uint64, c.c_void_p, c.c_wchar_p, c.c_int32
    S, P = c.Structure, c.POINTER
    class FT(S):
        _fields_ = [('low', D), ('high', D)]
    class SA(S):
        _fields_ = [('length', D), ('descriptor', H), ('inherit', B)]
    class SI(S):
        _fields_ = [('cb', D), ('reserved', W), ('desktop', W), ('title', W),
                    ('x', D), ('y', D), ('xsize', D), ('ysize', D), ('xcount', D), ('ycount', D),
                    ('fill', D), ('flags', D), ('show', c.c_uint16), ('reserved2size', c.c_uint16),
                    ('reserved2', H), ('stdin', H), ('stdout', H), ('stderr', H)]
    class SX(S):
        _fields_ = [('startup', SI), ('attributes', H)]
    class PI(S):
        _fields_ = [('process', H), ('thread', H), ('pid', D), ('tid', D)]
    class Limits(S):
        _fields_ = [('process_time', c.c_int64), ('job_time', c.c_int64), ('flags', D),
                    ('min_workset', c.c_size_t), ('max_workset', c.c_size_t), ('active', D),
                    ('affinity', c.c_size_t), ('priority', D), ('scheduling', D)]
    class IOCount(S):
        _fields_ = [('read', Q), ('write', Q), ('other', Q), ('readbytes', Q),
                    ('writebytes', Q), ('otherbytes', Q)]
    class Ext(S):
        _fields_ = [('limits', Limits), ('io', IOCount), ('processmem', c.c_size_t),
                    ('jobmem', c.c_size_t), ('peakprocess', c.c_size_t), ('peakjob', c.c_size_t)]
    class OL(S):
        _fields_ = [('internal', c.c_size_t), ('internal_high', c.c_size_t),
                    ('offset', D), ('offset_high', D), ('event', H)]
    class Info(S):
        _fields_ = [('attributes', D), ('created', FT), ('accessed', FT), ('written', FT),
                    ('volume', D), ('sizehigh', D), ('sizelow', D), ('links', D),
                    ('indexhigh', D), ('indexlow', D)]
    class LUID(S):
        _fields_ = [('low', D), ('high', D)]
    class SIDAttr(S):
        _fields_ = [('sid', H), ('attributes', D)]
    class TokenStats(S):
        _fields_ = [('token_id', LUID), ('auth', LUID), ('expiration', c.c_int64),
                    ('type', D), ('impersonation', D), ('charged', D), ('available', D),
                    ('groups', D), ('privileges', D), ('modified', LUID)]
    class TokenGroup(S):
        _fields_ = [('count', D), ('group', SIDAttr * 1)]
    class JobPids(S):
        _fields_ = [('assigned', D), ('count', D), ('pids', c.c_size_t * 2)]
    return dict(D=D, Q=Q, H=H, W=W, B=B, P=P, FT=FT, SA=SA, SI=SI, SX=SX, PI=PI,
                Limits=Limits, Ext=Ext, OL=OL, Info=Info, LUID=LUID, SIDAttr=SIDAttr,
                TokenStats=TokenStats, TokenGroup=TokenGroup, JobPids=JobPids)


def signatures(c, t):
    D,H,W,B,P=t['D'],t['H'],t['W'],t['B'],t['P']
    # dll, return type, positional argtypes. A named symbol is never resolved via caller data.
    k, a = 'kernel32.dll', 'advapi32.dll'
    common = {
        'GetCurrentProcess': (k,H,()), 'GetCurrentProcessId': (k,D,()),
        'GetProcessTimes': (k,B,(H,P(t['FT']),P(t['FT']),P(t['FT']),P(t['FT']))),
        'QueryFullProcessImageNameW': (k,B,(H,D,W,P(D))),
        'ProcessIdToSessionId': (k,B,(D,P(D))),
        'OpenProcessToken': (a,B,(H,D,P(H))),
        'GetTokenInformation': (a,B,(H,D,H,D,P(D))),
        'ConvertSidToStringSidW': (a,B,(H,P(H))), 'IsValidSid': (a,B,(H,)),
        'GetLengthSid': (a,D,(H,)), 'LocalFree': (k,H,(H,)),
        'CloseHandle': (k,B,(H,)), 'GetHandleInformation': (k,B,(H,P(D))),
        'SetHandleInformation': (k,B,(H,D,D)), 'GetFileType': (k,D,(H,)),
        'ReadFile': (k,B,(H,H,D,P(D),P(t['OL']))),
        'WriteFile': (k,B,(H,H,D,P(D),P(t['OL']))),
        'GetStdHandle': (k,H,(D,)),
    }
    owner = {
        'CreateFileW': (k,H,(W,D,D,P(t['SA']),D,D,H)),
        'GetFileInformationByHandle': (k,B,(H,P(t['Info']))),
        'GetFinalPathNameByHandleW': (k,D,(H,W,D,D)),
        'SetFilePointerEx': (k,B,(H,c.c_int64,P(c.c_int64),D)),
        'CreateJobObjectW': (k,H,(P(t['SA']),W)),
        'SetInformationJobObject': (k,B,(H,D,H,D)),
        'QueryInformationJobObject': (k,B,(H,D,H,D,P(D))),
        'IsProcessInJob': (k,B,(H,H,P(B))),
        'TerminateJobObject': (k,B,(H,D)),
        'CreateNamedPipeW': (k,H,(W,D,D,D,D,D,D,P(t['SA']))),
        'ConnectNamedPipe': (k,B,(H,P(t['OL']))),
        'GetNamedPipeClientProcessId': (k,B,(H,P(D))),
        'CreateEventW': (k,H,(P(t['SA']),B,B,W)),
        'GetOverlappedResult': (k,B,(H,P(t['OL']),P(D),B)),
        'CancelIoEx': (k,B,(H,P(t['OL']))),
        'WaitForSingleObject': (k,D,(H,D)),
        'GetExitCodeProcess': (k,B,(H,P(D))),
        'GetProcessId': (k,D,(H,)),
        'ResumeThread': (k,D,(H,)),
        'InitializeProcThreadAttributeList': (k,B,(H,D,D,P(c.c_size_t))),
        'UpdateProcThreadAttribute': (k,B,(H,D,c.c_size_t,H,c.c_size_t,H,H)),
        'DeleteProcThreadAttributeList': (k,None,(H,)),
        'CreateProcessW': (k,B,(W,W,P(t['SA']),P(t['SA']),B,D,H,W,P(t['SI']),P(t['PI']))),
        'ConvertStringSecurityDescriptorToSecurityDescriptorW': (a,B,(W,D,P(H),P(D))),
    }
    return common, owner


def check_win64_layout(c, t):
    expected = {'FT':8,'SA':24,'SI':104,'SX':112,'PI':24,'Limits':64,'Ext':144,
                'OL':32,'Info':52,'LUID':8,'SIDAttr':16,'TokenStats':56,'TokenGroup':24,'JobPids':24}
    if c.sizeof(c.c_void_p) != 8 or c.sizeof(c.c_wchar) != 2:
        raise RuntimeError('win64_widths_required')
    for name,size in expected.items():
        if c.sizeof(t[name]) != size:
            raise RuntimeError('win64_struct:'+name)
    for name,field,offset in [('SI','stdin',80),('SX','attributes',104),('Ext','processmem',112),
                              ('OL','event',24),('TokenGroup','group',8),('JobPids','pids',8)]:
        if getattr(t[name],field).offset != offset:
            raise RuntimeError('win64_offset:'+name+'.'+field)
    return expected
