"""CPU loss/gradient and mocked entry wiring, without data or optimizer steps."""

import ast
from contextlib import ExitStack
import inspect
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import torch

from yuntapr.experimental.core_innovation.stage4 import engine
from yuntapr.experimental.phase_b_v2_ablations.config import get_config
from yuntapr.experimental.phase_b_v2_ablations.total import candidate_loss
from yuntapr.experimental.research_readiness import dynamic_training as tasks


def fixture(kind, *, dry=False):
    """Match the engine's3430 valid pixels using artificial output tensors."""
    logit = torch.linspace(-0.7, 0.7, 3430).reshape(1, 1, 1, 3430).requires_grad_()
    qlog = torch.linspace(0.2, 4.0, 32, dtype=torch.float64)
    qlog = qlog.reshape(1, 32, 1, 1).expand(1, 32, 1, 3430).clone().requires_grad_()
    rate = torch.tensor([0.0, 0.05, 0.1, 0.11, 2.0, 25.0, 60.0]).repeat(490)
    rate = rate.reshape(1, 1, 1, 3430)
    if dry:
        rate.zero_()
    valid = torch.ones_like(rate, dtype=torch.bool)
    output = SimpleNamespace(rain_logit=logit, conditional_quantiles_log=qlog)
    model = MagicMock(kind=kind, grid=object(), return_value=output)
    batch = SimpleNamespace(
        identity={'population_sha256': engine.POPULATION_SHA}, ids=('SYNTHETIC',),
        x=object(), native_valid=object(), environment=object(),
        environment_valid=object(), dynamic=object(), dynamic_valid=object(),
        rate=rate, valid=valid, region=valid.clone(),
    )
    return model, batch, output


def loss_gradients(loss, output):
    return torch.autograd.grad(
        loss.training_objective, (output.rain_logit, output.conditional_quantiles_log),
    )


