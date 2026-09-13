using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using SkynetVS.G1.SameHandleV1;
using SkynetVS.G1.ParentChainV1;
using SkynetVS.G1.ParentChainNativeAdapterV1;

namespace SkynetVS.G1.InstalledRootCandidateV1
{
    internal sealed class RootStopwatch : IRootClock
    {
        private readonly Stopwatch watch=Stopwatch.StartNew();
        public long Milliseconds { get { return watch.ElapsedMilliseconds; } }
    }
    internal sealed class WindowsRootCalls : IRootCalls
    {
        private readonly WindowsNtCalls nt=new WindowsNtCalls();
        private readonly NativeFileApi file=new NativeFileApi();
        internal static int NewApiEntries;
        public string Domain { get { return Rules.NativeDomain; } }
        private static void Enter()
        {
            NativeProcessGate.Check();
            Rules.Need(IntPtr.Size==8&&Environment.OSVersion.Platform==PlatformID.Win32NT,"WINDOWS_X64_ONLY");
            Interlocked.Increment(ref NewApiEntries);
        }
        private static string KnownFolder(string id)
        {
            Guid guid=new Guid(id);IntPtr result=IntPtr.Zero;
            try {
                Enter();int hr=SHGetKnownFolderPath(ref guid,0x4000,IntPtr.Zero,out result);
                Rules.Need(hr==0&&result!=IntPtr.Zero,"KNOWN_FOLDER_QUERY_FAILED_"+unchecked((uint)hr).ToString("x8"));
                var text=new StringBuilder();
                for(int i=0;i<=Rules.MaxPath;i++) {
                    char c=(char)Marshal.ReadInt16(result,i*2);
                    if(c=='\0')return text.ToString();text.Append(c);
                }
                throw new RootFailure("KNOWN_FOLDER_PATH_BOUND",false);
            }
            finally { if(result!=IntPtr.Zero)CoTaskMemFree(result); }
        }
        public LocationInput Locations()
        {
            string pf=KnownFolder("6D809377-6AF0-444B-8957-A3773F02200E");
            string pd=KnownFolder("62AB5D82-FDC1-4DC3-A9DD-070D1D495D97");
            var image=new StringBuilder(Rules.MaxPath+1);Enter();
            uint n=GetModuleFileNameW(IntPtr.Zero,image,(uint)image.Capacity);
            Rules.Need(n>0&&n<image.Capacity&&n==image.Length,"CURRENT_IMAGE_QUERY_FAILED_OR_TRUNCATED");
            return new LocationInput(pf,pd,image.ToString());
        }
        public OpenOutcome OpenVolume(string drive)
        {
            Rules.Need(LocalPath.Parse(drive).Parts().Length==0,"EXACT_DRIVE_ROOT_ONLY");
            Enter();Rules.Need(GetDriveTypeW(drive)==3,"LOCAL_FIXED_DRIVE_REQUIRED");
            Enter();IntPtr h=CreateFileW(drive,NativeShape.DirectoryAccess,1,IntPtr.Zero,3,0x02200000,IntPtr.Zero);
            int error=Marshal.GetLastWin32Error();
            if(h==new IntPtr(-1)||h==IntPtr.Zero)throw new ObservationFailure("drive_root_open","Read-only volume open failed",error);
            return new OpenOutcome(h,false); // Publish owned handle; engine registers it before further checks.
        }
        private static RootFailure Unknown(NtFrame frame,string message)
        { frame.Retain();NativeProcessGate.Poison();return new RootFailure(message,true); }
        public OpenOutcome OpenRelative(IntPtr parent,string component,bool directory)
        {
            using(NtOpenFrame f=new NtOpenFrame(parent,component,directory)) {
                int status;try{status=nt.Open(f);}catch{throw Unknown(f,"NATIVE_OPEN_COMPLETION_UNKNOWN");}
                try{f.Check();}catch{throw Unknown(f,"NATIVE_OPEN_FRAME_CHANGED");}
                if(status>0)throw Unknown(f,"NATIVE_OPEN_POSITIVE_OR_PENDING");
                if(status<0){
                    if(f.ResultHandle!=IntPtr.Zero)throw Unknown(f,"FAILED_NATIVE_OPEN_WITH_HANDLE");
                    uint u=unchecked((uint)status);
                    if(u==0xc0000034||u==0xc000003a)return new OpenOutcome(IntPtr.Zero,true);
                    throw new RootFailure("NT_OPEN_ERROR_"+u.ToString("x8"),false);
                }
                if(!Limits.ValidHandle(f.ResultHandle)||f.IoStatus!=0||f.Information!=NativeShape.FileOpened)
                    throw Unknown(f,"NATIVE_OPEN_INVALID_COMPLETION");
                return new OpenOutcome(f.ResultHandle,false);
            }
        }
        public DeviceFacts Device(IntPtr handle)
        {
            using(NtDeviceFrame f=new NtDeviceFrame()) {
                int status;try{status=nt.Device(handle,f);}catch{throw Unknown(f,"DEVICE_COMPLETION_UNKNOWN");}
                try{f.Check();}catch{throw Unknown(f,"DEVICE_FRAME_CHANGED");}
                if(status>0)throw Unknown(f,"DEVICE_POSITIVE_OR_PENDING");
                if(status<0)throw new RootFailure("NT_DEVICE_ERROR_"+unchecked((uint)status).ToString("x8"),false);
                if(f.IoStatus!=0||f.Information!=8)throw Unknown(f,"DEVICE_INVALID_COMPLETION");
                return NativeShape.DecodeDevice(f.Output.Read(),status,f.IoStatus,f.Information);
            }
        }
        public FileFacts Facts(IntPtr h){NativeProcessGate.Check();return file.Facts(h);}
        public byte[] Security(IntPtr h){NativeProcessGate.Check();return file.Security(h);}
        public void Close(IntPtr h){NativeProcessGate.Check();file.Close(h);}

        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
        [DllImport("shell32.dll",ExactSpelling=true)]
        private static extern int SHGetKnownFolderPath(ref Guid id,uint flags,IntPtr token,out IntPtr path);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
        [DllImport("ole32.dll",ExactSpelling=true)] private static extern void CoTaskMemFree(IntPtr pointer);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
        [DllImport("kernel32.dll",ExactSpelling=true,CharSet=CharSet.Unicode,SetLastError=true)]
        private static extern uint GetModuleFileNameW(IntPtr module,StringBuilder path,uint size);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
        [DllImport("kernel32.dll",ExactSpelling=true,CharSet=CharSet.Unicode)]
        private static extern uint GetDriveTypeW(string root);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
        [DllImport("kernel32.dll",ExactSpelling=true,CharSet=CharSet.Unicode,SetLastError=true)]
        private static extern IntPtr CreateFileW(string path,uint access,uint sharing,IntPtr security,uint creation,uint flags,IntPtr template);
    }
}
