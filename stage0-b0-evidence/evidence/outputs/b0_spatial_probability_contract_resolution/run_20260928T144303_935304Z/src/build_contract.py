"""Read-only B0 spatial/probability contract evidence builder.

Run with F:/pytorch/Research/.venv/Scripts/python.exe. No raw data are changed.
Scientific choices remain candidates pending researcher approval.
"""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import netCDF4
import numpy as np


ROOT = Path(r"F:\pytorch\Research\outputs")
READINESS = ROOT / "stage1_b0_formal_readiness_resolution" / "run_20260928T124313_169375Z"
FREEZE = ROOT / "stage0_spatial_decision_update" / "run_20260928T102636_513428Z"
OUT_PARENT = ROOT / "b0_spatial_probability_contract_resolution"
GPROF = Path(r"C:\Users\chenerxiao\Desktop\降水反演的代码\gprof_ir-main")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def save_json(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def save_md(path: Path, body: str) -> None:
    path.write_text(body.strip() + "\n", encoding="utf-8")


def save_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"No rows: {path}")
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def edges(centers: np.ndarray) -> np.ndarray:
    c = np.asarray(centers, dtype=np.float64)
    assert c.ndim == 1 and len(c) > 1 and np.all(np.diff(c) > 0)
    e = np.empty(len(c) + 1, dtype=np.float64)
    e[1:-1] = (c[:-1] + c[1:]) / 2
    e[0] = c[0] - (c[1] - c[0]) / 2
    e[-1] = c[-1] + (c[-1] - c[-2]) / 2
    return e


def axis_mapping(native: np.ndarray, target: np.ndarray, tol: float = 1e-5) -> list[dict]:
    """Return source *original* indices, with boundary ambiguity explicit."""
    e = edges(target)
    result = []
    for i, center in enumerate(target):
        low, high = map(float, e[i:i + 2])
        strict = np.flatnonzero((native > low + tol) & (native < high - tol)).tolist()
        raw_half_open = np.flatnonzero((native >= low) & (native < high)).tolist()
        low_boundary = np.flatnonzero(np.abs(native - low) <= tol).tolist()
        high_boundary = np.flatnonzero(np.abs(native - high) <= tol).tolist()
        nearest = int(np.argmin(np.abs(native.astype(np.float64) - float(center))))
        result.append(dict(target_index=i, target_center=float(center), lower=low, upper=high,
                           strict_source_indices=strict, raw_half_open_source_indices=raw_half_open,
                           lower_boundary_source_indices=low_boundary,
                           upper_boundary_source_indices=high_boundary, nearest_source_index=nearest,
                           nearest_source_center=float(native[nearest]),
                           nearest_offset_degrees=float(native[nearest] - center)))
    return result


def arr_summary(a: np.ndarray) -> dict:
    d = np.diff(a.astype(np.float64))
    return dict(shape=list(a.shape), dtype=str(a.dtype), direction="ascending" if np.all(d > 0) else "descending",
                minimum=float(np.min(a)), maximum=float(np.max(a)), first=float(a[0]), last=float(a[-1]),
                spacing_signed_min=float(np.min(d)), spacing_signed_median=float(np.median(d)),
                spacing_signed_max=float(np.max(d)),
                unique_spacing_rounded_8=[float(x) for x in np.unique(np.round(d, 8))],
                raw_bytes_sha256=hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest())


def rows_for_tau() -> list[dict]:
    rows = []
    formulas = {
        "Q01": lambda i: (i - .5) / 32,
        "Q02": lambda i: i / 33,
        "Q03": lambda i: 1 - (1 - (i - .5) / 32) ** 2,
    }
    for id_, func in formulas.items():
        vals = [func(i) for i in range(1, 33)]
        assert len(vals) == 32 and all(0 < v < 1 for v in vals)
        assert all(a < b for a, b in zip(vals, vals[1:]))
        for i, v in enumerate(vals, 1):
            rows.append(dict(candidate_id=id_, rank=i, tau=f"{v:.12f}", min_tau=f"{vals[0]:.12f}",
                             max_tau=f"{vals[-1]:.12f}", count_ge_0_5=sum(x >= .5 for x in vals),
                             count_ge_0_9=sum(x >= .9 for x in vals),
                             formula={"Q01": "(i-0.5)/32", "Q02": "i/33", "Q03": "1-(1-(i-0.5)/32)^2"}[id_],
                             status="RESEARCHER_DECISION_REQUIRED"))
    return rows


