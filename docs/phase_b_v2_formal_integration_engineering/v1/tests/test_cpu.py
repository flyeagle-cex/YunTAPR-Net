"""New integration checks only. No models, real readers or optimizer updates."""
import copy
import json
import math
import sqlite3
import unittest
from unittest.mock import patch
import numpy as np
import torch
from yuntapr.experimental.phase_b_v2_ablations.config import RunSpec, proposed_runs, workload
from yuntapr.experimental.phase_b_v2_formal_integration_candidate import protocol as p
from yuntapr.experimental.phase_b_v2_formal_integration_candidate.metrics import Evaluator, block_id, TAU
from yuntapr.experimental.phase_b_v2_formal_integration_candidate.storage import Workspace, database, transaction
from yuntapr.experimental.phase_b_v2_formal_integration_candidate.state import B9State
from yuntapr.experimental.phase_b_v2_formal_integration_candidate.access import RealDataAdapter, RejectingAuthority, start_formal, verify_synthetic_bytes
from yuntapr.experimental.phase_b_v2_formal_integration_candidate.checkpoint import Store, Schedule, validate, SCHEMA
from yuntapr.experimental.phase_b_v2_runner_candidate import rng

def ident(profile=None):
    return p.identity(RunSpec('E0','B0_MATCHED_V2',2026),profile or p.Profile('SYNTHETIC_SMALL',2,2),
                      {k:p.digest(k) for k in ('data','qualification','scaler','mask','sp04','protocol','resource')})

def receipt(identity):
    profile=p.Profile(**identity['profile'])
    r=dict(complete=True,source_sha=p.digest(identity),ids_sha=p.digest(profile.ids('development')),
           summary=dict(scenes=profile.validation_scenes,n_valid=profile.validation_scenes*3430))
    r['receipt_sha']=p.digest(r); return r

def fixture(prob=(.5,.5,.25,.75),rates=(0.,1.,0.,2.),dtype=torch.float64):
    probability=torch.tensor(prob,dtype=dtype).reshape(1,1,1,-1)
    logit=torch.logit(probability); probability=torch.sigmoid(logit)
    q=torch.linspace(.11,3.21,32,dtype=torch.float64).reshape(1,32,1,1).expand(1,32,1,len(prob)).clone()
    rate=torch.tensor(rates,dtype=torch.float32).reshape(1,1,1,-1); mask=torch.ones_like(rate,dtype=torch.bool)
    return logit,probability,q,rate,mask,mask.clone()

def evaluate(values=None):
    ev=Evaluator((p.SCOPE+'/x',),p.digest('source'),Workspace())
    ev.add((p.SCOPE+'/x',),('2024-03-01T00:00:00Z',),*(values or fixture()))
    return ev,ev.finish()['summary']

