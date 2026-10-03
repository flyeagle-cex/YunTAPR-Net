"""TEST_FIXTURE_ONLY: no formal run, no raw data, temporary optimizer states only."""
import copy,json,math,os,tempfile,unittest,uuid,shutil
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
import numpy as np,torch
from yuntapr.contracts.loader import REPO_ROOT,sha256
from yuntapr.data import dataset_b1 as d
from yuntapr.models.b1 import paired_models,MISMATCHED,B1Model
from yuntapr.training import paired_phase_a as p
from yuntapr.training.phase_a_protocol import ValidationSelection,state_digest,seed_reproducibility,lr_for_update,capture_rng
from yuntapr.training.phase_a_validation import GlobalValidationAccumulator
from yuntapr.models.probability_heads import B0Output


@contextmanager
def owned_temporary_directory():
    # Inherited Windows ACLs; tempfile.mkdtemp mode=0700 fails under this sandbox.
    parent=Path(tempfile.gettempdir()).resolve();root=parent/('yuntapr_paired_fixture_'+uuid.uuid4().hex)
    root.mkdir()
    try:yield str(root)
    finally:
        if root.resolve().parent!=parent or not root.name.startswith('yuntapr_paired_fixture_'):raise ValueError('Unsafe fixture cleanup')
        shutil.rmtree(root)


