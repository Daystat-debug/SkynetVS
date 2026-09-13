using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using SkynetVS.G1.SameHandleV1;
using SkynetVS.G1.ParentChainV1;

namespace SkynetVS.G1.ParentChainNativeAdapterV1
{
    // These frames never use ref/out managed storage for potentially pending NT I/O.
    // Quarantined HGlobal allocations have NO finalizer. They survive GC until process
    // exit. Fake tests alone can explicitly free a frame after simulating completion.
    internal sealed class NtBlock : IDisposable
    {
        private IntPtr allocation;
        private bool retained;
        internal readonly int Length;
        internal static int OutstandingBlocks;
        internal IntPtr Pointer { get { return IntPtr.Add(allocation,16); } }
        internal bool IsRetained { get { return retained; } }
        internal NtBlock(int length)
        {
            if(length<1 || length>4096) throw new ArgumentOutOfRangeException("length");
            Length=length;
            byte[] initial=new byte[length+32];
            for(int i=0;i<16;i++) { initial[i]=0xa5;initial[16+length+i]=0xa5; }
            allocation=Marshal.AllocHGlobal(initial.Length);
            try { Marshal.Copy(initial,0,allocation,initial.Length); }
            catch { Marshal.FreeHGlobal(allocation);allocation=IntPtr.Zero;throw; }
            Interlocked.Increment(ref OutstandingBlocks);
        }
        internal void Check()
        {
            Limits.Need(allocation!=IntPtr.Zero,"nt_buffer","Disposed NT buffer");
            for(int i=0;i<16;i++)
                Limits.Need(Marshal.ReadByte(allocation,i)==0xa5 && Marshal.ReadByte(allocation,16+Length+i)==0xa5,
                    "nt_buffer","NT buffer guard changed");
        }
        internal byte[] Read()
        { Check();byte[] b=new byte[Length];Marshal.Copy(Pointer,b,0,Length);return b; }
        internal void Put(byte[] b)
        { Limits.Need(b!=null && b.Length==Length,"nt_buffer","Exact input length required");Marshal.Copy(b,0,Pointer,b.Length); }
        internal void Retain() { retained=true; }
        internal void FreeCompletedFakeOnly(IManagedNtCalls fake)
        { if(fake==null)throw new ArgumentNullException("fake");retained=false;Dispose(); }
        public void Dispose()
        {
            if(!retained && allocation!=IntPtr.Zero)
            { Marshal.FreeHGlobal(allocation);allocation=IntPtr.Zero;Interlocked.Decrement(ref OutstandingBlocks); }
        }
    }

    internal abstract class NtFrame : IDisposable
    {
        protected readonly List<NtBlock> blocks=new List<NtBlock>(5);
        internal bool Retained { get; private set; }
        internal int Bytes { get { int n=0;foreach(NtBlock b in blocks)n+=b.Length+32;return n; } }
        protected NtBlock NewBlock(int n) { NtBlock b=new NtBlock(n);blocks.Add(b);return b; }
        internal virtual void Check() { foreach(NtBlock b in blocks)b.Check(); }
        internal void Retain()
        { Retained=true;foreach(NtBlock b in blocks)b.Retain(); }
        internal void FreeCompletedFakeOnly(IManagedNtCalls fake)
        { foreach(NtBlock b in blocks)b.FreeCompletedFakeOnly(fake);Retained=false; }
        public void Dispose() { for(int i=blocks.Count-1;i>=0;i--)blocks[i].Dispose(); }
    }

