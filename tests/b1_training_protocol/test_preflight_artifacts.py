"""Evidence checks only: no new raw reads, training, inference or checkpoint load."""
import json,unittest
from pathlib import Path
from yuntapr.contracts.loader import REPO_ROOT,sha256
from yuntapr.training.paired_phase_a import RunnerContract,STEPS,W,U,COUNTS
from yuntapr.data.dataset_b1 import SCALER_SHA

RUN=REPO_ROOT/'docs/b1_training_protocol/preflight/run_20261003T074333_289400Z'
def read(name):return json.loads((RUN/name).read_text(encoding='utf-8'))


class ArtifactTests(unittest.TestCase):
    def test_protocol_contract_pins_all_identities(self):
        c=RunnerContract.load();self.assertEqual(c.protocol_sha256,read('protocol_manifest.json')['protocol_sha256'])
        self.assertEqual(c.protocol['normalization_sha256'],SCALER_SHA)
    def test_paired_initializer_and_replay(self):
        m=read('paired_initialization_manifest.json')
        self.assertTrue(m['fresh_deterministic_replay_verified'] and m['all_shared_tensors_bit_identical'])
        self.assertEqual(set(m['different_tensors']),{'backbone.enc0.conv1.weight','backbone.enc0.skip.weight'})
        self.assertTrue(m['independent_reseed_before_each_model']);self.assertFalse(m['historical_checkpoint_loaded'])
    def test_actual_gpu_both_batch2_and_inherited_headroom(self):
        g=read('gpu_feasibility.json');self.assertEqual(g['status'],'PASS')
        for k,x in g['training'].items():
            self.assertEqual(x['batch'],2);self.assertEqual(x['iterations'],7)
            self.assertEqual(x['engineering_optimizer_steps'],7);self.assertTrue(x['recommended_20_percent'])
            self.assertLessEqual(x['peak_reserved_bytes'],.8*x['total_bytes'])
            self.assertGreaterEqual(x['estimated_min_free_bytes'],.2*x['total_bytes'])
    def test_validation_common_maximum_and_next_boundary(self):
        g=read('gpu_feasibility.json');safe=g['common_validation_batch'];unsafe=g['first_unsafe_common_batch']
        self.assertEqual(unsafe,safe+1);self.assertTrue(g['maximum_common_integer_batch_verified'])
        self.assertTrue(all(r['recommended_20_percent'] for r in g['validation_cases'][str(safe)].values()))
        self.assertFalse(all(r['recommended_20_percent'] for r in g['validation_cases'][str(unsafe)].values()))
        self.assertFalse(any(r['training'] for case in g['validation_cases'].values() for r in case.values()))
    def test_four_independent_smokes_and_exact_tail_lr(self):
        e=read('engineering_preflight.json');self.assertEqual([c['case'] for c in e['cases']],['A','B','C','D'])
        for c in e['cases']:
            x=c['updates'][0];self.assertEqual(c['engineering_optimizer_steps'],1)
            self.assertEqual(x['actual_denominator'],c['batch']*3430)
            self.assertLessEqual(x['post_clip_norm'],5.00001)
            self.assertTrue(c['temporary_model_optimizer_destroyed'])
            if c['batch']==1:self.assertEqual(x['LR'],1e-4);self.assertEqual(x['update'],5228)
        self.assertEqual(e['engineering_optimizer_steps'],18);self.assertEqual(e['FORMAL_OPTIMIZER_STEPS'],0)
        self.assertFalse(e['formal_checkpoint_written'])
    def test_all_smoke_precision_numerical_invariants(self):
        for c in read('engineering_preflight.json')['cases']:
            x=c['updates'][0]
            for k in ('quantile_crossing','support_violation','nonfinite'):self.assertEqual(x[k],0)
            self.assertTrue(x['probability_in_unit_interval']);self.assertEqual(x['raw_quantile_dtype'],'torch.float32')
            self.assertEqual(x['quantile_pinball_dtype'],'torch.float64')
    def test_fresh_model_sha_each_case(self):
        init=read('paired_initialization_manifest.json')
        for c in read('engineering_preflight.json')['cases']:
            self.assertEqual(c['initial_model_sha256'],init['B1_INITIAL_MODEL_SHA256' if c['kind']=='B1' else 'B0_MATCHED_INITIAL_MODEL_SHA256'])
    def test_actual_two_worker_six_frame_loader(self):
        m=read('loader_preflight.json');self.assertEqual(m['status'],'PASS');self.assertEqual(m['configuration']['num_workers'],2)
        for k,r in m['results'].items():
            self.assertEqual(r['scenes'],32);self.assertEqual(len(r['workers']),2)
            self.assertEqual(r['source_reads'],32*(7 if k=='B1' else 2));self.assertTrue(r['cleanup_success'])
        self.assertTrue(m['same_target_and_latest_normalized_B13'])
    def test_actual_2024_validation_only_gpu_confirmation(self):
        m=read('validation_2024_inference_gpu_audit.json')
        self.assertEqual(m['status'],'PASS');self.assertEqual(m['sample_year'],2024)
        self.assertEqual(m['unique_fixture_scenes_per_model'],16);self.assertFalse(m['full_10501_validation_executed'])
        self.assertEqual(m['ENGINEERING_OPTIMIZER_STEPS'],0);self.assertEqual(m['selected_common_validation_batch'],8)
        self.assertTrue(all(x['recommended_20_percent'] and not x['training'] for x in m['cases']['8'].values()))
        self.assertFalse(all(x['recommended_20_percent'] for x in m['cases']['9'].values()))
        for items in m['source_fixtures'].values():
            for item in items:
                self.assertTrue(item['sample_id'].startswith('2024-'))
                self.assertTrue(all(x['cleanup_success'] and x['sha256_match'] for x in item['staging']))
    def test_every_staging_record_size_sha_cleanup_and_scope(self):
        m=read('loader_preflight.json');records=[r for v in m['results'].values() for r in v['staging_records']]
        records += [q for item in m['validation_fixtures'] for q in item['staging']]
        for r in records:
            self.assertTrue(r['size_match'] and r['sha256_match'] and r['cleanup_success'])
            self.assertIsNone(r['error']);self.assertLessEqual(r['temporary_bytes'],734003200)
            self.assertNotRegex(Path(r['source_path']).name,r'2025\d{4}')
            self.assertGreaterEqual(r['copy_seconds'],0);self.assertGreaterEqual(r['read_seconds'],0)
    def test_scheduler_all_updates_and_permutations(self):
        self.assertEqual(read('scheduler_verification.json')['updates_checked'],261400)
        m=read('sample_order_verification.json');self.assertEqual(len(m['epochs']),50)
        for e in m['epochs']:self.assertEqual(e['samples'],10455);self.assertEqual(e['updates'],5228);self.assertTrue(e['same_B0_B1_order'])
    def test_exact_optimizer_inventories(self):
        m=read('optimizer_group_verification.json')
        for k in COUNTS:self.assertEqual(m[k]['counts'],COUNTS[k]);self.assertTrue(m[k]['disjoint'] and m[k]['complete_union'])
    def test_pairwise_fairness_and_frozen_scaler_adoption(self):
        f=read('PAIRWISE_FAIRNESS_MANIFEST.json');self.assertEqual(f['parameter_delta'],2400)
        self.assertEqual(f['difference'],'INPUT_INFORMATION_DIFFERENCE');self.assertEqual(f['normalization_sha256'],SCALER_SHA)
        self.assertTrue(f['same_loss_optimizer_scheduler_permutation_seed_earlystop_BEST_metrics'])
    def test_runtime_implementation_hashes(self):
        m=read('runner_manifest.json')
        archive=read('engineering_execution_source_archive.json')
        for rel,digest in m['implementation_hashes'].items():
            p=REPO_ROOT/(archive[rel]['snapshot_path'] if rel in archive else rel)
            self.assertEqual(sha256(p),digest,rel)
        for rel,digest in read('runner_closure_manifest.json')['implementation_hashes'].items():self.assertEqual(sha256(REPO_ROOT/rel),digest,rel)
    def test_historical_files_all_byte_identical(self):
        m=read('history_before.json')
        self.assertEqual(len(m['files']),1982)
        for rel,ref in m['files'].items():self.assertEqual(sha256(REPO_ROOT/rel),ref['sha256'],rel)
    def test_no_binary_artifacts_or_2025_inference(self):
        self.assertFalse(any(p.suffix.lower() in ('.pt','.pth','.ckpt','.nc') for p in RUN.rglob('*')))
        e=read('engineering_preflight.json');self.assertEqual(e['2025_PIXELS_READ'],0);self.assertEqual(e['2025_MODEL_INFERENCE_SCENES'],0)


if __name__=='__main__':unittest.main()
