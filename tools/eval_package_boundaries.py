from __future__ import annotations

import ast
import json

from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent

EXPECTED_DEVELOPER_FILES = {
    "modules/developer/__init__.py",
    "modules/developer/developer_task_check_static.py",
    "modules/developer/developer_task_check_static_git.py",
    "modules/developer/developer_task_check_static_python.py",
    "modules/developer/developer_task_execution_boundary_composition.py",
    "modules/developer/developer_task_execution_boundary_composition_payload.py",
    "modules/developer/developer_task_execution_boundary_contract.py",
    "modules/developer/developer_task_execution_boundary_crypto.py",
    "modules/developer/developer_task_execution_boundary_policy.py",
    "modules/developer/developer_task_execution_boundary_verifier.py",
    "modules/developer/developer_task_execution_boundary_worker.py",
    "modules/developer/developer_task_execution_boundary_worker_payload.py",
    "modules/developer/developer_task_execution_environment_inventory.py",
    "modules/developer/developer_task_execution_environment_inventory_policy.py",
    "modules/developer/developer_task_execution_toolchain_observation.py",
    "modules/developer/developer_task_execution_toolchain_observation_policy.py",
    "modules/developer/developer_task_execution_workspace_snapshot.py",
    "modules/developer/developer_task_execution_workspace_snapshot_policy.py",
    "modules/developer/developer_task_execution_runtime_attestation.py",
    "modules/developer/developer_task_execution_runtime_attestation_contract.py",
    "modules/developer/developer_task_execution_runtime_attestation_payload.py",
    "modules/developer/developer_task_execution_runtime_attestation_policy.py",
    "modules/developer/developer_task_execution_runtime_attestation_verifier.py",
    "modules/developer/developer_task_execution_runtime_bundle.py",
    "modules/developer/developer_task_execution_runtime_composition.py",
    "modules/developer/developer_task_execution_runtime_composition_fs.py",
    "modules/developer/developer_task_execution_runtime_lease.py",
    "modules/developer/developer_task_execution_runtime_lease_policy.py",
    "modules/developer/developer_task_execution_runtime_policy.py",
    "modules/developer/developer_task_execution_backend_host.py",
    "modules/developer/developer_task_execution_backend_lifecycle.py",
    "modules/developer/developer_task_execution_backend_lifecycle_payload.py",
    "modules/developer/developer_task_execution_backend_lifecycle_windows.py",
    "modules/developer/developer_task_execution_backend_policy.py",
    "modules/developer/developer_task_contract.py",
    "modules/developer/developer_task_patch_apply.py",
    "modules/developer/developer_task_patch_apply_git.py",
    "modules/developer/developer_task_patch_index.py",
    "modules/developer/developer_task_patch_integrity.py",
    "modules/developer/developer_task_patch_scope.py",
    "modules/developer/developer_task_preflight.py",
    "modules/developer/developer_task_preflight_composition.py",
    "modules/developer/developer_task_validator.py",
    "modules/developer/developer_task_workspace.py",
    "modules/developer/developer_task_workspace_cleanup.py",
    "modules/developer/developer_task_workspace_cleanup_fs.py",
    "modules/developer/developer_task_workspace_git.py",
    "modules/developer/developer_task_workspace_source.py",
}

