"""Read-only artifact checks; no original 2025 source or FINAL is opened.

The caller must supply B0_CATALOGUE_ARTIFACT_RUN for this independent suite.
It does not authorize any catalogue execution, source read, or inference.
"""
from functools import lru_cache
import json
import os
from pathlib import Path
import unittest

from yuntapr.contracts.loader import REPO_ROOT,sha256
from yuntapr.evaluation import catalogue_gate_b0 as gate
from yuntapr.evaluation import catalogue_execution_v1_1 as execution


@lru_cache(maxsize=1)
def artifacts():
    run=gate.safe_artifact_path(os.environ['B0_CATALOGUE_ARTIFACT_RUN'])
    if not run.is_relative_to(REPO_ROOT/'docs/final_test_b0/catalogue_gate_v1_1/catalogue_only_runs'):
        raise ValueError('Independent catalogue artifact run required')
    root=run/'catalogue'
    candidates=gate.read_csv(root/'b0_2025_final_test_candidate_catalogue_v1.csv')
    population=gate.read_csv(root/'b0_2025_final_test_population_manifest_v1.csv',gate.POPULATION_COLUMNS)
    return run,root,candidates,population,gate.read(root/'catalogue_freeze_record.json'),gate.read(run/'final_status.json')


class RealCatalogueArtifactTests(unittest.TestCase):
    def test_exact_28_and_12_columns_in_fixed_order(self):
        _,_,rows,pop,_,_=artifacts()
        self.assertTrue(all(tuple(r)==gate.COLUMNS for r in rows))
        self.assertTrue(all(tuple(r)==gate.POPULATION_COLUMNS for r in pop))

    def test_complete_10272_time_slots_no_gap_duplicate_reorder_or_october(self):
        _,_,rows,_,_,_=artifacts()
        self.assertEqual(len(rows),10272)
        self.assertEqual([gate.utc(r['window_start']) for r in rows],list(gate.scheduled_times()))
        self.assertEqual([int(r['candidate_index']) for r in rows],list(range(10272)))
        self.assertEqual(len({r['sample_id'] for r in rows}),10272)
        for row in rows:gate.guard_paths(row)

    def test_eligible_manifest_is_exact_identity_projection_and_counts_reconcile(self):
        _,_,rows,pop,freeze,status=artifacts()
        eligible=gate.validate_manifests(rows,pop)
        self.assertEqual(len(eligible),freeze['eligible_count'])
        self.assertEqual(10272-len(eligible),freeze['rejected_count'])
        self.assertEqual(len(pop),status['REAL_2025_ELIGIBLE_COUNT'])
        self.assertEqual(freeze['eligible_count']+freeze['rejected_count'],10272)

    def test_only_frozen_eligibility_enum_and_no_older_fallback(self):
        _,_,rows,_,_,_=artifacts()
        for row in rows:
            reasons=gate.eligibility(row)
            self.assertEqual(row['rejection_reason'],';'.join(reasons))
            self.assertEqual(row['eligible'],str(not reasons))
            self.assertEqual(row['used_older_causal_frame'],'False')

    def test_two_csv_freeze_record_and_authorization_hashes(self):
        run,root,_,_,freeze,status=artifacts();binding=gate.read(run/'authorization_binding.json')
        self.assertEqual(sha256(root/'b0_2025_final_test_candidate_catalogue_v1.csv'),status['CANDIDATE_CATALOGUE_SHA256'])
        self.assertEqual(sha256(root/'b0_2025_final_test_population_manifest_v1.csv'),status['ELIGIBLE_POPULATION_MANIFEST_SHA256'])
        self.assertEqual(sha256(root/'catalogue_freeze_record.json'),status['CATALOGUE_FREEZE_RECORD_SHA256'])
        self.assertEqual(sha256(REPO_ROOT/binding['authorization_path']),freeze['catalogue_authorization_sha256'])

    def test_original_protocol_backend_and_all_1771_baseline_artifacts_unchanged(self):
        run,_,_,_,freeze,status=artifacts();gate.load_protocol()
        self.assertEqual(execution.verify_history(gate.read(run/'history_before.json')),1771)
        self.assertEqual(freeze['implementation_sha256'],gate.implementation_hashes())
        self.assertEqual(status['historical_artifacts_unchanged'],1771)
        authorization=gate.read(REPO_ROOT/'config/evaluation/b0_2025_catalogue_only_authorization_v1.1.json')
        self.assertEqual(authorization['execution_implementation_sha256'],execution.execution_hashes())

    def test_source_copy_hash_bytes_and_peak_match_unique_staged_identities(self):
        _,_,rows,_,freeze,_=artifacts();telemetry=gate.sanitized_telemetry(freeze['raw_access_telemetry'])
        sizes=[int(r['b13_bytes'] or 0) for r in rows]
        daily={r['imerg_day_path']:int(r['imerg_bytes'] or 0) for r in rows}
        total=sum(sizes)+sum(daily.values())
        self.assertEqual(telemetry['source_copy_bytes_read'],total)
        self.assertEqual(telemetry['source_copy_bytes_written'],total)
        self.assertEqual(telemetry['source_hash_bytes_read'],total)
        self.assertEqual(telemetry['raw_source_open_events'],2*(sum(v>0 for v in sizes)+sum(v>0 for v in daily.values())))
        self.assertEqual(telemetry['temporary_bytes_peak'],max(sizes+list(daily.values())))
        self.assertIs(telemetry['cleanup_success'],True)
        self.assertEqual(telemetry['2025_PIXELS_READ'],telemetry['b13_pixel_values_read']+telemetry['imerg_pixel_values_read'])

    def test_formal_execution_and_outcome_flags_remain_disabled(self):
        _,_,_,_,freeze,status=artifacts()
        for key in ('FINAL_TEST_2025_AUTHORIZED','FINAL_TEST_2025_EXECUTED','2025_FINAL_TEST_EXECUTED',
                    '2025_FINAL_TEST_METRICS_COMPUTED','2025_TARGET_OUTCOME_SUMMARIES_EXPOSED','MODEL_PARAMETERS_UPDATED'):
            self.assertIs(status[key],False)
        for key in ('2025_MODEL_INFERENCE_SCENES','OPTIMIZER_STEPS','BACKWARD_CALLS','FINAL_CHECKPOINT_LOADS','MODEL_FORWARD_CALLS'):
            self.assertEqual(status[key],0)
        self.assertIs(freeze['2025_FINAL_TEST_EXECUTED'],False)
        self.assertIs(status['FINAL_actual_file_sha256_recomputed'],False)
        self.assertIs(status['FINAL_identity_record_sha256_unchanged'],True)
        self.assertTrue(status['second_stage_researcher_authorization_required'])
