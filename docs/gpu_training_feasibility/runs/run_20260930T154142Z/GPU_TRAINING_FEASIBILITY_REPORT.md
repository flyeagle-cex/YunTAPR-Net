# GPU_TRAINING_FEASIBILITY_REPORT

Run: `run_20260930T154142Z`

Baseline: `9cb83aa493b57acbad648df5b2c257739b23045e`. Scientific Freeze v1.1 / engineering v4 are unchanged.

## Result

```json
{
  "MAX_TESTED_SAFE_BATCH": 2,
  "RECOMMENDED_SAFE_PHYSICAL_BATCH": 2,
  "AMP_FP16_FEASIBLE": true,
  "AMP_BF16_FEASIBLE": true,
  "RECOMMENDED_AMP_MODE": "BF16",
  "RECOMMENDED_VALIDATION_BATCH": 8,
  "GPU_PRESENT": true,
  "CUDA_TORCH_AVAILABLE": true,
  "RTX5060_SM120_EXECUTION_VERIFIED": true,
  "RECOMMENDED_NUM_WORKERS": 2,
  "GPU_STABILITY_PASS": true,
  "REAL_B0_CUDA_REGRESSION_PASS": true,
  "TRAINING_ENVIRONMENT_READY": true,
  "B0_FORMAL_TRAINING_STARTED": false,
  "FORMAL_TRAINING_AUTHORIZED": false,
  "scope": "ENGINEERING_RECOMMENDATION_ONLY",
  "bottleneck": "GPU_COMPUTE_BOUND",
  "cpu_reference_packages_unchanged": true,
  "worker_comparison": [
    {
      "workers": 0,
      "samples": 32,
      "active_seconds_sum": 4.550204399987706,
      "active_samples_per_second": 7.032651104659487,
      "full_wall_samples_per_second": 7.020662203777495,
      "startup_and_shutdown_seconds": 0.007770200012600981,
      "data_wait_fraction": 0.23118508697631324,
      "gpu_step_fraction": 0.7168990034841582
    },
    {
      "workers": 2,
      "samples": 32,
      "active_seconds_sum": 3.1368239000148606,
      "active_samples_per_second": 10.201401487615675,
      "full_wall_samples_per_second": 3.920029391401556,
      "startup_and_shutdown_seconds": 5.026380199982668,
      "data_wait_fraction": 0.038816173260524355,
      "gpu_step_fraction": 0.8837873557329681
    },
    {
      "workers": 4,
      "samples": 32,
      "active_seconds_sum": 3.1904595000014524,
      "active_samples_per_second": 10.029903216130915,
      "full_wall_samples_per_second": 2.4563811193208065,
      "startup_and_shutdown_seconds": 9.836834900001122,
      "data_wait_fraction": 0.04554569647584738,
      "gpu_step_fraction": 0.8766395248084715
    }
  ],
  "worker_selection": "Active throughput for an epoch; prefer fewer workers within 5% of best. Startup included separately. 32-sample full wall also reported.",
  "limitations": [
    "No optimizer state or optimizer step measured; a future optimizer consumes extra VRAM and time.",
    "No model fitting or accuracy/convergence claim; AMP unscaled gradients only.",
    "32 pinned scenes, order 0/2/4, filesystem cache not flushed; not a cold-disk or full-epoch benchmark.",
    "Device-wide memory estimate is conservative reservation arithmetic, not a physical residency measurement.",
    "Validation full real DataLoader epoch not measured; serial I/O proxy clearly separated.",
    "Worker staging isolation belongs to this audit; no production DataLoader refactor."
  ]
}
```

## Measurement method

Verified CUDA Python: `F:\pytorch\Research\.venv-cuda\Scripts\python.exe`; torch 2.11.0+cu128; RTX 5060 Laptop, SM120, runtime 12.8. Exact runtime settings are in environment.json. Input is normalized synthetic full-valid `[B,1,501,501]`, with the frozen Yunnan mask. No optimizer was instantiated; no parameter update or checkpoint occurred. Alpha=0.25 and gamma=2 are engineering test values, not a new scientific freeze.

Each compute case performed two warmups and five measured iterations. CUDA synchronization separates forward, loss and backward. All seven passes are checked for finite outputs/loss/gradients and strict qlog order. Raw quantile and all parameters remain float32; qlog, qphysical and conditional pinball remain float64. `compute_iterations.json` retains every check. Model hashes before/after each case match. Timings exclude external numerical checks; the coupled/stability wall times include them. Validation uses eval/no_grad; its tiny backward_ms field is context-exit overhead, not an executed backward.

