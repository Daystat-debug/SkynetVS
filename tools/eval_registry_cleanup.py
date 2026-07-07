from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set


PROJECT_ROOT = Path(__file__).resolve().parent.parent


TARGETS = {
    "entity_registry": PROJECT_ROOT / "modules" / "entity_registry.py",
    "nlu": PROJECT_ROOT / "modules" / "nlu.py",
    "entity_resolver": PROJECT_ROOT / "modules" / "entity_resolver.py",
    "actions": PROJECT_ROOT / "modules" / "actions.py",
    "pipeline": PROJECT_ROOT / "tools" / "pipeline.py",
}


LEGACY_NLU_ASSIGNMENTS = {
    "_APP_SYNS",
    "_APP_TITLES",
    "_SITE_SYNS",
    "_SITE_TITLES",
    "_SITE_URLS",
    "_FOLDER_SYNS",
    "_FOLDER_TITLES",
    "_SETTINGS_SECTION_SYNS",
    "_SETTINGS_SECTION_TITLES",
}


LEGACY_ENTITY_RESOLVER_ASSIGNMENTS = {
    "_APP_ALIASES",
    "_SITE_ALIASES",
    "_SITE_TITLES",
    "_SITE_URLS",
}


REQUIRED_ENTITY_REGISTRY_MARKERS = [
    "APP_REGISTRY",
    "SITE_REGISTRY",
    "FOLDER_REGISTRY",
    "SETTINGS_SECTION_REGISTRY",
    "match_app_code",
    "match_site_code",
    "match_folder_code",
    "match_settings_section_code",
    "get_app_open_command",
    "get_app_image_names",
    "get_app_title_patterns",
    "get_app_close_strategy",
    "get_folder_path_kind",
    "get_settings_section_uri",
]


REQUIRED_NLU_MARKERS = [
    "from modules.entity_registry import",
    "APP_ALIASES as _APP_SYNS",
    "SITE_ALIASES as _SITE_SYNS",
    "FOLDER_ALIASES as _FOLDER_SYNS",
    "SETTINGS_SECTION_ALIASES as _SETTINGS_SECTION_SYNS",
    "match_app_code",
    "match_site_code",
    "match_folder_code",
    "match_settings_section_code",
]


REQUIRED_ENTITY_RESOLVER_MARKERS = [
    "from modules.entity_registry import",
    "match_app",
    "match_site",
    "get_site_title",
    "get_site_url",
]


REQUIRED_ACTIONS_MARKERS = [
    "from modules.entity_registry import",
    "get_app_close_strategy",
    "get_app_image_names",
    "get_app_open_command",
    "get_app_title_patterns",
    "get_folder_path_kind",
    "get_settings_section_uri",
]


FORBIDDEN_ENTITY_RESOLVER_SNIPPETS = [
    "from difflib import SequenceMatcher",
    "_best_candidate_from_aliases",
    "_APP_ALIASES",
    "_SITE_ALIASES",
    "_SITE_URLS",
]


