"""M154: retain an experiment, its checks and its report before attempting push.

The supplied plan is the explicit scope. The user's checkout is only read.
This is an ordinary user-invoked experiment tool, not a DTR authority grant.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import subprocess
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from development_lessons import load_lessons, make_observation, prepare_context, select_lessons
from git_transport import Transport

SCHEMA = "SKYNETVS_EXPERIMENT_PLAN_V1"
REMOTE = "https://github.com/Daystat-debug/SkynetVS.git"
REPORT_BRANCH = "reports/m154"
FALLBACK_IDENTITY = {"user.name": "SkynetVS experiment", "user.email": "skynetvs-experiment@users.noreply.github.com"}


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".new")
    temporary.write_bytes(json_bytes(value))
    temporary.replace(path)


@contextmanager
def run_lock(run_dir: Path):
    """OS lock: released on process exit, including an unexpected crash."""
    with (run_dir / "run.lock").open("a+b") as stream:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise WorkflowError("RUN_ALREADY_ACTIVE", "This run is already active in another process.") from exc
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class WorkflowError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def child_environment() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "Never"
    return env


def git(repo: Path, *args: str, check: bool = True, identity: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    # /dev/null and NUL disable hooks without touching the source configuration.
    command = ["git", "--no-optional-locks", "-c", "core.autocrlf=false", "-c", "core.eol=lf",
               "-c", "core.longpaths=true", "-c", "core.fsmonitor=false", "-c", "commit.gpgsign=false",
               "-c", "core.hooksPath=" + os.devnull, "-C", str(repo)]
    for key, value in (identity or {}).items():
        command += ["-c", key + "=" + value]
    result = subprocess.run(command + list(args), env=child_environment(), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=60, shell=False)
    if check and result.returncode:
        raise WorkflowError("GIT_COMMAND_FAILED", result.stderr.decode("utf-8", "replace").strip())
    return result


def git_text(repo: Path, *args: str) -> str:
    return git(repo, *args).stdout.decode("utf-8", "strict").strip()


def source_snapshot(repo: Path) -> dict[str, Any]:
    git_directory = Path(git_text(repo, "rev-parse", "--absolute-git-dir"))
    status = git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all").stdout
    refs = git(repo, "for-each-ref", "--format=%(refname) %(objectname)").stdout
    result = {"head": git_text(repo, "rev-parse", "HEAD"), "status_sha256": sha256(status),
              "refs_sha256": sha256(refs), "dirty": bool(status),
              "tracked_diff_sha256": sha256(git(repo, "diff", "HEAD", "--binary", "--no-ext-diff", "--no-textconv").stdout)}
    for name in ("index", "config"):
        path = git_directory / name
        result[name + "_sha256"] = sha256(path.read_bytes()) if path.is_file() else None
    return result


def git_identity(source: Path) -> dict[str, str]:
    identity = dict(FALLBACK_IDENTITY)
    if source.is_dir():
        for key in identity:
            try:
                result = git(source, "config", "--get", key, check=False)
                value = result.stdout.decode("utf-8", "replace").strip()
                if result.returncode == 0 and value and "\n" not in value:
                    identity[key] = value
            except (OSError, subprocess.SubprocessError, WorkflowError):
                pass
    return identity


def relative_path(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise WorkflowError("INVALID_PLAN_PATH", "A payload path must be a relative POSIX path.")
    path = PurePosixPath(value)
    if path.is_absolute() or str(path) != value or any(p in ("..", ".git") or ":" in p for p in path.parts):
        raise WorkflowError("INVALID_PLAN_PATH", "A payload path escapes its declared repository scope.")
    return value


def validate_plan(plan: Any) -> None:
    if not isinstance(plan, dict) or plan.get("schema") != SCHEMA or plan.get("stage") != "M154":
        raise WorkflowError("INVALID_PLAN_SCHEMA", "Unsupported experiment plan.")
    if not re.fullmatch(r"[0-9a-f]{40}", str(plan.get("base_commit", ""))):
        raise WorkflowError("INVALID_BASE_COMMIT", "The plan must pin one full base commit.")
    payloads, checks = plan.get("payloads"), plan.get("checks")
    if not isinstance(payloads, list) or not 1 <= len(payloads) <= 100:
        raise WorkflowError("INVALID_PAYLOADS", "The plan must list 1 to 100 exact payload files.")
    paths = []
    for entry in payloads:
        if not isinstance(entry, dict):
            raise WorkflowError("INVALID_PAYLOAD", "Invalid payload entry.")
        paths.append(relative_path(entry.get("path")))
        for key in ("sha256", "before_sha256"):
            value = entry.get(key)
            if key == "before_sha256" and value is None:
                continue
            if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
                raise WorkflowError("INVALID_PAYLOAD_HASH", "Invalid exact payload hash.")
    if len(set(paths)) != len(paths):
        raise WorkflowError("DUPLICATE_PAYLOAD", "Payload paths must be unique.")
    if not isinstance(checks, list) or not 1 <= len(checks) <= 30:
        raise WorkflowError("INVALID_CHECKS", "The plan must list 1 to 30 checks.")
    ids = []
    for item in checks:
        if not isinstance(item, dict) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", str(item.get("id", ""))):
            raise WorkflowError("INVALID_CHECK_ID", "Invalid check ID.")
        ids.append(item["id"])
        args = item.get("argv")
        if not isinstance(args, list) or not args or any(not isinstance(a, str) or "\x00" in a for a in args):
            raise WorkflowError("INVALID_CHECK_ARGUMENTS", "Check arguments must be an explicit string array.")
        if args[0] != "{python}":
            raise WorkflowError("INVALID_CHECK_EXECUTABLE", "This runner starts checks with the selected Python only.")
        timeout = item.get("timeout_seconds")
        if type(timeout) is not int or not 1 <= timeout <= 1800:
            raise WorkflowError("INVALID_CHECK_TIMEOUT", "Check timeout must be between 1 and 1800 seconds.")
    if len(set(ids)) != len(ids):
        raise WorkflowError("DUPLICATE_CHECK", "Check IDs must be unique.")


def redact_log(data: bytes, roots: dict[str, Path], limit: int = 65536) -> str:
    if len(data) > limit:
        data = data[:limit // 4] + b"\n[... output truncated; complete log retained locally ...]\n" + data[-limit * 3 // 4:]
    text = data.decode("utf-8", "replace")
    for label, path in sorted(roots.items(), key=lambda item: len(str(item[1])), reverse=True):
        for form in (str(path), str(path).replace("\\", "/"), str(path).replace("/", "\\")):
            text = text.replace(form, "<" + label + ">")
    text = re.sub(r"(?i)(authorization\s*[:=]\s*)(?:bearer\s+)?[^\s]+", r"\1<REDACTED>", text)
    text = re.sub(r"(?i)(\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)\b[\"']?\s*[:=]\s*)[\"']?[^\s,;\"']+", r"\1<REDACTED>", text)
    text = re.sub(r"https?://[^\s/@:]+:[^\s/@]+@", "https://<REDACTED>@", text)
    text = re.sub(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,})\b", "<REDACTED>", text)
    return text


def terminate_process_tree(process: subprocess.Popen) -> bool:
    if process.poll() is not None:
        return True
    try:
        tree_confirmed = True
        if os.name == "nt":
            killed = subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15, shell=False)
            if killed.returncode:
                tree_confirmed = False
                if process.poll() is None:
                    process.kill()
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=10)
        return tree_confirmed
    except (OSError, subprocess.SubprocessError):
        return False


def execute_check(item: dict, code: Path, run_dir: Path, python: str, checkpoint=None) -> dict:
    values = {"{python}": python, "{code}": str(code), "{run}": str(run_dir)}
    argv = []
    for arg in item["argv"]:
        for token, replacement in values.items():
            arg = arg.replace(token, replacement)
        if re.search(r"\{(?:python|code|run)[^}]*\}", arg):
            raise WorkflowError("UNRESOLVED_ARGUMENT", "An argument placeholder was not expanded.")
        argv.append(arg)
    log_path = run_dir / "private_logs" / (item["id"] + ".log")
    log_path.parent.mkdir(exist_ok=True)
    env = child_environment()
    env.pop("PYTHONHOME", None)
    env.update({"PYTHONPATH": str(code), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
    temporary = run_dir / "t"
    temporary.mkdir(exist_ok=True)
    env.update({"TMP": str(temporary), "TEMP": str(temporary), "TMPDIR": str(temporary)})
    result = {"name": item["id"], "status": "RUNNING", "exit_code": None, "started_at": utc_now()}
    if checkpoint:
        checkpoint(result)
    print("CHECK_STARTED=" + item["id"], flush=True)
    start = time.monotonic()
    with log_path.open("wb") as output:
        options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        try:
            process = subprocess.Popen(argv, cwd=code, env=env, stdout=output, stderr=subprocess.STDOUT, shell=False, **options)
        except OSError as exc:
            detail = (type(exc).__name__ + ": " + str(exc) + "\n").encode("utf-8", "replace")
            output.write(detail)
            result.update(status="START_FAILED", exit_code=2, process_exit_code=None, error_type=type(exc).__name__,
                          elapsed_seconds=round(time.monotonic() - start, 3), finished_at=utc_now(), log_sha256=sha256(detail))
            print("CHECK_RESULT=" + item["id"] + ":START_FAILED:2", flush=True)
            return result
        try:
            while True:
                remaining = item["timeout_seconds"] - (time.monotonic() - start)
                if remaining <= 0:
                    result.update(status="TIMEOUT", exit_code=124, process_tree_terminated=terminate_process_tree(process))
                    break
                try:
                    status = process.wait(timeout=min(10, remaining))
                    result.update(status="PASS" if status == 0 else "FAIL", exit_code=status)
                    break
                except subprocess.TimeoutExpired:
                    print("CHECK_RUNNING=" + item["id"], flush=True)
        except KeyboardInterrupt:
            result.update(status="INTERRUPTED", exit_code=130, process_tree_terminated=terminate_process_tree(process))
        finally:
            if process.poll() is None:
                result["process_tree_terminated"] = terminate_process_tree(process)
            result["process_exit_code"] = process.poll()
    result["elapsed_seconds"] = round(time.monotonic() - start, 3)
    result["finished_at"] = utc_now()
    result["log_sha256"] = sha256(log_path.read_bytes())
    print("CHECK_RESULT=" + item["id"] + ":" + result["status"] + ":" + str(result["exit_code"]), flush=True)
    return result


def _write_public(run_dir: Path, files: dict[str, bytes]) -> None:
    public = run_dir / "public"
    public.mkdir(exist_ok=True)
    for path, content in files.items():
        destination = public / relative_path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and destination.read_bytes() != content:
            raise WorkflowError("IMMUTABLE_PUBLIC_FILE_CONFLICT", "A completed run's public files cannot be changed.")
        destination.write_bytes(content)


def recover_interrupted(run_dir: Path, state: dict) -> None:
    """Archive an abandoned attempt without executing its checks again.

    Called only while holding the OS run lock. It does not infer the exit code
    of a child that might have survived an abrupt parent-process termination.
    """
    plan = state.get("plan", {})
    if not plan:
        try:
            loaded = json.loads((run_dir / "input_plan.json").read_bytes())
            if isinstance(loaded, dict):
                plan = loaded
        except (OSError, ValueError):
            pass
    checks = []
    for entry in state.get("checks", []):
        item = dict(entry)
        if item.get("status") == "RUNNING":
            item.update(status="INTERRUPTED_UNKNOWN_EXIT", exit_code=None)
        checks.append(item)
    candidate = state.get("candidate_commit")
    code = run_dir / "c"
    if not candidate and (code / ".git").is_dir():
        try:
            head = git_text(code, "rev-parse", "HEAD")
            parent = git_text(code, "rev-parse", "HEAD^")
            branch = git_text(code, "symbolic-ref", "--short", "HEAD")
            if parent == plan.get("base_commit") and branch == state["candidate_branch"]:
                candidate = head
        except (OSError, subprocess.SubprocessError, WorkflowError):
            pass
    patch = b""
    if candidate and re.fullmatch(r"[0-9a-f]{40}", str(plan.get("base_commit", ""))):
        try:
            patch = git(code, "diff", "--binary", "--no-ext-diff", "--no-textconv", plan["base_commit"], candidate).stdout
        except (OSError, subprocess.SubprocessError, WorkflowError):
            pass
    summary = {"schema": "SKYNETVS_M154_AUTOMATIC_EXPERIMENT_V1", "run_id": state["run_id"],
               "status": "INTERRUPTED", "exit_code": 130, "purpose": plan.get("purpose", "UNKNOWN"),
               "base_commit": plan.get("base_commit"), "candidate_commit": candidate,
               "candidate_branch": state.get("candidate_branch") if candidate else None,
               "patch_sha256": sha256(patch), "checks": checks, "recovered_without_retesting": True,
               "child_completion_after_parent_interruption": "UNKNOWN",
               "user_project_written_by_runner": False, "user_project_applied": False,
               "pipeline_gate_closed": False, "runner_requested_model_training": False,
               "remaining_checks": plan.get("remaining_checks", []), "started_at": state["started_at"], "finished_at": utc_now()}
    files = {"summary.json": json_bytes(summary), "plan.json": json_bytes(plan), "change.patch": patch,
             "Development_Context.md": state.get("development_context", "").encode("utf-8"),
             "observation.json": json_bytes(make_observation(summary)),
             "diagnostics.json": json_bytes({"schema": "SKYNETVS_M154_EXPERIMENT_DIAGNOSTICS_V1", "errors": [{
                 "stage": state.get("phase"), "code": "RECOVERED_INTERRUPTED_RUN", "detail": "The previous process ended without a final checkpoint. Child exit codes are not inferred; checks were not rerun."}]})}
    roots = {"SOURCE": Path(state["source"]), "RUN": run_dir, "HOME": Path.home()}
    for entry in checks:
        name = entry.get("name", "")
        if re.fullmatch(r"[a-z][a-z0-9_]{0,63}", name):
            log = run_dir / "private_logs" / (name + ".log")
            if log.is_file():
                files["logs/" + name + ".txt"] = redact_log(log.read_bytes(), roots).encode("utf-8")
    files["receipt.json"] = json_bytes({"schema": "SKYNETVS_PUBLIC_EXPERIMENT_RECEIPT_V1", "project": "SkynetVS", "stage": "M154",
        "run_id": state["run_id"], "base_commit": plan.get("base_commit"), "candidate_commit": candidate,
        "files": {path: {"sha256": sha256(data), "size_bytes": len(data)} for path, data in files.items()},
        "review_scope": "Recovered interrupted run. No rerun, guessed child exit, or DTR promotion."})
    public = run_dir / "public"
    if public.exists():
        public.rename(run_dir / ("incomplete_public_" + uuid.uuid4().hex[:8]))
    _write_public(run_dir, files)
    state.update(phase="FINISHED", candidate_commit=candidate, exit_code=130, finished_at=summary["finished_at"])
    atomic_json(run_dir / "state.json", state)


def publish_saved(run_dir: Path) -> dict:
    run_dir = run_dir.resolve()
    state = json.loads((run_dir / "state.json").read_bytes())
    if state.get("schema") != "SKYNETVS_M154_LOCAL_RUN_V1":
        raise WorkflowError("UNOWNED_RUN_DIRECTORY", "This directory does not contain an owned experiment state.")
    source = Path(state["source"]).resolve()
    if run_dir.is_relative_to(source) or source.is_relative_to(run_dir):
        raise WorkflowError("RUN_SOURCE_OVERLAP", "The experiment directory must be outside the source repository.")
    with run_lock(run_dir):
        state = json.loads((run_dir / "state.json").read_bytes())
        if state.get("phase") != "FINISHED":
            recover_interrupted(run_dir, state)
        return _publish_saved_unlocked(run_dir)


def _publish_saved_unlocked(run_dir: Path) -> dict:
    state = json.loads((run_dir / "state.json").read_bytes())
    if state.get("phase") != "FINISHED":
        raise WorkflowError("INCOMPLETE_RUN", "An unfinished run must be recovered before publication.")
    prefix = "reports/M154/" + state["run_id"] + "/"
    public = run_dir / "public"
    receipt_path = public / "receipt.json"
    if receipt_path.is_symlink():
        raise WorkflowError("PUBLIC_REPORT_SYMLINK", "The report receipt must be a plain file.")
    receipt_bytes = receipt_path.read_bytes()
    receipt = json.loads(receipt_bytes)
    if receipt.get("schema") != "SKYNETVS_PUBLIC_EXPERIMENT_RECEIPT_V1" or receipt.get("run_id") != state["run_id"]:
        raise WorkflowError("PUBLIC_RECEIPT_MISMATCH", "The report receipt is not bound to this run.")
    files = {prefix + "receipt.json": receipt_bytes}
    for name, entry in receipt["files"].items():
        path = public / relative_path(name)
        if path.is_symlink() or not path.resolve().is_relative_to(public.resolve()):
            raise WorkflowError("PUBLIC_REPORT_SYMLINK", "A public report path leaves its explicit directory.")
        data = path.read_bytes()
        if len(data) != entry["size_bytes"] or sha256(data) != entry["sha256"]:
            raise WorkflowError("PUBLIC_REPORT_HASH_MISMATCH", "Public report bytes differ from their recorded receipt.")
        files[prefix + name] = data
    identity = git_identity(Path(state["source"]))
    transport = Transport(run_dir / "report_git", state["remote_url"], report_branch=REPORT_BRANCH, identity=identity)
    transport.prepare_report(files, state["run_id"])
    candidate = state.get("candidate_commit")
    result = transport.publish(candidate_repo=(run_dir / "c") if candidate else None,
                               candidate_commit=candidate, candidate_branch=state.get("candidate_branch") if candidate else None)
    atomic_json(run_dir / "publication.json", result)
    return result


def run_experiment(source: Path, bundle: Path, run_dir: Path, *, python: str = sys.executable,
                   remote_url: str = REMOTE, run_id: str | None = None) -> dict:
    source, bundle, run_dir = source.resolve(), bundle.resolve(), run_dir.resolve()
    if run_dir.is_relative_to(source) or source.is_relative_to(run_dir):
        raise WorkflowError("RUN_SOURCE_OVERLAP", "The experiment directory must be outside the source repository.")
    if run_dir.exists() and not (run_dir / "state.json").exists():
        if any(path.name != "run.lock" for path in run_dir.iterdir()):
            raise WorkflowError("UNOWNED_RUN_DIRECTORY", "The experiment directory is not empty or owned by this runner.")
    run_dir.mkdir(parents=True, exist_ok=True)
    with run_lock(run_dir):
        return _run_experiment_locked(source, bundle, run_dir, python=python, remote_url=remote_url, run_id=run_id)


def _run_experiment_locked(source: Path, bundle: Path, run_dir: Path, *, python: str,
                           remote_url: str, run_id: str | None) -> dict:
    if (run_dir / "state.json").exists():
        state = json.loads((run_dir / "state.json").read_bytes())
        if (state.get("schema") != "SKYNETVS_M154_LOCAL_RUN_V1" or Path(state.get("source", "")).resolve() != source
                or state.get("remote_url") != remote_url):
            raise WorkflowError("RUN_BINDING_MISMATCH", "This run belongs to a different source or remote.")
        if state.get("plan_input_sha256") is not None:
            if sha256((bundle / "plan.json").read_bytes()) != state["plan_input_sha256"]:
                raise WorkflowError("RUN_PLAN_MISMATCH", "This run belongs to a different prepared plan.")
        if state.get("phase") == "FINISHED":
            return {"summary": json.loads((run_dir / "public" / "summary.json").read_bytes()),
                    "publication": _publish_saved_unlocked(run_dir), "retried_without_tests": True}
        recover_interrupted(run_dir, state)
        return {"summary": json.loads((run_dir / "public" / "summary.json").read_bytes()),
                "publication": _publish_saved_unlocked(run_dir), "retried_without_tests": True}
    identifier = run_id or uuid.uuid4().hex
    if not re.fullmatch(r"[0-9a-f]{32}", identifier):
        raise WorkflowError("INVALID_RUN_ID", "Expected a 32-character hexadecimal run ID.")
    state = {"schema": "SKYNETVS_M154_LOCAL_RUN_V1", "run_id": identifier, "phase": "PREPARING",
             "source": str(source), "bundle": str(bundle), "remote_url": remote_url, "started_at": utc_now(),
             "candidate_commit": None, "candidate_branch": "experiments/m154/" + identifier}
    atomic_json(run_dir / "state.json", state)
    plan, before, after, patch = {}, None, None, b""
    selected, context, errors = [], "", []
    checks: list[dict] = []
    task_exit, status, candidate, stage = 2, "SETUP_FAILED", None, "READ_PLAN"
    code = run_dir / "c"
    roots = {"SOURCE": source, "RUN": run_dir, "HOME": Path.home()}
    try:
        plan_bytes = (bundle / "plan.json").read_bytes()
        (run_dir / "input_plan.json").write_bytes(plan_bytes)
        state["plan_input_sha256"] = sha256(plan_bytes)
        atomic_json(run_dir / "state.json", state)
        loaded_plan = json.loads(plan_bytes)
        validate_plan(loaded_plan)
        plan = loaded_plan
        checks = [{"name": item["id"], "status": "NOT_RUN", "exit_code": None} for item in plan["checks"]]
        stage = "READ_SOURCE"
        before = source_snapshot(source)
        state["source_snapshot_before"] = before
        if before["head"] != plan["base_commit"]:
            raise WorkflowError("BASE_COMMIT_MISMATCH", "Source HEAD differs from the pinned experiment base.")
        stage = "CREATE_INDEPENDENT_COPY"
        git(source, "clone", "--quiet", "--no-hardlinks", "--no-checkout", str(source), str(code))
        git(code, "checkout", "--quiet", "-b", state["candidate_branch"], plan["base_commit"])
        stage = "PREPARE_CANDIDATE"
        total = 0
        paths = []
        for item in plan["payloads"]:
            path = item["path"]
            data = (bundle / "payload" / path).read_bytes()
            total += len(data)
            if total > 8 * 1024 * 1024 or sha256(data) != item["sha256"]:
                raise WorkflowError("PAYLOAD_HASH_MISMATCH", "A payload file does not match the prepared plan.")
            target = code / path
            if any(p.is_symlink() for p in [target, *target.parents] if p != code.parent):
                raise WorkflowError("SYMLINK_PAYLOAD_PATH", "A payload target must be a plain file in the experiment.")
            original = sha256(target.read_bytes()) if target.is_file() else None
            if original != item.get("before_sha256"):
                raise WorkflowError("TARGET_BASE_HASH_MISMATCH", "The original target bytes differ from the plan.")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            paths.append(path)
        git(code, "add", "--", *paths)
        patch = git(code, "diff", "--cached", "--binary", "--no-ext-diff", "--no-textconv", plan["base_commit"], "--", *paths).stdout
        identity = git_identity(source)
        git(code, "commit", "--quiet", "--only", "-m", "M154: experiment " + identifier + " (checks recorded separately)", "--", *paths, identity=identity)
        candidate = git_text(code, "rev-parse", "HEAD")
        state.update(candidate_commit=candidate, phase="CHECKING")
        state["checks"] = checks
        state["plan"] = plan
        atomic_json(run_dir / "state.json", state)
        for item in plan["payloads"]:
            blob = git(code, "show", candidate + ":" + item["path"]).stdout
            if sha256(blob) != item["sha256"]:
                raise WorkflowError("COMMITTED_PAYLOAD_MISMATCH", "Committed candidate bytes differ from the plan.")
        stage = "PREPARE_LESSONS"
        lessons_path = bundle / "lessons.json"
        if lessons_path.is_file():
            selected = select_lessons(load_lessons(lessons_path), task=str(plan.get("goal", "")),
                                      paths=paths, tags=plan.get("lesson_tags", []))
            prepared_context = prepare_context(selected)
            context = prepared_context["text"]
            state["context_lesson_ids"] = prepared_context["lesson_ids"]
        state["development_context"] = context
        atomic_json(run_dir / "state.json", state)
        stage = "CHECKS"
        status, task_exit = "PASS", 0
        for index, item in enumerate(plan["checks"]):
            def checkpoint(value):
                checks[index] = value
                state["checks"] = checks
                atomic_json(run_dir / "state.json", state)
            checks[index] = execute_check(item, code, run_dir, python, checkpoint=checkpoint)
            checkpoint(checks[index])
            if checks[index]["status"] != "PASS":
                status, task_exit = checks[index]["status"], checks[index]["exit_code"]
                break
        stage = "VERIFY_TESTED_SNAPSHOT"
        if git_text(code, "rev-parse", "HEAD") != candidate:
            raise WorkflowError("TEST_CHANGED_HEAD", "A check changed the candidate HEAD.")
        for item in plan["payloads"]:
            if sha256((code / item["path"]).read_bytes()) != item["sha256"]:
                raise WorkflowError("TEST_CHANGED_CANDIDATE_FILE", "A check changed a committed candidate file.")
    except KeyboardInterrupt:
        status, task_exit = "INTERRUPTED", 130
        errors.append({"stage": stage, "code": "USER_INTERRUPTED", "detail": "Experiment interrupted."})
    except Exception as exc:
        status, task_exit = ("SETUP_FAILED", 2) if stage != "VERIFY_TESTED_SNAPSHOT" else ("SNAPSHOT_CHANGED", 2)
        errors.append({"stage": stage, "code": getattr(exc, "code", type(exc).__name__),
                       "detail": redact_log(str(exc).encode("utf-8", "replace"), roots, 4096)})
        (run_dir / "private_error.txt").write_text(traceback.format_exc(), encoding="utf-8")
    finally:
        try:
            after = source_snapshot(source)
        except Exception:
            after = None
        source_equal = before == after if before is not None and after is not None else None
        if source_equal is False:
            errors.append({"stage": "SOURCE_AFTER", "code": "SOURCE_CHANGED_DURING_RUN", "detail": "The source snapshot changed during the experiment."})
            if task_exit == 0:
                status, task_exit = "SOURCE_CHANGED", 2
        post_status = None
        if candidate:
            try:
                post_status = git(code, "status", "--porcelain=v1", "--untracked-files=all").stdout
            except Exception:
                pass
        summary = {"schema": "SKYNETVS_M154_AUTOMATIC_EXPERIMENT_V1", "run_id": identifier,
                   "status": status, "exit_code": task_exit, "purpose": plan.get("purpose", "UNKNOWN"),
                   "base_commit": plan.get("base_commit"), "candidate_commit": candidate,
                   "candidate_branch": state["candidate_branch"] if candidate else None,
                   "code_commit_before_tests": candidate is not None, "patch_sha256": sha256(patch),
                   "plan_sha256": sha256(json_bytes(plan)), "checks": checks,
                   "source_git_state_unchanged": source_equal,
                   "source_snapshot_scope": "HEAD, refs, index, config, porcelain and tracked diff; ignored files are not observed",
                   "user_project_written_by_runner": False,
                   "source_dirty_files_copied": False, "source_snapshot_before": before, "source_snapshot_after": after,
                   "post_check_worktree_dirty": bool(post_status) if post_status is not None else None,
                   "post_check_status_sha256": sha256(post_status) if post_status is not None else None,
                   "generated_files_auto_committed": False, "user_project_applied": False,
                   "pipeline_gate_closed": False, "remaining_checks": plan.get("remaining_checks", []),
                   "runner_requested_model_training": False, "model_calls_by_runner": 0,
                   "model_activity_in_checks": "NOT_INSTRUMENTED",
                   "agent_context_prepared": bool(context), "agent_context_consumed_by_gui": False,
                   "selected_lesson_ids": state.get("context_lesson_ids", []),
                   "started_at": state["started_at"], "finished_at": utc_now()}
        files = {"summary.json": json_bytes(summary), "diagnostics.json": json_bytes({"schema": "SKYNETVS_M154_EXPERIMENT_DIAGNOSTICS_V1", "errors": errors}),
                 "plan.json": json_bytes(plan), "change.patch": patch, "Development_Context.md": context.encode("utf-8"),
                 "observation.json": json_bytes(make_observation(summary))}
        for item in checks:
            log = run_dir / "private_logs" / (item["name"] + ".log")
            if log.is_file():
                files["logs/" + item["name"] + ".txt"] = redact_log(log.read_bytes(), roots).encode("utf-8")
        receipt = {"schema": "SKYNETVS_PUBLIC_EXPERIMENT_RECEIPT_V1", "project": "SkynetVS", "stage": "M154", "run_id": identifier,
                   "base_commit": plan.get("base_commit"), "candidate_commit": candidate,
                   "files": {path: {"sha256": sha256(data), "size_bytes": len(data)} for path, data in files.items()},
                   "review_scope": "User-invoked experiment and automated check records; no DTR promotion or model-weight training."}
        files["receipt.json"] = json_bytes(receipt)
        _write_public(run_dir, files)
        state.update(phase="FINISHED", candidate_commit=candidate, finished_at=summary["finished_at"], exit_code=task_exit)
        atomic_json(run_dir / "state.json", state)
    try:
        publication = _publish_saved_unlocked(run_dir)
    except Exception as exc:
        publication = {"queue_state": "LOCAL_FILES_PENDING_COMMIT", "candidate": {"status": "PENDING"},
                       "report": {"status": "PENDING"}, "error_code": getattr(exc, "code", type(exc).__name__)}
        atomic_json(run_dir / "publication.json", publication)
    return {"summary": summary, "publication": publication, "retried_without_tests": False}


def _published(publication: dict) -> bool:
    accepted = {"PUBLISHED", "NOT_CREATED"}
    return publication.get("report", {}).get("status") in accepted and publication.get("candidate", {}).get("status") in accepted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(r"C:\Project\SkynetVS"))
    parser.add_argument("--bundle", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--retry", action="store_true", help="Publish a completed run without rerunning checks.")
    args = parser.parse_args(argv)
    try:
        if args.retry:
            publication = publish_saved(args.run_dir)
            summary = json.loads((args.run_dir / "public" / "summary.json").read_bytes())
            result = {"summary": summary, "publication": publication, "retried_without_tests": True}
        else:
            result = run_experiment(args.source, args.bundle, args.run_dir)
        summary, publication = result["summary"], result["publication"]
        print("RUN_ID=" + summary["run_id"])
        print("TEST_STATUS=" + summary["status"])
        print("TEST_EXIT_CODE=" + str(summary["exit_code"]))
        print("CODE_COMMIT=" + str(summary.get("candidate_commit")))
        print("CODE_PUBLISH_STATUS=" + str(publication.get("candidate", {}).get("status")))
        print("REPORT_PUBLISH_STATUS=" + str(publication.get("report", {}).get("status")))
        print("REPORT_URL=https://github.com/Daystat-debug/SkynetVS/tree/reports/m154/reports/M154/" + summary["run_id"])
        print("RETRIED_WITHOUT_TESTS=" + str(result["retried_without_tests"]).upper())
        print("PRESERVED_RUN_DIRECTORY=" + str(args.run_dir))
        if _published(publication):
            print("PUBLICATION=COMPLETE")
        else:
            print("PUBLICATION=PENDING; repeat the same launcher to retry without rerunning checks")
        return summary["exit_code"] if summary["exit_code"] != 0 else (0 if _published(publication) else 75)
    except Exception as exc:
        print("M154_AUTORUN_STOP=" + getattr(exc, "code", type(exc).__name__))
        print("PRESERVED_RUN_DIRECTORY=" + str(args.run_dir))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
