"""HWA02-B2 portable volume runtime and repeat/history acceptance.

All audio callbacks are injected or use fake AudioControl endpoints. No real host
audio, media key, native worker, Sandbox, network, or subprocess effect occurs.
"""
from __future__ import annotations

import ast
import copy
import dataclasses
import hashlib
import json
import os
from pathlib import Path
import pickle
import sys
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import modules.volume_action_runtime as model
from modules.action_contract import ActionContractError, ActionRequest, ActionStatus, EffectState
from modules.action_error import ActionExecutionError
import modules.action_authority as authority
from modules.command_decision import build_command_decision
from modules.command_outcome import classify_command_outcome
from modules.command_runtime import handle_command_runtime
import types
_actions_stub = types.ModuleType("modules.actions")
_actions_stub.Actions = type("Actions", (), {})
sys.modules.setdefault("modules.actions", _actions_stub)
from modules.router import Router
from modules.audio_control import AudioControl, AudioEndpointBinding

EXPECTED_TESTS = 51


def fail_audio(intent="VOLUME_UP", code="audio_control_failed", operation="audio_control.change_volume"):
    return ActionExecutionError(
        intent=intent,
        operation=operation,
        detail="RAW PRIVATE DETAIL",
        user_message="UNTRUSTED MESSAGE",
        error_code=code,
        context={"secret": "DO NOT FORWARD"},
    )


def build(*, step=10, change=None, remember=None):
    calls=[]; history=[]
    def default_change(intent, delta):
        calls.append((intent, delta)); return (55, False)
    owner, port = model.compose_volume_action_runtime(
        step=step,
        change_volume=change if change is not None else default_change,
        remember_volume_success=remember if remember is not None else lambda intent: history.append(intent),
    )
    return owner, port, calls, history


def prepare(port, intent="VOLUME_UP"):
    return port.prepare(intent=intent, slots={})


