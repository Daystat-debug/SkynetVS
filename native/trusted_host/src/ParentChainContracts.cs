using System;
using System.Collections.Generic;
using System.Threading;
using SkynetVS.G1.SameHandleV1;

namespace SkynetVS.G1.ParentChainV1
{
    internal static class Limits
    {
        internal const int Directories = 16, FileBytes = 65536, DescriptorBytes = 65536;
        internal const int ChunkBytes = 4096, Operations = 131256;
        internal const string Domain = "SYNTHETIC_PARENT_CHAIN_TEST_ONLY";
        internal static void Need(bool condition, string stage, string message)
        { if (!condition) throw new ObservationFailure(stage, message, null); }
        internal static bool ValidHandle(IntPtr h) { return h.ToInt64() > 0; }
        internal static void Component(string s)
        {
            Need(s != null && s.Length >= 1 && s.Length <= 120, "component", "Component length outside budget");
            Need(s != "." && s != ".." && !s.EndsWith(".", StringComparison.Ordinal)
                && !s.EndsWith(" ", StringComparison.Ordinal), "component", "Ambiguous component");
            foreach (char c in s)
                Need(c >= 32 && c <= 126 && "\\/:\"<>|?*%".IndexOf(c) < 0, "component", "Invalid component character");
            string stem = s.Split('.')[0].ToUpperInvariant();
            Need(stem != "CON" && stem != "PRN" && stem != "AUX" && stem != "NUL"
                && stem != "CONIN$" && stem != "CONOUT$"
                && !(stem.Length == 4 && (stem.StartsWith("COM", StringComparison.Ordinal)
                    || stem.StartsWith("LPT", StringComparison.Ordinal)) && stem[3] >= '1' && stem[3] <= '9'),
                "component", "Device component");
        }
    }

    internal sealed class ScopePin
    {
        private readonly string[] values;
        internal ScopePin(string deployment, string generation, string boot, string inspection, string policy)
        { values = new string[] { deployment, generation, boot, inspection, policy }; }
        internal void Validate()
        {
            foreach (string v in values)
            {
                Limits.Need(v != null && v.Length > 0 && v.Length <= 128, "scope", "Missing or oversized scope pin");
                foreach (char c in v) Limits.Need(c >= 33 && c <= 126, "scope", "Invalid scope pin character");
            }
        }
        internal bool Same(ScopePin other)
        {
            if (other == null) return false;
            for (int i = 0; i < values.Length; i++)
                if (!String.Equals(values[i], other.values[i], StringComparison.Ordinal)) return false;
            return true;
        }
    }

    internal sealed class ChainPlan
    {
        private readonly string[] directories;
        internal readonly string Leaf;
        internal readonly int PrivateRootDepth, MaxBytes;
        internal ChainPlan(string[] dirs, string leaf, int privateRootDepth, int maxBytes)
        { directories = dirs == null ? null : (string[])dirs.Clone(); Leaf = leaf; PrivateRootDepth = privateRootDepth; MaxBytes = maxBytes; }
        internal int DirectoryCount { get { return directories == null ? -1 : directories.Length; } }
        internal string DirectoryAt(int i) { return directories[i]; }
        internal void Validate()
        {
            Limits.Need(directories != null && directories.Length < Limits.Directories, "budget", "Too many directory handles");
            Limits.Need(MaxBytes >= 0 && MaxBytes <= Limits.FileBytes, "budget", "Byte budget outside fixed bound");
            Limits.Need(PrivateRootDepth >= 0 && PrivateRootDepth <= directories.Length, "coverage", "Private root outside covered chain");
            foreach (string s in directories) Limits.Component(s);
            Limits.Component(Leaf);
        }
        internal bool Same(ChainPlan other)
        {
            if (other == null || DirectoryCount != other.DirectoryCount || MaxBytes != other.MaxBytes
                || PrivateRootDepth != other.PrivateRootDepth || !String.Equals(Leaf, other.Leaf, StringComparison.Ordinal)) return false;
            for (int i = 0; i < DirectoryCount; i++)
                if (!String.Equals(directories[i], other.directories[i], StringComparison.Ordinal)) return false;
            return true;
        }
    }

