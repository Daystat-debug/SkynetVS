import unittest
from dataclasses import replace
from ..wsb01_policy import CoreError
from ..wsb01_layout import (LayoutSpec, plan_layout, validate_catalog, ArtifactObservation)
from .test_contract import model_bundle, h


def layout_spec():
    base = "C:\\SkynetVSLabStage\\" + "1" * 32
    return LayoutSpec("1" * 32, *(base + "\\" + x for x in ("Input", "Runtime", "Control", "Output")),
                      "C:\\Project\\SkynetVS", "C:\\Users\\User\\Downloads", "C:\\AcceptedEvidence",
                      ("C:\\Users\\User\\Secrets",))


def catalog():
    _, snap, _ = model_bundle()
    return tuple(ArtifactObservation(x.name, len(x.data), h(x.data), "regular", False, False, 1)
                 for x in snap.before_retirement)


class LayoutTests(unittest.TestCase):
    def test_LAY01_permissions(self):
        plan = plan_layout(layout_spec())
        self.assertEqual(tuple(x.guest_writable for x in plan.mappings), (False, False, False, True))
        self.assertFalse(plan.filesystem_verified)
        self.assertTrue(validate_catalog(plan, catalog()).valid)
        bad = replace(plan, mappings=(replace(plan.mappings[0], guest_writable=True),) + plan.mappings[1:])
        self.assertFalse(validate_catalog(bad, catalog()).valid)

    def test_LAY02_forbidden_roots(self):
        for path in ("C:\\Project\\SkynetVS", "C:\\Project\\SkynetVS\\sub", "C:\\Users\\User\\Downloads",
                     "C:\\Users\\User", "C:\\Lab\\.git", "C:\\Lab\\.venv", "C:\\Users\\User\\Secrets"):
            with self.subTest(path=path), self.assertRaises(CoreError):
                plan_layout(replace(layout_spec(), input_root=path))
        # A dedicated child of Downloads is not a mapping of all Downloads.
        good = replace(layout_spec(), input_root="C:\\Users\\User\\Downloads\\DedicatedInput")
        self.assertIsNotNone(plan_layout(good))

    def test_LAY03_alias_paths(self):
        for path in ("C:\\A\\..\\B", "C:\\A\\.\\B", "C:\\A\\B ", "C:\\A\\B.", "C:\\A\\file:stream",
                     "\\\\server\\share", "\\\\?\\C:\\Lab", "C:/Lab/Input", "C:\\A\\CON.txt", "C:\\A\\LPT¹",
                     "C:\\A\\COM1", "C:\\A\\PROGRA~1", "C:\\A\\\\B", "C:\\"):
            with self.subTest(path=path), self.assertRaises(CoreError):
                plan_layout(replace(layout_spec(), input_root=path))
        with self.assertRaises(CoreError):
            plan_layout(replace(layout_spec(), runtime_root=layout_spec().input_root.lower().replace("c:", "C:")))

    def test_LAY04_overlap(self):
        spec = layout_spec()
        for path in (spec.input_root, spec.control_root + "\\Child", "C:\\AcceptedEvidence\\Nested"):
            with self.subTest(path=path), self.assertRaises(CoreError):
                plan_layout(replace(spec, output_root=path))

    def test_LAY05_catalog_membership(self):
        plan, entries = plan_layout(layout_spec()), catalog()
        for bad in (entries[:-1], entries + (entries[0],),
                    entries + (ArtifactObservation("failure.json", 10, h(b"x"), "regular", False, False, 1),),
                    (replace(entries[0], name="READY.JSON"),) + entries[1:],
                    (replace(entries[0], name="../ready.json"),) + entries[1:]):
            with self.subTest(names=[x.name for x in bad]):
                self.assertFalse(validate_catalog(plan, bad).valid)

    def test_LAY06_metadata_and_limits(self):
        entries, plan = catalog(), plan_layout(layout_spec())
        for patch in ({"kind": "directory"}, {"reparse": True}, {"symlink": None}, {"link_count": None},
                      {"link_count": 2}, {"link_count": True}, {"size": True}, {"size": -1}, {"size": 65537},
                      {"sha256": "invalid"}):
            with self.subTest(patch=patch):
                self.assertFalse(validate_catalog(plan, (replace(entries[0], **patch),) + entries[1:]).valid)
        self.assertFalse(validate_catalog(plan, entries * 5).valid)
