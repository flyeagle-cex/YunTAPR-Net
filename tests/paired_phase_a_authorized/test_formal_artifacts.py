"""Read-only completed-run integrity. Never construct an optimizer or inference model."""
import json,os,unittest
from pathlib import Path
import torch
from yuntapr.contracts.loader import REPO_ROOT,sha256
from yuntapr.training import paired_phase_a as frozen
from yuntapr.training import paired_phase_a_audit as a
from yuntapr.training.phase_a_protocol import ValidationSelection,state_digest,lr_for_update

def registry():
    p=Path(os.environ['YUNTAPR_PAIRED_AUTHORIZATION_REGISTRY'])
    return json.loads(p.read_text(encoding='utf8'))

class CompletedRunChecks:
    @classmethod
    def setUpClass(cls):
        cls.spec=registry()[cls.MODEL];cls.public=Path(cls.spec['public_directory'])
        cls.status=json.loads((cls.public/'final_status.json').read_text(encoding='utf8'))
        if cls.status['status']!='FORMAL_PHASE_A_COMPLETE':raise AssertionError('Full completion required; NOT_RUN never PASS')
        cls.manifest=json.loads((cls.public/'run_manifest.json').read_text(encoding='utf8'))
        cls.history=json.loads((cls.public/'training_validation_history.json').read_text(encoding='utf8'))
        cls.identities=json.loads((cls.public/'checkpoint_registry.json').read_text(encoding='utf8'))
        cls.loaded={};cls.before={}
        for identity in cls.identities.values():
            path=Path(identity['absolute_local_path'])
            if path.parent!=frozen.ROOTS[cls.MODEL]/cls.spec['run_id']:raise AssertionError('Cross-model checkpoint root rejected before open')
            digest=sha256(path)
            if digest!=identity['sha256'] or path.stat().st_size!=identity['bytes']:raise AssertionError('File identity before deserialize')
            cls.before[str(path)]=digest
            if str(path) not in cls.loaded:
                payload=torch.load(path,map_location='cpu',weights_only=False)
                frozen.validate_payload(payload,cls.manifest);cls.loaded[str(path)]=payload
    @classmethod
    def tearDownClass(cls):
        for path,digest in cls.before.items():
            if sha256(Path(path))!=digest:raise AssertionError('Read-only integrity test changed checkpoint')
        cls.loaded.clear()
    def test_completed_epochs_steps_and_actual_calls(self):
        e=self.status['completed_epoch'];self.assertEqual(self.status['FORMAL_OPTIMIZER_STEPS'],e*5228)
        self.assertEqual(self.status['OPTIMIZER_STEPS_COMPLETED'],e*5228);self.assertEqual(self.status['BACKWARD_CALLS'],e*5228)
        self.assertEqual(self.status['TRAIN_FORWARD_CALLS'],e*5228)
        self.assertEqual(self.status['VALIDATION_FORWARD_CALLS'],e*((10501+7)//8))
    def test_full_history_rows_and_valid_denominators(self):
        self.assertEqual([r['epoch'] for r in self.history],list(range(1,self.status['completed_epoch']+1)))
        for row in self.history:
            self.assertEqual(row['train']['N_valid'],10455*3430);self.assertEqual(row['validation']['N_valid'],10501*3430)
            self.assertEqual(row['validation']['validation_scenes'],10501);self.assertEqual(row['train']['optimizer_steps'],5228)
    def test_selection_and_early_stop_recomputed_exactly(self):
        selection=ValidationSelection()
        for row in self.history:
            decision=selection.update(row['epoch'],row['validation']['global_val_core_loss'])
            self.assertEqual(row['selection'],decision);self.assertEqual(row['BEST_epoch'],selection.selected_checkpoint_epoch)
            self.assertEqual(row['early_stop_counter'],selection.non_improvement_count)
        self.assertEqual(self.identities['BEST']['epoch'],selection.selected_checkpoint_epoch)
        self.assertEqual(self.status['selected_best_val_core'],selection.best_checkpoint_value)
        self.assertTrue(selection.completed_epoch==50 or selection.non_improvement_count==8)
    def test_every_recorded_sample_order_matches_frozen_permutation(self):
        records=frozen.load_records(self.MODEL,2023)
        for row in self.history:
            order,_=frozen.batch_plan(row['epoch']-1)
            digest=state_digest([records[i]['sample_id'] for i in order])
            self.assertEqual(row['sample_order_identity_sha256'],digest)
            self.assertEqual(row['train']['ordered_sample_identity_sha256'],digest)
    def test_actual_lr_boundaries_and_core_arithmetic(self):
        for row in self.history:
            train,val,e=row['train'],row['validation'],row['epoch']
            self.assertEqual(train['LR_start'],lr_for_update((e-1)*5228+1,steps_per_epoch=5228))
            self.assertEqual(train['LR_end'],lr_for_update(e*5228,steps_per_epoch=5228))
            self.assertEqual(train['global_core_loss'],(train['S_occ']+train['S_qr'])/(10455*3430))
            self.assertEqual(val['global_val_core_loss'],(val['S_occ']+val['S_qr'])/(10501*3430))
    def test_checkpoint_boundary_and_best_last_identities(self):
        self.assertEqual(self.identities,self.status and {'BEST':self.status['BEST'],'LAST':self.status['LAST']})
        for role,identity in self.identities.items():
            payload=self.loaded[identity['absolute_local_path']]
            self.assertEqual(payload['completed_epoch'],identity['epoch']);self.assertEqual(payload['global_update'],identity['epoch']*5228)
            self.assertTrue(payload['training_completed'] and payload['validation_completed'])
            self.assertEqual(payload['validation'],self.history[identity['epoch']-1]['validation'])
        self.assertEqual(self.identities['LAST']['epoch'],self.status['completed_epoch'])
    def test_real_state_parameter_counts_and_optimizer_groups(self):
        for payload in self.loaded.values():
            names=payload['optimizer_groups']['names'];state=payload['model_state_dict']
            counts={g:sum(state[n].numel() for n in group) for g,group in names.items()};counts['total']=sum(counts.values())
            self.assertEqual(counts,frozen.COUNTS[self.MODEL]);self.assertEqual(payload['parameter_counts'],counts)
            self.assertFalse(set(names['DECAY_GROUP'])&set(names['NO_DECAY_GROUP']))
            for group in payload['optimizer_state_dict']['param_groups']:
                self.assertEqual(group['lr'],payload['last_applied_lr']);self.assertEqual(group['betas'],(.9,.999))
                self.assertEqual(group['eps'],1e-8);self.assertEqual(group['weight_decay'],1e-4 if group['group_name']=='DECAY_GROUP' else 0.)
            for state in payload['optimizer_state_dict']['state'].values():
                self.assertEqual(int(state['step']),payload['global_update'])
    def test_pinned_fresh_initialization_and_no_historical_transfer(self):
        self.assertEqual(self.manifest['initial_model_sha256'],a.INITIAL[self.MODEL])
        proof=self.manifest['paired_initialization'];self.assertFalse(proof['historical_checkpoint_loaded'])
        self.assertFalse(proof['optimizer_state_transferred']);self.assertEqual(proof['same_shape_tensor_count'],72)
    def test_provenance_and_normalization_unchanged(self):
        self.assertEqual(self.manifest['protocol_sha256'],a.PROTOCOL_SHA)
        self.assertEqual(self.manifest['normalization_sha256'],a.data.SCALER_SHA)
        for name,ref in self.manifest['identity'].items():
            path=Path(ref['path']);path=path if path.is_absolute() else REPO_ROOT/path
            self.assertEqual(sha256(path),ref['sha256'],name)
        self.assertEqual(self.manifest['code_hashes'],a.code_hashes())
    def test_quantile_probability_diagnostics_no_tuning(self):
        for row in self.history:
            val=row['validation']
            for key in ('strict_crossing_count','nonfinite_count','support_violation_count'):self.assertEqual(val[key],0)
            self.assertEqual(len(val['per_tau_pinball']),32);self.assertEqual(len(val['per_tau_conditional_coverage']),32)
            for key in ('POD','FAR','CSI'):self.assertEqual(val[key],'THRESHOLD_NOT_FROZEN')
    def test_staging_cleanup_and_no_2025_access(self):
        self.assertTrue(self.status['source_cleanup_state']['cleanup_success'])
        self.assertEqual(self.status['source_cleanup_state']['remaining_temporary_files'],[])
        for key in ('2025_PIXELS_READ','2025_RAW_ACCESS','2025_MODEL_INFERENCE_SCENES'):self.assertEqual(self.status[key],0)
        self.assertFalse(self.status['2025_FINAL_TEST_EXECUTED'])
    def test_formal_fixture_engineering_accounting_separate(self):
        self.assertEqual(self.status['ENGINEERING_OPTIMIZER_STEPS'],0);self.assertEqual(self.status['TEST_FIXTURE_OPTIMIZER_STEPS'],0)
        self.assertEqual(self.manifest['scope'],a.SCOPES[self.MODEL])
        self.assertFalse(any(p.suffix in ('.pt','.pth','.ckpt') for p in self.public.rglob('*')))

class MatchedCompletedTests(CompletedRunChecks,unittest.TestCase):MODEL='B0_MATCHED'
class B1CompletedTests(CompletedRunChecks,unittest.TestCase):MODEL='B1'

class PairwiseTests(unittest.TestCase):
    def test_same_frozen_target_sample_set_and_order(self):
        for year in (2023,2024):
            b0=frozen.load_records('B0_MATCHED',year);b1=frozen.load_records('B1',year)
            for field in ('sample_id','window_start','analysis_time','imerg_sha256','imerg_index'):
                self.assertEqual([r[field] for r in b0],[r[field] for r in b1])
    def test_same_epoch_permutation_identity(self):
        histories=[json.loads((Path(spec['public_directory'])/'training_validation_history.json').read_text(encoding='utf8')) for spec in registry().values()]
        for left,right in zip(*histories):self.assertEqual(left['sample_order_identity_sha256'],right['sample_order_identity_sha256'])
    def test_both_best_selected_only_by_global_core(self):
        for spec in registry().values():
            rows=json.loads((Path(spec['public_directory'])/'training_validation_history.json').read_text(encoding='utf8'))
            ident=json.loads((Path(spec['public_directory'])/'best_checkpoint_identity.json').read_text(encoding='utf8'))
            best=min(rows,key=lambda r:r['validation']['global_val_core_loss'])
            self.assertEqual(ident['epoch'],best['epoch'])
    def test_no_phase_b_or_final_test_authorization(self):
        for spec in registry().values():
            value=json.loads(Path(spec['authorization_path']).read_text(encoding='utf8'))
            self.assertFalse(value['Phase_B_authorized'] or value['B2_to_B8_authorized'] or value['2025_Final_Test_authorized'])

if __name__=='__main__':unittest.main()
