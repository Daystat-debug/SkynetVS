// New bounded candidate codec. No installed registration or trusted policy resolver is supplied.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;

namespace SkynetVS.G1.InstallationBootstrapV1
{
    internal sealed class BootstrapFailure : Exception
    {
        internal readonly string Code;
        internal readonly int? NativeCode;
        internal BootstrapFailure(string code) : base(code) { Code = code; }
        internal BootstrapFailure(string code, int native) : base(code) { Code = code; NativeCode = native; }
    }

    internal static class Data
    {
        internal static void Need(bool ok, string code) { if (!ok) throw new BootstrapFailure(code); }
        internal static byte[] Copy(byte[] a, int limit, string code)
        { Need(a != null && a.Length > 0 && a.Length <= limit, code); return (byte[])a.Clone(); }
        internal static bool Equal(byte[] a, byte[] b)
        { if (a == null || b == null || a.Length != b.Length) return false; for (int i=0;i<a.Length;i++) if(a[i]!=b[i])return false; return true; }
        internal static string Hash(byte[] a)
        { using (SHA256 h = SHA256.Create()) { byte[] d=h.ComputeHash(a); StringBuilder s=new StringBuilder(64);foreach(byte b in d)s.Append(b.ToString("x2",CultureInfo.InvariantCulture));return s.ToString(); } }
        internal static bool Hex(string s,int n)
        { if(s==null||s.Length!=n)return false;foreach(char c in s)if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')))return false;return true; }
        internal static bool NonzeroHex(string s,int n) { return Hex(s,n)&&s!=new string('0',n); }
        internal static object Clone(object x)
        {
            Dictionary<string,object> d=x as Dictionary<string,object>;
            if(d!=null){Dictionary<string,object> c=new Dictionary<string,object>(StringComparer.Ordinal);foreach(KeyValuePair<string,object> k in d)c.Add(k.Key,Clone(k.Value));return c;}
            List<object> l=x as List<object>;
            if(l!=null){List<object> c=new List<object>();foreach(object i in l)c.Add(Clone(i));return c;}
            return x; // codec leaves are immutable strings, Int64, bool and null
        }
        internal static Dictionary<string,object> Map(object o, params string[] keys)
        {
            Dictionary<string,object> d=o as Dictionary<string,object>;Need(d!=null,"OBJECT_REQUIRED");
            Need(d.Count==keys.Length,"EXACT_FIELD_SET_REQUIRED");foreach(string k in keys)Need(d.ContainsKey(k),"MISSING_FIELD_"+k);return d;
        }
        internal static string Str(Dictionary<string,object> d,string k){string s=d[k] as string;Need(s!=null,"STRING_REQUIRED_"+k);return s;}
        internal static long Num(Dictionary<string,object> d,string k,long lo,long hi)
        {Need(d[k] is long,"INTEGER_REQUIRED_"+k);long v=(long)d[k];Need(v>=lo&&v<=hi,"INTEGER_BOUND_"+k);return v;}
        internal static string HexField(Dictionary<string,object> d,string k,int n)
        {string s=Str(d,k);Need(Hex(s,n),"HEX_REQUIRED_"+k);return s;}
        internal static string Id(Dictionary<string,object> d,string k)
        {string s=HexField(d,k,32);Need(NonzeroHex(s,32),"ZERO_ID_"+k);return s;}
    }

