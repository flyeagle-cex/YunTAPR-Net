"""Array-only strict/inclusive tail envelopes, reusing the existing strict API.

The frozen head defines p=P(R>0.1) and conditional quantiles of R|R>0.1.
It does not identify a complete CDF or physical tail. This interface assumes
only the supplied quantile constraints and their strictly-positive-rain
support; it never interpolates nodes, extrapolates a tail, or reads data.

At r=0.1, the nonrain component matters for >=: callers must explicitly
declare either delta_0 or unknown mass on [0,0.1]. This is a caller assertion,
not a new frozen model definition or a conclusion from the occurrence label.
The threshold-censored mean proxy alone is not evidence of a physical delta_0.
"""
from dataclasses import dataclass
import math

import numpy as np

from tools.research_readiness.extreme_diagnostic_candidates import (
    Bounds, decision_identification, exceedance_bounds,
)


METHOD_STATUS = "CANDIDATE_PARTIAL_IDENTIFICATION_NO_CDF_COMPLETION"
DELTA_AT_ZERO = "DELTA_AT_ZERO"
UNKNOWN_NONRAIN = "NOT_IDENTIFIED_ON_CLOSED_0_TO_0_1"


@dataclass(frozen=True)
class TailIdentifiability:
    strict_exceedance: Bounds
    inclusive_exceedance: Bounds
    cdf_right_limit: Bounds
    cdf_left_limit: Bounds
    threshold_mass: Bounds
    strict_probability_identified: np.ndarray
    inclusive_probability_identified: np.ndarray
    threshold_mass_identified: np.ndarray
    strict_decision: dict | None
    inclusive_decision: dict | None
    nonrain_component: str
    method_status: str = METHOD_STATUS
    envelope_scope: str = "CONSERVATIVE_CLOSED_NOT_ENDPOINT_ATTAINABILITY"
    conditional_support: str = "R_GIVEN_R_STRICTLY_GREATER_THAN_0_1"
    evidence_scope: str = "CALLER_ARRAYS_NOT_PAYLOAD_OR_CALIBRATION_VERIFIED"


def threshold_identifiability(probability, quantiles_log, threshold_mm_h, *,
                              nonrain_component, probability_cutoff=None):
    """Return envelopes for >, >=, F(r), F(r-) and mass at r.

    For r>0.1, quantiles q_i<log1p(r) bound F_+(r-) from below;
    q_i>=log1p(r) bound it from above. In contrast, the inherited strict
    exceedance implementation uses q_i<=log1p(r) for F_+(r)'s lower bound.
    These distinct comparisons permit discrete atoms at a threshold. Node
    equality never silently assumes a continuous distribution.

    Supplied nodes must satisfy the inherited [N,32], finite, ordered support
    checks even when p=0. No source sorting, clipping, repair or row deletion
    occurs. The module reuses repository tools and is not a standalone loader.
    """
    if nonrain_component not in (DELTA_AT_ZERO, UNKNOWN_NONRAIN):
        raise ValueError("Explicit delta_0 or unspecified [0,0.1] nonrain component required")
    strict = exceedance_bounds(probability, quantiles_log, threshold_mm_h)
    p = np.asarray(probability, dtype=np.float64)
    q = np.asarray(quantiles_log, dtype=np.float64)
    at_occurrence = threshold_mm_h == .1
    if at_occurrence:
        # Conditional support is strictly above .1. The remaining mass is at
        # zero only when the caller explicitly binds that particular model.
        inclusive = Bounds(p.copy(), p.copy() if nonrain_component == DELTA_AT_ZERO
                           else np.ones_like(p))
        strict_identified = np.ones_like(p, dtype=bool)
        inclusive_identified = (np.ones_like(p, dtype=bool)
                                if nonrain_component == DELTA_AT_ZERO else p == 1)
    else:
        tau = (np.arange(32, dtype=np.float64) + .5) / 32
        z = math.log1p(threshold_mm_h)
        f_left_lower = np.max(np.where(q < z, tau, 0.), axis=1)
        f_left_upper = np.min(np.where(q >= z, tau, 1.), axis=1)
        inclusive = Bounds(p * (1 - f_left_upper), p * (1 - f_left_lower))
        strict_identified = p == 0
        inclusive_identified = p == 0
        # With 32 finite nodes the enclosing probability intervals have
        # positive mathematical width for p>0. Do not call underflow a proof
        # of point identification or use a falsely collapsed decision bound.
        if np.any((p > 0) & ((strict.upper <= strict.lower)
                             | (inclusive.upper <= inclusive.lower))):
            raise FloatingPointError("Tail envelope lost numerical width; no repair")
    cdf_right = Bounds(1 - strict.upper, 1 - strict.lower)
    cdf_left = Bounds(1 - inclusive.upper, 1 - inclusive.lower)
    # Interval subtraction is conservative; joint sharpness or endpoint
    # attainment is not asserted. Zero is the universal lower bound here.
    mass = Bounds(np.zeros_like(p), inclusive.upper - strict.lower)
    mass_identified = (inclusive_identified if at_occurrence else p == 0)
    if (np.any(mass.upper < 0) or np.any(mass.upper > 1)
            or not np.isfinite(mass.upper).all()):
        raise FloatingPointError("Invalid threshold-mass envelope; no repair")
    strict_decision = inclusive_decision = None
    if probability_cutoff is not None:
        strict_decision = decision_identification(strict.lower, strict.upper, probability_cutoff)
        inclusive_decision = decision_identification(inclusive.lower, inclusive.upper, probability_cutoff)
    return TailIdentifiability(
        strict, inclusive, cdf_right, cdf_left, mass,
        strict_identified, inclusive_identified, mass_identified,
        strict_decision, inclusive_decision, nonrain_component,
    )
