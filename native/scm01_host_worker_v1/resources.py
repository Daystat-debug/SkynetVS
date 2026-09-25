"""Immediate ownership registration; exactly one close attempt per acquired resource."""
from dataclasses import dataclass
from .contract import need


@dataclass(slots=True)
class Resource:
    name: str
    value: object
    close: object
    is_handle: bool = True
    state: str = 'OPEN'
    error: str | None = None


class Resources:
    def __init__(self):
        self.items = []
        self.events = []

    def add(self, name, value, close, *, is_handle=True):
        need(type(name) is str and bool(name), 'resource_name')
        need(not any(r.name == name for r in self.items), 'resource_name_reused')
        if is_handle:
            need(type(value) is int and 0 < value < (1 << 64) - 1, 'invalid_owned_handle')
            need(not any(r.is_handle and r.state == 'OPEN' and r.value == value
                         for r in self.items), 'duplicate_live_handle')
        r = Resource(name, value, close, is_handle)
        self.items.append(r)
        self.events.append({'event': 'ACQUIRED', 'resource': name})
        return value

    def close_one(self, name):
        rows = [r for r in self.items if r.name == name]
        need(len(rows) == 1 and rows[0].state == 'OPEN', 'close_not_owned_or_repeated')
        r = rows[0]
        r.state = 'CLOSE_ATTEMPTED'
        try:
            r.close(r.value)
        except BaseException as exc:
            r.state = 'UNCERTAIN'
            r.error = type(exc).__name__ + ':' + str(exc)[:160]
            self.events.append({'event': 'CLOSE_UNCERTAIN', 'resource': name, 'error': r.error})
            raise
        else:
            r.state = 'CLOSED'
            self.events.append({'event': 'CLOSED', 'resource': name})

    def close_all(self, exclude=()):
        errors = []
        for r in reversed(self.items):
            if r.state != 'OPEN' or r.name in exclude:
                continue
            try:
                self.close_one(r.name)
            except BaseException as exc:
                errors.append(type(exc).__name__ + ':' + str(exc)[:160])
        return errors

    def summary(self):
        return {'unreleased_handles': sum(r.state == 'OPEN' for r in self.items),
                'uncertain_closes': sum(r.state not in ('OPEN', 'CLOSED') for r in self.items)}

    def all_closed(self):
        return all(r.state == 'CLOSED' for r in self.items)
