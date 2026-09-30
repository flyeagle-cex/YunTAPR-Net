"""Real Train/Validation formal-rule forward/loss/backward; no parameter update."""
import argparse
import csv
from dataclasses import asdict
from datetime import timedelta
import json
from pathlib import Path
import sys
import numpy as np
import torch

from yuntapr.contracts.loader import REPO_ROOT, load_contract, sha256
from yuntapr.data.dataset_b0 import B0Dataset, B0Record
from yuntapr.data.formal_policy import MISSING_LATEST
from yuntapr.data.masks import read_frozen_yunnan_mask
from yuntapr.data.normalization import PhaseANormalizer
from yuntapr.data.sample_schema import HimawariFrame, utc
from yuntapr.data.staging import BoundedEnglishStaging, StagedB13Reader, StagedIMERGReader
from yuntapr.models.b0 import B0Model
from yuntapr.spatial.sp04_mapping import load_sp04
from yuntapr.training.batch_contract import B0Batch
from yuntapr.training.forward_step import formal_rules_engineering_forward_step
from fit_phase_a_v1_1 import HROOT, MASK, PRIOR, evidence, dump


def run(out):
    if (out / "real_normalized_forward_smoke.json").exists():
        raise FileExistsError("A completed real smoke run must not be overwritten")
    _, cfg = load_contract()
    mapping = load_sp04()
    yunnan = read_frozen_yunnan_mask(MASK, mapping)
    normalizer = PhaseANormalizer.from_pinned()
    stage = BoundedEnglishStaging(Path(r"F:\pytorch\Research\stage0_himawari\cache\staging"), cfg["staging"]["max_temporary_bytes"], True, True)
    b13, imerg = StagedB13Reader(stage, mapping), StagedIMERGReader(stage, mapping)
    prior_manifest = json.loads((PRIOR/"manifest.json").read_text(encoding="utf-8"))
    frames = evidence("b13_per_frame.csv", prior_manifest)
    by_relative = {f["relative_path"]: f for f in frames if f["relative_path"]}
    by_nominal = {utc(f["nominal"]): f for f in frames}
    with (out/"formal_sample_eligibility_2023_2024.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    targets = json.loads((out/"imerg_development_revalidation.json").read_text(encoding="utf-8"))["days"]
    target_hashes = {d["day_path"]: d["sha256"] for d in targets}
    examples = [("FULL_VALID_2023", next(r for r in rows if r["month"].startswith("2023") and r["formal_supervised_eligible"] == "True")),
                ("FULL_VALID_2024", next(r for r in rows if r["month"].startswith("2024") and r["formal_supervised_eligible"] == "True")),
                ("PARTIAL_REJECT", next(r for r in rows if r["formal_reject_reason"] == "B13_PARTIAL_FORMAL_SUPERVISION_REJECTED")),
                ("OLDER_FALLBACK_REJECT", next(r for r in rows if r["formal_reject_reason"] == MISSING_LATEST))]
    torch.set_num_threads(2)
    torch.manual_seed(20260930)
    model = B0Model().eval()
    results = []
    for category, row in examples:
        f = by_relative[row["selected_b13_relative_path"]]
        source, target = HROOT/f["relative_path"], Path(row["imerg_day_path"])
        before = sha256(source), sha256(target)
        if before[1] != target_hashes[str(target)]:
            raise ValueError("IMERG source changed after time/grid/provenance revalidation")
        frame = HimawariFrame(source, utc(f["nominal"]), utc(f["obs_start"]), utc(f["obs_end"]), utc(f["date_created"]))
        context_frames = []
        for offset in range(6):
            candidate = by_nominal.get(utc(row["expected_nominal"])-timedelta(minutes=offset*10))
            if candidate and candidate["status"] in ("FULL_VALID", "PARTIAL", "ALL_FILL"):
                context_frames.append(HimawariFrame(HROOT/candidate["relative_path"], utc(candidate["nominal"]),
                    utc(candidate["obs_start"]), utc(candidate["obs_end"]), utc(candidate["date_created"])))
        record = B0Record(category+"_"+row["window_start"], utc(row["window_start"]), tuple(context_frames), target, int(row["imerg_index"]), "IMERG", "V07", "Final", True)
        dataset = B0Dataset([record], mapping, yunnan, b13, imerg, frozen_mask_path=MASK,
                            formal_supervised=True, normalizer=normalizer)
        result = {"category": category, "window_start": row["window_start"], "year": utc(row["window_start"]).year,
                  "expected_latest_slot": row["expected_nominal"], "selected_nominal": f["nominal"],
                  "obs_start": f["obs_start"], "obs_end": f["obs_end"], "date_created": f["date_created"],
                  "source_sha256": before[0], "target_sha256": before[1], "expected_formal_eligible": row["formal_supervised_eligible"] == "True"}
        result["causal_selection_context"] = "All indexed readable slots among expected latest and preceding five ten-minute slots"
        result["context_frame_count"] = len(context_frames)
        if category.endswith("REJECT"):
            # Independently read the preserved real frame to verify actual partial/older evidence.
            actual, mask, observed = b13(source, frame.nominal_time)
            result["actual_valid_fraction"] = float(mask.mean())
            if category == "PARTIAL_REJECT" and (mask.all() or not mask.any()):
                raise ValueError("Selected partial evidence no longer partial")
            if category == "OLDER_FALLBACK_REJECT":
                if not (frame.nominal_time < utc(row["expected_nominal"]) and frame.obs_end <= utc(row["analysis_time"])):
                    raise ValueError("Selected older frame is not actually older and causal")
                expected_name = "NC_H09_"+utc(row["expected_nominal"]).strftime("%Y%m%d_%H%M")+"_R21_FLDK.06001_06001.nc"
                if any(source.parent.glob(expected_name)):
                    raise ValueError("Expected slot became present; refresh inventory before eligibility")
            try:
                dataset[0]
                raise AssertionError("Formal path accepted rejected real sample")
            except ValueError as error:
                if str(error) != row["formal_reject_reason"]:
                    raise
                result.update(formal_rejected=True, reject_reason=str(error), backbone_entered=False)
        else:
            sample = dataset[0]
            batch = B0Batch.from_formal_samples([sample])
            model.zero_grad(set_to_none=True)
            output, loss = formal_rules_engineering_forward_step(model, batch, focal_alpha=.25, focal_gamma=2.,
                                                                 quantile_axis_reduction=cfg["loss"]["quantile_axis_reduction"])
            if not torch.isfinite(loss.total):
                raise FloatingPointError("Normalized real loss nonfinite")
            loss.total.backward()
            grads = [p.grad for p in model.parameters()]
            if any(g is None or not torch.isfinite(g).all() for g in grads):
                raise FloatingPointError("Normalized real backward not fully finite")
            result.update(formal_supervised_qc_pass=sample.formal_supervised_qc_pass,
                expected_latest_available=sample.expected_latest_available, older_causal_available=sample.older_causal_available,
                used_older_causal_frame=sample.used_older_causal_frame, b13_full_valid=sample.b13_full_valid,
                normalization_version=sample.normalization_version, normalization_mu=sample.normalization_mu,
                normalization_sigma=sample.normalization_sigma, normalization_sha256=sample.normalization_artifact_sha256,
                normalized_input_min=float(sample.x_b13_normalized.min()), normalized_input_max=float(sample.x_b13_normalized.max()),
                native_shape=output.native_feature_shape, target_shape=output.target_feature_shape,
                placeholder_policy=output.placeholder_policy, valid_yunnan_loss_pixels=loss.valid_supervised_count,
                loss=float(loss.total.detach()), finite_forward_loss_backward=True, finite_gradient_parameter_tensors=len(grads))
        if before != (sha256(source), sha256(target)):
            raise ValueError("Read-only raw source hash changed")
        result["source_unchanged"] = True
        results.append(result)
        print(json.dumps({"sample": category, "completed": True}), flush=True)
    inventory = json.loads((out/"staging_inventory_v3.json").read_text(encoding="utf-8"))
    large = Path(inventory["path"])
    large_frame = next(f for f in frames if str(HROOT/f["relative_path"]) == str(large))
    large_before = sha256(large)
    x, valid, meta = b13(large, utc(large_frame["nominal"]))
    if not valid.all() or large_before != sha256(large):
        raise ValueError("Verified large valid file no longer passes staging/full-valid checks")
    if stage._owned or any(not r.cleanup_success or not r.sha256_match for r in stage.records):
        raise ValueError("Staging cleanup or SHA failure")
    dump(out/"real_normalized_forward_smoke.json", {"execution_scope": "ENGINEERING_ONLY", "python": sys.executable,
        "focal_parameter_scope": "ENGINEERING_TEST_ONLY", "focal_alpha": .25, "focal_gamma": 2.,
        "formal_training_started": False, "optimizer_step_performed": False, "checkpoint_generated": False,
        "samples": results, "largest_valid_file": {"bytes": large.stat().st_size, "sha256": large_before,
        "full_valid_count": int(valid.sum()), "cap_bytes": stage.max_bytes, "passed": True},
        "staging_operations": [asdict(r) for r in stage.records], "all_cleanup_success": True})


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", type=Path, required=True)
    run(p.parse_args().run_dir)
