"""Permanent refusal. No token, environment variable or model receipt can open it."""
from typing import NoReturn


class RuntimeClosed(RuntimeError):
    pass


def require_runtime_authority(record=None) -> NoReturn:
    raise RuntimeClosed("RUNTIME_CLOSED_SOURCE_ONLY: no runtime issuer or executor")