class VolumeBoundaryTests(unittest.TestCase):
    def test_prepare_is_data_only(self):
        _,p,c,h=build(); plan=prepare(p)
        self.assertEqual(c,[]);self.assertEqual(h,[]);self.assertEqual(p._state.issuer._domain.issued,set())
        self.assertIs(type(plan),model.PreparedVolumeAction)

    def test_step_exact_type_and_bounds(self):
        for step in [True,False,0,-1,101,10.0,"10",None]:
            with self.subTest(step=step), self.assertRaises(ActionContractError): build(step=step)

    def test_only_volume_pair(self):
        _,p,_,_=build()
        for intent in ["MUTE","SET_VOLUME","SET_TIMER","VOLUME_UP ","volume_up",""]:
            with self.subTest(intent=intent), self.assertRaises(ActionContractError): p.prepare(intent=intent,slots={})

    def test_slots_must_be_exact_empty_dict(self):
        _,p,_,_=build()
        for slots in [None,(),{"delta":10},{"approved":True}]:
            with self.subTest(slots=slots), self.assertRaises(ActionContractError): p.prepare(intent="VOLUME_UP",slots=slots)

    def test_prepare_freezes_signed_delta(self):
        _,p,c,h=build(step=7); up=prepare(p,"VOLUME_UP");down=prepare(p,"VOLUME_DOWN")
        p._state.step=99
        p.execute(up);p.execute(down)
        self.assertEqual(c,[("VOLUME_UP",7),("VOLUME_DOWN",-7)])
        self.assertEqual(h,["VOLUME_UP","VOLUME_DOWN"])

    def test_request_specs_bind_exact_delta(self):
        _,p,_,_=build(step=10); up=prepare(p)
        with self.assertRaises(ActionContractError):
            model._spec_for(dataclasses.replace(up.request,parameters=(("delta",11),)),p._state.specs)

    def test_success_contains_verified_observed_state(self):
        _,p,c,h=build(change=lambda i,d:(73,True)); plan=prepare(p)
        result,f=model._dispatch(p._state,plan.request)
        self.assertIs(result.status,ActionStatus.SUCCEEDED);self.assertEqual(result.output,(("muted",True),("volume",73)))
        self.assertIsNone(f);self.assertEqual(h,[]);self.assertEqual(c,[])

    def test_execute_success_commits_history_once(self):
        _,p,c,h=build(); p.execute(prepare(p))
        self.assertEqual(c,[("VOLUME_UP",10)]);self.assertEqual(h,["VOLUME_UP"])

    def test_down_success(self):
        _,p,c,h=build(); p.execute(prepare(p,"VOLUME_DOWN"))
        self.assertEqual(c,[("VOLUME_DOWN",-10)]);self.assertEqual(h,["VOLUME_DOWN"])

    def test_same_plan_replay_no_audio_no_history(self):
        _,p,c,h=build(); plan=prepare(p);p.execute(plan)
        with self.assertRaises(ActionExecutionError) as ctx:p.execute(plan)
        self.assertEqual(ctx.exception.error_code,"volume_action_denied")
        self.assertEqual(len(c),1);self.assertEqual(h,["VOLUME_UP"])

    def test_reconstructed_request_not_authority(self):
        _,p,c,h=build(); plan=prepare(p);p.execute(plan)
        clone=ActionRequest.from_bytes(plan.request.to_bytes())
        res,_=model._dispatch(p._state,clone)
        self.assertIs(res.status,ActionStatus.DENIED);self.assertEqual(len(c),1);self.assertEqual(len(h),1)

    def test_other_scope_denied(self):
        _,p,_,_=build();_,q,c,h=build();res,_=model._dispatch(q._state,prepare(p).request)
        self.assertIs(res.status,ActionStatus.DENIED);self.assertEqual(c,[]);self.assertEqual(h,[])

    def test_changed_record_denied_without_effect(self):
        _,p,c,h=build();plan=prepare(p)
        bad=dataclasses.replace(plan,repeat_record=model.VolumeRepeatRecord("VOLUME_DOWN",()))
        with self.assertRaises(ActionExecutionError):p.execute(bad)
        self.assertEqual(c,[]);self.assertEqual(h,[])

    def test_changed_request_delta_denied_without_effect(self):
        _,p,c,h=build();plan=prepare(p)
        bad=dataclasses.replace(plan,request=dataclasses.replace(plan.request,parameters=(("delta",9),)))
        with self.assertRaises(ActionExecutionError):p.execute(bad)
        self.assertEqual(c,[]);self.assertEqual(h,[])

    def test_unavailable_is_bounded(self):
        def change(i,d):raise fail_audio(i,"audio_control_unavailable")
        _,p,_,h=build(change=change)
        with self.assertRaises(ActionExecutionError) as ctx:p.execute(prepare(p))
        e=ctx.exception;self.assertEqual(e.error_code,"audio_control_unavailable");self.assertEqual(e.user_message,"Управление звуком сейчас недоступно.")
        raw=json.dumps(e.to_payload(),ensure_ascii=False)
        for word in ["RAW PRIVATE DETAIL","UNTRUSTED MESSAGE","DO NOT FORWARD","secret"]:self.assertNotIn(word,raw)
        self.assertEqual(h,[])

    def test_failed_is_bounded(self):
        def change(i,d):raise fail_audio(i,"audio_control_failed")
        _,p,_,h=build(change=change)
        with self.assertRaises(ActionExecutionError) as ctx:p.execute(prepare(p,"VOLUME_DOWN"))
        self.assertEqual(ctx.exception.error_code,"audio_control_failed");self.assertEqual(h,[])

    def test_invalid_request_from_trusted_callback_is_internal(self):
        def change(i,d):raise fail_audio(i,"audio_control_invalid_request")
        _,p,_,_=build(change=change)
        with self.assertRaises(ActionExecutionError) as ctx:p.execute(prepare(p))
        self.assertEqual(ctx.exception.error_code,"volume_action_internal_error")

    def test_unexpected_structured_error_is_bounded(self):
        def change(i,d):raise fail_audio(i,"audio_control_unexpected_error")
        _,p,_,_=build(change=change)
        with self.assertRaises(ActionExecutionError) as ctx:p.execute(prepare(p))
        self.assertEqual(ctx.exception.error_code,"audio_control_unexpected_error")

    def test_wrong_intent_cannot_borrow_failure(self):
        def change(i,d):raise fail_audio("VOLUME_DOWN","audio_control_unavailable")
        _,p,_,_=build(change=change);r,f=model._dispatch(p._state,prepare(p).request)
        self.assertIs(r.status,ActionStatus.FAILED);self.assertIs(f,model.FailureKind.UNCLASSIFIED)

    def test_wrong_operation_is_unclassified(self):
        def change(i,d):raise fail_audio(i,"audio_control_unavailable","unsafe")
        _,p,_,_=build(change=change);r,f=model._dispatch(p._state,prepare(p).request)
        self.assertIs(r.status,ActionStatus.FAILED);self.assertIs(f,model.FailureKind.UNCLASSIFIED)

    def test_exception_subclass_becomes_unknown(self):
        class Child(ActionExecutionError):pass
        def change(i,d):raise Child(intent=i,operation="audio_control.change_volume",detail="x")
        _,p,_,_=build(change=change);r,f=model._dispatch(p._state,prepare(p).request)
        self.assertIs(r.status,ActionStatus.UNKNOWN);self.assertIsNone(f)

    def test_unexpected_exception_after_effect_unknown_no_retry(self):
        effects=[]
        def change(i,d):effects.append((i,d));raise RuntimeError("SECRET")
        _,p,_,h=build(change=change);plan=prepare(p);r,f=model._dispatch(p._state,plan.request)
        self.assertIs(r.status,ActionStatus.UNKNOWN);self.assertIs(r.effect,EffectState.MAY_HAVE_OCCURRED);self.assertEqual(effects,[("VOLUME_UP",10)]);self.assertEqual(h,[])
        replay,_=model._dispatch(p._state,plan.request);self.assertIs(replay.status,ActionStatus.DENIED);self.assertEqual(len(effects),1)

    def test_invalid_observed_shape_is_unknown(self):
        _,p,_,_=build(change=lambda i,d:{"volume":50});r,_=model._dispatch(p._state,prepare(p).request)
        self.assertIs(r.status,ActionStatus.UNKNOWN)

    def test_invalid_observed_types_are_unknown(self):
        for value in [(True,False),(50,1),(101,False),(-1,False),(50.0,False)]:
            with self.subTest(value=value):
                _,p,_,_=build(change=lambda i,d,v=value:v);r,_=model._dispatch(p._state,prepare(p).request);self.assertIs(r.status,ActionStatus.UNKNOWN)

    def test_history_failure_does_not_repeat_audio(self):
        calls=[]
        def change(i,d):calls.append((i,d));return (60,False)
        def remember(i):raise RuntimeError("history secret")
        _,p,_,_=build(change=change,remember=remember)
        with self.assertRaises(ActionExecutionError) as ctx:p.execute(prepare(p))
        self.assertEqual(ctx.exception.error_code,"volume_history_commit_failed");self.assertEqual(calls,[("VOLUME_UP",10)])
        self.assertNotIn("history secret",json.dumps(ctx.exception.to_payload(),ensure_ascii=False))

    def test_closed_port_blocks_future_effect(self):
        o,p,c,h=build();o.close()
        with self.assertRaises(ActionContractError):p.prepare(intent="VOLUME_UP",slots={})
        self.assertEqual(c,[]);self.assertEqual(h,[])

    def test_close_after_prepare_blocks_dispatch(self):
        o,p,c,h=build();plan=prepare(p);o.close()
        with self.assertRaises(ActionExecutionError):p.execute(plan)
        self.assertEqual(c,[]);self.assertEqual(h,[])

    def test_reentrant_call_is_refused(self):
        nested=[]; holder={}
        def change(i,d):
            try:holder['p'].execute(prepare(holder['p']))
            except ActionExecutionError as e:nested.append(e.error_code)
            return (55,False)
        _,p,c,h=build(change=change);holder['p']=p;p.execute(prepare(p))
        self.assertEqual(nested,["volume_action_denied"]);self.assertEqual(h,["VOLUME_UP"])

    def test_concurrent_attempt_refused(self):
        entered=threading.Event();release=threading.Event();errors=[]
        def change(i,d):entered.set();release.wait(2);return (55,False)
        _,p,_,h=build(change=change);plan1=prepare(p);plan2=prepare(p,"VOLUME_DOWN")
        t=threading.Thread(target=lambda:p.execute(plan1));t.start();self.assertTrue(entered.wait(1))
        try:p.execute(plan2)
        except ActionExecutionError as e:errors.append(e.error_code)
        release.set();t.join(2)
        self.assertEqual(errors,["volume_action_denied"]);self.assertEqual(h,["VOLUME_UP"])

    def test_capability_not_pickleable_or_copyable(self):
        import copy as cp
        o,p,_,_=build()
        for obj in [o,p]:
            with self.assertRaises(TypeError):cp.copy(obj)
            with self.assertRaises(TypeError):cp.deepcopy(obj)
            with self.assertRaises(TypeError):pickle.dumps(obj)

    def test_executor_and_verifier_do_not_hold_issuer(self):
        _,p,_,_=build();bindings=p._state.issuer._domain.bindings
        for b in bindings:
            self.assertFalse(hasattr(b.executor,"issuer"));self.assertFalse(hasattr(b.verifier,"issuer"))

    def test_policy_mentions_current_default_endpoint_refresh(self):
        _,p,_,_=build();self.assertTrue(all("current-default-endpoint-refresh" in s.policy_revision for s in p._state.specs))

    def test_audio_control_internal_retry_is_inside_one_adapter_dispatch(self):
        class Endpoint:
            def __init__(self,volume,fail=False):self.volume=volume;self.fail=fail;self.set_calls=[]
            def GetMasterVolumeLevelScalar(self):return self.volume/100.0
            def GetMute(self):return 0
            def SetMasterVolumeLevelScalar(self,value,_):
                self.set_calls.append(round(value*100))
                if self.fail:raise RuntimeError("first endpoint failed")
                self.volume=round(value*100);return 0
        first=Endpoint(40,True);second=Endpoint(70,False);providers=[]
        seq=[AudioEndpointBinding(object(),first,"a","A"),AudioEndpointBinding(object(),second,"b","B")]
        def provider():providers.append(1);return seq[min(len(providers)-1,1)]
        audio=AudioControl(endpoint_provider=provider,retry_delay_sec=0,validate_on_init=False)
        adapter=[]
        def change(i,d):adapter.append((i,d));state=audio.change_volume(d);return state.volume,state.muted
        _,p,_,h=build(step=10,change=change);p.execute(prepare(p))
        self.assertEqual(adapter,[("VOLUME_UP",10)]);self.assertEqual(len(providers),2)
        self.assertEqual(first.set_calls,[50]);self.assertEqual(second.set_calls,[80]);self.assertEqual(h,["VOLUME_UP"])


