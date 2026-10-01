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
        and autocast_enabled and autocast_dtype=="torch.bfloat16"
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


def tests(out):
    if read(out/"gpu_dryrun_status.json")["status"]!="PASS":
        raise RuntimeError("Real GPU gates must pass before the complete test suite")
    os.environ["YUNTAPR_PROTOCOL_DRYRUN_EVIDENCE"]=str(out.resolve())
    suites=("scientific_freeze","b0_skeleton","development_qc","scientific_freeze_v1_1",
        "quantile_numerical_closure","training_environment_audit","gpu_training_feasibility",
        "phase_a_protocol_prefreeze","phase_a_protocol_v1","phase_a_optimizer_resume")
    rows=[]
    with (out/"test_results.txt").open("x",encoding="utf-8",newline="\n") as stream:
        for directory in suites:
            stream.write("\nSUITE "+directory+"\n")
            suite=unittest.TestLoader().discover(str(ROOT/"tests"/directory))
            result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
            row={"suite":directory,"tests":result.testsRun,"failures":len(result.failures),
                "errors":len(result.errors),"skipped":len(result.skipped),"pass":result.wasSuccessful() and not result.skipped}
            rows.append(row)
            stream.flush()
            print(json.dumps(row),flush=True)
            if not row["pass"]:
                break
    history=sum(row["tests"] for row in rows[:8])
    passed=len(rows)==10 and all(row["pass"] for row in rows) and history==137
    save(out/"test_summary.json",{"status":"PASS" if passed else "FAIL","suites":rows,
        "historical_tests_actually_executed":history,"protocol_tests":rows[8]["tests"] if len(rows)>8 else 0,
        "optimizer_resume_evidence_tests":rows[9]["tests"] if len(rows)>9 else 0,
        "total_tests":sum(row["tests"] for row in rows),"pass":passed,"skipped_count":sum(row["skipped"] for row in rows),
        "historical_evidence_substituted_for_execution":False,"additional_optimizer_steps_during_tests":0})
    if not passed:
        raise RuntimeError("STOP: full required test suite failure")


