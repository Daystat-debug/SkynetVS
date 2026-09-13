using System;
using System.Collections.Generic;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Threading;

namespace SkynetVS.G1.SameHandleV1
{
    // Observation only. No public control protocol, issuer, ACL setter or live receipt factory.
    public sealed class ObservationFailure : Exception
    {
        public readonly string Stage;
        public readonly int? NativeCode;
        public ObservationFailure(string stage, string detail, int? code) : base(detail)
        { Stage = stage; NativeCode = code; }
    }

    public static class Binary
    {
        public static void Range(byte[] b, int at, int count)
        {
            if (b == null || at < 0 || count < 0 || at > b.Length || count > b.Length - at)
                throw new ObservationFailure("bounded_decode", "Field outside returned buffer", null);
        }
        public static uint U16(byte[] b, int at)
        { Range(b, at, 2); return (uint)b[at] | ((uint)b[at + 1] << 8); }
        public static uint U32(byte[] b, int at)
        { Range(b, at, 4); return (uint)b[at] | ((uint)b[at+1]<<8) | ((uint)b[at+2]<<16) | ((uint)b[at+3]<<24); }
        public static ulong U64(byte[] b, int at)
        { Range(b, at, 8); return (ulong)U32(b, at) | ((ulong)U32(b, at+4)<<32); }
        public static long I64(byte[] b, int at) { return unchecked((long)U64(b, at)); }
        public static byte[] Slice(byte[] b, int at, int n)
        { Range(b, at, n); byte[] r = new byte[n]; Buffer.BlockCopy(b, at, r, 0, n); return r; }
        public static bool Equal(byte[] a, byte[] b)
        {
            if (a == null || b == null || a.Length != b.Length) return false;
            for (int i=0; i<a.Length; ++i) if (a[i] != b[i]) return false;
            return true;
        }
        public static string Hex(byte[] b) { return BitConverter.ToString(b).Replace("-", "").ToLowerInvariant(); }
        public static string Hash(byte[] b)
        { using (SHA256 h = SHA256.Create()) { return Hex(h.ComputeHash(b)); } }
    }

    public sealed class FileFacts
    {
        public uint FileType, Attributes, ReparseTag, Links;
        public ulong Volume;
        public byte[] Id;
        public long Size, Allocation, Creation, Access, Write, Change;
        public bool DeletePending, Directory;
        public static FileFacts Decode(uint type, byte[] id, byte[] standard, byte[] tag, byte[] basic)
        {
            if (id.Length != 24 || standard.Length != 24 || tag.Length != 8 || basic.Length != 40)
                throw new ObservationFailure("file_metadata", "Unexpected fixed structure buffer size", null);
            if (standard[20] > 1 || standard[21] > 1)
                throw new ObservationFailure("file_metadata", "Invalid BOOLEAN in FILE_STANDARD_INFO", null);
            FileFacts f = new FileFacts(); f.FileType = type;
            f.Volume = Binary.U64(id,0); f.Id = Binary.Slice(id,8,16);
            f.Allocation = Binary.I64(standard,0); f.Size = Binary.I64(standard,8);
            f.Links = Binary.U32(standard,16); f.DeletePending = standard[20] != 0; f.Directory = standard[21] != 0;
            f.Attributes = Binary.U32(tag,0); f.ReparseTag = Binary.U32(tag,4);
            f.Creation = Binary.I64(basic,0); f.Access = Binary.I64(basic,8);
            f.Write = Binary.I64(basic,16); f.Change = Binary.I64(basic,24);
            if (Binary.U32(basic,32) != f.Attributes)
                throw new ObservationFailure("file_metadata", "Basic and attribute-tag snapshots disagree", null);
            return f;
        }
        public void RequireOrdinaryLeaf(int maxBytes)
        {
            if (FileType != 1 || Directory || (Attributes & 0x10u) != 0)
                throw new ObservationFailure("file_kind", "Only a disk-file leaf is supported", null);
            if ((Attributes & (0x400u | 0x1000u | 0x40000u | 0x400000u)) != 0 || ReparseTag != 0)
                throw new ObservationFailure("file_kind", "Reparse/offline/recall leaf rejected", null);
            if (DeletePending || Links != 1)
                throw new ObservationFailure("file_kind", "Delete-pending or non-single-link leaf rejected", null);
            if (Size < 0 || Size > maxBytes || Allocation < 0)
                throw new ObservationFailure("file_size", "File size outside fixed capture budget", null);
        }
        public bool Stable(FileFacts o)
        {
            // LastAccessTime is recorded, not compared: a read may update it.
            return o != null && FileType == o.FileType && Volume == o.Volume && Binary.Equal(Id,o.Id)
                && Size == o.Size && Allocation == o.Allocation && Links == o.Links
                && Attributes == o.Attributes && ReparseTag == o.ReparseTag
                && Creation == o.Creation && Write == o.Write && Change == o.Change
                && DeletePending == o.DeletePending && Directory == o.Directory;
        }
        public Dictionary<string, object> Record()
        {
            return new Dictionary<string, object> {
                {"file_type",FileType},{"volume_serial_hex",Volume.ToString("x16",CultureInfo.InvariantCulture)},
                {"file_id_128_hex",Binary.Hex(Id)},{"size",Size},{"allocation",Allocation},
                {"links",Links},{"attributes",Attributes},{"reparse_tag",ReparseTag},
                {"delete_pending",DeletePending},{"directory",Directory},
                {"creation_time",Creation},{"last_access_time",Access},{"last_write_time",Write},{"change_time",Change}
            };
        }
    }