class _FakeLogger:
    def __init__(self,events):self.events=events;self.payloads=[]
    def event(self,k,p):self.events.append("log:"+k);self.payloads.append((k,p))
    def inbox(self,t,m):self.events.append("inbox")
class _FakeLearning:
    def __init__(self,e):self.events=e
    def log_action_failure(self,**kw):self.events.append("learning:action_failure")
    def log_nlu_hard_case(self,**kw):self.events.append("learning:nlu")
class _FakeRouter:
    def __init__(self,e):self.events=e
    def reply(self,m):return "ROUTER"
    def execute(self,m):self.events.append("router_execute:"+str(m.get("intent")))
class _DummyMode:
    def set_pending_confirmation(self,p):raise AssertionError
    def enter_dictation_mode(self):raise AssertionError
    def exit_dictation_mode(self):raise AssertionError
    def close_command_window(self):raise AssertionError
class _Dummy:pass


def runtime_case(*,intent="VOLUME_UP",volume_actions=None,mutate_reply=None,fail_tts=False):
    events=[];meta={"intent":intent,"confidence":1.0,"slots":{}}
    d=build_command_decision(meta,accept_conf=.35);o=classify_command_outcome(meta,d)
    def reply(m):
        events.append("reply:"+intent)
        if mutate_reply:mutate_reply(m)
        return "OK"
    def say(s,t,text,**kw):
        events.append("say:"+text)
        if fail_tts:raise RuntimeError("tts failure")
        return 1.0
    r=handle_command_runtime(raw_text="x",final_text="x",meta=meta,decision=d,outcome=o,
        learning_memory=_FakeLearning(events),logger=_FakeLogger(events),router=_FakeRouter(events),mode_manager=_DummyMode(),
        stt=_Dummy(),tts=_Dummy(),say_func=say,say_interruptible_func=lambda t,x:2.0,reply_text_func=reply,
        current_mode_name_func=lambda:"direct",cancel_cmd_timer_func=lambda:None,volume_actions=volume_actions)
    return r,events


