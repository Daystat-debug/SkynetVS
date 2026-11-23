"""Test an internal grammar extraction against the accepted public parser, only in scratch."""
import ast
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import probe_reminder_move as probe


BASE = "793cd41bf6f691ca13ca1b5770606180a16e6279"


def extract_tokens(repo):
    path = repo / probe.OLD
    source = path.read_text("utf-8")
    lines = source.splitlines(keepends=True)
    private_rules = {"_Token", "_NUMBER_WORDS", "_DAY_PARTS", "_tokenize", "_is_number",
                     "_parse_number", "_consume_clock_number", "_convert_hour", "_parse_clock"}
    blocks, removed = [], set()
    for node in ast.parse(source).body:
        name = node.targets[0].id if isinstance(node, ast.Assign) else getattr(node, "name", None)
        if name not in private_rules:
            continue
        decorators = getattr(node, "decorator_list", ())
        start = min([node.lineno, *(d.lineno for d in decorators)]) - 1
        blocks.append("".join(lines[start:node.end_lineno]).rstrip())
        removed.update(range(start, node.end_lineno))
    assert len(blocks) == len(private_rules)
    package = repo / "modules/reminders"
    package.mkdir()
    (package / "__init__.py").write_bytes(b"")
    header = "from __future__ import annotations\n\nimport re\nfrom dataclasses import dataclass"
    (package / "_time_tokens.py").write_text("\n\n\n".join([header, *blocks]) + "\n", encoding="utf-8")
    public = "".join(line for n, line in enumerate(lines) if n not in removed)
    public = public.replace("from typing import Any\n", "from typing import Any\n\n"
                            "from modules.reminders._time_tokens import (\n"
                            "    _Token, _is_number, _parse_clock, _parse_number, _tokenize,\n)\n")
    path.write_text(public, encoding="utf-8")


def stored_reminder(writer, reader, temp):
    path = str(temp / "reminders.json")
    probe.python(writer, "-c", """
from datetime import datetime, timezone
from modules.reminder_command_parser import parse_reminder_command
from modules.reminder_repository import ReminderRepository
import sys
slots = parse_reminder_command('напомни через час проверить', now=datetime(2026, 1, 1, tzinfo=timezone.utc)).slots
ReminderRepository(sys.argv[1]).add(text=slots['reminder_text'], due_at_epoch=slots['due_at_epoch'],
                                     reminder_id='probe', created_at_epoch=1767225600)
""", path)
    raw = Path(path).read_bytes()
    probe.python(reader, "-c", """
from modules.reminder_repository import ReminderRepository
import sys
record, = ReminderRepository(sys.argv[1]).list_all()
assert (record.reminder_id, record.text, record.created_at_epoch, record.due_at_epoch) == (
    'probe', 'проверить', 1767225600, 1767229200)
""", path)
    assert Path(path).read_bytes() == raw
    Path(path).unlink()
    return raw


def main():
    with tempfile.TemporaryDirectory(prefix="sk-tokens-") as tmp:
        scratch = Path(tmp)
        old, new = scratch / "old", scratch / "new"
        probe.git(probe.ROOT, "clone", "-q", "--local", "--no-hardlinks", "--no-checkout", str(probe.ROOT), str(old))
        probe.git(old, "checkout", "-q", "--detach", BASE)
        probe.git(old, "worktree", "add", "-q", "--detach", str(new), BASE)
        extract_tokens(new)
        left, right = probe.evaluate(old, False), probe.evaluate(new, False)
        assert left == right and all(v["rc"] == 0 for v in right["targeted"].values())
        cross = [probe.serialization(a, b, scratch) for a, b in ((old, new), (new, old))]
        assert cross == ["ok", "ok"]
        assert stored_reminder(old, new, scratch) == stored_reminder(new, old, scratch)
        print(json.dumps({"base": BASE, "identical_evaluations": right, "pickle_forward_rollback": cross,
                          "json_forward_rollback_identical": True}, indent=2))


if __name__ == "__main__":
    main()
