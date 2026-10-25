# Stage 2 executable candidates

Base: `ede6e645`. Stage 1's 52 checks are inherited, not rerun. New code is in
`src/yuntapr/experimental/core_innovation/stage2/`; formal training, loss,
probability heads, evaluation, historical receipts and main are unchanged.

| Interface | Implemented boundary |
| --- | --- |
| `population.py` | Bounded actual seven-band decoding, frozen native axes/FP32 packing; six-slot joint eligibility; strict time-major B3 adapter; streaming complete-2023-population moments; B13 scaler preserved. Missing evidence never passes. |
| `coupling.py` | Actual CF observation intervals, inherited concurrent `[analysis-30min, analysis)` target; strict same-valid retrospective connection selected by researcher. Distinct valid times are never labelled vintage comparisons. |
| `environment.py`, `models.py` | Explicit 11-channel Train-only scaling adapter; B2/B3/B4 and B1+GFS pilot constructors; inherited widths/SP04/V2 heads; fresh B3/B4 common initialization; target-grid MEE candidate. |
| `dote_v13.py` | O850/O700, W=max(O,0), L=max(-O,0), explicit candidate moisture coupling; native metric derivatives aggregated as vectors with WGS84 area weights; slope/aspect recomputed. O is a diagnostic, not validated vertical velocity. |
| `fusion.py` | Same GFS and O/W/L/M payload for B7 concat/B8 bounded DTFM; scale projections, fusion convolution and residual; identical active parameter counts without padding. AMP boundary uses parameter-precision affine/fusion arithmetic, then restores feature dtype. |
| `budget.py` | Independent matched-population update arithmetic; synthetic memory/compute proxy, no execution grant or inherited allowance. |

Synthetic checks: `python -B tools/core_stage2/run_checks.py`. To repeat only a
changed test: add `--test module.Class.test_name`. The evidence index lists the
latest outcome of each delta test; failed original runs are retained. Public
logs redact runtime paths; original logs remain ignored locally. Final index:
`evidence_index_v2.json`; the earlier index is retained before the final
inherited-time-rule regression. Existing
NetCDF4/NumPy deprecation warnings are recorded without changing dependencies.

`probe_models.py` tests full native-grid batch-2 forward/backward with zero
optimizer updates. `probe_validation_fusion.py` separately tests batch-8
inference memory and tiny CUDA AMP B7/B8 connectivity. Finite gradients and
parameter matching do not establish scientific effectiveness. The initial
zero MEE/fusion paths legitimately start with some zero parameter gradients.

Real-data checks use `check_connections.py` and the explicit unread-f003
continuation, existing inventories and CF receipts: fixed samples, aggregate
GFS cap 8 MiB, seven-band cap two files/16 MiB, no raw scan or target-payload
read. They write only to ignored `.local/`. Do not rerun completed raw checks
without a changed question and read budget. `prepare_matrix.py` joins existing
metadata and measured synthetic profiles without opening weather payloads.
Real receipts, selected populations, private paths and new research results
are intentionally absent from the public branch.

Researcher choices still needed (none are training authorization):

| Choice | Concrete alternatives and consequence |
| --- | --- |
| Same-valid vintage | Latest init minimizes lead but unknown historical release prevents NRT claims; fixed older cycle has longer lead but better separation from target-time initialization. Source caveats remain. No selection is implicit. |
| PWAT reference / M | Positive 2023-Train mean preserves positivity and uses no Dev fitting; approved fixed physical reference has simpler cross-dataset units but requires a justified value. `M=PWAT/ref*O` retains lee sign; `M=PWAT/ref*W` only enhances ascent proxy. No z-score/clipping default. |
| DEM footprint / edges | 0.02-degree native-IR-scale footprint retains more slope structure; 0.10-degree target footprint smooths opposing slopes. Both average native metre derivatives, not differentiate averaged heights. Complete native stencils/one-cell halo are implemented; mosaic seams and source datum need production evidence. Partial-support thresholds are not invented. |
| MEE / DTFM | Candidate T/RH850/700, MEE width16 and target-grid insertion need freeze; adding T/RH500 changes the channel contract. DTFM four-scale widths48/96/192/256, condition width16 and bound0.5 are tested candidates, not backbone insertion approval. B7/B8 adapters each have 2,319,408 active parameters in that configuration; full B7/B8 models are not yet wired. |
| Formal comparison | Choose one existing loss arm, paired seed and epoch budget; verify common seven-band population and fit new Train scalers first. Old B1 metrics cannot be directly compared if populations differ. New formal budgets are independent and zero-replay by default. |

The next useful work is the bounded production of the selected common
population and Train scalers after its reading budget is approved, followed by
an explicit B3/B4 experiment authorization. No seed2028, FinalFit or 2025 access.
