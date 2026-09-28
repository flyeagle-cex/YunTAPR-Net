# YunTAPR-Net public GitHub export

The target repository is public. [GADM's license](https://gadm.org/license.html) does not permit redistribution of its data without prior permission. This export therefore omits the GADM source geometry, derived mask cell payloads, and all `.nc`/`.npz`/`.geojson` scientific arrays or geometry payloads. Their local source paths, sizes, and SHA256 values remain in `manifests/public_repository_omissions.csv`; the frozen source files themselves remain unchanged on the workstation. No claim of legal permission to publish those payloads is made.

The initial public export contained 951 copied source/evidence files (140,639,850 bytes). The original staging selection was 970 files; 19 payloads were removed before Git initialization or push. `manifests/included_files.csv` lists that initial snapshot. Later run additions carry their own public export manifests. Existing run reports may link to locally preserved files that this public snapshot cannot carry; the hash and provenance records allow audit against the local freeze.

## Stage-0 / B0 engineering evidence

This is a versioned source and evidence snapshot prepared for GitHub review. It is not a scientific data release or a B0 formal-training result.

The public snapshot contains project code, Stage-0 outputs, B0 engineering smoke, and B0 formal-readiness resolution. Earlier failed runs remain represented. See `manifests/included_files.csv` for per-file SHA256 and local source path.

The initial selection excluded 28 named files by type or the 5 MB file cap (583,874,320 bytes), plus cache, Zarr, benchmark candidate and temporary directories. Public curation excluded a further 19 payloads before upload. See `manifests/omitted_named_files.csv`, `manifests/public_repository_omissions.csv` and `manifests/source_summary.csv`. The excluded directory counts are not part of the named-file omission tables. Raw Himawari, IMERG, GFS and DEM roots were never source roots for this export. Source runs were read only.

The original formal-readiness report is in `evidence/outputs/stage1_b0_formal_readiness_resolution/run_20260928T124313_169375Z/FINAL_B0_FORMAL_READINESS_REPORT.md`. Its result is **B0_FORMAL_NOT_READY**: 30 focused tests passed, while 12 entry items remain blocked. The prior smoke remains PASS. The 2025-10 IMERG V07 Final gap remains MISSING; the discovered Late files were not substituted. Candidate timing, input domain, context, splits, normalization method, and formal architecture were not frozen.

The later [B0 spatial/probability contract run](evidence/outputs/b0_spatial_probability_contract_resolution/run_20260928T144303_935304Z/FINAL_B0_SPATIAL_PROBABILITY_CONTRACT_REPORT.md) adds 40 passing geometry and synthetic probability tests. It reports that the actual coordinate arrays give a uniform 5×5 center membership **under the explicitly stated half-open edge rule**, while excluding the northmost native row and eastmost native column. The rule is a candidate, not a frozen scientific projection. See its `PUBLIC_EXPORT_NOTICE.md` and `public_export_manifest.csv`; local coordinate arrays and all GADM-derived mask payloads remain off GitHub. Formal B0 remains on hold.

Reports and scripts can contain local absolute provenance paths; they point to the original workstation and do not make raw files available from this repository. CSV and Parquet pairs are retained when each component is within the export cap. Large scientific audit tables and storage benchmark arrays stay local; refer to the original run manifests and this export's omission table before claiming full reanalysis from this GitHub snapshot.

No training or next stage was launched by the export.
