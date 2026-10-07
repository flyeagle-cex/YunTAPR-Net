"""Read-only scientific diagnostics; no fitting, optimization or sample selection."""
from __future__ import annotations

from dataclasses import replace
import csv
import hashlib
import heapq
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch
from torch.utils.data import Dataset

from yuntapr.contracts.loader import sha256
from yuntapr.data.dataset_b0 import B0Dataset, B0Record
from yuntapr.data.normalization import PhaseANormalizer
from yuntapr.data.sample_schema import utc
from yuntapr.data.staging import BoundedEnglishStaging, StagedB13Reader, StagedIMERGReader
from yuntapr.training.formal_phase_a import SCOPE as INHERITED_SCOPE, NORMALIZATION_SHA, MU, SIGMA, guard_record
from yuntapr.training.phase_a_validation import GlobalValidationAccumulator

SCOPE = "SCIENTIFIC_RESULT_REVIEW_ONLY"
BASELINE = "5383dfceda6cc64e6907c6953032a14935c0ee46"
BEST_SHA = "3f517f31394a4efa54ea0abed7757c7d59eb048416cfa98f02ab91ba60c24fe3"
BEST_BYTES = 52062315
N_SCENES, N_VALID, N_RAIN = 11727, 40223610, 4809183
BEST_CORE = 0.04730775889882134
TAU = (np.arange(1, 33, dtype=np.float64) - .5) / 32
HROOT = Path(r"H:\葵花202303_202510")
IROOT = Path(r"F:\云南极端降水数据\raw\IMERG\2024")
RATE_UPPER = np.array([1., 5., 10., 20., 30., 50., np.inf])
RATE_LABELS = ["(0.1,1]", "(1,5]", "(5,10]", "(10,20]", "(20,30]", "(30,50]", "(50,inf)"]


def rows(path):
    with Path(path).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def table(path, values):
    if not values:
        raise ValueError("Empty diagnostic table")
    with Path(path).open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(values[0]))
        writer.writeheader()
        writer.writerows(values)


def diagnostic_rules():
    return {"scope": SCOPE, "declared_before_inference": True,
        "case_rules": ["MAX_ABSOLUTE_DIAGNOSTIC_PROXY_ERROR", "HIGHEST_TRUE_RAIN_RATE", "LOWEST_TRUE_RATE_AMONG_RAINY"],
        "top_N_each": 10, "ties": "frozen scene order, then target row-major cell index",
        "probability_edges": [i / 10 for i in range(11)], "last_probability_bin_includes_one": True,
        "rainrate_bins": RATE_LABELS, "rate_bin_status": "DESCRIPTIVE_RATE_BINS_ONLY",
        "rainy_definition": "float32 target > float32(0.1), before float64 promotion; frozen production convention",
        "spatial_conditional_pinball_min_rain_count": 30, "minimum_count_scope": "DISPLAY_DIAGNOSTIC_ONLY",
        "quantile_groups": {"low": "tau < 0.2", "middle": "0.2 <= tau <= 0.8", "high": "tau > 0.8"},
        "group_status": "ANALYTIC_GROUPING_ONLY", "exceedances_mm_h": [10, 20, 30, 50],
        "exceedance_status": "DESCRIPTIVE_ONLY", "extreme_definition": "NOT_FROZEN",
        "probability_histogram_edges": [i / 100 for i in range(101)],
        "no_evaluation_population_changes": True, "no_cutoff_selection": True,
        "metric_comparison_tolerance": {"absolute": 1e-12, "relative": 1e-12},
        "integer_counts_and_quantile_coverage_require_exact_match": True}


class InferenceOnlyGuard:
    """Make accidental optimizer construction/step or any backward fail immediately."""
    def __init__(self):
        self.attempts = {"optimizer_creation": 0, "optimizer_step": 0, "backward": 0}
        self.saved = []

    def __enter__(self):
        def patch(owner, name, kind):
            old = getattr(owner, name)
            def reject(*args, **kwargs):
                self.attempts[kind] += 1
                raise RuntimeError("SCIENTIFIC_RESULT_REVIEW_ONLY prohibits " + kind)
            self.saved.append((owner, name, old))
            setattr(owner, name, reject)
        patch(torch.optim.Optimizer, "__init__", "optimizer_creation")
        for value in vars(torch.optim).values():
            if isinstance(value, type) and issubclass(value, torch.optim.Optimizer) and "step" in value.__dict__:
                patch(value, "step", "optimizer_step")
        patch(torch.Tensor, "backward", "backward")
        patch(torch.autograd, "backward", "backward")
        patch(torch.autograd, "grad", "backward")
        return self

    def __exit__(self, *exc):
        for owner, name, old in reversed(self.saved):
            setattr(owner, name, old)