    // Bounded managed decoder. It reports ACEs; it does NOT calculate effective access.
    public static class Descriptor
    {
        private static int Offset(byte[] b, int at)
        { uint n=Binary.U32(b,at); if(n>65536) throw new ObservationFailure("descriptor", "Offset exceeds budget", null); return (int)n; }
        private static string Sid(byte[] b, int at, int end, out int length)
        {
            Binary.Range(b,at,8);
            if(at < 20 || at+8>end || b[at]!=1 || b[at+1]>15)
                throw new ObservationFailure("descriptor_sid", "Invalid SID header or offset", null);
            length=8+4*b[at+1]; Binary.Range(b,at,length);
            if(length>end-at) throw new ObservationFailure("descriptor_sid", "SID extends beyond its container", null);
            ulong authority=0;
            for(int i=2;i<8;i++) authority=(authority<<8)|b[at+i];
            string result="S-1-"+authority.ToString(CultureInfo.InvariantCulture);
            for(int i=0;i<b[at+1];i++) result+="-"+Binary.U32(b,at+8+4*i).ToString(CultureInfo.InvariantCulture);
            return result;
        }
        public static Dictionary<string,object> Decode(byte[] b)
        {
            if(b==null || b.Length<20 || b.Length>65536 || b[0]!=1)
                throw new ObservationFailure("descriptor", "Unsupported descriptor header/length", null);
            uint control=Binary.U16(b,2);
            if((control&0x8000)==0 || Offset(b,12)!=0)
                throw new ObservationFailure("descriptor", "Expected self-relative OWNER/GROUP/DACL-only descriptor", null);
            int ownerAt=Offset(b,4), groupAt=Offset(b,8), aclAt=Offset(b,16), ownerLen=0,groupLen=0;
            foreach(int n in new int[]{ownerAt,groupAt,aclAt})
                if(n!=0 && (n<20 || n%4!=0 || n>=b.Length))
                    throw new ObservationFailure("descriptor", "Unaligned/out-of-range descriptor offset", null);
            string owner=ownerAt==0?null:Sid(b,ownerAt,b.Length,out ownerLen);
            string group=groupAt==0?null:Sid(b,groupAt,b.Length,out groupLen);
            bool present=(control&4)!=0, nullDacl=present && aclAt==0;
            if(!present && aclAt!=0) throw new ObservationFailure("descriptor", "DACL offset without PRESENT flag", null);
            int aclLen=0; bool onlyBasic=true; List<object> aces=new List<object>();
            if(present && !nullDacl)
            {
                Binary.Range(b,aclAt,8); aclLen=(int)Binary.U16(b,aclAt+2);
                int count=(int)Binary.U16(b,aclAt+4);
                if((b[aclAt]!=2 && b[aclAt]!=4) || aclLen<8 || count>256)
                    throw new ObservationFailure("descriptor_acl", "Unsupported ACL header/budget", null);
                Binary.Range(b,aclAt,aclLen); int pos=aclAt+8,end=aclAt+aclLen;
                for(int i=0;i<count;i++)
                {
                    if(end-pos<4) throw new ObservationFailure("descriptor_ace", "Truncated ACE header", null);
                    int size=(int)Binary.U16(b,pos+2), type=b[pos], flags=b[pos+1];
                    if(size<4 || size%4!=0 || size>end-pos)
                        throw new ObservationFailure("descriptor_ace", "Invalid ACE size", null);
                    bool basic=type==0 || type==1; object sid=null,mask=null;
                    if(basic)
                    {
                        if(size<16) throw new ObservationFailure("descriptor_ace", "Basic ACE too short", null);
                        int sidLen; sid=Sid(b,pos+8,pos+size,out sidLen); mask=Binary.U32(b,pos+4);
                        if(sidLen+8!=size) throw new ObservationFailure("descriptor_ace", "Trailing basic ACE data", null);
                    }
                    else onlyBasic=false;
                    aces.Add(new Dictionary<string,object>{{"type",type},{"flags",flags},{"mask",mask},{"sid",sid},
                        {"basic_allow_or_deny",basic},{"raw_base64",Convert.ToBase64String(Binary.Slice(b,pos,size))}});
                    pos+=size;
                }
            }
            // Reject overlapping component ranges, except owner/group exact shared SID.
            int[] starts={ownerAt,groupAt,aclAt}; int[] lens={ownerLen,groupLen,aclLen};
            for(int i=0;i<3;i++) for(int j=i+1;j<3;j++)
                if(lens[i]>0 && lens[j]>0 && starts[i]<starts[j]+lens[j] && starts[j]<starts[i]+lens[i]
                    && !(i==0 && j==1 && starts[i]==starts[j] && lens[i]==lens[j]))
                    throw new ObservationFailure("descriptor", "Overlapping descriptor components", null);
            return new Dictionary<string,object>{{"owner_sid",owner},{"group_sid",group},{"control",control},
                {"dacl_present",present},{"dacl_null",nullDacl},{"dacl_protected",(control&0x1000)!=0},
                {"dacl_aces",aces},{"only_basic_aces",onlyBasic},{"raw_bytes",b.Length},
                {"raw_sha256",Binary.Hash(b)},{"raw_base64",Convert.ToBase64String(b)},
                {"effective_access_calculated",false},{"acl_policy_accepted",false},{"sacl_observed",false}};
        }
    }

