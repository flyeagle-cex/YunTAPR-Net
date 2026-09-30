"""Package measured B0 feasibility evidence without starting model training."""
import argparse
import csv
import json
import math
from pathlib import Path

from yuntapr.contracts.loader import REPO_ROOT, load_contract, sha256


BASELINE = "2e243ebfc368ac778538a15413598cbc60fd4f70"
TRAIN_SCENES = 11720
RUN_ROOT = REPO_ROOT / "docs/training_environment_audit/runs"


def read(run, name):
    return json.loads((run / name).read_text(encoding="utf-8"))


def write_json(run, name, data):
    path = run / name
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def write_csv(run, name, rows):
    with (run / name).open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def recommendation(gpu, io):
    workers = {int(r["num_workers"]): r for r in io["worker_summaries"]}
    if not all(workers[n]["status"] == "PASS" for n in (0, 2, 4)):
        raise ValueError("A measured DataLoader worker configuration failed")
    if not gpu["GPU_PRESENT"] or gpu["CUDA_TORCH_AVAILABLE"]:
        raise ValueError("This run requires the observed GPU-present/CPU-only environment")
    return {
        "status": "ENGINEERING_RECOMMENDATION_ONLY",
        "scope": "Future B0 Phase-A Development training planning; not an authorized training configuration",
        "GPU_PRESENT": True,
        "CUDA_TORCH_AVAILABLE": False,
        "TRAINING_ENVIRONMENT_READY": False,
        "CUDA_ENVIRONMENT_ACTION_REQUIRED": True,
        "MAX_TESTED_SAFE_BATCH": "NOT_AVAILABLE",
        "AMP_FEASIBLE": "NOT_TESTED",
        "DATALOADER_IO_READY": True,
        "RECOMMENDED_ENGINEERING_STARTING_POINT": {
            "device": "CUDA_AFTER_SEPARATE_ENVIRONMENT_ACTION_AND_REBENCHMARK",
            "physical_batch_size": "NOT_DETERMINED_CUDA_BENCHMARK_NOT_RUN",
            "gradient_accumulation": "NOT_DETERMINED_CUDA_BENCHMARK_NOT_RUN",
            "amp_enabled": "NOT_DETERMINED_CUDA_BENCHMARK_NOT_RUN",
            "amp_dtype": "NOT_DETERMINED_CUDA_BENCHMARK_NOT_RUN",
            "num_workers": "0_CONSERVATIVE; 2_MEASURED_PROMISING_WITH_INDEPENDENT_PER_WORKER_STAGING",
            "pin_memory": False,
            "persistent_workers": False,
        },
        "worker_evidence": {str(n): {"eight_sample_wall_seconds": workers[n]["total_wall_seconds_including_spawn"],
                                      "samples_per_second": workers[n]["samples_per_second_including_spawn"]}
                            for n in (0, 2, 4)},
        "vram_headroom_target_fraction": "approximately 0.15-0.20; cannot validate without CUDA PyTorch",
        "environment_action": "A separately authorized, compatible CUDA-enabled PyTorch environment is required before GPU feasibility can be measured; this audit did not install or change software.",
        "B0_FORMAL_TRAINING_STARTED": False,
        "FORMAL_TRAINING_AUTHORIZED": False,
    }