def finalize(out):
    identity=read(out/"protocol_identity.json")
    config=load_protocol(expected_sha256=identity["protocol_sha256"])
    preserved=unchanged_baseline()
    if preserved!=identity["unchanged_baseline_files_sha256"]:
        raise RuntimeError("Historical disk SHA changed during this run")
    for kind in ("protocol","document"):
        if sha256(ROOT/identity[kind+"_path"])!=identity[kind+"_sha256"]:
            raise RuntimeError("Frozen protocol identity changed")
    boundary=read(out/"lr_schedule_boundary_tests.json")
    finalfit=read(out/"scheduler_finalfit_replay.json")
    preliminary_result=read(out/"preliminary_test_summary.json")
    gpu_status=read(out/"gpu_dryrun_status.json")
    precision=read(out/"precision_checks.json")
    ab=read(out/"determinism_comparison.json")
    resume=read(out/"resume_checkpoint_test.json")
    guard=read(out/"checkpoint_provenance_guard.json")
    test_result=read(out/"test_summary.json")
    def rows(name):
        with (out/name).open(encoding="utf-8",newline="") as stream:
            return list(csv.DictReader(stream))
    step_rows,memory_rows=rows("optimizer_steps.csv"),rows("optimizer_memory.csv")
    gates={"SCHEDULER_BOUNDARY_PASS":boundary["status"]=="PASS" and preliminary_result["pass"],
        "SCHEDULER_FINALFIT_REPLAY_PASS":finalfit["status"]=="PASS" and all(row["exact"] for row in finalfit["epochs"]),
        "DRYRUN_OPTIMIZER_STEP_PASS":gpu_status["status"]=="PASS" and len(step_rows)==9 and gpu_status["actual_optimizer_steps"]==9,
        "DRYRUN_MEMORY_SAFE":len(memory_rows)==9 and all(row["safe_20pct"]=="True" for row in memory_rows),
        "PRECISION_GATE_PASS":precision["status"]=="PASS" and precision["completed_updates"]==9,
        "DETERMINISTIC_REPLAY_PASS":ab["bit_exact_pass"],
        "RESUME_REPLAY_EXACT_PASS":resume["exact_pass"] and resume["temporary_checkpoint_deleted"] and resume["temporary_root_deleted"],
        "CHECKPOINT_PROVENANCE_GUARD_PASS":guard["pass"] and guard["actual_serialized_loader_test"],
        "FULL_TEST_SUITE_PASS":test_result["pass"] and test_result["historical_tests_actually_executed"]==137}
    if not all(gates.values()):
        raise RuntimeError("Do not mark an incomplete gate as PASS: "+repr(gates))
    from benchmark_b0_gpu_feasibility import STAGING
    if list((STAGING/f"gpu_{out.name}").rglob("yuntapr_b0_*.nc")):
        raise RuntimeError("Owned staging copies remain")
    if list(Path(tempfile.gettempdir()).glob("yuntapr_phase_a_"+out.name+"_*")):
        raise RuntimeError("Owned checkpoint temporary directory remains")
    # Preserve this turn's zero-update harness attempt as immutable supporting history.
    attempt=ROOT/"docs/phase_a_optimizer_dryrun/runs/run_20261001T025132Z"
    attempt_manifest=read(attempt/"manifest.json")
    for name,info in attempt_manifest["public_files"].items():
        if sha256(attempt/name)!=info["sha256"]:
            raise RuntimeError("Retained zero-update attempt changed")
    # Recover the exact GPU invocation source, before later tests/report phases were added.
    snapshot=(attempt/"attempt_script_snapshot.py").read_bytes().replace(
        b'and precision["backbone_autocast_output"]=="torch.bfloat16" and autocast_enabled and autocast_dtype=="torch.bfloat16"',
        b'and autocast_enabled and autocast_dtype=="torch.bfloat16"')
    if hashlib.sha256(snapshot).hexdigest()!=read(out/"gpu_started.json")["script_sha256"]:
        raise RuntimeError("GPU invocation source reconstruction mismatch")
    with (out/"gpu_script_snapshot.py").open("xb") as stream:
        stream.write(snapshot)
    final={"run_status":"PROTOCOL_ENGINEERING_VALIDATED",**gates,
        "PROTOCOL_ENGINEERING_VALIDATED":True,"PHASE_A_TRAINING_PROTOCOL_VERSION":"v1.0",
        "PHASE_A_TRAINING_PROTOCOL_FROZEN":True,"HEAD_IMPLEMENTATION_DETAIL_PINNED":True,
        "FOCAL_ALPHA":.5,"FOCAL_GAMMA":2.,"OPTIMIZER":"AdamW","BASE_LR":1e-4,"WEIGHT_DECAY":1e-4,
        "TRAIN_PHYSICAL_BATCH":2,"GRADIENT_ACCUMULATION":1,"EFFECTIVE_BATCH":2,"AMP_MODE":"BF16",
        "VALIDATION_BATCH":8,"NUM_WORKERS":2,"MAX_EPOCHS":50,"WARMUP_EPOCHS":1,"MIN_LR":1e-6,
        "EARLY_STOP_PATIENCE":8,"EARLY_STOP_MIN_DELTA":1e-4,"GRAD_CLIP_NORM":5.,"PRIMARY_SEED":2026,
        "CHECKPOINT_METRIC":"global_val_core_loss","B0_FORMAL_TRAINING_STARTED":False,"FORMAL_TRAINING_AUTHORIZED":False,
        "previous_run":"STOPPED_SCHEDULER_BOUNDARY_FAILURE","current_correction":"WARMUP_EVALUATION_ORDER_ONLY",
        "scientific_parameters_changed":False,"protocol_version_changed":False,"actual_optimizer_steps":9,
        "real_unique_2023_samples":6,"2025_pixels_read":False,"Phase_B_executed":False,
        "Phase_B_normalization_computed":False,"formal_checkpoints_created":0,"temporary_checkpoint_files_remaining":0,
        "owned_staging_copies_remaining":0,"full_test_count":test_result["total_tests"],"skipped_test_count":0,
        "retained_zero_update_harness_attempt":attempt.relative_to(ROOT).as_posix(),
        "retained_initial_test_runner_attempt":"tests_initial",
        "execution_scope":"ENGINEERING_ONLY"}
    save(out/"final_status.json",final)
    save(out/"scientific_identity_preservation.json",{"baseline":BASELINE,
        "protocol_sha256":identity["protocol_sha256"],"document_sha256":identity["document_sha256"],
        "unchanged_baseline_file_count":len(preserved),"allowed_existing_file_change":IMPLEMENTATION,
        "allowed_patch":"return 1e-4 * u / W => return 1e-4 * (u / W)",
        "previous_scheduler_failure_run_immutable":True,"scientific_parameters_changed":False,
        "protocol_version_changed":False,"zero_update_attempt_manifest_sha256":sha256(attempt/"manifest.json")})
    worst_reserved=max(float(row["peak_reserved_MiB"]) for row in memory_rows)
    minimum_free=min(float(row["estimated_min_device_free_MiB"]) for row in memory_rows)
    minimum_free_fraction=min(float(row["estimated_free_fraction"]) for row in memory_rows)
    reader=read(out/"real_sample_read_audit.json")
    group_info=read(out/"parameter_groups.json")
    environment=read(out/"environment.json")
    report=["# PHASE_A_OPTIMIZER_DRYRUN_REPORT","",
        "结果：**PROTOCOL_ENGINEERING_VALIDATED = true**。Phase-A protocol 仍为 v1.0；本轮仅数值实现修正与 ENGINEERING_ONLY dry-run，正式训练未启动、未授权。","",
        f"Run `{out.name}`；baseline `{BASELINE}`。","",
        "## 科学合同与唯一已有源码修正","",
        "研究者批准的唯一 scheduler 修正为 warmup 求值顺序 `(base_lr*u)/W` → `base_lr*(u/W)`。Cosine 部分未变，无 clamp/min/max/round/Decimal/isclose 或 tolerance 代替 exact LR 判据。所有 alpha/gamma、AdamW、weight decay、LR、batch、AMP、warmup/horizon、epoch/early-stop、seed、checkpoint metric 和 D1–D8 保持不变。","",
        f"`previous_run=STOPPED_SCHEDULER_BOUNDARY_FAILURE`；`current_correction=WARMUP_EVALUATION_ORDER_ONLY`；`scientific_parameters_changed=false`；`protocol_version_changed=false`。旧 run_20261001T023702Z 和其全部产物未改写。除 scheduler 这一行外，{len(preserved)} 个基线文件逐一 Git blob / disk SHA 核验保持不变。","",
        f"Protocol YAML SHA256 `{identity['protocol_sha256']}`。文档 SHA256 `{identity['document_sha256']}`。没有修改任何冻结文档或 YAML；完整继承来源/版本/hash见 protocol_identity.json。","",
        "## Exact scheduler gate","",
        "原16项 preliminary tests 原样实际执行，16/16 PASS。完整检查5860个warmup点和287140个cosine点：warmup严格递增且0<LR<=base，cosine单调非增且min<=LR<=base；只做数学检查，没有执行293000次模型更新。","",
        "| Update | LR | Float hex |","|---:|---:|---|"]
    report += [f"| {row['u']} | {row['LR']!r} | `{row['hex']}` |" for row in boundary["boundaries"]]
    report += ["","Phase-B仅验证同epoch进度的函数等式；epoch=1,2,10,25,49,50、steps/epoch=8000与Phase-A5860的LR及hex全部精确相等，absolute error=0。保持50-epoch horizon，未运行Phase B、未计算新normalization。详见 scheduler_finalfit_replay.json。","",
        "## 六个真实样本与读取链","",
        "完整11720行Train manifest仅用于固定身份索引；按[0,2343,4687,7031,9375,11719]等间隔选6个2023 eligible样本，读取前登记，未按雨量/模型结果筛选。3组batch2。原始B13/IMERG经英文staging、正式QC、pinned Phase-A normalization、tensor/CUDA/B0/SP04/heads进入 loss/backward/clipping/AdamW。2025像元读取数为0。","",
        f"worker=2，各自独立ASCII root，prefetch=1、pin_memory=false、persistent_workers=false；one_file_at_a_time、700MiB cap，12次B13/IMERG读取均核验既有source SHA与copy SHA、size和cleanup。读取wall={reader['reader_wall_seconds']:.3f}s；临时staging副本剩余0。H永久只读。六个正式reader结果仅在RAM中只读重放，无永久数据cache。固定fixture顺序不是正式epoch shuffle实现。时间与归一化身份、读写额外I/O逐样本记录于 real_sample_read_audit.json。","",
        f"Model trainable={group_info['counts']['total']:,}；Conv2d kernels DECAY={group_info['counts']['DECAY_GROUP']:,}、bias/GN NO_DECAY={group_info['counts']['NO_DECAY_GROUP']:,}，互斥且完整。参数名及exact heads详见 parameter_groups.json。","",
        "## 实际 optimizer 与数值精度","",
        "A/B完全fresh seed2026各3步；C完全fresh2步，保存专属临时checkpoint、销毁model/optimizer、重建并恢复后第3步。总共恰好9次ENGINEERING_ONLY optimizer.step，无额外seed、无完整epoch拟合。AdamW betas(.9,.999)、eps1e-8、decay1e-4仅Conv kernel，foreach/fused及其他冻结布尔参数为false。","",
        "每步参数/raw quantile=float32，BF16 autocast开启，qlog/qphysical/pinball=float64；loss、grad、post-step parameters/optimizer state全部finite，qlog及physical quantile严格单调，crossing=0。GradScaler未使用。","",
        "| Run A update | LR | Core loss | Pre-clip norm | Post-clip norm | Clipped |","|---:|---:|---:|---:|---:|---|"]
    report += [f"| {row['global_update']} | {row['LR']} | {float(row['loss']):.15g} | {float(row['pre_clip_norm']):.9g} | {float(row['post_clip_norm']):.9g} | {row['clipping_triggered']} |" for row in step_rows if row["run"]=="A"]
    report += ["","顺序为backward→独立pre norm→clip_grad_norm_(max_norm=5,error_if_nonfinite=true)→记录→AdamW.step。clip函数返回norm与独立pre norm exact一致；post-clip解释保留PyTorch的5/(pre+1e-6)比例与float32舍入，不加GradScaler。各步LR在step前设置，两个optimizer组均与stateless函数精确一致。","",
        "## Optimizer VRAM gate","",
        f"Dedicated VRAM={environment['dedicated_total_MiB']:.4f} MiB。9步最大peak reserved={worst_reserved:.1f} MiB；最小保守设备空闲={minimum_free:.3f} MiB（{minimum_free_fraction:.3%}）。全部通过20% dedicated engineering headroom，不改batch。每步同时记录allocated/reserved/device-free及峰值；A/B/C step1记录AdamW moment首次初始化。","",
        "采用两项共同判据：peak reservation<=80% dedicated，以及min(post-device-free, pre-device-free−incremental-peak-reservation)>=20% dedicated。设备空闲含其他应用，峰值空闲为保守估计，不冒称持续采样的瞬时最小值。记录的allocator与CUDA mem_get_info数据来自实际9步，包含本次活跃桌面负载；该短dry-run不是完整epoch热稳定性证据。","",
        "| Run | Update | Peak allocated MiB | Peak reserved MiB | Post device free MiB | Estimated min free MiB | Optimizer CUDA state MiB |","|---|---:|---:|---:|---:|---:|---:|"]
    report += [f"| {row['run']} | {row['global_update']} | {float(row['peak_allocated_MiB']):.2f} | {float(row['peak_reserved_MiB']):.2f} | {float(row['device_free_MiB']):.2f} | {float(row['estimated_min_device_free_MiB']):.2f} | {float(row['optimizer_cuda_state_MiB']):.4f} |" for row in memory_rows]
    report += ["","## Bit-exact replay 与 temporary resume","",
        f"Run A/B每步loss、LR、pre-clip norm、clipping action exact相同。initial/final model（含buffers）、optimizer logical state和全部Python/NumPy/torch CPU/CUDA RNG摘要也相同。A/B final model SHA256=`{ab['run_a_model_state_sha256']}`。未使用tolerance冒充bit-exact。","",
        f"Run C第二步临时checkpoint SHA256=`{resume['checkpoint_sha256']}`，bytes={resume['checkpoint_bytes']:,}。completed_epoch=0、global_update=2，是原协议明确允许的临时schema例外，不是正式epoch checkpoint。完整required schema检查通过，旧model/optimizer weakref确认已销毁；恢复model、optimizer、RNG、global_update及全部provenance后step3与A exact一致，包括optimizer和RNG logical state。临时checkpoint、三份篡改copy及自有空目录均已删除。","",
        "protocol、normalization、scientific contract SHA三种序列化篡改均被实际loader拒绝，错误包含具体字段；mock调用计数确认model.load_state_dict、optimizer.load_state_dict、restore_rng均为0，并交叉核验拒绝前后state/RNG摘要不变。冻结artifact没有被篡改。","",
        "## 全部测试与保留的工程错误历史","",
        f"完整套件本轮实际执行{test_result['total_tests']}项：137项历史+17项protocol+8项新real-evidence测试，全部PASS，skipped=0。原scheduler exact断言未改变；新增测试交叉检查实际步数/参数组、显存state、dtype/clip、replay/resume、serialized provenance与staging。没有用旧历史PASS替代本轮执行，测试没有新增optimizer更新。","",
        "另外保留两次新harness错误供追溯：run_20261001T025132Z 在首个forward后、backward前因审计脚本额外要求terminal backbone dtype=BF16而中止，optimizer更新0次；此要求不在冻结协议中。按实际参数/raw quantile/quantile/pinball与autocast要求修复新harness，末端activation float32继续如实记录。AMP是逐算子混合精度，见[PyTorch2.11 AMP](https://docs.pytorch.org/docs/2.11/amp.html)。未改变模型或AMP参数。该尝试的所有文件和脚本快照已seal，未覆盖。","",
        "本run的 tests_initial 保留第一次完整测试启动日志：137+17先通过，新8项因class路径属性覆盖TestCase.run未启动；只改新测试属性名后重跑完整162项全部通过，未改任何断言或GPU结果。完整初次日志、异常和source快照均保留。","",
        "## 环境、复现与发布边界","",
        f"Python `{environment['python']}`；torch={environment['packages']['torch']}，CUDA runtime={environment['torch_CUDA_runtime']}，GPU={environment['GPU']}，driver={environment['driver']}。完整包版本与process flags见 environment.json。CPU reference venv和其他包未升级。","",
        "启动前设置PYTHONHASHSEED=2026、CUBLAS_WORKSPACE_CONFIG=:4096:8；seed package启用strict deterministic算法、cudnn deterministic，禁benchmark/TF32，float32 matmul precision=highest。全部实际GPU操作支持这些设置，没有warn-only/fallback。","",
        "复现说明见README.md；使用新的run目录依次initialize→preliminary→gpu→tests→finalize。完整原始来源与pinned本地mask需要可读；只发布源码、测试和文本证据，不提交checkpoint、optimizer binary、raw data、wheel、venv或cache。每phase调用hash和实际GPU源码快照记录调用身份，manifest记录最终提交源码及所有新产物SHA。","",
        "## 最终状态","","```json",json.dumps(final,indent=2,ensure_ascii=False),"```","",
        "Protocol工程链验证完成不等于科研收敛、完整Validation或正式训练结果。本轮按授权发布至GitHub main后停止，B0_FORMAL_TRAINING_STARTED=false、FORMAL_TRAINING_AUTHORIZED=false。",""]
    with (out/"PHASE_A_OPTIMIZER_DRYRUN_REPORT.md").open("x",encoding="utf-8",newline="\n") as stream:
        stream.write("\n".join(report))
    with (out/"README.md").open("x",encoding="utf-8",newline="\n") as stream:
        stream.write("""# ENGINEERING_ONLY reproducibility

Use the verified F:\\pytorch\\Research\\.venv-cuda\\Scripts\\python.exe. Before starting Python, set PYTHONHASHSEED=2026, CUBLAS_WORKSPACE_CONFIG=:4096:8, PYTHONUTF8=1, PYTHONDONTWRITEBYTECODE=1; set TEMP/TMP to a writable ASCII path. No package installation is needed.

Use a NEW docs/phase_a_optimizer_dryrun/runs/run_<UTC> directory. Invoke scripts/resume_phase_a_optimizer_v1.py phases initialize, preliminary, gpu, tests, finalize in that order, each with --out <new-run> --scope ENGINEERING_ONLY. Initialization expects the pinned baseline Git commit; on a later checkout audit the explicit baseline rather than bypassing the lock. Never rerun a phase into old evidence or overwrite a failure.

The gpu phase requires the six pinned 2023 sources, frozen local Yunnan mask and previous local per-frame evidence. It reads only those six scenes with two independent bounded ASCII staging workers. B13/IMERG file sizes and SHA are checked; staged copies are deleted after successful decode/QC. Six immutable RAM fixtures are reused to make replay inputs identical. Extra Chinese-path copy/read/integrity/cleanup I/O timings are in real_sample_read_audit.json; they are excluded from optimizer-only step_seconds.

Exactly three updates in each A/B/C run are permitted. Temporary step2 checkpoint and three metadata-corrupted copies live only in an owned ASCII TEMP directory and are removed. A/B or resume mismatch, nonfinite gradients/outputs, quantile crossing, or insufficient20% dedicated VRAM headroom stops execution without changing parameters/batch. No formal training entrypoint, complete training epoch, 2025 pixels, or Phase-B normalization is invoked.

The tests phase actually reruns137 historical +17 protocol +8 real-evidence tests; it requires the generated CUDA artifacts and executes no additional optimizer steps. Full results and initial runner failure are both preserved. Finalize verifies frozen document/config and every historical baseline blob, adds full identity/manifest and then stops. Publishing Git commit and remote API verification occur separately; receipts are kept outside the tracked run to avoid a commit/hash cycle.

Current status is PROTOCOL_ENGINEERING_VALIDATED, with FORMAL_TRAINING_AUTHORIZED=false. The zero-update harness attempt and original scheduler failure remain separately recorded. Do not count their NOT_RUN gates as PASS for those runs.
""")
    print(json.dumps(final),flush=True)


