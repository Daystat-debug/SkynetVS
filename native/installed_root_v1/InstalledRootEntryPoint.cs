using System;
using System.Collections.Generic;
using System.Threading;
using SkynetVS.G1.InstallationBootstrapV1;
namespace SkynetVS.G1.InstalledRootCandidateV1
{
    internal static class InstalledRootEntryPoint
    {
        internal static bool AcceptArguments(string[] args)
        { return args!=null&&args.Length==1&&args[0]=="--observe-current-layout"; }
        private static void Emit(object value)
        { byte[] b=CanonicalJson.Encode(value);var output=Console.OpenStandardOutput();output.Write(b,0,b.Length);output.Flush(); }
        public static int Main(string[] args)
        {
            // Diagnostic image only. Not a ServiceMain, no install switch, no path/release argument.
            if(!AcceptArguments(args)){Console.Error.WriteLine("Only --observe-current-layout is supported.");return 2;}
            using(var watchdog=new Timer(delegate { Environment.FailFast("INSTALLED_ROOT_DIAGNOSTIC_WATCHDOG"); },null,12000,Timeout.Infinite)) {
                try {
                    var result=new InstalledRootReadOnly(new WindowsRootCalls(),new RootStopwatch()).Run();
                    result["new_native_api_entries"]=WindowsRootCalls.NewApiEntries;
                    Emit(result);return (string)result["result"]=="ROOT_READ_ERROR"?2:0;
                }
                catch(Exception e){Emit(new Dictionary<string,object>{{"result","ROOT_READ_ERROR"},{"error",e.GetType().Name+":"+e.Message},{"claims",Rules.Claims()}});return 2;}
            }
        }
    }
}