class MetricsTests(unittest.TestCase):
    def test_hand_brier_auc_ap(self):
        ev,r=evaluate(); self.addCleanup(ev.close)
        self.assertAlmostEqual(r['brier'],.15625); self.assertAlmostEqual(r['auroc'],.875)
        self.assertAlmostEqual(r['average_precision'],5/6)
        self.assertEqual([g[1:] for g in ev.score_groups()],[(1,0),(1,1),(0,1)])
    def test_all_tau_coverage_pinball(self):
        ev,r=evaluate(); self.addCleanup(ev.close)
        y=np.log1p([1.,2.]); q=np.linspace(.11,3.21,32)
        cov=(y[None,:]<=q[:,None]).mean(axis=1)
        np.testing.assert_array_equal(r['coverage'],cov)
        err=y[None,:]-q[:,None]; pin=np.maximum(TAU[:,None]*err,(TAU[:,None]-1)*err)
        self.assertAlmostEqual(r['conditional_pinball'],pin.mean())
        self.assertAlmostEqual(r['q32_signed_bias'],1-.984375)
        self.assertAlmostEqual(r['core_fp64'],(r['s_occ']+r['s_qr'])/4)
    def test_bins_and_seven_strata(self):
        values=fixture((.1,.2,.3,.4,.5,.6,.7),(1,5,10,20,30,50,51))
        ev,r=evaluate(values); self.addCleanup(ev.close)
        self.assertEqual([s['n'] for s in r['rain_strata']],[1]*7)
        self.assertEqual(sum(b['n'] for b in r['reliability']),7)
        self.assertTrue(any(b['mean_probability'] is None for b in r['reliability']))
    def test_fp32_threshold(self):
        rates=[0.,.1,float(torch.nextafter(torch.tensor(.1),torch.tensor(float('inf')))),1.]
        ev,r=evaluate(fixture(rates=rates)); self.addCleanup(ev.close); self.assertEqual(r['n_rain'],2)
    def test_no_rain(self):
        ev,r=evaluate(fixture(rates=(0,0,0,0))); self.addCleanup(ev.close)
        self.assertIsNone(r['conditional_pinball']); self.assertIsNone(r['auroc']); self.assertIsNone(r['average_precision'])
        self.assertEqual(r['coverage'],[None]*32)
    def test_all_rain(self):
        ev,r=evaluate(fixture(rates=(1,1,1,1))); self.addCleanup(ev.close)
        self.assertEqual(r['average_precision'],1); self.assertIsNone(r['auroc'])
    def test_bf16_score_identity(self):
        ev,r=evaluate(fixture(dtype=torch.bfloat16)); self.addCleanup(ev.close)
        self.assertEqual(sum(a+b for _,a,b in ev.score_groups()),4)
    def test_tail_counts(self):
        v=list(fixture()); v[2]+=10
        ev,r=evaluate(v); self.addCleanup(ev.close)
        for tail in r['tail']:
            self.assertEqual((tail['exposures'],tail['rain'],tail['dry'],tail['scenes'],tail['unique_grid']),(4,2,2,1,4))
    def test_report_weights_only_roundtrip(self):
        ev,_=evaluate();self.addCleanup(ev.close);report=ev.finish()
        store=Store(Workspace());ref=store.save('metric_report',report)
        self.assertEqual(store.read(ref),report)
    def test_blocks_pooled(self):
        ids=(p.SCOPE+'/a',p.SCOPE+'/b'); ev=Evaluator(ids,p.digest('source'),Workspace()); self.addCleanup(ev.close)
        for i in range(2):ev.add((ids[i],),(f'2024-03-{1+7*i:02d}T00:00:00Z',),*fixture())
        r=ev.finish(); self.assertEqual(r['summary']['n_valid'],8)
        self.assertEqual([b['n_valid'] for b in r['blocks'][:3]],[4,4,0])
        self.assertEqual(sum(a+b for _,a,b in ev.score_groups(1)),4)
    def test_order_duplicate_and_poison(self):
        ev=Evaluator((p.SCOPE+'/x',),p.digest('source'),Workspace()); self.addCleanup(ev.close)
        with self.assertRaises(ValueError): ev.add((p.SCOPE+'/wrong',),('2024-03-01T00:00:00Z',),*fixture())
        with self.assertRaises(ValueError):ev.finish()
    def test_incomplete(self):
        ev=Evaluator((p.SCOPE+'/x',),p.digest('source'),Workspace()); self.addCleanup(ev.close)
        with self.assertRaises(ValueError): ev.finish()
    def test_bad_probability(self):
        v=list(fixture());v[1]=v[1]+.01
        with self.assertRaises(ValueError):evaluate(v)
    def test_zero_valid(self):
        v=list(fixture());v[-1]=torch.zeros_like(v[-1])
        with self.assertRaises(ValueError):evaluate(v)
    def test_nonfinite(self):
        v=list(fixture());v[2][0,0,0,0]=float('nan')
        with self.assertRaises((ValueError,FloatingPointError)):evaluate(v)
    def test_rank_reference_many_ties(self):
        generator=np.random.default_rng(26); probs=generator.choice([.05,.2,.5,.9],size=60); rates=generator.integers(0,2,size=60)
        ev,r=evaluate(fixture(probs,rates));self.addCleanup(ev.close)
        pp=np.array([float(torch.sigmoid(torch.logit(torch.tensor(x,dtype=torch.float64)))) for x in probs])
        pairs=(pp[rates==1,None]>pp[None,rates==0]).mean()+.5*(pp[rates==1,None]==pp[None,rates==0]).mean()
        self.assertAlmostEqual(r['auroc'],pairs)
    def test_block_edges(self):
        self.assertEqual(block_id('2024-10-31T23:59:59Z'),34)
        for date in ('2024-11-01T00:00:00Z','2024-02-29T00:00:00Z','2024-03-01'):
            with self.assertRaises(ValueError):block_id(date)

