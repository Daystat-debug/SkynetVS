using System;
using System.Collections.Generic;
using System.Threading;
using SkynetVS.G1.ParentChainV1;
using SkynetVS.G1.SameHandleV1;

namespace SkynetVS.G1.InstalledRootCandidateV1
{
    internal sealed class HeldNode
    {
        internal readonly string Path; internal readonly IntPtr Handle; internal readonly bool Directory;
        internal FileFacts Initial; internal byte[] Descriptor; internal DeviceFacts Device;
        internal bool CloseAttempted, Closed;
        internal HeldNode(string path,IntPtr h,bool dir){Path=path;Handle=h;Directory=dir;}
    }
    internal sealed class InstalledRootReadOnly
    {
        private readonly IRootCalls io; private readonly IRootClock clock; private readonly string domain;
        private readonly int thread; private readonly long deadline; private long previous;
        private readonly List<HeldNode> owned=new List<HeldNode>();
        private readonly List<string> closes=new List<string>(), cleanupErrors=new List<string>();
        private bool used, revoked, terminal, busy; private int calls;
        internal InstalledRootReadOnly(IRootCalls source,IRootClock time)
        {
            Rules.Need(source!=null&&time!=null,"SOURCE_CLOCK_REQUIRED"); io=source;clock=time;domain=io.Domain;
            Rules.Need(domain==Rules.NativeDomain||domain==Rules.FakeDomain,"SOURCE_DOMAIN");
            thread=Thread.CurrentThread.ManagedThreadId;previous=clock.Milliseconds;
            Rules.Need(previous>=0&&previous<=Int64.MaxValue-8000,"INITIAL_CLOCK");deadline=previous+8000;
        }
        internal void Revoke(){revoked=true;}
        private void Origin()
        { if(io.Domain!=domain){terminal=true;throw new RootFailure("SOURCE_ORIGIN_CHANGED",true);} }
        private void Pulse()
        {
            Rules.Need(Thread.CurrentThread.ManagedThreadId==thread,"WRONG_THREAD");
            Rules.Need(!terminal&&!revoked,"SCOPE_STOPPED");Origin();
            long now;
            try { now=clock.Milliseconds; } catch { revoked=true;throw; }
            if(now<previous||now>=deadline){revoked=true;throw new RootFailure("EXPIRED_OR_REVERSED_CLOCK",false);}
            previous=now;Rules.Need(!revoked,"SCOPE_REVOKED_BY_CLOCK");Origin();
        }
        private T Call<T>(Func<T> action)
        {
            Pulse();Rules.Need(calls++<Rules.MaxCalls,"CALL_BOUND");T answer;
            try { answer=action(); }
            catch(RootFailure e){if(e.Terminal)terminal=true;throw;}
            catch(ObservationFailure){throw;}
            catch{terminal=true;throw new RootFailure("DISPATCH_COMPLETION_UNKNOWN",true);}
            // Opens must be registered before post-call time checks: handled by Acquire.
            return answer;
        }
        private HeldNode Acquire(string path,bool dir,Func<OpenOutcome> action)
        {
            Rules.Need(owned.Count<Rules.MaxHandles,"HANDLE_BOUND");OpenOutcome o=Call(action);
            if(o==null){terminal=true;throw new RootFailure("NULL_OPEN_OUTCOME",true);}
            if(o.Missing){if(o.Handle!=IntPtr.Zero){terminal=true;throw new RootFailure("MISSING_WITH_HANDLE",true);}Pulse();return null;}
            if(!Limits.ValidHandle(o.Handle)){terminal=true;throw new RootFailure("INVALID_OPEN_HANDLE",true);}
            foreach(HeldNode n in owned)if(!n.Closed&&n.Handle==o.Handle){terminal=true;throw new RootFailure("LIVE_HANDLE_ALIAS",true);}
            HeldNode node=new HeldNode(path,o.Handle,dir);owned.Add(node);Pulse();Observe(node);return node;
        }
        private static FileFacts Copy(FileFacts f)
        {
            Rules.Need(f!=null&&f.Id!=null&&f.Id.Length==16,"FACTS_SHAPE");
            return new FileFacts{FileType=f.FileType,Volume=f.Volume,Id=(byte[])f.Id.Clone(),Size=f.Size,Allocation=f.Allocation,
                Links=f.Links,Attributes=f.Attributes,ReparseTag=f.ReparseTag,Creation=f.Creation,Access=f.Access,
                Write=f.Write,Change=f.Change,DeletePending=f.DeletePending,Directory=f.Directory};
        }
        private static void Validate(HeldNode n,FileFacts f)
        {
            Rules.Need(f.FileType==1&&f.Directory==n.Directory&&((f.Attributes&16)!=0)==n.Directory,"OBJECT_KIND");
            Rules.Need((f.Attributes&(0x400u|0x1000u|0x40000u|0x400000u))==0&&f.ReparseTag==0&&!f.DeletePending,"REPARSE_OFFLINE_RECALL_DELETE");
            Rules.Need(f.Size>=0&&f.Allocation>=0&&f.Creation>=0&&f.Write>=0&&f.Change>=0&&f.Volume!=0,"METADATA_SHAPE");
            if(!n.Directory)Rules.Need(f.Links==1&&f.Size>0,"IMAGE_NOT_ORDINARY_SINGLE_LINK");
        }
        private void Observe(HeldNode n)
        {
            FileFacts a=Copy(Call<FileFacts>(delegate{return io.Facts(n.Handle);}));Pulse();Validate(n,a);
            DeviceFacts d=Call<DeviceFacts>(delegate{return io.Device(n.Handle);});Pulse();Rules.Need(d!=null,"DEVICE_REQUIRED");d.RequireLocalDisk();
            byte[] raw=Call<byte[]>(delegate{return io.Security(n.Handle);});
            Rules.Need(raw!=null&&raw.Length>=20&&raw.Length<=65536,"DESCRIPTOR_BOUND");raw=(byte[])raw.Clone();Pulse();
            // Structural decoder only; not an ACL/profile approval.
            Descriptor.Decode(raw);
            FileFacts b=Copy(Call<FileFacts>(delegate{return io.Facts(n.Handle);}));Pulse();Validate(n,b);
            Rules.Need(a.Stable(b),"METADATA_CHANGED_WITHIN_OBSERVATION");
            if(n.Initial!=null)Rules.Need(n.Initial.Stable(a)&&n.Device.Same(d)&&Binary.Equal(n.Descriptor,raw),"RETAINED_OBJECT_DRIFT");
            else {n.Initial=a;n.Device=d;n.Descriptor=raw;}
        }
        private HeldNode Walk(LocalPath path)
        {
            HeldNode node=Acquire(path.Drive,true,delegate{return io.OpenVolume(path.Drive);});
            Rules.Need(node!=null,"VOLUME_ROOT_UNAVAILABLE");string text=path.Drive;
            foreach(string component in path.Parts()) {
                HeldNode parent=node;string one=component;
                text=text.TrimEnd('\\')+"\\"+one;
                node=Acquire(text,true,delegate{return io.OpenRelative(parent.Handle,one,true);});
                if(node==null)throw new RootFailure("INSTALLED_COMPONENT_MISSING:"+text,false);
                Rules.Need(parent.Initial.Volume==node.Initial.Volume,"VOLUME_CHANGED_IN_CHAIN");
                Rules.Need(!Binary.Equal(parent.Initial.Id,node.Initial.Id),"PARENT_CHILD_OBJECT_ALIAS");
            }
            return node;
        }
        private void Cleanup()
        {
            if(terminal){cleanupErrors.Add("NO_NATIVE_CLEANUP_AFTER_UNKNOWN_COMPLETION");return;}
            for(int i=owned.Count-1;i>=0;i--) {
                HeldNode node=owned[i];if(node.CloseAttempted)continue;
                try {Origin();node.CloseAttempted=true;closes.Add(node.Path);io.Close(node.Handle);node.Closed=true;Origin();}
                catch(Exception e){terminal=true;cleanupErrors.Add(node.Path+":"+e.Message);break;}
            }
        }
        internal Dictionary<string,object> Run()
        {
            Rules.Need(Thread.CurrentThread.ManagedThreadId==thread,"WRONG_THREAD");
            if(used||busy){revoked=true;throw new RootFailure("SINGLE_USE_ROOT_READER",false);}used=true;busy=true;
            string outcome="ROOT_READ_ERROR",error=null;LayoutPlan plan=null;LocationInput before=null;
            try {
                before=Call<LocationInput>(delegate{return io.Locations();});Pulse();plan=LayoutPlan.FromObservedLocations(before);
                if(plan==null)outcome="CURRENT_IMAGE_OUTSIDE_INSTALLED_LAYOUT";
                else {
                    HeldNode host=Walk(plan.Host),store=Walk(plan.Store);
                    Rules.Need(host.Initial.Volume!=store.Initial.Volume||!Binary.Equal(host.Initial.Id,store.Initial.Id),"HOST_STORE_OBJECT_ALIAS");
                    HeldNode image=Acquire(plan.Host.Text+"\\Guard.exe",false,delegate{return io.OpenRelative(host.Handle,"Guard.exe",false);});
                    if(image==null)throw new RootFailure("INSTALLED_COMPONENT_MISSING:Guard.exe",false);
                    Rules.Need(host.Initial.Volume==image.Initial.Volume,"IMAGE_VOLUME_CHANGED");
                    for(int i=owned.Count-1;i>=0;i--)Observe(owned[i]);
                    outcome="ROOT_CANDIDATES_OBSERVED_NOT_ENROLLED";
                }
                LocationInput after=Call<LocationInput>(delegate{return io.Locations();});Pulse();
                Rules.Need(before.Same(after),"LOCATION_SOURCE_CHANGED");
            }
            catch(Exception e){error=e.GetType().Name+":"+e.Message;var r=e as RootFailure;
                if(r!=null&&r.Terminal)terminal=true;
                outcome=r!=null&&r.Code.StartsWith("INSTALLED_COMPONENT_MISSING:",StringComparison.Ordinal)?"INSTALLED_PATH_NOT_OBSERVED":"ROOT_READ_ERROR";}
            finally{Cleanup();busy=false;}
            if(cleanupErrors.Count==0&&!terminal){try{Pulse();}catch(Exception e){error=e.GetType().Name+":"+e.Message;outcome="ROOT_READ_ERROR";}}
            if(cleanupErrors.Count!=0)outcome="ROOT_READ_ERROR";
            var observations=new List<object>();int closed=0;
            foreach(HeldNode n in owned){if(n.Closed)closed++;if(n.Initial!=null)observations.Add(new Dictionary<string,object>{
                {"path",n.Path},{"facts",n.Initial.Record()},{"descriptor_bytes",n.Descriptor.Length},{"descriptor_sha256",Binary.Hash(n.Descriptor)}});}
            return new Dictionary<string,object>{{"kind","INSTALLED_ROOT_CANDIDATE_OBSERVATION_V1"},{"result",outcome},{"error",error},
                {"source_domain",domain},{"release_id",plan==null?null:plan.ReleaseId},{"owned_handles",owned.Count},{"closed_handles",closed},
                {"close_order",new List<string>(closes)},{"cleanup_errors",new List<string>(cleanupErrors)},{"observations",observations},
                {"process_exit_required",terminal||closed!=owned.Count},{"calls",calls},{"claims",Rules.Claims()},
                {"image_path_is_attestation",false},{"P00","NOT_ACCEPTED"},{"P01","NOT_IMPLEMENTED"}};
        }
    }
}
