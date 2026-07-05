from __future__ import annotations

from typing import Any, Callable, Dict, Optional


VolumeExtractor = Callable[[str], Optional[int]]


def _norm(text: str) -> str:
    return " ".join((text or "").lower().split())


# Команды, которые слишком короткие/системные,
# чтобы полностью доверять ML-классификатору.
EXACT_INTENT_RULES: Dict[str, str] = {
    # stop/listen
    "стоп": "STOP_LISTEN",
    "остановись": "STOP_LISTEN",
    "хватит": "STOP_LISTEN",

    # mute
    "выключи звук": "MUTE",
    "отключи звук": "MUTE",
    "заглуши звук": "MUTE",

    # unmute
    "включи звук": "UNMUTE",
    "верни звук": "UNMUTE",
    "разблокируй звук": "UNMUTE",

    # media controls
    "следующий трек": "MUSIC_NEXT",
    "включи следующий трек": "MUSIC_NEXT",
    "переключи на следующий трек": "MUSIC_NEXT",
    "следующая песня": "MUSIC_NEXT",
    "включи следующую песню": "MUSIC_NEXT",

    "перезапусти музыку": "MUSIC_RESTART",
    "перезапусти трек": "MUSIC_RESTART",
    "начни трек заново": "MUSIC_RESTART",
    "начни музыку заново": "MUSIC_RESTART",
    "включи трек сначала": "MUSIC_RESTART",

    # dictation mode control
    "выключи режим диктовки": "DICTATION_MODE_OFF",
    "закрой режим диктовки": "DICTATION_MODE_OFF",
    "останови диктовку": "DICTATION_MODE_OFF",
    "выключи диктовку": "DICTATION_MODE_OFF",
    "выйди из режима диктовки": "DICTATION_MODE_OFF",
}


# Неполные команды: пользователь начал команду,
# но не сказал объект действия.
INCOMPLETE_COMMAND_STARTERS = {
    "открой",
    "запусти",
    "закрой",
    "найди",
    "поищи",
    "переключи",
    "поставь",
    "установи",
    "включи",
    "выключи",
}


def get_exact_intent(text: str) -> str | None:
    return EXACT_INTENT_RULES.get(_norm(text))


def is_incomplete_command(text: str) -> bool:
    return _norm(text) in INCOMPLETE_COMMAND_STARTERS


def build_incomplete_command_meta(text: str) -> Dict[str, Any] | None:
    if not is_incomplete_command(text):
        return None

    return {
        "intent": None,
        "confidence": 0.0,
        "slots": {},
        "say": "Что именно нужно сделать?",
        "_rule": "incomplete_command_rule",
    }


def build_set_volume_meta(
    text: str,
    *,
    extract_volume: VolumeExtractor,
) -> Dict[str, Any] | None:
    """
    Domain-rule для SET_VOLUME.

    Это не замена модели, а страховка для команд с сильными признаками:
      - есть "громкость" или "звук"
      - есть число 0..100

    Примеры:
      - "громкость 50"
      - "поставь звук на 30"
      - "установи громкость 80"
    """
    t = _norm(text)

    if not any(marker in t for marker in ("громкость", "звук")):
        return None

    # Не перехватываем относительные команды:
    # "сделай громче на 10", "убавь звук на 10".
    # Это позже лучше делать отдельным intent/слотом VOLUME_DELTA.
    relative_markers = (
        "сделай громче",
        "сделай тише",
        "прибавь",
        "добавь",
        "убавь",
        "уменьши",
        "увеличь",
    )

    if any(marker in t for marker in relative_markers) and " до " not in f" {t} ":
        return None

    volume = extract_volume(t)
    if volume is None:
        return None

    return {
        "intent": "SET_VOLUME",
        "confidence": 1.0,
        "slots": {"volume": volume},
        "_rule": "set_volume_rule",
    }