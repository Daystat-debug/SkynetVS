"""Focused structural-investigation checks using synthetic sources and owned Git.

No application, model, training, SQLite, live data or project-source execution.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from modules.developer_task_ui.app import symbol_investigation as subject

COMMIT = "1" * 40
GOAL = "Исследуй выбранную функцию"


def analyze(sources, selector="run", scan=None):
    return subject.investigate_sources(COMMIT, sources, scan, GOAL, selector)


def callees(report):
    return [row["callee"]["qualname"] for row in report["outgoing"]]


def reasons(report):
    return {row["reason"] for row in report["unknown_outgoing"]}


class CoreSymbolInvestigationTests(unittest.TestCase):
    def test_definition_references_and_exact_source_identity(self):
        text = "def target():\n    return 1\n\ndef run():\n    return target()\n"
        result = analyze({"modules/a.py": text})
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(callees(result), ["target"])
        self.assertEqual(result["selected"]["start"], 4)
        self.assertEqual(result["outgoing"][0]["call_site"]["line"], 5)
        self.assertEqual(result["selected"]["source_sha256"], hashlib.sha256(text.encode()).hexdigest())
        raw = text.encode()
        oid = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
        self.assertEqual(result["selected"]["blob_oid"], oid)
        incoming = analyze({"modules/a.py": text}, "target")["incoming"]
        self.assertEqual([edge["caller"]["qualname"] for edge in incoming], ["run"])
        self.assertFalse(result["runtime_calls_proven"])
        self.assertFalse(result["git_head_observed"])

    def test_ambiguous_names_require_explicit_selection(self):
        sources = {"modules/a.py": "def run():\n    pass\n",
                   "modules/b.py": "def run():\n    pass\n"}
        result = analyze(sources)
        self.assertEqual(result["status"], "CHOICE_REQUIRED")
        self.assertIsNone(result["selected"])
        self.assertEqual(len(result["candidates"]), 2)
        chosen = analyze(sources, "modules/b.py::run@1")
        self.assertEqual(chosen["selected"]["path"], "modules/b.py")
        self.assertEqual(analyze(sources, "missing")["status"], "NOT_FOUND")

    def test_duplicate_definition_line_selection_does_not_resolve_rebinding(self):
        sources = {"modules/a.py": "def target():\n    pass\ndef target():\n    pass\ndef run():\n    target()\n"}
        self.assertEqual(analyze(sources, "target")["status"], "CHOICE_REQUIRED")
        selected = analyze(sources, "modules/a.py::target@1")
        self.assertEqual(selected["status"], "COMPLETE")
        self.assertEqual(selected["incoming"], [])
        self.assertIn("REBOUND_OR_DUPLICATE_NAME", reasons(analyze(sources)))

    def test_explicit_absolute_module_import_and_alias(self):
        sources = {"modules/a.py": "def target():\n    pass\n",
                   "modules/b.py": "import modules.a as alias\ndef run():\n    alias.target()\n"}
        result = analyze(sources)
        self.assertEqual(callees(result), ["target"])
        self.assertEqual(result["outgoing"][0]["resolution"], "EXPLICIT_IMPORT")
        sources["modules/b.py"] = "import modules.a\ndef run():\n    modules.a.target()\n"
        self.assertEqual(callees(analyze(sources)), ["target"])

    def test_explicit_relative_and_function_local_import(self):
        sources = {"modules/pkg/a.py": "def target():\n    pass\n",
                   "modules/pkg/b.py": "from .a import target as chosen\ndef run():\n    chosen()\n"}
        self.assertEqual(callees(analyze(sources)), ["target"])
        sources["modules/pkg/b.py"] = "def run():\n    from .a import target\n    target()\n"
        self.assertEqual(callees(analyze(sources)), ["target"])

    def test_from_package_submodule_requires_observed_unambiguous_parent(self):
        sources = {"modules/pkg/__init__.py": "# known empty package\n",
                   "modules/pkg/a.py": "def target():\n    pass\n",
                   "modules/use.py": "from modules.pkg import a\ndef run():\n    a.target()\n"}
        self.assertEqual(callees(analyze(sources)), ["target"])
        del sources["modules/pkg/__init__.py"]
        self.assertIn("AMBIGUOUS_IMPORTED_ATTRIBUTE", reasons(analyze(sources)))
        sources["modules/pkg/__init__.py"] = "def __getattr__(name):\n    return object()\n"
        self.assertIn("AMBIGUOUS_IMPORTED_ATTRIBUTE", reasons(analyze(sources)))
        sources["modules/pkg/__init__.py"] = "a = object()\n"
        self.assertEqual(analyze(sources)["outgoing"], [])

    def test_parameter_shadows_module_function(self):
        result = analyze({"modules/a.py": "def target():\n    pass\ndef run(target):\n    target()\n"})
        self.assertEqual(result["outgoing"], [])
        self.assertIn("PARAMETER_OR_LOCAL_BINDING", reasons(result))

    def test_assignment_after_call_is_local_binding(self):
        result = analyze({"modules/a.py": "def target():\n    pass\ndef run():\n    target()\n    target = None\n"})
        self.assertEqual(result["outgoing"], [])
        self.assertIn("PARAMETER_OR_LOCAL_BINDING", reasons(result))

    def test_closure_and_nonlocal_are_not_global_edges(self):
        source = ("def target():\n    pass\ndef outer(target):\n"
                  "    def run():\n        target()\n    return run\n")
        result = analyze({"modules/a.py": source}, "outer.run")
        self.assertEqual(result["outgoing"], [])
        source = source.replace("    def run():\n", "    def run():\n        nonlocal target\n")
        self.assertIn("GLOBAL_OR_NONLOCAL_BINDING", reasons(analyze({"modules/a.py": source}, "outer.run")))

    def test_global_rebinding_elsewhere_invalidates_stable_module_target(self):
        source = ("def target():\n    pass\ndef replace():\n    global target\n"
                  "    target = lambda: 1\ndef run():\n    target()\n")
        result = analyze({"modules/a.py": source})
        self.assertEqual(result["outgoing"], [])
        self.assertIn("GLOBAL_OR_NONLOCAL_BINDING", reasons(result))

    def test_class_global_and_descendant_nonlocal_rebindings_are_unknown(self):
        source = ("def target():\n    pass\nclass Rebind:\n    global target\n"
                  "    target = lambda: 1\ndef run():\n    target()\n")
        self.assertEqual(analyze({"modules/a.py": source})["outgoing"], [])
        self.assertIn("GLOBAL_OR_NONLOCAL_BINDING", reasons(analyze({"modules/a.py": source})))
        sources = {"modules/a.py": "def target():\n    pass\n",
                   "modules/b.py": ("def run():\n    import modules.a as item\n"
                                    "    class Rebind:\n        nonlocal item\n"
                                    "        item = replacement\n    item.target()\n")}
        self.assertEqual(analyze(sources)["outgoing"], [])
        self.assertIn("GLOBAL_OR_NONLOCAL_BINDING", reasons(analyze(sources)))

    def test_star_import_does_not_prove_binding(self):
        source = "from external import *\ndef target():\n    pass\ndef run():\n    target()\n"
        result = analyze({"modules/a.py": source})
        self.assertEqual(result["outgoing"], [])
        self.assertIn("STAR_IMPORT", reasons(result))

    def test_decorated_target_is_unknown(self):
        source = "@wrap\ndef target():\n    pass\ndef run():\n    target()\n"
        result = analyze({"modules/a.py": source})
        self.assertEqual(result["outgoing"], [])
        self.assertIn("DECORATED_TARGET", reasons(result))

    def test_conditional_definition_and_import_are_unknown(self):
        source = "if flag:\n    def target():\n        pass\ndef run():\n    target()\n"
        self.assertIn("CONDITIONAL_BINDING", reasons(analyze({"modules/a.py": source})))
        sources = {"modules/a.py": "def target():\n    pass\n",
                   "modules/b.py": "def run():\n    if flag:\n        from modules.a import target\n    target()\n"}
        self.assertIn("CONDITIONAL_BINDING", reasons(analyze(sources)))

    def test_module_reassignment_and_deletion_are_unknown(self):
        prefix = "def target():\n    pass\n"
        suffix = "def run():\n    target()\n"
        for middle in ("target = other\n", "del target\n"):
            with self.subTest(middle=middle):
                result = analyze({"modules/a.py": prefix + middle + suffix})
                self.assertEqual(result["outgoing"], [])
                self.assertIn("REBOUND_OR_DUPLICATE_NAME", reasons(result))

    def test_dynamic_self_cls_callbacks_and_factory_results_are_unknown(self):
        source = ("def target():\n    pass\nclass Box:\n    def run(self, callback):\n"
                  "        self.target()\n        cls.target()\n        callback()\n        factory()()\n")
        result = analyze({"modules/a.py": source}, "Box.run")
        self.assertEqual(result["outgoing"], [])
        self.assertTrue({"DYNAMIC_SELF_OR_CLS_ATTRIBUTE", "PARAMETER_OR_LOCAL_BINDING",
                         "DYNAMIC_CALL_EXPRESSION"}.issubset(reasons(result)))

    def test_imported_object_attribute_rebinding_is_unknown(self):
        sources = {"modules/a.py": "def target():\n    pass\n",
                   "modules/b.py": "import modules.a as item\nitem.target = replacement\ndef run():\n    item.target()\n"}
        self.assertIn("ATTRIBUTE_REBINDING", reasons(analyze(sources)))

    def test_nested_functions_have_their_own_call_ownership(self):
        source = ("def target():\n    pass\ndef run():\n    def inner():\n"
                  "        target()\n    return inner\n")
        sources = {"modules/a.py": source}
        self.assertEqual(analyze(sources)["outgoing"], [])
        self.assertEqual(callees(analyze(sources, "run.inner")), ["target"])
        target = analyze(sources, "target")
        self.assertEqual([row["caller"]["qualname"] for row in target["incoming"]], ["run.inner"])

    def test_lambda_comprehension_and_default_contexts_are_not_resolved(self):
        source = ("def target():\n    pass\ndef run():\n    thunk = lambda: target()\n"
                  "    values = [target() for target in callbacks]\n"
                  "    def inner(value=target()):\n        pass\n")
        result = analyze({"modules/a.py": source})
        self.assertEqual(result["outgoing"], [])
        self.assertTrue({"LAMBDA_SCOPE_NOT_RESOLVED", "COMPREHENSION_SCOPE_NOT_RESOLVED",
                         "DEFINITION_TIME_CONTEXT"}.issubset(reasons(result)))

    def test_method_body_does_not_close_over_class_namespace(self):
        source = ("def target():\n    pass\nclass Box:\n    target = other\n"
                  "    def run(self):\n        target()\n")
        result = analyze({"modules/a.py": source}, "Box.run")
        self.assertEqual(callees(result), ["target"])
        self.assertEqual(result["outgoing"][0]["callee"]["start"], 1)

    def test_generic_type_parameter_is_not_a_module_function(self):
        function = "def target():\n    pass\ndef run[target]():\n    target()\n"
        result = analyze({"modules/a.py": function})
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(result["outgoing"], [])
        self.assertIn("TYPE_PARAMETER_BINDING", reasons(result))
        cls = "def target():\n    pass\nclass Box[target]:\n    def run(self):\n        target()\n"
        self.assertIn("TYPE_PARAMETER_BINDING", reasons(analyze({"modules/a.py": cls}, "Box.run")))
        alias = "def target():\n    pass\ntype Alias[target] = target()\n"
        result = analyze({"modules/a.py": alias}, "target")
        self.assertEqual(result["incoming"], [])
        self.assertEqual(result["coverage"]["unknown_reason_counts"]["TYPE_ALIAS_SCOPE_NOT_RESOLVED"], 1)
        bounded = "def target():\n    pass\ndef run[T: target()]():\n    pass\n"
        result = analyze({"modules/a.py": bounded}, "target")
        self.assertEqual(result["incoming"], [])
        self.assertEqual(result["coverage"]["unknown_reason_counts"]["DEFINITION_TIME_CONTEXT"], 1)

    def test_reexport_and_ambiguous_module_are_not_followed(self):
        sources = {"modules/a.py": "def target():\n    pass\n",
                   "modules/b.py": "from modules.a import target\n",
                   "modules/use.py": "from modules.b import target\ndef run():\n    target()\n"}
        self.assertIn("TARGET_NOT_MODULE_FUNCTION", reasons(analyze(sources)))
        sources["modules/b/__init__.py"] = "def target():\n    pass\n"
        self.assertIn("EXTERNAL_OR_AMBIGUOUS_MODULE", reasons(analyze(sources)))

    def test_parse_failure_and_scanner_skips_are_visible(self):
        sources = {"modules/a.py": "def run():\n    pass\n", "modules/b.py": "def broken(:\n"}
        scan = {"partial": True, "skipped": {"too_large": 2, "not_utf8": 1}, "sources_read": 2}
        result = analyze(sources, scan=scan)
        self.assertEqual(result["status"], "COMPLETE")
        self.assertTrue(result["coverage"]["partial"])
        self.assertEqual(result["coverage"]["parsed_files"], 1)
        shown = subject.format_investigation(result)
        self.assertIn("пропущено источников 3", shown)
        self.assertIn("modules/b.py", shown)

    def test_ast_and_output_budgets_report_partial_results(self):
        sources = {"modules/a.py": "def target():\n    pass\ndef run():\n    target()\n    target()\n"}
        with mock.patch.object(subject, "MAX_RESULT_ROWS", 1):
            result = analyze(sources)
        self.assertEqual(len(result["outgoing"]), 1)
        self.assertEqual(result["coverage"]["truncated"]["outgoing"], 1)
        self.assertTrue(result["coverage"]["partial"])
        with mock.patch.object(subject, "MAX_AST_NODES_PER_FILE", 1):
            result = analyze(sources)
        self.assertEqual(result["status"], "NOT_FOUND")
        self.assertEqual(result["coverage"]["parse_diagnostics"][0]["reason"], "AST_NODE_BUDGET")
        with mock.patch.object(subject, "MAX_CALL_SITES", 1):
            result = analyze(sources)
        self.assertEqual(result["coverage"]["counts"]["call_sites_omitted"], 1)

    def test_source_is_data_and_report_omits_literals_and_goal(self):
        secret = "PRIVATE_LITERAL_NOT_EVIDENCE_117"
        source = f"raise RuntimeError({secret!r})\ndef run(callback):\n    callback({secret!r})\n"
        result = analyze({"modules/a.py": source})
        encoded = json.dumps(result, ensure_ascii=False)
        self.assertNotIn(secret, encoded)
        self.assertNotIn(GOAL, encoded)
        self.assertFalse(result["source_code_executed"])
        self.assertFalse(result["source_text_included"])
        self.assertIn("имя затенено", subject.format_investigation(result))

    def test_invalid_selectors_paths_and_budgets_refuse(self):
        sources = {"modules/a.py": "def run():\n    pass\n"}
        for selector in ("", "../../x.py::run", "run@0", "run()", "run@bogus"):
            with self.subTest(selector=selector), self.assertRaises(subject.InvestigationRefusal):
                analyze(sources, selector)
        with self.assertRaises(subject.InvestigationRefusal):
            analyze({"data/private.py": "def run(): pass"})
        with mock.patch.object(subject, "MAX_FILE_BYTES", 1), self.assertRaises(subject.InvestigationRefusal):
            analyze(sources)
        with mock.patch("modules.developer_task_ui.app.context_search.scan_head") as scan:
            for goal, selector in (("", "run"), (GOAL, "run()")):
                with self.assertRaises(subject.InvestigationRefusal):
                    subject.investigate_repository(Path("unused"), goal, selector, reader=object())
            scan.assert_not_called()

    def test_wrapper_reads_one_snapshot_and_distinguishes_observed_provenance(self):
        sources = {"modules/a.py": "def run():\n    pass\n"}
        reader = SimpleNamespace(_sha=lambda *args: COMMIT)
        with mock.patch("modules.developer_task_ui.app.context_search.scan_head",
                        return_value=(COMMIT, sources, {"partial": False})) as scan:
            result = subject.investigate_repository(Path("unused"), GOAL, "run", reader=reader,
                                                    expected_commit=COMMIT)
        scan.assert_called_once()
        self.assertTrue(result["git_head_observed"])
        self.assertEqual(result["source_binding"], "OBSERVED_GIT_HEAD_BLOBS")

    def test_wrapper_refuses_expected_commit_and_final_head_drift(self):
        sources = {"modules/a.py": "def run():\n    pass\n"}
        with mock.patch("modules.developer_task_ui.app.context_search.scan_head",
                        return_value=(COMMIT, sources, {})):
            with self.assertRaisesRegex(subject.InvestigationRefusal, "EXPECTED_COMMIT_CHANGED"):
                subject.investigate_repository(Path("unused"), GOAL, "run",
                                               reader=SimpleNamespace(_sha=lambda *args: COMMIT),
                                               expected_commit="2" * 40)
            with self.assertRaisesRegex(subject.InvestigationRefusal, "HEAD_CHANGED"):
                subject.investigate_repository(Path("unused"), GOAL, "run",
                                               reader=SimpleNamespace(_sha=lambda *args: "2" * 40))

    def test_owned_git_ignores_dirty_source_and_preserves_index_and_head(self):
        git = shutil.which("git")
        self.assertIsNotNone(git, "Git is required for the owned-repository integration case")
        env = {key: value for key, value in os.environ.items()
               if not key.upper().startswith(("GIT_", "PYTHON", "SSH_"))}
        env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                   GIT_CONFIG_SYSTEM=os.devnull, GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0")
        with tempfile.TemporaryDirectory(prefix="skynetvs_core_symbol_") as temporary:
            root = Path(temporary)
            def run(*args):
                return subprocess.run([git, "--no-optional-locks", "-C", str(root), *args],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      env=env, check=True, timeout=15).stdout
            run("init")
            (root / "modules").mkdir()
            committed = "def target():\n    pass\ndef run():\n    target()\n"
            path = root / "modules/a.py"
            path.write_bytes(committed.encode())
            run("add", "modules/a.py")
            run("-c", "user.name=Core Test", "-c", "user.email=core-test@example.invalid",
                "-c", "commit.gpgsign=false", "commit", "-m", "owned synthetic source")
            head_before = run("rev-parse", "HEAD").strip().decode()
            index_before = (root / ".git/index").read_bytes()
            dirty = "raise RuntimeError('dirty source must never run')\n"
            path.write_bytes(dirty.encode())
            (root / "untracked.txt").write_text("owned untracked evidence", encoding="utf-8")
            result = subject.investigate_repository(root, GOAL, "run")
            self.assertEqual(result["git_commit"], head_before)
            self.assertEqual(callees(result), ["target"])
            self.assertEqual(path.read_bytes(), dirty.encode())
            self.assertEqual((root / ".git/index").read_bytes(), index_before)
            self.assertEqual(run("rev-parse", "HEAD").strip().decode(), head_before)
            self.assertTrue(result["repo_worktree_not_read"])
            self.assertEqual((root / "untracked.txt").read_text(), "owned untracked evidence")


if __name__ == "__main__":
    unittest.main(verbosity=2)
