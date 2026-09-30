# B0 Training Environment + Memory Feasibility Audit v1

Run: `run_20260930T114738Z`. Baseline GitHub commit: `2e243ebfc368ac778538a15413598cbc60fd4f70`. Scope: `ENGINEERING_ONLY`. Scientific Freeze v1.1 and engineering v4 were loaded and verified. This run performed forward/backward and I/O smoke measurements; no optimizer was created or stepped, no checkpoint was produced, and no formal training was started.

## Decision

**TRAINING_ENVIRONMENT_READY = false.** `nvidia-smi` confirms one NVIDIA GeForce RTX 5060 Laptop GPU with 8151 MiB total VRAM, driver 573.24, compute capability 12.0. At inventory time 1815 MiB was occupied and about 6336 MiB free. The fixed interpreter `F:\pytorch\Research\.venv\Scripts\python.exe` has PyTorch `2.14.0+cpu` with `torch.version.cuda = null`, CUDA available false, and zero PyTorch CUDA devices. NVIDIA's driver-reported CUDA ceiling 12.8 is **not** a PyTorch CUDA runtime. CUDA batch/AMP/validation benchmarks were `NOT_RUN_CUDA_UNAVAILABLE`; no safe GPU batch, GPU throughput, AMP dtype, or 15–20% reserved-memory headroom can be established. Establishing a compatible CUDA-enabled PyTorch environment requires a separate action; no package, driver, or CUDA component was changed in this audit.

## Measured hardware and model

- Windows: Microsoft Windows 11 家庭版 中文版, build 26100; CPU Intel(R) Core(TM) Ultra 9 275HX (24 physical / 24 logical cores); RAM 31.43 GiB total, 16.90 GiB available at inventory. `cpu_ram_storage.json` records C:, F:, H: filesystems, capacities, free space, and source/staging availability. H: and F: raw files were read only.
- `B0Model`: 4,329,361 trainable parameters, all float32. Parameters 16.52 MiB, theoretical gradients 16.52 MiB, theoretical SGD no-momentum state 0 MiB (momentum 16.52 MiB), theoretical AdamW state 33.03 MiB. These exclude activations and allocator/workspace overhead. No optimizer was instantiated.
- Full input `[1,1,501,501]`; outputs rain logits `[1,1,100,100]`, conditional quantiles `[1,32,100,100]`. Model weights remain float32; qlog, qphysical, and conditional pinball were verified float64 with finite outputs, loss, and gradients.
- CPU batch 1: 1 warmup, 3 measured forward/loss/backward passes, 2 PyTorch threads. Mean forward 1.134 s, loss 0.0016 s, backward 2.316 s, total 3.451 s. Lifetime peak process working set 1.82 GiB; this includes initialization and warmup and is not an isolated step peak. The first attempt could not read this process counter and is preserved as `cpu_benchmark_memory_unavailable_attempt.json`; the corrected rerun is `cpu_benchmark.json`.

## Eight real final-eligible 2023 samples

The benchmark used hash-verified final-eligible 2023 manifest entries spread across the available Train period. Each sample followed raw H: B13 → bounded SHA-verified ASCII staging → netCDF read → formal QC → pinned Phase-A normalization → tensor; V07 Final IMERG was also read with verified staging. Original data were unchanged, and all owned temporary copies were cleaned. With 8 samples, DataLoader workers 0 / 2 / 4 took respectively 11.50 / 4.21 / 7.88 s including Windows spawn, all `PASS`. Multiprocess runs used independent per-worker staging directories solely for this audit; the production DataLoader was not refactored.

At workers=0, mean sample path was 1.437 s. Of that, B13 copy 0.0094 s, B13 netCDF open+read 0.0076 s, B13 reader QC 0.0004 s, IMERG copy/open/read/QC 0.0055 s, normalization 0.0020 s, tensor conversion 0.000074 s, and formal assembly/support QC 1.400 s. SHA verification/cleanup are separate timing columns. On this CPU, the 3.451 s model step was 2.40× the serial input path, so the observed classification is `CPU_COMPUTE_BOUND`. Formal assembly/support processing is the dominant input-path component; eight samples do not establish whole-epoch behavior or GPU bottlenecks. File-level values and integrity checks are in `dataloader_io_benchmark.csv`.

## Planning estimates and limits

For 11,720 Train scenes and physical batch 1, `ceil(11720/1) = 11720` steps per epoch. Arithmetic from measured CPU components gives 11.24 h compute-only or 15.91 h with serial sample I/O per epoch. For 10 / 30 / 50 illustrative epochs, compute-only is 112.4 / 337.1 / 561.8 h; adding the measured serial I/O component gives 159.1 / 477.4 / 795.7 h. `epoch_time_estimates.csv` holds all values. **ENGINEERING_ESTIMATE_ONLY:** this is component extrapolation, not a confidence bound or training budget; it omits optimizer steps, validation, scheduling, concurrent worker contention, checkpoints, and epoch variability. Epoch counts are not frozen.

Physical batch/gradient accumulation arithmetic (1×4, 2×2, 4×1 → effective 4) is recorded in `gradient_accumulation_candidates.csv` as `NOT_ASSESSED_CUDA_UNAVAILABLE`, not possible/memory-limited/not-needed judgments. `checkpoint_storage_estimate.json` gives a theoretical model+AdamW+metadata size of 50.55 MiB per checkpoint, and best/last/periodic illustrations. It created no checkpoint and froze no retention policy.

`engineering_recommendation.json` is **ENGINEERING_RECOMMENDATION_ONLY**: a future CUDA environment should be benchmarked again before choosing physical batch, AMP, accumulation, or validation batch. Meanwhile 0 workers is the conservative unmodified loader option; 2 workers with independent staging was faster in this short smoke and merits a longer coupled compute/I/O test. `pin_memory=false` and `persistent_workers=false` describe this CPU-only audit, not a formal CUDA configuration. No scientific or formal training configuration changed.

All six existing/new automated suites passed in `test_results.txt`. The first run of the old v1.1 staging tests failed to create fixtures in the sandboxed system temporary directory; its trace is preserved as `test_results_sandbox_attempt.txt`. Re-running with normal temporary-directory permissions passed without changing the tests or scientific code.

## Final status

- SCIENTIFIC_FREEZE_VERSION = v1.1
- QUANTILE_NUMERICAL_STABILITY_CLOSED = true
- PHASE_A_SAMPLE_ELIGIBILITY_READY = true
- PHASE_A_NORMALIZATION_READY = true
- GPU_PRESENT = true
- CUDA_TORCH_AVAILABLE = false
- TRAINING_ENVIRONMENT_READY = false
- CUDA_ENVIRONMENT_ACTION_REQUIRED = true
- MAX_TESTED_SAFE_BATCH = NOT_AVAILABLE
- AMP_FEASIBLE = NOT_TESTED
- DATALOADER_IO_READY = true
- B0_FORMAL_TRAINING_STARTED = false
- FORMAL_TRAINING_AUTHORIZED = false