def guard_identity(identity):
    """Reject wrong roles, years and paths before either staging reader can open data."""
    start = utc(identity["window_start"])
    if identity["role"] != "Validation" or start.year != 2024 or start.month not in range(3, 11) or int(identity["year"]) != 2024:
        raise ValueError("Review permits only frozen 2024 Validation sources")
    h = (HROOT / identity["b13_relative_path"]).resolve()
    i = Path(identity["imerg_day_path"]).resolve()
    if (not h.is_relative_to(HROOT.resolve()) or h.relative_to(HROOT.resolve()).parts[0] != start.strftime("%Y%m")
            or not i.is_relative_to(IROOT.resolve())):
        raise ValueError("Unauthorized raw path before I/O")
    return h, i


class ReviewDataset(Dataset):
    """Use formal readers/QC/normalizer without reading the old mixed-year QC file.

    The formal source SHA pins the full metadata too. Actual B13 timestamps are read
    once from the verified staging copy, checked against frozen pairing evidence,
    and then passed to the unchanged B0 assembler through an in-memory reader.
    """
    def __init__(self, identities, pairs, mapping, yunnan, mask_path, stage_root, authorization):
        for identity in identities:
            guard_identity(identity)
        self.identities, self.pairs = identities, pairs
        self.mapping, self.yunnan, self.mask_path = mapping, yunnan, mask_path
        self.stage_root, self.authorization = stage_root, authorization
        self.normalizer = PhaseANormalizer.from_pinned()
        self.set_staging("main")

    def set_staging(self, suffix):
        self.staging = BoundedEnglishStaging(self.stage_root / suffix, 734003200, True, True)
        self.b13_reader = StagedB13Reader(self.staging, self.mapping)
        self.imerg_reader = StagedIMERGReader(self.staging, self.mapping)

    def __len__(self):
        return len(self.identities)

    def __getitem__(self, index):
        expected = self.identities[index]
        h, i = guard_identity(expected)
        pair = self.pairs[index]
        before = len(self.staging.records)
        x, valid, observed = self.b13_reader(h, utc(pair["expected_nominal"]))
        if (observed.obs_end != utc(pair["selected_obs_end"]) or observed.nominal_time != utc(pair["selected_nominal"])
                or observed.obs_start > observed.obs_end):
            raise ValueError("Source timestamps differ from frozen causal pairing")
        record = B0Record(expected["sample_id"], utc(expected["window_start"]), (observed,), i,
            int(expected["imerg_index"]), "IMERG", "V07", "Final", True)
        guard_record(record)
        def cached_reader(path, nominal):
            if path != h or nominal != observed.nominal_time:
                raise ValueError("Unexpected cached source request")
            return x, valid, observed
        assembler = B0Dataset([record], self.mapping, self.yunnan, cached_reader, self.imerg_reader,
            frozen_mask_path=self.mask_path, formal_supervised=True, normalizer=self.normalizer)
        sample = assembler[0]
        staged = self.staging.records[before:]
        if (len(staged) != 2 or [r.source_sha256 for r in staged] != [expected["b13_sha256"], expected["imerg_sha256"]]
                or staged[0].temporary_bytes != int(expected["b13_bytes"])
                or any(not r.cleanup_success or not r.sha256_match for r in staged) or self.staging._owned):
            raise ValueError("Source SHA/size/staging cleanup differs from formal identity")
        supervised = sample.imerg_valid_mask & sample.yunnan_eval_mask
        if (not sample.formal_supervised_qc_pass or not sample.b13_full_valid or sample.used_older_causal_frame
                or sample.normalization_artifact_sha256 != NORMALIZATION_SHA or sample.normalization_mu != MU
                or sample.normalization_sigma != SIGMA or int(supervised.sum()) != int(expected["imerg_valid_yunnan_count"])
                or int(((sample.y_imerg > .1) & supervised).sum()) != int(expected["imerg_rain_yunnan_count"])):
            raise ValueError("Formal QC/count/normalization changed")
        # This inherited batch scope is only the unchanged input/forward contract;
        # the process-level authority remains read-only SCOPE with hard guards.
        sample = replace(sample, execution_scope=INHERITED_SCOPE, eligibility_scope=INHERITED_SCOPE)
        detail = {"sample_id": sample.sample_id, "index": index,
            "authorization_manifest_sha256": self.authorization.manifest_sha256,
            "copy_seconds": sum(r.copy_seconds for r in staged), "read_seconds": sum(r.read_seconds for r in staged),
            "temporary_bytes_peak": max(r.temporary_bytes for r in staged), "cleanup_success": True,
            "b13_sha256": staged[0].source_sha256, "imerg_sha256": staged[1].source_sha256,
            "review_scope": SCOPE, "obs_start": observed.obs_start.isoformat(), "obs_end": observed.obs_end.isoformat(),
            "date_created": observed.date_created.isoformat() if observed.date_created else None}
        return sample, detail


