"""Allocate the remaining host steps across expression-specific research obligations."""
from itertools import combinations


POLICIES = ("joint_order", "joint_cheapest", "joint_plan")


class Products:
    """Private to one Search and its immutable AST nodes. Never accept products from a provider."""
    def __init__(self, search, calls):
        self.search = search
        self.calls = calls
        self.requested = set()
        self.arguments = {}
        self.hits = 0
        self.reused_trees = 0

    def remember(self, fn, call, rows):
        if fn in self.requested and len(self.arguments) < 96:
            self.arguments[fn, call] = rows

    def lookup(self, target, src, refuse):
        search = self.search
        if src is not search.src or set(search.index.trees) != set(src.pages):
            raise ValueError("snapshot_policy")
        src.current()
        paths = sorted(src.pages)
        self.reused_trees += len(paths)
        return self.calls._lookup_trees(target, src, refuse, paths, search.index.trees, remember=self.remember)

    def bound(self, site):
        # Search.incoming already verified caller/callee, coordinates, import/name bindings and anchors.
        self.search.check_budget()
        self.search.current(self.search.src)
        rows = self.arguments.get((site.callee.node, site.call))
        if rows is not None:
            self.hits += 1
        return rows

    def consistent(self, meta, claims, render):
        for proof in meta["proofs"]:
            sites = self.search.cache.get(proof["receipt"]["owner"], ())
            for row in claims[proof["start"]:proof["end"]]:
                if row["kind"] != "arguments":
                    continue
                if len(sites) != 1 or row["anchors"] != sites[0].anchors:
                    return False
                rows = self.arguments.get((sites[0].callee.node, sites[0].call))
                if rows is not None and row["text"] != render(rows):
                    return False
        return True


def ordered(policy, groups, decisions, effects, ctl, log):
    """Replan after every attempted object so actual consumption and verified caches take precedence."""
    search = ctl.s
    pending = list(groups)
    requests = {t:{decisions[i]["kind"] for i in indices} for t,indices in groups.items()}
    products = getattr(search, "products", None)
    if products:
        products.requested.update(effects[t].fn.node for t in pending if t in effects and "arguments" in requests[t])

    def identity(t):
        if t not in effects:
            return ("~", t, 0)
        e = effects[t]
        return (e.fn.path, e.expr.lineno, e.expr.col_offset)

    def operations(t):
        keys = {("locate", t)}
        if t not in effects:
            return keys
        e = effects[t]
        owner = e.fn.node.name
        wanted = requests[t]
        if wanted.intersection(("caller","arguments","caller_condition")) and owner not in search.cache:
            keys.add(("calls", owner))
        if "arguments" in wanted and products is None:
            keys.add(("bind", owner))
        if "condition" in wanted and (e.fn.path, e.stmt) not in ctl.proofs:
            keys.add(("proof", e.fn.path, e.stmt))
        if "caller_condition" in wanted:
            keys.add(("caller_proof", owner))
        return keys

    while pending:
        # A bounded 2^8 search over sets. Each real tool still enforces its original charge.
        remaining = search.budget - len(search.trace)
        keys = {t:operations(t) for t in pending}
        by_cost = sorted(pending, key=lambda t:(t not in effects,len(keys[t]),identity(t)))
        selected = by_cost
        if policy == "joint_order":
            selected = pending
        elif policy == "joint_plan":
            best = (0,0)
            for n in range(1,len(by_cost)+1):
                for subset in combinations(by_cost,n):
                    cost = len(set.union(*(keys[t] for t in subset)))
                    benefit = sum(len(requests[t]) for t in subset if t in effects)
                    if cost <= remaining and (benefit,-cost) > best:
                        selected, best = subset, (benefit,-cost)
        t = selected[0]
        log.append(dict(target=t, remaining=remaining, estimated_steps=len(keys[t]), requests=sorted(requests[t])))
        pending.remove(t)
        yield t, groups[t]
