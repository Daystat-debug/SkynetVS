"""Run one preregistered arm against a detached copy of the same Git snapshot."""
import json
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_skynet_explain import Trace, cli, pilot, verify

FREEZE = "7da41f76ea20db22b9e7d576b19b6dc97b1861ce"
CONTROL = "docs/maintenance/explanation_quality/control.json"


class Recording(Trace):
    def complete(self, system, user):
        self.write("input", case=self.case, system_text=system, user_text=user)
        return super().complete(system, user)


def oracle_prompt(case, aliases, src):
    lines, shown = [case["q"]], {}
    for alias, ranges in case["context"].items():
        path = aliases[alias]
        lines.append("Файл " + path)
        original = src.snapshot.sources[path].splitlines()
        for start, end in ranges:
            for n in range(start, end + 1):
                if n in src.pages[path]:
                    key = f"{alias}:{n}"
                    shown[key] = path, n
                    lines.append(f"{key} {original[n-1]}")
    return "\n".join(lines), shown


def run(group, arm, output):
    assert group in {"oracle", "cli"} and arm in {"baseline", "reviewed"}
    control = json.loads(pilot.git("show", FREEZE + ":" + CONTROL))
    source = control["source"]
    with tempfile.TemporaryDirectory() as temp, output.open("x", encoding="utf8", newline="\n") as stream:
        repo = Path(temp) / "repo"
        pilot.git("clone", "--quiet", "--local", "--no-checkout", str(pilot.ROOT), str(repo))
        pilot.git("checkout", "--quiet", "--detach", source, cwd=repo)
        trace = Recording(stream, len(control[group]) * (1 if arm == "baseline" else 2))
        with cli.local_reader(repo) as (src, ground, provider):
            trace.provider = provider
            trace.write("setup", freeze=FREEZE, source=src.commit, blobs=src.oids, group=group, arm=arm)
            assert src.commit == source
            for case in control[group]:
                trace.case = case["id"]
                q = case["q"]
                before = time.perf_counter()
                if group == "oracle":
                    user, shown = oracle_prompt(case, control["aliases"], src)
                    if arm == "baseline":
                        raw, timing = trace.complete(cli.windows.ANSWER, user)
                        try:
                            result = cli.publish(raw, src, shown, ground) if timing["finish_reason"] == "stop" else cli.refusal("invalid")
                        except (ValueError, KeyError, TypeError, RecursionError):
                            result = cli.refusal("invalid")
                    else:
                        result = cli.reviewed_context(q, shown, src, ground, trace)
                else:
                    fn = cli.baseline_answer if arm == "baseline" else cli.answer
                    result = fn(q, src, ground, trace)
                elapsed = round(time.perf_counter() - before, 3)
                verify(result, src.commit, src.raw)
                trace.write("result", case=trace.case, seconds=elapsed, result=result)
                print(trace.case, result["status"], elapsed, flush=True)
            info = provider.p.info if provider.p else {}
        assert trace.count == info.get("requests", 0) and info.get("stopped", True)
        trace.write("done", calls=trace.count, session=info)


if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2], Path(sys.argv[3]))
