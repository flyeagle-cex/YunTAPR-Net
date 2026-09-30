"""Synthetic engineering-only checks; no formal B0 experiment or test-year tuning."""
import ast
from datetime import datetime, timezone, timedelta
import io
from pathlib import Path
import unittest
import numpy as np
import torch

from yuntapr.contracts.loader import REPO_ROOT, load_contract
from yuntapr.data.dataset_b0 import B0Dataset, B0Record
from yuntapr.data.himawari_b13 import decode_b13
from yuntapr.data.imerg_v07 import decode_imerg, validate_final_provenance
from yuntapr.data.sample_schema import HimawariFrame, select_latest_causal_frame
from yuntapr.losses.pinball import frozen_taus
from yuntapr.losses.total_loss import b0_core_loss
from yuntapr.metrics.probabilistic import brier_at_occurrence
from yuntapr.models.b0 import B0Model
from yuntapr.models.monotonic_quantiles import monotonic_quantiles
from yuntapr.models.probability_heads import B0Output
from yuntapr.spatial.sp04_mapping import load_sp04
from yuntapr.spatial.projection import SP04Projection


torch.set_num_threads(2)


def tiny_output(logit=None, qlog=None):
    logit = torch.zeros(1, 1, 2, 2, requires_grad=True) if logit is None else logit
    qlog = monotonic_quantiles(torch.zeros(1, 32, 2, 2, requires_grad=True), 0.1) if qlog is None else qlog
    physical = torch.expm1(qlog)
    return B0Output(logit, torch.sigmoid(logit), qlog, physical,
                    torch.sigmoid(logit) * physical.mean(1, keepdim=True),
                    (1, 48, 501, 501), (1, 48, 100, 100),
                    torch.ones(1, 1, 100, 100), torch.zeros(1, dtype=torch.long), torch.ones(1))


class ContractAndSpatialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.science, cls.engineering = load_contract(version="v1")  # immutable historical assertions
        cls.mapping = load_sp04()

    def test_status_and_unset_development_parameters(self):
        self.assertEqual(self.science["execution_status"]["B0_FORMAL_SCIENTIFIC_CONTRACT"], "FROZEN")
        self.assertIs(self.science["execution_status"]["B0_FORMAL_TRAINING_STARTED"], False)
        self.assertIs(self.engineering["formal_training_started"], False)
        self.assertIsNone(self.science["missing_qc"]["partial_and_support_thresholds"]["numeric_value"])
        self.assertEqual(self.science["missing_qc"]["partial_and_support_thresholds"]["status"], "DEVELOPMENT_ESTIMATED_PARAMETER")
        self.assertEqual(self.science["split"]["internal_final_test"]["may_tune_architecture_loss_normalization_epoch_checkpoint_threshold"], False)

    def test_engineering_config_all_explicit(self):
        e = self.engineering
        self.assertEqual(e["status"], "ENGINEERING_CONFIG")
        self.assertEqual(e["backbone"], {"groupnorm_groups": 8, "downsample_kernel": 3, "downsample_padding": 1,
                                          "decoder_interpolation_mode": "nearest", "align_corners": None,
                                          "input_projection_skip_initialization": "zeros"})
        self.assertEqual(e["projection"]["feature_reduction_operator"], "arithmetic_mean")
        self.assertEqual(e["loss"]["quantile_axis_reduction"], "mean")
        self.assertEqual(e["missing"]["tensor_placeholder"], 0.0)
        self.assertIs(e["missing"]["placeholder_is_physical_observation"], False)
        self.assertEqual(e["time"]["equal_obs_end_tie_breaker"], "lexicographically_smallest_path")
        self.assertEqual(e["staging"]["staging_root_env_var"], "YUNTAPR_B0_STAGING_ROOT")
        self.assertEqual(e["staging"]["max_temporary_bytes"], 16777216)
        self.assertIs(e["staging"]["verify_sha256"], True)

    def test_membership_10000_by_25_and_orientation(self):
        m = self.mapping
        self.assertEqual(tuple(m.indices.shape), (10000, 25))
        self.assertEqual(int(m.indices[0, 0]), 496 * 501)
        self.assertEqual(int(m.indices[-1, -1]), 5 * 501 + 499)
        self.assertTrue(np.all(np.diff(m.axes["native_lat"]) < 0))
        self.assertTrue(np.all(np.diff(m.axes["target_lat"]) > 0))
        self.assertEqual(m.manifest["yunnan_evaluation_mask_true_cells"], 3430)

    def test_projection_real_indices_not_reshape_or_flip(self):
        p = SP04Projection(self.mapping, "arithmetic_mean")
        native = torch.arange(501 * 501, dtype=torch.float32).reshape(1, 1, 501, 501)
        target = p(native)
        self.assertEqual(tuple(target.shape), (1, 1, 100, 100))
        self.assertAlmostEqual(float(target[0, 0, 0, 0]), float(self.mapping.indices[0].float().mean()), places=5)
        self.assertAlmostEqual(float(target[0, 0, -1, -1]), float(self.mapping.indices[-1].float().mean()), places=5)
        self.assertGreater(float(target[0, 0, 0, 0]), float(target[0, 0, -1, 0]))  # south target uses high source row

    def test_exact_axis_match_rejects_flip_and_reconstructed_rounding(self):
        m = self.mapping
        m.assert_axes(**m.axes)
        with self.assertRaisesRegex(ValueError, "no flip"):
            m.assert_axes(m.axes["native_lat"][::-1], m.axes["native_lon"], m.axes["target_lat"], m.axes["target_lon"])
        altered = m.axes["target_lat"].copy()
        altered[0] = np.nextafter(altered[0], np.float32(np.inf))
        with self.assertRaises(ValueError):
            m.assert_axes(m.axes["native_lat"], m.axes["native_lon"], altered, m.axes["target_lon"])
        with self.assertRaises(ValueError):
            m.assert_axes(m.axes["native_lat"].astype("float64"), m.axes["native_lon"], m.axes["target_lat"], m.axes["target_lon"])


