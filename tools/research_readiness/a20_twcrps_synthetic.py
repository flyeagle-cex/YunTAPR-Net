"""Run one fixed synthetic E0 versus E0 + threshold-weighted CRPS comparison."""

import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

import torch
from torch import nn
from torch.nn import functional as F

from tools.research_readiness.point_rank_readout import rank_scores
from yuntapr.experimental.phase_b_v2_ablations.config import get_config
from yuntapr.experimental.phase_b_v2_ablations.schedule import COSINE9, scheduled_lr
from yuntapr.experimental.phase_b_v2_ablations.total import candidate_loss
from yuntapr.experimental.phase_b_v2_runner_candidate.optimizer import clip_and_check, new_adamw
from yuntapr.models.quantile_v2.heads import ProbabilityHeadsV2
from yuntapr.models.quantile_v2.parameterization import CandidateNumerics


SEED = 2029
UPDATES = 144
STRIDE = 30
WEIGHT = 1.0
TOLERANCE = 1e-8
# Name, count, initial rain probability, first and last physical quantiles,
# optional isolated q32, and lower/upper bounds of the deterministic label fixture.
GROUPS = (
    ("dry", 128, .12, .25, 2., None, 0., 0.),
    ("low_p_high_q32", 48, .01, .3, 3., 40., 0., 0.),
    ("weak", 64, .8, .28, .8, None, .50, .58),
    ("near_nonstrong", 24, .85, 21., 25., None, 16., 19.),
    ("strong_low", 12, .8, 12., 19.5, None, 27., 32.),
    ("strong_near", 12, .9, 20., 24., None, 26., 30.),
)
MIN_Q32_DROP = .02
MIN_STRONG_A_GAIN = .02
MIN_PHYSICAL_PINBALL_GAIN = 1e-5


def transform(x):
    """g' rises smoothly from 0.25/20 to 1.25/20 at the upper tail."""
    return (.25 * x + 5 * F.softplus((x - 20) / 5)) / 20


def mixture(p, q, y):
    atoms = transform(torch.cat((torch.zeros_like(p[:, None]), q), dim=1))
    weights = torch.cat(((1 - p)[:, None], (p / 32)[:, None].expand(-1, 32)), dim=1)
    return atoms, weights, transform(y)[:, None]


def score(p, q, y):
    atoms, weights, observed = mixture(p, q, y)
    prefix = weights.cumsum(dim=1) - weights
    distance = (weights * (atoms - observed).abs()).sum(dim=1)
    half_pair_distance = (weights * atoms * (2 * prefix + weights - 1)).sum(dim=1)
    return distance - half_pair_distance


def auxiliary(output, rate, valid, region):
    selected = (valid & region)[:, 0]
    with torch.autocast(rate.device.type, enabled=False):
        p = output.rain_prob[:, 0][selected].double()
        q = torch.expm1(output.conditional_quantiles_log.movedim(1, -1)[selected])
        truth = rate[:, 0][selected]
        truth = torch.where(truth > .1, truth, torch.zeros_like(truth)).double()
        result = score(p, q, truth).mean()
    if (not bool(torch.isfinite(result)) or not bool(torch.isfinite(q).all())
            or not bool(((0 <= p) & (p <= 1)).all())):
        raise FloatingPointError("Nonfinite or out-of-range mixed-distribution input")
    return result


class FixtureModel(nn.Module):
    """Shared 1x1 feature layer with the project's unmodified dual heads."""

    def __init__(self):
        super().__init__()
        self.shared = nn.Conv2d(48, 48, 1)
        self.heads = ProbabilityHeadsV2(numerics=CandidateNumerics(1e-4, 1e-4))
        with torch.no_grad():
            for param in self.parameters():
                param.zero_()
            for index, (_, _, probability, lower, upper, isolated, _, _) in enumerate(GROUPS):
                q = torch.linspace(lower, upper, 32 - (isolated is not None), dtype=torch.float64)
                if isolated is not None:
                    q = torch.cat((q, q.new_tensor([isolated])))
                log_nodes = q.log1p() - math.log1p(.1)
                allocation = torch.diff(log_nodes, prepend=log_nodes.new_zeros(1))
                self.heads.occurrence.weight[0, index, 0, 0] = math.log(probability / (1 - probability))
                self.heads.quantile.weight[:32, index, 0, 0] = torch.expm1(allocation - 1e-4).log()
                self.heads.quantile.weight[32, index, 0, 0] = torch.expm1(log_nodes[-1] - 1e-4).log()

    def forward(self, x):
        return self.heads(x + .125 * self.shared(x).tanh().float())


