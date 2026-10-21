"""Opt-in, read-only snapshot of ONE committed Python file.

No status/index refresh, checkout, filters, textconv, hooks, fetch, clone or apply.
This is trusted local tooling, NOT a hostile-repository or OS sandbox.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
from pathlib import Path

from .core import SourceSnapshot, blob_oid, check_plain_path, read_plain, sha256, validate_target


class GitReadError(ValueError):
    pass


def find_git() -> Path:
    if os.name == "nt":
        candidates: list[Path] = []
        for key in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)"):
            base = os.environ.get(key)
            if base:
                candidates.extend([Path(base) / "Git/cmd/git.exe", Path(base) / "Git/bin/git.exe"])
        local = os.environ.get("LOCALAPPDATA")
        if local:
            candidates.append(Path(local) / "Programs/Git/cmd/git.exe")
    else:
        found = shutil.which("git")
        candidates = [Path(found)] if found else []
    for path in candidates:
        if path.is_file():
            # Installed tool, not a name resolved from the project directory.
            return path.absolute()
    raise GitReadError("Установленный Git не найден в стандартных каталогах. Ничего не скачано. Учебный пример доступен без Git.")


def git_environment() -> dict[str, str]:
    env = {key: value for key, value in os.environ.items()
           if not key.upper().startswith(("GIT_", "PYTHON", "SSH_"))}
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_SYSTEM": os.devnull,
                "GIT_CONFIG_GLOBAL": os.devnull, "GIT_OPTIONAL_LOCKS": "0",
                "GIT_NO_LAZY_FETCH": "1", "GIT_NO_REPLACE_OBJECTS": "1",
                "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "", "SSH_ASKPASS": "",
                "GIT_ALLOW_PROTOCOL": "", "GIT_PAGER": "", "PAGER": "", "LC_ALL": "C"})
    return env


class GitSourceReader:
    def __init__(self, repository: Path, git: Path | None = None):
        self.repository = Path(os.path.abspath(repository))
        self.git = git or find_git()
        self.commands: list[dict] = []

    def _run(self, *args: str, limit: int = 4096) -> bytes:
        if not args or args[0] not in {"rev-parse", "ls-tree", "cat-file"}:
            raise GitReadError("Команда вне read-only профиля.")
        command = [str(self.git), "--no-optional-locks", "--no-replace-objects", "--literal-pathspecs",
                   "-c", "core.fsmonitor=false", "-c", f"core.hooksPath={os.devnull}",
                   "-c", "protocol.allow=never", "-c", "gc.auto=0", "-c", "maintenance.auto=false",
                   "-C", str(self.repository), *args]
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, env=git_environment(), shell=False,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        chunks: list[bytearray] = [bytearray(), bytearray()]
        errors: list[str] = []

        def consume(stream, index: int, cap: int) -> None:
            try:
                while True:
                    data = stream.read(4096)
                    if not data:
                        break
                    if len(chunks[index]) + len(data) > cap:
                        errors.append("Вывод Git превышает ограничение.")
                        process.kill()
                        break
                    chunks[index].extend(data)
            except Exception as exc:
                errors.append(str(exc))
            finally:
                stream.close()

        threads = [threading.Thread(target=consume, args=(process.stdout, 0, limit), daemon=True),
                   threading.Thread(target=consume, args=(process.stderr, 1, 16384), daemon=True)]
        for thread in threads:
            thread.start()
        try:
            code = process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            code = process.wait(timeout=5)
            errors.append("Превышено время ожидания Git (15 секунд); повтор не выполнялся.")
        for thread in threads:
            thread.join(timeout=3)
        if any(thread.is_alive() for thread in threads):
            errors.append("Потоки вывода Git не завершились.")
        stdout, stderr = bytes(chunks[0]), bytes(chunks[1])
        self.commands.append({"arguments": list(args), "exit_code": code,
                              "stdout_bytes": len(stdout), "stdout_sha256": sha256(stdout),
                              "stderr": stderr.decode("utf-8", "replace")[:2048], "errors": list(errors)})
        if errors or code != 0:
            raise GitReadError("; ".join(errors) or (stderr.decode("utf-8", "replace").strip()[:1200] or f"Git exit={code}"))
        return stdout

    def _sha(self, *args: str) -> str:
        text = self._run(*args).decode("ascii", "strict").strip()
        if not re.fullmatch("[0-9a-f]{40}", text):
            raise GitReadError("Текущий DTR-A требует Git SHA-1 из 40 символов; ответ Git не подходит.")
        return text

    def capture(self, selected: Path, *, allow_proposal_lf_worktree: bool = False) -> SourceSnapshot:
        check_plain_path(self.repository, directory=True)
        # Worktrees with a .git redirect are not silently followed by this first UI.
        check_plain_path(self.repository / ".git", directory=True)
        selected = Path(os.path.abspath(selected))
        try:
            relative = selected.relative_to(self.repository).as_posix()
        except ValueError as exc:
            raise GitReadError("Выбери файл внутри C:\\Project\\SkynetVS\\modules.") from exc
        validate_target(relative)  # Before reading the selected content.
        work_before = read_plain(selected, 65536)
        work_before.decode("utf-8", "strict")
        top = self._run("rev-parse", "--show-toplevel").decode("utf-8", "strict").strip()
        if os.path.normcase(os.path.abspath(top)) != os.path.normcase(str(self.repository)):
            raise GitReadError("Git сообщил другой корень проекта.")
        commit = self._sha("rev-parse", "--verify", "HEAD^{commit}")
        tree = self._sha("rev-parse", "--verify", commit + "^{tree}")
        row = self._run("ls-tree", "-z", "--full-tree", commit, "--", relative)
        match = re.fullmatch(rb"100644 blob ([0-9a-f]{40})\t" + re.escape(relative.encode("ascii")) + rb"\x00", row)
        if not match:
            raise GitReadError("В выбранном commit нет ровно одного обычного файла 100644 по этому пути.")
        oid = match[1].decode("ascii")
        size_text = self._run("cat-file", "-s", oid).strip()
        if not re.fullmatch(rb"[0-9]{1,6}", size_text) or int(size_text) > 65536:
            raise GitReadError("Git-версия файла превышает 64 КиБ или имеет неверный размер.")
        content = self._run("cat-file", "blob", oid, limit=65536)
        if len(content) != int(size_text) or blob_oid(content) != oid:
            raise GitReadError("Git blob не совпадает с размером/идентификатором.")
        content.decode("utf-8", "strict")
        if b"\0" in content:
            raise GitReadError("Бинарный файл не подходит для текстового запроса.")
        relation = "BYTE_EXACT"
        if work_before != content:
            # Only a documented CRLF working-copy transform; no custom Git filters invoked.
            if b"\r" not in content and work_before.replace(b"\r\n", b"\n") == content:
                relation = "ONLY_WORKTREE_CRLF_TO_BLOB_LF"
            elif (allow_proposal_lf_worktree and b"\r" not in work_before and
                  b"\r" not in content.replace(b"\r\n", b"") and
                  content.replace(b"\r\n", b"\n") == work_before):
                # Only M100 own-proposal capture opts in; existing DTR-A callers keep refusal.
                relation = "ONLY_WORKTREE_LF_TO_BLOB_CRLF_M100"
            else:
                raise GitReadError("Рабочий файл отличается от версии HEAD не только переводами строк. Запрос не создан: незакоммиченные изменения не игнорируются. Выбери другой файл или разберём изменения отдельно; автоматического commit/отката нет.")
        if self._sha("rev-parse", "--verify", "HEAD^{commit}") != commit:
            raise GitReadError("HEAD изменился во время чтения. Снимок не принят.")
        if read_plain(selected, 65536) != work_before:
            raise GitReadError("Файл изменился во время чтения. Снимок не принят.")
        return SourceSnapshot(relative, content, commit, tree,
                              {"kind": "OBSERVED_COMMITTED_FILE", "repository": str(self.repository),
                               "current_git_head_observed": True, "head_observation_scope": "ONLY_AT_CAPTURE",
                               "git_executable": str(self.git), "working_copy_sha256": sha256(work_before),
                               "working_copy_relation": relation, "git_read_commands": self.commands,
                               "source_code_executed": False, "source_write_operations": 0,
                               "atomic_hostile_snapshot_proven": False})
