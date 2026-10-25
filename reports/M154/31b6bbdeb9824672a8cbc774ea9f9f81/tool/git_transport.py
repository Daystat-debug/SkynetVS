"""M154: durable local report commits and ordinary, retryable Git publication.

This module never commits a user's working tree. Candidate commits are supplied
by the caller. Public report bytes are an explicit mapping; runtime directories
and raw logs are never discovered or swept into a commit.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Mapping
import uuid


SCHEMA = "SKYNETVS_M154_GIT_TRANSPORT_V1"
FALLBACK_IDENTITY = {
    "name": "SkynetVS experiment",
    "email": "skynetvs-experiment@users.noreply.github.com",
}
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
RUN_ID = re.compile(r"[0-9a-f]{32}\Z")


class TransportError(RuntimeError):
    """A public-safe code; underlying Git stderr remains in a private log."""

    def __init__(self, code: str, returncode: int | None = None):
        super().__init__(code)
        self.code = code
        self.returncode = returncode


def _atomic_json(path: Path, value: Any) -> None:
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    with temporary.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


class Transport:
    def __init__(
        self,
        state_dir: Path,
        remote_url: str,
        report_branch: str = "reports/m154",
        identity: Mapping[str, str] | None = None,
        git_executable: str = "git",
    ) -> None:
        self.state_dir = Path(state_dir).resolve()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.repo = self.state_dir / "report.git"
        self.state_file = self.state_dir / "state.json"
        self.private_log = self.state_dir / "transport.private.jsonl"
        self.hooks = self.state_dir / "empty-hooks"
        self.hooks.mkdir(exist_ok=True)
        self.remote_url = str(remote_url)
        self.report_branch = report_branch
        self.git_executable = git_executable
        if not self.remote_url or any(c in self.remote_url for c in "\r\n\0"):
            raise TransportError("INVALID_REMOTE")
        if report_branch != "reports/m154":
            raise TransportError("INVALID_REPORT_BRANCH")
        given = dict(identity or {})
        self.identity = {
            key: given.get(key) or given.get("user." + key) or default
            for key, default in FALLBACK_IDENTITY.items()
        }
        for value in self.identity.values():
            if not isinstance(value, str) or not value.strip() or any(c in value for c in "\r\n\0<>"):
                raise TransportError("INVALID_COMMIT_IDENTITY")
        marker = self.state_dir / "transport.owner"
        if not marker.exists():
            if self.repo.exists() or self.state_file.exists():
                raise TransportError("UNOWNED_TRANSPORT_DIRECTORY")
            marker.write_text(SCHEMA + "\n", encoding="ascii")
        elif marker.read_text(encoding="ascii") != SCHEMA + "\n":
            raise TransportError("TRANSPORT_OWNER_MISMATCH")
        if not self.repo.exists():
            self._git(self.state_dir, ["init", "--bare", "--quiet", str(self.repo)], code="REPORT_INIT_FAILED")
        if self._git(self.repo, ["rev-parse", "--is-bare-repository"]).strip() != b"true":
            raise TransportError("REPORT_REPOSITORY_NOT_BARE")
        self.state: dict[str, Any] | None = None
        if self.state_file.exists():
            self.state = json.loads(self.state_file.read_text(encoding="utf-8"))
            if (self.state.get("schema") != SCHEMA or self.state.get("remote_url") != self.remote_url
                    or self.state.get("report_branch") != self.report_branch):
                raise TransportError("TRANSPORT_STATE_MISMATCH")

    def _git(
        self,
        repository: Path,
        arguments: list[str],
        *,
        input_bytes: bytes | None = None,
        extra_env: Mapping[str, str] | None = None,
        code: str = "GIT_COMMAND_FAILED",
    ) -> bytes:
        environment = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
        environment.update({
            "GIT_TERMINAL_PROMPT": "0",
            "GCM_INTERACTIVE": "Never",
            "GIT_AUTHOR_NAME": self.identity["name"],
            "GIT_AUTHOR_EMAIL": self.identity["email"],
            "GIT_COMMITTER_NAME": self.identity["name"],
            "GIT_COMMITTER_EMAIL": self.identity["email"],
        })
        environment.update(extra_env or {})
        command = [
            self.git_executable, "--no-optional-locks", "-C", str(repository),
            "-c", "core.autocrlf=false", "-c", "core.eol=lf",
            "-c", "core.fsmonitor=false", "-c", "gc.auto=0",
            "-c", "core.hooksPath=" + str(self.hooks),
            "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false",
            "-c", "push.followTags=false", "-c", "push.recurseSubmodules=no",
            *arguments,
        ]
        try:
            result = subprocess.run(command, input=input_bytes, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, env=environment, shell=False,
                                    timeout=60, check=False)
        except subprocess.TimeoutExpired as exc:
            self._private_error(code + "_TIMEOUT", exc.stderr or b"")
            raise TransportError(code + "_TIMEOUT") from None
        except OSError as exc:
            self._private_error(code + "_START", type(exc).__name__.encode("ascii"))
            raise TransportError(code + "_START") from None
        if result.returncode:
            self._private_error(code, result.stderr, result.returncode)
            raise TransportError(code, result.returncode)
        return result.stdout

    def _private_error(self, code: str, stderr: bytes, returncode: int | None = None) -> None:
        with self.private_log.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"code": code, "returncode": returncode,
                                     "stderr": stderr.decode("utf-8", "replace")[-20000:]},
                                    ensure_ascii=False) + "\n")

    def _save(self) -> None:
        assert self.state is not None
        _atomic_json(self.state_file, self.state)

    @staticmethod
    def _checked_files(files: Mapping[str, bytes], run_id: str) -> dict[str, bytes]:
        if not RUN_ID.fullmatch(run_id):
            raise TransportError("INVALID_RUN_ID")
        if not files or len(files) > 100:
            raise TransportError("REPORT_SIZE_LIMIT")
        prefix = "reports/M154/" + run_id + "/"
        result = {}
        for path, data in files.items():
            if (not isinstance(path, str) or not path.startswith(prefix)
                    or not re.fullmatch(r"[A-Za-z0-9_./-]{1,400}", path)
                    or any(part in ("", ".", "..") for part in path.split("/"))
                    or not isinstance(data, bytes)):
                raise TransportError("INVALID_PUBLIC_REPORT_FILE")
            result[path] = data
        if sum(len(value) for value in result.values()) > 32 * 1024 * 1024:
            raise TransportError("REPORT_SIZE_LIMIT")
        return result

    def prepare_report(self, files: Mapping[str, bytes], run_id: str) -> dict[str, Any]:
        """Record exact public bytes locally, without any network command."""
        checked = self._checked_files(files, run_id)
        fingerprints = {path: {"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}
                        for path, data in sorted(checked.items())}
        if self.state is not None:
            old = {path: {"sha256": value["sha256"], "size_bytes": value["size_bytes"]}
                   for path, value in self.state["files"].items()}
            if self.state["run_id"] != run_id or old != fingerprints:
                raise TransportError("LOCAL_RUN_IMMUTABLE_CONFLICT")
            self._git(self.repo, ["cat-file", "-e", self.state["local_commit"] + "^{commit}"])
            return {"status": "LOCAL_RECORDED", "local_commit": self.state["local_commit"],
                    "local_ref": self.state["local_ref"], "run_id": run_id}
        entries = {}
        for path, data in checked.items():
            oid = self._git(self.repo, ["hash-object", "-w", "--stdin"], input_bytes=data).decode("ascii").strip()
            entries[path] = {**fingerprints[path], "blob": oid}
        local_ref = "refs/local/reports/" + run_id
        previous = self._git(self.repo, ["for-each-ref", "--format=%(objectname)", local_ref]).decode("ascii").strip()
        if previous:
            # Recover a crash after update-ref but before atomic state.json.
            rows = self._git(self.repo, ["ls-tree", "-r", "-z", previous]).split(b"\0")
            observed = {}
            for row in rows:
                if row:
                    metadata, path = row.split(b"\t", 1)
                    mode, kind, oid = metadata.decode("ascii").split(" ")
                    observed[path.decode("utf-8")] = (mode, kind, oid)
            expected = {path: ("100644", "blob", entry["blob"]) for path, entry in entries.items()}
            if observed != expected:
                raise TransportError("LOCAL_RUN_IMMUTABLE_CONFLICT")
            commit = previous
        else:
            commit = self._commit(entries, parent=None, message="M154: preserve local run " + run_id)
            self._git(self.repo, ["update-ref", local_ref, commit, ""])
        self.state = {"schema": SCHEMA, "run_id": run_id, "remote_url": self.remote_url,
                      "report_branch": self.report_branch, "files": entries,
                      "local_commit": commit, "local_ref": local_ref,
                      "candidate": None, "publish_calls": 0, "last_publication": None}
        self._save()
        return {"status": "LOCAL_RECORDED", "local_commit": commit,
                "local_ref": local_ref, "run_id": run_id}

    def _commit(self, entries: Mapping[str, Any], parent: str | None, message: str) -> str:
        index = self.state_dir / ("index." + uuid.uuid4().hex)
        env = {"GIT_INDEX_FILE": str(index)}
        try:
            self._git(self.repo, ["read-tree", parent] if parent else ["read-tree", "--empty"], extra_env=env)
            for path, entry in sorted(entries.items()):
                self._git(self.repo, ["update-index", "--add", "--cacheinfo", "100644", entry["blob"], path], extra_env=env)
            tree = self._git(self.repo, ["write-tree"], extra_env=env).decode("ascii").strip()
            args = ["commit-tree", tree, "-m", message]
            if parent:
                args += ["-p", parent]
            return self._git(self.repo, args).decode("ascii").strip()
        finally:
            index.unlink(missing_ok=True)
            index.with_name(index.name + ".lock").unlink(missing_ok=True)

    def _remote_head(self, repository: Path, branch: str) -> str | None:
        data = self._git(repository, ["ls-remote", "--heads", self.remote_url, "refs/heads/" + branch],
                         code="REMOTE_QUERY_FAILED").decode("utf-8", "strict").strip()
        if not data:
            return None
        rows = data.splitlines()
        if len(rows) != 1:
            raise TransportError("REMOTE_REF_AMBIGUOUS")
        oid, reference = rows[0].split("\t", 1)
        if not HEX40.fullmatch(oid) or reference != "refs/heads/" + branch:
            raise TransportError("REMOTE_REF_INVALID")
        return oid

    def _publish_candidate(self, candidate: dict[str, str] | None) -> dict[str, Any]:
        if candidate is None:
            return {"status": "NOT_CREATED", "commit": None, "branch": None}
        result: dict[str, Any] = {"status": "PENDING", "commit": candidate["commit"], "branch": candidate["branch"]}
        try:
            repository = Path(candidate["repository"])
            actual = self._git(repository, ["rev-parse", candidate["commit"] + "^{commit}"],
                               code="CANDIDATE_OBJECT_MISSING").decode("ascii").strip()
            if actual != candidate["commit"]:
                raise TransportError("CANDIDATE_OBJECT_MISMATCH")
            existing = self._remote_head(repository, candidate["branch"])
            if existing not in (None, candidate["commit"]):
                result.update(status="CONFLICT", error_code="CANDIDATE_REF_CONFLICT")
                return result
            if existing is None:
                self._git(repository, ["push", "--porcelain", self.remote_url,
                                      candidate["commit"] + ":refs/heads/" + candidate["branch"]],
                          code="CANDIDATE_PUSH_FAILED")
            result["status"] = "PUBLISHED"
        except TransportError as exc:
            result["error_code"] = exc.code
        return result

    def _publish_report(self) -> dict[str, Any]:
        assert self.state is not None
        result: dict[str, Any] = {"status": "PENDING", "commit": None, "branch": self.report_branch}
        entries = self.state["files"]
        prefix = "reports/M154/" + self.state["run_id"] + "/"
        for attempt in range(3):
            try:
                parent = self._remote_head(self.repo, self.report_branch)
                if parent is not None:
                    self._git(self.repo, ["fetch", "--quiet", "--no-tags", self.remote_url,
                                          "refs/heads/" + self.report_branch], code="REPORT_FETCH_FAILED")
                    parent = self._git(self.repo, ["rev-parse", "FETCH_HEAD^{commit}"]).decode("ascii").strip()
                    existing: dict[str, tuple[str, str]] = {}
                    rows = self._git(self.repo, ["ls-tree", "-r", "-z", parent, "--", prefix]).split(b"\0")
                    for row in rows:
                        if not row:
                            continue
                        metadata, path_bytes = row.split(b"\t", 1)
                        mode, kind, oid = metadata.decode("ascii").split(" ")
                        path = path_bytes.decode("utf-8", "strict")
                        if kind != "blob" or mode != "100644":
                            raise TransportError("REMOTE_RUN_IMMUTABLE_CONFLICT")
                        existing[path] = (mode, oid)
                    if any(path not in entries or entries[path]["blob"] != value[1]
                           for path, value in existing.items()):
                        raise TransportError("REMOTE_RUN_IMMUTABLE_CONFLICT")
                    if existing and set(existing) != set(entries):
                        # One report is published by one atomic Git commit. An
                        # existing subset is another run definition, not an
                        # interrupted upload that should be completed in place.
                        raise TransportError("REMOTE_RUN_IMMUTABLE_CONFLICT")
                    if set(existing) == set(entries):
                        result.update(status="PUBLISHED", commit=parent)
                        return result
                commit = self._commit(entries, parent, "M154: record run " + self.state["run_id"])
                self._git(self.repo, ["update-ref", "refs/local/publish/" + uuid.uuid4().hex, commit, ""])
                self._git(self.repo, ["push", "--porcelain", self.remote_url,
                                      commit + ":refs/heads/" + self.report_branch], code="REPORT_PUSH_FAILED")
                result.update(status="PUBLISHED", commit=commit)
                return result
            except TransportError as exc:
                result["error_code"] = exc.code
                if exc.code == "REMOTE_RUN_IMMUTABLE_CONFLICT":
                    result["status"] = "CONFLICT"
                    return result
                # Only a refused push can be an append race worth immediate retry.
                if exc.code != "REPORT_PUSH_FAILED" or attempt == 2:
                    return result
        return result

    def publish(
        self,
        candidate_repo: Path | None = None,
        candidate_commit: str | None = None,
        candidate_branch: str | None = None,
    ) -> dict[str, Any]:
        """Try both pushes. Failed candidate publication does not suppress reports.

        Retry by constructing Transport with the same state directory and calling
        publish() without arguments. Tests and candidate creation are not rerun.
        """
        if self.state is None:
            raise TransportError("REPORT_NOT_PREPARED")
        if any(value is not None for value in (candidate_repo, candidate_commit, candidate_branch)):
            if (candidate_repo is None or not isinstance(candidate_commit, str)
                    or not HEX40.fullmatch(candidate_commit)
                    or candidate_branch != "experiments/m154/" + self.state["run_id"]):
                raise TransportError("INVALID_CANDIDATE_BINDING")
            candidate = {"repository": str(Path(candidate_repo).resolve()),
                         "commit": candidate_commit, "branch": candidate_branch}
            if self.state["candidate"] not in (None, candidate):
                raise TransportError("CANDIDATE_BINDING_IMMUTABLE_CONFLICT")
            self.state["candidate"] = candidate
        self.state["publish_calls"] += 1
        self._save()  # Candidate binding survives an interruption during networking.
        candidate_result = self._publish_candidate(self.state["candidate"])
        report_result = self._publish_report()
        complete = (candidate_result["status"] in ("PUBLISHED", "NOT_CREATED")
                    and report_result["status"] == "PUBLISHED")
        blocked = "CONFLICT" in (candidate_result["status"], report_result["status"])
        result = {"candidate": candidate_result, "report": report_result,
                  "queue_state": "PUBLISHED" if complete else "BLOCKED" if blocked else "PENDING",
                  "local_report_commit": self.state["local_commit"], "run_id": self.state["run_id"]}
        self.state["last_publication"] = result
        self._save()
        return result
