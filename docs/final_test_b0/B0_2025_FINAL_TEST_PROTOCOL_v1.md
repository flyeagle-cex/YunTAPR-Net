# B0 2025 Final Test protocol v1

Declared at baseline `ddbb69ccca6c806973a89a91127ea02c9af42afd` before any 2025 raw data is opened. This release
freezes evaluation rules and authorizes only synthetic/historical-fixture preflight.
It does not authorize the Final Test. Protocol YAML SHA256: `6d08def2602dda3d931937c68cadeae86b5c16b60f9f7132c9e134b962cdbe3b`.

FINAL is the sole checkpoint: epoch 11, update 128964, SHA256
`05359d2fee2ae61daf654ae5a59b7977cb65247fd46d97a69a690a0133da7f65`. Its local path, byte count and immutable provenance are
registered in the YAML. Phase-B normalization is reused unchanged: mean
270.5900486586461 K, std 20.368583874067266 K, SHA256
`c7042beac2412594ca9fc264d7df10981755b393158c539cb48c9b56cd314327`. No optimizer or backward is permitted.

The population is only 2025 March through September, with 30-minute UTC window
starts from March 1 inclusive to October 1 exclusive. A future authorized
candidate catalogue must account for all 10272 scheduled windows. Eligibility
inherits V1.1 FULL_SCENE_REQUIRED B13 and latest-causal rules, verified IMERG V07
Final, and at least one valid frozen-Yunnan supervised pixel. Missing targets
remain masked; they are never converted to zeros. Data failures after population
freeze stop execution. There is no alternate source, older-frame fallback or skip.

Primary metrics are declared in the YAML now and cannot change after viewing
2025 results. Focal/pinball raw sums use full-population valid-pixel denominators;
conditional pinball and coverage use valid rainy pixels. Exact tied-rank AUROC/AP
inherit the existing conventions. The 32 tau, coverage error, numerical crossing,
nonfinite and support checks are fixed. POD/FAR/CSI remain THRESHOLD_NOT_FROZEN.

All 2024 Scientific Review diagnostic definitions are preserved verbatim in
`inherited_diagnostics`, including reliability edges, seven descriptive rain-rate
bins, spatial display minimum of 30 rainy observations, quantile groups,
descriptive exceedances, probability histogram and the three top-10 case rules.
Monthly diagnostics use the same statistics for March-September. Spatial outputs
retain exact frozen axes and per-cell masks; no new subregions are introduced.
DIAGNOSTIC_PROXY is probability times the mean of 32 physical conditional
quantiles, with MAE/RMSE/Bias; it is not an exact expectation or calibration.

The September 30 23:30 window is allowed even though its end is October 1 00:00.
Its B13 nominal source remains September 30 23:50. Every October source/window is
rejected before raw I/O. No 2025 source is opened in this preflight.

Future execution requires a separate researcher authorization bound to protocol,
runner/module, FINAL, normalization and full candidate-manifest hashes. Fixed
chronological inference visits every eligible identity once. FINAL is verified
before state application and checked unchanged afterwards. Formal inference has
no train/backward/optimizer/calibration/selection paths.

FINAL_TEST_2025_AUTHORIZED=false; FINAL_TEST_2025_EXECUTED=false;
2025_PIXELS_READ=0. Stop after preflight evidence is published.
