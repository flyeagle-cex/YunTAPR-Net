# Superseded candidate package

This v2 candidate is retained as an immutable preparation record and must not be executed.

Harness found a deterministic finalization failure in `start_paired_point_evaluation.py`: `finalize_pair()` used exclusive creation to write `paired_metrics.json` before and after binding `paired_joint_evidence_sha256`. Harness also identified an FP32/FP64 threshold mismatch between the per-arm q32 count and paired q32 count, and missing closeout checks for the ten strong-rain occurrence-probability bins.

The code fixes are being prepared under a new commit and candidate directory. This file does not authorize execution. Scientific status remains `NOT_VERIFIED`.
