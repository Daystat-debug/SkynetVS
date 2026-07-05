from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable


DEFAULT_EXCLUDE_DIRS = {
    ".git",
    ".idea",
    ".vscode",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "dist",
    "build",
    "coverage",
    "tmp",
    "temp",
}

DEFAULT_EXCLUDE_FILE_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".dll",
    ".exe",
    ".bin",
    ".zip",
    ".7z",
    ".rar",
    ".tar",
    ".gz",
    ".mp3",
    ".wav",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".ico",
    ".joblib",
    ".onnx",
    ".pt",
    ".pth",
    ".gguf",
    ".model",
}

SENSITIVE_FILENAMES = {
    ".env",
    ".env.local",
    ".env.dev",
    ".env.prod",
    "secrets.json",
    "credentials.json",
}


def should_skip_dir(path: Path) -> bool:
    return path.name in DEFAULT_EXCLUDE_DIRS


def should_skip_file(path: Path) -> bool:
    if path.suffix.lower() in DEFAULT_EXCLUDE_FILE_SUFFIXES:
        return True
    return False


def safe_file_label(path: Path) -> str:
    if path.name in SENSITIVE_FILENAMES:
        return f"{path.name}  [SENSITIVE: do not upload contents]"
    return path.name


def count_lines(path: Path) -> int | None:
    try:
        with path.open("r", encoding="utf-8") as f:
            return sum(1 for _ in f)
    except UnicodeDecodeError:
        try:
            with path.open("r", encoding="cp1251") as f:
                return sum(1 for _ in f)
        except Exception:
            return None
    except Exception:
        return None


def file_size_label(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / 1024 / 1024:.1f} MB"


def iter_project_files(root: Path) -> Iterable[Path]:
    for current_root, dirs, files in os.walk(root):
        current_path = Path(current_root)

        dirs[:] = [
            d for d in dirs
            if not should_skip_dir(current_path / d)
        ]

        for file_name in sorted(files):
            path = current_path / file_name
            if should_skip_file(path):
                continue
            yield path


def build_tree(root: Path, max_depth: int | None) -> list[str]:
    lines: list[str] = []
    lines.append(f"# Project inventory")
    lines.append("")
    lines.append(f"Root: `{root}`")
    lines.append("")
    lines.append("## Tree")
    lines.append("")

    all_paths = sorted(iter_project_files(root), key=lambda p: str(p).lower())

    for path in all_paths:
        rel = path.relative_to(root)
        depth = len(rel.parts) - 1

        if max_depth is not None and depth > max_depth:
            continue

        indent = "  " * depth
        try:
            size = path.stat().st_size
            size_text = file_size_label(size)
        except Exception:
            size_text = "unknown size"

        lines_count = count_lines(path)
        lines_text = f", {lines_count} lines" if lines_count is not None else ""

        display_name = safe_file_label(path)
        if len(rel.parts) > 1:
            display_path = Path(*rel.parts[:-1]) / display_name
        else:
            display_path = Path(display_name)

        lines.append(f"- `{display_path}` ({size_text}{lines_text})")

    return lines


def build_summary(root: Path) -> list[str]:
    files = list(iter_project_files(root))

    by_ext: dict[str, int] = {}
    by_top_dir: dict[str, int] = {}

    for path in files:
        rel = path.relative_to(root)

        ext = path.suffix.lower() or "[no extension]"
        by_ext[ext] = by_ext.get(ext, 0) + 1

        top = rel.parts[0] if rel.parts else "."
        by_top_dir[top] = by_top_dir.get(top, 0) + 1

    lines: list[str] = []
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Files listed: **{len(files)}**")
    lines.append("")

    lines.append("### By top-level folder")
    lines.append("")
    for key, value in sorted(by_top_dir.items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"- `{key}`: {value}")

    lines.append("")
    lines.append("### By extension")
    lines.append("")
    for key, value in sorted(by_ext.items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"- `{key}`: {value}")

    return lines


def build_focus_hints(root: Path) -> list[str]:
    interesting_names = {
        "main.py",
        "actions.py",
        "router.py",
        "nlu.py",
        "mode_manager.py",
        "config.py",
        "stt_vosk.py",
        "tts_edge.py",
        "learning_memory.py",
        "feedback_analyzer.py",
        "correction_memory.py",
        "promotion_engine.py",
        "pipeline.py",
        "eval_nlu.py",
        "intents.json",
        "say_templates.json",
    }

    found: list[Path] = []

    for path in iter_project_files(root):
        if path.name in interesting_names:
            found.append(path.relative_to(root))

    lines: list[str] = []
    lines.append("")
    lines.append("## Likely important files")
    lines.append("")
    if not found:
        lines.append("No obvious important files found by filename.")
    else:
        for path in sorted(found, key=lambda p: str(p).lower()):
            lines.append(f"- `{path}`")

    return lines


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        default=".",
        help="Project root. Default: current directory.",
    )
    parser.add_argument(
        "--out",
        default="project_inventory.md",
        help="Output markdown file. Default: project_inventory.md",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=None,
        help="Optional max tree depth.",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    out = Path(args.out).resolve()

    if not root.exists():
        print(f"[FAIL] root does not exist: {root}")
        return 1

    lines: list[str] = []
    lines.extend(build_tree(root, args.max_depth))
    lines.extend(build_summary(root))
    lines.extend(build_focus_hints(root))

    out.write_text("\n".join(lines), encoding="utf-8")

    print(f"[OK] inventory written: {out}")
    print("")
    print("Send me this file or paste its contents:")
    print(f"  {out}")
    print("")
    print("Important:")
    print("  Do NOT send .env contents or secrets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())