# Stage4 B3/B4 implementation candidate

Base `0cf938fb2037dec84a86cdeb0573b169103330be`; isolated branch
`dev/stage4-b3-b4-ready-20261024`. No formal experiment was launched.

- `src/yuntapr/experimental/core_innovation/stage2/models.py` and
  `environment.py`: explicit 13-variable MEE/scalers, width16, independent masks,
  existing target-grid zero-initialized residual. Original 11-variable default
  and B3 are preserved. Statistics order is the existing eleven variables followed
  by T500/RH500; no positional reinterpretation of produced statistics.
- `stage4/data.py`: pins final population/scaler/manifest/source hashes; native
  7x6 input, exact f006, existing IMERG decoder, frozen region mask, once-only
  source meter. No QC population production or statistics fitting. Each reader
  owns one finite pass; completed sources are not automatically reread. Target
  byte buffers are bounded to512MiB. Formal readers require explicit per-pass
  limits and a separate launch authorization; the dry subset cap is not reused.
- `stage4/engine.py`: common initialization/orders, existing E0 and AdamW groups,
  480-step warmup and original 24,000-step cosine horizon, first4,320 updates per
  model. Durable, nonrefundable attempt reservations, strict8,640 paired cap,
  full Train/Dev coverage, fixed ninth-epoch endpoint, new LAST/receipts only.
  No automatic restore/retry, BEST selection or historical quota reuse.
- `stage4/evaluation.py`: reuses frozen exact score ties/AUROC/AP, FP64 loss,
  Brier, conditional coverage/pinball and existing rain-rate bins. Adds UTC-hour,
  inherited scene-max>=20 partitions, optional explicit altitude masks and matched
  B4-minus-B3 summaries. Altitude grid/edges remain unapproved; no real DEM read.

`tools/core_stage4/dry_run.py` is the only launch CLI: it cannot train. Supply
private Stage3 run/request paths and a new ignored `docs/core_stage4/.local/`
output. Set `PYTHONHASHSEED=40261024` before Python; cuBLAS settings are set before
torch import. It loads only two May1 Train and eight May1/2 Dev scenes in manifest
order, caches necessary normalized tensors locally, runs real batch2 backward and
batch8 inference, and rejects optimizer construction/step. The selection is not
based on rainfall or model performance.

Future formal API is `PairedExecutor(plan, folder, decision=approved_decision,
altitude=approved_altitude_groups).run(approved_reader_factory)`. The factory
receives role, epoch, exact IDs and a new scoped receipt directory and returns a
`BatchReader` with independently approved full-pass file/byte limits. No default
formal seed/approval is supplied. `FormalDecision` rejects the dry seed, old
2026/2027/2028 seeds, a different population, incomplete science decisions or a
different cap. Set the researcher-selected hash seed before the future process.

Evidence: `summary/main.pdf` (editable `main.tex`), `evidence.json`, and targeted
test logs. Nine distinct new checks passed (8 first, then only2 affected checks
plus1 new startup-seed check). Historical tests and the unchanged GPU numerical
probe were not rerun. The initial import-only failure was an old campaign seed
gate triggered by importing a generic helper; Stage4 now avoids that import,
without modifying the old engine. Post-probe changes were metadata/guards and
inactive formal-run receipts; cached verification added zero raw reads.

All normalized batches, identities containing private source paths, raw access
ledger and untrained diagnostic numbers remain ignored/local. Public evidence
contains shape/resource/coverage checks only. Untrained predictions are not
research performance results. Data selection covers00/06/12/18UTC only and has
no established historical release timestamps; no all-day NRT or2025 claims.
