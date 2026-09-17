// Test-only static object imports. No advapi32 service API binding is compiled.
using System.Runtime.InteropServices;
namespace SkynetVS.G1.ServiceCallbackHarnessV1
{
    internal static unsafe class CallbackDriver
    {
        [DllImport("__Internal", EntryPoint = "ScbhInvokeServiceMain", ExactSpelling = true,
            CallingConvention = CallingConvention.Cdecl)]
        internal static extern uint InvokeServiceMain(nint callback, uint argc, nint argv);
        [DllImport("__Internal", EntryPoint = "ScbhInvokeHandler", ExactSpelling = true,
            CallingConvention = CallingConvention.Cdecl)]
        internal static extern uint InvokeHandler(nint callback, uint control, uint eventType,
            nint eventData, nint context, uint* output);
    }
}
