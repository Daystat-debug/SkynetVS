"""Safety and transfer properties of offline retrieval. Does not start a model."""
import ast
from hashlib import sha256
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skynet_source_language as language
import skynet_goal_facets as facets


def effect(owner, text):
    node = ast.parse(f"def {owner}():\n return {text!r}").body[0]
    stmt = node.body[0]
    return language.goals.Effect(SimpleNamespace(node=node), stmt, stmt.value, text, "")


class SourceLanguage(unittest.TestCase):
    def test_source_identity(self):
        card = effect("first", "opaque name")
        key = language.descriptor(card)
        card.stmt.lineno += 10
        self.assertEqual(key, language.descriptor(card))
        card.guard = "x > 0"
        self.assertNotEqual(key, language.descriptor(card))

    def test_alignment_requires_independent_descriptors(self):
        entries = ["disk read", "disk full"]
        captions = {sha256(s.encode()).hexdigest(): "диск" for s in entries}
        self.assertEqual(language.vocabulary(entries,captions), {"disk":["диск"]})

    def test_literal_and_ambiguity(self):
        cards = [effect(fn,"Дежурное сообщение") for fn in ("first","second")]
        with self.assertRaises(language.goals.NeedChoice):
            language.choose("Где «Дежурное»?",cards,"explore")
        with self.assertRaisesRegex(language.goals.route.control.Gap,"missing"):
            language.candidates("«Другая запись»",cards,"explore")

    def test_multi_operand_and_conjunction_inside_literal(self):
        self.assertEqual(language.relation("Есть ли вызов между «А и Б» и «В»?"), ["«А и Б»","«В»"])
        with self.assertRaisesRegex(language.goals.route.control.Gap,"ambiguous"):
            language.relation("Есть ли вызов между первым и вторым и третьим?")
        self.assertIsNone(language.relation("Обязательно ли исполняется вызов между ветками?"))
        with self.assertRaisesRegex(language.goals.route.control.Gap,"ambiguous"):
            language.candidates("«А» после завершения потока", [],"explore")

    def test_no_new_authority_or_unverified_number(self):
        self.assertIsNone(language.operation("Запусти запись «известный сигнал»"))
        cards = [effect("a","розовый квадрат"), effect("b","чёрный треугольник"), effect("c","белый круг")]
        with self.assertRaisesRegex(language.goals.route.control.Gap,"missing"):
            language.choose("Где возвращается розовый квадрат 777?",cards,"syntax")

    def test_match_independent_facets(self):
        cards=[effect("a","disk quota limit"),effect("b","network quota error"),effect("c","disk busy"),
               effect("d","light on"),effect("e","light off"),effect("f","network busy")]
        self.assertIs(facets.resolve(cards,[["disk"],["quota"]],"",False),cards[0])
        with self.assertRaisesRegex(language.goals.route.control.Gap,"ambiguous"):
            facets.resolve(cards,[["quota"],["quota"]],"",False)

    def test_model_may_only_return_data(self):
        for value in ('{"op":"exec","a":{},"b":null}', '{"op":"via","a":{},"b":null,"file":"x"}',
                      '{"op":"when","a":{"object":"p/x","detail":"b"},"b":null}',
                      '{"op":"where","a":{"object":"a","detail":"b"},"b":null}'):
            with self.subTest(value=value),self.assertRaises(language.goals.route.control.Gap):
                facets.specification("Когда появляется результат?",lambda *_:(value,{"finish_reason":"stop"}))

    def test_optional_slot_only_for_unary_requests(self):
        for op in ("when","between"):
            obj = language.json.dumps(dict(op=op,a=dict(object="door hatch",detail="closed shut")))
            read = lambda *_:(obj,{"finish_reason":"stop"})
            if op=="when":
                self.assertEqual(facets.specification("Когда заперт люк?",read,True)[0],"when")
            else:
                with self.assertRaises(language.goals.route.control.Gap):
                    facets.specification("Связаны ли места?",read,True)


if __name__ == "__main__":
    unittest.main()
