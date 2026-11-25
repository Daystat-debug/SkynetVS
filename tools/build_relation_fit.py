"""Rebuild the relation readout from immutable historical material; never open the 0.14 controls."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_object_binding as historical
import skynet_relation as relation

BASE = "98f76735805544f08c938c1a4f0dbd3ed8ec3157"


def read(path):
    return json.loads(historical.prev.ev.pilot.git("show", BASE + ":" + path))


def samples(name):
    panel = read("docs/maintenance/core_13/" + name + ".json")
    result = []
    for key, q, demands in panel["cases"]:
        spans = historical.parts.split(q)
        grouped = [[] for _ in spans]
        for cue, target, kind in demands:
            kind = panel.get("oracle_overrides", {}).get(key + "/" + cue, kind)
            grouped[historical.place(q, cue, spans)].append((target, kind))
        for span, labels in zip(spans, grouped):
            if len(labels) != 1:
                continue
            target, kind = labels[0]
            obj = panel["targets"][target][3] if target != "-" else ""
            text = relation.wording(span["text"], obj)
            if len(text) > 3:
                result.append((text, kind))
    return result


def build():
    seed = read("tools/skynet_obligation_memory.json")["examples"]
    examples = sorted(set((relation.wording(t), k) for t, k in seed) | set(samples("transfer")))
    known = {t for t, _ in examples}
    calibration = sorted(set((t, k) for t, k in samples("confirmation") if t not in known))
    model = relation.Classifier(examples)
    cutoffs = {}
    for policy in relation.POLICIES:
        scored = [(model.predict(t, policy == "relation_nearest"), k) for t, k in calibration]
        def utility(pair):
            floor, margin = pair
            # Mistaking the type of answer costs twice the benefit of a correct decision.
            return sum((1 if k == label else -2) for (k, s, m), label in scored if s >= floor and m >= margin)
        candidates = [(s, m) for s in (.10, .20, .30, .40) for m in (0., .04, .08, .12)]
        cutoffs[policy] = max(candidates, key=utility)
    return dict(base=BASE, examples=examples, calibration_size=len(calibration), cutoffs=cutoffs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    options = parser.parse_args()
    artifact = json.dumps(build(), ensure_ascii=False, indent=1) + "\n"
    if options.verify:
        assert relation.MODEL.read_text(encoding="utf8") == artifact
    else:
        with relation.MODEL.open("x", encoding="utf8", newline="\n") as stream:
            stream.write(artifact)
    print("Historical fit reproduced:", relation.MODEL.name)
