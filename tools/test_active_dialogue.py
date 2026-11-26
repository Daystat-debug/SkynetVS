"""Boundary and dialogue controls, independent of the transfer panel."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
import eval_active_dialogue as evaluation

d = evaluation.dialog
ev = evaluation.ev


class Controls(unittest.TestCase):
    def test_differences(self):
        self.assertEqual(d.choice.difference(["канал открыт сейчас","канал закрыт сейчас"]),["открыт","закрыт"])
        self.assertIsNone(d.choice.resolve_reply("канал",["канал открыт","канал закрыт"]))
        self.assertIsNone(d.choice.resolve_reply("не открыт",["канал открыт","канал закрыт"]))

    def test_simulator(self):
        user = dict(part=0,axis="object",visible="лампа",reply="речь о лампе")
        prompt = dict(part=0,axis="object",options=["лампа A","лампа B"])
        self.assertEqual(evaluation.simulate(prompt,user,"choice"),"ни один")
        self.assertEqual(evaluation.simulate(dict(prompt,axis="requirement"),user,"free"),"не знаю")

    def test_controlled_head(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/"repo"
            base = "f0a23772fd15c50c00a87383cf9e6f641cc120a7"
            ev.pilot.git("clone","--quiet","--local","--no-checkout",str(ev.pilot.ROOT),str(root))
            raw,_ = ev.old.blob(root,base,ev.old.RANK)
            ev.archive.prior_eval.checkout_fixture(root,base,raw+"\ndef control_flag(x):\n    if x:\n        return 'канал слева'\n    return 'канал справа'\n".encode())
            q = "Где записано «M127_INPUT_TOO_LARGE»? Где записано «канал»?"
            for check in ("select","scope","receipt","head"):
                session = d.Dialogue(root)
                first,prompt = session.start(q)
                self.assertEqual(first["state"],"partial")
                self.assertEqual(prompt["part"],1)
                if check == "receipt":
                    session.first["parts"][0]["claims"][0]["refs"][0]["blob_oid"] = "0"*40
                if check == "head":
                    ev.archive.set_head(root,base)
                reply = "outside/private.py" if check == "scope" else "#1"
                out,reason,_ = session.resume(reply)
                self.assertEqual(reason,dict(select="explicit_choice",scope="invalid_reply",receipt="invalid_reference",
                                             head="stale_snapshot")[check])
                if check=="select":
                    self.assertEqual(out["state"],"answered")
                if check in ("receipt","head"):
                    self.assertFalse(out["parts"])
                with self.assertRaises(ValueError):
                    session.resume("#2")


if __name__ == "__main__":
    unittest.main()
