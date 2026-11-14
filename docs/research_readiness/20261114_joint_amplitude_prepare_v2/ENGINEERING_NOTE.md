# YT-JOINT-PIXEL-20261114-V2 engineering package

**Status:** `READY_PENDING_HARNESS_REVIEW_AND_RESEARCHER_APPROVAL`
**Scientific status:** `NOT_VERIFIED`
**Inference/training authorization:** none
**Execution commit:** `3a530268b82b98c4342af200217ac4cb1ca69809`
**Canonical proposal SHA256:** `1036d8d62a7b6b4ba4c260b14a78a2f4f233ae226491924f0ffb0c59acada4eb`

## Scope

The candidate package binds the existing B7 seed-2029 fixed-E9 E0 and COSINE9 checkpoints to the same 963-scene 2024 Development population. It performs no training and makes no new seeds. The population contract is 3,303,090 valid pixel-times, 407,820 rainy pixel-times, and 717 strict-FP32 `R > 20 mm/h` pixel-times. The 2025 Final Test remains excluded.

Each arm streams the full valid population through the inherited point metrics and joint counter. It retains only the 717 strong-rain rows, with `(scene_id, analysis_time, pixel_index)` identity, reference rate, occurrence probability, all 32 conditional `qlog` nodes, and the inherited A/B/C point readouts. The ten probability bins retain the saved equal-width, `searchsorted(..., side="right")` convention. The paired closeout requires exact ordered keys and reference values in both arms before computing q32 coverage intersections/differences and point/probability changes.

This is descriptive Development evidence. q32 coverage is not POD, P20, AP20, or calibration. A pattern in these outputs cannot establish a causal defect in a branch, model capacity, supervision, optimization, or terrain mechanism. The single seed, reused Development year, reference-data limitations, and lack of independent storm-event count remain.

## Candidate execution limits

| Resource | Frozen candidate ceiling | Basis |
|---|---:|---|
| Weather, mask, static, checkpoint archive reservations | 53,494,753,532 bytes | Two fixed arms; each source open is charged at full delivered/archive length. This remains a reference-derived payload bound, not disk-sector I/O. |
| Payload opens | 15,906 | Two 7,950-file weather/mask passes; two static opens; separate checkpoint hash and load opens. |
| Metadata reservation | 1,476,395,008 bytes | Two 128 MiB preflight scopes + 128 MiB controller + two 512 MiB workers. Each read reserves the whole metadata archive before opening. |
| Metadata opens | 5,632 | Two 512-open preflight scopes + one 512-open controller + two 2,048-open workers. Bootstrap files are charged inside each scope. |
| Total source reservation | **54,971,148,540 bytes** | Payload plus metadata ceilings. |
| Total source opens | **21,538** | Payload plus metadata ceilings. |
| Elapsed time | **7,200 seconds (2 hours)** | One package deadline; 3,000 seconds maximum per model arm; bounded preflight and controller time. |
| Output storage | **4 GiB** | The inherited Evaluation creates at most six bounded 256 MiB SQLite groups per arm (3 GiB across two arms); remaining space covers logs, summaries, runtime scratch, and the compressed strong-row files. The row writer reserves the uncompressed array sizes plus 1 MiB before writing. |
| Admission | 8 GiB free output volume; 8 GiB host available memory; 5,120 MiB free GPU memory | Must pass live admission immediately before launch and each arm. Runtime version/GPU are still receipt references, not a new runtime probe. |
| Training updates / retries / replay | **0 / 0 / 0** | Fixed gate; any failed task stops the package and is never automatically replayed. |

The source caps are upper bounds enforced by the runner; they are not a request to consume every byte. They include validation, controller, worker, checkpoint hashing/loading, and metadata reads. They do not authorize a run. The checkpoint SHA values are inherited from saved receipts and have **not** been re-hashed during preparation.

## Metadata-only preparation receipt

`PREPARATION_RECEIPT.json` records 52 metadata files read in 60 opens, totaling 76,937,874 bytes under the preparation-only 256 MiB / 256-open limit. Source-volume existence checks passed. Scientific payload reads, checkpoint loads, model inference, and optimizer updates were all zero. These preparation reads are separate from the proposed execution budget.

The private binding and output paths are under the local `.local` namespace and are deliberately not included here. The formal output directory does not yet exist.

## Required independent review and authorization

Harness must review the exact execution commit, proposal SHA, per-arm source closures, mask/pixel pairing, output cap calculation, metadata/checkpoint accounting, timeout/admission gates, and stop/no-retry behavior. This review may inspect code, proposal, and receipts only; it must not perform a model forward or open scientific payloads.

Only after Harness records its review may the researcher decide whether to authorize this exact two-arm evaluation. The current proposal is not authorization to create the formal output package or run GPU inference.
