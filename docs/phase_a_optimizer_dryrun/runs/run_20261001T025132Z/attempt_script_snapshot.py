"""Bounded ENGINEERING_ONLY protocol gates and real optimizer replay; no fitting entrypoint."""
from __future__ import annotations
import argparse
import csv
from copy import deepcopy
from dataclasses import fields
from datetime import datetime, timezone
import gc
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import time
import traceback
import unittest
from unittest.mock import patch
import weakref

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "scripts")]
import numpy as np
import torch
from yuntapr.contracts.loader import sha256
from yuntapr.training.phase_a_protocol import (load_protocol, phase_a_lr_for_update, lr_for_update,
    require_engineering_scope, seed_reproducibility, head_pin, adamw, state_digest,
    capture_rng, checkpoint_metadata, load_temporary_checkpoint)
from yuntapr.models.b0 import B0Model
from yuntapr.training.batch_contract import B0Batch
from yuntapr.training.forward_step import formal_rules_engineering_forward_step

BASELINE = "8d5d15f6df85649cefedd264301d70ee2ba89c7e"
PREVIOUS = ROOT / "docs/phase_a_optimizer_dryrun/runs/run_20261001T023702Z"
IMPLEMENTATION = "src/yuntapr/training/phase_a_protocol.py"
PYTHON = Path(r"F:\pytorch\Research\.venv-cuda\Scripts\python.exe")


def save(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False, default=str)
        stream.write("\n")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def table(path, rows):
    names = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=names, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def unchanged_baseline():
    """All baseline files immutable except the one expressly approved expression."""
    expected = {}
    tree = subprocess.check_output(["git", "ls-tree", "-r", "-z", BASELINE], cwd=ROOT).decode("utf-8")
    for entry in tree.rstrip("\0").split("\0"):
        meta, name = entry.split("\t", 1)
        expected[name] = meta.split()[2]
    names = [name for name in expected if name != IMPLEMENTATION]
    blobs = subprocess.run(["git", "hash-object", "--stdin-paths"], cwd=ROOT, text=True, encoding="utf-8",
        input="\n".join(names)+"\n", capture_output=True, check=True).stdout.splitlines()
    if len(blobs) != len(names) or any(expected[name] != value for name, value in zip(names, blobs)):
        raise RuntimeError("Historical baseline file changed")
    original = subprocess.check_output(["git", "show", BASELINE+":"+IMPLEMENTATION], cwd=ROOT).decode("utf-8")
    corrected = original.replace("return 1e-4 * u / W", "return 1e-4 * (u / W)")
    if corrected == original or (ROOT/IMPLEMENTATION).read_text(encoding="utf-8") != corrected:
        raise RuntimeError("Change exceeds WARMUP_EVALUATION_ORDER_ONLY")
    return {name: sha256(ROOT/name) for name in names}


def initialize(out):
    if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() != BASELINE:
        raise RuntimeError("Unexpected baseline")
    preserved = unchanged_baseline()
    identity = read(PREVIOUS/"protocol_identity.json")
    for kind in ("protocol", "document"):
        if sha256(ROOT/identity[kind+"_path"]) != identity[kind+"_sha256"]:
            raise RuntimeError("Frozen protocol file changed")
    load_protocol(expected_sha256=identity["protocol_sha256"])
    out.mkdir(parents=True, exist_ok=False)
    save(out/"protocol_identity.json", {**identity, "current_baseline_commit": BASELINE,
        "current_run_created_UTC": datetime.now(timezone.utc).isoformat(),
        "previous_run": "STOPPED_SCHEDULER_BOUNDARY_FAILURE", "previous_run_path": PREVIOUS.relative_to(ROOT).as_posix(),
        "current_correction": "WARMUP_EVALUATION_ORDER_ONLY", "scientific_parameters_changed": False,
        "protocol_version_changed": False, "implementation_sha256": sha256(ROOT/IMPLEMENTATION),
        "unchanged_baseline_files_sha256": preserved})
    print("IDENTITY_AND_HISTORY_GATE_PASS", flush=True)


