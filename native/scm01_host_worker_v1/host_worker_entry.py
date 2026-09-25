"""Closed default entry; internal fixed-child route is DATA/channel bootstrap only.
It is not a grant to start this process. Parent must already have selected, pinned,
retained and created this exact trusted script in its Job. Same-user hostile code
is outside this component's threat model. No standalone native activation command.
"""
import json


def main():
    print(json.dumps({'kind':'HWA01_SOURCE_CONTRACT_V1','result':'HOST_WORKER_EXECUTION_CLOSED',
                      'runtime_authorized':False,'native_admission':False},sort_keys=True))
    return 92


from contextlib import contextmanager


@contextmanager
def _verified_child_modules(raw, base):
    """Execute only seven verified HWA child modules; no native factory here.
    This separates actual loader tests from native child environment checks.
    Parent-side pinned first-script trust is still required by the threat model.
    """
    import sys
    from pathlib import Path
    import hashlib
    import importlib.abc
    import importlib.util
    def pairs(rows):
        out={}
        for k,v in rows:
            if k in out:raise ValueError('duplicate_bootstrap_key')
            out[k]=v
        return out
    def reject(_):raise ValueError('bootstrap_number')
    if type(raw) is not bytes or not 0<len(raw)<=14000:
        raise ValueError('fixed_child_bootstrap_size')
    depth=0;quoted=False;escaped=False
    for ch in raw:
        if quoted:
            if escaped:escaped=False
            elif ch==92:escaped=True
            elif ch==34:quoted=False
        elif ch==34:quoted=True
        elif ch in (91,123):
            depth+=1
            if depth>8:raise ValueError('fixed_child_bootstrap_depth')
        elif ch in (93,125):
            depth-=1
            if depth<0:raise ValueError('fixed_child_bootstrap_depth')
    if depth or quoted:raise ValueError('fixed_child_bootstrap_shape')
    def integer(text):
        if len(text)>20:raise ValueError('fixed_child_bootstrap_integer')
        return int(text)
    envelope=json.loads(raw.decode('ascii'),object_pairs_hook=pairs,parse_int=integer,
                        parse_float=reject,parse_constant=reject)
    canonical=(json.dumps(envelope,sort_keys=True,ensure_ascii=True,separators=(',',':'),allow_nan=False)+'\n').encode('ascii')
    if canonical!=raw or type(envelope) is not dict or set(envelope)!={'plan','source'}:
        raise ValueError('fixed_child_envelope')
    members=('__init__.py','admission.py','bootstrap_data.py','contract.py','controller.py',
             'host_worker_entry.py','journal.py','lifecycle.py','protocol.py','resources.py',
             'winabi.py','windows_api.py','windows_owner.py','worker.py')
    child_members=('__init__.py','contract.py','protocol.py','bootstrap_data.py',
                   'worker.py','winabi.py','windows_api.py')
    source=envelope['source']
    if (type(source) is not dict or set(source)!={'kind','files'} or
        source['kind']!='HWA01_SOURCE_GRAPH_V1' or type(source['files']) is not list or
        len(source['files'])!=len(members)):
        raise ValueError('fixed_child_manifest')
    base=Path(base)
    verified={}
    for expected,row in zip(members,source['files']):
        if (type(row) is not dict or set(row)!={'name','bytes','sha256'} or
            row['name']!=expected or type(row['bytes']) is not int or not 0<row['bytes']<=262144 or
            type(row['sha256']) is not str or len(row['sha256'])!=64 or
            any(ch not in '0123456789abcdef' for ch in row['sha256'])):
            raise ValueError('fixed_child_member')
        with (base/expected).open('rb') as f:
            data=f.read(row['bytes']+1)
        if len(data)!=row['bytes'] or hashlib.sha256(data).hexdigest()!=row['sha256']:
            raise ValueError('fixed_child_source_pin')
        if expected in child_members:verified[expected]=data
    class Finder(importlib.abc.MetaPathFinder,importlib.abc.Loader):
        def find_spec(self,fullname,path=None,target=None):
            if fullname=='hwa01_fixed':name='__init__.py';pkg=True
            elif fullname.startswith('hwa01_fixed.'):
                name=fullname.split('.',1)[1]+'.py';pkg=False
            else:return None
            if name not in verified:raise ImportError('fixed_child_module_not_allowed:'+fullname)
            return importlib.util.spec_from_loader(fullname,self,is_package=pkg)
        def create_module(self,spec):return None
        def exec_module(self,module):
            name='__init__.py' if module.__name__=='hwa01_fixed' else module.__name__.split('.',1)[1]+'.py'
            module.__file__=str(base/name)
            if name=='__init__.py':module.__path__=[]
            exec(compile(verified[name],module.__file__,'exec',dont_inherit=True),module.__dict__)
    # Only exact verified module bytes execute; no project directory is put on sys.path.
    if any(n=='hwa01_fixed' or n.startswith('hwa01_fixed.') for n in sys.modules):
        raise ValueError('fixed_child_namespace_preloaded')
    finder=Finder();sys.meta_path.insert(0,finder)
    try:
        from hwa01_fixed.bootstrap_data import deserialize
        from hwa01_fixed.worker import serve_fixed
        from hwa01_fixed.windows_api import open_fixed_channel
        plan,bundle=deserialize(raw)
        yield plan,bundle,serve_fixed,open_fixed_channel
    finally:
        if finder in sys.meta_path:sys.meta_path.remove(finder)
        for name,module in list(sys.modules.items()):
            if (name=='hwa01_fixed' or name.startswith('hwa01_fixed.')) and getattr(module,'__loader__',None) is finder:
                del sys.modules[name]


def _fixed_child(raw_hex):
    import sys
    import os
    from pathlib import Path
    import hashlib
    if not (sys.platform=='win32' and sys.version_info[:3]==(3,12,10) and
            sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise ValueError('fixed_child_environment')
    if not (type(raw_hex) is str and 0<len(raw_hex)<=28000 and len(raw_hex)%2==0 and
            all(ch in '0123456789abcdef' for ch in raw_hex)):
        raise ValueError('fixed_child_argument')
    raw=bytes.fromhex(raw_hex)
    with _verified_child_modules(raw, Path(__file__).absolute().parent) as loaded:
        plan,bundle,serve_fixed,open_fixed_channel=loaded
        if (str(Path(plan.entrypoint.path)).casefold()!=str(Path(__file__).absolute()).casefold() or
            sys.executable.casefold()!=plan.runtime.executable.path.casefold()):
            raise ValueError('fixed_child_paths')
        # Hashing here is a cross-check, not proof of first-instruction provenance.
        for pin in (plan.runtime.executable,plan.runtime.python_dll):
            with open(pin.path,'rb') as f:data=f.read(pin.size+1)
            if len(data)!=pin.size or hashlib.sha256(data).hexdigest()!=pin.sha256:
                raise ValueError('fixed_child_runtime_pin')
        api,channel=open_fixed_channel()
        identity=api.identity()
        if identity.pid!=os.getpid() or identity.image.casefold()!=plan.runtime.executable.path.casefold():
            raise ValueError('fixed_child_identity')
        return serve_fixed(plan,identity,channel)


if __name__=='__main__':
    import sys
    if len(sys.argv)==3 and sys.argv[1]=='--hwa01-fixed-child':
        try:code=_fixed_child(sys.argv[2])
        except BaseException as exc:
            # Bounded diagnostic-only stderr; never interleave text into binary stdout.
            sys.stderr.write('HWA01_CHILD_FAILED:'+type(exc).__name__+':'+str(exc)[:160]+'\n')
            code=93
        raise SystemExit(code)
    raise SystemExit(main())
