using System;
using System.Globalization;
using System.Text;

namespace SkynetVS.G1.GateLeaseHandoffV1
{
    // Small fixed ASCII protocol. PID fields are observations, not process authentication by themselves.
    // A future parent must bind them to its HELD process handle returned by CreateProcess.
    internal static class GateHandoffWire
    {
        internal static byte[] Encode(ChildMessage m)
        {
            HCheck.Need(m != null && m.Pin != null && m.Child != null, "WIRE_MESSAGE");
            m.Match(m.Pin, m.Child, m.Step);
            return Encoding.ASCII.GetBytes(String.Join("|", new string[] { "GH1", m.Pin.Run, m.Pin.Nonce,
                m.Pin.Parent.Pid.ToString(CultureInfo.InvariantCulture), m.Pin.Parent.Creation.ToString(CultureInfo.InvariantCulture),
                m.Child.Pid.ToString(CultureInfo.InvariantCulture), m.Child.Creation.ToString(CultureInfo.InvariantCulture),
                m.Sequence.ToString(CultureInfo.InvariantCulture), m.Pin.Gate.FileId, m.Pin.Gate.Volume, m.Pin.Gate.DescriptorHash,
                m.InheritanceCleared ? "1" : "0", m.GateClosed ? "1" : "0", m.Pin.StartedMs.ToString(CultureInfo.InvariantCulture), m.Pin.DeadlineMs.ToString(CultureInfo.InvariantCulture) }) + "\n");
        }
        private static ulong U64(string text)
        {
            ulong result;
            HCheck.Need(text != null && text.Length > 0 && text.Length <= 20
                && UInt64.TryParse(text, NumberStyles.None, CultureInfo.InvariantCulture, out result), "WIRE_UNSIGNED_INTEGER");
            result = UInt64.Parse(text, CultureInfo.InvariantCulture);
            HCheck.Need(result > 0 && text == result.ToString(CultureInfo.InvariantCulture), "WIRE_CANONICAL_INTEGER"); return result;
        }
        internal static ChildMessage Decode(byte[] raw)
        {
            HCheck.Need(raw != null && raw.Length > 0 && raw.Length <= 512 && raw[raw.Length-1] == 10, "WIRE_BOUNDS_OR_LF");
            for (int i = 0; i < raw.Length-1; i++) HCheck.Need(raw[i] >= 33 && raw[i] <= 126, "WIRE_ASCII_ONLY");
            string[] a = Encoding.ASCII.GetString(raw, 0, raw.Length-1).Split('|');
            HCheck.Need(a.Length == 15 && a[0] == "GH1", "WIRE_FIELDS");
            ulong pp = U64(a[3]), cp = U64(a[5]), seq = U64(a[7]);
            HCheck.Need(pp <= UInt32.MaxValue && cp <= UInt32.MaxValue && seq <= 3, "WIRE_INTEGER_BOUNDS");
            HCheck.Need((a[11] == "0" || a[11] == "1") && (a[12] == "0" || a[12] == "1"), "WIRE_BOOLEAN");
            ulong start = a[13] == "0" ? 0ul : U64(a[13]), deadline = U64(a[14]);
            HCheck.Need(start <= (ulong)Int64.MaxValue && deadline <= (ulong)Int64.MaxValue, "WIRE_DEADLINE_BOUNDS");
            var pin = new HandoffPin(a[1], a[2], new ProcessStamp((uint)pp, U64(a[4])), new GateStamp(a[8], a[9], a[10]), (long)start, (long)deadline);
            var result = new ChildMessage(pin, new ProcessStamp((uint)cp, U64(a[6])), (WireStep)seq, (int)seq, a[11] == "1", a[12] == "1");
            result.Match(pin, result.Child, (WireStep)seq); return result;
        }
    }
}
