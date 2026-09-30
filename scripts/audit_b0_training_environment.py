"""Read-only B0 hardware audit and synthetic engineering forward/backward timings."""
import argparse
import csv
import gc
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import statistics
import subprocess
import sys
import time

import numpy as np
import torch

from yuntapr.contracts.loader import REPO_ROOT, load_contract, sha256
from yuntapr.data.masks import read_frozen_yunnan_mask
from yuntapr.models.b0 import B0Model
from yuntapr.spatial.sp04_mapping import load_sp04
from yuntapr.losses.total_loss import b0_core_loss
from fit_phase_a_v1_1 import MASK


def save(out, name, data):
    path = out / name
    if path.exists():
        raise FileExistsError(f"Versioned evidence must not be overwritten: {path}")
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def csv_rows(out, name, rows):
    path = out / name
    if path.exists():
        raise FileExistsError(f"Versioned evidence must not be overwritten: {path}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)


def shell_json(command):
    executable = shutil.which("pwsh") or shutil.which("powershell.exe")
    if not executable:
        return None, "PowerShell executable unavailable"
    proc = subprocess.run([executable, "-NoProfile", "-NonInteractive", "-Command", command],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    if proc.returncode:
        return None, (proc.stderr or proc.stdout).strip()[:400]
    try:
        return json.loads(proc.stdout.strip()), None
    except json.JSONDecodeError as exc:
        return None, f"PowerShell JSON parse error: {exc}"


def process_memory():
    """Windows process working set and lifetime peak; no optional psutil dependency."""
    observed, error = shell_json(
        f"Get-Process -Id {os.getpid()} | Select-Object WorkingSet64,PeakWorkingSet64,PrivateMemorySize64 | ConvertTo-Json -Compress")
    if error or not observed:
        raise RuntimeError(f"Cannot measure process memory: {error}")
    return {"working_set_bytes": int(observed["WorkingSet64"]),
            "process_lifetime_peak_working_set_bytes": int(observed["PeakWorkingSet64"]),
            "private_usage_bytes": int(observed["PrivateMemorySize64"])}


def system_inventory(out):
    os_info, os_error = shell_json("Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber,TotalVisibleMemorySize,FreePhysicalMemory | ConvertTo-Json -Compress")
    cpu_info, cpu_error = shell_json("Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors | ConvertTo-Json -Compress")
    volumes, volume_error = shell_json("Get-CimInstance Win32_LogicalDisk | Where-Object { $_.DeviceID -in @('C:','F:','H:') } | Select-Object DeviceID,FileSystem,FreeSpace,Size | ConvertTo-Json -Compress")
    system = {"os": (os_info or {}).get("Caption", platform.platform()),
              "windows_version": (os_info or {}).get("Version", platform.version()),
              "windows_build": (os_info or {}).get("BuildNumber"), "python_path": sys.executable,
              "python_version": sys.version, "platform": platform.platform(),
              "cim_errors": {"operating_system": os_error, "processor": cpu_error, "volumes": volume_error}}
    save(out, "system_environment.json", system)
    observed = volumes if isinstance(volumes, list) else ([volumes] if volumes else [])
    disk = {v["DeviceID"]: {"filesystem": v["FileSystem"], "free_bytes": int(v["FreeSpace"]),
                            "total_bytes": int(v["Size"])} for v in observed}
    for drive in ("C:", "F:", "H:"):
        if drive not in disk and Path(drive+"\\").exists():
            usage = shutil.disk_usage(drive+"\\")
            disk[drive] = {"filesystem": "UNKNOWN_CIM_UNAVAILABLE", "free_bytes": usage.free,
                           "total_bytes": usage.total}
    roots = {"himawari_source": Path(r"H:\葵花202303_202510"),
             "imerg_source": Path(r"F:\云南极端降水数据\raw\IMERG"),
             "bounded_staging": Path(r"F:\pytorch\Research\stage0_himawari\cache\staging"),
             "existing_output_root": Path(r"F:\pytorch\Research\outputs"),
             "repository_project": REPO_ROOT}
    result = {"cpu_model": (cpu_info or {}).get("Name"),
              "physical_cores": (cpu_info or {}).get("NumberOfCores"),
              "logical_cores": (cpu_info or {}).get("NumberOfLogicalProcessors", os.cpu_count()),
              "system_ram_total_bytes": int(os_info["TotalVisibleMemorySize"])*1024 if os_info else None,
              "system_ram_available_bytes": int(os_info["FreePhysicalMemory"])*1024 if os_info else None,
              "drives": disk, "paths": {k: {"path": str(v), "exists": v.exists()} for k,v in roots.items()},
              "future_checkpoint_location": "UNSET; F:\\pytorch\\Research\\outputs is an existing engineering candidate only"}
    save(out, "cpu_ram_storage.json", result)
    return result


def cuda_inventory(out):
    cuda = torch.cuda.is_available()
    version = torch.__version__
    build = "CPU_ONLY" if "+cpu" in version and not cuda else "CUDA_ENABLED" if torch.version.cuda is not None else "UNKNOWN"
    pytorch = {"torch_version": version, "torch_version_cuda": torch.version.cuda,
               "cudnn_version": torch.backends.cudnn.version(), "torch_cuda_is_available": cuda,
               "torch_cuda_device_count": torch.cuda.device_count(), "TORCH_BUILD": build,
               "CURRENT_TORCH_CANNOT_USE_CUDA": build == "CPU_ONLY",
               "python_path": sys.executable}
    save(out, "pytorch_cuda_environment.json", pytorch)
    smi = shutil.which("nvidia-smi")
    raw_status, inventory = "NOT_FOUND", []
    reported_cuda = None
    if smi:
        full = subprocess.run([smi], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        raw_status = "PASS" if full.returncode == 0 else f"FAILED_EXIT_{full.returncode}"
        match = re.search(r"CUDA Version:\s*([\d.]+)", full.stdout)
        reported_cuda = match.group(1) if match else None
        query = subprocess.run([smi, "--query-gpu=index,name,compute_cap,driver_version,memory.total,memory.used,temperature.gpu,power.limit",
                                "--format=csv,noheader,nounits"], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=30)
        if query.returncode == 0:
            for line in query.stdout.splitlines():
                values = next(csv.reader([line]))
                if len(values) != 8:
                    continue
                index, name, capability, driver, total, used, temp, power = [v.strip() for v in values]
                inventory.append({"index": int(index), "name": name, "compute_capability": capability,
                                  "driver_version": driver, "total_vram_mib": int(total),
                                  "current_memory_used_mib": int(used),
                                  "current_memory_free_estimate_mib": int(total)-int(used),
                                  "temperature_c": float(temp) if temp not in ("N/A", "[N/A]") else None,
                                  "power_limit_w": float(power) if power not in ("N/A", "[N/A]") else None})
        elif raw_status == "PASS":
            raw_status = f"QUERY_FAILED_EXIT_{query.returncode}"
    present = True if inventory else (True if cuda else "unknown")
    result = {"nvidia_smi_executable": smi, "nvidia_smi_status": raw_status,
              "nvidia_driver_reported_max_cuda_version": reported_cuda,
              "pytorch_cuda_runtime": torch.version.cuda, "GPU_PRESENT": present,
              "CUDA_TORCH_AVAILABLE": cuda, "CUDA_ENVIRONMENT_ACTION_REQUIRED": present is True and not cuda,
              "gpus": inventory, "gpu_presence_basis": "nvidia-smi query" if inventory else "CUDA runtime or unknown"}
    save(out, "gpu_inventory.json", result)
    return result


def model_static(out):
    science, cfg = load_contract()
    model = B0Model()
    params = list(model.parameters())
    n = sum(p.numel() for p in params)
    trainable = sum(p.numel() for p in params if p.requires_grad)
    parameter_bytes = sum(p.numel()*p.element_size() for p in params)
    state_bytes = sum(t.numel()*t.element_size() for t in model.state_dict().values())
    dtypes = {}
    for p in params:
        key = str(p.dtype)
        dtypes[key] = dtypes.get(key, 0)+p.numel()
    if any(p.dtype != torch.float32 for p in params) or cfg["quantile_numerics"]["accumulation_dtype"] != "float64":
        raise ValueError("B0 v4 parameter/quantile dtype contract changed")
    result = {"model": "B0Model", "science_version": science["schema_version"],
              "engineering_version": cfg["schema_version"], "parameter_count": n,
              "trainable_parameter_count": trainable, "parameter_dtype_elements": dtypes,
              "float32_parameter_count": dtypes.get("torch.float32", 0),
              "float64_parameter_count": dtypes.get("torch.float64", 0),
              "parameters_bytes": parameter_bytes, "gradients_theoretical_bytes": parameter_bytes,
              "sgd_no_momentum_theoretical_optimizer_state_bytes": 0,
              "sgd_momentum_theoretical_optimizer_state_bytes": trainable*4,
              "adamw_theoretical_optimizer_state_bytes": trainable*8,
              "sgd_no_momentum_params_grads_state_bytes": parameter_bytes*2,
              "adamw_params_grads_state_bytes": parameter_bytes*2+trainable*8,
              "state_dict_tensor_bytes": state_bytes, "optimizer_created": False,
              "input_shape_batch_1": [1,1,501,501],
              "rain_logit_shape_batch_1": [1,1,100,100],
              "quantile_shape_batch_1": [1,32,100,100],
              "qlog_output_dtype": "float64", "qphysical_output_dtype": "float64",
              "qlog_bytes_per_batch_1": 32*100*100*8,
              "qphysical_bytes_per_batch_1": 32*100*100*8,
              "first_native_feature_bytes_per_batch_1": 48*501*501*4,
              "scope": "Theoretical tensor bytes; full activation/autograd/workspace memory must be measured"}
    save(out, "model_memory_static.json", result)
    return result


def synthetic_tensors(batch, device, yunnan):
    x = torch.randn((batch, 1, 501, 501), dtype=torch.float32, device=device)
    valid = torch.ones_like(x, dtype=torch.bool)
    mask = torch.from_numpy(yunnan[None, None].copy()).to(device).expand(batch,-1,-1,-1)
    y = mask.float()
    y_valid = torch.ones_like(y, dtype=torch.bool)
    return x, valid, y, y_valid, mask


def timed_pass(model, tensors, reduction, *, backward, amp_dtype=None):
    x, valid, y, y_valid, mask = tensors
    device = x.device
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    model.zero_grad(set_to_none=True)
    started = time.perf_counter()
    context = (torch.autocast("cuda", dtype=amp_dtype) if amp_dtype is not None else torch.autocast("cpu", enabled=False))
    with context:
        output = model(x, valid)
        if device.type == "cuda":
            torch.cuda.synchronize(device)
        forward = time.perf_counter()
        loss = b0_core_loss(output, y, y_valid, mask, focal_alpha=.25, focal_gamma=2.,
                            quantile_axis_reduction=reduction)
        if device.type == "cuda":
            torch.cuda.synchronize(device)
        after_loss = time.perf_counter()
    if backward:
        loss.total.backward()
        if device.type == "cuda":
            torch.cuda.synchronize(device)
    finished = time.perf_counter()
    gradients_finite = all(p.grad is not None and bool(torch.isfinite(p.grad).all()) for p in model.parameters()) if backward else None
    return {"forward_seconds": forward-started, "loss_seconds": after_loss-forward,
            "backward_seconds": finished-after_loss if backward else None,
            "total_seconds": finished-started,
            "rain_logit_shape": list(output.rain_logit.shape),
            "quantile_shape": list(output.conditional_quantiles_log.shape),
            "qlog_dtype": str(output.conditional_quantiles_log.dtype),
            "qphysical_dtype": str(output.conditional_quantiles_physical.dtype),
            "conditional_pinball_dtype": str(loss.conditional_quantile.dtype),
            "outputs_finite": bool(torch.isfinite(output.rain_logit).all() and torch.isfinite(output.conditional_quantiles_log).all()
                                   and torch.isfinite(output.conditional_quantiles_physical).all()),
            "loss_finite": bool(torch.isfinite(loss.total)),
            "gradients_finite": gradients_finite, "valid_yunnan_loss_pixels": loss.valid_supervised_count}


def cpu_benchmark(out, yunnan, config):
    torch.set_num_threads(2)
    torch.manual_seed(20260930)
    model = B0Model().eval()
    tensors = synthetic_tensors(1, torch.device("cpu"), yunnan)
    before = process_memory()
    warmup = timed_pass(model, tensors, config["loss"]["quantile_axis_reduction"], backward=True)
    measures = [timed_pass(model, tensors, config["loss"]["quantile_axis_reduction"], backward=True)
                for _ in range(3)]
    after = process_memory()
    if not all(m["outputs_finite"] and m["loss_finite"] and m["gradients_finite"]
               and m["qlog_dtype"] == m["qphysical_dtype"] == m["conditional_pinball_dtype"] == "torch.float64"
               and m["rain_logit_shape"] == [1,1,100,100] and m["quantile_shape"] == [1,32,100,100]
               for m in measures):
        raise ValueError("CPU B0 benchmark violated current model/numerical contract")
    result = {"status": "PASS", "device": "cpu", "input": "synthetic_normalized_float32_full_valid_501x501",
              "frozen_yunnan_mask_true_cells": int(yunnan.sum()), "torch_threads": 2,
              "warmup_count": 1, "measurement_count": 3,
              "warmup_seconds": warmup["total_seconds"], "measurements": measures,
              "mean_forward_seconds": statistics.mean(m["forward_seconds"] for m in measures),
              "mean_loss_seconds": statistics.mean(m["loss_seconds"] for m in measures),
              "mean_backward_seconds": statistics.mean(m["backward_seconds"] for m in measures),
              "mean_total_step_seconds": statistics.mean(m["total_seconds"] for m in measures),
              "min_total_step_seconds": min(m["total_seconds"] for m in measures),
              "max_total_step_seconds": max(m["total_seconds"] for m in measures),
              "memory_before": before, "memory_after": after,
              "peak_memory_note": "Windows process lifetime peak working set includes model initialization and warmup; not an isolated per-step peak",
              "execution_scope": "ENGINEERING_ONLY", "focal_parameters": "ENGINEERING_TEST_ONLY",
              "optimizer_created": False, "optimizer_step_performed": False, "checkpoint_generated": False}
    save(out, "cpu_benchmark.json", result)
    return result


def gpu_benchmarks(out, yunnan, config, gpu):
    fields = ["status","mode","batch","warmup_count","measurement_count","allocated_before_bytes",
              "peak_allocated_bytes","peak_reserved_bytes","peak_reserved_fraction_total_vram",
              "forward_seconds_mean","backward_seconds_mean","total_step_seconds_mean",
              "outputs_finite","loss_finite","gradients_finite","oom","error"]
    if not torch.cuda.is_available():
        row = {k:"" for k in fields}; row.update(status="NOT_RUN_CUDA_UNAVAILABLE",mode="FP32",oom="NOT_TESTED")
        csv_rows(out, "gpu_batch_benchmark.csv", [row])
        row = {k:"" for k in fields}; row.update(status="NOT_RUN_CUDA_UNAVAILABLE",mode="AMP",oom="NOT_TESTED")
        csv_rows(out, "gpu_amp_benchmark.csv", [row])
        row = {k:"" for k in fields}; row.update(status="NOT_RUN_CUDA_UNAVAILABLE",mode="VALIDATION",oom="NOT_TESTED")
        csv_rows(out, "gpu_validation_benchmark.csv", [row])
        return {"MAX_TESTED_SAFE_BATCH": "NOT_AVAILABLE", "AMP_FEASIBLE": "NOT_TESTED", "validation_max_tested_batch": "NOT_AVAILABLE"}
    device = torch.device("cuda:0")
    total_vram = torch.cuda.get_device_properties(device).total_memory
    model = B0Model().to(device).eval()
    reduction = config["loss"]["quantile_axis_reduction"]
    train_rows, amp_rows, val_rows = [], [], []
    safe = 0
    def measure(batch, *, backward, mode, amp=None, warmups=2, repeats=3):
        tensors = synthetic_tensors(batch, device, yunnan)
        for _ in range(warmups):
            timed_pass(model, tensors, reduction, backward=backward, amp_dtype=amp)
        torch.cuda.synchronize(device)
        allocated = torch.cuda.memory_allocated(device)
        torch.cuda.reset_peak_memory_stats(device)
        runs = [timed_pass(model, tensors, reduction, backward=backward, amp_dtype=amp) for _ in range(repeats)]
        row = {"status":"PASS", "mode":mode, "batch":batch, "warmup_count":warmups,
               "measurement_count":repeats, "allocated_before_bytes":allocated,
               "peak_allocated_bytes":torch.cuda.max_memory_allocated(device),
               "peak_reserved_bytes":torch.cuda.max_memory_reserved(device),
               "peak_reserved_fraction_total_vram":torch.cuda.max_memory_reserved(device)/total_vram,
               "forward_seconds_mean":statistics.mean(r["forward_seconds"] for r in runs),
               "backward_seconds_mean":statistics.mean(r["backward_seconds"] or 0 for r in runs),
               "total_step_seconds_mean":statistics.mean(r["total_seconds"] for r in runs),
               "outputs_finite":all(r["outputs_finite"] for r in runs),
               "loss_finite":all(r["loss_finite"] for r in runs),
               "gradients_finite":all(r["gradients_finite"] for r in runs) if backward else "NOT_APPLICABLE",
               "oom":False,"error":""}
        if any(r["qlog_dtype"] != "torch.float64" or r["qphysical_dtype"] != "torch.float64"
               or r["conditional_pinball_dtype"] != "torch.float64" for r in runs):
            row.update(status="FAIL_NUMERICAL_PRECISION",error="quantile float64 contract violated")
        return row
    for batch in (1,2,4,8):
        try:
            row=measure(batch,backward=True,mode="FP32")
            train_rows.append(row)
            if row["status"] != "PASS" or not row["outputs_finite"] or not row["loss_finite"] or not row["gradients_finite"]:
                break
            safe=batch
        except torch.cuda.OutOfMemoryError as error:
            train_rows.append({**{k:"" for k in fields},"status":"OOM","mode":"FP32","batch":batch,"oom":True,"error":repr(error)[:500]})
            gc.collect(); torch.cuda.empty_cache(); break
    csv_rows(out,"gpu_batch_benchmark.csv",train_rows)
    if safe:
        amp_options = [("BF16",torch.bfloat16)] if torch.cuda.is_bf16_supported() else []
        amp_options += [("FP16",torch.float16)]
        for mode,dtype in amp_options:
            try:
                amp_rows.append(measure(safe,backward=True,mode=mode,amp=dtype))
            except (torch.cuda.OutOfMemoryError, FloatingPointError) as error:
                amp_rows.append({**{k:"" for k in fields},"status":"FAILED","mode":mode,"batch":safe,"oom":"out of memory" in str(error).lower(),"error":repr(error)[:500]})
                gc.collect(); torch.cuda.empty_cache()
    if not amp_rows:
        amp_rows = [{**{k:"" for k in fields},"status":"NOT_RUN_NO_SAFE_FP32_BATCH","mode":"AMP","oom":"NOT_TESTED"}]
    csv_rows(out,"gpu_amp_benchmark.csv",amp_rows)
    validation_max=0
    for batch in (1,2,4,8):
        try:
            with torch.no_grad():
                row=measure(batch,backward=False,mode="VALIDATION",warmups=1,repeats=3)
            val_rows.append(row)
            validation_max=batch
        except torch.cuda.OutOfMemoryError as error:
            val_rows.append({**{k:"" for k in fields},"status":"OOM","mode":"VALIDATION","batch":batch,"oom":True,"error":repr(error)[:500]})
            gc.collect(); torch.cuda.empty_cache(); break
    csv_rows(out,"gpu_validation_benchmark.csv",val_rows)
    feasible=any(r["status"] == "PASS" and r["outputs_finite"] and r["loss_finite"] and r["gradients_finite"]
                 for r in amp_rows)
    return {"MAX_TESTED_SAFE_BATCH":safe or "NOT_AVAILABLE", "AMP_FEASIBLE":feasible,
            "validation_max_tested_batch":validation_max or "NOT_AVAILABLE"}


def checkpoint_estimates(out, static):
    model_bytes = static["state_dict_tensor_bytes"]
    adam_bytes = static["adamw_theoretical_optimizer_state_bytes"]
    metadata_allowance = 1024*1024
    full = model_bytes+adam_bytes+metadata_allowance
    choices=[]
    for epochs in (10,30,50):
        every=10
        count=2+math.ceil(epochs/every)
        choices.append({"illustrative_total_epochs":epochs,"illustrative_every_n_epochs":every,
                        "best_last_and_periodic_count_upper_bound":count,"storage_bytes_upper_bound":count*full})
    result={"state_dict_tensor_bytes":model_bytes,"adamw_state_theoretical_bytes":adam_bytes,
            "scheduler_and_metadata_allowance_bytes":metadata_allowance,
            "single_model_only_bytes":model_bytes,"single_model_plus_adamw_metadata_bytes":full,
            "best_plus_last_bytes_upper_bound":2*full,"illustrative_periodic_plans":choices,
            "status":"THEORETICAL_ENGINEERING_ESTIMATE_ONLY",
            "optimizer_created":False,"checkpoint_generated":False,"epoch_or_save_interval_frozen":False}
    save(out,"checkpoint_storage_estimate.json",result)


def main(out):
    if not out.is_dir():
        raise FileNotFoundError("Versioned run directory must already exist")
    science, config=load_contract()
    if science["execution_status"]["B0_FORMAL_TRAINING_STARTED"] is not False or config["formal_training_started"] is not False:
        raise ValueError("Formal training remains forbidden")
    system_inventory(out)
    gpu=cuda_inventory(out)
    static=model_static(out)
    yunnan=read_frozen_yunnan_mask(MASK, load_sp04())
    cpu=cpu_benchmark(out,yunnan,config)
    gpu_result=gpu_benchmarks(out,yunnan,config,gpu)
    checkpoint_estimates(out,static)
    save(out,"measurement_gate.json",{"environment":gpu,"cpu_benchmark_status":cpu["status"],
         "gpu_benchmark_gate":gpu_result,"B0_FORMAL_TRAINING_STARTED":False,"FORMAL_TRAINING_AUTHORIZED":False})
    print(json.dumps({"torch_build":gpu["CUDA_TORCH_AVAILABLE"],"gpu_present":gpu["GPU_PRESENT"],
                      "cpu_mean_step_seconds":cpu["mean_total_step_seconds"],"gpu_status":gpu_result}),flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--run-dir",type=Path,required=True)
    main(parser.parse_args().run_dir)
