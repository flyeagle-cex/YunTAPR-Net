"""Numerical closure tests distinguish monotonic precision from physical overflow."""
import ast
import copy
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
import textwrap
import unittest

import torch

from yuntapr.contracts.loader import REPO_ROOT, load_contract, sha256
from yuntapr.losses.pinball import frozen_taus, pinball_sum
from yuntapr.losses.total_loss import b0_core_loss
from yuntapr.models.b0 import B0Model
from yuntapr.models.monotonic_quantiles import monotonic_quantiles
from yuntapr.models.probability_heads import B0Output, ProbabilityHeads

BASELINE = "957e8519e8063a6174b7bced5f10a819be0ef64e"
RUN = REPO_ROOT / "docs/quantile_numerical_closure/runs/run_20260930T110155Z"
torch.set_num_threads(2)


class FreezeAndConfig(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.science, cls.v4 = load_contract()
        cls.old_science, cls.v3 = load_contract(engineering_version=3)

    def test_scientific_contract_byte_identical_to_baseline(self):
        path = "config/science_contract_v1.1.yaml"
        historical = subprocess.check_output(["git", "show", BASELINE+":"+path], cwd=REPO_ROOT)
        self.assertEqual(hashlib.sha256(historical).hexdigest(), sha256(REPO_ROOT/path))
        self.assertEqual(self.science, self.old_science)

    def test_v4_changes_only_numerical_engineering(self):
        old, new = copy.deepcopy(self.v3), copy.deepcopy(self.v4)
        old.pop("schema_version")
        new.pop("schema_version")
        old.pop("quantile_numerics")
        new.pop("quantile_numerics")
        self.assertEqual(old, new)
        q = self.v4["quantile_numerics"]
        self.assertEqual(q["status"], "ENGINEERING_CONFIG")
        self.assertEqual(q["epsilon_mono"], self.v3["quantile_numerics"]["epsilon_mono"])
        self.assertEqual((q["raw_dtype"], q["accumulation_dtype"], q["qlog_output_dtype"], q["physical_quantile_dtype"]),
                         ("float32", "float64", "float64", "float64"))

    def test_probability_semantics_and_tau_unchanged(self):
        self.assertEqual(self.science["probability"]["occurrence"]["threshold"], .1)
        expected = torch.tensor([(i-.5)/32 for i in range(1,33)], dtype=torch.float64)
        self.assertTrue(torch.equal(frozen_taus(dtype=torch.float64), expected))
        self.assertEqual(len(expected), 32)

    def test_backbone_and_head_parameter_dtype(self):
        model = B0Model()
        self.assertTrue(all(p.dtype == torch.float32 for p in model.parameters()))
        self.assertEqual(model.heads.accumulation_dtype, torch.float64)

    def test_training_still_forbidden(self):
        self.assertIs(self.science["execution_status"]["B0_FORMAL_TRAINING_STARTED"], False)
        self.assertIs(self.science["execution_status"]["FORMAL_TRAINING_AUTHORIZED"], False)
        self.assertIs(self.v4["formal_training_started"], False)
        self.assertFalse(any(RUN.rglob("*.pt")))
        self.assertFalse(any(RUN.rglob("*.ckpt")))
        tree = ast.parse((REPO_ROOT/"scripts/quantile_numerical_closure_v1.py").read_text(encoding="utf-8"))
        self.assertFalse(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "step"
                             for n in ast.walk(tree)))


