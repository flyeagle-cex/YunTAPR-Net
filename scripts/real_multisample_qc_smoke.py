"""Few real Development samples: forward, masked loss, backward; no optimizer."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
import json
from pathlib import Path
import sys

import numpy as np
import torch

from yuntapr.contracts.loader import REPO_ROOT, load_contract, sha256
from yuntapr.data.dataset_b0 import B0Dataset, B0Record
from yuntapr.data.masks import read_frozen_yunnan_mask
from yuntapr.data.sample_schema import HimawariFrame, utc
from yuntapr.data.staging import BoundedEnglishStaging, StagedB13Reader, StagedIMERGReader
from yuntapr.models.b0 import B0Model
from yuntapr.spatial.sp04_mapping import load_sp04
from yuntapr.training.batch_contract import B0Batch
from yuntapr.training.forward_step import engineering_forward_step


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def categories(pair, frame):
    tags = {"YEAR_" + pair["month"][:4]}
    rain = int(pair["imerg_rain_yunnan_count"] or 0)
    zero = int(pair["imerg_zero_yunnan_count"] or 0)
    if rain == 0:
        tags.add("DRY")
    else:
        tags.add("RAINY")
    if pair["imerg_max_yunnan_mmhr"] and float(pair["imerg_max_yunnan_mmhr"]) >= 20:
        tags.add("HEAVY_RATE_PROXY_GE20")
    if frame["status"] == "PARTIAL":
        tags.add("PARTIAL_B13")
    if zero > 0:
        tags.add("VALID_ZERO_IMERG")
    return tags


def select_examples(pairs, frames):
    by_rel = {r["relative_path"]: r for r in frames if r["relative_path"]}
    eligible = [(p, by_rel[p["selected_b13_relative_path"]]) for p in pairs
                if p["selected_b13_relative_path"] in by_rel
                and p["pair_status"] == "EXPECTED_LATEST_SLOT_AVAILABLE"]
    wanted = {"YEAR_2023", "YEAR_2024", "DRY", "RAINY", "VALID_ZERO_IMERG",
              "HEAVY_RATE_PROXY_GE20", "PARTIAL_B13"}
    available = set().union(*(categories(p, f) for p, f in eligible)) if eligible else set()
    remaining = wanted & available
    selected = []
    used = set()
    while remaining and len(selected) < 6:
        # Rare categories first, then maximize uncovered categories.
        rarity = {tag: sum(tag in categories(p, f) for p, f in eligible) for tag in remaining}
        options = [(p, f) for p, f in eligible if (p["window_start"], p["selected_b13_relative_path"]) not in used]
        if not options:
            break
        best = max(options, key=lambda item: sum(1 / rarity[tag] for tag in remaining & categories(*item)))
        selected.append(best)
        used.add((best[0]["window_start"], best[0]["selected_b13_relative_path"]))
        remaining -= categories(*best)
    if not {"YEAR_2023", "YEAR_2024"}.issubset(set().union(*(categories(*x) for x in selected))):
        raise ValueError("Could not select real examples from both Development years")
    return selected, available, wanted - available


def smoke(args):
    science, engineering = load_contract()
    if science["execution_status"]["B0_FORMAL_TRAINING_STARTED"]:
        raise ValueError("Formal training state unexpectedly changed")
    mapping = load_sp04()
    yunnan = read_frozen_yunnan_mask(args.mask, mapping)
    stage = BoundedEnglishStaging(args.staging_root, 16777216, True)
    b13 = StagedB13Reader(stage, mapping)
    imerg = StagedIMERGReader(stage, mapping)
    pairs = read_csv(args.local_dir / "causal_pairing_per_slot.csv")
    frames = read_csv(args.local_dir / "b13_per_frame.csv")
    examples, available, unavailable = select_examples(pairs, frames)
    torch.set_num_threads(2)
    torch.manual_seed(20260930)
    model = B0Model().eval()
    results = []
    for pair, frame in examples:
        source = args.himawari_root / pair["selected_b13_relative_path"]
        target = Path(pair["imerg_day_path"])
        before = (sha256(source), sha256(target))
        observed = HimawariFrame(source, utc(frame["nominal"]), utc(frame["obs_start"]),
                                 utc(frame["obs_end"]), utc(frame["date_created"]) if frame["date_created"] else None)
        record = B0Record("development_qc_" + utc(pair["window_start"]).strftime("%Y%m%dT%H%MZ"),
                          utc(pair["window_start"]), (observed,), target, int(pair["imerg_index"]),
                          "IMERG", "V07", "Final", True)
        sample = B0Dataset([record], mapping, yunnan, b13, imerg, frozen_mask_path=args.mask)[0]
        batch = B0Batch(torch.from_numpy(sample.x_b13[None, None].copy()),
                        torch.from_numpy(sample.b13_valid_mask[None, None].copy()),
                        torch.from_numpy(sample.y_imerg[None, None].copy()),
                        torch.from_numpy(sample.imerg_valid_mask[None, None].copy()),
                        torch.from_numpy(sample.yunnan_eval_mask[None, None].copy()))
        model.zero_grad(set_to_none=True)
        output, loss = engineering_forward_step(model, batch, focal_alpha=0.25, focal_gamma=2.0,
                                                quantile_axis_reduction=engineering["loss"]["quantile_axis_reduction"])
        if not bool(torch.isfinite(loss.total)):
            raise FloatingPointError("Real multi-sample masked loss is nonfinite")
        loss.total.backward()
        grads = [p.grad for p in model.parameters() if p.grad is not None]
        if not grads or not all(bool(torch.isfinite(g).all()) for g in grads):
            raise FloatingPointError("Real multi-sample backward gradient nonfinite")
        if before != (sha256(source), sha256(target)):
            raise RuntimeError("Source changed during real smoke")
        result = {"sample_id": sample.sample_id, "year": pair["month"][:4],
                  "categories": sorted(categories(pair, frame)),
                  "pair_status": pair["pair_status"], "causality_pass": sample.himawari_obs_end <= sample.analysis_time,
                  "b13_valid_fraction": sample.b13_valid_fraction,
                  "target_valid_yunnan_pixels": loss.valid_supervised_count,
                  "valid_zero_imerg_yunnan_pixels": int(((sample.y_imerg == 0) & sample.imerg_valid_mask & yunnan).sum()),
                  "finite_forward_loss_backward": True, "parameter_tensors_with_finite_grad": len(grads),
                  "native_shape": output.native_feature_shape, "target_shape": output.target_feature_shape,
                  "source_sha256": before[0], "target_sha256": before[1]}
        results.append(result)
        print(json.dumps({"sample_done": result["sample_id"], "categories": result["categories"]}), flush=True)
    if stage._owned or any(not r.cleanup_success or r.sha256_match is False for r in stage.records):
        raise RuntimeError("Bounded staging integrity failure")
    public = {"scope": "ENGINEERING_TEST_ONLY", "formal_training_started": False,
              "optimizer_step_performed": False, "checkpoint_generated": False,
              "focal_alpha": 0.25, "focal_gamma": 2.0, "focal_parameters_frozen": False,
              "python": sys.executable, "selected_sample_count": len(results),
              "available_categories": sorted(available), "unavailable_categories": sorted(unavailable),
              "samples": results, "staging_copy_count": len(stage.records),
              "staging_cleanup_all_success": True}
    with (args.run_dir / "real_multisample_smoke.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(public, stream, ensure_ascii=False, indent=2, default=str)
        stream.write("\n")
    print(json.dumps({"smoke_complete": True, "selected": len(results)}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("run-dir", "local-dir", "himawari-root", "mask", "staging-root"):
        parser.add_argument("--" + name, type=Path, required=True)
    smoke(parser.parse_args())


if __name__ == "__main__":
    main()
