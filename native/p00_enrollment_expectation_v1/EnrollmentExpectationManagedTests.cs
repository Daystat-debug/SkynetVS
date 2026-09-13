#if P00_ENROLLMENT_MANAGED_TESTS
using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Threading;
using SkynetVS.G1.InstallationBootstrapV1;
using SkynetVS.G1.InstalledRootCandidateV1;
using SkynetVS.G1.LiveRootEpochBridgeV1;
using SkynetVS.G1.ParentChainNativeAdapterV1;
using SkynetVS.G1.P00EpochNativeStoreV1;
using SkynetVS.G1.P00EpochReadLeaseV1;
using SkynetVS.G1.SameHandleV1;

namespace SkynetVS.G1.P00EnrollmentExpectationV1
{
    internal static class EnrollmentExpectationManagedTests
    {
        private static int assertions;
        private static readonly List<string> passed = new List<string>(), failures = new List<string>();
        private static Dictionary<string, object> successExample;
        private static bool librarySeamsAbsent;
        private static void Check(bool ok, string message)
        { assertions++; if (!ok) throw new Exception(message); }
        private static void Throws(Action action)
        { bool refused = false; try { action(); } catch { refused = true; } Check(refused, "EXPECTED_REFUSAL"); }
        private static void Test(string name, Action action)
        {
            try { action(); Check(NtBlock.OutstandingBlocks == 0, "RETAINED_FAKE_STORAGE"); passed.Add(name); }
            catch (Exception e) { failures.Add(name + ":" + e.GetType().Name + ":" + e.Message); }
        }
        private static EnrollmentExpectationSession Session(EnrollmentTestClock clock)
        { return EnrollmentExpectationSession.ForManagedTests(EnrollmentManagedVectors.Seed(), clock); }
        private static Dictionary<string, object> Run(BridgeFixture fixture)
        { var session = Session(new EnrollmentTestClock()); return session.RunManagedBridge(session.PrepareBridge(), fixture); }
        private static void Complete(Dictionary<string, object> result)
        { Check((string)result["result"] == "ENROLLMENT_BOUND_DIAGNOSTIC_COMPLETED_NOT_P00", "BOUND_RESULT"); }
        private static void NoIo(BridgeFixture f) { Check(f.Trace.Count == 0, "IO_BEFORE_BOUNDARY"); }
        private static void Clean(BridgeFixture f) { Check(f.Closed.Count == f.Paths.Count, "KNOWN_HANDLE_CLEANUP"); }
        private static void FalseClaims(Dictionary<string, object> report)
        {
            var claims = (Dictionary<string, object>)report["claims"];
            foreach (var p in claims) Check(p.Value is bool && !(bool)p.Value, "CLAIM:" + p.Key);
        }
        private sealed class PoisonDiagnostic
        { public override string ToString() { throw new Exception("IMPORT_MUST_NOT_INSPECT_DIAGNOSTIC"); } }
        private static Dictionary<string, object> Execute()
        {
            Test("EE001_approved_scope_is_not_runtime_authority", delegate {
                Check(EnrollmentContract.ServiceName == "SkynetVSGuard", "SERVICE");
                Check(EnrollmentContract.RuntimeAccount == "NT SERVICE\\SkynetVSGuard", "ACCOUNT");
                Check(EnrollmentContract.ServiceType == "SERVICE_WIN32_OWN_PROCESS", "TYPE");
                Check(EnrollmentContract.HostRelative == "SkynetVS\\TrustedHost\\releases"
                    && EnrollmentContract.StoreRelative == "SkynetVS-Trust\\LifecycleV1", "LOCATIONS");
                Throws(delegate { EnrollmentNativeBridgeFactory.OpenInstalled(); });
            });
            Test("EE002_independent_vector_pin_required", delegate {
                Throws(delegate { IndependentEnrollmentSeed.ForManagedTests(EnrollmentManagedVectors.Anchor(), new string('1', 64),
                    EnrollmentManagedVectors.Host(), EnrollmentManagedVectors.AnchorObject()); });
            });
            Test("EE003_matching_digest_does_not_make_malformed_anchor_valid", delegate {
                byte[] value = new byte[] { 1, 2, 3 };
                Throws(delegate { IndependentEnrollmentSeed.ForManagedTests(value, Data.Hash(value),
                    EnrollmentManagedVectors.Host(), EnrollmentManagedVectors.AnchorObject()); });
            });
            Test("EE004_independent_object_identities_required", delegate {
                Throws(delegate { IndependentEnrollmentSeed.ForManagedTests(EnrollmentManagedVectors.Anchor(), EnrollmentManagedVectors.AnchorSha256,
                    null, EnrollmentManagedVectors.AnchorObject()); });
            });
            Test("EE005_seed_object_alias_refused", delegate {
                var host = EnrollmentManagedVectors.Host();
                Throws(delegate { IndependentEnrollmentSeed.ForManagedTests(EnrollmentManagedVectors.Anchor(), EnrollmentManagedVectors.AnchorSha256, host, host); });
            });
            Test("EE006_seed_defensive_copy", delegate {
                byte[] vector = EnrollmentManagedVectors.Anchor();
                var seed = IndependentEnrollmentSeed.ForManagedTests(vector, EnrollmentManagedVectors.AnchorSha256,
                    EnrollmentManagedVectors.Host(), EnrollmentManagedVectors.AnchorObject());
                vector[0] = 0;
                Check(seed.CopyForDiagnosticConsumer().Anchor.Digest == EnrollmentManagedVectors.AnchorSha256, "VECTOR_ALIAS");
                FalseClaims(seed.ExportUntrusted());
            });
            Test("EE007_session_requires_origin_and_clock", delegate {
                Throws(delegate { EnrollmentExpectationSession.ForManagedTests(null, new EnrollmentTestClock()); });
                Throws(delegate { EnrollmentExpectationSession.ForManagedTests(EnrollmentManagedVectors.Seed(), null); });
            });
            Test("EE008_initial_negative_clock_refused", delegate {
                Throws(delegate { Session(new EnrollmentTestClock { Now = -1 }); });
            });
            Test("EE009_initial_clock_overflow_refused", delegate {
                Throws(delegate { Session(new EnrollmentTestClock { Now = Int64.MaxValue - 7999 }); });
            });
            Test("EE010_one_ticket_per_original_assessment", delegate {
                var s = Session(new EnrollmentTestClock()); var t = s.PrepareBridge(); var f = new BridgeFixture();
                Throws(delegate { s.PrepareBridge(); }); Throws(delegate { s.RunManagedBridge(t, f); }); NoIo(f);
            });
            Test("EE011_prepare_wrong_thread_no_ticket", delegate {
                var s = Session(new EnrollmentTestClock()); Exception caught = null;
                var worker = new Thread(delegate() { try { s.PrepareBridge(); } catch (Exception e) { caught = e; } });
                worker.Start(); worker.Join(); Check(caught != null, "WRONG_THREAD_PREPARE");
                Throws(delegate { s.PrepareBridge(); });
            });
            Test("EE012_consume_wrong_thread_no_dispatch", delegate {
                var s = Session(new EnrollmentTestClock()); var t = s.PrepareBridge(); var f = new BridgeFixture(); Exception caught = null;
                var worker = new Thread(delegate() { try { s.RunManagedBridge(t, f); } catch (Exception e) { caught = e; } });
                worker.Start(); worker.Join(); Check(caught != null, "WRONG_THREAD_CONSUME"); NoIo(f);
            });
            Test("EE013_ticket_replay_cannot_reopen_roots", delegate {
                var s = Session(new EnrollmentTestClock()); var t = s.PrepareBridge(); var f = new BridgeFixture();
                Complete(s.RunManagedBridge(t, f)); int calls = f.Trace.Count;
                Throws(delegate { s.RunManagedBridge(t, f); }); Check(calls == f.Trace.Count, "REPLAY_DISPATCH");
            });
            Test("EE014_foreign_session_ticket_refused", delegate {
                var a = Session(new EnrollmentTestClock()); var b = Session(new EnrollmentTestClock());
                var t = a.PrepareBridge(); b.PrepareBridge(); var f = new BridgeFixture();
                Throws(delegate { b.RunManagedBridge(t, f); }); NoIo(f);
                Complete(a.RunManagedBridge(t, f));
            });
            Test("EE015_expiry_before_ticket_no_renewal", delegate {
                var c = new EnrollmentTestClock(); var s = Session(c); c.Now = 8000;
                Throws(delegate { s.PrepareBridge(); }); c.Now = 0; Throws(delegate { s.PrepareBridge(); });
            });
            Test("EE016_expiry_between_issue_and_use_no_io", delegate {
                var c = new EnrollmentTestClock(); var s = Session(c); var t = s.PrepareBridge(); c.Now = 8000; var f = new BridgeFixture();
                Throws(delegate { s.RunManagedBridge(t, f); }); NoIo(f);
            });
            Test("EE017_attach_preserves_enrollment_deadline", delegate {
                var c = new EnrollmentTestClock(); var s = Session(c); var t = s.PrepareBridge(); c.Now = 7000;
                var f = new BridgeFixture(); f.Before = delegate(string k, string p) { if (k == "root_open") c.Now = 8000; };
                Throws(delegate { s.RunManagedBridge(t, f); }); Check(f.RootOpens == 1, "DEADLINE_WAS_RESTARTED"); Clean(f);
            });
            Test("EE018_reversed_clock_revokes_ticket", delegate {
                var c = new EnrollmentTestClock { Now = 10 }; var s = Session(c); var t = s.PrepareBridge(); c.Now = 9; var f = new BridgeFixture();
                Throws(delegate { s.RunManagedBridge(t, f); }); NoIo(f);
            });
            Test("EE019_clock_exception_cannot_recover", delegate {
                var c = new EnrollmentTestClock(); var s = Session(c);
                c.OnRead = delegate { throw new Exception("CLOCK_FAULT"); };
                Throws(delegate { s.PrepareBridge(); }); c.OnRead = null; Throws(delegate { s.PrepareBridge(); });
            });
            Test("EE020_reentrant_issue_revokes_outer", delegate {
                var c = new EnrollmentTestClock(); var s = Session(c);
                c.OnRead = delegate { c.OnRead = null; Throws(delegate { s.PrepareBridge(); }); };
                Throws(delegate { s.PrepareBridge(); });
            });
            Test("EE021_revoke_before_issue", delegate {
                var s = Session(new EnrollmentTestClock()); s.Revoke(); Throws(delegate { s.PrepareBridge(); });
            });
            Test("EE022_revoke_after_issue_no_io", delegate {
                var s = Session(new EnrollmentTestClock()); var t = s.PrepareBridge(); s.Revoke(); var f = new BridgeFixture();
                Throws(delegate { s.RunManagedBridge(t, f); }); NoIo(f);
            });
            Test("EE023_revocation_reaches_active_bridge", delegate {
                var s = Session(new EnrollmentTestClock()); var t = s.PrepareBridge(); var f = new BridgeFixture();
                f.Before = delegate(string k, string p) { if (k == "root_open") s.Revoke(); };
                Throws(delegate { s.RunManagedBridge(t, f); }); Check(f.RootOpens == 1, "REVOKE_NOT_PROPAGATED"); Clean(f);
            });
            Test("EE024_post_cleanup_expiry_no_success", delegate {
                var c = new EnrollmentTestClock(); var s = Session(c); var t = s.PrepareBridge(); var f = new BridgeFixture();
                f.Before = delegate(string k, string p) { if (k == "close") c.Now = 8000; };
                Throws(delegate { s.RunManagedBridge(t, f); }); Clean(f);
                Check(f.Closes[f.Closes.Count - 1] == f.GatePath, "CLEANUP_ORDER_CHANGED");
            });
            Test("EE025_new_boundary_to_unchanged_bridge_integration", delegate {
                // Seed is created before the observed fixture exists; it never reads fixture.Expected/Records.
                var s = Session(new EnrollmentTestClock()); var t = s.PrepareBridge(); var f = new BridgeFixture();
                var r = s.RunManagedBridge(t, f); Complete(r); Clean(f); FalseClaims(r);
                Check((long)r["original_start_ms"] == 0 && (long)r["original_deadline_ms"] == 8000, "ORIGINAL_WINDOW");
                var bridge = (Dictionary<string, object>)r["bridge"];
                Check((int)bridge["transferred_roots"] == 2 && (int)bridge["spine_close_successes"] == 9, "LIVE_ROOT_TRANSFER");
                Check(f.Closes.Count == 16 && f.Closes[15] == f.GatePath, "GLOBAL_GATE_LAST");
                successExample = r;
            });
            Test("EE026_observed_anchor_cannot_replace_seed", delegate {
                var f = new BridgeFixture(); f.ChangeRecord(f.AnchorPath, "delivery_review_id", new string('9', 32));
                var r = Run(f); Check((string)r["result"] == "ENROLLMENT_BOUND_BRIDGE_REFUSED", "OBSERVED_ANCHOR_ADOPTED"); Clean(f);
            });
            Test("EE027_observed_release_cannot_replace_seed", delegate {
                var f = new BridgeFixture(); f.Input = new LocationInput(f.Input.ProgramFiles, f.Input.ProgramData,
                    f.Input.Image.Replace(BridgeFixture.Release, new string('9', 32)));
                var r = Run(f); Check((string)r["result"] == "ENROLLMENT_BOUND_BRIDGE_REFUSED" && f.RootOpens == 0, "RELEASE_SELF_ENROLLMENT");
            });
            Test("EE028_observed_identity_cannot_refresh_seed", delegate {
                var f = new BridgeFixture(); f.ChangeFacts = delegate(string p, FileFacts facts) { if (p == f.HostPath) facts.Id[0] ^= 1; };
                var r = Run(f); Check((string)r["result"] == "ENROLLMENT_BOUND_BRIDGE_REFUSED" && f.EpochOpens == 0, "IDENTITY_REFRESH"); Clean(f);
            });
            Test("EE029_fixture_expectation_is_not_consumer_input", delegate {
                var f = new BridgeFixture(); f.Expected = null; Complete(Run(f)); Clean(f);
            });
            Test("EE030_detached_export_is_not_reimportable", delegate {
                var seed = EnrollmentManagedVectors.Seed(); var export = seed.ExportUntrusted();
                ((Dictionary<string, object>)export["anchor_metadata"])["host_release_id"] = new string('9', 32);
                Check(seed.CopyForDiagnosticConsumer().Anchor.Digest == EnrollmentManagedVectors.AnchorSha256, "EXPORT_ALIAS");
                Throws(delegate { EnrollmentNativeBridgeFactory.ImportDiagnostic(export); });
                Throws(delegate { EnrollmentNativeBridgeFactory.ImportDiagnostic(new PoisonDiagnostic()); });
            });
            Test("EE031_native_factories_stay_closed", delegate {
                Throws(delegate { EnrollmentNativeBridgeFactory.OpenInstalled(); });
                Throws(delegate { LiveRootEpochBridge.OpenInstalled(); });
                Throws(delegate { P00ProductionStart.OpenInstalled(); });
                Check(typeof(EnrollmentNativeBridgeFactory).GetMethod("OpenInstalled", BindingFlags.NonPublic | BindingFlags.Static).GetParameters().Length == 0,
                    "CALLER_CONTROLLED_NATIVE_INPUT");
            });
            Test("EE032_forged_ticket_even_same_owner_refused", delegate {
                var s = Session(new EnrollmentTestClock()); s.PrepareBridge(); var forged = new EnrollmentExpectationSession.BridgeTicket(s); var f = new BridgeFixture();
                Throws(delegate { s.RunManagedBridge(forged, f); }); NoIo(f);
            });
            Test("EE033_at_7999_original_window_still_valid", delegate {
                var c = new EnrollmentTestClock(); var s = Session(c); var t = s.PrepareBridge(); c.Now = 7999; var f = new BridgeFixture();
                var r = s.RunManagedBridge(t, f); Complete(r); Check((long)r["original_deadline_ms"] == 8000, "WINDOW_SHIFT"); Clean(f);
            });
            Test("EE034_library_excludes_positive_test_origin_seams", delegate {
                string path = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "P00EnrollmentExpectation.dll");
                Assembly library = Assembly.ReflectionOnlyLoadFrom(path); // Metadata only: no DLL code is executed.
                Check(library.ReflectionOnly, "LIBRARY_MUST_BE_METADATA_ONLY");
                string ns = "SkynetVS.G1.P00EnrollmentExpectationV1.";
                foreach (string n in new string[] { "IndependentEnrollmentSeed", "EnrollmentExpectationSession" }) {
                    Type type = library.GetType(ns + n, true);
                    Check(type.GetMethod("ForManagedTests", BindingFlags.Static | BindingFlags.NonPublic | BindingFlags.Public) == null, "TEST_FACTORY_IN_LIBRARY:" + n);
                    foreach (ConstructorInfo ctor in type.GetConstructors(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic))
                        Check(ctor.IsPrivate, "CONSTRUCTOR_ORIGIN_ESCAPE:" + n);
                }
                Check(library.GetType(ns + "EnrollmentExpectationSession", true).GetMethod("RunManagedBridge", BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public) == null,
                    "TEST_EXECUTOR_IN_LIBRARY");
                Check(library.GetType(ns + "EnrollmentManagedVectors", false) == null && library.GetType(ns + "EnrollmentExpectationManagedTests", false) == null,
                    "TEST_VECTOR_OR_MAIN_IN_LIBRARY");
                librarySeamsAbsent = true;
            });
            Test("EE035_completed_session_export_stays_diagnostic", delegate {
                var s = Session(new EnrollmentTestClock()); Complete(s.RunManagedBridge(s.PrepareBridge(), new BridgeFixture()));
                var r = s.ExportUntrusted(); Check((bool)r["consumed"] && (bool)r["completed"], "SESSION_NOT_TERMINAL"); FalseClaims(r);
                Throws(delegate { EnrollmentNativeBridgeFactory.ImportDiagnostic(r); }); Throws(delegate { s.PrepareBridge(); });
            });
            Test("EE036_no_native_entries_no_live_test_storage", delegate {
                Check(WindowsRootCalls.NewApiEntries == 0 && NativeFileApi.EntryCount == 0 && WindowsNtCalls.EntryCount == 0
                    && WindowsEpochStoreCalls.ReadEntries == 0, "NATIVE_ENTRY");
                Check(NtBlock.OutstandingBlocks == 0, "TEST_STORAGE");
                FalseClaims(new Dictionary<string, object> { { "claims", EnrollmentContract.Claims() } });
            });
            return new Dictionary<string, object> {
                {"kind", "P00_ENROLLMENT_EXPECTATION_MANAGED_TESTS_V1"},
                {"result", failures.Count == 0 ? "PASS_P00_ENROLLMENT_EXPECTATION_MANAGED" : "FAIL_P00_ENROLLMENT_EXPECTATION_MANAGED"},
                {"tests_run", passed.Count + failures.Count}, {"passed", passed}, {"failures", failures}, {"assertions", assertions},
                {"all_io_synthetic", true}, {"old_suites_executed", false}, {"library_test_seams_absent", librarySeamsAbsent},
                {"claims", EnrollmentContract.Claims()}, {"success_example", successExample},
                {"native_api_entries", WindowsRootCalls.NewApiEntries + NativeFileApi.EntryCount + WindowsNtCalls.EntryCount + WindowsEpochStoreCalls.ReadEntries},
                {"outstanding_test_blocks", NtBlock.OutstandingBlocks}
            };
        }
        public static int Main(string[] args)
        {
            if (args.Length != 1 || args[0] != "--managed-enrollment-only") return 2;
            var result = Execute(); byte[] bytes = CanonicalJson.Encode(result);
            var output = Console.OpenStandardOutput(); output.Write(bytes, 0, bytes.Length); output.Flush();
            return failures.Count == 0 ? 0 : 1;
        }
    }
}
#endif
