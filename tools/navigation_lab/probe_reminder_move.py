"""Rehearse one move in disposable checkouts. Output contains summaries, never local inputs."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
BASE = "ce6500fb97cba391f0081ed822828638b54e5c2a"
M01 = "a21f9be67a7f4a0388d37ef00912ca2065b9a77f"
OLD = Path("modules/reminder_datetime_parser.py")
NEW = Path("modules/reminders/datetime_parser.py")
CONSUMER = Path("modules/reminder_command_parser.py")
EVALS = ("reminder_datetime", "reminder_command_parser", "reminder_repository",
         "reminder_service", "reminder_actions", "reminder_runtime", "package_boundaries")
FACADE = """from modules.reminders.datetime_parser import (
    MAX_REMINDER_HORIZON_SEC, MIN_REMINDER_LEAD_SEC, ReminderDateTimeParseResult,
    normalize_reminder_text, parse_reminder_datetime,
)
"""


def git(cwd, *args):
    return subprocess.check_output(["git", *args], cwd=cwd).decode().strip()


def python(repo, *args, check=True):
    env = {**os.environ, "PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1",
           "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    return subprocess.run([sys.executable, "-B", *args], cwd=repo, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          encoding="utf-8", check=check)


def rehearse(repo):
    old, new = repo / OLD, repo / NEW
    new.parent.mkdir()
    (new.parent / "__init__.py").write_bytes(b"")
    new.write_bytes(old.read_bytes())
    old.write_text(FACADE, encoding="utf-8")
    consumer = repo / CONSUMER
    data = consumer.read_bytes()
    before = b"from modules.reminder_datetime_parser import"
    assert data.count(before) == 1
    consumer.write_bytes(data.replace(before, b"from modules.reminders.datetime_parser import"))
    assert git(repo, "hash-object", NEW.as_posix()) == git(repo, "rev-parse", f"HEAD:{OLD.as_posix()}")


def evaluate(repo, use_pipeline):
    checks = {}
    for name in EVALS:
        result = python(repo, f"tools/eval_{name}.py", check=False)
        summary = result.stdout.rpartition("=== SUMMARY ===")[2].strip()
        checks[name] = {"rc": result.returncode, "summary": json.loads(summary)}
    # All returned fields for every frozen date case, including epoch and normalized input.
    code = """
import hashlib, json
from tools.eval_reminder_datetime import CASES, NOW, parse_reminder_datetime
rows = [parse_reminder_datetime(c['text'], now=NOW).to_dict() for c in CASES]
print(hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest())
"""
    data = {"targeted": checks, "date_payload_sha256": python(repo, "-c", code).stdout.strip()}
    if use_pipeline:
        shutil.copyfile(ROOT / "models/nlu_intent.joblib", repo / "models/nlu_intent.joblib")
        result = python(repo, "tools/pipeline.py", "check", "--no-log",
                        "--summary-json", "check-summary.json", check=False)
        summary = json.loads((repo / "check-summary.json").read_text("utf-8"))
        data["pipeline"] = {"rc": result.returncode, "counts": summary["counts"],
                            "failed": [s["name"] for s in summary["steps"] if s["status"] == "FAIL"]}
        if "=== INTENT COVERAGE ===" in result.stdout:
            coverage, _ = json.JSONDecoder().raw_decode(result.stdout.split("=== INTENT COVERAGE ===")[1].lstrip())
            data["pipeline"]["missing_intents"] = coverage["missing_eval_intents"]
    return data


def serialization(writer, reader, scratch):
    # Deserialize exclusively the value produced just above in a private temporary directory.
    sample = str(scratch / "value.pickle")
    python(writer, "-c", """
from datetime import datetime
from pathlib import Path
import pickle, sys
from modules.reminder_datetime_parser import parse_reminder_datetime
value = parse_reminder_datetime("напомни через час проверить", now=datetime(2026, 7, 13, 15))
Path(sys.argv[1]).write_bytes(pickle.dumps(value))
""", sample)
    return python(reader, "-c", """
from pathlib import Path
import pickle, sys
from modules.reminder_datetime_parser import ReminderDateTimeParseResult
try:
    value = pickle.loads(Path(sys.argv[1]).read_bytes())
except ModuleNotFoundError as exc:
    print(type(exc).__name__, exc.name)
else:
    assert type(value) is ReminderDateTimeParseResult and value.ok
    print("ok")
""", sample).stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pipeline", action="store_true",
                        help="Also run the real check flow with the installed project NLU model in both copies.")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="sk-move-") as location:
        scratch = Path(location)
        baseline, trial, shipped = scratch / "baseline", scratch / "trial", scratch / "shipped"
        git(ROOT, "clone", "-q", "--local", "--no-hardlinks", "--no-checkout", str(ROOT), str(baseline))
        git(baseline, "checkout", "-q", "--detach", BASE)
        git(baseline, "worktree", "add", "-q", "--detach", str(trial), BASE)
        git(baseline, "worktree", "add", "-q", "--detach", str(shipped), M01)
        rehearse(trial)
        if args.pipeline:
            for repo in (baseline, trial, shipped):
                (repo / "models").mkdir(exist_ok=True)
        output = {"baseline_revision": BASE, "integration_revision": M01,
                  "parser_blob": git(baseline, "rev-parse", f"HEAD:{OLD.as_posix()}")}
        for label, repo in (("baseline", baseline), ("trial", trial), ("shipped", shipped)):
            output[label] = evaluate(repo, args.pipeline)
        assert git(trial, "diff", "--name-only", "--", "tools", "main.py", "modules/developer") == ""
        identity = python(trial, "-c", """
from modules import reminder_datetime_parser as facade
from modules.reminders import datetime_parser as impl
assert all(getattr(facade, n) is getattr(impl, n) for n in vars(facade) if not n.startswith("_"))
print(impl.ReminderDateTimeParseResult.__module__)
""").stdout.strip()
        output.update({"trial_class_module": identity, "legacy_to_trial": serialization(baseline, trial, scratch),
                       "trial_to_rollback": serialization(trial, baseline, scratch)})
        git(shipped, "revert", "--no-commit", M01)
        output["m01_revert_restores_parent_tree"] = git(shipped, "write-tree") == git(shipped, "rev-parse", "HEAD^1^{tree}")
        assert output["m01_revert_restores_parent_tree"]
        print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