    internal sealed class NtOpenFrame : NtFrame
    {
        internal readonly NtBlock Handle, Io, Name, Unicode, Attributes;
        internal readonly bool Directory;
        internal readonly uint Access, Options;
        private readonly byte[] originalName, originalUnicode, originalAttributes;
        internal NtOpenFrame(IntPtr parent,string component,bool directory)
        {
            Limits.Need(IntPtr.Size==8 && Limits.ValidHandle(parent),"nt_open_input","x64 retained parent required");
            Limits.Component(component);
            Directory=directory;Access=directory?NativeShape.DirectoryAccess:NativeShape.LeafAccess;
            Options=directory?NativeShape.DirectoryOptions:NativeShape.LeafOptions;
            try
            {
                Handle=NewBlock(8);Io=NewBlock(16);
                // Do not accidentally accept an uninitialised IO_STATUS_BLOCK as success.
                Marshal.WriteInt32(Io.Pointer,unchecked((int)0xc0000001));
                originalName=Encoding.Unicode.GetBytes(component+"\0");Name=NewBlock(originalName.Length);Name.Put(originalName);
                Unicode=NewBlock(16);Attributes=NewBlock(48);
                NativeShape.UnicodeString us=new NativeShape.UnicodeString {
                    Length=(ushort)(originalName.Length-2),MaximumLength=(ushort)originalName.Length,Buffer=Name.Pointer };
                Marshal.StructureToPtr(us,Unicode.Pointer,false);
                NativeShape.ObjectAttributes oa=new NativeShape.ObjectAttributes {
                    Length=48,RootDirectory=parent,ObjectName=Unicode.Pointer,Attributes=NativeShape.ObjDontReparse,
                    SecurityDescriptor=IntPtr.Zero,SecurityQualityOfService=IntPtr.Zero };
                Marshal.StructureToPtr(oa,Attributes.Pointer,false);
                originalUnicode=Unicode.Read();originalAttributes=Attributes.Read();
            }
            catch { Dispose();throw; }
        }
        internal IntPtr ResultHandle { get { return Marshal.ReadIntPtr(Handle.Pointer); } }
        internal int IoStatus { get { return Marshal.ReadInt32(Io.Pointer); } }
        internal ulong Information { get { return unchecked((ulong)Marshal.ReadInt64(Io.Pointer,8)); } }
        internal override void Check()
        {
            base.Check();
            Limits.Need(Binary.Equal(originalName,Name.Read()) && Binary.Equal(originalUnicode,Unicode.Read())
                && Binary.Equal(originalAttributes,Attributes.Read()),"nt_input_mutation","Read-only NT input changed");
        }
    }
    internal sealed class NtDeviceFrame : NtFrame
    {
        internal readonly NtBlock Io, Output;
        internal NtDeviceFrame()
        {
            try { Io=NewBlock(16);Output=NewBlock(8);Marshal.WriteInt32(Io.Pointer,unchecked((int)0xc0000001)); }
            catch { Dispose();throw; }
        }
        internal int IoStatus { get { return Marshal.ReadInt32(Io.Pointer); } }
        internal ulong Information { get { return unchecked((ulong)Marshal.ReadInt64(Io.Pointer,8)); } }
    }

    internal interface INtCalls
    {
        string Domain { get; }
        int Open(NtOpenFrame frame);
        int Device(IntPtr handle,NtDeviceFrame frame);
    }
    // Marker for tests with no queued OS I/O. The real transport NEVER implements it.
    internal interface IManagedNtCalls : INtCalls { }

    internal static class NativeProcessGate
    {
        private static int poisoned;
        internal static void Poison() { Interlocked.Exchange(ref poisoned,1); }
        internal static void Check()
        { Limits.Need(Interlocked.CompareExchange(ref poisoned,0,0)==0,"native_process_poisoned","Diagnostic process exit required; no further native operations"); }
    }

    internal sealed class WindowsNtCalls : INtCalls
    {
        internal const string NativeDomain="NT_CHAIN_OBSERVATION_NOT_AUTHORITY";
        internal static int EntryCount;
        public string Domain { get { return NativeDomain; } }
        private static void Enter()
        {
            NativeProcessGate.Check();
            if(IntPtr.Size!=8 || Environment.OSVersion.Platform!=PlatformID.Win32NT)
                throw new PlatformNotSupportedException("Windows x64 only");
            Interlocked.Increment(ref EntryCount);
        }
        public int Open(NtOpenFrame f)
        {
            Enter();
            return NtCreateFile(f.Handle.Pointer,f.Access,f.Attributes.Pointer,f.Io.Pointer,
                IntPtr.Zero,0,NativeShape.ShareRead,NativeShape.FileOpen,f.Options,IntPtr.Zero,0);
        }
        public int Device(IntPtr handle,NtDeviceFrame f)
        { Enter();return NtQueryVolumeInformationFile(handle,f.Io.Pointer,f.Output.Pointer,8,NativeShape.FileFsDeviceInformation); }

        // IntPtr output storage is deliberate: no temporary P/Invoke marshaler buffer
        // or stack IO_STATUS_BLOCK may be freed if an unexpected STATUS_PENDING occurs.
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
        [DllImport("ntdll.dll",EntryPoint="NtCreateFile",ExactSpelling=true,SetLastError=false,CallingConvention=CallingConvention.Winapi)]
        private static extern int NtCreateFile(IntPtr resultHandle,uint access,IntPtr attributes,IntPtr iosb,
            IntPtr allocation,uint fileAttributes,uint share,uint disposition,uint options,IntPtr ea,uint eaLength);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
        [DllImport("ntdll.dll",EntryPoint="NtQueryVolumeInformationFile",ExactSpelling=true,SetLastError=false,CallingConvention=CallingConvention.Winapi)]
        private static extern int NtQueryVolumeInformationFile(IntPtr handle,IntPtr iosb,IntPtr output,uint length,int informationClass);
    }
}
