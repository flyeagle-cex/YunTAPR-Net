"""Independent checks against completed real-fit artifacts; never raw pixels."""
from collections import Counter
from datetime import timedelta
import json,unittest
import numpy as np
from yuntapr.contracts.loader import REPO_ROOT,sha256
from yuntapr.data import b1_scientific_freeze as f
from yuntapr.data import b1_temporal_audit as a

def current_run():
    design=f.read(REPO_ROOT/f.DESIGN)
    return (REPO_ROOT/design['researcher_decisions']['path']).parent

class SampleSetArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifact_run=current_run();cls.freeze=f.read(cls.artifact_run/'sample_set_freeze.json')
        cls.frames={}
        for ref in cls.freeze['source_evidence_refs']:
            if '/native_frames/' in ref['path']:
                for r in f.rows(REPO_ROOT/ref['path']):cls.frames[r['nominal']]=r
    def test_formal_exact_counts_order_unique_roles_and_target_identities(self):
        for year,count in f.COUNTS.items():
            b1=f.rows(self.artifact_run/f'b1_{year}_formal_manifest.csv');control=f.rows(self.artifact_run/f'b0_matched_control_{year}_formal_manifest.csv')
            self.assertEqual(len(b1),count);self.assertEqual(len(control),count)
            keys=[r['sample_id'] for r in b1];self.assertEqual(keys,sorted(set(keys)))
            self.assertEqual(keys,[r['sample_id'] for r in control])
            for i,(x,y) in enumerate(zip(b1,control)):
                self.assertEqual(int(x['index']),i);self.assertEqual(x['role'],'Train' if year==2023 else 'Validation')
                self.assertEqual(int(x['year']),year);self.assertEqual(a.utc(x['window_start']).year,year)
                for k in ('window_start','analysis_time','imerg_day_path','imerg_index','imerg_sha256','original_b0_sample_id'):
                    self.assertEqual(x[k],y[k])
                self.assertEqual(int(x['target_valid_yunnan_cells']),3430)
    def test_exact_approved_common_intersection_membership(self):
        prior=REPO_ROOT/f.PRIOR
        for year in f.COUNTS:
            keys=[r['sample_id'] for r in f.rows(self.artifact_run/f'b1_{year}_formal_manifest.csv')]
            for name in ('b1_candidate_eligible','intersection_candidate'):
                self.assertEqual(keys,[r['sample_id'] for r in f.rows(prior/f'{name}_{year}.csv')])
            original={r['sample_id'] for r in f.rows(prior/f'b0_original_eligible_{year}.csv')}
            self.assertTrue(set(keys)<=original)
    def test_six_causal_source_sha_bindings_and_control_latest(self):
        for year in f.COUNTS:
            b1=f.rows(self.artifact_run/f'b1_{year}_formal_manifest.csv');control=f.rows(self.artifact_run/f'b0_matched_control_{year}_formal_manifest.csv')
            for x,y in zip(b1,control):
                fs=f.strict_scene_frames(x['window_start'],self.frames)
                self.assertEqual([x[f'slot_{s}_nominal'] for s in range(6)],[z['nominal'] for z in fs])
                self.assertEqual(x['frame_identity_index_sha256'],f.FRAME_INDEX_SHA)
                self.assertEqual(int(y['selected_slot']),5)
                self.assertEqual(y['b13_relative_path'],fs[5]['relative_path']);self.assertEqual(y['b13_sha256'],fs[5]['source_sha256'])
                self.assertEqual(int(y['b13_bytes']),int(fs[5]['source_bytes']))
    def test_train_exposure_rebuilt_independently_from_six_nominal_columns(self):
        scenes=f.rows(self.artifact_run/'b1_2023_formal_manifest.csv')
        expected=Counter(r[f'slot_{s}_nominal'] for r in scenes for s in range(6))
        plan=f.rows(self.artifact_run/'normalization_train_exposure_plan.csv')
        self.assertEqual({r['nominal']:int(r['scene_slot_exposures']) for r in plan},dict(expected))
        self.assertEqual(sum(expected.values()),62730);self.assertEqual(len(plan),33219)
        self.assertTrue(all(a.utc(r['nominal']).year==2023 and 3<=a.utc(r['nominal']).month<=10 for r in plan))
    def test_window_start_targets_excluded_with_no_february_slots(self):
        for year in f.COUNTS:
            b1=f.rows(self.artifact_run/f'b1_{year}_formal_manifest.csv')
            self.assertNotIn(f'{year}-03-01T00:00:00+00:00',{r['sample_id'] for r in b1})
            self.assertEqual(b1[0]['sample_id'],f'{year}-03-01T00:30:00+00:00')
            self.assertTrue(all(3<=a.utc(r[f'slot_{s}_nominal']).month<=10 for r in b1 for s in range(6)))
    def test_signed_references_and_all_1941_historical_files_unchanged(self):
        f.verify_refs(self.freeze['source_evidence_refs']+list(self.freeze['manifests'].values())+
            [self.freeze['normalization_exposure_plan'],self.freeze['design'],self.freeze['training_protocol']])
        self.assertEqual(f.verify_history(self.artifact_run),1941)

class NormalizationArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifact_run=current_run();cls.norm=f.read(cls.artifact_run/'normalization_b1_2023_shared_v1.json')
        cls.execution=f.read(cls.artifact_run/'normalization_execution.json')
    def test_real_completion_and_train_only_exposure_denominator(self):
        n=self.norm
        self.assertEqual(n['status'],'TRAIN_ONLY_FITTED_FROZEN');self.assertTrue(n['ready'])
        self.assertEqual(n['fit_years'],[2023]);self.assertEqual(n['fit_role'],'Train');self.assertEqual(n['fit_scene_count'],10455)
        self.assertEqual(n['valid_pixel_count'],15745292730);self.assertEqual(n['scene_slot_exposures'],62730)
        self.assertEqual(n['unique_frames_read'],33219);self.assertEqual(n['ddof'],0)
        self.assertEqual(n['weighting'],'SCENE_SLOT_EXPOSURE_EACH_NATIVE_PIXEL');self.assertTrue(n['all_six_slots_share_identical_scaler'])
    def test_independent_float32_decode_and_centered_variance_replay(self):
        rows=f.rows(REPO_ROOT/self.norm['histogram']['path'])
        self.assertEqual([int(r['packed_int16_code']) for r in rows],list(range(-32768,32768)))
        hist=np.array([int(r['weighted_count']) for r in rows],dtype=np.int64)
        support=(np.arange(-32768,32768,dtype=np.float32)*np.float32(.01)+np.float32(273.15)).astype(np.float64)
        count=int(hist.sum());mean=float(np.sum(hist*support,dtype=np.float64)/count)
        std=float(np.sqrt(np.sum(hist*(support-mean)**2,dtype=np.float64)/count))
        self.assertEqual(count,self.norm['valid_pixel_count'])
        self.assertAlmostEqual(mean,self.norm['mean_K'],places=11);self.assertAlmostEqual(std,self.norm['std_K'],places=11)
        self.assertEqual(sha256(REPO_ROOT/self.norm['histogram']['path']),self.norm['histogram']['sha256'])
    def test_every_real_frame_read_sha_size_cleanup_and_io_totals(self):
        plan=f.rows(self.artifact_run/'normalization_train_exposure_plan.csv');log=f.rows(self.artifact_run/'normalization_frame_read_log.csv')
        self.assertEqual(len(log),len(plan));total_bytes=0
        for p,r in zip(plan,log):
            for k in ('nominal','source_sha256','source_bytes','scene_slot_exposures'):self.assertEqual(p[k],r[k])
            self.assertEqual(r['cleanup_success'],'True');self.assertEqual(r['temporary_bytes'],r['source_bytes'])
            self.assertGreaterEqual(float(r['copy_seconds']),0);self.assertGreaterEqual(float(r['read_seconds']),0)
            total_bytes+=int(r['source_bytes'])
        t=self.execution['telemetry']
        for key in ('source_copy_bytes_read','source_hash_bytes_read','source_copy_bytes_written'):self.assertEqual(t[key],total_bytes)
        self.assertEqual(t['raw_source_open_events'],2*len(plan));self.assertEqual(self.execution['source_guard_final_open_events'],2*len(plan))
        self.assertEqual(t['b13_pixel_values_read'],len(plan)*251001)
        self.assertLessEqual(t['temporary_bytes_peak'],734003200);self.assertTrue(t['cleanup_success'])
        self.assertEqual(self.execution['owned_staging_files_remaining'],0)
    def test_real_execution_no_outcome_model_or_parameter_operations(self):
        for key in ('2024_PIXELS_READ_FOR_FIT','2025_PIXELS_READ','IMERG_PIXELS_READ','MODEL_CHECKPOINT_LOADS',
                    'MODEL_FORWARD_CALLS','BACKWARD_CALLS','OPTIMIZER_STEPS','source_guard_prohibited_attempts'):
            self.assertEqual(self.execution[key],0,key)
        self.assertFalse(self.norm['MODEL_PARAMETERS_UPDATED'])
        for name,digest in self.norm['generation_code_sha256'].items():self.assertEqual(sha256(REPO_ROOT/name),digest)

class ProtocolArtifactTests(unittest.TestCase):
    def test_only_approved_items_frozen_and_training_unauthorized(self):
        p=f.read(REPO_ROOT/f.PROTOCOL);d=f.read(REPO_ROOT/f.DESIGN)
        self.assertFalse(p['TRAINING_PROTOCOL_FULLY_FROZEN']);self.assertFalse(p['automatic_phase_a_protocol_inheritance_approved'])
        for x in (p,d):
            self.assertFalse(x['B1_TRAINING_AUTHORIZED']);self.assertFalse(x['B0_MATCHED_CONTROL_TRAINING_AUTHORIZED'])
        for key in ('optimizer','base_lr','physical_batch','drop_last','epoch_budget','early_stopping',
                    'initialization_seed','checkpoint_selection','b0_matched_control_normalization'):
            self.assertEqual(p['RESEARCHER_DECISION_REQUIRED'][key],'NOT_YET_FROZEN')
        self.assertEqual(d['missing_policy'],'M1_STRICT_SIX_SLOT_FULL_VALID_CAUSAL')
        self.assertEqual(d['primary_comparison'],'COMMON_INTERSECTION_WITH_INDEPENDENT_B0_MATCHED_CONTROL')
        self.assertEqual(d['backbone']['parameter_count_verified'],4331761);self.assertTrue(d['historical_b0_immutable'])

if __name__=='__main__':unittest.main()