def numerical_counts(output):
    q, p = output.conditional_quantiles_log, output.conditional_quantiles_physical
    return {"qlog_crossing_count": int((q[:, 1:] <= q[:, :-1]).sum()),
        "qphysical_crossing_count": int((p[:, 1:] <= p[:, :-1]).sum()),
        "nonfinite_qlog": int((~torch.isfinite(q)).sum()), "nonfinite_qphysical": int((~torch.isfinite(p)).sum()),
        "q1_support_violation": int((q[:, 0] <= math.log1p(.1)).sum())}


def probability_bin(p):
    # searchsorted on declared edges puts exact edges into the right-hand bin.
    p = np.asarray(p, dtype=np.float64)
    if not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError("Invalid occurrence probability")
    return np.minimum(np.searchsorted(np.arange(1, 10) / 10, p, side="right"), 9)


def probability_summary(frequencies):
    keys = np.array(sorted(frequencies), dtype=np.float64)
    counts = np.array([frequencies[k] for k in keys], dtype=np.int64)
    n = int(counts.sum())
    mean = float(np.dot(keys, counts) / n)
    cumulative = counts.cumsum()
    def percentile(percent):
        h = (n - 1) * percent / 100
        a, b = math.floor(h), math.ceil(h)
        av = keys[np.searchsorted(cumulative, a, side="right")]
        bv = keys[np.searchsorted(cumulative, b, side="right")]
        return float(av + (h - a) * (bv - av))
    return {"count": n, "mean": mean, "std": math.sqrt(float(np.dot((keys - mean)**2, counts) / n)),
        "std_ddof": 0, "percentile_convention": "numpy linear/type-7, exact weighted order statistics",
        **{("median" if v == 50 else "p" + str(v)): percentile(v) for v in (1, 5, 25, 50, 75, 95, 99)}}


