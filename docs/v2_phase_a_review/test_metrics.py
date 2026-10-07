"""CPU-only synthetic checks, no sources, checkpoints, model, backward or optimizer."""
import math
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
EXEC = Path(__file__).resolve().parents[3] / 'YunTAPR-Net-v2-phase-a-execution'
sys.path[:0] = [str(EXEC/'src'), str(Path(__file__).parent)]
import numpy as np
import torch
from metrics import ReviewMetrics
from yuntapr.training.phase_a_validation import grouped_occurrence_metrics
torch.set_num_threads(2)


def fixture(batch=1, rainy=True, high=False):
    target=torch.zeros((batch,1,100,100),dtype=torch.float32)
    mask=torch.zeros_like(target,dtype=torch.bool)
    mask.flatten(2)[:,:,:3430]=True
    if rainy:target.flatten(2)[:,:,:1715]=1.
    p=torch.full_like(target,.5)
    q=(torch.arange(1,33,dtype=torch.float64)/32+math.log1p(.1)).reshape(1,32,1,1).expand(batch,32,100,100).clone()
    if high:q[:,:,70:,:]+=1000.
    out=SimpleNamespace(rain_logit=torch.zeros_like(target),rain_prob=p,conditional_quantiles_log=q)
    return out,target,torch.ones_like(mask),mask


class MetricsTests(unittest.TestCase):
    def test_tied_scores_and_brier(self):
        a=ReviewMetrics();a.add(*fixture());r=a.report()
        self.assertEqual(r['Brier_Score'],.25)
        self.assertEqual(r['AUROC'],.5)
        self.assertEqual(r['Average_Precision'],.5)
        self.assertEqual(r['N_valid'],3430);self.assertEqual(r['N_rain'],1715)
        self.assertEqual(r['conditional_mean_pinball'],r['S_qr']/1715)

    def test_grouped_rank_oracle(self):
        r=grouped_occurrence_metrics([.9,.8,.8,.1],[True,False,True,False])
        self.assertAlmostEqual(r['AUROC'],.875)
        self.assertAlmostEqual(r['Average_Precision'],5/6)

    def test_batch_partition_and_outside_noninterference(self):
        a=ReviewMetrics();a.add(*fixture(2,high=True))
        b=ReviewMetrics();b.add(*fixture());b.add(*fixture())
        for key in ('global_val_core_loss','conditional_mean_pinball','Brier_Score','AUROC','Average_Precision'):
            self.assertAlmostEqual(a.report()[key],b.report()[key],places=14)

    def test_single_class_and_empty(self):
        a=ReviewMetrics();a.add(*fixture(rainy=False));r=a.report()
        self.assertIsNone(r['AUROC']);self.assertIsNone(r['Average_Precision'])
        self.assertIsNone(r['conditional_mean_pinball'])
        with self.assertRaises(FloatingPointError):ReviewMetrics().report()

    def test_no_mutation_rng_or_physical_transform(self):
        f=fixture(high=True);q=f[0].conditional_quantiles_log.clone();rng=torch.get_rng_state().clone()
        a=ReviewMetrics();a.add(*f);r=a.report()
        self.assertTrue(torch.equal(q,f[0].conditional_quantiles_log))
        self.assertTrue(torch.equal(rng,torch.get_rng_state()))
        self.assertFalse(r['physical_materialization']);self.assertEqual(r['OPTIMIZER_STEPS'],0)

if __name__=='__main__':unittest.main(verbosity=2)
