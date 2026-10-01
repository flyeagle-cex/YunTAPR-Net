# Seed and reproducibility candidates

All seed policies and values are unselected, RESEARCHER_DECISION_REQUIRED.
A: one fixed seed, identical across the complete B0–B8 main ablation.
B: three prespecified seeds, each used for all B0–B8, reporting each run and a
specified aggregate/dispersion. An illustrative candidate set is 17, 42, 2026;
these values are not chosen or tested as performance hyperparameters.
C: one seed for main ablation, three seeds for specified key models. Different
repeat counts make uncertainty precision unequal; do not compare three-seed
means against one-seed points as if replication were balanced. If K key models
receive two additional seeds, total seed-model runs=9+2K (K=2 gives 13).

At 31.19 min/epoch from the earlier B0 engineering estimate, 30/50/80 epochs cost
15.595/25.992/41.587 hours per B0 seed. Three seeds multiply by three. The CSV
also shows 9-model and mixed examples, assuming EVERY model had B0 throughput;
future B1–B8 may differ substantially. Optimizer, checkpoint and sustained full
epoch changes can alter real time; these are arithmetic cost scenarios only.

Before authorized training, pin Python random seed, NumPy seed, torch CPU seed,
all CUDA seeds, DataLoader generator and worker seed derivation. Candidate worker
derivation uses torch.initial_seed()%2**32 to initialize NumPy/Python, with a
separately seeded generator; exact epoch/worker/persistent-worker behavior and
shuffle order must be recorded. Cross-model initialization differs by shape,
so equal seed alone is not identical random-number consumption or initialization.
The forward diagnostic's isolated seed 20261001 is an audit fixture, not a
recommended formal seed. Its RNG state and temporary thread count were restored.

Read-only current settings are in reproducibility_settings.json. Consider
torch.use_deterministic_algorithms(True), cuDNN determinism, benchmark and TF32
policies as a package. Deterministic kernels can lower performance and unsupported
operations can raise; versions/device still matter, and one seed does not promise
identical results across releases/platforms. These tradeoffs follow the
[PyTorch reproducibility guide](https://docs.pytorch.org/docs/2.11/notes/randomness.html). No deterministic,
TF32 or cuDNN setting was changed by this audit.
