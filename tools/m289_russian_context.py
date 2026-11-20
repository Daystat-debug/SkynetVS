"""Experimental Russian admission fallback; reuse the original bounded packer."""
from m289_multifragment import MultiFragment, Window, windows
from m289_russian import best_line, stems


def russian_windows(core, snapshot, candidates, question):
    literal, reason = windows(core, snapshot, candidates, question)
    if reason != "NO_CODE_MENTION":
        return literal, reason
    query = stems(question)
    matches = []
    seen = set()
    for selector in candidates:
        view = core.structural_view(snapshot, selector)["evidence"]
        path, first, last = view["path"], view["start"], view["end"]
        lines = snapshot.sources[path].splitlines()[first - 1:last]
        hits, center = best_line(query, lines, first)
        if len(hits) < 2 or (path, center) in seen:
            continue
        seen.add((path, center))
        # The packer always retains the entire center line. Its optional ASCII
        # identifier check is inapplicable to a Russian witness on that line.
        name = selector.split("::")[1].split("@")[0]
        matches.append((hits, Window(selector, path, name, first, last, center, set(), set())))
    if not matches:
        return [], "NO_LOCAL_RUSSIAN_SUPPORT"
    matches.sort(key=lambda item: -len(item[0]))
    first_hits, first_window = matches[0]
    if any(hits == first_hits for hits, _ in matches[1:]):
        return [], "AMBIGUOUS_RUSSIAN_SUPPORT"
    selected = [first_window]
    covered = set(first_hits)
    for hits, window in matches[1:]:
        if len(hits - covered) >= 2:
            selected.append(window)
            covered.update(hits)
            if len(selected) == 3:
                break
    return selected, "LOCAL_RUSSIAN_SUPPORT"


class RussianContext(MultiFragment):
    select_windows = staticmethod(russian_windows)
