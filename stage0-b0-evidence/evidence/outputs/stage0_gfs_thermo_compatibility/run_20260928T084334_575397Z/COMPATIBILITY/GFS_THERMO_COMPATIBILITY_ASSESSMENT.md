# GFS_thermo compatibility assessment

Overall engineering verdict: **PARTIALLY_COMPATIBLE**.

| item | dimension | status | evidence |
| --- | --- | --- | --- |
| A | file structure compatibility | PASS | All thermo NETCDF4, one structural version; companion variable schema is readable without format rewriting |
| B | grid compatibility | PASS | 12960 exact array matches; both coordinate hashes agree; max absolute differences 0 |
| C | forecast init compatibility | PASS | All thermo init keys exist in reused main inventory; [00,06,12,18] UTC |
| D | lead compatibility | PASS | All thermo leads [0,3,6]h match main; thermo global coverage is a subset |
| E | valid-time compatibility | PASS | All thermo identities and paired valid times agree |
| F | variable semantic compatibility | PASS | Explicit Temperature_isobaric and Relative_humidity_isobaric at three required levels; no q/dewpoint/potential-T substitution |
| G | unit compatibility | PASS | T K, RH %, pressure Pa agree with available main metadata; no data conversion |
| H | pressure-level compatibility | PASS | 50000/70000/85000 Pa present; main PS Pa allows future comparison, no mask computed |
| I | research-period coverage | PASS | 24 months and 8820/8820 pairs have all six target metadata fields |
| J | source lineage compatibility | PARTIAL | SUPPORTED_WITH_CAVEATS: declared GFS archive/forecast identifiers agree; converted payload lineage not independently proven |
| K | one-to-one pairing quality | PASS | 12960/12960 thermo keys unique and matched; no ambiguous selections |

The partial component is source/conversion lineage, not missing T/RH in the requested research months.
Across all historical main keys there are 11,428 MAIN_ONLY entries, outside the requested 2023–2025 March–October period. Thermo is not a complete companion for every historical main-library key.
Within the requested period, all 24 months satisfy the exact structural coverage criteria; they are READY in the monthly audit table.

Can current thermo fill T850/T700/T500/RH850/RH700/RH500 in 2023–2025 March–October?
**Yes as a structural, temporal and metadata-completeness candidate: 8,820/8,820 required forecast pairs.** Dataset adoption remains unapproved because source/conversion provenance and operational vintage decisions require researcher review.
Source lineage: SUPPORTED_WITH_CAVEATS. No assessment item upgrades conservative +5h to observed availability.

READY here is strictly a coverage status. Existing official predictor readiness was not rewritten; READY_CANDIDATE does not mean an approved Dataset, integration, Stage-0 scientific closeout or B0 permission.
