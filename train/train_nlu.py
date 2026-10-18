from __future__ import annotations

import json
import hashlib
import re
from pathlib import Path
from typing import List, Dict, Tuple

import joblib
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV


INTENTS_PATH = Path("data/intents.json")
OUT_MODEL_PATH = Path("models/nlu_intent.joblib")
FIT_RECIPE_PATH = Path("data/nlu_training_recipe.json")


def _load_dataset(path: Path) -> Tuple[List[str], List[str], Dict[str, int]]:
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    intents = data.get("intents") or []

    X: List[str] = []
    y: List[str] = []

    seen: set[tuple[str, str]] = set()
    duplicate_count = 0
    skipped_empty_count = 0

    for item in intents:
        intent = str(item.get("intent") or "").strip().upper()
        examples = item.get("examples") or []

        if not intent or not isinstance(examples, list):
            continue

        for ex in examples:
            s = str(ex or "").strip().lower()

            if not s:
                skipped_empty_count += 1
                continue

            key = (intent, s)
            if key in seen:
                duplicate_count += 1
                continue

            seen.add(key)
            X.append(s)
            y.append(intent)

    if not X:
        raise ValueError("Dataset is empty: no examples found")

    stats = {
        "duplicate_count": duplicate_count,
        "skipped_empty_count": skipped_empty_count,
    }

    return X, y, stats


def _unique_json_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("NLU_RECIPE_DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _apply_fit_recipe(X: List[str], y: List[str], recipe_path: Path) -> int:
    """Apply bounded fit-only weights to examples already present in intents.json.

    Never invent new commands or labels: records reference existing examples by
    normalized-text SHA-256. Missing/changed recipes fail closed, rather than
    silently retraining a model with different class boundaries.
    """
    if not recipe_path.is_file() or recipe_path.is_symlink():
        raise ValueError("NLU_RECIPE_REQUIRED")
    raw = recipe_path.read_bytes()
    if not (1 <= len(raw) <= 16384):
        raise ValueError("NLU_RECIPE_SIZE_INVALID")
    doc = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_json_pairs)
    if not isinstance(doc, dict) or set(doc) != {"schema", "weights"}:
        raise ValueError("NLU_RECIPE_SCHEMA_INVALID")
    if doc["schema"] != "SKYNETVS_NLU_FIT_WEIGHTS_V1":
        raise ValueError("NLU_RECIPE_SCHEMA_VERSION_UNKNOWN")
    weights = doc["weights"]
    if not isinstance(weights, list) or not (1 <= len(weights) <= 64):
        raise ValueError("NLU_RECIPE_WEIGHTS_INVALID")
    if len(X) != len(y):
        raise ValueError("NLU_RECIPE_DATASET_MISMATCH")
    original = list(zip(X, y))
    records = set()
    extra_X, extra_y = [], []
    for item in weights:
        if not isinstance(item, dict) or set(item) != {"intent", "normalized_text_sha256", "fit_repeats"}:
            raise ValueError("NLU_RECIPE_WEIGHT_FIELDS_INVALID")
        label, digest, repetitions = (item["intent"], item["normalized_text_sha256"], item["fit_repeats"])
        if not isinstance(label, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{1,79}", label):
            raise ValueError("NLU_RECIPE_INVALID_INTENT")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("NLU_RECIPE_INVALID_SHA256")
        if type(repetitions) is not int or not (2 <= repetitions <= 8):
            raise ValueError("NLU_RECIPE_INVALID_REPEATS")
        key = (label, digest)
        if key in records:
            raise ValueError("NLU_RECIPE_DUPLICATE_WEIGHT")
        records.add(key)
        matches = [(text, old_label) for text, old_label in original
                   if hashlib.sha256(text.encode("utf-8")).hexdigest() == digest]
        if len(matches) != 1 or matches[0][1] != label:
            raise ValueError("NLU_RECIPE_EXAMPLE_NOT_UNIQUE_OR_CONFLICTING")
        extra_X.extend([matches[0][0]] * (repetitions - 1))
        extra_y.extend([label] * (repetitions - 1))
    if len(extra_X) > 256:
        raise ValueError("NLU_RECIPE_TOTAL_WEIGHT_EXCEEDED")
    X.extend(extra_X)
    y.extend(extra_y)
    return len(extra_X)


def train() -> Pipeline:
    X, y, stats = _load_dataset(INTENTS_PATH)
    weighted_extra = _apply_fit_recipe(X, y, FIT_RECIPE_PATH)

    # LinearSVC хорошо работает на маленьких датасетах, но не умеет predict_proba.
    # Поэтому заворачиваем в CalibratedClassifierCV, чтобы получить "confidence".
    base = LinearSVC(class_weight="balanced", random_state=42)
    clf = CalibratedClassifierCV(base, method="sigmoid", cv=3)

    pipe: Pipeline = Pipeline(
        steps=[
            # Символьные n-gram дают заметный буст на командах (RU/EN) и опечатках
            ("tfidf", TfidfVectorizer(
                analyzer="char_wb",
                ngram_range=(3, 5),
                min_df=1,
                lowercase=True,
            )),
            ("clf", clf),
        ]
    )

    pipe.fit(X, y)

    OUT_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, OUT_MODEL_PATH)

    print(f"[OK] trained on {len(X)} samples (fit-only extra={weighted_extra})")
    print(f"[OK] skipped duplicate examples: {stats['duplicate_count']}")
    print(f"[OK] skipped empty examples: {stats['skipped_empty_count']}")
    print(f"[OK] saved model: {OUT_MODEL_PATH}")
    return pipe