def main() -> Path:
    stamp = datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%S_%fZ")
    out = OUT_PARENT / stamp
    for d in ("SPATIAL", "PROBABILITY", "MODEL", "DECISIONS", "tests", "logs", "src"):
        (out / d).mkdir(parents=True, exist_ok=False)
    h_path = READINESS / "SPATIAL" / "himawari_actual_coordinates.npz"
    i_path = FREEZE / "FROZEN" / "MASK" / "imerg_actual_coordinates.npz"
    m_path = FREEZE / "FROZEN" / "MASK" / "yunnan_evaluation_mask_center_gadm41_imerg_v1.nc"
    registry = json.loads((FREEZE / "freeze_registry.json").read_text(encoding="utf-8"))
    assert sha(i_path) == registry["artifacts"]["coordinates"]["sha256"]
    assert sha(m_path) == registry["artifacts"]["primary_mask"]["sha256"]
    with np.load(h_path) as h, np.load(i_path) as g:
        hlat_full, hlon_full = h["latitude"].copy(), h["longitude"].copy()
        ilat_full, ilon_full = g["lat"].copy(), g["lon"].copy()
    with netCDF4.Dataset(m_path) as ds:
        assert np.array_equal(ilat_full, ds.variables["lat"][:])
        assert np.array_equal(ilon_full, ds.variables["lon"][:])
        mask_full = np.asarray(ds.variables["yunnan_mask"][:], dtype=bool)
    assert mask_full.shape == (130, 140) and int(mask_full.sum()) == 3430
    # Select actual samples; never reconstruct a coordinate with idealized steps.
    hr = np.flatnonzero((hlat_full >= 20) & (hlat_full <= 30))
    hc = np.flatnonzero((hlon_full >= 97) & (hlon_full <= 107))
    ir = np.flatnonzero((ilat_full >= 20) & (ilat_full <= 30))
    ic = np.flatnonzero((ilon_full >= 97) & (ilon_full <= 107))
    hlat, hlon = hlat_full[hr], hlon_full[hc]
    ilat, ilon = ilat_full[ir], ilon_full[ic]
    assert (len(hlat), len(hlon), len(ilat), len(ilon)) == (501, 501, 100, 100)
    assert np.all(np.diff(hlat) < 0) and np.all(np.diff(hlon) > 0)
    assert np.all(np.diff(ilat) > 0) and np.all(np.diff(ilon) > 0)
    assert int(mask_full[np.ix_(ir, ic)].sum()) == 3430
    # All source indices in tables refer to full-readiness arrays.
    lat_map = axis_mapping(hlat_full, ilat)
    lon_map = axis_mapping(hlon_full, ilon)
    out_arrays = out / "SPATIAL" / "sp04_coordinate_arrays.npz"
    np.savez_compressed(out_arrays, native_lat=hlat, native_lon=hlon, target_lat=ilat, target_lon=ilon,
                        native_lat_full_indices=hr, native_lon_full_indices=hc,
                        target_lat_full_indices=ir, target_lon_full_indices=ic)
    sources = {"himawari_coordinate_evidence": str(h_path), "himawari_evidence_sha256": sha(h_path),
               "imerg_frozen_coordinate_evidence": str(i_path), "imerg_evidence_sha256": sha(i_path),
               "frozen_mask_source": str(m_path), "frozen_mask_sha256": sha(m_path),
               "frozen_registry": str(FREEZE / "freeze_registry.json"),
               "himawari_raw_file_provenance": json.loads((READINESS / "SPATIAL" / "himawari_coordinate_metadata.json").read_text(encoding="utf-8"))["source"]}
    summaries = {k: arr_summary(v) for k, v in {"native_lat": hlat, "native_lon": hlon,
                                                "target_lat": ilat, "target_lon": ilon}.items()}
    save_json(out / "SPATIAL" / "sp04_coordinate_contract.json",
              dict(status="CANDIDATE_GEOMETRY_VERIFIED_NOT_FORMAL_MAPPING", domain="SP04 97-107E 20-30N",
                   axes=summaries, source_evidence=sources, source_lat_original_indices=[int(hr[0]), int(hr[-1])],
                   target_lat_original_indices=[int(ir[0]), int(ir[-1])],
                   source_lon_original_indices=[int(hc[0]), int(hc[-1])],
                   target_lon_original_indices=[int(ic[0]), int(ic[-1])],
                   evaluation_mask_cells_within_target=3430, evaluation_mask_total_cells=3430,
                   no_transpose=True, no_lat_flip=True, no_science_resampling=True))
    save_json(out / "SPATIAL" / "sp04_coordinate_hashes.json",
              dict(output_npz_sha256=sha(out_arrays), source_npz_sha256=sha(h_path),
                   frozen_imerg_npz_sha256=sha(i_path), axes_raw_bytes_sha256={k: v["raw_bytes_sha256"] for k, v in summaries.items()}))
    cell_rows = []
    for y in lat_map:
        for x in lon_map:
            cell_rows.append(dict(target_row=y["target_index"], target_col=x["target_index"],
                                  target_full_row=int(ir[y["target_index"]]), target_full_col=int(ic[x["target_index"]]),
                                  lat_center=y["target_center"], lon_center=x["target_center"],
                                  south=y["lower"], north=y["upper"], west=x["lower"], east=x["upper"],
                                  native_strict_interior_rows=";".join(map(str, y["strict_source_indices"])),
                                  native_strict_interior_cols=";".join(map(str, x["strict_source_indices"])),
                                  native_raw_half_open_rows=";".join(map(str, y["raw_half_open_source_indices"])),
                                  native_raw_half_open_cols=";".join(map(str, x["raw_half_open_source_indices"])),
                                  strict_interior_native_center_count=len(y["strict_source_indices"]) * len(x["strict_source_indices"]),
                                  raw_half_open_native_center_count=len(y["raw_half_open_source_indices"]) * len(x["raw_half_open_source_indices"]),
                                  south_boundary_rows=";".join(map(str, y["lower_boundary_source_indices"])),
                                  north_boundary_rows=";".join(map(str, y["upper_boundary_source_indices"])),
                                  west_boundary_cols=";".join(map(str, x["lower_boundary_source_indices"])),
                                  east_boundary_cols=";".join(map(str, x["upper_boundary_source_indices"])),
                                  nearest_native_row=y["nearest_source_index"], nearest_native_col=x["nearest_source_index"],
                                  nearest_native_lat=y["nearest_source_center"], nearest_native_lon=x["nearest_source_center"],
                                  nearest_lat_offset_deg=y["nearest_offset_degrees"], nearest_lon_offset_deg=x["nearest_offset_degrees"]))
    save_csv(out / "SPATIAL" / "target_cell_native_mapping.csv", cell_rows)
    sample_indices = [(0, 0), (0, 99), (99, 0), (99, 99), (50, 50), (49, 49), (1, 1), (98, 98), (0, 50), (50, 0)]
    save_csv(out / "SPATIAL" / "index_mapping_visual_check.csv",
             [dict(cell_rows[y * 100 + x], check_label=f"row{y}_col{x}") for y, x in sample_indices])
    lc = Counter(len(x["raw_half_open_source_indices"]) for x in lat_map)
    xc = Counter(len(x["raw_half_open_source_indices"]) for x in lon_map)
    cc = Counter(r["raw_half_open_native_center_count"] for r in cell_rows)
    boundary_counts = {axis: sum(bool(x["lower_boundary_source_indices"] or x["upper_boundary_source_indices"]) for x in maps)
                       for axis, maps in (("lat_cells", lat_map), ("lon_cells", lon_map))}
    geo = dict(lat_raw_half_open_counts=dict(sorted(lc.items())), lon_raw_half_open_counts=dict(sorted(xc.items())),
               cell_raw_half_open_counts=dict(sorted(cc.items())), boundary_touch_cells=boundary_counts,
               first_lat=lat_map[0], last_lat=lat_map[-1], first_lon=lon_map[0], last_lon=lon_map[-1],
               all_evaluation_cells_in_target=True, source_to_target_ratio="501/100=5.01; not exact 5-to-1",
               boundary_tolerance_degrees=1e-5,
               half_open_observed_uniform_5_by_5=all(len(y["raw_half_open_source_indices"]) == 5 for y in lat_map)
               and all(len(x["raw_half_open_source_indices"]) == 5 for x in lon_map),
               half_open_excluded_native_lat_rows=[int(i) for i in sorted(set(range(501)) - set().union(*(set(y["raw_half_open_source_indices"]) for y in lat_map)))],
               half_open_excluded_native_lon_cols=[int(i) for i in sorted(set(range(501)) - set().union(*(set(x["raw_half_open_source_indices"]) for x in lon_map)))])
    save_json(out / "SPATIAL" / "geometry_summary.json", geo)
    save_md(out / "SPATIAL" / "native_target_exact_geometry.md", f"""
# SP04 native-to-target geometry (actual coordinate evidence)

Himawari 501×501 coordinates: latitude descending 30→20°, longitude ascending 97→107°. Actual IMERG target subset: latitude ascending {ilat[0]:.9f}→{ilat[-1]:.9f}°, longitude ascending {ilon[0]:.9f}→{ilon[-1]:.9f}°, 100×100. Frozen full IMERG grid is 130×140; the 3430 Yunnan mask cells all fall in this 100×100 subset. Context cells outside the Yunnan mask are **not** evaluation cells.

Target edges are inferred by midpoints of the *actual float32 target center arrays*, with endpoint half-step extrapolation in float64. These inferred edges are geometry diagnostics, not approved pixel-footprint metadata. Source center and target-edge numeric values can differ by float32 rounding. The `raw_half_open` diagnostic uses the exact numeric rule `[lower, upper)`; `strict_interior` excludes source centers within 1e-5° of either edge; boundary columns expose these near-coincident centers without assigning ownership. The 1e-5° tolerance is an engineering comparison tolerance, not a scientific resampling decision.

- Target-center phase against source grid: nearest-source offsets are stored for every cell; both latitude and longitude show an approximately half-native-step phase, but float32 roundoff prevents treating it as exact mathematical equality.
- 1D raw half-open source-center counts: latitude {dict(sorted(lc.items()))}; longitude {dict(sorted(xc.items()))}. 2D counts: {dict(sorted(cc.items()))}. **For these actual arrays, all 10,000 target cells contain exactly 5×5 native centers under the raw numeric `[lower,upper)` rule.** This is an observed candidate mapping, not a universal property of 0.02°/0.1° grids.
- Target boundaries touching a native center within tolerance: {boundary_counts}. Four-by-four source centers per cell are strictly interior under the stated tolerance; the additional row and column depend on boundary ownership. The 5×5 assignment is therefore conditional on the half-open rule.
- `501` source centers span both 20/30° and 97/107° endpoints. The half-open rule assigns original native latitude indices 1–500 and longitude indices 0–499 across all cells, **excluding the northmost row 0 and eastmost column 500**; it is not a lossless 501→100 reshape. Another boundary convention would shift ownership or include endpoints differently.
- Original source row 0 is north, original target row 0 is south. Every mapping row records **original source indices** and target full-grid indices. No array flip or transpose was performed.
- A fully deterministic 5×5 center-membership index table **has been constructed for the explicit raw half-open rule**, along with strict interiors, boundary ties, and nearest source indices. It does not declare the half-open rule scientifically final or assert native pixel footprints coincide with IMERG cells.
- Off-by-one risks: endpoint ownership at both outer edges; north/south row reversal; floating boundary ties; last-target-cell exclusion under half-open numeric comparison; and a 501→500 silent crop. No such crop/resampling was applied.

Evidence: `sp04_coordinate_contract.json`, `sp04_coordinate_hashes.json`, `target_cell_native_mapping.csv`, and `index_mapping_visual_check.csv`. Raw coordinate arrays are local only.
""")
    options = [
        ("SA01", "Nearest native center at each target center", "Center-specific, tie policy needed", "Low; drops subcell cloud structure", "Nearest invalid must remain invalid or explicit fallback", "All centers within native domain", "Easy", "Low", "Aliasing and half-step ties"),
        ("SA02", "Bilinear native-to-target-center", "Coordinate-aware if exact axes supplied", "Moderate; smooths extremes", "NaN-aware weights and minimum support required", "Four-neighbor edge support check", "Easy", "Medium", "Cold cloud-top attenuation and invalid blending"),
        ("SA03", "Target footprint mean or valid-weighted mean", "Footprint and area support require a frozen rule", "Low; local extreme diluted", "Valid fraction and weight sum must be outputs", "Boundary pixels and partial support explicit", "Easy", "Medium", "Brightness-temperature mean may not represent convective features"),
        ("SA04", "Native encoder then explicit target projection", "Only coordinate-aware projection is exact by construction", "High until projection; decoder detail may change", "Carry validity/support through encoder and projection", "Projection edge behavior explicit", "Strong", "High", "Adaptive pooling/interpolation alone may silently shift geography"),
        ("SA05", "Coordinate-defined fixed aggregation plus native pathway", "Potentially exact after boundary/footprint decision", "High if native branch retained", "Support-weighted validity and missing fraction", "Endpoint ownership must be frozen", "Strong", "Medium-high", "Near-5 ratio tempts an invalid hard-coded 5×5 reshape"),
    ]
    save_csv(out / "SPATIAL" / "spatial_alignment_candidates.csv",
             [dict(candidate_id=a, method=b, coordinate_exactness=c, preserves_native_detail=d,
                   missing_semantics=e, edge_support=f, future_B0_B8_consistency=g,
                   engineering_complexity=h, scientific_risk=i, reproducibility="Deterministic only with versioned axes and frozen projection rule",
                   future_GFS_DEM_compatibility="Target-grid alignment possible; fusion stage and resolution still undecided",
                   status="RESEARCHER_DECISION_REQUIRED") for a, b, c, d, e, f, g, h, i in options])
    save_md(out / "DECISIONS" / "01_formal_spatial_alignment.md", """
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
""")
    save_csv(out / "PROBABILITY" / "quantile_tau_candidates.csv", rows_for_tau())
    save_md(out / "PROBABILITY" / "local_probability_design_evidence.md", f"""
# Bounded local probability-design evidence

1. **V1.3/user-provided contract:** occurrence head `P(R>0.1 mm h⁻¹)`, 32 conditional quantiles, `log1p(R)` suggested, focal BCE indicated, loss-family symbols `L_det,L_qr,L_ext,L_nc,L_KD` with `L_KD=0` for B0–B8. `λ_ext=0.2` is an initial suggestion and `λ_nc=0.05` optional. Exact τ, conditioning threshold, loss weights, tails, and interpolation remain open. Source: supplied task text and local V1.3 PDF at `C:/Users/chenerxiao/Downloads/YunTAPR-Net_V1.3_云南全境近实时降水反演_科研主体掌握与成果转化正式方案 (1).pdf` (not parsed by this builder).
2. **Local external GPROF-IR material:** `{GPROF / 'manuscript/main.tex'}` lines 409–417 explicitly say 32 posterior quantiles trained with quantile-regression loss, posterior mean reconstructed from approximated CDF, and arbitrary-rate exceedance probabilities. Lines 975–984 reiterate this. `{GPROF / 'src/gprof_ir/retrieval.py'}` imports `pytorch_retrieve` and implements inference; `{GPROF / 'src/gprof_ir/config_files/gprof_ir_ss_inference.toml'}` requests `ExpectedValue`. Bounded search of this local GPROF-IR source/manuscript found **no exact τ vector, conditional-rain threshold, focal BCE, or non-crossing definition**. `pytorch_retrieve` is absent from the fixed Python environment, so its underlying implementation was not inspected as an authoritative source here. GPROF-IR's 32-quantile **unconditional posterior** design is not proof of YunTAPR-Net's dual-head conditional distribution.
3. **Current engineering candidates only:** Q01/Q02/Q03, NC01/NC02/NC03, and SA01–SA05 are proposed for explicit researcher selection. No new source or code was downloaded. Absence in this bounded search is not evidence that no published definition exists.
""")
    save_md(out / "PROBABILITY" / "rain_conditioning_semantics.md", """
# Conditional rain is an unresolved scientific definition

Let `R≥0` be physical precipitation and `p=P(R>0.1)`. The phrase *positive rain* could mean `R>0` or `R>0.1` mm h⁻¹. For a mathematically consistent two-part exceedance formula at `r>0.1`, define `F₊(r)=P(R≤r | R>0.1)`; then `P(R>r)=p[1−F₊(r)]`, and at `r=0.1`, `P(R>0.1)=p` exactly. Conditional pinball pixels would be valid `R>0.1`; valid `0≤R≤0.1` still train the occurrence head as 0.

If instead `F₊=P(R≤r | R>0)` while `p=P(R>0.1)`, the formula above is generally wrong: the conditional law includes `0<R≤0.1` drizzle while the mixing weight excludes it. A separate `P(R>0)` and subthreshold component would be required. Even with conditioning on `R>0.1`, `p E[R|R>0.1]` is **the expectation of threshold-censored rain** (`R·I(R>0.1)`), not exact physical `E[R]`, which also includes `(1−p)E[R|R≤0.1]`. Do not silently zero drizzle or label the censored value the full physical mean.

**Candidate recommendation:** conditional law `R>0.1` for algebraic consistency with the occurrence head; researcher must approve the treatment of subthreshold rain and deterministic-mean label. **RESEARCHER_DECISION_REQUIRED.**
""")
    save_md(out / "DECISIONS" / "02_quantile_tau_grid.md", """
# Decision 02 — 32 τ levels

No exact local original τ vector was found. `Q01=(i−0.5)/32` has min 0.015625, max 0.984375 and 16 points at/above median. `Q02=i/33` has min ≈0.030303, max ≈0.969697 and 16 points at/above median. `Q03=1−[1−(i−0.5)/32]²` is an **illustrative, unsourced** high-tail-dense candidate; it changes coverage of the lower half and cannot be presented as GPROF-IR's rule. Exact values and counts are in `../PROBABILITY/quantile_tau_candidates.csv`.

Q01 reaches farther into both tails; Q02 leaves a wider uncovered extreme tail; Q03 allocates more quantiles to high precipitation but gives poorer lower-tail resolution. A simple unweighted mean of pinball losses over nonuniform Q03 τ is **not** the same quadrature for CRPS as a uniform τ grid; τ-integration weights and endpoint/tail treatment must be specified. Any grid is sensitive to finite-sample upper-tail noise, especially for rare extremes. Q01/Q02 are simple; Q03 requires a versioned formula and calibration study. No τ grid is frozen. **RESEARCHER_DECISION_REQUIRED.**
""")
    save_md(out / "PROBABILITY" / "quantile_crossing_options.md", """
# Quantile crossing options

**NC01 independent outputs + penalty:** quantile rank i retains exact τᵢ identity under pinball supervision. Candidate `L_nc=mean_valid Σᵢ relu(qᵢ−qᵢ₊₁)`; soft penalty permits crossings and weight must be selected. V1.3 lists optional `λ_nc=0.05`, not frozen.

**NC02 monotonic parameterization:** `q₁=base`, `qᵢ=qᵢ₋₁+softplus(δᵢ)` for i>1, with numerically stable softplus. Outputs are ordered by construction, so `L_nc` is mathematically zero and usually unnecessary; parameter sharing constrains expressiveness and may over-smooth rare high tail. The base must obey approved physical/log-domain support. Exact rank semantics still depend on pinball at each τ. No evidence here that GPROF-IR uses this parameterization.

**NC03 post-hoc sort:** sorting independent outputs after training enforces order numerically but reassigns predictions to τ ranks. This can alter calibration/quantile identity and conceal training defects. It is **not a default**; if considered, it needs a separate validation protocol and explicit declaration. No silent sort in any test or proposed interface.

Researcher chooses mechanism, penalty formula/normalization, and weight. **RESEARCHER_DECISION_REQUIRED.**
""")
    save_md(out / "PROBABILITY" / "output_tensor_contract.md", """
# Unified B0–B8 probability output interface — candidate

For SP04 target `H=W=100`, `rain_logit:[B,1,100,100]`, `conditional_quantiles_raw:[B,32,100,100]`, versioned `tau:[32]`, and `target_valid_mask:[B,1,100,100]` Boolean. Raw quantile tensor's rank i corresponds to τᵢ; its physical/log transform status must be metadata. The mask is an IMERG *data-validity* mask, distinct from the frozen Yunnan evaluation mask and from `R>0.1` conditional-training mask.

`rain_prob=sigmoid(rain_logit)∈[0,1]`; if raw quantiles are in log1p(mm h⁻¹) space, `q_physical=expm1(q_raw)` exactly. Any negative raw value maps to a negative physical quantile, revealing a violated support contract; no implicit clamp, relabeling, or sorting. An approved support parameterization or explicit error policy is needed. If conditional law is `R>0.1`, its physical quantiles should lie above 0.1, again requiring an approved support mechanism.

Raw model outputs, transformed physical conditional quantiles, deterministic diagnostic (mixture median/mean **choice pending**), and exceedance products are distinct named objects. An unchosen tail/CDF rule must produce `NOT_ESTABLISHED`, not silent zeros. Brier/reliability/CRPS need probability forecasts plus observed thresholds and valid/evaluation masks; no training/metric calculation occurred. **RESEARCHER_DECISION_REQUIRED.**
""")
    save_md(out / "PROBABILITY" / "pinball_loss_contract.md", """
# Conditional pinball candidate

For `u=y−qτ`, `ρτ(u)=max(τu,(τ−1)u)`. If output is log space, `y=log1p(R)` for each valid **conditional** pixel; `conditional log1p(R)` means the same transform with a conditioning mask, not a separately renormalized variable. If conditioning is approved as `R>0.1`, `M_q=M_valid ∧ (R>0.1)`; only those pixels contribute to `L_qr`. `L_qr = Σ_{bxy,i} M_q ρτᵢ(log1p R−qᵢ) / [32 Σ_{bxy} M_q]` is an illustrative per-pixel normalization; behavior for empty conditional batches must be explicit (e.g. skip this component with logged count), not divide by zero. If τ quadrature weights differ, replace uniform 1/32 explicitly.

`M_valid` excludes IMERG missing values from **all** terms. A valid observed zero is an occurrence negative (`z=0`) and never treated as missing. Valid `0<R≤0.1` is also occurrence negative but excluded from the conditional quantile term under the `R>0.1` candidate. Threshold choice, reduction and loss weights require approval. No loss was applied to training data.
""")
    save_md(out / "PROBABILITY" / "focal_loss_contract.md", """
# Occurrence loss candidate

For valid IMERG rate `R`, `z=I(R>0.1 mm h⁻¹)` (strict greater-than; `R=0.1` has z=0). Let `p=sigmoid(logit)`, `p_t=p` when z=1 else `1−p`, and `α_t=α` when z=1 else `1−α`. Focal BCE candidate: `L_occ = mean_valid[−α_t(1−p_t)^γ log(p_t)]`, implemented with stable logits/BCE rather than raw log near 0/1. Standard BCE is the γ=0/unweighted comparison, **not** a replacement of V1.3's Focal BCE direction.

Neither γ nor α was found frozen in local evidence. Do not assume 2 or 0.25. Positive/negative class reweighting, mask denominator, empty batch, exact transform, and occurrence-family weight require approval. Valid zero is a negative example; missing is excluded. **RESEARCHER_DECISION_REQUIRED.**
""")
    save_md(out / "PROBABILITY" / "extreme_loss_options.md", """
# L_ext options — no approved mathematics yet

V1.3 mentions moderate weighting at ≥10/20 mm h⁻¹ and `λ_ext=0.2` as an initial suggestion, not a frozen rule. **EX01:** pixel/sample weight `w(R)` multiplying conditional pinball; must specify thresholds, weights, normalization, label dependence and gradient behavior. **EX02:** auxiliary exceedance loss at 10/20 from probability head/CDF, or an additional head; must define CDF/tails, Brier/log score, coupling and capacity effect. **EX03:** omit L_ext in *first* B0 formal protocol; if later added, rerun B0–B8 consistently under a new protocol. EX03 is cleanest for first-pass ablation fairness if every stage shares the same omission, but it does not meet an eventual extreme-loss design objective by itself.

No method is selected. A selected EX01/EX02 must be identically applied across B0–B8 and versioned before formal experiments. **RESEARCHER_DECISION_REQUIRED.**
""")
    save_md(out / "PROBABILITY" / "noncrossing_loss_contract.md", """
# L_nc candidate

If NC01 is selected: `L_nc=Σ valid pixels Σ_{i=1}^{31} max(q_i−q_{i+1},0) / (31·N_valid)` is one candidate; transformed-vs-log units and whether the mask is all valid or conditional positive need approval. V1.3 `λ_nc=0.05` is explicitly **OPTIONAL**, not frozen. If NC02 guarantees monotonicity in raw space and expm1 is monotonic, crossings cannot occur in physical space, so L_nc can be omitted or kept only as a zero-valued diagnostic. NC03 sorting is not a loss and is not silently applied. **RESEARCHER_DECISION_REQUIRED.**
""")
    save_md(out / "PROBABILITY" / "deterministic_summary_options.md", """
# Point estimates for MAE/RMSE/Bias/CC

Conditional median describes `R | R>threshold`, **not** the marginal mixture median. Conditional mean reconstructed from 32 quantiles requires CDF interpolation, both endpoint tails, and integration in **physical R space**; mean of log quantiles is not mean rain. `p·E[R|R>0.1]` is the mean of threshold-censored `R·I(R>0.1)`, not exact `E[R]` if subthreshold rain exists. Exact marginal mixture mean requires `(1−p)E[R|R≤0.1]` too. Exact mixture median requires a specified subthreshold distribution and may be zero or in `(0,0.1]`.

Candidate diagnostic labels must state what they estimate. MAE is aligned to marginal median, RMSE to marginal mean, while Bias/CC can be calculated for either with label retained. CRPS needs a full predictive CDF or declared quantile-integral approximation, including subthreshold and tails. **RESEARCHER_DECISION_REQUIRED.**
""")
    save_md(out / "PROBABILITY" / "exceedance_probability_contract.md", """
# Exceedance probability and score inputs

For candidate conditional `R>0.1`: `P(R>0.1)=p` exactly; for `r∈{1,5,10,20}` mm h⁻¹, `P(R>r)=p[1−F₊(r)]`. Observed binary target for each threshold is `I(R>r)` on valid IMERG data, and evaluation further intersects the frozen 3430-cell Yunnan mask. Brier score is mean squared probability error; reliability bins compare forecast probability with empirical event frequency, with bin definition/counts fixed before analysis.

Discrete conditional quantiles specify CDF knots but do **not** uniquely determine between-knot shape or tails. Candidates: (1) piecewise-linear CDF in physical rate with repeated-quantile/tie policy; (2) monotone CDF interpolation in log1p rate; (3) a separately fitted parametric upper/lower tail. For `r>max(q)`, the upper tail remains at least `1−τ_max` just below/at the last quantile under a continuous interpretation; setting it to zero or extending a line is unjustified. Return `NOT_ESTABLISHED`/coverage diagnostic until a tail rule is frozen. The same applies below min quantile and to CRPS, which also needs subthreshold mass. A quantile-integrated pinball approximation to CRPS must state τ quadrature weights/endpoints and differs from exact full-mixture CRPS. **RESEARCHER_DECISION_REQUIRED.**
""")
    save_md(out / "MODEL" / "b0_b3_backbone_shape_options.md", """
# Four-level native encoder and 100×100 target-head shape feasibility (no training)

V1.3 direction: channels `48→96→192→256`. Four **levels** mean three 2× downsample operations in this table; four downsampling operations would be a different architecture and must be named separately.

| Rule | Level 1 / skip | Level 2 / skip | Level 3 / skip | Level 4 | Decoder ×2 mismatch | Projection to target |
|---|---:|---:|---:|---:|---|---|
| same-padding 3×3×2, floor pool2 | 501 | 250 | 125 | 62 | 62→124 vs 125; 125→250 exact; 250→500 vs 501 | Explicit coordinate-aware 100×100 projection after decoder, not bare 501→100 adaptive pool |
| same-padding 3×3×2, ceil pool2 | 501 | 251 | 126 | 63 | 63→126 exact; 126→252 vs 251; 251→502 vs 501 | Same explicit projection |
| valid 3×3×2, floor pool2 | 497 | 244 | 118 | 55 | Decoder/skip matches require separately computed *declared* crop/pad; native border information lost | Exact support and edge-loss policy needed |

Valid-conv arithmetic is `501−4=497 →floor/2=248 →244 →122 →118 →59 →55`. Same-padding skips require explicit asymmetric crop/pad or coordinate-based resize; none was performed. A naive adaptive pool 501→100 has unequal source supports and no guaranteed geographic alignment. A coordinate-aware projection point could be on native decoder features before the 1×1 probability head; then `rain_logit[B,1,100,100]` and conditional quantiles `[B,32,100,100]`. Projection of earlier coarse features needs its own spatial-reference tracking. Exact padding, skip alignment, and projection remain decisions. **RESEARCHER_DECISION_REQUIRED.**
""")
    save_md(out / "MODEL" / "b0_b3_fairness_contract.md", """
# B0–B3 controlled input-information comparison — candidate

| Stage | Satellite input | Channel-stack example |
|---|---|---:|
| B0 | B13×1 frame | 1 |
| B1 | B13×6 frames | 6 |
| B2 | 7 channels×1 frame | 7 |
| B3 | 7 channels×6 frames | 42 |

Across stages: same SP04 domain and frozen evaluation mask, one **approved** native-target mapping, 4-level encoder depth, decoder family, dual probability heads, chosen 32 τ, loss family and weights, target validity rules, split/evaluation protocol and causal frame selection. Only Himawari information changes. If frames/channels are stacked in the first layer, a 3×3 convolution with 48 outputs changes weight count by `48×9×(C−1)` relative to B0: B1 +2160, B2 +2592, B3 +17712; bias is unchanged. A temporal-fusion alternative must report its actual capacity separately. These are arithmetic examples, not instantiated/trained models. Do not compensate by silently changing the rest of the network. B1–B3 were not run.
""")
    save_md(out / "RESEARCHER_DECISIONS_REQUIRED.md", """
# Decisions required before B0 formal experiment

1. Confirm SP04 97–107°E/20–30°N as the exact formal input domain, including whether bounds denote native centers or physical cell edges and how outside-context coverage is handled. This run verifies geometry but does **not** freeze the bbox.
2. Choose SA01–SA05 native→target operator; specify pixel/target footprints, boundary ownership, float tolerance, missing/valid support, edge behavior, projection point, padding/crop, and versioned B0–B8 index contract.
3. Choose conditional rain threshold (`R>0` or `R>0.1`) and treatment of valid drizzle `0<R≤0.1`; clarify full physical mean versus threshold-censored mean.
4. Approve exact 32 τ values (Q01/Q02/Q03 or sourced alternative), noncrossing method, quantile support transform, and whether outputs are physical or log1p.
5. Approve complete focal loss (γ, α, weighting, reduction), pinball reduction/τ quadrature, L_det definition, L_ext option/weights, and optional L_nc mechanism/weight. `L_KD=0` stays in B0–B8 core.
6. Approve full-mixture CDF/tail/interpolation/subthreshold policy for CRPS and exceedance probabilities, and a clearly labeled point estimate for MAE/RMSE/Bias/CC.
7. Approve four-level backbone's exact padding, skip matching, projection location and fairness/capacity accounting; then resolve independent prior readiness blockers (including time binding and missing 2025 October Final coverage) before any B0 formal run.

No item above was silently frozen. **B0_FORMAL_TRAINING_STARTED=false.**
""")
    report = f"""
# FINAL B0 Spatial + Probability Contract Resolution Report

**Run:** `{out.name}`  
**Spatial status:** `SPATIAL_CONTRACT_READY_FOR_RESEARCHER_DECISION`  
**Probability status:** `PROBABILITY_CONTRACT_READY_FOR_RESEARCHER_DECISION`  
**B0_FORMAL_TRAINING_STARTED:** `false`

## Answers A–M

**A. Geometry:** 501×501 native axis centers span 20–30°N and 97–107°E inclusive, with latitude descending. Actual IMERG centers inside SP04 make 100×100, latitude ascending, with inferred cell edges close to the source endpoints. Under explicit raw half-open cell membership, **all 10,000 target cells contain exactly 25 native centers** ({dict(sorted(cc.items()))}); strict interiors contain 4×4 and near-boundary centers require a declared ownership rule. All 3430 frozen Yunnan evaluation cells lie in target subset.

**B. Integer mapping:** **yes, an exact 5×5 index mapping exists for these actual arrays under the explicitly stated raw half-open `[lower,upper)` rule**. It assigns native latitude rows 1–500 and longitude columns 0–499; northmost row 0 and eastmost column 500 are excluded. A direct 501×501 reshape is impossible, and no endpoint-ownership or physical-footprint choice is yet approved. The actual-coordinate index table is deterministic for each stated rule; do not replace it with an assumed generic stride-5 reshape.

**C. Candidate recommendation:** investigate SA05 coordinate-defined hybrid / SA04 native encoder plus coordinate-aware target projection for interpretability and B0–B8 consistency. It is an engineering recommendation, not approval or performance result.

**D. SP04 freeze:** source/target containment and mask retention are verified; exact domain-edge semantics, native→target mapping and padding remain undecided. Thus SP04 is **not yet safe to mark a complete formal input/projection contract**.

**E. Local τ source:** GPROF-IR manuscript mentions 32 quantiles and quantile regression, but bounded local search found no exact 32 τ vector or matching dual-head conditional law.

**F. τ candidates:** Q01 midpoint uniform reaches farther into tails; Q02 interior uniform gives more endpoint gap; Q03 illustrative upper-tail-dense grid shifts coverage and needs nonuniform CRPS quadrature. None frozen.

**G. Conditioning:** `R>0.1` aligns algebraically with occurrence `P(R>0.1)` for exceedances above 0.1. `R>0` without a drizzle component does not. Even `R>0.1` does not make `p·conditional_mean` an exact physical mean if drizzle is nonzero.

**H. Crossing:** NC01 independent+penalty, NC02 positive increments, NC03 post-hoc sorting; NC03 risks quantile-rank/calibration changes and is not default.

**I. Loss:** `L_qr` pinball family and `L_KD=0` for B0–B8 are specified; exact τ/reduction/conditioning and `L_det`, focal γ/α, `L_ext` mathematics/weights, optional `L_nc=0.05` remain researcher decisions. `λ_ext=0.2` is only initial suggestion.

**J. Tensor candidate:** rain logit `[B,1,100,100]`, conditional quantiles `[B,32,100,100]`, τ `[32]`, data-validity mask `[B,1,100,100]`; explicit sigmoid/log1p inverse, no silent clamp/sort.

**K. Metrics/products:** point diagnostic must be labeled mixture median/mean or conditional/censored diagnostic; full CRPS needs full CDF/subthreshold/tails or declared approximation. At 0.1, exceedance is p. At 1/5/10/20, use p·[1−F₊(r)] only after conditioning/CDF interpolation/tails are approved. Brier/reliability use threshold event indicators on valid Yunnan cells. Above max quantile: `NOT_ESTABLISHED` pending tail rule.

**L. Already frozen:** GADM4.1 Yunnan center mask (3430), true IMERG coordinates, 0≠missing, raw read-only, `obs_end≤analysis_time`, 2023–2025 March–October and 2025 Final Test, `L_KD=0` in B0–B8 core, and researcher direction of shared B0–B8 domain/dual-head probability. Geometry evidence can be registered, not a new silent scientific mapping freeze.

**M. Researcher decision:** SP04 exact domain and mapping, τ, conditioning/drizzle, loss math/weights, crossing/support, CDF/tails/point estimate, padding/projection/backbone, and remaining prior formal-readiness blockers. See `RESEARCHER_DECISIONS_REQUIRED.md`.

## Execution and evidence

No science resampling, training, dataset, split, statistics, benchmark or next-stage run was performed. `SPATIAL/` contains exact axis arrays and 10,000-cell index mapping; `PROBABILITY/` contains definitions/candidates; `MODEL/` contains shape/fairness review; `DECISIONS/` contains researcher decision briefs. `logs/tests.txt` records focused automated checks. Previous runs were only read.

B0 spatial/probability contract resolution complete.  
No formal model training was started.  
SP04 geometry was evaluated using actual coordinate arrays.  
No provisional spatial projection was silently frozen.  
No unspecified quantile or loss hyperparameter was silently frozen.  
The final scientific contract remains subject to explicit researcher approval.
"""
    save_md(out / "FINAL_B0_SPATIAL_PROBABILITY_CONTRACT_REPORT.md", report)
    save_md(out / "README.md", """
# B0 Spatial + Probability Contract Resolution

Read `FINAL_B0_SPATIAL_PROBABILITY_CONTRACT_REPORT.md` then `RESEARCHER_DECISIONS_REQUIRED.md`. This run is a read-only evidence/decision package, not a formal science or training run. It preserves old run results. `SPATIAL/sp04_coordinate_arrays.npz` is local coordinate evidence; frozen GADM-derived mask/geometry are referenced by hash and remain in the prior spatial-freeze run. Public GitHub export excludes coordinate arrays and any licensed mask/geometry payload; source code and redacted evidence summaries may be published.

Run source: `src/build_contract.py`; tests: `tests/test_contract.py`; fixed Python: `F:/pytorch/Research/.venv/Scripts/python.exe`. The package builder uses actual saved coordinate arrays and checks frozen IMERG/mask SHA before writing. `logs/source_hashes.json` and `evidence_registry.csv` provide traceability.
""")
    shutil.copy2(Path(__file__), out / "src" / "build_contract.py")
    shutil.copy2(Path(__file__).with_name("contract_math.py"), out / "src" / "contract_math.py")
    test_src = Path(__file__).with_name("test_contract.py")
    shutil.copy2(test_src, out / "tests" / "test_contract.py")
    save_json(out / "logs" / "source_hashes.json", dict(builder_sha256=sha(out / "src" / "build_contract.py"),
                  math_sha256=sha(out / "src" / "contract_math.py"),
                  tests_sha256=sha(out / "tests" / "test_contract.py"), sources=sources,
                  created_utc=datetime.now(timezone.utc).isoformat(), python_executable=r"F:\pytorch\Research\.venv\Scripts\python.exe"))
    evidence = []
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name not in ("evidence_registry.csv",):
            evidence.append(dict(relative_path=str(p.relative_to(out)).replace("\\", "/"), sha256=sha(p),
                                 bytes=p.stat().st_size, role="GENERATED_EVIDENCE",
                                 public_export="EXCLUDE" if p.suffix == ".npz" else "REVIEW_BEFORE_EXPORT"))
    save_csv(out / "evidence_registry.csv", evidence)
    print(out)
    return out


if __name__ == "__main__":
    main()
