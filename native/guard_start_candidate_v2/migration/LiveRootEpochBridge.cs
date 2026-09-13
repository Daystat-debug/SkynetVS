// Additive managed-only bridge candidate. Existing root reader/transport are unchanged.
// No native factory, path import, installation, enrollment or P00 admission is enabled.
using System;
using System.Collections.Generic;
using System.Threading;
using SkynetVS.G1.InstalledRootCandidateV1;
using SkynetVS.G1.ParentChainV1;
using SkynetVS.G1.ParentChainNativeAdapterV1;
using SkynetVS.G1.P00EpochNativeStoreV1;
using SkynetVS.G1.P00EpochReadLeaseV1;
using SkynetVS.G1.SameHandleV1;

namespace SkynetVS.G1.LiveRootEpochBridgeV1
{
    // One synthetic object supplies both views of the SAME handle namespace.
    // The marker is a test seam, not a security claim about arbitrary in-process code.
    internal interface IManagedBridgeCalls : IRootCalls, IManagedEpochStoreCalls { }

    internal sealed class LiveRootEpochBridge
    {
        private sealed class Node
        {
            internal readonly string Path;
            internal readonly IntPtr Handle;
            internal readonly bool Directory;
            internal FileFacts Initial;
            internal DeviceFacts Device;
            internal byte[] Security;
            internal bool Transferred, CloseAttempted, Closed;
            internal Node(string path, IntPtr handle, bool directory)
            { Path=path; Handle=handle; Directory=directory; }
        }

        private readonly IRootCalls roots;
        private readonly IManagedEpochStoreCalls epoch;
        private readonly IRootClock clock;
        private readonly DiagnosticEpochExpectation expected;
        private readonly int thread;
        private readonly long deadline;
        private long previous;
        private readonly List<Node> nodes=new List<Node>();
        private readonly List<string> closeOrder=new List<string>();
        private readonly List<string> cleanupErrors=new List<string>();
        private P00EpochNativeReadTransport transport;
        private bool used, busy, terminal, transferCompleted;
        private int revoked, rootCalls;
        private string stage="NEW", firstError;

        private LiveRootEpochBridge(IManagedBridgeCalls source, DiagnosticEpochExpectation expectation, IRootClock time)
        {
            Rules.Need(source!=null && expectation!=null && time!=null,"BRIDGE_INPUTS");
            roots=source; epoch=source; expected=expectation; clock=time;
            thread=Thread.CurrentThread.ManagedThreadId;
            Origin(); previous=clock.Milliseconds;
            Rules.Need(previous>=0 && previous<=Int64.MaxValue-8000,"BRIDGE_INITIAL_CLOCK");
            deadline=previous+8000;
        }

