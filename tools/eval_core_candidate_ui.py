"""Headless Core candidate UI roundtrips with the actual bundled DTR contracts.

Only owned strings and temporary artifact folders are used. No Tk window,
repository capture, model, network, source import or proposed-code execution.
Run: Python -I -S -B tools/eval_core_candidate_ui.py
"""
from __future__ import annotations

import copy
from dataclasses import replace
import difflib
import hashlib
import json
from pathlib import Path
import queue
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).absolute().parent.parent
BUNDLE = ROOT / "modules" / "developer_task_ui"
sys.dont_write_bytecode = True
sys.path[:0] = [str(BUNDLE / "vendor"), str(BUNDLE)]

from app import ui
from app.core import ArtifactStore, SourceSnapshot, json_bytes, response_template, restore_request
from app.symbol_investigation import investigate_sources
from app.symbol_task_bridge import report_fingerprint
from modules.developer import developer_task_proposal_intake as bundled_intake

COMMIT, TREE = "a" * 40, "b" * 40
PATH = "modules/sample.py"
GOAL = "Измени normalize в modules/sample.py, чтобы после strip строка приводилась к нижнему регистру."
SOURCE = "def normalize(value):\n    return value.strip()\n\ndef caller(value):\n    return normalize(value)\n"
PROPOSED = SOURCE.replace("return value.strip()", "return value.strip().lower()")


class Button:
    def __init__(self):
        self.disabled = True

    def state(self, values):
        if "disabled" in values:
            self.disabled = True
        if "!disabled" in values:
            self.disabled = False


class Value:
    """Enough Tk variable/Text behavior to exercise the original UI methods."""
    def __init__(self, value=""):
        self.value = value
        self.modified = False
        self.tags = []

    def get(self, *_):
        return self.value

    def set(self, value):
        self.value = value

    def configure(self, **_):
        pass

    def delete(self, *_):
        self.value = ""
        self.tags.clear()

    def insert(self, _index, value):
        self.value += value

    def tag_add(self, *args):
        self.tags.append(args)

    def edit_modified(self, value=None):
        if value is None:
            return self.modified
        self.modified = value


def investigation():
    report = investigate_sources(COMMIT, {PATH: SOURCE}, {"partial": False}, GOAL, PATH + "::normalize")
    # Deliberately synthetic fixture metadata; no actual Git observation.
    report["git_head_observed"] = True
    report["source_binding"] = "OBSERVED_GIT_HEAD_BLOBS"
    return report


def source_snapshot():
    return SourceSnapshot(PATH, SOURCE.encode("utf-8"), COMMIT, TREE,
        {"kind": "OBSERVED_COMMITTED_FILE", "current_git_head_observed": True,
         "synthetic_test_fixture": True})


def window(root):
    app = ui.DeveloperWindow.__new__(ui.DeveloperWindow)
    app.root = Mock()
    app.repository = root / "not_a_repository"
    app.store = ArtifactStore(root / "artifacts")
    app.source = app.request = app.review = None
    app.request_folder = app.static_preview = app.static_folder = None
    app.imported_session = False
    app.dtrb_view = app.dtrb_folder = None
    app.events, app.errors = [], []
    app.fail = lambda exc: app.errors.append(str(exc))
    app.muting = app.ai_busy = False
    app.ai_queue = queue.Queue()
    app._legacy_visible = True
    app.ai_symbol_result = app.ai_symbol_report_sha256 = None
    app.ai_task_search_result = app.ai_context_text = app.ai_bridge_summary = None
    app.ai_report = app.ai_proposal = app.ai_proposal_finding_id = app.ai_apply_checked = None
    app._populate_own_findings = Mock()
    app.tabs = Mock()
    app.task_tab, app.prompt_tab, app.review_tab, app.dtrb_tab = "task", "prompt", "review", "dtrb"
    for name in ("title_var", "instruction", "prompt", "prompt_path", "review_summary", "details",
                 "review_path", "patch", "static_summary", "status", "source_info", "source_text",
                 "dtrb_summary", "dtrb_text", "ai_info", "ai_goal", "ai_model", "ai_backend", "ai_text"):
        setattr(app, name, Value())
    app.ai_goal.set(GOAL)
    app.ai_backend.set("own")
    for name in ("static_button", "ai_button", "ai_context_button", "ai_bridge_button", "ai_symbol_button",
                 "ai_task_request_button", "ai_proposal_button", "ai_verify_button", "ai_apply_button",
                 "ai_proposal_copy_button", "ai_context_copy_button"):
        setattr(app, name, Button())
    app._clear_core_request_binding()
    return app