def fixture(seed, device):
    generator = torch.Generator().manual_seed(seed)
    categories, truth = [], []
    for index, (_, count, _, _, _, _, lower, upper) in enumerate(GROUPS):
        categories.extend([index] * count)
        truth.append(lower + (upper - lower) * torch.rand(count, generator=generator))
    categories = torch.tensor(categories)
    truth = torch.cat(truth)
    order = torch.randperm(len(truth), generator=generator)
    count = len(truth)
    features = torch.zeros(48, 10_000)
    features[categories[order], torch.arange(count)] = 1
    features[8, :count] = .25
    features[9, :count] = .25 * torch.rand(count, generator=generator)
    rate = torch.full((10_000,), float("nan"))
    rate[:count] = truth[order]
    valid = torch.zeros(10_000, dtype=torch.bool)
    valid[:count + 1] = True
    region = torch.zeros_like(valid)
    region[:count] = True
    region[count + 1] = True
    return (features.view(1, 48, 100, 100).to(device), rate.view(1, 1, 100, 100).to(device),
            valid.view(1, 1, 100, 100).to(device), region.view(1, 1, 100, 100).to(device),
            categories[order].to(device))


def run_arm(model, batches, device, *, candidate, extra_loss=None):
    opt, _ = new_adamw(model)
    num_clipped = 0
    max_norm = 0.
    config = get_config("E0")
    for update in range(1, UPDATES + 1):
        features, rate, valid, region, _ = batches[(update - 1) % len(batches)]
        for group in opt.param_groups:
            group["lr"] = scheduled_lr(update * STRIDE, profile=COSINE9)
        opt.zero_grad(set_to_none=True)
        with torch.autocast(device.type, dtype=torch.bfloat16):
            output = model(features)
            base = candidate_loss(output.rain_logit, output.conditional_quantiles_log,
                                  rate, valid, region, config=config)
            loss = base.training_objective
            if candidate:
                loss = loss + WEIGHT * auxiliary(output, rate, valid, region)
            if extra_loss is not None:
                loss = loss + extra_loss(output, rate, valid, region, base.n_valid)
        loss.backward()
        evidence = clip_and_check(model)
        max_norm = max(max_norm, evidence["pre_clip_norm"])
        num_clipped += evidence["pre_clip_norm"] > 5.
        opt.step()
    return dict(updates=UPDATES, clipped_updates=num_clipped, max_gradient_norm=max_norm)


def pinball(delta):
    tau = (torch.arange(32, device=delta.device, dtype=torch.float64) + .5) / 32
    return torch.maximum(delta * tau, delta * (tau - 1)).mean()


@torch.no_grad()
def metrics(model, batch, device):
    features, rate, valid, region, category = batch
    with torch.autocast(device.type, dtype=torch.bfloat16):
        output = model(features)
    selected = (valid & region)[:, 0]
    p = output.rain_prob[:, 0][selected].double()
    qlog = output.conditional_quantiles_log.movedim(1, -1)[selected]
    q = qlog.expm1()
    y = rate[:, 0][selected].double()
    a = (p * q.mean(dim=1)).float()
    strong = y > 20
    weak = (y > .1) & (y <= 1)
    rain = y > .1
    hard = category == 1
    under = category == 4
    uses = rank_scores(p.float().cpu().numpy(), rain.cpu().numpy())
    return dict(
        strong_low_mean_a=float(a[under].double().mean()),
        low_p_negative_mean_q32=float(q[hard, -1].mean()), low_p_negative_mean_p=float(p[hard].mean()),
        strong_physical_pinball_over20=float(pinball((y[strong, None] - q[strong]) / 20)),
        weak_log_pinball=float(pinball(y[weak, None].log1p() - qlog[weak])),
        occurrence_brier=float((p - rain.double()).square().mean()),
        occurrence_ap=uses["ap20"], occurrence_auroc=uses["auroc20"],
        a_tp=int(((a > 20) & strong).sum()), a_fp=int(((a > 20) & ~strong).sum()),
        q32_tp=int(((q[:, -1] > 20) & strong).sum()), q32_fp=int(((q[:, -1] > 20) & ~strong).sum()),
        mean_twcrps=float(auxiliary(output, rate, valid, region)),
    )


