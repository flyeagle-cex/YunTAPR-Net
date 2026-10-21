"""Bounded, metadata-only review. Never imports project training code or opens data.

Run with the independent bundled Python and -B. Only the isolated checkout is
writable; --live-root is used for an explicit small set of JSON/code observations.
No SQLite, checkpoint payload, raw observation, environment or process control.
This is a retrospective reproduction tool, not a live monitoring command. Its
metadata parsing consumes shared RAM/I/O; do not rerun during formal training
without separately establishing adequate resource headroom. The review's final
RUN-01 incident means zero resource interference was not demonstrated.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/audits/20261021_completed_work_review"
FREEZE = "docs/b1_scientific_freeze/runs/run_20261003T045139_110133Z"
FRAME = "docs/b1_temporal_audit/runs/run_20261003T035724_142784Z"
V7 = "docs/phase_b_v2_formal_execution/seed2027_b1_epoch7_recovery_v7"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def digest(value):
    return sha(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())


def write(name, value):
    path = OUT / "evidence" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-root", type=Path, required=True)
    args = parser.parse_args()
    live = args.live_root.resolve()
    if live == ROOT or git("branch", "--show-current") != "audit/completed-work-20261021":
        raise PermissionError("Use the explicitly isolated audit branch")
    observations = []

    def read(relative, *, source=ROOT, maximum=20 * 1024**2):
        # Only repository metadata/code. No path resolution/stat on dataset paths.
        relative = relative.replace("\\", "/")
        if not relative.startswith(("docs/", "config/", "src/", "scripts/", "tools/", "stage0-b0-evidence/")):
            raise PermissionError(relative)
        if ".." in relative.split("/") or not relative.endswith((".json", ".csv", ".md", ".py", ".txt", ".yaml", ".ps1", ".html")):
            raise PermissionError(relative)
        path = source / relative
        with path.open("rb") as stream:
            raw = stream.read(maximum + 1)
        if len(raw) > maximum:
            raise ValueError("Metadata size bound: " + relative)
        observations.append(dict(path=relative, source="live_read_only" if source == live else "isolated_base",
                                 bytes=len(raw), sha256=sha(raw)))
        return raw

    def js(relative, **kwargs):
        return json.loads(read(relative, **kwargs))

    def rows(relative):
        return list(csv.DictReader(read(relative).decode("utf-8-sig").splitlines()))

    release = js(V7 + "/release.json", source=live)
    code = []
    for relative, expected in release["source_pins"].items():
        actual = sha(read(relative, source=live))
        isolated = sha(read(relative))
        code.append(dict(path=relative, expected=expected, live_sha256=actual,
                         isolated_sha256=isolated, match=expected == actual,
                         isolated_matches_live=isolated == actual))
    write("v7_code_identity.json", dict(source_commit=release["source_commit"],
        source_sha256=release["source_sha256"], computed_source_sha256=digest(release["source_pins"]),
        matched=sum(x["match"] for x in code), total=len(code), files=code))

    names = ["execution_status.json", ".local/sessions/session_0001/heartbeat.json",
             ".local/sessions/session_0001/worker_identity.json",
             ".local/sessions/session_0001/supervisor_identity.json",
             ".local/B1_V2__E0__s2027/authorized_b1_epoch7_recovery.json"]
    runtime = dict(observed_utc=datetime.now(timezone.utc).isoformat(), isolated_base_commit=git("rev-parse", "HEAD"),
                   live_root=str(live), isolated_root=str(ROOT), observations={}, not_read=[
                       "live SQLite ledger", "all checkpoint payloads", "raw datasets including 2025",
                       "270+ MB live event log", "training environment packages"])
    for name in names:
        try:
            runtime["observations"][name] = js(V7 + "/" + name, source=live, maximum=512*1024)
        except (OSError, ValueError) as error:
            runtime["observations"][name] = dict(unavailable=type(error).__name__)
    status = runtime["observations"]["execution_status.json"]
    quota = status["quota"]
    runtime["accounting_consistent"] = (
        quota["reserved"] == 166305 + quota["new_reserved"]
        and quota["returned_verified"] == 166304 + quota["new_returned_verified"]
        and quota["limit"] == 364969
        and quota["reserved"] <= quota["limit"]
        and quota["old_unverified_attempts"] == 1
        and quota["abandoned_old_updates"] + quota["adopted_prior_updates"] == 166305)
    runtime["scope_limitations"] = "JSON snapshots are sequential, not an atomic ledger transaction; native Job not probed."
    for item in runtime["observations"].values():
        if "nonce" in item:
            item["nonce_sha256"] = sha(item.pop("nonce").encode())
        if "job_name" in item:
            item["job_name_sha256"] = sha(item.pop("job_name").encode())
    write("runtime_snapshot.json", runtime)

    registry = js("config/science_v2/scientific_freeze_v2_registry_v1.json")
    pins = []
    for key in ("researcher_approval", "frozen_head", "frozen_phase_a_protocol", "accepted_candidate_head", "accepted_candidate_protocol"):
        item = registry[key]
        pins.append(dict(name=key, path=item["path"], match=sha(read(item["path"])) == item["sha256"]))
    protocol = js("config/science_v2/phase_a_protocol_frozen_v1.json")
    for key, item in protocol["identity"].items():
        relative = item["path"].replace("\\", "/")
        if ":" in relative:
            pins.append(dict(name=key, path=relative, match=None, status="RESTRICTED_PRIVATE_PAYLOAD_NOT_READ"))
        else:
            pins.append(dict(name=key, path=relative, match=sha(read(relative)) == item["sha256"]))
    write("freeze_identity.json", pins)

    frames = {}
    frame_index = js(FRAME + "/frame_identity_index.json")
    frame_pins = []
    for relative, expected in frame_index["files"].items():
        raw = read(FRAME + "/" + relative)
        frame_pins.append(dict(path=relative, match=sha(raw) == expected))
        for row in csv.DictReader(raw.decode("utf-8-sig").splitlines()):
            if row["nominal"] in frames:
                raise ValueError("Duplicate frame identity")
            frames[row["nominal"]] = row
    temporal = dict(frame_count=len(frames), frame_index_expected=frame_index["nominal_count"],
                    frame_pins=frame_pins, years=[])
    for year, expected_count in ((2023, 10455), (2024, 10501)):
        b1 = rows(f"{FREEZE}/b1_{year}_formal_manifest.csv")
        b0 = rows(f"{FREEZE}/b0_matched_control_{year}_formal_manifest.csv")
        failures = []
        late_created = 0
        for i, (one, zero) in enumerate(zip(b1, b0)):
            start = datetime.fromisoformat(one["window_start"])
            analysis = datetime.fromisoformat(one["analysis_time"])
            valid = (len(b1) == len(b0) == expected_count and int(one["index"]) == i
                and one["sample_id"] == zero["sample_id"] == one["window_start"]
                and start.year == year and 3 <= start.month <= 10
                and start.utcoffset() == timedelta(0) and analysis == start + timedelta(minutes=30)
                and one["imerg_day_path"] == zero["imerg_day_path"]
                and one["imerg_index"] == zero["imerg_index"]
                and one["imerg_sha256"] == zero["imerg_sha256"]
                and int(one["target_valid_yunnan_cells"]) == int(zero["target_valid_yunnan_cells"]) == 3430
                and zero["selected_slot"] == "5")
            for slot, minutes in enumerate((60, 50, 40, 30, 20, 10)):
                nominal = one[f"slot_{slot}_nominal"]
                frame = frames[nominal]
                end = datetime.fromisoformat(frame["obs_end"])
                begin = datetime.fromisoformat(frame["obs_start"])
                valid &= (datetime.fromisoformat(nominal) == analysis - timedelta(minutes=minutes)
                    and begin <= end <= analysis and int(frame["valid_count"]) == 251001
                    and all(frame[k] == "True" for k in ("present", "readable", "decoded", "full_valid", "metadata_valid")))
                if frame.get("date_created") and datetime.fromisoformat(frame["date_created"]) > analysis:
                    late_created += 1
            valid &= zero["expected_nominal"] == one["slot_5_nominal"]
            if not valid:
                failures.append(one["sample_id"])
        temporal["years"].append(dict(year=year, b0=len(b0), b1=len(b1),
            unique_b1=len({x["sample_id"] for x in b1}), failures=failures,
            selected_scene_slot_refs=len(b1)*6, date_created_after_analysis_refs=late_created))
    temporal["normalization"] = js(FREEZE + "/normalization_b1_2023_shared_v1.json")
    write("paired_data_contract.json", temporal)
    del frames

    analysis_manifest = js("docs/phase_b_v2_seed2026_scientific_analysis/v1/manifest.json")
    analysis_rows = rows("docs/phase_b_v2_seed2026_scientific_analysis/v1/tables/final_metrics.csv")
    complete_status = js("docs/phase_b_v2_formal_execution/seed2026_operator_v3/execution_status.json")
    reports = []
    for relative, expected in analysis_manifest["public_sources_and_local_aggregate_receipt_sha256"].items():
        if "/.local/" in relative or not relative.endswith("__s2026.json"):
            continue
        raw = read(relative)
        report = json.loads(raw)
        checks = []
        for epoch in report["epochs"]:
            dev = epoch["development"]
            unsigned = {k: v for k, v in dev.items() if k != "receipt_sha"}
            summary = dev["summary"]
            checks.append(dict(epoch=epoch["epoch"], receipt_match=digest(unsigned) == dev["receipt_sha"],
                scenes=summary["scenes"], n_valid=summary["n_valid"], n_rain=summary["n_rain"],
                train_scenes=epoch["train"]["scenes"], train_batches=epoch["train"]["batches"],
                train_ids_sha=epoch["train"]["ids_sha"], dev_ids_sha=dev["ids_sha"],
                scene_blocks_sha=digest(dev["scene_blocks"]),
                receipt_sha=dev["receipt_sha"], checkpoint=epoch["checkpoint"],
                blocks_pool_valid=sum(b["n_valid"] for b in dev["blocks"]) == summary["n_valid"],
                blocks_pool_rain=sum(b["n_rain"] for b in dev["blocks"]) == summary["n_rain"]))
        short_model = "B0" if report["run_id"].startswith("B0") else "B1"
        arm = report["run_id"].split("__")[1]
        table = next(r for r in analysis_rows if r["model"] == short_model and r["arm"] == arm)
        summary = report["epochs"][-1]["development"]["summary"]
        metric_matches = {k: float(table[k]) == summary[k] for k in
                          ("core_fp64", "brier", "auroc", "average_precision", "conditional_pinball")}
        metric_matches["q32_coverage"] = float(table["q32_coverage"]) == summary["coverage"][-1]
        ledger_run = next(r for r in complete_status["quota"]["runs"] if r["id"] == report["run_id"])
        reports.append(dict(path=relative, sha256=sha(raw), recorded_sha_match=sha(raw) == expected,
            run_id=report["run_id"], status=report["status"], updates=report["updates"],
            epoch_sequence=[r["epoch"] for r in checks], epochs=checks,
            final_metrics={k: summary[k] for k in metric_matches if k != "q32_coverage"},
            q32_coverage=summary["coverage"][-1], published_metric_matches=metric_matches,
            final_ledger_last_match=checks[-1]["checkpoint"]["payload_sha256"] == ledger_run["last_sha"]))
    write("seed2026_receipt_audit.json", dict(reports=reports, completed_status=complete_status,
        total_retained_updates=sum(r["updates"] for r in reports),
        validated_epoch_receipts=sum(len(r["epochs"]) for r in reports),
        limitations="No exact score DB reorder, raw re-evaluation, ledger query or checkpoint payload read; inherited separate payload/backup audits."))

    extra = []
    for relative in ("docs/phase_b_v2_formal_execution/seed2027_epoch2_recovery_v2/B0_MATCHED_V2__E0__s2027.json",
                     V7 + "/B1_V2__E0__s2027.json"):
        report = js(relative, source=live)
        epochs = report["epochs"]
        extra.append(dict(path=relative, run_id=report["run_id"], status=report["status"], updates=report["updates"],
            epochs=[e["epoch"] for e in epochs],
            receipts_match=all(digest({k:v for k,v in e["development"].items() if k != "receipt_sha"}) == e["development"]["receipt_sha"] for e in epochs),
            last_sha256=epochs[-1]["checkpoint"]["payload_sha256"],
            final_summary=epochs[-1]["development"]["summary"]))
    write("seed2027_completed_e0.json", extra)

    write("source_manifest.json", dict(schema="COMPLETED_WORK_REVIEW_METADATA_v1", observed_utc=datetime.now(timezone.utc).isoformat(),
        base_commit=git("rev-parse", "HEAD"), branch=git("branch", "--show-current"), python=sys.version,
        observations=observations, optimizer_updates=0, raw_payload_reads=0, checkpoint_payload_reads=0,
        live_ledger_queries=0, historical_record_writes=0))
    print(json.dumps(dict(code_pins=len(code), code_mismatches=sum(not x["match"] for x in code),
        data_failures=sum(len(y["failures"]) for y in temporal["years"]), seed2026_reports=len(reports),
        epoch_receipt_mismatches=sum(not e["receipt_match"] for r in reports for e in r["epochs"]),
        metric_mismatches=sum(not x for r in reports for x in r["published_metric_matches"].values()),
        new_optimizer_updates=0), indent=2))


if __name__ == "__main__":
    main()
