"""Full development-pass receipt and frozen FP64 global accumulation."""
from __future__ import annotations
from yuntapr.training.phase_a_validation_v2 import LogDomainValidation
from .data import Coverage, Batch, ROLES
from . import SCOPE


class StreamingValidation:
    def __init__(self, expected_ids: tuple[str, ...]):
        self.coverage = Coverage(expected_ids)
        self.accumulator = LogDomainValidation()

    def add(self, output, batch: Batch):
        if batch.role != ROLES[1]:
            raise ValueError("Validation input must have separate development role")
        self.coverage.add(batch.ids)
        self.accumulator.add(output, batch.rate, batch.reference_valid, batch.region_mask)

    def finish(self) -> dict:
        coverage = self.coverage.finish()
        report = self.accumulator.report()
        if report["scenes"] != len(self.coverage.expected) or report["N_valid"] != 3430 * len(self.coverage.expected):
            raise ValueError("Incomplete/global validation denominator")
        return {"scope": SCOPE, "scientific_performance_evidence": False, "coverage": coverage, **report,
                "conditional_pinball_synthetic": report["S_qr"] / report["N_rain"] if report["N_rain"] else None,
                "common_occurrence_gamma": 2, "lambda_in_common_metric": False}

