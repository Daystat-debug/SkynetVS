// TEST ASSEMBLY ONLY. This class substitutes ServiceNative at compile time.
// The original ServiceEntryPoint.cs and OriginRefusal.cs are linked UNCHANGED.
// No real SCM call, token claim, acceptance issuer, installed path, or runtime dispatch switch.
using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.CompilerServices;
using System.Text.Json;
using SkynetVS.G1.ServiceCallbackHarnessV1;
namespace SkynetVS.G1.GuardStartCandidateV3
{
    internal static unsafe class ServiceNative
    {
        private const nint TestStatusHandle = 0x1357;
        private static readonly List<string> events = new List<string>();
        private static readonly List<string> faults = new List<string>();
        private static readonly List<ServiceStatus> statuses = new List<ServiceStatus>();
        private static readonly List<uint> controls = new List<uint>();
        private static readonly List<uint> controlResults = new List<uint>();
        private static string scenario = "UNSET";
        private static nint serviceCallback, handlerCallback;
        private static int dispatchCalls, registerCalls, serviceCalls, serviceReturns, handlerCalls;
        private static bool reentered, emitted;

        private static void ReadScenario()
        {
            string[] args = Environment.GetCommandLineArgs();
            if (args.Length != 3 || args[1] != "--case")
                throw new InvalidOperationException("HARNESS_REQUIRES_EXACT_CASE");
            scenario = args[2];
            switch (scenario)
            {
                case "SCBH001": case "SCBH002": case "SCBH003": case "SCBH004":
                case "SCBH005": case "SCBH006": case "SCBH007": case "SCBH008":
                case "SCBH009": case "SCBH010": case "SCBH011": case "SCBH012":
                case "SCBH013": case "SCBH014": case "SCBH015": case "SCBH016":
                case "SCBH017": case "SCBH018": return;
                default: throw new InvalidOperationException("HARNESS_UNKNOWN_CASE");
            }
        }

        private static void RecordFault(string code) { faults.Add(code); }
        private static void InvokeService(uint argc, nint argv)
        {
            serviceCalls++;
            events.Add("service_call");
            uint sentinel = CallbackDriver.InvokeServiceMain(serviceCallback, argc, argv);
            if (sentinel != 0x53564331u) RecordFault("NATIVE_SERVICE_RETURN_SENTINEL");
            serviceReturns++;
            events.Add("service_return");
        }
        private static void InvokeControls()
        {
            uint[] codes = { 0, 1, 2, 3, 4, 5, 128, 255, uint.MaxValue };
            foreach (uint code in codes)
            {
                uint observed = uint.MaxValue;
                handlerCalls++;
                uint sentinel = CallbackDriver.InvokeHandler(handlerCallback, code, uint.MaxValue,
                    (nint)1, (nint)(-1), &observed);
                if (sentinel != 0x43544c31u) RecordFault("NATIVE_HANDLER_RETURN_SENTINEL");
                controls.Add(code); controlResults.Add(observed); events.Add("handler_return");
            }
        }

        [MethodImpl(MethodImplOptions.NoInlining)]
        internal static int StartServiceCtrlDispatcherW(ServiceTableEntry* table)
        {
            dispatchCalls++; events.Add("dispatcher_enter");
            try
            {
                ReadScenario();
                if (table == null || table[0].Name == 0 || table[0].ServiceProc == 0)
                    throw new InvalidOperationException("INVALID_TEST_SERVICE_TABLE");
                if (new string((char*)table[0].Name) != "SkynetVSGuard") RecordFault("TABLE_NAME");
                if (table[1].Name != 0 || table[1].ServiceProc != 0) RecordFault("TABLE_SENTINEL");
                serviceCallback = table[0].ServiceProc;
                if (scenario == "SCBH002") { events.Add("dispatcher_false"); return 0; }
                if (scenario == "SCBH003")
                { events.Add("dispatcher_throw"); throw new InvalidOperationException("INJECT_DISPATCHER"); }
                if (scenario == "SCBH016") { events.Add("dispatcher_no_callback"); return 1; }
                InvokeService(scenario == "SCBH015" ? uint.MaxValue : 0u,
                    scenario == "SCBH015" ? (nint)1 : 0);
                if (scenario == "SCBH010" || scenario == "SCBH018") InvokeService(0, 0);
                // Deliberately adversarial post-terminal handler input, not a claimed SCM schedule.
                if (scenario == "SCBH014") InvokeControls();
                if (scenario == "SCBH017") { events.Add("dispatcher_false_after_callback"); return 0; }
                events.Add("dispatcher_true");
                return 1;
            }
            finally { EmitTrace(); }
        }

