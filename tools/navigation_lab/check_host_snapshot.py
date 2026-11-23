"""Run the registered host check in a clean, disposable checkout with the installed NLU asset."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
CONTROLS = Path("docs/maintenance/arch_migration_02/control.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("revision", nargs="?", default="HEAD")
    parser.add_argument("--fit", action="store_true",
                        help="Build the NLU classifier from this checkout in the temporary directory.")
    parser.add_argument("--diagnose-tail", action="store_true",
                        help="Run late NOT_RUN steps separately after a failed check; retain the official failure.")
    args = parser.parse_args()
    sha = subprocess.check_output(["git", "rev-parse", "--verify", "--end-of-options",
                                   args.revision + "^{commit}"], cwd=ROOT, text=True).strip()
    with tempfile.TemporaryDirectory(prefix="sk-check-") as temp:
        repo = Path(temp) / "repo"
        subprocess.run(["git", "clone", "-q", "--local", "--no-hardlinks", "--no-checkout",
                        str(ROOT), str(repo)], check=True)
        subprocess.run(["git", "checkout", "-q", "--detach", sha], cwd=repo, check=True)
        (repo / "models").mkdir(exist_ok=True)
        model = repo / "models/nlu_intent.joblib"
        env = {**os.environ, "PYTHONPATH": str(repo), "PYTHONUTF8": "1",
               "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
        if args.fit:
            subprocess.run([sys.executable, "-B", "train/train_nlu.py"], cwd=repo, env=env,
                           stdout=subprocess.DEVNULL, check=True)
        else:
            shutil.copyfile(ROOT / "models/nlu_intent.joblib", model)
        control_run = """
import json, sys
from pathlib import Path
from modules.nlu import predict, predict_candidates
rows = []
for text, expected in json.loads(Path(sys.argv[1]).read_text('utf8'))['cases']:
    rows.append({'text': text, 'expected': expected, 'actual': predict(text)['intent']})
fallback = next(c for c in predict_candidates('стоп') if c['source'] == 'model')
print(json.dumps({'rows': rows, 'stop_raw': fallback['confidence']}))
"""
        controls = subprocess.check_output([sys.executable, "-B", "-c", control_run, str(ROOT / CONTROLS)],
                                           cwd=repo, env=env, encoding="utf-8")
        summary = Path(temp) / "summary.json"
        result = subprocess.run([sys.executable, "-B", "tools/pipeline.py", "check", "--no-log",
                                 "--summary-json", str(summary)], cwd=repo, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8")
        report = json.loads(summary.read_text("utf-8"))
        data = {"snapshot": sha, "returncode": result.returncode, "counts": report["counts"],
                "failed": [s["name"] for s in report["steps"] if s["status"] == "FAIL"],
                "model_source": "disposable_fit" if args.fit else "installed",
                "model_sha256": hashlib.sha256(model.read_bytes()).hexdigest(),
                "controls": json.loads(controls)}
        if "=== INTENT COVERAGE ===" in result.stdout:
            tail = result.stdout.split("=== INTENT COVERAGE ===", 1)[1]
            data["intent_coverage"], _ = json.JSONDecoder().raw_decode(tail.lstrip())
            data["nlu_cases"], _ = json.JSONDecoder().raw_decode(tail.split("=== SUMMARY ===", 1)[1].lstrip())
        if "=== NLU RISK GUARD REPORT ===" in result.stdout:
            tail = result.stdout.split("=== NLU RISK GUARD REPORT ===", 1)[1]
            data["risk_guard"], _ = json.JSONDecoder().raw_decode(tail.lstrip())
        if args.diagnose_tail and data["failed"]:
            trace = """
import contextlib, io, json, sys
from tools.pipeline import available_flows, run_step_result, PROJECT_ROOT
selected = available_flows()['check']
rows = []
for idx in json.loads(sys.argv[1]):
    with contextlib.redirect_stdout(io.StringIO()):
        result = run_step_result(selected[idx-1], cwd=PROJECT_ROOT)
    rows.append(dict(index=idx, name=selected[idx-1].name, status=result.status))
print(json.dumps(rows))
"""
            indices = [s["index"] for s in report["steps"] if s["status"] == "NOT_RUN"]
            rows = subprocess.check_output([sys.executable, "-B", "-c", trace, json.dumps(indices)],
                                           cwd=repo, env=env, encoding="utf-8")
            data["independent_tail"] = json.loads(rows)
        if data["failed"]:
            # Retain child diagnostics on the operator's console only.
            diagnostics = result.stdout.split("[STOP] Flow", 1)[0].split("[RUN] ")[-1]
            print(diagnostics[-5000:], file=sys.stderr)
        print(json.dumps(data, indent=2))
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
