"""Synthetic lifecycle tests; metadata only."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from completion_gate import reconcile_selection, resolve_authority, check_pair


def plateau():
    rows=[]
    for ep in range(1,10):
        value=.5 if ep==1 else .49995
        rows.append({'epoch':ep,'validation':{'global_val_core_loss':value},
            'decision':{'checkpoint_selected':ep<=2,'early_stop_improvement':ep==1,'stop':ep==9},
            'selection':{'best_checkpoint_value':value,'selected_checkpoint_epoch':1 if ep==1 else 2,
                         'early_stop_best':.5,'non_improvement_count':ep-1,'completed_epoch':ep}})
    return rows


class CompletionTests(unittest.TestCase):
    def test_best_and_es_are_distinct(self):
        r=reconcile_selection(plateau())
        self.assertEqual(r['best_checkpoint_epoch'],2);self.assertEqual(r['best_es_epoch'],1)
        self.assertEqual(r['final_early_stop_counter'],8);self.assertEqual(r['termination_reason'],'EARLY_STOP_PATIENCE_8')

    def test_incomplete_is_not_complete(self):
        self.assertEqual(reconcile_selection(plateau()[:8])['termination_reason'],'NOT_TERMINATED')

    def test_no_epoch_after_patience(self):
        rows=plateau();extra=copy.deepcopy(rows[-1]);extra['epoch']=10;rows.append(extra)
        with self.assertRaisesRegex(ValueError,'termination'):reconcile_selection(rows)

    def test_changed_best_and_nonfinite_rejected(self):
        rows=plateau();rows[-1]['decision']['checkpoint_selected']=True
        with self.assertRaisesRegex(ValueError,'Decision'):reconcile_selection(rows)
        rows=plateau();rows[0]['validation']['global_val_core_loss']=float('nan')
        with self.assertRaisesRegex(ValueError,'Nonfinite'):reconcile_selection(rows)


class RecoveryAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.origin_path = self.root/'original.json'
        self.path = self.root/'recovery'/'authorization.json'
        self.path.parent.mkdir()
        keys = ('scope FORMAL_TRAINING_AUTHORIZED V2_PHASE_A_AUTHORIZED V2_PHASE_B_AUTHORIZED '
                '2025_RAW_ACCESS 2025_PIXELS_READ pair_id run_ids models checkpoint_roots publication_root '
                'publication_repository execution_checkout execution_commit scientific_commit protocol_sha256 '
                'head_sha256 normalization_sha256 code_sha256 initial_state_sha256 preflight_path '
                'preflight_sha256 test_summary_path test_summary_sha256').split()
        original = dict.fromkeys(keys, 'synthetic_frozen_identity')
        original.update(publication_repository=str(self.root), publication_root=str(self.root/'public'),
                        models=['B0_MATCHED_V2', 'B1_V2'], resume_authorized=False)
        self.origin_path.write_text(json.dumps(original), encoding='utf-8')
        self.origin_sha = hashlib.sha256(self.origin_path.read_bytes()).hexdigest()
        self.precheck = self.root/'precheck.json'
        self.precheck.write_text(json.dumps({'status':'PASS','checkpoint':{'sha256':'lastsha'}}), encoding='utf-8')
        self.auth = dict(original, resume_authorized=True, resume_model='B0_MATCHED_V2',
            origin_authorization_path=str(self.origin_path), origin_authorization_sha256=self.origin_sha,
            resume_precheck_path=str(self.precheck), resume_precheck_sha256=hashlib.sha256(self.precheck.read_bytes()).hexdigest(),
            resume_LAST_sha256='lastsha')
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.auth), encoding='utf-8')

    def test_recovery_binds_original_and_waits_without_overwriting_stop(self):
        stopped = self.root/'process_exit.json'
        stopped.write_text('{"exit_code":1}', encoding='utf-8')
        before = stopped.read_bytes()
        _, sha = resolve_authority(self.path)
        self.assertEqual(sha, self.origin_sha)
        proof = check_pair(self.path)
        self.assertEqual(proof['status'], 'WAITING_FOR_BOTH_PHASE_A_COMPLETION')
        self.assertIn(str(self.path.parent/'process_exit.json'), proof['missing'])
        self.assertFalse(proof['REVIEW_INFERENCE_ALLOWED'])
        self.assertEqual(stopped.read_bytes(), before)

    def test_origin_tampering_rejected(self):
        self.origin_path.write_text('{}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'origin SHA'):resolve_authority(self.path)

    def test_changed_scientific_and_run_identity_rejected(self):
        for field in ('protocol_sha256', 'run_ids', 'normalization_sha256', 'checkpoint_roots'):
            old = self.auth[field]
            self.auth[field] = 'changed'
            self.save()
            with self.assertRaisesRegex(ValueError, 'frozen authority'):resolve_authority(self.path)
            self.auth[field] = old

    def test_changed_precheck_and_last_rejected(self):
        self.auth['resume_LAST_sha256'] = 'different'
        self.save()
        with self.assertRaisesRegex(ValueError, 'LAST/precheck'):resolve_authority(self.path)
        self.precheck.write_text('{}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'precheck SHA'):resolve_authority(self.path)

if __name__=='__main__':unittest.main(verbosity=2)
