"""Bounded B0 GPU engineering measurements. No optimizer, fitting, or checkpoints.

Each phase writes new evidence only. Run with the verified CUDA interpreter.
"""
from __future__ import annotations

import argparse
from contextlib import nullcontext
import csv
import ctypes
from dataclasses import fields
from datetime import datetime, timezone
import gc
import hashlib
import inspect
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
import threading
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "scripts")]
import numpy as np
import torch
from torch.utils.data import DataLoader, get_worker_info
from yuntapr.contracts.loader import load_contract, sha256
from yuntapr.models.b0 import B0Model
from yuntapr.losses.total_loss import b0_core_loss
from yuntapr.data.dataset_b0 import B0Dataset, B0Record
from yuntapr.data.sample_schema import HimawariFrame, utc
from yuntapr.data.masks import read_frozen_yunnan_mask
from yuntapr.spatial.sp04_mapping import load_sp04
from yuntapr.training.batch_contract import B0Batch
from audit_b0_dataloader_io import AuditDataset, PRIOR, DEVELOPMENT_PRIOR
from fit_phase_a_v1_1 import HROOT, MASK

MIB = 1024 ** 2
BASELINE = "9cb83aa493b57acbad648df5b2c257739b23045e"
STAGING = Path(r"F:\pytorch\Research\stage0_himawari\cache\staging")


def save(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False, default=str)
        stream.write("\n")


def write_csv(path, rows):
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def mean(rows, key):
    values = [float(r[key]) for r in rows if r.get(key) not in (None, "", "[N/A]")]
    return statistics.mean(values) if values else None


def safe_memory(peak_reserved, total, estimated_free, margin):
    """Both allocator and device-wide headroom must pass; no OOM is insufficient."""
    return total > 0 and peak_reserved <= (1-margin)*total and estimated_free >= margin*total


def can_advance(row):
    return row.get("status") == "PASS" and row.get("safe_15pct") is True


def epoch_arithmetic(train_batch, val_batch, train_step_seconds, val_step_seconds, epochs):
    train_steps, val_steps = math.ceil(11720/train_batch), math.ceil(11727/val_batch)
    train, val = train_steps*train_step_seconds, val_steps*val_step_seconds
    return {"train_scenes": 11720, "validation_scenes": 11727,
            "physical_batch": train_batch, "validation_batch": val_batch,
            "steps_per_epoch": train_steps, "validation_steps": val_steps,
            "train_seconds_per_epoch": train, "validation_seconds_per_epoch": val,
            "total_epoch_seconds": train+val, "epochs": epochs,
            "wall_hours": (train+val)*epochs/3600, "status": "ENGINEERING_ESTIMATE_ONLY"}


def sync():
    torch.cuda.synchronize()


def clean():
    gc.collect()
    torch.cuda.empty_cache()
    sync()


def context(mode):
    return nullcontext() if mode == "FP32" else torch.autocast("cuda", dtype={"FP16": torch.float16, "BF16": torch.bfloat16}[mode])


def model_new():
    torch.manual_seed(20260930)
    model = B0Model().cuda()
    model.raw_dtype = None
    def capture(_module, _inputs, output):
        model.raw_dtype = str(output.dtype)  # no graph retained
    model.heads.quantile.register_forward_hook(capture)
    return model


def parameter_hash(model):
    h = hashlib.sha256()
    for name, value in model.named_parameters():
        h.update(name.encode())
        h.update(value.detach().cpu().numpy().tobytes())
    return h.hexdigest()


def synthetic(batch, yunnan):
    x = torch.randn(batch, 1, 501, 501, device="cuda")
    mask = torch.from_numpy(yunnan[None, None].copy()).cuda().expand(batch, -1, -1, -1)
    return B0Batch(x, torch.ones_like(x, dtype=torch.bool), mask.float(), torch.ones_like(mask), mask)


def to_cuda(batch):
    for f in fields(batch):
        value = getattr(batch, f.name)
        if isinstance(value, torch.Tensor):
            setattr(batch, f.name, value.cuda())
    sync()
    return batch


def numerical_checks(model, output, loss, backward):
    tensors = [getattr(output, f.name) for f in fields(output)
               if isinstance(getattr(output, f.name), torch.Tensor)]
    grad = [p.grad for p in model.parameters() if p.requires_grad]
    result = {"outputs_finite": all(bool(torch.isfinite(t).all()) for t in tensors),
              "loss_finite": bool(torch.isfinite(loss.total)),
              "gradients_finite": all(g is not None and bool(torch.isfinite(g).all()) for g in grad) if backward else None,
              "qlog_strict": bool((output.conditional_quantiles_log[:, 1:] > output.conditional_quantiles_log[:, :-1]).all()),
              "parameter_dtype": ",".join(sorted({str(p.dtype) for p in model.parameters()})),
              "raw_quantile_dtype": model.raw_dtype,
              "qlog_dtype": str(output.conditional_quantiles_log.dtype),
              "qphysical_dtype": str(output.conditional_quantiles_physical.dtype),
              "conditional_pinball_dtype": str(loss.conditional_quantile.dtype),
              "valid_yunnan_pixels": loss.valid_supervised_count,
              "loss": float(loss.total.detach())}
    result["pass"] = (result["outputs_finite"] and result["loss_finite"] and result["qlog_strict"]
        and (not backward or result["gradients_finite"])
        and result["parameter_dtype"] == result["raw_quantile_dtype"] == "torch.float32"
        and result["qlog_dtype"] == result["qphysical_dtype"] == result["conditional_pinball_dtype"] == "torch.float64")
    return result


def step(model, batch, mode, cfg, backward=True, formal=False):
    model.zero_grad(set_to_none=True)
    sync()
    start = time.perf_counter()
    with context(mode), (nullcontext() if backward else torch.no_grad()):
        if formal:
            batch.validate_formal()  # same validation sequence as formal_rules_engineering_forward_step
            output = model.forward_formal(batch)
        else:
            output = model(batch.x_b13, batch.b13_valid_mask)
        sync()
        fwd = time.perf_counter()
        loss = b0_core_loss(output, batch.y_imerg, batch.imerg_valid_mask, batch.yunnan_eval_mask,
                           focal_alpha=.25, focal_gamma=2., quantile_axis_reduction=cfg["loss"]["quantile_axis_reduction"])
        sync()
        loss_end = time.perf_counter()
    if backward:
        loss.total.backward()
        sync()
    end = time.perf_counter()
    checks = numerical_checks(model, output, loss, backward)
    check_end = time.perf_counter()
    result = {"forward_ms": (fwd-start)*1000, "loss_ms": (loss_end-fwd)*1000,
              "backward_ms": (end-loss_end)*1000, "total_ms": (end-start)*1000,
              "checks_ms": (check_end-end)*1000, "samples_per_second": batch.x_b13.shape[0]/(end-start),
              **checks}
    return result


