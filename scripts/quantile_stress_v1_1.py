"""Measure float32 epsilon recurrence and its explicit precision guard, without repair."""
import argparse
import json
import math
from pathlib import Path
import torch
from torch.nn import functional as F
from yuntapr.contracts.loader import load_contract
from yuntapr.models.monotonic_quantiles import monotonic_quantiles


def probe(name, values, epsilon):
    raw = values.detach().clone().float().requires_grad_(True)
    deltas = F.softplus(raw) + epsilon
    parts = [math.log1p(.1) + deltas[:, :1]]
    for i in range(1, 32):
        parts.append(parts[-1] + deltas[:, i:i+1])
    measured = torch.cat(parts, 1)
    measured.mean().backward()
    row = {"case": name, "dtype": str(raw.dtype), "shape": list(raw.shape),
           "finite": bool(torch.isfinite(measured).all()),
           "strictly_increasing": bool((measured[:, 1:] > measured[:, :-1]).all()),
           "support_above_threshold": bool((measured[:, :1] > math.log1p(.1)).all()),
           "adjacent_equal_count": int((measured[:, 1:] == measured[:, :-1]).sum()),
           "gradient_finite": bool(torch.isfinite(raw.grad).all()),
           "min_adjacent_delta": float((measured[:, 1:]-measured[:, :-1]).min().detach()),
           "max_q_log": float(measured.max().detach())}
    try:
        checked = monotonic_quantiles(raw, .1, epsilon_mono=epsilon)
        if not torch.equal(checked.detach(), measured.detach()):
            raise AssertionError("Runtime differs from specified sequential recurrence")
        row["runtime_status"] = "PASS"
    except FloatingPointError as error:
        row["runtime_status"] = "FAIL_LOUDLY"
        row["runtime_error"] = str(error)
    return row


def stress():
    _, config = load_contract()
    eps = config["quantile_numerics"]["epsilon_mono"]
    torch.set_num_threads(2)
    gen = torch.Generator().manual_seed(20260930)
    cases = [(f"constant_{x}", torch.full((1,32,4,4), float(x))) for x in (-100,-80,-40,-20,-10,0,10,40,80,100)]
    cases.extend([("random_uniform_minus100_plus100", torch.rand((8,32,32,32), generator=gen)*200-100),
                  ("random_normal_sigma100", torch.randn((8,32,32,32), generator=gen)*100),
                  ("random_signed_100", torch.randint(0,2,(8,32,32,32), generator=gen)*200.-100.)])
    adversarial = torch.full((1,32,1,1), -100.)
    adversarial[:, :22] = 100.
    cases.append(("mixed_22_positive100_then_10_negative100", adversarial))
    rows = [probe(n, r, eps) for n, r in cases]
    return {"epsilon_mono": eps, "domain": "log1p(mm h^-1)", "status": "ENGINEERING_CONFIG",
            "recurrence": "q1=log1p(0.1)+softplus(raw1)+eps; qi=qprev+softplus(rawi)+eps",
            "random_seed": 20260930, "cases": rows,
            "QUANTILE_NUMERICAL_STABILITY_CLOSED": all(r["runtime_status"] == "PASS" and r["gradient_finite"] for r in rows),
            "guards_fail_loudly_on_every_lost_ordering": all(r["runtime_status"] == "FAIL_LOUDLY" for r in rows if not r["strictly_increasing"]),
            "explanation": "At q around 2200, float32 ULP is 0.000244140625; adding 0.0001 can round back to q. This specified epsilon cannot guarantee all mixed extreme tensors. Runtime raises; no sort/clamp/dtype/epsilon change was made.",
            "physical_domain_note": "This stress validates the specified log domain. expm1 of very large positive quantiles can overflow float32 independently; the probability head retains its explicit physical-finiteness error.",
            "RESEARCHER_DECISION_REQUIRED": "Review a precision strategy or approved bounded raw domain before claiming universal numerical closure; no automatic scientific or engineering parameter change.",
            "formal_training_started": False}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = stress()
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"closed": result["QUANTILE_NUMERICAL_STABILITY_CLOSED"], "cases": [(x["case"], x["runtime_status"], x["adjacent_equal_count"]) for x in result["cases"]]}))
