"""Approval, read, time, lifetime seams; synthetic fixtures only, no torch."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.research_readiness import start_extreme_diagnostic as runtime
from tools.research_readiness.extreme_diagnostic_provider import attach_provider
from tools.research_readiness import start_independent_process as host


class ExecutionGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.p = dict(authorization_scope=runtime.SCOPE, tasks=list(runtime.ORDER), budget=dict(runtime.LIMITS),
                      execution_code_commit='a'*40, scientific_choices={'threshold':20}, final_2025_access=False,
                      models=[dict(model=m, seed=s) for m in ('B4','B7','B8') for s in (2029,2030,2031)])
        self.p['proposal_sha256'] = runtime.digest(self.p)
        self.v = dict(proposal_sha256=self.p['proposal_sha256'], output_root='SYNTHETIC_NEW_OUTPUT')
        self.a = dict(approved_by_researcher=True, authorization_scope=runtime.SCOPE,
                      proposal_sha256=self.p['proposal_sha256'], code_commit='a'*40, tasks=list(runtime.ORDER),
                      scientific_choices={'threshold':20}, budget=dict(runtime.LIMITS), output_root='SYNTHETIC_NEW_OUTPUT',
                      decision_id='SYNTHETIC_NOT_A_RESEARCH_GRANT', researcher_instruction='synthetic fixture only')

    def test_exact_synthetic_identity_matches(self):
        runtime.validate_grant(self.p, self.v, self.a)

    def test_absent_or_old_or_false_grants_rejected(self):
        for change in [dict(approved_by_researcher=False), dict(code_commit='b'*40),
                       dict(decision_id=''), dict(researcher_instruction=''), dict(output_root='OLD_OUTPUT'),
                       dict(authorization_scope='HISTORICAL_CONSUMED_APPROVAL')]:
            approval = dict(self.a, **change)
            with self.subTest(change=change), self.assertRaises(PermissionError):
                runtime.validate_grant(self.p, self.v, approval)

    def test_budget_and_method_cannot_drift(self):
        for name in ('maximum_seconds','output_storage_cap_bytes','retries','optimizer_updates'):
            p = copy.deepcopy(self.p); p['budget'][name] += 1
            with self.subTest(name=name), self.assertRaises(PermissionError): runtime.validate_grant(p,self.v,self.a)
        a = copy.deepcopy(self.a); a['scientific_choices']['threshold'] = 10
        with self.assertRaises(PermissionError): runtime.validate_grant(self.p,self.v,a)

    def test_missing_approval_rejected_before_read_or_provider_import(self):
        with patch.object(runtime, 'read', side_effect=AssertionError('metadata/provider should not be read')):
            with self.assertRaises(PermissionError):
                runtime.validate_only(self.root/'missing-proposal',self.root/'missing-private',self.root/'missing-grant')

    def test_model_seed_task_and_2025_expansion_rejected(self):
        for kind in ('models','tasks','final_2025_access'):
            p=copy.deepcopy(self.p)
            if kind=='models': p['models'][0]['seed']=2032
            elif kind=='tasks':p['tasks'].append('B9_s2029')
            else:p[kind]=True
            with self.subTest(kind=kind),self.assertRaises(PermissionError):runtime.validate_grant(p,self.v,self.a)

    def test_both_clocks_prevent_sleep_or_clock_rollback_extension(self):
        mono, wall = [0.], [100.]
        deadline=runtime.DualDeadline(10,monotonic=lambda:mono[0],wall=lambda:wall[0])
        wall[0]=111
        with self.assertRaises(TimeoutError):deadline.remaining()
        wall[0]=90;mono[0]=11
        with self.assertRaises(TimeoutError):deadline.remaining()

    def test_package_deadline_is_stronger_than_task_limit(self):
        deadline=runtime.DualDeadline(100,absolute_wall=105,monotonic=lambda:0,wall=lambda:100)
        self.assertEqual(deadline.remaining(),5)

    def test_provider_code_changes_block_before_model_access(self):
        src=self.root/'src';src.mkdir();code=src/'fixture.py';code.write_text('x=1',encoding='utf-8')
        manifest={'src/fixture.py':runtime.sha(code)}
        runtime.validate_provider_files(self.root,manifest)
        code.write_text('x=2',encoding='utf-8')
        with self.assertRaises(ValueError):runtime.validate_provider_files(self.root,manifest)
        code.write_text('x=1',encoding='utf-8');(src/'extra.py').write_text('pass',encoding='utf-8')
        with self.assertRaises(ValueError):runtime.validate_provider_files(self.root,manifest)

    def test_output_reservation_checked_before_write(self):
        out=self.root/'out';out.mkdir();(out/'existing').write_bytes(b'12345')
        limit=runtime.OutputLimit(out,8,runtime.DualDeadline(60))
        with self.assertRaises(MemoryError):limit(4)
        self.assertEqual((out/'existing').read_bytes(),b'12345')

    def guard(self, source, *, opens=1):
        out=self.root/'out';out.mkdir(exist_ok=True)
        return runtime.ScientificReadGuard({str(source):dict(bytes=3,opens=opens,category='synthetic',source_id='fixture')},
            out,out/'journal',metadata_cap=100,metadata_opens=2,metadata_roots=[self.root],check=lambda:None)

    def test_real_python_audit_enforces_no_reread_on_synthetic_bytes(self):
        source=self.root/'fixture.nc';source.write_bytes(b'abc');guard=self.guard(source)
        guard.install()
        try:
            self.assertEqual(source.read_bytes(),b'abc')
            with self.assertRaises(PermissionError):source.read_bytes()
        finally:result=guard.close()
        self.assertEqual(result['payload_reserved_bytes'],{'synthetic':3})

    def test_unlisted_2025_payload_and_source_writes_rejected(self):
        source=self.root/'fixture.nc';source.write_bytes(b'abc');guard=self.guard(source);guard.active=True
        with self.assertRaises(PermissionError):guard._event('open',(str(self.root/'2025_UNOPENED.nc'),'r',0))
        with self.assertRaises(PermissionError):guard._event('open',(str(source),'w',os.O_WRONLY))
        self.assertEqual(source.read_bytes(),b'abc')

    def test_frozen_metadata_gets_its_own_finite_reservation(self):
        source=self.root/'fixture.nc';source.write_bytes(b'abc');meta=self.root/'meta.json';meta.write_bytes(b'{}')
        guard=self.guard(source);guard.active=True
        guard._event('open',(str(meta),'r',0));guard._event('open',(str(meta),'r',0))
        with self.assertRaises(PermissionError):guard._event('open',(str(meta),'r',0))
        self.assertEqual(guard.meta_bytes,4)

    def test_forward_wrapper_calls_original_once_and_returns_same_object(self):
        class Tensor:
            def __init__(self,value,requires_float=False):self.value=np.asarray(value);self.requires_float=requires_float
            def detach(self):return self
            def float(self):return Tensor(self.value.astype(np.float32))
            def cpu(self):return self
            def numpy(self):
                if self.requires_float:raise TypeError('synthetic BF16 requires an exact FP32 carrier')
                return self.value
        output=types.SimpleNamespace(rain_prob=Tensor(np.array([.5],dtype=np.float32),requires_float=True),
                                     conditional_quantiles_log=Tensor(np.array([1.],dtype=np.float64)))
        calls=[];received=[]
        class Original:
            def __init__(self):pass
            def forward(self,item):calls.append(item);return output
        class Collector:
            def add(self,*args,**kwargs):received.append((args,kwargs))
        engine=types.SimpleNamespace(FAMILY_ADAPTERS={'b3b4':Original,'b7b8':Original})
        attach_provider(engine,lambda adapter:Collector(),lambda adapter:(lambda item:None),lambda:None)
        item=dict(ids=('synthetic',),batch=types.SimpleNamespace(analyses=('synthetic',)),
                  rate=Tensor([1]),valid=Tensor([True]),region=Tensor([True]))
        actual=engine.FAMILY_ADAPTERS['b3b4']().forward(item)
        self.assertIs(actual,output);self.assertEqual(len(calls),1);self.assertEqual(len(received),1)

    def test_independent_dispatcher_rejects_before_creating_any_target(self):
        service=self.root/'service';service.mkdir()
        entry=ROOT/'tools/research_readiness/start_extreme_diagnostic.py'
        command=[sys.executable,'-B',str(entry),'execute','--proposal',str(self.root/'proposal.json'),
                 '--private-preparation',str(self.root/'private.json'),'--researcher-approval',str(self.root/'MISSING_APPROVAL.json')]
        path=self.root/'spec.json';path.write_text(json.dumps(dict(kind='BOUNDED_EXTREME_DIAGNOSTIC',
            service_dir=str(service),command=command,environment={},cwd=str(ROOT))),encoding='utf-8')
        with patch.object(host,'PRIVATE',self.root):
            with self.assertRaises(PermissionError):host.validate_spec(path)
        self.assertFalse((service/'independent_launch_claim.json').exists())

    def test_old_engineering_probe_route_stays_separate(self):
        service=self.root/'service';service.mkdir();entry=self.root/'probe.py';entry.write_text('pass',encoding='utf-8')
        path=self.root/'spec.json';path.write_text(json.dumps(dict(kind='ENGINEERING_PROBE',service_dir=str(service),
            command=[sys.executable,'-B',str(entry)],environment={},cwd=str(self.root))),encoding='utf-8')
        with patch.object(host,'PRIVATE',self.root):
            spec,folder=host.validate_spec(path)
        self.assertEqual(spec['kind'],'ENGINEERING_PROBE');self.assertEqual(folder,service.resolve())


if __name__=='__main__':unittest.main()
