# Core innovation interfaces · 2026-10-24

Evidence baseline: `ae4b448ab3db73fba855a2df5d37e0f1bb2e2f4e`.
Development branch: `dev/core-innovation-20261024`. Existing formal models,
contracts, results, ledgers and checkpoints are unchanged. E0/E1/E2 are loss
arms; they do not define the B0–B8 architecture ablations.

Code is isolated in `src/yuntapr/experimental/core_innovation/`:

| File | Executable interface | Remaining scientific boundary |
| --- | --- | --- |
| `gfs.py` | Bounded main/thermo NetCDF decoding; CF/global/filename identity; explicit variables and Pa/K/m/s units; fill/packed masks; strict above-ground layers; paired environment channels | Source-lineage acceptance, formal predictor set, train-only environment normalization and temporal matching/vintage are not frozen. No implicit init+lag availability. |
| `grid.py` | Existing hash-verified SP04 target axes; explicit geographic identity; masked bilinear candidate point map | Point interpolation is not the existing SP04 25-native-center reduction and is not a frozen production aggregation rule. |
| `terrain.py` | Bounded native HGT/zip window; WGS84 signed metre distances; native derivatives, slope/aspect; optional mapping after gradients | Full mosaic seams, vertical datum, derivative scale and target footprint aggregation require a production choice. Border/no-data stencils remain invalid. |
| `dote.py` | `u*dh/dx + v*dh/dnorth`, with explicit pressure units, level axis, wind/grid identity and masks | Diagnostic candidate, not true vertical velocity; no humidity weighting or vertical integration is selected. |
| `dtfm.py` | Explicit per-scale conditioning channels, aligned grids and masks; identity-initialized bounded affine prototype; shape/device/dtype and gradient checks | Conditioning variables, scale hierarchy, modulation form/strength and backbone insertion remain researcher decisions. |
| `multispectral.py` | Explicit Kelvin thermal channels, causal history order, existing B13 scaler adapter and per-band 2023-Train provenance; independent masks | B2/B3 channels/frames and joint valid population are not frozen. New bands need their own Train-only statistics; reflective bands cannot use this Kelvin adapter. |

Run the bounded interface suite with the existing compatible environment:

```text
python -B tools/core_innovation/run_checks.py
```

The runner uses CPU and one thread, stores actual stdout/summary under
`test_runs/`, and does not run an optimizer or evaluate precipitation skill.
The initial failed integration run is retained alongside corrected passing
runs. The existing NetCDF4/NumPy deprecation warning is recorded, not promoted
to a scientific failure or hidden by modifying the environment.

A separate tiny synthetic CUDA forward/backward probe is recorded in
`device_cuda_synthetic.json`; optimizer updates and weather-payload reads are
both zero. Its memory counter is PyTorch allocated memory, not whole-driver
or whole-machine memory.

`tools/core_innovation/check_real_gfs.py` supports an explicitly supplied private
four-file schema probe and optional bounded DEM probe. It checks only authorized
2023/2024 files, caps source bytes/cells and writes real-source evidence solely
under ignored `.local/`. It can connect real wind fields to a native DEM window
and the DOTE candidate; this is engineering connectivity, not model validation.
Private paths, decoded data and real-check outputs are not included in this
source branch. No 2025 data, weights, training loop or new formal experiment is
part of these checks.

The most useful next check is a small predeclared 2023/2024 multi-vintage sample
covering f000/f003/f006 and terrain/pressure-mask boundaries, once retrospective
source acceptance and spatial/temporal operators are selected. Formal B2/B3 or
environment-fusion training needs a separately agreed architecture/data matrix
and budget; synthetic correctness does not grant that authorization.
