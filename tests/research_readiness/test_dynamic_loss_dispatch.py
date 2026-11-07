"""Dispatcher argument binding and failure gates, with no subprocess execution."""

from contextlib import ExitStack
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import mock_open, patch

from tools.research_readiness import start_dynamic_pair as entry
from tools.research_readiness import start_independent_process as launcher
from yuntapr.experimental.research_readiness import dynamic_training as tasks
from yuntapr.experimental.core_innovation.stage4 import engine


class DynamicLossDispatchTests(unittest.TestCase):
    def test_independent_launcher_restricts_new_entry_to_exact_E2_scope(self):
        proposal={'protocol':{'loss':'E2','lambda_q':2.0},
                  'tasks':[dict(model='B7',seed=2029),dict(model='B8',seed=2029)],
                  'runtime_binding':{'python_executable_sha256':'SYNTHETIC'}}
        with patch.object(launcher,'sha',return_value='SYNTHETIC'):
            launcher.validate_dynamic_loss_scope(['python','-B','entry','execute','--lambda-q','2'],proposal,Path('SYNTHETIC'))
            for command in (['python','-B','entry','execute'],['python','-B','entry','execute','--lambda-q','1']):
                with self.assertRaises(PermissionError):
                    launcher.validate_dynamic_loss_scope(command,proposal,Path('SYNTHETIC'))
            wrong=dict(proposal,tasks=[dict(model='B7',seed=2030),dict(model='B8',seed=2030)])
            with self.assertRaises(PermissionError):
                launcher.validate_dynamic_loss_scope(['--lambda-q','2'],wrong,Path('SYNTHETIC'))

    def test_independent_launcher_rejects_unbound_interpreter(self):
        proposal={'protocol':{'loss':'E2','lambda_q':2},
                  'tasks':[dict(model='B7',seed=2029),dict(model='B8',seed=2029)],
                  'runtime_binding':{'python_executable_sha256':'EXPECTED'}}
        with patch.object(launcher,'sha',return_value='WRONG'),self.assertRaises(PermissionError):
            launcher.validate_dynamic_loss_scope(['--lambda-q','2'],proposal,Path('SYNTHETIC'))

    def test_runtime_mismatch_fails_before_population_metadata(self):
        proposal={'protocol':{'loss':'E2'},'runtime_binding':{'version':'EXPECTED'},'code_sha256':{}}
        proposal['proposal_sha256']=tasks.digest(proposal)
        private={'proposal_sha256':proposal['proposal_sha256']}
        with patch.object(tasks,'read',side_effect=[proposal,private,{}]), \
                patch.object(tasks,'validate_approval'),patch.object(tasks,'hashes',return_value={}), \
                patch.object(tasks,'runtime_binding',return_value={'version':'WRONG'}), \
                patch.object(tasks,'load_inherited') as load:
            with self.assertRaisesRegex(ValueError,'numerical runtime'):
                tasks.checked(Path('SYNTHETIC'),'p','v','a','c')
            load.assert_not_called()

    def test_E9_summary_keeps_primary_denominator_and_records_tradeoffs(self):
        identity={'population':'SYNTHETIC'}
        def report(pinball):
            summary={'n_valid':20,'n_rain':4,'s_qr':pinball*4,'conditional_pinball':pinball,
                     'brier':.11,'auroc':.7,'average_precision':.6,'coverage':[.94]*32}
            return {'source_identity':identity,'groups':{'all':{'summary':summary}}}
        historical={}
        for kind,pinball in (('B7',.5),('B8',.6)):
            metrics=tasks.metric_values(report(pinball));metrics.update(qr_per_valid=pinball/5,brier=.1)
            historical[kind]={'n_valid':20,'n_rain':4,'metrics':metrics}
        proposal={'data':identity,'scientific_choices':{'historical_e0':historical}}
        with patch.object(tasks,'read',side_effect=lambda path:report(.4 if 'B7' in path.name else .45)):
            result=tasks.loss_pair_summary(proposal,Path('SYNTHETIC'))
        self.assertAlmostEqual(result['lambda2_minus_lambda1']['B7']['conditional_pinball'],-.1)
        self.assertAlmostEqual(result['values']['B7']['E2']['qr_per_valid'],.08)
        self.assertAlmostEqual(result['interaction']['conditional_pinball'],-.05)
        self.assertTrue(result['guardrail_degradation']['B7']['brier'])
        self.assertEqual(result['AP20_q32'],'NOT_VERIFIED')
        self.assertEqual(result['scientific_acceptance'],'NOT_VERIFIED')

    def test_E9_summary_rejects_population_mismatch(self):
        proposal={'data':{'population':'EXPECTED'},'scientific_choices':{'historical_e0':{
            'B7':{'n_valid':20,'n_rain':4,'metrics':{}}}}}
        report={'source_identity':{'population':'WRONG'},'groups':{'all':{'summary':{'n_valid':20,'n_rain':4}}}}
        with patch.object(tasks,'read',return_value=report),self.assertRaises(ValueError):
            tasks.loss_pair_summary(proposal,Path('SYNTHETIC'))

    def test_missing_origin_reference_fails_before_resources_or_model_creation(self):
        decision=engine.FormalDecision('SYNTHETIC',2029,engine.POPULATION_SHA,True,True,True)
        executor=engine.PairedExecutor(None,'SYNTHETIC',kinds=('B7',),decision=decision,lambda_q=2)
        with patch.object(engine,'resources') as resources:
            with self.assertRaises(PermissionError):executor.run(None)
            resources.assert_not_called()

    def test_origin_gate_accepts_only_matching_initial_state_and_all_nine_orders(self):
        orders={e:(f'SYNTHETIC_{e}',) for e in range(1,10)}
        reference={'original_model_state_sha256':'a'*64,
                   'epoch_order_sha256':[engine.digest(orders[e]) for e in range(1,10)]}
        executor=engine.PairedExecutor(None,'SYNTHETIC',kinds=('B8',),
                                       decision=SimpleNamespace(seed=2029),lambda_q=2,origin_reference=reference)
        identity={'B8':{'full_state_sha256':'a'*64}}
        executor.check_origin_pair(identity,orders)
        with self.assertRaises(RuntimeError):
            executor.check_origin_pair({'B8':{'full_state_sha256':'b'*64}},orders)
        with self.assertRaises(RuntimeError):
            changed_orders=dict(orders)
            changed_orders[9]=('DIFFERENT',)
            executor.check_origin_pair(identity,changed_orders)

    def test_cli_passes_explicit_weight_to_execute_and_worker(self):
        for mode in ('execute', 'worker'):
            argv = ['entry', mode, '--proposal', 'SYNTHETIC.json',
                    '--private-preparation', 'SYNTHETIC_PRIVATE.json',
                    '--researcher-approval', 'SYNTHETIC_APPROVAL.json', '--lambda-q', '2']
            if mode == 'worker':
                argv.extend(('--task-index', '1'))

            def git_output(command, **kwargs):
                return 'a' * 40 if 'rev-parse' in command else ''

            with self.subTest(mode=mode), patch.object(entry.sys, 'argv', argv), \
                    patch.object(entry.os, 'chdir'), \
                    patch.object(entry.subprocess, 'check_output', side_effect=git_output), \
                    patch.object(tasks, mode) as dispatch:
                entry.main()
                self.assertEqual(dispatch.call_args.kwargs['lambda_q'], 2.0)

    def test_worker_passes_bound_weight_to_actual_task_for_both_architectures(self):
        for index in (0, 1):
            proposal = {'protocol': {'loss': 'E2', 'lambda_q': 2}}
            private = {'output_root': 'SYNTHETIC', 'historical_pair': 'SYNTHETIC_BASE'}
            approval = {'decision_id': 'SYNTHETIC'}

            def read_binding(path):
                if path.name == 'authorization_binding.json':
                    return {'controller_pid': os.getppid(), 'approval': approval}
                return {'index': index, 'controller_pid': os.getppid(), 'code_commit': 'SYNTHETIC'}

            with self.subTest(index=index), \
                    patch.object(tasks, 'checked', return_value=(proposal, private, approval, {})), \
                    patch.object(tasks, 'read', side_effect=read_binding), \
                    patch.object(tasks, 'run_task') as run_task:
                tasks.worker(Path('SYNTHETIC'), 'p', 'v', 'a', 'SYNTHETIC', index, lambda_q=2)
                self.assertEqual(run_task.call_args.args[6:8], tasks.TASKS[index])
                self.assertEqual(run_task.call_args.kwargs['lambda_q'], 2)
                self.assertIsNone(run_task.call_args.kwargs['pair_reference'])

    def test_old_protocol_rejects_weight_two_before_worker_binding_or_resources(self):
        with patch.object(tasks, 'checked', return_value=({'protocol': {'loss': 'E0'}},
                                                        {'output_root': 'SYNTHETIC'}, {}, {})), \
                patch.object(tasks, 'read') as read, patch.object(tasks, 'resources') as resources:
            with self.assertRaises(PermissionError):
                tasks.worker(Path('SYNTHETIC'), 'p', 'v', 'a', 'c', 0, lambda_q=2)
            with self.assertRaises(PermissionError):
                tasks.execute(Path('SYNTHETIC'), 'p', 'v', 'a', 'c', lambda_q=2)
            read.assert_not_called()
            resources.assert_not_called()

    def test_controller_sends_weight_to_child_and_blocks_second_after_failure(self):
        for weight in (1.0, 2.0):
            with self.subTest(weight=weight), ExitStack() as stack:
                protocol = {'loss': 'E0'} if weight == 1 else {'loss': 'E2', 'lambda_q': 2}
                proposal = {'protocol': protocol, 'budget': {'initial_free_bytes': 0,
                                                            'max_package_seconds': 1, 'max_model_seconds': 1}}
                private = {'output_root': 'SYNTHETIC_OUTPUT'}
                stack.enter_context(patch.object(Path, 'exists', return_value=False))
                stack.enter_context(patch.object(Path, 'mkdir'))
                stack.enter_context(patch.object(Path, 'open', mock_open()))
                stack.enter_context(patch.object(tasks, 'checked', return_value=(proposal, private, {}, {})))
                stack.enter_context(patch.object(tasks.time, 'monotonic', return_value=0))
                stack.enter_context(patch.object(tasks.shutil, 'disk_usage', return_value=SimpleNamespace(free=1)))
                stack.enter_context(patch.object(tasks, 'resources', return_value={}))
                stack.enter_context(patch.object(tasks, 'write'))
                launch = stack.enter_context(patch.object(tasks.subprocess, 'Popen'))
                launch.return_value.wait.return_value = 1
                with self.assertRaisesRegex(RuntimeError, 'remaining tasks blocked'):
                    tasks.execute(Path('SYNTHETIC'), 'p', 'v', 'a', 'c', lambda_q=weight)
                launch.assert_called_once()
                command = launch.call_args.args[0]
                if weight == 1:
                    self.assertNotIn('--lambda-q', command)
                else:
                    self.assertEqual(command[-2:], ['--lambda-q', '2.0'])


if __name__ == '__main__':
    unittest.main()