        internal static LiveRootEpochBridge ForManagedTests(IManagedBridgeCalls source,
            DiagnosticEpochExpectation expectation, IRootClock clock)
        { return new LiveRootEpochBridge(source,expectation,clock); }
        internal static object OpenInstalled()
        { throw new RootFailure("NATIVE_BRIDGE_SUPERVISION_AND_ENROLLMENT_NOT_DELIVERED",false); }
        internal static object ImportObservation(object ignored)
        { throw new RootFailure("DETACHED_OBSERVATION_CANNOT_SUPPLY_LIVE_ROOTS",false); }
        internal void Revoke() { Interlocked.Exchange(ref revoked,1); }
        private void ThreadCheck()
        { Rules.Need(Thread.CurrentThread.ManagedThreadId==thread,"BRIDGE_THREAD_AFFINITY"); }
        private void Origin()
        {
            try {
                if(roots.Domain!=Rules.FakeDomain || epoch.Domain!=StoreContract.FakeDomain)
                    throw new RootFailure("BRIDGE_SOURCE_DOMAIN_CHANGED",true);
            } catch { terminal=true; Revoke(); throw; }
        }
        private long Pulse()
        {
            ThreadCheck(); Rules.Need(!terminal && Interlocked.CompareExchange(ref revoked,0,0)==0,"BRIDGE_STOPPED");
            Origin(); long now;
            try { now=clock.Milliseconds; }
            catch { Revoke(); throw; }
            if(now<previous || now>=deadline) { Revoke(); throw new RootFailure("BRIDGE_ORIGINAL_DEADLINE_OR_CLOCK",false); }
            previous=now;
            Rules.Need(Interlocked.CompareExchange(ref revoked,0,0)==0,"BRIDGE_REVOKED_DURING_CLOCK");
            Origin(); return now;
        }
        private T RootCall<T>(Func<T> action)
        {
            Pulse(); Rules.Need(rootCalls++<Rules.MaxCalls,"BRIDGE_ROOT_CALL_BOUND");
            try { return action(); }
            catch(RootFailure e) { if(e.Terminal)terminal=true; throw; }
            catch(ObservationFailure) { throw; }
            catch { terminal=true; throw new RootFailure("BRIDGE_ROOT_COMPLETION_UNKNOWN",true); }
        }
        private Node Acquire(string path, bool directory, Func<OpenOutcome> action)
        {
            Rules.Need(nodes.Count<Rules.MaxHandles,"BRIDGE_HANDLE_BOUND");
            OpenOutcome opened=RootCall(action);
            if(opened==null || (opened.Missing && opened.Handle!=IntPtr.Zero))
            { terminal=true; throw new RootFailure("BRIDGE_AMBIGUOUS_OPEN",true); }
            if(opened.Missing) { Pulse(); return null; }
            if(!Limits.ValidHandle(opened.Handle) || HasRootHandle(opened.Handle))
            { terminal=true; throw new RootFailure("BRIDGE_INVALID_OR_ALIASED_HANDLE",true); }
            Node node=new Node(path,opened.Handle,directory);
            nodes.Add(node); // Register BEFORE any fallible post-open checks.
            Pulse(); Observe(node); return node;
        }
        private bool HasRootHandle(IntPtr h)
        { foreach(Node n in nodes)if(n.Handle==h && !n.Closed)return true; return false; }
        private static void Validate(Node n, FileFacts f)
        {
            Rules.Need(f.FileType==1 && f.Directory==n.Directory && ((f.Attributes&16u)!=0)==n.Directory,"BRIDGE_OBJECT_KIND");
            Rules.Need((f.Attributes&(0x400u|0x1000u|0x40000u|0x400000u))==0 && f.ReparseTag==0 && !f.DeletePending,"BRIDGE_REPARSE_OR_DELETE");
            Rules.Need(f.Size>=0 && f.Allocation>=0 && f.Creation>=0 && f.Write>=0 && f.Change>=0 && f.Volume!=0,"BRIDGE_METADATA");
            if(!n.Directory)Rules.Need(f.Links==1 && f.Size>0,"BRIDGE_IMAGE_KIND");
        }
        private void Observe(Node n)
        {
            FileFacts a=StoreSnapshot.CopyFacts(RootCall<FileFacts>(delegate { return roots.Facts(n.Handle); })); Pulse(); Validate(n,a);
            DeviceFacts d=RootCall<DeviceFacts>(delegate { return roots.Device(n.Handle); }); Pulse();
            Rules.Need(d!=null,"BRIDGE_DEVICE_REQUIRED"); d.RequireLocalDisk();
            byte[] raw=RootCall<byte[]>(delegate { return roots.Security(n.Handle); });
            Rules.Need(raw!=null && raw.Length>=20 && raw.Length<=65536,"BRIDGE_DESCRIPTOR_BOUND");
            raw=(byte[])raw.Clone(); Pulse(); Descriptor.Decode(raw); // Structural only, not ACL approval.
            FileFacts b=StoreSnapshot.CopyFacts(RootCall<FileFacts>(delegate { return roots.Facts(n.Handle); })); Pulse(); Validate(n,b);
            Rules.Need(a.Stable(b),"BRIDGE_OBSERVATION_DRIFT");
            if(n.Initial==null) { n.Initial=a; n.Device=d; n.Security=raw; }
            else Rules.Need(n.Initial.Stable(a) && n.Device.Same(d) && Binary.Equal(n.Security,raw),"BRIDGE_RETAINED_SPINE_DRIFT");
        }
        private Node Walk(LocalPath path)
        {
            Node n=Acquire(path.Drive,true,delegate { return roots.OpenVolume(path.Drive); });
            Rules.Need(n!=null,"BRIDGE_VOLUME_UNAVAILABLE"); string text=path.Drive;
            foreach(string component in path.Parts()) {
                Node parent=n; string one=component; text=text.TrimEnd('\\')+"\\"+one;
                n=Acquire(text,true,delegate { return roots.OpenRelative(parent.Handle,one,true); });
                if(n==null)throw new RootFailure("BRIDGE_COMPONENT_MISSING:"+text,false);
                Rules.Need(n.Initial.Volume==parent.Initial.Volume && !Binary.Equal(n.Initial.Id,parent.Initial.Id),"BRIDGE_CHAIN_VOLUME_OR_ALIAS");
            }
            return n;
        }
        private void RecheckSpine(LocationInput first)
        {
            for(int i=nodes.Count-1;i>=0;i--)Observe(nodes[i]);
            LocationInput last=RootCall<LocationInput>(delegate { return roots.Locations(); }); Pulse();
            Rules.Need(first.Same(last),"BRIDGE_LOCATION_DRIFT");
        }
        private static void MatchSnapshot(Node node, StoreSnapshot snapshot)
        {
            Rules.Need(snapshot!=null && node.Initial.Stable(snapshot.Facts) && node.Device.Type==snapshot.DeviceType
                && node.Device.Characteristics==snapshot.DeviceFlags && Binary.Equal(node.Security,snapshot.Security()),
                "BRIDGE_ROOT_SNAPSHOT_DISCONTINUITY");
        }
        private StoreRef Open(StoreRole role, string selected)
        {
            StoreRef r=transport.OpenFixed(role,selected);
            // Transport checks aliases among its seven roles; the aggregate adds the retained spine/image.
            foreach(Node node in nodes)
                Rules.Need(!StoreContract.Identity(node.Initial).Same(StoreContract.Identity(r.Initial.Facts)),"BRIDGE_EPOCH_OBJECT_ALIASES_SPINE");
            return r;
        }
        private void Repeat(EpochRecord anchor, EpochRecord state, EpochRecord acceptance)
        {
            Rules.Need(Binary.Equal(transport.ReadRecord(transport.Ref(StoreRole.InstallAnchor)),anchor.Raw()),"BRIDGE_ANCHOR_DRIFT");
            Rules.Need(Binary.Equal(transport.ReadRecord(transport.Ref(StoreRole.Acceptance)),acceptance.Raw()),"BRIDGE_ACCEPTANCE_DRIFT");
            Rules.Need(Binary.Equal(transport.ReadRecord(transport.Ref(StoreRole.State)),state.Raw()),"BRIDGE_STATE_DRIFT");
            EpochCodec.Bind(anchor,state,acceptance);
            foreach(StoreRole role in Enum.GetValues<StoreRole>())transport.Observe(transport.Ref(role));
            Pulse();
        }
        private void Cleanup()
        {
            if(transport!=null && transport.Terminal)terminal=true;
            if(terminal) { cleanupErrors.Add("NO_CLEANUP_AFTER_UNKNOWN_COMPLETION_OR_ORIGIN"); return; }
            // Close the retained image/ancestors FIRST. Transferred roots remain owned by the transport.
            // Transport then closes its children/roots and finally Gate, globally last.
            for(int i=nodes.Count-1;i>=0;i--) {
                Node n=nodes[i]; if(n.Transferred || n.CloseAttempted)continue;
                try {
                    Origin(); n.CloseAttempted=true; closeOrder.Add("spine:"+n.Path);
                    roots.Close(n.Handle); n.Closed=true; Origin();
                } catch(Exception e) { terminal=true; cleanupErrors.Add("spine:"+n.Path+":"+e.Message); return; }
            }
            if(transport!=null) {
                try { transport.CloseAll(); }
                catch(Exception e) { terminal=true; cleanupErrors.Add("transport:"+e.Message); }
                if(transport.MayRemain) { terminal=true; cleanupErrors.Add("TRANSPORT_HANDLES_MAY_REMAIN"); }
            }
        }
        internal Dictionary<string,object> RunDiagnostic()
        {
            ThreadCheck();
            if(used || busy) { Revoke(); throw new RootFailure("BRIDGE_SINGLE_USE",false); }
            used=true; busy=true;
            string result="LIVE_ROOT_EPOCH_BRIDGE_ERROR", digest=null, release=null;
            try {
                stage="ACQUIRING_SPINE";
                LocationInput location=RootCall<LocationInput>(delegate { return roots.Locations(); }); Pulse();
                LayoutPlan plan=LayoutPlan.FromObservedLocations(location);
                if(plan==null)result="CURRENT_IMAGE_OUTSIDE_INSTALLED_LAYOUT";
                else {
                    release=plan.ReleaseId;
                    // The independent expectation is supplied BEFORE acquisition; it is never manufactured from observed bytes.
                    Rules.Need(release==expected.Anchor.Text("host_release_id"),"BRIDGE_EXPECTED_RELEASE_MISMATCH");
                    Node host=Walk(plan.Host), store=Walk(plan.Store);
                    Rules.Need(StoreContract.Identity(host.Initial).Same(expected.HostRoot)
                        && StoreContract.Identity(store.Initial).Same(expected.StoreRoot),"BRIDGE_EXPECTED_ROOT_MISMATCH");
                    Node image=Acquire(plan.Image.Text,false,delegate { return roots.OpenRelative(host.Handle,"Guard.exe",false); });
                    Rules.Need(image!=null && image.Initial.Volume==host.Initial.Volume,"BRIDGE_IMAGE_MISSING_OR_VOLUME");
                    RecheckSpine(location); stage="ATTACHING_LIVE_ROOTS";
                    OwnedDiagnosticRootPair pair=new OwnedDiagnosticRootPair(host.Handle,store.Handle);
                    transport=P00EpochNativeReadTransport.ForManagedTests(new EpochView(this),pair,expected,new SharedClock(this));
                    // Attach is exact-source known: transfer is its final, non-fallible step.
                    // These ownership flags MUST precede Pulse, metadata, logging and any other fallible work.
                    host.Transferred=true; store.Transferred=true; transferCompleted=true;
                    Pulse(); transport.InitializeRoots();
                    MatchSnapshot(host,transport.Ref(StoreRole.HostReleaseRoot).Initial);
                    MatchSnapshot(store,transport.Ref(StoreRole.StoreRoot).Initial);
                    stage="READING_EPOCH_DIAGNOSTIC";
                    StoreRef anchorRef=Open(StoreRole.InstallAnchor,null);
                    EpochRecord anchor=EpochCodec.Anchor(transport.ReadRecord(anchorRef));
                    Rules.Need(anchor.Same(expected.Anchor),"BRIDGE_INDEPENDENT_ANCHOR_MISMATCH");
                    Open(StoreRole.Gate,null);
                    EpochRecord state=EpochCodec.State(transport.ReadRecord(Open(StoreRole.State,null)));
                    Rules.Need(state.Text("state")=="ACTIVE","BRIDGE_NONACTIVE_NO_FALLBACK");
                    Open(StoreRole.AcceptanceDirectory,null);
                    EpochRecord acceptance=EpochCodec.Acceptance(transport.ReadRecord(Open(StoreRole.Acceptance,state.Text("acceptance_id"))));
                    EpochCodec.Bind(anchor,state,acceptance);
                    stage="RECHECKING_WITH_GATE_HELD";
                    Repeat(anchor,state,acceptance); RecheckSpine(location); Pulse();
                    digest=acceptance.Digest;
                    result="LIVE_ROOT_EPOCH_DIAGNOSTIC_COMPLETED_NOT_P00";
                }
            } catch(Exception e) {
                firstError=e.GetType().Name+":"+e.Message;
                RootFailure r=e as RootFailure; EpochIoFailure t=e as EpochIoFailure;
                if((r!=null && r.Terminal) || (t!=null && t.Terminal))terminal=true;
            } finally { Cleanup(); busy=false; }
            if(cleanupErrors.Count==0 && firstError==null) {
                try { Pulse(); }
                catch(Exception e) { firstError=e.GetType().Name+":"+e.Message; }
            }
            if(firstError!=null || cleanupErrors.Count!=0)result="LIVE_ROOT_EPOCH_BRIDGE_ERROR";
            int transferred=0, closed=0;
            foreach(Node n in nodes) { if(n.Transferred)transferred++; if(n.Closed)closed++; }
            bool mayRemain=terminal || nodes.Count-transferred!=closed || (transport!=null && transport.MayRemain);
            return new Dictionary<string,object> {
                {"kind","LIVE_ROOT_EPOCH_BRIDGE_MANAGED_DIAGNOSTIC_V1"},{"result",result},{"stage",stage},{"error",firstError},
                {"release_id",release},{"selection_digest",digest},{"root_nodes",nodes.Count},{"spine_close_successes",closed},
                {"transferred_roots",transferred},{"transfer_completed",transferCompleted},{"root_calls",rootCalls},
                {"aggregate_close_order",new List<string>(closeOrder)},{"cleanup_errors",new List<string>(cleanupErrors)},
                {"epoch_transport",transport==null?null:transport.Export()},{"process_exit_required",mayRemain},
                {"all_io_synthetic",true},{"native_factory_enabled",false},{"claims",Rules.Claims()},
                {"P00","NOT_ACCEPTED"},{"P01","NOT_IMPLEMENTED"},{"acquisition","BLOCKED"}
            };
        }
        // No fake cleanup method may re-enable this owner. This only frees quarantined HGlobal test buffers.
        internal void ReleaseCompletedFakeStorageForTests()
        { ThreadCheck(); Rules.Need(used && !busy,"BRIDGE_TEST_RELEASE_AFTER_RUN_ONLY"); if(transport!=null)transport.ReleaseRetainedFakeStorageForTests(); }

