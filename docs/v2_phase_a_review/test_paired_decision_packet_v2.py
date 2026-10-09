"""Isolated metadata fixtures; no model, raw source, optimizer or GPU."""
import copy
import unittest

from build_paired_decision_packet_v2 import FROZEN, KINDS, validate_inputs, render_tex
from completion_gate import reconcile_selection
from test_completion_gate import plateau


def fixture():
    flags = {'MODEL_PARAMETERS_UPDATED': False, 'OPTIMIZER_STEPS': 0,
             'BACKWARD_CALLS': 0, '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0,
             'V2_PHASE_B_AUTHORIZED': False}
    io = {'2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0, 'DENIED_ATTEMPTS': 0}
    review = dict(flags, status='PAIRED_FULL_2024_REVIEW_PASS',
                  checkpoint_selection_performed=False, models={})
    audits, early, counters, histories = {}, {}, {}, {}
    for kind in KINDS:
        rows = plateau()  # BEST=2, early-stop best=1: distinct by min_delta.
        for row in rows:
            row['checkpoint'] = {'epoch': row['epoch'], 'model': kind, 'sha256': str(row['epoch'])}
            row['validation']['N_rain'] = 4496600
        histories[kind] = rows
        es = reconcile_selection(rows)
        early[kind] = dict(es, status='PASS', patience=8, min_delta=1e-4,
                           uses_only_global_val_core_loss=True)
        audits[kind] = dict(flags, **FROZEN, status='TERMINAL_MODEL_AUDIT_PASS', model=kind,
            historical_artifacts_unchanged=True, STATE_APPLICATION_PERFORMED=False,
            final=dict(es, status='COMPLETE'), BEST=rows[1]['checkpoint'], LAST=rows[-1]['checkpoint'])
        counter = {'FORWARD_CALLS': 9 * 6541, 'TRAIN_FORWARDS': 9 * 5228,
                   'VALIDATION_FORWARDS': 9 * 1313, 'BACKWARD_CALLS': 9 * 5228,
                   'OPTIMIZER_STEP_ATTEMPTS': 9 * 5228, 'OPTIMIZER_STEPS': 9 * 5228,
                   'CHECKPOINT_WRITES': 9}
        counters[kind] = {'status': 'PASS', 'retained_trajectory_exact_counters': counter,
            'audit_optimizer_steps': 0, 'audit_backward_calls': 0, 'audit_forward_calls': 0,
            'all_attempt_source_io': dict(io), 'all_attempt_optimizer_reconciliation': {
                'all_attempt_updates_lower_bound': 47351, 'all_attempt_updates_upper_bound': 47352,
                'discarded_updates_lower_bound': 299, 'discarded_updates_upper_bound': 300}}
        metrics = {'global_val_core_loss': .49995, 'Brier_Score': .1, 'AUROC': .7,
                   'Average_Precision': .3, 'conditional_mean_pinball': .2,
                   'scenes': 10501, 'forwards': 1313, 'N_valid': 36018430, 'N_rain': 4496600,
                   'physical_materialization': False, 'strict_crossing_count': 0,
                   'support_violation_count': 0, 'nonfinite_count': 0}
        tail = {'phase': 'VALIDATION', 'scenes': 10501, 'forwards': 1313,
                'affects_loss_BEST_early_stop_LR_parameters_batch_or_termination': False}
        for partition in ('YUNNAN_INSIDE', 'YUNNAN_OUTSIDE'):
            tail[partition] = {'max_qlog': 1000., 'q32_per_forward_max_p99': 5.,
                'q32_per_forward_max_p99_9': 6., 'FP64_PHYSICAL_OVERFLOW_RISK': True,
                'threshold_exceedances': {str(t): {'scene_pixel_tau_exposure': 3,
                    'scene_pixel_any_tau_exposure': 2} for t in (10, 50, 100, 500, 1000)}}
        review['models'][kind] = dict(flags, status='FULL_2024_BEST_REVIEW_PASS', model=kind,
            BEST=rows[1]['checkpoint'], model_state_sha256_before='same-state',
            model_state_sha256_after='same-state', metrics=metrics, io=dict(io),
            REVIEW_FORWARD_CALLS=1313, validation_sample_ids_sha256='same-fixed-order',
            training_best_metric_reconciliation={'tolerance': 0, 'mismatches': {}},
            upper_tail_diagnostics=tail)
    return tuple(copy.deepcopy(value) for value in (review, audits, early, counters, histories))


class PacketEvidenceTests(unittest.TestCase):
    def test_best_can_differ_from_early_stop_best_and_risk_is_descriptive(self):
        validate_inputs(*fixture())

    def test_partial_review_and_missing_model_rejected(self):
        for mutate in (lambda r: r.update(status='NOT_RUN'),
                       lambda r: r['models'].pop('B1_V2')):
            values = fixture(); mutate(values[0])
            with self.assertRaises(ValueError): validate_inputs(*values)

    def test_wrong_best_and_changed_model_rejected(self):
        for mutate in (lambda r: r['BEST'].update(sha256='changed'),
                       lambda r: r.update(model_state_sha256_after='changed')):
            values = fixture(); mutate(values[0]['models']['B1_V2'])
            with self.assertRaises(ValueError): validate_inputs(*values)

    def test_frozen_identity_and_2025_access_rejected(self):
        values = fixture(); values[1]['B1_V2']['normalization_sha256'] = 'changed'
        with self.assertRaises(ValueError): validate_inputs(*values)
        values = fixture(); values[0]['models']['B1_V2']['io']['2025_RAW_ACCESS'] = 1
        with self.assertRaises(ValueError): validate_inputs(*values)

    def test_test_or_audit_steps_cannot_be_counted_as_formal(self):
        values = fixture(); values[3]['B1_V2']['retained_trajectory_exact_counters']['OPTIMIZER_STEPS'] += 4
        with self.assertRaises(ValueError): validate_inputs(*values)
        values = fixture(); values[3]['B1_V2']['audit_forward_calls'] = 1
        with self.assertRaises(ValueError): validate_inputs(*values)

    def test_reordered_samples_or_loss_mismatch_rejected(self):
        values = fixture(); values[0]['models']['B1_V2']['validation_sample_ids_sha256'] = 'reordered'
        with self.assertRaises(ValueError): validate_inputs(*values)
        values = fixture(); values[0]['models']['B1_V2']['metrics']['global_val_core_loss'] = .5
        with self.assertRaises(ValueError): validate_inputs(*values)

    def test_diagnostic_selection_or_partial_coverage_rejected(self):
        values = fixture()
        values[0]['models']['B1_V2']['upper_tail_diagnostics']['affects_loss_BEST_early_stop_LR_parameters_batch_or_termination'] = True
        with self.assertRaises(ValueError): validate_inputs(*values)
        values = fixture(); values[0]['models']['B1_V2']['metrics']['scenes'] -= 5
        with self.assertRaises(ValueError): validate_inputs(*values)

    def test_nan_rejected_but_defined_single_class_none_allowed(self):
        values = fixture(); values[0]['models']['B1_V2']['metrics']['Brier_Score'] = float('nan')
        with self.assertRaises(ValueError): validate_inputs(*values)
        values = fixture()
        for kind in KINDS:
            metrics = values[0]['models'][kind]['metrics']
            metrics.update(N_rain=0, AUROC=None, Average_Precision=None, conditional_mean_pinball=None)
            values[4][kind][1]['validation']['N_rain'] = 0
        validate_inputs(*values)

    def test_report_uses_sample_set_and_bounds_without_training_reselection(self):
        review, audits, early, counters, _ = fixture()
        packet = {'created_utc': 'SYNTHETIC_FIXTURE_ONLY', 'frozen_identities': FROZEN,
                  'models': {k: {**audits[k], 'early_stopping': early[k],
                    'formal_counters': counters[k], 'metrics': review['models'][k]['metrics'],
                    'upper_tail_diagnostics': review['models'][k]['upper_tail_diagnostics']} for k in KINDS}}
        for model in packet['models'].values():
            for name in ('BEST', 'LAST'):
                model[name] = {**model[name], 'absolute_local_path': 'F:/fixture_only/no_binary.pt',
                               'bytes': 123, 'sha256': 'f' * 64}
        output = render_tex(packet)
        self.assertIn('样本集合', output)
        self.assertNotIn('人口', output)
        self.assertIn('299 至 300', output)
        self.assertIn('Phase-B 未授权', output)
        self.assertNotIn('expm1(', output)
        self.assertTrue(output.endswith('\\end{document}\n'))


if __name__ == '__main__':
    unittest.main()