    internal sealed class DeviceFacts
    {
        internal readonly uint Type, Characteristics;
        internal DeviceFacts(uint type, uint characteristics) { Type = type; Characteristics = characteristics; }
        internal void RequireLocalDisk()
        { Limits.Need(Type == 7 && (Characteristics & 0x10u) == 0, "volume_device", "Non-local/unsupported device observation"); }
        internal bool Same(DeviceFacts other)
        { return other != null && Type == other.Type && Characteristics == other.Characteristics; }
        internal Dictionary<string, object> Record()
        { return new Dictionary<string, object> { {"device_type", Type}, {"characteristics", Characteristics} }; }
    }

    // A seam contract, not a proof that an implementation is trustworthy. Open transfers
    // a fresh owned handle on return; an implementation MUST NOT throw after acquiring
    // an unreported handle. No name lookup or new authority occurs in Facts/Security.
    internal interface IChainApi
    {
        string Domain { get; }
        IntPtr OpenRelative(IntPtr parent, string component, bool directory);
        FileFacts Facts(IntPtr h);
        DeviceFacts Device(IntPtr h);
        byte[] Security(IntPtr h);
        byte[] Read(IntPtr h, int count);
        void Rewind(IntPtr h);
        void Close(IntPtr h);
    }
    internal interface IManagedFixtureApi : IChainApi { }
    internal interface IClock { long Milliseconds { get; } }

    internal sealed class ManagedRoot
    {
        internal readonly IManagedFixtureApi Api;
        internal readonly ScopePin Scope;
        internal readonly ChainPlan ApprovedPlan;
        internal readonly ulong Volume;
        internal readonly bool LocalAnchorPrecondition;
        internal readonly long Started, Deadline;
        private readonly byte[] rootId;
        private readonly IntPtr handle;
        private int used;
        internal ManagedRoot(IManagedFixtureApi api, IntPtr ownedHandle, ScopePin scope,
            ChainPlan approved, ulong volume, byte[] id, bool localAnchorPrecondition, long started, long deadline)
        {
            if (api == null) throw new ArgumentNullException("api");
            Api = api; handle = ownedHandle; Scope = scope; ApprovedPlan = approved; Volume = volume;
            rootId = id == null ? null : (byte[])id.Clone(); LocalAnchorPrecondition = localAnchorPrecondition;
            Started = started; Deadline = deadline;
        }
        internal IntPtr Take()
        {
            Limits.Need(Interlocked.CompareExchange(ref used, 1, 0) == 0, "root_lifetime", "Root has already been consumed; no reuse");
            return handle;
        }
        internal bool IdMatches(byte[] actual) { return Binary.Equal(rootId, actual); }
        internal void Validate()
        {
            Limits.Need(Scope != null && ApprovedPlan != null, "root", "Incomplete independent synthetic root pins");
            Scope.Validate(); ApprovedPlan.Validate();
            Limits.Need(rootId != null && rootId.Length == 16 && Volume != 0, "root_pin", "Invalid anchor identity pin");
            Limits.Need(LocalAnchorPrecondition, "root_locality", "Independent local-anchor precondition absent");
            Limits.Need(Started >= 0 && Deadline > Started && Deadline - Started <= 90000,
                "deadline", "Missing or excessive fixed observation window");
            Limits.Need(Api.Domain == Limits.Domain, "source_domain", "Not the managed fixture domain");
        }
    }

    internal static class ProtectedRootAdmission
    {
        internal static object OpenLive(object publicClaim)
        { throw new ObservationFailure("live_root_disabled", "NO_INDEPENDENT_PROTECTED_ROOT_PRODUCER; live root not created", null); }
    }
    internal static class AuthorityJoin
    {
        internal static object OpenLive(object observation)
        { throw new ObservationFailure("authority_disabled", "NO_PROTECTED_G1_G2_PRODUCERS; no receipt or Context", null); }
    }

    internal sealed class FixedBudget
    {
        private readonly IClock clock;
        private readonly long deadline;
        private long previous;
        internal int Operations;
        internal FixedBudget(IClock source, long started, long ends)
        { if (source == null) throw new ArgumentNullException("source"); clock = source; previous = started; deadline = ends; }
        internal void Check()
        {
            long now = clock.Milliseconds;
            Limits.Need(now >= previous && now < deadline, "deadline", "Expired or reversed clock; deadline is never renewed");
            previous = now;
        }
        internal void Enter()
        { Check(); Limits.Need(Operations < Limits.Operations, "operation_budget", "Fixed operation budget exhausted"); Operations++; }
    }
}