Safety requires both allocator and device-wide headroom: at least 15% for progression and 20% for recommendation. Device-wide free memory is conservatively estimated from pre-case free minus incremental peak reservation, and capped by post-case free. Negative arithmetic values indicate over-reservation, not negative physical free memory. Windows can complete allocations beyond dedicated VRAM; completion alone is therefore not a safe result. Shared-memory paging is suspected from reservation and slowdown, not directly traced.

## Training batch

| Batch | Allocated MiB | Reserved MiB | Reserved fraction | Step ms | samples/s | 15% safe |
|---:|---:|---:|---:|---:|---:|:---|
| 1 | 1726.6 | 2240.0 | 0.275 | 105.82 | 9.45 | True |
| 2 | 3421.3 | 4420.0 | 0.542 | 210.98 | 9.48 | True |
| 4 | 6814.9 | 8768.0 | 1.076 | 657.46 | 6.08 | False |

Batch 4 completed but failed headroom; batch 8 was NOT_RUN under the progression rule. No CUDA OOM was observed. The safe maximum is within the tested FP32 sweep; larger AMP training batches were not tested or claimed safe.

## Precision at recommended physical batch

| Mode | Reserved MiB | Step ms | samples/s | Numerical status |
|---|---:|---:|---:|---|
| FP32 | 4420.0 | 212.77 | 9.40 | PASS |
| FP16 | 3258.0 | 164.52 | 12.16 | PASS |
| BF16 | 3260.0 | 163.54 | 12.23 | PASS |

BF16 and FP16 are close in this short benchmark; the recommendation uses the fastest measured safe mode and is not a claim of statistical superiority. No GradScaler or loss scaling was used. Float32 parameters and the quantile precision guard remain unchanged.

## Validation

| Batch | Reserved MiB | Forward + loss ms | samples/s | 20% headroom |
|---:|---:|---:|---:|---|
| 1 | 658.0 | 35.20 | 28.41 | True |
| 2 | 1068.0 | 65.20 | 30.68 | True |
| 4 | 2122.0 | 119.74 | 33.41 | True |
| 8 | 4186.0 | 237.82 | 33.64 | True |
| 16 | 8296.0 | 613.66 | 26.07 | False |

Batch 16 completed but was rejected for headroom. Validation batch 8 is an engineering recommendation only.

## Real data and DataLoader

One pinned full-valid 2023 Train scene and one pinned full-valid 2024 Validation scene passed the complete raw H: → bounded English staging → formal QC → pinned normalization → CUDA B0/SP04/heads/loss/backward chain. Both have 3430 supervised Yunnan pixels. All source hashes match the previous pinned audit; every copy is size/SHA verified and cleaned. Time identities and normalization hash are retained in real_cuda_regression.json. No 2025 source data were read.

The same 32 unique final-eligible 2023 scenes were sampled across the pinned population, with shuffle disabled. Main thread count=2; worker thread count=1; per-worker prefetch=1 batch; pin_memory=false; persistent_workers=false. Each worker owns one bounded staging root and one copy at a time, cap 734003200 bytes per root. Aggregate worst-case worker copy bound is worker_count × cap. No staging copies remain. Data wait is time inside next(iterator); main batch assembly and H2D are separately measured. GPU_step_ms is synchronized forward/loss/backward wall time and includes existing formal CPU validation, not pure kernel event time.

| Workers | Full 32-scene wall s | Full samples/s | Active samples/s | Mean wait ms/batch | Mean GPU step ms | GPU utilization % | CPU utilization % |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 4.56 | 7.02 | 7.03 | 65.75 | 203.88 | 75.8 | 15.1 |
| 2 | 8.16 | 3.92 | 10.20 | 7.61 | 173.27 | 43.5 | 12.9 |
| 4 | 13.03 | 2.46 | 10.03 | 9.08 | 174.81 | 17.8 | 12.5 |

Recommended workers=2; measured active critical path classification: **GPU_COMPUTE_BOUND** (GPU step fraction 88.4%, data wait 3.9%). Device utilization is whole-device telemetry including worker startup, other desktop applications and CPU validation gaps; it is not process-exclusive utilization. The first sweep is preserved under loader_initial because its worker-4 run overlapped the independent profiler. Only the later serial sweep informs these recommendations. Filesystem cache was not flushed, and fixed worker order can favor later runs.

## Formal assembly profile

| Component | Mean ms/sample |
|---|---:|
| mask_assembly_and_eligibility | 0.035 |
| normalization | 2.064 |
| other_python_and_formal_qc | 1.078 |
| reader_copy_io_integrity_qc | 27.638 |
| sample_construction | 0.645 |
| sp04_support_mapping | 0.748 |
| Batch NumPy stacking/copy → torch (all five arrays) | 0.251 |
| Batch formal validation and other work | 2.985 |

