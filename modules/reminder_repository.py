from __future__ import annotations

import json
import math
import os
import tempfile
import threading
import time
import uuid

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable


REMINDER_SCHEMA_VERSION = 1
MAX_REMINDER_TEXT_LENGTH = 500


class ReminderRepositoryError(RuntimeError):
    pass


class ReminderValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ReminderRecord:
    reminder_id: str
    text: str
    due_at_epoch: float
    created_at_epoch: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.reminder_id,
            "text": self.text,
            "due_at_epoch": self.due_at_epoch,
            "created_at_epoch": (
                self.created_at_epoch
            ),
        }


ClockFunc = Callable[[], float]
IdFactory = Callable[[], str]


def _default_id_factory() -> str:
    return uuid.uuid4().hex


def _normalize_text(text: str) -> str:
    return " ".join(
        str(text or "").split()
    )


def _validate_epoch(
    value: Any,
    *,
    field_name: str,
) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ReminderValidationError(
            f"{field_name} must be numeric"
        ) from exc

    if not math.isfinite(result):
        raise ReminderValidationError(
            f"{field_name} must be finite"
        )

    if result <= 0:
        raise ReminderValidationError(
            f"{field_name} must be positive"
        )

    return result


def _build_record(
    *,
    reminder_id: Any,
    text: Any,
    due_at_epoch: Any,
    created_at_epoch: Any,
) -> ReminderRecord:
    clean_id = str(
        reminder_id or ""
    ).strip()

    if not clean_id:
        raise ReminderValidationError(
            "reminder id is empty"
        )

    clean_text = _normalize_text(
        str(text or "")
    )

    if not clean_text:
        raise ReminderValidationError(
            "reminder text is empty"
        )

    if len(clean_text) > (
        MAX_REMINDER_TEXT_LENGTH
    ):
        raise ReminderValidationError(
            "reminder text is too long"
        )

    return ReminderRecord(
        reminder_id=clean_id,
        text=clean_text,
        due_at_epoch=_validate_epoch(
            due_at_epoch,
            field_name="due_at_epoch",
        ),
        created_at_epoch=_validate_epoch(
            created_at_epoch,
            field_name="created_at_epoch",
        ),
    )


class ReminderRepository:
    """
    Потокобезопасное JSON-хранилище нап )
    """