def analytic_checks(device):
    p = torch.tensor([.01, .8], dtype=torch.float64, device=device, requires_grad=True)
    q = torch.stack((torch.linspace(.3, 40., 32), torch.linspace(1., 16.5, 32))).to(device, torch.float64)
    q.requires_grad_()
    y = q.new_tensor([0., 30.])
    atoms, weights, observed = mixture(p, q, y)
    full = (weights * (atoms - observed).abs()).sum(dim=1) - .5 * (
        weights[:, :, None] * weights[:, None, :] * (atoms[:, :, None] - atoms[:, None, :]).abs()
    ).sum(dim=(1, 2))
    fast = score(p, q, y)
    torch.testing.assert_close(fast, full, rtol=0, atol=1e-12)
    grads = torch.autograd.grad(fast.sum(), (p, q), retain_graph=True)
    reference = torch.autograd.grad(full.sum(), (p, q))
    for actual, expected in zip(grads, reference):
        torch.testing.assert_close(actual, expected, rtol=0, atol=1e-12)
    assert grads[1][0, -1] > 0 and grads[1][1, -1] < 0
    q_mix = torch.linspace(29., 31., 32, dtype=torch.float64, device=device)
    mixture_truth = torch.cat((q_mix.new_zeros(1), q_mix))
    truthful_weights = torch.cat((q_mix.new_tensor([.5]), q_mix.new_full((32,), .5 / 32)))
    predictions = q_mix.expand(33, 32)
    truthful = (truthful_weights * score(q_mix.new_full((33,), .5), predictions, mixture_truth)).sum()
    inflated = (truthful_weights * score(q_mix.new_full((33,), .75), predictions, mixture_truth)).sum()
    assert truthful < inflated and .5 * q_mix.mean() < 20 < .75 * q_mix.mean()
    return dict(pairwise_value_and_gradient_match=True,
                dry_high_q32_gradient=float(grads[1][0, -1]), under_strong_q32_gradient=float(grads[1][1, -1]),
                proper_mixture_a=15., inflated_mixture_a=22.5,
                truthful_twcrps=float(truthful), inflated_twcrps=float(inflated))


def compare(base, candidate):
    delta = {key: candidate[key] - value for key, value in base.items()}
    gates = dict(
        strong_low_a_gain=delta["strong_low_mean_a"] >= MIN_STRONG_A_GAIN,
        low_p_negative_q32_drop=delta["low_p_negative_mean_q32"] <= -MIN_Q32_DROP,
        strong_physical_pinball_gain=delta["strong_physical_pinball_over20"] <= -MIN_PHYSICAL_PINBALL_GAIN,
        weak_log_pinball_not_worse=delta["weak_log_pinball"] <= TOLERANCE,
        occurrence_brier_not_worse=delta["occurrence_brier"] <= TOLERANCE,
        occurrence_ap_not_worse=delta["occurrence_ap"] >= -TOLERANCE,
        occurrence_auroc_not_worse=delta["occurrence_auroc"] >= -TOLERANCE,
    )
    return delta, gates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    if args.receipt.exists():
        raise FileExistsError("Use a new result path")
    torch.set_num_threads(1)
    torch.manual_seed(SEED)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cuda.matmul.allow_tf32 = False
    device = torch.device("cuda")
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("CUDA BF16 is required for the fixed comparison")
    checks = analytic_checks(device)
    model = FixtureModel().to(device)
    control_model, candidate_model = deepcopy(model), deepcopy(model)
    train = [fixture(SEED + n, device) for n in range(4)]
    evaluation = fixture(SEED + 1000, device)
    with torch.no_grad(), torch.autocast(device.type, dtype=torch.bfloat16):
        features, rate, valid, region, _ = evaluation
        output = model(features)
        masked = torch.where(valid & region, rate, torch.full_like(rate, 900.))
        torch.testing.assert_close(auxiliary(output, rate, valid, region),
                                   auxiliary(output, masked, valid, region), rtol=0, atol=0)
    checks["masked_invalid_nan_excluded"] = True
    initial = metrics(model, evaluation, device)
    control_run = run_arm(control_model, train, device, candidate=False)
    candidate_run = run_arm(candidate_model, train, device, candidate=True)
    control = metrics(control_model, evaluation, device)
    candidate = metrics(candidate_model, evaluation, device)
    delta, gates = compare(control, candidate)
    data = dict(
        status="PASS_SYNTHETIC_DIRECTION_ONLY" if all(gates.values()) else "STOP_BEFORE_REAL_TRAINING",
        scientific_status="NOT_VERIFIED", seed=SEED, synthetic_examples_per_grid=sum(row[1] for row in GROUPS),
        training_grids=4, evaluation_grids=1, loss_weight=WEIGHT, transform="(0.25*x+5*softplus((x-20)/5))/20",
        model="Shared synthetic 1x1 layer + ProbabilityHeadsV2",
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        schedule_sample_stride=STRIDE, updates_each=UPDATES, last_cosine_index=UPDATES * STRIDE,
        occurrence_precision="CUDA_BF16", quantile_precision="FP64_AFTER_FP32_CONV",
        gpu=torch.cuda.get_device_name(), torch_version=torch.__version__,
        admission_thresholds=dict(min_a_gain=MIN_STRONG_A_GAIN, min_q32_drop=MIN_Q32_DROP,
                                  min_physical_pinball_gain=MIN_PHYSICAL_PINBALL_GAIN, guard_tolerance=TOLERANCE),
        analytic_checks=checks, initial=initial, control=control, candidate=candidate,
        control_run=control_run, candidate_run=candidate_run, delta_candidate_minus_control=delta,
        synthetic_direction_gates=gates,
        real_source_payload_reads=0, real_checkpoints_loaded=0, formal_updates=0, final_2025_access=False,
    )
    with args.receipt.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps(dict(status=data["status"], delta=delta, gates=gates)))


if __name__ == "__main__":
    main()
