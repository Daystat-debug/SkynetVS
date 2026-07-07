from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()

from modules.actions import Actions


class DummyService:
    pass


class FakePopen:
    calls: List[List[str]] = []

    def __init__(self, cmd: list[str], *args: Any, **kwargs: Any) -> None:
        _ = args
        _ = kwargs
        self.cmd = list(cmd)
        FakePopen.calls.append(self.cmd)


class TestActions(Actions):
    def __init__(self) -> None:
        super().__init__(
            audio=None,
            screenshot_service=DummyService(),
            weather_service=DummyService(),
            typing_service=DummyService(),
            window_context_service=DummyService(),
        )
        self.events: List[str] = []

    def _close_explorer_windows(self) -> bool:
        self.events.append("close_explorer_windows")
        return True

    def _close_windows_by_image_names(self, image_names: list[str]) -> bool:
        self.events.append(f"close_by_image:{','.join(image_names)}")
        return False

    def _close_windows_by_title_patterns(self, patterns: list[str]) -> bool:
        self.events.append(f"close_by_title:{','.join(patterns)}")
        return False

    def _terminate_by_image_names(self, image_names: list[str]) -> bool:
        self.events.append(f"terminate_by_image:{','.join(image_names)}")
        return True


Case = Dict[str, Any]


CASES: List[Case] = [
    {
        "name": "open notepad uses registry command",
        "action": "open_app",
        "app": "notepad",
        "expected": {
            "popen_calls": [["notepad.exe"]],
            "events": [],
        },
    },
    {
        "name": "open explorer uses registry command",
        "action": "open_app",
        "app": "explorer",
        "expected": {
            "popen_calls": [["explorer.exe"]],
            "events": [],
        },
    },
    {
        "name": "folder downloads resolves from registry path kind",
        "action": "folder_path",
        "folder": "downloads",
        "expected_suffix": os.path.join("", "Downloads"),
    },
    {
        "name": "settings sound resolves from registry uri",
        "action": "settings_uri",
        "section": "sound",
        "expected": {
            "uri": "ms-settings:sound",
        },
    },
    {
        "name": "chrome image names come from registry",
        "action": "image_names",
        "app": "chrome",
        "expected": {
            "image_names": ["chrome.exe"],
        },
    },
    {
        "name": "chrome title patterns come from registry",
        "action": "title_patterns",
        "app": "chrome",
        "expected_contains": "chrome",
    },
    {
        "name": "close explorer uses safe explorer strategy",
        "action": "close_app",
        "app": "explorer",
        "expected": {
            "events": ["close_explorer_windows"],
        },
    },
    {
        "name": "close chrome uses registry image names and title patterns",
        "action": "close_app",
        "app": "chrome",
        "expected": {
            "events": [
                "close_by_image:chrome.exe",
                "close_by_title:chrome,google chrome,хром",
                "terminate_by_image:chrome.exe",
            ],
        },
    },
]


def _run_case(actions: TestActions, case: Case) -> Dict[str, Any]:
    action = str(case["action"])

    if action == "open_app":
        FakePopen.calls = []
        original_popen = subprocess.Popen
        subprocess.Popen = FakePopen  # type: ignore[assignment]
        try:
            actions._open_app(str(case["app"]))
        finally:
            subprocess.Popen = original_popen  # type: ignore[assignment]

        return {
            "popen_calls": FakePopen.calls,
            "events": actions.events,
        }

    if action == "folder_path":
        path = actions._resolve_folder_path(str(case["folder"]))
        return {
            "path": path,
            "path_endswith": bool(path and path.endswith(str(case["expected_suffix"]))),
        }

    if action == "settings_uri":
        return {
            "uri": actions._resolve_settings_uri(str(case["section"])),
        }

    if action == "image_names":
        return {
            "image_names": actions._app_image_names(str(case["app"])),
        }

    if action == "title_patterns":
        return {
            "title_patterns": actions._app_window_title_patterns(str(case["app"])),
        }

    if action == "close_app":
        actions._exec_close_app({"app": str(case["app"])})
        return {
            "events": actions.events,
        }

    raise ValueError(f"Unknown action: {action}")


def main() -> int:
    fail_count = 0

    print("=== ACTIONS REGISTRY EVAL REPORT ===")

    for idx, case in enumerate(CASES, start=1):
        actions = TestActions()
        actual = _run_case(actions, case)

        expected = case.get("expected")
        expected_suffix = case.get("expected_suffix")
        expected_contains = case.get("expected_contains")

        if expected is not None:
            ok = actual == expected
        elif expected_suffix is not None:
            ok = bool(actual.get("path_endswith"))
        elif expected_contains is not None:
            ok = str(expected_contains) in actual.get("title_patterns", [])
        else:
            ok = False

        print()
        print(f"{idx}. {case['name']}")
        print(
            json.dumps(
                {
                    "expected": expected
                    if expected is not None
                    else {
                        "expected_suffix": expected_suffix,
                        "expected_contains": expected_contains,
                    },
                    "actual": actual,
                    "ok": ok,
                },
                ensure_ascii=False,
            )
        )

        if ok:
            print("[OK] actions registry case")
        else:
            fail_count += 1
            print("[FAIL] actions registry mismatch")

    print()
    print("=== SUMMARY ===")
    print(
        json.dumps(
            {
                "total_cases": len(CASES),
                "fail_count": fail_count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())