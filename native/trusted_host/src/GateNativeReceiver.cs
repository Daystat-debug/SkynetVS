using System;
using System.Collections.Generic;
using System.Threading;
using SkynetVS.G1.GateLeaseHandoffV1;

namespace SkynetVS.G1.GateLeaseHandoffNativeV1
{
    internal interface IOperationalReceiverCalls
    {
        string Domain {get;}
        bool BindParent(ProcessStamp expected);
        bool ClearInheritedFlags();
        GateStamp ObserveInheritedGate();
        bool CloseGateOnce();
        void Send(ChildMessage message);
    }
    internal interface ITestOperationalReceiverCalls : IOperationalReceiverCalls { }
    internal sealed class NativeReceiverScope
    {
        private readonly IOperationalReceiverCalls calls;
        private readonly HandoffPin pin;
        private readonly ProcessStamp child;
        private readonly HandoffWindow window;
        private readonly string domain;
        private readonly int ownerThread=Thread.CurrentThread.ManagedThreadId;
        private int phase;
        private bool failed,busy;
        private NativeReceiverScope(IOperationalReceiverCalls provider,IHandoffClock clock,HandoffPin expected,ProcessStamp own,string sourceDomain)
        {HCheck.Need(provider!=null&&expected!=null&&own!=null&&own.Pid!=expected.Parent.Pid,"NATIVE_RECEIVER_INPUTS");calls=provider;pin=expected;child=own;domain=sourceDomain;window=new HandoffWindow(clock,pin.StartedMs,pin.DeadlineMs);}
        internal static NativeReceiverScope ForWindows(WindowsReceiverCalls calls,IHandoffClock clock,HandoffPin pin,ProcessStamp own)
        {return new NativeReceiverScope(calls,clock,pin,own,NativeScope.Domain);}
        internal static NativeReceiverScope ForTests(ITestOperationalReceiverCalls calls,IHandoffClock clock,HandoffPin pin,ProcessStamp own)
        {return new NativeReceiverScope(calls,clock,pin,own,NativeScope.TestDomain);}
        private void Check(){HCheck.Need(!failed&&calls.Domain==domain,"RECEIVER_DOMAIN_OR_STOPPED");window.Check();HCheck.Need(!failed&&calls.Domain==domain,"RECEIVER_DOMAIN_OR_STOPPED");}
        internal void Perform(WireStep step)
        {
            HCheck.Need(Thread.CurrentThread.ManagedThreadId==ownerThread,"RECEIVER_WRONG_THREAD");
            if(busy||failed||(int)step!=phase+1||!Enum.IsDefined(typeof(WireStep),step))
            {failed=true;window.Revoke();throw new HandoffFailure("RECEIVER_SEQUENCE_OR_REENTRANCY");}
            busy=true;
            try
            {
                Check();
                if(phase==0)
                {HCheck.Need(calls.BindParent(pin.Parent),"RECEIVER_PARENT_BINDING");Check();HCheck.Need(calls.ClearInheritedFlags(),"RECEIVER_INHERITANCE_FLAGS");Check();}
                HCheck.Need(pin.Gate.Same(calls.ObserveInheritedGate()),"RECEIVER_GATE_CHANGED");Check();
                if(step==WireStep.GateClosed){HCheck.Need(calls.CloseGateOnce(),"RECEIVER_GATE_CLOSE_UNCONFIRMED");Check();}
                calls.Send(new ChildMessage(pin,child,step,(int)step,true,step==WireStep.GateClosed));Check();phase++;
            }
            catch{failed=true;window.Revoke();throw;}
            finally{busy=false;}
        }
        internal bool Complete {get{return !failed&&phase==3;}}
    }
    internal sealed class WindowsReceiverCalls : IOperationalReceiverCalls
    {
        private readonly HandleLedger ledger=new HandleLedger(Win.Close);
        private readonly HandoffPin pin;
        private readonly ProcessStamp self;
        private readonly HandoffWindow window;
        private readonly BoundedPipe channel;
        private readonly OwnedHandle gate,control,report;
        private OwnedHandle parent;
        internal WindowsReceiverCalls(RestrictedInheritancePlan plan,HandoffPin binding,IHandoffClock clock)
        {
            HCheck.Need(plan!=null&&binding!=null,"RECEIVER_HANDLES_REQUIRED");pin=binding;
            // Adopt immediately; handles belong to this process, never close handles in the parent.
            gate=ledger.Add("InheritedGate",plan.GateCopy);control=ledger.Add("InheritedControlRead",plan.ControlRead);report=ledger.Add("InheritedReportWrite",plan.ReportWrite);
            self=Win.Current();window=new HandoffWindow(clock,pin.StartedMs,pin.DeadlineMs);channel=new BoundedPipe(new WindowsPipeCalls(),Check);
        }
        public string Domain {get{return NativeScope.Domain;}}
        private void Check()
        {NativeHealth.Check();window.Check();if(parent!=null)HCheck.Need(Win.Wait(parent.Use(),0)==258,"PARENT_EXITED");}
        public bool BindParent(ProcessStamp expected)
        {
            Check();HCheck.Need(parent==null&&pin.Parent.Same(expected),"PARENT_BIND_ONCE");parent=ledger.Add("BoundParentProcess",Win.OpenParent(expected.Pid));
            return expected.Same(Win.Identity(parent.Use()))&&Win.Wait(parent.Use(),0)==258;
        }
        public bool ClearInheritedFlags()
        {
            Check();Win.RequireGateAccess(gate.Use(),true);Win.RequireEndpoint(control.Use(),true,true);Win.RequireEndpoint(report.Use(),false,true);
            Win.SetInheritance(gate.Use(),false);Win.SetInheritance(control.Use(),false);Win.SetInheritance(report.Use(),false);return true;
        }
        public GateStamp ObserveInheritedGate(){Check();Win.RequireGateAccess(gate.Use(),false);return Win.ObserveGate(gate.Use());}
        public bool CloseGateOnce(){Check();ledger.CloseOnce(gate);return true;}
        public void Send(ChildMessage message){Check();message.Match(pin,self,message.Step);channel.Send(report.Use(),GateHandoffWire.Encode(message));}
        internal void Command(int step){Check();GateCommandWire.Require(channel.Receive(control.Use()),pin,self,step);Check();}
        internal bool Finish()
        {
            Check();HCheck.Need(gate.State==OwnedState.Closed,"NO_WORK_AFTER_GATE_CLOSE");
            // No more gate operations; only endpoint/process resource cleanup after CLOSED message.
            ledger.CloseOnce(control);ledger.CloseOnce(report);ledger.CloseOnce(parent);window.Check();return ledger.Empty;
        }
        internal void ReportFailure(Exception error)
        {
            if(NativeHealth.Poisoned||ledger.Poisoned||report.State!=OwnedState.Owned)return;
            // Error-only output. Never a new lease window; outer job/watchdog still apply.
            try{byte[] frame=ReceiverFailureWire.Encode(pin,self,error);int n=new WindowsPipeCalls().Write(report.Use(),frame,0,frame.Length);HCheck.Need(n==frame.Length,"ERROR_FRAME_SHORT_WRITE");}catch{}
        }
        internal void Abort()
        {if(!NativeHealth.Poisoned&&!ledger.Poisoned)ledger.CloseKnownReverse();}
    }
}