def create(run):
    science, engineering = load_contract()
    gpu = read(run, "gpu_inventory.json")
    torch_env = read(run, "pytorch_cuda_environment.json")
    cpu = read(run, "cpu_benchmark.json")
    memory = read(run, "model_memory_static.json")
    io = read(run, "io_breakdown.json")
    disk = read(run, "cpu_ram_storage.json")
    checkpoint = read(run, "checkpoint_storage_estimate.json")
    if science["schema_version"] != "1.1" or engineering["schema_version"] != 4:
        raise ValueError("Unexpected scientific or engineering version")
    if (memory["parameter_count"] != 4329361 or io["sample_count"] != 8 or
            cpu["status"] != "PASS" or cpu["measurement_count"] != 3 or
            not io["DATALOADER_IO_READY"] or torch_env["TORCH_BUILD"] != "CPU_ONLY"):
        raise ValueError("Measured prerequisites are incomplete")

    step = float(cpu["mean_total_step_seconds"])
    io_mean = float(io["mean_end_to_end_sample_io_seconds"])
    if step <= 0 or io_mean <= 0:
        raise ValueError("Non-positive measured time")
    rows = []
    for epochs in (1, 10, 30, 50):
        steps = math.ceil(TRAIN_SCENES / 1)
        compute_only = steps * step * epochs
        serial_components = steps * (step + io_mean) * epochs
        rows.append({
            "status": "ENGINEERING_ESTIMATE_ONLY", "device": "cpu",
            "physical_batch": 1, "training_samples": TRAIN_SCENES,
            "steps_per_epoch": steps, "epochs_illustrative_only": epochs,
            "measured_step_seconds_mean": step, "measured_sample_io_seconds_mean": io_mean,
            "compute_only_seconds": compute_only,
            "serial_measured_components_seconds": serial_components,
            "compute_only_minutes": compute_only / 60,
            "serial_measured_components_minutes": serial_components / 60,
            "compute_only_hours": compute_only / 3600,
            "serial_measured_components_hours": serial_components / 3600,
            "uncertainty": "Illustrative component arithmetic, not a confidence interval; no optimizer.step, validation, epochs, scheduling, or coupled I/O/compute measured",
        })
    write_csv(run, "epoch_time_estimates.csv", rows)

    accumulation = []
    for physical, accum in ((1, 4), (2, 2), (4, 1)):
        accumulation.append({
            "status": "ENGINEERING_CANDIDATE_ONLY", "physical_batch": physical,
            "accumulation_steps": accum, "effective_batch_arithmetic": physical * accum,
            "gpu_feasibility": "NOT_ASSESSED_CUDA_UNAVAILABLE",
            "memory_limited": "UNKNOWN", "needed": "UNKNOWN",
            "formal_effective_batch_frozen": False,
        })
    write_csv(run, "gradient_accumulation_candidates.csv", accumulation)

    rec = recommendation(gpu, io)
    write_json(run, "engineering_recommendation.json", rec)

    device = gpu["gpus"][0]
    status = [
        "SCIENTIFIC_FREEZE_VERSION = v1.1",
        "QUANTILE_NUMERICAL_STABILITY_CLOSED = true",
        "PHASE_A_SAMPLE_ELIGIBILITY_READY = true",
        "PHASE_A_NORMALIZATION_READY = true",
        "GPU_PRESENT = true",
        "CUDA_TORCH_AVAILABLE = false",
        "TRAINING_ENVIRONMENT_READY = false",
        "CUDA_ENVIRONMENT_ACTION_REQUIRED = true",
        "MAX_TESTED_SAFE_BATCH = NOT_AVAILABLE",
        "AMP_FEASIBLE = NOT_TESTED",
        "DATALOADER_IO_READY = true",
        "B0_FORMAL_TRAINING_STARTED = false",
        "FORMAL_TRAINING_AUTHORIZED = false",
    ]
    report = f"""# B0 Training Environment + Memory Feasibility Audit v1

Run: `{run.name}`. Baseline GitHub commit: `{BASELINE}`. Scope: `ENGINEERING_ONLY`. Scientific Freeze v1.1 and engineering v4 were loaded and verified. This run performed forward/backward and I/O smoke measurements; no optimizer was created or stepped, no checkpoint was produced, and no formal training was started.

## Decision

**TRAINING_ENVIRONMENT_READY = false.** `nvidia-smi` confirms one {device['name']} with {device['total_vram_mib']} MiB total VRAM, driver {device['driver_version']}, compute capability {device['compute_capability']}. At inventory time {device['current_memory_used_mib']} MiB was occupied and about {device['current_memory_free_estimate_mib']} MiB free. The fixed interpreter `{torch_env['python_path']}` has PyTorch `{torch_env['torch_version']}` with `torch.version.cuda = null`, CUDA available false, and zero PyTorch CUDA devices. NVIDIA's driver-reported CUDA ceiling {gpu['nvidia_driver_reported_max_cuda_version']} is **not** a PyTorch CUDA runtime. CUDA batch/AMP/validation benchmarks were `NOT_RUN_CUDA_UNAVAILABLE`; no safe GPU batch, GPU throughput, AMP dtype, or 15–20% reserved-memory headroom can be established. Establishing a compatible CUDA-enabled PyTorch environment requires a separate action; no package, driver, or CUDA component was changed in this audit.

## Measured hardware and model

- Windows: {read(run, 'system_environment.json')['os']}, build {read(run, 'system_environment.json')['windows_build']}; CPU {disk['cpu_model']} ({disk['physical_cores']} physical / {disk['logical_cores']} logical cores); RAM {disk['system_ram_total_bytes']/2**30:.2f} GiB total, {disk['system_ram_available_bytes']/2**30:.2f} GiB available at inventory. `cpu_ram_storage.json` records C:, F:, H: filesystems, capacities, free space, and source/staging availability. H: and F: raw files were read only.
- `B0Model`: {memory['parameter_count']:,} trainable parameters, all float32. Parameters {memory['parameters_bytes']/2**20:.2f} MiB, theoretical gradients {memory['gradients_theoretical_bytes']/2**20:.2f} MiB, theoretical SGD no-momentum state 0 MiB (momentum {memory['sgd_momentum_theoretical_optimizer_state_bytes']/2**20:.2f} MiB), theoretical AdamW state {memory['adamw_theoretical_optimizer_state_bytes']/2**20:.2f} MiB. These exclude activations and allocator/workspace overhead. No optimizer was instantiated.
- Full input `[1,1,501,501]`; outputs rain logits `[1,1,100,100]`, conditional quantiles `[1,32,100,100]`. Model weights remain float32; qlog, qphysical, and conditional pinball were verified float64 with finite outputs, loss, and gradients.
- CPU batch 1: 1 warmup, 3 measured forward/loss/backward passes, 2 PyTorch threads. Mean forward {cpu['mean_forward_seconds']:.3f} s, loss {cpu['mean_loss_seconds']:.4f} s, backward {cpu['mean_backward_seconds']:.3f} s, total {step:.3f} s. Lifetime peak process working set {cpu['memory_after']['process_lifetime_peak_working_set_bytes']/2**30:.2f} GiB; this includes initialization and warmup and is not an isolated step peak. The first attempt could not read this process counter and is preserved as `cpu_benchmark_memory_unavailable_attempt.json`; the corrected rerun is `cpu_benchmark.json`.

## Eight real final-eligible 2023 samples

The benchmark used hash-verified final-eligible 2023 manifest entries spread across the available Train period. Each sample followed raw H: B13 → bounded SHA-verified ASCII staging → netCDF read → formal QC → pinned Phase-A normalization → tensor; V07 Final IMERG was also read with verified staging. Original data were unchanged, and all owned temporary copies were cleaned. With 8 samples, DataLoader workers 0 / 2 / 4 took respectively {io['worker_summaries'][0]['total_wall_seconds_including_spawn']:.2f} / {io['worker_summaries'][1]['total_wall_seconds_including_spawn']:.2f} / {io['worker_summaries'][2]['total_wall_seconds_including_spawn']:.2f} s including Windows spawn, all `PASS`. Multiprocess runs used independent per-worker staging directories solely for this audit; the production DataLoader was not refactored.

At workers=0, mean sample path was {io_mean:.3f} s. Of that, B13 copy {io['mean_b13_copy_seconds']:.4f} s, B13 netCDF open+read {io['mean_b13_netcdf_open_seconds']+io['mean_b13_netcdf_read_seconds']:.4f} s, B13 reader QC {io['mean_b13_reader_qc_seconds']:.4f} s, IMERG copy/open/read/QC {io['mean_imerg_copy_seconds']+io['mean_imerg_netcdf_open_seconds']+io['mean_imerg_netcdf_read_seconds']+io['mean_imerg_reader_qc_seconds']:.4f} s, normalization {io['mean_normalization_seconds']:.4f} s, tensor conversion {io['mean_tensor_conversion_seconds']:.6f} s, and formal assembly/support QC {io['mean_formal_assembly_qc_seconds']:.3f} s. SHA verification/cleanup are separate timing columns. On this CPU, the {step:.3f} s model step was {io['compute_to_io_ratio']:.2f}× the serial input path, so the observed classification is `{io['measured_bottleneck']}`. Formal assembly/support processing is the dominant input-path component; eight samples do not establish whole-epoch behavior or GPU bottlenecks. File-level values and integrity checks are in `dataloader_io_benchmark.csv`.

## Planning estimates and limits

For {TRAIN_SCENES:,} Train scenes and physical batch 1, `ceil(11720/1) = 11720` steps per epoch. Arithmetic from measured CPU components gives {rows[0]['compute_only_hours']:.2f} h compute-only or {rows[0]['serial_measured_components_hours']:.2f} h with serial sample I/O per epoch. For 10 / 30 / 50 illustrative epochs, compute-only is {rows[1]['compute_only_hours']:.1f} / {rows[2]['compute_only_hours']:.1f} / {rows[3]['compute_only_hours']:.1f} h; adding the measured serial I/O component gives {rows[1]['serial_measured_components_hours']:.1f} / {rows[2]['serial_measured_components_hours']:.1f} / {rows[3]['serial_measured_components_hours']:.1f} h. `epoch_time_estimates.csv` holds all values. **ENGINEERING_ESTIMATE_ONLY:** this is component extrapolation, not a confidence bound or training budget; it omits optimizer steps, validation, scheduling, concurrent worker contention, checkpoints, and epoch variability. Epoch counts are not frozen.

Physical batch/gradient accumulation arithmetic (1×4, 2×2, 4×1 → effective 4) is recorded in `gradient_accumulation_candidates.csv` as `NOT_ASSESSED_CUDA_UNAVAILABLE`, not possible/memory-limited/not-needed judgments. `checkpoint_storage_estimate.json` gives a theoretical model+AdamW+metadata size of {checkpoint['single_model_plus_adamw_metadata_bytes']/2**20:.2f} MiB per checkpoint, and best/last/periodic illustrations. It created no checkpoint and froze no retention policy.

`engineering_recommendation.json` is **ENGINEERING_RECOMMENDATION_ONLY**: a future CUDA environment should be benchmarked again before choosing physical batch, AMP, accumulation, or validation batch. Meanwhile 0 workers is the conservative unmodified loader option; 2 workers with independent staging was faster in this short smoke and merits a longer coupled compute/I/O test. `pin_memory=false` and `persistent_workers=false` describe this CPU-only audit, not a formal CUDA configuration. No scientific or formal training configuration changed.

All six existing/new automated suites passed in `test_results.txt`. The first run of the old v1.1 staging tests failed to create fixtures in the sandboxed system temporary directory; its trace is preserved as `test_results_sandbox_attempt.txt`. Re-running with normal temporary-directory permissions passed without changing the tests or scientific code.

## Final status

""" + "\n".join(f"- {line}" for line in status) + "\n"
    with (run / "TRAINING_ENVIRONMENT_AUDIT_REPORT.md").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(report)


