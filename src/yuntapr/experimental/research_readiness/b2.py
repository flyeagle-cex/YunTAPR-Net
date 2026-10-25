"""B2 candidate paired with the unchanged seed2029 B3 initializer.

The input-stem rule is a proposal requiring researcher approval. It is not a
new frozen scientific decision. Historical B3/B4 modules are left unchanged.
"""
import math
import torch
from yuntapr.contracts.loader import REPO_ROOT
from yuntapr.models.quantile_v2.parameterization import CandidateNumerics
from yuntapr.training.phase_a_protocol import state_digest
from yuntapr.experimental.core_innovation.stage2 import CHANNELS, OFFSETS
from yuntapr.experimental.core_innovation.stage2.models import SpectralCandidate
from yuntapr.experimental.core_innovation.stage4.engine import paired_models
from yuntapr.experimental.core_innovation.stage4 import POPULATION_SHA
from yuntapr.experimental.phase_b_v2_ablations.total import candidate_loss
from yuntapr.experimental.phase_b_v2_ablations.config import get_config

STEM_RULE = 'LATEST_SLOT_FANIN_RESCALED_SQRT6_PROPOSED'
INPUT_OFFSET_MINUTES = 10
STEM_WEIGHTS = ('backbone.enc0.conv1.weight', 'backbone.enc0.skip.weight')


def latest_frame(x, valid):
    if (x.ndim != 4 or x.shape[1:] != (42, 501, 501)
            or valid.shape != x.shape or valid.dtype != torch.bool
            or valid.device != x.device):
        raise ValueError('Frozen six-frame time-major batch and bool masks required')
    # Eligibility remains the historical six-frame, seven-band joint population.
    # Reject a bad earlier frame too; do not silently enlarge B2 membership.
    if not bool(valid.all()) or not bool(torch.isfinite(x).all()):
        raise ValueError('Joint full-valid population required, including unused frames')
    slot = OFFSETS.index(INPUT_OFFSET_MINUTES)
    return x[:, slot * len(CHANNELS):(slot + 1) * len(CHANNELS)], valid[:, slot * len(CHANNELS):(slot + 1) * len(CHANNELS)]


def initialize_b2(reference_b3, *, stem_rule, root=REPO_ROOT):
    if stem_rule != STEM_RULE or reference_b3.kind != 'B3':
        raise ValueError('Explicit reviewed input-stem rule and fresh B3 reference required')
    # Keep the reference RNG state intact; all B2 tensors are explicitly assigned.
    with torch.random.fork_rng(devices=[]):
        b2 = SpectralCandidate('B2', numerics=CandidateNumerics(1e-4, 1e-4), root=root)
    source = reference_b3.state_dict()
    target = b2.state_dict()
    if target.keys() != source.keys():
        raise ValueError('Unexpected reference state schema')
    slot = OFFSETS.index(INPUT_OFFSET_MINUTES)
    for name in target:
        if name in STEM_WEIGHTS:
            # Fan-in correction: Kaiming variance for 7 versus 42 input channels.
            value = source[name][:, slot*7:(slot+1)*7].clone() * math.sqrt(6.)
        else:
            value = source[name].clone()
        if value.shape != target[name].shape:
            raise ValueError('Unreviewed shape difference: ' + name)
        target[name] = value
    b2.load_state_dict(target, strict=True)
    shared = {k: v for k, v in target.items() if k not in STEM_WEIGHTS}
    if not all(torch.equal(v, source[k]) for k, v in shared.items()):
        raise AssertionError('Shape-compatible initialization differs')
    evidence = dict(stem_rule=stem_rule, decision_status='PROPOSED_REQUIRES_RESEARCHER_APPROVAL',
                    b3_reference_sha256=state_digest(source),
                    b2_initial_sha256=state_digest(target),
                    compatible_state_sha256=state_digest(shared),
                    compatible_tensors=len(shared),
                    differing_input_kernels={k: dict(B2=list(target[k].shape), B3=list(source[k].shape)) for k in STEM_WEIGHTS},
                    selected_slot=slot, offset_before_analysis_minutes=INPUT_OFFSET_MINUTES,
                    new_formal_optimizer_updates=0)
    return b2, evidence


def fresh_b2(seed, *, stem_rule, root=REPO_ROOT):
    # Reproduce the original B3-first constructor sequence, not a trained weight.
    models = paired_models(seed, root)
    b2, evidence = initialize_b2(models['B3'], stem_rule=stem_rule, root=root)
    del models
    return b2, evidence


def forward_b2(model, batch):
    if model.kind != 'B2' or batch.identity['population_sha256'] != POPULATION_SHA:
        raise ValueError('Wrong model or population')
    x, mask = latest_frame(batch.x, batch.native_valid)
    out = model(x, mask, channel_order=CHANNELS)
    loss = candidate_loss(out.rain_logit, out.conditional_quantiles_log, batch.rate,
                          batch.valid, batch.region, config=get_config('E0'))
    if loss.n_valid != len(batch.ids)*3430:
        raise ValueError('Frozen supervision denominator differs')
    return out, loss
