using System;
using System.Collections.Generic;
using System.Threading;
using SkynetVS.G1.InstallationBootstrapV1;
using SkynetVS.G1.P00EpochReadLeaseV1;
using SkynetVS.G1.SameHandleV1;
namespace SkynetVS.G1.P00EpochNativeStoreV1
{
    internal enum StoreRole { HostReleaseRoot, StoreRoot, InstallAnchor, Gate, State, AcceptanceDirectory, Acceptance }
    internal sealed class EpochIoFailure : Exception
    {
        internal readonly string Code;internal readonly int? NtStatus;internal readonly bool Terminal;
        internal EpochIoFailure(string code,int? status,bool terminal,Exception inner):base(code,inner)
        {Code=code;NtStatus=status;Terminal=terminal;}
        internal Dictionary<string,object> Export()
        {
            ObservationFailure o=InnerException as ObservationFailure;
            return new Dictionary<string,object>{{"code",Code},{"ntstatus_hex",NtStatus.HasValue?unchecked((uint)NtStatus.Value).ToString("x8"):null},
                {"terminal",Terminal},{"inner_type",InnerException==null?null:InnerException.GetType().Name},
                {"inner_message",InnerException==null?null:InnerException.Message},{"win32_code",o==null?null:(object)o.NativeCode},
                {"observer_stage",o==null?null:o.Stage}};
        }
    }
    internal static class StoreContract
    {
        internal const string FakeDomain="SYNTHETIC_EPOCH_NATIVE_IO_TEST_ONLY";
        internal static void Need(bool ok,string code){if(!ok)throw new EpochIoFailure(code,null,false,null);}
        internal static Dictionary<string,object> Claims()
        {
            var d=EpochData.Claims();foreach(string k in new[]{"installed_path_resolution_implemented","root_origin_authenticated",
                "native_read_semantics_host_verified","native_gate_sharing_host_verified","native_child_handoff_implemented"})d[k]=false;
            return d;
        }
        internal static Dictionary<string,object> Error(Exception e)
        {var f=e as ObservationFailure;return new Dictionary<string,object>{{"type",e.GetType().Name},{"message",e.Message},{"observer_stage",f==null?null:f.Stage},{"win32_code",f==null?null:(object)f.NativeCode}};}
        internal static string Name(StoreRole role,string selected)
        {
            Need(Enum.IsDefined(typeof(StoreRole),role),"UNKNOWN_ROLE");
            Need((role==StoreRole.Acceptance)==(selected!=null),"SELECTOR_ROLE");
            if(role==StoreRole.Acceptance){Need(Data.NonzeroHex(selected,32),"CANONICAL_ACCEPTANCE_ID");return selected+".bin";}
            switch(role){case StoreRole.InstallAnchor:return "InstallAnchor.bin";case StoreRole.Gate:return "Lifecycle.gate";
                case StoreRole.State:return "Lifecycle.state";case StoreRole.AcceptanceDirectory:return "Acceptances";}
            throw new EpochIoFailure("ROOTS_NOT_PATH_OPENED",null,false,null);
        }
        internal static bool IsDirectory(StoreRole role){return role==StoreRole.HostReleaseRoot||role==StoreRole.StoreRoot||role==StoreRole.AcceptanceDirectory;}
        internal static int Cap(StoreRole role)
        {switch(role){case StoreRole.InstallAnchor:return EpochCodec.AnchorLimit;case StoreRole.State:return EpochCodec.StateLimit;
            case StoreRole.Acceptance:return EpochCodec.AcceptanceLimit;default:return 0;}}
        internal static EpochIdentity Identity(FileFacts f){return new EpochIdentity(f.Volume.ToString("x16"),Binary.Hex(f.Id));}
    }
    // This input explicitly does NOT authenticate a root/epoch. No installed path resolver is supplied.
    internal sealed class DiagnosticEpochExpectation
    {
        internal readonly EpochRecord Anchor;
        internal readonly EpochIdentity HostRoot, AnchorId, StoreRoot, Gate;
        internal DiagnosticEpochExpectation(byte[] independentAnchorVector,EpochIdentity hostRoot,EpochIdentity anchorId)
        {
            StoreContract.Need(hostRoot!=null&&anchorId!=null,"DIAGNOSTIC_IDENTITIES_REQUIRED");
            Anchor=EpochCodec.Anchor(independentAnchorVector);HostRoot=hostRoot;AnchorId=anchorId;
            StoreRoot=EpochIdentity.Parse(Anchor.Field("store_root_identity"));Gate=EpochIdentity.Parse(Anchor.Field("gate_identity"));
            StoreContract.Need(hostRoot.Volume==anchorId.Volume,"HOST_ANCHOR_VOLUME");
            var ids=new HashSet<string>(StringComparer.Ordinal);
            foreach(EpochIdentity v in new[]{HostRoot,AnchorId,StoreRoot,Gate})StoreContract.Need(ids.Add(v.Key),"EXPECTED_OBJECT_ALIAS");
        }
        internal EpochIdentity Expected(StoreRole r)
        {switch(r){case StoreRole.HostReleaseRoot:return HostRoot;case StoreRole.StoreRoot:return StoreRoot;
            case StoreRole.InstallAnchor:return AnchorId;case StoreRole.Gate:return Gate;default:return null;}}
    }
    internal sealed class OwnedDiagnosticRootPair
    {
        internal readonly IntPtr Host, Store;
        private int consumed;
        internal OwnedDiagnosticRootPair(IntPtr host,IntPtr store)
        {StoreContract.Need(host.ToInt64()>0&&store.ToInt64()>0&&host!=store,"TWO_DISTINCT_OWNED_ROOT_HANDLES");Host=host;Store=store;}
        internal void Take(){StoreContract.Need(Interlocked.Exchange(ref consumed,1)==0,"ROOT_PAIR_ALREADY_TAKEN");}
        // Caller relinquishes both handles only after Attach returns successfully.
        // Native caller must supply synchronous, local, directory objects and independent supervision.
    }
    internal sealed class StoreRef
    {
        internal readonly object Owner;internal readonly StoreRole Role;internal IntPtr Handle;
        internal bool Closed,CloseAttempted;
        internal StoreSnapshot Initial;
        internal StoreRef(object owner,StoreRole role,IntPtr handle){Owner=owner;Role=role;Handle=handle;}
    }
    internal sealed class StoreSnapshot
    {
        internal readonly FileFacts Facts;internal readonly uint DeviceType,DeviceFlags;
        private readonly byte[] security;
        internal StoreSnapshot(FileFacts f,uint type,uint flags,byte[] raw)
        {Facts=CopyFacts(f);DeviceType=type;DeviceFlags=flags;security=(byte[])raw.Clone();}
        internal byte[] Security(){return (byte[])security.Clone();}
        internal bool Same(StoreSnapshot b){return b!=null&&Facts.Stable(b.Facts)&&DeviceType==b.DeviceType&&DeviceFlags==b.DeviceFlags&&Binary.Equal(security,b.security);}
        internal static FileFacts CopyFacts(FileFacts f)
        {
            StoreContract.Need(f!=null&&f.Id!=null&&f.Id.Length==16,"FACTS_SHAPE");
            return new FileFacts{FileType=f.FileType,Attributes=f.Attributes,ReparseTag=f.ReparseTag,Links=f.Links,Volume=f.Volume,Id=(byte[])f.Id.Clone(),
                Size=f.Size,Allocation=f.Allocation,Creation=f.Creation,Access=f.Access,Write=f.Write,Change=f.Change,
                DeletePending=f.DeletePending,Directory=f.Directory};
        }
    }
    internal static class InstalledEpochNativeAdmission
    {
        internal static object OpenInstalled(){throw new EpochFailure("ENROLLED_ROOT_RESOLVER_TRUSTED_START_NOT_IMPLEMENTED");}
        internal static object TransferChildLease(){throw new EpochFailure("NATIVE_GATE_CHILD_HANDOFF_NOT_IMPLEMENTED");}
        internal static object ImportDiagnostic(object ignored){throw new EpochFailure("DIAGNOSTIC_IS_NOT_P00_BASIS");}
    }
}