Four real scenes were profiled with production code unchanged. Dataset categories are exclusive call-site timings; nested readers include copy, SHA, decode and cleanup. The separate mask tensor probe overlaps NumPy→torch and must not be added again. Instrumentation overhead is included. The earlier CPU audit's ~1.4 s/sample residual was NOT reproduced, and this run does not establish its historical cause. Differences in thread/runtime configuration, Windows scheduling and cache conditions remain possible. Current support mapping itself is small. Formal validation recomputes normalization in B0Batch and again at forward entry; future engineering work could evaluate eliminating duplicate validation after preserving provenance guarantees. No such refactor was made.

## Three-minute stability

Duration 180.03 s, 1042 forward/backward iterations, mean step 164.01 ms. Peak allocated/reserved 2704.1/3260.0 MiB; max device temperature 74.0 °C; mean power 92.69 W; mean graphics clock 2933 MHz. Thermal throttle detected=False; power cap active samples=0. Power cap activity is not silently classified as thermal throttle. CUDA errors=0; driver event query=QUERIED; matching events=0. Telemetry is sampled roughly once per second and cannot exclude unsampled transients. Parameter SHA before/after is identical.

## Epoch arithmetic and accumulation

All rows are ENGINEERING_ESTIMATE_ONLY. Train=11720, Validation=11727; steps use ceiling division. The compute-only scenario omits all data delivery. The real-train scenario extrapolates the measured active 32-scene coupled rate, adds measured worker startup/shutdown once per epoch, and adds a conservative serial per-scene 2023 reader/assembly proxy to validation GPU time. A real 2024 validation DataLoader epoch has not been benchmarked. Optimizer work/state, checkpointing, logging, storage contention and sustained full-epoch thermal changes are excluded; these are arithmetic scenarios, not wall-time guarantees.

| Scenario | Epochs | Train min/epoch | Validation min/epoch | Total min/epoch | Wall hours |
|---|---:|---:|---:|---:|---:|
| GPU_COMPUTE_ONLY_ARITHMETIC | 1 | 15.97 | 5.81 | 21.78 | 0.36 |
| REAL_TRAIN_ACTIVE_PLUS_SERIAL_VALIDATION_IO_PROXY | 1 | 19.15 | 11.96 | 31.19 | 0.52 |
| GPU_COMPUTE_ONLY_ARITHMETIC | 10 | 15.97 | 5.81 | 21.78 | 3.63 |
| REAL_TRAIN_ACTIVE_PLUS_SERIAL_VALIDATION_IO_PROXY | 10 | 19.15 | 11.96 | 31.19 | 5.20 |
| GPU_COMPUTE_ONLY_ARITHMETIC | 30 | 15.97 | 5.81 | 21.78 | 10.89 |
| REAL_TRAIN_ACTIVE_PLUS_SERIAL_VALIDATION_IO_PROXY | 30 | 19.15 | 11.96 | 31.19 | 15.59 |
| GPU_COMPUTE_ONLY_ARITHMETIC | 50 | 15.97 | 5.81 | 21.78 | 18.15 |
| REAL_TRAIN_ACTIVE_PLUS_SERIAL_VALIDATION_IO_PROXY | 50 | 19.15 | 11.96 | 31.19 | 25.99 |

gradient_accumulation_candidates.csv lists physical batch × accumulation steps = effective batch for measured-safe physical batches only. Accumulation execution, loss scaling semantics and optimizer behavior were not benchmarked; no candidate, epoch budget or AMP mode is frozen.

## Verification and reproducibility

Automated tests: 126 executed, all passing=True; no skipped tests accepted as pass. CPU reference pip freeze unchanged=True. All scientific configuration and production source files remain at the baseline. Historical reports are preserved. The initial test import failure is retained in tests_initial; adding the repository root to this new audit entrypoint's import path resolved it without changing old tests or production code. Per-phase invocation hashes capture the benchmark script as executed; the final manifest captures the submitted source. Tests cover shared-memory over-reservation, other GPU consumers, safety vs recommendation margins, progression stop rules and epoch tail arithmetic in addition to the existing suites.

Run `benchmark_b0_gpu_feasibility.py` phases in order: compute, real, loader, profile, stability, tests, finalize; use a new versioned run directory. Set TEMP/TMP to an ASCII writable directory for tests. Raw inputs and frozen local evidence must already be available; no download or installation is performed. The benchmark writes staging only below its own gpu_<run> directories and removes only copies it creates. Never overwrite old evidence.

TRAINING_ENVIRONMENT_READY describes this engineering forward/backward audit only. Formal training authorization remains false. This task stops after report publication to GitHub; Phase-A Training is not started.
