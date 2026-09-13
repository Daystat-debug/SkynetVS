// SOURCE/MANAGED candidate. This does NOT authenticate enrollment or an installed start.
// Positive test-origin factories are absent unless P00_ENROLLMENT_MANAGED_TESTS is defined.
using System;
using System.Collections.Generic;
using System.Threading;
using SkynetVS.G1.InstallationBootstrapV1;
using SkynetVS.G1.InstalledRootCandidateV1;
using SkynetVS.G1.LiveRootEpochBridgeV1;
using SkynetVS.G1.P00EpochNativeStoreV1;
using SkynetVS.G1.P00EpochReadLeaseV1;

namespace SkynetVS.G1.P00EnrollmentExpectationV1
{
    internal sealed class EnrollmentFailure : Exception
    {
        internal EnrollmentFailure(string code) : base(code) { }
    }

    internal static class EnrollmentContract
    {
        internal const string ServiceName = "SkynetVSGuard";
        internal const string RuntimeAccount = "NT SERVICE\\SkynetVSGuard";
        internal const string ServiceType = "SERVICE_WIN32_OWN_PROCESS";
        internal const string HostRelative = "SkynetVS\\TrustedHost\\releases";
        internal const string StoreRelative = "SkynetVS-Trust\\LifecycleV1";
        internal const long AssessmentDuration = 8000;
        internal static void Need(bool ok, string code)
        { if (!ok) throw new EnrollmentFailure(code); }
        internal static Dictionary<string, object> Claims()
        {
            var result = EpochData.Claims();
            result["enrollment_accepted"] = false;
            result["loaded_image_identity_proven"] = false;
            result["native_factory_enabled"] = false;
            return result;
        }
    }

    // Frozen input from a FINITE, independent enrollment source, not from observed roots.
    // There is deliberately NO production issuer. A digest/SID/label is not its provenance.
    internal sealed class IndependentEnrollmentSeed
    {
        private readonly byte[] anchor;
        private readonly EpochIdentity hostRoot, anchorId;
        private readonly string digest;

        private IndependentEnrollmentSeed(byte[] independentVector, string independentDigest,
            EpochIdentity host, EpochIdentity anchorObject)
        {
            EnrollmentContract.Need(Data.NonzeroHex(independentDigest, 64), "ENROLLMENT_PIN_REQUIRED");
            byte[] frozen = Data.Copy(independentVector, EpochCodec.AnchorLimit, "ENROLLMENT_VECTOR_BOUND");
            EnrollmentContract.Need(Data.Hash(frozen) == independentDigest, "ENROLLMENT_VECTOR_PIN_MISMATCH");
            // Reuse the EXACT existing codec and disjoint-object checks; no new wire schema.
            var expected = new DiagnosticEpochExpectation(frozen, host, anchorObject);
            anchor = expected.Anchor.Raw();
            hostRoot = expected.HostRoot;
            anchorId = expected.AnchorId;
            digest = independentDigest;
        }

        internal DiagnosticEpochExpectation CopyForDiagnosticConsumer()
        { return new DiagnosticEpochExpectation((byte[])anchor.Clone(), hostRoot, anchorId); }

        internal Dictionary<string, object> ExportUntrusted()
        {
            return new Dictionary<string, object> {
                {"kind", "UNTRUSTED_ENROLLMENT_SEED_DIAGNOSTIC_V1"},
                {"anchor_bytes", anchor.Length}, {"anchor_sha256", digest},
                {"anchor_metadata", EpochCodec.Anchor(anchor).Metadata()},
                {"claims", EnrollmentContract.Claims()}
            };
        }

#if P00_ENROLLMENT_MANAGED_TESTS
        internal static IndependentEnrollmentSeed ForManagedTests(byte[] independentVector,
            string independentDigest, EpochIdentity host, EpochIdentity anchorObject)
        { return new IndependentEnrollmentSeed(independentVector, independentDigest, host, anchorObject); }
#endif
    }

    // Nonserializable, single-assessment owner. It is not a P00StartSession or a live basis.
    // No hostile-in-process isolation claim: these types share the assembly's TCB.
    internal sealed class EnrollmentExpectationSession
    {
        internal sealed class BridgeTicket
        {
            internal readonly EnrollmentExpectationSession Owner;
            internal BridgeTicket(EnrollmentExpectationSession owner) { Owner = owner; }
        }

        private readonly IndependentEnrollmentSeed seed;
        private readonly IRootClock clock;
        private readonly int ownerThread;
        private readonly long start, deadline;
        private long last;
        private int revoked, issued, consumed, completed, readingClock;
        private BridgeTicket ticket;

        private EnrollmentExpectationSession(IndependentEnrollmentSeed independentSeed, IRootClock source)
        {
            EnrollmentContract.Need(independentSeed != null && source != null, "ENROLLMENT_SESSION_INPUTS");
            seed = independentSeed;
            clock = source;
            ownerThread = Thread.CurrentThread.ManagedThreadId;
            long now = source.Milliseconds;
            EnrollmentContract.Need(now >= 0 && now <= Int64.MaxValue - EnrollmentContract.AssessmentDuration,
                "ENROLLMENT_INITIAL_CLOCK");
            start = now; last = now; deadline = now + EnrollmentContract.AssessmentDuration;
        }

