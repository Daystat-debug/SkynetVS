"""Optional four-generation comparison on frozen public questions. No tools given to Qwen."""
import json
from pathlib import Path
import sys
import tempfile
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skynet_investigate as loop

pilot = loop.host.lab.cli.pilot
DIR = "docs/maintenance/core_01"
PROMPT = """Определи намерение пользователя. Доступны статический путь между функциями (path),
непосредственный вызывающий (calls), происхождение поля (flow) и уточнение (clarify).
Верни только объект JSON с полями route и names. Для path names содержит имена из вопроса
в порядке от вызывающего к вызываемому. Для calls — одно имя из вопроса. Для flow и
clarify — пустой массив. Не отвечай на вопрос и не предлагай команды."""


def main():
    dest = Path(sys.argv[1])
    plan = json.loads(pilot.git("show", "cd3a230:" + DIR + "/controls.json"))
    truth = {"A": ("path", ["search_repository", "extract_symbols"]),
             "B": ("path", ["module_rank", "modules_from_source"]),
             "J": ("calls", ["expand_query"]), "K": ("flow", [])}
    loop.host._runtime()  # verify original package and install the existing Windows job
    import runtime289 as runtime
    with dest.open("x", encoding="utf8") as output, tempfile.TemporaryDirectory() as temp:
        start = perf_counter()
        with runtime.LocalProvider(Path(temp)) as model:
            startup_ms = round((perf_counter() - start) * 1000)
            rows = []
            for case in (c for c in plan["tasks"] if c["id"] in truth):
                route, names = truth[case["id"]]
                question = case["question"]
                start = perf_counter()
                raw, timing = model.complete(PROMPT, question)
                ms = round((perf_counter() - start) * 1000)
                try:
                    obj = loop.host.lab.cli.strict(raw)
                except ValueError:
                    obj = {}
                correct = timing["finish_reason"] == "stop" and obj == dict(route=route, names=names)
                begin = perf_counter()
                parsed = loop.endpoints(question)
                if parsed:
                    rule = dict(route="path", names=list(parsed))
                else:
                    result = loop.supervised(question)
                    action, = result["steps"]
                    rule = dict(route=action["tool"], names=[action["target"]] if action["tool"] == "calls" else [])
                rows.append(dict(case=case["id"], qwen_correct=correct, model_ms=ms,
                                 deterministic_correct=rule == dict(route=route, names=names),
                                 deterministic_ms=round(1000*(perf_counter()-begin)),
                                 finish=timing["finish_reason"]))
            assert model.calls == 4
        json.dump(dict(rows=rows, generations=model.calls, startup_ms=startup_ms,
                       model_sha256=runtime.MODEL_SHA256, runtime_sha256=runtime.RUNTIME_SHA256,
                       stopped=model.info["stopped"]), output, indent=2)
        output.write("\n")


if __name__ == "__main__":
    main()
