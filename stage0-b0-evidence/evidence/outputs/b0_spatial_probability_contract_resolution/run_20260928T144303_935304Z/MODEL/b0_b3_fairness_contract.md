# B0–B3 controlled input-information comparison — candidate

| Stage | Satellite input | Channel-stack example |
|---|---|---:|
| B0 | B13×1 frame | 1 |
| B1 | B13×6 frames | 6 |
| B2 | 7 channels×1 frame | 7 |
| B3 | 7 channels×6 frames | 42 |

Across stages: same SP04 domain and frozen evaluation mask, one **approved** native-target mapping, 4-level encoder depth, decoder family, dual probability heads, chosen 32 τ, loss family and weights, target validity rules, split/evaluation protocol and causal frame selection. Only Himawari information changes. If frames/channels are stacked in the first layer, a 3×3 convolution with 48 outputs changes weight count by `48×9×(C−1)` relative to B0: B1 +2160, B2 +2592, B3 +17712; bias is unchanged. A temporal-fusion alternative must report its actual capacity separately. These are arithmetic examples, not instantiated/trained models. Do not compensate by silently changing the rest of the network. B1–B3 were not run.
