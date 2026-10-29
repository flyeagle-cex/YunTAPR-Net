"""Only the new two-control grant, serial dispatch and summary direction."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import time
import types
import unittest
from unittest.mock import patch
import uuid

ROOT=Path(__file__).resolve().parents[2]
FILE=ROOT/'tools/research_readiness/start_dote_numeric_multiseed.py'
spec=importlib.util.spec_from_file_location('dote_multi',FILE)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class NewControlTests(unittest.TestCase):
    def setUp(self):
        self.folder=ROOT/'tests/research_readiness/.local'/('dote_multi_'+uuid.uuid4().hex)
        self.folder.mkdir(parents=True)
        self.v=dict(output_root=str(self.folder),proposal_sha256='')
        self.p=dict(execution_code_commit='c'*40,tasks=copy.deepcopy(m.TASKS),scientific_choices={},
                    budget=m.budget(dict(roles={'Train':dict(bytes_per_pass=26424262556,file_count=7918),
                                              'Development':dict(bytes_per_pass=26639253112,file_count=7950)})),
                    private_locator_sha256=m.digest({'output_root':str(self.folder)}))
        self.p['proposal_sha256']=m.digest(self.p);self.v['proposal_sha256']=self.p['proposal_sha256']
        self.a=dict(approved_by_researcher=True,decision_id='SYNTHETIC_NOT_A_GRANT_FILE',code_commit='c'*40,
                    proposal_sha256=self.p['proposal_sha256'],tasks=m.TASKS,scientific_choices={},budget=self.p['budget'],
                    output_root=str(self.folder),approved_replay_updates=0)
    def result(self,seed):
        return dict(status='COMPLETE_TRAIN_AND_DEV_EVALUATION',model='B7',control_id='B7_ZERO_DOTE',seed=seed,
                    optimizer_updates=4320,code_commit='c'*40,endpoint='FIXED_EPOCH_9_LAST',replay=0,
                    total_logical_source_bytes=477571953840,total_logical_source_files=142813)
    def test_exact_grant_and_rejection_before_any_runtime_work(self):
        m.validate(self.a,self.p,self.v,'c'*40)
        for change in (dict(approved_by_researcher=False),dict(tasks=[dict(model='B7_ZERO_DOTE',seed=2029)]),
                       dict(code_commit='d'*40),dict(approved_replay_updates=1),dict(budget={})):
            with self.assertRaises(PermissionError):m.validate(dict(self.a,**change),self.p,self.v,'c'*40)
        bad=dict(self.v,output_root='SYNTHETIC_DIFFERENT_NAMESPACE')
        with self.assertRaises(PermissionError):m.validate(self.a,self.p,bad,'c'*40)
    def test_exact_budget_from_frozen_passes(self):
        b=self.p['budget'];self.assertEqual((b['total_updates'],b['total_source_bytes'],b['total_source_files']),(8640,955143907680,285626))
        self.assertEqual((b['max_model_seconds'],b['max_package_seconds'],b['replay_allowance'],b['additional_retry_allowance']),(21600,43200,0,0))
    def test_serial_two_seeds_and_environment_and_once_only_claim(self):
        calls=[]
        def child(command,env,log,timeout):
            seed=int(env['PYTHONHASHSEED']);calls.append(seed);self.assertEqual(env['CUBLAS_WORKSPACE_CONFIG'],':4096:8')
            self.assertEqual(command[3],'worker');self.assertEqual(command[-1],str(len(calls)-1));self.assertLessEqual(timeout,21600)
            self.assertTrue((self.folder/f'task_{len(calls)}_claim.json').exists())
            m.write(self.folder/f'B7_ZERO_DOTE_s{seed}_complete.json',self.result(seed))
        self.assertEqual(m.dispatch(self.p,self.v,self.a,'c'*40,[],time.monotonic(),child),[8640,955143907680,285626])
        self.assertEqual(calls,[2030,2031])
        with self.assertRaises(FileExistsError):m.dispatch(self.p,self.v,self.a,'c'*40,[],time.monotonic(),child)
        self.assertEqual(calls,[2030,2031])
    def test_failure_keeps_partial_accounting_and_never_starts_second(self):
        calls=[]
        def child(command,env,log,timeout):
            calls.append(int(env['PYTHONHASHSEED']));m.write(self.folder/'partial_update_metadata.json',{'returned':62})
            raise RuntimeError('SYNTHETIC_IO_FAILURE')
        with self.assertRaises(RuntimeError):m.dispatch(self.p,self.v,self.a,'c'*40,[],time.monotonic(),child)
        self.assertEqual(calls,[2030]);self.assertFalse((self.folder/'task_2_claim.json').exists())
        self.assertEqual(m.load(self.folder/'partial_update_metadata.json')['returned'],62)
        self.assertIn('NOT_ZERO',m.load(self.folder/'failure.json')['partial_counts'])
    def test_incorrect_endpoint_blocks_later_task(self):
        calls=[]
        def child(command,env,log,timeout):
            seed=int(env['PYTHONHASHSEED']);calls.append(seed)
            m.write(self.folder/f'B7_ZERO_DOTE_s{seed}_complete.json',dict(self.result(seed),endpoint='BEST'))
        with self.assertRaises(RuntimeError):m.dispatch(self.p,self.v,self.a,'c'*40,[],time.monotonic(),child)
        self.assertEqual(calls,[2030]);self.assertTrue((self.folder/'failure.json').exists())
    def test_independent_entry_allowlist_and_frozen_transform_wiring(self):
        import ast
        source=FILE.read_text(encoding='utf-8');tree=ast.parse(source)
        calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='run_task']
        self.assertEqual(len(calls),1);kw={k.arg:ast.unparse(k.value) for k in calls[0].keywords}
        self.assertEqual(kw['dynamic_transform_factory'],'ZeroNumericDote')
        self.assertIn("v['real_B7'][str(seed)]",kw['pair_reference'])
        host=(ROOT/'tools/research_readiness/start_independent_process.py').read_text(encoding='utf-8')
        self.assertIn("'start_dote_numeric_multiseed.py'",host);self.assertIn('host.require_independent(host.host_identity())',source)
    def test_three_seed_summary_is_real_minus_zero_and_q32_uses_absolute_error(self):
        def arm(offset):
            s=dict(brier=.1+offset,auroc=.8-offset,average_precision=.5-offset,conditional_pinball=.2+offset,
                   q32_coverage=.95-offset,q32_signed_bias=.95-offset-.984375,q32_absolute_error=.984375-(.95-offset))
            return {'all':dict(summary=s,ids_sha256='SAME_IDS')}
        def tail():return dict(strata=[dict(n_rain=6,conditional_pinball=.2,q32_coverage=0)],elevation_diagnostics=dict(bins={}))
        old=dict(endpoint_groups={'B7':arm(0),'B7_ZERO_DOTE':arm(.01)},tail_diagnostics={'B7':tail(),'B7_ZERO_DOTE':tail()})
        real=dict(endpoint_groups={str(s):{'B7':arm(0)} for s in (2030,2031)},tail_diagnostics={str(s):{'B7':tail()} for s in (2030,2031)})
        for seed in (2030,2031):
            f=self.folder/f'B7_s{seed}';f.mkdir();a=arm(.01)['all'];m.write(f/'B7_development_09.json',{'groups':{'all':dict(summary=a['summary'],ids_sha='SAME_IDS')}});m.write(f/'B7_tail_09.json',tail())
        p=dict(real_B7_completion_evidence='REAL_PUBLIC',seed2029_control_completion_evidence='OLD_PUBLIC')
        original=m.load
        def load(path):
            if Path(path).name=='REAL_PUBLIC':return real
            if Path(path).name=='OLD_PUBLIC':return old
            return original(path)
        fake=types.ModuleType('yuntapr.experimental.research_readiness.multiseed');fake.metric_values=lambda r:r['groups']['all']['summary']
        with patch.object(m,'load',load),patch.dict(sys.modules,{'yuntapr.experimental.research_readiness.multiseed':fake}):m.summarize(self.folder,p)
        s=m.load(self.folder/'three_seed_dote_control_summary.json');self.assertEqual(s['difference'],'B7_REAL_MINUS_B7_ZERO_DOTE')
        for k in ('brier','conditional_pinball','q32_absolute_error'):
            d=s['groups']['all'][k];self.assertAlmostEqual(d['mean'],-.01);self.assertEqual(d['improvement_seeds'],3);self.assertEqual(d['sample_sd'],0)
        self.assertEqual(s['groups']['all']['q32_coverage']['improvement_seeds'],3)


if __name__=='__main__':unittest.main()