    // Exact new wire grammar: compact JSON with ordinal-sorted keys and one final LF.
    // Only positive integer syntax is used by this schema; generic codec also reads bool/null.
    internal sealed class CanonicalJson
    {
        private readonly string text;
        private int pos, nodes;
        private CanonicalJson(string s){text=s;}
        internal static object Parse(byte[] input,int max)
        {
            byte[] raw=Data.Copy(input,max,"JSON_SIZE");string s;
            try{s=new UTF8Encoding(false,true).GetString(raw);}catch(DecoderFallbackException){throw new BootstrapFailure("INVALID_UTF8");}
            Data.Need(s.Length>1&&s[s.Length-1]=='\n',"FINAL_LF_REQUIRED");
            CanonicalJson p=new CanonicalJson(s.Substring(0,s.Length-1));object v=p.Value(0);
            Data.Need(p.pos==p.text.Length,"TRAILING_JSON");Data.Need(Data.Equal(raw,Encode(v)),"NONCANONICAL_JSON");return v;
        }
        private char Next(){Data.Need(pos<text.Length,"TRUNCATED_JSON");return text[pos++];}
        private void Lit(string s){for(int i=0;i<s.Length;i++)Data.Need(Next()==s[i],"JSON_LITERAL");}
        private object Value(int depth)
        {
            Data.Need(depth<=12&&++nodes<=2048,"JSON_COMPLEXITY");Data.Need(pos<text.Length,"TRUNCATED_JSON");char c=text[pos];
            if(c=='"')return String();
            if(c=='{'){
                pos++;Dictionary<string,object> d=new Dictionary<string,object>(StringComparer.Ordinal);
                if(pos<text.Length&&text[pos]=='}'){pos++;return d;}
                while(true){Data.Need(d.Count<64,"OBJECT_FIELD_BOUND");string k=String();Data.Need(k.Length<=80&&!d.ContainsKey(k),"DUPLICATE_OR_LONG_KEY");Data.Need(Next()==':',"COLON_REQUIRED");d.Add(k,Value(depth+1));char t=Next();if(t=='}')return d;Data.Need(t==',',"OBJECT_DELIMITER");}
            }
            if(c=='['){pos++;List<object> l=new List<object>();if(pos<text.Length&&text[pos]==']'){pos++;return l;}while(true){Data.Need(l.Count<64,"ARRAY_BOUND");l.Add(Value(depth+1));char t=Next();if(t==']')return l;Data.Need(t==',',"ARRAY_DELIMITER");}}
            if(c=='t'){Lit("true");return true;}if(c=='f'){Lit("false");return false;}if(c=='n'){Lit("null");return null;}
            Data.Need(c>='0'&&c<='9',"JSON_VALUE");int start=pos;while(pos<text.Length&&text[pos]>='0'&&text[pos]<='9')pos++;
            Data.Need(pos-start==1||text[start]!='0',"LEADING_ZERO");long number;
            Data.Need(long.TryParse(text.Substring(start,pos-start),NumberStyles.None,CultureInfo.InvariantCulture,out number),"NUMBER_OVERFLOW");return number;
        }
        private string String()
        {
            Data.Need(Next()=='"',"STRING_REQUIRED");StringBuilder b=new StringBuilder();
            while(true){char c=Next();if(c=='"')return b.ToString();Data.Need(c>=32&&c!='\u007f',"CONTROL_IN_STRING");
                if(c=='\\'){char e=Next();Data.Need(e=='"'||e=='\\',"NONCANONICAL_ESCAPE");b.Append(e);}
                else if(char.IsHighSurrogate(c)){char lo=Next();Data.Need(char.IsLowSurrogate(lo),"SURROGATE");b.Append(c).Append(lo);}
                else{Data.Need(!char.IsLowSurrogate(c),"SURROGATE");b.Append(c);}Data.Need(b.Length<=4096,"STRING_BOUND");}
        }
        internal static byte[] Encode(object o){StringBuilder b=new StringBuilder();Write(b,o,0);b.Append('\n');return new UTF8Encoding(false,true).GetBytes(b.ToString());}
        private static void Quoted(StringBuilder b,string s)
        {b.Append('"');foreach(char c in s){Data.Need(c>=32&&c!='\u007f',"CONTROL_IN_STRING");if(c=='"'||c=='\\')b.Append('\\');b.Append(c);}b.Append('"');}
        private static void Write(StringBuilder b,object o,int depth)
        {
            Data.Need(depth<=12,"JSON_DEPTH");if(o==null){b.Append("null");return;}if(o is string){Quoted(b,(string)o);return;}
            if(o is bool){b.Append((bool)o?"true":"false");return;}if(o is long||o is int){long n=Convert.ToInt64(o,CultureInfo.InvariantCulture);Data.Need(n>=0,"NEGATIVE_NUMBER");b.Append(n.ToString(CultureInfo.InvariantCulture));return;}
            Dictionary<string,object> d=o as Dictionary<string,object>;if(d!=null){List<string> keys=new List<string>(d.Keys);keys.Sort(StringComparer.Ordinal);b.Append('{');bool first=true;foreach(string k in keys){if(!first)b.Append(',');first=false;Quoted(b,k);b.Append(':');Write(b,d[k],depth+1);}b.Append('}');return;}
            System.Collections.IEnumerable list=o as System.Collections.IEnumerable;Data.Need(list!=null,"UNSUPPORTED_JSON_TYPE");b.Append('[');bool start=true;foreach(object x in list){if(!start)b.Append(',');start=false;Write(b,x,depth+1);}b.Append(']');
        }
    }

