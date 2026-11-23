"""Targeted checks. Run explicitly; never discover or execute repository tests here."""
import csv
import json
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import measure
import nav


ROOT = Path("docs/maintenance/navigation_01")
SUITE = json.loads((ROOT / "questions.json").read_text("utf-8"))


class NavigationChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snap = nav.Snapshot(SUITE["snapshot"])
        cls.index = nav.Index(cls.snap)

    def test_every_tracked_path_once(self):
        tracked = nav.git("ls-tree", "-rz", "--name-only", self.snap.sha).decode().split("\0")[:-1]
        expected = list(nav.audit(self.snap))
        stored = (ROOT / "inventory.tsv").read_text("utf-8").splitlines()
        self.assertEqual(expected, stored)
        rows = list(csv.DictReader(stored, delimiter="\t"))
        self.assertEqual(sorted(tracked), [r["path"] for r in rows])
        self.assertFalse(any(r["role"] == "unclassified" for r in rows))

    def test_python_parsed_and_edge_coordinate(self):
        self.assertFalse(self.index.errors)
        owner = "modules/command_processor.py"
        source = dict(self.snap.sources([owner]))[owner].decode().splitlines()
        line = self.index.deps[owner]["modules/command_runtime.py"]
        self.assertIn("from modules.command_runtime import", source[line - 1])

    def test_overwritten_name(self):
        self.assertEqual(self.index.defs["ReminderRepository"], [
            nav.Site("modules/reminder_repository.py", 131),
            nav.Site("modules/reminder_repository.py", 136)])

    def test_bundle_not_merged(self):
        target = "modules/developer/developer_task_contract.py"
        self.assertEqual({s.path for s in self.index.defs["DeveloperTaskManifest"]},
                         {target, nav.UI + "vendor/" + target})
        self.assertEqual(nav.resolve(nav.UI + "app/core.py", "modules.developer.developer_task_contract",
                                     0, self.snap.python_blobs), nav.UI + "vendor/" + target)
        self.assertIn("select a path", self.index.find("DeveloperTaskManifest", 8))

    def test_literal_is_not_an_import(self):
        target = "test.py"
        line = self.index.literals[target]["tools/pipeline.py"]
        self.assertEqual(line, 1073)
        self.assertNotIn(target, self.index.deps["tools/pipeline.py"])
        self.assertNotIn("test.py", self.index.users["tools/pipeline.py"])

    def test_no_match_and_limit(self):
        self.assertIn("definitions (0)", self.index.find("MissingNavigationSymbolXYZ", 2))
        self.assertIn("more", self.index.find("CommandProcessor", 2))
        self.assertEqual(self.index.file_rows("../local.py", 2), ["no tracked path"])

    def test_cards(self):
        for row in nav.topics(self.snap, None):
            with self.subTest(row=row):
                self.assertEqual(len(nav.topics(self.snap, row.split()[0])), 4)

    def test_ui_import_root_limit_and_task_route(self):
        test_file = "tools/eval_core_symbol_ui.py"
        target = nav.UI + "app/ui.py"
        contents = dict(self.snap.sources([test_file]))[test_file].decode()
        self.assertIn("from app import ui", contents)
        self.assertIn('str(BUNDLE / "vendor")', contents)
        # The external harness sets sys.path. Generic repository layout misses this edge.
        self.assertNotIn(test_file, self.index.users[target])
        self.assertIn(f"check: {test_file}", nav.topics(self.snap, "ui"))

    def test_quick_cli_bytes(self):
        symbols = [c[0] for c in SUITE["cases"]]
        actual = subprocess.check_output([sys.executable, "-I", "-S", "-B",
                                          "tools/navigation_lab/nav.py", "--snapshot",
                                          self.snap.sha, "quick", *symbols])
        self.assertEqual(actual, measure.render(["snapshot " + self.snap.sha] +
                                                [self.index.brief(s, 8) for s in symbols]))

    def test_partial_and_full_index_agree_on_frozen_tasks(self):
        symbols = [c[0] for c in SUITE["cases"]] + ["DeveloperTaskManifest", "ReminderRepository"]
        quick = nav.quick_index(self.snap, symbols)
        for symbol in symbols:
            with self.subTest(symbol=symbol):
                self.assertEqual(quick.brief(symbol, 8), self.index.brief(symbol, 8))
        for case in SUITE["cases"]:
            actual = self.index.brief(case[0], 8)
            self.assertNotIn(False, measure.coverage(actual, case, "index").values())
            if case[2] is None:
                self.assertIn("imports (0)", actual)


if __name__ == "__main__":
    unittest.main(verbosity=2)