class CommandRuntimeTests(unittest.TestCase):
    def test_volume_runs_after_success_tts_without_router(self):
        events=[]
        _,p,_,_=build(change=lambda i,d:(events.append("audio") or (55,False)),remember=lambda i:events.append("history"))
        r,ev=runtime_case(volume_actions=p);self.assertEqual(r.reason,"executed")
        self.assertEqual(ev,["reply:VOLUME_UP","say:OK"]);self.assertEqual(events,["audio","history"])

    def test_volume_failure_has_no_router_fallback(self):
        _,p,_,h=build(change=lambda i,d:(_ for _ in ()).throw(fail_audio(i)))
        r,ev=runtime_case(volume_actions=p);self.assertEqual(r.reason,"action_failed");self.assertFalse(any(x.startswith("router_execute") for x in ev));self.assertEqual(h,[])

    def test_volume_none_port_preserves_legacy_router(self):
        r,ev=runtime_case(volume_actions=None);self.assertEqual(r.reason,"executed");self.assertEqual(ev,["reply:VOLUME_UP","say:OK","router_execute:VOLUME_UP"])

    def test_prepare_before_reply_meta_mutation(self):
        _,p,c,h=build(step=8)
        r,ev=runtime_case(volume_actions=p,mutate_reply=lambda m:m.update(intent="VOLUME_DOWN"));self.assertEqual(r.reason,"executed")
        self.assertEqual(c,[("VOLUME_UP",8)]);self.assertEqual(h,["VOLUME_UP"])

    def test_tts_failure_before_dispatch_has_no_effect_or_history(self):
        _,p,c,h=build()
        with self.assertRaises(RuntimeError):runtime_case(volume_actions=p,fail_tts=True)
        self.assertEqual(c,[]);self.assertEqual(h,[]);self.assertEqual(p._state.issuer._domain.issued,set())

    def test_history_failure_is_action_failed_after_success_tts(self):
        calls=[]
        _,p,_,_=build(change=lambda i,d:(calls.append((i,d)) or (55,False)),remember=lambda i:(_ for _ in ()).throw(RuntimeError("x")))
        r,ev=runtime_case(volume_actions=p);self.assertEqual(r.reason,"action_failed");self.assertEqual(calls,[("VOLUME_UP",10)])
        self.assertEqual(ev[0:2],["reply:VOLUME_UP","say:OK"]);self.assertFalse(any(x.startswith("router_execute") for x in ev))

    def test_down_uses_port(self):
        _,p,c,h=build();r,ev=runtime_case(intent="VOLUME_DOWN",volume_actions=p)
        self.assertEqual(c,[("VOLUME_DOWN",-10)]);self.assertEqual(h,["VOLUME_DOWN"]);self.assertFalse(any(x.startswith("router_execute") for x in ev))


