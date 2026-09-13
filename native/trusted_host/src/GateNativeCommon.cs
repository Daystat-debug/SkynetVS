using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;
using SkynetVS.G1.GateLeaseHandoffV1;

namespace SkynetVS.G1.GateLeaseHandoffNativeV1
{
    internal static class NativeScope
    {
        internal const string Mode = "DISPOSABLE_CROSS_PROCESS_GATE_ONLY_V1";
        internal const string Domain = "WINDOWS_GATE_HANDOFF_DIAGNOSTIC_NOT_P00";
        internal const string TestDomain = "SYNTHETIC_NATIVE_AGGREGATE_TEST_ONLY";
        internal const int SharingViolation = unchecked((int)0xc0000043);
        internal const uint ReadGate = 0x00120081;
        internal const uint ExclusiveGate = 0x00120083;
        internal static ulong Number(string text, ulong maximum)
        {
            ulong value;
            HCheck.Need(text != null && text.Length > 0 && text.Length <= 20 &&
                UInt64.TryParse(text, NumberStyles.None, CultureInfo.InvariantCulture, out value), "BAD_UNSIGNED_ARGUMENT");
            value = UInt64.Parse(text, CultureInfo.InvariantCulture);
            HCheck.Need(value > 0 && value <= maximum && text == value.ToString(CultureInfo.InvariantCulture), "NONCANONICAL_ARGUMENT");
            return value;
        }
        internal static byte[] AsciiLine(string line)
        {
            HCheck.Need(line != null && line.Length > 1 && line.Length <= 512 && line[line.Length-1] == '\n', "FRAME_LENGTH");
            for (int i=0;i<line.Length-1;i++) HCheck.Need(line[i] >= 33 && line[i] <= 126, "FRAME_ASCII");
            return Encoding.ASCII.GetBytes(line);
        }
        internal static Dictionary<string, object> Claims() { return HandoffClaims.Closed(); }
        internal static object OpenInstalled() { throw new HandoffFailure("ENROLLMENT_AND_TRUSTED_START_NOT_IMPLEMENTED"); }
        internal static object ImportDiagnostic(object value) { throw new HandoffFailure("DIAGNOSTIC_NOT_PRODUCTION_BASIS"); }
    }

    // Commands bind both held process identities and the original parent deadline.
    internal static class GateCommandWire
    {
        internal static byte[] Encode(HandoffPin p, ProcessStamp child, int step)
        {
            HCheck.Need(p != null && child != null && (step == 2 || step == 3), "COMMAND_INPUT");
            return NativeScope.AsciiLine(String.Join("|", new string[] { "GHC1", p.Run, p.Nonce,
                p.Parent.Pid.ToString(CultureInfo.InvariantCulture), p.Parent.Creation.ToString(CultureInfo.InvariantCulture),
                child.Pid.ToString(CultureInfo.InvariantCulture), child.Creation.ToString(CultureInfo.InvariantCulture),
                step.ToString(CultureInfo.InvariantCulture), p.StartedMs.ToString(CultureInfo.InvariantCulture),
                p.DeadlineMs.ToString(CultureInfo.InvariantCulture) }) + "\n");
        }
        internal static void Require(byte[] raw, HandoffPin p, ProcessStamp child, int step)
        {
            HCheck.Need(raw != null && raw.Length <= 512, "COMMAND_BOUNDS");
            byte[] expected = Encode(p, child, step);
            HCheck.Need(raw.Length == expected.Length, "COMMAND_BINDING_LENGTH");
            for (int i=0;i<raw.Length;i++) HCheck.Need(raw[i] == expected[i], "COMMAND_BINDING_OR_SEQUENCE");
        }
    }

