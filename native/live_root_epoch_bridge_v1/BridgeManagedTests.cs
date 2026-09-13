using System;
using System.Collections.Generic;
using System.Threading;
using SkynetVS.G1.InstalledRootCandidateV1;
using SkynetVS.G1.InstallationBootstrapV1;
using SkynetVS.G1.ParentChainNativeAdapterV1;
using SkynetVS.G1.P00EpochNativeStoreV1;
using SkynetVS.G1.P00EpochReadLeaseV1;
using SkynetVS.G1.SameHandleV1;

namespace SkynetVS.G1.LiveRootEpochBridgeV1
{
    internal static class BridgeManagedTests
    {
        private static int assertions;
        private static readonly List<string> passed=new List<string>(), failures=new List<string>();
        private static Dictionary<string,object> successExample;
        private static void Check(bool value,string message)
        { assertions++; if(!value)throw new Exception(message); }
        private static void Throws(Action action)
        { bool yes=false; try { action(); } catch { yes=true; } Check(yes,"EXPECTED_REFUSAL"); }
        private static void Test(string id,Action action)
        {
            try { action(); Check(NtBlock.OutstandingBlocks==0,"LEAKED_TEST_FRAME"); passed.Add(id); }
            catch(Exception e) { failures.Add(id+":"+e.GetType().Name+":"+e.Message); }
        }
        private static Dictionary<string,object> Run(BridgeFixture f,BridgeTestClock clock)
        {
            LiveRootEpochBridge bridge=LiveRootEpochBridge.ForManagedTests(f,f.Expected,clock);
            try { return bridge.RunDiagnostic(); }
            finally { bridge.ReleaseCompletedFakeStorageForTests(); }
        }
        private static Dictionary<string,object> Run(BridgeFixture f) { return Run(f,new BridgeTestClock()); }
        private static void Result(Dictionary<string,object> r,string value)
        { Check((string)r["result"]==value,"RESULT="+r["result"]+" ERROR="+r["error"]); }
        private static void Error(Dictionary<string,object> r) { Result(r,"LIVE_ROOT_EPOCH_BRIDGE_ERROR"); }
        private static void Clean(BridgeFixture f,Dictionary<string,object> r)
        { Check(!(bool)r["process_exit_required"] && f.Closed.Count==f.Paths.Count,"KNOWN_HANDLES_NOT_CLOSED"); }
        private static void GateLast(BridgeFixture f)
        { Check(f.Closes.Count>0 && f.Closes[f.Closes.Count-1]==f.GatePath,"GATE_NOT_GLOBALLY_LAST"); }
        private static void Claims(Dictionary<string,object> r)
        { foreach(var p in (Dictionary<string,object>)r["claims"])Check(p.Value is bool && !(bool)p.Value,"POSITIVE_CLAIM:"+p.Key); }
        internal static Dictionary<string,object> Execute()
        {
            Test("BR001_live_transfer_same_handles_global_gate_last",delegate {
                var f=new BridgeFixture(); var r=Run(f); Result(r,"LIVE_ROOT_EPOCH_DIAGNOSTIC_COMPLETED_NOT_P00"); Clean(f,r); GateLast(f);
                Check((int)r["root_nodes"]==11 && (int)r["transferred_roots"]==2 && (int)r["spine_close_successes"]==9,"OWNERSHIP_COUNTS");
                Check(f.Paths.Count==16 && f.RootOpens==11 && f.EpochOpens==5,"NO_ROOT_REOPEN");
                Check(f.Paths[f.EpochParents[f.AnchorPath]]==f.HostPath && f.Paths[f.EpochParents[f.GatePath]]==f.StorePath,"EXACT_PARENT_HANDLES");
                Claims(r); Claims((Dictionary<string,object>)r["epoch_transport"]); successExample=r;
            });
            Test("BR002_spine_retained_through_all_epoch_reads",delegate {
                var f=new BridgeFixture(); int reads=0;
                f.Before=delegate(string k,string p) { if(k=="read") { reads++; Check(f.Closed.Count==0,"SPINE_CLOSED_DURING_READ"); } };
                var r=Run(f); Result(r,"LIVE_ROOT_EPOCH_DIAGNOSTIC_COMPLETED_NOT_P00"); Check(reads>=6,"FULL_AND_REPEAT_READS");
            });
            Test("BR003_outside_layout_no_epoch_or_root_opens",delegate {
                var f=new BridgeFixture(); f.Input=new LocationInput(f.Input.ProgramFiles,f.Input.ProgramData,"C:\\Downloads\\Reader.exe");
                var r=Run(f); Result(r,"CURRENT_IMAGE_OUTSIDE_INSTALLED_LAYOUT"); Check(f.RootOpens==0 && f.EpochOpens==0,"NO_SCAN"); Clean(f,r);
            });
            Test("BR004_independent_release_expectation_required",delegate {
                var f=new BridgeFixture(); f.Input=new LocationInput(f.Input.ProgramFiles,f.Input.ProgramData,f.Input.Image.Replace(BridgeFixture.Release,new string('2',32)));
                var r=Run(f); Error(r); Check(f.RootOpens==0 && !(bool)r["transfer_completed"],"NO_SELF_ENROLLMENT"); Clean(f,r);
            });
            Test("BR005_independent_root_identity_required",delegate {
                var f=new BridgeFixture(); f.Expected=new DiagnosticEpochExpectation(f.Expected.Anchor.Raw(),BridgeFixture.Identity("C:\\Other"),BridgeFixture.Identity(f.AnchorPath));
                var r=Run(f); Error(r); Check(!(bool)r["transfer_completed"] && f.EpochOpens==0,"NO_ROOT_EXPECTATION_FROM_OBSERVATION"); Clean(f,r);
            });
            Test("BR006_missing_component_cleans_owned_prefix",delegate {
                var f=new BridgeFixture(); f.RootOpenOverride=delegate(string p) { return p.EndsWith("SkynetVS")?new OpenOutcome(IntPtr.Zero,true):null; };
                var r=Run(f); Error(r); Check(f.Closed.Count==2,"PREFIX_CLEANUP"); Clean(f,r);
            });
            Test("BR007_expiry_after_open_registers_before_check",delegate {
                var f=new BridgeFixture(); var c=new BridgeTestClock(); f.Before=delegate(string k,string p) { if(k=="root_open")c.Now=8000; };
                var r=Run(f,c); Error(r); Check(f.Closed.Count==1,"POST_OPEN_OWNERSHIP"); Clean(f,r);
            });
            Test("BR008_attach_does_not_restart_original_deadline",delegate {
                var f=new BridgeFixture(); var c=new BridgeTestClock();
                f.Before=delegate(string k,string p) { if(k=="locations" && f.LocationsCount==1)c.Now=7900; if(k=="epoch_open")c.Now=8000; };
                var r=Run(f,c); Error(r); Check((bool)r["transfer_completed"] && f.EpochOpens==1 && f.ReadCalls==0,"ORIGINAL_DEADLINE"); Clean(f,r);
            });
            Test("BR009_attach_constructor_failure_keeps_root_owner",delegate {
                var f=new BridgeFixture(); var c=new BridgeTestClock(); int postLocation=0;
                c.OnRead=delegate { if(f.LocationsCount==2 && ++postLocation==2)throw new Exception("ATTACH_CLOCK_FAILURE"); };
                var r=Run(f,c); Error(r); Check(!(bool)r["transfer_completed"] && f.Closed.Count==11,"ATTACH_FAILURE_ROOTS_NOT_TRANSFERRED"); Clean(f,r);
            });
            Test("BR010_deadline_during_cleanup_no_false_success",delegate {
                var f=new BridgeFixture(); var c=new BridgeTestClock(); f.Before=delegate(string k,string p) { if(k=="close")c.Now=8000; };
                var r=Run(f,c); Error(r); Clean(f,r); GateLast(f);
            });
            Test("BR011_revoke_before_run_no_dispatch",delegate {
                var f=new BridgeFixture(); var b=LiveRootEpochBridge.ForManagedTests(f,f.Expected,new BridgeTestClock()); b.Revoke();
                var r=b.RunDiagnostic(); Error(r); Check(f.RootOpens==0 && f.LocationsCount==0,"REVOKE_DISPATCH"); Throws(delegate { b.RunDiagnostic(); });
            });
            Test("BR012_reentrancy_revokes_outer_run",delegate {
                var f=new BridgeFixture(); var b=LiveRootEpochBridge.ForManagedTests(f,f.Expected,new BridgeTestClock()); bool attempted=false;
                f.Before=delegate(string k,string p) { if(!attempted && k=="root_open") { attempted=true; Throws(delegate { b.RunDiagnostic(); }); } };
                var r=b.RunDiagnostic(); Error(r); Check(attempted,"REENTRANCY_ATTEMPTED"); Clean(f,r);
            });
            Test("BR013_wrong_thread_no_dispatch",delegate {
                var f=new BridgeFixture(); var b=LiveRootEpochBridge.ForManagedTests(f,f.Expected,new BridgeTestClock()); bool refused=false;
                var t=new Thread(delegate() { try { b.RunDiagnostic(); } catch { refused=true; } }); t.Start(); t.Join();
                Check(refused && f.RootOpens==0 && f.LocationsCount==0,"THREAD_AFFINITY");
            });
            Test("BR014_epoch_domain_flip_stops_both_cleanup_groups",delegate {
                var f=new BridgeFixture(); f.Before=delegate(string k,string p) { if(k=="epoch_open")f.EpochDomain="OTHER"; };
                var r=Run(f); Error(r); Check((bool)r["process_exit_required"] && f.Closed.Count==0,"DOMAIN_TERMINAL");
            });
            Test("BR015_root_domain_flip_during_epoch_stops_dispatch",delegate {
                var f=new BridgeFixture(); f.Before=delegate(string k,string p) { if(k=="read")f.RootDomain="OTHER"; };
                var r=Run(f); Error(r); Check((bool)r["process_exit_required"] && f.Closed.Count==0 && f.ReadCalls==1,"CROSS_VIEW_DOMAIN");
            });
            Test("BR016_unknown_root_completion_no_cleanup",delegate {
                var f=new BridgeFixture(); f.Before=delegate(string k,string p) { if(k=="root_open" && f.RootOpens==1)throw new Exception("UNKNOWN_ROOT_OPEN"); };
                var r=Run(f); Error(r); Check((bool)r["process_exit_required"] && f.Closed.Count==0,"UNKNOWN_ROOT_TERMINAL");
            });
            Test("BR017_pending_epoch_open_quarantines_no_cleanup",delegate {
                var f=new BridgeFixture(); f.PendingEpochOpen=true; var r=Run(f); Error(r);
                Check((bool)r["process_exit_required"] && f.Closed.Count==0,"PENDING_EPOCH_TERMINAL");
                Check((bool)((Dictionary<string,object>)r["epoch_transport"])["retained_frame"],"FRAME_QUARANTINE");
            });
            Test("BR018_pending_epoch_read_quarantines_no_cleanup",delegate {
                var f=new BridgeFixture(); f.PendingRead=f.AnchorPath; var r=Run(f); Error(r);
                Check((bool)r["process_exit_required"] && f.Closed.Count==0 && f.ReadCalls==1,"PENDING_READ_TERMINAL");
            });
            Test("BR019_epoch_handle_aliases_retained_spine_terminal",delegate {
                var f=new BridgeFixture(); f.AliasEpochPath=f.AnchorPath; f.AliasEpochHandle=100;
                var r=Run(f); Error(r); Check((bool)r["process_exit_required"] && f.ReadCalls==0 && f.Closed.Count==0,"GLOBAL_HANDLE_ALIAS");
            });
            Test("BR020_epoch_object_aliases_image_before_record_read",delegate {
                var f=new BridgeFixture(); f.ChangeFacts=delegate(string p,FileFacts x) { if(p==f.StatePath)x.Id=BridgeFixture.Id(f.Input.Image); };
                var r=Run(f); Error(r); Check(f.ReadCalls==1,"STATE_ALIAS_NOT_READ"); Clean(f,r); GateLast(f);
            });
            Test("BR021_root_snapshots_bound_across_attach",delegate {
                var f=new BridgeFixture(); int hostFacts=0;
                f.ChangeFacts=delegate(string p,FileFacts x) { if(p==f.HostPath && ++hostFacts>=5)x.Write=9; };
                var r=Run(f); Error(r); Check((bool)r["transfer_completed"] && f.EpochOpens==0,"SNAPSHOT_CONTINUITY"); Clean(f,r);
            });
            Test("BR022_ancestor_drift_while_gate_held_refused",delegate {
                var f=new BridgeFixture(); f.ChangeFacts=delegate(string p,FileFacts x) { if(p=="C:\\Program Files" && f.EpochOpens==5)x.Write=9; };
                var r=Run(f); Error(r); Check(f.EpochOpens==5,"REACHED_FINAL_SPINE_RECHECK"); Clean(f,r); GateLast(f);
            });
            Test("BR023_guard_descriptor_drift_after_epoch_refused",delegate {
                var f=new BridgeFixture(); f.ChangeSecurity=delegate(string p) { var b=BridgeFixture.DescriptorBytes(); if(p==f.Input.Image && f.EpochOpens==5)b[3]=144; return b; };
                var r=Run(f); Error(r); Clean(f,r); GateLast(f);
            });
            Test("BR024_missing_anchor_known_failure_no_fallback",delegate {
                var f=new BridgeFixture(); f.MissingEpoch=f.AnchorPath; var r=Run(f); Error(r);
                Check(f.EpochOpens==1 && f.ReadCalls==0,"NO_SEARCH_OR_FALLBACK"); Clean(f,r);
            });
            Test("BR025_nonactive_state_no_acceptance_open",delegate {
                var f=new BridgeFixture(); f.ChangeRecord(f.StatePath,"state","SUSPENDED"); f.ChangeRecord(f.StatePath,"acceptance_id",null);
                f.ChangeRecord(f.StatePath,"acceptance_bytes",0L); f.ChangeRecord(f.StatePath,"acceptance_sha256",null);
                var r=Run(f); Error(r); Check(f.EpochOpens==3,"NO_ACCEPTANCE_SELECTION"); Clean(f,r); GateLast(f);
            });
            Test("BR026_actual_anchor_does_not_replace_independent_vector",delegate {
                var f=new BridgeFixture(); f.ChangeRecord(f.AnchorPath,"host_manifest_digest",new string('9',64));
                var r=Run(f); Error(r); Check(f.EpochOpens==1,"MISMATCH_BEFORE_GATE"); Clean(f,r);
            });
            Test("BR027_acceptance_digest_mismatch_refused",delegate {
                var f=new BridgeFixture(); f.ChangeRecord(f.StatePath,"acceptance_sha256",new string('9',64));
                var r=Run(f); Error(r); Check(f.EpochOpens==5,"SELECTION_CHECKED"); Clean(f,r); GateLast(f);
            });
            Test("BR028_root_handle_alias_no_duplicate_close",delegate {
                var f=new BridgeFixture(); f.RootOpenOverride=delegate(string p) { return f.RootOpens>1?new OpenOutcome(new IntPtr(100),false):null; };
                var r=Run(f); Error(r); Check((bool)r["process_exit_required"] && f.Closed.Count==0,"ROOT_ALIAS_TERMINAL");
            });
            Test("BR029_spine_close_failure_does_not_close_transport",delegate {
                var f=new BridgeFixture(); f.FailClose=f.Input.Image; var r=Run(f); Error(r);
                Check((bool)r["process_exit_required"] && f.Closes.Count==0,"NO_TRANSPORT_CLEANUP_AFTER_SPINE_CLOSE_ERROR");
            });
            Test("BR030_transport_close_failure_stops_no_retry",delegate {
                var f=new BridgeFixture(); f.FailClose=f.AcceptancePath; var r=Run(f); Error(r);
                Check((bool)r["process_exit_required"] && f.Closes.Count==9 && !f.Closes.Contains(f.GatePath),"STOP_WITH_GATE_RETAINED");
            });
            Test("BR031_origin_flip_during_cleanup_stops_next_group",delegate {
                var f=new BridgeFixture(); f.Before=delegate(string k,string p) { if(k=="close")f.EpochDomain="OTHER"; };
                var r=Run(f); Error(r); Check((bool)r["process_exit_required"] && f.Closes.Count==1,"ONE_COMPLETED_CLOSE_THEN_STOP");
            });
            Test("BR032_two_volumes_same_owner_cleanup",delegate {
                var f=new BridgeFixture(true); var r=Run(f); Result(r,"LIVE_ROOT_EPOCH_DIAGNOSTIC_COMPLETED_NOT_P00"); Clean(f,r); GateLast(f);
            });
            Test("BR033_single_use_never_reopens_after_completion",delegate {
                var f=new BridgeFixture(); var b=LiveRootEpochBridge.ForManagedTests(f,f.Expected,new BridgeTestClock());
                var r=b.RunDiagnostic(); Result(r,"LIVE_ROOT_EPOCH_DIAGNOSTIC_COMPLETED_NOT_P00"); int count=f.Trace.Count;
                Throws(delegate { b.RunDiagnostic(); }); Check(f.Trace.Count==count,"NO_SECOND_DISPATCH");
            });
            Test("BR034_native_and_detached_factories_closed",delegate {
                Throws(delegate { LiveRootEpochBridge.OpenInstalled(); }); Throws(delegate { LiveRootEpochBridge.ImportObservation(successExample); });
                Throws(delegate { ProductionRootAdmission.OpenInstalled(); }); Throws(delegate { InstalledEpochNativeAdmission.OpenInstalled(); });
                foreach(var method in typeof(LiveRootEpochBridge).GetMethods(System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.Public))
                    Check(method.ReturnType!=typeof(P00EpochNativeReadTransport) && method.ReturnType!=typeof(OwnedDiagnosticRootPair) && method.ReturnType!=typeof(IntPtr),"RAW_OWNER_ESCAPE");
            });
            Test("BR035_zero_native_entries_and_no_retained_test_storage",delegate {
                Check(WindowsRootCalls.NewApiEntries==0 && NativeFileApi.EntryCount==0 && WindowsNtCalls.EntryCount==0 && WindowsEpochStoreCalls.ReadEntries==0,"NATIVE_ENTRY");
                Check(NtBlock.OutstandingBlocks==0,"TEST_STORAGE");
            });
            return new Dictionary<string,object> {
                {"kind","LIVE_ROOT_EPOCH_BRIDGE_MANAGED_TESTS_V1"},
                {"result",failures.Count==0?"PASS_LIVE_ROOT_EPOCH_BRIDGE_MANAGED":"FAIL_LIVE_ROOT_EPOCH_BRIDGE_MANAGED"},
                {"tests_run",passed.Count+failures.Count},{"passed",passed},{"failures",failures},{"assertions",assertions},
                {"claims",Rules.Claims()},{"success_example",successExample},{"all_io_synthetic",true},
                {"native_api_entries",WindowsRootCalls.NewApiEntries+NativeFileApi.EntryCount+WindowsNtCalls.EntryCount+WindowsEpochStoreCalls.ReadEntries},
                {"outstanding_test_blocks",NtBlock.OutstandingBlocks},{"old_suites_executed",false}
            };
        }
        public static int Main(string[] args)
        {
            if(args.Length!=1 || args[0]!="--managed-bridge-only")return 2;
            var r=Execute(); byte[] b=CanonicalJson.Encode(r); var stdout=Console.OpenStandardOutput(); stdout.Write(b,0,b.Length); stdout.Flush();
            return failures.Count==0?0:1;
        }
    }
}
