"""Read-only self-consistency check. Does not compile, execute or admit trust."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath


def _ordinary(path: Path) -> None:
    info = path.lstat()
    if path.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
        raise ValueError(f"Reparse/symlink is not part of this baseline: {path}")


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def check(root: Path) -> dict[str, object]:
    root = root.absolute()
    for parent in reversed((root, *root.parents)):
        _ordinary(parent)
    manifest_path = root / "SOURCE_BASELINE.json"
    _ordinary(manifest_path)
    raw = manifest_path.read_bytes()
    if len(raw) > 131072:
        raise ValueError("Manifest too large")
    manifest = json.loads(raw, object_pairs_hook=_pairs)
    if manifest.get("kind") != "TRUSTED_HOST_SOURCE_BASELINE_V1":
        raise ValueError("Wrong baseline manifest kind")
    files = manifest["files"]
    expected = set(files) | {"SOURCE_BASELINE.json"}
    expected_dirs: set[str] = set()
    for rel in expected:
        parts = PurePosixPath(rel)
        if parts.is_absolute() or any(p in ("..", ".") for p in parts.parts):
            raise ValueError("Unsafe manifest path")
        if str(parts) != rel or "\\" in rel or ":" in rel:
            raise ValueError("Noncanonical manifest path")
        expected_dirs.update(str(p) for p in parts.parents if str(p) != ".")
    observed: set[str] = set()
    observed_dirs: set[str] = set()
    for directory, dirs, names in os.walk(root, followlinks=False):
        base = Path(directory)
        for name in dirs + names:
            _ordinary(base / name)
        observed_dirs.update((base / n).relative_to(root).as_posix() for n in dirs)
        observed.update((base / n).relative_to(root).as_posix() for n in names)
    if observed != expected or observed_dirs != expected_dirs:
        raise ValueError("Baseline inventory differs; do not delete or repair automatically")
    for rel, identity in files.items():
        data = (root / rel).read_bytes()
        actual = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        if actual != identity:
            raise ValueError(f"Baseline bytes differ: {rel}")
    return {
        "result": "SOURCE_SELF_CONSISTENCY_ONLY",
        "files_checked": len(files),
        "native_sources": len([x for x in files if x.endswith(".cs")]),
        "compiler_executed": False,
        "native_executed": False,
        "production_runtime_accepted": False,
        "P00": "NOT_ACCEPTED",
        "P01": "NOT_IMPLEMENTED",
    }


if __name__ == "__main__":
    try:
        print(json.dumps(check(Path(__file__).parent), sort_keys=True, indent=2))
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(f"SOURCE_BASELINE_CHECK_ERROR: {error}")
