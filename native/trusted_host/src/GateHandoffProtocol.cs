using System;
using System.Collections.Generic;
using System.Threading;

namespace SkynetVS.G1.GateLeaseHandoffV1
{
    internal sealed class CloseReceipt
    {
        internal readonly bool Completed, AllLocalGateCopiesClosed;
        internal CloseReceipt(bool completed, bool allCopies) { Completed = completed; AllLocalGateCopiesClosed = allCopies; }
    }
    internal sealed class ExclusiveProbe
    {
        internal readonly int NtStatus;
        internal readonly bool HandleReturned, Closed, WritePerformed;
        internal readonly GateStamp Object;
        internal ExclusiveProbe(int status, bool returned, bool closed, bool written, GateStamp stamp)
        { NtStatus = status; HandleReturned = returned; Closed = closed; WritePerformed = written; Object = stamp; }
    }
    internal sealed class ExitReceipt
    {
        internal readonly ProcessStamp Child;
        internal readonly bool Signaled, TerminationAttempted;
        internal readonly uint ExitCode;
        internal ExitReceipt(ProcessStamp child, bool signaled, uint code, bool killed)
        { Child = child; Signaled = signaled; ExitCode = code; TerminationAttempted = killed; }
    }
    internal interface IHandoffCoordinatorCalls
    {
        string Domain { get; }
        GateStamp ObserveOriginal();
        RestrictedInheritancePlan PrepareReadOnlyGateAndIpc();
        ProcessStamp StartSuspended(RestrictedInheritancePlan plan);
        bool ResumeOnce(ProcessStamp child);
        ChildMessage Receive(WireStep step);
        CloseReceipt CloseTransferCopy();
        CloseReceipt CloseOriginalGate();
        bool ChildAlive(ProcessStamp child);
        ExclusiveProbe ProbeExclusive();
        void RequestHeldCheck();
        void RequestRelease();
        ExitReceipt WaitForExit(ProcessStamp child);
        bool CloseCommunicationAndProcess();
        // Must preserve ownership on unknown launch/exit. NO arbitrary kill-by-PID or success conversion.
        // Source-only implementation is fake. A real aggregate provider requires a new reviewed native supervisor.
        void AbortPreservingUnknown();
    }
    internal interface IFakeHandoffCoordinatorCalls : IHandoffCoordinatorCalls { }
    internal sealed class GateHandoffCoordinator
    {
        internal const string FakeDomain = "SYNTHETIC_GATE_HANDOFF_ORCHESTRATION_ONLY";
        internal const int SharingViolation = unchecked((int)0xc0000043);
        private readonly IFakeHandoffCoordinatorCalls calls;
        private readonly HandoffWindow window;
        private readonly HandoffPin pin;
        private readonly int thread = Thread.CurrentThread.ManagedThreadId;
        private bool used, busy, failed, complete;
        private readonly List<string> trace = new List<string>();
        private readonly List<string> cleanupErrors = new List<string>();
        internal GateHandoffCoordinator(IFakeHandoffCoordinatorCalls provider, IHandoffClock clock, HandoffPin expected)
        { HCheck.Need(provider != null && expected != null, "COORDINATOR_INPUTS"); calls = provider; window = new HandoffWindow(clock, expected.StartedMs, expected.DeadlineMs); pin = expected; Check(); }
        private void Origin() { HCheck.Need(calls.Domain == FakeDomain, "COORDINATOR_ORIGIN_CHANGED"); }
        private void Check() { Origin(); window.Check(); Origin(); HCheck.Need(!failed, "COORDINATOR_STOPPED"); }
        internal void Revoke() { failed = true; window.Revoke(); }
        private T Step<T>(string name, Func<T> action)
        { Check(); trace.Add(name); T result = action(); Check(); return result; }
        private void StepAction(string name, Action action) { Step<bool>(name, delegate { action(); return true; }); }
        internal Dictionary<string, object> Run()
        {
            HCheck.Need(Thread.CurrentThread.ManagedThreadId == thread, "WRONG_THREAD");
            if (busy) { Revoke(); throw new HandoffFailure("COORDINATOR_REENTRANT"); }
            HCheck.Need(!used && !failed, "SINGLE_USE_COORDINATOR"); used = busy = true;
            try
            {
                HCheck.Need(pin.Gate.Same(Step("observe_original", calls.ObserveOriginal)), "ORIGINAL_GATE_MISMATCH");
                RestrictedInheritancePlan plan = Step("prepare_exact_three_handles", calls.PrepareReadOnlyGateAndIpc);
                HCheck.Need(plan != null, "MISSING_INHERITANCE_PLAN");
                ProcessStamp child = Step("start_suspended", delegate { return calls.StartSuspended(plan); });
                HCheck.Need(child != null && child.Pid != pin.Parent.Pid, "CREATED_CHILD_IDENTITY");
                // Close the parent's temporary inheritable copy immediately after creation, before Resume.
                // The original still holds the gate; the suspended child owns its inherited copy already.
                CloseReceipt transfer = Step("close_parent_transfer_copy", calls.CloseTransferCopy);
                HCheck.Need(transfer != null && transfer.Completed, "TRANSFER_COPY_CLOSE_UNCONFIRMED");
                HCheck.Need(Step("resume_once", delegate { return calls.ResumeOnce(child); }), "RESUME_NOT_CONFIRMED");
                Step("child_ready", delegate { return calls.Receive(WireStep.Ready); }).Match(pin, child, WireStep.Ready);
                CloseReceipt original = Step("close_parent_original_gate", calls.CloseOriginalGate);
                HCheck.Need(original != null && original.Completed && original.AllLocalGateCopiesClosed, "PARENT_GATE_COPIES_REMAIN");
                HCheck.Need(Step("child_alive_before_probe", delegate { return calls.ChildAlive(child); }), "CHILD_EXITED_EARLY");
                ExclusiveProbe blocked = Step("exclusive_while_only_child_holds", calls.ProbeExclusive);
                HCheck.Need(blocked != null && blocked.NtStatus == SharingViolation && !blocked.HandleReturned
                    && !blocked.WritePerformed, "EXACT_SHARING_REFUSAL_REQUIRED");
                StepAction("request_child_held_recheck", calls.RequestHeldCheck);
                Step("child_still_holds_same_gate", delegate { return calls.Receive(WireStep.HeldAfterProbe); }).Match(pin, child, WireStep.HeldAfterProbe);
                HCheck.Need(Step("child_alive_after_probe", delegate { return calls.ChildAlive(child); }), "CHILD_EXITED_BEFORE_RELEASE");
                StepAction("request_child_release", calls.RequestRelease);
                Step("child_gate_closed", delegate { return calls.Receive(WireStep.GateClosed); }).Match(pin, child, WireStep.GateClosed);
                ExitReceipt exit = Step("wait_same_child_exit", delegate { return calls.WaitForExit(child); });
                HCheck.Need(exit != null && child.Same(exit.Child) && exit.Signaled && exit.ExitCode == 0 && !exit.TerminationAttempted,
                    "CLEAN_CHILD_EXIT_REQUIRED");
                ExclusiveProbe released = Step("exclusive_after_confirmed_exit", calls.ProbeExclusive);
                HCheck.Need(released != null && released.NtStatus == 0 && released.HandleReturned && released.Closed
                    && !released.WritePerformed && pin.Gate.Same(released.Object), "POST_EXIT_SAME_GATE_REQUIRED");
                HCheck.Need(Step("close_ipc_and_process", calls.CloseCommunicationAndProcess), "COORDINATOR_CLEANUP_INCOMPLETE");
                Check(); complete = true;
                return Export();
            }
            catch
            {
                failed = true; window.Revoke();
                // A changed provider/origin is not dispatched to again. An outer future supervisor must resolve it.
                if (calls.Domain == FakeDomain) { try { calls.AbortPreservingUnknown(); } catch (Exception cleanup) { cleanupErrors.Add(cleanup.GetType().Name + ": " + cleanup.Message); } }
                throw;
            }
            finally { busy = false; }
        }
        internal Dictionary<string, object> Export()
        { return new Dictionary<string, object> { {"complete", complete}, {"failed", failed},
            {"source_domain", FakeDomain}, {"native_execution", false},
            {"status", complete ? "SIMULATED_GATE_HANDOFF_COMPLETE_NOT_P00" : "HANDOFF_NOT_COMPLETED"},
            {"trace", trace.ToArray()}, {"cleanup_errors", cleanupErrors.ToArray()}, {"claims", HandoffClaims.Closed()} }; }
    }

