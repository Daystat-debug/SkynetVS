from __future__ import annotations

import argparse
from pathlib import Path

from modules.learning.correction_evidence_runtime import (
    activate_learning_evidence, build_learning_corrections)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build correction memory, or explicitly activate event evidence.")
    parser.add_argument("--repo", default=str(Path.cwd()), help="Local project root (default: current directory).")
    parser.add_argument("--activate-evidence", action="store_true",
                        help="Freeze legacy counting and initialize a new event epoch; stop older app/builder processes first.")
    args = parser.parse_args(argv)
    repo = Path(args.repo).absolute()
    result = (activate_learning_evidence if args.activate_evidence else build_learning_corrections)(repo)
    print("CORRECTION_RUNTIME_STATUS=" + result["status"])
    print("CORRECTION_RUNTIME_MODE=" + str(result["mode"] or "UNAVAILABLE"))
    if result["status"] == "REFUSED":
        print("CORRECTION_RUNTIME_REASON=" + result["reason"])
        if result["detail_reason"]:
            print("CORRECTION_RUNTIME_DETAIL=" + result["detail_reason"])
        return 2
    if args.activate_evidence:
        print("[OK] Event evidence selected; existing history and correction-memory bytes preserved.")
        print("[INFO] New commands receive the active epoch. No model training or promotion was run.")
        return 0

    stats = result["stats"]
    print("[OK] correction memory checked: data/learning/correction_memory.jsonl")
    print(f"[OK] normalized correction pairs: {stats['processed']}")
    print(f"[OK] created={stats['created']}; increased={stats['increased']}; "
          f"baselined={stats.get('baselined', 0)}; unchanged={stats['unchanged']}; "
          f"new_evidence={stats['new_evidence']}; written={stats['written']}")
    if stats.get("baselined"):
        print("[INFO] Legacy counts preserved; current totals recorded as a baseline.")
    if stats.get("lower_totals"):
        print(f"[INFO] Lower cumulative totals retained: {stats['lower_totals']}; "
              "history truncation or replacement requires a separate review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