    internal sealed class SelectorCandidate
    {
        private readonly byte[] raw;
        internal readonly string RegistrationId, RegistrationSha256;
        internal readonly int RegistrationBytes;
        internal SelectorCandidate(byte[] b,string id,int len,string hash){raw=(byte[])b.Clone();RegistrationId=id;RegistrationBytes=len;RegistrationSha256=hash;}
        internal byte[] Raw(){return (byte[])raw.Clone();}
    }
    internal sealed class RegistrationCandidate
    {
        private readonly byte[] raw;
        private readonly Dictionary<string,object> metadata;
        internal readonly string RegistrationId;
        internal RegistrationCandidate(byte[] b,Dictionary<string,object> d,string id){raw=(byte[])b.Clone();metadata=(Dictionary<string,object>)Data.Clone(d);RegistrationId=id;}
        internal byte[] Raw(){return (byte[])raw.Clone();}
        internal Dictionary<string,object> Metadata(){return (Dictionary<string,object>)Data.Clone(metadata);}
        internal Dictionary<string,object> Export()
        {return new Dictionary<string,object>{{"kind","INSTALLATION_REGISTRATION_CANDIDATE_V1"},{"status","PARSED_REGISTRATION_CANDIDATE_NOT_AUTHENTICATED"},{"registration_id",RegistrationId},{"raw_sha256",Data.Hash(raw)},{"raw_bytes",(long)raw.Length},{"raw_base64",Convert.ToBase64String(raw)},{"metadata",Metadata()},{"claims",Trust.ClosedClaims()}};}
    }
    internal static class Trust
    {
        internal static Dictionary<string,object> ClosedClaims()
        {Dictionary<string,object>d=new Dictionary<string,object>();foreach(string k in new[]{"installation_registration_authenticated","registry_protection_proven","root_registration_authenticated","service_identity_verified","protected_root_admitted","protected_provenance","candidate_set_verified","authority_admitted","live_context_created","execution_authorized","runtime_attestation","continuous_namespace_proven","read_lease_created","policies_resolved","production_profile_approved"})d.Add(k,false);return d;}
        internal static object OpenAuthenticated(RegistrationCandidate candidate){throw new BootstrapFailure("REGISTRY_PROTECTION_PRODUCER_NOT_IMPLEMENTED");}
    }

