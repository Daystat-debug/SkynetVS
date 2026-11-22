"""Static Windows CLI for one separately authorized, immutable research snapshot."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
import threading

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skynet_explain as cli

SOURCE = "ee908b063c31a5c9dd8e97ef64ca2ddc3b423235"
BASE = frozenset((cli.pilot.CS, cli.pilot.GS, cli.pilot.RK))
SCOPE = BASE | {cli.pilot.PREFIX + "retrieval/" + name for name in ("m126_rank.py", "m127_symbol.py")}
MODES = {"calls": "callers", "flow": "data_flow", "auto": "automatic", "compose": "composed"}
CALL_LIMIT = "Проверяются прямые вызовы внутри функций верхнего уровня. Блок запуска модуля, методы и динамические вызовы вне этой проверки."


class Objects:
    """Only object IDs seen at a manifest path in SOURCE may reach cat-file."""
    def __init__(self, launch, *, baseline=False):
        self.root = launch.plain(cli.pilot.ROOT, directory=True)
        launch.plain(self.root / ".git", directory=True)
        self.exe = launch.plain(Path(r"C:\Program Files\Git\cmd\git.exe"), hardlinks=True)
        self.scope = BASE if baseline else SCOPE
        self.sizes = {}

    def _run(self, *args, limit=4096):
        tree = (len(args) == 6 and args[:5] == ("ls-tree", "-z", "--full-tree", SOURCE, "--")
                and args[-1] in self.scope)
        size = len(args) == 3 and args[:2] == ("cat-file", "-s") and args[2] in self.sizes
        blob = (len(args) == 3 and args[:2] == ("cat-file", "blob") and args[2] in self.sizes
                and self.sizes[args[2]] is not None and limit == self.sizes[args[2]] + 1)
        if not (tree or size or blob) or not (1 <= limit <= (262145 if blob else 4096)):
            raise ValueError("LAB_OBJECT_SCOPE")
        env = {k: os.environ[k] for k in ("SystemRoot", "WINDIR", "TEMP", "TMP") if k in os.environ}
        env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_NO_LAZY_FETCH="1",
                   GIT_ALLOW_PROTOCOL="", GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0", LC_ALL="C")
        command = [self.exe, "--no-optional-locks", "--no-replace-objects", "--literal-pathspecs",
                   "-c", "protocol.allow=never", "-c", "core.hooksPath=" + os.devnull,
                   "-c", "core.fsmonitor=false", "-c", "maintenance.auto=false", "-c", "gc.auto=0",
                   "--git-dir=" + str(self.root / ".git"), *args]
        with subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, env=env) as proc:
            timer = threading.Timer(15, proc.kill)
            timer.start()
            try:
                data = proc.stdout.read(limit + 1)
                if len(data) > limit:
                    proc.kill()
                    raise ValueError("LAB_GIT_OUTPUT_LIMIT")
                if proc.wait():
                    raise ValueError("LAB_GIT_FAILED_" + args[0])
            finally:
                timer.cancel()
                timer.join()
        if tree:
            entry = re.fullmatch(rb"100(?:644|755) blob ([a-f0-9]{40})\t" + re.escape(args[-1].encode()) + rb"\0", data)
            if not entry:
                raise ValueError("LAB_SOURCE_ENTRY")
            self.sizes[entry[1].decode()] = None
        elif size:
            if not re.fullmatch(rb"[1-9][0-9]{0,5}\n", data) or int(data) > 262144:
                raise ValueError("LAB_BLOB_SIZE")
            self.sizes[args[2]] = int(data)
        return data


class Sources(cli.GitSources):
    def head(self):
        # Every ls-tree addresses this literal commit, even across branch switches.
        return SOURCE


def trusted_tools():
    if not (sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode and not sys.flags.optimize):
        raise ValueError("USE_PYTHON_I_S_B")
    cli.pilot.verify_package()
    import ground289
    import retrieval284
    import run289
    run289.own_job()
    if BASE != retrieval284.SCOPE:
        raise ValueError("LAB_BASE_DRIFT")
    return retrieval284.original("m254_core"), retrieval284.original("m254_runner"), ground289


def snapshot(core, launch, *, baseline=False):
    reader = Objects(launch, baseline=baseline)
    return Sources(reader, core, reader.scope)


def ask(mode, question, sources, ground, pending=None):
    result = cli.answer(question, sources, ground, None, clarification=pending, **{MODES[mode]: True})
    if result.get("reason") == "external":
        result["text"] = "Запрошенный файл вне разрешённой области этого снимка."
    return result


def display(result):
    cli.display(result)
    if result.get("status") == "call_sites" or any(a["tool"] == "calls" for a in result.get("actions", [])):
        print(CALL_LIMIT)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    for mode in MODES:
        modes.add_argument("--" + mode, action="store_const", dest="mode", const=mode)
    parser.set_defaults(mode="compose")
    parser.add_argument("question", nargs="?")
    args = parser.parse_args()
    core, launch, ground = trusted_tools()
    sources = snapshot(core, launch)
    print("Git", sources.commit, *sorted(sources.pages), sep="\n")
    if args.question is not None:
        display(ask(args.mode, args.question, sources, ground))
        return
    pending = None
    while True:
        try:
            question = input("> ").strip()
        except EOFError:
            break
        if question == "/exit":
            break
        if question:
            result = ask(args.mode, question, sources, ground, pending)
            display(result)
            pending = result.get("clarification")


if __name__ == "__main__":
    if not sys.stdout.isatty():
        sys.stdout.reconfigure(encoding="utf8")
    try:
        main()
    except (ValueError, OSError, RuntimeError) as exc:
        sys.exit("Чтение остановлено: " + str(exc))
