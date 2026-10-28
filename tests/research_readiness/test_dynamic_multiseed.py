"""Only new seed dispatch and changed legacy task wiring; no real training."""
import copy,json,os,statistics,unittest,uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from yuntapr.contracts.loader import REPO_ROOT
from yuntapr.experimental.research_readiness import dynamic_multiseed as m,dynamic_training as old

class DynamicMultiseedTests(unittest.TestCase):
    def setUp(self):
        self.dir=REPO_ROOT/'tests/research_readiness/.local'/('dynamic_seeds_'+uuid.uuid4().hex);self.dir.mkdir(parents=True)
        self.prepared=dict(roles={'Train':dict(bytes_per_pass=26424262556,file_count=7918),'Development':dict(bytes_per_pass=26639253112,file_count=7950)})
        self.caps=m.budget(self.prepared)
    def test_exact_manifest_budget_and_no_extra_payload_cache(self):
        self.assertEqual(self.caps['total_updates'],17280);self.assertEqual(self.caps['total_source_bytes'],1910287815360);self.assertEqual(self.caps['total_source_files'],571252)
        self.assertEqual(self.caps['total_source_bytes_per_model'],dict(B7=477571953840,B8=477571953840))
        self.assertEqual(self.caps['initial_free_bytes'],96*1024**3);self.assertEqual(self.caps['replay_allowance'],0);self.assertEqual(self.caps['dynamic_extra_raw_source_bytes'],0)
    def proposal(self):
        p=dict(proposal_sha256='p'*64,execution_code_commit='c'*40,tasks=[dict(model=k,seed=s) for k,s in m.TASKS],budget=self.caps,scientific_choices={'unchanged':True})
        v=dict(output_root=str(self.dir/'new'));a=dict(approved_by_researcher=True,code_commit='c'*40,proposal_sha256=p['proposal_sha256'],tasks=p['tasks'],budget=p['budget'],scientific_choices=p['scientific_choices'],output_root=v['output_root'],decision_id='SYNTHETIC_ONLY')
        return p,v,a
    def test_old_or_partial_grant_rejected_before_gpu_or_source(self):
        p,v,a=self.proposal();m.validate_approval(a,p,v,'c'*40)
        for key,value in [('approved_by_researcher',False),('tasks',[dict(model='B7',seed=2029)]),('budget',dict(self.caps,replay_allowance=1)),('code_commit','d'*40),('output_root','other')]:
            with self.assertRaises(PermissionError):m.validate_approval(dict(a,**{key:value}),p,v,'c'*40)
        with patch.object(m,'checked',side_effect=PermissionError('No new grant')),patch.object(m,'resources',side_effect=AssertionError('No GPU')):
            with self.assertRaises(PermissionError):m.execute(REPO_ROOT,'p','v','a','c'*40)
    def test_all_four_workers_use_task_seed_new_ledger_and_paired_reference(self):
        p,v,a=self.proposal();out=Path(v['output_root']);out.mkdir();v['seed_references']={str(s):str(self.dir/f'ref{s}') for s in (2030,2031)}
        m.write(out/'authorization_binding.json',dict(controller_pid=os.getppid(),approval=a))
        for i,(kind,seed) in enumerate(m.TASKS):
            m.write(out/f'task_{i+1}_claim.json',dict(index=i,controller_pid=os.getppid(),code_commit='c'*40))
            with patch.object(m,'checked',return_value=(p,v,a,self.prepared)),patch.object(m,'run_task',return_value='NO_TRAINING') as run:
                self.assertEqual(m.worker(REPO_ROOT,'p','v','a','c'*40,i),'NO_TRAINING')
            args=run.call_args.args;kw=run.call_args.kwargs;self.assertEqual(args[-2:],(kind,seed));self.assertEqual(kw['static_name'],f'{kind}_s{seed}_static_source.sqlite')
            self.assertEqual(kw['pair_reference'],Path(v['seed_references'][str(seed)]) if kind=='B7' else out/f'B7_s{seed}')
    def test_legacy_seed2029_worker_delegates_without_changing_scope(self):
        package=self.dir/'legacy';package.mkdir();p=dict(budget={});v=dict(output_root=str(package),historical_pair='SYNTHETIC_B6_2029');a={'decision_id':'SYNTHETIC'}
        old.write(package/'authorization_binding.json',dict(controller_pid=os.getppid(),approval=a));old.write(package/'task_1_claim.json',dict(index=0,controller_pid=os.getppid(),code_commit='c'*40))
        with patch.object(old,'checked',return_value=(p,v,a,{})),patch.object(old,'run_task',return_value='NO_TRAINING') as run:
            self.assertEqual(old.worker(REPO_ROOT,'p','v','a','c'*40,0),'NO_TRAINING')
        self.assertEqual(run.call_args.args[-2:],('B7',2029));self.assertEqual(run.call_args.kwargs['static_name'],'B7_static_source.sqlite')
    def controller(self,fail_at=None):
        p,v,a=self.proposal();out=Path(v['output_root']);calls=[];caps=self.caps
        class Process:
            def __init__(inner,cmd,**kw):
                inner.i=int(cmd[-1]);kind,seed=m.TASKS[inner.i];calls.append((kind,seed,kw['env']['PYTHONHASHSEED'],kw['creationflags']))
            def wait(inner,timeout):
                if inner.i==fail_at:return 2
                kind,seed=m.TASKS[inner.i];folder=out/f'{kind}_s{seed}';folder.mkdir()
                m.write(folder/'completion.json',dict(status='COMPLETE_TRAIN_AND_DEV_EVALUATION',model=kind,seed=seed,optimizer_updates=4320,code_commit='c'*40,total_logical_source_bytes=477571953840,total_logical_source_files=142813))
                for name in ('paired_initial_identity.json','paired_orders.json'):m.write(folder/name,{'same_within_seed':seed})
                m.write(folder/f'{kind}_development_09.json',{'synthetic':True})
                return 0
            def poll(inner):return 2 if inner.i==fail_at else 0
        with patch.object(m,'checked',return_value=(p,v,a,self.prepared)),patch.object(m,'resources',return_value={}),patch.object(m.shutil,'disk_usage',return_value=SimpleNamespace(free=100*1024**3)),patch.object(m,'admit_source'),patch.object(m.subprocess,'Popen',Process),patch.object(m,'paired_difference',return_value={'synthetic':True}),patch.object(m,'summarize') as summary:
            if fail_at is None:
                result=m.execute(REPO_ROOT,'p','v','a','c'*40);self.assertEqual(result['updates'],17280);summary.assert_called_once()
            else:
                with self.assertRaises(RuntimeError):m.execute(REPO_ROOT,'p','v','a','c'*40)
                summary.assert_not_called();self.assertEqual(m.read(out/'failure.json')['completed_updates'],4320*fail_at)
            with self.assertRaises(PermissionError):m.execute(REPO_ROOT,'p','v','a','c'*40)
        return calls
    def test_serial_order_seed_env_once_only_and_hidden_workers(self):
        calls=self.controller();self.assertEqual([(k,s) for k,s,h,f in calls],list(m.TASKS));self.assertTrue(all(h==str(s) and f==m.worker_creation_flags() for k,s,h,f in calls))
    def test_second_task_failure_preserves_first_and_blocks_remaining_without_replay(self):
        self.assertEqual([(k,s) for k,s,h,f in self.controller(fail_at=1)],list(m.TASKS[:2]))
    def test_insufficient_disk_fails_before_marker_without_cleanup(self):
        p,v,a=self.proposal()
        with patch.object(m,'checked',return_value=(p,v,a,self.prepared)),patch.object(m.shutil,'disk_usage',return_value=SimpleNamespace(free=95*1024**3)),patch.object(m,'resources',side_effect=AssertionError('No GPU')):
            with self.assertRaises(RuntimeError):m.execute(REPO_ROOT,'p','v','a','c'*40)
        self.assertFalse(Path(v['output_root']).exists())
    def test_q32_overshoot_not_called_improvement_and_sample_SD_uses_three_seeds(self):
        pairs={}
        for seed,a,b in [(2029,.97,.96),(2030,.99,.98),(2031,.96,.97)]:
            pairs[seed]=dict(q32_coverage=a-b,q32_signed_bias=a-b,q32_absolute_error=abs(a-.984375)-abs(b-.984375),brier={2029:-1.,2030:0.,2031:1.}[seed])
        r=m.aggregate(pairs);self.assertEqual(r['brier']['mean'],0);self.assertEqual(r['brier']['sample_sd'],1)
        self.assertEqual(r['q32_coverage']['improvement'],'CLOSER_TO_NOMINAL');self.assertGreater(r['q32_absolute_error']['by_seed']['2030'],0)
        with self.assertRaises(ValueError):m.aggregate({2029:pairs[2029],2030:pairs[2030]})
    def test_metadata_IO_failure_is_recorded_and_never_silently_skipped(self):
        out=self.dir/'source';out.mkdir();scope=dict(roles={'Train':{'files':{'SYNTHETIC/NC_H09_20231025_2300_R21_FLDK.06001_06001.nc':dict(year=2023,bytes=123)}}})
        with patch.object(m.subprocess,'run',return_value=SimpleNamespace(stdout=json.dumps(dict(status='OS_ERROR',winerror=121,errno=22)))) as run:
            with self.assertRaises(RuntimeError):m.admit_source(scope,out)
        run.assert_called_once();self.assertEqual(m.read(out/'source_admission.json')['winerror'],121)
    def test_actual_metadata_child_opens_only_synthetic_source_without_payload(self):
        source=self.dir/'NC_H09_20231025_2300_R21_FLDK.06001_06001.nc';source.write_bytes(b'SYNTHETIC_ONLY')
        out=self.dir/'source_pass';out.mkdir();scope=dict(roles={'Train':{'files':{str(source):dict(year=2023,bytes=14)}}})
        m.admit_source(scope,out);r=m.read(out/'source_admission.json');self.assertEqual(r['status'],'PASS');self.assertEqual(r['payload_bytes'],0)
    def test_summary_reads_only_fixed_E9_all_three_seeds_and_keeps_negative_deltas(self):
        out=self.dir/'summary';out.mkdir();v={}
        for seed in (2029,2030,2031):
            for kind in ('B7','B8'):
                base=self.dir/f'history_{kind}' if seed==2029 else out/f'{kind}_s{seed}';base.mkdir()
                if seed==2029:v['historical_'+kind]=str(base)
                delta={2029:-.01,2030:.02,2031:.03}[seed] if kind=='B8' else 0
                s=dict(brier=.1+delta,auroc=.8+delta,average_precision=.5+delta,conditional_pinball=.2+delta,coverage=[.94+delta]*32)
                report=dict(groups={g:dict(ids_sha='same',summary=s) for g in ('all','analysis_UTC_06','scene_max_ge20')})
                m.write(base/f'{kind}_development_09.json',report)
                m.write(base/f'{kind}_tail_09.json',dict(strata=[dict(lower=.1,upper=1.,n_rain=20,conditional_pinball=.2+delta,q32_coverage=.94+delta)],elevation_diagnostics=dict(bins={'elevation_ge_2000m':dict(n_valid=100,n_rain=20,brier=.1+delta,conditional_pinball=.2+delta,q32_coverage=.94+delta)})))
        with patch.object(m,'paired_difference') as pair:m.summarize(out,v)
        self.assertEqual(pair.call_count,3);r=m.read(out/'three_seed_innovation_summary.json')
        self.assertGreater(r['metrics']['brier']['by_seed']['2030'],0);self.assertLess(r['metrics']['brier']['by_seed']['2029'],0)
        self.assertAlmostEqual(r['metrics']['brier']['mean'],statistics.mean([-.01,.02,.03]));self.assertIn('NO_PER_STRATUM_NOMINAL_TARGET',r['rain_strata']['0']['q32_coverage']['improvement'])
        self.assertEqual(r['independent_weather_years'],1);self.assertEqual(set(r['group_endpoints']),{'2029','2030','2031'})
if __name__=='__main__':unittest.main()
