"""Read-only regional reductions before the unchanged physical transform."""
import math
import torch
from quantile_autopsy_v1.observer import Observer as PreviousObserver
from mask_partitioned_replay_v1 import common as c


@torch.no_grad()
def partition_statistics(qlog, mask, sample_ids, *, require_frozen_count=True):
    if qlog.shape != (len(sample_ids), 32, 100, 100) or qlog.dtype != torch.float64:
        raise ValueError("Expected native qlog [B,32,100,100] FP64")
    mask = mask.detach().to(device="cpu")
    if mask.shape != (100, 100) or mask.dtype != torch.bool:
        raise ValueError("Frozen bool mask must be 100x100; no transpose/flip")
    if require_frozen_count and int(mask.sum()) != 3430:
        raise ValueError("Frozen Yunnan count changed")
    # Detached CPU copy. Nothing is written back to qlog, raw outputs or model.
    values = qlog.detach().to(device="cpu")
    if not bool(torch.isfinite(values).all()):
        raise ValueError("Diagnostic replay expects the prior finite qlog trajectory")
    result = {}
    for name, region_mask in (("YUNNAN_INSIDE", mask), ("YUNNAN_OUTSIDE", ~mask)):
        positions = torch.nonzero(region_mask.flatten(), as_tuple=False).flatten()
        n = positions.numel()
        if n == 0:
            raise ValueError("Empty diagnostic mask partition")
        region = values[:, :, region_mask]
        flat = int(region.argmax())
        pixel = flat % n; flat //= n
        tau = flat % 32; batch_index = flat // 32
        native_pixel = int(positions[pixel])
        maximum = float(region.max())
        location = {"sample_id": sample_ids[batch_index], "batch_index": batch_index,
                    "tau_index_zero_based": tau, "tau_ordinal": tau + 1, "tau": (tau + .5) / 32,
                    "row": native_pixel // 100, "column": native_pixel % 100, "qlog_value": maximum}
        thresholds = []
        for rate in c.RATES:
            exceeded = region > math.log1p(rate)
            thresholds.append({"physical_threshold_mm_h": rate, "qlog_threshold": math.log1p(rate),
                "scene_pixel_tau_exposure": int(exceeded.sum()),
                "scene_pixel_any_tau_exposure": int(exceeded.any(dim=1).sum()),
                "per_tau_scene_pixel_exposure": exceeded.sum(dim=(0, 2)).tolist()})
        overflow = region > c.FP64_BOUNDARY
        result[name] = {"global_qlog_max": maximum, "global_qlog_min": float(region.min()),
            "per_tau_qlog_max": region.amax(dim=(0, 2)).tolist(),
            "per_tau_qlog_median": region.permute(1, 0, 2).reshape(32, -1).median(dim=1).values.tolist(),
            "argmax": location, "cells_per_scene": n, "scene_exposures": len(sample_ids),
            "scene_pixel_exposures": len(sample_ids) * n,
            "scene_pixel_tau_exposures": len(sample_ids) * n * 32,
            "threshold_exceedance_counts": thresholds,
            "FP64_PHYSICAL_OVERFLOW_RISK_OBSERVED": maximum > c.FP64_BOUNDARY,
            "fp64_boundary_scene_pixel_tau_exposure": int(overflow.sum()),
            "fp64_boundary_scene_pixel_any_tau_exposure": int(overflow.any(dim=1).sum())}
    return result


class Observer(PreviousObserver):
    def __init__(self, model, frozen_mask):
        super().__init__(model)
        self.frozen_mask = frozen_mask.detach().cpu().clone()
        if self.frozen_mask.shape != (100, 100) or int(self.frozen_mask.sum()) != 3430:
            raise ValueError("Frozen target mask identity/count required")

    def begin(self, *args, **kwargs):
        super().begin(*args, **kwargs)
        self.current["scope"] = c.SCOPE

    @torch.no_grad()
    def see_qlog(self, qlog):
        if self.raw is None or self.features is None or self.logit is None or self.batch is None:
            raise RuntimeError("Observation ordering failed")
        actual_mask = self.batch.yunnan_eval_mask.detach().cpu()
        if actual_mask.shape != (len(self.batch.sample_ids), 1, 100, 100):
            raise ValueError("Batch evaluation mask shape changed")
        if not torch.equal(actual_mask, self.frozen_mask.expand_as(actual_mask)):
            raise ValueError("Batch mask differs from frozen Yunnan mask")
        parts = partition_statistics(qlog, self.frozen_mask, self.batch.sample_ids)
        self.current["mask_partitioned"] = parts
        self.current["qlog_per_tau_max"] = [max(parts[r]["per_tau_qlog_max"][t] for r in c.REGIONS) for t in range(32)]
        self.current["captured_before_expm1"] = True
        maximum = max(v["global_qlog_max"] for v in parts.values())
        self.current["qlog"] = {"min": min(v["global_qlog_min"] for v in parts.values()),
                                "max": maximum, "all_finite": True, "dtype": str(qlog.dtype)}
        if maximum > c.FP64_BOUNDARY:
            identities = [{"sample_id": item["sample_id"], "index": item["index"],
                           "frames": item["frames"], "imerg_sha256": item["target_sha256"],
                           "normalization_sha256": item["normalization_sha256"]} for item in self.items]
            inside, outside = parts["YUNNAN_INSIDE"], parts["YUNNAN_OUTSIDE"]
            self.failure = {"scope": c.SCOPE, "update": self.current["update"],
                "captured_before_expm1": True, "qlog_max": maximum,
                "sample_identities": identities, "qlog_all_finite": True,
                "inside_max_qlog": inside["global_qlog_max"], "inside_max_location": inside["argmax"],
                "outside_max_qlog": outside["global_qlog_max"], "outside_max_location": outside["argmax"],
                "inside_any_qlog_above_fp64_boundary": inside["FP64_PHYSICAL_OVERFLOW_RISK_OBSERVED"],
                "outside_any_qlog_above_fp64_boundary": outside["FP64_PHYSICAL_OVERFLOW_RISK_OBSERVED"],
                "FP64_PHYSICAL_BOUNDARY": c.FP64_BOUNDARY, "mask_partitioned": parts}
        # PreviousObserver.installed still delegates to original torch.expm1
        # exactly once, with this same qlog; no replacement output or bypass.
