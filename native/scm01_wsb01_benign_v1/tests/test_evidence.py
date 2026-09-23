"""EVIDENCE01-08: structural candidates and negative native verdict admission."""
import unittest
from dataclasses import replace
from . import test_contract as f
from . import test_windows_bindings as w
from .. import benign_contract as c
from .. import benign_evidence as e
from .. import benign_windows_crypto as crypto
from .. import benign_windows_fs as fs
from .. import benign_windows_session as ps


class EvidenceTests(unittest.TestCase):
    def test_EVIDENCE01_roundtrip_candidate(self):
        expected, raw = f.full_fixture(); candidate = e.validate_terminal(expected, raw)
        self.assertTrue(candidate.completed); self.assertTrue(candidate.structural_only)
        expected, raw = f.full_fixture(failure=True)
        self.assertFalse(e.validate_terminal(expected, raw).completed)

    def test_EVIDENCE02_ready_proof_of_possession_not_origin(self):
        expected, raw = f.ready_fixture(); pin = e.validate_ready(expected, raw)
        receipt = crypto._CryptoEngine(w.FakeCrypto()).verify(pin.key, c.READY_DOMAIN, pin.raw, pin.signature)
        self.assertEqual(receipt.evidence_domain, 'OFFLINE_MODEL')
        self.assertFalse(crypto.is_native_receipt(receipt, c.READY_DOMAIN, pin.raw, pin.key, pin.signature))
        self.assertFalse(hasattr(pin, 'source_origin_verified'))

    def test_EVIDENCE03_pinned_ready_cannot_change(self):
        expected, raw = f.full_fixture()
        raw['ready.sig'] = (2).to_bytes(32, 'big') * 2
        mark = c.parse_benign('ready_commit', raw['ready.commit.json']).fields
        mark['ready_signature_sha256'] = c.sha(raw['ready.sig'])
        raw['ready.commit.json'] = c.serialize_benign('ready_commit', mark)
        with self.assertRaises(c.BenignError): e.validate_terminal(expected, raw)

    def test_EVIDENCE04_cross_signing_domain(self):
        api = w.FakeCrypto(); engine = crypto._CryptoEngine(api)
        r = engine.verify(f.KEY, c.READY_DOMAIN, b'x', f.SIG)
        self.assertNotEqual(crypto.prehash(c.READY_DOMAIN, b'x'), crypto.prehash(c.TERMINAL_DOMAIN, b'x'))
        self.assertFalse(crypto.is_native_receipt(r, c.TERMINAL_DOMAIN, b'x', f.KEY, f.SIG))
        with self.assertRaises(c.BenignError): crypto.prehash(b'OFFLINE_MODEL', b'x')

    def test_EVIDENCE05_journal_binding_sequence_clock(self):
        exp, original = f.full_fixture()
        for field, value in (('sequence', 0), ('guest_monotonic_ns', 0)):
            raw = dict(original); lines = raw['journal.jsonl'].splitlines(keepends=True)
            lines[1] = f.rewrite(lines[1], field, value); journal = b''.join(lines)
            raw['journal.jsonl'] = journal
            term = c.parse_benign('terminal', raw['terminal.json']).fields
            term.update(journal_bytes=len(journal), journal_sha256=c.sha(journal))
            raw['terminal.json'] = c.serialize_benign('terminal', term); f.refresh_terminal_mark(raw)
            with self.subTest(field=field), self.assertRaises(c.BenignError): e.validate_terminal(exp, raw)

    def test_EVIDENCE06_inventory_limits_failure(self):
        exp, raw = f.full_fixture()
        for extra in ('failure.json', 'unknown.txt'):
            with self.subTest(extra=extra), self.assertRaises(c.BenignError): e.validate_terminal(exp, dict(raw, **{extra: b'x'}))
        broken = dict(raw); broken['journal.jsonl'] = b'x' * 65537
        with self.assertRaises(c.BenignError): e.validate_terminal(exp, broken)
        broken = dict(raw); del broken['terminal.commit.json']
        with self.assertRaises(c.BenignError): e.validate_terminal(exp, broken)

    def test_EVIDENCE07_postexit_required_no_dictionary_receipts(self):
        exp, raw = f.full_fixture()
        for receipts, snapshots in (({}, (raw, raw)),
                                   (e.NativeReceipts((), object(), ()), (raw, raw))):
            with self.subTest(receipt=type(receipts)), self.assertRaises(c.BenignError):
                e.finalize_lab(exp, receipts, snapshots)
        changed = dict(raw); changed['terminal.sig'] = (3).to_bytes(32, 'big') * 2
        self.assertNotEqual(e.snapshot_digest(raw), e.snapshot_digest(changed))

    def test_EVIDENCE08_fake_snapshots_never_native(self):
        exp, raw = f.full_fixture(); api, engine, root = w.root_fs()
        for name, data in raw.items(): api.put(root.path + '\\' + name, data)
        snap = fs.capture_snapshot(root, c.FILE_CAPS, 'before_retirement')
        self.assertFalse(fs.is_native_snapshot(snap, 'before_retirement'))
        native = e.NativeReceipts((), ps.RetirementObservation(f.RID, f.NONCE, f.BOOT, f.SESSION,
                       True, False, True, (0, 250000000, 500000000)), ())
        with self.assertRaises(c.BenignError): e.finalize_lab(exp, native, (snap, snap))
        root.close()