class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = B0Model().eval()

    def test_full_forward_shapes_and_quantile_support(self):
        self.assertEqual(int(torch.count_nonzero(self.model.backbone.enc0.skip.weight)), 0)
        self.assertEqual(int(torch.count_nonzero(self.model.backbone.enc0.skip.bias)), 0)
        with torch.no_grad():
            x = torch.ones(1, 1, 501, 501)
            valid = torch.ones_like(x, dtype=torch.bool)
            valid[0, 0, 500, 0] = False
            x[~valid] = float("nan")
            out = self.model(x, valid)
        self.assertEqual(out.native_feature_shape, (1, 48, 501, 501))
        self.assertEqual(out.target_feature_shape, (1, 48, 100, 100))
        self.assertEqual(tuple(out.rain_logit.shape), (1, 1, 100, 100))
        self.assertEqual(tuple(out.rain_prob.shape), (1, 1, 100, 100))
        self.assertEqual(tuple(out.conditional_quantiles_log.shape), (1, 32, 100, 100))
        self.assertTrue(bool((out.conditional_quantiles_log[:, 1:] > out.conditional_quantiles_log[:, :-1]).all()))
        self.assertTrue(bool((out.conditional_quantiles_physical > 0.1).all()))
        self.assertAlmostEqual(float(out.target_support_fraction[0, 0, 0, 0]), 24 / 25, places=6)
        self.assertEqual(int(out.b13_invalid_count[0]), 1)
        self.assertTrue(torch.allclose(out.threshold_censored_mean, out.rain_prob * out.conditional_quantiles_physical.mean(1, keepdim=True)))
        self.assertEqual(out.exceedance_probability(0.1)["status"], "ESTABLISHED")
        self.assertEqual(out.exceedance_probability(100.0)["status"], "NOT_ESTABLISHED")

    def test_wrong_input_or_mask_fails(self):
        with self.assertRaisesRegex(ValueError, "501"):
            self.model(torch.zeros(1, 1, 500, 500), torch.ones(1, 1, 500, 500, dtype=torch.bool))
        with self.assertRaisesRegex(ValueError, "mask"):
            self.model(torch.ones(1, 1, 501, 501), torch.ones(1, 1, 501, 501))
        with self.assertRaisesRegex(ValueError, "all-fill"):
            self.model(torch.full((1, 1, 501, 501), float("nan")), torch.zeros(1, 1, 501, 501, dtype=torch.bool))

    def test_tau_exact_and_strict_failure(self):
        expected = torch.tensor([(i - .5) / 32 for i in range(1, 33)])
        self.assertTrue(torch.equal(frozen_taus(), expected))
        with self.assertRaises(FloatingPointError):
            monotonic_quantiles(torch.full((1, 32, 1, 1), -1e6), .1)

    def test_head_backward_and_state_dict_reload_engineering_only(self):
        features = torch.randn(1, 48, 100, 100, requires_grad=True)
        logit, prob, qlog, qphysical = self.model.heads(features)
        scalar = logit.mean() + qlog.mean() + (prob * qphysical.mean(1, keepdim=True)).mean()
        scalar.backward()
        self.assertTrue(torch.isfinite(features.grad).all())
        self.assertTrue(any(p.grad is not None and torch.isfinite(p.grad).all() for p in self.model.heads.parameters()))
        buffer = io.BytesIO()
        torch.save(self.model.state_dict(), buffer)
        buffer.seek(0)
        reloaded = B0Model().eval()
        reloaded.load_state_dict(torch.load(buffer, map_location="cpu", weights_only=True))
        self.assertTrue(torch.equal(reloaded.heads.occurrence.weight, self.model.heads.occurrence.weight))

    def test_full_model_backward_finite_engineering_only(self):
        model = B0Model()
        x = torch.ones(1, 1, 501, 501)
        valid = torch.ones_like(x, dtype=torch.bool)
        out = model(x, valid)
        (out.rain_logit.mean() + out.conditional_quantiles_log.mean()).backward()
        self.assertTrue(all(p.grad is not None and bool(torch.isfinite(p.grad).all()) for p in model.parameters()))