def preliminary(out):
    from tests.phase_a_protocol_v1.test_protocol_v1 import ProtocolTests
    names = [name for name in unittest.defaultTestLoader.getTestCaseNames(ProtocolTests)
             if name != "test_real_replay_and_resume_evidence"]
    if len(names) != 16:
        raise RuntimeError("Expected the unchanged original sixteen tests")
    with (out/"preliminary_test_results.txt").open("x", encoding="utf-8", newline="\n") as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.TestSuite(ProtocolTests(name) for name in names))
    passed = result.wasSuccessful() and not result.skipped and result.testsRun == 16
    save(out/"preliminary_test_summary.json", {"executed": result.testsRun, "failures": len(result.failures),
        "errors": len(result.errors), "skipped": len(result.skipped), "pass": passed,
        "original_test_file_sha256": sha256(ROOT/"tests/phase_a_protocol_v1/test_protocol_v1.py")})
    W, U = 5860, 293000
    boundaries = [{"u": u, "LR": phase_a_lr_for_update(u), "hex": phase_a_lr_for_update(u).hex()} for u in (1,W,W+1,U)]
    warmup = np.array([phase_a_lr_for_update(u) for u in range(1,W+1)])
    cosine = np.array([phase_a_lr_for_update(u) for u in range(W+1,U+1)])
    boundary_pass = (phase_a_lr_for_update(1) == 1e-4/5860 and phase_a_lr_for_update(W) == 1e-4
        and phase_a_lr_for_update(W+1) < 1e-4 and phase_a_lr_for_update(U) == 1e-6
        and bool((np.diff(warmup)>0).all()) and bool(((warmup>0)&(warmup<=1e-4)).all())
        and bool((np.diff(cosine)<=0).all()) and bool(((cosine>=1e-6)&(cosine<=1e-4)).all()))
    save(out/"lr_schedule_boundary_tests.json", {"status": "PASS" if boundary_pass else "FAIL", "boundaries": boundaries,
        "warmup_updates_checked": len(warmup), "cosine_updates_checked": len(cosine),
        "comparison": "EXACT; no tolerance/clamp/round/isclose", "warmup_evaluation": "base_lr*(u/W)",
        "cosine_formula_unchanged": True, "real_updates_used_for_scheduler_sweep": 0})
    replay = []
    for epoch in (1,2,10,25,49,50):
        a, b = phase_a_lr_for_update(epoch*5860), lr_for_update(epoch*8000, steps_per_epoch=8000)
        replay.append({"epoch": epoch, "phase_a_LR": a, "FinalFit_LR": b, "phase_a_hex": a.hex(),
                       "FinalFit_hex": b.hex(), "absolute_error": abs(a-b), "exact": a == b})
    save(out/"scheduler_finalfit_replay.json", {"status": "PASS" if all(r["exact"] for r in replay) else "FAIL",
        "rule": "SAME_EPOCH_PROGRESS_ON_50_EPOCH_HORIZON", "epochs": replay, "Phase_B_executed": False})
    print(json.dumps({"preliminary_16_pass": passed, "scheduler_boundary_pass": boundary_pass,
                      "FinalFit_exact_pass": all(r["exact"] for r in replay)}), flush=True)
    if not passed or not boundary_pass or not all(r["exact"] for r in replay):
        raise RuntimeError("STOP: preliminary/scheduler gate failure; do not apply another scheduler fix")


def worker_init_seed(worker_id):
    from benchmark_b0_gpu_feasibility import worker_init
    worker_init(worker_id)
    seed = torch.initial_seed() % 2**32
    np.random.seed(seed)
    random.seed(seed)


def tensor_batch_hash(batch):
    return state_digest({f.name: getattr(batch, f.name) for f in fields(batch)
                         if isinstance(getattr(batch, f.name), torch.Tensor)})