LEGACY_DEVELOPER_FILES = {
    "modules/developer_task_check_static.py",
    "modules/developer_task_check_static_git.py",
    "modules/developer_task_check_static_python.py",
    "modules/developer_task_execution_boundary_composition.py",
    "modules/developer_task_execution_boundary_composition_payload.py",
    "modules/developer_task_execution_boundary_contract.py",
    "modules/developer_task_execution_boundary_crypto.py",
    "modules/developer_task_execution_boundary_policy.py",
    "modules/developer_task_execution_boundary_verifier.py",
    "modules/developer_task_execution_boundary_worker.py",
    "modules/developer_task_execution_boundary_worker_payload.py",
    "modules/developer_task_execution_environment_inventory.py",
    "modules/developer_task_execution_environment_inventory_policy.py",
    "modules/developer_task_execution_toolchain_observation.py",
    "modules/developer_task_execution_toolchain_observation_policy.py",
    "modules/developer_task_execution_workspace_snapshot.py",
    "modules/developer_task_execution_workspace_snapshot_policy.py",
    "modules/developer_task_execution_runtime_attestation.py",
    "modules/developer_task_execution_runtime_attestation_contract.py",
    "modules/developer_task_execution_runtime_attestation_payload.py",
    "modules/developer_task_execution_runtime_attestation_policy.py",
    "modules/developer_task_execution_runtime_attestation_verifier.py",
    "modules/developer_task_execution_runtime_bundle.py",
    "modules/developer_task_execution_runtime_composition.py",
    "modules/developer_task_execution_runtime_composition_fs.py",
    "modules/developer_task_execution_runtime_lease.py",
    "modules/developer_task_execution_runtime_lease_policy.py",
    "modules/developer_task_execution_runtime_policy.py",
    "modules/developer_task_execution_backend_host.py",
    "modules/developer_task_execution_backend_lifecycle.py",
    "modules/developer_task_execution_backend_lifecycle_payload.py",
    "modules/developer_task_execution_backend_lifecycle_windows.py",
    "modules/developer_task_execution_backend_policy.py",
    "modules/developer_task_contract.py",
    "modules/developer_task_patch_apply.py",
    "modules/developer_task_patch_apply_git.py",
    "modules/developer_task_patch_index.py",
    "modules/developer_task_patch_integrity.py",
    "modules/developer_task_patch_scope.py",
    "modules/developer_task_preflight.py",
    "modules/developer_task_preflight_composition.py",
    "modules/developer_task_validator.py",
    "modules/developer_task_workspace.py",
    "modules/developer_task_workspace_cleanup.py",
    "modules/developer_task_workspace_cleanup_fs.py",
    "modules/developer_task_workspace_git.py",
    "modules/developer_task_workspace_source.py",
}

