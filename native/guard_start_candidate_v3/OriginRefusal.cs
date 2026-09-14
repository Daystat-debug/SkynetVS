// Exact refusing types extracted from the pinned enrollment baseline; no seed/session/bridge.
using System;
namespace SkynetVS.G1.P00EnrollmentExpectationV1
{
    internal sealed class EnrollmentFailure : Exception
    {
        internal EnrollmentFailure(string code) : base(code) { }
    }

    internal static class EnrollmentNativeBridgeFactory
    {
        // Parameterless by design. No caller vector, path, SID, bool approval, JSON or callback can mint an origin.
        [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
        internal static object OpenInstalled()
        { throw new EnrollmentFailure("NATIVE_ENROLLMENT_AND_PREENTRY_TRUSTED_START_NOT_DELIVERED"); }
        internal static object ImportDiagnostic(object ignored)
        { throw new EnrollmentFailure("DETACHED_DATA_CANNOT_ISSUE_ENROLLMENT_EXPECTATION"); }
    }
}