def benchmark_case(batch_size, mode, yunnan, cfg, backward=True):
    clean()
    free_before, total = torch.cuda.mem_get_info()
    reserve_before = torch.cuda.memory_reserved()
    torch.cuda.reset_peak_memory_stats()
    model = batch = None
    rows = []
    result = {"batch": batch_size, "mode": mode, "backward": backward,
              "warmup_required": 2, "measured_required": 5, "status": "NOT_RUN"}
    try:
        model = model_new().train(backward)
        before_hash = parameter_hash(model)
        batch = synthetic(batch_size, yunnan)
        for i in range(7):
            row = {"iteration": i, "warmup": i < 2, **step(model, batch, mode, cfg, backward)}
            rows.append(row)
            if not row["pass"]:
                raise FloatingPointError("Finite/dtype/strict-quantile regression failed")
        result["parameters_unchanged"] = parameter_hash(model) == before_hash
        result["status"] = "PASS" if result["parameters_unchanged"] else "PARAMETER_CHANGED"
    except torch.cuda.OutOfMemoryError as exc:
        result.update(status="OOM", error=str(exc))
    except Exception as exc:
        result.update(status="ERROR", error=repr(exc))
    finally:
        peak_alloc, peak_reserved = torch.cuda.max_memory_allocated(), torch.cuda.max_memory_reserved()
        free_after, _ = torch.cuda.mem_get_info()
        estimated_free = min(free_after, free_before-max(0, peak_reserved-reserve_before))
        result.update(peak_allocated_MiB=peak_alloc/MIB, peak_reserved_MiB=peak_reserved/MIB,
                      total_VRAM_MiB=total/MIB, reserved_fraction=peak_reserved/total,
                      free_before_MiB=free_before/MIB, estimated_min_device_free_MiB=estimated_free/MIB,
                      safe_15pct=result["status"] == "PASS" and safe_memory(peak_reserved, total, estimated_free, .15),
                      recommended_20pct=result["status"] == "PASS" and safe_memory(peak_reserved, total, estimated_free, .20),
                      warmup_completed=sum(r["warmup"] for r in rows), measured_completed=sum(not r["warmup"] for r in rows))
        measured = [r for r in rows if not r["warmup"]]
        if measured:
            result.update({k: mean(measured, k) for k in ("forward_ms", "loss_ms", "backward_ms", "total_ms", "checks_ms")})
            result["samples_per_second"] = batch_size*1000/result["total_ms"]
        if model is not None:
            model.zero_grad(set_to_none=True)
        del batch, model
        clean()
    print(json.dumps(result), flush=True)
    return result, rows


def compute(out):
    science, cfg = load_contract()
    mapping = load_sp04()
    yunnan = read_frozen_yunnan_mask(MASK, mapping)
    save(out/"environment.json", {"baseline": BASELINE, "python": sys.executable,
         "torch": torch.__version__, "cuda_runtime": torch.version.cuda,
         "gpu": torch.cuda.get_device_name(), "capability": torch.cuda.get_device_capability(),
         "science_schema": science["schema_version"], "engineering_schema": cfg["schema_version"],
         "threads": torch.get_num_threads(), "fp32_matmul_precision": torch.get_float32_matmul_precision(),
         "cudnn_benchmark": torch.backends.cudnn.benchmark,
         "autocast_note": "No GradScaler and no optimizer; gradients checked unscaled. Finite benchmark is not convergence evidence.",
         "headroom_method": "Both allocator reservation and estimated device-wide free VRAM; min(post-case free, pre-case free minus incremental peak reservation). Other applications remain active.",
         "focal_parameters": {"alpha": .25, "gamma": 2., "scope": "ENGINEERING_TEST_ONLY"}})
    training, raw = [], []
    for batch in (1, 2, 4, 8):
        row, iterations = benchmark_case(batch, "FP32", yunnan, cfg)
        training.append(row)
        raw.extend({"phase": "train", "batch": batch, "mode": "FP32", **r} for r in iterations)
        if not can_advance(row):
            break
    write_csv(out/"gpu_batch_benchmark.csv", training)
    safe = [r for r in training if r["recommended_20pct"]]
    if not safe:
        save(out/"compute_iterations.json", raw)
        raise RuntimeError("No FP32 batch with 20 percent device headroom; stop and review")
    chosen_batch = max(r["batch"] for r in safe)
    amp = []
    for mode in ("FP32", "FP16", "BF16"):
        row, iterations = benchmark_case(chosen_batch, mode, yunnan, cfg)
        amp.append(row)
        raw.extend({"phase": "amp", "batch": chosen_batch, "mode": mode, **r} for r in iterations)
    write_csv(out/"gpu_amp_benchmark.csv", amp)
    candidates = [r for r in amp if r["recommended_20pct"]]
    chosen = min(candidates, key=lambda r: r["total_ms"])
    validation = []
    for batch in (1, 2, 4, 8, 16):
        row, iterations = benchmark_case(batch, chosen["mode"], yunnan, cfg, backward=False)
        validation.append(row)
        raw.extend({"phase": "validation", "batch": batch, "mode": chosen["mode"], **r} for r in iterations)
        if not can_advance(row):
            break
    write_csv(out/"gpu_validation_benchmark.csv", validation)
    save(out/"compute_iterations.json", raw)
    val_safe = [r for r in validation if r["recommended_20pct"]]
    if not val_safe:
        raise RuntimeError("No safe validation configuration")
    val_chosen = max(val_safe, key=lambda r: r["samples_per_second"])
    decision = {"MAX_TESTED_SAFE_BATCH": max(r["batch"] for r in training if r["safe_15pct"]),
                "MAX_COMPLETED_BATCH": max(r["batch"] for r in training if r["status"] == "PASS"),
                "RECOMMENDED_SAFE_PHYSICAL_BATCH": chosen_batch,
                "AMP_FP16_FEASIBLE": amp[1]["status"] == "PASS", "AMP_BF16_FEASIBLE": amp[2]["status"] == "PASS",
                "RECOMMENDED_AMP_MODE": chosen["mode"], "RECOMMENDED_VALIDATION_BATCH": val_chosen["batch"],
                "scope": "ENGINEERING_RECOMMENDATION_ONLY", "training_batch_sweep_mode": "FP32",
                "larger_batches_not_run": [b for b in (1, 2, 4, 8) if b not in [r["batch"] for r in training]],
                "chosen_training_measurement": chosen, "chosen_validation_measurement": val_chosen}
    save(out/"compute_recommendation.json", decision)


GPU_FIELDS = ("timestamp", "utilization.gpu", "memory.used", "memory.total", "temperature.gpu", "power.draw",
              "clocks.current.graphics", "clocks.current.sm", "clocks.current.memory",
              "clocks_event_reasons.hw_thermal_slowdown", "clocks_event_reasons.sw_thermal_slowdown",
              "clocks_event_reasons.sw_power_cap")


def cpu_times():
    idle, kernel, user = ctypes.c_ulonglong(), ctypes.c_ulonglong(), ctypes.c_ulonglong()
    if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
        raise OSError("GetSystemTimes failed")
    return idle.value, kernel.value+user.value


