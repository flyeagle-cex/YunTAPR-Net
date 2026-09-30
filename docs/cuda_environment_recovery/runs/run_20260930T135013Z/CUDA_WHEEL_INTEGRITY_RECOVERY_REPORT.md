# CUDA wheel delivery integrity recovery — 2026-09-30

**Result: STOPPED_AT_DELIVERY_INTEGRITY_GATE.** No verified CUDA wheel was acquired on the current network. No wheel was installed, no CUDA kernel or B0 smoke was run, and no GPU benchmark or training was started. This run is separate from, and does not overwrite, the previous failed CUDA environment run at `docs/cuda_environment/runs/run_20260930T130515Z/`. Baseline commit: `0abbd7127bccde9a047c61e93a6fc71b9ee0f452`.

## Official artifact and local delivery evidence

The official [PyTorch cu128 torch index](https://download.pytorch.org/whl/cu128/torch/) was read again at 2026-09-30 13:51:01 UTC. It still lists `torch-2.11.0+cu128-cp312-cp312-win_amd64.whl` at the [official wheel URL](https://download-r2.pytorch.org/whl/cu128/torch-2.11.0%2Bcu128-cp312-cp312-win_amd64.whl), with SHA256 `7c78215c3af4f62e63f2b2e360f1722fc719b0853c7ac22666483d9810613a4c`. This is unchanged from the prior run. A normal-network HEAD request returned HTTP 200 and `Content-Length: 2753189216`. DNS resolved both official hosts. The restricted process context reported a local `127.0.0.1:9` proxy and rejected HTTPS; this is recorded separately from the successful normal-network HEAD request. No proxy or TLS settings were altered.

The two delivery methods did not pass the hash gate:

| Method | Result | SHA256 evidence |
| --- | --- | --- |
| `curl.exe -L` with retries, official exact URL | Interrupted after 13,103,104 of 2,753,189,216 bytes. Throughput projected many hours; the incomplete file was hashed, then only this run's staging `.part` file was removed. | Partial-file SHA256 `064cd9b1aa96e46c40e436e5eaa410dfc12c644d563f20cedcbe353f4201f14b`; **not comparable to the complete wheel**. |
| Isolated CUDA venv `pip --isolated download`, official cu128 index, `--no-deps --no-cache-dir` | pip reported a full 2,753.2 MB download, then rejected it on hash mismatch; exit code 1. No wheel file was retained. | pip-reported SHA256 `657f0a3aac453f086542e6e2fc91c3028c5bfa776527bc8fdd2294a3a7dc26ba`, which does not match the official value. |

Two complete downloads in the prior run were also rejected, with distinct SHA256 values `c68b95c7923e7574b1b31d7de8df4966bfaa948b731de839250f1b2c776f94e5` and `3b392f56b71dc8dc96b7a39463619d8d3f192fe3960709012bdd91888ec14eb8`. Three different nonofficial digests across complete pip downloads support `DELIVERY_PATH_UNSTABLE=true`; they do **not** identify the cause. No failed torch wheel uniquely attributable to this task was found in the pip cache before download, so unrelated cache entries were left untouched.

## Gate state

| Status | Value |
| --- | --- |
| `OFFICIAL_WHEEL_IDENTIFIED` | `true` |
| `OFFICIAL_SHA256_RECONFIRMED` | `true` |
| `VERIFIED_WHEEL_ACQUIRED` | `false` |
| `DOWNLOAD_A_VERIFIED` / `DOWNLOAD_B_VERIFIED` | `false` / `false` |
| `DELIVERY_PATH_UNSTABLE` | `true`, based on three distinct complete pip-download mismatches |
| `ALTERNATE_TRUSTED_NETWORK_REQUIRED` | `true` |
| `CUDA_TORCH_INSTALLED` / `CUDA_TORCH_AVAILABLE` | `false` / `false` |
| `RTX5060_SM120_EXECUTION_VERIFIED` | `false` (`NOT_RUN`) |
| `EXISTING_114_TESTS_PASS_IN_CUDA_ENV` | `false` (`NOT_RUN`) |
| `TRAINING_ENVIRONMENT_READY` | `false` |
| `B0_FORMAL_TRAINING_STARTED` / `FORMAL_TRAINING_AUTHORIZED` | `false` / `false` |

The isolated `F:\pytorch\Research\.venv-cuda\Scripts\python.exe` still has no importable `torch`. The CPU reference environment at `F:\pytorch\Research\.venv\Scripts\python.exe` still reports `torch 2.14.0+cpu`; its 52-package `pip freeze` has zero differences from the prior recorded baseline. Install, CUDA kernel gate, synthetic B0 smoke, the 114 CUDA-environment tests, and the GPU audit are explicitly `NOT_RUN` because their prerequisite verified wheel does not exist. A `NOT_RUN` item is not a pass.

## Required next delivery step

Switch manually to a trusted network, such as a trusted mobile hotspot, campus/laboratory network, or other trusted broadband, and download the **same official URL** again. An offline transfer from another trusted computer by USB drive is also acceptable. Before installation on this target computer, run `Get-FileHash -Algorithm SHA256` against the transferred complete wheel and require an exact match to `7c78215c3af4f62e63f2b2e360f1722fc719b0853c7ac22666483d9810613a4c`. Filename, reported file size, or a successful HTTP response alone do not satisfy the gate. Resume the installation and kernel checks only after that local match. Do not use a third-party mirror or bypass the hash check.

The Scientific Freeze, B0/QC, normalization, and quantile-stability work remain as previously recorded. This failure concerns CUDA wheel delivery only; it does not reverse those research results or authorize Phase-A/formal training.

The machine-readable files alongside this report record the official metadata, redacted proxy settings, DNS/HTTPS checks, cache inventory, both download attempts, hash comparison, blocked downstream gates, and run manifest.
