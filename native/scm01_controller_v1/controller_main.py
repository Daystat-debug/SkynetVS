"""Public entrypoint intentionally refuses before importing any native backend."""
import json


def main():
    print(json.dumps({'kind': 'SCM01_CONTROLLER_V1', 'result': 'RUNTIME_CLOSED_SOURCE_BUILD_ONLY',
                      'scm_calls': 0, 'guard_executed': False, 'runtime_authorized': False}))
    return 92


if __name__ == '__main__':
    raise SystemExit(main())
