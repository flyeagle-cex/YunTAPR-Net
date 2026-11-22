"""Bind a Development source allowlist from receipt metadata, without opening payloads."""

from datetime import datetime, timedelta
from hashlib import sha256
import json
from pathlib import Path
import re


def _utc_2024(value):
    moment = datetime.fromisoformat(value)
    if moment.year != 2024 or moment.utcoffset() != timedelta(0):
        raise ValueError("Explicit 2024 UTC identity required")
    return moment


def bind_main_sources(ids, scenes, forecast_records, source_metadata, *, positive_support_count):
    """Join each frozen target window to exactly one sealed f006 main archive."""
    if (not ids or len(set(ids)) != len(ids) or type(positive_support_count) is not int
            or positive_support_count <= 0):
        raise ValueError("Unique population and positive supported count required")
    by_scene = _index(scenes, "sample_id")
    by_analysis = _index([row for row in forecast_records if row["kind"] == "main"], "valid")
    by_file = {}
    for path, spec in source_metadata.items():
        if spec["kind"] != "GFS_main":
            continue
        name = Path(path).name
        if (name in by_file or spec["year"] != 2024 or type(spec["bytes"]) is not int
                or not 0 < spec["bytes"] <= 2 * 1024**2
                or not re.fullmatch(r"[0-9a-f]{64}", spec["sha"])):
            raise ValueError("Ambiguous or invalid sealed main source identity")
        by_file[name] = dict(path=path, bytes=spec["bytes"], sha256=spec["sha"])

    joined = []
    used_names = set()
    for sample_id in ids:
        scene = by_scene[sample_id]
        target = _utc_2024(scene["window_start"])
        analysis = _utc_2024(scene["analysis_time"])
        # The sealed Stage 3 per-scene role is Validation for the Development split.
        if (sample_id != scene["window_start"] or scene["year"] != "2024" or scene["role"] != "Validation"
                or analysis != target + timedelta(minutes=30)
                or analysis.hour not in (0, 6, 12, 18) or any((analysis.minute, analysis.second, analysis.microsecond))):
            raise ValueError("Target-window and analysis identity differs")
        forecast = by_analysis[scene["analysis_time"]]
        init = _utc_2024(forecast["init"])
        name = Path(forecast["relative_path"]).name
        stored = by_file[name]
        if (name in used_names or forecast["lead"] != 6 or init != analysis - timedelta(hours=6)
                or name != f"gfs_0p25_{init:%Y%m%d%H}_f006.nc" or forecast["bytes"] != stored["bytes"]):
            raise ValueError("Main archive filename, f006 time, size or uniqueness differs")
        used_names.add(name)
        joined.append(dict(sample_id=sample_id, analysis_time=analysis.isoformat(),
                           init_time=init.isoformat(), **stored))

    # A scene without a supported positive cannot contribute any within-scene pair.
    file_cap = min(positive_support_count, len(joined))
    sizes = sorted((row["bytes"] for row in joined), reverse=True)
    return joined, dict(all_main_files=len(joined), all_main_bytes=sum(sizes),
                        main_open_cap=file_cap, main_byte_cap=sum(sizes[:file_cap]))


def _index(rows, key):
    index = {}
    for row in rows:
        if row[key] in index:
            raise ValueError(f"Duplicate source key: {key}")
        index[row[key]] = row
    return index


def prepare(private_output):
    """Materialize a private metadata allowlist and return a public budget receipt."""
    from tools.research_readiness import a20_anchored_regime_readout as baseline

    root = Path(__file__).resolve().parents[2]
    readiness = root / "docs/research_readiness"
    previous = readiness / "20261110_cosine9/EXECUTION_PROPOSAL.json"
    other = readiness / ".local/cosine9_prepare_20261110_v1/PRIVATE_PREPARATION.json"
    evidence = root / "docs/core_stage3/execution_summary/evidence.json"
    old, local, stage3 = [json.loads(path.read_bytes()) for path in (previous, other, evidence)]
    inherited = Path(local["inherited"]).read_bytes()
    if sha256(inherited).hexdigest() != local["inherited_file_sha256"]:
        raise ValueError("Inherited COSINE9 source binding differs")
    prepared = json.loads(inherited)["prepared"]
    if prepared["data"] != old["data"]:
        raise ValueError("Inherited COSINE9 population differs")
    scope = prepared["roles"]["Development"]
    request_file = Path(prepared["private_inputs"]["request"])
    request = json.loads(request_file.read_bytes())
    request_sha = request.pop("request_sha256")
    if request_sha != stage3["request_sha256"] or _digest(request) != request_sha:
        raise ValueError("Frozen Stage 3 request differs")
    dev_manifest = request_file.parent / request["roles"]["Development"]["manifest"]
    dev = json.loads(dev_manifest.read_bytes())
    dev_sha = dev.pop("manifest_sha256")
    if dev_sha != stage3["candidate_manifest_sha256"]["Development"] or _digest(dev) != dev_sha:
        raise ValueError("Frozen Development manifest differs")
    joined, main_budget = bind_main_sources(
        scope["ids"], dev["scene_records"], dev["gfs_files"], scope["files"], positive_support_count=160,
    )
    expected = stage3["read_breakdown"]["Development"]["main"]
    if len(joined) != 963 or expected != dict(files=963, bytes=main_budget["all_main_bytes"]):
        raise ValueError("Main sources do not reproduce the inherited 963-scene ledger")
    static = dict(path=str(Path(local["terrain"]) / "B6_static.npz"), bytes=312828,
                  sha256=old["static_source_sha256"]["B7"])
    arrays = baseline.manifest()
    budget = dict(
        saved_array_opens=len(arrays), saved_array_bytes=sum(row["bytes"] for row in arrays),
        gfs_main_opens_max=main_budget["main_open_cap"], gfs_main_bytes_max=main_budget["main_byte_cap"],
        static_pack_opens_max=1, static_pack_bytes_max=static["bytes"],
        satellite_opens=0, imerg_opens=0, gfs_thermo_opens=0, checkpoint_loads=0,
        forwards=0, optimizer_updates=0, retries=0, final_2025_access=False,
    )
    budget["total_payload_bytes_max"] = sum(
        budget[key] for key in ("saved_array_bytes", "gfs_main_bytes_max", "static_pack_bytes_max")
    )
    private = dict(source_by_scene=joined, prediction_shards=arrays, static_pack=static,
                   prediction_folder=str(baseline.SOURCE / "arrays"), budget=budget)
    report = dict(
        status="SOURCE_METADATA_BOUND_EXECUTION_NOT_AUTHORIZED",
        development_manifest_sha256=dev_sha, inherited_source_scope_sha256=scope["source_manifest_sha256"],
        checkpoint_sha256=baseline.CHECKPOINT_SHA, saved_completion_sha256=baseline.COMPLETION_SHA,
        supervision_mask_sha256=baseline.MASK_SHA, static_pack_sha256=static["sha256"],
        private_allowlist_sha256=_digest(private), baseline_main_metadata=main_budget, budget=budget,
        opened_scientific_payloads=0,
    )
    private["receipt"] = report
    baseline.write(private_output, private)
    return report


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.private_output), indent=2))
