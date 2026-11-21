"""Reconstruct A20's negative-loss coverage from frozen QC and training metadata."""

import argparse
import csv
from hashlib import sha256
import io
import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
QC_PATH = "docs/b0_pretraining_closure/runs/run_20260930T095416Z/formal_sample_eligibility_2023_2024.csv"
PROPOSAL_PATH = "docs/research_readiness/20261119_conditional_intensity_diagnostic/A20_RESTART_PROPOSAL.json"
ORDERS_SHA256 = "193fcbc6eab5fa3b29b02ecc3419ab7a01b45a143f08f0a7464fbcc1f4067502"
SCENES = 959
VALID_PER_SCENE = 3430
STRONG_PER_EPOCH = 484
RAIN_PER_EPOCH = 345725
NONZERO_PER_EPOCH = 388020
EPOCHS = 9
BATCH = 2


def qc_strong_scenes(rows, scene_ids):
    """Discriminate strict FP32 >20 using the same-mask scene maxima."""
    maxima = {}
    rain_count, nonzero_count = 0, 0
    for row in rows:
        scene = row["window_start"]
        if scene not in scene_ids:
            continue
        if scene in maxima or int(row["imerg_valid_yunnan_count"]) != VALID_PER_SCENE:
            raise ValueError("Duplicate scene or fixed supervision count changed")
        value = np.float32(float(row["imerg_max_yunnan_mmhr"]))
        if not np.isfinite(value) or value < 0:
            raise ValueError("Invalid saved maximum")
        maxima[scene] = value
        rain_count += int(row["imerg_rain_yunnan_count"])
        nonzero_count += VALID_PER_SCENE - int(row["imerg_zero_yunnan_count"])
    if set(maxima) != scene_ids or (rain_count, nonzero_count) != (RAIN_PER_EPOCH, NONZERO_PER_EPOCH):
        raise ValueError("QC and Train coverage do not match")
    return {scene for scene, value in maxima.items() if value > np.float32(20)}, sum(
        int(value == np.float32(20)) for value in maxima.values()
    )


def count_epoch(order, strong_scenes, total_strong):
    """Count skipped negative exposures including a possible unpaired last scene."""
    if not strong_scenes <= set(order) or len(set(order)) != len(order):
        raise ValueError("Strong-scene scope or batch order changed")
    negatives = len(order) * VALID_PER_SCENE - total_strong
    if not len(strong_scenes) <= total_strong <= len(strong_scenes) * VALID_PER_SCENE:
        raise ValueError("Inconsistent strong-pixel total")
    batch_count = (len(order) + BATCH - 1) // BATCH
    skipped_batches, skipped_negatives = 0, 0
    for start in range(0, len(order), BATCH):
        batch = order[start : start + BATCH]
        if not strong_scenes.intersection(batch):
            skipped_batches += 1
            skipped_negatives += len(batch) * VALID_PER_SCENE
    return dict(batches=batch_count, skipped_batches=skipped_batches,
                negative_exposures=negatives, skipped_negative_exposures=skipped_negatives)


def reconstruct(run, root=ROOT):
    proposal = json.loads((root / PROPOSAL_PATH).read_bytes())
    qc = (root / QC_PATH).read_bytes()
    order_bytes = (run / "paired_orders.json").read_bytes()
    qc_sha = sha256(qc).hexdigest()
    if qc_sha != proposal["data"]["target_QC_sha256"] or sha256(order_bytes).hexdigest() != ORDERS_SHA256:
        raise ValueError("Frozen QC or training-order file changed")
    orders = json.loads(order_bytes)
    if set(orders) != {str(e) for e in range(1, EPOCHS + 1)}:
        raise ValueError("Expected the complete nine training orders")
    scene_ids = set(orders["1"]["ids"])
    if len(scene_ids) != SCENES or not all(s.startswith("2023-") for s in scene_ids):
        raise ValueError("Only the frozen 2023 Train population")
    strong_scenes, equal_to20 = qc_strong_scenes(
        csv.DictReader(io.StringIO(qc.decode("utf-8-sig"))), scene_ids
    )
    epochs = []
    for epoch in range(1, EPOCHS + 1):
        supplied = orders[str(epoch)]
        order = supplied["ids"]
        receipt = json.loads((run / f"B7_train_{epoch:02}.json").read_bytes())
        order_sha = sha256(json.dumps(order, separators=(",", ":")).encode()).hexdigest()
        if set(order) != scene_ids or order_sha != supplied["sha256"] or order_sha != receipt["train_order_sha256"]:
            raise ValueError("Training order differs from the sealed receipt")
        if (receipt["loss_arm"], receipt["scenes"], receipt["batches"], receipt["updates"],
            receipt["n_valid"], receipt["n_rain"], receipt["n_strong"]) != (
                "A20-BISIDE-V1", SCENES, 480, epoch * 480, SCENES * VALID_PER_SCENE, RAIN_PER_EPOCH, STRONG_PER_EPOCH
            ):
            raise ValueError("Training receipt differs from the fixed A20 run")
        epochs.append(dict(epoch=epoch, **count_epoch(order, strong_scenes, STRONG_PER_EPOCH)))
    totals = {field: sum(row[field] for row in epochs) for field in (
        "batches", "skipped_batches", "negative_exposures", "skipped_negative_exposures"
    )}
    return dict(
        protocol="A20_LABEL_COVERAGE_V1", status="COMPLETE_FROM_EXISTING_METADATA",
        training_proposal_sha256=proposal["proposal_sha256"], order_file_sha256=ORDERS_SHA256,
        target_qc_sha256=qc_sha, strong_scenes=len(strong_scenes), scenes_max_equal_to20=equal_to20,
        strong_pixels_per_epoch=STRONG_PER_EPOCH, epochs=epochs, totals=totals,
        real_label_opens=0, model_loads=0, optimizer_updates=0, final_2025_access=False,
        scientific_status="NOT_VERIFIED",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path, help="Directory of the sealed A20 train metadata")
    args = parser.parse_args()
    print(json.dumps(reconstruct(args.run), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
