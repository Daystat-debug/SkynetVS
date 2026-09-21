"""No runtime authority is issued in SCM01 controller V1 source/build delivery."""
from scm01_contract import RuntimeClosed


def require_runtime_authority(_record=None):
    raise RuntimeClosed('SCM01 source/build-only: no named-guest runtime authorization or capsule issuer has been delivered')
