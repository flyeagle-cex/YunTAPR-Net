import csv
import json
import math
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
import torch
import yaml
from yuntapr.contracts.loader import REPO_ROOT,sha256
from yuntapr.training.phase_b_preparation import (SCENES,PIXELS,STEPS,EPOCHS,UPDATES,TAIL_POLICY,
    validate_population,exact_histogram_summary,merge_moments,batch_plan,finalfit_lr,PhaseBNormalizer)
from yuntapr.training.phase_a_protocol import lr_for_update,state_digest


class PreparationUnitTests(unittest.TestCase):
    def test_population_arithmetic(self):
        self.assertEqual(11720+11727,SCENES)
        self.assertEqual(SCENES*501*501,PIXELS)
        self.assertEqual(math.ceil(SCENES/2),STEPS)
        self.assertEqual(EPOCHS*STEPS,UPDATES)

    def test_tail_does_not_drop_or_duplicate(self):
        p,batches=batch_plan(0)
        self.assertEqual(len(batches),11724)
        self.assertTrue(all(len(b)==2 for b in batches[:-1]))
        self.assertEqual(len(batches[-1]),1)
        self.assertTrue(torch.equal(torch.cat(batches),p))
        self.assertEqual(sorted(p.tolist()),list(range(SCENES)))

    def test_epoch_permutation_reproducible_and_independent(self):
        a,_=batch_plan(0);torch.manual_seed(7);torch.rand(100)
        b,_=batch_plan(0);c,_=batch_plan(1)
        self.assertTrue(torch.equal(a,b));self.assertFalse(torch.equal(a,c))

    def test_wrong_population_rejected(self):
        with self.assertRaises(ValueError):batch_plan(0,count=23446)
        with self.assertRaises(ValueError):validate_population([])

    def test_scheduler_exact_boundaries(self):
        self.assertEqual(finalfit_lr(1),1e-4*(1/11724))
        self.assertEqual(finalfit_lr(STEPS),1e-4)
        self.assertLess(finalfit_lr(STEPS+1),1e-4)
        self.assertEqual(finalfit_lr(50*STEPS),1e-6)
        self.assertGreater(finalfit_lr(UPDATES),1e-6)

    def test_same_epoch_progress(self):
        for numerator in range(1,101):
            # Common half-epoch coordinates on different update lattices.
            a=lr_for_update(numerator*2930)
            b=finalfit_lr(numerator*5862)
            self.assertEqual(a,b)

    def test_warmup_not_clamped_to_minimum(self):
        self.assertLess(finalfit_lr(1),1e-6)
        self.assertGreater(finalfit_lr(1),0)
        with self.assertRaises(ValueError):finalfit_lr(0)
        with self.assertRaises(ValueError):finalfit_lr(586201)

    def test_exact_histogram_matches_expanded_pixels(self):
        raw=np.array([-7000,-5000,-5000,0,100,100,100,2000],dtype=np.int16)
        x=raw.astype(np.float32)*np.float32(.01)+np.float32(273.15)
        h=np.bincount(raw.astype(np.int32)+32768,minlength=65536).astype(np.int64)
        v=exact_histogram_summary(h)
        self.assertAlmostEqual(v['mean_K'],x.astype(np.float64).mean(),places=12)
        self.assertAlmostEqual(v['std_K'],x.astype(np.float64).std(ddof=0),places=12)
        for key,p in [('min_K',0),('p1_K',1),('q1_K',25),('median_K',50),('q3_K',75),('p99_K',99),('max_K',100)]:
            self.assertEqual(v[key],float(np.percentile(x.astype(np.float64),p,method='linear')))

    def test_histogram_rejects_invalid_population(self):
        with self.assertRaises(ValueError):exact_histogram_summary(np.zeros(65536,dtype=np.int64))
        h=np.zeros(65536,dtype=np.int64);h[0]=-1
        with self.assertRaises(ValueError):exact_histogram_summary(h)

    def test_independent_moments(self):
        chunks=[np.array([270.,271.]),np.array([220.,290.,299.]),np.array([260.])]
        state=(0,0.,0.)
        for x in chunks:state=merge_moments(state,x)
        x=np.concatenate(chunks)
        self.assertEqual(state[0],len(x));self.assertAlmostEqual(state[1],x.mean(),places=12)
        self.assertAlmostEqual(math.sqrt(state[2]/state[0]),x.std(ddof=0),places=12)

    def test_singleton_and_mixed_batch_denominator(self):
        from yuntapr.models.probability_heads import B0Output
        from yuntapr.losses.total_loss import b0_core_loss
        logits=torch.zeros(2,1,1,3,dtype=torch.float64)
        q=torch.linspace(.2,3,32,dtype=torch.float64).reshape(1,32,1,1).expand(2,32,1,3)
        y=torch.tensor([[[[0.,2.,0.]]],[[[.5,0.,1.]]]],dtype=torch.float32)
        valid=torch.tensor([[[[True,True,False]]],[[[True,True,True]]]])
        def output(logits,q):return B0Output(logits,torch.sigmoid(logits),q,torch.expm1(q),torch.zeros_like(logits),(),(),torch.ones_like(logits),torch.zeros(logits.shape[0]),torch.ones(logits.shape[0]))
        all_loss=b0_core_loss(output(logits,q),y,valid,torch.ones_like(valid),focal_alpha=.5,focal_gamma=2.,quantile_axis_reduction='mean')
        singleton=[]
        for i in range(2):
            loss=b0_core_loss(output(logits[i:i+1],q[i:i+1]),y[i:i+1],valid[i:i+1],torch.ones_like(valid[i:i+1]),focal_alpha=.5,focal_gamma=2.,quantile_axis_reduction='mean')
            singleton.append(loss)
        reference=sum(l.total*l.valid_supervised_count for l in singleton)/5
        self.assertAlmostEqual(float(all_loss.total),float(reference),places=14)
        self.assertEqual(singleton[0].valid_supervised_count,2);self.assertEqual(singleton[1].valid_supervised_count,3)

    def test_fresh_seed_model_no_checkpoint_load(self):
        from yuntapr.models.b0 import B0Model
        with patch('torch.load',side_effect=AssertionError('Checkpoint initialization forbidden')) as loader:
            torch.manual_seed(2026);a=B0Model();digest=state_digest(a.state_dict());del a
            torch.manual_seed(2026);b=B0Model();self.assertEqual(digest,state_digest(b.state_dict()));del b
            loader.assert_not_called()


class PreparationArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out=Path(os.environ['YUNTAPR_PHASE_B_PREPARATION_EVIDENCE'])
        cls.norm=json.loads((cls.out/'normalization_phaseB_finalfit_2023_2024.json').read_text(encoding='utf-8'))

    def test_actual_manifest_population(self):
        with (self.out/'phase_b_finalfit_manifest.csv').open(encoding='utf-8',newline='') as f: values=list(csv.DictReader(f))
        self.assertEqual(validate_population(values),{2023:11720,2024:11727})
        self.assertTrue(all(r['imerg_version']=='V07' and r['imerg_run_type']=='Final' and r['used_older_causal_frame']=='False' for r in values))

    def test_actual_normalization_counts_and_independent_moments(self):
        self.assertEqual(self.norm['eligible_scene_count'],SCENES);self.assertEqual(self.norm['valid_pixel_count'],PIXELS)
        self.assertEqual(self.norm['ddof'],0);self.assertFalse(self.norm['phase_a_constants_reused'])
        self.assertLess(abs(self.norm['mean_K']-self.norm['streaming_mean_K']),1e-9)
        self.assertLess(abs(self.norm['std_K']-self.norm['streaming_std_K']),1e-9)

    def test_phase_b_normalizer_identity_and_scope(self):
        p=self.out/'normalization_phaseB_finalfit_2023_2024.json';n=PhaseBNormalizer.from_artifact(p,sha256(p))
        x=np.ones((501,501),dtype=np.float32)*270;v=np.ones_like(x,dtype=bool)
        self.assertTrue(np.array_equal(n.transform(x,v,'2024-07-01T00:00:00+00:00'),((x.astype(np.float64)-n.mu)/n.sigma).astype(np.float32)))
        with self.assertRaises(ValueError):n.transform(x,v,'2025-07-01T00:00:00+00:00')
        v[0,0]=False
        with self.assertRaises(ValueError):n.transform(x,v,'2023-07-01T00:00:00+00:00')
        with self.assertRaises(ValueError):PhaseBNormalizer.from_artifact(p,'0'*64)

    def test_actual_read_ledger_cleanup(self):
        data=json.loads((self.out/'normalization_execution.json').read_text(encoding='utf-8'))
        self.assertEqual(data['actual_scenes_read'],SCENES);self.assertEqual(data['actual_pixels_read'],PIXELS)
        self.assertTrue(data['cleanup_success']);self.assertEqual(data['owned_staging_files_remaining'],0)
        self.assertEqual(data['2025_PIXELS_READ'],0)
        for ref in data['local_artifacts'].values():self.assertEqual(sha256(Path(ref['absolute_local_path'])),ref['sha256'])

    def test_protocol_horizon_tail_and_authorization(self):
        p=yaml.safe_load((REPO_ROOT/'config/training/phase_b_finalfit_preparation_v1.yaml').read_text(encoding='utf-8'))
        self.assertEqual(p['FINALFIT_EPOCHS'],11);self.assertEqual(p['steps_per_epoch'],11724)
        self.assertEqual(p['scheduler']['W'],11724);self.assertEqual(p['scheduler']['U'],586200)
        self.assertEqual(p['FINALFIT_TAIL_BATCH_POLICY'],TAIL_POLICY);self.assertEqual(p['PHASE_B_MODEL_INITIALIZATION'],'FRESH_SEED_2026')
        self.assertFalse(p['PHASE_B_AUTHORIZED']);self.assertFalse(p['early_stopping'])

    def test_acceptance_bound_to_unchanged_review(self):
        p=yaml.safe_load((REPO_ROOT/'config/decisions/b0_phase_a_acceptance_v1.yaml').read_text(encoding='utf-8'))
        self.assertTrue(p['B0_PHASE_A_ACCEPTED']);self.assertEqual(p['TRANSFER_EPOCH_BUDGET_TO_PHASE_B'],11)
        self.assertEqual(p['scientific_review_commit'],'5050b6cc77ab75eacb96e1494a165d61142227f4')
        old=json.loads((REPO_ROOT/'docs/scientific_review/b0_phase_a/runs/run_20261002T005448_798068Z/final_status.json').read_text(encoding='utf-8'))
        self.assertEqual(old['B0_PHASE_A_ACCEPTED'],'UNDECIDED')

    def test_actual_scheduler_and_initialization_evidence(self):
        p=json.loads((self.out/'protocol_sanity.json').read_text(encoding='utf-8'))
        self.assertEqual(p['status'],'PASS');self.assertTrue(p['same_epoch_progress_replay_exact'])
        self.assertTrue(p['fresh_seed_initialization_reproducible']);self.assertEqual(p['checkpoint_load_calls'],0)

    def test_actual_two_batch_dryrun(self):
        p=json.loads((self.out/'engineering_dryrun.json').read_text(encoding='utf-8'))
        self.assertEqual(p['status'],'PASS');self.assertEqual([r['batch_size'] for r in p['batches']],[2,1])
        self.assertEqual(p['ENGINEERING_OPTIMIZER_STEPS'],2);self.assertEqual(p['FORMAL_OPTIMIZER_STEPS'],0)
        self.assertTrue(p['temporary_model_optimizer_released']);self.assertEqual(p['checkpoint_load_calls'],0)
        self.assertFalse(p['PHASE_B_FORMAL_TRAINING_STARTED']);self.assertFalse(p['PHASE_B_AUTHORIZED'])