        internal void Revoke() { Interlocked.Exchange(ref revoked, 1); }
        private void OwnerThread()
        {
            if (Thread.CurrentThread.ManagedThreadId != ownerThread) {
                Revoke(); throw new EnrollmentFailure("ENROLLMENT_THREAD_AFFINITY");
            }
        }
        private long Pulse()
        {
            OwnerThread();
            if (Interlocked.Exchange(ref readingClock, 1) != 0) {
                Revoke(); throw new EnrollmentFailure("ENROLLMENT_CLOCK_REENTRANCY");
            }
            try {
                EnrollmentContract.Need(Interlocked.CompareExchange(ref revoked, 0, 0) == 0
                    && Interlocked.CompareExchange(ref completed, 0, 0) == 0, "ENROLLMENT_SESSION_CLOSED");
                long now = clock.Milliseconds;
                EnrollmentContract.Need(Interlocked.CompareExchange(ref revoked, 0, 0) == 0,
                    "ENROLLMENT_REVOKED_DURING_CLOCK");
                EnrollmentContract.Need(now >= last && now < deadline, "ENROLLMENT_ORIGINAL_DEADLINE_OR_CLOCK");
                last = now;
                return now;
            } catch { Revoke(); throw; }
            finally { Interlocked.Exchange(ref readingClock, 0); }
        }
        internal BridgeTicket PrepareBridge()
        {
            OwnerThread();
            if (Interlocked.Exchange(ref issued, 1) != 0) {
                Revoke(); throw new EnrollmentFailure("ENROLLMENT_TICKET_ALREADY_ISSUED");
            }
            Pulse();
            ticket = new BridgeTicket(this);
            Pulse();
            return ticket;
        }
        private DiagnosticEpochExpectation Take(BridgeTicket candidate)
        {
            OwnerThread();
            if (candidate == null || !Object.ReferenceEquals(candidate, ticket)
                || !Object.ReferenceEquals(candidate.Owner, this)) {
                Revoke(); throw new EnrollmentFailure("ENROLLMENT_FOREIGN_OR_FORGED_TICKET");
            }
            if (Interlocked.Exchange(ref consumed, 1) != 0) {
                Revoke(); throw new EnrollmentFailure("ENROLLMENT_TICKET_ALREADY_CONSUMED");
            }
            Pulse();
            return seed.CopyForDiagnosticConsumer();
        }
        internal Dictionary<string, object> ExportUntrusted()
        {
            OwnerThread();
            return new Dictionary<string, object> {
                {"kind", "UNTRUSTED_ENROLLMENT_SESSION_DIAGNOSTIC_V1"},
                {"original_start_ms", start}, {"original_deadline_ms", deadline},
                {"issued", Interlocked.CompareExchange(ref issued, 0, 0) != 0},
                {"consumed", Interlocked.CompareExchange(ref consumed, 0, 0) != 0},
                {"completed", Interlocked.CompareExchange(ref completed, 0, 0) != 0},
                {"revoked", Interlocked.CompareExchange(ref revoked, 0, 0) != 0},
                {"seed", seed.ExportUntrusted()}, {"claims", EnrollmentContract.Claims()}
            };
        }

        private sealed class OriginalAssessmentClock : IRootClock
        {
            private readonly EnrollmentExpectationSession owner;
            internal OriginalAssessmentClock(EnrollmentExpectationSession session) { owner = session; }
            public long Milliseconds { get { return owner.Pulse(); } }
        }

#if P00_ENROLLMENT_MANAGED_TESTS
        internal static EnrollmentExpectationSession ForManagedTests(IndependentEnrollmentSeed seed, IRootClock clock)
        { return new EnrollmentExpectationSession(seed, clock); }

        internal Dictionary<string, object> RunManagedBridge(BridgeTicket candidate, IManagedBridgeCalls source)
        {
            OwnerThread();
            LiveRootEpochBridge bridge = null;
            bool runStarted = false;
            try {
                DiagnosticEpochExpectation expectation = Take(candidate);
                // No expectation/path/release argument from the downstream diagnostic caller.
                // The original session clock wraps both the bridge window and its epoch transport window.
                bridge = LiveRootEpochBridge.ForManagedTests(source, expectation, new OriginalAssessmentClock(this));
                Pulse();
                runStarted = true;
                Dictionary<string, object> result = bridge.RunDiagnostic();
                Pulse();
                return new Dictionary<string, object> {
                    {"kind", "P00_ENROLLMENT_BOUND_BRIDGE_MANAGED_V1"},
                    {"result", (string)result["result"] == "LIVE_ROOT_EPOCH_DIAGNOSTIC_COMPLETED_NOT_P00"
                        ? "ENROLLMENT_BOUND_DIAGNOSTIC_COMPLETED_NOT_P00" : "ENROLLMENT_BOUND_BRIDGE_REFUSED"},
                    {"original_start_ms", start}, {"original_deadline_ms", deadline},
                    {"bridge", result}, {"all_io_synthetic", true},
                    {"claims", EnrollmentContract.Claims()},
                    {"P00", "NOT_ACCEPTED"}, {"P01", "NOT_IMPLEMENTED"}, {"acquisition", "BLOCKED"}
                };
            } finally {
                // Only an explicit managed helper may free fake quarantined HGlobal test storage.
                // It does not retry unknown closes, re-enable the owner, or release a native handle.
                try { if (bridge != null && runStarted) bridge.ReleaseCompletedFakeStorageForTests(); }
                finally { Interlocked.Exchange(ref completed, 1); }
            }
        }
#endif
    }

    internal static class EnrollmentNativeBridgeFactory
    {
        // Parameterless by design. No caller vector, path, SID, bool approval, JSON or callback can mint an origin.
        internal static object OpenInstalled()
        { throw new EnrollmentFailure("NATIVE_ENROLLMENT_AND_PREENTRY_TRUSTED_START_NOT_DELIVERED"); }
        internal static object ImportDiagnostic(object ignored)
        { throw new EnrollmentFailure("DETACHED_DATA_CANNOT_ISSUE_ENROLLMENT_EXPECTATION"); }
    }
}
