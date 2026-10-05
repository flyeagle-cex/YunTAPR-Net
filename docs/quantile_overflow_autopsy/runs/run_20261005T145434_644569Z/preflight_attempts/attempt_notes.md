# Preflight attempt history

No formal runner or real-source replay was started during these fixture attempts. All historical files and formal counters remained unchanged.

- The first test harness attempt found that pytest was not installed in the pinned CUDA environment. No dependency was installed or upgraded. The harness was replaced with Python's existing unittest.
- The first unittest execution actually ran 36 cases because a temporary module-level class alias was discovered twice. Both copies of the CUDA fixture failed at the observer's per-tau CUDA median: this operation is not supported under the frozen deterministic setting. The `test_result_20261005T150057_failed.json` records the actual counts and source hashes. Its CUDA-equivalence text describes the verification target; the overall status is FAIL.
- The observer median was moved to the CPU read-only statistics path. No determinism flag or production operation changed. The accidental class alias was removed. The next actual suite had 18 passing cases, whose result was preserved.
- A new synthetic overflow capture case was added. The final gate had 19 passes, zero failures/errors/skips. It verifies capture occurs before expm1 and that the original transform and physical finite guard still execute. The passed gate and diagnostic numerical source hashes are in `observer_test_result.json`.

No test created a checkpoint/model/optimizer binary. CUDA fixture parameters, optimizer states and tensors were transient and released; real LAST was not opened by these tests. No raw source was opened, and 2025 rejection tests reject the path before opening it.

The later real engineering replay uses only the final passed observer implementation. It has its own counters; none is added to the formal 50,537 optimizer steps. Previous failed fixture evidence is retained, not converted into PASS.
