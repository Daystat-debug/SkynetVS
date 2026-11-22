"""Replay frozen questions and inject publication faults without executing analyzed source."""
from copy import deepcopy
import json
from pathlib import Path
import sys
from threading import Event, Thread
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skynet_core_explain as app
import skynet_core_task as core

LOCK = "f68ce89b699f5e97890d389abddfc6dd0d286f8b"
DIR = "docs/maintenance/core_tool_adapter"
pilot = app.lab.cli.pilot


def questions(host, plan):
    results = []
    ids = set()
    for case in plan["cases"]:
        task = host.task(case["q"])
        result = host.run(task)
        assert result["state"] == case["state"], case["id"]
        e, p = result["evidence_set"], result["answer_proposal"]
        assert task.request.task_id == e["task_id"] and task.request.task_id not in ids
        ids.add(e["task_id"])
        assert e["snapshot_id"] == plan["source_commit"] and e["source_id"] == app.SOURCE_ID
        analysis = e["analysis"]
        items = {i["ref_id"]:i for i in e["items"]}
        assert list(items) == result["delivered_ref_ids"] and len(items) == len(e["items"])
        for item in items.values():
            ref = item["locator"]
            assert ref["path"] in app.lab.SCOPE and ref["commit"] == plan["source_commit"]
            raw = pilot.git("cat-file", "blob", ref["commit"] + ":" + ref["path"])
            text = b"".join(raw.splitlines(keepends=True)[ref["start"]-1:ref["end"]])
            assert text.decode("utf8") == item["text"] and pilot.sha(text) == ref["excerpt_sha256"]
            assert pilot.git("rev-parse", ref["commit"] + ":" + ref["path"]).decode().strip() == ref["blob_oid"]
        if "tools" in case:
            assert case["tools"] == [a["tool"] for a in analysis["actions"]]
        if case["state"] == "answered":
            assert p["status"] == "answer" and p["claims"]
            assert all(a["ref_id"] in items for c in p["claims"] for a in c["anchors"])
        else:
            assert p == {"status":"insufficient", "claims":[], "reason":case["reason"]}
        facts = p["claims"] if p["status"] == "answer" else analysis["observations"]
        assert all(word in " ".join(c["text"] for c in facts) for word in case.get("facts", []))
        if "edge" in case:
            edge, = analysis["relations"]
            assert [edge["function"],edge["field"]] == case["edge"]
            assert set(edge["supports"].values()) <= items.keys()
        if "contexts" in case:
            assert sorted(o["call_site"]["kind"] for o in facts_with_sites(analysis)) == sorted(case["contexts"])
        assert result["assessment"]["execution_observed"] is False
        results.append(dict(id=case["id"], result=result))
    return results


def facts_with_sites(analysis):
    return [o for o in analysis["observations"] if "call_site" in o]