def finalize(run):
    required = ["TRAINING_ENVIRONMENT_AUDIT_REPORT.md", "system_environment.json",
                "pytorch_cuda_environment.json", "gpu_inventory.json", "cpu_ram_storage.json",
                "model_memory_static.json", "gpu_batch_benchmark.csv", "gpu_amp_benchmark.csv",
                "gpu_validation_benchmark.csv", "cpu_benchmark.json", "dataloader_io_benchmark.csv",
                "io_breakdown.json", "epoch_time_estimates.csv", "gradient_accumulation_candidates.csv",
                "checkpoint_storage_estimate.json", "engineering_recommendation.json", "test_results.txt"]
    if not all((run / name).is_file() for name in required):
        raise ValueError("Required audit artifact missing")
    tests = (run / "test_results.txt").read_text(encoding="utf-8")
    if "FINAL_TEST_STATUS: PASS" not in tests:
        raise ValueError("Automated test suites have not passed")
    code_paths = ["scripts/audit_b0_training_environment.py", "scripts/audit_b0_dataloader_io.py",
                  "scripts/package_b0_training_environment_audit.py", "scripts/run_training_environment_audit_tests.py",
                  "src/yuntapr/data/himawari_b13.py",
                  "src/yuntapr/data/imerg_v07.py", "config/science_contract_v1.1.yaml",
                  "config/b0_engineering_v4.yaml", "tests/training_environment_audit/test_audit.py", "README.md"]
    manifest = {"run_id": run.name, "baseline_commit": BASELINE,
                "scientific_freeze_version": "v1.1", "engineering_version": 4,
                "formal_training_started": False, "formal_training_authorized": False,
                "source_2025_read": False, "historical_reports_overwritten": False,
                "artifact_sha256": {name: sha256(run / name) for name in required},
                "additional_attempt_sha256": {p.name: sha256(p) for p in run.glob("*_attempt.*")},
                "code_contract_test_sha256": {name: sha256(REPO_ROOT / name) for name in code_paths}}
    write_json(run, "manifest.json", manifest)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--finalize", action="store_true")
    args = parser.parse_args()
    run = args.run_dir.resolve()
    if run.parent != RUN_ROOT.resolve() or not run.name.startswith("run_"):
        raise ValueError("Audit outputs must be an independent versioned run")
    (finalize if args.finalize else create)(run)
