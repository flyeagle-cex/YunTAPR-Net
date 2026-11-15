"""Close one completed PHYS20 run using saved receipts and output identities."""

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from yuntapr.experimental.research_readiness.physical_pinball_training import (
    pair_summary, verify_schedule_receipts,
)
from yuntapr.experimental.core_innovation.stage3.planning import digest


def read(path):
    return json.loads(path.read_bytes())


def identity(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return {"bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--preparation", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    package, prep = args.package.resolve(), args.preparation.resolve()
    folder = package / "B7_s2029"
    public = ROOT / "docs/research_readiness/20261115_physical_pinball_prepare"
    proposal = read(public / "EXECUTION_PROPOSAL.json")
    private = read(prep / "PRIVATE_PREPARATION.json")
    approval = read(prep / "RESEARCHER_APPROVAL.json")
    done, task = read(package / "completion.json"), read(folder / "completion.json")
    exit_record = read(prep / "execution_service_01/target_exit.json")
    launch = read(prep / "execution_service_01/target_launch.json")
    assert not (package / "failure.json").exists() and not (folder / "failure.json").exists()
    assert done["status"] == task["status"] == "COMPLETE_TRAIN_AND_DEV_EVALUATION"
    assert done["code_commit"] == task["code_commit"] == approval["code_commit"]
    assert private["proposal_sha256"] == approval["proposal_sha256"] == proposal["proposal_sha256"]
    assert exit_record["return_code"] == 0 and exit_record["automatic_retry"] is False
    assert done["updates"] == task["optimizer_updates"] == 4320 and task["replay"] == 0
    elapsed = (datetime.fromisoformat(exit_record["at"]) - datetime.fromisoformat(launch["at"])).total_seconds()
    assert 0 < elapsed <= proposal["budget"]["max_package_seconds"]
    with sqlite3.connect((folder / "updates.sqlite").as_uri() + "?mode=ro", uri=True) as db:
        updates = db.execute("SELECT model,state,COUNT(*),MIN(u),MAX(u) FROM updates GROUP BY model,state").fetchall()
    assert updates == [("B7", "RETURNED", 4320, 1, 4320)]
    verify_schedule_receipts(folder)
    source_bytes = source_files = 0
    seals = []
    for epoch in range(1, 10):
        checkpoint = read(folder / f"B7_LAST_epoch_{epoch:02d}.receipt.json")
        dev_path = folder / f"B7_development_{epoch:02d}.json"
        assert digest(read(dev_path)) == checkpoint["validation_receipt_sha256"]
        assert checkpoint["updates"] == epoch * 480
        for role in ("train", "dev"):
            path = folder / f"B7_{role}_reads_{epoch:02d}/pass_receipt.json"
            receipt = read(path)
            actual = receipt["actual_reads"]
            assert actual["delivered_bytes"] == actual["reserved_bytes"]
            source_bytes += actual["delivered_bytes"]
            source_files += actual["opened_files"]
            seals.append({"epoch": epoch, "role": role, "identity": identity(path)})
    source_bytes += task["static_source_reads"]["delivered_bytes"]
    source_files += task["static_source_reads"]["opened_files"]
    assert source_bytes == done["source_bytes"] == proposal["budget"]["total_source_bytes"]
    assert source_files == done["source_files"] == proposal["budget"]["total_source_files"]
    summary = pair_summary(ROOT, Path(private["control"]), folder)
    saved = read(package / "paired_physical_summary.json")
    for key in ("values", "candidate_minus_control", "development_screen_gates", "screen_passed"):
        assert summary[key] == saved[key]
    assert summary["screen_passed"] == done["screen_passed"]
    weight = identity(folder / "B7_LAST_epoch_09.pt")
    assert weight["sha256"] == task["checkpoints"][-1]["checkpoint_sha256"]
    tail = read(folder / "B7_tail_09.json")
    totals = tail["training_statistics_totals"]
    assert tuple(totals[k] for k in ("n_valid", "n_rain", "n_strong", "n_weak")) == (3303090, 407820, 717, 246473)
    assert len(tail["training_scene_statistics"]) == 963
    metrics = []
    for name, baseline in summary["values"]["CONTROL_COSINE9"].items():
        candidate = summary["values"]["CANDIDATE_PHYS20_COSINE9"][name]
        metrics.append(dict(metric=name, control=baseline, candidate=candidate,
                            relative_percent=100 * (candidate - baseline) / baseline,
                            gate_passed=summary["development_screen_gates"][name]))
    result = dict(status="ENGINEERING_COMPLETE_SCREEN_FAILED" if not done["screen_passed"] else "ENGINEERING_COMPLETE_SCREEN_PASSED",
                  code_commit=done["code_commit"], proposal_sha256=proposal["proposal_sha256"],
                  exit_utc=exit_record["at"], elapsed_seconds=elapsed, optimizer_updates=4320,
                  source_bytes=source_bytes, source_files=source_files, replay=0, automatic_retry=False,
                  metrics=metrics, screen_passed=done["screen_passed"],
                  point_gt20={method: rows[4] for method, rows in totals["point_thresholds"].items()},
                  population={k: totals[k] for k in ("n_valid", "n_rain", "n_strong", "n_weak")},
                  output_checkpoint=weight, checkpoint_evidence="ACTUAL_E9_OUTPUT_SHA256_READ_ONCE_NO_DESERIALIZATION",
                  output_weight_hash_bytes=weight["bytes"], source_pass_seals=seals,
                  evidence={name: identity(package / name) for name in ("completion.json", "paired_physical_summary.json")},
                  scientific_status="NOT_VERIFIED", independent_event_count="NOT_IDENTIFIED",
                  decision="ARCHIVE_FIXED_FAILED_CANDIDATE_NO_AUTOMATIC_WEIGHT_SWEEP_OR_SEED_EXPANSION")
    with args.receipt.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({key: result[key] for key in ("status", "elapsed_seconds", "metrics")}))


if __name__ == "__main__":
    main()
