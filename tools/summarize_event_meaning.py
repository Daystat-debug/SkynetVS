"""Post-measurement audit of the recorded experiment. Does not rerun or change any decisions."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_event_meaning as lab


def audit(panel, data):
    diagnostics = data["diagnostics"]
    by_id = {r["id"]: r for r in data["rows"]}
    cases = []
    for d in diagnostics["questions"]:
        row = by_id[d["id"]]
        arm = row["event_vocab"]
        x = next(x for x in arm["identity"] if x["cue"]==d["cue"])
        record = x["hypothesis"]
        query = record["query_frame"]
        domain = d["source_domain"]
        closed = diagnostics["sources"][domain]["frames"]
        manual = {k:lab.meaning.decode(v) for k,v in panel["cards"][domain].items()}
        arms = {}
        for name,q,events in (("vocabulary_closed",query,closed),
                              ("vocabulary_known_sources",query,manual),
                              ("bag_known_both",d["reference"],manual)):
            chosen,why,comparison = lab.meaning.decide(q,events,unordered=name=="bag_known_both")
            arms[name] = dict(chosen=chosen,why=why,comparison=comparison)
        covers = [int(k) for k,v in record["comparison"].items() if v=="covers"]
        gold = x["gold"]
        cases.append(dict(id=d["id"],cue=d["cue"],target=d["gold"],gold=gold,
                          extraction=record["extraction"],query=query,
                          fields=lab.semantics(query,d["reference"],panel["aliases"]),
                          exact_covers_in_actual_pool=covers, unreadable=list(k for k,v in
                          record["comparison"].items() if v=="unreadable"), full_decision=record["why"],
                          isolated=arms))
    m = {}
    for label in cases[0]["isolated"]:
        choices = [(c["target"],c["isolated"][label]["chosen"]) for c in cases]
        m[label] = dict(positive=sum(t==v for t,v in choices), negative=sum(t=="-" and v is None for t,v in choices),
                        wrong=sum(v is not None and t!=v for t,v in choices))
    all_sources = [x["hypothesis"] for r in by_id.values() for x in r["event_vocab"]["identity"]
                   if "extraction" in x["hypothesis"]]
    first_pass_equal = sum(data["generations"][r["event_vocab"]["calls"][0]]["raw"]==
                           data["generations"][r["event_meaning"]["calls"][1]]["raw"]
                           for r in by_id.values() if r["event_vocab"]["calls"])
    return dict(frozen_experiment=data["panel_blob"],questions=cases,closed_metrics=m,
                vocabulary_questions_exact=sum(all(c["fields"]) for c in cases),
                identical_source_replies=first_pass_equal,
                source_extraction=dict(Counter(s["extraction"][1] for s in all_sources)))


if __name__=="__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("mode",choices=("write","verify"))
    mode = cli.parse_args().mode
    panel = lab.load(lab.DIR/"transfer.json")
    raw = json.loads(gzip.decompress((lab.DIR/"transfer_trace.json.gz").read_bytes()))
    result = audit(panel,raw)
    lab.artifact(lab.DIR/"delivery_audit.json",result,mode=="write")
    print(result["closed_metrics"],result["vocabulary_questions_exact"],result["identical_source_replies"])
