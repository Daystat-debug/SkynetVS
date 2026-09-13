using System;
using System.Collections.Generic;
using System.Threading;
using SkynetVS.G1.GateLeaseHandoffV1;

namespace SkynetVS.G1.GateLeaseHandoffNativeV1
{
    internal sealed class NativeHandoffCoordinator
    {
        internal const string FakeDomain = NativeScope.TestDomain;
        private readonly bool native;
        internal const int SharingViolation = unchecked((int)0xc0000043);
        private readonly IHandoffCoordinatorCalls calls;
        private readonly HandoffWindow window;
        private readonly HandoffPin pin;
        private readonly int thread = Thread.CurrentThread.ManagedThreadId;
        private bool used, busy, failed, complete;
        private readonly List<string> trace = new List<string>();
        private readonly List<string> cleanupErrors = new List<string>();
        private NativeHandoffCoordinator(IHandoffCoordinatorCalls provider, IHandoffClock clock, HandoffPin expected, bool actual)
        { HCheck.Need(provider != null && expected != null, "COORDINATOR_INPUTS"); calls = provider; native = actual; window = new HandoffWindow(clock, expected.StartedMs, expected.DeadlineMs); pin = expected; Check(); }
        internal static NativeHandoffCoordinator ForWindows(WindowsCoordinatorCalls calls, IHandoffClock clock, HandoffPin pin)
        { HCheck.Need(calls!=null,"WINDOWS_COORDINATOR_REQUIRED"); return new NativeHandoffCoordinator(calls,clock,pin,true); }
        internal static NativeHandoffCoordinator ForTests(IFakeHandoffCoordinatorCalls calls, IHandoffClock clock, HandoffPin pin)
        { HCheck.Need(calls!=null && calls.Domain==FakeDomain,"TEST_COORDINATOR_REQUIRED"); return new NativeHandoffCoordinator(calls,clock,pin,false); }
        private void Origin() { HCheck.Need(calls.Domain == (native ? NativeScope.Domain : FakeDomain), "COORDINATOR_ORIGIN_CHANGED"); }
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
                if (calls.Domain == (native ? NativeScope.Domain : FakeDomain)) { try { calls.AbortPreservingUnknown(); } catch (Exception cleanup) { cleanupErrors.Add(cleanup.GetType().Name + ": " + cleanup.Message); } }
                throw;
            }
            finally { busy = false; }
        }
        internal Dictionary<string, object> Export()
        { return new Dictionary<string, object> { {"complete", complete}, {"failed", failed},
            {"source_domain", native ? NativeScope.Domain : FakeDomain}, {"native_execution", native},
            {"status", complete ? (native ? "OBSERVED_NATIVE_HANDOFF_NOT_P00" : "SIMULATED_NATIVE_AGGREGATE_COMPLETE_NOT_P00") : "HANDOFF_NOT_COMPLETED"},
            {"trace", trace.ToArray()}, {"cleanup_errors", cleanupErrors.ToArray()}, {"claims", HandoffClaims.Closed()} }; }
    }

}