        [MethodImpl(MethodImplOptions.NoInlining)]
        internal static nint RegisterServiceCtrlHandlerExW(char* name, nint callback, nint context)
        {
            registerCalls++; events.Add("register");
            if (name == null || new string(name) != "SkynetVSGuard") RecordFault("REGISTER_NAME");
            if (callback == 0 || context != 0) RecordFault("REGISTER_CALLBACK_CONTEXT");
            handlerCallback = callback;
            if (scenario == "SCBH004" || scenario == "SCBH018")
            { events.Add("register_zero"); return 0; }
            if (scenario == "SCBH005")
            { events.Add("register_throw"); throw new InvalidOperationException("INJECT_REGISTER"); }
            if (scenario == "SCBH011" && !reentered)
            { reentered = true; events.Add("register_reenter"); InvokeService(uint.MaxValue, (nint)1); }
            return TestStatusHandle;
        }

        [MethodImpl(MethodImplOptions.NoInlining)]
        internal static int SetServiceStatus(nint handle, ServiceStatus* status)
        {
            if (handle != TestStatusHandle) RecordFault("STATUS_HANDLE");
            if (status == null) throw new InvalidOperationException("NULL_STATUS");
            ServiceStatus copy = *status;
            statuses.Add(copy); events.Add(copy.CurrentState == 1 ? "status_stopped" : "status_pending");
            if (copy.CurrentState == 2)
            {
                if (scenario == "SCBH012" && !reentered)
                { reentered = true; events.Add("pending_reenter"); InvokeService(uint.MaxValue, (nint)1); }
                if (scenario == "SCBH013") InvokeControls();
                if (scenario == "SCBH006") { events.Add("pending_false"); return 0; }
                if (scenario == "SCBH007")
                { events.Add("pending_throw"); throw new InvalidOperationException("INJECT_PENDING"); }
            }
            else if (copy.CurrentState == 1)
            {
                if (scenario == "SCBH008") { events.Add("stopped_false"); return 0; }
                if (scenario == "SCBH009")
                { events.Add("stopped_throw"); throw new InvalidOperationException("INJECT_STOPPED"); }
            }
            else RecordFault("UNEXPECTED_SERVICE_STATE");
            return 1;
        }

        private static void EmitTrace()
        {
            if (emitted) return;
            emitted = true;
            // Output only; this is a test observation, not an embedded PASS decision.
            Stream output = Console.OpenStandardOutput();
            using (Utf8JsonWriter w = new Utf8JsonWriter(output))
            {
                w.WriteStartObject();
                w.WriteString("kind", "SERVICE_CALLBACK_HARNESS_TRACE_V1");
                w.WriteString("case", scenario);
                w.WriteNumber("dispatch_calls", dispatchCalls); w.WriteNumber("register_calls", registerCalls);
                w.WriteNumber("service_calls", serviceCalls); w.WriteNumber("service_returns", serviceReturns);
                w.WriteNumber("handler_calls", handlerCalls);
                w.WriteStartArray("events"); foreach (string e in events) w.WriteStringValue(e); w.WriteEndArray();
                w.WriteStartArray("faults"); foreach (string e in faults) w.WriteStringValue(e); w.WriteEndArray();
                w.WriteStartArray("statuses");
                foreach (ServiceStatus s in statuses)
                {
                    w.WriteStartObject(); w.WriteNumber("service_type", s.ServiceType);
                    w.WriteNumber("state", s.CurrentState); w.WriteNumber("controls_accepted", s.ControlsAccepted);
                    w.WriteNumber("win32_exit", s.Win32ExitCode); w.WriteNumber("specific_exit", s.ServiceSpecificExitCode);
                    w.WriteNumber("checkpoint", s.CheckPoint); w.WriteNumber("wait_hint", s.WaitHint); w.WriteEndObject();
                }
                w.WriteEndArray();
                w.WriteStartArray("controls");
                for (int i = 0; i < controls.Count; i++)
                {
                    w.WriteStartObject(); w.WriteNumber("code", controls[i]);
                    w.WriteNumber("result", controlResults[i]); w.WriteEndObject();
                }
                w.WriteEndArray();
                w.WriteBoolean("real_service_native_compiled", false);
                w.WriteBoolean("production_origin_enabled", false);
                w.WriteBoolean("source_callback_bodies_changed", false);
                w.WriteString("scope", "SYNTHETIC_PROVIDER_NATIVE_CALLBACKS_NOT_SCM");
                w.WriteEndObject(); w.Flush();
            }
            output.WriteByte(10); output.Flush();
        }
    }
}
