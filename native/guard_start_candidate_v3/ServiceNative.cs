// BUILD-ONLY refusal bootstrap; not independently authenticated service startup.
using System;
using System.Runtime.InteropServices;
namespace SkynetVS.G1.GuardStartCandidateV3
{
    [StructLayout(LayoutKind.Explicit, Size = 16)]
    internal struct ServiceTableEntry
    {
        [FieldOffset(0)] internal nint Name;
        [FieldOffset(8)] internal nint ServiceProc;
    }
    [StructLayout(LayoutKind.Explicit, Size = 28)]
    internal struct ServiceStatus
    {
        [FieldOffset(0)] internal uint ServiceType;
        [FieldOffset(4)] internal uint CurrentState;
        [FieldOffset(8)] internal uint ControlsAccepted;
        [FieldOffset(12)] internal uint Win32ExitCode;
        [FieldOffset(16)] internal uint ServiceSpecificExitCode;
        [FieldOffset(20)] internal uint CheckPoint;
        [FieldOffset(24)] internal uint WaitHint;
    }
    internal static unsafe class ServiceNative
    {
        // Raw blittable values: Win32 BOOL is int, DWORD is uint, pointers are nint.
        // No string/delegate marshalling, reflection, or dynamic export discovery.
        [DllImport("advapi32.dll", EntryPoint = "StartServiceCtrlDispatcherW",
            ExactSpelling = true, CallingConvention = CallingConvention.StdCall)]
        internal static extern int StartServiceCtrlDispatcherW(ServiceTableEntry* table);
        [DllImport("advapi32.dll", EntryPoint = "RegisterServiceCtrlHandlerExW",
            ExactSpelling = true, CallingConvention = CallingConvention.StdCall)]
        internal static extern nint RegisterServiceCtrlHandlerExW(char* name, nint callback, nint context);
        [DllImport("advapi32.dll", EntryPoint = "SetServiceStatus",
            ExactSpelling = true, CallingConvention = CallingConvention.StdCall)]
        internal static extern int SetServiceStatus(nint statusHandle, ServiceStatus* status);
    }
}
