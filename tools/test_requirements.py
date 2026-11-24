import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
import skynet_requirements as req


class Requirements(unittest.TestCase):
    def test_blind_to_literal_and_rejects_extra_authority(self):
        def select(prompt,text):
            self.assertEqual(text,"Где ОБЪЕКТ?")
            return json.dumps({"need":["site"],"path":"other.py"}),{"finish_reason":"stop"}
        with self.assertRaises(req.Gap):
            req.interpret("Где «marker»?",select)

    def test_unanswered_condition(self):
        meta=dict(required=["site","condition"],supported=["site"],missing=["condition"],line=8,owner="f")
        rows=[dict(kind="site",anchors=[dict(lines=[8,8])])]
        req.verify_receipts(meta,rows)
        with self.assertRaises(req.observed.route.arguments.host.Rejected):
            req.verify_receipts(dict(meta,missing=[]),rows)

    def test_control_proof_for_wrong_owner(self):
        meta=dict(required=["site","condition"],supported=["site","condition"],missing=[],line=8,owner="f")
        rows=[dict(kind="site",anchors=[dict(lines=[8,8])]),dict(kind="condition",control=dict(function="g"))]
        with self.assertRaises(req.observed.route.arguments.host.Rejected):
            req.verify_receipts(meta,rows)


if __name__=="__main__":
    unittest.main()
