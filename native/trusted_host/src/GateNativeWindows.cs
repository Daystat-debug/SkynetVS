using System;
using System.Collections.Generic;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using SkynetVS.G1.GateLeaseHandoffV1;
using SkynetVS.G1.SameHandleV1;

namespace SkynetVS.G1.GateLeaseHandoffNativeV1
{
    internal static class NativeHealth
    {
        private static int poisoned;
        internal static bool Poisoned { get { return Thread.VolatileRead(ref poisoned)!=0; } }
        internal static void Poison() { Interlocked.Exchange(ref poisoned,1); }
        internal static void Check() { HCheck.Need(!Poisoned,"NATIVE_DOMAIN_TERMINAL_PROCESS_EXIT_REQUIRED"); }
    }
    // Guarded unmanaged storage remains allocated if a call has ambiguous completion.
    internal sealed class NativeBuffer : IDisposable
    {
        private readonly IntPtr allocation;
        internal readonly IntPtr Data;
        internal readonly int Length;
        internal bool Retained;
        private bool disposed;
        internal NativeBuffer(int n)
        {
            HCheck.Need(n>0 && n<=65536,"NATIVE_BUFFER_SIZE");Length=n;
            allocation=Marshal.AllocHGlobal(n+32);Data=IntPtr.Add(allocation,16);
            for(int i=0;i<n+32;i++)Marshal.WriteByte(allocation,i,(byte)(i<16||i>=n+16?0xa5:0));
        }
        internal void Verify()
        {
            for(int i=0;i<16;i++) if(Marshal.ReadByte(allocation,i)!=0xa5 || Marshal.ReadByte(allocation,Length+16+i)!=0xa5)
            { Retained=true;NativeHealth.Poison();throw new HandoffFailure("NATIVE_BUFFER_GUARD_CHANGED"); }
        }
        internal byte[] Bytes(int n)
        { Verify();HCheck.Need(n>=0&&n<=Length,"NATIVE_RETURNED_LENGTH");byte[] b=new byte[n];Marshal.Copy(Data,b,0,n);return b; }
        public void Dispose()
        { if(disposed)return;disposed=true;if(Retained||NativeHealth.Poisoned)return;Verify();Marshal.FreeHGlobal(allocation); }
    }
    [StructLayout(LayoutKind.Sequential)] internal struct NUnicode { internal ushort Length,MaximumLength;internal IntPtr Buffer; }
    [StructLayout(LayoutKind.Sequential)] internal struct NObject
    { internal uint Length;internal IntPtr Root,Name;internal uint Attributes;internal IntPtr Security,Qos; }
    internal sealed class GateOpenResult
    { internal readonly int Status;internal readonly IntPtr Handle;internal GateOpenResult(int status,IntPtr handle){Status=status;Handle=handle;} }
    internal sealed class NativePipePair
    { internal IntPtr Read,Write; }
    internal sealed class NativeClock : IHandoffClock
    { public long Milliseconds { get { ulong n=Win.GetTickCount64();HCheck.Need(n<=(ulong)Int64.MaxValue,"NATIVE_CLOCK_RANGE");return (long)n; } } }
    internal static class Win
    {
        internal static int Entries;
        private static void Entry(){NativeHealth.Check();Interlocked.Increment(ref Entries);}
        internal static void Need(bool ok,string operation)
        { if(!ok)throw new HandoffFailure(operation+"_WIN32_"+Marshal.GetLastWin32Error().ToString(CultureInfo.InvariantCulture)); }
        internal static bool Close(IntPtr h) { Entry();return CloseHandle(h); }
        internal static long Now { get { return new NativeClock().Milliseconds; } }
        internal static ProcessStamp Current() { return Identity(GetCurrentProcess()); }
        internal static ProcessStamp Identity(IntPtr h)
        {
            Entry();uint pid=GetProcessId(h);Need(pid!=0,"GET_PROCESS_ID");
            long creation,exit,kernel,user;Entry();Need(GetProcessTimes(h,out creation,out exit,out kernel,out user),"GET_PROCESS_TIMES");
            HCheck.Need(creation>0,"PROCESS_CREATION_INVALID");return new ProcessStamp(pid,(ulong)creation);
        }
        internal static uint Wait(IntPtr process,uint ms)
        { Entry();uint status=WaitForSingleObject(process,ms);HCheck.Need(status==0||status==258,"PROCESS_WAIT_FAILED");return status; }
        internal static uint ExitCode(IntPtr process)
        { Entry();uint code;Need(GetExitCodeProcess(process,out code),"GET_EXIT_CODE");return code; }
        internal static IntPtr OpenParent(uint pid)
        { Entry();IntPtr h=OpenProcess(0x00101000,false,pid);Need(HCheck.Handle(h),"OPEN_PARENT");return h; }
        internal static uint Resume(IntPtr thread) { Entry();return ResumeThread(thread); }
        internal static bool InJob(IntPtr child,IntPtr job)
        { Entry();bool inside;Need(IsProcessInJob(child,job,out inside),"IS_PROCESS_IN_JOB");return inside; }
        internal static void RequireImage(IntPtr process,string expected)
        {
            StringBuilder text=new StringBuilder(1024);uint n=1024;Entry();Need(QueryFullProcessImageNameW(process,0,text,ref n),"QUERY_CHILD_IMAGE");
            HCheck.Need(n>0&&n<1024&&String.Equals(text.ToString(),expected,StringComparison.OrdinalIgnoreCase),"CHILD_IMAGE_PATH_MISMATCH");
        }
        internal static string WindowsDirectory()
        {StringBuilder s=new StringBuilder(260);Entry();uint n=GetWindowsDirectoryW(s,260);HCheck.Need(n>2&&n<260,"WINDOWS_DIRECTORY");return s.ToString();}
        internal static void SetInheritance(IntPtr h,bool inherit)
        { Entry();Need(SetHandleInformation(h,1,inherit?1u:0u),"SET_INHERITANCE");RequireFlags(h,inherit); }
        internal static void RequireFlags(IntPtr h,bool inherit)
        { Entry();uint flags;Need(GetHandleInformation(h,out flags),"GET_HANDLE_FLAGS");HCheck.Need(flags==(inherit?1u:0u),"HANDLE_FLAGS_MISMATCH"); }
        internal static uint GrantedAccess(IntPtr h)
        {
            using(NativeBuffer b=new NativeBuffer(56))
            {
                uint n;Entry();int status=NtQueryObject(h,0,b.Data,56,out n);b.Verify();
                if(status>0){NativeHealth.Poison();throw new HandoffFailure("OBJECT_QUERY_AMBIGUOUS_STATUS");}
                HCheck.Need(status==0&&n==56,"OBJECT_BASIC_INFORMATION_STATUS_"+unchecked((uint)status).ToString("x8")+"_BYTES_"+n.ToString());return unchecked((uint)Marshal.ReadInt32(b.Data,4));
            }
        }
        internal static PipeEndpointSnapshot ObservePipeEndpoint(IntPtr h)
        {
            Entry();uint flags;Need(GetHandleInformation(h,out flags),"GET_PIPE_FLAGS");
            Entry();uint type=GetFileType(h);
            return new PipeEndpointSnapshot(type,flags,GrantedAccess(h));
        }
        internal static void RequireEndpoint(IntPtr h,bool reader,bool inherit)
        { PipeEndpointRights.RequireExact(ObservePipeEndpoint(h),reader,inherit); }
        internal static PipeDuplicateOutcome DuplicatePipeEndpoint(IntPtr source,uint desired)
        {
            HCheck.Need(HCheck.Handle(source) &&
                (desired==PipeEndpointRights.Reader || desired==PipeEndpointRights.Writer),"PIPE_DUPLICATE_INPUT");
            IntPtr copy=IntPtr.Zero;bool ok;int error;
            try
            {
                Entry();IntPtr current=GetCurrentProcess();
                ok=DuplicateHandle(current,source,current,out copy,desired,false,0);
                error=Marshal.GetLastWin32Error();
            }
            catch { NativeHealth.Poison();throw; }
            bool known=ok?HCheck.Handle(copy):copy==IntPtr.Zero;
            if(!known)NativeHealth.Poison();
            return new PipeDuplicateOutcome(known,ok,copy,error);
        }
        internal static void RequireGateAccess(IntPtr h,bool inherit)
        { RequireFlags(h,inherit);HCheck.Need(GrantedAccess(h)==NativeScope.ReadGate,"READ_ONLY_GATE_ACCESS"); }
        internal static NativePipePair Pipe()
        {
            NativePipePair pair=new NativePipePair();Entry();bool ok=CreatePipe(out pair.Read,out pair.Write,IntPtr.Zero,4096);
            if(!ok){if(pair.Read!=IntPtr.Zero||pair.Write!=IntPtr.Zero)NativeHealth.Poison();Need(false,"CREATE_PIPE");}
            if(!HCheck.Handle(pair.Read)||!HCheck.Handle(pair.Write)||pair.Read==pair.Write){NativeHealth.Poison();throw new HandoffFailure("PIPE_OUTPUT_SHAPE");}return pair;
        }
        internal static IntPtr OpenDirectory(string path)
        {
            Entry();IntPtr h=CreateFileW(path,0x00120081,1,IntPtr.Zero,3,0x02200000,IntPtr.Zero);
            Need(HCheck.Handle(h),"OPEN_FIXTURE_DIRECTORY");return h;
        }
        internal static void RequireDirectory(IntPtr h)
        {
            NativeFileApi api=new NativeFileApi();FileFacts first=api.Facts(h),last=api.Facts(h);
            HCheck.Need(first.FileType==1 && first.Directory && (first.Attributes&0x10)!=0 &&
                (first.Attributes&0x441400)==0 && first.ReparseTag==0 && !first.DeletePending && first.Stable(last),"FIXTURE_DIRECTORY_SHAPE_OR_DRIFT");
        }
        internal static GateOpenResult OpenGate(IntPtr root,bool exclusive)
        {
            HCheck.Need(HCheck.Handle(root)&&Marshal.SizeOf(typeof(NObject))==48&&Marshal.SizeOf(typeof(NUnicode))==16,"NT_OPEN_ABI");
            byte[] name=Encoding.Unicode.GetBytes("Lifecycle.gate\0");
            using(NativeBuffer text=new NativeBuffer(name.Length))using(NativeBuffer unicode=new NativeBuffer(16))
            using(NativeBuffer attributes=new NativeBuffer(48))using(NativeBuffer iosb=new NativeBuffer(16))using(NativeBuffer output=new NativeBuffer(8))
            {
                Marshal.Copy(name,0,text.Data,name.Length);
                NUnicode u=new NUnicode();u.Length=(ushort)(name.Length-2);u.MaximumLength=(ushort)name.Length;u.Buffer=text.Data;
                Marshal.StructureToPtr(u,unicode.Data,false);
                NObject o=new NObject();o.Length=48;o.Root=root;o.Name=unicode.Data;o.Attributes=0x1040;
                Marshal.StructureToPtr(o,attributes.Data,false);
                int status;
                try { Entry();status=NtCreateFile(output.Data,exclusive?NativeScope.ExclusiveGate:NativeScope.ReadGate,
                    attributes.Data,iosb.Data,IntPtr.Zero,0,exclusive?0u:1u,1,0x60,IntPtr.Zero,0); }
                catch { NativeHealth.Poison();throw; }
                text.Verify();unicode.Verify();attributes.Verify();iosb.Verify();output.Verify();
                IntPtr h=Marshal.ReadIntPtr(output.Data);
                if(status>0 || (status<0&&h!=IntPtr.Zero)) { NativeHealth.Poison();throw new HandoffFailure("NT_OPEN_AMBIGUOUS_COMPLETION"); }
                if(status==0)
                {
                    if(!HCheck.Handle(h)||Marshal.ReadInt32(iosb.Data)!=0||Marshal.ReadInt64(iosb.Data,8)!=1)
                    {NativeHealth.Poison();throw new HandoffFailure("NT_OPEN_OUTPUT_INVALID");}
                }
                return new GateOpenResult(status,h);
            }
        }
        internal static GateStamp ObserveGate(IntPtr h) { NativeHealth.Check();return NativeGateCopyPrimitive.ObserveTransferred(h); }
        internal static IntPtr HoldImage(string path)
        { Entry();IntPtr h=CreateFileW(path,0x00120081,1,IntPtr.Zero,3,0x00200000,IntPtr.Zero);Need(HCheck.Handle(h),"OPEN_CHILD_IMAGE");return h; }
        internal static void RequireImageBytes(IntPtr handle,string expectedHash)
        {
            HCheck.Hex(expectedHash,64,"IMAGE_HASH");NativeFileApi api=new NativeFileApi();FileFacts before=api.Facts(handle);before.RequireOrdinaryLeaf(2097152);
            HCheck.Need(before.Size>0,"EMPTY_CHILD_IMAGE");List<byte> bytes=new List<byte>();WindowsPipeCalls io=new WindowsPipeCalls();
            while(bytes.Count<before.Size){byte[] part=io.Read(handle,(int)Math.Min(4096,before.Size-bytes.Count));HCheck.Need(part.Length>0,"IMAGE_EOF");bytes.AddRange(part);}
            FileFacts after=api.Facts(handle);HCheck.Need(before.Stable(after)&&Binary.Hash(bytes.ToArray())==expectedHash,"CHILD_IMAGE_BYTES_CHANGED");
        }
        internal static IntPtr CreateContainedJob()
        {
            Entry();IntPtr job=CreateJobObjectW(IntPtr.Zero,null);Need(HCheck.Handle(job),"CREATE_JOB");
            try
            {
                using(NativeBuffer b=new NativeBuffer(144))
                {
                    // JOBOBJECT_EXTENDED_LIMIT_INFORMATION x64: Basic.LimitFlags @16, ActiveProcessLimit @40.
                    Marshal.WriteInt32(b.Data,16,0x2008);Marshal.WriteInt32(b.Data,40,1);
                    Entry();Need(SetInformationJobObject(job,9,b.Data,144),"SET_KILL_ON_CLOSE_JOB");b.Verify();
                }
                RequireFlags(job,false);return job;
            }
            catch { if(!NativeHealth.Poisoned && !Close(job))NativeHealth.Poison();throw; }
        }
        // These two termination methods are allowed even in poisoned state. They never imply success.
        internal static bool EmergencyStopJob(IntPtr job)
        {Interlocked.Increment(ref Entries);return TerminateJobObject(job,234);}
        internal static bool EmergencyWait(IntPtr process,uint milliseconds)
        {Interlocked.Increment(ref Entries);return WaitForSingleObject(process,milliseconds)==0;}
        internal static void EmergencyExit()
        {TerminateProcess(GetCurrentProcess(),235);Environment.FailFast("GATE_HANDOFF_TERMINAL");}

        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)] [DllImport("kernel32.dll",ExactSpelling=true)] internal static extern ulong GetTickCount64();
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)] [DllImport("kernel32.dll",ExactSpelling=true)] private static extern IntPtr GetCurrentProcess();
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)] [DllImport("kernel32.dll",ExactSpelling=true,SetLastError=true)] private static extern uint GetProcessId(IntPtr h);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)] [DllImport("kernel32.dll",ExactSpelling=true,SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] private static extern bool GetProcessTimes(IntPtr h,out long c,out long e,out long k,out long u);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)] [DllImport("kernel32.dll",ExactSpelling=true,SetLastError=true)] private static extern IntPtr OpenProcess(uint access,[MarshalAs(UnmanagedType.Bool)]bool inherit,uint pid);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)] [DllImport("kernel32.dll",ExactSpelling=true,SetLastError=true)] internal static extern uint WaitForSingleObject(IntPtr h,uint milliseconds);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)] [DllImport("kernel32.dll",ExactSpelling=true,SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] private static extern bool GetExitCodeProcess(IntPtr h,out uint code);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)] [DllImport("kernel32.dll",ExactSpelling=true,SetLastError=true)] private static extern uint ResumeThread(IntPtr h);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)] [DllImport("kernel32.dll",ExactSpelling=true,SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] private static extern bool IsProcessInJob(IntPtr p,IntPtr j,[MarshalAs(UnmanagedType.Bool)]out bool inside);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)] [DllImport("kernel32.dll",ExactSpelling=true,CharSet=CharSet.Unicode,SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] private static extern bool QueryFullProcessImageNameW(IntPtr p,uint flags,StringBuilder text,ref uint size);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)] [DllImport("kernel32.dll",ExactSpelling=true,CharSet=CharSet.Unicode)] private static extern uint GetWindowsDirectoryW(StringBuilder text,uint length);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)] [DllImport("kernel32.dll",ExactSpelling=true,SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] private static extern bool GetHandleInformation(IntPtr h,out uint flags);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)] [DllImport("kernel32.dll",ExactSpelling=true,SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] private static extern bool SetHandleInformation(IntPtr h,uint mask,uint flags);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)] [DllImport("kernel32.dll",ExactSpelling=true,SetLastError=true)] private static extern uint GetFileType(IntPtr h);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)] [DllImport("kernel32.dll",ExactSpelling=true,SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] private static extern bool CreatePipe(out IntPtr read,out IntPtr write,IntPtr sa,uint bytes);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)] [DllImport("kernel32.dll",ExactSpelling=true,SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] private static extern bool DuplicateHandle(IntPtr sourceProcess,IntPtr source,IntPtr targetProcess,out IntPtr target,uint access,[MarshalAs(UnmanagedType.Bool)]bool inherit,uint options);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)] [DllImport("kernel32.dll",ExactSpelling=true,CharSet=CharSet.Unicode,SetLastError=true)] private static extern IntPtr CreateFileW(string path,uint access,uint share,IntPtr sa,uint disposition,uint flags,IntPtr template);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)] [DllImport("kernel32.dll",ExactSpelling=true,SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] private static extern bool CloseHandle(IntPtr h);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)] [DllImport("ntdll.dll",ExactSpelling=true)] private static extern int NtCreateFile(IntPtr output,uint access,IntPtr attributes,IntPtr iosb,IntPtr allocation,uint fileAttributes,uint share,uint disposition,uint options,IntPtr ea,uint eaLength);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)] [DllImport("ntdll.dll",ExactSpelling=true)] private static extern int NtQueryObject(IntPtr h,int info,IntPtr data,uint length,out uint returned);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)] [DllImport("kernel32.dll",ExactSpelling=true,CharSet=CharSet.Unicode,SetLastError=true)] private static extern IntPtr CreateJobObjectW(IntPtr sa,string name);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)] [DllImport("kernel32.dll",ExactSpelling=true,SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] private static extern bool SetInformationJobObject(IntPtr job,int info,IntPtr data,uint length);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)] [DllImport("kernel32.dll",ExactSpelling=true,SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] private static extern bool TerminateJobObject(IntPtr job,uint code);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)] [DllImport("kernel32.dll",ExactSpelling=true,SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] private static extern bool TerminateProcess(IntPtr process,uint code);
    }

    internal sealed class WindowsPipeCalls : IPipeCalls
    {
        public int Available(IntPtr h)
        {
            NativeHealth.Check();uint read,available,left;Interlocked.Increment(ref Win.Entries);
            bool ok=PeekNamedPipe(h,IntPtr.Zero,0,out read,out available,out left);int error=Marshal.GetLastWin32Error();
            if(!ok&&error==109)return -1;Win.Need(ok,"PEEK_PIPE");HCheck.Need(available<=65536,"PIPE_BUFFER_OVERSIZE");return (int)available;
        }
        public byte[] Read(IntPtr h,int count)
        {
            HCheck.Need(count>0&&count<=4096,"READ_REQUEST_LIMIT");
            using(NativeBuffer b=new NativeBuffer(count))using(NativeBuffer n=new NativeBuffer(4))
            {
                NativeHealth.Check();Interlocked.Increment(ref Win.Entries);bool ok=ReadFile(h,b.Data,(uint)count,n.Data,IntPtr.Zero);int error=Marshal.GetLastWin32Error();
                if(!ok&&error==997){NativeHealth.Poison();throw new HandoffFailure("SYNCHRONOUS_READ_PENDING");}
                b.Verify();n.Verify();Win.Need(ok,"READ_PIPE_OR_IMAGE");uint got=unchecked((uint)Marshal.ReadInt32(n.Data));
                HCheck.Need(got<=(uint)count,"READ_RETURN_LENGTH");return b.Bytes((int)got);
            }
        }
        public int Write(IntPtr h,byte[] bytes,int offset,int count)
        {
            HCheck.Need(bytes!=null&&count>0&&count<=512&&offset>=0&&offset<=bytes.Length-count,"WRITE_FRAME_BOUNDS");
            Win.RequireEndpoint(h,false,false); // This function can never write a disk gate or image.
            using(NativeBuffer b=new NativeBuffer(count))using(NativeBuffer n=new NativeBuffer(4))
            {
                Marshal.Copy(bytes,offset,b.Data,count);NativeHealth.Check();Interlocked.Increment(ref Win.Entries);
                bool ok=WriteFile(h,b.Data,(uint)count,n.Data,IntPtr.Zero);int error=Marshal.GetLastWin32Error();
                if(!ok&&error==997){NativeHealth.Poison();throw new HandoffFailure("SYNCHRONOUS_WRITE_PENDING");}
                b.Verify();n.Verify();Win.Need(ok,"WRITE_PIPE");uint wrote=unchecked((uint)Marshal.ReadInt32(n.Data));
                HCheck.Need(wrote<=(uint)count,"WRITE_RETURN_LENGTH");return (int)wrote;
            }
        }
        public void Pause(){Thread.Sleep(1);}
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)] [DllImport("kernel32.dll",ExactSpelling=true,SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] private static extern bool PeekNamedPipe(IntPtr h,IntPtr data,uint size,out uint read,out uint available,out uint left);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)] [DllImport("kernel32.dll",ExactSpelling=true,SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] private static extern bool ReadFile(IntPtr h,IntPtr data,uint count,IntPtr read,IntPtr overlapped);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)] [DllImport("kernel32.dll",ExactSpelling=true,SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] private static extern bool WriteFile(IntPtr h,IntPtr data,uint count,IntPtr written,IntPtr overlapped);
    }

    // Owns a separate held parent handle. No dependency on the main thread making progress.
    internal sealed class ParentDeadlineWatchdog
    {
        private readonly IntPtr parent;
        private readonly long hardDeadline;
        private readonly ManualResetEvent stop=new ManualResetEvent(false);
        private readonly Thread thread;
        private bool finished;
        internal ParentDeadlineWatchdog(ProcessStamp expected,long deadline)
        {
            parent=Win.OpenParent(expected.Pid);
            try
            {
                HCheck.Need(expected.Same(Win.Identity(parent)) && Win.Wait(parent,0)==258,"WATCHDOG_PARENT_IDENTITY");
                hardDeadline=checked(deadline+2000);thread=new Thread(Loop);thread.IsBackground=true;thread.Start();
            }
            catch{if(!Win.Close(parent))NativeHealth.Poison();throw;}
        }
        private void Loop()
        {
            try
            {
                while(!stop.WaitOne(20))
                    if(NativeHealth.Poisoned || Win.Now>=hardDeadline || Win.WaitForSingleObject(parent,0)!=258)Win.EmergencyExit();
            }
            catch{Win.EmergencyExit();}
        }
        internal void Finish()
        {
            HCheck.Need(!finished,"WATCHDOG_FINISH_ONCE");finished=true;stop.Set();
            if(!thread.Join(1000))Win.EmergencyExit();
            HCheck.Need(Win.Close(parent),"WATCHDOG_PARENT_CLOSE");stop.Dispose();
        }
    }
}
