"""Test the coordinator with in-memory ports and no Git, tool modules or model."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skynet_core_task import Task


def run():
    task = Task("Откуда берётся число?", "fixture")
    assert task.state == "accepted"
    steps = []

    def retrieve(req):
        steps.append("read")
        return dict(task_id=req.task_id,source_id=req.source_id,snapshot_id="fixture",coverage="partial",
                    gaps=[],items=[dict(ref_id="R",text="count = 2",locator={"line":1})])

    def propose(req, e):
        steps.append("propose")
        assert task.state == "running"
        e["items"][0]["text"] = "provider copy"
        return dict(status="answer",claims=[dict(text="Число задано литералом.",anchors=[{"ref_id":"R","lines":[1,1]}])])

    def verify(req, e, proposal, delivered):
        steps.append("check")
        assert e["items"][0]["text"] == "count = 2" and delivered == ["R"]
        return {"references":"checked"}

    result = task.run(retrieve,propose,verify)
    assert steps == ["read","propose","check"] and result["state"] == task.state == "answered"
    assert task.run(None,None,None) is result and not task.cancel(task.request.task_id)
    empty = Task("Другая задача", "fixture")
    def none(req):
        return dict(retrieve(req),items=[],gaps=["no_match"])
    result = empty.run(none,None,lambda *args: {"references":"none"})
    assert result["state"] == "insufficient" and result["delivered_ref_ids"] == []
    assert "skynet_scope_lab" not in sys.modules
    print("In-memory answer, immutable handoff, empty evidence, single terminal decision verified.")


if __name__ == "__main__":
    run()
