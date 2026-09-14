// LP01; source/build-only. DO NOT install or run this candidate.
// It is a service-shaped REFUSAL path, not a working Guard or a trust issuer.
using System;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;
using System.Threading;
using SkynetVS.G1.P00EnrollmentExpectationV1;
[assembly: System.Runtime.Versioning.SupportedOSPlatform("windows")]
namespace SkynetVS.G1.GuardStartCandidateV3
{
    internal static unsafe class ServiceEntryPoint
    {
        private const string ServiceName = "SkynetVSGuard";
        private const int MissingOrigin = 78, UnexpectedOriginReturn = 79, BootstrapFailure = 80;
        private const int DispatcherRefused = 81, RegistrationRefused = 82, StatusRefused = 83;
        private const uint OwnProcess = 0x10, StartPending = 2, Stopped = 1;
        private const uint ErrorServiceSpecific = 1066, Interrogate = 4, ErrorCallNotImplemented = 120;
        private static int dispatcherEntered, serviceEntered;
        private static int processResult = BootstrapFailure;

        [MethodImpl(MethodImplOptions.NoInlining)]
        private static int Main()
        {
            if (Interlocked.Exchange(ref dispatcherEntered, 1) != 0) return BootstrapFailure;
            try
            {
                // Not a runtime trust check: this is only an ABI guard for the candidate.
                if (IntPtr.Size != 8 || sizeof(ServiceTableEntry) != 16 || sizeof(ServiceStatus) != 28)
                    return BootstrapFailure;
                fixed (char* name = ServiceName)
                {
                    ServiceTableEntry* table = stackalloc ServiceTableEntry[2];
                    table[0] = new ServiceTableEntry {
                        Name = (nint)name,
                        ServiceProc = (nint)(delegate* unmanaged[Stdcall]<uint, nint, void>)&ServiceMain
                    };
                    table[1] = default;
                    // One attempt, no console fallback. The pinned name/table live until return.
                    if (ServiceNative.StartServiceCtrlDispatcherW(table) == 0) return DispatcherRefused;
                }
                return Volatile.Read(ref processResult); // Always nonzero; never an admission.
            }
            catch (Exception) { return BootstrapFailure; }
        }

        [UnmanagedCallersOnly(CallConvs = new[] { typeof(CallConvStdcall) })]
        [MethodImpl(MethodImplOptions.NoInlining)]
        private static void ServiceMain(uint argc, nint argv)
        {
            // Service arguments are deliberately not read and cannot supply an origin.
            // No managed exception may escape this callback during ordinary failure handling.
            try { RunRefusingStart(); }
            catch (Exception) { Volatile.Write(ref processResult, BootstrapFailure); }
        }

        [UnmanagedCallersOnly(CallConvs = new[] { typeof(CallConvStdcall) })]
        [MethodImpl(MethodImplOptions.NoInlining)]
        private static uint Handler(uint control, uint eventType, nint eventData, nint context)
        {
            // Pending startup accepts no controls. Interrogate does not republish status.
            // Never dereference caller data; never stop/free work on the dispatcher thread.
            return control == Interrogate ? 0u : ErrorCallNotImplemented;
        }

        [MethodImpl(MethodImplOptions.NoInlining)]
        private static void RunRefusingStart()
        {
            if (Interlocked.Exchange(ref serviceEntered, 1) != 0) return;
            nint statusHandle = 0;
            int failure = BootstrapFailure;
            try
            {
                fixed (char* name = ServiceName)
                {
                    statusHandle = ServiceNative.RegisterServiceCtrlHandlerExW(name,
                        (nint)(delegate* unmanaged[Stdcall]<uint, uint, nint, nint, uint>)&Handler, 0);
                }
                if (statusHandle == 0) { failure = RegistrationRefused; return; }
                ServiceStatus pending = new ServiceStatus {
                    ServiceType = OwnProcess, CurrentState = StartPending, ControlsAccepted = 0,
                    Win32ExitCode = 0, ServiceSpecificExitCode = 0, CheckPoint = 1, WaitHint = 1000
                };
                if (ServiceNative.SetServiceStatus(statusHandle, &pending) == 0)
                    failure = StatusRefused;
                else
                    failure = RefuseMissingOrigin();
            }
            catch (Exception) { failure = BootstrapFailure; }
            finally
            {
                Volatile.Write(ref processResult, failure);
                if (statusHandle != 0)
                {
                    // No work handles/workers were created. This is the sole STOPPED attempt.
                    // SERVICE_STATUS_HANDLE is not a kernel CloseHandle-owned handle.
                    ServiceStatus stopped = new ServiceStatus {
                        ServiceType = OwnProcess, CurrentState = Stopped, ControlsAccepted = 0,
                        Win32ExitCode = ErrorServiceSpecific, ServiceSpecificExitCode = (uint)failure,
                        CheckPoint = 0, WaitHint = 0
                    };
                    // Do not retry STOPPED even if its completion fails or throws.
                    // All bookkeeping precedes this terminal call; no later native work.
                    try { _ = ServiceNative.SetServiceStatus(statusHandle, &stopped); }
                    catch (Exception) { }
                }
            }
        }

        [MethodImpl(MethodImplOptions.NoInlining)]
        private static int RefuseMissingOrigin()
        {
            try
            {
                EnrollmentNativeBridgeFactory.OpenInstalled();
                return UnexpectedOriginReturn;
            }
            catch (EnrollmentFailure) { return MissingOrigin; }
            catch (Exception) { return BootstrapFailure; }
        }
    }
}
