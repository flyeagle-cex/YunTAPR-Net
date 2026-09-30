"""Run self-contained checks and emit one immutable scientific-freeze sync report."""
from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "docs" / "scientific_freeze" / "runs" / "run_20260930T033524Z"
DOC = ROOT / "docs" / "scientific_freeze" / "YUNTAPR_SCIENTIFIC_FREEZE_v1.md"
CONFIG = ROOT / "config" / "science_contract_v1.yaml"
README = ROOT / "README.md"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_links(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    found = re.findall(r"\[[^]]+\]\(([^)]+)\)", text)
    local = [x.split("#", 1)[0] for x in found if not (x.startswith("http:") or x.startswith("https:") or x.startswith("#"))]
    missing = [x for x in local if not (path.parent / x).is_file()]
    if missing:
        raise AssertionError(f"Broken links in {path}: {missing}")
    return len(local)


def main() -> None:
    assert not RUN.exists(), "Do not overwrite a prior versioned run"
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert cfg["execution_status"]["B0_FORMAL_SCIENTIFIC_CONTRACT"] == "FROZEN"
    assert cfg["execution_status"]["B0_FORMAL_TRAINING_STARTED"] is False
    links = check_links(DOC) + check_links(README)
    historical_changes = subprocess.run(
        ["git", "diff", "--name-only", "HEAD", "--", "stage0-b0-evidence"],
        cwd=ROOT, text=True, capture_output=True, check=True)
    assert not historical_changes.stdout.strip(), historical_changes.stdout
    test = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests/scientific_freeze",
         "-p", "test_science_contract_v1.py", "-v"],
        cwd=ROOT, text=True, capture_output=True)
    combined = test.stdout + test.stderr
    assert test.returncode == 0 and "Ran 42 tests" in combined and combined.rstrip().endswith("OK"), combined
    rows = cfg["decision_status"]
    assert len(rows) == 7
    RUN.mkdir(parents=True)
    (RUN / "test_results.txt").write_text(combined, encoding="utf-8")
    fields = ["decision_id", "name", "status", "supersedes", "remaining_numeric_parameters", "evidence"]
    with (RUN / "decision_status.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    mapping_manifest = json.loads((ROOT / "config" / "spatial" / "sp04_coordinate_manifest_v1.json").read_text(encoding="utf-8"))
    status_table = "\n".join(
        f"| {r['decision_id']} | {r['name']} | {r['status']} | {r['remaining_numeric_parameters']} |"
        for r in rows)
    report = f"""# Scientific Freeze Synchronization Report

**Run:** `{RUN.name}`  
**Authority:** explicit researcher decisions D1–D7, 2026-09-30  
**Result:** `B0_FORMAL_SCIENTIFIC_CONTRACT=FROZEN`; `B0_FORMAL_TRAINING_STARTED=false`  
**Next phase:** `FORMAL_B0_SKELETON_IMPLEMENTATION`

The approved rules are now [human-readable](../../YUNTAPR_SCIENTIFIC_FREEZE_v1.md) and [machine-readable](../../../../config/science_contract_v1.yaml) in GitHub source. Earlier Stage-0, smoke, readiness and candidate reports were not modified. Their unresolved D1–D7 candidate labels are superseded by the later researcher decision; their measurements and data-gap evidence remain historical records.

| ID | Decision | Status | Remaining numerical/configuration item |
|---|---|---|---|
{status_table}

The SP04 axes were copied from SHA-verified actual float32 coordinate evidence, not regenerated from nominal increments. The v1 map contains 10,000 unique target cells and 25 native centers per cell under explicitly float32-rounded center-derived edges and `[south,north) × [west,east)` ownership. It matches the prior candidate map row-for-row. Native input retains all 501×501 centers; direct feature aggregation excludes native north row 0 and east column 500. The frozen Yunnan evaluation mask remains 3430 cells with SHA256 `{mapping_manifest['mask_hash_not_payload']}` and is not redistributed.

The frozen mask file's ancillary bounds yield 4/5/6 raw float64 center counts along either axis (11/78/11 cells); they are not this feature-membership rule. This difference is disclosed in v1 and does not alter the mask. The mapping CSV SHA256 is `{mapping_manifest['mapping_csv_sha256']}`; the axis CSV SHA256 is `{mapping_manifest['axes_csv_sha256']}`. `config/spatial/sp04_coordinate_manifest_v1.json` records source and axis hashes.

**Checks:** 42 repository-self-contained unit tests PASS; {links} local Markdown links resolve; historical `stage0-b0-evidence` files show no tracked modifications. No data split, train statistics, model initialization/training, 2025 Test tuning, original-file mutation, or GADM geometry/mask publication occurred. Parameters still marked `DEVELOPMENT_ESTIMATED_PARAMETER` or `ENGINEERING_CONFIG` have no scientific numeric default and must be recorded before formal training.
"""
    (RUN / "SCIENTIFIC_FREEZE_SYNC_REPORT.md").write_text(report, encoding="utf-8")
    files = [README, DOC, CONFIG,
             ROOT / "config" / "spatial" / "sp04_coordinate_axes_v1.csv",
             ROOT / "config" / "spatial" / "sp04_target_cell_membership_v1.csv",
             ROOT / "config" / "spatial" / "sp04_coordinate_manifest_v1.json",
             ROOT / "tools" / "scientific_freeze" / "build_sp04_spatial_v1.py",
             ROOT / "tools" / "scientific_freeze" / "verify_freeze_v1.py",
             ROOT / "tests" / "scientific_freeze" / "test_science_contract_v1.py",
             RUN / "test_results.txt", RUN / "decision_status.csv", RUN / "SCIENTIFIC_FREEZE_SYNC_REPORT.md"]
    manifest = {
        "run_id": RUN.name,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "SCIENTIFIC_FREEZE_SYNCHRONIZED",
        "tests_passed": 42,
        "markdown_links_checked": links,
        "old_evidence_tracked_files_modified": 0,
        "b0_formal_training_started": False,
        "files": {p.relative_to(ROOT).as_posix(): sha(p) for p in files},
    }
    (RUN / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"run": str(RUN), "tests": 42, "links": links,
                      "report_sha256": sha(RUN / "SCIENTIFIC_FREEZE_SYNC_REPORT.md")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
