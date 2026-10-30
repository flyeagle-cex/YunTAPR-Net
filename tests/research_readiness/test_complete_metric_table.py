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

    def test_archived_group_retains_saved_values(self):
        x=dict(model='B7',seed='2030',arm='E0',group='all',N_valid='10',N_rain='3',TP='2',FP='1',FN='1',TN='6',Brier='.12',AUROC='.8',AP='.6',conditional_pinball='.1',q32_coverage='.95',**dict.fromkeys(m.RATE_FIELDS,'.5'))
        known={'B7_s2030':dict(n_valid=10)}
        y=m.archived_group(x,known)
        self.assertEqual(y['values']['Brier'],.12);self.assertEqual(y['rates'],[.5]*4)
        with self.assertRaises(ValueError):m.archived_group(x,{})
        with self.assertRaises(ValueError):m.archived_group(x,{'B7_s2030':dict(n_valid=11)})

    def test_old_best_proxy_cannot_enter_main_comparison(self):
        x=dict(model='B0',seed='2026',artifact_generation='PHASE_A_BEST_NOT_MAIN_LAST',population='old',MAE_mm_h='.25',RMSE_mm_h='.8',Bias_mm_h='.02',Pearson_CC='NOT_AVAILABLE')
        y=m.historical_proxy(x)
        self.assertFalse(y['eligible_for_main_comparison']);self.assertIsNone(y['cc'])
        self.assertEqual(y['status'],'HISTORICAL_DIFFERENT_WEIGHT_NOT_MAIN_E9')


if __name__=='__main__':unittest.main()
