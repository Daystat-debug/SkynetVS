"""Headless callback tests for the symbol investigation UI integration.

Imports the real UI with its normal bundled contract layout; constructs no Tk
window and performs no application analysis, network access or source writes.
"""
from __future__ import annotations

import copy
from pathlib import Path
import queue
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).absolute().parent.parent
BUNDLE = ROOT / "modules" / "developer_task_ui"
sys.dont_write_bytecode = True
sys.path[:0] = [str(BUNDLE / "vendor"), str(BUNDLE)]

from app import ui
from app.core import SourceSnapshot
from app.symbol_investigation import investigate_sources
from app.symbol_task_bridge import report_fingerprint

COMMIT, TREE = "a" * 40, "b" * 40
PATH = "modules/sample.py"
GOAL = "Измени normalize в modules/sample.py, чтобы пустая строка возвращалась без ошибки."
SOURCE = "def normalize(value):\n    return value.strip()\n"


def fixture(*, goal=GOAL, ambiguous=False, path=PATH):
    sources = {path: SOURCE}
    if ambiguous:
        sources["modules/second.py"] = SOURCE
    result = investigate_sources(COMMIT, sources, {"partial": False}, goal, "normalize")
    result["git_head_observed"] = True
    result["source_binding"] = "OBSERVED_GIT_HEAD_BLOBS"
    return result


class Button:
    def __init__(self):
        self.disabled = True

    def state(self, states):
        if "disabled" in states:
            self.disabled = True
        if "!disabled" in states:
            self.disabled = False


class Value:
    def __init__(self, value=""):
        self.value = value
        self.modified = False

    def get(self, *_):
        return self.value

    def set(self, value):
        self.value = value

    def edit_modified(self, value=None):
        if value is None:
            return self.modified
        self.modified = value


class Store:
    def __init__(self):
        self.writes = []

    def _folder(self, prefix):
        return Path("/synthetic-artifacts") / (prefix + "owned")

    def write(self, folder, name, data):
        self.writes.append((folder, name, data))


def window(goal=GOAL):
    value = ui.DeveloperWindow.__new__(ui.DeveloperWindow)
    value.root = Mock()
    value.repository = Path("/synthetic-project")
    value.store = Store()
    value.ai_busy = False
    value.ai_queue = queue.Queue()
    value.ai_goal = Value(goal)
    value.ai_model = Value("unused")
    value.ai_backend = Value("own")
    value.ai_info = Value()
    value.ai_text = Value()
    value.ai_symbol_result = None
    value.ai_symbol_report_sha256 = None
    value.ai_symbol_selector = ""
    value.ai_task_search_result = None
    value.ai_context_text = None
    value.ai_bridge_summary = None
    value.ai_report = None
    value.ai_proposal = None
    value.ai_proposal_finding_id = None
    value.ai_apply_checked = None
    value.events = []
    value.errors = []
    value.fail = lambda exc: value.errors.append(str(exc))
    value.set_text = lambda widget, text: widget.set(text)
    value._populate_own_findings = Mock()
    value.invalidate = Mock()
    value.set_task = Mock()
    value.refresh_source = Mock()
    value.prepare = Mock(return_value=True)
    value._legacy_visible = True
    for name in ("ai_button", "ai_context_button", "ai_bridge_button",
                 "ai_symbol_button", "ai_task_request_button", "ai_proposal_button",
                 "ai_verify_button", "ai_apply_button", "ai_proposal_copy_button",
                 "ai_context_copy_button"):
        setattr(value, name, Button())
    return value


class InlineThread:
    def __init__(self, *, target, daemon):
        self.target = target

    def start(self):
        self.target()


