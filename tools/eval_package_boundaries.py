from __future__ import annotations

import ast
import json

from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent

EXPECTED_DEVELOPER_FILES = {
    "modules/developer/__init__.py",
    "modules/developer/developer_task_contract.py",
    "modules/developer/developer_task_validator.py",
}

LEGACY_DEVELOPER_FILES = {
    "modules/developer_task_contract.py",
    "modules/developer_task_validator.py",
}

LEGACY_DEVELOPER_MODULES = {
    "modules.developer_task_contract",
    "modules.developer_task_validator",
}

EXPECTED_CORE_FILES = {
    "modules/core/__init__.py",
    "modules/core/config.py",
    "modules/core/error_log.py",
    "modules/core/logger.py",
    "modules/core/operation_telemetry.py",
}

LEGACY_CORE_FILES = {
    "modules/config.py",
    "modules/error_log.py",
    "modules/logger.py",
    "modules/operation_telemetry.py",
}

LEGACY_CORE_REFERENCES = {
    "modules.config",
    "modules.error_log",
    "modules.logger",
    "modules.operation_telemetry",
    "modules/config.py",
    "modules/error_log.py",
    "modules/logger.py",
    "modules/operation_telemetry.py",
    r"modules\config.py",
    r"modules\error_log.py",
    r"modules\logger.py",
    r"modules\operation_telemetry.py",
}


def _project_python_files() -> tuple[Path, ...]:
    paths = [PROJECT_ROOT / "main.py"]

    for root_name in ("modules", "tools"):
        root = PROJECT_ROOT / root_name

        if root.is_dir():
            paths.extend(root.rglob("*.py"))

    return tuple(sorted({
        path.resolve()
        for path in paths
        if path.is_file() and "__pycache__" not in path.parts
    }))


def _module_imports(tree: ast.AST) -> tuple[str, ...]:
    imports: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(f"{'.' * int(node.level or 0)}{node.module or ''}")

    return tuple(imports)


def _assignment_strings(tree: ast.Module, name: str) -> set[str]:
    for node in tree.body:
        value: ast.AST | None = None

        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            value = node.value

        if value is None:
            continue

        result = ast.literal_eval(value)

        if not isinstance(result, (list, tuple, set)) or not all(isinstance(item, str) for item in result):
            raise RuntimeError(f"{name} must contain strings")

        return set(result)

    raise RuntimeError(f"Assignment not found: {name}")


