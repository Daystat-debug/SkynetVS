using System;
using System.Collections.Generic;
using System.Threading;
using SkynetVS.G1.ParentChainV1;
using SkynetVS.G1.SameHandleV1;
using SkynetVS.G1.ParentChainNativeAdapterV1;
using SkynetVS.G1.InstallationBootstrapV1;
namespace SkynetVS.G1.InstalledRootCandidateV1
{
    internal sealed class TestClock : IRootClock
    {
        internal long Now;
        internal Action Callback;
        public long Milliseconds { get { if(Callback!=null)Callback();return Now; } }
    }
    internal sealed class FakeRoots : IRootCalls
    {
        internal const string Id="0123456789abcdef0123456789abcdef";
        internal string MutableDomain=Rules.FakeDomain;
        internal LocationInput Input=new LocationInput("C:\\Program Files","C:\\ProgramData","C:\\Program Files\\SkynetVS\\TrustedHost\\releases\\"+Id+"\\Guard.exe");
        internal Action<string> Before;
        internal Func<string,OpenOutcome> OverrideOpen;
        internal Action<string,FileFacts> ChangeFacts;
        internal Func<string,byte[]> ChangeSecurity;
        internal string FailClose;
        internal int Opens,Locs;
        internal bool Remote;
        internal readonly Dictionary<long,string> Paths=new Dictionary<long,string>();
        internal readonly Dictionary<long,bool> Dirs=new Dictionary<long,bool>();
        internal readonly Dictionary<string,byte[]> Ids=new Dictionary<string,byte[]>(StringComparer.OrdinalIgnoreCase);
        internal readonly List<string> Closed=new List<string>();
        private long next=100;
        public string Domain { get {return MutableDomain;} }
        private void Hit(string op){if(Before!=null)Before(op);}
        public LocationInput Locations(){Hit("locations");Locs++;return Input;}
        private OpenOutcome Open(string p,bool d)
        {
            Hit("open:"+p);Opens++;
            if(OverrideOpen!=null){OpenOutcome x=OverrideOpen(p);if(x!=null)return x;}
            long h=next++;Paths.Add(h,p);Dirs.Add(h,d);
            if(!Ids.ContainsKey(p)){byte[] id=new byte[16];id[0]=(byte)(Ids.Count+1);Ids.Add(p,id);}
            return new OpenOutcome(new IntPtr(h),false);
        }
        public OpenOutcome OpenVolume(string drive){return Open(drive,true);}
        public OpenOutcome OpenRelative(IntPtr p,string c,bool d){return Open(Paths[p.ToInt64()].TrimEnd('\\')+"\\"+c,d);}
        public FileFacts Facts(IntPtr h)
        {
            string p=Paths[h.ToInt64()];Hit("facts:"+p);bool d=Dirs[h.ToInt64()];
            var f=new FileFacts{FileType=1,Id=(byte[])Ids[p].Clone(),Volume=(ulong)(p[0]=='D'?2:1),Directory=d,Attributes=d?16u:32u,
                Links=1,Size=d?4096:2048,Allocation=4096,Creation=1,Access=2,Write=3,Change=4};
            if(ChangeFacts!=null)ChangeFacts(p,f);return f;
        }
        public DeviceFacts Device(IntPtr h){Hit("device");return new DeviceFacts(7,Remote?16u:0u);}
        internal static byte[] MinimalDescriptor()
        {byte[] b=new byte[20];b[0]=1;b[3]=128;return b;} // Structural, not policy-approved.
        public byte[] Security(IntPtr h){string p=Paths[h.ToInt64()];Hit("security:"+p);return ChangeSecurity==null?MinimalDescriptor():ChangeSecurity(p);}
        public void Close(IntPtr h){string p=Paths[h.ToInt64()];Hit("close:"+p);if(p==FailClose)throw new Exception("CLOSE_FAILED");Closed.Add(p);}
    }
    internal static class InstalledRootManagedTests
    {
        private static int assertions;
        private static readonly List<string> passed=new List<string>(),failures=new List<string>();
        private static void Check(bool x,string msg){assertions++;if(!x)throw new Exception(msg);}
        private static void Throws(Action a){bool threw=false;try{a();}catch{threw=true;}Check(threw,"Expected refusal");}
        private static void Test(string id,Action a){try{a();passed.Add(id);}catch(Exception e){failures.Add(id+":"+e.Message);}}
        private static Dictionary<string,object> Run(FakeRoots f){return new InstalledRootReadOnly(f,new TestClock()).Run();}
        private static void Result(Dictionary<string,object> r,string expected){Check((string)r["result"]==expected,"result "+r["result"]+" error "+r["error"]);}
        private static void AllFalse(Dictionary<string,object> r){foreach(var p in (Dictionary<string,object>)r["claims"])Check(p.Value is bool&&!(bool)p.Value,"claim");}
        internal static Dictionary<string,object> Execute()
        {
            Test("IR001_exact_layout",delegate{LayoutPlan p=LayoutPlan.FromObservedLocations(new FakeRoots().Input);Check(p!=null&&p.ReleaseId==FakeRoots.Id,"exact plan");Check(p.Store.Text=="C:\\ProgramData\\SkynetVS-Trust\\LifecycleV1","fixed store");});
            Test("IR002_no_current_image_release_no_scan",delegate{var f=new FakeRoots();f.Input=new LocationInput("C:\\Program Files","C:\\ProgramData","C:\\Downloads\\Reader.exe");var r=Run(f);Result(r,"CURRENT_IMAGE_OUTSIDE_INSTALLED_LAYOUT");Check(f.Opens==0,"no directory scan");});
            Test("IR003_prefix_boundary",delegate{var i=new FakeRoots().Input;Check(LayoutPlan.FromObservedLocations(new LocationInput(i.ProgramFiles,i.ProgramData,i.Image.Replace("releases\\","releases-evil\\")))==null,"prefix");});
            Test("IR004_release_ids",delegate{var i=new FakeRoots().Input;foreach(string id in new[]{new string('0',32),new string('A',32),"123"})Check(LayoutPlan.FromObservedLocations(new LocationInput(i.ProgramFiles,i.ProgramData,i.Image.Replace(FakeRoots.Id,id)))==null,"id");});
            Test("IR005_no_paths_from_cli",delegate{Check(InstalledRootEntryPoint.AcceptArguments(new[]{"--observe-current-layout"}),"mode");foreach(string[] args in new[]{new string[0],new[]{"--observe-current-layout","C:\\Other"},new[]{"--install"}})Check(!InstalledRootEntryPoint.AcceptArguments(args),"args refused");});
            Test("IR006_ambiguous_paths_refused",delegate{foreach(string path in new[]{"C:\\PROGRA~1","C:relative","\\\\host\\share","\\\\?\\C:\\x","c:\\x","C:\\x\\","C:\\x\\..","C:\\x:y","C:\\%windir%","C:\\NUL","C:\\x.","C:\\x ","C:\\a\\\\b","C:/x","C:\\a"+(char)0+"b","C:\\"+(char)233}){string one=path;Throws(delegate{LocalPath.Parse(one);});}});
            Test("IR007_path_and_depth_bounds",delegate{Throws(delegate{LocalPath.Parse("C:\\"+new string('x',121));});Throws(delegate{LocalPath.Parse("C:\\"+String.Join("\\",new string[17]));});Throws(delegate{LocalPath.Parse(null);});});
            Test("IR008_plan_defensive_copy",delegate{var p=LocalPath.Parse("C:\\Program Files");var a=p.Parts();a[0]="Other";Check(p.Parts()[0]=="Program Files","copy");});
            Test("IR009_complete_owner_and_reverse_cleanup",delegate{var f=new FakeRoots();var r=Run(f);Result(r,"ROOT_CANDIDATES_OBSERVED_NOT_ENROLLED");Check((int)r["owned_handles"]==11&&(int)r["closed_handles"]==11,"11 retained nodes");Check(f.Closed[0].EndsWith("Guard.exe")&&f.Closed[f.Closed.Count-1]=="C:\\","reverse");AllFalse(r);});
            Test("IR010_two_local_volumes",delegate{var f=new FakeRoots();f.Input=new LocationInput(f.Input.ProgramFiles,"D:\\Data",f.Input.Image);Result(Run(f),"ROOT_CANDIDATES_OBSERVED_NOT_ENROLLED");});
            Test("IR011_known_folder_root_forbidden",delegate{Throws(delegate{LayoutPlan.FromObservedLocations(new LocationInput("C:\\","C:\\ProgramData","C:\\x"));});});
            Test("IR012_missing_child_distinct_from_access_denied",delegate{var f=new FakeRoots();f.OverrideOpen=delegate(string p){return p.EndsWith("SkynetVS")?new OpenOutcome(IntPtr.Zero,true):null;};var r=Run(f);Result(r,"INSTALLED_PATH_NOT_OBSERVED");Check(f.Closed.Count==2,"ancestors closed");});
            Test("IR013_access_denied_is_error",delegate{var f=new FakeRoots();f.Before=delegate(string s){if(s.StartsWith("open:")&&s.EndsWith("SkynetVS"))throw new RootFailure("ACCESS_DENIED",false);};Result(Run(f),"ROOT_READ_ERROR");Check(f.Closed.Count==2,"cleanup");});
            Test("IR014_missing_volume_is_error",delegate{var f=new FakeRoots();f.OverrideOpen=delegate(string p){return new OpenOutcome(IntPtr.Zero,true);};Result(Run(f),"ROOT_READ_ERROR");});
            Test("IR015_reparse_refused",delegate{var f=new FakeRoots();f.ChangeFacts=delegate(string p,FileFacts x){x.Attributes|=0x400;};Result(Run(f),"ROOT_READ_ERROR");Check(f.Closed.Count==1,"owned bad root closed");});
            Test("IR016_directory_and_image_kind",delegate{var f=new FakeRoots();f.ChangeFacts=delegate(string p,FileFacts x){if(p.EndsWith("Guard.exe"))x.Directory=true;};Result(Run(f),"ROOT_READ_ERROR");Check(f.Closed.Count==11,"image owned");});
            Test("IR017_image_single_link",delegate{var f=new FakeRoots();f.ChangeFacts=delegate(string p,FileFacts x){if(!x.Directory)x.Links=2;};Result(Run(f),"ROOT_READ_ERROR");});
            Test("IR018_local_device_required",delegate{var f=new FakeRoots();f.Remote=true;Result(Run(f),"ROOT_READ_ERROR");});
            Test("IR019_volume_cannot_change_in_chain",delegate{var f=new FakeRoots();f.ChangeFacts=delegate(string p,FileFacts x){if(p.EndsWith("SkynetVS"))x.Volume=22;};Result(Run(f),"ROOT_READ_ERROR");});
            Test("IR020_timestamp_drift",delegate{var f=new FakeRoots();int count=0;f.ChangeFacts=delegate(string p,FileFacts x){x.Write=++count;};Result(Run(f),"ROOT_READ_ERROR");});
            Test("IR021_last_access_not_stability_gate",delegate{var f=new FakeRoots();int count=0;f.ChangeFacts=delegate(string p,FileFacts x){x.Access=++count;};Result(Run(f),"ROOT_CANDIDATES_OBSERVED_NOT_ENROLLED");});
            Test("IR022_descriptor_drift",delegate{var f=new FakeRoots();int n=0;f.ChangeSecurity=delegate(string p){var b=FakeRoots.MinimalDescriptor();if(++n>11)b[3]=144;return b;};Result(Run(f),"ROOT_READ_ERROR");});
            Test("IR023_malformed_descriptor",delegate{var f=new FakeRoots();f.ChangeSecurity=delegate(string p){return new byte[21];};Result(Run(f),"ROOT_READ_ERROR");});
            Test("IR024_source_location_change",delegate{var f=new FakeRoots();f.Before=delegate(string p){if(p=="locations"&&f.Locs==1)f.Input=new LocationInput(f.Input.ProgramFiles,"D:\\Data",f.Input.Image);};Result(Run(f),"ROOT_READ_ERROR");});
            Test("IR025_live_handle_alias_terminal",delegate{var f=new FakeRoots();f.OverrideOpen=delegate(string p){return f.Opens>1?new OpenOutcome(new IntPtr(100),false):null;};var r=Run(f);Result(r,"ROOT_READ_ERROR");Check((bool)r["process_exit_required"]&&f.Closed.Count==0,"terminal alias");});
            Test("IR026_pending_or_unknown_terminal",delegate{var f=new FakeRoots();f.Before=delegate(string p){if(p.StartsWith("open:")&&f.Opens>0)throw new RootFailure("SIMULATED_PENDING",true);};var r=Run(f);Result(r,"ROOT_READ_ERROR");Check((bool)r["process_exit_required"]&&f.Closed.Count==0,"no dispatch after pending");});
            Test("IR027_close_error_no_success_or_retry",delegate{var f=new FakeRoots();f.FailClose=f.Input.Image;var r=Run(f);Result(r,"ROOT_READ_ERROR");Check((bool)r["process_exit_required"]&&f.Closed.Count==0,"close terminal");});
            Test("IR028_deadline_after_open_still_owned",delegate{var f=new FakeRoots();var clock=new TestClock();f.Before=delegate(string op){if(op.StartsWith("open:"))clock.Now=8000;};var r=new InstalledRootReadOnly(f,clock).Run();Result(r,"ROOT_READ_ERROR");Check(f.Closed.Count==1,"open registered before deadline");});
            Test("IR029_deadline_during_cleanup",delegate{var f=new FakeRoots();var clock=new TestClock();f.Before=delegate(string op){if(op.StartsWith("close:"))clock.Now=8000;};Result(new InstalledRootReadOnly(f,clock).Run(),"ROOT_READ_ERROR");Check(f.Closed.Count==11,"all known cleanup");});
            Test("IR030_revoke_and_single_use",delegate{var f=new FakeRoots();var reader=new InstalledRootReadOnly(f,new TestClock());reader.Revoke();Result(reader.Run(),"ROOT_READ_ERROR");Throws(delegate{reader.Run();});Check(f.Opens==0,"no IO after revoke");});
            Test("IR031_domain_change_stops_dispatch",delegate{var f=new FakeRoots();f.Before=delegate(string op){if(op.StartsWith("facts:"))f.MutableDomain="OTHER";};var r=Run(f);Result(r,"ROOT_READ_ERROR");Check((bool)r["process_exit_required"]&&f.Closed.Count==0,"origin unknown");});
            Test("IR032_wrong_thread_and_factories",delegate{var f=new FakeRoots();var reader=new InstalledRootReadOnly(f,new TestClock());bool refused=false;var t=new Thread(delegate(){try{reader.Run();}catch{refused=true;}});t.Start();t.Join();Check(refused&&f.Opens==0,"thread");Throws(delegate{ProductionRootAdmission.OpenInstalled();});Throws(delegate{ProductionRootAdmission.ImportObservation(new object());});});
            Test("IR033_clock_fault_cannot_recover",delegate{var f=new FakeRoots();var clock=new TestClock();int n=0;clock.Callback=delegate(){n++;clock.Now=n==4?-1:0;};var reader=new InstalledRootReadOnly(f,clock);Result(reader.Run(),"ROOT_READ_ERROR");Throws(delegate{reader.Run();});});
            Test("IR034_no_native_calls",delegate{Check(WindowsRootCalls.NewApiEntries==0&&NativeFileApi.EntryCount==0&&WindowsNtCalls.EntryCount==0,"no Windows API calls");Check(NtBlock.OutstandingBlocks==0,"no NT frames allocated");});
            return new Dictionary<string,object>{{"kind","INSTALLED_ROOT_MANAGED_TESTS_V1"},{"result",failures.Count==0?"PASS_INSTALLED_ROOT_MANAGED":"FAIL_INSTALLED_ROOT_MANAGED"},
                {"tests_run",passed.Count+failures.Count},{"passed",passed},{"failures",failures},{"assertions",assertions},
                {"all_io_synthetic",true},{"native_api_entries",WindowsRootCalls.NewApiEntries+NativeFileApi.EntryCount+WindowsNtCalls.EntryCount},
                {"claims",Rules.Claims()},{"old_suites_executed",false}};
        }
        public static int Main(string[] args)
        {
            if(args.Length!=1||args[0]!="--managed-only")return 2;
            var result=Execute();byte[] bytes=CanonicalJson.Encode(result);var output=Console.OpenStandardOutput();output.Write(bytes,0,bytes.Length);output.Flush();
            return failures.Count==0?0:1;
        }
    }
}
