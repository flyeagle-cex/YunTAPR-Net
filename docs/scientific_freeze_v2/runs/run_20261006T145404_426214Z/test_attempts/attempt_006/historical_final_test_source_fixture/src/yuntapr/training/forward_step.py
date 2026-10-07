"""One engineering-only forward/loss evaluation; does not update parameters."""
from yuntapr.losses.total_loss import b0_core_loss
from yuntapr.training.batch_contract import B0Batch


def engineering_forward_step(model, batch: B0Batch, *, focal_alpha: float | None = None,
                             focal_gamma: float | None = None, quantile_axis_reduction: str):
    batch.validate()
    output = model(batch.x_b13, batch.b13_valid_mask)
    if batch.y_imerg is None:
        return output, None
    losses = b0_core_loss(output, batch.y_imerg, batch.imerg_valid_mask, batch.yunnan_eval_mask,
                          focal_alpha=focal_alpha, focal_gamma=focal_gamma,
                          quantile_axis_reduction=quantile_axis_reduction)
    return output, losses


def formal_rules_engineering_forward_step(model, batch: B0Batch, *, focal_alpha: float,
                                          focal_gamma: float, quantile_axis_reduction: str):
    """Validate formal sample rules with development-only forward/backward; no fit loop."""
    batch.validate_formal()
    output = model.forward_formal(batch)
    losses = b0_core_loss(output, batch.y_imerg, batch.imerg_valid_mask, batch.yunnan_eval_mask,
                         focal_alpha=focal_alpha, focal_gamma=focal_gamma,
                         quantile_axis_reduction=quantile_axis_reduction)
    return output, losses
