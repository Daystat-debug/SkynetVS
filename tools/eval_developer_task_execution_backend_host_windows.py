from __future__ import annotations

import json
import sys

from modules.developer.developer_task_execution_backend_host import (
    inspect_developer_task_execution_backend_host,
)


def main() -> int:
    print("=== DEVELOPER TASK EXECUTION BACKEND HOST WINDOWS SMOKE ===")

    if sys.platform != "win32":
        print(json.dumps(
            {
                "ok": False,
                "issue_codes": ["execution_backend_platform_unsupported"],
                "platform": sys.platform,
            },
            ensure_ascii=False,
            indent=2,
        ))
        return 1

    report = inspect_developer_task_execution_backend_host()
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
