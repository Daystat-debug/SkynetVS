"""Six targeted checks; synthetic files, no main/model/private-data imports."""
from __future__ import annotations

import ast
from contextlib import contextmanager
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SECRET = "synthetic-private-route-text-103"
EPOCH = "e1" * 16
EVENT_ID = "d2" * 16


class RuntimeObservationTraceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="skynetvs_route_trace_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        names = ("modules", "modules.learning", "modules.runtime_observation_trace",
                 "modules.learning.correction_evidence_runtime", "modules.learning.learning_memory",
                 "modules.learning.voice_learning_entry_port")
        absent = object()
        previous = {name: sys.modules.get(name, absent) for name in names}

        def restore():
            for name, value in previous.items():
                if value is absent:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = value
        self.addCleanup(restore)
        for name in ("modules", "modules.learning"):
            package = ModuleType(name)
            package.__path__ = []
            sys.modules[name] = package
        self.trace_module = self.load("modules.runtime_observation_trace", "modules/runtime_observation_trace.py")
        self.runtime = self.load("modules.learning.correction_evidence_runtime",
                                 "modules/learning/correction_evidence_runtime.py")
        self.writer_module = self.load("modules.learning.learning_memory", "modules/learning/learning_memory.py")
        self.entry_module = self.load("modules.learning.voice_learning_entry_port",
                                     "modules/learning/voice_learning_entry_port.py")

    @staticmethod
    def load(name, relative):
        spec = importlib.util.spec_from_file_location(name, ROOT / relative)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    def storage(self, label, state="LEGACY"):
        project = self.root / label
        base = project / "data" / "learning"
        base.mkdir(parents=True)
        if state != "LEGACY":
            (base / self.runtime.CONTROL_NAME).write_text(json.dumps({
                "kind": self.runtime.CONTROL_KIND, "version": 1,
                "state": state, "epoch": EPOCH if state == "ACTIVE" else None,
            }) + "\n", encoding="utf-8")
        return project, base

    @staticmethod
    def arguments():
        return {"raw_text": SECRET, "final_text": SECRET,
                "meta": {"intent": "GREET", "confidence": 0.7, "slots": {}, "say": "", "_text": ""},
                "mode": "text", "accepted": True, "immediate_label": "immediate", "missing_slots": []}

    def trace(self, project, base, *, broken=False):
        rows = []

        def event(kind, payload):
            if broken:
                raise OSError(SECRET)
            rows.append((kind, dict(payload)))
        trace = self.trace_module.RuntimeObservationTrace(
            SimpleNamespace(event=event), project_root=project, history_base=str(base),
        )
        return trace, rows

    @staticmethod
    def handlers(trace, command_processor, phrase_processor):
        # Execute only these two existing nested handlers, not main or imports.
        tree = ast.parse((ROOT / "main.py").read_text(encoding="utf-8-sig"))
        main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
        functions = {node.name: node for node in main.body if isinstance(node, ast.FunctionDef)}
        factory = ast.parse("def factory():\n    last_tts_end = 10.0\n    ack_ignore_until = 20.0\n").body[0]
        factory.body.extend([functions["handle_command_text"], functions["handle_phrase_event"]])
        factory.body.extend(ast.parse(
            "def state():\n    return last_tts_end, ack_ignore_until\n"
            "return handle_command_text, handle_phrase_event, state\n"
        ).body)
        module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
                                  factory], type_ignores=[])
        namespace = {"observation_trace": trace, "command_processor": command_processor,
                     "phrase_event_processor": phrase_processor}
        exec(compile(ast.fix_missing_locations(module), "<isolated-main-handlers>", "exec"), namespace)
        return namespace["factory"]()

    def test_session_phrase_command_and_writer_share_correlation_after_real_append(self):
        for state in ("LEGACY", "PREPARING", "ACTIVE"):
            with self.subTest(state=state):
                project, base = self.storage(state, state)
                trace, rows = self.trace(project, base)
                callback_errors, callbacks, actions = [], [], []

                def report(**payload):
                    try:
                        # This must succeed both before and after the writer lock.
                        with self.runtime.learning_evidence_lock(base):
                            pass
                    except Exception as error:
                        callback_errors.append(error)
                    callbacks.append(dict(payload))
                    trace.observation(**payload)
                writer = self.writer_module.LearningMemory(str(base), observation_reporter=report)
                meta = {"synthetic_meta": True}

                def process(text, *, immediate_label):
                    self.assertEqual((text, immediate_label), (SECRET, "immediate"))
                    self.assertIsNone(writer.log_command(**self.arguments()))
                    actions.append(text)
                    return SimpleNamespace(meta=meta, last_tts_end=31.0, reason="executed")
                phrase_processor = SimpleNamespace()
                command, phrase, snapshot = self.handlers(trace, SimpleNamespace(process=process), phrase_processor)

                def process_phrase(text, **options):
                    self.assertEqual(text, SECRET)
                    self.assertIs(command(text, immediate_label="immediate"), meta)
                    return SimpleNamespace(reason="immediate_hotword_command", last_tts_end=31.0, ack_ignore_until=41.0)
                phrase_processor.process_phrase = process_phrase
                trace.session_started()
                trace.loop_ready()
                fixed_clock = SimpleNamespace(now=lambda: datetime(2026, 1, 1, 12, 0, 0))
                with mock.patch.object(self.writer_module, "datetime", fixed_clock), mock.patch.object(
                        self.writer_module, "uuid4", return_value=SimpleNamespace(hex=EVENT_ID)):
                    self.assertIsNone(phrase({"text": SECRET}))
                    self.assertIsNone(phrase({"text": SECRET}))
                    # The optional observer does not change the original writer API/payload.
                    plain = self.writer_module.LearningMemory(str(base))
                    self.assertIsNone(plain.log_command(**self.arguments()))
                trace.loop_exited()
                self.assertEqual(snapshot(), (31.0, 41.0))
                self.assertEqual(actions, [SECRET, SECRET])
                self.assertEqual(callback_errors, [])
                self.assertEqual([item["status"] for item in callbacks],
                                 ["ATTEMPTED", "APPEND_RETURNED"] * 2)
                self.assertEqual([item["control_state"] for item in callbacks], ["UNKNOWN", state] * 2)
                expected = {"ts": "2026-01-01T12:00:00", "event_id": EVENT_ID, **self.arguments()}
                if state == "ACTIVE":
                    expected["evidence_epoch"] = EPOCH
                history = [json.loads(line) for line in (base / "command_history.jsonl").read_text(encoding="utf-8").splitlines()]
                self.assertEqual(history, [expected] * 3)
                payloads = [payload for _, payload in rows]
                self.assertEqual(len({item["session_id"] for item in payloads}), 1)
                for ordinal in (1, 2):
                    self.assertEqual([item["event"] for item in payloads if item["phrase_sequence"] == ordinal], [
                        "PHRASE_ENTERED", "COMMAND_ENTERED", "OBSERVATION_ATTEMPTED",
                        "OBSERVATION_APPEND_RETURNED", "COMMAND_RETURNED", "PHRASE_RETURNED",
                    ])
                self.assertEqual([item["event"] for item in payloads if item["phrase_sequence"] is None],
                                 ["SESSION_STARTED", "LOOP_READY", "LOOP_EXITED"])
                self.assertNotIn(SECRET, json.dumps(rows))
                self.assertNotIn(EPOCH, json.dumps(rows))
                self.assertNotIn(EVENT_ID, json.dumps(rows))

    def test_early_voice_learning_nlu_error_is_reported_without_command(self):
        project, base = self.storage("early")
        trace, rows = self.trace(project, base)
        predictor = mock.Mock(side_effect=RuntimeError(SECRET))
        port = self.entry_module.VoiceLearningEntryPort(
            bridge=SimpleNamespace(state="IDLE"), has_hotword=lambda text: True,
            strip_hotword=lambda text: text, operator_start_intent="GREET", predict_nlu_intent=predictor,
            result_type=lambda **value: SimpleNamespace(last_tts_end=None, ack_ignore_until=None, **value),
            report_start=lambda event: None,
        )
        command_processor = SimpleNamespace(process=mock.Mock(side_effect=AssertionError("must not run")))
        phrase_processor = SimpleNamespace(process_phrase=lambda text, **options: port(text))
        _, phrase, snapshot = self.handlers(trace, command_processor, phrase_processor)
        self.assertIsNone(phrase({"text": SECRET}))
        self.assertEqual(snapshot(), (10.0, 20.0))
        predictor.assert_called_once()
        command_processor.process.assert_not_called()
        self.assertFalse((base / "command_history.jsonl").exists())
        self.assertEqual([item["event"] for _, item in rows], ["PHRASE_ENTERED", "PHRASE_RETURNED"])
        self.assertEqual(rows[-1][1]["reason"], "voice_learning_nlu_error")
        self.assertNotIn(SECRET, json.dumps(rows))

    def test_refusal_and_unexpected_writer_errors_preserve_identity_and_lock_release(self):
        for label, error, status, reason in (
            ("known", self.runtime.RuntimeRefused("BUSY"), "REFUSED", "BUSY"),
            ("unknown", self.runtime.RuntimeRefused(SECRET), "REFUSED", "RUNTIME_REFUSED"),
            ("unexpected", RuntimeError(SECRET), "RAISED", "NONE"),
            ("exit", RuntimeError(SECRET), "RAISED", "NONE"),
        ):
            with self.subTest(label=label):
                project, base = self.storage(label, "ACTIVE")
                trace, rows = self.trace(project, base)
                callback_errors = []

                def report(**payload):
                    try:
                        with self.runtime.learning_evidence_lock(base):
                            pass
                    except Exception as diagnostic_error:
                        callback_errors.append(diagnostic_error)
                    trace.observation(**payload)
                writer = self.writer_module.LearningMemory(str(base), observation_reporter=report)

                @contextmanager
                def exit_failure(path):
                    with self.runtime.learning_evidence_lock(path) as locked:
                        yield locked
                    raise error
                patcher = (mock.patch.object(self.writer_module, "learning_evidence_lock", exit_failure)
                           if label == "exit" else mock.patch.object(writer, "_append_jsonl", side_effect=error))
                with patcher, self.assertRaises(type(error)) as caught:
                    writer.log_command(**self.arguments())
                self.assertIs(caught.exception, error)
                self.assertEqual(callback_errors, [])
                self.assertEqual([item["event"] for _, item in rows], ["OBSERVATION_ATTEMPTED", "OBSERVATION_" + status])
                self.assertEqual(rows[-1][1]["reason"], reason)
                self.assertEqual(rows[-1][1]["control_state"], "ACTIVE")
                self.assertEqual((base / "command_history.jsonl").exists(), label == "exit")
                self.assertNotIn(SECRET, json.dumps(rows))

    def test_diagnostic_failures_preserve_main_returns_and_original_errors(self):
        for broken in (False, True):
            with self.subTest(logger_failure=broken):
                project, base = self.storage("broken_" + str(broken))
                trace, _ = self.trace(project, base, broken=broken)
                reporter = mock.Mock(side_effect=OSError(SECRET))
                writer = self.writer_module.LearningMemory(str(base), observation_reporter=reporter)
                meta, actions, calls = {"unchanged_meta": True}, [], []

                def process(text, **options):
                    calls.append(text)
                    writer.log_command(**self.arguments())
                    actions.append(text)
                    return SimpleNamespace(meta=meta, last_tts_end=30.0, reason="executed")
                original = RuntimeError(SECRET)
                phrase_processor = SimpleNamespace(process_phrase=mock.Mock(side_effect=original))
                command, phrase, snapshot = self.handlers(trace, SimpleNamespace(process=process), phrase_processor)
                self.assertIs(command(SECRET, immediate_label="immediate"), meta)
                self.assertEqual(snapshot(), (30.0, 20.0))
                self.assertEqual(reporter.call_count, 2)
                with mock.patch.object(writer, "_append_jsonl", side_effect=original), self.assertRaises(RuntimeError) as caught:
                    command(SECRET, immediate_label="immediate")
                self.assertIs(caught.exception, original)
                self.assertEqual(calls, [SECRET, SECRET])
                self.assertEqual(actions, [SECRET])
                with self.assertRaises(RuntimeError) as caught:
                    phrase({"text": SECRET})
                self.assertIs(caught.exception, original)
                phrase_processor.process_phrase.assert_called_once()
                self.assertEqual(snapshot(), (30.0, 20.0))
        with mock.patch.object(self.trace_module, "uuid4", side_effect=RuntimeError(SECRET)):
            trace, rows = self.trace(self.root, self.root / "data" / "learning")
        trace.session_started()
        with trace.phrase(), trace.command():
            trace.phrase_returned("no_phrase_handler_matched")
        self.assertEqual(rows, [])

    def test_closed_trace_payload_rejects_private_and_unknown_values(self):
        project, base = self.storage("closed")
        trace, rows = self.trace(project, base)
        with trace.phrase():
            for value in (SECRET, {"private": SECRET}, [SECRET]):
                trace.phrase_returned(value)
                trace.observation(status="REFUSED", control_state=value, reason=value)
            before = len(rows)
            trace.observation(status=SECRET, control_state=SECRET, reason=SECRET)
            self.assertEqual(len(rows), before)
        trace.loop_exited()
        other, other_rows = self.trace(project, self.root / "different" / "learning")
        other.session_started()
        unknown_rows = []
        unknown = self.trace_module.RuntimeObservationTrace(
            SimpleNamespace(event=lambda kind, payload: unknown_rows.append((kind, payload))),
            project_root=project, history_base=object(),
        )
        unknown.session_started()
        all_rows = rows + other_rows + unknown_rows
        self.assertEqual({item["history_scope"] for _, item in all_rows}, {"PROJECT", "OTHER", "UNKNOWN"})
        self.assertFalse((self.root / "different").exists())
        self.assertNotEqual(rows[0][1]["session_id"], other_rows[0][1]["session_id"])
        for kind, payload in all_rows:
            self.assertEqual(kind, "runtime_observation_trace")
            self.assertEqual(set(payload), {"schema", "session_id", "phrase_sequence", "event", "reason",
                                            "control_state", "history_scope"})
            self.assertEqual(payload["schema"], 1)
            self.assertRegex(payload["session_id"], r"^[0-9a-f]{32}$")
            self.assertTrue(payload["phrase_sequence"] is None or type(payload["phrase_sequence"]) is int)
            self.assertIn(payload["event"], self.trace_module.EVENTS)
            self.assertIn(payload["reason"], self.trace_module.PHRASE_REASONS | self.trace_module.REFUSAL_REASONS | {"NONE", "OTHER"})
            self.assertIn(payload["control_state"], {"ACTIVE", "PREPARING", "LEGACY", "UNKNOWN"})
        self.assertNotIn(SECRET, json.dumps(all_rows))
        bounded, bounded_rows = self.trace(project, base)
        bounded._next_phrase = self.trace_module.MAX_PHRASE_SEQUENCE - 1
        with bounded.phrase():
            bounded.phrase_returned("no_phrase_handler_matched")
        with bounded.phrase():
            bounded.phrase_returned("no_phrase_handler_matched")
        bounded.loop_exited()
        self.assertEqual([item["event"] for _, item in bounded_rows], ["PHRASE_ENTERED", "PHRASE_RETURNED"])
        self.assertEqual([item["phrase_sequence"] for _, item in bounded_rows],
                         [self.trace_module.MAX_PHRASE_SEQUENCE] * 2)

    def test_main_wiring_preserves_composition_and_loop_boundaries(self):
        tree = ast.parse((ROOT / "main.py").read_text(encoding="utf-8-sig"))
        main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
        constructors = [node for node in ast.walk(main) if isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name) and node.func.id == "RuntimeObservationTrace"]
        self.assertEqual(len(constructors), 1)
        self.assertEqual(constructors[0].args[0].id, "logger")
        self.assertEqual(next(key.value.id for key in constructors[0].keywords if key.arg == "history_base"), "learning_base")
        memory = [node for node in ast.walk(main) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Name) and node.func.id == "LearningMemory"]
        self.assertEqual(len(memory), 1)
        self.assertEqual(memory[0].args[0].id, "learning_base")
        reporter = next(key.value for key in memory[0].keywords if key.arg == "observation_reporter")
        self.assertEqual((reporter.value.id, reporter.attr), ("observation_trace", "observation"))
        learning_base = next(node.value.value for node in main.body if isinstance(node, ast.Assign)
                             and any(isinstance(target, ast.Name) and target.id == "learning_base" for target in node.targets))
        self.assertEqual(learning_base, "data/learning")
        loop = next(node for node in main.body if isinstance(node, ast.Try)
                    and node.body and isinstance(node.body[0], ast.While))
        preceding = main.body[main.body.index(loop) - 1].value.func
        self.assertEqual((preceding.value.id, preceding.attr), ("observation_trace", "loop_ready"))
        first_finally = loop.finalbody[0].value.func
        self.assertEqual((first_finally.value.id, first_finally.attr), ("observation_trace", "loop_exited"))
        for handler_name, method, processor_name, processor_method in (
            ("handle_phrase_event", "phrase", "phrase_event_processor", "process_phrase"),
            ("handle_command_text", "command", "command_processor", "process"),
        ):
            handler = next(node for node in main.body if isinstance(node, ast.FunctionDef) and node.name == handler_name)
            wrappers = [node for node in handler.body if isinstance(node, ast.With)]
            self.assertEqual(len(wrappers), 1)
            context = wrappers[0].items[0].context_expr.func
            self.assertEqual((context.value.id, context.attr), ("observation_trace", method))
            calls = [node for node in ast.walk(handler) if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
                     and node.func.value.id == processor_name and node.func.attr == processor_method]
            self.assertEqual(len(calls), 1)
            self.assertIn(calls[0], list(ast.walk(wrappers[0])))
        self.assertNotIn("main", sys.modules)
        self.assertNotIn("modules.nlu", sys.modules)
        self.assertNotIn("modules.stt_vosk", sys.modules)


if __name__ == "__main__":
    unittest.main(verbosity=2)
