# B0 Phase-B FinalFit formal authorization v1

The researcher explicitly authorizes B0_PHASE_B_FINALFIT_ONLY in the attached
AUTHORIZE AND EXECUTE task. Baseline: `4de37ac087183bddf3b9f8c7d548a0f976a50e91`. Authority attachment SHA256:
`eb766b694fc1d671c4a1d35df8e29de73d9ca13c2324f232fac8ca310c8da8db`. Authorization is run-level and does not change historical
preparation, runner configuration or their PHASE_B_AUTHORIZED=false fields.

PHASE_B_AUTHORIZED=true. Fresh seed 2026 only; no Phase-A model, optimizer or
scheduler state. FinalFit consists of 23,447 frozen identities (2023:11,720;
2024:11,727; 2025:0), each exactly once per epoch. Physical batch2, accumulation1,
drop_last=false, singleton allowed without drop/duplication. Fixed eleven epochs,
11,724 updates per epoch, total128,964. Stateless LR preserves W=11,724/U=586,200,
base LR1e-4 and min LR1e-6. No cosine compression or scientific parameter change.

Normalization SHA256: `c7042beac2412594ca9fc264d7df10981755b393158c539cb48c9b56cd314327`; mean270.5900486586461K,
std20.368583874067266K, no refit. Manifest SHA256: `00e6bd018eae6aeb05be0740b55a92b7a5cc9a44b9ab2b80affbad3e3282ccff`.
All approved architecture/loss/AdamW/precision/clipping rules inherit the frozen
protocol. Every original source SHA is verified before model initialization and
again during staged runtime reads. Source/QC/causality/numerical failure stops execution.

No early stopping, BEST, validation selection, epoch reselection, 2025 read,
threshold calibration, hyperparameter tuning or B1-B8 execution is authorized.
Only completed epoch boundaries produce checkpoints. LAST and epoch11 FINAL are
registered; payloads remain at `F:\pytorch\Research\outputs\formal_training\b0_phase_b_finalfit` and never enter Git.
Resume is only from verified completed LAST after provenance-before-state application.

The exact current baseline runner/module/config SHA values below are unchanged.
A separately SHA-pinned adapter adds source-open auditing and requested epoch
telemetry while delegating numerical updates/epochs to the baseline functions.

```json
{
  "phase_a_acceptance": {
    "path": "config/decisions/b0_phase_a_acceptance_v1.yaml",
    "sha256": "d91add2d00495e781acb3fc58b0f95a41ac1801b53fbaaafcff25e25402f6b1c"
  },
  "scientific_review": {
    "path": "docs/scientific_review/b0_phase_a/runs/run_20261002T005448_798068Z/review_manifest.json",
    "sha256": "5e2a38c4b8ac6a09d078b13e05851c098c576c2d2923bcc488ba05abae366a1a"
  },
  "scientific_review_final_status": {
    "path": "docs/scientific_review/b0_phase_a/runs/run_20261002T005448_798068Z/final_status.json",
    "sha256": "ff521287ea708d5f56626fad448fd170438192b9a0c1ab70a554c1e1745fcc15"
  },
  "phase_b_preparation": {
    "path": "docs/phase_b_finalfit_preparation/runs/run_20261002T014649_144967Z/preparation_manifest.json",
    "sha256": "fc0965a8c1cfd84ebc45ce3071b3bfb50e50ba1dc34346205d48e4fb8e09bb3c"
  },
  "phase_b_preparation_final_status": {
    "path": "docs/phase_b_finalfit_preparation/runs/run_20261002T014649_144967Z/final_status.json",
    "sha256": "9acc0abeb4aa4bf09f7ec2788fb09d7349639e1b66e33fa5f7c14cd21ec7923d"
  },
  "phase_b_runner_preflight": {
    "path": "docs/phase_b_formal_runner/runs/run_20261002T031500_884240Z/runner_manifest.json",
    "sha256": "ae3f6c7c3cf96f3091ff255c78afcece9f738b335c14287f864dcac1ce8dfccb"
  },
  "phase_b_runner_preflight_final_status": {
    "path": "docs/phase_b_formal_runner/runs/run_20261002T031500_884240Z/final_status.json",
    "sha256": "00ae5f77657d70c741f82d9d8c8025b1af3e715db2f384fa72ac3ef0ac2f441f"
  },
  "formal_phase_b_module": {
    "path": "src/yuntapr/training/formal_phase_b.py",
    "sha256": "9f9e8fb203334a4195c982181553daa11fb95f327fccfa2f626cf1dab91a2b55"
  },
  "formal_entrypoint": {
    "path": "scripts/train_b0_phase_b_finalfit_v1.py",
    "sha256": "1bddb634909ff6786e69e67becd4052e6829e6619e3d6513bccf97709f44c3b8"
  },
  "telemetry_adapter": {
    "path": "scripts/execute_b0_phase_b_finalfit_formal_v1.py",
    "sha256": "fda5878ce5b36c3c9eef1eef1e8340ac743cb3eda1171a991373ccf604b624b6"
  },
  "runner_config": {
    "path": "config/training/b0_phase_b_finalfit_runner_v1.yaml",
    "sha256": "07c43cd14152e6b318159633f864c830a44f75e5da9c109e725cd10851c752eb"
  }
}
```

After eleven epochs: verify FINAL read-only; rerun all242 current tests and legal
new tests; verify FINAL SHA unchanged; publish text evidence; STOP. Final Test2025,
B1-B8 and subsequent stages remain unauthorized.