    internal static class InstallationRegistration
    {
        internal const int SelectorLimit=4096, RecordLimit=65536;
        internal static readonly string[] PolicyNames={"registry_private","registry_platform_parent","filesystem_platform_parent","authority_private","ledger_private","scm_configuration","service_process_object","service_primary_token","pipe_security","loader"};
        internal static SelectorCandidate ParseSelector(byte[] raw)
        {
            byte[] b=Data.Copy(raw,SelectorLimit,"SELECTOR_SIZE");Dictionary<string,object>d=Data.Map(CanonicalJson.Parse(b,SelectorLimit),"kind","schema_version","registration_id","registration_bytes","registration_sha256");
            Data.Need(Data.Str(d,"kind")=="SKYNETVS_ACTIVE_INSTALLATION_V1","SELECTOR_KIND");Data.Num(d,"schema_version",1,1);
            return new SelectorCandidate(b,Data.Id(d,"registration_id"),(int)Data.Num(d,"registration_bytes",1,RecordLimit),Data.HexField(d,"registration_sha256",64));
        }
        internal static RegistrationCandidate ParseRecord(byte[] input,SelectorCandidate selected)
        {
            Data.Need(selected!=null,"SELECTOR_REQUIRED");byte[] b=Data.Copy(input,RecordLimit,"RECORD_SIZE");
            Data.Need(b.Length==selected.RegistrationBytes&&Data.Hash(b)==selected.RegistrationSha256,"SELECTOR_RECORD_BINDING_MISMATCH");
            Dictionary<string,object>d=Data.Map(CanonicalJson.Parse(b,RecordLimit),"kind","schema_version","registration_id","deployment_id","provisioning_epoch","installation_policy_sha256","service","roots","release","public_protocol","policy_refs");
            Data.Need(Data.Str(d,"kind")=="SKYNETVS_GUARD_INSTALLATION_V1","RECORD_KIND");Data.Num(d,"schema_version",1,1);
            string id=Data.Id(d,"registration_id");Data.Need(id==selected.RegistrationId,"REGISTRATION_ID_MISMATCH");Data.Id(d,"deployment_id");Data.Id(d,"provisioning_epoch");Data.HexField(d,"installation_policy_sha256",64);
            Data.Need(Data.Str(d,"public_protocol")=="skynetvs-guard-control-v1","PROTOCOL");
            Dictionary<string,object> policies=Data.Map(d["policy_refs"],PolicyNames);foreach(string p in PolicyNames)Data.HexField(policies,p,64);
            Dictionary<string,object>s=Data.Map(d["service"],"name","account","service_sid","sid_type","service_type","binary_command_line","approved_config_sha256","required_privileges_policy_ref");
            Data.Need(Data.Str(s,"name")=="SkynetVSGuard"&&Data.Str(s,"account")=="NT SERVICE\\SkynetVSGuard","SERVICE_PROFILE");
            Data.Need(ServiceSid(Data.Str(s,"service_sid")),"SERVICE_SID_SYNTAX");long st=Data.Num(s,"sid_type",1,3);Data.Need(st==1||st==3,"EXACT_SID_TYPE");Data.Num(s,"service_type",16,16);
            Data.Need(ImageCommand(Data.Str(s,"binary_command_line")),"IMAGE_COMMAND_SYNTAX");Data.HexField(s,"approved_config_sha256",64);Data.HexField(s,"required_privileges_policy_ref",64);
            Dictionary<string,object>roots=Data.Map(d["roots"],"authority_store","ledger_store");Dictionary<string,object>a=Root(roots["authority_store"]),l=Root(roots["ledger_store"]);
            Data.Need(Data.Str(a,"registration_root_id")!=Data.Str(l,"registration_root_id"),"ROOT_ROLE_ALIAS");
            bool sameVolume=Data.Str(a,"volume_serial_hex")==Data.Str(l,"volume_serial_hex");
            Data.Need(!(sameVolume&&Data.Str(a,"root_file_id_128_hex")==Data.Str(l,"root_file_id_128_hex")),"ROOT_ROLE_ALIAS");
            if(Data.Str(a,"volume_locator")==Data.Str(l,"volume_locator"))Data.Need(sameVolume,"VOLUME_METADATA_CONFLICT");
            if(sameVolume&&Data.Str(a,"anchor_file_id_128_hex")==Data.Str(l,"anchor_file_id_128_hex")){
                List<object> ap=(List<object>)a["component_plan"],lp=(List<object>)l["component_plan"];int n=Math.Min(ap.Count,lp.Count);bool prefix=true;
                for(int i=0;i<n;i++)if(!String.Equals((string)ap[i],(string)lp[i],StringComparison.OrdinalIgnoreCase))prefix=false;
                Data.Need(!prefix,"WRITABLE_ROOT_OVERLAP");}
            Dictionary<string,object>r=Data.Map(d["release"],"release_id","loader_closure_sha256","protected_release_root_ref","manifest_bytes","manifest_sha256");
            Data.Id(r,"release_id");Data.Id(r,"protected_release_root_ref");Data.HexField(r,"loader_closure_sha256",64);Data.HexField(r,"manifest_sha256",64);
            Data.Num(r,"manifest_bytes",1,16777216); // candidate metadata cap only; no release manifest is read
            return new RegistrationCandidate(b,d,id);
        }
        private static Dictionary<string,object> Root(object value)
        {
            Dictionary<string,object>d=Data.Map(value,"registration_root_id","volume_locator","volume_serial_hex","anchor_file_id_128_hex","root_file_id_128_hex","component_plan","private_boundary_index","parent_policy_ref","private_policy_ref");
            Data.Id(d,"registration_root_id");Data.Need(VolumeLocator(Data.Str(d,"volume_locator")),"VOLUME_LOCATOR_SYNTAX");
            foreach(string f in new[]{"volume_serial_hex","anchor_file_id_128_hex","root_file_id_128_hex"}){int n=f=="volume_serial_hex"?16:32;Data.Need(Data.NonzeroHex(Data.Str(d,f),n),"ROOT_IDENTITY_SYNTAX");}
            List<object>p=d["component_plan"] as List<object>;Data.Need(p!=null&&p.Count>=1&&p.Count<=16,"COMPONENT_PLAN_BOUND");foreach(object v in p)Data.Need(Component(v as string),"ROOT_COMPONENT");
            Data.Num(d,"private_boundary_index",0,p.Count-1);Data.HexField(d,"parent_policy_ref",64);Data.HexField(d,"private_policy_ref",64);return d;
        }
        internal static bool ServiceSid(string s)
        {
            if(s==null||s.Length>80)return false;string[] a=s.Split('-');if(a.Length!=9||a[0]!="S"||a[1]!="1"||a[2]!="5"||a[3]!="80")return false;
            for(int i=4;i<9;i++){if(a[i].Length==0||a[i].Length>10||(a[i].Length>1&&a[i][0]=='0'))return false;foreach(char c in a[i])if(c<'0'||c>'9')return false;uint v;if(!uint.TryParse(a[i],NumberStyles.None,CultureInfo.InvariantCulture,out v))return false;}return true;
        }
        internal static bool VolumeLocator(string s)
        {
            const string pre="\\\\?\\Volume{";if(s==null||s.Length!=49||!s.StartsWith(pre,StringComparison.Ordinal)||!s.EndsWith("}\\",StringComparison.Ordinal))return false;
            string g=s.Substring(pre.Length,36);for(int i=0;i<g.Length;i++){if(i==8||i==13||i==18||i==23){if(g[i]!='-')return false;}else if(!Data.Hex(g[i].ToString(),1))return false;}return g!="00000000-0000-0000-0000-000000000000";
        }
        internal static bool Component(string s)
        {
            if(s==null||s.Length==0||s.Length>64||s[0]=='.'||s[s.Length-1]=='.')return false;
            foreach(char c in s)if(!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='_'||c=='-'||c=='.'))return false;
            string stem=s.Split('.')[0].ToUpperInvariant();if(stem=="CON"||stem=="PRN"||stem=="AUX"||stem=="NUL")return false;
            if(stem.Length==4&&(stem.StartsWith("COM",StringComparison.Ordinal)||stem.StartsWith("LPT",StringComparison.Ordinal))&&stem[3]>='0'&&stem[3]<='9')return false;return true;
        }
        internal static bool ImageCommand(string s)
        {
            if(s==null||s.Length<10||s.Length>1026||s[0]!='"'||s[s.Length-1]!='"')return false;string p=s.Substring(1,s.Length-2);
            if(p.Length<7||p[0]<'A'||p[0]>'Z'||p[1]!=':'||p[2]!='\\'||!p.EndsWith(".exe",StringComparison.Ordinal))return false;
            string[] a=p.Substring(3).Split('\\');foreach(string c in a){if(c.Length==0||c.Length>128||c[0]==' '||c[c.Length-1]==' '||c[c.Length-1]=='.')return false;foreach(char ch in c)if(!((ch>='a'&&ch<='z')||(ch>='A'&&ch<='Z')||(ch>='0'&&ch<='9')||ch==' '||ch=='_'||ch=='-'||ch=='.'))return false;string st=c.Split('.')[0].ToUpperInvariant();if(st=="CON"||st=="PRN"||st=="AUX"||st=="NUL"||(st.Length==4&&(st.StartsWith("COM",StringComparison.Ordinal)||st.StartsWith("LPT",StringComparison.Ordinal))&&st[3]>='0'&&st[3]<='9'))return false;}return true;
        }
    }
}
