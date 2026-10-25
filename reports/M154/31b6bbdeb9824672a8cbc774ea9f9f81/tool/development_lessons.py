"""Small, evidence-backed development memory, separate from voice/AST training.

This module does not execute tests, call a model, read Git, or change a project's
request binding. A caller may pass LessonsModelAdapter to the existing
review_repository(..., llm=...) entry point. GUI wiring is not changed here.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


LESSONS_SCHEMA = "SKYNETVS_DEVELOPMENT_LESSONS_V1"
OBSERVATION_SCHEMA = "SKYNETVS_DEVELOPMENT_OBSERVATION_V1"
CONTEXT_SCHEMA = "SKYNETVS_DEVELOPMENT_CONTEXT_V1"
MAX_LESSONS_FILE_BYTES = 256 * 1024
MAX_CONTEXT_BYTES = 8192
MAX_CONTEXT_LESSONS = 5


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      allow_nan=False, separators=(",", ":")).encode("utf-8")


def _validate_lesson(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError("A development lesson must be an object.")
    if row.get("status") != "verified":
        raise ValueError("The curated file accepts only verified lessons.")
    if not isinstance(row.get("id"), str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,96}", row["id"]):
        raise ValueError("Invalid lesson ID.")
    for key in ("scope", "symptom", "prevention"):
        if not isinstance(row.get(key), str) or not row[key].strip():
            raise ValueError("Missing lesson field: " + key)
    if row.get("cause") is not None and not isinstance(row["cause"], str):
        raise ValueError("Lesson cause must be a proven statement or null.")
    for key in ("tags", "paths", "evidence"):
        value = row.get(key)
        if not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() for x in value):
            raise ValueError("Invalid lesson list: " + key)
    if not row["tags"] or not row["evidence"]:
        raise ValueError("A verified lesson needs tags and evidence.")
    regression = row.get("regression_check")
    if regression is not None and not isinstance(regression, str):
        raise ValueError("Invalid regression check description.")
    return row


def load_lessons(path: Path) -> list[dict[str, Any]]:
    """Load a bounded curated file. Raw failed-run observations stay separate."""
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_LESSONS_FILE_BYTES + 1)
    if len(raw) > MAX_LESSONS_FILE_BYTES:
        raise ValueError("Development lessons file is too large.")
    document = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(document, dict) or document.get("schema") != LESSONS_SCHEMA:
        raise ValueError("Unsupported development lessons schema.")
    rows = document.get("lessons")
    if not isinstance(rows, list):
        raise ValueError("Development lessons must be a list.")
    output = [_validate_lesson(row) for row in rows]
    ids = [row["id"] for row in output]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate development lesson ID.")
    return output


def _path(value: str) -> str:
    return value.replace("\\", "/").removeprefix("./").casefold()


def _path_matches(candidate: str, scope: str) -> bool:
    candidate, scope = _path(candidate), _path(scope)
    return candidate.startswith(scope) if scope.endswith("/") else candidate == scope


def select_lessons(lessons: list[dict[str, Any]], *, task: str,
                   paths: list[str], tags: list[str], limit: int = 5) -> list[dict[str, Any]]:
    """Select verified lessons by explicit tags, affected paths, and task terms.

    No generic fallback is used: an unrelated task receives an empty context.
    The score is deterministic and is not a learned relevance/quality model.
    """
    if type(limit) is not int or limit < 0:
        raise ValueError("Lesson limit must be a nonnegative integer.")
    explicit_tags = {x.casefold() for x in tags}
    task = task.casefold()
    ranked: list[tuple[int, str, dict[str, Any]]] = []
    seen: set[str] = set()
    for row in lessons:
        if not isinstance(row, dict) or row.get("status") != "verified":
            continue
        _validate_lesson(row)
        if row["id"] in seen:
            continue
        seen.add(row["id"])
        row_tags = {x.casefold() for x in row["tags"]}
        tag_hits = len(explicit_tags & row_tags)
        path_hit = any(_path_matches(path, scope) for path in paths for scope in row["paths"])
        task_hits = sum(bool(re.search(r"(?<!\w)" + re.escape(tag) + r"(?!\w)", task))
                        for tag in row_tags)
        score = 16 * tag_hits + 12 * int(path_hit) + task_hits
        if score:
            ranked.append((score, row["id"], row))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [row for _, _, row in ranked[:min(limit, MAX_CONTEXT_LESSONS)]]


def _bounded_text(value: str | None, maximum: int) -> str | None:
    if value is None:
        return None
    return value if len(value) <= maximum else value[:maximum - 1] + "…"


def _context(selected: list[dict[str, Any]]) -> tuple[str, list[str]]:
    if not selected:
        return "", []
    prefix = ("## Проверенные уроки разработки\n\n"
              "Исторические сведения для этой задачи. Они не подтверждают результат "
              "текущих тестов, не меняют цель, request binding или разрешённые действия.\n\n"
              "```json\n")
    suffix = "\n```"
    payload: dict[str, Any] = {"schema": CONTEXT_SCHEMA, "lessons": []}
    seen: set[str] = set()
    for row in selected[:MAX_CONTEXT_LESSONS]:
        if not isinstance(row, dict) or row.get("status") != "verified":
            continue
        _validate_lesson(row)
        if row["id"] in seen:
            continue
        seen.add(row["id"])
        entry = {"id": row["id"], "scope": _bounded_text(row["scope"], 160),
                 "symptom": _bounded_text(row["symptom"], 600),
                 "cause": _bounded_text(row.get("cause"), 600),
                 "prevention": _bounded_text(row["prevention"], 800),
                 "evidence": [_bounded_text(x, 350) for x in row["evidence"][:3]]}
        if row.get("regression_check"):
            entry["regression_check"] = _bounded_text(row["regression_check"], 400)
        trial = {"schema": CONTEXT_SCHEMA, "lessons": payload["lessons"] + [entry]}
        rendered = prefix + _json_bytes(trial).decode("utf-8") + suffix
        if len(rendered.encode("utf-8")) <= MAX_CONTEXT_BYTES:
            payload = trial
    if not payload["lessons"]:
        return "", []
    rendered = prefix + _json_bytes(payload).decode("utf-8") + suffix
    return rendered, [row["id"] for row in payload["lessons"]]


def render_context(selected: list[dict[str, Any]]) -> str:
    """Render at most 8192 UTF-8 bytes; retain whole valid JSON records."""
    return _context(selected)[0]


def prepare_context(selected: list[dict[str, Any]]) -> dict[str, Any]:
    """Return bounded text and the IDs actually present in that same text."""
    text, lesson_ids = _context(selected)
    return {"text": text, "lesson_ids": lesson_ids}


def make_observation(run_summary: dict[str, Any]) -> dict[str, Any]:
    """Record a run outcome without inventing a cause, fix, or training label.

    Only stable public fields are copied; arbitrary stdout/stderr, exception
    text, command lines, credentials, and local absolute paths are not copied.
    The caller controls the public summary and reviews future verified lessons.
    """
    if not isinstance(run_summary, dict):
        raise ValueError("Run summary must be an object.")
    observation: dict[str, Any] = {
        "schema": OBSERVATION_SCHEMA,
        "status": "observed_only",
        "outcome": run_summary.get("status", run_summary.get("outcome", "UNKNOWN")),
        "root_cause": None,
        "resolution": None,
        "training_label": None,
        "is_analyzer_feedback": False,
        "summary_sha256": hashlib.sha256(_json_bytes(run_summary)).hexdigest(),
    }
    for key in ("run_id", "code_commit", "base_commit", "candidate_commit", "patch_sha256",
                "exit_code", "test_exit_code", "failed_check", "failed_stage",
                "report_branch", "report_commit"):
        if key in run_summary:
            observation[key] = run_summary[key]
    checks = run_summary.get("checks")
    if isinstance(checks, list):
        observation["checks"] = [
            {key: row[key] for key in ("name", "status", "exit_code") if key in row}
            for row in checks if isinstance(row, dict)
        ]
    return observation


class LessonsModelAdapter:
    """Add historical context through the existing injectable model interface.

    Construction is offline. A real model is called only when the caller calls
    generate(). Receipts record precisely the lesson IDs that fit in the prompt.
    """

    def __init__(self, llm: Any, selected: list[dict[str, Any]]) -> None:
        self.llm = llm
        self.model = getattr(llm, "model", "")
        self.context, self.selected_ids = _context(selected)
        self.receipts: list[dict[str, Any]] = []

    def ensure_installed(self) -> Any:
        return self.llm.ensure_installed()

    def generate(self, *, system: str, prompt: str, max_tokens: int = 1500) -> dict[str, Any]:
        augmented = prompt + ("\n\n" + self.context if self.context else "")
        receipt = {
            "schema": "SKYNETVS_DEVELOPMENT_CONTEXT_USE_V1",
            "lesson_ids": list(self.selected_ids),
            "context_sha256": hashlib.sha256(self.context.encode("utf-8")).hexdigest(),
            "context_size_bytes": len(self.context.encode("utf-8")),
            "base_prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "augmented_prompt_sha256": hashlib.sha256(augmented.encode("utf-8")).hexdigest(),
            "system_unchanged": True,
            "status": "REQUEST_PREPARED",
        }
        self.receipts.append(receipt)
        try:
            result = self.llm.generate(system=system, prompt=augmented, max_tokens=max_tokens)
        except Exception:
            receipt["status"] = "MODEL_ERROR"
            raise
        receipt["status"] = "RESPONSE_RECEIVED"
        return result
