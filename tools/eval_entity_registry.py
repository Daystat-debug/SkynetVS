from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List

from dotenv import load_dotenv

load_dotenv()

from modules.entity_registry import (
    APP_REGISTRY,
    FOLDER_REGISTRY,
    SETTINGS_SECTION_REGISTRY,
    SITE_REGISTRY,
    get_app_close_strategy,
    get_app_image_names,
    get_app_open_command,
    get_app_title,
    get_app_title_patterns,
    get_folder_path_kind,
    get_folder_title,
    get_settings_section_title,
    get_settings_section_uri,
    get_site_title,
    get_site_url,
    match_app_code,
    match_folder_code,
    match_settings_section_code,
    match_site_code,
    normalize_entity_text,
)


Case = Dict[str, Any]


MATCH_CASES: List[Case] = [
    {
        "kind": "app",
        "text": "открой блокнот",
        "expected": "notepad",
    },
    {
        "kind": "app",
        "text": "открой кальк",
        "expected": "calc",
    },
    {
        "kind": "app",
        "text": "открой браузер",
        "expected": "chrome",
    },
    {
        "kind": "app",
        "text": "открой проводник",
        "expected": "explorer",
    },
    {
        "kind": "app",
        "text": "открой де скоро",
        "expected": "discord",
    },
    {
        "kind": "site",
        "text": "открой ютуб",
        "expected": "youtube",
    },
    {
        "kind": "site",
        "text": "открой github.com",
        "expected": "github",
    },
    {
        "kind": "site",
        "text": "открой чат gpt",
        "expected": "chatgpt",
    },
    {
        "kind": "site",
        "text": "открой вк точка ком",
        "expected": "vk",
    },
    {
        "kind": "folder",
        "text": "открой папку загрузок",
        "expected": "downloads",
    },
    {
        "kind": "folder",
        "text": "открой рабочий стол",
        "expected": "desktop",
    },
    {
        "kind": "folder",
        "text": "открой мои документы",
        "expected": "documents",
    },
    {
        "kind": "settings",
        "text": "открой настройки звука",
        "expected": "sound",
    },
    {
        "kind": "settings",
        "text": "открой параметры сети",
        "expected": "network",
    },
    {
        "kind": "settings",
        "text": "открой настройки",
        "expected": "system",
    },
]


def _match(kind: str, text: str) -> str | None:
    if kind == "app":
        return match_app_code(text)
    if kind == "site":
        return match_site_code(text)
    if kind == "folder":
        return match_folder_code(text)
    if kind == "settings":
        return match_settings_section_code(text)
    raise ValueError(f"Unknown match kind: {kind}")


def _validate_aliases(
    *,
    registry_name: str,
    aliases_by_code: Dict[str, Iterable[str]],
) -> List[str]:
    errors: List[str] = []
    seen: Dict[str, str] = {}

    for code, aliases in aliases_by_code.items():
        if not code:
            errors.append(f"{registry_name}: empty code")
            continue

        alias_list = list(aliases)

        if not alias_list:
            errors.append(f"{registry_name}.{code}: no aliases")

        for alias in alias_list:
            alias_norm = normalize_entity_text(alias)

            if not alias_norm:
                errors.append(f"{registry_name}.{code}: empty alias")
                continue

            owner = seen.get(alias_norm)
            if owner and owner != code:
                errors.append(
                    f"{registry_name}: duplicate alias {alias_norm!r} for {owner!r} and {code!r}"
                )
            else:
                seen[alias_norm] = code

    return errors


