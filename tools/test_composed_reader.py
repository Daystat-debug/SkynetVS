"""Check end-to-end composition against controlled, static data dependencies."""
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import skynet_explain as cli
from test_flow_reader import fixture


class Ground:
    @staticmethod
    def _text(q, limit):
        return bool(q.strip()) and len(q) <= limit


def run():
    producer = "def collect(v):\n    return {'score': 17}\n"
    reader = ("from .a import collect as get\n"
              "def report():\n    ignored = get(4); data = get(9)\n"
              "    return {'final_score': data['score'], 'enabled_flag': True}\n"
              "def screen(report):\n    return f\"Баллов: {report['final_score']}\"\n")

    def ask(q, source=reader, pending=None):
        src = fixture({"modules/p/a.py":producer,"modules/p/b.py":source})
        return cli.answer(q,src,Ground,None,composed=True,clarification=pending)

    query = "Кто вызывает collect, куда записывает результат и откуда берётся поле final_score?"
    r = ask(query)
    assert [s["tool"] for s in r["actions"]] == ["calls","flow"] and len(r["relations"]) == 1
    selected = [c["text"] for c in r["claims"] if "участвует" in c["text"]]
    assert len(selected) == 1 and "`data`" in selected[0] and "`ignored`" not in selected[0]
    assert r["relations"][0]["site"]["column"] == reader.splitlines()[2].rindex("get")
    assert all(c["evidence_blocks"] for c in r["claims"])
    other = ask("Откуда берётся поле enabled_flag? Кто вызывает collect?")
    assert other["relations"] == [] and "не установлена" in other["text"]
    assert [s["tool"] for s in other["actions"]] == ["flow","calls"]
    assert len(ask("Кто вызывает collect, какие параметры передаёт и куда уходит ответ?")["actions"]) == 1
    unclear = ask("Кто вызывает collect и откуда берётся значение?")
    assert unclear["auto_route"] == "clarify"
    continued = ask("Баллов",pending=unclear["clarification"])
    assert continued["relations"] == r["relations"]
    for q, route in [("Кто вызывает collect в main.py и как появляется final_score?","external"),
                     ("Кто вызывает collect и сколько раз запускали вчера?","observation"),
                     ("Кто вызывает collect и предложи оптимизацию.","clarify")]:
        assert ask(q)["auto_route"] == route
    changed = reader.replace("data = get(9)", "data = get(9); data['score'] = 555")
    modified = ask(query,changed)
    assert not modified["relations"], "stale provenance after same-line overwrite"
    # A quoted diagnostic with punctuation must remain one selector.
    marked = producer.replace("return", "if not v: raise ValueError('Ошибка, и что?')\n    return")
    src = fixture({"modules/p/a.py":marked,"modules/p/b.py":reader})
    quoted = cli.answer("Где вызывают функцию с сообщением «Ошибка, и что?» и как формируется final_score?",
                        src,Ground,None,composed=True)
    assert quoted["relations"] == r["relations"] and quoted["selection_evidence"]
    print("Composition, exact call identity, boundaries, follow-up and distinct operations verified.")


if __name__ == "__main__":
    run()