class DataAndLossTests(unittest.TestCase):
    def test_v07_final_provenance_requires_metadata_and_manifest(self):
        attrs = {"source": "GPM_3IMERGHH_07", "title": "GPM IMERG Final Run V07B regional subset"}
        row = {"status": "complete", "granules": 48, "bytes": 1129135}
        validate_final_provenance(attrs, row, 1129135)
        with self.assertRaisesRegex(ValueError, "V07 Final"):
            validate_final_provenance({**attrs, "source": "GPM_3IMERGHHL_07"}, row, 1129135)
        with self.assertRaisesRegex(ValueError, "48-granule"):
            validate_final_provenance(attrs, {**row, "granules": 47}, 1129135)

    def test_b13_packed_fill_and_partial(self):
        raw = np.array([[100, -9999]], dtype=np.int16)
        x, valid = decode_b13(raw, {"scale_factor": .01, "add_offset": 200.,
                                    "valid_min": 0, "valid_max": 30000, "_FillValue": -9999})
        self.assertTrue(valid[0, 0])
        self.assertFalse(valid[0, 1])
        self.assertTrue(np.isnan(x[0, 1]))

    def test_zero_is_valid_missing_excluded(self):
        raw = np.array([[0.0, -9999.0]], dtype=np.float32)
        y, valid = decode_imerg(raw, {"_FillValue": -9999.0})
        self.assertTrue(valid[0, 0])
        self.assertEqual(y[0, 0], 0.0)
        self.assertFalse(valid[0, 1])
        self.assertTrue(np.isnan(y[0, 1]))

    def test_causal_latest_and_no_fallback(self):
        t = datetime(2024, 7, 1, tzinfo=timezone.utc)
        frames = [HimawariFrame(Path("b.nc"), t + timedelta(minutes=10), t + timedelta(minutes=10), t + timedelta(minutes=19), None),
                  HimawariFrame(Path("a.nc"), t + timedelta(minutes=20), t + timedelta(minutes=20), t + timedelta(minutes=29), None),
                  HimawariFrame(Path("future.nc"), t + timedelta(minutes=30), t + timedelta(minutes=30), t + timedelta(minutes=39), None)]
        self.assertEqual(select_latest_causal_frame(frames, t + timedelta(minutes=30)).path, Path("a.nc"))
        with self.assertRaisesRegex(ValueError, "NO_COMPLETED"):
            select_latest_causal_frame(frames[-1:], t + timedelta(minutes=30))

    def test_dataset_partial_and_2025_october_roles(self):
        m = load_sp04()
        t = datetime(2025, 10, 1, tzinfo=timezone.utc)
        path = REPO_ROOT / "config/science_contract_v1.yaml"  # existing-file stub; reader is synthetic
        frame = HimawariFrame(path, t + timedelta(minutes=20), t + timedelta(minutes=20), t + timedelta(minutes=29), None)
        def reader(_path, _nominal):
            x = np.ones((501, 501), dtype=np.float32)
            valid = np.ones((501, 501), dtype=bool)
            x[500, 0] = np.nan
            valid[500, 0] = False
            return x, valid, frame
        record = B0Record("engineering-oct", t, (frame,), None, None, None, None, None)
        sample = B0Dataset([record], m, np.ones((100, 100), dtype=bool), reader, None, engineering_fixture_mask=True)[0]
        self.assertTrue(sample.inference_eligible)
        self.assertFalse(sample.supervised_eligible)
        self.assertFalse(sample.internal_test_eligible)
        self.assertEqual(sample.b13_invalid_count, 1)
        self.assertAlmostEqual(float(sample.target_support_fraction[0, 0]), 24 / 25, places=6)
        self.assertEqual(sample.analysis_time, t + timedelta(minutes=30))
        with self.assertRaisesRegex(ValueError, "frozen SHA-verified"):
            B0Dataset([record], m, np.ones((100, 100), dtype=bool), reader, None)
        unverified_final = B0Record("unverified", t, (frame,), path, 0, "IMERG", "V07", "Final")
        with self.assertRaisesRegex(ValueError, "provenance must be verified"):
            B0Dataset([unverified_final], m, None, reader, None)[0]
        missing = HimawariFrame(REPO_ROOT / "nonexistent_B0_frame.nc", frame.nominal_time, frame.obs_start, frame.obs_end, None)
        with self.assertRaisesRegex(FileNotFoundError, "REQUIRED_HIMAWARI_FRAME_MISSING"):
            B0Dataset([B0Record("missing", t, (missing,), None, None, None, None, None)], m, None, reader, None)[0]
        def all_fill(_path, _nominal):
            return np.full((501, 501), np.nan, dtype=np.float32), np.zeros((501, 501), dtype=bool), frame
        with self.assertRaisesRegex(ValueError, "B13_ALL_FILL"):
            B0Dataset([record], m, None, all_fill, None)[0]

    def test_masked_loss_denominator_and_empty_rain(self):
        out = tiny_output()
        y = torch.tensor([[[[0.0, 1.0], [float("nan"), 2.0]]]])
        valid = torch.tensor([[[[True, True], [False, True]]]])
        mask = torch.tensor([[[[True, True], [True, False]]]])
        losses = b0_core_loss(out, y, valid, mask, focal_alpha=.4, focal_gamma=1., quantile_axis_reduction="mean")
        self.assertEqual(losses.valid_supervised_count, 2)
        self.assertEqual(losses.rainy_valid_count, 1)
        self.assertTrue(torch.isfinite(losses.total))
        rainy_only = torch.tensor([[[[False, True], [False, False]]]])
        same_y = torch.where(rainy_only, y, torch.full_like(y, 1e5))
        same_valid = b0_core_loss(out, same_y, valid, mask, focal_alpha=.4, focal_gamma=1., quantile_axis_reduction="mean")
        self.assertEqual(same_valid.valid_supervised_count, 2)
        self.assertNotEqual(float(losses.total.detach()), float(same_valid.total.detach()))  # valid dry zero really participates
        dry = b0_core_loss(out, torch.zeros_like(out.rain_logit), torch.ones_like(valid), torch.ones_like(mask),
                           focal_alpha=.4, focal_gamma=1., quantile_axis_reduction="mean")
        self.assertTrue(dry.conditional_skipped)
        self.assertEqual(dry.rainy_valid_count, 0)
        self.assertEqual(float(dry.conditional_quantile.detach()), 0)
        empty = b0_core_loss(out, y, torch.zeros_like(valid), mask, focal_alpha=.4, focal_gamma=1., quantile_axis_reduction="mean")
        self.assertTrue(empty.batch_skipped)
        self.assertEqual(empty.valid_supervised_count, 0)
        self.assertEqual(float(empty.total.detach()), 0)

    def test_missing_focal_development_values_fail_loudly(self):
        out = tiny_output()
        y = torch.zeros_like(out.rain_logit)
        mask = torch.ones_like(y, dtype=torch.bool)
        with self.assertRaisesRegex(ValueError, "REQUIRED_DEVELOPMENT_PARAMETER"):
            b0_core_loss(out, y, mask, mask, quantile_axis_reduction="mean", formal_mode=True)

    def test_metric_excludes_invalid_target(self):
        out = tiny_output()
        y = torch.tensor([[[[0.0, float("nan")], [2.0, 0.0]]]])
        valid = torch.tensor([[[[True, False], [True, True]]]])
        mask = torch.ones_like(valid)
        metric = brier_at_occurrence(out, y, valid, mask)
        self.assertEqual(metric["count"], 3)
        self.assertTrue(torch.isfinite(metric["value"]))

    def test_forbidden_imports_absent_and_no_formal_checkpoint(self):
        forbidden = ("gfs", "dem", "dote", "dtfm", "mee", "era5", "attention", "transformer", "convlstm", "convgru")
        src = REPO_ROOT / "src/yuntapr"
        for file in src.rglob("*.py"):
            tree = ast.parse(file.read_text(encoding="utf-8"))
            imports = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
            imports += [alias.name for n in ast.walk(tree) if isinstance(n, ast.Import) for alias in n.names]
            self.assertFalse(any(any(word in name.lower() for word in forbidden) for name in imports), str(file))
        self.assertFalse(any(src.rglob("*.ckpt")))
        self.assertFalse(any(src.rglob("*.pt")))
        if (REPO_ROOT / "docs/b0_skeleton").exists():
            self.assertFalse(any((REPO_ROOT / "docs/b0_skeleton").rglob("*.pt")))


if __name__ == "__main__":
    unittest.main()
