"""Check RH700 capture, projection and frozen stop rules without real inputs."""

from datetime import datetime, timedelta
from types import SimpleNamespace
import unittest

import numpy as np
import torch

from tools.research_readiness import start_train_rh700_separability as runner
from tools.research_readiness import start_train_rh700_amplitude as amplitude
from yuntapr.experimental.core_innovation.gfs import EnvironmentFrame, Field, ForecastIdentity, _above_ground
from yuntapr.experimental.core_innovation.grid import GridSpec


class TrainRH700ExecutionTests(unittest.TestCase):
    def test_projection_agrees_with_full_mapping_and_preserves_dynamic_result(self):
        native = GridSpec([25, 26], [100, 101])
        target = GridSpec([25.25, 26], [100.25, 101])
        init = datetime.fromisoformat("2023-03-01T00:00:00+00:00")
        identity = ForecastIdentity(init, timedelta(hours=6), init + timedelta(hours=6))
        mask = np.ones(native.shape, dtype=bool)
        frame = EnvironmentFrame(identity, native, _above_ground({
            runner.FEATURE: Field(np.full(native.shape, 73.), mask, "relative_humidity", "%", 70000.),
            "ps": Field(np.array([[70000., 90000.], [90000., 90000.]]), mask, "surface_pressure", "Pa", None),
            "pwat": Field(np.full(native.shape, 29.), mask, "precipitable_water", "kg m-2", None),
        }), "retrospective", ())
        field = frame.on_grid(target, operator="bilinear_point_candidate").fields[runner.FEATURE]
        self.assertFalse(field.valid[0, 0])
        self.assertTrue(field.valid[1, 1])

        class FakeDote:
            pack = SimpleNamespace(grid=target, values=np.ones((6, *target.shape)))

            def __call__(self, incoming):
                if incoming is not frame:
                    raise AssertionError("DOTE must receive the original frame")
                return payload

        payload = (np.zeros((8, *target.shape)), np.ones((8, *target.shape), dtype=bool))
        sid = "2023-03-01T05:30:00+00:00"
        summary = runner.Summary([sid])
        capture, verify = summary.hooks(FakeDote(), SimpleNamespace(
            environment={runner.FEATURE: SimpleNamespace(mean=50., std=10.)},
        ))
        self.assertIs(capture(frame), payload)
        env = torch.zeros((1, 13, *target.shape), dtype=torch.float32)
        valid = torch.zeros_like(env, dtype=torch.bool)
        env[0, runner.FEATURE_INDEX] = torch.tensor((np.where(field.valid, field.values, 50.) - 50.) / 10.)
        valid[0, runner.FEATURE_INDEX] = torch.from_numpy(field.valid)
        batch = SimpleNamespace(ids=(sid,), analyses=(identity.valid.isoformat(),), environment=env,
                                environment_valid=valid)
        verify(batch)
        valid[0, runner.FEATURE_INDEX, 0, 0] = True
        with self.assertRaisesRegex(ValueError, "MEE correspondence"):
            verify(batch)

    def test_integer_decision_and_leave_one_block_stop(self):
        stable = {i: dict(valid_pairs=10, wins=6) for i in range(3)}
        self.assertEqual(runner.decision(stable)["decision"], "DESCRIPTIVE_TRAIN_SIGNAL_ONLY")
        clustered = {0: dict(valid_pairs=10, wins=10), 1: dict(valid_pairs=10, wins=5),
                     2: dict(valid_pairs=10, wins=5)}
        self.assertEqual(runner.decision(clustered)["decision"], "STOP_RH700_DIRECTION")
        self.assertEqual(runner.decision({0: dict(valid_pairs=40, wins=30)})["decision"], "INSUFFICIENT_COVERAGE")

    def test_amplitude_bounds_include_unmatched_same_scene_negative(self):
        sid = "2023-03-01T05:30:00+00:00"
        summary = amplitude.Summary([sid])
        mask = np.zeros((1, 1, 100, 100), dtype=bool)
        mask.ravel()[:3430] = True
        truth = np.zeros_like(mask, dtype=np.float32)
        truth[0, 0, 0, 0] = 35.
        probability = np.full(mask.shape, .75)
        nodes = np.broadcast_to(np.log1p(np.linspace(14., 19., 32)[None, :, None, None]), (1, 32, 100, 100))
        humidity = np.zeros((100, 100))
        humidity[0, :2] = [90., 95.]
        summary.pending[sid] = (None, humidity, np.ones_like(humidity, dtype=bool))
        summary.add((sid,), truth, mask, mask, probability, nodes)
        self.assertEqual(summary.target_negative, 3429)
        self.assertEqual(amplitude.conclude(summary.bounds)["decision"], "STOP_LOCAL_NEGATIVE_CEILING")
        self.assertEqual(amplitude.conclude(dict(first_hit=1., point_stop=2., tail_stop=1.))["decision"],
                         "NUMERICAL_BOUNDARY_UNRESOLVED")


if __name__ == "__main__":
    unittest.main()
