"""Controlled tests of the CLI's scope, Git identity, line selection and publication."""
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skynet_explain as cli


def run():
    cli.pilot.verify_package()
    import ground289 as g
    import retrieval284 as ret
    core = ret.original("m254_core")
    p = sorted(ret.SCOPE)[0]
    raw = b"def sample():\n    return 807\n"
    oid = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()

    class Reader:
        head = "a" * 40
        body = raw

        def _sha(self, *args):
            return self.head

        def _run(self, cmd, *args, **kwargs):
            if cmd == "ls-tree":
                return f"100644 blob {oid}\t{p}\0".encode()
            return str(len(raw)).encode() if args[0] == "-s" else self.body

    class Fixed:
        def __init__(self, response):
            self.response = response

        def complete(self, system, user):
            return json.dumps(self.response), {"finish_reason":"stop"}

    reader = Reader()
    src = cli.GitSources(reader,core,{p})
    assert src.pages[p] == {1:"def sample():",2:"return 807"}
    reply = {"quotes":[[999,"return 807"]],"fact":"Проверить возвращённое значение","missing":""}
    picked, hint, _ = cli.select(Fixed(reply),"Что вернётся?",p,src.pages[p])
    assert picked == [2] and hint
    reply["quotes"] = [[2,"return 987"]]
    assert not cli.select(Fixed(reply),"Что вернётся?",p,src.pages[p])[0]
    user, shown = cli.pack("Что вернётся?",src.pages,{p:picked},{p:hint})
    assert len((cli.EXPLAIN + user).encode()) <= 3584
    active = {"claims":[{"text":"Возвращается 807.","lines":["A:2"]}]}
    out = cli.publish(json.dumps(active),src,shown,g)
    assert out["claims"][0]["anchors"][0]["url"].endswith(f"/{reader.head}/{p}#L2")
    active["claims"][0]["lines"] = ["B:2"]
    try:
        cli.publish(json.dumps(active),src,shown,g)
    except KeyError:
        pass
    else:
        raise AssertionError("fabricated line accepted")
    assert cli.answer("Что в main.py?",src,g,None)["reason"] == "external"
    reader.head = "b" * 40
    try:
        src.current()
    except ValueError as exc:
        assert str(exc) == "HEAD_CHANGED_RESTART"
    else:
        raise AssertionError("stale HEAD accepted")
    reader.body = b"x" * len(raw)
    try:
        cli.GitSources(reader,core,{p})
    except ValueError as exc:
        assert str(exc) == "SOURCE_BLOB"
    else:
        raise AssertionError("forged blob accepted")
    assert len(g.selftest_details()) == 15
    print("Scope, blob, stale HEAD, literal selection, byte budget, verified links and 15 grounding checks passed.")


if __name__ == "__main__":
    run()