    public interface IFileApi
    {
        string Domain { get; }
        IntPtr Open(string path);
        FileFacts Facts(IntPtr handle);
        byte[] Security(IntPtr handle);
        byte[] Read(IntPtr handle, int count);
        void Rewind(IntPtr handle);
        void Close(IntPtr handle);
    }

    public static class CaptureEngine
    {
        public const int MaxFileBytes=65536;
        // Conservative lexical gate only, NOT parent-chain or local-volume attestation.
        public static void ValidatePath(string path)
        {
            if(path==null || path.Length<4 || path.Length>240 || path[0]<'A' || path[0]>'Z'
                || path[1]!=':' || path[2]!='\\') throw new ObservationFailure("path", "Expected fixed absolute DOS file path", null);
            for(int i=3;i<path.Length;i++)
                if(path[i]<32 || path[i]>126 || "/:\"<>|?*%".IndexOf(path[i])>=0)
                    throw new ObservationFailure("path", "Unsupported path character", null);
            foreach(string part in path.Substring(3).Split('\\'))
            {
                if(part.Length==0 || part=="." || part==".." || part.EndsWith(".") || part.EndsWith(" "))
                    throw new ObservationFailure("path", "Ambiguous path component", null);
                string stem=part.Split('.')[0].ToUpperInvariant();
                if(stem=="CON" || stem=="PRN" || stem=="AUX" || stem=="NUL" || stem=="CONIN$" || stem=="CONOUT$"
                    || (stem.Length==4 && (stem.StartsWith("COM")||stem.StartsWith("LPT")) && stem[3]>='1' && stem[3]<='9'))
                    throw new ObservationFailure("path", "Device component rejected", null);
            }
        }
        private static Dictionary<string,object> Error(string fallback,Exception e)
        {
            ObservationFailure f=e as ObservationFailure;
            return new Dictionary<string,object>{{"stage",f==null?fallback:f.Stage},{"type",e.GetType().FullName},
                {"code",f==null?null:(object)f.NativeCode},{"message",e.Message}};
        }
        private static byte[] ReadExact(IFileApi api,IntPtr h,int size)
        {
            byte[] output=new byte[size]; int at=0;
            while(at<size)
            {
                int request=Math.Min(4096,size-at); byte[] part=api.Read(h,request);
                if(part==null || part.Length==0 || part.Length>request)
                    throw new ObservationFailure("read", "Early EOF or invalid returned length", null);
                Buffer.BlockCopy(part,0,output,at,part.Length); at+=part.Length;
            }
            byte[] eof=api.Read(h,1);
            if(eof==null || eof.Length!=0) throw new ObservationFailure("read", "File grew past expected EOF", null);
            return output;
        }
        public static Dictionary<string,object> Capture(IFileApi api,string path,int maxBytes)
        {
            if(api==null) throw new ArgumentNullException("api");
            IntPtr h=IntPtr.Zero; object primary=null; List<object> cleanup=new List<object>();
            Dictionary<string,object> snapshot=null; bool opened=false,closed=false;
            string stage="validate";
            try
            {
                ValidatePath(path);
                if(maxBytes<0 || maxBytes>MaxFileBytes) throw new ObservationFailure("budget", "Byte budget out of range",null);
                stage="open"; h=api.Open(path);
                if(h==IntPtr.Zero || h==new IntPtr(-1)) { h=IntPtr.Zero; throw new ObservationFailure("open","Invalid returned handle",null); }
                opened=true;
                stage="metadata_before"; FileFacts first=api.Facts(h); first.RequireOrdinaryLeaf(maxBytes);
                stage="descriptor_before"; byte[] sd0=api.Security(h); Dictionary<string,object> descriptor=Descriptor.Decode(sd0);
                stage="read_first"; byte[] bytes=ReadExact(api,h,(int)first.Size);
                stage="rewind"; api.Rewind(h);
                stage="read_second"; byte[] repeated=ReadExact(api,h,(int)first.Size);
                if(!Binary.Equal(bytes,repeated)) throw new ObservationFailure("read_stability","Two byte reads differ",null);
                stage="descriptor_after"; byte[] sd1=api.Security(h); Descriptor.Decode(sd1);
                if(!Binary.Equal(sd0,sd1)) throw new ObservationFailure("descriptor_stability","Two descriptors differ",null);
                stage="metadata_after"; FileFacts last=api.Facts(h); last.RequireOrdinaryLeaf(maxBytes);
                if(!first.Stable(last)) throw new ObservationFailure("metadata_stability","Metadata or object identity changed",null);
                snapshot=new Dictionary<string,object>{{"bytes",bytes.Length},{"sha256",Binary.Hash(bytes)},
                    {"content_base64",Convert.ToBase64String(bytes)},{"descriptor",descriptor},
                    {"before",first.Record()},{"after",last.Record()},{"repeated_bytes_equal",true},
                    {"repeated_descriptor_equal",true},{"last_access_time_compared",false}};
            }
            catch(Exception e) { primary=Error(stage,e); }
            finally
            {
                if(opened)
                {
                    try { api.Close(h); closed=true; }
                    catch(Exception e) { cleanup.Add(Error("close_file_handle",e)); }
                }
            }
            bool ok=primary==null && cleanup.Count==0 && opened && closed;
            return new Dictionary<string,object>{{"kind","SAME_HANDLE_FILE_OBSERVATION_V1"},
                {"status",ok?"OBSERVED_FILE_SNAPSHOT":(cleanup.Count!=0?"CLEANUP_FAILED":"OBSERVATION_FAILED")},
                {"source_domain",api.Domain},{"primary_error",primary},{"cleanup_errors",cleanup},
                {"file_opened",opened},{"explicit_close_succeeded",closed},{"snapshot",ok?snapshot:null},
                {"observation_accepted_as_authority",false},{"parent_chain_verified",false},
                {"live_context_created",false},{"execution_authorized",false},
                {"continuous_immutability_proven",false},{"handle_retained_after_return",false}};
        }
    }

