"""Only the new consolidation boundary; old125 inference formula tests inherited."""
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
s=importlib.util.spec_from_file_location('complete_metric_table',ROOT/'tools/research_readiness/assemble_complete_metrics.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)


class TableTests(unittest.TestCase):
    def test_far_is_not_fpr(self):
        x=m.ratios(dict(TP=2,FP=1,FN=3,TN=4,N=10))
        self.assertAlmostEqual(x['FAR'],1/3);self.assertNotEqual(x['FAR'],1/5);self.assertAlmostEqual(x['HSS'],.2)
    def test_zero_and_missing_distinct(self):
        self.assertEqual(m.num('0'),0);self.assertIsNone(m.num(''))
        x=m.ratios(dict(TP=0,FP=0,FN=2,TN=8,N=10));self.assertEqual(x['POD'],0);self.assertIsNone(x['FAR'])
    def test_population_mismatch_rejected(self):
        with self.assertRaises(ValueError):m.ratios(dict(TP=1,FP=2,FN=3,TN=4,N=11))
    def test_saved_reliability_bins(self):
        bins=[dict(n=10,rain=i) for i in range(10)]
        x=m.counts(dict(reliability=bins,n_valid=100,n_rain=45))
        self.assertEqual(x,dict(TP=35,FP=15,FN=10,TN=40,N=100));m.ratios(x)


if __name__=='__main__':unittest.main()
