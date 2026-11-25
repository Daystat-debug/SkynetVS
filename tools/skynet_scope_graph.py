"""Resolve the scope of predicates before opening any evidence frontier."""
from itertools import product

import skynet_experience as experience
import skynet_relation as relation
import skynet_evidence_plan as allocation

req = relation.req
POLICIES = ("scope_graph", "scope_nearest", "scope_local") + allocation.POLICIES
# Only grammatical material may disappear around a grounded topic.
GLUE = frozenset("и а также для у по о об про с в на к обоих обеих оба обе".split())


def predicates(parts, edges, effects):
    """None is an object mention without a predicate. An unrecognized demand stays a demand."""
    predictor, cutoffs = relation.fitted()
    seeds = []
    for part, edge in zip(parts, edges, strict=True):
        text = part["text"]
        effect = effects.get(edge["target"])
        words = relation.wording(text, effect.label if effect else "")
        if edge["object"] and not set(words.split()) - GLUE:
            seeds.append(None)
            continue
        kind, score, margin = predictor.predict(words, False)
        floor, gap = cutoffs["relation_frame"]
        if score < floor or margin < gap:
            needs, issues, _ = experience.shared_plan([part])[0]
            # Strip structural prerequisites; keep only an unambiguous requested result.
            leaves = [n for n in needs if not any(n in req.closure([k]) for k in needs if k != n)]
            options = leaves + issues
            kind = options[0] if len(options) == 1 else "unverified_meaning"
        if req.goals.route.arguments.cli.auto_reader.EVENT.search(text):
            kind = "runtime"
        seeds.append(kind)
    return seeds


def alternatives(indices, seeds):
    """Enumerate projective contiguous scopes. Each domain has at most one overt predicate."""
    best = -1
    winners = []
    for cuts in product((False, True), repeat=len(indices)-1):
        groups = [[]]
        for j, i in enumerate(indices):
            if j and cuts[j-1]:
                groups.append([])
            groups[-1].append(i)
        origins = []
        for group in groups:
            heads = [i for i in group if seeds[i] is not None]
            if len(heads) > 1 or (len(group) > 1 and heads and seeds[heads[0]] not in req.KINDS):
                break
            origins.extend([heads[0] if heads else None] * len(group))
        else:
            coverage = sum(o is not None for o in origins)
            if coverage > best:
                best, winners = coverage, []
            if coverage == best and origins not in winners:
                winners.append(origins)
    return winners


def sentences(parts, edges):
    group = []
    for i, p in enumerate(parts):
        if group and parts[i-1]["text"].rstrip().endswith((".", ";", "?", "!")):
            # A separately introduced topic followed by an explicit reference to itself.
            if not (len(group) == 1 and edges[i]["via"] == "reference" and
                    edges[i]["target"] == edges[group[0]]["target"]):
                yield group
                group = []
        group.append(i)
    if group:
        yield group


def link(parts, edges, seeds, policy):
    decisions = []
    for group in sentences(parts, edges):
        if policy == "scope_graph" or policy in allocation.POLICIES:
            candidates = alternatives(group, seeds)
        else:
            heads = [i for i in group if seeds[i] in req.KINDS]
            candidates = [[min(heads, key=lambda h: abs(i-h)) if heads and seeds[i] is None
                           and policy == "scope_nearest" else i for i in group]]
        for j, i in enumerate(group):
            origins = sorted({row[j] for row in candidates if row[j] is not None})
            options = sorted({seeds[o] for o in origins if seeds[o] is not None})
            kind = options[0] if len(options) == 1 else "ambiguous" if options else "unverified_meaning"
            decisions.append(dict(kind=kind, initial=seeds[i], origins=origins,
                                  alternatives=options, revised=kind != seeds[i] and seeds[i] is None))
    return decisions


def interpret(parts, edges, effects, policy):
    return link(parts, edges, predicates(parts, edges, effects), policy)


def verify(parts, meta, claims, catalog, commit, policy, suggestions=None):
    import skynet_object_binding as objects
    edges, effects = objects.resolve(parts, catalog, commit, policy, suggestions)
    decisions = interpret(parts, edges, effects, policy)
    for p, d, (needs, issues, _) in zip(meta["parts"], decisions, relation.plan(decisions), strict=True):
        if (p["need"] != needs or not set(issues) <= set(p["issues"])
                or p.get("relation") != relation.projection(p, d, claims)
                or (p["status"] == "established" and not p["relation"]["direct"])):
            raise req.observed.route.arguments.host.Rejected("claim_binding")
