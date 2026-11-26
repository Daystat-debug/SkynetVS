"""Compile checked synthetic events and fit from scratch using only the Python standard library."""
import argparse
from collections import Counter, defaultdict
import gzip
from hashlib import sha256
import itertools
import json
from pathlib import Path
import random
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import skynet_learned_match as match


def event_label(left,right):
    if any(a!=b for a,b in zip(left,right,strict=True) if a is not None and b is not None):
        return "different"
    return "unknown" if None in left or None in right else "equal"


def render(template,wrapper,event,people,items,form):
    a,p,x,b,n = event
    row = []
    for word in template.split():
        if word=="{n}":
            if n:
                row.append(("не","n"))
        elif word=="{x}":
            if x is not None:
                row.append((items[x],"x"))
        elif word.startswith("{"):
            role, case = word[1], int(word[2])
            entity = a if role=="a" else b
            if entity is not None:
                row.append((people[entity][case],role))
        elif word.endswith(":r"):
            row.append((word[:-2],"r"))
        else:
            row.append((word,"o"))
    text = wrapper.format(" ".join(w for w,_ in row))
    prefix, suffix = wrapper.split("{}")
    tags = ["o"]*len(match.words(prefix)) + [t for _,t in row] + ["o"]*len(match.words(suffix))
    assert len(tags)==len(match.words(text))
    return dict(text=text,tags=tags,event=event,predicate=form)


def compile_set(corpus, split):
    rng = random.Random(1901 if split=="train" else 1902)
    groups = []
    for domain, family, names, items in corpus[split]:
        people = [n.split("|") for n in names]
        forms = corpus["forms"][family]
        for a,b in itertools.permutations(range(len(people)),2):
            for p,x,n in itertools.product(range(len(forms)), range(len(items)) if items else [-1], (False,True)):
                event = (a,p,x,b,n)
                def phrase(e,wrap,variant):
                    rel,templates = forms[e[1]]
                    return render(templates[variant],wrap,e,people,items,rel)
                variant = rng.randrange(3)
                missing = list(event)
                missing[rng.choice([3,2] if items else [3])] = None
                for question_event in (event,tuple(missing)):
                    question = phrase(question_event,rng.choice(corpus["wrappers"]),variant)
                    candidates = [event,(b,p,x,a,n),(a,1-p,x,b,n),(a,p,x,b,not n),
                                  (next(i for i in range(len(people)) if i not in (a,b)),p,x,b,n)]
                    if items:
                        candidates.append((a,p,1-x,b,n))
                    # Place the equivalent in varying positions and express competitors in the same style.
                    rng.shuffle(candidates)
                    style = (variant + rng.randint(1,2))%3
                    sources = [phrase(e,"{}",style) for e in candidates]
                    groups.append((domain,question,sources))
    return groups


def fit_tagger(groups):
    labels = match.TAGS
    samples = {}
    aliases = defaultdict(Counter)
    for _,q,rows in groups:
        for entry in [q,*rows]:
            tokens = match.words(entry["text"])
            sample = (tuple(tokens),tuple(entry["tags"]))
            if sample not in samples:
                for token,role in zip(*sample):
                    if role=="r":
                        aliases[token][entry["predicate"]] += 1
                samples[sample] = None
    examples = list(samples)
    rng = random.Random(1911)
    weights = defaultdict(lambda:[0]*len(labels))
    totals = defaultdict(lambda:[0]*len(labels))
    stamps = {}
    step = 0
    for _ in range(5):
        rng.shuffle(examples)
        for tokens,tags in examples:
            prev = "o"
            for i,expected in enumerate(tags):
                step += 1
                keys = match.context(tokens,i,prev)
                selected = match.tag(weights,keys)
                target = labels.index(expected)
                if selected!=target:
                    for key in keys:
                        for k,delta in ((target,1),(selected,-1)):
                            totals[key][k] += (step-stamps.get((key,k),0))*weights[key][k]
                            stamps[key,k] = step
                            weights[key][k] += delta
                prev = labels[selected]
    avg = {key:[round((totals[key][k]+(step-stamps.get((key,k),0))*v)/step,6)
                for k,v in enumerate(row)] for key,row in sorted(weights.items())}
    return avg,{w:c.most_common(1)[0][0] for w,c in sorted(aliases.items()) if len(c)==1}


