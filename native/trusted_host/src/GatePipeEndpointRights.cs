using System;
using SkynetVS.G1.GateLeaseHandoffV1;

namespace SkynetVS.G1.GateLeaseHandoffNativeV1
{
    internal sealed class PipeEndpointSnapshot
    {
        internal readonly uint Type,Flags,Access;
        internal PipeEndpointSnapshot(uint type,uint flags,uint access)
        {Type=type;Flags=flags;Access=access;}
    }
    internal sealed class PipeDuplicateOutcome
    {
        internal readonly bool CompletionKnown,Success;
        internal readonly IntPtr Handle;
        internal readonly int Error;
        internal PipeDuplicateOutcome(bool known,bool success,IntPtr handle,int error)
        {CompletionKnown=known;Success=success;Handle=handle;Error=error;}
    }
    internal static class PipeEndpointRights
    {
        // Preserve FILE_GENERIC_READ for the documented PeekNamedPipe contract.
        internal const uint Reader=0x00120089;
        // Synchronous byte writes only. No CREATE_PIPE_INSTANCE (0x4), EA/attribute or ACL access.
        internal const uint Writer=0x00100002;
        internal static uint For(bool reader){return reader?Reader:Writer;}
        internal static void RequireRaw(PipeEndpointSnapshot observed,bool reader)
        {
            HCheck.Need(observed!=null && observed.Type==3 && observed.Flags==0,"RAW_PIPE_TYPE_OR_FLAGS");
            uint requested=For(reader);
            HCheck.Need((observed.Access&requested)==requested,"RAW_PIPE_MISSING_REQUIRED_ACCESS_"+observed.Access.ToString("x8"));
            // Supersets are accepted ONLY for fresh, non-inheritable temporary CreatePipe handles.
            // Such a handle is never a final endpoint, an inheritance-list member or an IO argument.
        }
        internal static void RequireExact(PipeEndpointSnapshot observed,bool reader,bool inherit)
        {
            HCheck.Need(observed!=null && observed.Type==3,"PIPE_ENDPOINT_TYPE");
            HCheck.Need(observed.Flags==(inherit?1u:0u),"HANDLE_FLAGS_MISMATCH");
            HCheck.Need(observed.Access==For(reader),"PIPE_ENDPOINT_ACCESS_ACTUAL_"+observed.Access.ToString("x8"));
        }
    }
    internal interface IPipeNarrowCalls
    {
        PipeEndpointSnapshot Observe(IntPtr handle);
        PipeDuplicateOutcome Duplicate(IntPtr source,uint access);
        void Poison();
    }
    internal sealed class WindowsPipeNarrowCalls : IPipeNarrowCalls
    {
        public PipeEndpointSnapshot Observe(IntPtr handle){return Win.ObservePipeEndpoint(handle);}
        public PipeDuplicateOutcome Duplicate(IntPtr source,uint access){return Win.DuplicatePipeEndpoint(source,access);}
        public void Poison(){NativeHealth.Poison();}
    }
    internal sealed class NormalizedPipePair
    {
        internal readonly OwnedHandle Read,Write;
        internal NormalizedPipePair(OwnedHandle read,OwnedHandle write){Read=read;Write=write;}
    }
    // The caller owns raw endpoints in the same ledger BEFORE calling this routine.
    // On an ordinary failure caller cleanup uses that ledger. No private cleanup or hidden retry.
    internal static class PipeEndpointNarrower
    {
        private static OwnedHandle DuplicateOne(IPipeNarrowCalls calls,HandleLedger ledger,
            OwnedHandle source,string role,bool reader,Action check)
        {
            check();PipeDuplicateOutcome result;
            try{result=calls.Duplicate(source.Use(),PipeEndpointRights.For(reader));}
            catch{calls.Poison();throw;}
            if(result==null || !result.CompletionKnown ||
                (result.Success?!HCheck.Handle(result.Handle):result.Handle!=IntPtr.Zero))
            {calls.Poison();throw new HandoffFailure("PIPE_DUPLICATE_COMPLETION_UNKNOWN");}
            if(!result.Success)throw new HandoffFailure("PIPE_DUPLICATE_FAILED_WIN32_"+result.Error.ToString());
            OwnedHandle copy;
            try{copy=ledger.Add(role,result.Handle);}
            catch{calls.Poison();throw;}
            // Acquire ownership BEFORE any clock callback or output check can throw.
            check();PipeEndpointSnapshot observed=calls.Observe(copy.Use());check();
            PipeEndpointRights.RequireExact(observed,reader,false);return copy;
        }
        internal static NormalizedPipePair NarrowPair(IPipeNarrowCalls calls,HandleLedger ledger,
            OwnedHandle rawRead,OwnedHandle rawWrite,string readRole,string writeRole,Action check)
        {
            HCheck.Need(calls!=null && ledger!=null && rawRead!=null && rawWrite!=null && check!=null,
                "PIPE_NORMALIZE_INPUTS");
            HCheck.Need(readRole!=null && writeRole!=null && readRole.Length>0 && writeRole.Length>0 &&
                readRole!=writeRole && rawRead.Use()!=rawWrite.Use(),"PIPE_NORMALIZE_ROLES");
            check();PipeEndpointSnapshot first=calls.Observe(rawRead.Use());check();PipeEndpointRights.RequireRaw(first,true);
            PipeEndpointSnapshot second=calls.Observe(rawWrite.Use());check();PipeEndpointRights.RequireRaw(second,false);
            OwnedHandle read=DuplicateOne(calls,ledger,rawRead,readRole,true,check);
            OwnedHandle write=DuplicateOne(calls,ledger,rawWrite,writeRole,false,check);
            // Neither source can survive a successful return. All copies remain non-inheritable here.
            check();ledger.CloseOnce(rawWrite);check();ledger.CloseOnce(rawRead);check();
            return new NormalizedPipePair(read,write);
        }
    }
}
