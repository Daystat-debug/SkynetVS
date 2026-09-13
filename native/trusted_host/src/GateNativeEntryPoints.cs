using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Reflection;
using SkynetVS.G1.GateLeaseHandoffV1;
using SkynetVS.G1.InstallationBootstrapV1;

namespace SkynetVS.G1.GateLeaseHandoffNativeV1
{
    internal sealed class CoordinatorInput
    {
        internal string Run,Nonce,GateId,Volume,ChildHash;
        internal ProcessStamp Parent,Self;
        internal static CoordinatorInput Parse(string[] args)
        {
            HCheck.Need(args!=null&&args.Length==9&&args[0]=="--native-gate-coordinator"&&args[8]==NativeScope.Mode,"COORDINATOR_ARGUMENTS");
            HCheck.Hex(args[1],32,"RUN");HCheck.Hex(args[2],32,"NONCE");HCheck.Hex(args[5],32,"GATE_ID");HCheck.Hex(args[6],16,"GATE_VOLUME");HCheck.Hex(args[7],64,"CHILD_HASH");
            return new CoordinatorInput{Run=args[1],Nonce=args[2],Parent=new ProcessStamp((uint)NativeScope.Number(args[3],UInt32.MaxValue),NativeScope.Number(args[4],UInt64.MaxValue)),GateId=args[5],Volume=args[6],ChildHash=args[7]};
        }
        internal string FixtureDirectory()
        {return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),"Downloads","SkynetVS_GateHandoff_Fixture_"+Run);}
    }
    internal sealed class ReceiverInput
    {
        internal HandoffPin Pin;
        internal RestrictedInheritancePlan Handles;
        internal static ReceiverInput Parse(string[] a)
        {
            HCheck.Need(a!=null&&a.Length==14&&a[0]=="--gate-lease-receiver"&&a[13]=="GATE_HANDOFF_DIAGNOSTIC_ONLY_V1","RECEIVER_ARGUMENTS");
            long started=a[11]=="0"?0:(long)NativeScope.Number(a[11],(ulong)Int64.MaxValue);
            long deadline=(long)NativeScope.Number(a[12],(ulong)Int64.MaxValue);
            var pin=new HandoffPin(a[1],a[2],new ProcessStamp((uint)NativeScope.Number(a[3],UInt32.MaxValue),NativeScope.Number(a[4],UInt64.MaxValue)),
                new GateStamp(a[8],a[9],a[10]),started,deadline);
            var plan=new RestrictedInheritancePlan(new IntPtr((long)NativeScope.Number(a[5],(ulong)Int64.MaxValue)),new IntPtr((long)NativeScope.Number(a[6],(ulong)Int64.MaxValue)),new IntPtr((long)NativeScope.Number(a[7],(ulong)Int64.MaxValue)));
            return new ReceiverInput{Pin=pin,Handles=plan};
        }
    }
    internal static class NativeEventOutput
    {
        internal static Dictionary<string,object> ArmPayload(CoordinatorInput input,long deadline)
        {return new Dictionary<string,object>{{"deadline_ms",deadline},{"parent_pid",(long)input.Parent.Pid},{"parent_creation",input.Parent.Creation.ToString(CultureInfo.InvariantCulture)}};}
        internal static byte[] Encode(string kind,CoordinatorInput input,object result)
        {
            HCheck.Need(input!=null&&input.Self!=null&&!input.Self.Same(input.Parent),"OUTER_PROCESS_IDENTITY_REQUIRED");
            var message=new Dictionary<string,object>{{"kind",kind},{"run_id",input.Run},{"nonce",input.Nonce},{"pid",(long)input.Self.Pid},{"creation_filetime",input.Self.Creation.ToString(CultureInfo.InvariantCulture)},
                {"native_execution",true},{"result",result},{"claims",NativeScope.Claims()}};
            byte[] raw=CanonicalJson.Encode(message);HCheck.Need(raw.Length<=65536,"OUTER_EVENT_LIMIT");return raw;
        }
        internal static void Write(string kind,CoordinatorInput input,object result)
        {
            byte[] raw=Encode(kind,input,result);Stream stream=Console.OpenStandardOutput();stream.Write(raw,0,raw.Length);stream.Flush(); // watchdog remains active through output
        }
    }
    internal static class GateNativeCoordinatorEntryPoint
    {
        public static int Main(string[] args)
        {
            CoordinatorInput input=null;WindowsCoordinatorCalls backend=null;NativeHandoffCoordinator coordinator=null;ParentDeadlineWatchdog watchdog=null;
            try
            {
                input=CoordinatorInput.Parse(args);HCheck.Need(IntPtr.Size==8&&Environment.OSVersion.Platform==PlatformID.Win32NT,"WINDOWS_X64_REQUIRED");
                input.Self=Win.Current();NativeClock clock=new NativeClock();long started=clock.Milliseconds;
                watchdog=new ParentDeadlineWatchdog(input.Parent,checked(started+8000));
                NativeEventOutput.Write("GATE_NATIVE_COORDINATOR_ARMED",input,NativeEventOutput.ArmPayload(input,started+8000));
                string binaries=Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
                backend=new WindowsCoordinatorCalls(input.FixtureDirectory(),binaries,input.ChildHash,input.Run,input.Nonce,input.GateId,input.Volume,started,clock);
                HCheck.Need(backend.Pin.Parent.Same(input.Self),"COORDINATOR_SELF_ID_CHANGED");
                coordinator=NativeHandoffCoordinator.ForWindows(backend,clock,backend.Pin);
                Dictionary<string,object> completed=coordinator.Run();
                HCheck.Need(clock.Milliseconds<started+8000,"DEADLINE_BEFORE_OUTER_RESULT");
                NativeEventOutput.Write("GATE_NATIVE_COORDINATOR_RESULT",input,new Dictionary<string,object>{{"handoff",completed},{"backend",backend.Diagnostics()}});
                HCheck.Need(clock.Milliseconds<started+8000,"DEADLINE_BEFORE_OUTER_FINAL");
                NativeEventOutput.Write("GATE_NATIVE_COORDINATOR_FINAL",input,new Dictionary<string,object>{{"complete",true},{"owned_handoff_handles_closed",true},{"watchdog_active_through_output",true},{"watchdog_parent_close_pending",true},{"production_basis_issued",false}});
                watchdog.Finish();watchdog=null;HCheck.Need(clock.Milliseconds<started+8000,"DEADLINE_AFTER_SUPERVISION_CLOSE");return 0;
            }
            catch(Exception error)
            {
                if(backend!=null)backend.AbortPreservingUnknown();
                if(input!=null)
                {
                    try{NativeEventOutput.Write("GATE_NATIVE_COORDINATOR_ERROR",input,new Dictionary<string,object>{{"error_type",error.GetType().Name},{"error",error.Message},
                        {"handoff",coordinator==null?null:coordinator.Export()},{"backend",backend==null?null:backend.Diagnostics()}});}catch{}
                }
                return 2;
            }
            finally{if(watchdog!=null){try{watchdog.Finish();}catch{Win.EmergencyExit();}}}
        }
    }
    internal static class GateNativeReceiverEntryPoint
    {
        public static int Main(string[] args)
        {
            ParentDeadlineWatchdog watchdog=null;WindowsReceiverCalls calls=null;
            try
            {
                ReceiverInput input=ReceiverInput.Parse(args);HCheck.Need(IntPtr.Size==8&&Environment.OSVersion.Platform==PlatformID.Win32NT,"WINDOWS_RECEIVER_REQUIRED");
                NativeClock clock=new NativeClock();watchdog=new ParentDeadlineWatchdog(input.Pin.Parent,input.Pin.DeadlineMs);
                calls=new WindowsReceiverCalls(input.Handles,input.Pin,clock);
                NativeReceiverScope receiver=NativeReceiverScope.ForWindows(calls,clock,input.Pin,Win.Current());
                receiver.Perform(WireStep.Ready);calls.Command(2);receiver.Perform(WireStep.HeldAfterProbe);
                calls.Command(3);receiver.Perform(WireStep.GateClosed);
                HCheck.Need(receiver.Complete&&calls.Finish(),"RECEIVER_FINALIZATION");
                watchdog.Finish();watchdog=null;HCheck.Need(clock.Milliseconds<input.Pin.DeadlineMs,"RECEIVER_FINAL_DEADLINE");return 0;
            }
            catch(Exception error){if(calls!=null){calls.ReportFailure(error);calls.Abort();}return 2;}
            finally{if(watchdog!=null){try{watchdog.Finish();}catch{Win.EmergencyExit();}}}
        }
    }
}
