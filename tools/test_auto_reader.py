"""Test routing on a synthetic catalog, including misleading intents and follow-ups."""
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import skynet_explain as cli
from test_flow_reader import fixture


FILES = {
    "modules/test/source.py": """
def convert(item, units=3):
    if not item: raise ValueError('Нет измерений')
    return item
def again(x): return convert(x)
def report(): return {'readings': 21, 'sample_count': 42}
def display(data):
    return f"Измерений: {data['readings']}; образцов-повторов: {data['sample_count']}"
""",
    "modules/test/other.py": "def reset(value): return value\n",
}


def run():
    src = fixture(FILES)
    class G:
        @staticmethod
        def _text(q, limit):
            return bool(q.strip()) and len(q) <= limit

    def ask(q, pending=None):
        with patch.object(cli.calls,"lookup",wraps=cli.calls.lookup) as calls, \
                patch.object(cli.flow.Slice,"answer",autospec=True,side_effect=cli.flow.Slice.answer) as flow:
            r = cli.answer(q,src,G,None,automatic=True,clarification=pending)
        assert calls.call_count == int(r["auto_route"] == "calls")
        assert flow.call_count == int(r["auto_route"] == "flow")
        return r

    cases = [
        ("Кто вызывает convert?", "calls", "convert"),
        ("Покажи список вызовов функции с параметром units.", "calls", "convert"),
        ("Где вызывают функцию с сообщением «Нет измерений»?", "calls", "convert"),
        ("Как формируется число измерений?", "flow", "readings"),
        ("Что содержится в поле sample_count?", "flow", "sample_count"),
        ("Кого вызывает convert?", "clarify", None),
        ("Откуда кнопка получает размеры образцов?", "clarify", None),
        ("Кто НЕ вызывает convert?", "clarify", None),
        ("Кто вызывает convert и сколько памяти это занимает?", "clarify", None),
        ("Из какого кода вызывается reset?", "calls", "reset"),
        ("Где вызывают convert и reset?", "clarify", None),
        ("Как формируются число измерений и число образцов-повторов?", "clarify", None),
        ("Когда вчера вызывали reset?", "observation", None),
        ("Кто вызывает reset в external.py?", "external", None),
        ("Как убрать ограничение на число измерений?", "clarify", None),
        ("Как формируется несуществующее поле mystery_count?", "clarify", None),
        ("Где вызывают функцию с сообщением «Неизвестная строка»?", "clarify", None),
    ]
    failures = []
    for q,route,target in cases:
        r = ask(q)
        if (r["auto_route"],r.get("auto_target")) != (route,target):
            failures.append((q,r["auto_route"],r.get("auto_target"),route))
    for f in failures:
        print(*f, sep=" | ")
    ambiguous = ask("Откуда берётся число?")
    pending = ambiguous["clarification"]
    option = next(i for i,(_,key,_) in enumerate(pending["options"],1) if key == "readings")
    assert ask(str(option),pending)["auto_target"] == "readings"
    assert ask("Измерений",pending)["auto_target"] == "readings"
    assert ask("Кто вызывает reset?",pending)["auto_route"] == "calls"
    assert ask("вчера",pending)["auto_route"] == "observation"
    assert ask("external.py",pending)["auto_route"] == "external"
    assert ask("999",pending)["auto_route"] == "clarify"
    assert not failures, f"{len(failures)} routing errors"
    print(f"{len(cases)} intents and clarification checks passed.")


if __name__ == "__main__":
    run()