FORBIDDEN_ACTIONS_SNIPPETS = [
    'if app == "notepad"',
    'if app == "calc"',
    'if app == "chrome"',
    'if app == "explorer"',
    'if app == "discord"',
    'if app_code == "explorer"',
    'subprocess.Popen(["notepad.exe"])',
    'subprocess.Popen(["calc.exe"])',
    'subprocess.Popen(["explorer.exe"])',
    'subprocess.Popen(["cmd", "/c", "start", "chrome"])',
    'subprocess.Popen(["cmd", "/c", "start", "discord"])',
    '"CalculatorApp.exe"',
    '"Discord.exe"',
    '"chrome.exe"',
    '"ms-settings:sound"',
    '"ms-settings:network"',
    '"ms-settings:bluetooth"',
    '"ms-settings:display"',
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _parse(path: Path) -> ast.Module:
    return ast.parse(_read(path), filename=str(path))


def _target_names(target: ast.AST) -> Iterable[str]:
    if isinstance(target, ast.Name):
        yield target.id
        return

    if isinstance(target, (ast.Tuple, ast.List)):
        for item in target.elts:
            yield from _target_names(item)


def _top_level_assigned_names(tree: ast.Module) -> Set[str]:
    result: Set[str] = set()

    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                result.update(_target_names(target))
        elif isinstance(node, ast.AnnAssign):
            result.update(_target_names(node.target))
        elif isinstance(node, ast.AugAssign):
            result.update(_target_names(node.target))

    return result


def _missing_markers(text: str, markers: Iterable[str]) -> List[str]:
    return [
        marker
        for marker in markers
        if marker not in text
    ]


def _present_forbidden_snippets(text: str, snippets: Iterable[str]) -> List[str]:
    return [
        snippet
        for snippet in snippets
        if snippet in text
    ]


def _function_source(text: str, tree: ast.Module, function_name: str) -> str:
    lines = text.splitlines()

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is None:
                return ""
            return "\n".join(lines[node.lineno - 1:end_lineno])

    return ""


def _check_entity_registry() -> List[str]:
    errors: List[str] = []
    text = _read(TARGETS["entity_registry"])

    for marker in _missing_markers(text, REQUIRED_ENTITY_REGISTRY_MARKERS):
        errors.append(f"entity_registry.py: missing required marker {marker!r}")

    return errors


def _check_nlu() -> List[str]:
    errors: List[str] = []
    text = _read(TARGETS["nlu"])
    tree = _parse(TARGETS["nlu"])

    assigned = _top_level_assigned_names(tree)
    legacy_assigned = sorted(assigned & LEGACY_NLU_ASSIGNMENTS)

    for name in legacy_assigned:
        errors.append(f"nlu.py: legacy local registry assignment is back: {name}")

    for marker in _missing_markers(text, REQUIRED_NLU_MARKERS):
        errors.append(f"nlu.py: missing registry integration marker {marker!r}")

    return errors


def _check_entity_resolver() -> List[str]:
    errors: List[str] = []
    text = _read(TARGETS["entity_resolver"])
    tree = _parse(TARGETS["entity_resolver"])

    assigned = _top_level_assigned_names(tree)
    legacy_assigned = sorted(assigned & LEGACY_ENTITY_RESOLVER_ASSIGNMENTS)

    for name in legacy_assigned:
        errors.append(f"entity_resolver.py: legacy local registry assignment is back: {name}")

    for marker in _missing_markers(text, REQUIRED_ENTITY_RESOLVER_MARKERS):
        errors.append(f"entity_resolver.py: missing registry integration marker {marker!r}")

    for snippet in _present_forbidden_snippets(text, FORBIDDEN_ENTITY_RESOLVER_SNIPPETS):
        errors.append(f"entity_resolver.py: forbidden legacy snippet found: {snippet!r}")

    return errors


def _check_actions() -> List[str]:
    errors: List[str] = []
    text = _read(TARGETS["actions"])
    tree = _parse(TARGETS["actions"])

    for marker in _missing_markers(text, REQUIRED_ACTIONS_MARKERS):
        errors.append(f"actions.py: missing registry integration marker {marker!r}")

    for snippet in _present_forbidden_snippets(text, FORBIDDEN_ACTIONS_SNIPPETS):
        errors.append(f"actions.py: forbidden legacy hardcode found: {snippet!r}")

    method_requirements: Dict[str, List[str]] = {
        "_open_app": [
            "get_app_open_command",
            "subprocess.Popen(list(command))",
        ],
        "_resolve_folder_path": [
            "get_folder_path_kind",
        ],
        "_resolve_settings_uri": [
            "get_settings_section_uri",
        ],
        "_app_image_names": [
            "get_app_image_names",
        ],
        "_app_window_title_patterns": [
            "get_app_title_patterns",
        ],
        "_exec_close_app": [
            "get_app_close_strategy(app_code)",
            '"explorer_windows_only"',
        ],
    }

    for method_name, markers in method_requirements.items():
        source = _function_source(text, tree, method_name)

        if not source:
            errors.append(f"actions.py: method {method_name} not found")
            continue

        for marker in markers:
            if marker not in source:
                errors.append(
                    f"actions.py: method {method_name} does not use required marker {marker!r}"
                )

    return errors


def _check_pipeline() -> List[str]:
    errors: List[str] = []
    text = _read(TARGETS["pipeline"])

    required = [
        '"registry_cleanup"',
        "Evaluate registry cleanup",
        "tools/eval_registry_cleanup.py",
    ]

    for marker in _missing_markers(text, required):
        errors.append(f"pipeline.py: missing registry_cleanup marker {marker!r}")

    return errors


def main() -> int:
    checks: Dict[str, List[str]] = {
        "entity_registry": _check_entity_registry(),
        "nlu": _check_nlu(),
        "entity_resolver": _check_entity_resolver(),
        "actions": _check_actions(),
        "pipeline": _check_pipeline(),
    }

    fail_count = sum(1 for errors in checks.values() if errors)

    print("=== REGISTRY CLEANUP EVAL REPORT ===")
    print(
        json.dumps(
            {
                "checks": checks,
                "fail_count": fail_count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    if fail_count:
        for section, errors in checks.items():
            for error in errors:
                print(f"[FAIL] {section}: {error}")
    else:
        print("[OK] registry cleanup checks passed")

    print()
    print("=== SUMMARY ===")
    print(
        json.dumps(
            {
                "sections": len(checks),
                "fail_count": fail_count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())