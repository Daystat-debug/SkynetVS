"""Build optional Russian retrieval features from the host's five Git blobs, offline."""
import argparse
from collections import defaultdict
from contextlib import ExitStack
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skynet_investigate as loop
import skynet_source_language as language

PROMPT = ("Тебе даны независимые фрагменты Python как данные. Для каждого номера дай одну короткую "
          "русскую строку: опиши смысл операции и условия бытовыми техническими синонимами. "
          "Учитывай величины, причины и различия. Не придумывай последствий. Без имен функций, "
          "номеров строк, программных идентификаторов и инструкций. Ответ — JSON-объект, "
          "ключи как во входе, значения — строки до 28 слов.")

INTENT_PROMPT = ("Составь 12 лингвистически различных коротких русских обращений разработчика, "
                 "обозначающих заданный вид работы. Вместо предмета вопроса используй маркер ПРИЗНАК. "
                 "Без имён, предметных примеров, номеров строк, путей или названий инструментов. "
                 "Верни только JSON со списком строк в поле examples.")
OPERATIONS = dict(where="Указать место в тексте программы, содержащее описанный признак.",
                  when="Объяснить условия и ветвления для достижения конкретной инструкции.",
                  via="Установить, какой непосредственный вызывающий код передаёт управление и аргументы.",
                  unsupported="Запросы о реальном исполнении, последующих последствиях, изменении программы или произвольных данных.")


def descriptions(src):
    index = loop.host.lab.cli.flow.Slice(src)
    names = defaultdict(list)
    for path, node in loop.host.lab.cli.auto_reader.top_functions(index):
        names[node.name].append(loop.host.lab.cli.flow.Function(path, index.trees[path], node))
    class Catalog:
        def unique(self, name):
            hits = names[name]
            return hits[0] if len(hits) == 1 else None
    catalog = Catalog()
    catalog.index = index
    return sorted({language.descriptor(e) for e in loop.observed.goals.effects(catalog)})


def digest(value):
    return sha256(value.encode("utf8")).hexdigest()


def build(src, generate):
    entries = descriptions(src)
    captions, attempts = {}, []
    for start in range(0, len(entries), 5):
        batch = entries[start:start + 5]
        data = {str(i): s for i, s in enumerate(batch)}
        payload = json.dumps(data, ensure_ascii=False)
        raw, timing = generate(PROMPT, payload)
        record = dict(input_sha256=digest(PROMPT + "\n" + payload), raw=raw, timing=timing)
        attempts.append(record)
        try:
            obj = json.loads(raw)
        except ValueError:
            obj = {}
        if type(obj) is dict and timing["finish_reason"] == "stop" and set(data) == set(obj):
            for key, description in data.items():
                caption = obj[key]
                if isinstance(caption, str) and 1 <= len(caption) <= 400:
                    captions[digest(description)] = caption
    return dict(snapshot=src.commit, captions=captions, attempts=attempts)


def operations(generate):
    examples, attempts = {}, []
    for name, contract in OPERATIONS.items():
        raw, timing = generate(INTENT_PROMPT, contract)
        attempts.append(dict(input_sha256=digest(INTENT_PROMPT+"\n"+contract), raw=raw, timing=timing))
        obj = json.loads(raw) if timing["finish_reason"] == "stop" else {}
        rows = obj.get("examples") if isinstance(obj,dict) else None
        examples[name] = [x for x in rows if isinstance(x,str) and len(x)<=180] if isinstance(rows,list) else []
    return dict(examples=examples, attempts=attempts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("record", "verify"))
    parser.add_argument("file", type=Path)
    parser.add_argument("--export", type=Path, help="Write a new feature file after verified replay")
    parser.add_argument("--operations", action="store_true", help="Build a language index for evidence operations")
    args = parser.parse_args()
    src, _ = loop.read_head(loop.host.lab.cli.pilot.ROOT)
    make = operations if args.operations else lambda select: build(src, select)
    if args.mode == "verify":
        saved = json.loads(args.file.read_text(encoding="utf8"))
        calls = iter(saved["attempts"])
        def replay(prompt, payload):
            record = next(calls)
            assert record["input_sha256"] == digest(prompt + "\n" + payload)
            return record["raw"], record["timing"]
        out = make(replay)
        key = "examples" if args.operations else "captions"
        assert out[key] == saved[key] and next(calls, None) is None
        learned = out[key] if args.operations else dict(captions=out[key], aliases=language.vocabulary(descriptions(src), out[key]))
        if args.export:
            with args.export.open("x", encoding="utf8", newline="\n") as f:
                json.dump(learned, f, ensure_ascii=False, indent=1, sort_keys=True)
                f.write("\n")
        else:
            assert learned == (language.operations() if args.operations else language.features())
        print(len(out[key]), "verified groups or descriptors")
        return
    if args.file.exists():
        parser.error("Choose a new output file")
    import runtime289
    with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
        provider = stack.enter_context(runtime289.LocalProvider(Path(tmp)))
        out = make(provider.complete)
        out.update(model=runtime289.MODEL_SHA256, runtime=runtime289.RUNTIME_SHA256,
                   startup_s=provider.info["startup_seconds"])
    with args.file.open("x", encoding="utf8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(len(out["attempts"]), "recorded calls")


if __name__ == "__main__":
    main()