def _validate_registry_integrity() -> List[str]:
    errors: List[str] = []

    for code, spec in APP_REGISTRY.items():
        if spec.code != code:
            errors.append(f"APP_REGISTRY key mismatch: key={code!r}, spec.code={spec.code!r}")
        if not spec.title:
            errors.append(f"APP_REGISTRY.{code}: empty title")
        if not get_app_title(code):
            errors.append(f"APP_REGISTRY.{code}: get_app_title is empty")

        # В V1 допускаем пустой open_command только если приложение пока не запускается.
        # Но для текущих app все команды должны быть заполнены.
        if not get_app_open_command(code):
            errors.append(f"APP_REGISTRY.{code}: empty open_command")

        if code != "explorer" and not get_app_image_names(code):
            errors.append(f"APP_REGISTRY.{code}: empty image_names")

        if code not in {"explorer"} and not get_app_title_patterns(code):
            errors.append(f"APP_REGISTRY.{code}: empty title_patterns")

        if not get_app_close_strategy(code):
            errors.append(f"APP_REGISTRY.{code}: empty close_strategy")

    for code, spec in SITE_REGISTRY.items():
        if spec.code != code:
            errors.append(f"SITE_REGISTRY key mismatch: key={code!r}, spec.code={spec.code!r}")
        if not get_site_title(code):
            errors.append(f"SITE_REGISTRY.{code}: empty title")
        url = get_site_url(code)
        if not url.startswith("https://"):
            errors.append(f"SITE_REGISTRY.{code}: bad url={url!r}")

    for code, spec in FOLDER_REGISTRY.items():
        if spec.code != code:
            errors.append(f"FOLDER_REGISTRY key mismatch: key={code!r}, spec.code={spec.code!r}")
        if not get_folder_title(code):
            errors.append(f"FOLDER_REGISTRY.{code}: empty title")
        if not get_folder_path_kind(code):
            errors.append(f"FOLDER_REGISTRY.{code}: empty path_kind")

    for code, spec in SETTINGS_SECTION_REGISTRY.items():
        if spec.code != code:
            errors.append(
                f"SETTINGS_SECTION_REGISTRY key mismatch: key={code!r}, spec.code={spec.code!r}"
            )
        if not get_settings_section_title(code):
            errors.append(f"SETTINGS_SECTION_REGISTRY.{code}: empty title")
        if not get_settings_section_uri(code).startswith("ms-settings:"):
            errors.append(f"SETTINGS_SECTION_REGISTRY.{code}: bad uri")

    errors.extend(
        _validate_aliases(
            registry_name="APP_REGISTRY",
            aliases_by_code={code: spec.aliases for code, spec in APP_REGISTRY.items()},
        )
    )
    errors.extend(
        _validate_aliases(
            registry_name="SITE_REGISTRY",
            aliases_by_code={code: spec.aliases for code, spec in SITE_REGISTRY.items()},
        )
    )
    errors.extend(
        _validate_aliases(
            registry_name="FOLDER_REGISTRY",
            aliases_by_code={code: spec.aliases for code, spec in FOLDER_REGISTRY.items()},
        )
    )
    errors.extend(
        _validate_aliases(
            registry_name="SETTINGS_SECTION_REGISTRY",
            aliases_by_code={code: spec.aliases for code, spec in SETTINGS_SECTION_REGISTRY.items()},
        )
    )

    return errors


def main() -> int:
    fail_count = 0

    print("=== ENTITY REGISTRY EVAL REPORT ===")

    integrity_errors = _validate_registry_integrity()

    print()
    print("--- registry integrity ---")
    print(
        json.dumps(
            {
                "app_count": len(APP_REGISTRY),
                "site_count": len(SITE_REGISTRY),
                "folder_count": len(FOLDER_REGISTRY),
                "settings_section_count": len(SETTINGS_SECTION_REGISTRY),
                "errors": integrity_errors,
            },
            ensure_ascii=False,
        )
    )

    if integrity_errors:
        fail_count += 1
        for error in integrity_errors:
            print(f"[FAIL] {error}")
    else:
        print("[OK] registry integrity")

    print()
    print("--- alias match cases ---")

    for idx, case in enumerate(MATCH_CASES, start=1):
        kind = str(case["kind"])
        text = str(case["text"])
        expected = str(case["expected"])

        actual = _match(kind, text)
        ok = actual == expected

        print()
        print(f"{idx}. {kind}: {text}")
        print(
            json.dumps(
                {
                    "kind": kind,
                    "text": text,
                    "expected": expected,
                    "actual": actual,
                    "ok": ok,
                },
                ensure_ascii=False,
            )
        )

        if ok:
            print("[OK] registry match case")
        else:
            fail_count += 1
            print("[FAIL] registry match mismatch")

    print()
    print("=== SUMMARY ===")
    print(
        json.dumps(
            {
                "match_cases": len(MATCH_CASES),
                "fail_count": fail_count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())