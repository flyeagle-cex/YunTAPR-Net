"""TEST_FIXTURE_ONLY. No raw files or formal checkpoints; all owned fixtures removed."""
import copy,json,os,shutil,subprocess,sys,unittest,uuid
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import torch
from yuntapr.contracts.loader import REPO_ROOT,sha256
from yuntapr.training import paired_phase_a_audit as a
from yuntapr.training import paired_phase_a as frozen
from yuntapr.training.phase_a_protocol import parameter_groups,state_digest,lr_for_update
from yuntapr.models.b1 import paired_models
sys.path.insert(0,str(REPO_ROOT/'scripts'))
import authorized_paired_phase_a_entry as entry
import paired_phase_a_entry as original

class AuditTests(unittest.TestCase):
    TEST_FIXTURE_ONLY=True
    def setUp(self):
        self.parent=REPO_ROOT.parent/'tmp/paired_authorization_fixtures';self.parent.mkdir(parents=True,exist_ok=True)
        self.root=self.parent/uuid.uuid4().hex;self.root.mkdir()
        for rel in ('scripts/train_b1_phase_a_v1.py','scripts/train_b0_matched_phase_a_v1.py','scripts/paired_phase_a_entry.py',*a.ADAPTERS):
            p=self.root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('TEST_FIXTURE_ONLY\n')
        sp=self.root/a.SLOT_PATH;sp.parent.mkdir(parents=True,exist_ok=True);sp.write_bytes((REPO_ROOT/a.SLOT_PATH).read_bytes())
        self.contract=SimpleNamespace(root=self.root,protocol_sha256=a.PROTOCOL_SHA,protocol=frozen.protocol_body(8,{}))
        self.proof={'same_shape_tensor_count':72,'all_shared_tensors_bit_identical':True,'independent_reseed_before_each_model':True,
                    'historical_checkpoint_loaded':False,'optimizer_state_transferred':False,'native_zero_skip_preserved':True}
    def tearDown(self):
        self.assertEqual(self.root.resolve().parent,self.parent.resolve());shutil.rmtree(self.root)
    def save(self,path,value):
        path.write_text(json.dumps(value,allow_nan=False),encoding='utf8');return sha256(path)
    def auth(self,kind='B1'):
        value=a.authorization_fields(self.contract,kind)
        gate={'status':'PASS','FORMAL_OPTIMIZER_STEPS':0,'2025_RAW_ACCESS':0,'2025_PIXELS_READ':0,
              'protocol_sha256':a.PROTOCOL_SHA,'normalization_sha256':a.data.SCALER_SHA,
              'implementation_sha256':value['implementation_sha256'],'initial_model_sha256':a.INITIAL,
              'parameter_counts':frozen.COUNTS,'all_related_tests_passed':True,'historical_files_byte_identical':True,
              'scheduler_boundaries_pass':True,'optimizer_groups_pass':True,'paired_initialization_provenance':self.proof}
        p=self.root/'gate.json';gs=self.save(p,gate)
        value.update(pretraining_gate_path=str(p),pretraining_gate_sha256=gs,researcher_approval_reference='TEST_FIXTURE_ONLY',
                     historical_snapshot_path=str(self.root/'snapshot.json'),historical_snapshot_sha256='TEST_FIXTURE_ONLY',
                     paired_initialization_provenance=self.proof)
        return value
    def load(self,value,kind='B1'):
        p=self.root/'authorization.json';digest=self.save(p,value)
        with patch.object(a,'verify_history',return_value={'file_count':2061,'all_byte_identical':True}) as history:
            result=a.AuditedAuthorization.load(p,digest,self.contract,kind)
            history.assert_called_once()
        return result
    def reject(self,key,value):
        auth=self.auth();auth[key]=value
        p=self.root/'authorization.json';digest=self.save(p,auth)
        with patch.object(a,'verify_history'),self.assertRaises(PermissionError):a.AuditedAuthorization.load(p,digest,self.contract,'B1')
    def test_valid_b1_authorization(self):self.assertEqual(self.load(self.auth()).value['scope'],a.SCOPES['B1'])
    def test_valid_matched_authorization(self):self.assertEqual(self.load(self.auth('B0_MATCHED'),'B0_MATCHED').value['scope'],a.SCOPES['B0_MATCHED'])
    def test_b0_authorization_cannot_launch_b1(self):
        with self.assertRaises(PermissionError):self.load(self.auth('B0_MATCHED'),'B1')
    def test_b1_authorization_cannot_launch_b0(self):
        with self.assertRaises(PermissionError):self.load(self.auth(),'B0_MATCHED')
    def test_generic_scope_rejected(self):self.reject('scope','FORMAL_PAIRED_PHASE_A')
    def test_wrong_protocol_rejected(self):self.reject('protocol_sha256','wrong')
    def test_wrong_normalization_rejected(self):self.reject('normalization_sha256','wrong')
    def test_wrong_train_manifest_rejected(self):self.reject('train_manifest_sha256','wrong')
    def test_wrong_validation_manifest_rejected(self):self.reject('validation_manifest_sha256','wrong')
    def test_wrong_initial_state_rejected(self):self.reject('initial_model_sha256','wrong')
    def test_wrong_checkpoint_root_rejected(self):self.reject('checkpoint_root',str(frozen.ROOTS['B0_MATCHED']))
    def test_wrong_code_rejected(self):self.reject('implementation_sha256','wrong')
    def test_wrong_seed_rejected(self):self.reject('seed',2027)
    def test_wrong_batch_rejected(self):self.reject('physical_batch',1)
    def test_wrong_accumulation_rejected(self):self.reject('accumulation',2)
    def test_wrong_validation_batch_rejected(self):self.reject('validation_batch',9)
    def test_wrong_warmup_rejected(self):self.reject('W',5860)
    def test_wrong_horizon_rejected(self):self.reject('U',586200)
    def test_historical_transfer_rejected(self):self.reject('initialization','PHASE_A_BEST_TRANSFER')
    def test_2025_authorization_rejected(self):self.reject('2025_raw_access',True)
    def test_missing_approval_rejected(self):self.reject('researcher_approval_reference','')
    def test_missing_authorization_before_contract_model_optimizer(self):
        with (patch.object(entry.frozen.RunnerContract,'load',side_effect=AssertionError('contract must not load')),
              patch.object(entry,'paired_models',side_effect=AssertionError('model must not construct')),
              patch.object(entry.frozen,'optimizer_for',side_effect=AssertionError('optimizer must not construct'))):
            with self.assertRaises(SystemExit):entry.reject_before_construction('B1',[])
    def test_bad_authorization_sha(self):
        p=self.root/'authorization.json';self.save(p,self.auth())
        with self.assertRaises(PermissionError):a.AuditedAuthorization.load(p,'wrong',self.contract,'B1')
    def test_incomplete_pretraining_gate(self):
        value=self.auth();p=Path(value['pretraining_gate_path']);v=json.loads(p.read_text());v['FORMAL_OPTIMIZER_STEPS']=1
        value['pretraining_gate_sha256']=self.save(p,v)
        with self.assertRaises(PermissionError):self.load(value)
    def test_scope_gate_rejects_before_formal_raw_io(self):
        guard=a.RawFirewall()
        with self.assertRaises(PermissionError):guard.check(str(a.data.H_ROOT/'202303'/'202303010000.nc'))
        self.assertEqual(guard.raw_opens,0)
    def test_2025_himawari_rejected_before_io(self):
        guard=a.RawFirewall(True)
        with self.assertRaises(PermissionError):guard.check(str(a.data.H_ROOT/'202503'/'202503010000.nc'))
        self.assertEqual(guard.raw_opens,0)
    def test_2025_imerg_rejected_before_io(self):
        guard=a.RawFirewall(True)
        with self.assertRaises(PermissionError):guard.check(str(a.data.IMERG_ROOT/'IMERG_20250301.nc'))
    def test_installed_guard_rejects_before_resolve_open_or_netcdf_backend(self):
        script="""
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,sys.argv[1])
from yuntapr.training.paired_phase_a_audit import RawFirewall,data
g=RawFirewall(True);g.install()
with patch.object(Path,'resolve',side_effect=AssertionError('No forbidden metadata I/O')):
    for operation in (lambda:open(str(data.H_ROOT/'202503'/'202503010000.nc'),'rb'),
                      lambda:data.netCDF4.Dataset(str(data.IMERG_ROOT/'IMERG_20250301.nc'))):
        try:operation()
        except PermissionError:pass
        else:raise AssertionError('Forbidden source was not rejected')
assert g.raw_opens==0 and g.forbidden_attempts==2
print('GUARD_BEFORE_IO_PASS')
"""
        result=subprocess.run([sys.executable,'-c',script,str(REPO_ROOT/'src')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr);self.assertIn('GUARD_BEFORE_IO_PASS',result.stdout)
    def test_root_year_range_does_not_reject_actual_2023(self):
        a.RawFirewall(True).check(str(a.data.H_ROOT/'202303'/'202303010000.nc'))
    def test_february_rejected(self):
        with self.assertRaises(PermissionError):a.RawFirewall(True).check(str(a.data.H_ROOT/'202302'/'202302282350.nc'))
    def test_raw_mutation_rejected(self):
        with self.assertRaises(PermissionError):a.RawFirewall(True).check(str(a.data.H_ROOT/'202303'/'202303010000.nc'),'wb')
    def test_unlisted_source_rejected(self):
        with self.assertRaises(PermissionError):a.RawFirewall(True,['different']).check(str(a.data.IMERG_ROOT/'IMERG_20230301.nc'))
    def test_raw_authorization_path_rejects_before_hash(self):
        with patch.object(a,'sha256',side_effect=AssertionError('must not hash')):
            with self.assertRaises(PermissionError):a.repository_json_path(str(a.data.IMERG_ROOT/'20250301.json'))
    def registry(self,kind='B1'):
        ident={'model':kind,'epoch':1,'global_update':5228,'sha256':'fixture',
               'absolute_local_path':str(frozen.ROOTS[kind]/'run_fixture'/'epoch_001.pt')}
        return {'BEST':copy.deepcopy(ident),'LAST':ident}
    def resume_auth(self):return SimpleNamespace(value={'resume_authorized':True,'resume_ancestry':{'run_id':'run_fixture','LAST_sha256':'fixture'}})
    def test_valid_same_model_completed_epoch_resume(self):a.validate_resume_ancestry(self.resume_auth(),'B1','run_fixture',self.registry())
    def test_cross_model_resume_rejected(self):
        with self.assertRaises(ValueError):a.validate_resume_ancestry(self.resume_auth(),'B1','run_fixture',self.registry('B0_MATCHED'))
    def test_mid_epoch_resume_rejected(self):
        r=self.registry();r['LAST']['global_update']=5227
        with self.assertRaises(ValueError):a.validate_resume_ancestry(self.resume_auth(),'B1','run_fixture',r)
    def test_automatic_resume_rejected(self):
        with self.assertRaises(PermissionError):a.validate_resume_ancestry(SimpleNamespace(value={}), 'B1','run_fixture',self.registry())
    def test_resume_last_sha_mismatch_rejected(self):
        r=self.registry();r['LAST']['sha256']='wrong'
        with self.assertRaises(ValueError):a.validate_resume_ancestry(self.resume_auth(),'B1','run_fixture',r)
    def test_frozen_initialization_replay_and_parameter_groups(self):
        anchor,temporal,proof=paired_models();self.assertEqual(a.verify_initialization(anchor,temporal,proof),a.INITIAL)
        for kind,model in [('B0_MATCHED',anchor),('B1',temporal)]:
            _,groups=parameter_groups(model,check_counts=False);self.assertEqual(groups['counts'],frozen.COUNTS[kind])
        temporal.backbone.enc0.conv1.weight.data.add_(1)
        with self.assertRaises(ValueError):a.verify_initialization(anchor,temporal,proof)
        del anchor,temporal
    def test_scheduler_boundaries_unchanged(self):
        self.assertEqual(lr_for_update(1,steps_per_epoch=5228),1e-4/5228)
        self.assertEqual(lr_for_update(5228,steps_per_epoch=5228),1e-4)
        self.assertEqual(lr_for_update(261400,steps_per_epoch=5228),1e-6)
    def test_actual_step_backward_forward_counters_and_fixture_cleanup(self):
        model=torch.nn.Linear(1,1);optimizer=torch.optim.AdamW(model.parameters(),lr=1e-4)
        audit=a.RunAudit(self.root,'B1');audit.phase='TRAIN';back=torch.Tensor.backward
        with audit.instrument(model,optimizer):
            model(torch.ones(1,1)).sum().backward();optimizer.step()
        self.assertIs(torch.Tensor.backward,back);self.assertEqual(audit.counters.FORMAL_OPTIMIZER_STEPS,1)
        self.assertEqual(audit.counters.OPTIMIZER_STEPS_COMPLETED,1);self.assertEqual(audit.counters.BACKWARD_CALLS,1)
        self.assertEqual(audit.counters.TRAIN_FORWARD_CALLS,1);self.assertEqual(audit.counters.ENGINEERING_OPTIMIZER_STEPS,0)
        del model,optimizer
    def test_failure_after_real_step_retains_actual_count(self):
        model=torch.nn.Linear(1,1);optimizer=torch.optim.AdamW(model.parameters(),lr=1e-4)
        audit=a.RunAudit(self.root,'B1');audit.phase='TRAIN'
        try:
            with audit.instrument(model,optimizer):
                model(torch.ones(1,1)).sum().backward();optimizer.step();raise RuntimeError('TEST_FIXTURE_ONLY reporting error after update')
        except RuntimeError as error:audit.preserve_failure(error,{}, {'cleanup_success':True})
        failure=json.loads((self.root/'failure.json').read_text());self.assertEqual(failure['FORMAL_OPTIMIZER_STEPS'],1)
        before=(self.root/'failure.json').read_bytes()
        try:raise RuntimeError('second isolated fixture error')
        except RuntimeError as error:audit.preserve_failure(error,{}, {'cleanup_success':True})
        self.assertEqual((self.root/'failure.json').read_bytes(),before);self.assertFalse(failure['B1_start_allowed'])
        del model,optimizer
    def test_inference_counter_does_not_increment_update_or_backward(self):
        model=torch.nn.Linear(1,1);opt=torch.optim.AdamW(model.parameters());audit=a.RunAudit(self.root,'B1');audit.phase='VALIDATION'
        with audit.instrument(model,opt),torch.inference_mode():model(torch.ones(1,1))
        self.assertEqual(audit.counters.VALIDATION_FORWARD_CALLS,1);self.assertEqual(audit.counters.FORMAL_OPTIMIZER_STEPS,0)
        self.assertEqual(audit.counters.BACKWARD_CALLS,0);del model,opt
    def test_validation_diagnostics_are_descriptive(self):
        v=entry.enrich_validation({'per_tau_conditional_coverage':[(i+.5)/32 for i in range(32)]},10501,0)
        self.assertEqual(v['coverage_error'],[0.]*32);self.assertEqual(v['support_violation_count'],0)
    def test_non_owned_staging_root_rejected_without_deletion(self):
        with self.assertRaises(ValueError):a.staging_state(a.data.H_ROOT)
    def test_update_metric_event_does_not_duplicate_update_keyword(self):
        audit=a.RunAudit(self.root,'B1');audit.event('TRAIN_UPDATE_AUDITED',sample_ids=['fixture'],**{'update':1,'LR':1e-4})
        self.assertEqual(json.loads((self.root/'logs/epoch_000/step_events.jsonl').read_text())['update'],1)

    def test_formal_loop_failure_preserves_one_actual_fixture_update(self):
        self.exercise_loop_failure(after_update=True)

    def test_formal_loop_source_failure_preserves_zero_updates(self):
        self.exercise_loop_failure(after_update=False)

    def exercise_loop_failure(self,after_update):
        # Historical metadata only; toy tensors and an isolated output root.
        contract=frozen.RunnerContract.load();kind='B1';runid='run_20000101T000000_000001Z'
        value=a.authorization_fields(contract,kind);value.update(planned_run_id=runid,pretraining_gate_path=str(self.root/'gate.json'))
        auth=SimpleNamespace(value=value,sha256='TEST_FIXTURE_ONLY')
        firewall=a.RawFirewall(True);args=SimpleNamespace(resume_run_id=None,authorization=str(self.root/'authorization.json'))
        model=torch.nn.Linear(1,1)
        groups={'counts':frozen.COUNTS[kind],'disjoint':True,'complete_union':True}
        plan=frozen.batch_plan(0)[1]
        batch=SimpleNamespace(x_b13=torch.ones(2,1),indices=plan[0],sample_ids=['TEST_FIXTURE_ONLY_A','TEST_FIXTURE_ONLY_B'])
        class DummyDataset:
            def __init__(self,*args,**kwargs):pass
        class FailingLoader:
            def __init__(self,*args,**kwargs):
                if kwargs['num_workers']!=2 or kwargs['pin_memory'] or kwargs['persistent_workers'] or kwargs['prefetch_factor']!=1:
                    raise AssertionError('Frozen loader settings changed')
            def __iter__(self):
                if after_update:yield ['TEST_FIXTURE_ONLY']
                raise IOError('TEST_FIXTURE_ONLY source failure')
        def toy_update(m,opt,b,u):
            opt.zero_grad(set_to_none=True);m(b.x_b13).sum().backward()
            lr=lr_for_update(u,steps_per_epoch=5228)
            for group in opt.param_groups:group['lr']=lr
            opt.step()
            return {'LR':lr,'update':u,'actual_denominator':6860,'clipped':False,'pre_clip_norm':1.,'post_clip_norm':1.},object()
        def make_opt(m,k):return torch.optim.AdamW(m.parameters(),lr=1e-4),groups
        contexts=(patch.object(entry,'ROOT',self.root),patch.object(entry,'reject_before_construction',return_value=(args,contract,auth,firewall)),
              patch.dict(frozen.ROOTS,{'B1':self.root/'checkpoints'}),patch.object(entry,'repository_json_path',side_effect=lambda p:Path(p)),
              patch('train_b0_phase_b_finalfit_v1.environment',return_value={'TEST_FIXTURE_ONLY':True}),
              patch.object(entry,'load_sp04',return_value=None),patch.object(entry,'read_frozen_yunnan_mask',return_value=None),
              patch.object(entry.data,'load_frames',return_value={}),patch.object(entry,'paired_models',return_value=(model,model,self.proof)),
              patch.object(entry,'verify_initialization'),patch.object(entry,'parameter_groups',return_value=([],groups)),
              patch.object(torch.nn.Linear,'cuda',lambda m:m),patch.object(entry,'state_digest',return_value=a.INITIAL[kind]),
              patch.object(frozen,'optimizer_for',side_effect=make_opt),patch.object(entry,'allowed_sources',return_value=[]),
              patch.object(entry,'AuditedTemporalDataset',DummyDataset),patch.object(entry,'DataLoader',FailingLoader),
              patch.object(entry.data,'make_batch',return_value=batch),patch.object(original,'execute_update',side_effect=toy_update),
              patch.object(entry,'train_numerators',return_value=(1.,2.,6860,3)),
              patch.object(entry,'staging_state',return_value={'cleanup_success':True,'remaining_temporary_files':[]}))
        with ExitStack() as stack:
            for context in contexts:stack.enter_context(context)
            with self.assertRaisesRegex(IOError,'TEST_FIXTURE_ONLY source failure'):entry.main(kind,[])
        public=self.root/'docs/formal_training/b1_phase_a/runs'/runid
        failure=json.loads((public/'failure.json').read_text())
        self.assertEqual(failure['FORMAL_OPTIMIZER_STEPS'],int(after_update))
        self.assertEqual(failure['BACKWARD_CALLS'],int(after_update))
        self.assertEqual(failure['OPTIMIZER_STEPS_COMPLETED'],int(after_update))
        self.assertEqual(failure['completed_epoch'],0);self.assertIsNone(failure['last_verified_checkpoint'])
        self.assertEqual(failure['completed_epoch_identities'],{});self.assertFalse(failure['B1_start_allowed'])
        self.assertTrue(failure['source_cleanup_state']['cleanup_success'])
        self.assertFalse(list((self.root/'checkpoints').rglob('*.pt')))
        self.assertTrue((public/'partial_training_log.jsonl').is_file());del model

if __name__=='__main__':unittest.main()
