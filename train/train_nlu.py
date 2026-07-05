from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Tuple

import joblib
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV


INTENTS_PATH = Path("data/intents.json")
OUT_MODEL_PATH = Path("models/nlu_intent.joblib")


def _load_dataset(path: Path) -> Tuple[List[str], List[str]]:
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    intents = data.get("intents") or []

    X: List[str] = []
    y: List[str] = []

    for item in intents:
        intent = str(item.get("intent") or "").strip()
        examples = item.get("examples") or []
        if not intent or not isinstance(examples, list):
            continue
        for ex in examples:
            s = str(ex or "").strip().lower()
            if s:
                X.append(s)
                y.append(intent)

    if not X:
        raise ValueError("Dataset is empty: no examples found")

    return X, y


def train() -> Pipeline:
    X, y = _load_dataset(INTENTS_PATH)

    # LinearSVC хорошо работает на маленьких датасетах, но не умеет predict_proba.
    # Поэтому заворачиваем в CalibratedClassifierCV, чтобы получить "confidence".
    base = LinearSVC(class_weight="balanced")
    clf = CalibratedClassifierCV(base, method="sigmoid", cv=3)

    pipe: Pipeline = Pipeline(
        steps=[
            # Символьные n-gram дают заметный буст на командах (RU/EN) и опечатках
            ("tfidf", TfidfVectorizer(
                analyzer="char_wb",
                ngram_range=(3, 5),
                min_df = 1,
                lowercase = True,
            )),
            ("clf", clf),
        ]
    )

    pipe.fit(X, y)

    OUT_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, OUT_MODEL_PATH)

    print(f"[OK] trained on {len(X)} samples")
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
