"""Summarize existing intervention receipts without loading data or models."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / 'docs/research_readiness'


def main():
    names = dict(e2='20261108_lambda2_recovery/RESULTS.json', uq='20261108_upper_quantile_pair/RESULTS.json',
                 cosine='20261110_cosine9/RESULTS.json', physical='20261115_physical_pinball_prepare/TERMINAL_VERIFICATION.json',
                 nodes='20261115_v7_followup/NEXT_STEP.json', mountain='20261115_mountain_pair_results/PAIRED_METRICS.json')
    sources, identities = {}, {}
    for name, relative in names.items():
        raw = (PUBLIC / relative).read_bytes()
        sources[name] = json.loads(raw)
        identities[relative] = dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    e2, uq, cosine, physical, nodes, mountain = [sources[k] for k in names]
    summary = mountain['full_population']['REAL_COSINE9']
    assert summary['n_valid'] == 3303090 and summary['n_rain'] == 407820
    assert sum(row['n'] for row in summary['rain_strata'][4:]) == 717
    assert e2['values']['B7']['E0']['conditional_pinball'] == uq['metrics'][0]['control']
    assert cosine['metrics'][0]['candidate'] == summary['conditional_pinball']
    assert physical['metrics'][0]['control'] == summary['conditional_pinball']
    strong_sum = sum(row['pinball_sum'] for row in summary['rain_strata'][4:])
    all_sum = sum(row['pinball_sum'] for row in summary['rain_strata'])
    assert abs(all_sum - summary['s_qr']) < 1e-8
    shares = dict(population='2024_DEVELOPMENT_REAL_COSINE9', n_valid=3303090, n_rain=407820, n_strong=717,
                  strong_share_of_wet_percent=100 * 717 / 407820,
                  strong_share_of_valid_percent=100 * 717 / 3303090,
                  strong_share_of_log_pinball_sum_percent=100 * strong_sum / all_sum,
                  weak_share_of_log_pinball_sum_percent=100 * summary['rain_strata'][0]['pinball_sum'] / all_sum,
                  interpretation='SAVED_DEV_LOSS_VALUES_ONLY_TRAINING_GRADIENT_CONTRIBUTIONS_UNOBSERVED')
    rows = []
    e2_all = e2['values']['B7']
    e2_strata = e2['E2_tail_diagnostics']['B7']['strata'][4:]
    e2_strong = sum(row['n_rain'] * row['conditional_pinball'] for row in e2_strata) / 717
    baseline_strong = next(row['control'] for row in uq['metrics'] if row['metric'] == 'strong_log_pinball')
    rows.append(dict(intervention='E2', factor='ALL_RAIN_QUANTILE_LOSS_MULTIPLIER_1_TO_2', control='B7_E0_ORIGINAL_SCHEDULE',
                     all_log_relative_percent=100 * (e2_all['E2']['conditional_pinball'] / e2_all['E0']['conditional_pinball'] - 1),
                     strong_log_relative_percent=100 * (e2_strong / baseline_strong - 1),
                     identified='One fixed loss-weight contrast under its original schedule',
                     unidentified='Rain-intensity-specific gradient norms and shared-encoder interference'))
    for name, source, control, factor in (
        ('UQ_MILD', uq, 'B7_E0_ORIGINAL_SCHEDULE', 'UPPER_QUANTILE_NODE_WEIGHTS'),
        ('COSINE9', cosine, 'B7_E0_ORIGINAL_SCHEDULE', 'LEARNING_RATE_SCHEDULE'),
        ('PHYS20', physical, 'B7_E0_COSINE9', 'PHYSICAL_PINBALL_OVER20_TARGET'),
    ):
        metrics = {row['metric']: row for row in source['metrics']}
        rows.append(dict(intervention=name, control=control, factor=factor,
                         all_log_relative_percent=100 * (metrics['all_log_pinball']['candidate'] / metrics['all_log_pinball']['control'] - 1),
                         strong_log_relative_percent=100 * (metrics['strong_log_pinball']['candidate'] / metrics['strong_log_pinball']['control'] - 1),
                         strong_physical_relative_percent=100 * (metrics['strong_physical_pinball']['candidate'] / metrics['strong_physical_pinball']['control'] - 1),
                         interpretation='Use each intervention against its own matched control, retain guardrail failures'))
    evidence = dict(status='EXISTING_EVIDENCE_TABLE_COMPLETE', source_identities=identities,
        axes=dict(training_target=rows, sample_contribution=shares, readout=nodes['findings']),
        identifiability=dict(
            measured='Saved model response to four existing interventions and finite-node readout on observed strong pixels',
            unresolved=['Per-intensity training-gradient norms and directions', 'Conditional distribution between nodes and beyond q32',
                        'Full-population strong-exceedance ranking/calibration from the current21-cell aggregates',
                        'Independent storm uncertainty and reproducibility of the local terrain effect']),
        next_preparation=dict(task='TARGETED_CONDITIONAL_INTENSITY_DIAGNOSTIC',
            scope='Use existing loss/readout and tail-identifiability interfaces to specify the missing measurements',
            reuse=['src/yuntapr/experimental/research_readiness/tail_identifiability.py',
                   'tools/research_readiness/extreme_diagnostic_candidates.py::exceedance_bounds'],
            candidate_training='NOT_SPECIFIED_FROM_CURRENT_CAUSAL_EVIDENCE',
            reason='Current receipts do not distinguish gradient allocation from representation or finite-node readout limitations'),
        model_modes=dict(engineering='Sol High', bounded_scientific_design='Web ChatGPT High', routine_receipt_sync='Luna'),
        new_training=0, new_inference=0, raw_weather_or_weight_reads=0, scientific_status='NOT_VERIFIED')
    output = PUBLIC / '20261115_mountain_pair_results/CONDITIONAL_INTENSITY_EVIDENCE.json'
    with output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(evidence, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(dict(status=evidence['status'], shares=shares, interventions=rows)))


if __name__ == '__main__':
    main()