def quick_test(pipe: Pipeline) -> None:
    tests = [
        # базовые
        "привет",
        "скайнет привет",
        "открой блокнот",
        "запусти калькулятор",
        "какая погода",
        "сделай скриншот",
        "стоп",
        "закрой режим",
        "что ты умеешь",

        # звук
        "сделай громче",
        "прибавь звук",
        "увеличь громкость",
        "сделай тише",
        "убавь звук",
        "уменьши громкость",
        "выключи звук",
        "отключи звук",
        "включи звук",
        "верни звук",
        "поставь звук на 30",
        "громкость 50",
        "звук на 10",
        "установи громкость 80",
        "прибавь громкость",
        "сделай звук потише",

        # hardening
        "сними экран",
        "сделай скрин",
        "приостанови музыку",
        "включи следующий трек",
        "перезапусти трек",
        "закрой режим ввода текста",
        "нажми клавишу enter",
        "нажми клавишу tab",
        "сделай отступ",

        # dictation separation
        "режим диктовки",
        "режим ввода текста",
        "включи диктовку",
        "запусти режим диктовки",
        "активируй режим диктовки",
        "включи голосовой ввод",
        "начни ввод текста голосом",
        "отключи диктовку",
        "выключи голосовой ввод",
        "останови голосовой ввод",
        "заверши ввод текста голосом",

        # backspace separation
        "нажми бэкспейс",
        "нажми бэк спейс",
        "нажми бэк спайс",
        "нажми клавишу backspace",
        "нажми клавишу бэкспейс",
        "нажми клавишу бэк спайс",
        "сотри символ",
        "удали предыдущий символ",
        "сотри последний символ",

        # system health
        "состояние системы",
        "проверь сервисы",
        "покажи текущий статус системы",
        "есть ли сейчас проблемы с сервисами",
        ]

    print("\n[TEST] predictions:")
    for t in tests:
        pred = pipe.predict([t.lower()])[0]
        conf = None
        if hasattr(pipe, "predict_proba"):
            proba = pipe.predict_proba([t.lower()])[0]
            conf = float(proba.max())
        if conf is None:
            print(f"  '{t}' -> {pred}")
        else:
            print(f"  '{t}' -> {pred} (conf={conf:.2f})")


if __name__ == "__main__":
    model = train()
    quick_test(model)