def real_fixtures(out, config):
    from benchmark_b0_gpu_feasibility import pinned_candidates, dataset_new, list_collate, STAGING
    records, hashes, selected, _, _ = pinned_candidates(6)
    indices = np.linspace(0,11719,6,dtype=np.int64).tolist()
    for index, record, details in zip(indices, records, selected):
        if record.imerg_window_start.year != 2023:
            raise RuntimeError("Non-2023 sample prohibited")
        frame = record.frames[0]
        details.update(train_manifest_index=index, nominal_time=str(frame.nominal_time),
            obs_start=str(frame.obs_start), obs_end=str(frame.obs_end), date_created=str(frame.date_created),
            imerg_index=record.imerg_index, year=2023)
    save(out/"selected_dryrun_samples.json", {"status": "IDENTITIES_REGISTERED_BEFORE_READ",
        "rule": "np.linspace(0,11719,6,dtype=int64), no rain/model criteria", "indices": indices,
        "manifest_sha256": config["identity"]["eligible_train_manifest"]["sha256"], "samples": selected})
    dataset = dataset_new(records, hashes, out, "phase_a_optimizer")
    generator = torch.Generator().manual_seed(2026)
    loader = torch.utils.data.DataLoader(dataset, batch_size=2, shuffle=False, drop_last=False,
        num_workers=2, pin_memory=False, persistent_workers=False, prefetch_factor=1,
        worker_init_fn=worker_init_seed, collate_fn=list_collate, generator=generator)
    fixtures, evidence, batches = [], [], []
    started = time.perf_counter()
    for items in loader:
        samples = [sample for sample, _ in items]
        if len(samples) != 2:
            raise RuntimeError("Three complete batch2 fixtures required")
        cpu_batch = B0Batch.from_formal_samples(samples)
        if any(sample.normalization_artifact_sha256 != config["identity"]["phase_a_normalization_artifact"]["sha256"] for sample in samples):
            raise RuntimeError("Normalization SHA mismatch")
        # Arrays will never be mutated; new CUDA tensors are built from them per update.
        for sample in samples:
            for field in fields(sample):
                value = getattr(sample, field.name)
                if isinstance(value, np.ndarray):
                    value.flags.writeable = False
        fixtures.append(tuple(samples))
        batches.append({"batch": len(fixtures), "samples": [s.sample_id for s in samples],
                        "CPU_tensor_sha256": tensor_batch_hash(cpu_batch)})
        for sample, detail in items:
            detail.update(analysis_time=str(sample.analysis_time), causality_pass=sample.himawari_obs_end<=sample.analysis_time,
                formal_QC_pass=sample.formal_supervised_qc_pass, b13_full_valid=sample.b13_full_valid,
                normalization_sha256=sample.normalization_artifact_sha256,
                normalization_mu=sample.normalization_mu, normalization_sigma=sample.normalization_sigma,
                valid_Yunnan_cells=int((sample.imerg_valid_mask & sample.yunnan_eval_mask).sum()))
            evidence.append(detail)
        print("REAL_FIXTURE_BATCH_"+str(len(fixtures))+"_PASS", flush=True)
    if len(fixtures) != 3 or len(evidence) != 6 or {r["worker_id"] for r in evidence} != {0,1}:
        raise RuntimeError("Expected six scenes and two independent reader workers")
    roots = {r["staging_root"] for r in evidence}
    if len(roots) != 2 or any(not root.isascii() for root in roots):
        raise RuntimeError("Independent ASCII staging roots required")
    remaining = list((STAGING/f"gpu_{out.name}").rglob("yuntapr_b0_*.nc"))
    if remaining:
        raise RuntimeError("Owned staging copies remain")
    save(out/"real_sample_read_audit.json", {"status": "PASS", "samples": evidence, "batches": batches,
        "reader_wall_seconds": time.perf_counter()-started, "source_H_read_only": True,
        "num_workers": 2, "pin_memory": False, "persistent_workers": False, "prefetch_factor": 1,
        "fixture_order_shuffle": False, "fixture_order_note": "Fixed engineering replay subset, not a formal epoch sampler",
        "worker_seed_rule": "DataLoader independent generator seed2026; Python/NumPy worker seeds from torch.initial_seed modulo2**32",
        "one_file_at_a_time": True, "max_temporary_bytes_per_worker": 734003200,
        "owned_staging_copies_remaining": 0, "RAM_fixture_reuse": "Same immutable six real outputs for A/B/C; no permanent disk data cache",
        "2025_pixels_read": False})
    return fixtures, batches


def clean_cuda():
    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.synchronize()


def fresh_model():
    seed_reproducibility()
    model = B0Model().cuda().train()
    observed = {}
    def capture_raw(_module, _input, output):
        observed["raw_quantile_dtype"] = str(output.dtype)
    def capture_backbone(_module, _input, output):
        observed["backbone_output_dtype"] = str(output.dtype)
    model.heads.quantile.register_forward_hook(capture_raw)
    model.backbone.register_forward_hook(capture_backbone)
    optimizer, group_evidence = adamw(model)
    head_pin(model)
    return model, optimizer, observed, group_evidence


def gradient_norm(parameters):
    return torch.linalg.vector_norm(torch.stack([torch.linalg.vector_norm(p.grad.detach(), 2) for p in parameters]), 2)