def prepare_bound(app):
    app.ai_symbol_result = investigation()
    app.ai_symbol_report_sha256 = report_fingerprint(app.ai_symbol_result)
    reader = Mock()
    reader.capture.return_value = source_snapshot()
    with patch.object(ui, "GitSourceReader", return_value=reader), \
            patch.object(ui, "find_git", return_value=Path("/synthetic-git")), \
            patch.object(ui.messagebox, "askyesno", return_value=True):
        app.prepare_task_request_from_symbol()
    reader.capture.assert_called_once_with(app.repository / PATH)


def response_bytes(app, proposed=PROPOSED, *, patch_text=None):
    if patch_text is None:
        patch_text = f"diff --git a/{app.source.path} b/{app.source.path}\n" + "".join(difflib.unified_diff(
            app.source.content.decode("utf-8").splitlines(keepends=True), proposed.splitlines(keepends=True),
            fromfile="a/" + app.source.path, tofile="b/" + app.source.path))
    response = response_template(app.request)
    response.update(patch_text=patch_text, explanation="Synthetic proposed change; never executed.")
    return json_bytes(response)


class CoreCandidateUITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="core_candidate_ui_")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.counter = 0

    def app(self, *, bound=True):
        self.counter += 1
        root = self.root / str(self.counter)
        root.mkdir()
        app = window(root)
        if bound:
            prepare_bound(app)
            self.assertEqual(app.errors, [])
            self.assertIsInstance(app.core_request_context, bytes)
        return app

    def complete(self, app, proposed=PROPOSED):
        raw = response_bytes(app, proposed)
        self.assertTrue(app.accept_bytes(raw)["intake"]["ok"])
        preview = app.check_patch_preview()
        self.assertIsNotNone(preview, app.errors)
        return raw, preview

    def test_ui01_real_saved_context_and_candidate_roundtrip(self):
        app = self.app()
        self.assertTrue(Path(bundled_intake.__file__).resolve().is_relative_to((BUNDLE / "vendor").resolve()))
        saved_context = (app.request_folder / "Core_SymbolTaskContext.json").read_bytes()
        self.assertEqual(saved_context, app.core_request_context)
        self.assertEqual(hashlib.sha256(saved_context).hexdigest(), app.core_request_context_sha256)
        self.assertNotIn(SOURCE, saved_context.decode("utf-8"))
        restored, source = restore_request((app.request_folder / "DTR_Request.json").read_bytes())
        self.assertEqual(restored.binding_dict(), app.request.binding_dict())
        self.assertEqual(source.content, SOURCE.encode("utf-8"))
        raw, preview = self.complete(app)
        self.assertEqual(app.accepted_response_bytes, raw)
        self.assertEqual(preview["python_ast_parse"], "PASS")
        self.assertEqual(app.core_candidate_state, "SAVED")
        saved = json.loads((app.static_folder / "Core_CandidateReview.json").read_bytes())
        self.assertEqual(saved, app.core_candidate_review)
        self.assertEqual(saved["source_binding"], "CAPTURED_DTRA_REQUEST_BYTES")
        self.assertFalse(saved["current_git_head_rechecked"])
        self.assertFalse(saved["runtime_authorized"])
        self.assertFalse(saved["installation_authorized"])
        self.assertEqual(saved["behavior"], "NOT_TESTED")
        self.assertTrue(saved["selected"]["components_changed"]["body"])
        self.assertFalse(saved["selected"]["components_changed"]["signature"])
        self.assertFalse(saved["file_comparison"]["outside_selected_ast_changed"])
        self.assertEqual(len(saved["historical_references"]["incoming"]), 1)
        readable = (app.static_folder / "Core_CandidateReview.txt").read_text("utf-8")
        self.assertEqual(readable, app.core_candidate_text)
        self.assertIn(readable, app.patch.get())
        self.assertTrue(app.patch.get().endswith(app.review["patch_text"]))
        self.assertNotIn("Исторические входящие", app.static_summary.get())
        self.assertTrue((app.static_folder / "DTR_PatchStaticPreview.json").is_file())
        self.assertFalse(app.repository.exists())
        self.assertTrue(app.ai_apply_button.disabled)
        self.assertTrue(app.ai_verify_button.disabled)

    def test_ui02_signature_and_outside_changes_are_readable(self):
        app = self.app()
        proposed = PROPOSED.replace("normalize(value):", "normalize(value, mode=False):").replace(
            "return normalize(value)", "return normalize(value).upper()")
        self.complete(app, proposed)
        report = app.core_candidate_review
        self.assertTrue(report["selected"]["components_changed"]["signature"])
        self.assertTrue(report["file_comparison"]["outside_selected_ast_changed"])
        self.assertIn("сигнатура", app.patch.get())
        self.assertIn("вне выбранной функции: да", app.patch.get())
        self.assertIn("caller", app.patch.get())

    def test_ui03_response_replacement_clears_derived_results(self):
        app = self.app()
        self.complete(app)
        old_folder = app.static_folder
        old_context = app.core_request_context
        raw = response_bytes(app, SOURCE.replace("strip()", "rstrip()"))
        app.accept_bytes(raw)
        self.assertIsNone(app.static_preview)
        self.assertIsNone(app.core_candidate_review)
        self.assertEqual(app.core_candidate_state, "NOT_CHECKED")
        self.assertEqual(app.accepted_response_bytes, raw)
        self.assertEqual(app.core_request_context, old_context)
        self.assertNotIn("Core: структурная проверка", app.patch.get())
        self.assertTrue((old_folder / "Core_CandidateReview.json").is_file())
        app.check_patch_preview()
        self.assertNotEqual(app.static_folder, old_folder)
        self.assertEqual(app.core_candidate_review["response_sha256"], hashlib.sha256(raw).hexdigest())

    def test_ui04_rejected_response_clears_success_and_preserves_request_context(self):
        app = self.app()
        self.complete(app)
        context = app.core_request_context
        rejected = app.accept_bytes(b"{\"not_a_response\": true}\n")
        self.assertFalse(rejected["intake"]["ok"])
        self.assertIsNone(app.accepted_response_bytes)
        self.assertIsNone(app.static_preview)
        self.assertIsNone(app.core_candidate_review)
        self.assertEqual(app.core_request_context, context)
        self.assertTrue(app.static_button.disabled)
        self.assertIsNone(app.check_patch_preview())

    def test_ui05_failed_response_read_intake_or_save_never_leaves_old_success(self):
        for failure in ("oversize", "mutable_bytes", "save_review", "file_read"):
            with self.subTest(failure=failure):
                app = self.app()
                self.complete(app)
                if failure == "oversize":
                    with self.assertRaises(ValueError):
                        app.accept_bytes(b" " * (256 * 1024 + 1))
                elif failure == "mutable_bytes":
                    with self.assertRaises(ValueError):
                        app.accept_bytes(bytearray(response_bytes(app)))
                elif failure == "save_review":
                    with patch.object(app.store, "save_review", side_effect=OSError("owned fixture failure")):
                        with self.assertRaises(OSError):
                            app.accept_bytes(response_bytes(app))
                else:
                    with patch.object(ui.filedialog, "askopenfilename", return_value=str(self.root / "missing.json")):
                        app.import_file()
                self.assertIsNone(app.accepted_response_bytes)
                self.assertIsNone(app.review)
                self.assertIsNone(app.static_preview)
                self.assertIsNone(app.core_candidate_review)
                self.assertTrue(app.static_button.disabled)
                self.assertNotIn("Core: структурная проверка", app.patch.get())
                self.assertEqual(app.review_path.get(), "")

    def test_ui06_generic_prepare_clears_core_and_retains_generic_preview(self):
        app = self.app()
        self.complete(app)
        self.assertTrue(app.prepare())
        self.assertIsNone(app.core_request_context)
        self.assertIsNone(app.accepted_response_bytes)
        self.assertFalse((app.request_folder / "Core_SymbolTaskContext.json").exists())
        self.complete(app)
        self.assertEqual(app.core_candidate_state, "UNBOUND")
        self.assertEqual(app.static_preview["python_ast_parse"], "PASS")
        self.assertFalse((app.static_folder / "Core_CandidateReview.json").exists())

    def test_ui07_task_edit_and_source_selection_clear_binding(self):
        for action in ("instruction", "choose_source"):
            with self.subTest(action=action):
                app = self.app()
                self.complete(app)
                if action == "instruction":
                    app.instruction.set("Другая задача")
                    app.instruction.edit_modified(True)
                    app.instruction_changed()
                else:
                    reader = Mock()
                    reader.capture.return_value = source_snapshot()
                    with patch.object(ui.filedialog, "askopenfilename", return_value=str(app.repository / PATH)), \
                            patch.object(ui.messagebox, "askyesno", return_value=True), \
                            patch.object(ui, "find_git", return_value=Path("/synthetic-git")), \
                            patch.object(ui, "GitSourceReader", return_value=reader):
                        app.choose_source()
                self.assertIsNone(app.request)
                self.assertIsNone(app.core_request_context)
                self.assertIsNone(app.core_request_context_sha256)
                self.assertIsNone(app.accepted_response_bytes)
                self.assertIsNone(app.static_preview)
                self.assertIsNone(app.core_candidate_review)

    def test_ui08_external_request_does_not_restore_existing_sidecar(self):
        app = self.app()
        filename = app.request_folder / "DTR_Request.json"
        context = app.core_request_context
        request, source = restore_request(filename.read_bytes())
        self.complete(app)
        app._load_request(request, source, str(filename))
        self.assertTrue((filename.parent / "Core_SymbolTaskContext.json").exists())
        self.assertTrue(app.imported_session)
        self.assertIsNone(app.core_request_context)
        self.assertIsNone(app.accepted_response_bytes)
        self.complete(app)
        self.assertEqual(app.core_candidate_state, "UNBOUND")
        # Even injected retained bytes do not authenticate an imported session.
        app.accept_bytes(response_bytes(app))
        app.core_request_context = context
        app.core_request_context_sha256 = hashlib.sha256(context).hexdigest()
        preview = app.check_patch_preview()
        self.assertEqual(preview["python_ast_parse"], "PASS")
        self.assertEqual(app.core_candidate_state, "REFUSED")
        self.assertIn("CURRENT_SESSION_REQUIRED", app.core_candidate_text)

    def test_ui09_ai_goal_and_search_report_changes_do_not_rebind_request(self):
        app = self.app()
        context, fingerprint = app.core_request_context, app.request.request_fingerprint
        app.ai_goal.set("Покажи другую функцию без изменений")
        app.ai_goal.edit_modified(True)
        app.ai_goal_changed()
        app.ai_symbol_result["selected"]["qualname"] = "different_live_report"
        app.ai_symbol_report_sha256 = "f" * 64
        with patch.object(ui.threading, "Thread") as thread:
            app.start_context_search()
        thread.return_value.start.assert_called_once()
        self.assertIsNone(app.ai_symbol_result)
        self.assertEqual(app.core_request_context, context)
        self.assertEqual(app.request.request_fingerprint, fingerprint)
        self.complete(app)
        self.assertEqual(app.core_candidate_state, "SAVED")
        self.assertEqual(app.core_candidate_review["selected"]["before"]["qualname"], "normalize")

    def test_ui10_context_tampering_refuses_core_but_keeps_static_receipt(self):
        for mutation in ("bytes", "digest"):
            with self.subTest(mutation=mutation):
                app = self.app()
                app.accept_bytes(response_bytes(app))
                if mutation == "bytes":
                    app.core_request_context += b" "
                else:
                    app.core_request_context_sha256 = "0" * 64
                preview = app.check_patch_preview()
                self.assertEqual(preview["python_ast_parse"], "PASS")
                self.assertEqual(app.core_candidate_state, "REFUSED")
                self.assertIsNone(app.core_candidate_review)
                self.assertFalse((app.static_folder / "Core_CandidateReview.json").exists())
                self.assertTrue((app.static_folder / "DTR_PatchStaticPreview.json").is_file())
                self.assertEqual(app.errors, [])

    def test_ui11_previous_request_context_cannot_bind_a_new_request(self):
        app = self.app()
        old_context, old_sha = app.core_request_context, app.core_request_context_sha256
        self.assertTrue(app.prepare())
        app.core_request_context, app.core_request_context_sha256 = old_context, old_sha
        self.complete(app)
        self.assertEqual(app.core_candidate_state, "REFUSED")
        self.assertIn("CONTEXT_BINDING_MISMATCH", app.core_candidate_text)
        self.assertEqual(app.static_preview["python_ast_parse"], "PASS")

    def test_ui12_rejected_text_or_ast_preview_never_runs_core(self):
        for proposed, bad_patch in ((PROPOSED.replace("return value.strip().lower()", "return ("), None),
                                    (PROPOSED, "diff --git a/modules/wrong.py b/modules/wrong.py\n")):
            with self.subTest(bad_patch=bad_patch):
                app = self.app()
                raw = response_bytes(app, proposed, patch_text=bad_patch)
                self.assertTrue(app.accept_bytes(raw)["intake"]["ok"])
                with patch.object(ui, "review_candidate") as core_review:
                    preview = app.check_patch_preview()
                core_review.assert_not_called()
                self.assertNotEqual(preview["python_ast_parse"], "PASS")
                self.assertEqual(app.core_candidate_state, "PREVIEW_REJECTED")
                self.assertFalse((app.static_folder / "Core_CandidateReview.json").exists())

    def test_ui13_context_persistence_failure_keeps_only_generic_request(self):
        app = self.app(bound=False)
        write = app.store.write
        def fail_context(folder, name, data):
            if name == "Core_SymbolTaskContext.json":
                raise OSError("owned sidecar failure")
            return write(folder, name, data)
        with patch.object(app.store, "write", side_effect=fail_context):
            prepare_bound(app)
        self.assertIsNotNone(app.request)
        self.assertTrue((app.request_folder / "DTR_Request.json").is_file())
        self.assertIsNone(app.core_request_context)
        self.assertIsNone(app.core_request_context_sha256)
        self.assertFalse(app.events[-1]["candidate_review_bound"])
        self.assertIn("привязка Core не сохранена", app.ai_info.get())
        self.assertEqual(app.errors, [])
        self.complete(app)
        self.assertEqual(app.core_candidate_state, "UNBOUND")

    def test_ui14_static_receipt_write_failure_does_not_run_core_or_cache_success(self):
        app = self.app()
        app.accept_bytes(response_bytes(app))
        with patch.object(app.store, "save_static_preview", side_effect=OSError("owned static save failure")), \
                patch.object(ui, "review_candidate") as core_review:
            self.assertIsNone(app.check_patch_preview())
        core_review.assert_not_called()
        self.assertIsNone(app.static_preview)
        self.assertIsNone(app.static_folder)
        self.assertIsNone(app.core_candidate_review)
        self.assertIsNone(app.static_input_sha256)
        self.assertTrue(app.errors)

    def test_ui15_partial_core_save_is_distinct_and_cached_without_retry(self):
        for failed_name in ("Core_CandidateReview.json", "Core_CandidateReview.txt"):
            with self.subTest(failed_name=failed_name):
                app = self.app()
                app.accept_bytes(response_bytes(app))
                write = app.store.write
                def fail_core(folder, name, data):
                    if name == failed_name:
                        raise OSError("owned candidate save failure")
                    return write(folder, name, data)
                with patch.object(app.store, "write", side_effect=fail_core):
                    preview = app.check_patch_preview()
                self.assertEqual(preview["python_ast_parse"], "PASS")
                self.assertEqual(app.core_candidate_state, "SAVE_FAILED")
                self.assertIsNone(app.core_candidate_review)
                self.assertTrue((app.static_folder / "DTR_PatchStaticPreview.json").is_file())
                self.assertEqual((app.static_folder / "Core_CandidateReview.json").exists(),
                                 failed_name == "Core_CandidateReview.txt")
                self.assertFalse(any(event["event"] == "CORE_CANDIDATE_REVIEW_SAVED" for event in app.events))
                displayed = app.patch.get()
                with patch.object(app.store, "write") as save, patch.object(ui, "review_candidate") as core_review:
                    self.assertEqual(app.check_patch_preview(), preview)
                save.assert_not_called()
                core_review.assert_not_called()
                self.assertEqual(app.patch.get(), displayed)
                self.assertIn("ошибка сохранения", app.status.get())

    def test_ui16_cache_preserves_full_display_and_does_not_recompute_or_rewrite(self):
        app = self.app()
        _, preview = self.complete(app)
        displayed, folder, review = app.patch.get(), app.static_folder, copy.deepcopy(app.core_candidate_review)
        with patch.object(app.store, "save_static_preview") as save_static, \
                patch.object(app.store, "write") as write, patch.object(ui, "review_candidate") as core_review:
            self.assertEqual(app.check_patch_preview(), preview)
        save_static.assert_not_called()
        write.assert_not_called()
        core_review.assert_not_called()
        self.assertEqual(app.static_folder, folder)
        self.assertEqual(app.core_candidate_review, review)
        self.assertEqual(app.patch.get(), displayed)
        self.assertIn("структурный отчёт сохранён", app.status.get())

    def test_ui17_changed_cached_inputs_invalidate_instead_of_showing_old_success(self):
        for mutation in ("context", "digest", "raw", "review", "source", "request", "imported"):
            with self.subTest(mutation=mutation):
                app = self.app()
                self.complete(app)
                if mutation == "context":
                    app.core_request_context += b" "
                elif mutation == "digest":
                    app.core_request_context_sha256 = "f" * 64
                elif mutation == "raw":
                    app.accepted_response_bytes += b" "
                elif mutation == "review":
                    app.review["patch_text"] += "unexpected\n"
                elif mutation == "source":
                    app.source = replace(app.source, content=app.source.content + b"# changed\n")
                elif mutation == "request":
                    app.request = replace(app.request, title="Different request")
                else:
                    app.imported_session = True
                with patch.object(ui, "review_candidate") as core_review:
                    self.assertIsNone(app.check_patch_preview())
                core_review.assert_not_called()
                self.assertIsNone(app.request)
                self.assertIsNone(app.accepted_response_bytes)
                self.assertIsNone(app.core_request_context)
                self.assertIsNone(app.static_preview)
                self.assertIsNone(app.core_candidate_review)
                self.assertIn("Привязка сохранённой проверки изменилась", app.errors[-1])

    def test_ui18_missing_saved_core_artifact_never_displays_cached_success(self):
        app = self.app()
        _, preview = self.complete(app)
        (app.static_folder / "Core_CandidateReview.txt").unlink()
        self.assertEqual(app.check_patch_preview(), preview)
        self.assertEqual(app.core_candidate_state, "SAVE_FAILED")
        self.assertIsNone(app.core_candidate_review)
        self.assertIn("отсутствуют или изменились", app.patch.get())
        self.assertNotIn("структурный отчёт сохранён", app.status.get())

    def test_ui19_missing_saved_static_receipt_clears_both_results(self):
        app = self.app()
        self.complete(app)
        (app.static_folder / "DTR_PatchStaticPreview.json").unlink()
        self.assertIsNone(app.check_patch_preview())
        self.assertIsNone(app.static_preview)
        self.assertIsNone(app.core_candidate_review)
        self.assertIsNone(app.accepted_response_bytes)
        self.assertTrue(app.errors)

    def test_ui20_demo_uses_generic_flow_and_does_not_reuse_core(self):
        app = self.app()
        self.complete(app)
        with patch.object(ui, "GitSourceReader") as reader:
            app.run_demo()
        reader.assert_not_called()
        self.assertIsNone(app.core_request_context)
        self.assertIsNone(app.core_request_context_sha256)
        self.assertIsNone(app.core_candidate_review)
        self.assertEqual(app.source.provenance["kind"], "DEMO_SYNTHETIC_NOT_REPOSITORY")
        self.assertTrue(app.review["intake"]["ok"])
        self.assertEqual(app.check_patch_preview()["python_ast_parse"], "PASS")
        self.assertEqual(app.core_candidate_state, "UNBOUND")

    def test_ui21_mutated_review_before_first_preview_is_not_authoritative(self):
        app = self.app()
        app.accept_bytes(response_bytes(app))
        app.review["patch_text"] = app.review["patch_text"].replace("lower()", "upper()")
        with patch.object(ui, "preview_patch_in_memory") as preview, patch.object(ui, "review_candidate") as core_review:
            self.assertIsNone(app.check_patch_preview())
        preview.assert_not_called()
        core_review.assert_not_called()
        self.assertIsNone(app.review)
        self.assertIsNone(app.accepted_response_bytes)
        self.assertIsNone(app.static_preview)

    def test_ui22_unexpected_engine_failure_keeps_static_receipt_separate(self):
        app = self.app()
        app.accept_bytes(response_bytes(app))
        with patch.object(ui, "review_candidate", side_effect=RuntimeError("owned failure")):
            preview = app.check_patch_preview()
        self.assertEqual(preview["python_ast_parse"], "PASS")
        self.assertEqual(app.core_candidate_state, "FAILED")
        self.assertIsNone(app.core_candidate_review)
        self.assertFalse((app.static_folder / "Core_CandidateReview.json").exists())
        self.assertTrue((app.static_folder / "DTR_PatchStaticPreview.json").is_file())
        self.assertEqual(app.errors, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
