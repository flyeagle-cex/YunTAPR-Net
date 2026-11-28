"""Synthetic tests for the B2/B5/B6 seed-completion package skeleton.

No real payload, model build, CUDA call or training happens here.
"""
from pathlib import Path
from contextlib import redirect_stdout
import copy
import io
import json
import tempfile
import unittest
from unittest.mock import patch

from yuntapr.contracts.loader import REPO_ROOT
from yuntapr.experimental.research_readiness import seed_completion as module

DECISION = 'SYNTHETIC_VALIDATOR_ONLY'


def _proposal():
    proposal = dict(
        version=module.VERSION,
        scope=module.SCOPE,
        kind=module.KIND,
        entry=module.ENTRY,
        status='READY_WAITING_EXPLICIT_SEED_COMPLETION_APPROVAL',
        authorized=False,
        tasks=[dict(model=kind, seed=seed) for kind, seed in module.TASKS],
        scientific_choices={'b2_stem_rule': module.STEM_RULE, 'static_width': 16},
        budget=copy.deepcopy(module.BUDGET),
        static_source_sha256=dict(module.STATIC_SOURCE_SHA256),
        terrain_receipt_sha256=module.TERRAIN_RECEIPT_SHA256,
        input_pins={},
        code_sha256={'synthetic': '0' * 64},
    )
    proposal['proposal_sha256'] = module.digest(proposal)
    return proposal


def _private(proposal, output_root):
    return dict(proposal_sha256=proposal['proposal_sha256'], output_root=str(output_root),
                inherited={}, prepared={}, terrain='SYNTHETIC')


def _approval(proposal, private, commit='c' * 40):
    return dict(approved_by_researcher=True, decision_id=DECISION, code_commit=commit,
                proposal_sha256=proposal['proposal_sha256'], tasks=proposal['tasks'],
                budget=proposal['budget'], scientific_choices=proposal['scientific_choices'],
                output_root=private['output_root'])