    internal static class ReceiverFailureWire
    {
        private static string Prefix(HandoffPin p,ProcessStamp child)
        {return "GHERR1|"+p.Run+"|"+p.Nonce+"|"+p.Parent.Pid.ToString(CultureInfo.InvariantCulture)+"|"+
            p.Parent.Creation.ToString(CultureInfo.InvariantCulture)+"|"+child.Pid.ToString(CultureInfo.InvariantCulture)+"|"+
            child.Creation.ToString(CultureInfo.InvariantCulture)+"|"+p.StartedMs.ToString(CultureInfo.InvariantCulture)+"|"+
            p.DeadlineMs.ToString(CultureInfo.InvariantCulture)+"|";}
        internal static byte[] Encode(HandoffPin p,ProcessStamp child,Exception error)
        {
            string detail=error.GetType().Name+":"+error.Message;StringBuilder safe=new StringBuilder();
            foreach(char c in detail){if(safe.Length==160)break;safe.Append(c>=32&&c<=126?c:'?');}
            return NativeScope.AsciiLine(Prefix(p,child)+Convert.ToBase64String(Encoding.ASCII.GetBytes(safe.ToString()))+"\n");
        }
        internal static void RejectIfFailure(byte[] raw,HandoffPin p,ProcessStamp child)
        {
            HCheck.Need(raw!=null&&raw.Length<=512,"FAILURE_FRAME_BOUNDS");string text=Encoding.ASCII.GetString(raw);
            if(!text.StartsWith("GHERR1|",StringComparison.Ordinal))return;
            string prefix=Prefix(p,child);HCheck.Need(text.StartsWith(prefix,StringComparison.Ordinal)&&text.EndsWith("\n",StringComparison.Ordinal),"FAILURE_FRAME_BINDING");
            string b64=text.Substring(prefix.Length,text.Length-prefix.Length-1);byte[] decoded=Convert.FromBase64String(b64);
            HCheck.Need(decoded.Length>0&&decoded.Length<=160&&Convert.ToBase64String(decoded)==b64,"FAILURE_FRAME_DETAIL");
            foreach(byte b in decoded)HCheck.Need(b>=32&&b<=126,"FAILURE_FRAME_ASCII");
            throw new HandoffFailure("RECEIVER_REPORTED_FAILURE:"+Encoding.ASCII.GetString(decoded));
        }
    }

    internal enum OwnedState { Owned, Closed, CloseUnknown }
    internal sealed class OwnedHandle
    {
        internal readonly string Role;
        internal readonly IntPtr Value;
        internal OwnedState State;
        internal OwnedHandle(string role, IntPtr value) { Role=role; Value=value; State=OwnedState.Owned; }
        internal IntPtr Use() { HCheck.Need(State == OwnedState.Owned, "HANDLE_NOT_OWNED_"+Role); return Value; }
    }
    internal sealed class HandleLedger
    {
        private readonly List<OwnedHandle> handles = new List<OwnedHandle>();
        private readonly Func<IntPtr, bool> close;
        internal readonly List<string> Closed = new List<string>();
        internal readonly List<string> Errors = new List<string>();
        internal bool Poisoned { get; private set; }
        internal HandleLedger(Func<IntPtr, bool> closer) { HCheck.Need(closer != null, "CLOSER_REQUIRED"); close=closer; }
        internal OwnedHandle Add(string role, IntPtr h)
        {
            HCheck.Need(!Poisoned && HCheck.Handle(h), "ACQUIRED_HANDLE_INVALID");
            foreach (OwnedHandle old in handles)
                if (old.State != OwnedState.Closed && old.Value == h) { Poisoned=true; throw new HandoffFailure("LIVE_HANDLE_ALIAS"); }
            OwnedHandle entry=new OwnedHandle(role,h); handles.Add(entry); return entry;
        }
        internal void CloseOnce(OwnedHandle entry)
        {
            HCheck.Need(entry != null && handles.Contains(entry) && !Poisoned && entry.State == OwnedState.Owned, "CLOSE_NOT_OWNED_OR_POISONED");
            // Mark BEFORE entering the API; no retry even if the call throws.
            entry.State=OwnedState.CloseUnknown;
            bool ok=false;
            try { ok=close(entry.Value); }
            catch { Poisoned=true; Errors.Add("CLOSE_EXCEPTION:"+entry.Role); throw; }
            if (!ok) { Poisoned=true; Errors.Add("CLOSE_FAILED:"+entry.Role); throw new HandoffFailure("CLOSE_FAILED_"+entry.Role); }
            entry.State=OwnedState.Closed; Closed.Add(entry.Role);
        }
        internal void CloseKnownReverse()
        {
            if (Poisoned) return;
            for (int i=handles.Count-1;i>=0;i--)
                if (handles[i].State==OwnedState.Owned) { try { CloseOnce(handles[i]); } catch { break; } }
        }
        internal bool Empty { get { foreach(OwnedHandle h in handles) if(h.State!=OwnedState.Closed)return false; return !Poisoned; } }
    }

