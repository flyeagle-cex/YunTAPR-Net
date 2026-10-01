# Optimizer candidates — RESEARCHER_DECISION_REQUIRED

No optimizer object or optimizer state was created. AdamW is a candidate only.
beta1=0.9, beta2=0.999, eps=1e-8 are **DEFAULT_REFERENCE**, verified from installed
torch 2.11.0's signature and [PyTorch 2.11 AdamW](https://docs.pytorch.org/docs/2.11/generated/torch.optim.AdamW.html). Defaults
are API references, not scientific truths. Weight decay grid 0, 1e-4, 1e-3,
1e-2 is an explicit unselected candidate grid; no value is adopted.

| Count | Parameters |
|---|---:|
| Total trainable | 4329361 |
| Bias, including GroupNorm beta | 4673 |
| GroupNorm affine gamma+beta | 3712 |
| Bias/GroupNorm overlap | 1856 |
| Conv weights, including heads | 4322832 |
| Head weights, subset of Conv weights | 1584 |

Counts overlap as stated; summing every row would double count. Full named groups
and set-partition assertions are in model_parameter_groups.json.

Candidate A explicitly means decay **every trainable parameter**, including
bias and GroupNorm affine, 4329361 elements. This avoids an
implicit interpretation of 'weights' that changes treatment of biases.
Candidate B decays Conv kernels only (4322832 elements),
excluding every bias and GroupNorm affine parameter (6529).
The exclusion set is a union, so GroupNorm beta is not counted twice.
A shrinks biases and normalization scale/offset; B leaves those affine degrees
unshrunk. Decoupled decay interacts with LR and number of optimizer updates;
effective batch changes update frequency. No claim of better validation skill.

Two float32 Adam moments alone would add approximately
33.03 MiB persistent state. This is
arithmetic, not an allocation measurement; foreach/fused temporaries, step latency
and full optimizer VRAM were not benchmarked. Prior GPU headroom is forward/backward
evidence. Future authorized training must log AdamW implementation flags, groups,
LR, decay, betas, eps and real optimizer memory.
