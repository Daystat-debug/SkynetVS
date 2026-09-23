"""Source delivery has no issuer. No JSON, fake object or CLI flag opens this gate."""
class RuntimeClosed(RuntimeError):
    pass


def require_benign_run_authority(*_args, **_kwargs):
    raise RuntimeClosed('BEN01_RUNTIME_CLOSED_SOURCE_ONLY')


def require_native_authority(*_args, **_kwargs):
    raise RuntimeClosed('BEN01_NATIVE_SMOKE_NOT_AUTHORIZED')