class Telemetry:
    def __init__(self):
        self.rows, self.errors = [], []
        self.stop_event = threading.Event()

    def sample(self):
        result = subprocess.run(["nvidia-smi", "--query-gpu="+",".join(GPU_FIELDS), "--format=csv,noheader,nounits"],
                                capture_output=True, text=True, timeout=8, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:
            raise RuntimeError(result.stderr)
        row = dict(zip(GPU_FIELDS, next(csv.reader([result.stdout.strip()]))))
        row = {k: v.strip() for k, v in row.items()}
        row["monotonic_seconds"] = time.perf_counter()
        new_cpu = cpu_times()
        old_cpu = self.last_cpu
        delta = new_cpu[1]-old_cpu[1]
        row["cpu_utilization_percent"] = 100*(1-(new_cpu[0]-old_cpu[0])/delta) if delta > 0 else None
        self.last_cpu = new_cpu
        self.rows.append(row)

    def loop(self):
        while not self.stop_event.is_set():
            try:
                self.sample()
            except Exception as exc:
                self.errors.append(repr(exc))
            self.stop_event.wait(1.)

    def __enter__(self):
        self.last_cpu = cpu_times()
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop_event.set()
        self.thread.join(timeout=10)

    def summary(self):
        return {"telemetry_samples": len(self.rows), "telemetry_errors": self.errors,
                "GPU_utilization_percent": mean(self.rows, "utilization.gpu"),
                "CPU_utilization_percent": mean(self.rows, "cpu_utilization_percent"),
                "thermal_throttle_detected": any(r[k] == "Active" for r in self.rows for k in GPU_FIELDS[9:11]),
                "power_cap_active_samples": sum(r[GPU_FIELDS[11]] == "Active" for r in self.rows),
                "max_temperature_C": max((float(r["temperature.gpu"]) for r in self.rows), default=None),
                "max_device_memory_MiB": max((float(r["memory.used"]) for r in self.rows), default=None),
                "mean_power_W": mean(self.rows, "power.draw"),
                "mean_graphics_clock_MHz": mean(self.rows, "clocks.current.graphics")}


def pinned_candidates(count=32):
    manifest = read_json(PRIOR/"manifest.json")
    for name in ("normalization_phaseA_sample_manifest.csv", "formal_sample_eligibility_2023_2024.csv",
                 "imerg_development_revalidation.json", "real_normalized_forward_smoke.json"):
        if sha256(PRIOR/name) != manifest["public_files_sha256"][name]:
            raise ValueError("Pinned prior evidence changed: "+name)
    prior_manifest = DEVELOPMENT_PRIOR/"manifest.json"
    if sha256(prior_manifest) != manifest["prior_development_manifest_sha256"]:
        raise ValueError("Prior development manifest changed")
    frame_info = read_json(prior_manifest)["local_evidence"]["b13_per_frame.csv"]
    frame_path = Path(frame_info["local_path"])
    if sha256(frame_path) != frame_info["sha256"]:
        raise ValueError("Pinned per-frame evidence changed")
    frames = {r["relative_path"]: r for r in read_csv(frame_path) if r["relative_path"]}
    candidates = read_csv(PRIOR/"normalization_phaseA_sample_manifest.csv")
    pairs = {r["window_start"]: r for r in read_csv(PRIOR/"formal_sample_eligibility_2023_2024.csv")}
    day_hash = {r["day_path"]: r["sha256"] for r in read_json(PRIOR/"imerg_development_revalidation.json")["days"]}
    records, hashes, selected = [], [], []
    for i in np.linspace(0, len(candidates)-1, count, dtype=np.int64):
        row = candidates[int(i)]
        pair, frame = pairs[row["window_start"]], frames[row["b13_relative_path"]]
        if not pair["month"].startswith("2023") or pair["formal_supervised_eligible"] != "True":
            raise ValueError("Only eligible 2023 Train records allowed in loader")
        source, target = HROOT/row["b13_relative_path"], Path(pair["imerg_day_path"])
        record = B0Record(row["sample_id"], utc(row["window_start"]),
                          (HimawariFrame(source, utc(frame["nominal"]), utc(frame["obs_start"]), utc(frame["obs_end"]), utc(frame["date_created"])),),
                          target, int(pair["imerg_index"]), "IMERG", "V07", "Final", True)
        records.append(record)
        hashes.append({"b13": row["source_sha256"], "imerg": day_hash[str(target)]})
        selected.append({"sample_id": row["sample_id"], "window_start": row["window_start"],
                         "source_path": str(source), "target_path": str(target), **hashes[-1]})
    if len({r.sample_id for r in records}) != count:
        raise ValueError("Unique sample count mismatch")
    regression, reg_hashes = [], []
    for old in read_json(PRIOR/"real_normalized_forward_smoke.json")["samples"]:
        if old["category"] not in ("FULL_VALID_2023", "FULL_VALID_2024"):
            continue
        pair = pairs[old["window_start"]]
        source = HROOT/pair["selected_b13_relative_path"]
        regression.append(B0Record(old["category"], utc(old["window_start"]),
                          (HimawariFrame(source, utc(old["selected_nominal"]), utc(old["obs_start"]), utc(old["obs_end"]), utc(old["date_created"])),),
                          Path(pair["imerg_day_path"]), int(pair["imerg_index"]), "IMERG", "V07", "Final", True))
        reg_hashes.append({"b13": old["source_sha256"], "imerg": old["target_sha256"]})
    if len(regression) != 2:
        raise ValueError("Two real regression samples required")
    return records, hashes, selected, regression, reg_hashes


class RealDataset(AuditDataset):
    """Use existing formal reader/QC; return the sample, never bypass QC for speed."""
    def __getitem__(self, index):
        start = time.perf_counter()
        sample = self.dataset[index]
        elapsed = time.perf_counter()-start
        reader = {"b13": dict(self.b13.last), "imerg": dict(self.imerg.last)}
        for kind, evidence in reader.items():
            if (evidence["source_sha256"] != self.expected_hashes[index][kind]
                    or not evidence["sha256_match"] or not evidence["cleanup_success"]
                    or evidence["owned_copy_count_after"]):
                raise ValueError("Source SHA/staging/cleanup failed: "+kind)
        if not sample.formal_supervised_qc_pass or not sample.b13_full_valid or sample.used_older_causal_frame:
            raise ValueError("Formal sample QC failed")
        detail = {"sample_id": sample.sample_id, "year": sample.imerg_window_start.year,
                  "worker_id": get_worker_info().id if get_worker_info() else "main",
                  "staging_root": str(self.staging.root), "sample_seconds": elapsed,
                  "normalization_seconds": self.normalizer.last_seconds,
                  "reader_seconds": sum(r["total_reader_seconds"] for r in reader.values()),
                  "copy_seconds": sum(r["copy_seconds"] for r in reader.values()),
                  "formal_assembly_seconds": elapsed-sum(r["total_reader_seconds"] for r in reader.values())-self.normalizer.last_seconds,
                  "readers": reader}
        return sample, detail


def worker_init(worker_id):
    dataset = get_worker_info().dataset
    torch.set_num_threads(1)
    dataset.set_staging(f"worker_{worker_id}")


def list_collate(items):
    return items


def dataset_new(records, hashes, out, suffix):
    _, cfg = load_contract()
    mapping = load_sp04()
    yunnan = read_frozen_yunnan_mask(MASK, mapping)
    return RealDataset(records, hashes, mapping, yunnan, STAGING/f"gpu_{out.name}"/suffix,
                       cfg["staging"]["max_temporary_bytes"])


def real(out):
    _, cfg = load_contract()
    rec = read_json(out/"compute_recommendation.json")
    _, _, _, records, hashes = pinned_candidates()
    dataset = dataset_new(records, hashes, out, "regression")
    rows = []
    model = model_new().train()
    before = parameter_hash(model)
    for i, record in enumerate(records):
        sample, evidence = dataset[i]
        batch = to_cuda(B0Batch.from_formal_samples([sample]))
        result = step(model, batch, rec["RECOMMENDED_AMP_MODE"], cfg, formal=True)
        frame = record.frames[0]
        rows.append({"category": record.sample_id, "window_start": str(record.imerg_window_start),
                     "analysis_time": str(sample.analysis_time), "nominal_time": str(frame.nominal_time),
                     "obs_start": str(frame.obs_start), "obs_end": str(frame.obs_end), "date_created": str(frame.date_created),
                     "causality_pass": frame.obs_end <= sample.analysis_time, "formal_qc_pass": sample.formal_supervised_qc_pass,
                     "normalization_sha256": sample.normalization_artifact_sha256, "evidence": evidence, **result})
        del batch, sample
        if not result["pass"]:
            break
    unchanged = before == parameter_hash(model)
    passed = len(rows) == 2 and all(r["pass"] for r in rows) and unchanged
    save(out/"real_cuda_regression.json", {"status": "PASS" if passed else "FAIL", "mode": rec["RECOMMENDED_AMP_MODE"],
         "parameters_unchanged": unchanged, "optimizer_step_performed": False, "samples": rows})
    print("REAL_CUDA_REGRESSION="+str(passed), flush=True)
    if not passed:
        raise RuntimeError("Real CUDA regression failed")


def loader(out):
    if read_json(out/"real_cuda_regression.json")["status"] != "PASS":
        raise RuntimeError("Real regression must pass first")
    _, cfg = load_contract()
    rec = read_json(out/"compute_recommendation.json")
    records, hashes, selected, _, _ = pinned_candidates()
    save(out/"selected_32_real_samples.json", selected)
    summaries, all_detail, batch_rows, telemetry_rows = [], [], [], []
    for workers in (0, 2, 4):
        clean()
        model = model_new().train()
        before = parameter_hash(model)
        dataset = dataset_new(records, hashes, out, f"loader_{workers}")
        options = {"prefetch_factor": 1} if workers else {}
        data_loader = DataLoader(dataset, batch_size=rec["RECOMMENDED_SAFE_PHYSICAL_BATCH"], shuffle=False,
                                 num_workers=workers, collate_fn=list_collate, worker_init_fn=worker_init if workers else None,
                                 persistent_workers=False, pin_memory=False, **options)
        completed, error, rows = 0, None, []
        iterator = None
        start = time.perf_counter()
        with Telemetry() as telemetry:
            try:
                spawn_start = time.perf_counter()
                iterator = iter(data_loader)
                iterator_creation = time.perf_counter()-spawn_start
                while True:
                    wait_start = time.perf_counter()
                    try:
                        items = next(iterator)
                    except StopIteration:
                        break
                    received = time.perf_counter()
                    batch = B0Batch.from_formal_samples([item[0] for item in items])
                    assembled = time.perf_counter()
                    batch = to_cuda(batch)
                    transferred = time.perf_counter()
                    result = step(model, batch, rec["RECOMMENDED_AMP_MODE"], cfg, formal=True)
                    row = {"num_workers": workers, "batch_index": len(rows), "samples": len(items),
                           "data_wait_ms": (received-wait_start)*1000, "batch_assembly_ms": (assembled-received)*1000,
                           "host_to_device_ms": (transferred-assembled)*1000, "GPU_step_ms": result["total_ms"],
                           "checks_ms": result["checks_ms"], "pass": result["pass"]}
                    rows.append(row)
                    all_detail.extend({"num_workers": workers, **item[1]} for item in items)
                    completed += len(items)
                    del batch, items
                    if not result["pass"]:
                        raise FloatingPointError("Coupled real finite/dtype check failed")
            except Exception as exc:
                error = repr(exc)
            finally:
                del iterator, data_loader
        wall = time.perf_counter()-start
        unchanged = before == parameter_hash(model)
        leftovers = list(dataset.base_staging.rglob("yuntapr_b0_*.nc"))
        passed = completed == 32 and error is None and unchanged and not leftovers
        details = [r for r in all_detail if r["num_workers"] == workers]
        summary = {"num_workers": workers, "status": "PASS" if passed else "ERROR", "error": error,
                   "physical_batch": rec["RECOMMENDED_SAFE_PHYSICAL_BATCH"], "mode": rec["RECOMMENDED_AMP_MODE"],
                   "samples_completed": completed, "data_wait_ms": mean(rows, "data_wait_ms"),
                   "GPU_step_ms": mean(rows, "GPU_step_ms"), "batch_assembly_ms": mean(rows, "batch_assembly_ms"),
                   "host_to_device_ms": mean(rows, "host_to_device_ms"), "wall_time_seconds": wall,
                   "samples_per_second": completed/wall, "iterator_creation_seconds": iterator_creation,
                   "mean_sample_reader_seconds": mean(details, "reader_seconds"),
                   "mean_sample_assembly_seconds": mean(details, "formal_assembly_seconds"),
                   "parameters_unchanged": unchanged, "staging_copies_remaining": len(leftovers),
                   **telemetry.summary()}
        summaries.append(summary)
        batch_rows.extend(rows)
        telemetry_rows.extend({"num_workers": workers, **r} for r in telemetry.rows)
        print(json.dumps(summary), flush=True)
        del dataset, model
        clean()
        if not passed:
            break
    write_csv(out/"dataloader_gpu_benchmark.csv", summaries)
    write_csv(out/"dataloader_gpu_batches.csv", batch_rows)
    write_csv(out/"dataloader_gpu_telemetry.csv", telemetry_rows)
    save(out/"dataloader_real_sample_evidence.json", all_detail)
    if len(summaries) != 3 or any(r["status"] != "PASS" for r in summaries):
        raise RuntimeError("DataLoader coupled benchmark failed; evidence preserved")


class AssemblyTracer:
    """Exclusive categories at selected production frames; inline calls timed inclusively.

    Nested reader/normalizer calls are assigned to their call site. Instrumentation
    is audit-only, no source edits or alternative calculation paths.
    """
    def __init__(self):
        self.target = B0Dataset.__getitem__.__code__
        lines, first = inspect.getsourcelines(B0Dataset.__getitem__)
        self.labels = {}
        constructing = False
        for number, line in enumerate(lines, first):
            text = line.strip()
            if text.startswith("return B0Sample("):
                constructing = True
            if constructing:
                label = "sample_construction"
            elif any(s in text for s in ("self.b13_reader(", "self.imerg_reader(")):
                label = "reader_copy_io_integrity_qc"
            elif "self.normalizer.transform(" in text:
                label = "normalization"
            elif any(text.startswith(s) for s in ("native_mask =", "members =", "support =")):
                label = "sp04_support_mapping"
            elif any(s in text for s in ("target_valid & self.yunnan_mask", "supervised = bool", "formal_qc = bool")):
                label = "mask_assembly_and_eligibility"
            else:
                label = "other_python_and_formal_qc"
            self.labels[number] = label
        self.times, self.line_times = {}, {}
        self.previous = None
        self.last_time = None

    def trace(self, frame, event, _arg):
        if frame.f_code != self.target:
            return None
        now = time.perf_counter()
        if event in ("line", "return"):
            if self.previous is not None:
                elapsed = now-self.last_time
                label = self.labels[self.previous]
                self.times[label] = self.times.get(label, 0.)+elapsed
                self.line_times[self.previous] = self.line_times.get(self.previous, 0.)+elapsed
            self.previous = frame.f_lineno if event == "line" else None
            self.last_time = now
        return self.trace


def profile(out):
    import cProfile
    import pstats
    records, hashes, _, _, _ = pinned_candidates()
    dataset = dataset_new(records[:4], hashes[:4], out, "profile")
    rows, functions = [], []
    for i in range(4):
        tracer = AssemblyTracer()
        sys.settrace(tracer.trace)
        try:
            sample, detail = dataset[i]
        finally:
            sys.settrace(None)
        profiler = cProfile.Profile()
        profiler.enable()
        start = time.perf_counter()
        batch = B0Batch.from_formal_samples([sample])
        batch_seconds = time.perf_counter()-start
        profiler.disable()
        stats = pstats.Stats(profiler)
        numpy_tensor, mask_numpy_tensor = 0., 0.
        for (filename, line, name), (cc, nc, tt, ct, _callers) in stats.stats.items():
            functions.append({"sample": i, "file": filename, "line": line, "function": name,
                              "calls": nc, "self_seconds": tt, "inclusive_seconds": ct})
            if filename.endswith("batch_contract.py") and name == "tensor":
                numpy_tensor += ct  # stacking/copy + from_numpy for all five arrays
        # A separate exact expression measures mask tensor assembly, not added to batch total.
        t = time.perf_counter()
        for name in ("b13_valid_mask", "imerg_valid_mask", "yunnan_eval_mask"):
            torch.from_numpy(np.stack([getattr(sample, name)])[:, None].copy())
        mask_numpy_tensor = time.perf_counter()-t
        rows.append({"sample_id": sample.sample_id, "dataset_exclusive_categories_seconds": tracer.times,
                     "dataset_line_times_seconds": tracer.line_times,
                     "batch_construction_seconds": batch_seconds, "numpy_to_torch_inclusive_seconds": numpy_tensor,
                     "batch_validation_and_other_seconds": max(0., batch_seconds-numpy_tensor),
                     "mask_tensor_assembly_separate_probe_seconds": mask_numpy_tensor,
                     "reader_detail": detail})
        del batch, sample
    all_labels = set(k for r in rows for k in r["dataset_exclusive_categories_seconds"])
    means = {k: statistics.mean(r["dataset_exclusive_categories_seconds"].get(k, 0.) for r in rows) for k in sorted(all_labels)}
    top = sorted(functions, key=lambda r: r["inclusive_seconds"], reverse=True)[:30]
    save(out/"formal_assembly_profile.json", {"sample_count": 4, "status": "PASS", "mean_dataset_categories_seconds": means,
         "mean_batch_construction_seconds": mean(rows, "batch_construction_seconds"),
         "mean_numpy_to_torch_seconds": mean(rows, "numpy_to_torch_inclusive_seconds"),
         "mean_batch_validation_seconds": mean(rows, "batch_validation_and_other_seconds"),
         "mean_mask_tensor_separate_probe_seconds": mean(rows, "mask_tensor_assembly_separate_probe_seconds"),
         "method": "Targeted dataset line trace with inclusive call-site timing; cProfile of unchanged B0Batch construction. Categories are exclusive only within dataset. Separate mask probe overlaps conversion category and must not be added. Instrumentation overhead included; compare uninstrumented DataLoader evidence.",
         "source_sha256": {"dataset_b0.py": sha256(ROOT/"src/yuntapr/data/dataset_b0.py"),
                           "batch_contract.py": sha256(ROOT/"src/yuntapr/training/batch_contract.py")},
         "rows": rows, "top_batch_functions": top, "production_refactored": False})
    print(json.dumps(means), flush=True)


def driver_events(since):
    script = ("$ErrorActionPreference='Stop'; try { "
              "$events=@(Get-WinEvent -FilterHashtable @{LogName='System'; StartTime=[datetime]'"+since+
              "'} -ErrorAction Stop | Where-Object { $_.Id -eq 4101 -or $_.ProviderName -match 'nvlddmkm' } | "
              "Select-Object TimeCreated,Id,ProviderName,LevelDisplayName,Message); "
              "@{status='QUERIED';events=$events} | ConvertTo-Json -Depth 5 } catch { "
              "if ($_.FullyQualifiedErrorId -match 'NoMatchingEventsFound') { "
              "@{status='QUERIED';events=@()} | ConvertTo-Json -Depth 5 } else { "
              "@{status='UNAVAILABLE';error=$_.Exception.Message} | ConvertTo-Json -Depth 5 } }")
    result = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=25, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        return json.loads(result.stdout)
    except Exception:
        return {"status": "UNAVAILABLE", "error": result.stderr[:2000]}


def stability(out):
    if read_json(out/"real_cuda_regression.json")["status"] != "PASS":
        raise RuntimeError("Real regression must pass before stability")
    _, cfg = load_contract()
    rec = read_json(out/"compute_recommendation.json")
    clean()
    model = model_new().train()
    before = parameter_hash(model)
    mapping = load_sp04()
    batch = synthetic(rec["RECOMMENDED_SAFE_PHYSICAL_BATCH"], read_frozen_yunnan_mask(MASK, mapping))
    for _ in range(2):
        if not step(model, batch, rec["RECOMMENDED_AMP_MODE"], cfg)["pass"]:
            raise RuntimeError("Stability warmup failed")
    torch.cuda.reset_peak_memory_stats()
    started_utc = datetime.now(timezone.utc).isoformat()
    rows, errors = [], []
    start = time.perf_counter()
    with Telemetry() as telemetry:
        try:
            while time.perf_counter()-start < 180.:
                row = step(model, batch, rec["RECOMMENDED_AMP_MODE"], cfg)
                rows.append(row)
                if not row["pass"]:
                    raise FloatingPointError("Stability numerical check failed")
        except Exception as exc:
            errors.append(repr(exc))
    elapsed = time.perf_counter()-start
    events = driver_events(started_utc)
    summary = telemetry.summary()
    unchanged = before == parameter_hash(model)
    reset = any(e.get("Id") == 4101 for e in events.get("events", []))
    passed = elapsed >= 180 and bool(rows) and not errors and unchanged and not summary["thermal_throttle_detected"] and not reset
    save(out/"gpu_stability_smoke.json", {"status": "PASS" if passed else "FAIL", "duration_seconds": elapsed,
         "requested_seconds": 180, "started_utc": started_utc, "batch": rec["RECOMMENDED_SAFE_PHYSICAL_BATCH"],
         "mode": rec["RECOMMENDED_AMP_MODE"], "iterations": len(rows), "all_finite_and_dtype_pass": all(r["pass"] for r in rows),
         "peak_allocated_MiB": torch.cuda.max_memory_allocated()/MIB,
         "peak_reserved_MiB": torch.cuda.max_memory_reserved()/MIB,
         "mean_step_ms": mean(rows, "total_ms"), "samples_per_second_including_checks": len(rows)*batch.x_b13.shape[0]/elapsed,
         "CUDA_errors": errors, "driver_reset_detected": reset if events["status"] == "QUERIED" else None,
         "driver_event_query": events, "parameters_unchanged": unchanged,
         "parameter_sha256_before": before, "parameter_sha256_after": parameter_hash(model),
         "optimizer_step_performed": False, "checkpoint_generated": False, **summary})
    write_csv(out/"gpu_stability_telemetry.csv", telemetry.rows)
    write_csv(out/"gpu_stability_iterations.csv", rows)
    print("GPU_STABILITY_PASS="+str(passed), flush=True)
    if not passed:
        raise RuntimeError("Stability failed; review recorded evidence")


def tests(out):
    import io
    import unittest
    suites = ("scientific_freeze", "b0_skeleton", "development_qc", "scientific_freeze_v1_1",
              "quantile_numerical_closure", "training_environment_audit", "gpu_training_feasibility")
    results = []
    with (out/"test_results.txt").open("x", encoding="utf-8", newline="\n") as log:
        for directory in suites:
            log.write("\nSUITE: "+directory+"\n")
            suite = unittest.TestLoader().discover(str(ROOT/"tests"/directory))
            result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
            results.append({"suite": directory, "tests": result.testsRun,
                            "failures": len(result.failures), "errors": len(result.errors),
                            "skipped": len(result.skipped), "pass": result.wasSuccessful() and not result.skipped})
            log.flush()
            print(json.dumps(results[-1]), flush=True)
            if not results[-1]["pass"]:
                break
    save(out/"test_summary.json", results)
    if len(results) != len(suites) or not all(r["pass"] for r in results):
        raise RuntimeError("Automated suite failed; inspect preserved log")


def finalize(out):
    rec = read_json(out/"compute_recommendation.json")
    real_result = read_json(out/"real_cuda_regression.json")
    stability_result = read_json(out/"gpu_stability_smoke.json")
    prof = read_json(out/"formal_assembly_profile.json")
    test_result = read_json(out/"test_summary.json")
    loader_rows = read_csv(out/"dataloader_gpu_benchmark.csv")
    batches = read_csv(out/"dataloader_gpu_batches.csv")
    iterations = read_json(out/"compute_iterations.json")
    detail = read_json(out/"dataloader_real_sample_evidence.json")
    checks = {
        "all_compute_iterations_finite_strict_and_precision_valid": bool(iterations) and all(r["pass"] for r in iterations),
        "two_warmup_five_measured_every_completed_case": all(
            int(r["warmup_completed"]) == 2 and int(r["measured_completed"]) >= 5
            for name in ("gpu_batch_benchmark.csv", "gpu_amp_benchmark.csv", "gpu_validation_benchmark.csv")
            for r in read_csv(out/name) if r["status"] == "PASS"),
        "all_three_worker_settings_completed_32": {int(r["num_workers"]) for r in loader_rows} == {0, 2, 4}
            and all(r["status"] == "PASS" and int(r["samples_completed"]) == 32 for r in loader_rows),
        "each_worker_setting_has_32_unique_2023_samples": all(
            len({r["sample_id"] for r in detail if r["num_workers"] == w and r["year"] == 2023}) == 32 for w in (0, 2, 4)),
        "all_staging_hashes_and_cleanup_verified": all(
            v["sha256_match"] and v["cleanup_success"] and v["owned_copy_count_after"] == 0
            for r in detail for v in r["readers"].values()),
        "real_regression_both_years_and_yunnan_pixels": {r["evidence"]["year"] for r in real_result["samples"]} == {2023, 2024}
            and all(r["pass"] and r["valid_yunnan_pixels"] == 3430 for r in real_result["samples"]),
        "stability_duration_at_least_180_seconds": stability_result["duration_seconds"] >= 180,
        "stability_did_not_update_parameters": stability_result["parameters_unchanged"],
    }
    save(out/"artifact_validation.json", checks)
    if not all(checks.values()):
        raise RuntimeError("Evidence completeness validation failed")
    worker_comparison = []
    for row in loader_rows:
        workers = int(row["num_workers"])
        rows = [b for b in batches if int(b["num_workers"]) == workers]
        active = sum(sum(float(r[k]) for k in ("data_wait_ms", "batch_assembly_ms", "host_to_device_ms", "GPU_step_ms", "checks_ms")) for r in rows)/1000
        worker_comparison.append({"workers": workers, "samples": int(row["samples_completed"]),
             "active_seconds_sum": active, "active_samples_per_second": int(row["samples_completed"])/active,
             "full_wall_samples_per_second": float(row["samples_per_second"]),
             "startup_and_shutdown_seconds": float(row["wall_time_seconds"])-active,
             "data_wait_fraction": sum(float(r["data_wait_ms"]) for r in rows)/(active*1000),
             "gpu_step_fraction": sum(float(r["GPU_step_ms"]) for r in rows)/(active*1000)})
    best_rate = max(r["active_samples_per_second"] for r in worker_comparison)
    # Prefer fewer workers when active rates differ by no more than five percent.
    preferred = min((r for r in worker_comparison if r["active_samples_per_second"] >= .95*best_rate), key=lambda r: r["workers"])
    worker_count = preferred["workers"]
    selected_loader = next(r for r in loader_rows if int(r["num_workers"]) == worker_count)
    selected_batches = [r for r in batches if int(r["num_workers"]) == worker_count]
    batch_size = rec["RECOMMENDED_SAFE_PHYSICAL_BATCH"]
    val_batch = rec["RECOMMENDED_VALIDATION_BATCH"]
    train_gpu = rec["chosen_training_measurement"]["total_ms"]/1000
    val_gpu = rec["chosen_validation_measurement"]["total_ms"]/1000
    active_step = preferred["active_seconds_sum"]/len(selected_batches)
    # Validation I/O was not directly benchmarked: explicit conservative additive proxy.
    preprocessing_per_sample = (float(selected_loader["mean_sample_reader_seconds"])
                               +float(selected_loader["mean_sample_assembly_seconds"]))
    val_proxy_step = val_gpu+val_batch*preprocessing_per_sample
    estimates = []
    for epochs in (1, 10, 30, 50):
        compute_row = epoch_arithmetic(batch_size, val_batch, train_gpu, val_gpu, epochs)
        compute_row.update(scenario="GPU_COMPUTE_ONLY_ARITHMETIC", validation_io="EXCLUDED", optimizer_and_checkpoint="EXCLUDED")
        estimates.append(compute_row)
        coupled_row = epoch_arithmetic(batch_size, val_batch, active_step, val_proxy_step, epochs)
        coupled_row.update(scenario="REAL_TRAIN_ACTIVE_PLUS_SERIAL_VALIDATION_IO_PROXY", validation_io="2023_READER_ASSEMBLY_PROXY_NOT_MEASURED_2024_EPOCH",
                           optimizer_and_checkpoint="EXCLUDED", worker_startup_per_epoch_seconds=preferred["startup_and_shutdown_seconds"])
        coupled_row["total_epoch_seconds"] += preferred["startup_and_shutdown_seconds"]
        coupled_row["wall_hours"] = coupled_row["total_epoch_seconds"]*epochs/3600
        estimates.append(coupled_row)
    write_csv(out/"epoch_time_estimates.csv", estimates)
    accumulation = [{"physical_batch": b, "accumulation_steps": a, "effective_batch": b*a,
                     "mode": "FP32_OR_VERIFIED_AMP_AT_BATCH_2" if b == 2 else "FP32",
                     "status": "ENGINEERING_CANDIDATE_ONLY_NOT_EXECUTED_OR_FROZEN"}
                    for b in (1, 2, 4, 8) if b <= rec["MAX_TESTED_SAFE_BATCH"] for a in (1, 2, 4, 8)]
    write_csv(out/"gradient_accumulation_candidates.csv", accumulation)
    cpu_before = (out/"cpu_reference_before.txt").read_text(encoding="utf-8-sig").splitlines()
    cpu_after = (out/"cpu_reference_after.txt").read_text(encoding="utf-8-sig").splitlines()
    cpu_unchanged = cpu_before == cpu_after
    events = stability_result["driver_event_query"]
    tests_ok = len(test_result) == 7 and all(r["pass"] for r in test_result)
    ready = (real_result["status"] == stability_result["status"] == "PASS" and tests_ok and cpu_unchanged
             and len(loader_rows) == 3 and all(r["status"] == "PASS" for r in loader_rows)
             and events["status"] == "QUERIED" and not events.get("events")
             and not stability_result["telemetry_errors"] and stability_result["telemetry_samples"] >= 30)
    gpu_fraction = preferred["gpu_step_fraction"]
    bottleneck = "GPU_COMPUTE_BOUND" if gpu_fraction >= .7 else "MIXED"
    final = {k: rec[k] for k in ("MAX_TESTED_SAFE_BATCH", "RECOMMENDED_SAFE_PHYSICAL_BATCH", "AMP_FP16_FEASIBLE",
                               "AMP_BF16_FEASIBLE", "RECOMMENDED_AMP_MODE", "RECOMMENDED_VALIDATION_BATCH")}
    final.update(GPU_PRESENT=True, CUDA_TORCH_AVAILABLE=True, RTX5060_SM120_EXECUTION_VERIFIED=True,
         RECOMMENDED_NUM_WORKERS=worker_count, GPU_STABILITY_PASS=stability_result["status"] == "PASS",
         REAL_B0_CUDA_REGRESSION_PASS=real_result["status"] == "PASS", TRAINING_ENVIRONMENT_READY=ready,
         B0_FORMAL_TRAINING_STARTED=False, FORMAL_TRAINING_AUTHORIZED=False,
         scope="ENGINEERING_RECOMMENDATION_ONLY", bottleneck=bottleneck, cpu_reference_packages_unchanged=cpu_unchanged,
         worker_comparison=worker_comparison,
         worker_selection="Active throughput for an epoch; prefer fewer workers within 5% of best. Startup included separately. 32-sample full wall also reported.",
         limitations=["No optimizer state or optimizer step measured; a future optimizer consumes extra VRAM and time.",
                      "No model fitting or accuracy/convergence claim; AMP unscaled gradients only.",
                      "32 pinned scenes, order 0/2/4, filesystem cache not flushed; not a cold-disk or full-epoch benchmark.",
                      "Device-wide memory estimate is conservative reservation arithmetic, not a physical residency measurement.",
                      "Validation full real DataLoader epoch not measured; serial I/O proxy clearly separated.",
                      "Worker staging isolation belongs to this audit; no production DataLoader refactor."])
    save(out/"engineering_recommendation.json", final)
    train_rows = read_csv(out/"gpu_batch_benchmark.csv")
    amp_rows = read_csv(out/"gpu_amp_benchmark.csv")
    validation_rows = read_csv(out/"gpu_validation_benchmark.csv")
    lines = ["# GPU_TRAINING_FEASIBILITY_REPORT", "", "Run: `"+out.name+"`", "",
        "Baseline: `"+BASELINE+"`. Scientific Freeze v1.1 / engineering v4 are unchanged.", "",
        "## Result", "", "```json", json.dumps(final, indent=2, ensure_ascii=False), "```", "",
        "## Measurement method", "",
        "Verified CUDA Python: `F:\\pytorch\\Research\\.venv-cuda\\Scripts\\python.exe`; torch 2.11.0+cu128; RTX 5060 Laptop, SM120, runtime 12.8. Exact runtime settings are in environment.json. Input is normalized synthetic full-valid `[B,1,501,501]`, with the frozen Yunnan mask. No optimizer was instantiated; no parameter update or checkpoint occurred. Alpha=0.25 and gamma=2 are engineering test values, not a new scientific freeze.", "",
        "Each compute case performed two warmups and five measured iterations. CUDA synchronization separates forward, loss and backward. All seven passes are checked for finite outputs/loss/gradients and strict qlog order. Raw quantile and all parameters remain float32; qlog, qphysical and conditional pinball remain float64. `compute_iterations.json` retains every check. Model hashes before/after each case match. Timings exclude external numerical checks; the coupled/stability wall times include them. Validation uses eval/no_grad; its tiny backward_ms field is context-exit overhead, not an executed backward.", "",
        "Safety requires both allocator and device-wide headroom: at least 15% for progression and 20% for recommendation. Device-wide free memory is conservatively estimated from pre-case free minus incremental peak reservation, and capped by post-case free. Negative arithmetic values indicate over-reservation, not negative physical free memory. Windows can complete allocations beyond dedicated VRAM; completion alone is therefore not a safe result. Shared-memory paging is suspected from reservation and slowdown, not directly traced.", "",
        "## Training batch", "", "| Batch | Allocated MiB | Reserved MiB | Reserved fraction | Step ms | samples/s | 15% safe |", "|---:|---:|---:|---:|---:|---:|:---|" ]
    for r in train_rows:
        lines.append(f"| {r['batch']} | {float(r['peak_allocated_MiB']):.1f} | {float(r['peak_reserved_MiB']):.1f} | {float(r['reserved_fraction']):.3f} | {float(r['total_ms']):.2f} | {float(r['samples_per_second']):.2f} | {r['safe_15pct']} |")
    lines += ["", "Batch 4 completed but failed headroom; batch 8 was NOT_RUN under the progression rule. No CUDA OOM was observed. The safe maximum is within the tested FP32 sweep; larger AMP training batches were not tested or claimed safe.", "",
        "## Precision at recommended physical batch", "", "| Mode | Reserved MiB | Step ms | samples/s | Numerical status |", "|---|---:|---:|---:|---|"]
    for r in amp_rows:
        lines.append(f"| {r['mode']} | {float(r['peak_reserved_MiB']):.1f} | {float(r['total_ms']):.2f} | {float(r['samples_per_second']):.2f} | {r['status']} |")
    lines += ["", "BF16 and FP16 are close in this short benchmark; the recommendation uses the fastest measured safe mode and is not a claim of statistical superiority. No GradScaler or loss scaling was used. Float32 parameters and the quantile precision guard remain unchanged.", "",
        "## Validation", "", "| Batch | Reserved MiB | Forward + loss ms | samples/s | 20% headroom |", "|---:|---:|---:|---:|---|"]
    for r in validation_rows:
        lines.append(f"| {r['batch']} | {float(r['peak_reserved_MiB']):.1f} | {float(r['total_ms']):.2f} | {float(r['samples_per_second']):.2f} | {r['recommended_20pct']} |")
    lines += ["", "Batch 16 completed but was rejected for headroom. Validation batch 8 is an engineering recommendation only.", "",
        "## Real data and DataLoader", "",
        "One pinned full-valid 2023 Train scene and one pinned full-valid 2024 Validation scene passed the complete raw H: → bounded English staging → formal QC → pinned normalization → CUDA B0/SP04/heads/loss/backward chain. Both have 3430 supervised Yunnan pixels. All source hashes match the previous pinned audit; every copy is size/SHA verified and cleaned. Time identities and normalization hash are retained in real_cuda_regression.json. No 2025 source data were read.", "",
        "The same 32 unique final-eligible 2023 scenes were sampled across the pinned population, with shuffle disabled. Main thread count=2; worker thread count=1; per-worker prefetch=1 batch; pin_memory=false; persistent_workers=false. Each worker owns one bounded staging root and one copy at a time, cap 734003200 bytes per root. Aggregate worst-case worker copy bound is worker_count × cap. No staging copies remain. Data wait is time inside next(iterator); main batch assembly and H2D are separately measured. GPU_step_ms is synchronized forward/loss/backward wall time and includes existing formal CPU validation, not pure kernel event time.", "",
        "| Workers | Full 32-scene wall s | Full samples/s | Active samples/s | Mean wait ms/batch | Mean GPU step ms | GPU utilization % | CPU utilization % |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in loader_rows:
        active = next(w for w in worker_comparison if w["workers"] == int(r["num_workers"]))
        lines.append(f"| {r['num_workers']} | {float(r['wall_time_seconds']):.2f} | {float(r['samples_per_second']):.2f} | {active['active_samples_per_second']:.2f} | {float(r['data_wait_ms']):.2f} | {float(r['GPU_step_ms']):.2f} | {float(r['GPU_utilization_percent']):.1f} | {float(r['CPU_utilization_percent']):.1f} |")
    lines += ["", f"Recommended workers={worker_count}; measured active critical path classification: **{bottleneck}** (GPU step fraction {gpu_fraction:.1%}, data wait {preferred['data_wait_fraction']:.1%}). Device utilization is whole-device telemetry including worker startup, other desktop applications and CPU validation gaps; it is not process-exclusive utilization. The first sweep is preserved under loader_initial because its worker-4 run overlapped the independent profiler. Only the later serial sweep informs these recommendations. Filesystem cache was not flushed, and fixed worker order can favor later runs.", "",
        "## Formal assembly profile", "", "| Component | Mean ms/sample |", "|---|---:|"]
    for k, v in prof["mean_dataset_categories_seconds"].items():
        lines.append(f"| {k} | {v*1000:.3f} |")
    lines += [f"| Batch NumPy stacking/copy → torch (all five arrays) | {prof['mean_numpy_to_torch_seconds']*1000:.3f} |",
        f"| Batch formal validation and other work | {prof['mean_batch_validation_seconds']*1000:.3f} |", "",
        "Four real scenes were profiled with production code unchanged. Dataset categories are exclusive call-site timings; nested readers include copy, SHA, decode and cleanup. The separate mask tensor probe overlaps NumPy→torch and must not be added again. Instrumentation overhead is included. The earlier CPU audit's ~1.4 s/sample residual was NOT reproduced, and this run does not establish its historical cause. Differences in thread/runtime configuration, Windows scheduling and cache conditions remain possible. Current support mapping itself is small. Formal validation recomputes normalization in B0Batch and again at forward entry; future engineering work could evaluate eliminating duplicate validation after preserving provenance guarantees. No such refactor was made.", "",
        "## Three-minute stability", "",
        f"Duration {stability_result['duration_seconds']:.2f} s, {stability_result['iterations']} forward/backward iterations, mean step {stability_result['mean_step_ms']:.2f} ms. Peak allocated/reserved {stability_result['peak_allocated_MiB']:.1f}/{stability_result['peak_reserved_MiB']:.1f} MiB; max device temperature {stability_result['max_temperature_C']} °C; mean power {stability_result['mean_power_W']:.2f} W; mean graphics clock {stability_result['mean_graphics_clock_MHz']:.0f} MHz. Thermal throttle detected={stability_result['thermal_throttle_detected']}; power cap active samples={stability_result['power_cap_active_samples']}. Power cap activity is not silently classified as thermal throttle. CUDA errors={len(stability_result['CUDA_errors'])}; driver event query={events['status']}; matching events={len(events.get('events', []))}. Telemetry is sampled roughly once per second and cannot exclude unsampled transients. Parameter SHA before/after is identical.", "",
        "## Epoch arithmetic and accumulation", "",
        "All rows are ENGINEERING_ESTIMATE_ONLY. Train=11720, Validation=11727; steps use ceiling division. The compute-only scenario omits all data delivery. The real-train scenario extrapolates the measured active 32-scene coupled rate, adds measured worker startup/shutdown once per epoch, and adds a conservative serial per-scene 2023 reader/assembly proxy to validation GPU time. A real 2024 validation DataLoader epoch has not been benchmarked. Optimizer work/state, checkpointing, logging, storage contention and sustained full-epoch thermal changes are excluded; these are arithmetic scenarios, not wall-time guarantees.", "",
        "| Scenario | Epochs | Train min/epoch | Validation min/epoch | Total min/epoch | Wall hours |", "|---|---:|---:|---:|---:|---:|"]
    for r in estimates:
        lines.append(f"| {r['scenario']} | {r['epochs']} | {r['train_seconds_per_epoch']/60:.2f} | {r['validation_seconds_per_epoch']/60:.2f} | {r['total_epoch_seconds']/60:.2f} | {r['wall_hours']:.2f} |")
    lines += ["", "gradient_accumulation_candidates.csv lists physical batch × accumulation steps = effective batch for measured-safe physical batches only. Accumulation execution, loss scaling semantics and optimizer behavior were not benchmarked; no candidate, epoch budget or AMP mode is frozen.", "",
        "## Verification and reproducibility", "",
        f"Automated tests: {sum(r['tests'] for r in test_result)} executed, all passing={tests_ok}; no skipped tests accepted as pass. CPU reference pip freeze unchanged={cpu_unchanged}. All scientific configuration and production source files remain at the baseline. Historical reports are preserved. The initial test import failure is retained in tests_initial; adding the repository root to this new audit entrypoint's import path resolved it without changing old tests or production code. Per-phase invocation hashes capture the benchmark script as executed; the final manifest captures the submitted source. Tests cover shared-memory over-reservation, other GPU consumers, safety vs recommendation margins, progression stop rules and epoch tail arithmetic in addition to the existing suites.", "",
        "Run `benchmark_b0_gpu_feasibility.py` phases in order: compute, real, loader, profile, stability, tests, finalize; use a new versioned run directory. Set TEMP/TMP to an ASCII writable directory for tests. Raw inputs and frozen local evidence must already be available; no download or installation is performed. The benchmark writes staging only below its own gpu_<run> directories and removes only copies it creates. Never overwrite old evidence.", "",
        "TRAINING_ENVIRONMENT_READY describes this engineering forward/backward audit only. Formal training authorization remains false. This task stops after report publication to GitHub; Phase-A Training is not started.", ""]
    with (out/"GPU_TRAINING_FEASIBILITY_REPORT.md").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join(lines))
    print(json.dumps(final), flush=True)


def seal(out):
    required = ("GPU_TRAINING_FEASIBILITY_REPORT.md", "gpu_batch_benchmark.csv", "gpu_amp_benchmark.csv",
                "gpu_validation_benchmark.csv", "real_cuda_regression.json", "dataloader_gpu_benchmark.csv",
                "formal_assembly_profile.json", "gpu_stability_smoke.json", "epoch_time_estimates.csv",
                "gradient_accumulation_candidates.csv", "engineering_recommendation.json", "test_results.txt")
    for name in required:
        if not (out/name).is_file():
            raise FileNotFoundError(name)
    baseline_files = subprocess.check_output(["git", "ls-files", "src", "config", "artifacts"], cwd=ROOT, text=True).splitlines()
    changed = subprocess.check_output(["git", "diff", BASELINE, "--", "src", "config", "artifacts"], cwd=ROOT)
    if changed:
        raise RuntimeError("Frozen production inputs changed")
    scripts = [Path(__file__), ROOT/"tests/gpu_training_feasibility/test_benchmark_safety.py"]
    if list((STAGING/f"gpu_{out.name}").rglob("yuntapr_b0_*.nc")):
        raise RuntimeError("Owned staging copies remain")
    # Normalize only this run's textual evidence before computing final file hashes.
    for path in out.rglob("*"):
        if path.is_file() and path.suffix in (".txt", ".json", ".csv", ".md"):
            raw = path.read_bytes()
            normalized = raw.removeprefix(b"\xef\xbb\xbf").replace(b"\r\n", b"\n")
            if raw != normalized:
                path.write_bytes(normalized)
    files = {str(p.relative_to(out)).replace("\\", "/"): {"sha256": sha256(p), "bytes": p.stat().st_size}
             for p in sorted(out.rglob("*")) if p.is_file() and p.name != "manifest.json"}
    save(out/"manifest.json", {"task": "B0 GPU TRAINING FEASIBILITY BENCHMARK v1", "baseline": BASELINE,
         "created_utc": datetime.now(timezone.utc).isoformat(), "execution_scope": "ENGINEERING_ONLY",
         "public_files": files,
         "scripts": {str(p.relative_to(ROOT)).replace("\\", "/"): sha256(p) for p in scripts},
         "unchanged_production_inputs": {name: sha256(ROOT/name) for name in baseline_files},
         "source_data_committed": False, "cache_committed": False, "wheel_committed": False,
         "formal_training_started": False, "formal_training_authorized": False,
         "owned_staging_copies_remaining": 0})
    print("MANIFEST_SEALED", flush=True)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("phase", choices=["compute", "real", "loader", "profile", "stability", "tests", "finalize", "seal"])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if Path(sys.executable).resolve() != Path(r"F:\pytorch\Research\.venv-cuda\Scripts\python.exe").resolve():
        raise RuntimeError("Verified CUDA interpreter required")
    torch.set_num_threads(2)
    if not torch.cuda.is_available() or torch.cuda.get_device_capability() != (12, 0):
        raise RuntimeError("Expected verified SM120 CUDA GPU")
    args.out.mkdir(parents=True, exist_ok=True)
    save(args.out/(args.phase+"_invocation.json"), {"utc": datetime.now(timezone.utc).isoformat(),
         "python": sys.executable, "script_sha256": sha256(Path(__file__)), "argv": sys.argv,
         "formal_training_started": False})
    globals()[args.phase](args.out)


if __name__ == "__main__":
    main()
