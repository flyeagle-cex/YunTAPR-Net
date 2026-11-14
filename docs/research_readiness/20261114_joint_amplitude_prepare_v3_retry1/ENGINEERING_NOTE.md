# YT-JOINT-PIXEL-20261114-V3 engineering package

**Status:** `READY_PENDING_HARNESS_REVIEW_AND_RESEARCHER_APPROVAL`  
**Scientific status:** `NOT_VERIFIED`  
**Inference/training authorization:** none  
**Execution commit:** `3b99d3e612cf085875931a256e133064cfd311d6`  
**Canonical proposal SHA256:** `d1ba07f488b346a131989b6b71e11e3a21bd6c8293084849cbd644cbf987a668`

## Scope

This candidate compares the existing B7 seed-2029 fixed-E9 E0 and COSINE9 models on the same 963-scene 2024 Development population: 3,303,090 valid pixel-times, 407,820 rainy pixel-times, and 717 strict-FP32 `R > 20 mm/h` pixel-times. The 2025 Final Test is excluded. No training or new seed is included.

Each arm streams the full valid population through inherited point metrics and the joint accumulator, while retaining only the 717 strong-rain rows. Records carry `(scene_id, analysis_time, pixel_index)`, truth rate, `p_occ`, all 32 `qlog` nodes, and point readouts A/B/C. Pairing checks exact ordered keys and exact truth equality. q32 threshold classification uses the same strict FP32 convention as the inherited point metrics. Per-arm strong-rain `p_occ` bins are retained separately and must each sum to 717; they are not expected to have identical bin counts across arms.

This is descriptive Development evidence. q32 coverage is not POD, P20, AP20, or calibration. The outputs cannot establish a causal defect in a branch, model capacity, supervision, optimization, or terrain mechanism. The single seed, reused Development year, and lack of independent storm-event count remain.

## Engineering corrections since v2

Harness identified and Codex fixed a deterministic finalization failure: the previous version created `paired_metrics.json` twice with exclusive mode. V3 writes it once, after `paired_joint_evidence.json` is complete and its SHA has been added. The per-arm and paired q32 `>20` summaries now use matching FP32 decisions and are cross-checked. Finalization validates all ten strong-rain probability bins, nonnegative integer counts, per-bin count relationships, and a 717-row total for each arm. Rainy-population overrun now fails during accumulation. Four targeted CPU synthetic checks cover the finalizer, FP32 threshold edge, population guard, and exact-key pairing (5 tests total).

## Candidate execution limits

| Resource | Frozen ceiling | Basis |
|---|---:|---|
| Payload archive reservations | 53,494,753,532 bytes | Both fixed arms; full delivered/archive length charged per open; this is not sector I/O. |
| Payload opens | 15,906 | Two 7,950-file weather/mask passes plus static and checkpoint hash/load opens. |
| Metadata reservation | 1,476,395,008 bytes | Two 128 MiB preflights + 128 MiB controller + two 512 MiB workers. |
| Metadata opens | 5,632 | Two 512-open preflights + 512 controller + two 2,048-open workers. |
| Total source reservation | **54,971,148,540 bytes** | Payload plus metadata ceilings. |
| Total source opens | **21,538** | Payload plus metadata ceilings. |
| Elapsed time | **7,200 seconds (2 hours)** | One package deadline; at most 3,000 seconds per arm. |
| Output storage | **4 GiB** | Up to six bounded 256 MiB SQLite groups per arm; remaining allowance covers summaries, logs, runtime scratch, and compressed strong-pixel rows. |
| Admission | 8 GiB output-volume free; 8 GiB host available; 5,120 MiB GPU free | Must pass before launch and before each arm. Runtime/GPU identity remains an inherited receipt reference. |
| Training updates / retries / replay | **0 / 0 / 0** | Failure stops the package; no automatic retry or replay. |

These limits do not authorize a run. Checkpoint identities remain inherited from saved receipts and have not been re-hashed during preparation.

## Preparation receipt

`PREPARATION_RECEIPT.json` records a metadata-only preparation with zero scientific-payload reads, checkpoint loads, model inference, or optimizer updates. Preparation counters and source-volume admission are recorded there. These preparation reads are separate from the candidate execution budget. Private bindings and paths are omitted from this public note. The formal output directory remains absent.

## Approval boundary

Harness must review this exact proposal, code commit, and public receipt. After that, only the researcher may authorize this exact two-arm evaluation. The proposal is not authorization to create the formal output package or run GPU inference.
