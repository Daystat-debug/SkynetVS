"""LEDGER01-08; durable workflow failures simulated in memory, never write user files."""
import unittest
from . import test_contract as f
from .. import benign_contract as c
from .. import benign_ledger as l
from ..benign_runtime_gate import RuntimeClosed


class FakeStore:
    def __init__(self): self.data = {}; self.locked = False; self.fail = ''; self.calls = []
    def acquire(self):
        if self.locked: raise RuntimeError('exclusive lock held')
        self.locked = True; self.calls.append('lock')
    def release(self): self.locked = False; self.calls.append('unlock')
    def names(self): return tuple(sorted(self.data))
    def read(self, name): return self.data[name]
    def create(self, name, raw):
        self.calls.append(name)
        if name in self.data: raise FileExistsError(name)
        if self.fail and self.fail in name:
            self.data[name] = raw[:len(raw) // 2]
            raise OSError('simulated partial write/flush uncertainty')
        self.data[name] = raw


def descriptor(): return l.GrantDescriptor(f.request(), f.BOOT)


def granted():
    store = FakeStore(); engine = l._LedgerEngine(store); g = engine.reserve(descriptor())
    return store, engine, g


class LedgerTests(unittest.TestCase):
    def test_LEDGER01_no_public_issuer(self):
        for permit in (None, True, object(), {'approved': True}):
            with self.subTest(permit=type(permit)), self.assertRaises(RuntimeClosed):
                l.reserve_grant(descriptor(), object(), permit)

    def test_LEDGER02_json_is_not_descriptor_authority(self):
        engine = l._LedgerEngine(FakeStore())
        for bad in ({'approved': True}, f.request(), True):
            with self.subTest(bad=type(bad)), self.assertRaises(c.BenignError): engine.reserve(bad)

    def test_LEDGER03_exclusive_one_create(self):
        store, first, grant = granted(); second = l._LedgerEngine(store)
        with self.assertRaises(RuntimeError): second.reserve(descriptor())
        self.assertEqual(sum(n.endswith('.consumed.json') for n in store.calls), 1)
        first.close()
        with self.assertRaises(FileExistsError): l._LedgerEngine(store).reserve(descriptor())
        self.assertEqual(len(store.data), 1)

    def test_LEDGER04_partial_consumption_is_poisoned(self):
        store = FakeStore(); store.fail = '.consumed.json'; engine = l._LedgerEngine(store)
        with self.assertRaises(OSError): engine.reserve(descriptor())
        self.assertTrue(engine.grant.poisoned); self.assertFalse(store.locked)
        store.fail = ''
        with self.assertRaises(c.BenignError): l._LedgerEngine(store).reserve(descriptor())

    def test_LEDGER05_launch_intent_precedes_attempt(self):
        store, engine, grant = granted(); engine.launch_intent(grant)
        self.assertTrue(grant.launch_attempted)
        self.assertLess(store.calls.index(f.GRANT + '.consumed.json'), store.calls.index(f.RID + '.launch.intent.json'))
        with self.assertRaises(c.BenignError): engine.launch_intent(grant)
        engine.close()

    def test_LEDGER06_authorization_once_after_launch(self):
        exp, raw = f.full_fixture(); store, engine, grant = granted()
        with self.assertRaises(c.BenignError): engine.authorization_intent(grant, exp.authorization, exp.authorization_commit)
        engine.launch_intent(grant); engine.authorization_intent(grant, exp.authorization, exp.authorization_commit)
        with self.assertRaises(c.BenignError): engine.authorization_intent(grant, exp.authorization, exp.authorization_commit)
        engine.close()

    def test_LEDGER07_publication_unknown_not_reissued(self):
        exp, _ = f.full_fixture(); store, engine, grant = granted(); engine.launch_intent(grant)
        engine.authorization_intent(grant, exp.authorization, exp.authorization_commit)
        engine.publication_failed(grant)
        self.assertTrue(grant.publication_unknown); self.assertTrue(grant.poisoned)
        with self.assertRaises(c.BenignError): engine.authorization_intent(grant, exp.authorization, exp.authorization_commit)
        with self.assertRaises(c.BenignError): engine.outcome(grant, 'PASS_LAB_ONLY', True)
        engine.outcome(grant, 'UNKNOWN', False)

    def test_LEDGER08_restart_unresolved_blocks_different_grant(self):
        store, engine, grant = granted(); engine.launch_intent(grant); engine.close()
        other = l.GrantDescriptor(f.request(run_id='a' * 32, grant='b' * 32), f.BOOT)
        with self.assertRaises(c.BenignError): l._LedgerEngine(store).reserve(other)
        store.data[f.RID + '.outcome.json'] = c.canonical({'run_id': f.RID, 'retirement_confirmed': False})
        with self.assertRaises(c.BenignError): l._LedgerEngine(store).reserve(other)
