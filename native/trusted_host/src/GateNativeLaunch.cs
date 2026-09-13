using System;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using SkynetVS.G1.GateLeaseHandoffV1;

namespace SkynetVS.G1.GateLeaseHandoffNativeV1
{
    internal static class ContainedGateLaunch
    {
        internal const ulong JobListAttribute=0x0002000d;
        internal const int AttributeCount=2;
        internal static void FillVectors(RestrictedInheritancePlan plan, IntPtr job, NativeBuffer handles, NativeBuffer jobs)
        {
            HCheck.Need(plan!=null && HCheck.Handle(job) && handles!=null && jobs!=null && handles.Length==24 && jobs.Length==8,"ATTRIBUTE_VECTOR_SHAPE");
            IntPtr[] list=plan.ExportForNativeCall();
            for(int i=0;i<3;i++){HCheck.Need(list[i]!=job,"JOB_NOT_IN_INHERITED_LIST");Marshal.WriteIntPtr(handles.Data,i*8,list[i]);}
            Marshal.WriteIntPtr(jobs.Data,job);handles.Verify();jobs.Verify();
        }
        // The job is assigned by CreateProcess itself, before the suspended child can exist outside it.
        // No post-create AssignProcessToJobObject and no broad-inheritance fallback.
        internal static NativeLaunchOutcome Start(RestrictedLaunchRequest request,IntPtr job)
        {
            HCheck.Need(request!=null&&HCheck.Handle(job)&&IntPtr.Size==8,"CONTAINED_LAUNCH_INPUT");
            HCheck.Need(Marshal.SizeOf(typeof(HStartupInfo))==104&&Marshal.SizeOf(typeof(HStartupInfoEx))==112&&
                Marshal.SizeOf(typeof(HProcessInfo))==24,"CONTAINED_LAUNCH_ABI");
            foreach(IntPtr h in request.Plan.ExportForNativeCall()){HCheck.Need(h!=job,"JOB_NOT_IN_HANDLE_LIST");Win.RequireFlags(h,true);}
            Win.RequireFlags(job,false);
            UIntPtr size=UIntPtr.Zero;NativeHealth.Check();Interlocked.Increment(ref Win.Entries);
            bool sizing=InitializeProcThreadAttributeList(IntPtr.Zero,AttributeCount,0,ref size);int error=Marshal.GetLastWin32Error();
            HCheck.Need(!sizing&&error==122&&size.ToUInt64()>0&&size.ToUInt64()<=65536,"TWO_ATTRIBUTE_SIZE");
            NativeLaunchOutcome result=new NativeLaunchOutcome();
            using(NativeBuffer list=new NativeBuffer((int)size.ToUInt64()))using(NativeBuffer handles=new NativeBuffer(24))
            using(NativeBuffer jobs=new NativeBuffer(8))
            {
                bool initialized=false,inCall=false;
                try
                {
                    IntPtr[] allowed=request.Plan.ExportForNativeCall();FillVectors(request.Plan,job,handles,jobs);
                    Interlocked.Increment(ref Win.Entries);inCall=true;initialized=InitializeProcThreadAttributeList(list.Data,AttributeCount,0,ref size);inCall=false;
                    Win.Need(initialized,"INITIALIZE_TWO_ATTRIBUTES");HCheck.Need(size.ToUInt64()<=(ulong)list.Length,"ATTRIBUTE_RESIZE");
                    Interlocked.Increment(ref Win.Entries);inCall=true;
                    bool ok=UpdateProcThreadAttribute(list.Data,0,new UIntPtr(RestrictedInheritancePlan.HandleListAttribute),handles.Data,new UIntPtr(24),IntPtr.Zero,IntPtr.Zero);inCall=false;Win.Need(ok,"SET_HANDLE_LIST");
                    Interlocked.Increment(ref Win.Entries);inCall=true;
                    ok=UpdateProcThreadAttribute(list.Data,0,new UIntPtr(JobListAttribute),jobs.Data,new UIntPtr(8),IntPtr.Zero,IntPtr.Zero);inCall=false;Win.Need(ok,"SET_JOB_LIST");
                    HStartupInfoEx startup=new HStartupInfoEx();startup.Info.cb=112;startup.Attributes=list.Data;
                    IntPtr env=Marshal.StringToHGlobalUni(request.EnvironmentBlock);
                    try
                    {
                        HProcessInfo process;NativeHealth.Check();Interlocked.Increment(ref Win.Entries);inCall=true;
                        bool created=CreateProcessW(request.Application,new StringBuilder(request.CommandLine()),IntPtr.Zero,IntPtr.Zero,true,
                            RestrictedInheritancePlan.Flags|0x400u,env,request.Directory,ref startup,out process);
                        int last=Marshal.GetLastWin32Error();inCall=false;
                        result.Process=process;result.Created=created;result.Error=last; // ownership before checks
                        if(!created)
                        {
                            if(process.Process!=IntPtr.Zero||process.Thread!=IntPtr.Zero||process.Pid!=0||process.Tid!=0)
                                throw new HandoffFailure("FAILED_CREATE_RETURNED_PROCESS_RESOURCES");
                            result.Failure="CONTAINED_CREATE_FAILED_"+last.ToString();
                        }
                        else HCheck.Need(HCheck.Handle(process.Process)&&HCheck.Handle(process.Thread)&&process.Process!=process.Thread&&process.Pid!=0&&process.Tid!=0,
                            "CREATED_PROCESS_OUTPUT_SHAPE");
                        list.Verify();handles.Verify();jobs.Verify();
                        for(int i=0;i<3;i++)HCheck.Need(Marshal.ReadIntPtr(handles.Data,i*8)==allowed[i],"CREATE_CHANGED_HANDLE_LIST");
                        HCheck.Need(Marshal.ReadIntPtr(jobs.Data)==job&&startup.Info.cb==112&&startup.Attributes==list.Data,"CREATE_CHANGED_ATTRIBUTE_INPUT");
                    }
                    finally{if(!inCall)Marshal.FreeHGlobal(env);}
                }
                catch(Exception ex)
                {
                    result.Failure=ex.GetType().Name+":"+ex.Message;
                    if(inCall||result.Created||result.Process.Process!=IntPtr.Zero||NativeHealth.Poisoned)
                    { result.UnknownCompletion=true;result.AttributesRetained=true;list.Retained=handles.Retained=jobs.Retained=true;NativeHealth.Poison(); }
                }
                finally
                {
                    if(initialized&&!list.Retained&&!NativeHealth.Poisoned)
                    {
                        try{Interlocked.Increment(ref Win.Entries);DeleteProcThreadAttributeList(list.Data);list.Verify();}
                        catch(Exception ex){list.Retained=handles.Retained=jobs.Retained=true;NativeHealth.Poison();result.UnknownCompletion=true;result.AttributesRetained=true;result.CleanupFailure=ex.Message;result.Failure="ATTRIBUTE_CLEANUP_UNCONFIRMED";}
                    }
                }
            }
            return result;
        }
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)] [DllImport("kernel32.dll",ExactSpelling=true,SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] private static extern bool InitializeProcThreadAttributeList(IntPtr list,int count,uint flags,ref UIntPtr bytes);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)] [DllImport("kernel32.dll",ExactSpelling=true,SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] private static extern bool UpdateProcThreadAttribute(IntPtr list,uint flags,UIntPtr key,IntPtr value,UIntPtr bytes,IntPtr previous,IntPtr returned);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)] [DllImport("kernel32.dll",ExactSpelling=true)] private static extern void DeleteProcThreadAttributeList(IntPtr list);
        [DefaultDllImportSearchPaths(DllImportSearchPath.System32)] [DllImport("kernel32.dll",ExactSpelling=true,CharSet=CharSet.Unicode,SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] private static extern bool CreateProcessW(string application,StringBuilder command,IntPtr pa,IntPtr ta,[MarshalAs(UnmanagedType.Bool)]bool inherit,uint flags,IntPtr environment,string directory,ref HStartupInfoEx startup,out HProcessInfo process);
    }
}
