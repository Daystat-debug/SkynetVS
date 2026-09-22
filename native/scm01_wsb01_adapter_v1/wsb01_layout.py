"""Pure lexical path/layout/catalog model. Not Windows filesystem or ACL evidence."""
from dataclasses import dataclass
import re
import hashlib
from .wsb01_policy import (DEFAULT_POLICY, DOMAIN, ModelOnly, CoreError, need,
                          SUCCESS_NAMES, ALLOWED_NAMES)
from .wsb01_contract import hex_string, canonical_json_bytes

ROLES = ("Input", "Runtime", "Control", "Output")
FORBIDDEN_COMPONENTS = frozenset((".git", ".venv", ".ssh", ".aws", ".azure",
                                 "credentials", "enrollment", "credentialstore"))
RESERVED = re.compile(r"^(CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|COM[0-9¹²³]|LPT[0-9¹²³])(?:\..*)?$", re.IGNORECASE)


def canonical_windows_path(value: str) -> tuple[str, ...]:
    need(type(value) is str and 4 <= len(value) <= 1024, "path_type_or_size")
    need(re.match(r"^[A-Z]:\\", value) is not None, "path_absolute_canonical_drive")
    need("/" not in value and not value.endswith("\\"), "path_separator")
    parts = value[3:].split("\\")
    for part in parts:
        need(part not in ("", ".", "..") and not part.endswith((".", " ")), "path_component")
        need(all(ord(c) >= 32 and ord(c) != 127 for c in part), "path_control")
        need(not any(c in part for c in ':*?<>|"'), "path_reserved_character")
        need(RESERVED.fullmatch(part) is None, "path_reserved_device")
        need(not any(0xD800 <= ord(c) <= 0xDFFF for c in part), "path_surrogate")
        # Exclude DOS short-name aliases; lexical checking cannot resolve them.
        need("~" not in part, "path_short_alias")
    return (value[:2].casefold(),) + tuple(x.casefold() for x in parts)


def _ancestor(a, b):
    return len(a) <= len(b) and b[:len(a)] == a


def _overlap(a, b):
    return _ancestor(a, b) or _ancestor(b, a)


@dataclass(frozen=True)
class LayoutSpec:
    run_id: str
    input_root: str
    runtime_root: str
    control_root: str
    output_root: str
    repository_root: str
    downloads_root: str
    accepted_store_root: str
    credential_roots: tuple[str, ...] = ()


@dataclass(frozen=True)
class MappingPlan:
    role: str
    host_root: str
    guest_root: str
    guest_writable: bool
    trusted_output: bool = False


@dataclass(frozen=True)
class LayoutPlan(ModelOnly):
    spec: LayoutSpec
    mappings: tuple[MappingPlan, ...]
    sha256: str

    @property
    def filesystem_verified(self):
        return False


@dataclass(frozen=True)
class ArtifactObservation:
    name: str
    size: int
    sha256: str
    kind: str
    reparse: bool | None
    symlink: bool | None
    link_count: int | None


@dataclass(frozen=True)
class CatalogCheck(ModelOnly):
    valid: bool
    reasons: tuple[str, ...]
    total_bytes: int = 0

    @property
    def filesystem_verified(self):
        return False


def plan_layout(spec: LayoutSpec) -> LayoutPlan:
    need(type(spec) is LayoutSpec, "layout_spec_type")
    hex_string(spec.run_id, 32, "layout_run_id")
    need(type(spec.credential_roots) is tuple and len(spec.credential_roots) <= 16, "credential_roots_type")
    roots = (spec.input_root, spec.runtime_root, spec.control_root, spec.output_root)
    parsed = tuple(canonical_windows_path(x) for x in roots)
    protected = tuple(canonical_windows_path(x) for x in
                      (spec.repository_root, spec.accepted_store_root) + spec.credential_roots)
    downloads = canonical_windows_path(spec.downloads_root)
    for i, parts in enumerate(parsed):
        need(not any(x in FORBIDDEN_COMPONENTS for x in parts[1:]), "forbidden_mapping_component")
        need(not any(_overlap(parts, x) for x in protected), "protected_root_overlap")
        need(not _ancestor(parts, downloads), "whole_downloads_mapping")
        for other in parsed[i + 1:]:
            need(not _overlap(parts, other), "mapping_overlap_or_alias")
    mappings = tuple(MappingPlan(role, root,
                        "C:\\SkynetVSLab\\" + spec.run_id + "\\Mapped\\" + role,
                        role == "Output") for role, root in zip(ROLES, roots))
    description = {"evidence_domain": DOMAIN, "run_id": spec.run_id,
                   "mappings": [{"role": m.role, "host_root": m.host_root,
                                 "guest_root": m.guest_root, "guest_writable": m.guest_writable,
                                 "trusted_output": False} for m in mappings]}
    return LayoutPlan(spec, mappings, hashlib.sha256(canonical_json_bytes(description)).hexdigest())


def validate_catalog(plan: LayoutPlan, entries: tuple[ArtifactObservation, ...]) -> CatalogCheck:
    try:
        need(type(plan) is LayoutPlan and plan == plan_layout(plan.spec), "layout_plan_modified")
        need(type(entries) is tuple and len(entries) <= 16, "catalog_container_or_count")
        limits = {"ready.json": DEFAULT_POLICY.ready_bytes, "journal.jsonl": DEFAULT_POLICY.journal_bytes,
                  "terminal.json": DEFAULT_POLICY.terminal_bytes, "terminal.sig": DEFAULT_POLICY.signature_bytes,
                  "failure.json": DEFAULT_POLICY.failure_bytes}
        names = set()
        total = 0
        for entry in entries:
            need(type(entry) is ArtifactObservation, "catalog_entry_type")
            need(type(entry.name) is str and entry.name in ALLOWED_NAMES, "catalog_name")
            need(entry.name not in names, "catalog_duplicate")
            names.add(entry.name)
            need(entry.kind == "regular" and type(entry.kind) is str, "catalog_regular_file")
            need(entry.reparse is False and entry.symlink is False, "catalog_unknown_or_reparse")
            need(type(entry.link_count) is int and entry.link_count == 1, "catalog_link_count")
            need(type(entry.size) is int and 0 < entry.size <= limits[entry.name], "catalog_size")
            if entry.name == "terminal.sig":
                need(entry.size == 64, "catalog_signature_size")
            hex_string(entry.sha256, 64, "catalog_sha256")
            total += entry.size
            need(total <= DEFAULT_POLICY.accepted_raw_bytes, "catalog_total_bytes")
        need(names == set(SUCCESS_NAMES), "catalog_success_exact_names")
        return CatalogCheck(True, (), total)
    except CoreError as exc:
        return CatalogCheck(False, (str(exc),))