def perform_update(model, optimizer, observed, samples, expected_batch_hash, u, run, config):
    from benchmark_b0_gpu_feasibility import to_cuda, safe_memory
    parameters = list(model.parameters())
    if u not in (1,2,3):
        raise RuntimeError("Only three ENGINEERING_ONLY updates per replay run")
    free_before, reported_total = torch.cuda.mem_get_info()
    dedicated = torch.cuda.get_device_properties(0).total_memory
    reserved_before = torch.cuda.memory_reserved()
    torch.cuda.reset_peak_memory_stats()
    began = time.perf_counter()
    batch = to_cuda(B0Batch.from_formal_samples(samples))
    if tensor_batch_hash(batch) != expected_batch_hash:
        raise RuntimeError("Replay fixture input changed")
    optimizer.zero_grad(set_to_none=True)
    lr = phase_a_lr_for_update(u)
    for group in optimizer.param_groups:
        group["lr"] = lr
    with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
        autocast_enabled = torch.is_autocast_enabled("cuda")
        autocast_dtype = str(torch.get_autocast_dtype("cuda"))
        output, loss = formal_rules_engineering_forward_step(model, batch,
            focal_alpha=config["loss"]["occurrence"]["alpha"], focal_gamma=config["loss"]["occurrence"]["gamma"],
            quantile_axis_reduction=config["loss"]["quantile"]["axis_reduction"])
    qlog, qphysical = output.conditional_quantiles_log, output.conditional_quantiles_physical
    crossing = int((qlog[:,1:]<=qlog[:,:-1]).sum()) + int((qphysical[:,1:]<=qphysical[:,:-1]).sum())
    finite_loss = all(bool(torch.isfinite(value).all()) for value in (loss.total,loss.occurrence,loss.conditional_quantile))
    finite_outputs = all(bool(torch.isfinite(getattr(output,f.name)).all()) for f in fields(output)
        if isinstance(getattr(output,f.name),torch.Tensor))
    dtype_parameters = sorted({str(p.dtype) for p in parameters})
    precision = {"run": run, "global_update": u, "parameters": dtype_parameters,
        "raw_quantile": observed.get("raw_quantile_dtype"), "backbone_autocast_output": observed.get("backbone_output_dtype"),
        "autocast_enabled": autocast_enabled, "autocast_dtype": autocast_dtype,
        "qlog": str(qlog.dtype), "qphysical": str(qphysical.dtype), "pinball": str(loss.conditional_quantile.dtype),
        "strict_crossing_count": crossing, "finite_outputs": finite_outputs, "finite_loss": finite_loss,
        "valid_Yunnan_supervised_pixels": loss.valid_supervised_count, "rainy_pixels": loss.rainy_valid_count}
    precision_ok = (dtype_parameters==["torch.float32"] and precision["raw_quantile"]=="torch.float32"
        and precision["backbone_autocast_output"]=="torch.bfloat16" and autocast_enabled and autocast_dtype=="torch.bfloat16"
        and precision["qlog"]==precision["qphysical"]==precision["pinball"]=="torch.float64"
        and not crossing and finite_outputs and finite_loss and loss.valid_supervised_count==6860)
    if not precision_ok:
        raise RuntimeError("STOP: forward precision/finite/strict-quantile gate failure: "+repr(precision))
    loss.total.backward()
    gradients_finite = all(p.grad is not None and bool(torch.isfinite(p.grad).all()) for p in parameters)
    if not gradients_finite:
        raise RuntimeError("STOP: nonfinite or absent gradient")
    before_clip = gradient_norm(parameters)
    returned = torch.nn.utils.clip_grad_norm_(parameters,max_norm=5.,norm_type=2.,error_if_nonfinite=True,foreach=False)
    if float(before_clip) != float(returned):
        raise RuntimeError("Pre-clip norm calculation mismatch")
    after_clip = gradient_norm(parameters)
    coefficient = float(5./(returned+1e-6))
    triggered = coefficient < 1.
    if not bool(torch.isfinite(after_clip)):
        raise RuntimeError("STOP: nonfinite post-clip norm")
    optimizer.step()
    torch.cuda.synchronize()
    parameters_finite = all(bool(torch.isfinite(p).all()) for p in parameters)
    state_finite = all(bool(torch.isfinite(value).all()) for state in optimizer.state.values()
                       for value in state.values() if isinstance(value,torch.Tensor))
    precision.update(gradients_finite=gradients_finite,parameters_after_step_finite=parameters_finite,
        optimizer_state_finite=state_finite,pass_=precision_ok and parameters_finite and state_finite)
    if not parameters_finite or not state_finite:
        raise RuntimeError("STOP: nonfinite post-update parameter or optimizer state")
    free_after, _ = torch.cuda.mem_get_info()
    peak_allocated, peak_reserved = torch.cuda.max_memory_allocated(),torch.cuda.max_memory_reserved()
    conservative_free = min(free_after,free_before-max(0,peak_reserved-reserved_before))
    memory_safe = safe_memory(peak_reserved,dedicated,conservative_free,.20)
    optimizer_cuda_bytes = sum(value.numel()*value.element_size() for state in optimizer.state.values()
        for value in state.values() if isinstance(value,torch.Tensor) and value.is_cuda)
    MiB = 1024**2
    memory = {"run":run,"global_update":u,"allocated_MiB":torch.cuda.memory_allocated()/MiB,
        "reserved_MiB":torch.cuda.memory_reserved()/MiB,"device_free_MiB":free_after/MiB,
        "peak_allocated_MiB":peak_allocated/MiB,"peak_reserved_MiB":peak_reserved/MiB,
        "pre_device_free_MiB":free_before/MiB,"pre_reserved_MiB":reserved_before/MiB,
        "estimated_min_device_free_MiB":conservative_free/MiB,"dedicated_total_MiB":dedicated/MiB,
        "mem_get_info_total_MiB":reported_total/MiB,"reserved_fraction":peak_reserved/dedicated,
        "estimated_free_fraction":conservative_free/dedicated,"safe_20pct":memory_safe,
        "optimizer_state_first_initialized":u==1,"optimizer_state_parameter_tensors":len(optimizer.state),
        "optimizer_cuda_state_MiB":optimizer_cuda_bytes/MiB}
    step = {"run":run,"global_update":u,"LR":lr,"LR_hex":lr.hex(),"loss":float(loss.total.detach()),
        "loss_hex":float(loss.total.detach()).hex(),"L_occ":float(loss.occurrence.detach()),"L_qr":float(loss.conditional_quantile.detach()),
        "pre_clip_norm":float(before_clip),"pre_clip_norm_hex":float(before_clip).hex(),
        "clip_threshold":5.,"clipping_triggered":triggered,"post_clip_norm":float(after_clip),
        "post_clip_interpretation":"PyTorch coefficient=min(1,5/(pre_norm+1e-6)); foreach=False, no GradScaler",
        "actual_optimizer_group_LRs":[g["lr"] for g in optimizer.param_groups],
        "valid_Yunnan_supervised_pixels":loss.valid_supervised_count,"rainy_pixels":loss.rainy_valid_count,
        "sample_ids":[sample.sample_id for sample in samples],"step_seconds":time.perf_counter()-began,
        "scope":"ENGINEERING_ONLY","optimizer_step_performed":True}
    if any(value!=lr for value in step["actual_optimizer_group_LRs"]):
        raise RuntimeError("Actual optimizer LR differs from stateless schedule")
    # Release all graphs/tensors before the caller starts another update or destroys the model.
    del output,loss,batch,qlog,qphysical,before_clip,returned,after_clip
    return step,memory,precision


