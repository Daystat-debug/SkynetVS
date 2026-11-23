"""Operator navigation over a committed SkynetVS tree. Never import inspected modules."""
import argparse
import ast
from collections import defaultdict
from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys


def git(*args, data=None):
    return subprocess.run(["git", "--no-replace-objects", *args], input=data, stdout=subprocess.PIPE,
                          check=True).stdout


def check_file(path):
    return PurePosixPath(path).name.startswith(("eval_", "test_"))


def classify(path):
    """Role and review disposition. Neither is a runtime reachability claim."""
    parts = path.split("/")
    name = parts[-1]
    if path == "project_inventory.md":
        return "generated-inventory", "retirement-review"
    if path == "test.py":
        return "manual-desktop-consumer", "placement-review"
    if path == "main.py":
        return "runtime-composition", "retain"
    if parts[0] == "modules":
        if parts[1] == "developer_task_ui":
            role = parts[2] if parts[2] in ("vendor", "reference", "app") else "bundle"
            return "ui-" + role, "preserve-bundle"
        if len(parts) == 2:
            return "flat-runtime", "domain-review"
        return "package-" + parts[1], "preserve-boundary"
    if parts[0] == "native":
        if "evidence" in parts or "evidence" in parts[1]:
            return "native-evidence", "preserve-evidence"
        if "tests" in parts:
            role = "native-check"
        elif name.endswith((".cs", ".py", ".cpp", ".c", ".h", ".ps1")):
            role = "native-source-or-tool"
        elif name.endswith(".md"):
            role = "native-document"
        else:
            role = "native-profile-artifact"
        return role, "preserve-profile"
    if parts[0] == "docs":
        if parts[1] == "architecture":
            return ("architecture-record", "date-review" if name.endswith("CURRENT_STATE.md")
                    else "retain-reference")
        if len(parts) > 3 and parts[2] == "navigation_01":
            return "navigation-record", "retain-reference"
        if name == "M154_Workflow.md" or name.endswith("Plan.md"):
            return "maintenance-procedure", "retain-reference"
        if len(parts) > 3 and parts[2].startswith("core_0"):
            return "core-checkpoint", "preserve-evidence"
        return "maintenance-record", "archive-index-review"
    if parts[0] == "tools":
        if path == "tools/README.md":
            return "tooling-guide", "retain-reference"
        if "preparation_history" in parts:
            return "workflow-evidence", "preserve-evidence"
        if len(parts) > 2:
            return "tool-" + parts[1], "retain"
        if check_file(path):
            return "targeted-check", "retain-entrypoint"
        if name.startswith(("skynet_", "m289_", "review_m289_")):
            return "cognitive-experiment", "preserve-experiment"
        return "operator-tool", "retain-entrypoint"
    if parts[0] in ("data", "train"):
        return "project-" + parts[0], "retain"
    if path == "README.md":
        return "operator-guide", "date-review"
    if name.startswith(("requirements", ".")):
        return "repository-config", "retain"
    return "unclassified", "manual-review"


class Snapshot:
    def __init__(self, rev):
        self.sha = git("rev-parse", "--verify", "--end-of-options",
                       rev + "^{commit}").decode().strip()
        entries = git("ls-tree", "-rz", self.sha).split(b"\0")
        self.files = {}
        self.python_blobs = {}
        for entry in filter(None, entries):
            meta, raw_path = entry.split(b"\t", 1)
            mode, kind, oid = meta.decode().split()
            path = raw_path.decode()
            self.files[path] = oid
            if mode in ("100644", "100755") and kind == "blob" and path.endswith(".py"):
                self.python_blobs[path] = oid

    def sources(self, paths=None):
        selected = self.python_blobs if paths is None else {
            path: self.python_blobs[path] for path in sorted(paths) if path in self.python_blobs}
        oids = list(dict.fromkeys(selected.values()))
        if not oids:
            return
        raw = git("cat-file", "--batch", data="".join(x + "\n" for x in oids).encode())
        offset = 0
        blobs = {}
        for expected in oids:
            end = raw.index(b"\n", offset)
            oid, kind, size = raw[offset:end].decode().split()
            if oid != expected or kind != "blob":
                raise ValueError("unexpected object from Git")
            offset = end + 1 + int(size)
            blobs[oid] = raw[end + 1:offset]
            if raw[offset:offset + 1] != b"\n":
                raise ValueError("truncated Git batch")
            offset += 1
        for path, oid in selected.items():
            yield path, blobs[oid]


UI = "modules/developer_task_ui/"