def seal(out):
    final=read(out/"final_status.json")
    if not final["PROTOCOL_ENGINEERING_VALIDATED"]:
        raise RuntimeError("Cannot seal success without actual completed gates")
    unchanged_baseline()
    source_paths=[ROOT/IMPLEMENTATION,Path(__file__),ROOT/"tests/phase_a_optimizer_resume/test_optimizer_resume_evidence.py"]
    # Normalize only current owned run evidence; all historical runs remain untouched.
    for path in out.rglob("*"):
        if path.is_file() and path.suffix in (".json",".md",".csv",".txt"):
            original=path.read_bytes()
            normalized=original.removeprefix(b"\xef\xbb\xbf").replace(b"\r\n",b"\n")
            if original!=normalized:
                path.write_bytes(normalized)
    files={p.relative_to(out).as_posix():{"sha256":sha256(p),"bytes":p.stat().st_size}
           for p in sorted(out.rglob("*")) if p.is_file() and p.name!="manifest.json"}
    save(out/"manifest.json",{"task":"SCHEDULER_NUMERICAL_IMPLEMENTATION_CORRECTION_AND_FULL_OPTIMIZER_DRYRUN_RESUME",
        "baseline":BASELINE,"sealed_UTC":datetime.now(timezone.utc).isoformat(),"public_files":files,
        "source_files":{p.relative_to(ROOT).as_posix():sha256(p) for p in source_paths},
        "protocol_sha256":read(out/"protocol_identity.json")["protocol_sha256"],
        "scientific_parameters_changed":False,"protocol_version_changed":False,"actual_optimizer_steps":9,
        "historical_baseline_files_immutable_except_approved_scheduler_line":True,
        "raw_data_committed":False,"wheel_committed":False,"venv_committed":False,"cache_committed":False,
        "formal_checkpoints_created":0,"temporary_checkpoint_files_remaining":0,"owned_staging_copies_remaining":0,
        "B0_FORMAL_TRAINING_STARTED":False,"FORMAL_TRAINING_AUTHORIZED":False})
    print("SUCCESS_RUN_MANIFEST_SEALED",flush=True)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("phase", choices=("initialize", "preliminary", "gpu", "tests", "finalize"))
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
        if args.phase=="finalize":
            seal(args.out)
    except Exception as exc:
        if args.out.is_dir():
            save(args.out/(args.phase+"_failure.json"), {"UTC":datetime.now(timezone.utc).isoformat(),
                "error":repr(exc),"traceback":traceback.format_exc(),"status":"STOPPED","scope":args.scope,
                "B0_FORMAL_TRAINING_STARTED":False,"FORMAL_TRAINING_AUTHORIZED":False})
        raise


if __name__ == "__main__":
    main()
