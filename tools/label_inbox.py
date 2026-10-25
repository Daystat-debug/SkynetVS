# tools/label_inbox.py
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple

if __package__ in (None, ""):
    # Preserve the documented direct invocation: python tools/label_inbox.py.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.learning.intent_examples import add_example

INTENTS_PATH = Path("data/intents.json")
INBOX_PATH = Path("data/inbox_unlabeled.jsonl")
OUTBOX_PATH = Path("data/inbox_labeled.jsonl")  # сюда будем складывать обработанные


def load_intents() -> Dict[str, Any]:
    if not INTENTS_PATH.exists():
        raise FileNotFoundError(f"Missing {INTENTS_PATH}")
    return json.loads(INTENTS_PATH.read_text(encoding="utf-8"))


def save_intents(data: Dict[str, Any]) -> None:
    INTENTS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def list_intent_names(data: Dict[str, Any]) -> List[str]:
    intents = data.get("intents") or []
    names = []
    for it in intents:
        name = str(it.get("intent") or "").strip()
        if name:
            names.append(name)
    return sorted(set(names))


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                # пропускаем битые строки
                continue
    return out


def write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main() -> None:
    intents_data = load_intents()
    intent_names = list_intent_names(intents_data)

    inbox = read_jsonl(INBOX_PATH)
    if not inbox:
        print(f"[OK] inbox empty: {INBOX_PATH}")
        return

    outbox = read_jsonl(OUTBOX_PATH)

    # чтобы не размечать повторно: считаем уже обработанные
    processed_keys = set()
    for r in outbox:
        k = (str(r.get("text") or "").strip().lower(), str((r.get("meta") or {}).get("intent") or ""))
        processed_keys.add(k)

    pending: List[Dict[str, Any]] = []
    for r in inbox:
        text = str(r.get("text") or "").strip()
        if not text:
            continue
        meta = r.get("meta") or {}
        # ключ по тексту (intent мог быть None)
        k = (text.lower(), str(meta.get("intent") or ""))
        if k in processed_keys:
            continue
        pending.append(r)

    if not pending:
        print("[OK] nothing new to label")
        return

    print(f"[INFO] intents: {', '.join(intent_names)}")
    print(f"[INFO] pending: {len(pending)}")
    print("Команды: число=выбрать intent, 's'=skip, 'q'=quit\n")

    while pending:
        r = pending.pop(0)
        text = str(r.get("text") or "").strip()
        meta = r.get("meta") or {}
        conf = meta.get("confidence")

        print("-" * 60)
        print(f"TEXT: {text}")
        if conf is not None:
            try:
                print(f"NLU conf: {float(conf):.2f}")
            except Exception:
                pass

        # показать список интентов с номерами
        for i, name in enumerate(intent_names, start=1):
            print(f"  {i}) {name}")

        ans = input("Выбери intent (номер) / s / q: ").strip().lower()
        if ans == "q":
            pending.insert(0, r)
            break
        if ans == "s" or ans == "":
            # skip тоже сохраняем, чтобы не спамило одним и тем же (по желанию можно убрать)
            outbox.append({"text": text, "meta": meta, "label": None})
            continue

        try:
            idx = int(ans) - 1
            if idx < 0 or idx >= len(intent_names):
                raise ValueError()
            chosen = intent_names[idx]
        except Exception:
            print("[WARN] invalid choice, skipping")
            outbox.append({"text": text, "meta": meta, "label": None})
            continue

        added = add_example(intents_data, chosen, text)
        outbox.append({"text": text, "meta": meta, "label": chosen, "added": bool(added)})

        if added:
            print(f"[OK] added example -> {chosen}")
        else:
            print(f"[OK] already exists -> {chosen}")

    save_intents(intents_data)
    write_jsonl(OUTBOX_PATH, outbox)
    print(f"\n[OK] intents updated: {INTENTS_PATH}")
    print(f"[OK] labeled saved:   {OUTBOX_PATH}")
    print("\nДальше: python train/train_nlu.py")


if __name__ == "__main__":
    main()
