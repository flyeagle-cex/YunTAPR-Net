# Auxiliary time conflict classification

Reused baseline: F:\pytorch\Research\outputs\stage0_continuous_engineering\run_20260928T041855_828904Z. No full main raw metadata rescan.
All 24,388 prior primary forecast identities remain unchanged. Classified 17,665 prior auxiliary conflict records:
- ALTERNATIVE_REFERENCE_TIME: 17,665; current CF units and auxiliary udunits refer to different epochs.
- STALE_HISTORY_TOKEN: 3,628; overlapping subset of the above, not additional unique files.
- TRUE_FORECAST_TIME_CONFLICT detected in primary init/valid/lead evidence: 0.
- NO_AUXILIARY_CONFLICT: 6,723.

CONVERSION_TIMESTAMP, SOURCE_FILENAME_TOKEN and DOWNLOAD_OR_ARCHIVE_RECORD are separate context categories; their mere presence is not an anomaly.
Missing publication timestamps remain UNKNOWN. A generation-center/process identifier is not a generation timestamp.
No evidence here proves that every converted array originated from its claimed forecast; arithmetic consistency and metadata classification do not erase that limitation.

This run reread 9 allowlisted primary files covering [2019, 2021, 2023, 2024, 2025], conflict/non-conflict and stale-History examples. Current coordinates and init/valid/lead match prior evidence; sample SHA256 unchanged.
Strata where samples do not exist were not fabricated: 2019 has no auxiliary-conflict files; 2025 has no non-conflict files in the baseline. Selection counts are recorded in logs/main_sample_strata.json.
Detailed raw sample metadata and per-sample comparisons are saved alongside this report. The complete classification table is derived from existing audit metadata only.

Thermo: 0 auxiliary conflict flags; all 12,960 primary time identities PASS.
Release/availability for both sources: **NOT ESTABLISHED FROM CURRENT FILE METADATA**. All thermo conservative +5h fields explicitly state an assumption, not observed per-file publication.
