from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
import eval_description_match as lab


class Descriptions(unittest.TestCase):
    def test_unknown_negative_and_unreadable(self):
        def oracle(text,event):
            row=lab.fit.annotated(text,event)
            return lab.m.interpret(row["seq"],{"required":{}},tags=row["tags"],concepts=row["concepts"])[1]
        a=oracle("Экран{a} светится{r}",["экран","свет",None,None,"+"])
        b=oracle("Экран{a} не{n} светится{r}",["экран","свет",None,None,"-"])
        u=oracle("Неясно{u}, светится{r} ли экран{a}",["экран","свет",None,None,"?"])
        self.assertEqual(lab.m.compare(a,b),("different","opposite_polarity"))
        self.assertEqual(lab.m.compare(u,b),("unknown","unknown_property"))
        self.assertEqual(lab.m.compare({**a,"r":[]},b)[0],"unknown")
        self.assertIsNone(lab.m.select([("equal","aligned")]*2))

    def test_fit_and_host_scope(self):
        model=lab.m.models()
        self.assertEqual(lab.fit.build(),model)
        self.assertEqual(model["selected"],"desc_mixed")
        def no_calls(*args):
            self.fail("unexpected provider")
        out=lab.old.ev.loop.investigate("Где в modules/private.py нужная строка?",lab.old.ev.pilot.ROOT,
                                        discovery=model["selected"],select=no_calls)
        self.assertEqual(out["reason"],"out_of_scope")


if __name__=="__main__":
    unittest.main()
