"""New analysis-only acceptance tests; no models, checkpoints or observations."""
import csv,unittest
from common import OUT,ROOT,load,read,sha
from analyze import bootstrap_metrics,np

class AnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d=read(OUT/'ANALYSIS_DATA.json');cls.audit=read(OUT/'RECOMPUTATION_AUDIT.json')
    def test_01_all_54_receipts(self):
        self.assertEqual(self.audit['validated_epoch_receipts'],54)
        self.assertTrue(self.audit['direct_draw_pooling_verified'])
    def test_02_all_source_hashes(self):
        for name,expected in self.audit['sources'].items():
            self.assertEqual(sha((ROOT/name).read_bytes()),expected,name)
    def test_03_pooled_ratio_not_block_mean(self):
        report={'blocks':[dict(n_valid=1,n_rain=1,brier_sum=1,covered=[1]*32),dict(n_valid=9,n_rain=3,brier_sum=0,covered=[0]*32)]}
        r=bootstrap_metrics(report,np.array([[1,1],[2,0]]))
        np.testing.assert_array_equal(r['brier'],[.1,1.])
        np.testing.assert_array_equal(r['q32_absolute_error'],[abs(.25-.984375),abs(1-.984375)])
    def test_04_zero_rain_rejected(self):
        with self.assertRaisesRegex(ValueError,'DENOMINATOR'):
            bootstrap_metrics({'blocks':[dict(n_valid=1,n_rain=0)]},np.ones((1,1)))
    def test_05_invalid_weights_rejected(self):
        for w in (np.ones((1,2)),np.array([[-1]]),np.array([[float('nan')]])):
            with self.assertRaisesRegex(ValueError,'MULTIPLICITIES'):
                bootstrap_metrics({'blocks':[dict(n_valid=1,n_rain=1)]},w)
    def test_06_final_csv_full_precision(self):
        with (OUT/'tables/final_metrics.csv').open(encoding='utf-8') as f:rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),6)
        for a,b in zip(rows,self.d['final']):self.assertEqual(float(a['brier']),b['brier'])
    def test_07_32_coverage_and_denominator(self):
        self.assertEqual(len(self.d['quantiles']),192)
        for r in self.d['quantiles']:
            self.assertEqual(r['n_rain'],4496600)
            self.assertEqual(r['coverage'],r['covered']/r['n_rain'])
            self.assertEqual(r['tau'],(r['index']-.5)/32)
    def test_08_exactly_four_exploratory_contrasts(self):
        self.assertEqual(len(self.d['contrasts']),4)
        self.assertTrue(all(not r['confirmatory'] and r['replicates']==2000 for r in self.d['contrasts']))
    def test_09_all_dry_empty_bins_not_invented(self):
        for r in self.d['reliability']:
            if r['n']==0:self.assertIsNone(r['mean_probability']);self.assertIsNone(r['frequency'])
    def test_10_no_new_training_or_raw_reads(self):
        for key in ('new_optimizer_steps','raw_data_reads','model_inferences'):self.assertEqual(self.audit[key],0)
    def test_11_primary_sha_only_audit(self):
        a=read(OUT/'CHECKPOINT_PAYLOAD_AUDIT.json')
        self.assertEqual(len(a['primary']),6);self.assertTrue(a['no_deserialization'])
        self.assertTrue(all(r['status']=='PASS' and r['actual_sha256']==r['expected_sha256'] for r in a['primary']))
        self.assertEqual(a['historical_2025_path_attribute_access'],'NOT_INSTRUMENTED')
    def test_12_all_publication_formats(self):
        index=read(OUT/'FIGURE_INDEX.json')['figures']
        self.assertEqual(len(index),10)
        for r in index:
            for ext in ('.svg','.pdf','.png'):
                self.assertGreater((OUT/'figures'/(r['name']+ext)).stat().st_size,1000)
    def test_13_remaining_budget_is_arithmetic_not_permission(self):
        r=self.d['resource'];self.assertEqual(r['remaining_planned_updates'],12*9*5228)
        self.assertFalse(r['training_new_seeds_authorized']);self.assertFalse(r['forecast_is_confidence_interval'])
    def test_14_backup_not_inferred_from_primary(self):
        self.assertEqual(read(OUT/'CHECKPOINT_PAYLOAD_AUDIT.json')['independent_offline_backup'],'NOT_VERIFIED')
    def test_15_registered_endpoint(self):
        for r in load().values():
            self.assertEqual(r['status'],'COMPLETE');self.assertEqual(r['updates'],47052)
            self.assertEqual([e['epoch'] for e in r['epochs']],list(range(1,10)))
    def test_16_original_strata_counts(self):
        expected=[2764086,1470675,207616,46735,6053,1366,69]
        for m in ('B0','B1'):
            for a in ('E0','E1','E2'):
                self.assertEqual([r['n'] for r in self.d['strata'] if r['model']==m and r['arm']==a],expected)

if __name__=='__main__':unittest.main(verbosity=2)
