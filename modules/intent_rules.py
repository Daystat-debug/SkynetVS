from __future__ import annotations

from typing import Any, Callable, Dict, Optional


VolumeExtractor = Callable[[str], Optional[int]]

DurationExtractor = Callable[[str], Optional[int]]


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

    # dictation mode on
    "режим диктовки": "DICTATION_MODE_ON",
    "включи режим диктовки": "DICTATION_MODE_ON",
    "начни диктовку": "DICTATION_MODE_ON",
    "режим ввода текста": "DICTATION_MODE_ON",
    "включи режим ввода текста": "DICTATION_MODE_ON",
    "включи печать голосом": "DICTATION_MODE_ON",

    # dictation mode off
    "выключи режим диктовки": "DICTATION_MODE_OFF",
    "закрой режим диктовки": "DICTATION_MODE_OFF",
    "останови диктовку": "DICTATION_MODE_OFF",
    "выключи диктовку": "DICTATION_MODE_OFF",
    "выйди из режима диктовки": "DICTATION_MODE_OFF",
    "прекрати печать": "DICTATION_MODE_OFF",
    "останови печать": "DICTATION_MODE_OFF",
    "выйди из режима ввода текста": "DICTATION_MODE_OFF",
    "выключи режим ввода текста": "DICTATION_MODE_OFF",
    "заверши диктовку": "DICTATION_MODE_OFF",
    "закрой режим ввода текста": "DICTATION_MODE_OFF",
    "останови режим диктовки": "DICTATION_MODE_OFF",
    "заверши режим диктовки": "DICTATION_MODE_OFF",
    "заверши режим ввода текста": "DICTATION_MODE_OFF",
    "останови режим ввода текста": "DICTATION_MODE_OFF",

    # keyboard / editor controls
    "нажми enter": "PRESS_ENTER",
    "нажми энтер": "PRESS_ENTER",
    "enter": "PRESS_ENTER",
    "энтер": "PRESS_ENTER",
    "ввод": "PRESS_ENTER",
    "новая строка": "PRESS_ENTER",
    "перенос строки": "PRESS_ENTER",

    "нажми backspace": "PRESS_BACKSPACE",
    "нажми бэкспейс": "PRESS_BACKSPACE",
    "нажми бэк спейс": "PRESS_BACKSPACE",
    "нажми бэк спэйс": "PRESS_BACKSPACE",
    "нажми бэк спайс": "PRESS_BACKSPACE",
    "удали символ": "PRESS_BACKSPACE",
    "стереть символ": "PRESS_BACKSPACE",
    "удали последнюю букву": "PRESS_BACKSPACE",
    "сотри последнюю букву": "PRESS_BACKSPACE",

    "нажми tab": "PRESS_TAB",
    "нажми таб": "PRESS_TAB",
    "таб": "PRESS_TAB",
    "вставь таб": "PRESS_TAB",

    # volume relative controls
    "сделай громче": "VOLUME_UP",
    "громче": "VOLUME_UP",
    "прибавь звук": "VOLUME_UP",
    "добавь громкости": "VOLUME_UP",
    "увеличь громкость": "VOLUME_UP",
    "добавь звука": "VOLUME_UP",
    "громкость вверх": "VOLUME_UP",

    "сделай тише": "VOLUME_DOWN",
    "тише": "VOLUME_DOWN",
    "убавь звук": "VOLUME_DOWN",
    "уменьши громкость": "VOLUME_DOWN",
    "громкость вниз": "VOLUME_DOWN",
    "сделай звук тише": "VOLUME_DOWN",

    # timer set without duration:
    # intent распознан, но command_decision заблокирует
    # выполнение из-за отсутствующего duration_seconds.
    "поставь таймер": "SET_TIMER",
    "установи таймер": "SET_TIMER",
    "запусти таймер": "SET_TIMER",

    # timer status
    "сколько осталось на таймере": "TIMER_STATUS",
    "сколько осталось до конца таймера": "TIMER_STATUS",
    "сколько времени осталось на таймере": "TIMER_STATUS",
    "покажи таймер": "TIMER_STATUS",
    "статус таймера": "TIMER_STATUS",

    # timer cancel
    "отмени таймер": "CANCEL_TIMER",
    "останови таймер": "CANCEL_TIMER",
    "выключи таймер": "CANCEL_TIMER",
    "сбрось таймер": "CANCEL_TIMER",
    "удали таймер": "CANCEL_TIMER",
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
    "громкость",
    "звук",
    "таймер",
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


def build_set_timer_meta(
    text: str,
    *,
    extract_duration: DurationExtractor,
) -> Dict[str, Any] | None:
    """
    Детерминированное правило SET_TIMER.

    Примеры:
      - поставь таймер на 30 секунд
      - таймер на 5 минут
      - запусти таймер на 1 час 20 минут
    """
    t = _norm(text)

    if "таймер" not in t:
        return None

    # Эти команды принадлежат другим timer-intents.
    forbidden_markers = (
        "сколько осталось",
        "сколько времени",
        "статус таймера",
        "покажи таймер",
        "отмени таймер",
        "останови таймер",
        "выключи таймер",
        "сбрось таймер",
        "удали таймер",
    )

    if any(marker in t for marker in forbidden_markers):
        return None

    duration_seconds = extract_duration(t)

    if duration_seconds is None:
        return None

    return {
        "intent": "SET_TIMER",
        "confidence": 1.0,
        "slots": {
            "duration_seconds": duration_seconds,
        },
        "_rule": "set_timer_rule",
    }