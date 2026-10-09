"""Pure synthetic analysis tests: zero model forwards/backwards/optimizer steps."""
import unittest
import tempfile
from pathlib import Path
import numpy as np
from sufficient_stats import *

class StatisticsTests(unittest.TestCase):
    def test_2025_rejected_before_any_io(self):
        with self.assertRaises(ValueError): date_index('2025-03-01T00:00:00+00:00')
    def test_utc_required(self):
        with self.assertRaises(ValueError): date_index('2024-03-01T00:00:00+08:00')
    def test_date_blocks_and_complete_month_range(self):
        self.assertEqual(date_index('2024-03-08T23:30:00+00:00') // 7, 1)
        self.assertEqual(date_index('2024-10-31T23:30:00+00:00'), 244)
        with self.assertRaises(ValueError): date_index('2024-11-01T00:00:00+00:00')
    def test_exact_bf16_scores_no_rounding(self):
        np.testing.assert_equal(score_codes([0,.25,.5,1]), [0,16000,16128,16256])
        with self.assertRaises(ValueError): score_codes([.123456])
    def test_tied_rank_auc_ap(self):
        c=np.zeros((4,2)); c[0]=[1,0]; c[2]=[1,1]; c[3]=[0,1]
        np.testing.assert_allclose(ranking(c), [.875,5/6], atol=1e-15,rtol=0)
    def test_single_class_auc_is_undefined(self):
        c=np.array([[0,2],[0,1]])
        self.assertTrue(np.isnan(ranking(c)[0])); self.assertEqual(ranking(c)[1],1)
    def test_fixed_reliability_boundary_and_one(self):
        np.testing.assert_equal(probability_bin(np.array([0,.1,.9,1])),[0,1,9,9])
    def test_truth_rate_boundary_is_right_closed(self):
        np.testing.assert_equal(rate_bin(np.array([.1,1,5,10,50,51]),np.array([False,True,True,True,True,True])),[0,1,2,3,6,7])
    def test_global_pooling_is_not_mean_of_subgroup_means(self):
        a=np.zeros(SIZE); b=np.zeros(SIZE); a[:5]=[2,1,.1,.2,.4]; b[:5]=[8,1,.8,.2,.8]
        self.assertAlmostEqual(metrics(a+b,np.array([[1,1]]))[0],.13)
        self.assertNotAlmostEqual(metrics(a+b,np.array([[1,1]]))[0],(metrics(a,np.array([[1,1]]))[0]+metrics(b,np.array([[1,1]]))[0])/2)
    def test_observer_units_uniqueness_and_no_tensor_modification(self):
        mask=np.zeros(10000,bool); mask[:3430]=True; mask=mask.reshape(100,100)
        q=np.broadcast_to(.2+np.arange(32)*.01,(2,100,100,32)).copy()
        q[:,0,0]=np.linspace(1,8,32)
        p=np.full((2,100,100),.5); y=np.ones_like(p); rainy=y>.1; valid=np.ones_like(p,bool)
        before=q.copy(); records=[{'sample_id':str(i),'window_start':'2024-03-01T00:30:00+00:00','slot_5_nominal':'2024-03-01T00:50:00+00:00'} for i in range(2)]
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent / 'fixtures') as tmp:
            assert Path(tmp).resolve().is_relative_to((Path(__file__).parent / 'fixtures').resolve())
            obs=Observer(mask,tmp); obs.add_arrays(q,p,np.zeros_like(p),y,rainy,valid,records)
            report=obs.save()
            self.assertEqual(report['threshold_scenes'][0][4],2)
            self.assertEqual(report['threshold_unique_grid_cells'][0][4],1)
            self.assertEqual(report['threshold_scene_pixel_tau_and_any_counts'][0][4][1],2)
            self.assertGreater(report['threshold_scene_pixel_tau_and_any_counts'][0][4][0],2)
            self.assertEqual(obs.daily[0,0,0],6860)
            self.assertEqual(obs.scores[:,0].sum(),6860)
            self.assertEqual(report['independent_precipitation_events'],'NOT_ESTIMABLE_NO_PREDEFINED_EVENT_CATALOGUE')
        np.testing.assert_equal(q,before)
    def test_numerical_failure_never_repairs(self):
        mask=np.zeros(10000,bool); mask[:3430]=True
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent / 'fixtures') as tmp:
            assert Path(tmp).resolve().is_relative_to((Path(__file__).parent / 'fixtures').resolve())
            obs=Observer(mask,tmp)
            with self.assertRaises(FloatingPointError): obs.add_arrays(np.ones((1,100,100,32)),None,None,None,None,None,[{}])

if __name__=='__main__': unittest.main(verbosity=2)
