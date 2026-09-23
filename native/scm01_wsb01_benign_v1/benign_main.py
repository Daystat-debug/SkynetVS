"""Import-safe, always-closed public entrypoint."""
import json


def main(argv=None):
    # Deliberately do not parse argv, open files or issue a permit.
    print(json.dumps({'kind': 'SCM01_WSB01_BEN01_SOURCE_V1',
                      'result': 'RUNTIME_CLOSED_SOURCE_ONLY',
                      'evidence_domain': 'OFFLINE_MODEL',
                      'runtime_authorized': False, 'crypto_verified': False,
                      'sandbox': False, 'guest_bootstrap': False,
                      'real_scm': False, 'guard': False}, sort_keys=True))
    return 92


if __name__ == '__main__':
    raise SystemExit(main())