class StateTests(unittest.TestCase):
    def state(self,logical=False):
        w=Workspace(); i=ident(p.Profile('LOGICAL_B9',10455,10501) if logical else None)
        s=B9State(w,i); self.addCleanup(s.close);return w,i,s
    def test_full_b9_integer_coverage(self):
        _,i,s=self.state(True)
        for epoch in range(9):
            order=tuple(s.begin()); batches=[order[j:j+2] for j in range(0,len(order),2)]
            self.assertEqual(len(batches),5228);self.assertEqual(len(batches[-1]),1)
            s.finish_train(batches);s.validate(receipt(i));s.commit_last(p.digest(epoch))
        self.assertEqual(s.read()['updates'],47052);self.assertEqual(s.endpoint()['selected_synthetic_epoch'],9)
        self.assertFalse(s.endpoint()['BEST_used'])
        with self.assertRaises(ValueError):s.begin()
    def test_complete_small_and_reopen(self):
        w,i,s=self.state();order=tuple(s.begin());s.reserve();s.complete_step();s.finish_train([order]);s.validate(receipt(i));sha=p.digest('last');s.commit_last(sha)
        other=B9State(w,i);self.addCleanup(other.close);self.assertEqual(other.read(),s.read());other.check_restore(sha,1,1)
        with self.assertRaises(ValueError):other.check_restore(sha,0,0)
    def test_pending_no_refund(self):
        w,i,s=self.state();s.begin();s.reserve();other=B9State(w,i);self.addCleanup(other.close)
        self.assertEqual(other.read()['updates'],1)
        with self.assertRaises(ValueError):other.reserve()
        with self.assertRaises(ValueError):other.begin()
        with self.assertRaises(ValueError):other.check_restore(p.digest('x'),0,0)
    def test_last_before_validation(self):
        _,i,s=self.state();s.begin()
        with self.assertRaises(ValueError):s.commit_last(p.digest('x'))
        with self.assertRaises(ValueError):s.validate(receipt(i))
    def test_missing_scene(self):
        _,_,s=self.state(True);order=tuple(s.begin())
        with self.assertRaises(ValueError):s.finish_train([order[:2]])
    def test_wrong_order(self):
        _,_,s=self.state();order=tuple(s.begin());s.reserve();s.complete_step()
        with self.assertRaises(ValueError):s.finish_train([order[::-1]])
    def test_incomplete_validation(self):
        _,i,s=self.state();order=tuple(s.begin());s.reserve();s.complete_step();s.finish_train([order]);r=receipt(i);r['summary']['n_valid']-=1;r.pop('receipt_sha');r['receipt_sha']=p.digest(r)
        with self.assertRaises(ValueError):s.validate(r)
    def test_failure_blocks_last(self):
        _,_,s=self.state();s.fail('MODEL_NONFINITE')
        with self.assertRaises(ValueError):s.begin()
        with self.assertRaises(ValueError):s.commit_last(p.digest('last'))
    def test_concurrent_sqlite_lock(self):
        w,i,s=self.state(); other=B9State(w,i);self.addCleanup(other.close)
        with transaction(s.con):
            with self.assertRaises(sqlite3.OperationalError):other.begin()
    def test_identity_refusal(self):
        w,i,s=self.state();i['run']['seed']=2027
        with self.assertRaises(ValueError):B9State(w,i)
    def test_closed_matrix(self):
        runs=list(proposed_runs());self.assertEqual(len(runs),18)
        self.assertEqual(5228*9*18,846936)
        for r in runs:self.assertEqual(ident()['flags']['FORMAL_OPTIMIZER_STEPS'],0)
    def test_cross_process_pending_survives(self):
        import subprocess,sys
        w,i,s=self.state();s.begin();s.reserve()
        code="""import json,sys
from pathlib import Path
from yuntapr.experimental.phase_b_v2_formal_integration_candidate.storage import Workspace
from yuntapr.experimental.phase_b_v2_formal_integration_candidate.state import B9State
w=Workspace();w.root=Path(sys.argv[1]);s=B9State(w,json.loads(sys.argv[2]))
assert s.read()['pending'] and s.read()['updates']==1
try:s.reserve()
except ValueError:pass
else:raise AssertionError('Concurrent reservation unexpectedly admitted')
s.close()
"""
        result=subprocess.run([sys.executable,'-c',code,str(w.root),json.dumps(i)],capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))

