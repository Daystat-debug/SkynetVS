"""Error-log regression checks; all output and configuration are temporary."""
from __future__ import annotations

from datetime import datetime
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ERROR_LOG_SOURCE = PROJECT_ROOT / "modules/core/error_log.py"
# Keep even a direct invocation from creating bytecode in the source tree.
sys.dont_write_bytecode = True


class ErrorLogTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="skynetvs_error_log_")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        original_cwd = Path.cwd()
        self.addCleanup(os.chdir, original_cwd)
        os.chdir(self.root)
        environment = mock.patch.dict(os.environ)
        environment.start()
        self.addCleanup(environment.stop)
        os.environ.pop("ERROR_LOG_PATH", None)

        # Import before setting the path, just as main imports actions/audio
        # before loading .env. Only the stdlib logger is imported here.
        spec = importlib.util.spec_from_file_location("error_log_under_test", ERROR_LOG_SOURCE)
        assert spec is not None and spec.loader is not None
        self.logger = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.logger)

    def rows(self, relative: str | Path) -> list[dict]:
        path = self.root / relative
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def test_import_does_not_create_logs(self) -> None:
        self.assertEqual(list(self.root.iterdir()), [])

    def test_path_set_after_import_is_used(self) -> None:
        os.environ["ERROR_LOG_PATH"] = "late/errors.jsonl"
        self.logger.log_error("late-config", "configured after import")
        self.assertEqual(self.rows("late/errors.jsonl")[0]["source"], "late-config")
        self.assertFalse((self.root / "data/logs/errors.jsonl").exists())

    def test_destination_changes_between_calls(self) -> None:
        os.environ["ERROR_LOG_PATH"] = "first/errors.jsonl"
        self.logger.log_error("test", "first")
        os.environ["ERROR_LOG_PATH"] = "second/errors.jsonl"
        self.logger.log_error("test", "second")
        os.environ.pop("ERROR_LOG_PATH")
        self.logger.log_error("test", "default")
        self.assertEqual([row["message"] for row in self.rows("first/errors.jsonl")], ["first"])
        self.assertEqual([row["message"] for row in self.rows("second/errors.jsonl")], ["second"])
        self.assertEqual([row["message"] for row in self.rows("data/logs/errors.jsonl")], ["default"])

    def test_missing_empty_and_whitespace_paths_use_default(self) -> None:
        expected = []
        for value in (None, "", " \t\n "):
            with self.subTest(value=value):
                if value is None:
                    os.environ.pop("ERROR_LOG_PATH", None)
                else:
                    os.environ["ERROR_LOG_PATH"] = value
                message = "event-" + str(len(expected))
                self.logger.log_error("default", message)
                expected.append(message)
                self.assertEqual(
                    [row["message"] for row in self.rows("data/logs/errors.jsonl")], expected,
                )

    def test_relative_path_preserves_spaces_and_unicode(self) -> None:
        relative = Path("журналы приложения") / "ошибки.jsonl"
        os.environ["ERROR_LOG_PATH"] = "  " + str(relative) + "  "
        self.logger.log_error("источник", "текст ошибки")
        self.assertEqual(self.rows(relative)[0]["message"], "текст ошибки")
        self.assertFalse((self.root / "data/logs/errors.jsonl").exists())

    def test_absolute_path_appends_jsonl_and_preserves_fields(self) -> None:
        destination = self.root / "absolute logs" / "errors.jsonl"
        destination.parent.mkdir()
        original = '{"existing": true}\n'
        destination.write_text(original, encoding="utf-8")
        os.environ["ERROR_LOG_PATH"] = str(destination)
        self.logger.log_error("audio", "ошибка\nвторая строка", code=7, details={"ok": False})
        self.logger.log_error("actions", "next")
        content = destination.read_text(encoding="utf-8")
        self.assertTrue(content.startswith(original))
        self.assertEqual(len(content.splitlines()), 3)
        rows = self.rows(destination)
        self.assertEqual(rows[0], {"existing": True})
        self.assertEqual(rows[1]["source"], "audio")
        self.assertEqual(rows[1]["message"], "ошибка\nвторая строка")
        self.assertEqual(rows[1]["code"], 7)
        self.assertEqual(rows[1]["details"], {"ok": False})
        datetime.fromisoformat(rows[1]["ts"])
        self.assertEqual(rows[2]["message"], "next")

    def test_log_exception_preserves_type_traceback_and_extra(self) -> None:
        os.environ["ERROR_LOG_PATH"] = "exceptions.jsonl"
        try:
            raise ValueError("example failure")
        except ValueError as exc:
            self.logger.log_exception("actions", exc, operation="open")
        row = self.rows("exceptions.jsonl")[0]
        self.assertEqual(row["source"], "actions")
        self.assertEqual(row["message"], "example failure")
        self.assertEqual(row["error_type"], "ValueError")
        self.assertIn("ValueError: example failure", row["traceback"])
        self.assertEqual(row["operation"], "open")

    def test_io_failure_does_not_escape_or_redirect_to_default(self) -> None:
        blocker = self.root / "blocked"
        blocker.write_bytes(b"keep")
        os.environ["ERROR_LOG_PATH"] = "blocked/errors.jsonl"
        self.logger.log_error("audio", "unavailable destination")
        self.assertEqual(blocker.read_bytes(), b"keep")
        self.assertFalse((self.root / "data/logs/errors.jsonl").exists())

    def test_serialization_failure_does_not_stop_later_logging(self) -> None:
        os.environ["ERROR_LOG_PATH"] = "serialization.jsonl"
        self.logger.log_error("test", "before")
        self.logger.log_error("test", "cannot serialize", detail=object())
        self.logger.log_error("test", "after")
        self.assertEqual(
            [row["message"] for row in self.rows("serialization.jsonl")], ["before", "after"],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
