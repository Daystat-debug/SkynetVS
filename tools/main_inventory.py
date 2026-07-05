from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAIN_PATH = PROJECT_ROOT / "main.py"
OUT_DIR = PROJECT_ROOT / "data" / "logs" / "inventory"


@dataclass(frozen=True)
class FunctionInfo:
    name: str
    qualname: str
    lineno: int
    end_lineno: int
    loc: int
    depth: int


class FunctionCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.stack: List[str] = []
        self.functions: List[FunctionInfo] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._handle_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._handle_function(node)

    def _handle_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        end_lineno = int(getattr(node, "end_lineno", node.lineno))
        qualname = ".".join([*self.stack, node.name]) if self.stack else node.name

        info = FunctionInfo(
            name=node.name,
            qualname=qualname,
            lineno=int(node.lineno),
            end_lineno=end_lineno,
            loc=max(1, end_lineno - int(node.lineno) + 1),
            depth=len(self.stack),
        )
        self.functions.append(info)

        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()


def _read_main() -> str:
    return MAIN_PATH.read_text(encoding="utf-8")


def _line_count(text: str) -> int:
    return len(text.splitlines())


def _load_functions(source: str) -> List[FunctionInfo]:
    tree = ast.parse(source, filename=str(MAIN_PATH))
    collector = FunctionCollector()
    collector.visit(tree)
    return collector.functions


def _markdown_table(rows: List[List[str]], headers: List[str]) -> List[str]:
    lines: List[str] = []

    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join("---" for _ in headers) + " |")

    for row in rows:
        lines.append("| " + " | ".join(row) + " |")

    return lines


def _format_function_rows(functions: List[FunctionInfo]) -> List[List[str]]:
    return [
        [
            f"`{fn.qualname}`",
            str(fn.lineno),
            str(fn.end_lineno),
            str(fn.loc),
            str(fn.depth),
        ]
        for fn in functions
    ]


def build_report() -> str:
    source = _read_main()
    total_lines = _line_count(source)
    functions = _load_functions(source)

    top_level = [fn for fn in functions if fn.depth == 0]
    nested = [fn for fn in functions if fn.depth > 0]

    largest = sorted(functions, key=lambda fn: fn.loc, reverse=True)[:15]
    largest_nested = sorted(nested, key=lambda fn: fn.loc, reverse=True)[:15]

    main_fn = next((fn for fn in functions if fn.qualname == "main"), None)

    summary = {
        "main_py_lines": total_lines,
        "functions_total": len(functions),
        "top_level_functions": len(top_level),
        "nested_functions": len(nested),
        "main_function_lines": main_fn.loc if main_fn else None,
    }

    lines: List[str] = []
    lines.append("# main.py inventory")
    lines.append("")
    lines.append(f"Generated: `{datetime.now().isoformat(timespec='seconds')}`")
    lines.append(f"File: `{MAIN_PATH}`")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(summary, ensure_ascii=False, indent=2))
    lines.append("```")
    lines.append("")

    lines.append("## Largest functions")
    lines.append("")
    lines.extend(
        _markdown_table(
            _format_function_rows(largest),
            ["Function", "Start", "End", "LOC", "Depth"],
        )
    )
    lines.append("")

    lines.append("## Largest nested functions")
    lines.append("")
    if largest_nested:
        lines.extend(
            _markdown_table(
                _format_function_rows(largest_nested),
                ["Function", "Start", "End", "LOC", "Depth"],
            )
        )
    else:
        lines.append("No nested functions found.")
    lines.append("")

    lines.append("## Top-level functions")
    lines.append("")
    lines.extend(
        _markdown_table(
            _format_function_rows(top_level),
            ["Function", "Start", "End", "LOC", "Depth"],
        )
    )
    lines.append("")

    lines.append("## Nested functions")
    lines.append("")
    if nested:
        lines.extend(
            _markdown_table(
                _format_function_rows(nested),
                ["Function", "Start", "End", "LOC", "Depth"],
            )
        )
    else:
        lines.append("No nested functions found.")
    lines.append("")

    lines.append("## Interpretation hints")
    lines.append("")
    lines.append("- Very large nested functions are the best candidates for extraction.")
    lines.append("- Helpers with low coupling should be extracted before event-loop/stateful code.")
    lines.append("- Avoid moving several stateful blocks at once.")
    lines.append("- After every extraction, run `python tools/pipeline.py check`.")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    if not MAIN_PATH.exists():
        print(f"[FAIL] main.py not found: {MAIN_PATH}")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    report = build_report()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUT_DIR / f"{ts}_main_inventory.md"
    latest_path = OUT_DIR / "latest_main_inventory.md"

    out_path.write_text(report, encoding="utf-8")
    latest_path.write_text(report, encoding="utf-8")

    print("[OK] main inventory written:")
    print(f"  {out_path}")
    print(f"  {latest_path}")
    print()
    print("Send me latest_main_inventory.md or the timestamped report.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())