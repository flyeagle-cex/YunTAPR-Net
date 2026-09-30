"""One B0 engineering-only CUDA forward/backward; no optimizer or training loop."""

import json
from pathlib import Path
import sys
import time
import traceback


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
MASK = Path(
    r"F:\pytorch\Research\outputs\stage0_spatial_decision_update"
    r"\run_20260928T102636_513428Z\FROZEN\MASK"
    r"\yunnan_evaluation_mask_center_gadm41_imerg_v1.nc"
)


def main() -> int:
    result = {
        "status": "FAIL",
        "scope": "ENGINEERING_ONLY",
        "B0_CUDA_SYNTHETIC_FORWARD_BACKWARD": "FAIL",
        "optimizer_created": False,
        "optimizer_step_performed": False,
        "formal_training_started": False,
        "error": None,
    }
    start = time.perf_counter()
    try:
        import torch
        from yuntapr.contracts.loader import load_contract, sha256
        from yuntapr.data.masks import read_frozen_yunnan_mask
        from yuntapr.losses.total_loss import b0_core_loss
        from yuntapr.models.b0 import B0Model
        from yuntapr.spatial.sp04_mapping import load_sp04

        science, engineering = load_contract()
        assert science["schema_version"] == "1.1"
        assert engineering["schema_version"] == 4
        assert torch.cuda.is_available()
        torch.manual_seed(20260930)
        mapping = load_sp04()
        yunnan = read_frozen_yunnan_mask(MASK, mapping)
        assert yunnan.shape == (100, 100) and int(yunnan.sum()) == 3430

        device = torch.device("cuda:0")
        model = B0Model().to(device).eval()
        x = torch.randn((1, 1, 501, 501), dtype=torch.float32, device=device)
        b13_valid = torch.ones_like(x, dtype=torch.bool)
        eval_mask = torch.from_numpy(yunnan[None, None].copy()).to(device)
        y = eval_mask.to(torch.float32)  # synthetic 1 mm/h inside Yunnan only
        y_valid = torch.ones_like(eval_mask, dtype=torch.bool)

        output = model(x, b13_valid)
        loss = b0_core_loss(
            output,
            y,
            y_valid,
            eval_mask,
            focal_alpha=0.25,
            focal_gamma=2.0,
            quantile_axis_reduction=engineering["loss"]["quantile_axis_reduction"],
        )
        loss.total.backward()
        torch.cuda.synchronize(device)

        parameters = list(model.parameters())
        checks = {
            "input_shape": list(x.shape) == [1, 1, 501, 501],
            "rain_logit_shape": list(output.rain_logit.shape) == [1, 1, 100, 100],
            "quantile_shape": list(output.conditional_quantiles_log.shape)
            == [1, 32, 100, 100],
            "backbone_params_float32": all(
                p.dtype == torch.float32 for p in model.backbone.parameters()
            ),
            "head_params_float32": all(
                p.dtype == torch.float32 for p in model.heads.parameters()
            ),
            "qlog_float64": output.conditional_quantiles_log.dtype == torch.float64,
            "qphysical_float64": output.conditional_quantiles_physical.dtype
            == torch.float64,
            "loss_finite": bool(torch.isfinite(loss.total)),
            "outputs_finite": bool(
                torch.isfinite(output.rain_logit).all()
                and torch.isfinite(output.conditional_quantiles_log).all()
                and torch.isfinite(output.conditional_quantiles_physical).all()
            ),
            "gradients_finite": all(
                p.grad is not None and bool(torch.isfinite(p.grad).all())
                for p in parameters
            ),
            "yunnan_true_cells": int(yunnan.sum()) == 3430,
            "supervised_yunnan_cells": loss.valid_supervised_count == 3430,
        }
        result.update(
            science_version=science["schema_version"],
            engineering_version=engineering["schema_version"],
            python_path=sys.executable,
            torch_version=torch.__version__,
            device=str(device),
            mask_path=str(MASK),
            mask_sha256=sha256(MASK),
            input_description="normalized_synthetic_float32_full_valid_B13",
            focal_parameters="ENGINEERING_TEST_ONLY: alpha=0.25, gamma=2.0",
            checks=checks,
            loss_value=float(loss.total.detach().cpu()),
            elapsed_seconds=round(time.perf_counter() - start, 3),
        )
        if not all(checks.values()):
            raise AssertionError("B0 CUDA synthetic contract check failed")
        result["status"] = "PASS"
        result["B0_CUDA_SYNTHETIC_FORWARD_BACKWARD"] = "PASS"
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["traceback"] = traceback.format_exc()
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
