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
}