class QuotaTests(unittest.TestCase):
    def test_exhausted_or_ambiguous_never_steps(self):
        from yuntapr.experimental.phase_b_v2_formal_integration_candidate.state import ActualQuota
        # Pure metadata fixtures, separate from the real campaign database.
        for rows in ([('B0_MATCHED_V2','COMPLETED')]*2,[('B1_V2','COMPLETED')]*4,[('B1_V2','RESERVED')]):
            quota=object.__new__(ActualQuota);quota.con=database(Workspace().file('fixture_quota.sqlite'));self.addCleanup(quota.con.close)
            quota.con.execute('CREATE TABLE quota(id INTEGER PRIMARY KEY,model TEXT,status TEXT,source TEXT)')
            quota.con.executemany('INSERT INTO quota(model,status,source) VALUES(?,?,?)',[(m,s,p.code_sha()) for m,s in rows])
            opt=torch.optim.AdamW([torch.tensor([1.],requires_grad=True)])
            with patch.object(opt,'step',side_effect=AssertionError('No optimizer call allowed')) as spy:
                with self.assertRaises(PermissionError):quota.perform(opt,'B0_MATCHED_V2')
                spy.assert_not_called()
            self.assertEqual(quota.con.execute('SELECT COUNT(*) FROM quota').fetchone()[0],len(rows))

