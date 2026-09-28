# YunTAPR-Net approved spatial freeze

This run is the current researcher-approved spatial decision snapshot: `YunTAPR_STAGE0_SPATIAL_v1_run_20260928T102636_513428Z`.

Primary boundary: FROZEN/BOUNDARY/yunnan_gadm41_level1_boundary.geojson.
Primary evaluation mask: FROZEN/MASK/yunnan_evaluation_mask_center_gadm41_imerg_v1.nc.
Authority and content-addressed registration: freeze_registry.json. Registry SHA256: `04077f6d33f7535bcff28d426de4c1970da6c86255c32f16ec043fe2c12779df`.

Before consuming frozen files, call `verify_frozen(run_path)` from src/frozen_contract.py. It checks all artifact hashes, all five identity attributes, geometry hash, exact coordinate arrays, ascending orientation, dimensions, 3430 cells and center predicate. A replaced artifact raises ValueError. The registry and report are versioned evidence, not a claim of filesystem-enforced write protection.

The original candidate is byte-preserved under PROVENANCE; the formal mask was copied from it and only its global metadata changed. All variables, dtype, dimensions and values are unchanged. Its inherited cell-bounds arrays do not freeze an input-grid/aggregation convention; the primary rule uses centers only.

Archive source and original-member hashes, canonical original-geometry JSON hash, normalized WKB supplementary hash, coordinate hashes and generation-script hashes are saved. Geometry-hash definitions are explicit. Original raw MultiPolygon structure is preserved; the old union Polygon has identical spatial geometry and center-mask values. No geometry repair/simplification was performed.

COMPARISON intersection is non-primary and byte-identical to old candidate. DEM root inventory registers SRTM without creating a DEM product. AWS_Skadi remains separate. Remaining choices are listed in the report and new decision log.

Python: `F:\pytorch\Research\.venv\Scripts\python.exe`; dependencies unchanged. Source raw IMERG coordinates were reread through one 380398-byte English temporary copy with size/SHA256 verification, then cleaned. No raw or old-run writes. No next-stage work.

For a future version, require an explicit researcher change decision and a new run; do not rerun freeze.py into this completed directory or overwrite this registry.
