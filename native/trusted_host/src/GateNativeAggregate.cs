using System;
using System.Collections.Generic;
using SkynetVS.G1.GateLeaseHandoffV1;

namespace SkynetVS.G1.GateLeaseHandoffNativeV1
{
    // A dedicated coordinator process must be used: no concurrent broad-inheritance launcher is allowed.
    internal sealed class WindowsCoordinatorCalls : IHandoffCoordinatorCalls
    {
        private readonly HandleLedger ledger=new HandleLedger(Win.Close);
        private readonly string directory;
        private readonly HandoffWindow window;
        private readonly BoundedPipe channel;
        private OwnedHandle root,gate,image,job,copy,controlRead,controlWrite,reportRead,reportWrite,process,thread;
        private RestrictedInheritancePlan plan;
        private ProcessStamp child;
        private bool prepared,resumed,ready,gateClosedMessage,exitConfirmed,aborted;
        private int probeCount;
        private bool jobMembershipVerified,endpointsVerified;
        private readonly List<string> receivedFrames=new List<string>(),probeStatuses=new List<string>();
        internal HandoffPin Pin { get; private set; }
        public string Domain { get { return NativeScope.Domain; } }
        internal WindowsCoordinatorCalls(string fixtureDirectory,string binaryDirectory,string childHash,string run,string nonce,
            string gateId,string volume,long started,IHandoffClock clock)
        {
            HCheck.Need(Environment.OSVersion.Platform==PlatformID.Win32NT&&IntPtr.Size==8,"WINDOWS_X64_ONLY");
            directory=binaryDirectory;window=new HandoffWindow(clock,started,checked(started+8000));channel=new BoundedPipe(new WindowsPipeCalls(),Check);
            try
            {
                Check();root=ledger.Add("FixtureRoot",Win.OpenDirectory(fixtureDirectory));Win.RequireDirectory(root.Use());Check();
                GateOpenResult opened=Win.OpenGate(root.Use(),false);
                if(opened.Status!=0)throw new HandoffFailure("OPEN_ORIGINAL_GATE_"+unchecked((uint)opened.Status).ToString("x8"));
                gate=ledger.Add("OriginalGate",opened.Handle);Win.RequireGateAccess(gate.Use(),false);
                GateStamp observed=Win.ObserveGate(gate.Use());
                HCheck.Need(observed.FileId==gateId&&observed.Volume==volume,"FIXTURE_GATE_IDENTITY_MISMATCH");
                Pin=new HandoffPin(run,nonce,Win.Current(),observed,started,checked(started+8000));
                image=ledger.Add("ReceiverImage",Win.HoldImage(directory+"\\GateLeaseHandoffChild.exe"));
                Win.RequireImageBytes(image.Use(),childHash);Check();
            }
            catch{AbortPreservingUnknown();throw;}
        }
        private void Check(){NativeHealth.Check();window.Check();HCheck.Need(!aborted,"COORDINATOR_ABORTED");}
        public GateStamp ObserveOriginal(){Check();return Win.ObserveGate(gate.Use());}
        public RestrictedInheritancePlan PrepareReadOnlyGateAndIpc()
        {
            Check();HCheck.Need(!prepared,"PREPARE_ONCE");prepared=true;
            job=ledger.Add("ContainmentJob",Win.CreateContainedJob());
            NativePipePair control=Win.Pipe();
            OwnedHandle rawControlRead=ledger.Add("RawChildControlRead",control.Read);
            OwnedHandle rawControlWrite=ledger.Add("RawParentControlWrite",control.Write);
            NormalizedPipePair normalizedControl=PipeEndpointNarrower.NarrowPair(new WindowsPipeNarrowCalls(),ledger,
                rawControlRead,rawControlWrite,"ChildControlRead","ParentControlWrite",Check);
            controlRead=normalizedControl.Read;controlWrite=normalizedControl.Write;
            NativePipePair report=Win.Pipe();
            OwnedHandle rawReportRead=ledger.Add("RawParentReportRead",report.Read);
            OwnedHandle rawReportWrite=ledger.Add("RawChildReportWrite",report.Write);
            NormalizedPipePair normalizedReport=PipeEndpointNarrower.NarrowPair(new WindowsPipeNarrowCalls(),ledger,
                rawReportRead,rawReportWrite,"ParentReportRead","ChildReportWrite",Check);
            reportRead=normalizedReport.Read;reportWrite=normalizedReport.Write;
            HCheck.Need(rawControlRead.State==OwnedState.Closed && rawControlWrite.State==OwnedState.Closed &&
                rawReportRead.State==OwnedState.Closed && rawReportWrite.State==OwnedState.Closed,"RAW_PIPE_HANDLES_NOT_CLOSED");
            GateDuplicateOutcome duplicated=NativeGateCopyPrimitive.CreateInheritableReadCopy(gate.Use());
            if(duplicated.CompletionUnknown){NativeHealth.Poison();throw new HandoffFailure("DUPLICATE_COMPLETION_UNKNOWN");}
            HCheck.Need(duplicated.Success,"DUPLICATE_GATE_FAILED");copy=ledger.Add("TransferGateCopy",duplicated.Copy);
            Win.RequireGateAccess(copy.Use(),true);HCheck.Need(Pin.Gate.Same(Win.ObserveGate(copy.Use())),"GATE_COPY_IDENTITY");
            Win.SetInheritance(controlRead.Use(),true);Win.SetInheritance(reportWrite.Use(),true);endpointsVerified=true;
            plan=new RestrictedInheritancePlan(copy.Use(),controlRead.Use(),reportWrite.Use());Check();return plan;
        }
        public ProcessStamp StartSuspended(RestrictedInheritancePlan requested)
        {
            Check();HCheck.Need(Object.ReferenceEquals(requested,plan)&&process==null,"EXACT_OWNED_LAUNCH_PLAN");
            RestrictedLaunchRequest request=new RestrictedLaunchRequest(plan,Pin,directory,Win.WindowsDirectory());
            NativeLaunchOutcome launched=ContainedGateLaunch.Start(request,job.Use());
            if(HCheck.Handle(launched.Process.Process))process=ledger.Add("ReceiverProcess",launched.Process.Process);
            if(HCheck.Handle(launched.Process.Thread))thread=ledger.Add("ReceiverThread",launched.Process.Thread);
            HCheck.Need(!launched.UnknownCompletion&&launched.Created&&launched.Failure==null&&launched.CleanupFailure==null,"NATIVE_CREATE_NOT_CLEAN");
            child=Win.Identity(process.Use());HCheck.Need(child.Pid==launched.Process.Pid&&child.Pid!=Pin.Parent.Pid,"CREATED_HELD_PROCESS_ID");
            HCheck.Need(Win.InJob(process.Use(),job.Use()),"CREATED_CHILD_NOT_IN_OWNED_JOB");jobMembershipVerified=true;
            Win.RequireImage(process.Use(),request.Application);Win.RequireFlags(process.Use(),false);Win.RequireFlags(thread.Use(),false);
            Check();return child;
        }
        public CloseReceipt CloseTransferCopy()
        {
            Check();HCheck.Need(child!=null&&!resumed,"CLOSE_TRANSFER_BEFORE_RESUME");
            ledger.CloseOnce(copy);ledger.CloseOnce(controlRead);ledger.CloseOnce(reportWrite); // parent must not retain child IPC endpoints
            return new CloseReceipt(true,false);
        }
        public bool ResumeOnce(ProcessStamp expected)
        {
            Check();HCheck.Need(!resumed&&child.Same(expected)&&copy.State==OwnedState.Closed&&controlRead.State==OwnedState.Closed&&reportWrite.State==OwnedState.Closed,"RESUME_OWNERSHIP");
            HCheck.Need(expected.Same(Win.Identity(process.Use()))&&Win.Wait(process.Use(),0)==258,"RESUME_CHILD_IDENTITY");
            resumed=true;return Win.Resume(thread.Use())==1;
        }
        public ChildMessage Receive(WireStep step)
        {
            Check();HCheck.Need(resumed&&child!=null,"RECEIVE_BEFORE_RESUME");
            byte[] frame=channel.Receive(reportRead.Use());HCheck.Need(receivedFrames.Count<3,"EXTRA_REPLY_FRAME");receivedFrames.Add(Convert.ToBase64String(frame));
            ReceiverFailureWire.RejectIfFailure(frame,Pin,child);
            ChildMessage message=GateHandoffWire.Decode(frame);message.Match(Pin,child,step);
            if(step==WireStep.Ready)ready=true;if(step==WireStep.GateClosed)gateClosedMessage=true;return message;
        }
        public CloseReceipt CloseOriginalGate()
        {Check();HCheck.Need(ready&&copy.State==OwnedState.Closed,"READY_REQUIRED_BEFORE_ORIGINAL_CLOSE");ledger.CloseOnce(gate);return new CloseReceipt(true,true);}
        public bool ChildAlive(ProcessStamp expected)
        {Check();return child.Same(expected)&&expected.Same(Win.Identity(process.Use()))&&Win.Wait(process.Use(),0)==258;}
        public ExclusiveProbe ProbeExclusive()
        {
            Check();HCheck.Need(gate.State==OwnedState.Closed&&copy.State==OwnedState.Closed&&probeCount<2,"NO_PARENT_GATE_COPY");
            if(probeCount==1)HCheck.Need(exitConfirmed,"POST_PROBE_NEEDS_CONFIRMED_EXIT");probeCount++;
            GateOpenResult opened=Win.OpenGate(root.Use(),true);probeStatuses.Add(unchecked((uint)opened.Status).ToString("x8"));
            if(opened.Status!=0)return new ExclusiveProbe(opened.Status,false,false,false,null);
            OwnedHandle probe=ledger.Add("ExclusiveProbe"+probeCount.ToString(),opened.Handle);
            GateStamp stamp;
            try{stamp=Win.ObserveGate(probe.Use());}
            finally{if(!NativeHealth.Poisoned)ledger.CloseOnce(probe);}
            return new ExclusiveProbe(0,true,probe.State==OwnedState.Closed,false,stamp);
        }
        public void RequestHeldCheck(){Check();HCheck.Need(probeCount==1&&!exitConfirmed,"HELD_CHECK_SEQUENCE");channel.Send(controlWrite.Use(),GateCommandWire.Encode(Pin,child,2));}
        public void RequestRelease(){Check();HCheck.Need(probeCount==1&&!exitConfirmed,"RELEASE_SEQUENCE");channel.Send(controlWrite.Use(),GateCommandWire.Encode(Pin,child,3));}
        public ExitReceipt WaitForExit(ProcessStamp expected)
        {
            Check();HCheck.Need(gateClosedMessage&&expected.Same(child),"EXIT_REQUIRES_CLOSED_MESSAGE");
            while(Win.Wait(process.Use(),20)!=0)Check();Check();
            HCheck.Need(expected.Same(Win.Identity(process.Use())),"EXIT_HELD_PROCESS_MISMATCH");
            uint code=Win.ExitCode(process.Use());exitConfirmed=true;return new ExitReceipt(child,true,code,false);
        }
        public bool CloseCommunicationAndProcess()
        {
            Check();HCheck.Need(exitConfirmed&&!aborted&&probeCount==2,"FINAL_CLEANUP_SEQUENCE");
            channel.RequirePeerEof(reportRead.Use());ledger.CloseOnce(controlWrite);ledger.CloseOnce(reportRead);
            ledger.CloseOnce(thread);ledger.CloseOnce(process);ledger.CloseOnce(image);ledger.CloseOnce(root);ledger.CloseOnce(job);
            Check();return ledger.Empty;
        }
        public void AbortPreservingUnknown()
        {
            if(aborted)return;aborted=true;window.Revoke();
            bool safe=process==null;
            if(job!=null&&job.State==OwnedState.Owned)
            {
                Win.EmergencyStopJob(job.Value);
                if(process!=null&&process.State==OwnedState.Owned)safe=Win.EmergencyWait(process.Value,1000);
            }
            // Never dispose buffers/handles on unknown completion or unknown child exit. Process teardown owns that case.
            if(safe&&!NativeHealth.Poisoned&&!ledger.Poisoned)ledger.CloseKnownReverse();
        }
        internal Dictionary<string,object> Diagnostics()
        {return new Dictionary<string,object>{{"backend",Domain},{"job_membership_observed",jobMembershipVerified},{"child_exit_confirmed",exitConfirmed},
            {"aborted",aborted},{"all_owned_handles_closed",ledger.Empty},{"close_order",ledger.Closed.ToArray()},
            {"cleanup_errors",ledger.Errors.ToArray()},{"native_domain_terminal",NativeHealth.Poisoned},
            {"instrumented_win_calls",Win.Entries},{"baseline_file_calls",SkynetVS.G1.SameHandleV1.NativeFileApi.EntryCount},{"baseline_duplicate_calls",WindowsReadGateDuplicateApi.Entries},{"clock_watchdog_calls_not_in_counter",true},{"pipe_endpoint_rights_observed",endpointsVerified},{"reply_frames_base64",receivedFrames.ToArray()},{"probe_statuses",probeStatuses.ToArray()},{"protected_work_after_gate_close",false}};}
    }
}
