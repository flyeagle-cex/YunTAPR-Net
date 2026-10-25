# Stage 3: evidence-only population and statistics preparation

## Authorized data execution, 2026-10-24

The manifest-bound f006 campaign is complete on isolated branch
`dev/stage3-data-production-20261024`. See `execution_summary/main.pdf`
(editable `main.tex`) and `execution_summary/evidence.json` for the sanitized
outcome and receipt fingerprints. Private manifests, source paths, fitted
scalers and the byte/statistics ledger remain under ignored `.local/`.

`tools/core_stage3/produce_authorized.py` adds one serial, metered campaign with
a pilot, precommitted intents, a grant lock and no automatic rereads/retries.
`summarize_authorized.py` reconciles completed SQLite/JSON receipts and existing
target QC; it forbids raw weather opens. No optimizer or training was launched.
The execution receipt is retained unchanged; a reporting placeholder in its
inherited high-intensity baseline field is corrected in the cached-only final
summary and in future driver output. It did not affect membership or scalers.

The remaining text records the **c5ccd52 preparation-stage state**, before this
separately approved campaign. It is not the current execution status.

## Preparation-stage evidence

Base: `e4563a0`. Source/model/history modules from Stage 2 are unchanged. The
inherited 52+20 tests were not rerun. New tests are synthetic CPU/SQLite only.

- `tools/core_stage3/plan_population.py`: reads existing pinned B1 manifests,
  CF frame indexes, GFS inventories and target QC evidence. It never stats or
  opens raw sources. Separate f000/f003/f006 and union upper bounds, source
  deduplication, byte budgets, month/hour distributions, rainy-pixel and
  descriptive high-intensity scene loss are written to ignored `.local/`.
- `stage3/statistics.py`: per-source sufficient statistics, scene-exposure
  weighted merge through existing `TrainMoments`, unchanged frozen B13, masked
  GFS moments, explicit 11/13-variable contracts and positive Train PWAT scale.
  SQLite commits a read intent before invoking a future decoder. Completed jobs
  are reused; pending/uncertain jobs block automatic rereading. A changed source
  manifest, grant or processing identity cannot silently reuse a cache.
- `stage3/terrain_boundary.py`: bounded native DEM shared-edge join, exact
  coordinate/validity/elevation agreement; no seam averaging or automatic repair.
  Existing metric-gradient and pressure-mask implementations are reused.
- `config/core_stage3/paired_protocol_candidate.json`: same IDs, labels,
  initialization, ordering, optimizer/evaluation policy; one seed/E0 candidate,
  9 epochs and batch2/validation8. Exact attempts remain null until actual common
  population is verified. Old 5228-step scheduler/run identities cannot be reused.

The statistics core has been tested, but no real-data statistics production,
complete joint population or new formal training occurred. A future authorized
driver must bind existing bounded raw readers and CF/grid validation to the
cache; its decoder/physical I/O accounting still needs real-data commissioning.
The cache ledger alone does not verify decoder honesty or grant permissions.

For each finalized output the code supplies population/source manifest SHA,
processing version, channel order, means, standard deviations, counts, valid
fractions, source identities/exposures and positive-PWAT reference. Dev sources
produce QC only. Source moments can be retained before membership is finalized;
only final Train membership contributes to fitted scalers. A changed membership
requires recombining cached moments, not rescanning completed raw files.

Important remaining boundaries:

1. Fixed f006 is a recommendation. Same-valid source init is earlier, but actual
   historical release remains unproven. No operational or causal availability
   claim follows. Source and time-of-day selection changes the population.
2. V1.3 T500/RH500 are missing from the Stage2 eleven-channel MEE prototype.
   Thirteen-variable moments are supported as a candidate. The model adapter is
   deliberately unchanged until approval; data files need not change.
3. Two end-of-October targets in existing B1 records have analysis on November 1.
   Stage2's time adapter rejects those dates. They are excluded from the proposed
   raw-reading manifests pending a researcher decision, with history untouched.
4. Existing scene-max >=20 mm/h QC is descriptive. It cannot establish counts of
   high-intensity pixels or extreme events; no new target payload was read.
5. `decisions/main.tex` is the editable short decision table. Real manifests,
   indexed byte totals, aggregate research QC analyses and intermediate statistics
   remain local. Public artifacts contain code and synthetic evidence only.

Run only changed checks: `python -B tools/core_stage3/run_checks.py --test
module.Class.test_name`. No real-data production command or training launcher is
added by this stage. Scientific choices and one consolidated manifest-bound
reading request await researcher approval.
