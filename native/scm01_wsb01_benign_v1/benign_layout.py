"""Lexical layout and fixed XML only. OS filesystem facts come from a different provider."""
from dataclasses import dataclass
from pathlib import PureWindowsPath
import re
from xml.sax.saxutils import escape
from .benign_contract import need, hexstr, sha, canonical

SETTINGS = (('Networking', 'Disable'), ('vGPU', 'Disable'),
            ('ClipboardRedirection', 'Disable'), ('AudioInput', 'Disable'),
            ('VideoInput', 'Disable'), ('PrinterRedirection', 'Disable'),
            ('ProtectedClient', 'Enable'), ('MemoryInMB', '4096'))
ROLES = ('Input', 'Runtime', 'Control', 'Output')
GUEST_ROOTS = tuple('C:\\SkynetVSBenign' + x for x in ROLES)
_RESERVED = {'con', 'prn', 'aux', 'nul', 'clock$'} | {
    p + str(n) for p in ('com', 'lpt') for n in range(1, 10)}


def component(value):
    need(type(value) is str and 0 < len(value) <= 180, 'component_size')
    need(re.fullmatch(r'[A-Za-z0-9_. -]+', value) is not None, 'component_char')
    need(value not in ('.', '..') and not value.endswith(('.', ' ')) and '~' not in value,
         'component_alias')
    need(value.split('.')[0].casefold() not in _RESERVED, 'device_name')
    return value


def winpath(value):
    need(type(value) is str and len(value) <= 240 and '\x00' not in value, 'path')
    need(re.match(r'^[A-Za-z]:\\', value) is not None and '/' not in value,
         'absolute_dos_path')
    tail = value[3:]
    need(tail and not tail.endswith('\\') and '\\\\' not in tail, 'path_components')
    for c in tail.split('\\'):
        component(c)
    return value[0].upper() + value[1:]


def overlaps(a, b):
    aa, bb = a.casefold(), b.casefold()
    return aa == bb or aa.startswith(bb + '\\') or bb.startswith(aa + '\\')


@dataclass(frozen=True)
class LayoutSpec:
    lab_parent: str
    host_state: str
    repository: str
    downloads: str
    excluded: tuple[str, ...]
    run_id: str
    supported_settings: tuple[tuple[str, str], ...] = SETTINGS


@dataclass(frozen=True)
class BoundLayout:
    run_id: str
    lab_root: str
    host_state: str
    host_roles: tuple[str, ...]
    guest_roles: tuple[str, ...] = GUEST_ROOTS
    settings: tuple[tuple[str, str], ...] = SETTINGS

    def descriptor(self, wsb_bytes):
        return {'run_id': self.run_id, 'lab_root': self.lab_root,
                'host_state': self.host_state,
                'roles': [{'role': r, 'host': h, 'guest': g, 'read_only': r != 'Output'}
                          for r, h, g in zip(ROLES, self.host_roles, self.guest_roles)],
                'settings': dict(self.settings), 'wsb_sha256': sha(wsb_bytes)}


def plan_layout(spec):
    need(type(spec) is LayoutSpec, 'layout_spec')
    hexstr(spec.run_id, 32)
    need(spec.supported_settings == SETTINGS, 'mandatory_wsb_settings')
    parent, state, repo, downloads = map(winpath, (spec.lab_parent, spec.host_state,
                                                   spec.repository, spec.downloads))
    need(type(spec.excluded) is tuple, 'excluded_paths')
    excluded = tuple(winpath(x) for x in spec.excluded)
    root = winpath(parent + '\\' + spec.run_id)
    roles = tuple(winpath(root + '\\' + x) for x in ROLES)
    need(not overlaps(root, state), 'state_mapped')
    # A per-run subdirectory under Downloads is allowed; mapping Downloads itself is not.
    for p in roles:
        need(p.casefold() != downloads.casefold(), 'whole_downloads')
        need(not any(overlaps(p, x) for x in (repo, state) + excluded), 'forbidden_overlap')
        need(not any(x.casefold() in ('.git', '.venv', 'credentials', 'enrollment', 'accepted')
                     for x in PureWindowsPath(p).parts[1:]), 'forbidden_component')
    need(not overlaps(root, repo) and not any(overlaps(root, x) for x in excluded), 'lab_overlap')
    return BoundLayout(spec.run_id, root, state, roles)


def render_wsb(layout, bootstrap_pin):
    need(type(layout) is BoundLayout and layout.settings == SETTINGS and
         layout.guest_roles == GUEST_ROOTS, 'fixed_layout')
    hexstr(bootstrap_pin)
    for p in layout.host_roles:
        winpath(p)
    need(layout.host_roles == tuple(layout.lab_root + '\\' + x for x in ROLES), 'role_paths')
    parts = ['<Configuration>', '<!-- bootstrap_sha256=' + bootstrap_pin + ' -->']
    parts += ['<' + k + '>' + v + '</' + k + '>' for k, v in SETTINGS]
    parts.append('<MappedFolders>')
    for role, host, guest in zip(ROLES, layout.host_roles, GUEST_ROOTS):
        parts.append('<MappedFolder><HostFolder>' + escape(host) + '</HostFolder><SandboxFolder>' +
                     escape(guest) + '</SandboxFolder><ReadOnly>' +
                     ('false' if role == 'Output' else 'true') + '</ReadOnly></MappedFolder>')
    parts.append('</MappedFolders>')
    command = ('C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe '
               '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File '
               '"C:\\SkynetVSBenignInput\\guest_bootstrap.ps1"')
    parts += ['<LogonCommand><Command>' + escape(command) + '</Command></LogonCommand>',
              '</Configuration>']
    return ('\n'.join(parts) + '\n').encode('ascii')