class BoundaryTests(unittest.TestCase):
    def test_denial_before_path_protocol(self):
        class Trap:
            def __fspath__(self):raise AssertionError('Path conversion attempted')
        for f in (RealDataAdapter().open_scene,RealDataAdapter().open_manifest,RealDataAdapter().open_artifact,
                  RejectingAuthority().verify_execution,RejectingAuthority().verify_resume,start_formal):
            with self.assertRaises(PermissionError):f(Trap(),approval={'APPROVED':True})
    def test_memory_sha(self):
        import hashlib
        self.assertEqual(verify_synthetic_bytes(b'abc',hashlib.sha256(b'abc').hexdigest())['bytes'],3)
        with self.assertRaises(ValueError):verify_synthetic_bytes(b'abc','0'*64)
    def test_disk_limit(self):
        w=Workspace(); con=database(w.file('bounded.sqlite'),max_bytes=16384);self.addCleanup(con.close)
        con.execute('CREATE TABLE t(b BLOB)')
        with self.assertRaises(sqlite3.DatabaseError):con.execute('INSERT INTO t VALUES(?)',(b'x'*30000,))
    def test_disk_admission(self):
        with patch('shutil.disk_usage',return_value=type('Disk',(),{'free':0})()):
            with self.assertRaises(RuntimeError):database(Workspace().file('x.sqlite'))
    def test_schedule_prefix(self):
        from yuntapr.experimental.phase_b_v2_ablations.config import learning_rate_prefix
        s=Schedule();state=s.state_dict();state['completed']=47052;s.load_state_dict(state)
        self.assertEqual(s.completed,47052);self.assertAlmostEqual(learning_rate_prefix(5228),1e-4)
        state['original_horizon']=47052
        with self.assertRaises(ValueError):s.load_state_dict(state)
    def test_store_roundtrip_sha(self):
        store=Store(Workspace());ref=store.save('ok',{'synthetic':torch.tensor([1.])})
        self.assertEqual(float(store.read(ref)['synthetic']),1.)
        record=json.loads(ref.read_text());record['sha256']='0'*64;ref.write_text(json.dumps(record))
        with self.assertRaises(ValueError):store.read(ref)
    def test_partial_blob(self):
        store=Store(Workspace());ref=store.save('ok',{'synthetic':torch.tensor([1.])});(store.root/'ok.pt').write_bytes(b'partial')
        with self.assertRaises(ValueError):store.read(ref)
    def test_save_faults(self):
        for fault in ('after_serialization','after_blob','rename_locked'):
            store=Store(Workspace())
            with self.assertRaises(OSError):store.save('fault',{'x':torch.tensor(1.)},fault=fault)
            self.assertFalse((store.root/'fault.ref.json').exists())
    def test_existing_lock(self):
        store=Store(Workspace());(store.root/'locked.lock').write_text('owned')
        with self.assertRaises(FileExistsError):store.save('locked',{})
        self.assertEqual((store.root/'locked.lock').read_text(),'owned')
    def test_no_overwrite(self):
        store=Store(Workspace());store.save('once',{})
        with self.assertRaises(FileExistsError):store.save('once',{})
    def test_external_checkpoint_denied(self):
        from pathlib import Path
        store=Store(Workspace())
        with self.assertRaises(PermissionError):store.read(Path('Z:/2025/private.pt'))
        with self.assertRaises(PermissionError):store.resume_real('APPROVED')

def checkpoint_fixture():
    from yuntapr.experimental.phase_b_v2_integration.controls import synthetic_epoch_order
    from yuntapr.experimental.phase_b_v2_ablations.config import learning_rate_prefix
    i=ident();profile=p.Profile(**i['profile']);model={'w':torch.tensor([1.,2.])}
    group={'params':[0],'lr':learning_rate_prefix(1),'betas':(.9,.999),'weight_decay':.01}
    opt={'param_groups':[group],'state':{0:{'step':torch.tensor(1.),'exp_avg':torch.ones(2),'exp_avg_sq':torch.ones(2)}}}
    template={**copy.deepcopy(opt),'_shapes':{0:(2,)}}
    schedule=Schedule();schedule.completed=1;initial=p.digest('initial')
    payload=dict(schema=SCHEMA,identity=i,model=model,optimizer=opt,scheduler=schedule.state_dict(),rng=rng.capture(),
        initial_sha=initial,epoch=1,update=1,parent_last_sha=None,
        train=dict(scenes=2,batches=1,mode='SYNTHETIC_SMALL',ids_sha=p.digest(synthetic_epoch_order(profile.ids('train'),2026,0))),
        validation=receipt(i),quota={'hard_limit':4,'reserved':1,'FORMAL_OPTIMIZER_STEPS':0})
    return payload,i,copy.deepcopy(model),template,initial