class DynamicLossEntryTests(unittest.TestCase):
    def test_default_and_explicit_one_match_old_E0_loss_and_output_gradients(self):
        for kind in ('B7', 'B8'):
            with self.subTest(kind=kind):
                model, batch, output = fixture(kind)
                reference = candidate_loss(
                    output.rain_logit, output.conditional_quantiles_log,
                    batch.rate, batch.valid, batch.region, config=get_config('E0'),
                )
                _, default = engine.forward(model, batch)
                _, explicit = engine.forward(model, batch, loss_config=get_config('E0'))
                expected = loss_gradients(reference, output)
                for loss in (default, explicit):
                    self.assertTrue(torch.equal(loss.training_objective, reference.training_objective))
                    for actual, old in zip(loss_gradients(loss, output), expected):
                        self.assertTrue(torch.equal(actual, old))
                self.assertEqual(default.n_valid, 3430)
                self.assertEqual(default.n_rain, 1960)

    def test_two_changes_only_quantile_weight_and_its_output_gradient(self):
        for kind in ('B7', 'B8'):
            with self.subTest(kind=kind):
                model, batch, output = fixture(kind)
                _, e0 = engine.forward(model, batch)
                _, e2 = engine.forward(model, batch, loss_config=get_config('E2'))
                self.assertTrue(torch.equal(e0.s_occ, e2.s_occ))
                self.assertTrue(torch.equal(e0.s_qr, e2.s_qr))
                self.assertEqual((e0.n_valid, e0.n_rain), (e2.n_valid, e2.n_rain))
                self.assertTrue(torch.equal(
                    e2.training_objective, (e0.s_occ + 2.0 * e0.s_qr) / e0.n_valid,
                ))
                self.assertTrue(torch.equal(
                    e0.scientific_conditional_pinball, e2.scientific_conditional_pinball,
                ))
                g0, g2 = loss_gradients(e0, output), loss_gradients(e2, output)
                self.assertTrue(torch.equal(g0[0], g2[0]))
                self.assertTrue(torch.equal(2.0 * g0[1], g2[1]))

    def test_all_dry_preserves_occurrence_and_connected_zero_quantile_gradient(self):
        model, batch, output = fixture('B8', dry=True)
        _, e0 = engine.forward(model, batch)
        _, e2 = engine.forward(model, batch, loss_config=get_config('E2'))
        self.assertTrue(e0.conditional_skipped and e2.conditional_skipped)
        self.assertTrue(torch.equal(e0.training_objective, e2.training_objective))
        for loss in (e0, e2):
            occurrence, quantiles = loss_gradients(loss, output)
            self.assertGreater(torch.count_nonzero(occurrence).item(), 0)
            self.assertEqual(torch.count_nonzero(quantiles).item(), 0)

    def test_dynamic_spec_is_closed_without_expanding_legacy_candidates(self):
        from yuntapr.experimental.phase_b_v2_ablations.config import proposed_runs
        self.assertEqual(len(proposed_runs()), 18)
        for kind in ('B7', 'B8'):
            self.assertEqual(tasks.RunSpec(kind, 2031).loss_config, get_config('E0'))
            self.assertEqual(tasks.RunSpec(kind, 2029, 2).loss_config, get_config('E2'))
            for value in (True, '2', 0, -1, 1.5, float('nan'), float('inf')):
                with self.subTest(kind=kind, value=value), self.assertRaises(ValueError):
                    tasks.RunSpec(kind, 2029, value)
            with self.assertRaises(PermissionError):
                tasks.RunSpec(kind, 2030, 2)

    def test_nondefault_engine_requires_single_origin_B7_B8_seed2029(self):
        decision = SimpleNamespace(seed=2029)
        for kind in ('B7', 'B8'):
            executor = engine.PairedExecutor(None, 'SYNTHETIC', kinds=(kind,), decision=decision, lambda_q=2)
            self.assertEqual(executor.loss_config, get_config('E2'))
            with self.assertRaises(PermissionError):
                engine.PairedExecutor(None, 'SYNTHETIC', kinds=(kind,), decision=decision, lambda_q=2, recovery=object())
        for kinds, seed in [(('B3', 'B4'), 2029), (('B7', 'B8'), 2029), (('B8',), 2030)]:
            with self.assertRaises(PermissionError):
                engine.PairedExecutor(None, 'SYNTHETIC', kinds=kinds, decision=SimpleNamespace(seed=seed), lambda_q=2)

    def test_old_or_inconsistent_proposal_is_rejected_before_any_IO(self):
        cases = [({}, 2), ({'loss': 'E0'}, 2),
                 ({'loss': 'E2'}, 2), ({'loss': 'E2', 'lambda_q': 2}, 1)]
        with patch.object(tasks.sqlite3, 'connect', side_effect=AssertionError('No IO')) as connect:
            for protocol, weight in cases:
                with self.subTest(protocol=protocol, weight=weight), self.assertRaises(PermissionError):
                    tasks.run_task(Path('SYNTHETIC'), {'protocol': protocol}, {}, {}, {},
                                   'SYNTHETIC', 'B7', 2029, started=0,
                                   pair_reference=None, static_name='SYNTHETIC', lambda_q=weight)
            connect.assert_not_called()

    def test_run_task_reaches_real_executor_and_loss_with_mocked_source_boundaries(self):
        for kind in ('B7', 'B8'):
            for weight in (1, 2):
                with self.subTest(kind=kind, weight=weight), ExitStack() as stack:
                    model, batch, _ = fixture(kind)
                    observed = []

                    def synthetic_run(executor, readers):
                        observed.append((executor, engine.forward(model, batch, loss_config=executor.loss_config)[1]))

                    protocol = {} if weight == 1 else {'loss': 'E2', 'lambda_q': 2}
                    proposal = {
                        'protocol': protocol, 'data': batch.identity,
                        'budget': {'minimum_task_free_bytes': 0, 'max_model_seconds': 1},
                        'static_source_sha256': {kind: 'SYNTHETIC'},
                        'scientific_choices': {'DOTE': {'pwat_reference_kg_m2': 1.0,
                                                       'reference_provenance': 'SYNTHETIC'},
                                               'modulation_limit': 0.1},
                    }
                    private = {'output_root': 'SYNTHETIC', 'terrain': 'SYNTHETIC'}
                    prepared = {'private_inputs': {'stage3_run': 'SYNTHETIC', 'request': 'SYNTHETIC'}}
                    stack.enter_context(patch.dict(tasks.os.environ, {'PYTHONHASHSEED': '2029'}))
                    stack.enter_context(patch.object(tasks.sqlite3, 'connect'))
                    stack.enter_context(patch.object(tasks.shutil, 'disk_usage', return_value=SimpleNamespace(free=1)))
                    stack.enter_context(patch.object(tasks.time, 'monotonic', return_value=0))
                    stack.enter_context(patch.object(tasks, 'SourceMeter'))
                    stack.enter_context(patch.object(tasks, 'unpack', return_value=object()))
                    stack.enter_context(patch.object(tasks, 'read', return_value={'scalers': 'SYNTHETIC'}))
                    stack.enter_context(patch.object(tasks, 'PopulationPlan', return_value=SimpleNamespace(identity=batch.identity, strong_scene_ids=())))
                    stack.enter_context(patch.object(tasks, 'model_factory', return_value=object()))
                    stack.enter_context(patch.object(tasks, 'ReaderFactory'))
                    stack.enter_context(patch.object(tasks, 'write'))
                    stack.enter_context(patch.object(tasks, 'endpoint', return_value={'logical_source_bytes': 0, 'logical_source_files': 0}))
                    stack.enter_context(patch.object(engine.PairedExecutor, 'run', autospec=True, side_effect=synthetic_run))
                    result = tasks.run_task(
                        Path('SYNTHETIC'), proposal, private, {'decision_id': 'SYNTHETIC'},
                        prepared, 'SYNTHETIC', kind, 2029, started=0, pair_reference=None,
                        static_name='SYNTHETIC', dynamic_transform_factory=MagicMock(), lambda_q=weight,
                    )
                    executor, loss = observed[0]
                    self.assertEqual(executor.lambda_q, weight)
                    self.assertEqual(loss.experiment_id, 'E0' if weight == 1 else 'E2')
                    self.assertEqual(executor.kinds, (kind,))
                    if weight == 1:
                        self.assertNotIn('lambda_q', result)
                    else:
                        self.assertEqual((result['loss_arm'], result['lambda_q']), ('E2', 2))

    def test_actual_engine_loop_passes_selected_config_to_both_forward_calls(self):
        tree = ast.parse(inspect.getsource(engine.PairedExecutor))
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == 'forward']
        self.assertEqual(len(calls), 2)
        for call in calls:
            keyword = next(k for k in call.keywords if k.arg == 'loss_config')
            self.assertIsInstance(keyword.value, ast.Attribute)
            self.assertEqual(keyword.value.value.id, 'self')
            self.assertEqual(keyword.value.attr, 'loss_config')


if __name__ == '__main__':
    unittest.main()
