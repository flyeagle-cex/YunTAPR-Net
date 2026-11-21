"""Synthetic integration checks for the A20 training entry and result gate."""

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

import torch

from tools.research_readiness.start_tail20_aux import POINT_A20_ARM, point_completion, write
from yuntapr.experimental.core_innovation.stage3.planning import digest
from yuntapr.experimental.core_innovation.stage4.engine import POPULATION_SHA, PairedExecutor, forward
from yuntapr.experimental.phase_b_v2_ablations.schedule import COSINE9, schedule_identity
from yuntapr.models.quantile_v2.outputs import LogDomainOutput


class A20EntryTests(unittest.TestCase):
    def test_real_forward_routes_only_train_to_a20(self):
        rate = torch.zeros((1, 1, 1, 3430), dtype=torch.float32)
        rate[..., 0] = 25
        valid = torch.ones_like(rate, dtype=torch.bool)
        qlog = torch.linspace(1, 4, 32, dtype=torch.float64).reshape(1, 32, 1, 1).expand(1, 32, 1, 3430)
        output = LogDomainOutput(torch.zeros_like(rate), torch.full_like(rate, .5), qlog)

        class Model:
            kind = 'B7'
            grid = object()

            def __call__(self, *args, **kwargs):
                return output

        batch = SimpleNamespace(identity=dict(population_sha256=POPULATION_SHA), role='Train',
                                ids=('SYNTHETIC',), rate=rate, valid=valid, region=valid, x=None,
                                native_valid=None, environment=None, environment_valid=None,
                                dynamic=object(), dynamic_valid=object())
        model = Model()
        _, candidate_loss = forward(model, batch, quantile_profile=POINT_A20_ARM.profile)
        self.assertEqual(candidate_loss.experiment_id, POINT_A20_ARM.profile)
        self.assertEqual(candidate_loss.n_strong, 1)
        self.assertGreater(candidate_loss.weighted_point_auxiliary.item(), 0)
        batch.role = 'Development'
        with self.assertRaises(PermissionError):
            forward(model, batch, quantile_profile=POINT_A20_ARM.profile)
        _, baseline_loss = forward(model, batch)
        self.assertEqual(baseline_loss.experiment_id, 'E0')
        torch.testing.assert_close(candidate_loss.s_qr, baseline_loss.s_qr, rtol=0, atol=0)

    def test_executor_rejects_unbound_origin_or_observer_and_recovery(self):
        args = dict(decision=SimpleNamespace(seed=2029), kinds=('B7',), schedule_profile=COSINE9,
                    quantile_profile=POINT_A20_ARM.profile, origin_reference={'synthetic': True},
                    final_dev_observer=lambda ids: None)
        executor = PairedExecutor(None, Path('SYNTHETIC'), **args)
        self.assertEqual(executor.loss_identity, POINT_A20_ARM.loss_identity())
        for override in (dict(origin_reference=None), dict(final_dev_observer=None), dict(recovery=object())):
            with self.subTest(override=override), self.assertRaises(PermissionError):
                PairedExecutor(None, Path('SYNTHETIC'), **(args | override))

    def test_e9_needs_train_seal_and_a_restoration_in_addition_to_all_guards(self):
        with TemporaryDirectory(prefix='synthetic-a20-closure-') as temp:
            folder = Path(temp)
            proposal = dict(budget=dict(total_updates=4320), execution_code_commit='SYNTHETIC',
                            data=dict(population_sha256=POPULATION_SHA))
            training = dict(updates=4320)
            write(folder / 'B7_train_09.json', training)
            checkpoint = folder / 'B7_PREDEV_epoch_09.pt'
            checkpoint.write_bytes(b'SYNTHETIC')
            seal = dict(status='SEALED_TRAIN_BEFORE_DEV', model='B7', epoch=9, updates=4320,
                        checkpoint_sha256='ab' * 32, checkpoint_bytes=checkpoint.stat().st_size,
                        code_commit='SYNTHETIC', population_sha256=POPULATION_SHA,
                        loss_config=POINT_A20_ARM.loss_identity(), schedule=schedule_identity(),
                        train_receipt_sha256=digest(training))
            write(checkpoint.with_suffix('.receipt.json'), seal)
            for prior_guard, detection, expected in (
                ('PASS_DEV_TAIL_GATE', False, 'FAIL_DEV_POINT_A20_GATE'),
                ('FAIL_DEV_TAIL_GATE', True, 'FAIL_DEV_POINT_A20_GATE'),
                ('PASS_DEV_TAIL_GATE', True, 'PASS_DEV_POINT_A20_GATE'),
            ):
                gate = dict(comparison=dict(status=prior_guard, point_a_detection_restored=detection))
                self.assertEqual(point_completion(folder, gate, proposal)['point_a20_status'], expected)
            checkpoint.write_bytes(b'SHORT')
            with self.assertRaisesRegex(RuntimeError, 'pre-Development'):
                point_completion(folder, gate, proposal)


if __name__ == '__main__':
    unittest.main()