        private sealed class SharedClock : IEpochClock
        {
            private readonly LiveRootEpochBridge owner;
            internal SharedClock(LiveRootEpochBridge value) { owner=value; }
            // EpochWindow creates its own window, but this adapter ALWAYS enforces the original root deadline first.
            public long Milliseconds { get { return owner.Pulse(); } }
        }
        private sealed class EpochView : IManagedEpochStoreCalls
        {
            private readonly LiveRootEpochBridge owner;
            internal EpochView(LiveRootEpochBridge value) { owner=value; }
            public string Domain { get { owner.Origin(); return StoreContract.FakeDomain; } }
            public int Open(NtOpenFrame frame)
            {
                owner.Pulse(); int status=owner.epoch.Open(frame);
                frame.Check();
                if(frame.ResultHandle!=IntPtr.Zero && owner.HasRootHandle(frame.ResultHandle)) {
                    owner.terminal=true;
                    // Transport catches this and quarantines the entire NT frame, not just the handle.
                    throw new RootFailure("BRIDGE_EPOCH_HANDLE_ALIASES_SPINE",true);
                }
                return status;
            }
            public int Device(IntPtr h,NtDeviceFrame frame) { owner.Pulse(); return owner.epoch.Device(h,frame); }
            public FileFacts Facts(IntPtr h) { owner.Pulse(); return owner.epoch.Facts(h); }
            public byte[] Security(IntPtr h) { owner.Pulse(); return owner.epoch.Security(h); }
            public int Read(IntPtr h,EpochReadFrame frame) { owner.Pulse(); return owner.epoch.Read(h,frame); }
            public void Close(IntPtr h)
            {
                // Known-completion cleanup remains permitted after timeout/revoke, never after origin/terminal failure.
                owner.Origin(); Rules.Need(!owner.terminal,"BRIDGE_TERMINAL_CLOSE_FORBIDDEN");
                owner.closeOrder.Add("epoch:"+owner.RoleFor(h)); owner.epoch.Close(h); owner.Origin();
            }
        }
        private string RoleFor(IntPtr handle)
        {
            foreach(StoreRole role in Enum.GetValues<StoreRole>()) {
                StoreRef r=transport.Ref(role); if(r!=null && r.Handle==handle)return role.ToString();
            }
            throw new RootFailure("BRIDGE_CLOSE_UNKNOWN_HANDLE",true);
        }
    }
}