class ProtocolTests(unittest.TestCase):
    TEST_FIXTURE_ONLY=True
    @classmethod
    def setUpClass(cls):
        seed_reproducibility();cls.anchor,cls.temporal,cls.proof=paired_models()

    @classmethod
    def tearDownClass(cls):del cls.anchor,cls.temporal

    def test_independent_reseed_replay(self):
        a,b,proof=paired_models();self.assertEqual(proof,self.proof);del a,b
    def test_shared_tensors_bit_identical(self):
        a,b=self.anchor.state_dict(),self.temporal.state_dict()
        shared=[n for n in a if n not in MISMATCHED]
        self.assertEqual(len(shared),self.proof['same_shape_tensor_count'])
        self.assertTrue(all(torch.equal(a[n],b[n]) for n in shared))
    def test_exact_mismatched_kernels(self):
        a,b=self.anchor.state_dict(),self.temporal.state_dict()
        self.assertEqual({n for n in a if a[n].shape!=b[n].shape},MISMATCHED)
        self.assertTrue((b['backbone.enc0.skip.weight']==0).all())
        self.assertEqual({n:state_digest(b[n]) for n in MISMATCHED},self.proof['native_b1_input_kernel_sha256'])
    def test_parameter_counts(self):
        self.assertEqual(sum(x.numel() for x in self.anchor.parameters()),4329361)
        self.assertEqual(sum(x.numel() for x in self.temporal.parameters()),4331761)
    def test_optimizer_groups_and_exact_settings(self):
        for kind,model in [('B1',self.temporal),('B0_MATCHED',self.anchor)]:
            optimizer,e=p.optimizer_for(model,kind);self.assertEqual(e['counts'],p.COUNTS[kind])
            self.assertTrue(e['complete_union'] and e['disjoint'])
            for g in optimizer.param_groups:
                self.assertEqual(g['betas'],(.9,.999));self.assertEqual(g['eps'],1e-8)
                for k in ('amsgrad','maximize','capturable','differentiable','foreach','fused'):self.assertIs(g[k],False)
            del optimizer
    def test_unknown_parameter_stops(self):
        m=torch.nn.Linear(1,1)
        with self.assertRaisesRegex(ValueError,'Unknown'):p.parameter_groups(m,check_counts=False)
    def test_scaler_sha_and_no_refit(self):
        path=REPO_ROOT/d.FREEZE/'normalization_b1_2023_shared_v1.json';self.assertEqual(sha256(path),d.SCALER_SHA)
        x=np.array([271.60516,260.],dtype=np.float32)
        expected=((x.astype(np.float64)-271.60515414265217)/19.93959597783802).astype(np.float32)
        np.testing.assert_array_equal(d.normalize(x),expected)
    def test_bad_normalization_input_rejected(self):
        for x in [np.array([np.nan],np.float32),np.array([270.],np.float64)]:
            with self.assertRaises(ValueError):d.normalize(x)
    def test_frozen_four_sample_manifests(self):
        for k in ('B1','B0_MATCHED'):
            for year,count in [(2023,10455),(2024,10501)]:self.assertEqual(len(d.load_records(k,year)),count)
    def test_exact_shared_targets(self):
        for year in (2023,2024):
            a,b=d.load_records('B1',year),d.load_records('B0_MATCHED',year)
            keys=('sample_id','imerg_day_path','imerg_sha256','imerg_index')
            self.assertEqual([[r[k] for k in keys] for r in a],[[r[k] for k in keys] for r in b])
    def test_2025_february_hard_reject_before_io(self):
        for date in ['2025-03-01T00:00:00Z','2023-02-28T23:50:00Z','2024-11-01T00:00:00Z']:
            with self.assertRaises(ValueError):d.allowed_time(date)
        for path,kind in [(d.H_ROOT/'202503/01/x.nc','B13'),(d.IMERG_ROOT/'2025/imerg_20250301.nc','IMERG'),(d.H_ROOT/'202302/28/x.nc','B13')]:
            with self.assertRaises(ValueError):d.guard_source(path,kind)
    def test_source_root_no_fallback(self):
        with self.assertRaisesRegex(ValueError,'root'):d.guard_source(Path('F:/alternate/202303.nc'),'B13')
    def test_slot_order_and_matched_latest(self):
        r=d.load_records('B1',2023)[0];m=d.load_records('B0_MATCHED',2023)[0]
        a=d.utc(r['analysis_time'])
        for s,o in enumerate(d.OFFSETS):self.assertEqual(d.utc(r[f'slot_{s}_nominal']),a-d.timedelta(minutes=o))
        self.assertEqual(m['expected_nominal'],r['slot_5_nominal'])
    def test_last_october_target_analysis_midnight_is_metadata_only(self):
        r=d.load_records('B1',2023)[-1]
        self.assertEqual(d.utc(r['window_start']).month,10)
        self.assertEqual(d.utc(r['analysis_time']),d.utc(r['window_start'])+d.timedelta(minutes=30))
        self.assertTrue(all(d.allowed_time(r[f'slot_{s}_nominal']).month==10 for s in range(6)))
    def test_M1_missing_partial_allfill(self):
        good={'nominal':'2023-03-01T00:00:00Z','present':'True','readable':'True','decoded':'True','full_valid':'True','metadata_valid':'True','valid_count':'251001','obs_start':'2023-03-01T00:00:40Z','obs_end':'2023-03-01T00:09:40Z'}
        d.check_frame(good,'2023-03-01T01:00:00Z')
        for k,v in [('present','False'),('readable','False'),('full_valid','False'),('valid_count','0'),('metadata_valid','False'),('obs_end','2023-03-01T01:01:00Z')]:
            bad={**good,k:v}
            with self.assertRaises(ValueError):d.check_frame(bad,'2023-03-01T01:00:00Z')
    def test_tensor_M1_no_placeholder(self):
        x=torch.zeros(1,6,501,501);mask=torch.ones_like(x,dtype=torch.bool);mask[0,0,0,0]=False
        with self.assertRaisesRegex(ValueError,'M1'):self.temporal(x,mask)
    def test_wrong_channel_count(self):
        x=torch.zeros(1,1,501,501)
        with self.assertRaises(ValueError):self.temporal(x,torch.ones_like(x,dtype=torch.bool))
    def test_scheduler_boundaries(self):
        self.assertEqual(lr_for_update(1,steps_per_epoch=p.STEPS),1e-4/5228)
        self.assertEqual(lr_for_update(p.W,steps_per_epoch=p.STEPS),1e-4)
        self.assertEqual(lr_for_update(p.U,steps_per_epoch=p.STEPS),1e-6)
        self.assertLess(lr_for_update(1,steps_per_epoch=p.STEPS),1e-6)
        self.assertGreaterEqual(lr_for_update(p.W+1,steps_per_epoch=p.STEPS),1e-6)
    def test_scheduler_no_update_outside_horizon(self):
        for u in [0,p.U+1,True,1.5]:
            with self.assertRaises(ValueError):lr_for_update(u,steps_per_epoch=p.STEPS)
    def test_full_fifty_epoch_coverage(self):
        for ep in range(1,51):
            c=p.EpochCoverage(ep)
            for ix in c.plan:c.add(ix,len(ix)*3430)
            proof=c.complete();self.assertEqual(proof['samples'],10455);self.assertEqual(proof['updates'],5228)
            self.assertEqual(proof['tail_denominator'],3430);self.assertEqual(len(set(c.seen)),10455)
            self.assertEqual(c.plan[-1],[c.order[-1]])
    def test_epoch_order_replay_no_global_rng(self):
        torch.manual_seed(1);a=p.batch_plan(2);torch.manual_seed(9);self.assertEqual(a,p.batch_plan(2))
        self.assertNotEqual(a[0],p.batch_plan(3)[0])
    def test_duplicate_reordered_padded_coverage_rejected(self):
        for bad in [[],[0,0],[0,1,2]]:
            c=p.EpochCoverage(1)
            with self.assertRaises(ValueError):c.add(bad,len(bad)*3430)
        c=p.EpochCoverage(1)
        with self.assertRaises(ValueError):c.complete()
    def test_actual_full_vs_singleton_denominator(self):
        def item(i):
            mask=np.zeros((1,100,100),bool);mask.reshape(-1)[:3430]=True
            return {'x':np.zeros((6,501,501),np.float32),'y':np.zeros((1,100,100),np.float32),'valid':np.ones((1,100,100),bool),'yunnan':mask,'sample_id':str(i),'index':i}
        for n in (1,2):
            b=d.make_batch([item(i) for i in range(n)],'cpu');self.assertEqual(int((b.imerg_valid_mask&b.yunnan_eval_mask).sum()),n*3430)
    def test_selection_vs_earlystop_and_earliest_ties(self):
        s=ValidationSelection();self.assertTrue(s.update(1,1.)['checkpoint_selected']);a=s.update(2,.99999)
        self.assertTrue(a['checkpoint_selected']);self.assertFalse(a['early_stop_improvement'])
        self.assertFalse(s.update(3,.99999)['checkpoint_selected']);self.assertEqual(s.selected_checkpoint_epoch,2)
        for ep in range(4,10):res=s.update(ep,1.)
        self.assertTrue(res['stop'])
    def test_authorization_missing_before_any_io(self):
        with patch('yuntapr.training.paired_phase_a.sha256',side_effect=AssertionError('No I/O')):
            with self.assertRaises(PermissionError):p.Authorization.load(None,None,None,'B1')
    def test_authorization_raw_2025_and_checkpoint_paths_reject_before_sha(self):
        from types import SimpleNamespace
        contract=SimpleNamespace(root=REPO_ROOT)
        with patch('yuntapr.training.paired_phase_a.sha256',side_effect=AssertionError('No raw/checkpoint I/O')):
            for path in [d.H_ROOT/'202503/01/authorization.json',d.IMERG_ROOT/'2025/imerg_20250301.nc',p.ROOTS['B1']/'authorization.json']:
                with self.assertRaises(PermissionError):p.Authorization.load(path,'fake',contract,'B1')
    def test_formal_entry_missing_auth_no_construction(self):
        import sys
        sys.path.insert(0,str(REPO_ROOT/'scripts'));import paired_phase_a_entry as entry
        with patch.object(entry.RunnerContract,'load',side_effect=AssertionError('Metadata loader reached')),patch.object(entry,'paired_models',side_effect=AssertionError('Model construction')):
            for k in ('B1','B0_MATCHED'):
                with self.assertRaises(PermissionError):entry.main(k,[])
    def test_global_validation_partition_invariance(self):
        from types import SimpleNamespace
        y=torch.tensor([0.,.1,.2,5.],dtype=torch.float32).reshape(4,1,1,1);q=torch.arange(1,33,dtype=torch.float64).reshape(1,32,1,1).expand(4,-1,-1,-1)/10+.2
        z=torch.tensor([-1.,0.,1.,2.]).reshape(4,1,1,1);mask=torch.ones_like(y,dtype=torch.bool)
        def output(s):return SimpleNamespace(rain_logit=z[s],rain_prob=torch.sigmoid(z[s]),conditional_quantiles_log=q[s],conditional_quantiles_physical=torch.expm1(q[s]))
        a,b=GlobalValidationAccumulator(),GlobalValidationAccumulator();a.add(output(slice(None)),y,mask,mask)
        for s in [slice(0,3),slice(3,4)]:b.add(output(s),y[s],mask[s],mask[s])
        self.assertEqual(a.n_valid,4);self.assertAlmostEqual(a.report()['global_val_core_loss'],b.report()['global_val_core_loss'],places=14)
        self.assertEqual(a.report()['N_rain'],2)
    def fixture_payload(self):
        model=torch.nn.Conv2d(1,1,1);opt=torch.optim.AdamW(model.parameters(),lr=1e-4,foreach=False,fused=False)
        # Isolated temporary update only, never an actual training sample or checkpoint.
        model(torch.ones(1,1,1,1)).sum().backward();opt.step()
        for state in opt.state.values():state['step'].fill_(p.STEPS)
        for g in opt.param_groups:g['lr']=lr_for_update(p.STEPS,steps_per_epoch=p.STEPS)
        expected={'model':'B1','run_id':'run_TEST_FIXTURE_ONLY','TEST_FIXTURE_ONLY':True};sel=ValidationSelection();sel.update(1,1.)
        c=p.EpochCoverage(1)
        for ix in c.plan:c.add(ix,len(ix)*3430)
        v={'global_val_core_loss':1.,'D_valid':p.VAL*3430,'S_occ':float(p.VAL*3430),'S_qr':0.}
        return model,opt,p.payload_for(model,opt,expected,sel,1,c.complete(),v),expected
    def test_checkpoint_completed_boundary_and_no_partial(self):
        m,o,data,expected=self.fixture_payload();p.validate_payload(data,expected)
        for key,value in [('completed_epoch',0),('global_update',1),('validation_completed',False),('validation_samples',1)]:
            bad={**data,key:value}
            with self.assertRaises(ValueError):p.validate_payload(bad,expected)
    def test_provenance_reject_before_state_application(self):
        m,o,data,expected=self.fixture_payload();before=state_digest(m.state_dict())
        with self.assertRaisesRegex(ValueError,'Provenance'):p.validate_payload(data,{**expected,'normalization_sha256':'bad'})
        self.assertEqual(state_digest(m.state_dict()),before)
    def test_checkpoint_hash_nonfinite_and_optimizer_compatibility(self):
        m,o,data,expected=self.fixture_payload();bad=copy.deepcopy(data);bad['model_state_dict']['weight'].fill_(float('nan'))
        bad['model_state_dict_sha256']=state_digest(bad['model_state_dict'])
        with self.assertRaisesRegex(ValueError,'Nonfinite'):p.validate_payload(bad,expected)
        bad=copy.deepcopy(data);bad['optimizer_state_dict']['param_groups'][0]['eps']=.1
        with self.assertRaises(ValueError):p.compatible_states(bad,m,o)
    def test_epoch_boundary_resume_replays_next_update_and_rng(self):
        m,o,data,expected=self.fixture_payload()
        with owned_temporary_directory() as td:
            path=Path(td)/expected['run_id'];path.mkdir();file=path/'epoch_001.pt';torch.save(data,file)
            identity={'absolute_local_path':str(file),'epoch':1,'global_update':p.STEPS,'bytes':file.stat().st_size,'sha256':sha256(file)}
            def next_update(model,opt):
                opt.zero_grad(set_to_none=True)
                for g in opt.param_groups:g['lr']=lr_for_update(p.STEPS+1,steps_per_epoch=p.STEPS)
                model(torch.rand(1,1,1,1)).sum().backward();opt.step();return state_digest(model.state_dict()),state_digest(opt.state_dict())
            p.restore_rng(data['rng_states']);answer=next_update(m,o)
            m2=torch.nn.Conv2d(1,1,1);o2=torch.optim.AdamW(m2.parameters(),lr=1e-4,foreach=False,fused=False)
            p.load_checkpoint(identity,expected,m2,o2,fixture_root=td);self.assertEqual(answer,next_update(m2,o2))
    def test_bad_file_hash_rejects_before_deserialization(self):
        with owned_temporary_directory() as td:
            root=Path(td)/'run_TEST_FIXTURE_ONLY';root.mkdir();f=root/'epoch_001.pt';f.write_bytes(b'fixture')
            identity={'absolute_local_path':str(f),'epoch':1,'global_update':p.STEPS,'bytes':7,'sha256':'bad'}
            with patch('torch.load',side_effect=AssertionError('Must not deserialize')):
                with self.assertRaises(ValueError):p.load_checkpoint(identity,{'model':'B1','run_id':root.name},None,None,fixture_root=td)


if __name__=='__main__':unittest.main()
