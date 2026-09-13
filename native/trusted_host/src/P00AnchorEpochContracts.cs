// New SOURCE/MANAGED candidate only. Parsed records and simulated origins never authenticate P00.
using System;
using System.Collections.Generic;
using System.Threading;
using SkynetVS.G1.InstallationBootstrapV1;

namespace SkynetVS.G1.P00EpochReadLeaseV1
{
    internal sealed class EpochFailure : Exception
    {
        internal readonly string Code;
        internal readonly int? TransportCode;
        internal EpochFailure(string code) : base(code) { Code = code; }
        internal EpochFailure(string code, int transportCode) : base(code) { Code=code; TransportCode=transportCode; }
    }
    internal static class EpochData
    {
        internal const string Domain="SIMULATED_P00_EPOCH_READ_LEASE_ONLY";
        internal const string Protocol="P00_LIFECYCLE_FROZEN_V1";
        internal const string StoreSlot="P00_LIFECYCLE_V1_ENROLLED_SLOT";
        internal static void Need(bool ok,string code) { if(!ok) throw new EpochFailure(code); }
        internal static Dictionary<string,object> Claims()
        {
            Dictionary<string,object> d=Trust.ClosedClaims();
            foreach(string s in new[]{"p00_delivery_accepted","p01_producer_implemented","trusted_start_implemented",
                "epoch_acceptance_authenticated","gate_origin_verified","native_store_read","child_gate_handoff_implemented",
                "production_basis_issued","lifecycle_history_proven","native_registry_policy_observed",
                "effective_access_calculated","platform_acl_host_verified","platform_policy_implemented"}) d[s]=false;
            return d;
        }
        internal static object Copy(object value)
        {
            byte[] b=value as byte[];if(b!=null)return b.Clone();
            IDictionary<string,object>d=value as IDictionary<string,object>;
            if(d!=null){var r=new Dictionary<string,object>(StringComparer.Ordinal);foreach(var p in d)r.Add(p.Key,Copy(p.Value));return r;}
            if(value is string||value==null||value is bool||value is int||value is long)return value;
            System.Collections.IEnumerable a=value as System.Collections.IEnumerable;
            Need(a!=null,"UNSUPPORTED_DIAGNOSTIC_TYPE");var l=new List<object>();foreach(object x in a)l.Add(Copy(x));return l;
        }
        internal static string Code(Exception e)
        {
            EpochFailure f=e as EpochFailure;if(f!=null)return f.Code;
            BootstrapFailure b=e as BootstrapFailure;if(b!=null)return "CODEC_"+b.Code;
            return "UNEXPECTED_MANAGED_FAILURE_"+e.GetType().Name;
        }
        internal static string Hash(Dictionary<string,object>d,string name)
        {string s=Data.HexField(d,name,64);Need(Data.NonzeroHex(s,64),"ZERO_DIGEST_"+name);return s;}
        internal static bool SameData(object a,object b) {return Data.Equal(CanonicalJson.Encode(a),CanonicalJson.Encode(b));}
    }
    internal sealed class EpochIdentity
    {
        internal readonly string Volume, FileId;
        internal EpochIdentity(string volume,string fileId)
        {EpochData.Need(Data.NonzeroHex(volume,16)&&Data.NonzeroHex(fileId,32),"INVALID_OBJECT_IDENTITY");Volume=volume;FileId=fileId;}
        internal static EpochIdentity Parse(object value)
        {var d=Data.Map(value,"volume_serial_hex","file_id_128_hex");return new EpochIdentity(Data.Str(d,"volume_serial_hex"),Data.Str(d,"file_id_128_hex"));}
        internal Dictionary<string,object> Export()
        {return new Dictionary<string,object>{{"volume_serial_hex",Volume},{"file_id_128_hex",FileId}};}
        internal bool Same(EpochIdentity b){return b!=null&&Volume==b.Volume&&FileId==b.FileId;}
        internal string Key {get{return Volume+":"+FileId;}}
    }
    internal sealed class EpochRecord
    {
        private readonly byte[] raw;
        private readonly Dictionary<string,object> data;
        internal EpochRecord(byte[] bytes,Dictionary<string,object> value){raw=(byte[])bytes.Clone();data=(Dictionary<string,object>)EpochData.Copy(value);}
        internal byte[] Raw(){return (byte[])raw.Clone();}
        internal Dictionary<string,object> Metadata(){return (Dictionary<string,object>)EpochData.Copy(data);}
        internal string Text(string key){return Data.Str(data,key);}
        internal long Number(string key){return (long)data[key];}
        internal object Field(string key){return EpochData.Copy(data[key]);}
        internal string Digest {get{return Data.Hash(raw);}}
        internal bool Same(EpochRecord other){return other!=null&&Data.Equal(raw,other.raw);}
        internal Dictionary<string,object> ExportUntrusted()
        {return new Dictionary<string,object>{{"kind","UNTRUSTED_EPOCH_STORE_RECORD"},{"raw_bytes",raw.Length},
            {"raw_sha256",Digest},{"metadata",Metadata()},{"claims",EpochData.Claims()}};}
    }
    internal static class EpochCodec
    {
        internal const int AnchorLimit=16384, StateLimit=4096, AcceptanceLimit=65536;
        private static Dictionary<string,object> Read(byte[] raw,int limit,string kind,params string[] fields)
        {var d=Data.Map(CanonicalJson.Parse(raw,limit),fields);EpochData.Need(Data.Str(d,"kind")==kind,"RECORD_KIND");Data.Num(d,"format_version",1,1);return d;}
        internal static EpochRecord Anchor(byte[] value)
        {
            byte[] raw=Data.Copy(value,AnchorLimit,"ANCHOR_SIZE");
            var d=Read(raw,AnchorLimit,"P00_INSTALL_ANCHOR_V1","kind","format_version","installation_namespace_id","host_release_id",
                "host_manifest_digest","observer_closure_digest","initial_policy_set_digest","threat_model_digest","os_boundary_digest",
                "lifecycle_protocol_id","delivery_review_id","state_store_slot","store_root_identity","gate_identity","reader_sid","writer_sids");
            Data.Id(d,"installation_namespace_id");Data.Id(d,"host_release_id");Data.Id(d,"delivery_review_id");
            foreach(string k in new[]{"host_manifest_digest","observer_closure_digest","initial_policy_set_digest","threat_model_digest","os_boundary_digest"})EpochData.Hash(d,k);
            EpochData.Need(Data.Str(d,"lifecycle_protocol_id")==EpochData.Protocol&&Data.Str(d,"state_store_slot")==EpochData.StoreSlot,"FIXED_STORE_PROFILE_REQUIRED");
            EpochIdentity root=EpochIdentity.Parse(d["store_root_identity"]), gate=EpochIdentity.Parse(d["gate_identity"]);
            EpochData.Need(root.Volume==gate.Volume&&!root.Same(gate),"ROOT_GATE_ALIAS_OR_VOLUME");
            EpochData.Need(InstallationRegistration.ServiceSid(Data.Str(d,"reader_sid")),"READER_SID_SYNTAX_ONLY");
            List<object>w=d["writer_sids"] as List<object>;
            EpochData.Need(w!=null&&w.Count==2&&(w[0] as string)=="S-1-5-18"&&(w[1] as string)=="S-1-5-32-544","FIXED_WRITER_PROFILE_REQUIRED");
            return new EpochRecord(raw,d);
        }
        internal static EpochRecord State(byte[] value)
        {
            byte[] raw=Data.Copy(value,StateLimit,"STATE_SIZE");
            var d=Read(raw,StateLimit,"P00_LIFECYCLE_STATE_V1","kind","format_version","installation_namespace_id","state",
                "publication_revision","acceptance_id","acceptance_bytes","acceptance_sha256","host_release_id","operation_id");
            Data.Id(d,"installation_namespace_id");Data.Id(d,"host_release_id");Data.Id(d,"operation_id");
            string state=Data.Str(d,"state");EpochData.Need(Array.IndexOf(new[]{"UNENROLLED","SUSPENDED","ACTIVE","INDETERMINATE","RETIRED"},state)>=0,"UNSUPPORTED_STATE");
            Data.Num(d,"publication_revision",state=="ACTIVE"?1:0,long.MaxValue);
            if(state=="ACTIVE") {Data.Id(d,"acceptance_id");Data.Num(d,"acceptance_bytes",1,AcceptanceLimit);EpochData.Hash(d,"acceptance_sha256");}
            else {EpochData.Need(d["acceptance_id"]==null&&d["acceptance_sha256"]==null,"NONACTIVE_MUST_NOT_SELECT_ACCEPTANCE");Data.Num(d,"acceptance_bytes",0,0);}
            return new EpochRecord(raw,d);
        }
        internal static EpochRecord Acceptance(byte[] value)
        {
            byte[] raw=Data.Copy(value,AcceptanceLimit,"ACCEPTANCE_SIZE");
            var d=Read(raw,AcceptanceLimit,"P00_EPOCH_ACCEPTANCE_V1","kind","format_version","acceptance_id","operation_id",
                "installation_namespace_id","deployment_id","provisioning_epoch","publication_revision","registration_id",
                "record_bytes","record_sha256","selector_bytes","selector_sha256","host_release_id","observer_closure_digest",
                "initial_policy_set_digest","threat_model_digest","os_boundary_digest","lifecycle_protocol_id","birth_evidence_digest",
                "predecessor_acceptance_digest","administrative_review_id");
            foreach(string k in new[]{"acceptance_id","operation_id","installation_namespace_id","deployment_id","provisioning_epoch","registration_id","host_release_id","administrative_review_id"})Data.Id(d,k);
            foreach(string k in new[]{"record_sha256","selector_sha256","observer_closure_digest","initial_policy_set_digest","threat_model_digest","os_boundary_digest","birth_evidence_digest"})EpochData.Hash(d,k);
            Data.Num(d,"publication_revision",1,long.MaxValue);Data.Num(d,"record_bytes",1,65536);Data.Num(d,"selector_bytes",1,4096);
            if(d["predecessor_acceptance_digest"]!=null)EpochData.Hash(d,"predecessor_acceptance_digest");
            EpochData.Need(Data.Str(d,"lifecycle_protocol_id")==EpochData.Protocol,"LIFECYCLE_PROTOCOL_MISMATCH");
            return new EpochRecord(raw,d);
        }
        internal static void Bind(EpochRecord anchor,EpochRecord state,EpochRecord acceptance)
        {
            EpochData.Need(anchor!=null&&state!=null&&acceptance!=null,"THREE_RECORDS_REQUIRED");
            EpochData.Need(state.Text("state")=="ACTIVE","LIFECYCLE_NOT_ACTIVE");
            foreach(string k in new[]{"installation_namespace_id","host_release_id"})
                EpochData.Need(anchor.Text(k)==state.Text(k)&&state.Text(k)==acceptance.Text(k),"ANCHOR_SELECTION_MISMATCH_"+k);
            foreach(string k in new[]{"observer_closure_digest","initial_policy_set_digest","threat_model_digest","os_boundary_digest","lifecycle_protocol_id"})
                EpochData.Need(anchor.Text(k)==acceptance.Text(k),"ACCEPTANCE_PROFILE_MISMATCH_"+k);
            EpochData.Need(state.Text("acceptance_id")==acceptance.Text("acceptance_id")&&state.Text("operation_id")==acceptance.Text("operation_id")
                &&state.Number("publication_revision")==acceptance.Number("publication_revision"),"SELECTION_TUPLE_MISMATCH");
            EpochData.Need(state.Number("acceptance_bytes")==acceptance.Raw().Length&&state.Text("acceptance_sha256")==acceptance.Digest,"ACCEPTANCE_BYTES_OR_DIGEST_MISMATCH");
        }
    }
    // Explicit simulated enrollment. A matching record is NOT evidence of origin or startup.
    internal sealed class SimulatedEnrollment
    {
        internal readonly EpochIdentity AnchorIdentity, RootIdentity, GateIdentity;
        internal readonly string AnchorDigest;
        internal readonly int AnchorBytes;
        private readonly EpochRecord expected;
        internal SimulatedEnrollment(byte[] independentAnchorVector,EpochIdentity anchorIdentity)
        {
            EpochData.Need(anchorIdentity!=null,"ENROLLMENT_ANCHOR_ID_REQUIRED");expected=EpochCodec.Anchor(independentAnchorVector);
            AnchorIdentity=anchorIdentity;RootIdentity=EpochIdentity.Parse(expected.Field("store_root_identity"));GateIdentity=EpochIdentity.Parse(expected.Field("gate_identity"));
            EpochData.Need(!AnchorIdentity.Same(RootIdentity)&&!AnchorIdentity.Same(GateIdentity),"ENROLLMENT_OBJECT_ALIAS");
            AnchorDigest=expected.Digest;AnchorBytes=expected.Raw().Length;
        }
        internal void CheckAnchor(EpochRecord a){EpochData.Need(a!=null&&a.Same(expected),"ENROLLED_ANCHOR_VECTOR_MISMATCH");}
    }
    internal interface IEpochClock { long Milliseconds {get;} }
    internal sealed class EpochWindow
    {
        private readonly IEpochClock clock;
        private readonly long start;
        private long last;
        private int revoked;
        internal const long Duration=8000;
        internal EpochWindow(IEpochClock source)
        {
            EpochData.Need(source!=null,"CLOCK_REQUIRED");clock=source;long n=source.Milliseconds;
            EpochData.Need(n>=0&&n<=long.MaxValue-Duration,"CLOCK_RANGE");start=n;last=n;
        }
        internal void Revoke(){Interlocked.Exchange(ref revoked,1);}
        internal void Check()
        {
            try {
                EpochData.Need(Interlocked.CompareExchange(ref revoked,0,0)==0,"LEASE_REVOKED");
                long n=clock.Milliseconds;
                EpochData.Need(Interlocked.CompareExchange(ref revoked,0,0)==0,"LEASE_REVOKED");
                EpochData.Need(n>=0&&n<=long.MaxValue-Duration,"CLOCK_RANGE");EpochData.Need(n>=last,"CLOCK_REVERSED");last=n;
                EpochData.Need(n<start+Duration,"ORIGINAL_DEADLINE_EXPIRED");
            }catch{Revoke();throw;}
        }
    }
    internal static class P00ProductionStart
    {
        internal static object OpenInstalled(){throw new EpochFailure("NATIVE_ENROLLMENT_TRUSTED_START_NOT_IMPLEMENTED");}
        internal static object ImportDiagnostic(object value){throw new EpochFailure("DETACHED_DATA_CANNOT_CREATE_P00_BASIS");}
        internal static object TransferNativeChildLease(){throw new EpochFailure("NATIVE_CHILD_GATE_HANDOFF_NOT_IMPLEMENTED");}
    }
}