def main() -> int:
    case_count = 0
    fail_count = 0

    def check(name: str, actual: Any, expected: Any) -> None:
        nonlocal case_count, fail_count

        case_count += 1
        ok = actual == expected

        print()
        print(f"=== {name} ===")
        print(json.dumps(
            {
                "actual": actual,
                "expected": expected,
                "ok": ok,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ))

        if ok:
            print(f"[OK] {name}")
        else:
            fail_count += 1
            print(f"[FAIL] {name}")

    expected_presence = {
        path: (PROJECT_ROOT / path).is_file()
        for path in sorted(EXPECTED_DEVELOPER_FILES)
    }

    check(
        "DEVELOPER PACKAGE FILES EXIST",
        expected_presence,
        {path: True for path in sorted(EXPECTED_DEVELOPER_FILES)},
    )

    legacy_presence = {
        path: (PROJECT_ROOT / path).exists()
        for path in sorted(LEGACY_DEVELOPER_FILES)
    }

    check(
        "LEGACY DEVELOPER FILES ARE ABSENT",
        legacy_presence,
        {path: False for path in sorted(LEGACY_DEVELOPER_FILES)},
    )

    core_expected_presence = {
        path: (PROJECT_ROOT / path).is_file()
        for path in sorted(EXPECTED_CORE_FILES)
    }

    check(
        "CORE PACKAGE FILES EXIST",
        core_expected_presence,
        {
            path: True
            for path in sorted(EXPECTED_CORE_FILES)
        },
    )

    core_legacy_presence = {
        path: (PROJECT_ROOT / path).exists()
        for path in sorted(LEGACY_CORE_FILES)
    }

    check(
        "LEGACY CORE FILES ARE ABSENT",
        core_legacy_presence,
        {
            path: False
            for path in sorted(LEGACY_CORE_FILES)
        },
    )

    python_files = _project_python_files()
    this_file = Path(__file__).resolve()
    developer_legacy_references: list[str] = []
    core_legacy_references: list[str] = []

    for path in python_files:
        if path == this_file:
            continue

        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(PROJECT_ROOT).as_posix()

        for legacy in sorted(LEGACY_DEVELOPER_MODULES):
            if legacy in text:
                developer_legacy_references.append(
                    f"{relative}: {legacy}"
                )

        for legacy in sorted(LEGACY_CORE_REFERENCES):
            if legacy in text:
                core_legacy_references.append(
                    f"{relative}: {legacy}"
                )

    check(
        "LEGACY DEVELOPER MODULE REFERENCES ARE ABSENT",
        developer_legacy_references,
        [],
    )

    check(
        "LEGACY CORE REFERENCES ARE ABSENT",
        core_legacy_references,
        [],
    )

    developer_external_imports: list[str] = []

    for path in sorted((PROJECT_ROOT / "modules" / "developer").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        relative = path.relative_to(PROJECT_ROOT).as_posix()

        for imported in _module_imports(tree):
            if imported == "__future__" or imported.startswith("."):
                continue

            if imported == "tools" or imported.startswith("tools."):
                developer_external_imports.append(f"{relative}: {imported}")
                continue

            if (imported == "modules" or imported.startswith("modules.")) and not imported.startswith("modules.developer"):
                developer_external_imports.append(f"{relative}: {imported}")

    check(
        "DEVELOPER PACKAGE DEPENDS ONLY ON ITSELF AND STDLIB",
        developer_external_imports,
        [],
    )

    core_project_imports: list[str] = []

    for path in sorted((PROJECT_ROOT / "modules" / "core").glob("*.py")):
        tree = ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
        )
        relative = path.relative_to(PROJECT_ROOT).as_posix()

        for imported in _module_imports(tree):
            if imported == "__future__":
                continue

            normalized = imported.lstrip(".")

            if (
                imported.startswith(".")
                or normalized == "main"
                or normalized.startswith("main.")
                or normalized == "modules"
                or normalized.startswith("modules.")
                or normalized == "tools"
                or normalized.startswith("tools.")
            ):
                core_project_imports.append(
                    f"{relative}: {imported}"
                )

    check(
        "CORE PACKAGE HAS NO PROJECT LAYER DEPENDENCIES",
        core_project_imports,
        [],
    )

    modules_to_tools: list[str] = []

    for path in sorted((PROJECT_ROOT / "modules").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        relative = path.relative_to(PROJECT_ROOT).as_posix()

        for imported in _module_imports(tree):
            normalized = imported.lstrip(".")

            if normalized == "tools" or normalized.startswith("tools."):
                modules_to_tools.append(f"{relative}: {imported}")

    check("PRODUCTION MODULES DO NOT IMPORT TOOLS", modules_to_tools, [])

    init_path = PROJECT_ROOT / "modules" / "developer" / "__init__.py"
    init_tree = ast.parse(init_path.read_text(encoding="utf-8"), filename=str(init_path))
    init_imports = [item for item in _module_imports(init_tree) if item != "__future__"]

    check("DEVELOPER PACKAGE INIT HAS NO REEXPORTS", init_imports, [])

    core_init_path = PROJECT_ROOT / "modules" / "core" / "__init__.py"
    core_init_tree = ast.parse(
        core_init_path.read_text(encoding="utf-8"),
        filename=str(core_init_path),
    )
    core_init_imports = [
        item
        for item in _module_imports(core_init_tree)
        if item != "__future__"
    ]

    check(
        "CORE PACKAGE INIT HAS NO REEXPORTS",
        core_init_imports,
        [],
    )

    validator_path = PROJECT_ROOT / "modules" / "developer" / "developer_task_validator.py"
    validator_tree = ast.parse(validator_path.read_text(encoding="utf-8"), filename=str(validator_path))
    protected_exact = _assignment_strings(validator_tree, "_PROTECTED_EXACT_PATHS")
    protected_prefixes = _assignment_strings(validator_tree, "_PROTECTED_PATH_PREFIXES")

    check(
        "DEVELOPER SAFETY PATHS ARE PROTECTED",
        {
            "new_package": "modules/developer/" in protected_prefixes,
            "legacy_flat": "modules/developer_" in protected_prefixes,
            "developer_tools": "tools/developer_" in protected_prefixes,
            "developer_evals": "tools/eval_developer_" in protected_prefixes,
            "package_boundary_eval": "tools/eval_package_boundaries.py" in protected_exact,
            "browser_extension": "browser_extension/" in protected_prefixes,
        },
        {
            "new_package": True,
            "legacy_flat": True,
            "developer_tools": True,
            "developer_evals": True,
            "package_boundary_eval": True,
            "browser_extension": True,
        },
    )

    pipeline_text = (PROJECT_ROOT / "tools" / "pipeline.py").read_text(encoding="utf-8")
    audit_text = (PROJECT_ROOT / "tools" / "eval_runtime_architecture_audit.py").read_text(encoding="utf-8")

    check(
        "PACKAGE BOUNDARY GUARD IS WIRED",
        {
            "pipeline": "tools/eval_package_boundaries.py" in pipeline_text,
            "runtime_audit": "tools/eval_package_boundaries.py" in audit_text,
            "core_flow": '"core_package"' in pipeline_text,
        },
        {
            "pipeline": True,
            "runtime_audit": True,
            "core_flow": True,
        },
    )

    print()
    print("=== SUMMARY ===")
    print(json.dumps(
        {
            "case_count": case_count,
            "fail_count": fail_count,
        },
        ensure_ascii=False,
        indent=2,
    ))

    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())