class CoreSymbolUITests(unittest.TestCase):
    def test_complete_result_saves_metadata_and_only_enables_request(self):
        app = window()
        report = fixture()
        app.ai_busy = True
        app.ai_queue.put(("symbol", report))
        app.poll_ai_review()
        self.assertEqual(app.ai_symbol_report_sha256, report_fingerprint(report))
        self.assertFalse(app.ai_task_request_button.disabled)
        self.assertTrue(app.ai_apply_button.disabled)
        self.assertTrue(app.ai_verify_button.disabled)
        self.assertTrue(app.ai_proposal_button.disabled)
        self.assertEqual(app.store.writes[0][1], "Core_SymbolInvestigation.json")
        self.assertNotIn(SOURCE.encode("utf-8"), app.store.writes[0][2])
        self.assertFalse(app.ai_busy)
        self.assertEqual(app.errors, [])

    def test_ambiguous_result_requires_selection_without_dtra(self):
        app = window()
        report = fixture(ambiguous=True)
        app.ai_queue.put(("symbol", report))
        with patch.object(ui.simpledialog, "askinteger") as choose:
            app.poll_ai_review()
        self.assertEqual(app.ai_symbol_result["status"], "CHOICE_REQUIRED")
        self.assertTrue(app.ai_task_request_button.disabled)
        self.assertIn("modules/second.py", app.ai_text.get())
        choose.assert_not_called()
        app.prepare.assert_not_called()

    def test_goal_edit_during_scan_cannot_enable_stale_request(self):
        app = window("Измени normalize в modules/sample.py, чтобы None возвращал пустую строку.")
        app.ai_queue.put(("symbol", fixture()))
        app.poll_ai_review()
        self.assertTrue(app.ai_task_request_button.disabled)
        self.assertIn("STALE_GOAL", app.ai_info.get())
        app.prepare.assert_not_called()

    def test_read_only_goal_cannot_prepare_or_capture(self):
        goal = "Покажи функцию normalize без изменений."
        app = window(goal)
        app.ai_symbol_result = fixture(goal=goal)
        app.ai_symbol_report_sha256 = report_fingerprint(app.ai_symbol_result)
        with patch.object(ui, "GitSourceReader") as reader, patch.object(ui.messagebox, "askyesno") as ask:
            app.prepare_task_request_from_context()
        reader.assert_not_called()
        ask.assert_not_called()
        app.prepare.assert_not_called()
        self.assertTrue(app.ai_task_request_button.disabled)

    def test_changed_report_cannot_reach_confirmation_or_capture(self):
        app = window()
        app.ai_symbol_result = fixture()
        app.ai_symbol_report_sha256 = report_fingerprint(app.ai_symbol_result)
        app.ai_symbol_result["coverage"]["changed"] = True
        with patch.object(ui, "GitSourceReader") as reader, patch.object(ui.messagebox, "askyesno") as ask:
            app.prepare_task_request_from_context()
        reader.assert_not_called()
        ask.assert_not_called()
        app.prepare.assert_not_called()
        self.assertIn("REPORT_CHANGED", app.errors[0])

    def test_explicit_selected_function_reuses_capture_and_prepares_evidence(self):
        app = window()
        app.ai_symbol_result = fixture()
        app.ai_symbol_report_sha256 = report_fingerprint(app.ai_symbol_result)
        source = SourceSnapshot(PATH, SOURCE.encode(), COMMIT, TREE,
                                {"kind": "OBSERVED_COMMITTED_FILE", "current_git_head_observed": True})
        reader = Mock()
        reader.capture.return_value = source
        with patch.object(ui, "GitSourceReader", return_value=reader), \
                patch.object(ui, "find_git", return_value=Path("/synthetic-git")), \
                patch.object(ui.messagebox, "askyesno", return_value=True), \
                patch.object(ui.simpledialog, "askinteger") as chooser:
            app.prepare_task_request_from_context()
        reader.capture.assert_called_once_with(app.repository / PATH)
        chooser.assert_not_called()  # the user already selected the exact function
        app.prepare.assert_called_once_with()
        self.assertIn(app.ai_symbol_report_sha256, app.set_task.call_args.args[1])
        self.assertEqual(app.source, source)
        self.assertTrue(app.ai_apply_button.disabled)
        self.assertEqual(app.events[-1]["event"], "CORE_SYMBOL_TO_DTRA_REQUEST")
        self.assertEqual(app.errors, [])

    def test_head_changed_after_investigation_prevents_request_write(self):
        app = window()
        app.ai_symbol_result = fixture()
        app.ai_symbol_report_sha256 = report_fingerprint(app.ai_symbol_result)
        source = SourceSnapshot(PATH, SOURCE.encode(), "c" * 40, TREE,
                                {"kind": "OBSERVED_COMMITTED_FILE", "current_git_head_observed": True})
        reader = Mock()
        reader.capture.return_value = source
        with patch.object(ui, "GitSourceReader", return_value=reader), \
                patch.object(ui, "find_git", return_value=Path("/synthetic-git")), \
                patch.object(ui.messagebox, "askyesno", return_value=True):
            app.prepare_task_request_from_context()
        app.prepare.assert_not_called()
        app.set_task.assert_not_called()
        self.assertIn("SOURCE_OR_HEAD_DRIFT", app.errors[0])
        self.assertEqual(app.store.writes, [])

    def test_goal_changed_while_confirmation_open_prevents_capture(self):
        app = window()
        app.ai_symbol_result = fixture()
        app.ai_symbol_report_sha256 = report_fingerprint(app.ai_symbol_result)

        def edit_then_confirm(*_args, **_kwargs):
            app.ai_goal.set("Измени normalize в modules/sample.py, чтобы None возвращал пустую строку.")
            return True

        with patch.object(ui.messagebox, "askyesno", side_effect=edit_then_confirm), \
                patch.object(ui, "GitSourceReader") as reader:
            app.prepare_task_request_from_context()
        reader.assert_not_called()
        app.prepare.assert_not_called()
        self.assertIn("STALE_GOAL", app.errors[0])

    def test_choice_refinement_is_bound_to_displayed_head(self):
        app = window()
        previous = fixture(ambiguous=True)
        app.ai_symbol_result = previous
        app.ai_symbol_report_sha256 = report_fingerprint(previous)
        with patch.object(ui.simpledialog, "askstring", return_value=f"{PATH}::normalize@1"), \
                patch.object(ui.threading, "Thread", InlineThread), \
                patch.object(ui, "investigate_repository", return_value=fixture()) as investigate:
            app.start_symbol_investigation()
        self.assertEqual(investigate.call_args.kwargs["expected_commit"], COMMIT)
        self.assertEqual(investigate.call_args.args[2], f"{PATH}::normalize@1")
        self.assertTrue(app.ai_apply_button.disabled)
        self.assertTrue(app.ai_task_request_button.disabled)
        self.assertIsNone(app.ai_task_search_result)

    def test_cancelled_selector_keeps_current_report_and_does_not_scan(self):
        app = window()
        previous = fixture()
        app.ai_symbol_result = previous
        with patch.object(ui.simpledialog, "askstring", return_value=None), \
                patch.object(ui, "investigate_repository") as investigate:
            app.start_symbol_investigation()
        self.assertIs(app.ai_symbol_result, previous)
        self.assertFalse(app.ai_busy)
        investigate.assert_not_called()

    def test_new_existing_search_or_analysis_clears_symbol_binding(self):
        for method in ("start_context_search", "start_context_ast_bridge", "start_ai_review"):
            with self.subTest(method=method):
                app = window()
                app.ai_symbol_result = fixture()
                app.ai_symbol_report_sha256 = report_fingerprint(app.ai_symbol_result)
                with patch.object(ui.threading, "Thread"):
                    getattr(app, method)()
                self.assertIsNone(app.ai_symbol_result)
                self.assertIsNone(app.ai_symbol_report_sha256)
                self.assertTrue(app.ai_task_request_button.disabled)
                self.assertTrue(app.ai_symbol_button.disabled)

    def test_goal_edit_disables_shortcut_immediately(self):
        app = window()
        app.ai_symbol_result = fixture()
        app.ai_task_request_button.state(["!disabled"])
        app.ai_goal.modified = True
        app.ai_goal_changed()
        self.assertTrue(app.ai_task_request_button.disabled)
        self.assertFalse(app.ai_goal.modified)

    def test_failure_clears_retained_symbol_and_context_request_state(self):
        app = window()
        app.ai_symbol_result = fixture()
        app.ai_symbol_report_sha256 = report_fingerprint(app.ai_symbol_result)
        app.ai_task_search_result = {"old": True}
        app.ai_queue.put(("error", "synthetic refusal"))
        app.poll_ai_review()
        self.assertIsNone(app.ai_symbol_result)
        self.assertIsNone(app.ai_symbol_report_sha256)
        self.assertIsNone(app.ai_task_search_result)
        self.assertTrue(app.ai_task_request_button.disabled)
        self.assertTrue(app.ai_apply_button.disabled)

    def test_protected_definition_is_displayed_but_not_dtra_enabled(self):
        app = window()
        app.ai_queue.put(("symbol", fixture(path="modules/core/example.py")))
        app.poll_ai_review()
        self.assertIsNotNone(app.ai_symbol_result)
        self.assertTrue(app.ai_task_request_button.disabled)
        app.prepare.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
