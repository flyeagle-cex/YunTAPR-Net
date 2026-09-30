# CUDA Environment Establishment + GPU Re-benchmark v1

Baseline GitHub commit: `f147b8a48d9370241a101960bda58de1844d0ae9`. Run: `run_20260930T130515Z`. **Result: STOPPED_AT_OFFICIAL_WHEEL_INTEGRITY_GATE.** No GPU benchmark or formal training was performed.

PyTorch's official index publishes a Windows CPython 3.12 `torch 2.11.0+cu128` wheel with SHA256 `7c78215c3af4f62e63f2b2e360f1722fc719b0853c7ac22666483d9810613a4c`. The official 2.11 CUDA 12.8 support matrix includes Blackwell sm_120, and NVIDIA's CUDA 12.8 Windows driver minimum is 570.65; the local RTX 5060 Laptop reports sm_120 and driver 573.24. These are binary-candidate compatibility facts, **not** proof of local kernel execution. Links and the exact rationale are in `official_compatibility_evidence.md`.

An isolated `F:\pytorch\Research\.venv-cuda` was created with Python 3.12.14. Its first official-index install attempt timed out; the second download yielded SHA256 `c68b95c7923e7574b1b31d7de8df4966bfaa948b731de839250f1b2c776f94e5`; the cache-disabled third yielded `3b392f56b71dc8dc96b7a39463619d8d3f192fe3960709012bdd91888ec14eb8`. **Neither matches the official index hash.** `pip` refused both; all three complete logs are retained. The differing observed hashes indicate an unreliable delivery path or corrupted transfer; no cause such as tampering is asserted. We did not disable hash checking, change download source, install a driver or Toolkit, or try a CUDA 13 wheel incompatible with the current driver.

Verification after stopping: the new venv's package list contains only `pip==25.0.1`; `torch` is absent. The CPU reference interpreter `F:\pytorch\Research\.venv\Scripts\python.exe` still imports `torch 2.14.0+cpu` and reports CUDA unavailable. Its pre-install `pip freeze` is preserved. Raw H:/F: data, science files, model, and historical reports were not changed.

All device/kernel, existing-test, real-sample, batch, AMP, validation, coupled DataLoader, assembly-profile, stability, and GPU-time-estimate artifacts are present **solely as explicit NOT_RUN records**. They contain no fabricated timings or PASS values. A compatible wheel with verified integrity is required before any of these tests can run.

## Final status

- GPU_PRESENT = true (observed by `nvidia-smi`)
- CUDA_ENVIRONMENT_ESTABLISHED = false
- CUDA_TORCH_AVAILABLE = false
- CUDA_KERNEL_COMPATIBLE_WITH_GPU = false (NOT_RUN)
- RTX5060_SM120_EXECUTION_VERIFIED = false (NOT_RUN)
- EXISTING_114_TESTS_PASS_IN_CUDA_ENV = false (NOT_RUN)
- REAL_B0_CUDA_FORWARD_BACKWARD_PASS = false (NOT_RUN)
- MAX_TESTED_SAFE_BATCH = NOT_AVAILABLE
- RECOMMENDED_SAFE_PHYSICAL_BATCH = NOT_AVAILABLE
- AMP_FP16_FEASIBLE = false (NOT_RUN)
- AMP_BF16_FEASIBLE = false (NOT_RUN)
- RECOMMENDED_AMP_MODE = NOT_AVAILABLE
- RECOMMENDED_NUM_WORKERS = NOT_AVAILABLE
- TRAINING_ENVIRONMENT_READY = false
- B0_FORMAL_TRAINING_STARTED = false
- FORMAL_TRAINING_AUTHORIZED = false