def faults(host, q):
    rows = []
    unexpected = []

    def record(name, result, state, reason=None):
        assert result["state"] == state and result.get("reason") == reason, (name,result["state"])
        if state in ("failed","cancelled"):
            assert "answer_proposal" not in result and "evidence_set" not in result
        rows.append(dict(case=name, state=state, stage=result["stage"], reason=reason))

    def forbidden(*args):
        unexpected.append(True)
        raise AssertionError("Unexpected dependency call")

    unsupported = app.Host(opener=forbidden)
    record("unsupported_source", unsupported.run(unsupported.task(q, source_id="../main.py")),
           "failed", "unsupported_source")
    t = host.task(q)
    assert not t.cancel("other-task") and t.cancel(t.request.task_id)
    record("cancel_before_read", t.run(forbidden,forbidden,forbidden), "cancelled", "cancelled")

    real_ask = app.lab.ask
    def corrupt_ref(*args):
        result = real_ask(*args)
        result["claims"][0]["evidence_blocks"][0]["url"] += "?forged"
        return result
    with patch.object(app.lab, "ask", corrupt_ref):
        t = host.task(q)
        record("forged_git_url", t.run(host.retrieve, forbidden, host.verify), "failed", "invalid_reference")

    def switch_anchor(req, e):
        draft = app.propose(req, e)
        draft["claims"][0]["anchors"] = draft["claims"][1]["anchors"]
        return draft
    record("genuine_wrong_claim_anchor", host.task(q).run(host.retrieve,switch_anchor,host.verify),
           "failed", "claim_binding")

    def unknown_ref(req, e):
        draft = app.propose(req, e)
        draft["claims"][0]["anchors"][0]["ref_id"] = "unissued"
        return draft
    record("unissued_reference", host.task(q).run(host.retrieve,unknown_ref,host.verify), "failed", "invalid_anchor")

    entered, resume = Event(), Event()
    def delayed(req, e):
        entered.set()
        assert resume.wait(5)
        return app.propose(req, e)
    t = host.task(q)
    worker = Thread(target=t.run, args=(host.retrieve,delayed,forbidden))
    worker.start()
    try:
        assert entered.wait(5) and t.state == "running" and t.cancel(t.request.task_id)
    finally:
        resume.set()
        worker.join(5)
    assert not worker.is_alive() and not t.cancel(t.request.task_id)
    record("cancel_during_provider", t.result, "cancelled", "cancelled")

    clock = [0]
    def expired(*args):
        assessment = host.verify(*args)
        clock[0] = 100
        return assessment
    with patch.object(core, "monotonic", lambda:clock[0]):
        record("deadline_before_publication", host.task(q).run(host.retrieve,app.propose,expired),
               "failed", "deadline")

    retained = []
    def keep(req, e):
        draft = app.propose(req, e)
        retained.append(draft)
        return draft
    def mutate_after_check(*args):
        assessment = host.verify(*args)
        retained[0]["claims"][0]["text"] = "CONTROL_MUTATION"
        return assessment
    t = host.task(q)
    result = t.run(host.retrieve, keep, mutate_after_check)
    record("detached_provider_result", result, "answered")
    assert result["answer_proposal"]["claims"][0]["text"] != "CONTROL_MUTATION"
    assert not t.cancel(t.request.task_id)
    assert not unexpected
    return rows


def replay_key(report):
    copy = deepcopy(report)
    for row in copy["questions"]:
        for key in ("task_request","evidence_set"):
            row["result"][key]["task_id"] = "<host-generated>"
    return copy


def main(mode):
    plan = json.loads(pilot.git("show", LOCK + ":" + DIR + "/questions.json"))
    host = app.Host()
    rows = questions(host, plan)
    controls = faults(host, plan["cases"][1]["q"])
    # A separately bound three-file deployment cannot escalate on a question about M126.
    src, ground = host.session
    restricted = app.Host(baseline=True, opener=lambda _: (src,ground))
    bad = restricted.run(restricted.task(plan["cases"][1]["q"]))
    assert bad["state"] == "failed" and bad["reason"] == "snapshot_policy"
    controls.append(dict(case="unexpected_expanded_profile",state=bad["state"],stage=bad["stage"],reason=bad["reason"]))
    restricted = app.Host(baseline=True)
    limited = restricted.run(restricted.task(plan["cases"][1]["q"]))
    assert limited["state"] == "insufficient" and set(limited["evidence_set"]["analysis"]["allowed_paths"]) == app.lab.BASE
    controls.append(dict(case="three_file_host",state=limited["state"],stage=limited["stage"],
                         reason=limited["answer_proposal"]["reason"]))
    report = dict(protocol=LOCK, source=app.lab.SOURCE, questions=rows, controls=controls, model_generations=0)
    path = pilot.ROOT / DIR / "results.json"
    if mode == "record":
        pilot.dump(path, report)
    else:
        assert replay_key(report) == replay_key(json.loads(path.read_text(encoding="utf8")))
    for row in rows:
        r = row["result"]
        print(row["id"],r["state"],r["answer_proposal"].get("reason",""),len(r["delivered_ref_ids"]))
    print(len(controls), "publication, access and cancellation controls passed")


if __name__ == "__main__":
    if sys.argv[1:] not in (["record"], ["verify"]):
        sys.exit("Expected record or verify")
    main(sys.argv[1])
