"""HWA02-B1 portable timer runtime bridge and command-runtime acceptance.

No real TimerService, native worker, Sandbox, network, subprocess, or host UI
effect is used. Timer callbacks are injected in memory.
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
from unittest.mock import patch
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import modules.timer_action_runtime as model
from modules.action_contract import (
    ActionRequest, ActionStatus, ActionResult, EffectState, ActionContractError,
    VerificationStatus, ExecutorOutcome, ExecutorStatus,
)
from modules.action_error import ActionExecutionError
from modules.action_broker import ActionBroker
import modules.action_authority as authority
from modules.command_decision import build_command_decision
from modules.command_outcome import classify_command_outcome
from modules.command_runtime import handle_command_runtime

EXPECTED_TESTS = 56


def _stable_ast_dump(node: ast.AST) -> str:
    """Cross-version AST dump with empty fields included on Python 3.13+.

    CPython 3.12 ast.dump includes empty/None fields by default. CPython 3.13
    changed the default to omit them unless show_empty=True. This helper keeps
    the topology fingerprint stable across both versions.
    """
    try:
        return ast.dump(
            node,
            annotate_fields=True,
            include_attributes=False,
            show_empty=True,
        )
    except TypeError:
        return ast.dump(
            node,
            annotate_fields=True,
            include_attributes=False,
        )

def fail_unavailable(intent='SET_TIMER', **kw):
    fields = dict(intent=intent, operation='timer.start' if intent=='SET_TIMER' else 'timer.cancel',
                  detail='RAW PRIVATE DETAIL', user_message='UNTRUSTED MESSAGE',
                  error_code='timer_unavailable', context={'secret': 'DO NOT FORWARD'})
    fields.update(kw)
    return ActionExecutionError(**fields)


def build(start=None, cancel=None):
    calls=[]
    owner, port = model.compose_timer_action_runtime(
        start_timer=start if start is not None else lambda n: calls.append(('set',n)),
        cancel_timer=cancel if cancel is not None else lambda: calls.append(('cancel',)),
    )
    return owner, port, calls


def prepare(port, intent='SET_TIMER', n=60):
    return port.prepare(intent=intent, slots={'duration_seconds':n} if intent=='SET_TIMER' else {})


class ReceiptModelTests(unittest.TestCase):
    def test_prepare_is_not_dispatch_or_issuance(self):
        _,p,c=build(); prepare(p)
        self.assertEqual(c,[]); self.assertEqual(p._state.issuer._domain.issued,set())

    def test_prepare_freezes_value_before_reply_mutation(self):
        _,p,c=build(); slots={'duration_seconds':60}
        r=p.prepare(intent='SET_TIMER',slots=slots); slots['duration_seconds']=300
        p.execute(r); self.assertEqual(c,[('set',60)])

    def test_timer_bounds_and_exact_type(self):
        _,p,c=build()
        for v in [True,False,0,-1,86401,60.0,'60',None,2**90]:
            with self.subTest(value=v), self.assertRaises(ActionContractError): prepare(p,n=v)
        self.assertEqual(c,[])

    def test_valid_edge_durations(self):
        _,p,c=build(); p.execute(prepare(p,n=1));p.execute(prepare(p,n=86400))
        self.assertEqual(c,[('set',1),('set',86400)])

    def test_extra_slots_not_permits(self):
        _,p,_=build()
        for slots in [{'approved':True},{'duration_seconds':60,'authorized':True}]:
            with self.subTest(slots=slots), self.assertRaises(ActionContractError):
                p.prepare(intent='SET_TIMER', slots=slots)
        with self.assertRaises(ActionContractError):p.prepare(intent='CANCEL_TIMER',slots={'duration_seconds':60})

    def test_only_timer_pair_supported(self):
        _,p,_=build()
        for name in ['EMPTY_RECYCLE_BIN','VOLUME_UP','CREATE_REMINDER','TIMER_STATUS','set_timer','SET_TIMER ']:
            with self.subTest(intent=name), self.assertRaises(ActionContractError):
                p.prepare(intent=name,slots={})

    def test_one_set_callback_and_empty_verified_output(self):
        _,p,c=build(); result,d=model._dispatch(p._state,prepare(p))
        self.assertEqual(c,[('set',60)]);self.assertIs(result.status,ActionStatus.SUCCEEDED)
        self.assertEqual(result.output,());self.assertIsNone(d)
        self.assertIsNone(p._state.box.active)

    def test_one_cancel_callback(self):
        _,p,c=build(); p.execute(prepare(p,'CANCEL_TIMER'))
        self.assertEqual(c,[('cancel',)])

    def test_same_request_replay_refused(self):
        _,p,c=build();r=prepare(p);p.execute(r)
        result,d=model._dispatch(p._state,r)
        self.assertIs(result.status,ActionStatus.DENIED);self.assertIsNone(d)
        self.assertEqual(c,[('set',60)])

    def test_reconstructed_request_not_new_authority(self):
        _,p,c=build();r=prepare(p);p.execute(r)
        clone=ActionRequest.from_bytes(r.to_bytes());res,_=model._dispatch(p._state,clone)
        self.assertIs(res.status,ActionStatus.DENIED);self.assertEqual(len(c),1)

    def test_other_composition_scope_refused(self):
        _,p,_=build();_,q,c=build();res,_=model._dispatch(q._state,prepare(p))
        self.assertIs(res.status,ActionStatus.DENIED);self.assertEqual(c,[])

    def test_issued_id_cannot_rebind_duration(self):
        _,p,c=build();r=prepare(p);p.execute(r)
        other=dataclasses.replace(r,parameters=(('duration_seconds',70),))
        res,_=model._dispatch(p._state,other)
        self.assertIs(res.status,ActionStatus.DENIED);self.assertEqual(c,[('set',60)])

    def test_failure_receipt_supplements_failed_without_output(self):
        def start(n):raise fail_unavailable()
        _,p,_=build(start=start);res,d=model._dispatch(p._state,prepare(p))
        self.assertIs(res.status,ActionStatus.FAILED);self.assertEqual(res.output,())
        self.assertIs(res.effect,EffectState.MAY_HAVE_OCCURRED);self.assertIs(d,model.FailureKind.UNAVAILABLE)
        self.assertIsNone(p._state.box.active)

    def test_public_failure_is_fixed_message_no_raw_exception(self):
        def start(n):raise fail_unavailable()
        _,p,_=build(start=start)
        with self.assertRaises(ActionExecutionError) as ctx:p.execute(prepare(p))
        e=ctx.exception;self.assertEqual(e.error_code,'timer_unavailable')
        self.assertEqual(e.user_message,'Таймер сейчас недоступен.')
        encoded=json.dumps(e.to_payload(),ensure_ascii=False)
        for forbidden in ['RAW PRIVATE DETAIL','UNTRUSTED MESSAGE','DO NOT FORWARD','secret']:
            self.assertNotIn(forbidden,encoded)
        self.assertIsNone(e.__context__)

    def test_fixture_cancel_error_retains_safe_code_and_message(self):
        def cancel():raise ActionExecutionError(intent='CANCEL_TIMER',operation='cancel_timer',
            detail='fake timer failure',user_message='DO NOT COPY',error_code='timer_cancel_failed')
        _,p,_=build(cancel=cancel)
        with self.assertRaises(ActionExecutionError) as ctx:p.execute(prepare(p,'CANCEL_TIMER'))
        self.assertEqual(ctx.exception.error_code,'timer_cancel_failed')
        self.assertEqual(ctx.exception.user_message,'Не получилось отменить таймер.')
        self.assertEqual(ctx.exception.operation,'timer.cancel')

    def test_wrong_intent_cannot_borrow_failure_catalogue(self):
        def start(n):raise fail_unavailable(intent='CANCEL_TIMER')
        _,p,_=build(start=start);res,d=model._dispatch(p._state,prepare(p))
        self.assertIs(res.status,ActionStatus.FAILED);self.assertIs(d,model.FailureKind.UNCLASSIFIED)

    def test_unrecognised_structured_error_is_generic(self):
        def start(n):raise fail_unavailable(error_code='new_code',operation='unsafe.new',user_message='SECRET')
        _,p,_=build(start=start)
        with self.assertRaises(ActionExecutionError) as ctx:p.execute(prepare(p))
        self.assertEqual(ctx.exception.error_code,'action_failed');self.assertNotIn('SECRET',ctx.exception.user_message)

    def test_exception_subclass_is_unknown(self):
        class Child(ActionExecutionError):pass
        def start(n):raise Child(intent='SET_TIMER',operation='timer.start',detail='x')
        _,p,_=build(start=start);res,d=model._dispatch(p._state,prepare(p))
        self.assertIs(res.status,ActionStatus.UNKNOWN);self.assertIsNone(d)

    def test_unexpected_exception_after_effect_is_unknown_no_retry(self):
        effects=[]
        def start(n):effects.append(n);raise RuntimeError('RAW SECRET')
        _,p,_=build(start=start);r=prepare(p);res,d=model._dispatch(p._state,r)
        self.assertIs(res.status,ActionStatus.UNKNOWN);self.assertIsNone(d)
        self.assertIs(res.effect,EffectState.MAY_HAVE_OCCURRED);self.assertEqual(effects,[60])
        replay,_=model._dispatch(p._state,r);self.assertIs(replay.status,ActionStatus.DENIED)
        self.assertEqual(effects,[60])

    def test_failed_receipt_does_not_override_execution_deadline(self):
        def start(n):raise fail_unavailable()
        _,p,_=build(start=start)
        with patch.object(authority.time,'monotonic_ns',side_effect=[0,1,2,2_000_000_000]):
            res,d=model._dispatch(p._state,prepare(p))
        self.assertIs(res.status,ActionStatus.UNKNOWN);self.assertEqual(res.code,'execution_deadline')
        self.assertIsNone(d);self.assertEqual(res.output,())

    def test_expiry_before_dispatch_calls_nothing(self):
        _,p,c=build();r=prepare(p)
        with patch.object(authority.time,'monotonic_ns',side_effect=[0,1,6_000_000_000]):
            res,d=model._dispatch(p._state,r)
        self.assertIs(res.status,ActionStatus.DENIED);self.assertIsNone(d);self.assertEqual(c,[])

    def test_failed_receipt_cannot_override_unknown(self):
        def start(n):raise fail_unavailable()
        _,p,_=build(start=start);r=prepare(p)
        original=ActionBroker.execute
        def replace_result(broker,req,grant):
            actual=original(broker,req,grant)
            # The actual broker source stays unchanged; the test only checks
            # receipt enrichment is never used for another terminal class.
            return ActionResult(ActionStatus.UNKNOWN,'verifier_exception',actual.request_fingerprint,
                                actual.policy_fingerprint,VerificationStatus.UNKNOWN,EffectState.MAY_HAVE_OCCURRED)
        with patch.object(ActionBroker,'execute',replace_result):res,d=model._dispatch(p._state,r)
        self.assertIs(res.status,ActionStatus.UNKNOWN);self.assertIsNone(d)

    def test_receipt_tag_mismatch_is_discarded(self):
        def start(n):raise fail_unavailable()
        old=model._Executor.execute
        def change(executor,r,*,deadline_ns):
            out=old(executor,r,deadline_ns=deadline_ns)
            a=executor.box.active;a.failure=dataclasses.replace(a.failure,attempt_tag=object())
            return out
        with patch.object(model._Executor,'execute',change):
            _,p,_=build(start=start)
            res,d=model._dispatch(p._state,prepare(p))
        self.assertIs(res.status,ActionStatus.FAILED);self.assertIsNone(d)

    def test_receipt_request_mismatch_is_discarded(self):
        def start(n):raise fail_unavailable()
        old=model._Executor.execute
        def change(executor,r,*,deadline_ns):
            out=old(executor,r,deadline_ns=deadline_ns)
            a=executor.box.active;a.failure=dataclasses.replace(a.failure,request_fp='a'*64)
            return out
        with patch.object(model._Executor,'execute',change):
            _,p,_=build(start=start)
            res,d=model._dispatch(p._state,prepare(p))
        self.assertIs(res.status,ActionStatus.FAILED);self.assertIsNone(d)

    def test_receipt_policy_mismatch_is_discarded(self):
        def start(n):raise fail_unavailable()
        old=model._Executor.execute
        def change(executor,r,*,deadline_ns):
            out=old(executor,r,deadline_ns=deadline_ns)
            a=executor.box.active;a.failure=dataclasses.replace(a.failure,policy_fp='b'*64)
            return out
        with patch.object(model._Executor,'execute',change):
            _,p,_=build(start=start)
            res,d=model._dispatch(p._state,prepare(p))
        self.assertIs(res.status,ActionStatus.FAILED);self.assertIsNone(d)

    def test_next_call_cannot_see_previous_failure(self):
        calls=[]
        def start(n):
            calls.append(n)
            if n==60:raise fail_unavailable()
        _,p,_=build(start=start);first,d=model._dispatch(p._state,prepare(p,n=60))
        second,d2=model._dispatch(p._state,prepare(p,n=61))
        self.assertIs(first.status,ActionStatus.FAILED);self.assertIs(second.status,ActionStatus.SUCCEEDED)
        self.assertIsNone(d2);self.assertIsNone(p._state.box.active);self.assertEqual(calls,[60,61])

    def test_unexpected_callback_return_not_success(self):
        _,p,_=build(start=lambda n: {'ok':True});res,d=model._dispatch(p._state,prepare(p))
        self.assertIs(res.status,ActionStatus.UNKNOWN);self.assertIsNone(d)

    def test_unrecorded_success_is_not_verified(self):
        with patch.object(model._Executor,'execute',return_value=ExecutorOutcome(ExecutorStatus.SUCCEEDED)):
            _,p,c=build()
            res,d=model._dispatch(p._state,prepare(p))
        self.assertIs(res.status,ActionStatus.UNKNOWN);self.assertEqual(res.code,'verification_not_accepted')
        self.assertEqual(c,[]);self.assertIsNone(d)

    def test_bound_executor_method_is_captured_at_composition(self):
        _,p,c=build()
        with patch.object(model._Executor, 'execute', side_effect=RuntimeError('not captured')):
            result,_=model._dispatch(p._state,prepare(p))
        self.assertIs(result.status,ActionStatus.SUCCEEDED)
        self.assertEqual(c,[('set',60)])

    def test_reentrant_call_refused_not_deadlocked(self):
        inner=[];p=None
        def start(n):inner.append(model._dispatch(p._state,prepare(p,'CANCEL_TIMER'))[0])
        _,p,_=build(start=start);res,_=model._dispatch(p._state,prepare(p))
        self.assertIs(res.status,ActionStatus.SUCCEEDED);self.assertEqual(inner[0].code,'timer_port_busy')

    def test_concurrent_attempt_refused_without_receipt_contamination(self):
        entered=threading.Event();release=threading.Event();results=[];calls=[]
        def start(n):
            calls.append(n);entered.set()
            if not release.wait(1):raise RuntimeError('test synchronisation timeout')
        _,p,_=build(start=start);r=prepare(p)
        thread=threading.Thread(target=lambda:results.append(model._dispatch(p._state,r)))
        thread.start()
        try:
            self.assertTrue(entered.wait(1))
            refused,d=model._dispatch(p._state,prepare(p,n=80))
            self.assertEqual(refused.code,'timer_port_busy');self.assertIsNone(d)
        finally:release.set();thread.join(2)
        self.assertFalse(thread.is_alive());self.assertEqual(calls,[60])
        self.assertIs(results[0][0].status,ActionStatus.SUCCEEDED)
        self.assertIsNone(p._state.box.active)

    def test_close_prevents_future_issue(self):
        owner,p,c=build();r=prepare(p);owner.close();owner.close()
        res,_=model._dispatch(p._state,r);self.assertIs(res.status,ActionStatus.DENIED)
        self.assertEqual(c,[])
        with self.assertRaises(ActionContractError):prepare(p)

    def test_close_is_not_rollback_of_started_callback(self):
        owner=None
        def start(n):owner.close()
        owner,p,_=build(start=start);res,_=model._dispatch(p._state,prepare(p))
        self.assertIs(res.status,ActionStatus.SUCCEEDED)
        self.assertTrue(p._state.closed.is_set())

    def test_capacity_does_not_recreate_authority(self):
        _,p,c=build();issuer=p._state.issuer
        with patch.object(authority,'MAX_ISSUED_REQUESTS',1):
            p.execute(prepare(p));res,_=model._dispatch(p._state,prepare(p,n=70))
        self.assertIs(res.status,ActionStatus.DENIED);self.assertIs(p._state.issuer,issuer);self.assertEqual(len(c),1)

    def test_foreign_pid_refused_before_lock(self):
        _,p,c=build();r=prepare(p);p._state.pid=-1
        p._state.gate.acquire()
        try:res,_=model._dispatch(p._state,r)
        finally:p._state.gate.release()
        self.assertEqual(res.code,'foreign_process');self.assertEqual(c,[])

    def test_control_objects_are_not_serialisable(self):
        owner,p,_=build()
        for value in [owner,p]:
            for f in [copy.copy,copy.deepcopy,pickle.dumps]:
                with self.subTest(type=type(value).__name__,func=f.__name__), self.assertRaises(TypeError):f(value)

    def test_executor_and_verifier_do_not_hold_issuer(self):
        _,p,_=build()
        for binding in p._state.issuer._domain.bindings:
            for obj in [binding.executor,binding.verifier]:
                self.assertFalse(hasattr(obj,'issuer'));self.assertFalse(hasattr(obj,'_state'))
        self.assertFalse(hasattr(p,'issue'));self.assertFalse(hasattr(p,'broker'))


class _FakeLogger:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.payloads: list[tuple[str, dict[str, Any]]] = []

    def event(self, kind: str, payload: dict[str, Any]) -> None:
        self.events.append(f"log:{kind}")
        self.payloads.append((kind, dict(payload)))

    def inbox(self, text: str, meta: Mapping[str, Any]) -> None:
        self.events.append("inbox")


class _FakeRouter:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def reply(self, meta: Mapping[str, Any]) -> str:
        intent = str(meta.get("intent") or "")
        self.events.append(f"router_reply:{intent}")
        return f"ROUTER:{intent}"

    def execute(self, meta: Mapping[str, Any]) -> None:
        intent = str(meta.get("intent") or "")
        self.events.append(f"router_execute:{intent}")


class _FakeLearning:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def log_action_failure(self, **kwargs: Any) -> None:
        self.events.append("learning:action_failure")

    def log_nlu_hard_case(self, **kwargs: Any) -> None:
        self.events.append("learning:nlu_hard_case")


class _DummyMode:
    def set_pending_confirmation(self, payload: dict[str, Any]) -> None:
        raise AssertionError("confirmation not expected")
    def enter_dictation_mode(self) -> None:
        raise AssertionError("dictation not expected")
    def exit_dictation_mode(self) -> None:
        raise AssertionError("dictation not expected")
    def close_command_window(self) -> None:
        raise AssertionError("command close not expected")


class _Dummy:
    pass


def _runtime_case(*, intent: str, slots: dict[str, Any], timer_actions=None,
                  start=None, cancel=None, mutate_reply=None):
    events: list[str] = []
    calls: list[tuple[Any, ...]] = []
    owner = None
    port = timer_actions
    if port is None and (start is not None or cancel is not None):
        owner, port = model.compose_timer_action_runtime(
            start_timer=start if start is not None else lambda n: calls.append(("set", n)),
            cancel_timer=cancel if cancel is not None else lambda: calls.append(("cancel",)),
        )
    meta = {"intent": intent, "confidence": 1.0, "slots": slots}
    decision = build_command_decision(meta, accept_conf=0.35)
    outcome = classify_command_outcome(meta, decision)
    logger = _FakeLogger(events)
    router = _FakeRouter(events)
    learning = _FakeLearning(events)

    def reply(value: Mapping[str, Any]) -> str:
        events.append(f"reply:{intent}")
        if mutate_reply is not None:
            mutate_reply(value)
        return f"REPLY:{intent}"

    def say(stt, tts, text: str, *, mute_stt: bool = True) -> float:
        events.append(f"say:{text}")
        return 100.0

    result = handle_command_runtime(
        raw_text="test",
        final_text="test",
        meta=meta,
        decision=decision,
        outcome=outcome,
        learning_memory=learning,
        logger=logger,
        router=router,
        mode_manager=_DummyMode(),
        stt=_Dummy(),
        tts=_Dummy(),
        say_func=say,
        say_interruptible_func=lambda tts, text: 200.0,
        reply_text_func=reply,
        current_mode_name_func=lambda: "direct",
        cancel_cmd_timer_func=lambda: None,
        timer_actions=port,
    )
    return owner, port, result, events, calls, logger


class CommandRuntimeIntegrationTests(unittest.TestCase):
    def test_set_timer_uses_port_not_router_and_stays_pre_speech(self):
        events=[]
        owner, port = model.compose_timer_action_runtime(
            start_timer=lambda n: events.append(f"callback:{n}"), cancel_timer=lambda: None)
        meta={"intent":"SET_TIMER","confidence":1.0,"slots":{"duration_seconds":30}}
        decision=build_command_decision(meta,accept_conf=0.35); outcome=classify_command_outcome(meta,decision)
        router=_FakeRouter(events)
        result=handle_command_runtime(raw_text="x",final_text="x",meta=meta,decision=decision,outcome=outcome,
            learning_memory=_FakeLearning(events),logger=_FakeLogger(events),router=router,mode_manager=_DummyMode(),
            stt=_Dummy(),tts=_Dummy(),say_func=lambda s,t,text,**kw:(events.append(f"say:{text}") or 1.0),
            say_interruptible_func=lambda t,text:2.0,reply_text_func=lambda m:(events.append("reply") or "OK"),
            current_mode_name_func=lambda:"direct",cancel_cmd_timer_func=lambda:None,timer_actions=port)
        self.assertEqual(result.reason,"executed")
        self.assertEqual(events,["reply","callback:30","say:OK"])

    def test_cancel_timer_uses_port_not_router(self):
        events=[]
        owner,port=model.compose_timer_action_runtime(start_timer=lambda n:None,cancel_timer=lambda:events.append("callback:cancel"))
        meta={"intent":"CANCEL_TIMER","confidence":1.0,"slots":{}}
        d=build_command_decision(meta,accept_conf=0.35);o=classify_command_outcome(meta,d)
        r=handle_command_runtime(raw_text="x",final_text="x",meta=meta,decision=d,outcome=o,
            learning_memory=_FakeLearning(events),logger=_FakeLogger(events),router=_FakeRouter(events),mode_manager=_DummyMode(),
            stt=_Dummy(),tts=_Dummy(),say_func=lambda s,t,text,**kw:(events.append("say") or 1.0),
            say_interruptible_func=lambda t,text:2.0,reply_text_func=lambda m:(events.append("reply") or "OK"),
            current_mode_name_func=lambda:"direct",cancel_cmd_timer_func=lambda:None,timer_actions=port)
        self.assertEqual(r.reason,"executed");self.assertEqual(events,["reply","callback:cancel","say"])

    def test_none_port_preserves_legacy_set_timer_router_path(self):
        _,_,r,events,_,_= _runtime_case(intent="SET_TIMER",slots={"duration_seconds":30},timer_actions=None)
        self.assertEqual(r.reason,"executed")
        self.assertEqual(events,["reply:SET_TIMER","router_execute:SET_TIMER","say:REPLY:SET_TIMER"])

    def test_reminder_stays_legacy_pre_speech_with_timer_port_present(self):
        owner,port,_=build()
        _,_,r,events,_,_= _runtime_case(
            intent="CREATE_REMINDER",
            slots={"due_at_epoch": 2000000000.0, "reminder_text": "test"},
            timer_actions=port,
        )
        self.assertEqual(r.reason,"executed")
        self.assertEqual(events,["reply:CREATE_REMINDER","router_execute:CREATE_REMINDER","say:REPLY:CREATE_REMINDER"])

    def test_normal_action_stays_say_then_router(self):
        owner,port,_=build()
        _,_,r,events,_,_= _runtime_case(intent="OPEN_URL",slots={"url":"https://example.com"},timer_actions=port)
        self.assertEqual(r.reason,"executed")
        self.assertEqual(events,["reply:OPEN_URL","say:REPLY:OPEN_URL","router_execute:OPEN_URL"])

    def test_timer_failure_uses_existing_action_failed_path_without_success_tts(self):
        def fail(n): raise fail_unavailable()
        owner,port,_=build(start=fail)
        _,_,r,events,_,logger=_runtime_case(intent="SET_TIMER",slots={"duration_seconds":30},timer_actions=port)
        self.assertEqual(r.reason,"action_failed")
        self.assertNotIn("router_execute:SET_TIMER",events)
        self.assertNotIn("say:REPLY:SET_TIMER",events)
        self.assertIn("say:Таймер сейчас недоступен.",events)
        payload=dict(logger.payloads)["command_action_failed"]
        self.assertEqual(payload["error_code"],"timer_unavailable")

    def test_unexpected_exception_is_unknown_and_not_retried(self):
        calls=[]
        def start(n): calls.append(n); raise RuntimeError("SECRET")
        owner,port,_=build(start=start)
        _,_,r,events,_,logger=_runtime_case(intent="SET_TIMER",slots={"duration_seconds":30},timer_actions=port)
        self.assertEqual(r.reason,"action_failed");self.assertEqual(calls,[30])
        payload=dict(logger.payloads)["command_action_failed"]
        self.assertEqual(payload["error_code"],"timer_action_unknown")
        self.assertNotIn("SECRET",json.dumps(payload,ensure_ascii=False))

    def test_prepare_happens_before_reply_mutates_slots(self):
        calls=[]
        owner,port,_=build(start=lambda n:calls.append(n))
        def mutate(value): value["slots"]["duration_seconds"]=300
        _,_,r,events,_,_=_runtime_case(intent="SET_TIMER",slots={"duration_seconds":60},timer_actions=port,mutate_reply=mutate)
        self.assertEqual(r.reason,"executed");self.assertEqual(calls,[60])

    def test_invalid_duration_is_fail_closed_without_router_execution(self):
        owner,port,_=build()
        _,_,r,events,_,_=_runtime_case(intent="SET_TIMER",slots={"duration_seconds":"60"},timer_actions=port)
        self.assertEqual(r.reason,"action_failed")
        self.assertNotIn("router_execute:SET_TIMER",events)
        self.assertFalse(any(x == "say:REPLY:SET_TIMER" for x in events))

    def test_closed_port_is_fail_closed_without_legacy_fallback(self):
        owner,port,_=build();owner.close()
        _,_,r,events,_,_=_runtime_case(intent="CANCEL_TIMER",slots={},timer_actions=port)
        self.assertEqual(r.reason,"action_failed")
        self.assertNotIn("router_execute:CANCEL_TIMER",events)


class SourceTopologyTests(unittest.TestCase):
    def test_hwa02a_production_modules_are_byte_identical(self):
        expected={
            "modules/action_contract.py":"f342508bcda04842a04267cbadc39b59b4b468ca45d348a0e8351f2b4016c64a",
            "modules/action_authority.py":"0103888d91c03b4efa536a2fa8cdb741effe5f2a80f434276c74aaa74b96c87e",
            "modules/action_broker.py":"fa3c1978fb7d19af4082a9407e45a80d946c9698cc6a30a0cd1377220dee3125",
        }
        for rel,sha in expected.items():
            with self.subTest(path=rel):
                self.assertEqual(hashlib.sha256((PROJECT_ROOT/rel).read_bytes()).hexdigest(),sha)

    def test_legacy_actions_timer_service_and_router_methods_are_preserved(self):
        expected_files={
            "modules/actions.py":"dfdc9c8fd6acb5d239868c9dcb0ef9cc460bf346bf23f3d0715913940fcc1661",
            "modules/timer_service.py":"01d046642fe99d17d0194279bd8d9575a79b6416b8354e9a2641700d0f55710a",
        }
        for rel,sha in expected_files.items():
            with self.subTest(path=rel):
                self.assertEqual(hashlib.sha256((PROJECT_ROOT/rel).read_bytes()).hexdigest(),sha)

        expected_methods={
            "__init__":"3e705818a0adb5faae22d25c64d1cec9ae27423b7a1e8bdb669b9e0b65b6a023",
            "mode":"af3c804756c9a0a5ba40d1ae29fc5e08099b1dcd637cbe059b4816257e655757",
            "_norm":"d9f0df7f3febcf0d739ca452431db04ab1f336e2c137b9ff6062f05b7f2ac7b2",
            "_is_repeat_cmd":"4d4a75f48d34fc194ba689dbb26a979229b2e5f25f787bf5ef5ea0c4764e5233",
            "_repeat_variant_intent":"36c37abcd44024e419d397a4404d15710bae53d3da8dd4cabdc04dee2c7d35ce",
            "_already_resolved":"15e68f8a756027c8621d150d5dd9deff2801dd8db7b8cf422f81de1f047b19ab",
            "_history_meta":"6fc7e4ed71a0c6f844f15d9eb70e5eee1c67515f4200fbdc6169a6c1cf072dd8",
            "_variant_meta":"3481de2124fe67c3ee807b15d12846037c5824be235d28a5de12d0004d75af47",
            "_clean_meta_for_history":"0ab85f5ddd9d10ba759b8641825fdcd1e42a41387e5acd07013734c7a40f44f2",
            "_resolve_meta":"1a6d4178e3f844e58c4f68df8d096d13c4292587d868ccbaba436063820b2055",
            "preprocess":"f9d5f4982d52e95b9241d4b0a4832c2e908869b44d4cd3a25eb0eec943c8c2b9",
            "reply":"451d86d74059a46a0cbaeead9b0f43708f7a373ba2deb6364317a705771dadf9",
            "execute":"5a7f572e8eb4f9fafb4488b3544d2747b17dec17e7f451e91e818024ba90fef7",
        }
        tree=ast.parse((PROJECT_ROOT/"modules/router.py").read_text(encoding="utf-8-sig"))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=="Router")
        methods={n.name:n for n in cls.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
        self.assertEqual(set(methods),set(expected_methods)|{"remember_boundary_volume_success"})
        for name,sha in expected_methods.items():
            with self.subTest(method=name):
                raw=_stable_ast_dump(methods[name]).encode("utf-8")
                self.assertEqual(hashlib.sha256(raw).hexdigest(),sha)

    def test_timer_runtime_import_allowlist(self):
        rel="modules/timer_action_runtime.py"
        allowed={"__future__","dataclasses","enum","os","threading","uuid","typing",
                 "modules.action_contract","modules.action_authority","modules.action_broker","modules.action_error"}
        tree=ast.parse((PROJECT_ROOT/rel).read_text(encoding="utf-8"))
        actual=set()
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):actual.update(a.name for a in node.names)
            elif isinstance(node,ast.ImportFrom):actual.add(node.module)
        self.assertEqual(actual,allowed)

    def test_timer_runtime_has_no_native_or_effectful_static_imports(self):
        tree=ast.parse((PROJECT_ROOT/"modules/timer_action_runtime.py").read_text(encoding="utf-8"))
        names=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):names.extend(a.name for a in node.names)
            elif isinstance(node,ast.ImportFrom):names.append(node.module or "")
        self.assertFalse(any(n=="native" or n.startswith("native.") for n in names))
        self.assertFalse(any(n in {"subprocess","socket","ctypes","webbrowser"} for n in names))

    def test_main_wires_exact_timer_bridge_once(self):
        tree=ast.parse((PROJECT_ROOT/"main.py").read_text(encoding="utf-8-sig"))
        imports=[n for n in ast.walk(tree) if isinstance(n,ast.ImportFrom) and n.module=="modules.timer_action_runtime"]
        self.assertEqual(len(imports),1)
        calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=="compose_timer_action_runtime"]
        self.assertEqual(len(calls),1)

    def test_command_runtime_only_migrates_timer_pair(self):
        import modules.command_runtime as cr
        self.assertEqual(cr.HWA02B1_TIMER_INTENTS,frozenset({"SET_TIMER","CANCEL_TIMER"}))

    def test_command_processor_and_main_pass_timer_port_explicitly(self):
        cp_tree=ast.parse((PROJECT_ROOT/"modules/command_processor.py").read_text(encoding="utf-8-sig"))
        init=next(n for n in ast.walk(cp_tree) if isinstance(n,ast.FunctionDef) and n.name=="__init__")
        arg_names=[a.arg for a in init.args.kwonlyargs]
        self.assertIn("timer_actions",arg_names)
        process=next(n for n in ast.walk(cp_tree) if isinstance(n,ast.FunctionDef) and n.name=="process")
        runtime_calls=[n for n in ast.walk(process) if isinstance(n,ast.Call)
                       and isinstance(n.func,ast.Name) and n.func.id=="handle_command_runtime"]
        self.assertEqual(len(runtime_calls),1)
        timer_kw=[k for k in runtime_calls[0].keywords if k.arg=="timer_actions"]
        self.assertEqual(len(timer_kw),1)
        self.assertIsInstance(timer_kw[0].value,ast.Attribute)
        self.assertEqual(timer_kw[0].value.attr,"_timer_actions")

        main_tree=ast.parse((PROJECT_ROOT/"main.py").read_text(encoding="utf-8-sig"))
        processor_calls=[n for n in ast.walk(main_tree) if isinstance(n,ast.Call)
                         and isinstance(n.func,ast.Name) and n.func.id=="CommandProcessor"]
        self.assertEqual(len(processor_calls),1)
        main_kw=[k for k in processor_calls[0].keywords if k.arg=="timer_actions"]
        self.assertEqual(len(main_kw),1)
        self.assertIsInstance(main_kw[0].value,ast.Name)
        self.assertEqual(main_kw[0].value.id,"timer_actions")

        main_text=(PROJECT_ROOT/"main.py").read_text(encoding="utf-8-sig")
        self.assertIn("timer_start_handler = actions._exec_set_timer",main_text)
        self.assertIn("timer_cancel_handler = actions._exec_cancel_timer",main_text)
        self.assertIn("timer_action_owner.close()",main_text)

    def test_modules_have_no_native_imports(self):
        for path in (PROJECT_ROOT/"modules").rglob("*.py"):
            tree=ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                names=[]
                if isinstance(node,ast.Import):names=[a.name for a in node.names]
                elif isinstance(node,ast.ImportFrom):names=[node.module or ""]
                self.assertFalse(any(n=="native" or n.startswith("native.") for n in names),str(path))

    def test_pipeline_has_dedicated_timer_action_runtime_flow(self):
        tree=ast.parse((PROJECT_ROOT/"tools/pipeline.py").read_text(encoding="utf-8-sig"))
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="available_flows")
        expr=fn.body[0].value;flows={k.value:v.elts for k,v in zip(expr.keys,expr.values)}
        marker="tools/eval_timer_action_runtime.py"
        occurrences={}
        for key,nodes in flows.items():
            count=sum(any(isinstance(x,ast.Constant) and x.value==marker for x in ast.walk(n)) for n in nodes)
            if count:occurrences[key]=count
        self.assertEqual(occurrences,{"check":1,"timer_action_runtime":1})


class CountedResult(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.subtests=0
    def addSubTest(self,test,subtest,err):
        self.subtests+=1;return super().addSubTest(test,subtest,err)


def main() -> int:
    suite=unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    discovered=suite.countTestCases()
    expected=EXPECTED_TESTS
    result=unittest.TextTestRunner(stream=sys.stdout,verbosity=2,resultclass=CountedResult).run(suite)
    ok=result.wasSuccessful() and result.testsRun==expected and not result.skipped
    summary={"kind":"HWA02B1_TIMER_ACTION_RUNTIME_EVAL_V1","result":"PASS" if ok else "FAIL",
             "tests_run":result.testsRun,"expected_tests":expected,"discovered_tests":discovered,
             "subtests":result.subtests,"failures":len(result.failures),"errors":len(result.errors),
             "skipped":len(result.skipped),"runtime_wired":True,
             "migrated_actions":["SET_TIMER","CANCEL_TIMER"],"native_execution_authorized":False,
             "host_worker_launched":False,"real_timer_started":False}
    print("\n=== HWA02-B1 SUMMARY ===")
    print(json.dumps(summary,ensure_ascii=False,sort_keys=True))
    return 0 if ok else 1


if __name__=="__main__":
    raise SystemExit(main())
