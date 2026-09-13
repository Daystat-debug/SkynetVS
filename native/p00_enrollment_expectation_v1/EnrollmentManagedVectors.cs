// Test-only literal source authored independently of BridgeFixture and its observed records.
#if P00_ENROLLMENT_MANAGED_TESTS
using System;
using SkynetVS.G1.InstalledRootCandidateV1;
using SkynetVS.G1.P00EpochReadLeaseV1;
namespace SkynetVS.G1.P00EnrollmentExpectationV1
{
    internal sealed class EnrollmentTestClock : IRootClock
    {
        internal long Now = 0;
        internal Action OnRead = null;
        public long Milliseconds { get { if (OnRead != null) OnRead(); return Now; } }
    }
    internal static class EnrollmentManagedVectors
    {
        internal const string AnchorBase64 = "eyJkZWxpdmVyeV9yZXZpZXdfaWQiOiIwMTIzNDU2Nzg5YWJjZGVmMDEyMzQ1Njc4OWFiY2RlZiIsImZvcm1hdF92ZXJzaW9uIjoxLCJnYXRlX2lkZW50aXR5Ijp7ImZpbGVfaWRfMTI4X2hleCI6IjY5MzJhZDE4YWVjZDI4YzY1ODVjNGYyODY5NDYxZmVhIiwidm9sdW1lX3NlcmlhbF9oZXgiOiIwMDAwMDAwMDAwMDAwMDAxIn0sImhvc3RfbWFuaWZlc3RfZGlnZXN0IjoiMTExMTExMTExMTExMTExMTExMTExMTExMTExMTExMTExMTExMTExMTExMTExMTExMTExMTExMTExMTExMTExMSIsImhvc3RfcmVsZWFzZV9pZCI6IjAxMjM0NTY3ODlhYmNkZWYwMTIzNDU2Nzg5YWJjZGVmIiwiaW5pdGlhbF9wb2xpY3lfc2V0X2RpZ2VzdCI6IjMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMiLCJpbnN0YWxsYXRpb25fbmFtZXNwYWNlX2lkIjoiMDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWYiLCJraW5kIjoiUDAwX0lOU1RBTExfQU5DSE9SX1YxIiwibGlmZWN5Y2xlX3Byb3RvY29sX2lkIjoiUDAwX0xJRkVDWUNMRV9GUk9aRU5fVjEiLCJvYnNlcnZlcl9jbG9zdXJlX2RpZ2VzdCI6IjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIiLCJvc19ib3VuZGFyeV9kaWdlc3QiOiI1NTU1NTU1NTU1NTU1NTU1NTU1NTU1NTU1NTU1NTU1NTU1NTU1NTU1NTU1NTU1NTU1NTU1NTU1NTU1NTU1NTU1IiwicmVhZGVyX3NpZCI6IlMtMS01LTgwLTEtMi0zLTQtNSIsInN0YXRlX3N0b3JlX3Nsb3QiOiJQMDBfTElGRUNZQ0xFX1YxX0VOUk9MTEVEX1NMT1QiLCJzdG9yZV9yb290X2lkZW50aXR5Ijp7ImZpbGVfaWRfMTI4X2hleCI6ImVkNTJkZTJjNzA3OWMxZmE3NTYyYWIyODhhYTMzMjdiIiwidm9sdW1lX3NlcmlhbF9oZXgiOiIwMDAwMDAwMDAwMDAwMDAxIn0sInRocmVhdF9tb2RlbF9kaWdlc3QiOiI0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0NDQ0Iiwid3JpdGVyX3NpZHMiOlsiUy0xLTUtMTgiLCJTLTEtNS0zMi01NDQiXX0K";
        internal const string AnchorSha256 = "d9971d246373f03ac0e1b04f65f211c5416536f024cde2c47e6d883c16619d94";
        internal static byte[] Anchor() { return Convert.FromBase64String(AnchorBase64); }
        internal static EpochIdentity Host() { return new EpochIdentity("0000000000000001", "e2a900fbec250b4b97e3907abb3c891e"); }
        internal static EpochIdentity AnchorObject() { return new EpochIdentity("0000000000000001", "4e50cbfe6d94b52801c81b93302ac058"); }
        internal static IndependentEnrollmentSeed Seed()
        { return IndependentEnrollmentSeed.ForManagedTests(Anchor(), AnchorSha256, Host(), AnchorObject()); }
    }
}
#endif
