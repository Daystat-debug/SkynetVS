import ast
import contextlib
import io
import json
from pathlib import Path
import unittest
from .. import adapter_main
from ..wsb01_policy import DOMAIN
from ..wsb01_runtime_gate import RuntimeClosed, require_runtime_authority
from ..wsb01_transcript import validate_transcript_model, validate_scm_trace_model
from ..wsb01_state import initial_model
from .test_contract import model_bundle, expectation, journal_bytes
from .test_layout import layout_spec, catalog
from ..wsb01_layout import plan_layout, validate_catalog

ROOT = Path(__file__).resolve().parents[1]
CORE_ALLOWED = {"dataclasses", "enum", "hashlib", "json", "re", "struct", "typing", "collections.abc"}


class ClosedBoundaryTests(unittest.TestCase):
    def test_CLO01_entrypoint_refuses(self):
        for arguments in (None, [], ["--allow-runtime"], ["--unsafe", "approved=true"], object()):
            with self.subTest(arguments=arguments):
                stream = io.StringIO()
                with contextlib.redirect_stdout(stream):
                    self.assertEqual(adapter_main.main(arguments), 92)
                result = json.loads(stream.getvalue())
                self.assertEqual(result["result"], "RUNTIME_CLOSED_SOURCE_ONLY")
                self.assertIs(result["runtime_authorized"], False)
                self.assertIs(result["crypto_verified"], False)

    def test_CLO02_gate_always_refuses(self):
        pin, snap, obs = model_bundle()
        receipt = validate_transcript_model(pin, snap, obs)
        for value in (None, object(), {"approved": True}, {"runtime_authorized": True}, receipt, pin):
            with self.subTest(value=type(value)), self.assertRaises(RuntimeClosed):
                require_runtime_authority(value)

    def test_CLO03_no_active_imports(self):
        siblings = {p.stem for p in ROOT.glob("*.py")}
        for path in ROOT.glob("*.py"):
            tree = ast.parse(path.read_bytes(), str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertIn(alias.name, CORE_ALLOWED, (path.name, alias.name))
                elif isinstance(node, ast.ImportFrom):
                    if node.level:
                        self.assertEqual(node.level, 1)
                        self.assertIn(node.module, siblings)
                    else:
                        self.assertIn(node.module, CORE_ALLOWED)
                elif isinstance(node, ast.Call):
                    name = node.func.id if isinstance(node.func, ast.Name) else None
                    self.assertNotIn(name, {"open", "exec", "eval", "compile", "__import__"}, (path.name, name))

    def test_CLO04_no_live_credential_or_marker_writer(self):
        for path in ROOT.glob("*.py"):
            tree = ast.parse(path.read_bytes(), str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    self.assertNotIn(node.func.attr, {"write_bytes", "write_text", "mkdir", "unlink", "rmdir",
                                                     "open", "system", "Popen", "run", "WinDLL", "CDLL"})
        pin, snap, _ = model_bundle()
        self.assertEqual(pin.evidence_domain, DOMAIN)
        self.assertIn(b'"evidence_domain":"OFFLINE_MODEL"', snap.authorization)
        self.assertEqual(list(ROOT.glob("*.once.json")), [])
        self.assertEqual(list(ROOT.glob("*.wsb")), [])
        self.assertEqual(list(ROOT.glob("*.ps1")), [])

    def test_CLO05_source_allowlist_and_bindings(self):
        scope = json.loads((ROOT / "SOURCE_SCOPE.json").read_text(encoding="utf-8"))
        present = sorted(p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*")
                         if p.is_file() and "__pycache__" not in p.parts)
        self.assertEqual(len(present), 22)
        self.assertEqual(present, sorted(scope["relative_files"]))
        self.assertEqual(scope["existing_code_modifications"], [])
        self.assertFalse(scope["repository_apply_authorized"])
        bindings = json.loads((ROOT / "SOURCE_BINDINGS.json").read_text(encoding="utf-8"))
        self.assertTrue(bindings["reference_only"])
        self.assertEqual(len(bindings["source_entries"]), 76)
        self.assertFalse(bindings["runtime_imports_of_old_project_code"])

    def test_CLO06_model_types_never_live(self):
        pin, snap, obs = model_bundle()
        items = [pin, obs, obs.crypto, obs.retirement, initial_model(expectation()),
                 validate_transcript_model(pin, snap, obs), validate_scm_trace_model(journal_bytes(expectation()), expectation()),
                 plan_layout(layout_spec()), validate_catalog(plan_layout(layout_spec()), catalog())]
        for item in items:
            with self.subTest(type=type(item).__name__):
                self.assertEqual(item.evidence_domain, DOMAIN)
                self.assertIs(item.runtime_authorized, False)
                self.assertIs(item.crypto_verified, False)
        self.assertFalse(validate_catalog(plan_layout(layout_spec()), catalog()).filesystem_verified)

    def test_REG09_protocol_file_matches_code(self):
        from ..wsb01_contract import canonical_json_bytes, protocol_definition, schema_sha256
        import hashlib
        raw = (ROOT / "PROTOCOL.json").read_bytes()
        self.assertEqual(raw, canonical_json_bytes(protocol_definition()))
        self.assertEqual(hashlib.sha256(raw).hexdigest(), schema_sha256())

    def test_REG10_initializers_empty(self):
        self.assertEqual((ROOT / "__init__.py").read_bytes(), b"")
        self.assertEqual((ROOT / "tests" / "__init__.py").read_bytes(), b"")