def fit_head(groups,model,arm):
    cache = {}
    def encode(text):
        if text not in cache:
            cache[text] = match.analyze(text,model) if arm=="learn_roles" else (match.words(text),{})
        return cache[text]
    samples = []
    for _,q,rows in groups:
        for s in rows:
            samples.append((match.features(encode(q["text"]),encode(s["text"]),arm=="learn_roles"),
                            match.LABELS.index(event_label(q["event"],s["event"]))))
    # Inverse class frequencies prevent the generated contrast sets from determining class priors.
    counts = Counter(y for _,y in samples)
    weights = [[0.]*len(samples[0][0]) for _ in match.LABELS]
    rng = random.Random(1912)
    for epoch in range(16):
        rng.shuffle(samples)
        for values,target in samples:
            probs = match.probabilities(weights,values)
            rate = .08/(1+epoch*.2)*len(samples)/(3*counts[target])
            for k,row in enumerate(weights):
                error = rate*((k==target)-probs[k])
                for j,val in enumerate(values):
                    row[j] += error*val
    return [[round(v,7) for v in row] for row in weights]


def calibrate(groups,model,arm):
    records = []
    for _,q,rows in groups:
        _,pred = match.infer(q["text"],[s["text"] for s in rows],model,arm)
        gold = next((i for i,s in enumerate(rows) if event_label(q["event"],s["event"])=="equal"),None)
        records.append((pred,gold))
    best = None
    for threshold,margin in itertools.product((.4,.55,.7,.85),(.03,.12,.25)):
        right = wrong = 0
        for pred,gold in records:
            chosen = match.decide(pred,threshold,margin)
            if chosen is not None:
                right += chosen==gold
                wrong += chosen!=gold
        score = (right-3*wrong,-wrong,right)
        if best is None or score>best[0]:
            best = score,[threshold,margin],dict(right=right,wrong=wrong,groups=len(records))
    return best[1:]


def build():
    path = match.DIR/"experience.json"
    corpus = json.loads(path.read_bytes())
    train,cal = (compile_set(corpus,key) for key in ("train","calibration"))
    def sentences(rows):
        return {e["text"].casefold() for _,q,ss in rows for e in [q,*ss]}
    assert not sentences(train)&sentences(cal)
    assert not {d for d,_,_ in train}&{d for d,_,_ in cal}
    tagger,predicates = fit_tagger(train)
    model = dict(tagger=tagger,predicates=predicates,thresholds={})
    meta = dict(corpus_sha256=sha256(path.read_bytes().replace(b"\r\n",b"\n")).hexdigest(),
                train_groups=len(train),calibration_groups=len(cal),train_pairs=dict(Counter(
                    event_label(q["event"],s["event"]) for _,q,ss in train for s in ss)),calibration={})
    for arm in ("learn_bag","learn_roles"):
        model[arm] = fit_head(train,model,arm)
        model["thresholds"][arm],meta["calibration"][arm] = calibrate(cal,model,arm)
    material = {}
    for split,groups in (("train",train),("calibration",cal)):
        material[split] = [dict(domain=d,query=q,candidates=[
            dict(**s,label=event_label(q["event"],s["event"])) for s in ss]) for d,q,ss in groups]
    return model,meta,material


if __name__=="__main__":
    cli=argparse.ArgumentParser()
    cli.add_argument("mode",choices=("fit","verify"))
    cli.add_argument("--output",type=Path,default=match.DIR)
    args=cli.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    for filename,data in zip(("weights.json","fit.json","compiled.json.gz"),build(),strict=True):
        path=args.output/filename
        encoded=json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n"
        if args.mode=="verify":
            actual = gzip.decompress(path.read_bytes()).decode() if path.suffix==".gz" else path.read_text(encoding="utf8")
            assert actual==encoded,path
        elif path.suffix==".gz":
            with path.open("xb") as f:
                f.write(gzip.compress(encoded.encode(),mtime=0))
        else:
            with path.open("x",encoding="utf8",newline="\n") as f:
                f.write(encoded)
        print(filename,sha256(encoded.encode()).hexdigest())
