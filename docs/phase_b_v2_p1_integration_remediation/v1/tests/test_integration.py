"""New handoff and static rejection interfaces only; no update or prior suite."""
import ast
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch
from yuntapr.experimental.phase_b_v2_p1_integration_candidate.integration import (
    BoundaryProbe,ArtificialRunner,restore_artificial_boundary)
from yuntapr.experimental.phase_b_v2_p1_integration_candidate.checkpoint import Store,FixtureState
from yuntapr.experimental.phase_b_v2_p1_integration_candidate.scope import ROOT,Workspace
from yuntapr.experimental.phase_b_v2_formal_integration_candidate.access import RealDataAdapter,RejectingAuthority
from test_checkpoint import fixture


class IntegrationTests(unittest.TestCase):
    def pair(self):
        w=Workspace();self.addCleanup(w.close)
        payload,contract=fixture();store=Store(w,contract);commit=store.save('boundary_LAST',payload)
        row=dict(phase='READY',pending=False,epoch=1,updates=1,last_sha=commit.payload_sha)
        return store,commit,FixtureState(),row

    def test_complete_boundary_handoff(self):
        store,c,target,row=self.pair()
        ArtificialRunner().restore(store,c.reference,target,BoundaryProbe(row))
        self.assertEqual(target.value['update'],1)

    def test_pending_boundary_cannot_restore(self):
        store,c,target,row=self.pair();row['pending']=True
        with self.assertRaises(ValueError):restore_artificial_boundary(store,c.reference,target,BoundaryProbe(row))
        self.assertIsNone(target.value)

    def test_boundary_budget_and_last_cannot_roll_back(self):
        for field,value in (('epoch',2),('updates',2),('last_sha','f'*64),('phase','FAILED')):
            with self.subTest(field=field):
                store,c,target,row=self.pair();row[field]=value
                with self.assertRaises(ValueError):ArtificialRunner().restore(store,c.reference,target,BoundaryProbe(row))
                self.assertIsNone(target.value)

    def test_no_authority_from_fixture_or_boolean(self):
        r=ArtificialRunner()
        for fn in (r.start_formal,r.resume_formal,RejectingAuthority().verify_execution,RejectingAuthority().verify_resume):
            with self.assertRaises(PermissionError):fn(APPROVED=True,json={'signed':True},commit='ef74d94')

    def test_real_adapter_rejects_before_path_protocol(self):
        class Poison:
            def __fspath__(self):raise AssertionError('No access')
            def __str__(self):raise AssertionError('No access')
        a=RealDataAdapter()
        for fn in (a.open_scene,a.open_manifest,a.open_artifact):
            with self.assertRaises(PermissionError):fn(Poison(),APPROVED=True) if fn!=a.open_scene else fn('x',Poison(),True)

    def test_new_engine_has_no_step_model_forward_or_data_reader(self):
        folder=ROOT/'src/yuntapr/experimental/phase_b_v2_p1_integration_candidate'
        calls=[]
        for p in folder.glob('*.py'):
            tree=ast.parse(p.read_text(encoding='utf-8'))
            for n in ast.walk(tree):
                if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute): calls.append(n.func.attr)
        self.assertNotIn('backward',calls);self.assertNotIn('step',calls)
        self.assertNotIn('new_adamw',calls);self.assertNotIn('build_model',calls)

    def test_byte_reader_never_delegates_to_old_reader(self):
        source=(ROOT/'src/yuntapr/experimental/phase_b_v2_p1_integration_candidate/checkpoint.py').read_text()
        tree=ast.parse(source)
        loads=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
               and isinstance(n.func.value,ast.Name) and n.func.value.id=='torch' and n.func.attr=='load']
        self.assertEqual(len(loads),1)
        self.assertIsInstance(loads[0].args[0],ast.Call)
        self.assertEqual(loads[0].args[0].func.attr,'BytesIO')

    def test_job_backend_atomic_creation_and_ownership_retained(self):
        p=ROOT/'src/yuntapr/experimental/phase_b_v2_execution_watchdog_candidate/winjob.py'
        text=p.read_text()
        self.assertIn('0x2000D',text);self.assertIn('0x2000 | 0x8 | 0x200',text)
        self.assertNotIn('taskkill(',text)


if __name__=='__main__':unittest.main(verbosity=2)
