# CUDA verified wheel install — 2026-09-30

**Result: CUDA_ENVIRONMENT_ESTABLISHED.** The isolated CUDA environment now imports `torch 2.11.0+cu128`, executes kernels on the RTX 5060 Laptop GPU (sm_120), completes one B0 engineering-only synthetic forward/backward, and passes the existing 114 core tests. Six additional training-environment audit tests also pass. `TRAINING_ENVIRONMENT_READY=PARTIAL` because batch, AMP, and VRAM benchmarks have not been rerun. No optimizer step, checkpoint, Phase-A training, or formal training was performed or authorized. Baseline GitHub main: `d2456a186bf5b67cd0e8f8ac71f94cdd33a8550e`.

## Wheel identity and integrity

Before this run, no correct `torch-2.11.0+cu128-cp312-cp312-win_amd64.whl` was found in accessible Desktop, Downloads, or `F:\pytorch\Research` search paths. The previously reported approximately 1.8 MB `torch_tensorrt-2.11.0+cu128-cp312-cp312-win_amd64.whl` was also absent from those paths at this check. It is a different package, was not installed, and was not deleted.

The correct wheel was downloaded from the specified [official PyTorch URL](https://download-r2.pytorch.org/whl/cu128/torch-2.11.0%2Bcu128-cp312-cp312-win_amd64.whl) with resumable `curl.exe`, retries, standard TLS verification, and a `.part` file. The initial `HTTP_PROXY`, `HTTPS_PROXY`, and `ALL_PROXY` values pointed to `127.0.0.1:9`, and `PIP_NO_INDEX=1`; these were cleared only in the relevant download/install subprocesses. No system proxy, WinHTTP setting, or TLS verification setting was changed. The official endpoint returned HTTP 200 and `Content-Length: 2753189216`.

The download took 544.171 seconds and produced exactly **2,753,189,216 bytes**. Its locally computed SHA256 was **`7c78215c3af4f62e63f2b2e360f1722fc719b0853c7ac22666483d9810613a4c`**, identical to the official expected value. The renamed local wheel was independently rehashed before installation and matched again. The verified wheel remains only at `F:\pytorch\Research\cuda-wheel-staging\verified\torch-2.11.0+cu128-cp312-cp312-win_amd64.whl`; the wheel itself is not committed to Git.

## Isolated installation and execution gates

`F:\pytorch\Research\.venv-cuda\Scripts\python.exe -m pip install` used that verified local wheel. Required wheel dependencies came from the official PyPI index. NumPy 2.5.3, PyYAML 6.0.3, and netCDF4 1.7.4 were then added only to the CUDA environment to run the existing B0 code and tests. Final `pip check` found no broken requirements. The CPU reference environment's 52-package `pip freeze` is byte-for-byte unchanged before and after this run.

The final CUDA environment reports `torch 2.11.0+cu128`, CUDA runtime 12.8, `torch.cuda.is_available()=true`, one device named `NVIDIA GeForce RTX 5060 Laptop GPU`, and compute capability `(12, 0)`. Real CUDA elementwise, matrix multiplication, Conv2d, and backward operations all completed with finite results and gradients.

The B0 smoke used Scientific Freeze v1.1 and engineering v4 with a normalized synthetic `[1,1,501,501]` B13 tensor, full-valid mask, the hash-checked frozen Yunnan mask, B0 backbone, frozen SP04 projection, probability heads, float64 `qlog` and `qphysical`, loss, and backward. It checked float32 backbone/head parameters, output shapes, finite loss/outputs/gradients, and 3430 supervised Yunnan cells. Focal values `alpha=0.25` and `gamma=2.0` were used **only for this engineering test**, as in the existing synthetic audit; they are not frozen formal training values. The reproducible one-shot smoke script is included beside its JSON result.

## Tests and limits

All five established core suites passed in `.venv-cuda`: 42 scientific-freeze, 20 B0-skeleton, 8 development-QC, 30 scientific-freeze-v1.1, and 14 quantile-closure tests, totaling **114/114**. The additional six training-environment audit tests passed separately (**120/120** across all current suites). Two earlier test attempts failed only because the execution sandbox denied temporary-file writes, then because a temporary directory under the Chinese workspace path violated the staging test's English-path requirement. Their full logs are retained. The final tests used normal filesystem access and an English-only, process-local user Temp path; no test or scientific source was changed.

No batch-size, AMP, VRAM, validation, DataLoader/GPU, stability, or full GPU benchmark was run in this task. This run stops at the verified-install foundation and does not establish full training readiness.

## Final status

| Field | Value |
| --- | --- |
| `CORRECT_TORCH_WHEEL_FOUND` | `true` |
| `WRONG_TORCH_TENSORRT_PRESENT` | `false` in current searched locations; previously reported file was not installed or deleted |
| `VERIFIED_WHEEL_ACQUIRED` | `true` |
| `LOCAL_WHEEL_SHA256` | `7c78215c3af4f62e63f2b2e360f1722fc719b0853c7ac22666483d9810613a4c` |
| `OFFICIAL_WHEEL_SHA256` | `7c78215c3af4f62e63f2b2e360f1722fc719b0853c7ac22666483d9810613a4c` |
| `CUDA_TORCH_INSTALLED` / `CUDA_TORCH_AVAILABLE` | `true` / `true` |
| `GPU_DEVICE_NAME` | `NVIDIA GeForce RTX 5060 Laptop GPU` |
| `GPU_COMPUTE_CAPABILITY` | `(12, 0)` |
| `RTX5060_SM120_EXECUTION_VERIFIED` | `true` |
| `B0_CUDA_SYNTHETIC_FORWARD_BACKWARD` | `PASS` |
| `EXISTING_114_TESTS_PASS_IN_CUDA_ENV` | `true` |
| `CUDA_ENVIRONMENT_ESTABLISHED` | `true` |
| `TRAINING_ENVIRONMENT_READY` | `PARTIAL` |
| `B0_FORMAL_TRAINING_STARTED` / `FORMAL_TRAINING_AUTHORIZED` | `false` / `false` |
