"""v1.1 contract, formal QC, train-only statistics, precision guards and staging."""
import ast
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import inspect
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import torch

from yuntapr.contracts.loader import REPO_ROOT, load_contract, sha256
from yuntapr.data.dataset_b0 import B0Dataset, B0Record
from yuntapr.data.formal_policy import require_phase_a_fit_time, MISSING_LATEST
from yuntapr.data.normalization import PhaseANormalizer
from yuntapr.data.sample_schema import HimawariFrame
from yuntapr.data.staging import BoundedEnglishStaging
from yuntapr.models.b0 import B0Model
from yuntapr.models.monotonic_quantiles import monotonic_quantiles
from yuntapr.spatial.sp04_mapping import load_sp04
from yuntapr.training.batch_contract import B0Batch

torch.set_num_threads(2)


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s, cls.e = load_contract()
        cls.old, cls.old_e = load_contract(version="v1")

    def test_supersedes_only_approved_scopes(self):
        allowed = {"schema_version", "contract_id", "authoritative_document", "precedence", "execution_status", "decision_status", "formal_b0_supervision", "normalization", "quantile_numerical_implementation"}
        changed = {k for k in self.s if self.s.get(k) != self.old.get(k)}
        self.assertLessEqual(changed, allowed)
        self.assertEqual(self.s["precedence"]["inherits_sha256"], sha256(REPO_ROOT/"config/science_contract_v1.yaml"))

    def test_d1_through_d7_exactly_inherited(self):
        for name in ("time", "temporal_data_role", "spatial", "split", "missing_qc", "probability", "backbone"):
            self.assertEqual(self.s[name], self.old[name], name)
        self.assertEqual(self.s["decision_status"][:7], self.old["decision_status"])

    def test_d8_frozen_and_not_manual_values(self):
        n = self.s["normalization"]
        self.assertEqual(n["status"], "FROZEN")
        self.assertEqual(n["policy"], "TRAIN_ONLY_Z_SCORE")
        self.assertEqual(n["numeric_values_status"], "DEVELOPMENT_DERIVED_PARAMETER")
        self.assertNotIn("mean_K", n)

    def test_2023_only_fit_guard(self):
        require_phase_a_fit_time("2023-03-01T00:00:00Z")
        require_phase_a_fit_time("2023-10-31T23:30:00Z")
        with self.assertRaises(ValueError):
            require_phase_a_fit_time("2023-11-01T00:00:00Z")

    def test_2024_not_fit_phase_a(self):
        with self.assertRaisesRegex(ValueError, "2023"):
            require_phase_a_fit_time("2024-07-01T00:00:00Z")
        self.assertFalse(self.s["normalization"]["phase_a"]["validation_refit_allowed"])

    def test_2025_never_fit(self):
        with self.assertRaisesRegex(ValueError, "2023"):
            require_phase_a_fit_time("2025-07-01T00:00:00Z")
        self.assertEqual(self.s["normalization"]["phase_b"]["fit_years"], [2023, 2024])
        self.assertFalse(self.s["normalization"]["phase_b"]["statistics_ready"])
        self.assertEqual(self.s["normalization"]["final_test"]["statistics_source"], "Phase_B_FinalFit")

    def test_derived_artifact_population_and_pins(self):
        normalizer = PhaseANormalizer.from_pinned()
        data = json.loads((REPO_ROOT/self.s["normalization"]["phase_a"]["artifact"]).read_text(encoding="utf-8"))
        self.assertEqual(data["fit_years"], [2023])
        self.assertEqual(data["ddof"], 0)
        self.assertEqual(data["valid_pixel_count"], data["eligible_scene_count"]*251001)
        self.assertEqual(data["eligible_scene_count"], 11720)
        self.assertAlmostEqual(data["mean_K"], data["streaming_mean_K"], places=9)
        self.assertAlmostEqual(data["std_K"], data["streaming_std_K"], places=9)
        self.assertGreater(normalizer.sigma, 0)

    def test_epsilon_read_from_config_and_model(self):
        self.assertEqual(self.e["quantile_numerics"]["epsilon_mono"], 1e-4)
        self.assertEqual(B0Model().heads.epsilon_mono, 1e-4)

    def test_training_stays_false(self):
        self.assertFalse(self.s["execution_status"]["B0_FORMAL_TRAINING_STARTED"])
        self.assertFalse(self.s["execution_status"]["FORMAL_TRAINING_AUTHORIZED"])
        self.assertFalse(self.e["formal_training_started"])

    def test_no_checkpoint(self):
        for root in (REPO_ROOT/"src", REPO_ROOT/"docs/b0_pretraining_closure"):
            self.assertFalse(any(p.suffix in (".pt", ".pth", ".ckpt") for p in root.rglob("*")))

    def test_no_optimizer_step(self):
        paths = list((REPO_ROOT/"src/yuntapr").rglob("*.py"))
        paths += list((REPO_ROOT/"scripts").glob("*v1_1*.py"))
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            calls = [n.func for n in ast.walk(tree) if isinstance(n, ast.Call)]
            self.assertFalse(any(isinstance(n, ast.Attribute) and n.attr == "step" for n in calls), str(path))


class RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mapping = load_sp04()
        cls.normalizer = PhaseANormalizer("ENGINEERING_FIXTURE", 270., 20., "fixture-not-production")

    def fixture(self, *, year=2023, partial=False, older=False, allfill=False, future=False, missing_label=False):
        t = datetime(year, 7, 1, tzinfo=timezone.utc)
        path = REPO_ROOT/"config/science_contract_v1.yaml"
        nominal = t+timedelta(minutes=10 if older else 20)
        frame = HimawariFrame(path, nominal, nominal, t+timedelta(minutes=31 if future else 29), None)
        rec = B0Record("fixture", t, (frame,), None if missing_label else path, None if missing_label else 0,
                       None if missing_label else "IMERG", None if missing_label else "V07", None if missing_label else "Final", True)
        def b13(_path, _nominal):
            x = np.full((501,501), 280., dtype=np.float32)
            valid = np.ones_like(x, dtype=bool)
            if partial:
                valid[0,0] = False
            if allfill:
                valid[:] = False
            x[~valid] = np.nan
            return x, valid, frame
        def imerg(_path, _index):
            return np.ones((100,100), dtype=np.float32), np.ones((100,100), dtype=bool), t
        return B0Dataset([rec], self.mapping, np.ones((100,100), dtype=bool), b13, imerg,
                         engineering_fixture_mask=True, formal_supervised=True, normalizer=self.normalizer)

    def test_partial_formal_rejected(self):
        with self.assertRaisesRegex(ValueError, "PARTIAL_FORMAL"):
            self.fixture(partial=True)[0]

    def test_full_valid_formal_accepts_and_normalizes(self):
        sample = self.fixture()[0]
        self.assertTrue(sample.formal_supervised_qc_pass)
        self.assertTrue(sample.b13_full_valid)
        self.assertFalse(sample.used_older_causal_frame)
        self.assertTrue(np.all(sample.x_b13 == 280.))
        self.assertTrue(np.all(sample.x_b13_normalized == .5))
        self.assertEqual(sample.normalization_mu, 270.)
        self.assertEqual(sample.normalization_sigma, 20.)
        B0Batch.from_formal_samples([sample]).validate_formal()

    def test_missing_latest_older_exists_rejects(self):
        with self.assertRaisesRegex(ValueError, MISSING_LATEST):
            self.fixture(older=True)[0]

    def test_no_silent_fallback_reader_not_called(self):
        ds = self.fixture(older=True)
        with patch.object(ds, "b13_reader") as reader:
            with self.assertRaisesRegex(ValueError, MISSING_LATEST):
                ds[0]
            reader.assert_not_called()

    def test_future_latest_rejects(self):
        with self.assertRaisesRegex(ValueError, "NO_COMPLETED"):
            self.fixture(future=True)[0]

    def test_allfill_rejects(self):
        with self.assertRaisesRegex(ValueError, "ALL_FILL"):
            self.fixture(allfill=True)[0]

    def test_missing_imerg_rejects_before_normalization(self):
        with self.assertRaisesRegex(ValueError, "ELIGIBILITY"):
            self.fixture(missing_label=True)[0]

    def test_2024_uses_identical_constants(self):
        a, b = self.fixture()[0], self.fixture(year=2024)[0]
        self.assertEqual(a.normalization_mu, b.normalization_mu)
        self.assertEqual(a.normalization_sigma, b.normalization_sigma)
        self.assertTrue(np.array_equal(a.x_b13_normalized, b.x_b13_normalized))

    def test_2025_cannot_use_phase_a_statistics(self):
        with self.assertRaisesRegex(ValueError, "2025_REQUIRES_FINALFIT"):
            self.fixture(year=2025)[0]

    def test_raw_kelvin_cannot_bypass_normalized_batch(self):
        s = self.fixture()[0]
        batch = B0Batch.from_formal_samples([s])
        batch.x_b13.fill_(280.)
        with self.assertRaisesRegex(ValueError, "NOT_VERIFIED_NORMALIZED"):
            batch.validate_formal()

    def test_partial_cannot_reach_formal_backbone(self):
        batch = B0Batch.from_formal_samples([self.fixture()[0]])
        batch.b13_valid_mask[0,0,0,0] = False
        model = B0Model()
        with patch.object(model.backbone, "forward") as forward:
            with self.assertRaisesRegex(ValueError, "FULL_VALID"):
                model.forward_formal(batch)
            forward.assert_not_called()

    def test_formal_route_contains_no_placeholder(self):
        text = inspect.getsource(B0Model.forward_formal)
        self.assertNotIn("torch.where", text)
        self.assertIn("validate_formal", text)


