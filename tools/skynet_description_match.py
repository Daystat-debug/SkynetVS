"""Lab-only sequence interpretation and three-way comparison with explicit witnesses."""
from functools import lru_cache
import json
from pathlib import Path

import skynet_learned_match as old

DIR = old.DIR.parent / "core_20"
ROLES = ("a", "r", "x", "b")
TAGS = ("o", *ROLES, "n", "u", "r+n")
POLICIES = ("desc_regular", "desc_free", "desc_mixed")


def features(seq, i, mask=False):
    keys = ["bias"]
    for j in (-2,-1,0,1,2):
        index = i+j
        word = seq[index] if 0<=index<len(seq) else "#"
        if not mask or len(word)<=3:
            keys.append(f"{j}:{word}")
        keys.extend((f"{j}/{word[-2:]}", f"{j}~{word[-3:]}"))
    return keys


def decode(seq, weights, mask=False):
    """Viterbi over complete token labellings. Equal scores have stable tag order."""
    if not seq:
        return []
    count=len(TAGS)
    zero=[0.]*count
    trans=[weights.get("from/"+tag,zero) for tag in TAGS]
    history=[]
    scores=[]
    for i in range(len(seq)):
        emission=[0.]*count
        for key in features(seq,i,mask):
            if key in weights:
                for k,v in enumerate(weights[key]):
                    emission[k]+=v
        if i==0:
            scores=[v+w for v,w in zip(emission,weights.get("from/^",zero))]
        else:
            back=[max(range(count),key=lambda j:scores[j]+trans[j][k]) for k in range(count)]
            scores=[emission[k]+scores[j]+trans[j][k] for k,j in enumerate(back)]
            history.append(back)
    path=[max(range(count),key=scores.__getitem__)]
    for back in reversed(history):
        path.append(back[path[-1]])
    return [TAGS[j] for j in reversed(path)]


def interpret(seq, model, *, tags=None, concepts=None):
    tags=decode(seq,model["weights"]) if tags is None else tags
    frame={r:[] for r in ROLES}
    signs=set()
    for i,(word,tag) in enumerate(zip(seq,tags,strict=True)):
        for role in tag.split("+"):
            if role in frame:
                # The concepts-only intervention has no role information and cannot move a word.
                value=concepts[i] if concepts is not None else model["concepts"].get(word)
                atom="="+value if value else word
                if atom not in frame[role]:
                    frame[role].append(atom)
            elif role in ("u","n"):
                signs.add(role)
    frame["sign"]="?" if "u" in signs else "-" if "n" in signs else "+"
    predicate=frame["r"][0] if len(frame["r"])==1 else ""
    frame["required"]=model["required"].get(predicate.removeprefix("="),["a","r"])
    return tags,frame


def aligned(left,right):
    if not left or not right:
        return False
    if left==right:
        return True
    # A narrowly shared inflection supports an alignment. Failure is never evidence of a clash.
    return (not left.startswith("=") and not right.startswith("=") and min(len(left),len(right))>=5
            and old.similarity(left,right)>=.80)


def compare(q,s):
    if any(len(f[r])>1 for f in (q,s) for r in ROLES):
        return "unknown","unresolved_span"
    a={r:next(iter(q[r]),"") for r in ROLES}
    b={r:next(iter(s[r]),"") for r in ROLES}
    if not a["r"] or not b["r"]:
        return "unknown","missing_predicate"
    same={r:aligned(a[r],b[r]) for r in ROLES}
    if same["r"]:
        for other in ("b","x"):
            if not same["a"] and aligned(a["a"],b[other]) and aligned(a[other],b["a"]):
                return "different","role_reversal"
    # Only named concepts with established distinct identities witness a substitution.
    for r in ROLES:
        if a[r].startswith("=") and b[r].startswith("=") and not same[r]:
            return "different","concept_"+r
    if any(not a[r] or not b[r] for r in set(q["required"]) | set(s["required"])):
        return "unknown","incomplete_relation"
    if not same["a"] or not same["r"] or any((a[r] or b[r]) and not same[r] for r in ROLES):
        return "unknown","missing_or_unaligned_role"
    if "?" in (q["sign"],s["sign"]):
        return "unknown","unknown_property"
    if q["sign"]!=s["sign"]:
        return "different","opposite_polarity"
    return "equal","aligned"


def select(verdicts):
    matches=[i for i,out in enumerate(verdicts) if out[0]=="equal"]
    return matches[0] if len(matches)==1 else None


@lru_cache(maxsize=1)
def models():
    return json.loads((DIR/"models.json").read_text(encoding="utf8"))


def propose(parts,catalog,policy,skip,shortlist,payload):
    model=models()["bag"] if policy=="desc_bag" else models()["variants"][policy]
    menus={i:shortlist(p["text"],catalog)[0] for i,p in enumerate(parts) if not skip(p["text"])}
    if menus and payload(parts,catalog,menus) is None:
        return {i:dict(pool=[],first=None,chosen=None,why="input_budget") for i in menus}
    sources={}
    records={}
    for i,pool in menus.items():
        if policy=="desc_bag":
            _,pred=old.infer(parts[i]["text"],[catalog[k].label[:120] for k in pool],model,"learn_bag")
            j=old.decide(pred,*model["thresholds"])
            choice=pool[j] if j is not None else None
            records[i]=dict(pool=pool,first=choice,chosen=choice,why=policy if choice is not None else "ambiguous")
            continue
        _,q=interpret(old.words(parts[i]["text"]),model)
        for k in pool:
            if k not in sources:
                sources[k]=interpret(old.words(catalog[k].label[:120]),model)[1]
        pairs=[compare(q,sources[k]) for k in pool]
        j=select(pairs)
        choice=pool[j] if j is not None else None
        records[i]=dict(pool=pool,first=choice,chosen=choice,why="description_match" if choice is not None
                        else "ambiguous",frame=q,decisions=[list(v) for v in pairs])
    return records
