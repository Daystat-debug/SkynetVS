using System;
using System.Collections.Generic;
using System.Globalization;
using System.Threading;

namespace SkynetVS.G1.GateLeaseHandoffV1
{
    internal sealed class HandoffFailure : Exception
    {
        internal readonly string Code;
        internal HandoffFailure(string code) : base(code) { Code = code; }
    }
    internal static class HCheck
    {
        internal static void Need(bool yes, string code) { if (!yes) throw new HandoffFailure(code); }
        internal static bool Handle(IntPtr value) { return value.ToInt64() > 0; }
        internal static void Hex(string text, int length, string code)
        {
            Need(text != null && text.Length == length, code);
            foreach (char c in text) Need((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'), code);
        }
    }
    internal sealed class ProcessStamp
    {
        internal readonly uint Pid;
        internal readonly ulong Creation;
        internal ProcessStamp(uint pid, ulong creation)
        { HCheck.Need(pid != 0 && creation != 0, "PROCESS_IDENTITY_SHAPE"); Pid = pid; Creation = creation; }
        internal bool Same(ProcessStamp other)
        { return other != null && Pid == other.Pid && Creation == other.Creation; }
    }
    internal sealed class GateStamp
    {
        internal readonly string FileId, Volume, DescriptorHash;
        internal GateStamp(string fileId, string volume, string descriptorHash)
        {
            HCheck.Hex(fileId, 32, "FILE_ID"); HCheck.Hex(volume, 16, "VOLUME_ID");
            HCheck.Hex(descriptorHash, 64, "DESCRIPTOR_HASH");
            FileId = fileId; Volume = volume; DescriptorHash = descriptorHash;
        }
        internal bool Same(GateStamp other)
        { return other != null && FileId == other.FileId && Volume == other.Volume && DescriptorHash == other.DescriptorHash; }
    }
    internal sealed class HandoffPin
    {
        internal readonly string Run, Nonce;
        internal readonly ProcessStamp Parent;
        internal readonly GateStamp Gate;
        internal readonly long StartedMs, DeadlineMs;
        internal HandoffPin(string run, string nonce, ProcessStamp parent, GateStamp gate, long startedMs, long deadlineMs)
        {
            HCheck.Hex(run, 32, "RUN_ID"); HCheck.Hex(nonce, 32, "NONCE");
            HCheck.Need(parent != null && gate != null, "HANDOFF_PIN");
            HCheck.Need(startedMs >= 0 && startedMs <= Int64.MaxValue - 8000 && deadlineMs == startedMs + 8000, "FIXED_PARENT_DEADLINE");
            Run = run; Nonce = nonce; Parent = parent; Gate = gate; StartedMs = startedMs; DeadlineMs = deadlineMs;
        }
    }
    internal enum WireStep { Ready = 1, HeldAfterProbe = 2, GateClosed = 3 }
    internal sealed class ChildMessage
    {
        internal readonly HandoffPin Pin;
        internal readonly ProcessStamp Child;
        internal readonly WireStep Step;
        internal readonly int Sequence;
        internal readonly bool InheritanceCleared, GateClosed;
        internal ChildMessage(HandoffPin pin, ProcessStamp child, WireStep step, int sequence, bool cleared, bool closed)
        { Pin = pin; Child = child; Step = step; Sequence = sequence; InheritanceCleared = cleared; GateClosed = closed; }
        internal void Match(HandoffPin expected, ProcessStamp child, WireStep step)
        {
            HCheck.Need(Pin != null && expected != null && Child != null, "MESSAGE_SHAPE");
            HCheck.Need(Pin.Run == expected.Run && Pin.Nonce == expected.Nonce && Pin.Parent.Same(expected.Parent), "MESSAGE_BINDING");
            HCheck.Need(Pin.StartedMs == expected.StartedMs && Pin.DeadlineMs == expected.DeadlineMs, "MESSAGE_DEADLINE_BINDING");
            HCheck.Need(Child.Same(child) && child.Pid != expected.Parent.Pid, "CHILD_IDENTITY");
            HCheck.Need(expected.Gate.Same(Pin.Gate), "CHILD_GATE_IDENTITY");
            HCheck.Need(Enum.IsDefined(typeof(WireStep), step) && Step == step && Sequence == (int)step, "MESSAGE_SEQUENCE");
            HCheck.Need(InheritanceCleared && GateClosed == (step == WireStep.GateClosed), "CHILD_OWNERSHIP_STATE");
        }
    }
    // The sole allowed inheritance plan: one read-only capability plus two IPC endpoints.
    // No caller-provided list, root, service, process, job or writable file capability is accepted.
    internal sealed class RestrictedInheritancePlan
    {
        internal const uint GateAccess = 0x00120081;
        internal const uint Flags = 0x08080004; // NO_WINDOW | EXTENDED_STARTUPINFO_PRESENT | CREATE_SUSPENDED
        internal const ulong HandleListAttribute = 0x00020002;
        internal readonly IntPtr GateCopy, ControlRead, ReportWrite;
        internal RestrictedInheritancePlan(IntPtr gate, IntPtr control, IntPtr report)
        {
            HCheck.Need(HCheck.Handle(gate) && HCheck.Handle(control) && HCheck.Handle(report), "INHERITED_HANDLE_SHAPE");
            HCheck.Need(gate != control && gate != report && control != report, "INHERITED_HANDLE_ALIAS");
            GateCopy = gate; ControlRead = control; ReportWrite = report;
        }
        internal IntPtr[] ExportForNativeCall() { return new IntPtr[] { GateCopy, ControlRead, ReportWrite }; }
        internal const bool InheritHandles = true; // legal ONLY together with this exact HANDLE_LIST
        internal const bool GeneralInheritanceFallback = false;
    }
    internal interface IHandoffClock { long Milliseconds { get; } }
    internal sealed class HandoffWindow
    {
        private readonly IHandoffClock clock;
        private readonly int thread = Thread.CurrentThread.ManagedThreadId;
        private readonly long origin, deadline;
        private long previous;
        private bool reading, revoked;
        internal HandoffWindow(IHandoffClock source, long started, long expires)
        {
            HCheck.Need(source != null && started >= 0 && started <= Int64.MaxValue - 8000 && expires == started + 8000, "CLOCK_REQUIRED");
            clock = source; origin = started; deadline = expires; previous = source.Milliseconds;
            HCheck.Need(previous >= origin && previous < deadline, "CLOCK_OUTSIDE_PARENT_WINDOW");
        }
        internal void Revoke() { revoked = true; }
        internal void Check()
        {
            HCheck.Need(Thread.CurrentThread.ManagedThreadId == thread, "WRONG_THREAD");
            if (reading) { revoked = true; throw new HandoffFailure("CLOCK_REENTRANCY"); }
            HCheck.Need(!revoked, "HANDOFF_REVOKED"); reading = true;
            try
            {
                long now = clock.Milliseconds;
                HCheck.Need(!revoked && now >= previous && now >= origin && now < deadline, "ORIGINAL_DEADLINE_OR_CLOCK");
                previous = now;
            }
            catch { revoked = true; throw; }
            finally { reading = false; }
        }
    }
    internal static class HandoffClaims
    {
        internal static Dictionary<string, object> Closed()
        {
            return new Dictionary<string, object> {
                {"native_handoff_executed", false}, {"native_inheritance_verified", false},
                {"cross_process_gate_retention_verified", false}, {"child_exit_host_verified", false},
                {"production_basis_issued", false}, {"gate_origin_authenticated", false},
                {"epoch_acceptance_authenticated", false}, {"p00_delivery_accepted", false},
                {"p01_producer_implemented", false}, {"authority_admitted", false},
                {"execution_authorized", false}, {"installed_store_opened", false},
                {"registry_written", false}, {"service_installed_or_started", false} };
        }
        internal static object OpenInstalled() { throw new HandoffFailure("ENROLLMENT_AND_NATIVE_SUPERVISION_NOT_IMPLEMENTED"); }
        internal static object ImportDiagnostic(object value) { throw new HandoffFailure("DIAGNOSTIC_IS_NOT_A_LIVE_LEASE"); }
    }
}