    // Guarded pinned buffers check both fences regardless of native success.
    internal sealed class GuardedBuffer : IDisposable
    {
        private readonly byte[] storage; private GCHandle pinned; public readonly int Capacity;
        public IntPtr Pointer { get { return IntPtr.Add(pinned.AddrOfPinnedObject(),16); } }
        public GuardedBuffer(int size)
        {
            if(size<1 || size>65536) throw new ArgumentOutOfRangeException("size");
            Capacity=size; storage=new byte[size+32];
            for(int i=0;i<storage.Length;i++) storage[i]=0xA5;
            pinned=GCHandle.Alloc(storage,GCHandleType.Pinned);
        }
        public void Check()
        {
            for(int i=0;i<16;i++) if(storage[i]!=0xA5 || storage[16+Capacity+i]!=0xA5)
                throw new ObservationFailure("native_buffer","Buffer fence changed",null);
        }
        public byte[] Take(int count)
        { Check(); if(count<0||count>Capacity) throw new ObservationFailure("native_buffer","Returned count exceeds capacity",null); return Binary.Slice(storage,16,count); }
        public void Dispose() { if(pinned.IsAllocated) pinned.Free(); }
    }

    public sealed class NativeFileApi : IFileApi
    {
        public static int EntryCount;
        public string Domain { get { return "WIN32_FILE_OBSERVATION_NOT_AUTHORITY"; } }
        public const uint Access=0x00120081, Share=1, Disposition=3, Flags=0x00200000;
        private static void Enter() { Interlocked.Increment(ref EntryCount); }
        private static void Check(bool ok,string stage,int code)
        { if(!ok) throw new ObservationFailure(stage,"Win32 returned error "+code.ToString(CultureInfo.InvariantCulture),code); }
        public IntPtr Open(string path)
        {
            if(IntPtr.Size!=8 || Environment.OSVersion.Platform!=PlatformID.Win32NT) throw new PlatformNotSupportedException("Windows x64 only");
            CaptureEngine.ValidatePath(path); Enter(); IntPtr h=CreateFileW(path,Access,Share,IntPtr.Zero,Disposition,Flags,IntPtr.Zero);
            int error=Marshal.GetLastWin32Error();
            if(h==new IntPtr(-1) || h==IntPtr.Zero) throw new ObservationFailure("CreateFileW","Open-existing read-only failed",error);
            return h;
        }
        private byte[] Info(IntPtr h,int cls,int size)
        {
            using(GuardedBuffer b=new GuardedBuffer(size))
            {
                Enter(); bool ok=GetFileInformationByHandleEx(h,cls,b.Pointer,(uint)size); int error=Marshal.GetLastWin32Error();
                b.Check(); Check(ok,"GetFileInformationByHandleEx:"+cls,error); return b.Take(size);
            }
        }
        public FileFacts Facts(IntPtr h)
        {
            Enter(); uint type=GetFileType(h); int error=Marshal.GetLastWin32Error();
            if(type!=1) throw new ObservationFailure("GetFileType","Expected disk file",type==0?(int?)error:null);
            return FileFacts.Decode(type,Info(h,18,24),Info(h,1,24),Info(h,9,8),Info(h,0,40));
        }
        public byte[] Security(IntPtr h)
        {
            uint needed; Enter(); bool ok=GetKernelObjectSecurity(h,7,IntPtr.Zero,0,out needed); int error=Marshal.GetLastWin32Error();
            if(ok || error!=122 || needed<20 || needed>65536)
                throw new ObservationFailure("GetKernelObjectSecurity:size","Unexpected size probe; length="+needed+"; ok="+ok,error);
            using(GuardedBuffer b=new GuardedBuffer((int)needed))
            {
                uint returned; Enter(); ok=GetKernelObjectSecurity(h,7,b.Pointer,needed,out returned); error=Marshal.GetLastWin32Error();
                b.Check(); Check(ok,"GetKernelObjectSecurity:read",error);
                if(returned<20 || returned>needed) throw new ObservationFailure("GetKernelObjectSecurity:length","Invalid returned descriptor size "+returned,null);
                return b.Take((int)returned); // no retry if the descriptor grows or changes
            }
        }
        public byte[] Read(IntPtr h,int count)
        {
            if(count<1 || count>4096) throw new ArgumentOutOfRangeException("count");
            using(GuardedBuffer b=new GuardedBuffer(count))
            {
                uint n; Enter(); bool ok=ReadFile(h,b.Pointer,(uint)count,out n,IntPtr.Zero); int error=Marshal.GetLastWin32Error();
                b.Check(); Check(ok,"ReadFile",error);
                if(n>(uint)count) throw new ObservationFailure("ReadFile:length","Read exceeded requested bytes",null);
                return b.Take((int)n);
            }
        }
        public void Rewind(IntPtr h)
        {
            long pos; Enter(); bool ok=SetFilePointerEx(h,0,out pos,0); int error=Marshal.GetLastWin32Error();
            Check(ok,"SetFilePointerEx",error); if(pos!=0) throw new ObservationFailure("SetFilePointerEx","Cursor not at zero",null);
        }
        public void Close(IntPtr h) { Enter(); bool ok=CloseHandle(h); int error=Marshal.GetLastWin32Error(); Check(ok,"CloseHandle",error); }

        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
        [DllImport("kernel32.dll",EntryPoint="CreateFileW",ExactSpelling=true,CharSet=CharSet.Unicode,SetLastError=true)]
        private static extern IntPtr CreateFileW(string p,uint a,uint s,IntPtr sa,uint d,uint f,IntPtr t);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
        [DllImport("kernel32.dll",EntryPoint="GetFileInformationByHandleEx",ExactSpelling=true,SetLastError=true)]
        [return:MarshalAs(UnmanagedType.Bool)] private static extern bool GetFileInformationByHandleEx(IntPtr h,int c,IntPtr b,uint s);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
        [DllImport("kernel32.dll",EntryPoint="GetFileType",ExactSpelling=true,SetLastError=true)]
        private static extern uint GetFileType(IntPtr h);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
        [DllImport("advapi32.dll",EntryPoint="GetKernelObjectSecurity",ExactSpelling=true,SetLastError=true)]
        [return:MarshalAs(UnmanagedType.Bool)] private static extern bool GetKernelObjectSecurity(IntPtr h,uint i,IntPtr b,uint s,out uint needed);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
        [DllImport("kernel32.dll",EntryPoint="ReadFile",ExactSpelling=true,SetLastError=true)]
        [return:MarshalAs(UnmanagedType.Bool)] private static extern bool ReadFile(IntPtr h,IntPtr b,uint c,out uint n,IntPtr overlapped);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
        [DllImport("kernel32.dll",EntryPoint="SetFilePointerEx",ExactSpelling=true,SetLastError=true)]
        [return:MarshalAs(UnmanagedType.Bool)] private static extern bool SetFilePointerEx(IntPtr h,long d,out long p,uint m);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
        [DllImport("kernel32.dll",EntryPoint="CloseHandle",ExactSpelling=true,SetLastError=true)]
        [return:MarshalAs(UnmanagedType.Bool)] private static extern bool CloseHandle(IntPtr h);
    }
}
