// LP01 / message #46: non-deployable source/build candidate only.
// No caller-controlled path, mode, release or expectation input. No service startup.
using System;
using SkynetVS.G1.P00EnrollmentExpectationV1;
[assembly: System.Runtime.Versioning.SupportedOSPlatform("windows")]
namespace SkynetVS.G1.GuardStartCandidateV1
{
    internal static class CandidateEntryPoint
    {
        private static int Main()
        {
            try
            {
                // Use the REAL existing refusing boundary, not a replacement issuer.
                EnrollmentNativeBridgeFactory.OpenInstalled();
                // Even an unexpected return (including null) cannot admit production.
                return 79;
            }
            catch (EnrollmentFailure)
            {
                return 78;
            }
            catch (Exception)
            {
                return 80;
            }
        }
    }
}
