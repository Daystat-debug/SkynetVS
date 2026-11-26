"""One clarification, two terminal host tasks at most. The host owns the five-file source."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import re
import sys
from time import monotonic

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skynet_gap_choice as choice
import skynet_investigate as loop

goals = loop.requirements.goals
OPS = {"site":"Где записано", "condition":"При каком условии возникает",
       "caller":"Кто вызывает функцию с сообщением", "arguments":"Какие аргументы переданы функции с сообщением"}
KINDS = ["место в коде", "условие", "вызывающая функция", "переданные аргументы"]


def classify(part, cards):
    kind = part.get("relation", {}).get("kind")
    binding = part["binding"]
    issues = set(part["issues"])
    if kind in ("runtime", "external") or issues & {"observation_required","runtime","external"}:
        return "unavailable_information"
    quotes = goals.quoted(part["text"])
    if not binding["object"]:
        if len(quotes) == 1:
            hits = sum(quotes[0].casefold() in card[0].casefold() for card in cards)
            return "absent_catalog_literal" if hits == 0 else "intent_ambiguity" if hits > 1 else "interpretation_gap"
        return "interpretation_gap"
    other = {"where":"site","when":"condition"}.get(goals.action(part["text"]))
    if (kind not in OPS and kind != "caller_condition") or (other and other != kind):
        return "requirement_gap"
    if part["status"] != "established":
        return "missing_evidence"
    return None


class Dialogue:
    def __init__(self, root, style="contrast"):
        if style not in ("contrast","list"):
            raise ValueError("unknown prompt style")
        self.root, self.style = root, style
        self.first = None
        self.pending = None
        self.used = False
        self.cards = ()
        self.pools = {}

    def catalog(self, cards, pools):
        self.cards, self.pools = cards, pools

    def view(self, raw):
        parts = []
        for part in raw.get("parts", []):
            gap = classify(part, self.cards)
            direct = part.get("relation", {}).get("direct", [])
            ids = part["claims"] if gap in (None,"missing_evidence") else []
            parts.append(dict(text=part["text"], kind=part.get("relation",{}).get("kind"),
                              object=part["binding"]["object"], gap=gap,
                              issues=part["issues"], claims=[raw["claims"][i] for i in ids],
                              direct=[raw["claims"][i] for i in ids if i in direct]))
        state = raw["state"]
        if parts and any(p["gap"] for p in parts):
            state = "partial" if any(p["claims"] for p in parts) else "insufficient"
        return dict(state=state, snapshot=raw.get("snapshot"), parts=parts, reason=raw.get("reason"),
                    steps=len(raw["steps"]))

    def question(self, result):
        for i, part in enumerate(result["parts"]):
            gap = part["gap"]
            text = part["text"]
            if gap == "requirement_gap":
                obj = part["object"]
                labels = [c[0] for c in self.cards if c[1:] == (obj["owner"],obj["path"],obj["line"])]
                if len(labels) != 1:
                    continue
                prompt = "Какое сведение требуется о «" + labels[0] + "»?"
                return dict(part=i, axis="requirement", prompt=prompt, options=KINDS, pool=[], label=labels[0])
            if gap not in ("intent_ambiguity","interpretation_gap"):
                continue
            quotes = goals.quoted(text)
            if len(quotes) == 1:
                ids = [j for j,c in enumerate(self.cards) if quotes[0].casefold() in c[0].casefold()][:16]
            else:
                ids = choice.candidates(text, self.cards, self.pools.get(i, ()), goals.terms)
            if not ids:
                continue
            shown = ids
            if self.style == "contrast":
                # Ask about the closest contrast to the leading hypothesis, leaving the
                # whole menu available to a free-text correction.
                first = set(goals.terms(self.cards[ids[0]][0]))
                def overlap(j):
                    terms = set(goals.terms(self.cards[j][0]))
                    return len(terms & first) / max(1, len(terms | first))
                rival = max(ids[1:],key=overlap,default=None)
                shown = [ids[0]] + ([rival] if rival is not None else [])
            labels = [self.cards[j][0] for j in shown]
            prompt = "Какой объект вы имели в виду?"
            options = labels
            if self.style == "contrast":
                options = choice.difference(labels)
                prompt = "Для части «" + text.strip() + "» какой вариант описывает нужное событие? Если оба не подходят, назовите отличительный признак."
                if len(set(options)) < len(options):
                    options = [s+" ("+self.cards[j][1]+")" for s,j in zip(options,shown)]
            return dict(part=i, axis="object", prompt=prompt, options=options, pool=ids, shown=shown)
        return None

    def start(self, question):
        if self.first is not None:
            raise ValueError("dialogue_already_started")
        self.original = question
        start = monotonic()
        raw = loop.investigate(question,self.root,discovery="dialog_ground",checked_catalog=self.catalog)
        self.first = self.view(raw)
        if raw["state"] in ("answered","partial","insufficient") and self.cards:
            self.pending = self.question(self.first)
        if monotonic()-start >= loop.TIME_LIMIT:
            self.pending = None
            self.first = dict(state="failed",reason="deadline",parts=[],steps=self.first["steps"],snapshot=None)
        return deepcopy(self.first), self.public_prompt()

    def public_prompt(self):
        if not self.pending:
            return None
        return deepcopy({k:self.pending[k] for k in ("part","axis","prompt","options")})

    def resume(self, reply):
        if self.used or not self.pending:
            raise ValueError("no_pending_clarification")
        self.used = True
        start = monotonic()
        steps = 0
        def finish(result, reason):
            loop.head_current(src)
            if monotonic()-start >= loop.TIME_LIMIT:
                raise loop.host.Rejected("deadline")
            return deepcopy(result), reason, steps
        try:
            src, ground = loop.read_head(self.root)
            loop.head_current(src)
            if src.commit != self.first["snapshot"]:
                raise loop.host.Rejected("stale_snapshot")
            for part in self.first["parts"]:
                for claim in part["claims"]:
                    for ref in claim["refs"]:
                        loop.host.checked_item(src, ref)
            req = self.pending
            if not ground._text(reply, 300) or loop.host.lab.cli.PY_PATH.search(reply):
                return finish(self.first,"invalid_reply")
            if reply.strip().casefold() in ("ни один","не знаю","ни один из вариантов"):
                return finish(self.first,"unresolved_reply")
            selection = re.fullmatch(r"#([1-9][0-9]?)",reply.strip())
            index = int(selection[1])-1 if selection else None
            if index is not None and index >= len(req["options"]):
                return finish(self.first,"invalid_choice")
            part = self.first["parts"][req["part"]]
            if req["axis"] == "requirement":
                if index is None:
                    index = choice.resolve_reply(reply, KINDS)
                if index is None:
                    return finish(self.first,"unresolved_reply")
                label = req["label"]
                clause = list(OPS.values())[index]
            else:
                if index is None:
                    labels = [self.cards[j][0] for j in req["pool"]]
                    match = choice.resolve_reply(reply, labels)
                    if match is None:
                        return finish(self.first,"unresolved_reply")
                    candidate = req["pool"][match]
                else:
                    candidate = req["shown"][index]
                label = self.cards[candidate][0]
                clause = goals.QUOTES.sub("",part["text"]).strip().rstrip(".?!;")
            # Only host-owned source text can become a locator. Avoid introducing syntax
            # or a substring which could ground a different expression in the old analyzer.
            if (re.search('[«»"“”\r\n]', label) or
                    sum(label.casefold() in c[0].casefold() for c in self.cards) != 1):
                return finish(self.first,"nonunique_locator")
            span = loop.task_parts.split(self.original)[req["part"]]
            q = self.original[:span["start"]] + clause + " «" + label + "»? " + self.original[span["end"]:].lstrip()
            if not ground._text(q.strip(),600):
                return finish(self.first,"question_budget")
            new = loop.investigate(q.strip(),self.root,opener=lambda _: (src,ground),discovery="dialog_ground")
            steps = len(new["steps"])
            if new["state"] in ("failed","cancelled"):
                raise loop.host.Rejected(new.get("reason","failed"))
            result = self.view(new)
            return finish(result, "explicit_choice" if selection else "interpreted_reply")
        except loop.host.Rejected as exc:
            return dict(state="failed",reason=str(exc),parts=[],snapshot=None,steps=steps),str(exc),steps
        except (OSError,ValueError):
            return dict(state="failed",reason="snapshot_unavailable",parts=[],snapshot=None,steps=steps),"snapshot_unavailable",steps


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--reply",help="Текст уточнения или #номер из показанных вариантов")
    parser.add_argument("--interactive",action="store_true")
    args = parser.parse_args()
    dialog = Dialogue(loop.host.lab.cli.pilot.ROOT)
    answer, prompt = dialog.start(args.question)
    print(json.dumps(answer, ensure_ascii=False, indent=2))
    if prompt:
        print(prompt["prompt"])
        for n, option in enumerate(prompt["options"], 1):
            print(f"#{n} {option}")
        reply = args.reply if args.reply is not None else input("> ") if args.interactive else None
        if reply is not None:
            answer, reason, _ = dialog.resume(reply)
            print(reason, json.dumps(answer,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