class RouterRepeatTests(unittest.TestCase):
    class A:
        def handle(self,m):return "ok"
        def execute(self,m):pass
    def router(self):return Router(self.A(),settings=SimpleNamespace(exec_mode="direct",repeat_context_sec=60.0))

    def test_boundary_history_sink_only_allows_pair(self):
        r=self.router();r.remember_boundary_volume_success("VOLUME_UP")
        self.assertEqual(r.preprocess({"intent":None,"slots":{},"_text":"ещё"})["intent"],"VOLUME_UP")
        for intent in ["MUTE","SET_VOLUME","",None]:
            with self.subTest(intent=intent),self.assertRaises((ValueError,TypeError)):r.remember_boundary_volume_success(intent)

    def test_generic_repeat_uses_minimal_record(self):
        r=self.router();r.remember_boundary_volume_success("VOLUME_DOWN")
        m=r.preprocess({"intent":None,"confidence":0.1,"slots":{"junk":1},"_text":"повтори"})
        self.assertEqual(m["intent"],"VOLUME_DOWN");self.assertEqual(m["slots"],{});self.assertTrue(m["_from_history"]);self.assertEqual(m["confidence"],1.0)

    def test_repeat_variant_does_not_need_history(self):
        r=self.router();m=r.preprocess({"intent":None,"confidence":0.0,"slots":{},"_text":"ещё громче"})
        self.assertEqual(m["intent"],"VOLUME_UP");self.assertTrue(m["_from_repeat_variant"])
        n=r.preprocess({"intent":None,"confidence":0.0,"slots":{},"_text":"ещё тише"});self.assertEqual(n["intent"],"VOLUME_DOWN")

    def test_failed_attempt_cannot_enter_history_via_port(self):
        r=self.router();_,p,_,_=build(change=lambda i,d:(_ for _ in ()).throw(fail_audio(i)),remember=r.remember_boundary_volume_success)
        with self.assertRaises(ActionExecutionError):p.execute(prepare(p))
        m=r.preprocess({"intent":None,"confidence":0.0,"slots":{},"_text":"ещё"});self.assertTrue(m["_repeat_failed"])

    def test_success_then_generic_repeat_gets_new_request(self):
        r=self.router();_,p,c,_=build(remember=r.remember_boundary_volume_success);one=prepare(p);p.execute(one)
        m=r.preprocess({"intent":None,"confidence":0.0,"slots":{},"_text":"ещё"});two=p.prepare(intent=m["intent"],slots=m["slots"])
        self.assertNotEqual(one.request.request_id,two.request.request_id);p.execute(two);self.assertEqual(len(c),2)


