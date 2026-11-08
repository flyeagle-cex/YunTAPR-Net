"""CPU checks for the single E2 recovery, with no scientific source reads."""
import copy
from dataclasses import asdict
import importlib.util
from pathlib import Path
import random
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np
import torch

from yuntapr.experimental.core_innovation.stage4.engine import PairedExecutor
from yuntapr.experimental.core_innovation.stage4.recovery import restore_last
from yuntapr.experimental.research_readiness import dynamic_loss_recovery as recovery

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('loss_recovery_launcher',ROOT/'tools/research_readiness/start_independent_process.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class LossRecoveryTests(unittest.TestCase):
    def prepared(self):
        return dict(roles={'Train':dict(bytes_per_pass=26424262556,file_count=7918),
                           'Development':dict(bytes_per_pass=26639253112,file_count=7950)})

    def stop(self):
        return dict(actual=dict(returned_updates=8640,reserved_source_bytes=951352206452,source_files=284363),
                    wall_seconds_mtime_proxy_ceil=35144)

    def proposal(self):
        return dict(proposal_sha256='SYNTHETIC',tasks=recovery.TASKS,budget=recovery.budget(self.prepared(),self.stop()),
                    protocol=dict(loss='E2',lambda_q=2.,seed=2029,endpoint='FIXED_EPOCH_9',epochs=[9]),
                    scientific_choices={'recovery':dict(checkpoint_epoch=8,execute_epochs=[9])},
                    runtime_binding={'python_executable_sha256':'SYNTHETIC_EXE'})

    def test_exact_replay_and_cumulative_budget(self):
        budget = recovery.budget(self.prepared(),self.stop())
        self.assertEqual((budget['new_updates'],budget['replayed_updates'],budget['max_wall_seconds']),(480,480,3600))
        self.assertEqual((budget['new_source_bytes'],budget['new_source_files']),(53063828496,15869))
        self.assertEqual((budget['cumulative_updates'],budget['cumulative_source_bytes'],budget['cumulative_source_files']),
                         (9120,1004416034948,300232))

    def test_scope_or_parent_drift_rejected(self):
        prepared = self.prepared(); prepared['roles']['Train']['file_count'] += 1
        with self.assertRaises(ValueError):
            recovery.budget(prepared,self.stop())
        stop = self.stop(); stop['actual']['returned_updates'] -= 1
        with self.assertRaises(ValueError):
            recovery.budget(self.prepared(),stop)

    def test_external_approval_binds_all_limits_and_visible_scope(self):
        p = self.proposal(); private = dict(output_root='SYNTHETIC_OUTPUT')
        approval = dict(approved_by_researcher=True,code_commit='SYNTHETIC_COMMIT',proposal_sha256=p['proposal_sha256'],
                        tasks=p['tasks'],budget=p['budget'],scientific_choices=p['scientific_choices'],
                        output_root=private['output_root'],approved_replay_updates=480,
                        researcher_visible_scope_sha256=recovery.SCOPE_SHA,decision_id='SYNTHETIC_DECISION')
        recovery.validate_approval(approval,p,private,'SYNTHETIC_COMMIT')
        for key,value in [('approved_by_researcher',False),('approved_replay_updates',0),('code_commit','OLD'),
                          ('output_root','OLD_OUTPUT'),('researcher_visible_scope_sha256','WRONG')]:
            with self.subTest(key=key),self.assertRaises(PermissionError):
                recovery.validate_approval(dict(approval,**{key:value}),p,private,'SYNTHETIC_COMMIT')

    def test_launcher_rejects_expanded_or_different_loss_scope(self):
        with patch.object(launcher,'sha',return_value='SYNTHETIC_EXE'):
            launcher.validate_dynamic_loss_recovery_scope(self.proposal(),Path('SYNTHETIC'))
            for key,value in [('tasks',[dict(model='B7',seed=2029)]),('protocol',dict(loss='E0')),
                              ('budget',dict(new_updates=960,replayed_updates=960,max_wall_seconds=3600))]:
                p = self.proposal();p[key] = value
                with self.subTest(key=key),self.assertRaises(PermissionError):
                    launcher.validate_dynamic_loss_recovery_scope(p,Path('SYNTHETIC'))
        with patch.object(launcher,'sha',return_value='WRONG'),self.assertRaises(PermissionError):
            launcher.validate_dynamic_loss_recovery_scope(self.proposal(),Path('SYNTHETIC'))

    def test_executor_requires_matching_E2_restore_contract(self):
        decision = SimpleNamespace(seed=2029)
        state = recovery.B8E2Resume(dict(parent='SYNTHETIC'))
        executor = PairedExecutor(None,'SYNTHETIC',decision=decision,kinds=('B8',),lambda_q=2.,recovery=state)
        self.assertEqual(executor.loss_config,recovery.get_config('E2'))
        for kind,seed,resume in [(('B7',),2029,state),(('B8',),2030,state),(('B8',),2029,SimpleNamespace())]:
            with self.subTest(kind=kind,seed=seed),self.assertRaises(PermissionError):
                PairedExecutor(None,'SYNTHETIC',decision=SimpleNamespace(seed=seed),kinds=kind,lambda_q=2.,recovery=resume)

    def test_recovery_ledger_allows_only3841_through4320(self):
        state = recovery.B8E2Resume(dict(parent='SYNTHETIC'))
        ledger = state.ledger(':memory:',{'synthetic':True})
        try:
            with self.assertRaises(PermissionError):
                ledger.reserve('B8',3840)
            for update in range(3841,4321):
                ledger.reserve('B8',update)
                ledger.returned('B8',update)
            with self.assertRaises(PermissionError):
                ledger.reserve('B8',4321)
            self.assertEqual(ledger.db.execute("SELECT COUNT(*) FROM updates WHERE state='RETURNED'").fetchone()[0],480)
        finally:
            ledger.close()

    def test_only_E9_readers_admitted(self):
        with patch.object(recovery.ReaderFactory,'__call__',return_value='SYNTHETIC_READER') as call:
            readers = object.__new__(recovery.RemainingReaders)
            self.assertEqual(readers('Train',9,(),Path('B8_train_reads_09')),'SYNTHETIC_READER')
            self.assertEqual(readers('Development',9,(),Path('B8_dev_reads_09')),'SYNTHETIC_READER')
            for role,epoch,folder in [('Train',8,'B8_train_reads_08'),('Train',9,'B7_train_reads_09'),('Final',9,'B8_final')]:
                with self.assertRaises(PermissionError):
                    readers(role,epoch,(),Path(folder))
            self.assertEqual(call.call_count,2)

    def test_restore_hashes_once_and_passes_explicit_loss_identity(self):
        state = recovery.B8E2Resume(dict(parent='SYNTHETIC',checkpoint_sha256=recovery.CHECKPOINT_SHA,data_identity={'synthetic':True}))
        with patch.object(recovery,'sha',return_value=recovery.CHECKPOINT_SHA) as sha, \
                patch.object(recovery,'restore_last') as restore,patch.object(recovery,'read',return_value={'synthetic':True}):
            update,reports = state.restore('B8',Mock(),Mock(),[])
        self.assertEqual((update,len(reports)),(3840,8))
        sha.assert_called_once()
        self.assertEqual(restore.call_args.kwargs['loss_config'],asdict(recovery.get_config('E2')))

    def test_wrong_checkpoint_loss_rejected_before_loading_tensors(self):
        model, optimizer = Mock(), Mock()
        payload = dict(identity=dict(data={},model='B8',decision=dict(seed=2029),loss_config=asdict(recovery.get_config('E0'))),
                       optimizer_groups=[],epoch=8,updates=3840)
        with patch.object(torch,'load',return_value=payload),self.assertRaises(ValueError):
            restore_last('SYNTHETIC',model,optimizer,[],data_identity={},epoch=8,updates=3840,
                         kind='B8',seed=2029,loss_config=asdict(recovery.get_config('E2')))
        model.load_state_dict.assert_not_called(); optimizer.load_state_dict.assert_not_called()

    def test_complete_state_restoration_on_CPU_without_updates(self):
        model = torch.nn.Linear(2,1)
        optimizer = torch.optim.AdamW(model.parameters(),lr=.001)
        random.seed(123);np.random.seed(123);torch.manual_seed(123)
        rng = dict(python=random.getstate(),numpy=np.random.get_state(),torch_cpu=torch.get_rng_state(),torch_cuda=[])
        expected = (random.random(),float(np.random.rand()),float(torch.rand(())))
        payload = dict(identity=dict(data={},model='B8',decision=dict(seed=2029),loss_config=asdict(recovery.get_config('E2'))),
                       optimizer_groups=[],epoch=8,updates=3840,model=copy.deepcopy(model.state_dict()),
                       optimizer=copy.deepcopy(optimizer.state_dict()),rng=rng,
                       scheduler=dict(completed=3840,steps_per_epoch=480,original_horizon=24000))
        with torch.no_grad():
            model.weight.add_(5)
        optimizer.param_groups[0]['lr'] = .3
        with patch.object(torch,'load',return_value=payload),patch.object(torch.cuda,'set_rng_state_all') as cuda:
            restore_last('SYNTHETIC',model,optimizer,[],data_identity={},epoch=8,updates=3840,
                         kind='B8',seed=2029,loss_config=asdict(recovery.get_config('E2')))
        self.assertTrue(torch.equal(model.weight,payload['model']['weight']))
        self.assertEqual(optimizer.param_groups[0]['lr'],.001)
        self.assertEqual((random.random(),float(np.random.rand()),float(torch.rand(()))),expected)
        cuda.assert_called_once_with([])


if __name__ == '__main__':
    unittest.main()
