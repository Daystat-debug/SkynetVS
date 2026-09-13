using System;
using System.Collections.Generic;
using SkynetVS.G1.ParentChainV1;
using SkynetVS.G1.SameHandleV1;

namespace SkynetVS.G1.InstalledRootCandidateV1
{
    // Candidate discovery only. No public path/release/policy input and no P00 factory.
    internal sealed class RootFailure : Exception
    {
        internal readonly string Code; internal readonly bool Terminal;
        internal RootFailure(string code, bool terminal) : base(code) { Code=code; Terminal=terminal; }
    }
    internal static class Rules
    {
        internal const int MaxPath=2048, MaxComponents=16, MaxHandles=36, MaxCalls=512;
        internal const string NativeDomain="WINDOWS_INSTALLED_ROOT_CANDIDATE_NOT_ENROLLMENT";
        internal const string FakeDomain="SYNTHETIC_INSTALLED_ROOT_ONLY";
        internal static void Need(bool value,string code) { if(!value)throw new RootFailure(code,false); }
        internal static Dictionary<string,object> Claims()
        {
            var d=new Dictionary<string,object>();
            foreach(string s in new[]{"root_origin_authenticated","p00_delivery_accepted","p01_producer_implemented",
                "runtime_attestation","service_identity_verified","enrollment_accepted","loaded_image_identity_proven",
                "epoch_acceptance_authenticated","authority_admitted","execution_authorized","continuous_namespace_proven",
                "acl_policy_accepted","live_root_pair_released"})d[s]=false;
            return d;
        }
    }
    internal sealed class LocationInput
    {
        internal readonly string ProgramFiles, ProgramData, Image;
        internal LocationInput(string pf,string pd,string image) { ProgramFiles=pf;ProgramData=pd;Image=image; }
        internal bool Same(LocationInput other) { return other!=null&&ProgramFiles==other.ProgramFiles&&ProgramData==other.ProgramData&&Image==other.Image; }
    }
    internal sealed class LocalPath
    {
        internal readonly string Drive, Text;
        private readonly string[] parts;
        private LocalPath(string text,string[] components) { Text=text;Drive=text.Substring(0,3);parts=components; }
        internal string[] Parts() { return (string[])parts.Clone(); }
        internal static LocalPath Parse(string value)
        {
            Rules.Need(value!=null&&value.Length>=3&&value.Length<=Rules.MaxPath,"LOCAL_PATH_BOUND");
            // Deliberately support only ordinary DOS local paths, not aliases/UNC/long-path prefixes.
            Rules.Need(value[0]>='A'&&value[0]<='Z'&&value[1]==':'&&value[2]=='\\',"LOCAL_DOS_PATH_REQUIRED");
            Rules.Need(value.Length==3||!value.EndsWith("\\",StringComparison.Ordinal),"TRAILING_SEPARATOR");
            string[] p=value.Length==3?new string[0]:value.Substring(3).Split('\\');
            Rules.Need(p.Length<=Rules.MaxComponents,"PATH_DEPTH_BOUND");
            foreach(string c in p){Limits.Component(c);Rules.Need(c.IndexOf('~')<0,"SHORT_ALIAS_SYNTAX_UNSUPPORTED");} // Fixed narrow path profile.
            return new LocalPath(value,p);
        }
        internal LocalPath Append(params string[] extra)
        { foreach(string c in extra)Limits.Component(c);return Parse(Text+(Text.EndsWith("\\",StringComparison.Ordinal)?"":"\\")+String.Join("\\",extra)); }
    }
    internal sealed class LayoutPlan
    {
        internal readonly LocalPath Host, Store, Image;
        internal readonly string ReleaseId;
        private LayoutPlan(LocalPath host,LocalPath store,LocalPath image,string release)
        { Host=host;Store=store;Image=image;ReleaseId=release; }
        internal static LayoutPlan FromObservedLocations(LocationInput input)
        {
            Rules.Need(input!=null,"LOCATIONS_REQUIRED");
            LocalPath pf=LocalPath.Parse(input.ProgramFiles),pd=LocalPath.Parse(input.ProgramData),image=LocalPath.Parse(input.Image);
            Rules.Need(pf.Parts().Length>0&&pd.Parts().Length>0,"KNOWN_FOLDER_CANNOT_BE_VOLUME_ROOT");
            LocalPath releases=pf.Append("SkynetVS","TrustedHost","releases");
            string prefix=releases.Text+"\\";
            if(!image.Text.StartsWith(prefix,StringComparison.OrdinalIgnoreCase))return null;
            string[] tail=image.Text.Substring(prefix.Length).Split('\\');
            if(tail.Length!=2||!String.Equals(tail[1],"Guard.exe",StringComparison.OrdinalIgnoreCase))return null;
            string id=tail[0];bool nonzero=false;
            if(id.Length!=32)return null;
            foreach(char c in id){if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')))return null;if(c!='0')nonzero=true;}
            if(!nonzero)return null;
            LocalPath host=releases.Append(id),store=pd.Append("SkynetVS-Trust","LifecycleV1");
            Rules.Need(!IsWithin(host.Text,store.Text)&&!IsWithin(store.Text,host.Text),"HOST_STORE_PATH_OVERLAP");
            Rules.Need(host.Parts().Length+store.Parts().Length+3<=Rules.MaxHandles,"HANDLE_PLAN_BOUND");
            return new LayoutPlan(host,store,image,id);
        }
        private static bool IsWithin(string a,string b)
        { return String.Equals(a,b,StringComparison.OrdinalIgnoreCase)||a.StartsWith(b+"\\",StringComparison.OrdinalIgnoreCase); }
    }
    internal sealed class OpenOutcome
    {
        internal readonly IntPtr Handle; internal readonly bool Missing;
        internal OpenOutcome(IntPtr handle,bool missing){Handle=handle;Missing=missing;}
    }
    internal interface IRootCalls
    {
        string Domain { get; }
        LocationInput Locations();
        OpenOutcome OpenVolume(string drive);
        OpenOutcome OpenRelative(IntPtr parent,string component,bool directory);
        FileFacts Facts(IntPtr handle);
        DeviceFacts Device(IntPtr handle);
        byte[] Security(IntPtr handle);
        void Close(IntPtr handle);
    }
    internal interface IRootClock { long Milliseconds { get; } }
    internal static class ProductionRootAdmission
    {
        internal static object OpenInstalled(){throw new RootFailure("P00_ENROLLMENT_AND_LOADER_NOT_ACCEPTED",false);}
        internal static object ImportObservation(object ignored){throw new RootFailure("DETACHED_OBSERVATION_IS_NOT_ROOT_AUTHORITY",false);}
    }
}
