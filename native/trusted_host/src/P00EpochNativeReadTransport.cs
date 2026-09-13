using System;
using System.Collections.Generic;
using System.Threading;
using SkynetVS.G1.InstallationBootstrapV1;
using SkynetVS.G1.P00EpochReadLeaseV1;
using SkynetVS.G1.SameHandleV1;
using SkynetVS.G1.ParentChainV1;
using SkynetVS.G1.ParentChainNativeAdapterV1;
namespace SkynetVS.G1.P00EpochNativeStoreV1
{
    // Not IManagedEpochReadTransport: a native source must never claim the old synthetic domain.
    internal sealed class P00EpochNativeReadTransport
    {
        private readonly IEpochStoreCalls source;private readonly bool native;
        private readonly string domain;private readonly EpochWindow window;private readonly int thread;
        private readonly DiagnosticEpochExpectation expectation;
        private readonly StoreRef[] owned=new StoreRef[7];
        private readonly HashSet<string> objectIds=new HashSet<string>(StringComparer.Ordinal);
        private readonly List<object> closeOrder=new List<object>();
        private readonly List<string> cleanupErrors=new List<string>();
        private bool rootsReady,busy,stopped,cleanupStarted,terminal;
        private int next=2,calls,closeAttempts,closeSuccesses;
        private NtFrame retained;
        internal const int CallLimit=2048,ChunkLimit=256;
        private P00EpochNativeReadTransport(IEpochStoreCalls io,OwnedDiagnosticRootPair roots,DiagnosticEpochExpectation expected,IEpochClock clock,bool isNative)
        {
            StoreContract.Need(io!=null&&roots!=null&&expected!=null&&clock!=null,"ATTACH_INPUTS");
            if(isNative){StoreContract.Need(io.GetType()==typeof(WindowsEpochStoreCalls),"EXACT_NATIVE_PROVIDER");NativeProcessGate.Check();
                if(IntPtr.Size!=8||Environment.OSVersion.Platform!=PlatformID.Win32NT)throw new PlatformNotSupportedException("Windows x64 only");}
            else StoreContract.Need(io is IManagedEpochStoreCalls&&io.Domain==StoreContract.FakeDomain,"EXPLICIT_FAKE_PROVIDER");
            source=io;native=isNative;domain=isNative?WindowsEpochStoreCalls.NativeDomain:StoreContract.FakeDomain;
            window=new EpochWindow(clock);thread=Thread.CurrentThread.ManagedThreadId;expectation=expected;
            StoreRef h=new StoreRef(this,StoreRole.HostReleaseRoot,roots.Host),s=new StoreRef(this,StoreRole.StoreRoot,roots.Store);
            roots.Take();owned[0]=h;owned[1]=s; // No fallible operations after ownership transfer.
        }
        internal static P00EpochNativeReadTransport ForManagedTests(IManagedEpochStoreCalls source,OwnedDiagnosticRootPair roots,DiagnosticEpochExpectation expected,IEpochClock clock)
        {return new P00EpochNativeReadTransport(source,roots,expected,clock,false);}
        internal static P00EpochNativeReadTransport AttachOwnedNativeDiagnosticRoots(OwnedDiagnosticRootPair roots,DiagnosticEpochExpectation expected,IEpochClock clock)
        {return new P00EpochNativeReadTransport(new WindowsEpochStoreCalls(),roots,expected,clock,true);}
        internal DiagnosticEpochExpectation Expectation {get{return expectation;}}
        internal string Domain {get{return domain;}}
        internal bool IsNative {get{return native;}}
        internal bool Terminal {get{return terminal;}}
        internal int Calls {get{return calls;}}
        internal bool HasRetainedFrame {get{return retained!=null&&retained.Retained;}}
        private void ThreadCheck(){StoreContract.Need(Thread.CurrentThread.ManagedThreadId==thread,"THREAD_AFFINITY");}
        private void Origin()
        {
            if(source.Domain!=domain){terminal=true;stopped=true;window.Revoke();if(native)NativeProcessGate.Poison();throw new EpochIoFailure("SOURCE_ORIGIN_CHANGED",null,true,null);}
            if(native)NativeProcessGate.Check();
        }
        private void Pulse(){Origin();window.Check();Origin();}
        private void Enter()
        {
            ThreadCheck();if(busy){window.Revoke();stopped=true;throw new EpochIoFailure("REENTRANCY",null,false,null);}
            StoreContract.Need(!stopped&&!cleanupStarted&&!terminal,"TRANSPORT_STOPPED");
            try{Pulse();busy=true;}catch{stopped=true;throw;}
        }
        private void Before(){Pulse();StoreContract.Need(calls<CallLimit,"CALL_BUDGET");calls++;}
        private void Failed(){stopped=true;window.Revoke();}
        private EpochIoFailure Poison(NtFrame frame,string code,int? status,Exception inner)
        {
            frame.Retain();retained=frame;terminal=true;Failed();if(native)NativeProcessGate.Poison();
            return new EpochIoFailure(code,status,true,inner);
        }
        internal void ReleaseRetainedFakeStorageForTests()
        {
            StoreContract.Need(!native&&source is IManagedEpochStoreCalls,"FAKE_STORAGE_RELEASE_ONLY");
            if(retained!=null)retained.FreeCompletedFakeOnly((IManagedNtCalls)source);
            // Does not clear terminal or permit any more operations.
        }
        internal void Revoke(){window.Revoke();}
        internal void CheckWindow(){ThreadCheck();Pulse();}
        internal StoreRef Ref(StoreRole role)
        {StoreContract.Need(Enum.IsDefined(typeof(StoreRole),role),"UNKNOWN_ROLE");return owned[(int)role];}
        private void Known(StoreRef r)
        {StoreContract.Need(r!=null&&Object.ReferenceEquals(r.Owner,this)&&owned[(int)r.Role]==r&&!r.Closed&&!r.CloseAttempted,"FOREIGN_OR_CLOSED_REF");}
        private bool KnownHandle(IntPtr h){foreach(StoreRef r in owned)if(r!=null&&r.Handle==h)return true;return false;}
        internal void InitializeRoots()
        {
            Enter();try{StoreContract.Need(!rootsReady,"ROOTS_ALREADY_OBSERVED");ObserveCore(owned[0]);ObserveCore(owned[1]);rootsReady=true;}
            catch{Failed();throw;}finally{busy=false;}
        }
        internal StoreRef OpenFixed(StoreRole role,string acceptanceId)
        {
            Enter();try{
                StoreContract.Need(rootsReady&&(int)role==next&&next<7,"FIXED_OPEN_ORDER");string component=StoreContract.Name(role,acceptanceId);
                StoreRef parent=role==StoreRole.InstallAnchor?owned[0]:role==StoreRole.Acceptance?owned[5]:owned[1];Known(parent);
                StoreRef r=new StoreRef(this,role,IntPtr.Zero);
                using(NtOpenFrame f=new NtOpenFrame(parent.Handle,component,StoreContract.IsDirectory(role))) {
                    Before();int status;
                    try{status=source.Open(f);}catch(Exception e){throw Poison(f,"OPEN_COMPLETION_UNKNOWN",null,e);}
                    try{f.Check();}catch(Exception e){throw Poison(f,"OPEN_BUFFER_INTEGRITY",status,e);}
                    if(status>0)throw Poison(f,"OPEN_NONZERO_POSITIVE_STATUS",status,null);
                    if(status<0){if(f.ResultHandle!=IntPtr.Zero)throw Poison(f,"FAILED_OPEN_WITH_HANDLE",status,null);throw new EpochIoFailure("NT_OPEN_FAILED",status,false,null);}
                    if(!Limits.ValidHandle(f.ResultHandle)||KnownHandle(f.ResultHandle))throw Poison(f,"OPEN_HANDLE_INVALID_OR_ALIAS",status,null);
                    if(f.IoStatus!=0||f.Information!=NativeShape.FileOpened)throw Poison(f,"OPEN_COMPLETION_INVALID",status,null);
                    r.Handle=f.ResultHandle;owned[(int)role]=r;next++; // Before time, domain, metadata checks.
                    Pulse();ObserveCore(r);return r;
                }
            }catch{Failed();throw;}finally{busy=false;}
        }
        private DeviceFacts DeviceCore(StoreRef r)
        {
            using(NtDeviceFrame f=new NtDeviceFrame()) {
                Before();int status;try{status=source.Device(r.Handle,f);}catch(Exception e){throw Poison(f,"DEVICE_COMPLETION_UNKNOWN",null,e);}
                try{f.Check();}catch(Exception e){throw Poison(f,"DEVICE_BUFFER_INTEGRITY",status,e);}
                if(status>0)throw Poison(f,"DEVICE_NONZERO_POSITIVE_STATUS",status,null);
                if(status<0)throw new EpochIoFailure("NT_DEVICE_FAILED",status,false,null);
                if(f.IoStatus!=0||f.Information!=8)throw Poison(f,"DEVICE_COMPLETION_INVALID",status,null);
                DeviceFacts d=NativeShape.DecodeDevice(f.Output.Read(),status,f.IoStatus,f.Information);Pulse();d.RequireLocalDisk();return d;
            }
        }
        private FileFacts FactsCore(StoreRef r)
        {
            Before();FileFacts f;
            try{f=StoreSnapshot.CopyFacts(source.Facts(r.Handle));}
            catch(ObservationFailure){throw;}
            catch(Exception e){terminal=true;Failed();if(native)NativeProcessGate.Poison();throw new EpochIoFailure("FACTS_DISPATCH_UNKNOWN",null,true,e);}
            Pulse();return f;
        }
        private byte[] SecurityCore(StoreRef r)
        {
            Before();byte[] b;
            try{b=source.Security(r.Handle);if(b!=null)b=(byte[])b.Clone();}
            catch(ObservationFailure){throw;}
            catch(Exception e){terminal=true;Failed();if(native)NativeProcessGate.Poison();throw new EpochIoFailure("SECURITY_DISPATCH_UNKNOWN",null,true,e);}
            Pulse();StoreContract.Need(b!=null&&b.Length>=20&&b.Length<=65536,"SECURITY_BOUND");return b;
        }
        private void ValidateFacts(StoreRef r,FileFacts f)
        {
            bool dir=StoreContract.IsDirectory(r.Role);
            StoreContract.Need(f.FileType==1&&f.Directory==dir&&((f.Attributes&0x10u)!=0)==dir,"OBJECT_KIND");
            StoreContract.Need((f.Attributes&(0x400u|0x1000u|0x40000u|0x400000u))==0&&f.ReparseTag==0&&!f.DeletePending,"REPARSE_OFFLINE_RECALL_OR_DELETE");
            StoreContract.Need(f.Size>=0&&f.Allocation>=0&&f.Creation>=0&&f.Write>=0&&f.Change>=0,"NEGATIVE_METADATA");
            if(!dir){StoreContract.Need(f.Links==1,"SINGLE_LINK_FILE_REQUIRED");
                if(r.Role==StoreRole.Gate)StoreContract.Need(f.Size==0,"GATE_MUST_BE_EMPTY");
                else StoreContract.Need(f.Size>0&&f.Size<=StoreContract.Cap(r.Role),"ROLE_SIZE_BOUND");}
            EpochIdentity id=StoreContract.Identity(f),expected=expectation.Expected(r.Role);
            if(expected!=null)StoreContract.Need(id.Same(expected),"EXPECTED_OBJECT_IDENTITY_MISMATCH");
            string volume=r.Role==StoreRole.HostReleaseRoot||r.Role==StoreRole.InstallAnchor?expectation.HostRoot.Volume:expectation.StoreRoot.Volume;
            StoreContract.Need(id.Volume==volume,"ROLE_VOLUME_MISMATCH");
        }
        private StoreSnapshot ObserveCore(StoreRef r)
        {
            Known(r);FileFacts first=FactsCore(r);ValidateFacts(r,first);DeviceFacts device=DeviceCore(r);
            byte[] sd=SecurityCore(r);FileFacts last=FactsCore(r);ValidateFacts(r,last);
            StoreContract.Need(first.Stable(last),"METADATA_DRIFT_INSIDE_OBSERVATION");
            StoreSnapshot value=new StoreSnapshot(first,device.Type,device.Characteristics,sd);
            if(r.Initial==null){StoreContract.Need(objectIds.Add(StoreContract.Identity(first).Key),"OBJECT_ALIAS_BETWEEN_ROLES");r.Initial=value;}
            else StoreContract.Need(r.Initial.Same(value),"OBJECT_OBSERVATION_DRIFT");
            Pulse();return new StoreSnapshot(value.Facts,value.DeviceType,value.DeviceFlags,value.Security());
        }
        internal StoreSnapshot Observe(StoreRef r)
        {Enter();try{return ObserveCore(r);}catch{Failed();throw;}finally{busy=false;}}
        internal byte[] ReadRecord(StoreRef r)
        {
            Enter();try{
                Known(r);StoreContract.Need(StoreContract.Cap(r.Role)>0,"ROLE_IS_NOT_RECORD");StoreSnapshot before=ObserveCore(r);
                byte[] result=new byte[checked((int)before.Facts.Size)];int at=0,chunks=0;
                while(at<result.Length) {
                    StoreContract.Need(chunks++<ChunkLimit,"READ_CHUNK_BUDGET");
                    using(EpochReadFrame f=new EpochReadFrame(at,Math.Min(4096,result.Length-at))) {
                        Before();int status;try{status=source.Read(r.Handle,f);}catch(Exception e){throw Poison(f,"READ_COMPLETION_UNKNOWN",null,e);}
                        try{f.Check();}catch(Exception e){throw Poison(f,"READ_BUFFER_INTEGRITY",status,e);}
                        if(status>0)throw Poison(f,"READ_NONZERO_POSITIVE_STATUS",status,null);
                        if(status<0)throw new EpochIoFailure("NT_READ_FAILED",status,false,null);
                        if(f.IoStatus!=0||f.Information==0||f.Information>(ulong)f.Count)throw Poison(f,"READ_COMPLETION_INVALID",status,null);
                        int n=(int)f.Information;byte[] b=f.Output.Read();Buffer.BlockCopy(b,0,result,at,n);at+=n;Pulse();
                    }
                }
                StoreContract.Need(before.Same(ObserveCore(r)),"READ_OBSERVATION_DRIFT");return result;
            }catch{Failed();throw;}finally{busy=false;}
        }
        internal void CloseAll()
        {
            ThreadCheck();if(busy){window.Revoke();stopped=true;throw new EpochIoFailure("CLEANUP_DURING_OPERATION",null,false,null);}
            if(cleanupStarted)return;cleanupStarted=true;stopped=true;
            if(terminal){cleanupErrors.Add("CLEANUP_FORBIDDEN_AFTER_UNKNOWN_COMPLETION");return;}
            // Borrowed ancestor handles are now owned by this transport. Gate is LAST.
            foreach(int i in new[]{6,5,4,1,2,0,3}) {
                StoreRef r=owned[i];if(r==null||r.CloseAttempted)continue;
                try{Origin();}catch(Exception e){cleanupErrors.Add(e.Message);break;}
                r.CloseAttempted=true;closeAttempts++;closeOrder.Add(r.Role.ToString());
                try{source.Close(r.Handle);r.Closed=true;closeSuccesses++;Origin();}
                catch(Exception e){cleanupErrors.Add(r.Role+":"+e.GetType().Name+":"+e.Message);terminal=true;if(native)NativeProcessGate.Poison();break;}
            }
        }
        internal bool MayRemain{get{foreach(StoreRef r in owned)if(r!=null&&!r.Closed)return true;return terminal;}}
        internal Dictionary<string,object> Export()
        {
            ThreadCheck();int count=0;foreach(StoreRef r in owned)if(r!=null)count++;
            return new Dictionary<string,object>{{"source_domain",domain},{"owned_count",count},{"transferred_roots",2},
                {"dispatch_calls",calls},{"close_attempts",closeAttempts},{"close_successes",closeSuccesses},
                {"close_order",new List<object>(closeOrder)},{"cleanup_errors",new List<string>(cleanupErrors)},
                {"handles_may_remain",MayRemain},{"process_exit_required",terminal||cleanupStarted&&MayRemain},
                {"retained_frame",HasRetainedFrame},{"claims",StoreContract.Claims()}};
        }
    }
}
