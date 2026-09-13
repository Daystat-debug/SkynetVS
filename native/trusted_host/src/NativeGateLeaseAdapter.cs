using System;
using System.Collections.Generic;
using System.Threading;
using SkynetVS.G1.InstallationBootstrapV1;
using SkynetVS.G1.P00EpochReadLeaseV1;
namespace SkynetVS.G1.P00EpochNativeStoreV1
{
    internal sealed class DiagnosticNativeStoreReceipt
    {
        internal readonly object Owner;
        internal readonly string Session;
        internal DiagnosticNativeStoreReceipt(object owner,string session){Owner=owner;Session=session;}
    }
    // A separately typed native-domain diagnostic consumer. Never adapts to SyntheticOnly.
    // No child transfer. External diagnostic supervisor must cover lifetime before Attach.
    internal sealed class NativeGateLeaseAdapter : IDisposable
    {
        private readonly P00EpochNativeReadTransport transport;
        private readonly DiagnosticEpochExpectation expected;
        private readonly int thread=Thread.CurrentThread.ManagedThreadId;
        private readonly string session=Guid.NewGuid().ToString("N");
        private EpochRecord anchor,state,acceptance;
        private DiagnosticNativeStoreReceipt receipt;
        private bool busy,used,finished,consumed;
        private string stage="NEW";
        private Exception failure;
        internal NativeGateLeaseAdapter(P00EpochNativeReadTransport io,DiagnosticEpochExpectation expectation)
        {StoreContract.Need(io!=null&&expectation!=null&&Object.ReferenceEquals(io.Expectation,expectation),"OWNER_INPUTS");transport=io;expected=expectation;}
        private void ThreadCheck(){StoreContract.Need(Thread.CurrentThread.ManagedThreadId==thread,"THREAD_AFFINITY");}
        private void Enter()
        {ThreadCheck();if(busy){transport.Revoke();throw new EpochIoFailure("OWNER_REENTRANCY",null,false,null);}StoreContract.Need(!finished,"OWNER_FINISHED");busy=true;}
        private void Remember(Exception e){if(failure==null)failure=e;transport.Revoke();}
        private void Clean()
        {
            try{transport.CloseAll();}catch(Exception e){Remember(e);}
            try{transport.CheckWindow();}catch(Exception e){if(failure==null)failure=e;}
            finished=true;
        }
        private void RepeatRecords()
        {
            StoreContract.Need(Data.Equal(transport.ReadRecord(transport.Ref(StoreRole.InstallAnchor)),anchor.Raw()),"ANCHOR_BYTES_DRIFT");
            StoreContract.Need(Data.Equal(transport.ReadRecord(transport.Ref(StoreRole.Acceptance)),acceptance.Raw()),"ACCEPTANCE_BYTES_DRIFT");
            StoreContract.Need(Data.Equal(transport.ReadRecord(transport.Ref(StoreRole.State)),state.Raw()),"STATE_BYTES_DRIFT");
            EpochCodec.Bind(anchor,state,acceptance);
            foreach(StoreRole r in Enum.GetValues(typeof(StoreRole)))transport.Observe(transport.Ref(r));
            transport.CheckWindow();
        }
        internal DiagnosticNativeStoreReceipt Acquire()
        {
            Enter();try{
                StoreContract.Need(!used,"OWNER_SINGLE_USE");used=true;stage="OBSERVING_ROOTS";transport.InitializeRoots();
                var a=transport.OpenFixed(StoreRole.InstallAnchor,null);anchor=EpochCodec.Anchor(transport.ReadRecord(a));
                StoreContract.Need(anchor.Same(expected.Anchor),"EXPECTED_ANCHOR_BYTES_MISMATCH");
                stage="OPENING_GATE";transport.OpenFixed(StoreRole.Gate,null);
                stage="READING_SELECTED_STATE";var s=transport.OpenFixed(StoreRole.State,null);state=EpochCodec.State(transport.ReadRecord(s));
                StoreContract.Need(state.Text("state")=="ACTIVE","STATE_NOT_ACTIVE_NO_FALLBACK");
                transport.OpenFixed(StoreRole.AcceptanceDirectory,null);
                var v=transport.OpenFixed(StoreRole.Acceptance,state.Text("acceptance_id"));acceptance=EpochCodec.Acceptance(transport.ReadRecord(v));
                EpochCodec.Bind(anchor,state,acceptance);RepeatRecords();
                receipt=new DiagnosticNativeStoreReceipt(this,session);stage="DIAGNOSTIC_LEASE_ACTIVE_NOT_P00";return receipt;
            }catch(Exception e){Remember(e);Clean();stage="DIAGNOSTIC_ERROR";throw;}finally{busy=false;}
        }
        private void Receipt(DiagnosticNativeStoreReceipt value)
        {ThreadCheck();StoreContract.Need(value!=null&&Object.ReferenceEquals(value,receipt)&&Object.ReferenceEquals(value.Owner,this)&&value.Session==session&&!consumed,"FOREIGN_OR_CONSUMED_RECEIPT");}
        internal void CheckUse(DiagnosticNativeStoreReceipt value)
        {Receipt(value);Enter();try{transport.CheckWindow();transport.Observe(transport.Ref(StoreRole.Gate));}
            catch(Exception e){Remember(e);Clean();stage="DIAGNOSTIC_ERROR";throw;}finally{busy=false;}}
        internal Dictionary<string,object> FinalizeAndClose(DiagnosticNativeStoreReceipt value)
        {
            Receipt(value);Enter();consumed=true;
            try{RepeatRecords();}catch(Exception e){Remember(e);}finally{Clean();busy=false;}
            stage=failure==null&&!transport.MayRemain?"EPOCH_STORE_DIAGNOSTIC_COMPLETED_NOT_P00":"DIAGNOSTIC_ERROR";
            return Export();
        }
        internal void Revoke(){transport.Revoke();}
        public void Dispose()
        {
            ThreadCheck();if(busy){transport.Revoke();return;}if(finished)return;
            consumed=true;transport.Revoke();Clean();stage="DISPOSED_NOT_P00";
        }
        internal Dictionary<string,object> Export()
        {
            ThreadCheck();EpochIoFailure io=failure as EpochIoFailure;
            return new Dictionary<string,object>{{"kind","P00_EPOCH_NATIVE_STORE_DIAGNOSTIC_V1"},{"state",stage},
                {"session_id",session},{"receipt_consumed",consumed},{"selection_digest",acceptance==null?null:acceptance.Digest},
                {"source_domain",transport.Domain},{"error",failure==null?null:io!=null?(object)io.Export():StoreContract.Error(failure)},
                {"transport",transport.Export()},{"root_expectations_authenticated",false},{"installed_path_resolved",false},
                {"child_lease_transfer_available",false},{"claims",StoreContract.Claims()}};
        }
    }
}
