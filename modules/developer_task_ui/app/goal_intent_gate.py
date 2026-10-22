"""M147 conservative task-intent boundary for the context -> DTR-A shortcut.

Only user-visible routing: no source reads, model inference, patch generation,
OS commands, Git access or authorization. Never grants apply rights.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

READ_ONLY = "READ_ONLY"
CHANGE_EXPLICIT = "CHANGE_EXPLICIT"
AMBIGUOUS = "AMBIGUOUS"

# Require an imperative edit request. Infinitives such as "как исправить"
# do not create authorization to prepare a patch request.
_EDIT = re.compile(
    r"\b(?:исправь|почини|измени|поменяй|добавь|реализуй|удали|замени|"
    r"переименуй|перепиши|отрефактори|рефакторни|внеси\s+правк\w*|"
    r"fix|change|modify|implement|add|remove|delete|rename|replace|refactor|"
    r"update|patch)\b", re.IGNORECASE)
_READ = re.compile(
    r"\b(?:найди|покажи|объясни|проанализируй|исследуй|расскажи|"
    r"опиши|где|разбери|проверь|оцени|сравни|"
    r"find|locate|show|explain|analy[sz]e|investigate|describe|where|review)\b",
    re.IGNORECASE)
_NO_EDIT = re.compile(
    r"(?:\bне\s+(?:надо\s+)?(?:исправляй|меняй|изменяй|трогай|удаляй|"
    r"добавляй|вноси|переписывай|применяй|правь)\b|"
    r"\b(?:без\s+(?:изменени\w*|правок)|никаких\s+правок|"
    r"только\s+(?:найди|объясни|анализ|чтение)|только\s+для\s+чтения)\b|"
    r"\b(?:do\s+not|don't|never)\s+(?:change|edit|modify|fix|apply|"
    r"remove|add|patch)\b|\b(?:without\s+(?:changes|editing|modifications)|"
    r"no\s+(?:edits|changes)|read[- ]only)\b)", re.IGNORECASE)
_HOW = re.compile(
    r"(?:\b(?:объясни|покажи|расскажи|опиши)\b.{0,90}\bкак\b.{0,90}\b"
    r"(?:исправить|изменить|добавить|реализовать|починить|удалить)\b|"
    r"\b(?:explain|show|describe)\b.{0,90}\bhow\s+to\s+"
    r"(?:fix|change|modify|add|implement|remove)\b)", re.IGNORECASE)
# Distinguishes a specific requested behavioral change from "найди и исправь".
_DETAIL = re.compile(
    r"(?:\b(?:чтобы|если|когда|при\s+условии|вместо|должен|должна|"
    r"в\s+функции|в\s+методе|для\s+случая|когда|when|if|so\s+that|"
    r"instead\s+of|in\s+function)\b|"
    r"[A-Za-z_][A-Za-z0-9_]*\.(?:py|json)\b|"
    r"\b[A-Za-z_][A-Za-z0-9_]*_[A-Za-z0-9_]+\b)", re.IGNORECASE)


@dataclass(frozen=True)
class GoalDecision:
    kind: str
    reason: str


def classify_goal(goal: str) -> GoalDecision:
    """Fail closed: permission to *prepare DTR-A*, never permission to apply.

    Deterministic lexical guard, not a general-purpose NLU model. An explicit
    imperative with a specific change signal may enter the existing DTR-A
    manual-selection workflow; other text stays in read-only search or is refused.
    """
    if (not isinstance(goal, str) or len(goal) > 1200 or
            not goal.strip() or len(goal.encode("utf-8", "surrogatepass")) > 2500 or
            any(ord(c) < 32 and c not in "\r\n\t" for c in goal) or
            any(0xD800 <= ord(c) <= 0xDFFF for c in goal)):
        return GoalDecision(AMBIGUOUS, "INVALID_OR_EMPTY_GOAL")
    text = " ".join(goal.split()).casefold()
    negated = bool(_NO_EDIT.search(text))
    # Negated edit words are not affirmative edit requests on their own.
    positive_text = _NO_EDIT.sub(" ", text)
    edit = bool(_EDIT.search(positive_text))
    read = bool(_READ.search(text))
    how = bool(_HOW.search(text))
    if how and not _EDIT.search(_HOW.sub(" ", positive_text)):
        return GoalDecision(READ_ONLY, "EXPLANATION_ONLY")
    if negated:
        if edit:
            return GoalDecision(AMBIGUOUS, "CONFLICTING_EDIT_INSTRUCTIONS")
        if read or how:
            return GoalDecision(READ_ONLY, "EDIT_EXPLICITLY_DISALLOWED")
        return GoalDecision(AMBIGUOUS, "EDIT_DISALLOWED_WITHOUT_ANALYSIS_GOAL")
    if edit:
        # Mixed search+edit needs an actual change specification, not a vague
        # request to "find and fix" an unspecified problem.
        if read and not re.search(r"\b(?:чтобы|если|когда|вместо|when|if|so\s+that|instead\s+of)\b", text):
            return GoalDecision(AMBIGUOUS, "SEARCH_AND_EDIT_UNSPECIFIED")
        meaningful = re.findall(r"\w+", text, re.UNICODE)
        if len(meaningful) < 4 or not _DETAIL.search(text):
            return GoalDecision(AMBIGUOUS, "CHANGE_NOT_SPECIFIC_ENOUGH")
        return GoalDecision(CHANGE_EXPLICIT, "SPECIFIC_EDIT_REQUEST")
    if read:
        return GoalDecision(READ_ONLY, "ANALYSIS_REQUEST")
    return GoalDecision(AMBIGUOUS, "NO_EXPLICIT_MODE")
