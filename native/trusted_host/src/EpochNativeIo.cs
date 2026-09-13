// NEW source candidate. Only the managed entrypoint is authorized by this package.
using System;
using System.Runtime.InteropServices;
using System.Threading;
using SkynetVS.G1.SameHandleV1;
using SkynetVS.G1.ParentChainV1;
using SkynetVS.G1.ParentChainNativeAdapterV1;
namespace SkynetVS.G1.P00EpochNativeStoreV1
{
    internal sealed class EpochReadFrame : NtFrame
    {
        internal readonly NtBlock Io, Output, Offset;
        internal readonly int Count;
        private readonly byte[] originalOffset;
        internal EpochReadFrame(long offset,int count)
        {
            if(offset<0||offset>65536||count<1||count>4096)throw new ArgumentOutOfRangeException("offset/count");
            Count=count;
            try {
                Io=NewBlock(16);Output=NewBlock(count);Offset=NewBlock(8);
                Marshal.WriteInt32(Io.Pointer,unchecked((int)0xc0000001));
                Marshal.WriteInt64(Offset.Pointer,offset);originalOffset=Offset.Read();
            }catch{Dispose();throw;}
        }
        internal long Position {get{return Marshal.ReadInt64(Offset.Pointer);}}
        internal int IoStatus {get{return Marshal.ReadInt32(Io.Pointer);}}
        internal ulong Information {get{return unchecked((ulong)Marshal.ReadInt64(Io.Pointer,8));}}
        internal override void Check()
        {
            base.Check();Limits.Need(Binary.Equal(originalOffset,Offset.Read()),"read_input_mutation","Read offset changed");
        }
    }
    internal interface IEpochStoreCalls : INtCalls
    {
        FileFacts Facts(IntPtr h);
        byte[] Security(IntPtr h);
        int Read(IntPtr h,EpochReadFrame frame);
        void Close(IntPtr h);
    }
    internal interface IManagedEpochStoreCalls : IEpochStoreCalls,IManagedNtCalls { }
    internal sealed class WindowsEpochStoreCalls : IEpochStoreCalls
    {
        internal const string NativeDomain="NATIVE_EPOCH_STORE_DIAGNOSTIC_NOT_ENROLLMENT";
        private readonly WindowsNtCalls nt=new WindowsNtCalls();
        private readonly NativeFileApi file=new NativeFileApi();
        internal static int ReadEntries;
        public string Domain {get{return NativeDomain;}}
        private static void Enter()
        {
            NativeProcessGate.Check();
            if(IntPtr.Size!=8||Environment.OSVersion.Platform!=PlatformID.Win32NT)
                throw new PlatformNotSupportedException("Windows x64 diagnostic-child only");
        }
        public int Open(NtOpenFrame f){Enter();return nt.Open(f);}
        public int Device(IntPtr h,NtDeviceFrame f){Enter();return nt.Device(h,f);}
        public FileFacts Facts(IntPtr h){Enter();return file.Facts(h);}
        public byte[] Security(IntPtr h){Enter();return file.Security(h);}
        public void Close(IntPtr h){Enter();file.Close(h);}
        public int Read(IntPtr h,EpochReadFrame f)
        {
            Enter();Interlocked.Increment(ref ReadEntries);
            return NtReadFile(h,IntPtr.Zero,IntPtr.Zero,IntPtr.Zero,f.Io.Pointer,f.Output.Pointer,
                (uint)f.Count,f.Offset.Pointer,IntPtr.Zero);
        }
        // Explicit unmanaged IOSB/output/offset: unexpected pending retains the entire frame.
        // No ReadFile(out count), no overlapped marshaler temporary, no separate seek or dependence on the shared file cursor.
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
        [DllImport("ntdll.dll",EntryPoint="NtReadFile",ExactSpelling=true,SetLastError=false,CallingConvention=CallingConvention.Winapi)]
        private static extern int NtReadFile(IntPtr file,IntPtr evt,IntPtr apc,IntPtr apcContext,
            IntPtr iosb,IntPtr buffer,uint length,IntPtr offset,IntPtr key);
    }
}
