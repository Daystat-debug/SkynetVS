import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skynet_event_meaning as meaning


class Events(unittest.TestCase):
    def test_roles_polarity_and_ties(self):
        event = meaning.decode("wind|push|sail|?|+")
        reversed_roles = meaning.decode("sail|push|wind|?|+")
        negative = meaning.decode("wind|push|sail|?|-")
        choices = {2: negative, 5: reversed_roles, 7: event}
        selected, _, reasons = meaning.decide(event, choices)
        self.assertEqual(selected, 7)
        self.assertEqual(reasons, {2: "opposite_polarity", 5: "reversed_roles", 7: "covers"})
        self.assertIsNone(meaning.decide(event, choices, unordered=True)[0])
        self.assertIsNone(meaning.decide(event[:-1] + ["?"], choices)[0])
        self.assertIsNone(meaning.decide(event, {**choices, 9: None})[0])
        self.assertEqual(meaning.compare(event, meaning.decode("air|push|sail|?|+")), "different_terms")

    def test_extractor_integrity(self):
        for raw, stop, why in [('{"9":"x"}', "stop", "keys_format"),
                               ('{"0":[4]}', "stop", "field_format"),
                               ('{}', "length", "generation_length"), ('{', "stop", "json_format")]:
            rows, status = meaning.extract({"0": "x"}, meaning.SOURCE,
                lambda *_: (raw, {"finish_reason": stop}), json.loads)
            self.assertEqual(status, why)
            self.assertFalse(rows.get("0"))


if __name__ == "__main__":
    unittest.main()