def finish_run(model,optimizer,steps,initial_hash):
    return {"status":"PASS","initial_model_state_sha256":initial_hash,
        "model_state_sha256":state_digest(model.state_dict()),"optimizer_state_sha256":state_digest(optimizer.state_dict()),
        "RNG_states_sha256":state_digest(capture_rng()),"global_update":3,"steps":steps,
        "seed":2026,"scope":"ENGINEERING_ONLY","formal_epoch_completed":False}


def exact_comparison(a,b):
    fields_ = ("global_update","LR","loss","pre_clip_norm","clipping_triggered")
    return {"steps":[{"global_update":left["global_update"],"exact":all(left[key]==right[key] for key in fields_),
                      "field_exact":{key:left[key]==right[key] for key in fields_}}
                     for left,right in zip(a["steps"],b["steps"])],
        "model_state_exact":a["model_state_sha256"]==b["model_state_sha256"],
        "optimizer_state_exact":a["optimizer_state_sha256"]==b["optimizer_state_sha256"],
        "initial_state_exact":a["initial_model_state_sha256"]==b["initial_model_state_sha256"],
        "RNG_states_exact":a["RNG_states_sha256"]==b["RNG_states_sha256"]}


def remove_owned_temporary(path,root,owned):
    path = path.resolve()
    if path not in owned or not path.is_relative_to(root.resolve()) or not root.name.startswith("yuntapr_phase_a_"):
        raise RuntimeError("Refusing cleanup outside owned temporary checkpoint root")
    path.unlink(missing_ok=False)
    owned.remove(path)


