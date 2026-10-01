# Phase-A training protocol pre-freeze evidence

Latest run: [run_20261001T014523Z report](runs/run_20261001T014523Z/PHASE_A_PROTOCOL_PREFREEZE_REPORT.md).
Researcher review: [decision table](runs/run_20261001T014523Z/RESEARCHER_DECISION_TABLE.md).

Baseline: `bc287755cfade53dd5a52a32c99c7326e2c2dfe8`.

The audit counted every eligible 2023 Train scene (11,720), reading 245 pinned
IMERG V07 Final days. Across 40,199,600 valid Yunnan pixel observations, rainfall
greater than 0.1 mm/h occurred in 4,188,966 (10.420417%). Monthly prevalence and
the complete conditional rain-rate distribution are descriptive evidence only.

The current focal implementation weights the positive class by alpha and the
negative class by 1-alpha. Its valid-Yunnan denominator and conditional pinball
reduction are recorded exactly. The train-balanced alpha candidate is
0.895795828814217, but no alpha, gamma or other scientific parameter was selected.

The package includes synthetic loss-shaping tables, eight fixed real-data
forward-only loss diagnostics, precise metric definitions, parameter-group
counts, scheduler/FinalFit replay analysis, seed cost arithmetic and fairness
candidates. Existing batch/BF16/worker recommendations retain engineering status.
The direct 1x1 probability head architecture requires an explicit protocol pin.

All 126 previous tests and 11 new audit tests passed. Baseline file contents and
scientific contracts remain unchanged. No optimizer, parameter update, formal
training, checkpoint or Phase-B normalization was performed. Formal training
authorization remains false. Run the new audit script only in a fresh versioned
directory; its manifest identifies scripts, data references and all public evidence.
