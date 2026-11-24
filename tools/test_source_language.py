"""Safety and transfer properties of offline retrieval. Does not start a model."""
import ast
from hashlib import sha256
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skynet_source_language as language


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


if __name__ == "__main__":
    unittest.main()
