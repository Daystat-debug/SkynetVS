"""Read selected SkynetVS workspaces and publish an exact diagnostic receipt.

No project checkout, index, configuration or file is changed by this command.
Only the selected report directory owns local commits and publication state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent))
from git_transport import Transport
from workflow_run import atomic_json, json_bytes, relative_path, run_lock
from probe import collect, resolve_root, ProbeError

REMOTE = 'https://github.com/Daystat-debug/SkynetVS.git'
PROJECT = Path(r'C:\Project\SkynetVS')
BASE = '3cd5a06b3b17ce2e6b9b25351a1b455289974dfb'
SCHEMA = 'SKYNETVS_M154_WORKSPACE_CHECK_STATE_V1'


class CheckError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


def checked_tools(bundle: Path) -> dict[str, bytes]:
    manifest_bytes = (bundle / 'manifest.json').read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest.get('schema') != 'SKYNETVS_M154_WORKSPACE_CHECK_PACKAGE_V1':
        raise CheckError('PACKAGE_SCHEMA_MISMATCH')
    expected = {'workspace_check.py', 'probe.py', 'test_probe.py', 'test_workspace_check.py',
                'git_transport.py', 'workflow_run.py', 'development_lessons.py',
                'launch_template.ps1', 'preparation_qa.json', 'preparation_qa.log.txt'}
    if set(manifest['files']) != expected:
        raise CheckError('PACKAGE_FILE_SET_MISMATCH')
    files = {'tool/manifest.json': manifest_bytes}
    for name, entry in manifest['files'].items():
        path = bundle / name
        if path.is_symlink():
            raise CheckError('PACKAGE_SYMLINK')
        data = path.read_bytes()
        if len(data) != entry['size_bytes'] or sha(data) != entry['sha256']:
            raise CheckError('PACKAGE_FILE_HASH_MISMATCH')
        files['tool/' + name] = data
    return files


def read_saved_files(run_dir: Path, state: dict) -> dict[str, bytes]:
    public = run_dir / 'public'
    receipt_file = public / 'receipt.json'
    if receipt_file.is_symlink():
        raise CheckError('REPORT_SYMLINK')
    receipt_bytes = receipt_file.read_bytes()
    receipt = json.loads(receipt_bytes)
    if (receipt.get('schema') != 'SKYNETVS_M154_WORKSPACE_RECEIPT_V1'
            or receipt.get('run_id') != state['run_id']):
        raise CheckError('REPORT_RECEIPT_MISMATCH')
    files = {'receipt.json': receipt_bytes}
    for name, entry in receipt['files'].items():
        path = public / relative_path(name)
        if path.is_symlink() or not path.resolve().is_relative_to(public.resolve()):
            raise CheckError('REPORT_SYMLINK')
        data = path.read_bytes()
        if len(data) != entry['size_bytes'] or sha(data) != entry['sha256']:
            raise CheckError('REPORT_BYTES_CHANGED')
        files[name] = data
    return files


def publish(run_dir: Path, state: dict) -> dict:
    files = read_saved_files(run_dir, state)
    prefix = 'reports/M154/' + state['run_id'] + '/'
    transport = Transport(run_dir / 'report_git', state['remote_url'])
    transport.prepare_report({prefix + name: data for name, data in files.items()}, state['run_id'])
    publication = transport.publish()
    atomic_json(run_dir / 'publication.json', publication)
    return publication


def run_check(repo: Path, bundle: Path, run_dir: Path, *, project_repo: Path = PROJECT,
              remote_url: str = REMOTE) -> dict:
    repo, project_repo, bundle, run_dir = (p.resolve() for p in (repo, project_repo, bundle, run_dir))
    targets = [('selected_repository', repo)]
    if canonical(project_repo) != canonical(repo):
        targets.append(('previous_script_source', project_repo))
    for _, source in targets:
        roots = [source]
        try:
            roots.append(resolve_root(source))
        except ProbeError:
            pass  # Recorded below as a failed observation, if collection is new.
        if any(run_dir.is_relative_to(p) or p.is_relative_to(run_dir) for p in roots):
            raise CheckError('REPORT_SOURCE_OVERLAP')
    binding = {'selected_repository': canonical(repo), 'previous_script_source': canonical(project_repo),
               'remote_url': remote_url, 'manifest_sha256': sha((bundle / 'manifest.json').read_bytes())}
    if run_dir.exists() and not (run_dir / 'state.json').exists():
        if any(p.name != 'run.lock' for p in run_dir.iterdir()):
            raise CheckError('UNOWNED_REPORT_DIRECTORY')
    run_dir.mkdir(parents=True, exist_ok=True)
    with run_lock(run_dir):
        state_path = run_dir / 'state.json'
        if state_path.exists():
            state = json.loads(state_path.read_bytes())
            if state.get('schema') != SCHEMA or state.get('binding') != binding:
                raise CheckError('SAVED_RUN_BINDING_MISMATCH')
            if state.get('phase') != 'FINISHED':
                raise CheckError('INCOMPLETE_DIAGNOSTIC_RUN_USE_NEW_RUN')
            return {'summary': json.loads((run_dir / 'public/summary.json').read_bytes()),
                    'publication': publish(run_dir, state), 'reused_saved_diagnostics': True}

        tool_files = checked_tools(bundle)
        identifier = uuid.uuid4().hex
        state = {'schema': SCHEMA, 'run_id': identifier, 'phase': 'COLLECTING',
                 'binding': binding, 'remote_url': remote_url}
        atomic_json(state_path, state)
        observations, errors = [], []
        for label, source in targets:
            print('WORKSPACE_CHECK_STARTED=' + label, flush=True)
            try:
                record = collect(source)
                observations.append({'label': label, 'observation': record})
                if record.get('status') != 'COLLECTED':
                    errors.append({'label': label, 'code': record.get('status', 'INCOMPLETE_OBSERVATION')})
            except ProbeError as exc:
                errors.append({'label': label, 'error_type': 'ProbeError', 'code': exc.reason,
                               'operation': exc.operation, 'returncode': exc.returncode})
            except Exception as exc:
                # Do not copy raw exceptions or user paths into a public report.
                errors.append({'label': label, 'error_type': type(exc).__name__, 'code': 'PROBE_FAILED'})
            print('WORKSPACE_CHECK_FINISHED=' + label, flush=True)
        summary = {'schema': 'SKYNETVS_M154_WORKSPACE_DIAGNOSTIC_V1',
                   'purpose': 'WORKSPACE_BRANCH_AND_IGNORE_DIAGNOSTIC', 'run_id': identifier,
                   'expected_reminder_base': BASE, 'status': 'COLLECTED' if not errors else 'PARTIAL',
                   'exit_code': 0 if not errors else 2,
                   'selected_path_differs_from_previous_script_source': len(targets) == 2,
                   'observations': observations, 'errors': errors,
                   'source_project_written': False, 'source_git_written': False,
                   'pipeline_executed': False, 'repair_applied': False, 'main_merged': False,
                   'report_contains_user_runtime_file_contents': False,
                   'scope': 'Git metadata, ignore rules for fixed probe paths, counts and hashes; source file contents and arbitrary untracked names are not published.',
                   'finished_at': datetime.now(timezone.utc).isoformat(timespec='seconds')}
        files = {'summary.json': json_bytes(summary), 'diagnostics.json': json_bytes({'errors': errors}), **tool_files}
        receipt = {'schema': 'SKYNETVS_M154_WORKSPACE_RECEIPT_V1', 'project': 'SkynetVS', 'stage': 'M154',
                   'run_id': identifier, 'purpose': summary['purpose'],
                   'files': {name: {'sha256': sha(data), 'size_bytes': len(data)} for name, data in files.items()},
                   'scope': 'Read-only workspace observations and the exact trusted diagnostic source/tests. No project change or pipeline result.'}
        files['receipt.json'] = json_bytes(receipt)
        public = run_dir / 'public'
        public.mkdir()
        for name, data in files.items():
            path = public / relative_path(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        state['phase'] = 'FINISHED'
        atomic_json(state_path, state)
        return {'summary': summary, 'publication': publish(run_dir, state), 'reused_saved_diagnostics': False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=PROJECT)
    parser.add_argument('--bundle', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--run-dir', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run_check(args.repo, args.bundle, args.run_dir)
        summary, publication = result['summary'], result['publication']
        print('RUN_ID=' + summary['run_id'])
        print('DIAGNOSTIC_STATUS=' + summary['status'])
        print('REUSED_SAVED_DIAGNOSTICS=' + str(result['reused_saved_diagnostics']).upper())
        print('REPORT_PUBLISH_STATUS=' + publication['report']['status'])
        print('REPORT_URL=https://github.com/Daystat-debug/SkynetVS/tree/reports/m154/reports/M154/' + summary['run_id'])
        print('PRESERVED_RUN_DIRECTORY=' + str(args.run_dir))
        complete = publication['report']['status'] == 'PUBLISHED'
        print('PUBLICATION=' + ('COMPLETE' if complete else 'PENDING'))
        return summary['exit_code'] or (0 if complete else 75)
    except Exception as exc:
        print('WORKSPACE_CHECK_STOP=' + (getattr(exc, 'code', None) or type(exc).__name__))
        print('PRESERVED_RUN_DIRECTORY=' + str(args.run_dir))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