class ReminderRepository:
    """
    Потокобезопасное JSON-хранилище напоминаний.

    Гарантии:
      - атомарная запись через временный файл;
      - записи сортируются по времени срабатывания;
      - повреждённый JSON не перезаписывается молча;
      - одинаковые ID запрещены.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        clock: ClockFunc = time.time,
        id_factory: IdFactory = (
            _default_id_factory
        ),
    ) -> None:
        self._path = Path(path)
        self._clock = clock
        self._id_factory = id_factory
        self._lock = threading.RLock()

        self._records: dict[
            str,
            ReminderRecord,
        ] = {}

        self._load()

    @property
    def path(self) -> Path:
        return self._path

    def _sorted_locked(
        self,
    ) -> list[ReminderRecord]:
        return sorted(
            self._records.values(),
            key=lambda row: (
                row.due_at_epoch,
                row.created_at_epoch,
                row.reminder_id,
            ),
        )

    def _load(self) -> None:
        with self._lock:
            if not self._path.exists():
                self._records = {}
                return

            try:
                raw = self._path.read_text(
                    encoding="utf-8"
                )
                payload = json.loads(raw)
            except Exception as exc:
                raise ReminderRepositoryError(
                    "failed to read reminder "
                    f"repository: {self._path}"
                ) from exc

            if not isinstance(payload, dict):
                raise ReminderRepositoryError(
                    "reminder repository root "
                    "must be an object"
                )

            try:
                version = int(
                    payload.get("version")
                )
            except (TypeError, ValueError) as exc:
                raise ReminderRepositoryError(
                    "invalid reminder repository "
                    "version"
                ) from exc

            if version != REMINDER_SCHEMA_VERSION:
                raise ReminderRepositoryError(
                    "unsupported reminder "
                    f"repository version: {version}"
                )

            rows = payload.get("reminders")

            if not isinstance(rows, list):
                raise ReminderRepositoryError(
                    "reminders must be a list"
                )

            loaded: dict[
                str,
                ReminderRecord,
            ] = {}

            for index, row in enumerate(rows):
                if not isinstance(row, dict):
                    raise ReminderRepositoryError(
                        "invalid reminder row "
                        f"at index {index}"
                    )

                try:
                    record = _build_record(
                        reminder_id=row.get("id"),
                        text=row.get("text"),
                        due_at_epoch=row.get(
                            "due_at_epoch"
                        ),
                        created_at_epoch=row.get(
                            "created_at_epoch"
                        ),
                    )
                except ReminderValidationError as exc:
                    raise ReminderRepositoryError(
                        "invalid reminder row "
                        f"at index {index}"
                    ) from exc

                if record.reminder_id in loaded:
                    raise ReminderRepositoryError(
                        "duplicate reminder id: "
                        f"{record.reminder_id}"
                    )

                loaded[
                    record.reminder_id
                ] = record

            self._records = loaded

    def _save_locked(self) -> None:
        self._path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = {
            "version": REMINDER_SCHEMA_VERSION,
            "reminders": [
                record.to_dict()
                for record
                in self._sorted_locked()
            ],
        }

        file_descriptor: int | None = None
        temp_path: str | None = None

        try:
            (
                file_descriptor,
                temp_path,
            ) = tempfile.mkstemp(
                prefix=(
                    f".{self._path.name}."
                ),
                suffix=".tmp",
                dir=str(self._path.parent),
                text=True,
            )

            with os.fdopen(
                file_descriptor,
                "w",
                encoding="utf-8",
                newline="\n",
            ) as stream:
                file_descriptor = None

                json.dump(
                    payload,
                    stream,
                    ensure_ascii=False,
                    indent=2,
                )
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())

            os.replace(
                temp_path,
                self._path,
            )
            temp_path = None

        except Exception as exc:
            raise ReminderRepositoryError(
                "failed to save reminder "
                f"repository: {self._path}"
            ) from exc

        finally:
            if file_descriptor is not None:
                try:
                    os.close(file_descriptor)
                except OSError:
                    pass

            if temp_path is not None:
                try:
                    Path(temp_path).unlink(
                        missing_ok=True
                    )
                except OSError:
                    pass

    def count(self) -> int:
        with self._lock:
            return len(self._records)

    def list_all(
        self,
    ) -> list[ReminderRecord]:
        with self._lock:
            return list(
                self._sorted_locked()
            )

    def get(
        self,
        reminder_id: str,
    ) -> ReminderRecord | None:
        clean_id = str(
            reminder_id or ""
        ).strip()

        if not clean_id:
            return None

        with self._lock:
            return self._records.get(
                clean_id
            )

    def add(
        self,
        *,
        text: str,
        due_at_epoch: float,
        created_at_epoch: (
            float | None
        ) = None,
        reminder_id: str | None = None,
    ) -> ReminderRecord:
        with self._lock:
            clean_id = str(
                reminder_id
                or self._id_factory()
                or ""
            ).strip()

            created_at = (
                self._clock()
                if created_at_epoch is None
                else created_at_epoch
            )

            record = _build_record(
                reminder_id=clean_id,
                text=text,
                due_at_epoch=due_at_epoch,
                created_at_epoch=created_at,
            )

            if (
                record.reminder_id
                in self._records
            ):
                raise ReminderValidationError(
                    "duplicate reminder id: "
                    f"{record.reminder_id}"
                )

            self._records[
                record.reminder_id
            ] = record

            try:
                self._save_locked()
            except Exception:
                self._records.pop(
                    record.reminder_id,
                    None,
                )
                raise

            return record

    def remove(
        self,
        reminder_id: str,
    ) -> ReminderRecord | None:
        clean_id = str(
            reminder_id or ""
        ).strip()

        if not clean_id:
            return None

        with self._lock:
            record = self._records.pop(
                clean_id,
                None,
            )

            if record is None:
                return None

            try:
                self._save_locked()
            except Exception:
                self._records[
                    record.reminder_id
                ] = record
                raise

            return record

    def remove_many(
        self,
        reminder_ids: Iterable[str],
    ) -> list[ReminderRecord]:
        clean_ids = {
            str(value or "").strip()
            for value in reminder_ids
            if str(value or "").strip()
        }

        if not clean_ids:
            return []

        with self._lock:
            removed = [
                record
                for reminder_id, record
                in self._records.items()
                if reminder_id in clean_ids
            ]

            if not removed:
                return []

            for record in removed:
                self._records.pop(
                    record.reminder_id,
                    None,
                )

            try:
                self._save_locked()
            except Exception:
                for record in removed:
                    self._records[
                        record.reminder_id
                    ] = record
                raise

            return sorted(
                removed,
                key=lambda row: (
                    row.due_at_epoch,
                    row.created_at_epoch,
                    row.reminder_id,
                ),
            )

    def latest_created(
        self,
    ) -> ReminderRecord | None:
        with self._lock:
            if not self._records:
                return None

            return max(
                self._records.values(),
                key=lambda row: (
                    row.created_at_epoch,
                    row.reminder_id,
                ),
            )

    def search_text(
        self,
        query: str,
    ) -> list[ReminderRecord]:
        clean_query = _normalize_text(
            query
        ).casefold()

        if not clean_query:
            return []

        with self._lock:
            return [
                row
                for row
                in self._sorted_locked()
                if clean_query
                in row.text.casefold()
            ]