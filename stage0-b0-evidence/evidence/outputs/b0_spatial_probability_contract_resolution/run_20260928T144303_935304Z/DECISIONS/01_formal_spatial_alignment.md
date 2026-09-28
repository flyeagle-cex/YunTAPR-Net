# Decision 01 — formal spatial alignment

**Current evidence.** Actual 501×501 native and 100×100 target axes, opposite latitude direction, near-boundary native centers, and all 3430 frozen evaluation cells retained. See `../SPATIAL/native_target_exact_geometry.md` and full mapping CSV. SP04 is a researcher-approved **direction**, not an approved exact projection.

| Option | Pros | Cons | Scientific consequence | Engineering consequence |
|---|---|---|---|---|
| SA01 nearest center | Reproducible with tie rule, simple | Aliases cloud structure | Point sample, not cell observation | Very cheap; tie and invalid handling needed |
| SA02 bilinear center | Smooth coordinate-based map | Can soften cold convective pixels | Interpolated brightness temperature | Explicit descending-axis and invalid-weight logic |
| SA03 footprint mean/valid mean | Cell-support interpretation | Dilutes small cold cores; footprint uncertain | Defines areal summary of radiance/temperature | Need area overlap, support fraction, edge rule |
| SA04 native encoder + projection | Preserves native features longer | Projection and decoder choices remain | Native-scale features inform target prediction | Higher memory; adaptive pooling alone is not georeferencing |
| SA05 coordinate-defined hybrid | Explicit target support plus native detail | Requires physical support/boundary decision | Transparent multiscale observation support | More code, verifiable index tables |

**Engineering recommendation for researcher review:** use SA05/SA04 as the leading *design investigation*: keep native detail and use explicit, versioned coordinate-aware projection to target cells. Do not declare nearest, bilinear, fixed 5×5, adaptive pooling, or learned projection final based on this geometric audit. Missing-fraction and edge support must be part of any approved rule. No performance ranking was run.

**Decision needed:** choose source pixel support and target footprint semantics, boundary ownership/tolerance, projection location and operator, missing support threshold, and padding/crop rule. Then freeze a reproducible coordinate-index mapping with tests for B0–B8. **RESEARCHER_DECISION_REQUIRED.**
