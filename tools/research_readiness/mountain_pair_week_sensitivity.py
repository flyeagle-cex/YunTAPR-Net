"""One bounded leave-one-UTC-week-out analysis of saved mountain aggregates."""

import argparse
from collections import defaultdict
from datetime import datetime, timedelta
from hashlib import sha256
import json
from math import fsum, isclose, isfinite
from pathlib import Path
import time


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs/research_readiness/20261115_mountain_pair_results"
PRIVATE = ROOT / "docs/research_readiness/.local"
SOURCE = PRIVATE / "mountain_pair_evaluation_v1"
RUN = PRIVATE / "mountain_pair_week_sensitivity_v1"
SCOPE = "COSINE9_B7_E9_HIGH_ELEVATION_LEAVE_ONE_UTC_WEEK"
INPUTS = {
    "REAL_COSINE9": dict(bytes=3692556, sha256="95d2a238f43bcdb32a7c33b0f9bd2aabbc7aac640335ffbab3b10c5b277900fb"),
    "ZERO_COSINE9": dict(bytes=3692623, sha256="5a7c0f00a8c88622745a6a3536fe8f96096ae69285065ad83a534124c71a9c77"),
}
BUDGET = dict(saved_aggregate_bytes=7385179, saved_aggregate_opens=2, seconds=60,
              scientific_source_reads=0, forwards=0, optimizer_updates=0, retries=0, final_2025_access=False)
IDENTITY = "056ae0d9168dd572383543e652b4f49462b868643d19d6dab0babc1ec21a18ba"
BASELINE = -0.0006961972905197065
TOLERANCE = 1e-10


def utc_week(scene_id):
    target = datetime.fromisoformat(scene_id)
    if target.utcoffset() != timedelta(0) or target.year != 2024:
        raise ValueError("Only explicit 2024 UTC target metadata is permitted")
    analysis_day = (target + timedelta(minutes=30)).date()
    return analysis_day - timedelta(days=analysis_day.weekday())


def leave_one_week(real, zero, *, expected=(963, 178, 80, 36), baseline=BASELINE):
    if len(real) != len(zero) or len(real) != expected[0]:
        raise ValueError("Paired scene counts differ")
    weekly = defaultdict(list)
    occupied = set()
    for a, b in zip(real, zero):
        sid = a["scene_id"]
        if sid != b["scene_id"] or sid in occupied:
            raise ValueError("Scene identity, order or uniqueness differs")
        occupied.add(sid)
        a_cells, b_cells = (side["elevation_rainfall_cells"][2][4:] for side in (a, b))
        if len(a_cells) != 3 or len(b_cells) != 3:
            raise ValueError("Frozen high-elevation strong rainfall cells missing")
        n, differences = 0, []
        for x, y in zip(a_cells, b_cells):
            if type(x["n_rain"]) is not int or x["n_rain"] != y["n_rain"] or x["n_rain"] < 0:
                raise ValueError("The paired cell denominator differs")
            values = [z["physical_pinball_over20_sum"] for z in (x, y)]
            if not all(isfinite(value) and value >= 0 for value in values) or (x["n_rain"] == 0 and any(values)):
                raise ValueError("Invalid physical Pinball sum")
            n += x["n_rain"]
            differences.append(values[0] - values[1])
        weekly[utc_week(sid)].append((n, fsum(differences)))
    total_n = sum(n for rows in weekly.values() for n, _ in rows)
    strong_scenes = sum(n > 0 for rows in weekly.values() for n, _ in rows)
    if (len(real), total_n, strong_scenes, len(weekly)) != expected:
        raise ValueError("Frozen high-elevation population or UTC week count differs")
    totals = [(sum(n for n, _ in rows), fsum(d for _, d in rows)) for rows in weekly.values()]
    all_delta = fsum(d for _, d in totals) / total_n
    if not isclose(all_delta, baseline, rel_tol=0, abs_tol=TOLERANCE):
        raise ValueError("Saved source does not reconstruct the frozen physical difference")
    omitted = []
    for i, (removed, _) in enumerate(totals):
        if removed and removed < total_n:
            retained_delta = fsum(d for j, (_, d) in enumerate(totals) if i != j) / (total_n - removed)
            omitted.append(retained_delta)
    return dict(full_difference=all_delta, weeks=len(totals), strong_weeks=sum(n > 0 for n, _ in totals),
                estimable_informative_deletions=len(omitted), omitted_week_min=min(omitted, default=None),
                omitted_week_max=max(omitted, default=None),
                flips_to_real_higher_loss=sum(delta > TOLERANCE for delta in omitted),
                near_ties=sum(abs(delta) <= TOLERANCE for delta in omitted), scientific_status="NOT_VERIFIED")


def build_proposal():
    script_sha = sha256(Path(__file__).read_bytes()).hexdigest()
    plan = dict(authorization_scope=SCOPE, code_sha256=script_sha, budget=BUDGET, inputs=INPUTS,
                paired_population_sha256=IDENTITY, baseline_real_minus_zero=BASELINE,
                time_definition="UTC target plus 30 minutes; Monday calendar weeks",
                comparison="B7 seed2029 COSINE9 REAL minus ZERO, altitude >=2000m, float32 R >20mm/h",
                threshold_tolerance=TOLERANCE)
    plan["proposal_sha256"] = sha256(json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return plan


def execute_once():
    start = time.monotonic()
    proposal = json.loads((DOCS / "TERRAIN_WEEK_SENSITIVITY_PROPOSAL.json").read_text(encoding="utf-8"))
    if proposal != build_proposal():
        raise PermissionError("Frozen proposal and code identity differ")
    grant = json.loads((RUN / "RESEARCHER_APPROVAL.json").read_text(encoding="utf-8"))
    if (grant.get("approved_by_researcher") is not True or not grant.get("decision_id")
            or any(grant.get(k) != proposal[k] for k in ("authorization_scope", "budget", "proposal_sha256"))):
        raise PermissionError("Separate approval of the exact saved-aggregate scope is required")
    output = RUN / "output"
    output.mkdir(exist_ok=False)
    scenes = []
    for label, identity in INPUTS.items():
        file = SOURCE / label / "terrain_metrics.json"
        if file.stat().st_size != identity["bytes"]:
            raise ValueError("Saved aggregate size differs")
        with file.open("rb") as stream:
            raw = stream.read(identity["bytes"])
        if len(raw) != identity["bytes"] or sha256(raw).hexdigest() != identity["sha256"]:
            raise ValueError("Saved aggregate digest differs")
        body = json.loads(raw)
        if (body["paired_population_sha256"] != IDENTITY
                or body["population"] != dict(n_valid=3303090, n_rain=407820, n_strong=717)):
            raise ValueError("Frozen paired population differs")
        scenes.append(body["scene_statistics"])
    result = leave_one_week(*scenes)
    if time.monotonic() - start > BUDGET["seconds"]:
        raise TimeoutError("Saved-aggregate analysis deadline exceeded")
    result.update(status="COMPLETE", proposal_sha256=proposal["proposal_sha256"], budget=BUDGET,
                  elapsed_seconds=time.monotonic() - start)
    with (output / "completion.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("proposal", "execute"))
    args = parser.parse_args()
    print(json.dumps(build_proposal() if args.mode == "proposal" else execute_once(), indent=2))