def resolve(source, name, level, python_paths):
    """Static import candidate in the layout used by the script or UI bundle."""
    parent = PurePosixPath(source).parent
    if level:
        if level > len(parent.parts):
            return None
        roots = [parent.parents[level - 2] if level > 1 else parent]
    elif source.startswith(UI):
        roots = [PurePosixPath(UI + "vendor"), PurePosixPath(UI)]
    elif source.startswith(("tools/", "native/", "train/")):
        roots = [parent, PurePosixPath(".")]
    else:
        roots = [PurePosixPath(".")]
    for root in roots:
        base = (root / name.replace(".", "/")).as_posix()
        for target in (base + "/__init__.py", base + ".py"):
            if target in python_paths:
                return target
    return None


@dataclass(frozen=True, order=True)
class Site:
    path: str
    line: int

    def __str__(self):
        return f"{self.path}:{self.line}"


class Index:
    def __init__(self, snap, paths=None):
        self.snap = snap
        self.defs = defaultdict(list)
        self.deps = defaultdict(dict)
        self.users = defaultdict(dict)
        self.literals = defaultdict(dict)
        self.errors = {}
        self.add(paths)

    def add(self, paths):
        snap = self.snap
        for path, data in snap.sources(paths):
            try:
                tree = ast.parse(data, filename=path)
            except (SyntaxError, ValueError) as exc:
                self.errors[path] = str(exc).splitlines()[0]
                continue
            for stmt in tree.body:
                if isinstance(stmt, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    self.defs[stmt.name].append(Site(path, stmt.lineno))
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if node.value in snap.files:
                        self.literals[node.value].setdefault(path, node.lineno)
                    continue
                if isinstance(node, ast.Import):
                    names = [(a.name, 0) for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    names = [(mod, node.level)] if mod else []
                    names.extend((f"{mod}.{a.name}" if mod else a.name, node.level)
                                 for a in node.names if a.name != "*")
                else:
                    continue
                for name, level in names:
                    target = resolve(path, name, level, snap.python_blobs)
                    if target and target != path:
                        self.deps[path].setdefault(target, node.lineno)
                        self.users[target].setdefault(path, node.lineno)

    def file_rows(self, path, limit):
        if path not in self.snap.files:
            return ["no tracked path"]
        rows = []
        if path in self.errors:
            rows.append("source not parsed: " + self.errors[path])
        consumers = self.users[path]
        checks = [p for p in consumers if check_file(p)]
        stem = PurePosixPath(path).stem
        checks.sort(key=lambda p: (not PurePosixPath(p).stem.endswith(stem), p))
        groups = [
            ("imports", sorted(self.deps[path]), self.deps[path], True),
            ("checks", checks, consumers, False),
            ("imported-by", sorted(p for p in consumers if not check_file(p)), consumers, False),
            ("literal-in", sorted(self.literals[path]), self.literals[path], False),
        ]
        for label, paths, lines, forward in groups:
            if paths or (forward and path in self.snap.python_blobs and path not in self.errors):
                rows.append(f"{label} ({len(paths)})")
            for target in paths[:limit]:
                rows.append(f"  {Site(path, lines[target])} -> {target}" if forward
                            else f"  {Site(target, lines[target])}")
            if len(paths) > limit:
                rows.append(f"  +{len(paths) - limit} more")
        return rows or ["no indexed references"]

    def find(self, symbol, limit):
        sites = self.defs.get(symbol, [])
        rows = [symbol + f" | definitions ({len(sites)})"]
        shown = sites[:limit]
        rows.extend(str(site) for site in shown)
        if len(sites) > limit:
            rows.append(f"+{len(sites) - limit} more")
        if sites and len({site.path for site in sites}) == 1:
            rows.extend(self.file_rows(sites[0].path, limit))
        elif sites:
            rows.append("select a path with file")
        return "\n".join(rows)

    def brief(self, symbol, limit):
        """Owner, direct imports and importing checks; use file for reverse/literal edges."""
        sites = self.defs.get(symbol, [])
        if not sites or len({s.path for s in sites}) != 1:
            return self.find(symbol, limit)
        path = sites[0].path
        rows = [f"{symbol} " + " ".join(str(site) for site in sites[:limit])]
        if len(sites) > limit:
            rows.append(f"+{len(sites) - limit} definitions")
        tests = {p: line for p, line in self.users[path].items() if check_file(p)}
        for key, targets in (("imports", self.deps[path]), ("checks", tests)):
            rows.append(f"{key} ({len(targets)}): " + " ".join(
                (f"L{targets[p]}>{p}" if key == "imports" else str(Site(p, targets[p])))
                for p in sorted(targets)[:limit]))
            if len(targets) > limit:
                rows.append(f"+{len(targets) - limit} more")
        return "\n".join(rows)


def grep_paths(snap, flags, patterns, globs):
    if not patterns:
        return set()
    args = [arg for pattern in sorted(set(patterns)) for arg in ("-e", pattern)]
    result = subprocess.run(["git", "--no-replace-objects", "grep", "-l", "-z",
                             *flags, *args, snap.sha, "--", *globs], stdout=subprocess.PIPE)
    if result.returncode not in (0, 1):
        raise RuntimeError(f"git grep exited {result.returncode}")
    return {p.decode().removeprefix(snap.sha + ":") for p in result.stdout.split(b"\0") if p}


def quick_index(snap, symbols):
    """Prefilter conventional declarations, then parse owners + possible importing checks."""
    definitions = ["^(async[[:space:]]+def|def|class)[[:space:]]+" + re.escape(s)
                   + "($|[^[:alnum:]_])" for s in symbols if s.isidentifier()]
    owners = grep_paths(snap, ["-E"], definitions, ["*.py"])
    index = Index(snap, owners)
    names = set()
    for symbol in symbols:
        for site in index.defs.get(symbol, ()):
            path = PurePosixPath(site.path)
            names.add(path.parent.name if path.stem == "__init__" else path.stem)
    checks = grep_paths(snap, ["-w", "-F"], names,
                        ["eval_*.py", "test_*.py", "*/eval_*.py", "*/test_*.py"])
    index.add(checks - owners)
    return index


def audit(snap):
    yield "path\trole\treview"
    for path in sorted(snap.files):
        yield "\t".join((path, *classify(path)))


def topic_cards():
    return json.loads(Path(__file__).with_name("topics.json").read_text(encoding="utf-8"))


def topics(snap, key, cards=None):
    cards = topic_cards() if cards is None else cards
    if not key:
        return [f"{name}  {card['task']}" for name, card in cards.items()]
    card = cards[key]
    rows = [card["task"]]
    for kind in ("entry", "boundary", "check"):
        path = card[kind]
        if path not in snap.files:
            raise ValueError(f"card target absent at this revision: {path}")
        rows.append(f"{kind}: {path}")
    return rows


def task_route(snap, question):
    """Return cards supported by distinct subject terms; retain incomparable matches."""
    def terms(text):
        words = re.findall(r"[^\W_]+", text.casefold().replace("ё", "е"))
        # Process words recur in a developer question regardless of its subject.
        generic = {"провер", "запуск", "показа", "посмот", "исполь", "отдель", "нужный"}
        return {word[:6] for word in words if len(word) >= 3 or word == "ui"} - generic

    cards = topic_cards()
    wanted = terms(question)
    matches = {}
    for key, card in cards.items():
        evidence = wanted & terms(key + " " + card["task"])
        if evidence:
            matches[key] = evidence
    if not matches:
        return ["Нет совпадений в карточках. Список областей: topic."]
    candidates = sorted(key for key, terms_found in matches.items()
                        if not any(terms_found < other for other in matches.values()))
    if len(candidates) > 1:
        return ["Уточните область:"] + [f"topic {k}  {cards[k]['task']}" for k in candidates]
    key = candidates[0]
    return [f"topic {key}", *topics(snap, key, cards)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", default="HEAD")
    parser.add_argument("--limit", type=int, default=8)
    cmds = parser.add_subparsers(dest="cmd", required=True)
    for cmd in ("find", "brief", "quick"):
        cmds.add_parser(cmd).add_argument("symbols", nargs="+")
    cmds.add_parser("file").add_argument("path")
    cmds.add_parser("topic").add_argument("key", nargs="?")
    cmds.add_parser("task").add_argument("question", nargs="+")
    for cmd in ("audit", "edges", "session"):
        cmds.add_parser(cmd)
    args = parser.parse_args()
    if args.limit <= 0:
        parser.error("--limit must be positive")
    snap = Snapshot(args.snapshot)
    if args.cmd == "audit":
        for row in audit(snap):
            print(row)
        return
    print("snapshot", snap.sha)
    if args.cmd in ("topic", "task"):
        try:
            rows = (topics(snap, args.key) if args.cmd == "topic"
                    else task_route(snap, " ".join(args.question)))
            print("\n".join(rows))
        except (KeyError, ValueError) as exc:
            parser.error(str(exc))
        return
    index = quick_index(snap, args.symbols) if args.cmd == "quick" else Index(snap)
    for path, reason in index.errors.items():
        print(f"not indexed: {path}: {reason}", file=sys.stderr)
    if args.cmd == "edges":
        for source, targets in sorted(index.deps.items()):
            for target, line in sorted(targets.items()):
                print(f"{source}:{line}\t{target}")
    elif args.cmd == "file":
        print("\n".join(index.file_rows(args.path, args.limit)))
    elif args.cmd == "session":
        print("Enter a symbol or tracked file path per line. EOF exits.", flush=True)
        for query in sys.stdin:
            key = query.strip()
            if key:
                print("\n".join(index.file_rows(key, args.limit)) if key in snap.files
                      else index.find(key, args.limit), flush=True)
    else:
        for symbol in args.symbols:
            print(index.brief(symbol, args.limit) if args.cmd in ("brief", "quick")
                  else index.find(symbol, args.limit))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    main()
