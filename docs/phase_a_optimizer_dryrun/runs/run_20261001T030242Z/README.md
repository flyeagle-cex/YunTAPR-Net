# ENGINEERING_ONLY reproducibility

Use the verified F:\pytorch\Research\.venv-cuda\Scripts\python.exe. Before starting Python, set PYTHONHASHSEED=2026, CUBLAS_WORKSPACE_CONFIG=:4096:8, PYTHONUTF8=1, PYTHONDONTWRITEBYTECODE=1; set TEMP/TMP to a writable ASCII path. No package installation is needed.

Use a NEW docs/phase_a_optimizer_dryrun/runs/run_<UTC> directory. Invoke scripts/resume_phase_a_optimizer_v1.py phases initialize, preliminary, gpu, tests, finalize in that order, each with --out <new-run> --scope ENGINEERING_ONLY. Initialization expects the pinned baseline Git commit; on a later checkout audit the explicit baseline rather than bypassing the lock. Never rerun a phase into old evidence or overwrite a failure.

The gpu phase requires the six pinned 2023 sources, frozen local Yunnan mask and previous local per-frame evidence. It reads only those six scenes with two independent bounded ASCII staging workers. B13/IMERG file sizes and SHA are checked; staged copies are deleted after successful decode/QC. Six immutable RAM fixtures are reused to make replay inputs identical. Extra Chinese-path copy/read/integrity/cleanup I/O timings are in real_sample_read_audit.json; they are excluded from optimizer-only step_seconds.

Exactly three updates in each A/B/C run are permitted. Temporary step2 checkpoint and three metadata-corrupted copies live only in an owned ASCII TEMP directory and are removed. A/B or resume mismatch, nonfinite gradients/outputs, quantile crossing, or insufficient20% dedicated VRAM headroom stops execution without changing parameters/batch. No formal training entrypoint, complete training epoch, 2025 pixels, or Phase-B normalization is invoked.

The tests phase actually reruns137 historical +17 protocol +8 real-evidence tests; it requires the generated CUDA artifacts and executes no additional optimizer steps. Full results and initial runner failure are both preserved. Finalize verifies frozen document/config and every historical baseline blob, adds full identity/manifest and then stops. Publishing Git commit and remote API verification occur separately; receipts are kept outside the tracked run to avoid a commit/hash cycle.

Current status is PROTOCOL_ENGINEERING_VALIDATED, with FORMAL_TRAINING_AUTHORIZED=false. The zero-update harness attempt and original scheduler failure remain separately recorded. Do not count their NOT_RUN gates as PASS for those runs.
