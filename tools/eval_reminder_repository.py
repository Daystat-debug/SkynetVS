from __future__ import annotations

import json
import tempfile

from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from modules.reminder_repository import (
    ReminderRepository,
    ReminderRepositoryError,
    ReminderValidationError,
)


class IdFactory:
    def __init__(
        self,
        values: list[str],
    ) -> None:
        self._values = iter(values)

    def __call__(self) -> str:
        return next(self._values)


def main() -> int:
    fail_count = 0
    case_count = 0

    def check(
        name: str,
        actual: Any,
        expected: Any,
    ) -> None:
        nonlocal fail_count, case_count

        case_count += 1
        ok = actual == expected

        print()
        print(f"=== {name} ===")
        print(
            json.dumps(
                {
                    "actual": actual,
                    "expected": expected,
                    "ok": ok,
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )

        if ok:
            print(f"[OK] {name}")
        else:
            fail_count += 1
            print(f"[FAIL] {name}")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        repo_path = (
            root / "reminders.json"
        )

        ids = IdFactory(
            ["r1", "r2", "r3"]
        )

        repository = ReminderRepository(
            repo_path,
            clock=lambda: 100.0,
            id_factory=ids,
        )

        check(
            "EMPTY REPOSITORY",
            {
                "count": repository.count(),
                "rows": repository.list_all(),
                "file_exists": (
                    repo_path.exists()
                ),
            },
            {
                "count": 0,
                "rows": [],
                "file_exists": False,
            },
        )

        first = repository.add(
            text="Купить хлеб",
            due_at_epoch=500.0,
            created_at_epoch=100.0,
        )

        second = repository.add(
            text="Позвонить Сергею",
            due_at_epoch=300.0,
            created_at_epoch=200.0,
        )

        check(
            "ADD AND SORT",
            [
                row.reminder_id
                for row
                in repository.list_all()
            ],
            ["r2", "r1"],
        )

        reloaded = ReminderRepository(
            repo_path
        )

        check(
            "PERSIST AND RELOAD",
            [
                row.to_dict()
                for row
                in reloaded.list_all()
            ],
            [
                second.to_dict(),
                first.to_dict(),
            ],
        )

        latest = reloaded.latest_created()

        check(
            "LATEST CREATED",
            (
                latest.reminder_id
                if latest
                else None
            ),
            "r2",
        )

        check(
            "SEARCH TEXT",
            [
                row.reminder_id
                for row
                in reloaded.search_text(
                    "ХЛЕБ"
                )
            ],
            ["r1"],
        )

        removed = reloaded.remove("r2")

        check(
            "REMOVE ONE",
            {
                "removed": (
                    removed.reminder_id
                    if removed
                    else None
                ),
                "remaining": [
                    row.reminder_id
                    for row
                    in reloaded.list_all()
                ],
            },
            {
                "removed": "r2",
                "remaining": ["r1"],
            },
        )

        third = reloaded.add(
            reminder_id="r3",
            text="Проверить духовку",
            due_at_epoch=700.0,
            created_at_epoch=300.0,
        )

        removed_many = (
            reloaded.remove_many(
                [
                    first.reminder_id,
                    third.reminder_id,
                ]
            )
        )

        check(
            "REMOVE MANY",
            {
                "removed": [
                    row.reminder_id
                    for row in removed_many
                ],
                "count": reloaded.count(),
            },
            {
                "removed": ["r1", "r3"],
                "count": 0,
            },
        )

        invalid_count = 0

        invalid_cases = [
            {
                "text": "",
                "due_at_epoch": 100.0,
            },
            {
                "text": "Тест",
                "due_at_epoch": 0,
            },
            {
                "text": "Тест",
                "due_at_epoch": float(
                    "inf"
                ),
            },
        ]

        for case in invalid_cases:
            try:
                reloaded.add(**case)
            except ReminderValidationError:
                invalid_count += 1

        check(
            "INVALID RECORDS REJECTED",
            invalid_count,
            len(invalid_cases),
        )

        duplicate_repo = (
            ReminderRepository(
                root / "duplicate.json"
            )
        )

        duplicate_repo.add(
            reminder_id="same-id",
            text="Первое",
            due_at_epoch=100.0,
            created_at_epoch=10.0,
        )

        duplicate_rejected = False

        try:
            duplicate_repo.add(
                reminder_id="same-id",
                text="Второе",
                due_at_epoch=200.0,
                created_at_epoch=20.0,
            )
        except ReminderValidationError:
            duplicate_rejected = True

        check(
            "DUPLICATE ID REJECTED",
            duplicate_rejected,
            True,
        )

        broken_path = (
            root / "broken.json"
        )
        broken_path.write_text(
            "{not-json",
            encoding="utf-8",
        )

        broken_rejected = False

        try:
            ReminderRepository(
                broken_path
            )
        except ReminderRepositoryError:
            broken_rejected = True

        check(
            "BROKEN JSON REJECTED",
            broken_rejected,
            True,
        )

        version_path = (
            root / "version.json"
        )
        version_path.write_text(
            json.dumps(
                {
                    "version": 999,
                    "reminders": [],
                }
            ),
            encoding="utf-8",
        )

        version_rejected = False

        try:
            ReminderRepository(
                version_path
            )
        except ReminderRepositoryError:
            version_rejected = True

        check(
            "UNKNOWN VERSION REJECTED",
            version_rejected,
            True,
        )

    print()
    print("=== SUMMARY ===")
    print(
        json.dumps(
            {
                "case_count": case_count,
                "fail_count": fail_count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())