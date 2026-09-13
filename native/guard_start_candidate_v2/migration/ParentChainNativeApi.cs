using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
using SkynetVS.G1.SameHandleV1;

namespace SkynetVS.G1.ParentChainV1
{
    // Native ABI/specification seam only. There is deliberately NO native invocation
    // path in this delivery. A native adapter must be delivered/reviewed separately,
    // including success-with-postvalidation-error ownership and STATUS_PENDING lifetime.
    // Declaring an import and measuring a layout is NOT native behavior verification.
    internal static class NativeShape
    {
        internal const uint ObjDontReparse=0x1000, FileOpen=1, FileOpened=1, ShareRead=1;
        internal const uint DirectoryAccess=0x001200a0, LeafAccess=0x00120081;
        internal const uint DirectoryOptions=0x21, LeafOptions=0x60;
        internal const int FileFsDeviceInformation=4;

        [StructLayout(LayoutKind.Sequential)]
        internal struct UnicodeString
        { internal ushort Length, MaximumLength; internal IntPtr Buffer; }
        [StructLayout(LayoutKind.Sequential)]
        internal struct ObjectAttributes
        {
            internal uint Length;
            internal IntPtr RootDirectory, ObjectName;
            internal uint Attributes;
            internal IntPtr SecurityDescriptor, SecurityQualityOfService;
        }
        [StructLayout(LayoutKind.Explicit, Size=16)]
        internal struct IoStatusBlock
        {
            [FieldOffset(0)] internal int Status;
            [FieldOffset(0)] internal IntPtr Pointer;
            [FieldOffset(8)] internal UIntPtr Information;
        }
        internal static Dictionary<string,object> Layout()
        {
            Limits.Need(IntPtr.Size==8,"native_abi","Only x64 layout is described");
            return new Dictionary<string,object> {
                {"UNICODE_STRING.size",Marshal.SizeOf<UnicodeString>()},
                {"UNICODE_STRING.Buffer",Marshal.OffsetOf(typeof(UnicodeString),"Buffer").ToInt32()},
                {"OBJECT_ATTRIBUTES.size",Marshal.SizeOf<ObjectAttributes>()},
                {"OBJECT_ATTRIBUTES.RootDirectory",Marshal.OffsetOf(typeof(ObjectAttributes),"RootDirectory").ToInt32()},
                {"OBJECT_ATTRIBUTES.ObjectName",Marshal.OffsetOf(typeof(ObjectAttributes),"ObjectName").ToInt32()},
                {"OBJECT_ATTRIBUTES.Attributes",Marshal.OffsetOf(typeof(ObjectAttributes),"Attributes").ToInt32()},
                {"OBJECT_ATTRIBUTES.SecurityDescriptor",Marshal.OffsetOf(typeof(ObjectAttributes),"SecurityDescriptor").ToInt32()},
                {"OBJECT_ATTRIBUTES.SecurityQualityOfService",Marshal.OffsetOf(typeof(ObjectAttributes),"SecurityQualityOfService").ToInt32()},
                {"IO_STATUS_BLOCK.size",Marshal.SizeOf<IoStatusBlock>()},
                {"IO_STATUS_BLOCK.Information",Marshal.OffsetOf(typeof(IoStatusBlock),"Information").ToInt32()}
            };
        }
        internal static Dictionary<string,object> RelativePlan(IntPtr parent,string component,bool directory)
        {
            Limits.Need(Limits.ValidHandle(parent),"parent","A retained directory parent is required");
            Limits.Component(component);
            byte[] utf16=Encoding.Unicode.GetBytes(component+"\0");
            return new Dictionary<string,object> { {"parent_handle_for_test_only",parent.ToInt64()},
                {"name_bytes",utf16}, {"unicode_length",utf16.Length-2}, {"unicode_maximum_length",utf16.Length},
                {"object_attributes",ObjDontReparse}, {"desired_access",directory?DirectoryAccess:LeafAccess},
                {"create_options",directory?DirectoryOptions:LeafOptions}, {"share_access",ShareRead},
                {"create_disposition",FileOpen}, {"allocation_size_pointer",0}, {"ea_length",0},
                {"security_descriptor_pointer",0}, {"security_qos_pointer",0}, {"native_call_made",false} };
        }
        internal static void ValidateOpenCompletion(int callStatus,int ioStatus,ulong information)
        {
            // Pure decoder only. In a future invoker, pending buffers may NOT be freed
            // merely because this decoder throws. That lifetime is not implemented here.
            Limits.Need(callStatus==0,"ntstatus","Only exact synchronous STATUS_SUCCESS is supported");
            Limits.Need(ioStatus==0 && information==FileOpened,"nt_completion","Expected completed FILE_OPENED");
        }
        internal static DeviceFacts DecodeDevice(byte[] b,int callStatus,int ioStatus,ulong information)
        {
            Limits.Need(callStatus==0 && ioStatus==0,"ntstatus","Volume query did not complete successfully");
            Limits.Need(b!=null && b.Length==8 && information==8,"nt_length","FILE_FS_DEVICE_INFORMATION must be exactly 8 bytes");
            return new DeviceFacts(Binary.U32(b,0),Binary.U32(b,4));
        }
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
        [DllImport("ntdll.dll",EntryPoint="NtCreateFile",ExactSpelling=true,SetLastError=false)]
        private static extern int NtCreateFile(out IntPtr handle,uint access,ref ObjectAttributes attributes,
            out IoStatusBlock status,IntPtr allocation,uint fileAttributes,uint sharing,uint disposition,
            uint options,IntPtr ea,uint eaLength);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
        [DllImport("ntdll.dll",EntryPoint="NtQueryVolumeInformationFile",ExactSpelling=true,SetLastError=false)]
        private static extern int NtQueryVolumeInformationFile(IntPtr handle,out IoStatusBlock status,
            IntPtr output,uint length,int informationClass);
    }
    internal sealed class NativeChainApi : IChainApi
    {
        // Refusal is unconditional; no environment variable, command-line flag or
        // public "verified" record can enable it. It does not implement IManagedFixtureApi.
        private static ObservationFailure Disabled()
        { return new ObservationFailure("native_adapter_not_delivered","SOURCE_MANAGED_ONLY: native adapter and root admission are not available",null); }
        public string Domain { get { return "NATIVE_CHAIN_UNAVAILABLE"; } }
        public IntPtr OpenRelative(IntPtr parent,string component,bool directory) { throw Disabled(); }
        public FileFacts Facts(IntPtr h) { throw Disabled(); }
        public DeviceFacts Device(IntPtr h) { throw Disabled(); }
        public byte[] Security(IntPtr h) { throw Disabled(); }
        public byte[] Read(IntPtr h,int count) { throw Disabled(); }
        public void Rewind(IntPtr h) { throw Disabled(); }
        public void Close(IntPtr h) { throw Disabled(); }
    }
}