class ReviewAccumulator:
    def __init__(self, axes, rules):
        self.axes, self.rules = axes, rules
        self.global_acc = GlobalValidationAccumulator()
        self.months = {m: GlobalValidationAccumulator() for m in range(3, 11)}
        self.scenes = {m: 0 for m in range(3, 11)}
        self.spatial = {name: np.zeros((100, 100), dtype=(np.int64 if name.endswith("count") else np.float64))
            for name in ("valid_count", "rainy_count", "probability_sum", "brier_sum", "pinball_sum", "proxy_signed_sum", "proxy_abs_sum", "proxy_squared_sum")}
        self.bins = np.zeros((10, 3), dtype=np.float64)
        self.rate = np.zeros((7, 4), dtype=np.float64)
        self.exceed = np.zeros((4, 4), dtype=np.float64)
        self.exceed_tau_sum = np.zeros((4, 32), dtype=np.float64)
        self.exceed_coverage = np.zeros((4, 32), dtype=np.int64)
        self.frequencies = {"rainy_truth": {}, "dry_truth": {}}
        self.hist = {k: np.zeros(100, dtype=np.int64) for k in self.frequencies}
        self.heaps = {k: [] for k in rules["case_rules"]}
        self.numerics = {k: 0 for k in ("qlog_crossing_count", "qphysical_crossing_count", "nonfinite_qlog", "nonfinite_qphysical", "q1_support_violation")}
        self.seen = 0

    @torch.no_grad()
    def add(self, output, batch, samples, details):
        if [d["index"] for d in details] != list(range(self.seen, self.seen + len(samples))):
            raise ValueError("Frozen Validation order changed")
        checked = numerical_counts(output)
        for k, v in checked.items():
            self.numerics[k] += v
        if any(checked.values()):
            raise FloatingPointError("STOP: quantile numerical violation " + str(checked))
        self.global_acc.add(output, batch.y_imerg, batch.imerg_valid_mask, batch.yunnan_eval_mask)
        months = np.array([s.imerg_window_start.month for s in samples])
        for m in sorted(set(months)):
            subset = torch.tensor(np.flatnonzero(months == m), device=batch.y_imerg.device)
            sub = SimpleNamespace(**{name: getattr(output, name)[subset] for name in
                ("rain_logit", "rain_prob", "conditional_quantiles_log", "conditional_quantiles_physical")})
            self.months[m].add(sub, batch.y_imerg[subset], batch.imerg_valid_mask[subset], batch.yunnan_eval_mask[subset])
            self.scenes[m] += len(subset)
        valid = (batch.imerg_valid_mask & batch.yunnan_eval_mask).squeeze(1).cpu().numpy()
        # Rain labels must be computed in production target dtype before promotion.
        rainy_all = (batch.y_imerg > .1).squeeze(1).cpu().numpy()
        rates_all = batch.y_imerg.squeeze(1).double().cpu().numpy()
        prob_all = output.rain_prob.squeeze(1).double().cpu().numpy()
        q = output.conditional_quantiles_log.movedim(1, -1).cpu().numpy()[valid]
        physical = output.conditional_quantiles_physical.movedim(1, -1).cpu().numpy()[valid]
        y, rainy, prob = rates_all[valid], rainy_all[valid], prob_all[valid]
        error = np.log1p(y[rainy])[:, None] - q[rainy]
        pinball = np.maximum(TAU * error, (TAU - 1) * error)
        cond = pinball.mean(-1)
        pervalid = np.zeros(len(y), dtype=np.float64)
        pervalid[rainy] = cond
        proxy = prob * physical.mean(-1)
        proxy_error = proxy - y
        for name, values in (("valid_count", np.ones(len(y), dtype=np.int64)), ("rainy_count", rainy),
                ("probability_sum", prob), ("brier_sum", (prob - rainy)**2), ("pinball_sum", pervalid),
                ("proxy_signed_sum", proxy_error), ("proxy_abs_sum", np.abs(proxy_error)), ("proxy_squared_sum", proxy_error**2)):
            values_grid = np.zeros(valid.shape, dtype=self.spatial[name].dtype)
            values_grid[valid] = values
            self.spatial[name] += values_grid.sum(0)
        pb = probability_bin(prob)
        self.bins[:, 0] += np.bincount(pb, minlength=10)
        self.bins[:, 1] += np.bincount(pb, weights=prob, minlength=10)
        self.bins[:, 2] += np.bincount(pb, weights=rainy, minlength=10)
        rb = np.searchsorted(RATE_UPPER, y[rainy], side="left")
        for k, values in enumerate((np.ones(int(rainy.sum())), cond, proxy_error[rainy], np.abs(proxy_error[rainy]))):
            self.rate[:, k] += np.bincount(rb, weights=values, minlength=7)
        for j, threshold in enumerate((10, 20, 30, 50)):
            selected = y[rainy] > threshold
            self.exceed[j] += [int(selected.sum()), float(cond[selected].sum()),
                float(proxy_error[rainy][selected].sum()), float(np.abs(proxy_error[rainy][selected]).sum())]
            self.exceed_tau_sum[j] += pinball[selected].sum(0)
            self.exceed_coverage[j] += (y[rainy][selected, None] <= physical[rainy][selected]).sum(0)
        for name, label in (("rainy_truth", rainy), ("dry_truth", ~rainy)):
            keys, counts = np.unique(prob[label], return_counts=True)
            for key, count in zip(keys, counts):
                self.frequencies[name][float(key)] = self.frequencies[name].get(float(key), 0) + int(count)
            self.hist[name] += np.histogram(prob[label], bins=np.arange(101)/100)[0]
        loc = np.argwhere(valid)
        flat = loc[:, 1] * 100 + loc[:, 2]
        scene = loc[:, 0] + self.seen
        for name, score, available in (("MAX_ABSOLUTE_DIAGNOSTIC_PROXY_ERROR", np.abs(proxy_error), np.ones(len(y), bool)),
                ("HIGHEST_TRUE_RAIN_RATE", y, np.ones(len(y), bool)), ("LOWEST_TRUE_RATE_AMONG_RAINY", -y, rainy)):
            selected = np.flatnonzero(available)
            selected = selected[np.lexsort((flat[selected], scene[selected], -score[selected]))[:self.rules["top_N_each"]]]
            heap = self.heaps[name]
            for at in selected:
                b, r, c = loc[at]
                case = {"rule": name, "scene_index": int(scene[at]), "sample_id": samples[b].sample_id,
                    "window_start": samples[b].imerg_window_start.isoformat(), "analysis_time": samples[b].analysis_time.isoformat(),
                    "target_row": int(r), "target_col": int(c), "lat": float(self.axes["target_lat"][r]), "lon": float(self.axes["target_lon"][c]),
                    "IMERG_rate_mm_h": float(y[at]), "p_rain": float(prob[at]),
                    "qphysical_min": float(physical[at, 0]), "qphysical_middle_pair_mean": float(physical[at, 15:17].mean()),
                    "qphysical_max": float(physical[at, -1]), "qphysical_mean_32": float(physical[at].mean()),
                    "qphysical_32_mm_h": ";".join(format(v, ".17g") for v in physical[at]),
                    "DIAGNOSTIC_PROXY_mm_h": float(proxy[at]), "proxy_error_mm_h": float(proxy_error[at]),
                    "proxy_is_exact_expected_precipitation": False}
                entry = (float(score[at]), -int(scene[at]), -int(flat[at]), case)
                if len(heap) < self.rules["top_N_each"]:
                    heapq.heappush(heap, entry)
                elif entry[:3] > heap[0][:3]:
                    heapq.heapreplace(heap, entry)
        self.seen += len(samples)

    def spatial_metrics(self, yunnan):
        n, r = self.spatial["valid_count"], self.spatial["rainy_count"]
        def divide(values, count, minimum=1):
            result = np.full((100, 100), np.nan)
            use = yunnan & (count >= minimum)
            result[use] = values[use] / count[use]
            return result
        return {"valid_count": n, "rainy_count": r, "rain_frequency": divide(r, n),
            "mean_probability": divide(self.spatial["probability_sum"], n), "brier": divide(self.spatial["brier_sum"], n),
            "conditional_pinball": divide(self.spatial["pinball_sum"], r, self.rules["spatial_conditional_pinball_min_rain_count"]),
            "DIAGNOSTIC_PROXY_bias_mm_h": divide(self.spatial["proxy_signed_sum"], n),
            "DIAGNOSTIC_PROXY_MAE_mm_h": divide(self.spatial["proxy_abs_sum"], n),
            "DIAGNOSTIC_PROXY_RMSE_mm_h": np.sqrt(divide(self.spatial["proxy_squared_sum"], n))}

    def reconcile(self):
        g = self.global_acc
        checks = {"scenes": self.seen == N_SCENES,
            "global_counts": (g.n_valid, g.n_rain) == (N_VALID, N_RAIN),
            "monthly_valid": sum(v.n_valid for v in self.months.values()) == g.n_valid,
            "monthly_rain": sum(v.n_rain for v in self.months.values()) == g.n_rain,
            "monthly_scenes": sum(self.scenes.values()) == self.seen,
            "spatial_valid": int(self.spatial["valid_count"].sum()) == g.n_valid,
            "spatial_rain": int(self.spatial["rainy_count"].sum()) == g.n_rain,
            "rate_strata": int(self.rate[:, 0].sum()) == g.n_rain,
            "probability_bins": int(self.bins[:, 0].sum()) == g.n_valid,
            "probability_bin_rain": int(self.bins[:, 2].sum()) == g.n_rain,
            "probability_frequencies": sum(sum(v.values()) for v in self.frequencies.values()) == g.n_valid,
            "probability_histogram": sum(int(v.sum()) for v in self.hist.values()) == g.n_valid,
            "numerics": not any(self.numerics.values())}
        if not all(checks.values()):
            raise ValueError("STOP: reconciliation failure " + str(checks))
        return checks