class Numerics(unittest.TestCase):
    def test_mixed_counterexample_strict_in_float64(self):
        raw = torch.full((1,32,1,1), -100., requires_grad=True)
        with torch.no_grad():
            raw[:, :22] = 100.
        q = monotonic_quantiles(raw, .1, epsilon_mono=1e-4, accumulation_dtype=torch.float64)
        self.assertEqual(q.dtype, torch.float64)
        self.assertTrue(torch.isfinite(q).all())
        self.assertTrue((q[:,1:] > q[:,:-1]).all())
        self.assertEqual(int((q[:,1:] == q[:,:-1]).sum()), 0)
        q.mean().backward()
        self.assertEqual(raw.grad.dtype, torch.float32)
        self.assertTrue(torch.isfinite(raw.grad).all())

    def test_head_qlog_and_physical_double(self):
        head = ProbabilityHeads(48, .1, epsilon_mono=1e-4, accumulation_dtype=torch.float64)
        _, _, qlog, qphysical = head(torch.zeros(1,48,100,100))
        self.assertEqual(qlog.dtype, torch.float64)
        self.assertEqual(qphysical.dtype, torch.float64)
        self.assertTrue((qlog[:,1:]>qlog[:,:-1]).all())
        self.assertTrue(torch.isfinite(qphysical).all())

    def test_autocast_cannot_lower_quantile_dtype(self):
        head = ProbabilityHeads(48, .1, epsilon_mono=1e-4, accumulation_dtype=torch.float64)
        raw_dtype = []
        hook = head.quantile.register_forward_hook(lambda _m, _i, o: raw_dtype.append(o.dtype))
        try:
            with torch.autocast(device_type="cpu", dtype=torch.bfloat16):
                logit, probability, qlog, physical = head(torch.randn(1,48,100,100))
                loss = qlog.mean() + physical.mean() * 0
            loss.backward()
        finally:
            hook.remove()
        self.assertEqual(raw_dtype, [torch.float32])
        self.assertEqual(qlog.dtype, torch.float64)
        self.assertEqual(physical.dtype, torch.float64)
        self.assertEqual(head.quantile.weight.grad.dtype, torch.float32)
        self.assertTrue(torch.isfinite(head.quantile.weight.grad).all())

    def test_float64_pinball_target_tau_and_gradient(self):
        raw = torch.zeros((1,32,2,2), requires_grad=True)
        qlog = monotonic_quantiles(raw, .1, epsilon_mono=1e-4, accumulation_dtype=torch.float64)
        logit = torch.zeros((1,1,2,2), requires_grad=True)
        output = B0Output(logit, torch.sigmoid(logit), qlog, torch.expm1(qlog),
                          torch.expm1(qlog).mean(1, keepdim=True), (1,48,501,501),
                          (1,48,100,100), torch.ones(1,1,2,2), torch.zeros(1), torch.ones(1))
        y = torch.tensor([[[[0.,1.],[2.,3.]]]], dtype=torch.float32)
        mask = torch.ones_like(y, dtype=torch.bool)
        result = b0_core_loss(output, y, mask, mask, focal_alpha=.25, focal_gamma=2., quantile_axis_reduction="mean")
        self.assertEqual(result.conditional_quantile.dtype, torch.float64)
        self.assertEqual(result.total.dtype, torch.float64)
        self.assertTrue(torch.isfinite(result.total))
        result.total.backward()
        self.assertEqual(raw.grad.dtype, torch.float32)
        self.assertTrue(torch.isfinite(raw.grad).all())
        self.assertTrue((raw.grad != 0).any())
        with self.assertRaisesRegex(ValueError, "qlog precision"):
            pinball_sum(qlog, torch.zeros(1,1,2,2), mask, "mean")

    def test_physical_overflow_has_separate_error(self):
        head = ProbabilityHeads(48, .1, epsilon_mono=1e-4, accumulation_dtype=torch.float64)
        with torch.no_grad():
            head.quantile.weight.zero_()
            head.quantile.bias.fill_(100.)
        with self.assertRaisesRegex(FloatingPointError, "QUANTILE_PHYSICAL_OVERFLOW"):
            head(torch.zeros(1,48,100,100))

    def test_nonfinite_raw_has_monotonic_error(self):
        raw = torch.full((1,32,1,1), float("nan"))
        with self.assertRaisesRegex(FloatingPointError, "QUANTILE_MONOTONICITY_LOST"):
            monotonic_quantiles(raw, .1, epsilon_mono=1e-4, accumulation_dtype=torch.float64)

    def test_no_sort_clamp_or_downcast_in_transform(self):
        code = inspect.getsource(monotonic_quantiles)+inspect.getsource(ProbabilityHeads.forward)
        trees = (ast.parse(inspect.getsource(monotonic_quantiles)),
                 ast.parse(textwrap.dedent(inspect.getsource(ProbabilityHeads.forward))))
        calls = {n.attr for tree in trees for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        self.assertFalse(calls & {"sort", "argsort", "clamp", "clamp_min", "clamp_max", "nan_to_num"})
        self.assertIn("accumulation_dtype=self.accumulation_dtype", code)


class MeasuredResults(unittest.TestCase):
    def test_all_14_monotonic_cases(self):
        data = json.loads((RUN/"quantile_stress_float64.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data["cases"]), 14)
        self.assertTrue(data["all_required_cases_pass"])
        self.assertTrue(all(r["adjacent_equal_count"] == 0 and r["gradient_finite"] for r in data["cases"]))

    def test_real_2023_2024_and_gradient_trace(self):
        smoke = json.loads((RUN/"real_regression_smoke.json").read_text(encoding="utf-8"))
        trace = json.loads((RUN/"gradient_dtype_trace.json").read_text(encoding="utf-8"))
        self.assertTrue(smoke["all_passed"])
        self.assertEqual({s["year"] for s in smoke["samples"]}, {2023,2024})
        self.assertTrue(trace["all_dtype_and_gradient_contracts_pass"])
        self.assertTrue(all(t["nonzero_quantile_gradient"] and t["nonzero_backbone_gradient"] for t in trace["samples"]))


if __name__ == "__main__":
    unittest.main()