class SourceTopologyTests(unittest.TestCase):
    def test_preserved_production_sources(self):
        expected={
            "modules/actions.py":"dfdc9c8fd6acb5d239868c9dcb0ef9cc460bf346bf23f3d0715913940fcc1661",
            "modules/audio_control.py":"bcaa2f8dd54be259f55530e194c2fd2db308016bd4c59a6ae5d2a776027c6311",
            "modules/media_control.py":"80a8898fb4e362271bf58ed19d77fcf5803fc95d3a0880ff898d7d7fa577a8de",
            "modules/dialog_state.py":"ba12b4ca1f0fee12e98c5815cab3ed7b084603337046774c8fd1206d4b0b55ca",
            "modules/timer_action_runtime.py":"82eca7935aad4f9410309ec9f1574d44ff44e432d618e39dfaa47148d58741b8",
            "modules/action_contract.py":"f342508bcda04842a04267cbadc39b59b4b468ca45d348a0e8351f2b4016c64a",
            "modules/action_authority.py":"0103888d91c03b4efa536a2fa8cdb741effe5f2a80f434276c74aaa74b96c87e",
            "modules/action_broker.py":"fa3c1978fb7d19af4082a9407e45a80d946c9698cc6a30a0cd1377220dee3125",
        }
        for rel,sha in expected.items():
            with self.subTest(path=rel):self.assertEqual(hashlib.sha256((PROJECT_ROOT/rel).read_bytes()).hexdigest(),sha)

    def test_volume_runtime_import_allowlist(self):
        allowed={"__future__","dataclasses","enum","os","threading","uuid","typing","modules.action_contract","modules.action_authority","modules.action_broker","modules.action_error"}
        t=ast.parse((PROJECT_ROOT/"modules/volume_action_runtime.py").read_text())
        actual=set()
        for n in ast.walk(t):
            if isinstance(n,ast.Import):actual.update(a.name for a in n.names)
            elif isinstance(n,ast.ImportFrom):actual.add(n.module)
        self.assertEqual(actual,allowed)

    def test_no_native_imports(self):
        for p in (PROJECT_ROOT/"modules").rglob("*.py"):
            t=ast.parse(p.read_text(encoding="utf-8-sig"))
            for n in ast.walk(t):
                names=[]
                if isinstance(n,ast.Import):names=[a.name for a in n.names]
                elif isinstance(n,ast.ImportFrom):names=[n.module or ""]
                self.assertFalse(any(x=="native" or x.startswith("native.") for x in names),str(p))

    def test_command_runtime_migration_allowlists(self):
        import modules.command_runtime as cr
        self.assertEqual(cr.HWA02B1_TIMER_INTENTS,frozenset({"SET_TIMER","CANCEL_TIMER"}))
        self.assertEqual(cr.HWA02B2_VOLUME_INTENTS,frozenset({"VOLUME_UP","VOLUME_DOWN"}))

    def test_main_wires_volume_once_and_no_general_actions_execute(self):
        text=(PROJECT_ROOT/"main.py").read_text(encoding="utf-8-sig");tree=ast.parse(text)
        imports=[n for n in ast.walk(tree) if isinstance(n,ast.ImportFrom) and n.module=="modules.volume_action_runtime"]
        self.assertEqual(len(imports),1)
        calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=="compose_volume_action_runtime"]
        self.assertEqual(len(calls),1);self.assertIn("volume_change_handler = actions._execute_audio_control",text)
        self.assertIn("remember_volume_success=router.remember_boundary_volume_success",text)
        self.assertIn("volume_action_owner.close()",text)

    def test_command_processor_passes_volume_port(self):
        t=ast.parse((PROJECT_ROOT/"modules/command_processor.py").read_text())
        init=next(n for n in ast.walk(t) if isinstance(n,ast.FunctionDef) and n.name=="__init__")
        self.assertIn("volume_actions",[a.arg for a in init.args.kwonlyargs])
        proc=next(n for n in ast.walk(t) if isinstance(n,ast.FunctionDef) and n.name=="process")
        call=next(n for n in ast.walk(proc) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=="handle_command_runtime")
        kws={k.arg:ast.unparse(k.value) for k in call.keywords};self.assertEqual(kws["volume_actions"],"self._volume_actions")