class SchemaTests(unittest.TestCase):
    def test_complete_schema(self):validate(*checkpoint_fixture())
    def test_missing_components(self):
        for key in ('model','optimizer','rng','scheduler','validation','parent_last_sha','quota'):
            args=list(checkpoint_fixture());args[0].pop(key)
            with self.assertRaises(ValueError):validate(*args)
    def test_identity_fields(self):
        for key,value in (('seed',2027),('experiment_id','E1'),('model','B1_V2')):
            args=list(checkpoint_fixture());args[0]=copy.deepcopy(args[0]);args[0]['identity']['run'][key]=value
            with self.assertRaises(ValueError):validate(*args)
    def test_wrong_epoch(self):
        args=list(checkpoint_fixture());args[0]['epoch']=2
        with self.assertRaises(ValueError):validate(*args)
    def test_moment_missing(self):
        args=list(checkpoint_fixture());args[0]['optimizer']['state']={}
        with self.assertRaises(ValueError):validate(*args)
    def test_model_shape(self):
        args=list(checkpoint_fixture());args[0]['model']['w']=torch.ones(3)
        with self.assertRaises(ValueError):validate(*args)
    def test_lr_mismatch(self):
        args=list(checkpoint_fixture());args[0]['optimizer']['param_groups'][0]['lr']=.1
        with self.assertRaises(ValueError):validate(*args)
    def test_nan_moment(self):
        args=list(checkpoint_fixture());args[0]['optimizer']['state'][0]['exp_avg'][0]=float('nan')
        with self.assertRaises(FloatingPointError):validate(*args)
    def test_validation_tamper(self):
        args=list(checkpoint_fixture());args[0]['validation']['summary']['scenes']=1
        with self.assertRaises(ValueError):validate(*args)
    def test_formal_quota_rejected(self):
        args=list(checkpoint_fixture());args[0]['quota']['FORMAL_OPTIMIZER_STEPS']=1
        with self.assertRaises(ValueError):validate(*args)

class MetadataTests(unittest.TestCase):
    def scene(self):
        from datetime import datetime,timedelta,timezone
        a=datetime(2024,3,1,1,0,tzinfo=timezone.utc)
        return dict(id='SYNTHETIC_METADATA',year=2024,role='DEVELOPMENT',qualification='M1_Q1',analysis=a.isoformat(),
            window_start=(a-timedelta(minutes=30)).isoformat(),window_end=a.isoformat(),product='IMERG_V07_Final',units='mm hr-1',
            artifacts={k:p.digest(k) for k in ('scaler','mask','sp04','qualification','imerg')},
            slots=[dict(nominal=(a-timedelta(minutes=o)).isoformat(),obs_start=(a-timedelta(minutes=o)).isoformat(),
                   obs_end=(a-timedelta(minutes=o-5)).isoformat(),created=(a+timedelta(minutes=5)).isoformat(),sha256=p.digest(o),channel='B13') for o in (60,50,40,30,20,10)])
    def test_late_creation_not_causality(self):
        from yuntapr.experimental.phase_b_v2_formal_integration_candidate.access import audit_scene_metadata
        r=audit_scene_metadata(self.scene());self.assertEqual(r['file_created_after_analysis'],6);self.assertFalse(r['real_source_authenticated'])
    def test_sealed_role_product(self):
        from yuntapr.experimental.phase_b_v2_formal_integration_candidate.access import audit_scene_metadata
        for k,v in (('year',2025),('role','TRAIN'),('product','IMERG_Early'),('units','mm')):
            s=self.scene();s[k]=v
            with self.assertRaises((PermissionError,ValueError)):audit_scene_metadata(s)
    def test_future_observation(self):
        from yuntapr.experimental.phase_b_v2_formal_integration_candidate.access import audit_scene_metadata
        s=self.scene();s['slots'][0]['obs_end']='2024-03-01T02:00:00+00:00'
        with self.assertRaises(ValueError):audit_scene_metadata(s)
    def test_slot_order(self):
        from yuntapr.experimental.phase_b_v2_formal_integration_candidate.access import audit_scene_metadata
        s=self.scene();s['slots'].reverse()
        with self.assertRaises(ValueError):audit_scene_metadata(s)

if __name__=='__main__':unittest.main()
