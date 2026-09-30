# B0 GPU training feasibility audit

Latest run: [run_20260930T154142Z](runs/run_20260930T154142Z/GPU_TRAINING_FEASIBILITY_REPORT.md).

Baseline: `9cb83aa493b57acbad648df5b2c257739b23045e`.
Scientific Freeze v1.1 and engineering configuration v4 remain unchanged.

The RTX 5060 Laptop passed the real B0 CUDA regression and a 180-second
forward/backward stability smoke. Engineering recommendations are physical
batch 2, BF16, validation batch 8 and two DataLoader workers. This is not
authorization to start formal training. No optimizer step or formal checkpoint
was produced.

The run contains measured batch/precision/validation tables, 32-scene worker
comparisons, real source and staging evidence, assembly profiling, NVIDIA
telemetry, epoch arithmetic scenarios, accumulation candidates and automated
test logs. The manifest hashes all public evidence and records unchanged
production inputs. Initial worker measurements and the corrected test-entrypoint
import failure are retained as history; the report identifies the final evidence.

Use `scripts/benchmark_b0_gpu_feasibility.py` with the verified CUDA interpreter
and a new run directory. Execute compute → real → loader → profile → stability
→ tests → finalize → seal sequentially. The finalize phase also requires CPU
reference package snapshots before/after the audit. The scripts consume existing
local pinned evidence and raw read-only sources; no data, wheels, virtual
environments or temporary staging payloads are stored in Git.
