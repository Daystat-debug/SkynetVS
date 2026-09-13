using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
using SkynetVS.G1.InstalledRootCandidateV1;
using SkynetVS.G1.InstallationBootstrapV1;
using SkynetVS.G1.ParentChainV1;
using SkynetVS.G1.ParentChainNativeAdapterV1;
using SkynetVS.G1.P00EpochNativeStoreV1;
using SkynetVS.G1.P00EpochReadLeaseV1;
using SkynetVS.G1.SameHandleV1;

namespace SkynetVS.G1.LiveRootEpochBridgeV1
{
    internal sealed class BridgeTestClock : IRootClock
    {
        internal long Now=0;
        internal Action OnRead=null;
        public long Milliseconds { get { if(OnRead!=null)OnRead(); return Now; } }
    }
    internal sealed class BridgeFixture : IManagedBridgeCalls
    {
        internal const string Release="0123456789abcdef0123456789abcdef";
        internal const string AcceptanceId="11111111111111111111111111111111";
        internal string RootDomain=Rules.FakeDomain, EpochDomain=StoreContract.FakeDomain;
        internal LocationInput Input;
        internal readonly string HostPath, StorePath, AnchorPath, GatePath, StatePath, AcceptancePath;
        internal DiagnosticEpochExpectation Expected;
        internal readonly Dictionary<string,byte[]> Records=new Dictionary<string,byte[]>(StringComparer.OrdinalIgnoreCase);
        internal readonly Dictionary<long,string> Paths=new Dictionary<long,string>();
        internal readonly Dictionary<long,bool> Directories=new Dictionary<long,bool>();
        internal readonly HashSet<long> Closed=new HashSet<long>();
        internal readonly List<string> Closes=new List<string>(), Trace=new List<string>();
        internal readonly Dictionary<string,long> EpochParents=new Dictionary<string,long>();
        internal Action<string,string> Before=null;
        internal Action<string,FileFacts> ChangeFacts=null;
        internal Func<string,byte[]> ChangeSecurity=null;
        internal Func<string,OpenOutcome> RootOpenOverride=null;
        internal string FailClose=null, MissingEpoch=null, PendingRead=null, AliasEpochPath=null;
        internal long AliasEpochHandle=0;
        internal bool PendingEpochOpen=false;
        internal int RootOpens=0, EpochOpens=0, LocationsCount=0, ReadCalls=0;
        private long next=100;
        string IRootCalls.Domain { get { return RootDomain; } }
        string INtCalls.Domain { get { return EpochDomain; } }
        internal BridgeFixture() : this(false) { }
        internal BridgeFixture(bool twoVolumes)
        {
            string pd=twoVolumes?"D:\\Data":"C:\\ProgramData";
            HostPath="C:\\Program Files\\SkynetVS\\TrustedHost\\releases\\"+Release;
            StorePath=pd+"\\SkynetVS-Trust\\LifecycleV1";
            Input=new LocationInput("C:\\Program Files",pd,HostPath+"\\Guard.exe");
            AnchorPath=HostPath+"\\InstallAnchor.bin"; GatePath=StorePath+"\\Lifecycle.gate";
            StatePath=StorePath+"\\Lifecycle.state"; AcceptancePath=StorePath+"\\Acceptances\\"+AcceptanceId+".bin";
            BuildVectors();
        }
        internal static byte[] Id(string path)
        {
            byte[] h=System.Security.Cryptography.SHA256.Create().ComputeHash(Encoding.ASCII.GetBytes(path.ToUpperInvariant()));
            byte[] id=new byte[16]; Buffer.BlockCopy(h,0,id,0,16); return id;
        }
        internal static EpochIdentity Identity(string path)
        { return new EpochIdentity((path[0]=='D'?2ul:1ul).ToString("x16"),Binary.Hex(Id(path))); }
        private static string Dig(char c) { return new string(c,64); }
        private void BuildVectors()
        {
            // Fixed synthetic vectors exist BEFORE root acquisition; they are not reconstructed from reader output.
            var anchor=new Dictionary<string,object> {
                {"kind","P00_INSTALL_ANCHOR_V1"},{"format_version",1L},{"installation_namespace_id",Release},{"host_release_id",Release},
                {"host_manifest_digest",Dig('1')},{"observer_closure_digest",Dig('2')},{"initial_policy_set_digest",Dig('3')},
                {"threat_model_digest",Dig('4')},{"os_boundary_digest",Dig('5')},{"lifecycle_protocol_id",EpochData.Protocol},
                {"delivery_review_id",Release},{"state_store_slot",EpochData.StoreSlot},
                {"store_root_identity",Identity(StorePath).Export()},{"gate_identity",Identity(GatePath).Export()},
                {"reader_sid","S-1-5-80-1-2-3-4-5"},{"writer_sids",new List<object>{"S-1-5-18","S-1-5-32-544"}}
            };
            var acceptance=new Dictionary<string,object> {
                {"kind","P00_EPOCH_ACCEPTANCE_V1"},{"format_version",1L},{"acceptance_id",AcceptanceId},{"operation_id",Release},
                {"installation_namespace_id",Release},{"deployment_id",Release},{"provisioning_epoch",Release},{"publication_revision",1L},
                {"registration_id",Release},{"record_bytes",1L},{"record_sha256",Dig('6')},{"selector_bytes",1L},{"selector_sha256",Dig('7')},
                {"host_release_id",Release},{"observer_closure_digest",Dig('2')},{"initial_policy_set_digest",Dig('3')},
                {"threat_model_digest",Dig('4')},{"os_boundary_digest",Dig('5')},{"lifecycle_protocol_id",EpochData.Protocol},
                {"birth_evidence_digest",Dig('8')},{"predecessor_acceptance_digest",null},{"administrative_review_id",Release}
            };
            byte[] a=CanonicalJson.Encode(anchor), b=CanonicalJson.Encode(acceptance);
            var state=new Dictionary<string,object> {
                {"kind","P00_LIFECYCLE_STATE_V1"},{"format_version",1L},{"installation_namespace_id",Release},{"state","ACTIVE"},
                {"publication_revision",1L},{"acceptance_id",AcceptanceId},{"acceptance_bytes",(long)b.Length},
                {"acceptance_sha256",Binary.Hash(b)},{"host_release_id",Release},{"operation_id",Release}
            };
            Records[AnchorPath]=a; Records[StatePath]=CanonicalJson.Encode(state); Records[AcceptancePath]=b;
            Records[GatePath]=new byte[0];
            Expected=new DiagnosticEpochExpectation((byte[])a.Clone(),Identity(HostPath),Identity(AnchorPath));
        }
        internal void ChangeRecord(string path,string key,object value)
        { var d=(Dictionary<string,object>)CanonicalJson.Parse(Records[path],65536); d[key]=value; Records[path]=CanonicalJson.Encode(d); }
        private void Hit(string kind,string path)
        { Trace.Add(kind+":"+path); if(Before!=null)Before(kind,path); }
        public LocationInput Locations() { Hit("locations",""); LocationsCount++; return Input; }
        private OpenOutcome Create(string path,bool directory)
        { long h=next++; Paths.Add(h,path); Directories.Add(h,directory); return new OpenOutcome(new IntPtr(h),false); }
        private string Live(IntPtr h)
        { if(Closed.Contains(h.ToInt64()))throw new Exception("FAKE_USE_AFTER_CLOSE"); return Paths[h.ToInt64()]; }
        public OpenOutcome OpenVolume(string drive)
        { Hit("root_open",drive); RootOpens++; return RootOpenOverride==null?Create(drive,true):RootOpenOverride(drive)??Create(drive,true); }
        public OpenOutcome OpenRelative(IntPtr parent,string component,bool directory)
        {
            string path=Live(parent).TrimEnd('\\')+"\\"+component; Hit("root_open",path); RootOpens++;
            return RootOpenOverride==null?Create(path,directory):RootOpenOverride(path)??Create(path,directory);
        }
        public FileFacts Facts(IntPtr h)
        {
            string path=Live(h); Hit("facts",path); bool dir=Directories[h.ToInt64()]; byte[] raw;
            var f=new FileFacts { FileType=1, Id=Id(path), Volume=path[0]=='D'?2ul:1ul,
                Directory=dir, Attributes=dir?16u:32u, Links=1,
                Size=dir?4096:Records.TryGetValue(path,out raw)?raw.Length:2048, Allocation=4096,
                Creation=1, Access=2, Write=3, Change=4 };
            if(ChangeFacts!=null)ChangeFacts(path,f); return f;
        }
        public DeviceFacts Device(IntPtr h) { string p=Live(h); Hit("root_device",p); return new DeviceFacts(7,0); }
        internal static byte[] DescriptorBytes() { byte[] b=new byte[20]; b[0]=1; b[3]=128; return b; }
        public byte[] Security(IntPtr h)
        { string p=Live(h); Hit("security",p); return ChangeSecurity==null?DescriptorBytes():ChangeSecurity(p); }
        public void Close(IntPtr h)
        {
            string path=Live(h); Hit("close",path);
            if(path==FailClose)throw new Exception("SIMULATED_CLOSE_FAILURE");
            if(!Closed.Add(h.ToInt64()))throw new Exception("DOUBLE_CLOSE"); Closes.Add(path);
        }
        public int Open(NtOpenFrame frame)
        {
            IntPtr parent=Marshal.ReadIntPtr(frame.Attributes.Pointer,8);
            string name=Encoding.Unicode.GetString(frame.Name.Read()).TrimEnd('\0');
            string path=Live(parent).TrimEnd('\\')+"\\"+name; Hit("epoch_open",path); EpochOpens++;
            EpochParents[path]=parent.ToInt64();
            if(PendingEpochOpen)return 0x103;
            if(path==MissingEpoch)return unchecked((int)0xc0000034);
            IntPtr handle=path==AliasEpochPath?new IntPtr(AliasEpochHandle):Create(path,frame.Directory).Handle;
            Marshal.WriteIntPtr(frame.Handle.Pointer,handle); Marshal.WriteInt32(frame.Io.Pointer,0);
            Marshal.WriteInt64(frame.Io.Pointer,8,1); return 0;
        }
        public int Device(IntPtr h,NtDeviceFrame frame)
        {
            string path=Live(h); Hit("epoch_device",path);
            Marshal.WriteInt32(frame.Output.Pointer,7); Marshal.WriteInt32(frame.Output.Pointer,4,0);
            Marshal.WriteInt32(frame.Io.Pointer,0); Marshal.WriteInt64(frame.Io.Pointer,8,8); return 0;
        }
        public int Read(IntPtr h,EpochReadFrame frame)
        {
            string path=Live(h); Hit("read",path); ReadCalls++;
            if(path==PendingRead)return 0x103;
            byte[] raw=Records[path]; int count=Math.Min(frame.Count,raw.Length-(int)frame.Position);
            byte[] output=new byte[frame.Count]; Buffer.BlockCopy(raw,(int)frame.Position,output,0,count);
            frame.Output.Put(output); Marshal.WriteInt32(frame.Io.Pointer,0); Marshal.WriteInt64(frame.Io.Pointer,8,count); return 0;
        }
    }
}