class SeedCompletionTests(unittest.TestCase):
    def test_six_task_order_and_branch_mapping(self):
        self.assertEqual(module.TASKS, (('B2', 2030), ('B2', 2031), ('B5', 2030),
                                        ('B6', 2030), ('B5', 2031), ('B6', 2031)))
        expected = [('B2', 2030), ('B2', 2031), ('B5', 2030), ('B6', 2030), ('B5', 2031), ('B6', 2031)]
        self.assertEqual([module.task_for(index) for index in range(6)], expected)
        for bad in (-1, 6, 1.0, '0', None):
            with self.assertRaises(PermissionError):
                module.task_for(bad)

    def test_budget_arithmetic_and_six_task_mapping(self):
        budget = module.BUDGET
        self.assertTrue(module.validate_budget(budget))
        self.assertEqual(budget['total_updates'], 25920)
        self.assertEqual(budget['total_source_bytes'], 2865430597384)
        self.assertEqual(budget['total_source_files'], 856876)
        self.assertEqual(budget['source_bytes_per_task']['B2_s2030'], 477571641012)
        self.assertEqual(budget['source_bytes_per_task']['B5_s2030'], 477571703840)
        self.assertEqual(budget['source_bytes_per_task']['B6_s2030'], 477571953840)
        self.assertEqual(budget['source_bytes_per_task']['B2_s2031'], 477571641012)
        self.assertEqual(sum(budget['source_bytes_per_task'].values()), budget['total_source_bytes'])
        self.assertEqual(sum(budget['source_files_per_task'].values()), budget['total_source_files'])
        for path in (lambda b: b.update(total_source_bytes=1),
                     lambda b: b.update(total_updates=1),
                     lambda b: b.update(replay_allowance=1),
                     lambda b: b['source_bytes_per_task'].pop('B6_s2031'),
                     lambda b: b['comparison_baselines'].pop('2031')):
            broken = copy.deepcopy(budget)
            path(broken)
            with self.assertRaises(ValueError):
                module.validate_budget(broken)

    def test_proposal_digest_recomputed_and_tamper_detected(self):
        proposal = _proposal()
        self.assertEqual(module.verify_proposal_digest(proposal), proposal['proposal_sha256'])
        tampered = copy.deepcopy(proposal)
        tampered['tasks'][0]['seed'] = 2029
        with self.assertRaises(ValueError):
            module.verify_proposal_digest(tampered)

    def test_approval_exact_keys_and_mismatch_rejected(self):
        proposal = _proposal()
        private = _private(proposal, 'SYNTHETIC_NEW_OUTPUT')
        commit = 'c' * 40
        approval = _approval(proposal, private, commit)
        module.validate_approval(approval, proposal, private, commit)
        cases = []
        extra = copy.deepcopy(approval); extra['note'] = 'x'; cases.append(extra)
        missing = copy.deepcopy(approval); missing.pop('decision_id'); cases.append(missing)
        false_flag = copy.deepcopy(approval); false_flag['approved_by_researcher'] = False; cases.append(false_flag)
        blank = copy.deepcopy(approval); blank['decision_id'] = '   '; cases.append(blank)
        wrong_budget = copy.deepcopy(approval); wrong_budget['budget'] = {}; cases.append(wrong_budget)
        wrong_choice = copy.deepcopy(approval); wrong_choice['scientific_choices'] = {}; cases.append(wrong_choice)
        wrong_output = copy.deepcopy(approval); wrong_output['output_root'] = 'OTHER'; cases.append(wrong_output)
        for broken in cases:
            with self.assertRaises(PermissionError):
                module.validate_approval(broken, proposal, private, commit)

    def test_code_hash_drift_rejected(self):
        proposal = _proposal()
        with patch.object(module, 'code_hashes', return_value={'synthetic': '0' * 64}):
            self.assertTrue(module.check_code_hashes(REPO_ROOT, proposal))
            with patch.object(module, 'code_hashes', return_value={'synthetic': '1' * 64}):
                with self.assertRaises(ValueError):
                    module.check_code_hashes(REPO_ROOT, proposal)

    def test_output_root_exists_or_parent_missing_rejected(self):
        existing = Path(tempfile.mkdtemp())
        with self.assertRaises(PermissionError):
            module.validate_output_root(existing)
        with self.assertRaises(PermissionError):
            module.validate_output_root(existing / 'missing-parent' / 'output')
        with self.assertRaises(PermissionError):
            module.validate_output_root(Path('relative-output-probe'))

    def test_worker_environment_and_command_use_task_seed(self):
        self.assertEqual(module.worker_environment(2030)['PYTHONHASHSEED'], '2030')
        self.assertEqual(module.worker_environment(2031)['PYTHONHASHSEED'], '2031')
        self.assertEqual(module.worker_environment(2030)['CUBLAS_WORKSPACE_CONFIG'], ':4096:8')
        command = module.worker_command(REPO_ROOT, 'P', 'V', 'A', 3, worker_python=Path('python.exe'))
        self.assertEqual(command[0], 'python.exe')
        self.assertEqual(command[1], '-B')
        self.assertEqual(command[2], str(REPO_ROOT / module.ENTRY))
        self.assertEqual(command[command.index('--task-index') + 1], '3')
        self.assertEqual(command[command.index('worker')], 'worker')

    def test_package_closure_accepts_exact_and_rejects_drift(self):
        budget = module.BUDGET
        exact = dict(optimizer_updates=25920, total_logical_source_bytes=2865430597384,
                     total_logical_source_files=856876)
        self.assertTrue(module.validate_package_closure(exact, budget))
        for key, value in (('optimizer_updates', 25919), ('total_logical_source_bytes', 1),
                           ('total_logical_source_files', 856875)):
            broken = dict(exact)
            broken[key] = value
            with self.assertRaises(RuntimeError):
                module.validate_package_closure(broken, budget)

    def test_worker_completion_validation(self):
        budget = module.BUDGET
        commit = 'd' * 40
        result = dict(status='COMPLETE_TRAIN_AND_DEV_EVALUATION', model='B5', seed=2030,
                      optimizer_updates=4320, total_logical_source_bytes=477571703840,
                      total_logical_source_files=142813, code_commit=commit)
        self.assertTrue(module.validate_completion('B5', 2030, budget, commit, result))
        for key, value in (('status', 'STOP'), ('model', 'B6'), ('seed', 2031),
                           ('optimizer_updates', 4319), ('code_commit', 'e' * 40),
                           ('total_logical_source_bytes', 477571641012),
                           ('total_logical_source_files', 142812)):
            broken = dict(result)
            broken[key] = value
            with self.assertRaises(RuntimeError):
                module.validate_completion('B5', 2030, budget, commit, broken)

    def test_dry_run_ok_without_reading_any_file(self):
        proposal = _proposal()
        parent = Path(tempfile.mkdtemp())
        output_root = parent / 'fresh-package-root'
        private = _private(proposal, output_root)
        commit = 'f' * 40
        approval = _approval(proposal, private, commit)
        usage = type('Usage', (), {'free': 50 * module.GIB, 'total': 100 * module.GIB,
                                   'used': 50 * module.GIB})()
        captured = io.StringIO()
        with patch.object(module, 'code_hashes', return_value={'synthetic': '0' * 64}), \
                patch.object(module.shutil, 'disk_usage', return_value=usage), \
                patch.object(Path, 'read_bytes', side_effect=AssertionError('payload read forbidden')), \
                patch.object(Path, 'read_text', side_effect=AssertionError('payload read forbidden')), \
                redirect_stdout(captured):
            summary = module.dry_run(REPO_ROOT, proposal, private, approval, commit)
        self.assertEqual(summary['status'], 'DRY_RUN_OK')
        self.assertEqual(summary['optimizer_updates'], 25920)
        self.assertEqual(summary['total_source_bytes'], 2865430597384)
        self.assertEqual(summary['output_root'], str(output_root.resolve()))
        self.assertIn('DRY_RUN_OK', captured.getvalue())
        self.assertFalse(output_root.exists())

    def test_failure_path_writes_stop_status_and_never_overwrites(self):
        out = Path(tempfile.mkdtemp())
        path = module.write_package_failure(out, RuntimeError('synthetic boom'), 4, 5, 6)
        failure = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(failure['status'], 'STOP_NO_AUTOMATIC_REPLAY')
        self.assertIn('RuntimeError: synthetic boom', failure['error'])
        self.assertEqual(failure['completed_updates'], 4)
        self.assertEqual(failure['completed_source_bytes'], 5)
        self.assertEqual(failure['completed_source_files'], 6)
        module.write_package_failure(out, RuntimeError('second'), 7, 8, 9)
        self.assertEqual(json.loads(path.read_text(encoding='utf-8')), failure)

    def test_execute_spawns_worker_with_path_strings_not_documents(self):
        """Regression: the controller must pass file paths to the worker command.

        Passing the verified proposal/private/approval documents instead of their
        paths produced one ~115 KB argument and failed with WinError 206 before
        the first worker could start (2026-11-27 attempt).
        """
        parent = Path(tempfile.mkdtemp())
        out = parent / 'run'
        proposal = _proposal()
        private = _private(proposal, out)
        approval = _approval(proposal, private)
        proposal_path = parent / 'proposal.json'
        private_path = parent / 'private.json'
        approval_path = parent / 'approval.json'
        for path in (proposal_path, private_path, approval_path):
            path.write_text('{}', encoding='utf-8')
        captured = {}

        def fake_checked(root, proposal_arg, private_arg, approval_arg, commit):
            self.assertEqual(Path(proposal_arg), proposal_path)
            self.assertEqual(Path(private_arg), private_path)
            self.assertEqual(Path(approval_arg), approval_path)
            return proposal, private, approval

        def fake_validate_output_root(path):
            return Path(path), 10 ** 12

        def fake_popen(command, **kwargs):
            captured['command'] = list(command)
            captured['kwargs'] = dict(kwargs)
            raise RuntimeError('synthetic stop before a worker starts')

        with patch.object(module, 'checked', fake_checked), \
                patch.object(module, 'validate_output_root', fake_validate_output_root), \
                patch.object(module.subprocess, 'Popen', fake_popen), \
                patch.object(module, 'write', lambda *args, **kwargs: None), \
                patch.object(module, 'read', lambda *args, **kwargs: {}), \
                patch.object(module, 'write_package_failure', lambda *args, **kwargs: None):
            with self.assertRaises(RuntimeError):
                module.execute(REPO_ROOT, proposal_path, private_path, approval_path, 'c' * 40)

        command = captured['command']
        self.assertTrue(all(isinstance(item, str) for item in command))
        self.assertLess(sum(len(item) for item in command), 5000)
        self.assertEqual(command[command.index('--proposal') + 1], str(proposal_path))
        self.assertEqual(command[command.index('--private-preparation') + 1], str(private_path))
        self.assertEqual(command[command.index('--researcher-approval') + 1], str(approval_path))
        self.assertEqual(command[command.index('--task-index') + 1], '0')
        self.assertEqual(captured['kwargs']['env']['PYTHONHASHSEED'], '2030')

    def test_prepare_requires_explicit_paths_before_any_read(self):
        parent = Path(tempfile.mkdtemp())
        with self.assertRaises(PermissionError):
            module.prepare(REPO_ROOT, output_root=parent / 'out')
        self.assertFalse((parent / 'out').exists())

    def test_resolve_tasks_ordered_subset_and_subset_budget(self):
        subset = [('B2', 2031), ('B5', 2030), ('B6', 2030), ('B5', 2031), ('B6', 2031)]
        self.assertEqual(module.resolve_tasks([dict(model=m, seed=s) for m, s in subset]),
                         tuple(subset))
        budget = module.budget_for(subset)
        self.assertTrue(module.validate_budget(budget, subset))
        self.assertEqual(budget['models'], 5)
        self.assertEqual(budget['total_updates'], 21600)
        self.assertEqual(budget['total_source_bytes'], 2387858956372)
        self.assertEqual(budget['total_source_files'], 714064)
        self.assertEqual(budget['max_package_seconds'], 108000)
        self.assertEqual(set(budget['comparison_baselines']), {'2030', '2031'})
        for bad in ([], [('B5', 2030), ('B2', 2031)], [('B2', 2031), ('B2', 2031)],
                    [('B9', 2030)], [('B6', 2030), ('B5', 2030)]):
            with self.assertRaises(ValueError):
                module.resolve_tasks(bad)
        broken = copy.deepcopy(budget)
        broken['source_bytes_per_task'].pop('B6_s2031')
        with self.assertRaises(ValueError):
            module.validate_budget(broken, subset)
        broken = copy.deepcopy(budget)
        broken['total_updates'] = 25920
        with self.assertRaises(ValueError):
            module.validate_budget(broken, subset)
        broken = copy.deepcopy(budget)
        broken['max_package_seconds'] = 129600
        with self.assertRaises(ValueError):
            module.validate_budget(broken, subset)

    def test_task_for_uses_subset_index_space(self):
        tasks = [('B5', 2030), ('B6', 2031)]
        self.assertEqual(module.task_for(0, tasks), ('B5', 2030))
        self.assertEqual(module.task_for(1, tasks), ('B6', 2031))
        for bad in (-1, 2, 1.0, '0', None):
            with self.assertRaises(PermissionError):
                module.task_for(bad, tasks)

    def test_dry_run_accepts_approved_task_subset(self):
        subset = [('B2', 2031), ('B5', 2030), ('B6', 2030), ('B5', 2031), ('B6', 2031)]
        proposal = _proposal()
        proposal['tasks'] = [dict(model=m, seed=s) for m, s in subset]
        proposal['budget'] = module.budget_for(subset)
        proposal['proposal_sha256'] = module.digest(
            {k: v for k, v in proposal.items() if k != 'proposal_sha256'})
        parent = Path(tempfile.mkdtemp())
        output_root = parent / 'fresh-subset-root'
        private = _private(proposal, output_root)
        commit = 'a' * 40
        approval = _approval(proposal, private, commit)
        usage = type('Usage', (), {'free': 50 * module.GIB, 'total': 100 * module.GIB,
                                   'used': 50 * module.GIB})()
        captured = io.StringIO()
        with patch.object(module, 'code_hashes', return_value={'synthetic': '0' * 64}), \
                patch.object(module.shutil, 'disk_usage', return_value=usage), \
                patch.object(Path, 'read_bytes', side_effect=AssertionError('payload read forbidden')), \
                patch.object(Path, 'read_text', side_effect=AssertionError('payload read forbidden')), \
                redirect_stdout(captured):
            summary = module.dry_run(REPO_ROOT, proposal, private, approval, commit)
        self.assertEqual(summary['status'], 'DRY_RUN_OK')
        self.assertEqual(summary['model_count'], 5)
        self.assertEqual(summary['optimizer_updates'], 21600)
        self.assertEqual(summary['total_source_bytes'], 2387858956372)
        self.assertFalse(output_root.exists())

    def test_static_and_baseline_constants_are_complete(self):
        self.assertEqual(module.STATIC_SOURCE_BYTES, {'B5': 62828, 'B6': 312828})
        for kind in ('B5', 'B6'):
            self.assertEqual(len(module.STATIC_SOURCE_SHA256[kind]), 64)
            self.assertEqual(module.STATIC_SOURCE_SHA256[kind], module.STATIC_SOURCE_SHA256[kind].lower())
        self.assertEqual(module.TERRAIN_RECEIPT_BYTES, 31455)
        self.assertEqual(module.SLOT, 5)
        for seed in (2030, 2031):
            self.assertEqual(set(module.BASELINE_DEV[seed]), {'B2', 'B5', 'B6'})
            self.assertEqual(set(module.BUDGET['comparison_baselines'][str(seed)]), {'B2', 'B5', 'B6'})
            self.assertEqual(module.PAIR_REFERENCE[seed][0].endswith(f'B4_s{seed}'), True)
            for path, value, size in module.BASELINE_DEV[seed].values():
                self.assertEqual(len(value), 64)
                self.assertGreater(size, 0)
                self.assertTrue(path.endswith('_development_09.json'))
            self.assertEqual(len(module.PAIR_REFERENCE[seed][1]), 64)
            self.assertEqual(len(module.PAIR_REFERENCE[seed][2]), 64)

    def test_code_hashes_bind_new_module_and_frozen_executors(self):
        hashes = module.code_hashes(REPO_ROOT)
        for name in (module.ENTRY,
                     'src/yuntapr/experimental/research_readiness/seed_completion.py',
                     'src/yuntapr/experimental/research_readiness/b2_runner.py',
                     'src/yuntapr/experimental/research_readiness/static_training.py',
                     'src/yuntapr/experimental/research_readiness/multiseed.py'):
            self.assertIn(name, hashes)
            self.assertEqual(len(hashes[name]), 64)


if __name__ == '__main__':
    unittest.main()
