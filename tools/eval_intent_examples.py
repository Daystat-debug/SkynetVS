"""Regression checks for shared intent examples; all CLI data is temporary."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from modules.learning.intent_examples import add_example


class IntentExamplesTests(unittest.TestCase):
    def test_normalizes_and_adds_to_existing_intent(self) -> None:
        data = {"intents": [{"intent": "GREET", "examples": ["hello"]}]}
        self.assertTrue(add_example(data, " greet ", "  ПРИВЕТ\t МИР \n"))
        self.assertEqual(data["intents"][0]["examples"], ["hello", "привет мир"])
        self.assertEqual(len(data["intents"]), 1)

    def test_duplicate_does_not_modify_data(self) -> None:
        data = {"intents": [{"intent": "GREET", "examples": ["  HELLO   world  "]}]}
        before = copy.deepcopy(data)
        self.assertFalse(add_example(data, "GREET", "hello\tworld"))
        self.assertEqual(data, before)

    def test_creates_missing_intent(self) -> None:
        data: dict = {}
        self.assertTrue(add_example(data, " open_app ", " OPEN  NOTEPAD "))
        self.assertEqual(data, {"intents": [{"intent": "OPEN_APP", "examples": ["open notepad"]}]})

    def test_empty_values_do_not_modify_data(self) -> None:
        for intent, phrase in ((" ", "hello"), ("GREET", " \t\n")):
            with self.subTest(intent=intent, phrase=phrase):
                data = {"intents": [{"intent": "GREET", "examples": ["hello"]}]}
                before = copy.deepcopy(data)
                self.assertFalse(add_example(data, intent, phrase))
                self.assertEqual(data, before)

    def test_preserves_replacement_of_non_list_examples(self) -> None:
        data = {"intents": [{"intent": "GREET", "examples": None}]}
        self.assertTrue(add_example(data, "GREET", "hello"))
        self.assertEqual(data["intents"][0]["examples"], ["hello"])

    def test_legacy_import_is_the_same_helper(self) -> None:
        from tools.label_inbox import add_example as legacy_add_example

        self.assertIs(legacy_add_example, add_example)

    def test_voice_confirmation_works_without_tools_imports(self) -> None:
        code = r'''
import importlib.abc
import sys
sys.path.insert(0, sys.argv[1])
class RejectTools(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "tools" or fullname.startswith("tools."):
            raise ModuleNotFoundError("Runtime attempted to import tools")
sys.meta_path.insert(0, RejectTools())
from modules.learning.confirmed_voice_learning import ConfirmedVoiceLearning
data = {"intents": [{"intent": "GREET", "examples": ["hello"]}]}
session = ConfirmedVoiceLearning(data=data, operator_allowed_intents=frozenset({"GREET"}), clock=lambda: 0)
assert session.arm("GREET").code == "AWAIT_PHRASE"
assert session.on_transcript("good morning").code == "CONFIRM_REQUIRED"
result = session.on_transcript("\u0434\u0430")
assert result.code == "EXAMPLE_CONFIRMED_CANDIDATE_ONLY"
assert result.preview_data["intents"][0]["examples"] == ["hello", "good morning"]
assert data["intents"][0]["examples"] == ["hello"]
assert result.row["approved"] is True
assert not any(name == "tools" or name.startswith("tools.") for name in sys.modules)
print("VOICE_CONFIRMATION_WITHOUT_TOOLS=PASS")
'''
        result = subprocess.run(
            [sys.executable, "-I", "-S", "-B", "-c", code, str(PROJECT_ROOT)],
            capture_output=True, text=True, encoding="utf-8", timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("VOICE_CONFIRMATION_WITHOUT_TOOLS=PASS", result.stdout)

    def _run_cli(self, *, module: bool) -> None:
        with tempfile.TemporaryDirectory(prefix="skynetvs_intent_examples_") as directory:
            root = Path(directory)
            data = root / "data"
            data.mkdir()
            (data / "intents.json").write_text(
                json.dumps({"intents": [{"intent": "GREET", "examples": ["hello"]}]}), encoding="utf-8",
            )
            (data / "inbox_unlabeled.jsonl").write_text(
                json.dumps({"text": "Good Morning", "meta": {}}) + "\n", encoding="utf-8",
            )
            if module:
                # A minimal temporary project makes -m resolve from cwd without
                # using PYTHONPATH or touching the real project's data files.
                for relative in (
                    "modules/__init__.py", "modules/learning/__init__.py",
                    "modules/learning/intent_examples.py", "tools/label_inbox.py",
                ):
                    destination = root / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(PROJECT_ROOT / relative, destination)
                command = [sys.executable, "-S", "-B", "-X", "utf8", "-m", "tools.label_inbox"]
            else:
                command = [sys.executable, "-I", "-S", "-B", "-X", "utf8", str(PROJECT_ROOT / "tools/label_inbox.py")]
            result = subprocess.run(
                command, cwd=root, input="1\n", capture_output=True,
                text=True, encoding="utf-8", timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            updated = json.loads((data / "intents.json").read_text(encoding="utf-8"))
            self.assertEqual(updated["intents"][0]["examples"], ["hello", "good morning"])
            labeled = [json.loads(line) for line in (data / "inbox_labeled.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(labeled), 1)
            self.assertEqual(labeled[0]["label"], "GREET")
            self.assertIs(labeled[0]["added"], True)

    def test_documented_direct_cli(self) -> None:
        self._run_cli(module=False)

    def test_module_cli(self) -> None:
        self._run_cli(module=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