LEGACY_DEVELOPER_MODULES = {
    "modules.developer_task_check_static",
    "modules.developer_task_check_static_git",
    "modules.developer_task_check_static_python",
    "modules.developer_task_execution_boundary_composition",
    "modules.developer_task_execution_boundary_composition_payload",
    "modules.developer_task_execution_boundary_contract",
    "modules.developer_task_execution_boundary_crypto",
    "modules.developer_task_execution_boundary_policy",
    "modules.developer_task_execution_boundary_verifier",
    "modules.developer_task_execution_boundary_worker",
    "modules.developer_task_execution_boundary_worker_payload",
    "modules.developer_task_execution_environment_inventory",
    "modules.developer_task_execution_environment_inventory_policy",
    "modules.developer_task_execution_toolchain_observation",
    "modules.developer_task_execution_toolchain_observation_policy",
    "modules.developer_task_execution_workspace_snapshot",
    "modules.developer_task_execution_workspace_snapshot_policy",
    "modules.developer_task_execution_runtime_attestation",
    "modules.developer_task_execution_runtime_attestation_contract",
    "modules.developer_task_execution_runtime_attestation_payload",
    "modules.developer_task_execution_runtime_attestation_policy",
    "modules.developer_task_execution_runtime_attestation_verifier",
    "modules.developer_task_execution_runtime_bundle",
    "modules.developer_task_execution_runtime_composition",
    "modules.developer_task_execution_runtime_composition_fs",
    "modules.developer_task_execution_runtime_lease",
    "modules.developer_task_execution_runtime_lease_policy",
    "modules.developer_task_execution_runtime_policy",
    "modules.developer_task_execution_backend_host",
    "modules.developer_task_execution_backend_lifecycle",
    "modules.developer_task_execution_backend_lifecycle_payload",
    "modules.developer_task_execution_backend_lifecycle_windows",
    "modules.developer_task_execution_backend_policy",
    "modules.developer_task_contract",
    "modules.developer_task_patch_apply",
    "modules.developer_task_patch_apply_git",
    "modules.developer_task_patch_index",
    "modules.developer_task_patch_integrity",
    "modules.developer_task_patch_scope",
    "modules.developer_task_preflight",
    "modules.developer_task_preflight_composition",
    "modules.developer_task_validator",
    "modules.developer_task_workspace",
    "modules.developer_task_workspace_cleanup",
    "modules.developer_task_workspace_cleanup_fs",
    "modules.developer_task_workspace_git",
    "modules.developer_task_workspace_source",
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

EXPECTED_RUNTIME_FILES = {
    "modules/runtime/__init__.py",
    "modules/runtime/mode_manager.py",
    "modules/runtime/runtime_shutdown.py",
}

LEGACY_RUNTIME_FILES = {
    "modules/mode_manager.py",
    "modules/runtime_shutdown.py",
}

LEGACY_RUNTIME_REFERENCES = {
    "modules.mode_manager",
    "modules.runtime_shutdown",
    "modules/mode_manager.py",
    "modules/runtime_shutdown.py",
    r"modules\mode_manager.py",
    r"modules\runtime_shutdown.py",
}

EXPECTED_LEARNING_FILES = {
    "modules/learning/__init__.py",
    "modules/learning/correction_memory.py",
    "modules/learning/feedback_analyzer.py",
    "modules/learning/learning_memory.py",
    "modules/learning/promotion_engine.py",
}

LEGACY_LEARNING_FILES = {
    "modules/correction_memory.py",
    "modules/feedback_analyzer.py",
    "modules/learning_memory.py",
    "modules/promotion_engine.py",
}

LEGACY_LEARNING_REFERENCES = {
    "modules.correction_memory",
    "modules.feedback_analyzer",
    "modules.learning_memory",
    "modules.promotion_engine",
    "modules/correction_memory.py",
    "modules/feedback_analyzer.py",
    "modules/learning_memory.py",
    "modules/promotion_engine.py",
    r"modules\correction_memory.py",
    r"modules\feedback_analyzer.py",
    r"modules\learning_memory.py",
    r"modules\promotion_engine.py",
}

EXPECTED_DESKTOP_FILES = {
    "modules/desktop/__init__.py",
    "modules/desktop/screenshot.py",
    "modules/desktop/typing_service.py",
    "modules/desktop/window_context_service.py",
}

LEGACY_DESKTOP_FILES = {
    "modules/screenshot.py",
    "modules/typing_service.py",
    "modules/window_context_service.py",
}

LEGACY_DESKTOP_REFERENCES = {
    "modules.screenshot",
    "modules.typing_service",
    "modules.window_context_service",
    "modules/screenshot.py",
    "modules/typing_service.py",
    "modules/window_context_service.py",
    r"modules\screenshot.py",
    r"modules\typing_service.py",
    r"modules\window_context_service.py",
}


def _project_python_files() -> tuple[Path, ...]:
    paths = list(PROJECT_ROOT.glob("*.py"))

    for root_name in ("modules", "tools", "train"):
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

    runtime_expected_presence = {
        path: (PROJECT_ROOT / path).is_file()
        for path in sorted(EXPECTED_RUNTIME_FILES)
    }

    check(
        "RUNTIME PACKAGE FILES EXIST",
        runtime_expected_presence,
        {
            path: True
            for path in sorted(EXPECTED_RUNTIME_FILES)
        },
    )

    runtime_legacy_presence = {
        path: (PROJECT_ROOT / path).exists()
        for path in sorted(LEGACY_RUNTIME_FILES)
    }

    check(
        "LEGACY RUNTIME FILES ARE ABSENT",
        runtime_legacy_presence,
        {
            path: False
            for path in sorted(LEGACY_RUNTIME_FILES)
        },
    )

    learning_expected_presence = {
        path: (PROJECT_ROOT / path).is_file()
        for path in sorted(EXPECTED_LEARNING_FILES)
    }

    check(
        "LEARNING PACKAGE FILES EXIST",
        learning_expected_presence,
        {
            path: True
            for path in sorted(EXPECTED_LEARNING_FILES)
        },
    )

    learning_legacy_presence = {
        path: (PROJECT_ROOT / path).exists()
        for path in sorted(LEGACY_LEARNING_FILES)
    }

    check(
        "LEGACY LEARNING FILES ARE ABSENT",
        learning_legacy_presence,
        {
            path: False
            for path in sorted(LEGACY_LEARNING_FILES)
        },
    )

    desktop_expected_presence = {
        path: (PROJECT_ROOT / path).is_file()
        for path in sorted(EXPECTED_DESKTOP_FILES)
    }

    check(
        "DESKTOP PACKAGE FILES EXIST",
        desktop_expected_presence,
        {
            path: True
            for path in sorted(EXPECTED_DESKTOP_FILES)
        },
    )

    desktop_legacy_presence = {
        path: (PROJECT_ROOT / path).exists()
        for path in sorted(LEGACY_DESKTOP_FILES)
    }

    check(
        "LEGACY DESKTOP FILES ARE ABSENT",
        desktop_legacy_presence,
        {
            path: False
            for path in sorted(LEGACY_DESKTOP_FILES)
        },
    )

    python_files = _project_python_files()
    this_file = Path(__file__).resolve()
    developer_legacy_references: list[str] = []
    core_legacy_references: list[str] = []
    runtime_legacy_references: list[str] = []
    learning_legacy_references: list[str] = []
    desktop_legacy_references: list[str] = []

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

        for legacy in sorted(LEGACY_RUNTIME_REFERENCES):
            if legacy in text:
                runtime_legacy_references.append(
                    f"{relative}: {legacy}"
                )

        for legacy in sorted(LEGACY_LEARNING_REFERENCES):
            if legacy in text:
                learning_legacy_references.append(
                    f"{relative}: {legacy}"
                )

        for legacy in sorted(LEGACY_DESKTOP_REFERENCES):
            if legacy in text:
                desktop_legacy_references.append(
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

    check(
        "LEGACY RUNTIME REFERENCES ARE ABSENT",
        runtime_legacy_references,
        [],
    )

    check(
        "LEGACY LEARNING REFERENCES ARE ABSENT",
        learning_legacy_references,
        [],
    )

    check(
        "LEGACY DESKTOP REFERENCES ARE ABSENT",
        desktop_legacy_references,
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

    runtime_external_imports: list[str] = []

    for path in sorted((PROJECT_ROOT / "modules" / "runtime").glob("*.py")):
        tree = ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
        )
        relative = path.relative_to(PROJECT_ROOT).as_posix()

        for imported in _module_imports(tree):
            if imported == "__future__":
                continue

            normalized = imported.lstrip(".")

            if imported.startswith("."):
                runtime_external_imports.append(
                    f"{relative}: {imported}"
                )
                continue

            if normalized == "main" or normalized.startswith("main."):
                runtime_external_imports.append(
                    f"{relative}: {imported}"
                )
                continue

            if normalized == "tools" or normalized.startswith("tools."):
                runtime_external_imports.append(
                    f"{relative}: {imported}"
                )
                continue

            if (
                normalized == "modules"
                or normalized.startswith("modules.")
            ) and not (
                normalized == "modules.core"
                or normalized.startswith("modules.core.")
                or normalized == "modules.runtime"
                or normalized.startswith("modules.runtime.")
            ):
                runtime_external_imports.append(
                    f"{relative}: {imported}"
                )

    check(
        "RUNTIME PACKAGE DEPENDS ONLY ON CORE AND ITSELF",
        runtime_external_imports,
        [],
    )

    learning_external_imports: list[str] = []

    for path in sorted((PROJECT_ROOT / "modules" / "learning").glob("*.py")):
        tree = ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
        )
        relative = path.relative_to(PROJECT_ROOT).as_posix()

        for imported in _module_imports(tree):
            if imported == "__future__":
                continue

            normalized = imported.lstrip(".")

            if imported.startswith("."):
                learning_external_imports.append(
                    f"{relative}: {imported}"
                )
                continue

            if normalized == "main" or normalized.startswith("main."):
                learning_external_imports.append(
                    f"{relative}: {imported}"
                )
                continue

            if normalized == "tools" or normalized.startswith("tools."):
                learning_external_imports.append(
                    f"{relative}: {imported}"
                )
                continue

            if (
                normalized == "modules"
                or normalized.startswith("modules.")
            ) and not (
                normalized == "modules.core"
                or normalized.startswith("modules.core.")
                or normalized == "modules.learning"
                or normalized.startswith("modules.learning.")
            ):
                learning_external_imports.append(
                    f"{relative}: {imported}"
                )

    check(
        "LEARNING PACKAGE DEPENDS ONLY ON CORE AND ITSELF",
        learning_external_imports,
        [],
    )

    desktop_external_imports: list[str] = []

    for path in sorted((PROJECT_ROOT / "modules" / "desktop").glob("*.py")):
        tree = ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
        )
        relative = path.relative_to(PROJECT_ROOT).as_posix()

        for imported in _module_imports(tree):
            if imported == "__future__":
                continue

            normalized = imported.lstrip(".")

            if imported.startswith("."):
                desktop_external_imports.append(
                    f"{relative}: {imported}"
                )
                continue

            if normalized == "main" or normalized.startswith("main."):
                desktop_external_imports.append(
                    f"{relative}: {imported}"
                )
                continue

            if normalized == "tools" or normalized.startswith("tools."):
                desktop_external_imports.append(
                    f"{relative}: {imported}"
                )
                continue

            if (
                normalized == "modules"
                or normalized.startswith("modules.")
            ) and not (
                normalized == "modules.core"
                or normalized.startswith("modules.core.")
                or normalized == "modules.desktop"
                or normalized.startswith("modules.desktop.")
            ):
                desktop_external_imports.append(
                    f"{relative}: {imported}"
                )

    check(
        "DESKTOP PACKAGE DEPENDS ONLY ON CORE AND ITSELF",
        desktop_external_imports,
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

    runtime_init_path = PROJECT_ROOT / "modules" / "runtime" / "__init__.py"
    runtime_init_tree = ast.parse(
        runtime_init_path.read_text(encoding="utf-8"),
        filename=str(runtime_init_path),
    )
    runtime_init_imports = [
        item
        for item in _module_imports(runtime_init_tree)
        if item != "__future__"
    ]

    check(
        "RUNTIME PACKAGE INIT HAS NO REEXPORTS",
        runtime_init_imports,
        [],
    )

    learning_init_path = PROJECT_ROOT / "modules" / "learning" / "__init__.py"
    learning_init_tree = ast.parse(
        learning_init_path.read_text(encoding="utf-8"),
        filename=str(learning_init_path),
    )
    learning_init_imports = [
        item
        for item in _module_imports(learning_init_tree)
        if item != "__future__"
    ]

    check(
        "LEARNING PACKAGE INIT HAS NO REEXPORTS",
        learning_init_imports,
        [],
    )

    desktop_init_path = PROJECT_ROOT / "modules" / "desktop" / "__init__.py"
    desktop_init_tree = ast.parse(
        desktop_init_path.read_text(encoding="utf-8"),
        filename=str(desktop_init_path),
    )
    desktop_init_imports = [
        item
        for item in _module_imports(desktop_init_tree)
        if item != "__future__"
    ]

    check(
        "DESKTOP PACKAGE INIT HAS NO REEXPORTS",
        desktop_init_imports,
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
            "runtime_flow": '"runtime_package"' in pipeline_text,
            "learning_flow": '"learning_package"' in pipeline_text,
            "desktop_flow": '"desktop_package"' in pipeline_text,
            "developer_preflight_flow": '"developer_task_preflight"' in pipeline_text,
            "developer_preflight_eval": "tools/eval_developer_task_preflight.py" in pipeline_text,
            "developer_patch_integrity_eval": "tools/eval_developer_task_patch_integrity.py" in pipeline_text,
            "developer_patch_index_eval": "tools/eval_developer_task_patch_index.py" in pipeline_text,
            "developer_patch_scope_eval": "tools/eval_developer_task_patch_scope.py" in pipeline_text,
            "developer_preflight_composition_eval": "tools/eval_developer_task_preflight_composition.py" in pipeline_text,
            "developer_workspace_flow": '"developer_task_workspace"' in pipeline_text,
            "developer_workspace_eval": "tools/eval_developer_task_workspace.py" in pipeline_text,
            "developer_workspace_cleanup_flow": '"developer_task_workspace_cleanup"' in pipeline_text,
            "developer_workspace_cleanup_eval": "tools/eval_developer_task_workspace_cleanup.py" in pipeline_text,
            "developer_patch_apply_flow": '"developer_task_patch_apply"' in pipeline_text,
            "developer_patch_apply_eval": "tools/eval_developer_task_patch_apply.py" in pipeline_text,
            "developer_static_check_flow": '"developer_task_check_static"' in pipeline_text,
            "developer_static_check_eval": "tools/eval_developer_task_check_static.py" in pipeline_text,
            "developer_backend_host_flow": '"developer_task_execution_backend_host"' in pipeline_text,
            "developer_backend_host_eval": "tools/eval_developer_task_execution_backend_host.py" in pipeline_text,
            "developer_backend_host_windows_smoke": "tools/eval_developer_task_execution_backend_host_windows.py" in pipeline_text,
            "developer_backend_lifecycle_flow": '"developer_task_execution_backend_lifecycle"' in pipeline_text,
            "developer_backend_lifecycle_eval": "tools/eval_developer_task_execution_backend_lifecycle.py" in pipeline_text,
            "developer_backend_lifecycle_windows_smoke": "tools/eval_developer_task_execution_backend_lifecycle_windows.py" in pipeline_text,
            "developer_boundary_verifier_flow": '"developer_task_execution_boundary_verifier"' in pipeline_text,
            "developer_boundary_verifier_eval": "tools/eval_developer_task_execution_boundary_verifier.py" in pipeline_text,
            "developer_boundary_crypto_windows_smoke": "tools/eval_developer_task_execution_boundary_crypto_windows.py" in pipeline_text,
            "developer_boundary_worker_flow": '"developer_task_execution_boundary_worker"' in pipeline_text,
            "developer_boundary_worker_eval": "tools/eval_developer_task_execution_boundary_worker.py" in pipeline_text,
            "developer_boundary_worker_windows_smoke": "tools/eval_developer_task_execution_boundary_worker_windows.py" in pipeline_text,
            "developer_boundary_composition_flow": '"developer_task_execution_boundary_composition"' in pipeline_text,
            "developer_boundary_composition_eval": "tools/eval_developer_task_execution_boundary_composition.py" in pipeline_text,
            "developer_boundary_composition_windows_smoke": "tools/eval_developer_task_execution_boundary_composition_windows.py" in pipeline_text,
            "developer_runtime_bundle_flow": '"developer_task_execution_runtime_bundle"' in pipeline_text,
            "developer_runtime_bundle_eval": "tools/eval_developer_task_execution_runtime_bundle.py" in pipeline_text,
            "developer_runtime_bundle_windows_smoke": "tools/eval_developer_task_execution_runtime_bundle_windows.py" in pipeline_text,
            "developer_runtime_attestation_flow": '"developer_task_execution_runtime_attestation"' in pipeline_text,
            "developer_runtime_attestation_eval": "tools/eval_developer_task_execution_runtime_attestation.py" in pipeline_text,
            "developer_runtime_attestation_windows_smoke": "tools/eval_developer_task_execution_runtime_attestation_windows.py" in pipeline_text,
            "developer_runtime_attestation_verifier_flow": '"developer_task_execution_runtime_attestation_verifier"' in pipeline_text,
            "developer_runtime_attestation_verifier_eval": "tools/eval_developer_task_execution_runtime_attestation_verifier.py" in pipeline_text,
            "developer_runtime_attestation_crypto_windows_smoke": "tools/eval_developer_task_execution_runtime_attestation_crypto_windows.py" in pipeline_text,
            "developer_runtime_composition_flow": '"developer_task_execution_runtime_composition"' in pipeline_text,
            "developer_runtime_composition_eval": "tools/eval_developer_task_execution_runtime_composition.py" in pipeline_text,
            "developer_runtime_composition_windows_smoke": "tools/eval_developer_task_execution_runtime_composition_windows.py" in pipeline_text,
            "developer_runtime_lease_flow": '"developer_task_execution_runtime_lease"' in pipeline_text,
            "developer_runtime_lease_eval": "tools/eval_developer_task_execution_runtime_lease.py" in pipeline_text,
            "developer_runtime_lease_windows_smoke": "tools/eval_developer_task_execution_runtime_lease_windows.py" in pipeline_text,
            "developer_environment_inventory_flow": '"developer_task_execution_environment_inventory"' in pipeline_text,
            "developer_environment_inventory_eval": "tools/eval_developer_task_execution_environment_inventory.py" in pipeline_text,
            "developer_environment_inventory_windows_smoke": "tools/eval_developer_task_execution_environment_inventory_windows.py" in pipeline_text,
            "developer_toolchain_observation_flow": '"developer_task_execution_toolchain_observation"' in pipeline_text,
            "developer_toolchain_observation_eval": "tools/eval_developer_task_execution_toolchain_observation.py" in pipeline_text,
            "developer_toolchain_observation_windows_smoke": "tools/eval_developer_task_execution_toolchain_observation_windows.py" in pipeline_text,
            "developer_workspace_snapshot_flow": '"developer_task_execution_workspace_snapshot"' in pipeline_text,
            "developer_workspace_snapshot_eval": "tools/eval_developer_task_execution_workspace_snapshot.py" in pipeline_text,
            "developer_workspace_snapshot_windows_smoke": "tools/eval_developer_task_execution_workspace_snapshot_windows.py" in pipeline_text,
        },
        {
            "pipeline": True,
            "runtime_audit": True,
            "core_flow": True,
            "runtime_flow": True,
            "learning_flow": True,
            "desktop_flow": True,
            "developer_preflight_flow": True,
            "developer_preflight_eval": True,
            "developer_patch_integrity_eval": True,
            "developer_patch_index_eval": True,
            "developer_patch_scope_eval": True,
            "developer_preflight_composition_eval": True,
            "developer_workspace_flow": True,
            "developer_workspace_eval": True,
            "developer_workspace_cleanup_flow": True,
            "developer_workspace_cleanup_eval": True,
            "developer_patch_apply_flow": True,
            "developer_patch_apply_eval": True,
            "developer_static_check_flow": True,
            "developer_static_check_eval": True,
            "developer_backend_host_flow": True,
            "developer_backend_host_eval": True,
            "developer_backend_host_windows_smoke": True,
            "developer_backend_lifecycle_flow": True,
            "developer_backend_lifecycle_eval": True,
            "developer_backend_lifecycle_windows_smoke": True,
            "developer_boundary_verifier_flow": True,
            "developer_boundary_verifier_eval": True,
            "developer_boundary_crypto_windows_smoke": True,
            "developer_boundary_worker_flow": True,
            "developer_boundary_worker_eval": True,
            "developer_boundary_worker_windows_smoke": True,
            "developer_boundary_composition_flow": True,
            "developer_boundary_composition_eval": True,
            "developer_boundary_composition_windows_smoke": True,
            "developer_runtime_bundle_flow": True,
            "developer_runtime_bundle_eval": True,
            "developer_runtime_bundle_windows_smoke": True,
            "developer_runtime_attestation_flow": True,
            "developer_runtime_attestation_eval": True,
            "developer_runtime_attestation_windows_smoke": True,
            "developer_runtime_attestation_verifier_flow": True,
            "developer_runtime_attestation_verifier_eval": True,
            "developer_runtime_attestation_crypto_windows_smoke": True,
            "developer_runtime_composition_flow": True,
            "developer_runtime_composition_eval": True,
            "developer_runtime_composition_windows_smoke": True,
            "developer_runtime_lease_flow": True,
            "developer_runtime_lease_eval": True,
            "developer_runtime_lease_windows_smoke": True,
            "developer_environment_inventory_flow": True,
            "developer_environment_inventory_eval": True,
            "developer_environment_inventory_windows_smoke": True,
            "developer_toolchain_observation_flow": True,
            "developer_toolchain_observation_eval": True,
            "developer_toolchain_observation_windows_smoke": True,
            "developer_workspace_snapshot_flow": True,
            "developer_workspace_snapshot_eval": True,
            "developer_workspace_snapshot_windows_smoke": True,
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