def gpu(out):
    if not read(out/"preliminary_test_summary.json")["pass"] or read(out/"scheduler_finalfit_replay.json")["status"]!="PASS":
        raise RuntimeError("Preliminary scheduler gate must pass first")
    identity = read(out/"protocol_identity.json")
    config = load_protocol(expected_sha256=identity["protocol_sha256"])
    unchanged_baseline()
    if os.environ.get("PYTHONHASHSEED")!="2026" or os.environ.get("CUBLAS_WORKSPACE_CONFIG")!=":4096:8":
        raise RuntimeError("Set the reproducibility environment before launching Python")
    if not torch.cuda.is_available() or torch.cuda.get_device_capability()!=(12,0):
        raise RuntimeError("Verified SM120 CUDA device required")
    seed_reproducibility()
    packages = {}
    for name in ("torch","numpy","netCDF4","xarray","zarr","numcodecs","pyarrow","h5py","h5netcdf"):
        try:
            packages[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name]=None
    environment = {"python":sys.executable,"Python_version":sys.version,"packages":packages,
        "torch_CUDA_runtime":torch.version.cuda,"GPU":torch.cuda.get_device_name(),"capability":torch.cuda.get_device_capability(),
        "dedicated_total_MiB":torch.cuda.get_device_properties(0).total_memory/1024**2,
        "driver":subprocess.check_output(["nvidia-smi","--query-gpu=driver_version","--format=csv,noheader"],text=True).strip(),
        "PYTHONHASHSEED":os.environ["PYTHONHASHSEED"],"CUBLAS_WORKSPACE_CONFIG":os.environ["CUBLAS_WORKSPACE_CONFIG"],
        "deterministic_algorithms":torch.are_deterministic_algorithms_enabled(),
        "deterministic_warn_only":torch.is_deterministic_algorithms_warn_only_enabled(),
        "cudnn_deterministic":torch.backends.cudnn.deterministic,"cudnn_benchmark":torch.backends.cudnn.benchmark,
        "cuda_matmul_allow_tf32":torch.backends.cuda.matmul.allow_tf32,"cudnn_allow_tf32":torch.backends.cudnn.allow_tf32,
        "float32_matmul_precision":torch.get_float32_matmul_precision(),"CPU_threads":torch.get_num_threads(),
        "headroom_method":"Both peak reserved<=80% dedicated and min(post-free,pre-free-incremental-peak-reservation)>=20% dedicated",
        "formal_training_authorized":False}
    save(out/"environment.json",environment)
    fixtures, batch_identities = real_fixtures(out,config)
    steps_all,memory_all,precision_all = [],[],[]
    def update(model,optimizer,observed,samples,u,run):
        step,memory,precision=perform_update(model,optimizer,observed,samples,batch_identities[u-1]["CPU_tensor_sha256"],u,run,config)
        steps_all.append(step); memory_all.append(memory); precision_all.append(precision)
        save(out/("update_"+run+"_"+str(u)+".json"),{"step":step,"memory":memory,"precision":precision})
        print(json.dumps({"run":run,"update":u,"loss":step["loss"],"LR":step["LR"],
                          "peak_reserved_MiB":memory["peak_reserved_MiB"],"free_fraction":memory["estimated_free_fraction"],
                          "safe_20pct":memory["safe_20pct"]}),flush=True)
        if not memory["safe_20pct"]:
            raise RuntimeError("STOP: optimizer dedicated VRAM headroom below20%; batch unchanged")
        return step
    runs = {}
    try:
        for run in ("A","B"):
            clean_cuda()
            model,optimizer,observed,groups=fresh_model()
            initial_hash=state_digest(model.state_dict())
            if run=="A":
                save(out/"parameter_groups.json",{**groups,"head_pin":head_pin(model),"status":"PASS"})
            steps=[update(model,optimizer,observed,samples,u,run) for u,samples in enumerate(fixtures,1)]
            runs[run]=finish_run(model,optimizer,steps,initial_hash)
            save(out/("determinism_run_"+run.lower()+".json"),runs[run])
            del model,optimizer,observed
            clean_cuda()
        comparison=exact_comparison(runs["A"],runs["B"])
        comparison.update(run_a_model_state_sha256=runs["A"]["model_state_sha256"],run_b_model_state_sha256=runs["B"]["model_state_sha256"])
        comparison["bit_exact_pass"]=all(row["exact"] for row in comparison["steps"]) and all(comparison[key] for key in
            ("model_state_exact","optimizer_state_exact","initial_state_exact","RNG_states_exact"))
        save(out/"determinism_comparison.json",comparison)
        if not comparison["bit_exact_pass"]:
            raise RuntimeError("STOP: Run A/B bit-exact replay mismatch")
        model,optimizer,observed,groups=fresh_model()
        initial_hash=state_digest(model.state_dict())
        c_steps=[update(model,optimizer,observed,fixtures[u-1],u,"C") for u in (1,2)]
        metadata=checkpoint_metadata(config,identity["protocol_sha256"],groups,environment,2)
        temp_root=Path(tempfile.mkdtemp(prefix="yuntapr_phase_a_"+out.name+"_")).resolve()
        if not str(temp_root).isascii() or not temp_root.is_relative_to(Path(tempfile.gettempdir()).resolve()):
            raise RuntimeError("Owned ASCII temporary checkpoint root required")
        owned=set()
        checkpoint=temp_root/"step2_engineering_only.pt"
        checkpoint_sha=None
        guard_rows=[]
        try:
            rng=capture_rng()
            payload={"metadata":metadata,"model_state_dict":model.state_dict(),"optimizer_state_dict":optimizer.state_dict(),
                "rng_states":rng,"python_rng_state":rng["python"],"numpy_rng_state":rng["numpy"],
                "torch_cpu_rng_state":rng["torch_cpu"],"torch_cuda_rng_state":rng["torch_cuda"]}
            present=set(payload)|set(metadata)
            if not set(config["checkpoint"]["required_schema"]).issubset(present):
                raise RuntimeError("Incomplete temporary checkpoint schema")
            owned.add(checkpoint.resolve())
            torch.save(payload,checkpoint)
            checkpoint_sha=sha256(checkpoint)
            checkpoint_bytes=checkpoint.stat().st_size
            del payload,rng
            model_reference,optimizer_reference=weakref.ref(model),weakref.ref(optimizer)
            del model,optimizer,observed
            clean_cuda()
            destroyed=model_reference() is None and optimizer_reference() is None
            if not destroyed:
                raise RuntimeError("Original model/optimizer were not destroyed")
            model,optimizer,observed,recreated_groups=fresh_model()
            if recreated_groups!=groups:
                raise RuntimeError("Recreated group identity mismatch")
            # Three serialized corrupted copies. Wrappers prove no state/RNG application occurred.
            for key in ("protocol_sha256","normalization_artifact_sha256","scientific_contract_sha256"):
                corrupt=temp_root/("corrupt_"+key+".pt")
                payload=torch.load(checkpoint,map_location="cpu",weights_only=False)
                payload["metadata"][key]="0"*64
                owned.add(corrupt.resolve())
                torch.save(payload,corrupt)
                del payload
                original_model_hash=state_digest(model.state_dict())
                original_optimizer_hash=state_digest(optimizer.state_dict())
                original_rng_hash=state_digest(capture_rng())
                with patch.object(model,"load_state_dict",wraps=model.load_state_dict) as model_load, \
                     patch.object(optimizer,"load_state_dict",wraps=optimizer.load_state_dict) as optimizer_load, \
                     patch("yuntapr.training.phase_a_protocol.restore_rng") as rng_restore:
                    try:
                        load_temporary_checkpoint(corrupt,model,optimizer,metadata)
                    except ValueError as exc:
                        error=str(exc)
                    else:
                        raise RuntimeError("STOP: corrupt provenance accepted")
                    state_untouched=(model_load.call_count==optimizer_load.call_count==rng_restore.call_count==0
                        and state_digest(model.state_dict())==original_model_hash
                        and state_digest(optimizer.state_dict())==original_optimizer_hash
                        and state_digest(capture_rng())==original_rng_hash)
                    guard_rows.append({"mutated_metadata_key":key,"error":error,"rejected":True,
                        "rejected_before_state_application":state_untouched,"model_load_calls":model_load.call_count,
                        "optimizer_load_calls":optimizer_load.call_count,"rng_restore_calls":rng_restore.call_count,
                        "corrupted_file_sha256":sha256(corrupt)})
                remove_owned_temporary(corrupt,temp_root,owned)
                if not state_untouched or key not in error:
                    raise RuntimeError("STOP: provenance guard did not fail loudly before state application")
            save(out/"checkpoint_provenance_guard.json",{"status":"PASS","cases":guard_rows,
                "actual_serialized_loader_test":True,"pass":all(row["rejected_before_state_application"] for row in guard_rows),
                "frozen_artifacts_modified":False})
            global_update=load_temporary_checkpoint(checkpoint,model,optimizer,metadata)
            if global_update!=2:
                raise RuntimeError("Restored global_update mismatch")
            c_steps.append(update(model,optimizer,observed,fixtures[2],global_update+1,"C"))
            runs["C"]=finish_run(model,optimizer,c_steps,initial_hash)
            save(out/"determinism_run_c.json",runs["C"])
            c_compare=exact_comparison(runs["A"],runs["C"])
            exact=all(row["exact"] for row in c_compare["steps"]) and all(c_compare[key] for key in
                ("model_state_exact","optimizer_state_exact","initial_state_exact","RNG_states_exact"))
            remove_owned_temporary(checkpoint,temp_root,owned)
            if owned:
                raise RuntimeError("Owned checkpoint files remain")
            temp_root.rmdir()  # only this verified, empty, non-recursive owned root
            save(out/"resume_checkpoint_test.json",{"status":"PASS" if exact else "FAIL","exact_pass":exact,
                "checkpoint_sha256":checkpoint_sha,"checkpoint_bytes":checkpoint_bytes,"global_update":3,
                "checkpoint_global_update":2,"checkpoint_completed_epoch":0,"schema_complete":True,
                "engineering_partial_update_exception":True,"original_model_optimizer_destroyed":destroyed,
                "temporary_checkpoint_deleted":not checkpoint.exists(),"temporary_root_deleted":not temp_root.exists(),
                "optimizer_logically_equivalent":c_compare["optimizer_state_exact"],"comparison":c_compare,
                "restored": ["model", "optimizer", "RNG", "global_update", "protocol identity"],
                "formal_checkpoint_created":False})
            if not exact:
                raise RuntimeError("STOP: temporary checkpoint resume was not bit-exact")
            del model,optimizer,observed
            clean_cuda()
        finally:
            for path in list(owned):
                if path.exists():
                    remove_owned_temporary(path,temp_root,owned)
            if temp_root.exists() and not owned:
                temp_root.rmdir()
    finally:
        table(out/"optimizer_steps.csv",steps_all)
        table(out/"optimizer_memory.csv",memory_all)
        save(out/"precision_checks.json",{"status":"PASS" if len(precision_all)==9 and all(row["pass_"] for row in precision_all) else "INCOMPLETE_OR_FAILED",
            "checks":precision_all,"expected_updates":9,"completed_updates":len(precision_all),"GradScaler":False})
    if len(steps_all)!=9:
        raise RuntimeError("Exactly nine engineering updates required")
    save(out/"gpu_dryrun_status.json",{"status":"PASS","actual_optimizer_steps":9,"real_unique_samples":6,
        "all_memory_safe_20pct":all(row["safe_20pct"] for row in memory_all),"B0_FORMAL_TRAINING_STARTED":False,
        "FORMAL_TRAINING_AUTHORIZED":False})
    print("REAL_OPTIMIZER_REPLAY_RESUME_GATE_PASS",flush=True)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("phase", choices=("initialize", "preliminary", "gpu"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--scope", required=True)
    args = parser.parse_args()
    require_engineering_scope(args.scope)
    if Path(sys.executable).resolve() != PYTHON.resolve():
        raise RuntimeError("Verified CUDA interpreter required")
    torch.set_num_threads(2)
    try:
        if args.phase == "initialize":
            initialize(args.out)
        else:
            if not (args.out/"protocol_identity.json").is_file():
                raise RuntimeError("Initialize an independent run first")
            save(args.out/(args.phase+"_started.json"), {"UTC":datetime.now(timezone.utc).isoformat(),
                "script_sha256":sha256(Path(__file__)),"python":sys.executable,"argv":sys.argv,"scope":args.scope})
            globals()[args.phase](args.out)
        save(args.out/(args.phase+"_invocation.json"), {"UTC": datetime.now(timezone.utc).isoformat(),
            "python": sys.executable, "argv": sys.argv, "script_sha256": sha256(Path(__file__)), "scope": args.scope})
    except Exception as exc:
        if args.out.is_dir():
            save(args.out/(args.phase+"_failure.json"), {"UTC":datetime.now(timezone.utc).isoformat(),
                "error":repr(exc),"traceback":traceback.format_exc(),"status":"STOPPED","scope":args.scope,
                "B0_FORMAL_TRAINING_STARTED":False,"FORMAL_TRAINING_AUTHORIZED":False})
        raise


if __name__ == "__main__":
    main()
