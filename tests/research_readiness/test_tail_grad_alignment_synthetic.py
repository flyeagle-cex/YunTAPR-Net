"""Check local gradient directions using the unchanged loss and quantile parameterization."""

import math
import unittest

import torch

from yuntapr.experimental.phase_b_v2_ablations.pinball import conditional_pinball_numerator
from yuntapr.models.quantile_v2.outputs import LogDomainOutput, materialize_physical
from yuntapr.models.quantile_v2.parameterization import CandidateNumerics, normalized_monotonic_quantiles


NUMERICS = CandidateNumerics(1e-4, 1e-4)


def outputs(allocation, span, truth):
    nodes = normalized_monotonic_quantiles(allocation, span, numerics=NUMERICS)
    target = torch.full_like(span, math.log1p(truth))
    logit = torch.full_like(span, math.log(3), dtype=torch.float32)
    loss = conditional_pinball_numerator(nodes, target, torch.ones_like(target, dtype=torch.bool))
    point = materialize_physical(LogDomainOutput(logit, logit.sigmoid(), nodes)).threshold_censored_mean
    return nodes, loss, point


def measure(nodes_mm_h, truth):
    desired = torch.log1p(nodes_mm_h).reshape(1, 32, 1, 1)
    support = torch.full_like(desired[:, :1], math.log1p(.1))
    increments = torch.diff(desired, dim=1, prepend=support)
    # Choose logits that realize the desired strictly ordered nodes with the production head.
    allocation = torch.log(torch.expm1(increments - NUMERICS.epsilon_w))
    span = torch.log(torch.expm1(desired[:, -1:] - support - NUMERICS.epsilon_span))
    span.requires_grad_()
    nodes, loss, point = outputs(allocation, span, truth)
    loss_nodes, loss_span = torch.autograd.grad(loss, (nodes, span), retain_graph=True)
    point_nodes, point_span = torch.autograd.grad(point, (nodes, span))
    with torch.no_grad():
        shifted_span = span - .05 * loss_span.sign()
        _, shifted_loss, shifted_point = outputs(allocation, shifted_span, truth)
    return dict(
        nodes=nodes.detach(), loss_nodes=loss_nodes, point_nodes=point_nodes,
        loss_span=loss_span.item(), point_span=point_span.item(),
        loss_before=loss.item(), loss_after=shifted_loss.item(),
        point_before=point.float().item(), point_after=shifted_point.float().item(),
    )


def synthetic_cases():
    low_nodes = torch.linspace(8, 20, 32, dtype=torch.float64)
    mixed_nodes = torch.cat((
        torch.linspace(8, 20, 16, dtype=torch.float64),
        torch.linspace(30, 50, 16, dtype=torch.float64),
    ))
    return {
        "underpredicted_strong": measure(low_nodes, 25.),
        "mixed_strong": measure(mixed_nodes, 25.),
        "weak_rain": measure(low_nodes, .5),
    }


class TailGradientAlignmentTests(unittest.TestCase):
    def test_original_loss_and_point_gradient_directions(self):
        results = synthetic_cases()
        taus = (torch.arange(32, dtype=torch.float64).reshape(1, 32, 1, 1) + .5) / 32
        for case, truth in (("underpredicted_strong", 25.), ("mixed_strong", 25.), ("weak_rain", .5)):
            with self.subTest(case=case):
                row = results[case]
                expected_loss_gradient = torch.where(
                    row["nodes"] < math.log1p(truth), -taus, 1 - taus,
                ) / 32
                torch.testing.assert_close(row["loss_nodes"], expected_loss_gradient)
                torch.testing.assert_close(row["point_nodes"], .75 * row["nodes"].exp() / 32)

    def test_strong_gradient_conflict_through_the_actual_span(self):
        results = synthetic_cases()
        for row in results.values():
            self.assertLess(row["loss_after"], row["loss_before"])
            self.assertGreater(row["point_span"], 0)
        under = results["underpredicted_strong"]
        self.assertLess(under["loss_span"], 0)
        self.assertGreater(under["point_after"], under["point_before"])
        mixed = results["mixed_strong"]
        self.assertGreater(mixed["loss_span"], 0)
        self.assertLessEqual(mixed["point_after"], 20)
        self.assertGreater(mixed["point_before"], 20)
        weak = results["weak_rain"]
        self.assertGreater(weak["loss_span"], 0)
        self.assertLess(weak["point_after"], weak["point_before"])


if __name__ == "__main__":
    unittest.main()