class QuantileTests(unittest.TestCase):
    def test_constants_strict_finite_and_finite_gradient(self):
        eps = load_contract()[1]["quantile_numerics"]["epsilon_mono"]
        for value in (-100,-80,-40,-20,-10,0,10,40,80,100):
            with self.subTest(raw=value):
                raw = torch.full((1,32,2,2), float(value), requires_grad=True)
                q = monotonic_quantiles(raw, .1, epsilon_mono=eps)
                self.assertTrue(torch.isfinite(q).all())
                self.assertTrue((q[:,1:] > q[:,:-1]).all())
                self.assertEqual(int((q[:,1:] == q[:,:-1]).sum()), 0)
                q.mean().backward()
                self.assertTrue(torch.isfinite(raw.grad).all())

    def test_known_mixed_extreme_loss_raises(self):
        raw = torch.full((1,32,1,1), -100.)
        raw[:, :22] = 100.
        with self.assertRaisesRegex(FloatingPointError, "tensor precision"):
            monotonic_quantiles(raw, .1, epsilon_mono=1e-4)

    def test_no_sort_clamp_rank_repair(self):
        tree = ast.parse(inspect.getsource(monotonic_quantiles))
        attrs = [n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)]
        self.assertFalse(set(attrs) & {"sort", "argsort", "clamp", "clamp_min", "nan_to_num"})


class StagingTests(unittest.TestCase):
    def test_largest_file_fits_with_fixed_margin(self):
        cap = load_contract()[1]["staging"]["max_temporary_bytes"]
        self.assertGreaterEqual(cap, 636106619+32*1024**2)
        self.assertGreaterEqual(cap, 734003200)

    def test_one_file_sha_cleanup(self):
        with tempfile.TemporaryDirectory(prefix="yuntapr_test_") as root:
            src = Path(root)/"source.nc"
            src.write_bytes(b"fixture")
            stage = BoundedEnglishStaging(Path(root)/"staging", 1024, True, True)
            before = sha256(src)
            with stage.local(src) as local:
                self.assertEqual(local.read_bytes(), b"fixture")
                with self.assertRaisesRegex(ValueError, "one external"):
                    with stage.local(src):
                        self.fail("Nested staging accepted")
            self.assertFalse(local.exists())
            self.assertEqual(sha256(src), before)
            self.assertTrue(stage.records[-1].sha256_match)
            self.assertTrue(stage.records[-1].cleanup_success)
            self.assertFalse(stage._owned)

    def test_cleanup_failure_logged_and_blocks_next_copy(self):
        with tempfile.TemporaryDirectory(prefix="yuntapr_test_") as root:
            src = Path(root)/"source.nc"
            src.write_bytes(b"fixture")
            stage = BoundedEnglishStaging(Path(root)/"staging", 1024, True, True)
            with patch.object(Path, "unlink", side_effect=PermissionError("injected cleanup failure")):
                with self.assertRaisesRegex(IOError, "STAGING_CLEANUP_REQUIRED"):
                    with stage.local(src):
                        pass
            self.assertIn("injected", stage.records[-1].cleanup_error)
            with self.assertRaises(ValueError):
                with stage.local(src):
                    self.fail("Staging exceeded bounded owned file count")
            self.assertTrue(src.exists())

    def test_non_ascii_root_rejected(self):
        with self.assertRaisesRegex(ValueError, "ASCII"):
            BoundedEnglishStaging(Path(tempfile.gettempdir())/"中文", 1024, True, True)


if __name__ == "__main__":
    unittest.main()