class CountedResult(unittest.TextTestResult):
    def __init__(self,*a,**kw):super().__init__(*a,**kw);self.subtests=0
    def addSubTest(self,test,subtest,err):self.subtests+=1;return super().addSubTest(test,subtest,err)


def main()->int:
    suite=unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]);discovered=suite.countTestCases();expected=EXPECTED_TESTS or discovered
    result=unittest.TextTestRunner(stream=sys.stdout,verbosity=2,resultclass=CountedResult).run(suite)
    ok=result.wasSuccessful() and result.testsRun==expected and not result.skipped
    summary={"kind":"HWA02B2_VOLUME_ACTION_RUNTIME_EVAL_V1","result":"PASS" if ok else "FAIL","tests_run":result.testsRun,"expected_tests":expected,"discovered_tests":discovered,"subtests":result.subtests,"failures":len(result.failures),"errors":len(result.errors),"skipped":len(result.skipped),"runtime_wired":True,"migrated_actions":["VOLUME_UP","VOLUME_DOWN"],"real_audio_changed":False,"native_execution_authorized":False,"host_worker_launched":False}
    print("\n=== HWA02-B2 SUMMARY ===");print(json.dumps(summary,ensure_ascii=False,sort_keys=True));return 0 if ok else 1

if __name__=="__main__":raise SystemExit(main())
