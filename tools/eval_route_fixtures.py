"""Emit new Git fixtures and their reference answers together, without executing them."""
import random


def suite(seed, raw):
    rng = random.Random(seed)
    for index in range(18):
        shape = index % 6
        names = set()

        def name():
            while True:
                value = "r_" + format(rng.getrandbits(40), "x")
                if value not in names:
                    names.add(value)
                    return value

        entry, end, relay, flag = (name() for _ in range(4))
        message = "E_" + format(rng.getrandbits(32), "X")
        gate = rng.randint(2, 77)
        good, bad = gate, gate - rng.randint(1, 20)
        lines = []
        def emit(line):
            lines.append(line)
            return len(raw.splitlines()) + len(lines)

        emit("")
        definition = emit(f"def {end}({flag}={bad}):")
        guard = rng.choice((f"{flag} >= {gate}", f"not {flag} < {gate}", f"{flag} == {gate}"))
        condition = emit(f"    if {guard}:")
        outcome = emit(f"        raise ValueError('{message}')")
        emit("    return 0")
        refs = [definition, condition, outcome]
        controls = [[end, outcome, condition]]
        edges, required = [], []
        expected = "conditional_route"
        if shape in (0, 1, 5):
            places = list(range(rng.randint(2, 4)))
            active = (places[0] if shape == 1 else places[-1])
            for place in places:
                fn = relay if place == active else name()
                literal = good if place == active else bad
                forward = shape == 5 and place == active
                param = "value" if forward else ""
                expr = param if forward else str(literal)
                d = emit(f"def {fn}({param}):")
                c = emit(f"    return {end}({flag}={expr})")
                if place == active:
                    refs.extend([d,c])
                    controls.append([relay,c,True])
                    edges.append([relay,end,c])
            d = emit(f"def {entry}():")
            arg = str(good) if shape == 5 else ""
            c = emit(f"    return {relay}({arg})")
            refs.extend([d,c])
            controls.append([entry,c,True])
            edges.insert(0,[entry,relay,c])
            if shape == 5:
                required.extend([f"value ← `{good}`", f"{flag} ← `value`"])
            else:
                required.append(f"{flag} ← `{good}`")
        elif shape == 2:
            refs.append(emit(f"def {entry}():"))
            emit(f"    {end}()")
            c = emit(f"    return {end}({good})")
            refs.append(c)
            controls.append([entry,c,True])
            edges.append([entry,end,c])
            required.append(f"{flag} ← `{good}`")
        elif shape == 3:
            refs.append(emit(f"def {entry}():"))
            c = emit(f"    return {end}()")
            refs.append(c)
            controls.append([entry,c,True])
            edges.append([entry,end,c])
            expected = "excluded_route"
            required.extend([f"{flag}={bad}", "по умолчанию"])
        else:
            # A call in a conditional expression needs expression-level control.
            emit(f"def {entry}(choose):")
            emit(f"    return {end}({good}) if choose else None")
            expected = "unproven"
        question = f"Как из {entry} дойти до ошибки {message}?"
        case = dict(id=f"G{index+1:02}", q=question, expect=expected,
                    refs={"R":refs}, controls=controls, edges=edges,
                    text=required + [message])
        if shape == 4:
            case["reasons"] = ["conditional_expression"]
        yield raw + ("\n".join(lines)+"\n").encode(), case
