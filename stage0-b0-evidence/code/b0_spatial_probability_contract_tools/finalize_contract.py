"""Finalize only the current B0 decision run after its focused tests pass."""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main(run: Path) -> None:
    assert run.name == "run_20260928T144303_935304Z", "Never finalize a different/old run"
    log = (run / "logs" / "tests.txt").read_text(encoding="utf-8")
    assert "Ran 40 tests" in log and log.rstrip().endswith("OK")
    required = [
        "README.md", "FINAL_B0_SPATIAL_PROBABILITY_CONTRACT_REPORT.md", "RESEARCHER_DECISIONS_REQUIRED.md",
        "SPATIAL/sp04_coordinate_contract.json", "SPATIAL/sp04_coordinate_arrays.npz",
        "SPATIAL/sp04_coordinate_hashes.json", "SPATIAL/geometry_summary.json",
        "SPATIAL/native_target_exact_geometry.md", "SPATIAL/target_cell_native_mapping.csv",
        "SPATIAL/index_mapping_visual_check.csv", "SPATIAL/spatial_alignment_candidates.csv",
        "DECISIONS/01_formal_spatial_alignment.md", "DECISIONS/02_quantile_tau_grid.md",
        "PROBABILITY/local_probability_design_evidence.md", "PROBABILITY/rain_conditioning_semantics.md",
        "PROBABILITY/quantile_tau_candidates.csv", "PROBABILITY/quantile_crossing_options.md",
        "PROBABILITY/output_tensor_contract.md", "PROBABILITY/pinball_loss_contract.md",
        "PROBABILITY/focal_loss_contract.md", "PROBABILITY/extreme_loss_options.md",
        "PROBABILITY/noncrossing_loss_contract.md", "PROBABILITY/deterministic_summary_options.md",
        "PROBABILITY/exceedance_probability_contract.md", "MODEL/b0_b3_backbone_shape_options.md",
        "MODEL/b0_b3_fairness_contract.md", "tests/test_contract.py", "logs/tests.txt",
    ]
    missing = [p for p in required if not (run / p).is_file()]
    assert not missing, missing
    summary = json.loads((run / "SPATIAL" / "geometry_summary.json").read_text(encoding="utf-8"))
    assert summary["half_open_observed_uniform_5_by_5"] is True
    assert summary["half_open_excluded_native_lat_rows"] == [0]
    assert summary["half_open_excluded_native_lon_cols"] == [500]
    report = run / "FINAL_B0_SPATIAL_PROBABILITY_CONTRACT_REPORT.md"
    text = report.read_text(encoding="utf-8")
    anchor = "## Execution and evidence\n"
    assert text.count(anchor) == 1
    text = text.replace(anchor, """## Superseded draft preserved

`run_20260928T144036_365388Z` is an earlier diagnostic draft. Its prose incorrectly suggested that half-open native-center counts vary across target cells. It is preserved as traceable history and is **not** the final decision package. Actual-array recalculation in this run shows exactly 25 under the stated half-open rule for every target cell; the boundary/scientific-approval caveat remains.

""" + anchor)
    report.write_text(text, encoding="utf-8")
    src = Path(__file__)
    shutil.copy2(src, run / "src" / src.name)
    status = dict(run_id=run.name,
                  status=["SPATIAL_CONTRACT_READY_FOR_RESEARCHER_DECISION",
                          "PROBABILITY_CONTRACT_READY_FOR_RESEARCHER_DECISION"],
                  b0_formal_training_started=False, tests_passed=40, tests_failed=0,
                  science_mapping_frozen=False, tau_and_loss_hyperparameters_frozen=False,
                  superseded_draft="run_20260928T144036_365388Z",
                  completed_utc=datetime.now(timezone.utc).isoformat())
    (run / "logs" / "final_status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rows = []
    for p in sorted(run.rglob("*")):
        if p.is_file() and p.name != "evidence_registry.csv":
            rows.append(dict(relative_path=p.relative_to(run).as_posix(), sha256=sha(p), bytes=p.stat().st_size,
                             role="GENERATED_EVIDENCE",
                             public_export="EXCLUDE" if p.suffix == ".npz" else "REVIEW_BEFORE_EXPORT"))
    with (run / "evidence_registry.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    assert len(rows) >= len(required)
    print(json.dumps(dict(run=str(run), files=len(rows), tests_passed=40,
                          report_sha256=sha(report), registry_sha256=sha(run / "evidence_registry.csv")), ensure_ascii=False))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
