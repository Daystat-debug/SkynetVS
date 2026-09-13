using System;
using System.Collections.Generic;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using SkynetVS.G1.SameHandleV1;

namespace SkynetVS.G1.GateLeaseHandoffV1
{
    [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)]
    internal struct HStartupInfo
    {
        internal uint cb; internal IntPtr reserved, desktop, title;
        internal uint x, y, xSize, ySize, xChars, yChars, fill, flags;
        internal ushort show, reservedBytes;
        internal IntPtr reserved2, stdin, stdout, stderr;
    }
    [StructLayout(LayoutKind.Sequential)]
    internal struct HStartupInfoEx { internal HStartupInfo Info; internal IntPtr Attributes; }
    [StructLayout(LayoutKind.Sequential)]
    internal struct HProcessInfo { internal IntPtr Process, Thread; internal uint Pid, Tid; }

    // Request carries NO production authorization. Future owner must verify this exact executable closure
    // and hold all input handles for the call. Native start remains unreachable from the managed-only CLI.
    internal sealed class RestrictedLaunchRequest
    {
        internal readonly RestrictedInheritancePlan Plan;
        internal readonly HandoffPin Pin;
        internal readonly string Application, Directory, EnvironmentBlock;
        internal RestrictedLaunchRequest(RestrictedInheritancePlan plan, HandoffPin pin, string directory, string windows)
        {
            HCheck.Need(plan != null && pin != null, "LAUNCH_REQUEST");
            CheckDirectory(directory); CheckDirectory(windows);
            Plan = plan; Pin = pin; Directory = directory;
            Application = directory + "\\GateLeaseHandoffChild.exe";
            HCheck.Need(Application.Length <= 240, "APPLICATION_LENGTH");
            EnvironmentBlock = "PATH=" + windows + "\\System32\0SystemRoot=" + windows + "\0TEMP=" + directory
                + "\0TMP=" + directory + "\0WINDIR=" + windows + "\0\0";
        }
        private static void CheckDirectory(string value)
        {
            HCheck.Need(value != null && value.Length >= 3 && value.Length <= 208
                && value[0] >= 'A' && value[0] <= 'Z' && value[1] == ':' && value[2] == '\\'
                && !value.EndsWith("\\", StringComparison.Ordinal), "LOCAL_DIRECTORY_FORMAT");
            foreach (char c in value) HCheck.Need(c >= 32 && c <= 126 && "\"<>|?*%/".IndexOf(c) < 0, "DIRECTORY_CHARACTER");
            string[] parts = value.Substring(3).Split('\\');
            foreach (string part in parts) HCheck.Need(part.Length > 0 && part != "." && part != ".."
                && !part.EndsWith(".", StringComparison.Ordinal) && !part.EndsWith(" ", StringComparison.Ordinal)
                && part.IndexOf(':') < 0, "DIRECTORY_COMPONENT");
        }
        internal string CommandLine()
        {
            // No caller arguments, shell, registry path or grant. Handles are child-local inherited values.
            return "\"" + Application + "\" --gate-lease-receiver " + Pin.Run + " " + Pin.Nonce + " "
                + Pin.Parent.Pid.ToString(CultureInfo.InvariantCulture) + " " + Pin.Parent.Creation.ToString(CultureInfo.InvariantCulture)
                + " " + Plan.GateCopy.ToInt64().ToString(CultureInfo.InvariantCulture)
                + " " + Plan.ControlRead.ToInt64().ToString(CultureInfo.InvariantCulture)
                + " " + Plan.ReportWrite.ToInt64().ToString(CultureInfo.InvariantCulture)
                + " " + Pin.Gate.FileId + " " + Pin.Gate.Volume + " " + Pin.Gate.DescriptorHash
                + " " + Pin.StartedMs.ToString(CultureInfo.InvariantCulture) + " " + Pin.DeadlineMs.ToString(CultureInfo.InvariantCulture)
                + " GATE_HANDOFF_DIAGNOSTIC_ONLY_V1";
        }
    }
    internal interface IRestrictedLaunchApi
    {
        string Domain { get; }
        bool GetFlags(IntPtr handle, out uint flags, out int error);
        bool Initialize(IntPtr list, ref UIntPtr size, out int error);
        bool Update(IntPtr list, UIntPtr attribute, IntPtr handles, UIntPtr bytes, out int error);
        bool Create(RestrictedLaunchRequest request, ref HStartupInfoEx startup, out HProcessInfo process, out int error);
        void Delete(IntPtr list);
    }
    internal interface IFakeRestrictedLaunchApi : IRestrictedLaunchApi { }
    internal sealed class NativeLaunchOutcome
    {
        internal HProcessInfo Process;
        internal bool Created, UnknownCompletion, AttributesRetained;
        internal int Error;
        internal string Failure, CleanupFailure;
        // Non-null only on ambiguous provider behavior. Do NOT free/reuse these until owner process exits.
        internal LaunchStorage Retained;
    }
    internal sealed class LaunchStorage
    {
        internal readonly IntPtr Attributes, Handles;
        internal bool Initialized, Retained;
        internal LaunchStorage(int length, RestrictedInheritancePlan plan)
        {
            Attributes = Marshal.AllocHGlobal(length);
            try { Handles = Marshal.AllocHGlobal(IntPtr.Size * 3); }
            catch { Marshal.FreeHGlobal(Attributes); throw; }
            for (int i = 0; i < length; i++) Marshal.WriteByte(Attributes, i, 0);
            IntPtr[] slots = plan.ExportForNativeCall();
            for (int i = 0; i < slots.Length; i++) Marshal.WriteIntPtr(Handles, i * IntPtr.Size, slots[i]);
        }
        internal void VerifyHandles(RestrictedInheritancePlan plan)
        { IntPtr[] expected = plan.ExportForNativeCall(); for (int i=0;i<3;i++) HCheck.Need(Marshal.ReadIntPtr(Handles, i*8)==expected[i], "HANDLE_LIST_BUFFER_CHANGED"); }
        internal void FreeKnown(IRestrictedLaunchApi api)
        {
            if (Retained) return;
            if (Initialized) api.Delete(Attributes);
            Marshal.FreeHGlobal(Handles); Marshal.FreeHGlobal(Attributes);
        }
        internal void DiscardForFakeTestOnly(IFakeRestrictedLaunchApi api)
        {
            HCheck.Need(api != null && api.Domain == RestrictedChildLauncher.FakeDomain, "FAKE_FRAME_CLEANUP_ONLY");
            // Test harness owns synthetic memory only; never a production recovery/unpoison interface.
            Marshal.FreeHGlobal(Handles); Marshal.FreeHGlobal(Attributes);
        }
    }
    internal sealed class RestrictedChildLauncher
    {
        internal const string FakeDomain = "SYNTHETIC_STARTUPINFOEX_ONLY";
        private readonly IRestrictedLaunchApi api;
        private readonly bool native;
        private bool used;
        private readonly int thread = Thread.CurrentThread.ManagedThreadId;
        private RestrictedChildLauncher(IRestrictedLaunchApi provider, bool real)
        { api = provider; native = real; }
        internal static RestrictedChildLauncher ForTests(IFakeRestrictedLaunchApi api)
        { HCheck.Need(api != null && api.Domain == FakeDomain, "FAKE_START_PROVIDER"); return new RestrictedChildLauncher(api, false); }
        internal static RestrictedChildLauncher ForNativeSourceOnly()
        { return new RestrictedChildLauncher(new WindowsRestrictedLaunchApi(), true); }
        private void Origin()
        {
            HCheck.Need(api.Domain == (native ? WindowsRestrictedLaunchApi.NativeDomain : FakeDomain), "START_PROVIDER_ORIGIN");
            if (native) HCheck.Need(IntPtr.Size == 8 && Environment.OSVersion.Platform == PlatformID.Win32NT, "WINDOWS_X64_ONLY");
        }
        internal NativeLaunchOutcome StartSuspended(RestrictedLaunchRequest request)
        {
            HCheck.Need(Thread.CurrentThread.ManagedThreadId == thread && !used && request != null, "START_ONCE_OWNED_THREAD");
            used = true; Origin();
            HCheck.Need(IntPtr.Size == 8 && Marshal.SizeOf(typeof(HStartupInfo)) == 104
                && Marshal.SizeOf(typeof(HStartupInfoEx)) == 112 && Marshal.SizeOf(typeof(HProcessInfo)) == 24, "X64_ABI_LAYOUT");
            var result = new NativeLaunchOutcome(); LaunchStorage frame = null; bool callInProgress = false;
            try
            {
                foreach (IntPtr h in request.Plan.ExportForNativeCall())
                {
                    uint flags; int error;
                    Origin(); callInProgress = true; bool ok = api.GetFlags(h, out flags, out error); callInProgress = false; Origin();
                    HCheck.Need(ok && (flags & 1u) == 1 && (flags & ~3u) == 0 && (flags & 2u) == 0, "EXACT_INHERITABLE_INPUTS_REQUIRED");
                }
                UIntPtr size = UIntPtr.Zero; int firstError;
                callInProgress = true; bool first = api.Initialize(IntPtr.Zero, ref size, out firstError); callInProgress = false; Origin();
                HCheck.Need(!first && firstError == 122 && size.ToUInt64() > 0 && size.ToUInt64() <= 65536, "ATTRIBUTE_SIZE_PROBE");
                ulong allocation = size.ToUInt64(); frame = new LaunchStorage(checked((int)allocation), request.Plan);
                int errorCode;
                callInProgress = true; bool initialized = api.Initialize(frame.Attributes, ref size, out errorCode); callInProgress = false;
                if (initialized) frame.Initialized = true; // retain known initialization before further validation
                Origin(); HCheck.Need(initialized && size.ToUInt64() <= allocation, "ATTRIBUTE_INIT");
                callInProgress = true;
                bool updated = api.Update(frame.Attributes, new UIntPtr(RestrictedInheritancePlan.HandleListAttribute), frame.Handles,
                    new UIntPtr(24), out errorCode); callInProgress = false; Origin(); HCheck.Need(updated, "ATTRIBUTE_HANDLE_LIST");
                frame.VerifyHandles(request.Plan);
                var startup = new HStartupInfoEx(); startup.Info.cb = 112; startup.Attributes = frame.Attributes;
                HProcessInfo pi;
                callInProgress = true; bool created = api.Create(request, ref startup, out pi, out errorCode); callInProgress = false;
                result.Process = pi; result.Error = errorCode; result.Created = created; // publish handles BEFORE checks
                Origin(); frame.VerifyHandles(request.Plan);
                if (!created)
                {
                    if (pi.Process != IntPtr.Zero || pi.Thread != IntPtr.Zero || pi.Pid != 0 || pi.Tid != 0)
                        throw new HandoffFailure("FAILED_CREATE_RETURNED_RESOURCES");
                    result.Failure = "CREATE_FAILED_NO_FALLBACK"; return result;
                }
                HCheck.Need(HCheck.Handle(pi.Process) && HCheck.Handle(pi.Thread) && pi.Process != pi.Thread
                    && pi.Pid != 0 && pi.Tid != 0 && pi.Pid != request.Pin.Parent.Pid, "CREATED_PROCESS_SHAPE");
                return result; // deliberately NOT resumed; caller must bind PID+creation on held process first
            }
            catch (Exception error)
            {
                result.Failure = error.Message;
                result.UnknownCompletion = callInProgress || result.Created || result.Process.Process != IntPtr.Zero
                    || result.Process.Thread != IntPtr.Zero || api.Domain != (native ? WindowsRestrictedLaunchApi.NativeDomain : FakeDomain);
                if (result.UnknownCompletion && frame != null) { frame.Retained = true; result.Retained = frame; result.AttributesRetained = true; }
                return result;
            }
            finally
            {
                if (frame != null && !frame.Retained)
                {
                    try { frame.FreeKnown(api); }
                    catch (Exception error) { frame.Retained = true; result.Retained = frame; result.AttributesRetained = true;
                        result.UnknownCompletion = true; result.CleanupFailure = error.Message; if (result.Failure == null) result.Failure = "ATTRIBUTE_CLEANUP"; }
                }
            }
        }
    }
    internal sealed class WindowsRestrictedLaunchApi : IRestrictedLaunchApi
    {
        internal const string NativeDomain = "NATIVE_RESTRICTED_START_PRIMITIVE_NOT_ENROLLMENT";
        internal static int Entries;
        public string Domain { get { return NativeDomain; } }
        public bool GetFlags(IntPtr h, out uint flags, out int error)
        { Interlocked.Increment(ref Entries); bool ok = GetHandleInformation(h, out flags); error = Marshal.GetLastWin32Error(); return ok; }
        public bool Initialize(IntPtr p, ref UIntPtr size, out int error)
        { Interlocked.Increment(ref Entries); bool ok = InitializeProcThreadAttributeList(p, 1, 0, ref size); error = Marshal.GetLastWin32Error(); return ok; }
        public bool Update(IntPtr p, UIntPtr key, IntPtr value, UIntPtr bytes, out int error)
        { Interlocked.Increment(ref Entries); bool ok = UpdateProcThreadAttribute(p, 0, key, value, bytes, IntPtr.Zero, IntPtr.Zero); error = Marshal.GetLastWin32Error(); return ok; }
        public bool Create(RestrictedLaunchRequest r, ref HStartupInfoEx s, out HProcessInfo pi, out int error)
        {
            IntPtr env = Marshal.StringToHGlobalUni(r.EnvironmentBlock);
            try
            {
                Interlocked.Increment(ref Entries);
                bool ok = CreateProcessW(r.Application, new StringBuilder(r.CommandLine()), IntPtr.Zero, IntPtr.Zero,
                    true, RestrictedInheritancePlan.Flags | 0x400u, env, r.Directory, ref s, out pi);
                error = Marshal.GetLastWin32Error(); return ok;
            }
            finally { Marshal.FreeHGlobal(env); } // synchronous CreateProcess call, no async environment access contract
        }
        public void Delete(IntPtr p) { Interlocked.Increment(ref Entries); DeleteProcThreadAttributeList(p); }
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
        [DllImport("kernel32.dll",ExactSpelling=true,SetLastError=true)]
        [return:MarshalAs(UnmanagedType.Bool)] private static extern bool GetHandleInformation(IntPtr h,out uint flags);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
        [DllImport("kernel32.dll",ExactSpelling=true,SetLastError=true)]
        [return:MarshalAs(UnmanagedType.Bool)] private static extern bool InitializeProcThreadAttributeList(IntPtr p,int count,uint flags,ref UIntPtr size);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
        [DllImport("kernel32.dll",ExactSpelling=true,SetLastError=true)]
        [return:MarshalAs(UnmanagedType.Bool)] private static extern bool UpdateProcThreadAttribute(IntPtr p,uint flags,UIntPtr key,IntPtr value,UIntPtr bytes,IntPtr previous,IntPtr returned);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
        [DllImport("kernel32.dll",ExactSpelling=true)] private static extern void DeleteProcThreadAttributeList(IntPtr p);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
        [DllImport("kernel32.dll",ExactSpelling=true,CharSet=CharSet.Unicode,SetLastError=true)]
        [return:MarshalAs(UnmanagedType.Bool)] private static extern bool CreateProcessW(string app,StringBuilder command,IntPtr processAttributes,
            IntPtr threadAttributes,[MarshalAs(UnmanagedType.Bool)]bool inherit,uint flags,IntPtr environment,string directory,
            ref HStartupInfoEx startup,out HProcessInfo process);
    }
    internal interface IReadGateDuplicateApi
    {
        bool Duplicate(IntPtr original, uint access, bool inherit, uint options, out IntPtr copy, out int error);
    }
    internal interface IFakeReadGateDuplicateApi : IReadGateDuplicateApi { }
    internal sealed class GateDuplicateOutcome
    {
        internal IntPtr Copy;
        internal bool Success, CompletionUnknown;
        internal int Error;
    }
    internal static class NativeGateCopyPrimitive
    {
        internal static GateDuplicateOutcome ForTests(IFakeReadGateDuplicateApi api, IntPtr original)
        { HCheck.Need(api != null, "FAKE_DUPLICATE_REQUIRED"); return CopyCore(api, original); }
        internal static GateDuplicateOutcome CreateInheritableReadCopy(IntPtr original)
        {
            HCheck.Need(IntPtr.Size == 8 && Environment.OSVersion.Platform == PlatformID.Win32NT, "WINDOWS_X64_ONLY");
            return CopyCore(new WindowsReadGateDuplicateApi(), original);
        }
        private static GateDuplicateOutcome CopyCore(IReadGateDuplicateApi api, IntPtr original)
        {
            HCheck.Need(HCheck.Handle(original), "NATIVE_GATE_COPY_INPUT");
            var result = new GateDuplicateOutcome();
            try
            {
                IntPtr copy; int error;
                bool ok = api.Duplicate(original, RestrictedInheritancePlan.GateAccess, true, 0, out copy, out error);
                result.Copy = copy; result.Error = error;
                result.Success = ok && HCheck.Handle(copy) && copy != original;
                result.CompletionUnknown = ok ? !result.Success : copy != IntPtr.Zero;
            }
            catch { result.CompletionUnknown = true; }
            // Caller can always see an acquired copy, even when validation failed. No CLOSE_SOURCE option.
            return result;
        }
        internal static GateStamp ObserveTransferred(IntPtr handle)
        {
            HCheck.Need(IntPtr.Size == 8 && Environment.OSVersion.Platform == PlatformID.Win32NT && HCheck.Handle(handle), "NATIVE_GATE_OBSERVE_INPUT");
            var api = new NativeFileApi(); FileFacts first = api.Facts(handle); first.RequireOrdinaryLeaf(0);
            byte[] a = api.Security(handle), b = api.Security(handle); FileFacts last = api.Facts(handle); last.RequireOrdinaryLeaf(0);
            HCheck.Need(first.Stable(last) && Binary.Equal(a,b), "TRANSFERRED_GATE_DRIFT");
            return new GateStamp(Binary.Hex(first.Id), first.Volume.ToString("x16", CultureInfo.InvariantCulture), Binary.Hash(a));
        }
    }
    internal sealed class WindowsReadGateDuplicateApi : IReadGateDuplicateApi
    {
        internal static int Entries;
        public bool Duplicate(IntPtr original, uint access, bool inherit, uint options, out IntPtr copy, out int error)
        {
            IntPtr self = GetCurrentProcess(); Interlocked.Increment(ref Entries);
            bool ok = DuplicateHandle(self, original, self, out copy, access, inherit, options);
            error = Marshal.GetLastWin32Error(); return ok;
        }
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
        [DllImport("kernel32.dll",ExactSpelling=true)] private static extern IntPtr GetCurrentProcess();
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)]
        [DllImport("kernel32.dll",ExactSpelling=true,SetLastError=true)]
        [return:MarshalAs(UnmanagedType.Bool)] private static extern bool DuplicateHandle(IntPtr sourceProcess,IntPtr source,IntPtr targetProcess,
            out IntPtr target,uint access,[MarshalAs(UnmanagedType.Bool)]bool inherit,uint options);
    }
}