    internal interface IFakeHandoffChildCalls
    {
        string Domain { get; }
        bool BindParent(ProcessStamp parent);
        bool ClearInheritedFlags();
        GateStamp ObserveInheritedGate();
        bool CloseGateOnce();
        void Send(ChildMessage message);
    }
    // Receiver owns the inherited handle. It NEVER reopens gate by path or duplicates it onwards.
    internal sealed class GateHandoffChildScope
    {
        internal const string FakeDomain = "SYNTHETIC_GATE_RECEIVER_ONLY";
        private readonly IFakeHandoffChildCalls calls;
        private readonly HandoffPin pin;
        private readonly ProcessStamp child;
        private readonly HandoffWindow window;
        private readonly int thread = Thread.CurrentThread.ManagedThreadId;
        private int phase;
        private bool failed, busy;
        internal GateHandoffChildScope(IFakeHandoffChildCalls provider, IHandoffClock clock, HandoffPin expected, ProcessStamp own)
        { HCheck.Need(provider != null && expected != null && own != null && own.Pid != expected.Parent.Pid, "CHILD_INPUTS");
          calls = provider; pin = expected; child = own; window = new HandoffWindow(clock, expected.StartedMs, expected.DeadlineMs); }
        private void Check()
        { HCheck.Need(!failed && calls.Domain == FakeDomain, "CHILD_STOPPED_OR_ORIGIN"); window.Check();
          HCheck.Need(calls.Domain == FakeDomain && !failed, "CHILD_STOPPED_OR_ORIGIN"); }
        private void Enter(int expected)
        {
            HCheck.Need(Thread.CurrentThread.ManagedThreadId == thread, "WRONG_THREAD");
            if (busy) { failed = true; window.Revoke(); throw new HandoffFailure("CHILD_REENTRANT"); }
            if (failed || phase != expected) { failed = true; window.Revoke(); throw new HandoffFailure("CHILD_PROTOCOL_SEQUENCE"); } busy = true;
        }
        internal void Ready() { Perform(0, WireStep.Ready); }
        internal void HeldAfterProbe() { Perform(1, WireStep.HeldAfterProbe); }
        internal void Release() { Perform(2, WireStep.GateClosed); }
        private void Perform(int expected, WireStep message)
        {
            Enter(expected);
            try
            {
                Check();
                if (phase == 0)
                {
                    HCheck.Need(calls.BindParent(pin.Parent), "PARENT_NOT_BOUND"); Check();
                    HCheck.Need(calls.ClearInheritedFlags(), "INHERITANCE_NOT_CLEARED"); Check();
                }
                HCheck.Need(pin.Gate.Same(calls.ObserveInheritedGate()), "INHERITED_GATE_MISMATCH"); Check();
                if (message == WireStep.GateClosed) { HCheck.Need(calls.CloseGateOnce(), "CHILD_GATE_CLOSE_UNCONFIRMED"); Check(); }
                calls.Send(new ChildMessage(pin, child, message, (int)message, true, message == WireStep.GateClosed));
                Check(); phase++;
            }
            catch { failed = true; window.Revoke(); throw; }
            finally { busy = false; }
        }
        internal bool CanReturnZero { get { return !failed && phase == 3; } }
    }
}
