# Four-level native encoder and 100×100 target-head shape feasibility (no training)

V1.3 direction: channels `48→96→192→256`. Four **levels** mean three 2× downsample operations in this table; four downsampling operations would be a different architecture and must be named separately.

| Rule | Level 1 / skip | Level 2 / skip | Level 3 / skip | Level 4 | Decoder ×2 mismatch | Projection to target |
|---|---:|---:|---:|---:|---|---|
| same-padding 3×3×2, floor pool2 | 501 | 250 | 125 | 62 | 62→124 vs 125; 125→250 exact; 250→500 vs 501 | Explicit coordinate-aware 100×100 projection after decoder, not bare 501→100 adaptive pool |
| same-padding 3×3×2, ceil pool2 | 501 | 251 | 126 | 63 | 63→126 exact; 126→252 vs 251; 251→502 vs 501 | Same explicit projection |
| valid 3×3×2, floor pool2 | 497 | 244 | 118 | 55 | Decoder/skip matches require separately computed *declared* crop/pad; native border information lost | Exact support and edge-loss policy needed |

Valid-conv arithmetic is `501−4=497 →floor/2=248 →244 →122 →118 →59 →55`. Same-padding skips require explicit asymmetric crop/pad or coordinate-based resize; none was performed. A naive adaptive pool 501→100 has unequal source supports and no guaranteed geographic alignment. A coordinate-aware projection point could be on native decoder features before the 1×1 probability head; then `rain_logit[B,1,100,100]` and conditional quantiles `[B,32,100,100]`. Projection of earlier coarse features needs its own spatial-reference tracking. Exact padding, skip alignment, and projection remain decisions. **RESEARCHER_DECISION_REQUIRED.**