    internal interface IPipeCalls
    {
        // -1 means all peer write endpoints closed. Zero means no bytes yet.
        int Available(IntPtr h);
        byte[] Read(IntPtr h, int count);
        int Write(IntPtr h, byte[] bytes, int offset, int count);
        void Pause();
    }
    // One reader and one writer per endpoint. Fixed frames; no growing buffer or unbounded retry.
    // Windows implementation is synchronous. Its independent process watchdog handles a stuck call.
    internal sealed class BoundedPipe
    {
        private readonly IPipeCalls calls;
        private readonly Action check;
        private int totalRead, totalWritten;
        internal BoundedPipe(IPipeCalls io, Action checkWindow)
        { HCheck.Need(io!=null && checkWindow!=null,"PIPE_CONTRACT"); calls=io; check=checkWindow; }
        internal byte[] Receive(IntPtr pipe)
        {
            List<byte> data=new List<byte>();
            while(true)
            {
                check(); int available=calls.Available(pipe); check();
                HCheck.Need(available>=0,"PIPE_EOF_BEFORE_FRAME");
                HCheck.Need(available<=2048,"PIPE_QUEUED_OUTPUT_LIMIT");
                if(available==0){calls.Pause();continue;}
                // Byte-at-a-time, at most 512 per frame; never consumes a second frame.
                byte[] part=calls.Read(pipe,1); check();
                HCheck.Need(part!=null && part.Length==1,"PIPE_READ_COUNT");
                totalRead++; HCheck.Need(totalRead<=1536,"PIPE_TOTAL_READ_LIMIT");
                data.Add(part[0]); HCheck.Need(data.Count<=512,"PIPE_FRAME_OVERFLOW");
                if(part[0]==10) { HCheck.Need(data.Count>1,"EMPTY_FRAME"); return data.ToArray(); }
                HCheck.Need(part[0]>=33 && part[0]<=126,"PIPE_INVALID_BYTE");
            }
        }
        internal void Send(IntPtr pipe, byte[] frame)
        {
            HCheck.Need(frame!=null,"NULL_FRAME"); NativeScope.AsciiLine(Encoding.ASCII.GetString(frame));
            foreach(byte b in frame)HCheck.Need(b==10 || (b>=33 && b<=126),"PIPE_INVALID_OUTPUT_BYTE");
            HCheck.Need(totalWritten<=1536-frame.Length,"PIPE_TOTAL_WRITE_LIMIT");
            int at=0;
            while(at<frame.Length)
            {
                check(); int n=calls.Write(pipe,frame,at,frame.Length-at); check();
                HCheck.Need(n>0 && n<=frame.Length-at,"PIPE_WRITE_COUNT"); at+=n;
            }
            totalWritten+=frame.Length;
        }
        internal void RequirePeerEof(IntPtr pipe)
        {
            check(); int n=calls.Available(pipe); check();
            HCheck.Need(n==-1,"TRAILING_OUTPUT_OR_UNCLOSED_PEER_ENDPOINT");
        }
    }
}
