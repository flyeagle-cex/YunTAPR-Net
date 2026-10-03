"""Independent checks of the completed B1 audit's scalar/identity artifacts.

No raw data, model, checkpoint, normalization or outcomes are opened here.
These tests intentionally fail if the real audit has not completed.
"""
import csv
from collections import Counter
from datetime import timedelta
import hashlib
import json
import re
import unittest
from yuntapr.contracts.loader import REPO_ROOT,sha256
from yuntapr.data.b1_temporal_audit import utc,times,LAGS,FRAME_FIELDS,SLOT_FIELDS,POP_FIELDS

RUN=REPO_ROOT/'docs/b1_temporal_audit/runs/run_20261003T035724_142784Z'
DESIGN=REPO_ROOT/'docs/b1_scientific_design/candidates/run_20261003T024550_523841Z'

def read(path):return json.loads(path.read_text(encoding='utf-8'))
def csv_rows(path,fields):
    with path.open(encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream)
        if tuple(reader.fieldnames)!=tuple(fields):raise AssertionError('Unexpected artifact columns')
        return list(reader)

class B1FullAuditArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.status=read(RUN/'final_status.json')
        cls.summary=read(RUN/'temporal_availability_summary.json')
        cls.start=read(RUN/'audit_start.json')
        cls.frames={};cls.slots={}
        for name in sorted(cls.status['native_frame_csv_sha256']):
            for r in csv_rows(RUN/name,FRAME_FIELDS):
                if r['nominal'] in cls.frames:raise AssertionError('Duplicate native identity')
                cls.frames[r['nominal']]=r
        for name in sorted(cls.status['six_slot_csv_sha256']):
            for r in csv_rows(RUN/name,SLOT_FIELDS):cls.slots.setdefault(r['sample_id'],[]).append(r)

    def test_complete_fixed_native_and_target_schedule(self):
        expected=[t.isoformat() for y in (2023,2024) for t in times(y,10)]
        self.assertEqual(list(self.frames),expected)
        targets=[t.isoformat() for y in (2023,2024) for t in times(y,30)]
        self.assertEqual(list(self.slots),targets)
        self.assertEqual(sum(len(v) for v in self.slots.values()),141120)
        self.assertEqual(len(self.status['native_frame_csv_sha256']),16)
        self.assertEqual(len(self.status['six_slot_csv_sha256']),16)

    def test_real_metadata_causality_and_order_independently(self):
        for sid,rows in self.slots.items():
            self.assertEqual([int(r['slot']) for r in rows],list(range(6)))
            a=utc(sid)+timedelta(minutes=30)
            for i,r in enumerate(rows):
                n=a-timedelta(minutes=LAGS[i]);self.assertEqual(utc(r['expected_nominal']),n)
                if n.month==2:
                    self.assertEqual(r['frame_status'],'OUTSIDE_AUDIT_SCOPE');continue
                frame=self.frames[n.isoformat()]
                self.assertEqual(r['frame_status'],frame['status'])
                if frame['metadata_valid']=='True':
                    start,end=utc(frame['obs_start']),utc(frame['obs_end'])
                    self.assertEqual(r['causality_pass'],str(start<=end<=a))
                    self.assertEqual(r['scan_bucket_conforms'],str(n<=start<=end<=n+timedelta(minutes=10)))
                    self.assertEqual('NONCAUSAL_FRAME' in r['reasons'],not start<=end<=a)

    def test_outside_scope_not_misreported_as_missing(self):
        outside=[r for rows in self.slots.values() for r in rows if r['frame_status']=='OUTSIDE_AUDIT_SCOPE']
        self.assertEqual(len(outside),6)
        for year in (2023,2024):
            rows=self.slots[f'{year}-03-01T00:00:00+00:00']
            self.assertEqual([r['frame_status'] for r in rows[:3]],['OUTSIDE_AUDIT_SCOPE']*3)
            self.assertTrue(all(r['reasons']=='OUTSIDE_AUDIT_SCOPE' for r in rows[:3]))
        self.assertFalse(any(utc(k).month==2 for k in self.frames))

    def test_reported_per_slot_reason_counts(self):
        pairs=(('MISSING','missing_by_slot'),('CORRUPT_OR_UNREADABLE','unreadable_by_slot'),
               ('PARTIAL','partial_by_slot'),('ALL_FILL','all_fill_by_slot'),
               ('NONCAUSAL_FRAME','noncausal_by_slot'),('OUTSIDE_AUDIT_SCOPE','outside_scope_by_slot'))
        for annual in self.summary['annual']:
            year=int(annual['role'][:4]);rows=[r for sid,value in self.slots.items() if utc(sid).year==year for r in value]
            for reason,key in pairs:
                values=[sum(reason in r['reasons'].split(';') for r in rows if int(r['slot'])==i) for i in range(6)]
                self.assertEqual(annual[key],values)
            self.assertEqual(annual['scan_bucket_deviation_by_slot'],
                [sum(r['scan_bucket_conforms']=='False' for r in rows if int(r['slot'])==i) for i in range(6)])
            self.assertEqual(annual['metadata_error_by_slot'],
                [sum(bool(set(r['reasons'].split(';'))&{'TIME_METADATA_ERROR','B13_GRID_OR_PACKING_METADATA_ERROR'})
                     for r in rows if int(r['slot'])==i) for i in range(6)])

    def test_candidate_population_and_multi_reason_reconciliation(self):
        source=self.start['definition']['baseline_commit']
        self.assertEqual(source,'4286f8151fea2185c99b3cea0c8e532e8cd90070')
        index=read(RUN/'frame_identity_index.json')
        ref=index['original_target_refs']['combined_eligibility_source']
        self.assertEqual(sha256(REPO_ROOT/ref['path']),ref['sha256'])
        with (REPO_ROOT/ref['path']).open(encoding='utf-8-sig',newline='') as stream:
            pinned={utc(r['window_start']).isoformat():r for r in csv.DictReader(stream)}
        valid={sid:int(r['imerg_valid_yunnan_count'] or 0)>0 for sid,r in pinned.items()}
        for name in self.status['population_csv_sha256']:
            for r in csv_rows(RUN/name,POP_FIELDS):
                original=pinned[r['sample_id']]
                self.assertEqual(r['window_start'],r['sample_id'])
                self.assertEqual(utc(r['analysis_time']),utc(r['window_start'])+timedelta(minutes=30))
                self.assertEqual(r['imerg_day_path'],original['imerg_day_path'])
                self.assertEqual(r['imerg_index'],original['imerg_index'])
        for annual in self.summary['annual']:
            year=int(annual['role'][:4]);expected=set();reasons=Counter();combinations=Counter();complete=0;present=0
            for sid,rows in self.slots.items():
                if utc(sid).year!=year:continue
                rs=[f'S{r["slot"]}_{v}' for r in rows for v in r['reasons'].split(';') if v]
                if not valid[sid]:rs.append('TARGET_NO_VALID_YUNNAN_FROM_PINNED_2023_2024_EVIDENCE')
                if not rs:expected.add(sid)
                reasons.update(rs)
                if rs:combinations[';'.join(rs)]+=1
                complete+=all(not r['reasons'] for r in rows)
                present+=all(r['frame_status']!='OUTSIDE_AUDIT_SCOPE' and
                    self.frames[r['expected_nominal']]['present']=='True' for r in rows)
            actual=csv_rows(RUN/f'b1_candidate_eligible_{year}.csv',POP_FIELDS)
            self.assertEqual({r['sample_id'] for r in actual},expected)
            self.assertEqual(len(actual),len(expected))
            self.assertTrue(all(r['population_status']=='B1_COMPLETE_SIX_SLOT_FULL_VALID_CAUSAL_CANDIDATE_NOT_FORMAL' for r in actual))
            self.assertEqual(annual['six_slot_candidate_eligible'],len(expected))
            self.assertEqual(annual['candidate_rejected_or_unresolved'],11760-len(expected))
            self.assertEqual(annual['all_6_slots_full_valid_causal'],complete)
            self.assertEqual(annual['all_6_slots_present'],present)
            self.assertEqual(annual['rejection_or_unresolved_reason_counts'],dict(sorted(reasons.items())))
            self.assertEqual(annual['multi_reason_combinations'],dict(sorted(combinations.items())))

    def test_original_population_and_intersection_exact_sets(self):
        refs=read(RUN/'frame_identity_index.json')['original_target_refs']
        for year,key,count in ((2023,'eligible_train_manifest',11720),(2024,'eligible_validation_manifest',11727)):
            ref=refs[key];self.assertEqual(sha256(REPO_ROOT/ref['path']),ref['sha256'])
            with (REPO_ROOT/ref['path']).open(encoding='utf-8-sig',newline='') as stream:
                original={utc(r['window_start']).isoformat() for r in csv.DictReader(stream)}
            b0=csv_rows(RUN/f'b0_original_eligible_{year}.csv',POP_FIELDS)
            b1=csv_rows(RUN/f'b1_candidate_eligible_{year}.csv',POP_FIELDS)
            intersection=csv_rows(RUN/f'intersection_candidate_{year}.csv',POP_FIELDS)
            self.assertEqual(len(b0),count);self.assertEqual({r['sample_id'] for r in b0},original)
            self.assertEqual({r['sample_id'] for r in intersection},original&{r['sample_id'] for r in b1})
            self.assertEqual(len(intersection),len({r['sample_id'] for r in intersection}))
            self.assertTrue(all(r['population_status']=='B0_B1_CANDIDATE_INTERSECTION_NOT_PRIMARY_FROZEN' for r in intersection))

    def test_identity_hashes_code_definition_and_csv_bindings(self):
        for key in ('native_frame_csv_sha256','six_slot_csv_sha256','population_csv_sha256'):
            for name,digest in self.status[key].items():self.assertEqual(sha256(RUN/name),digest)
        self.assertEqual(sha256(RUN/'frame_identity_index.json'),self.status['frame_identity_index_sha256'])
        self.assertEqual(read(RUN/'frame_identity_index.json')['files'],self.status['native_frame_csv_sha256'])
        definition=REPO_ROOT/'config/b1/b1_six_slot_audit_definition_v1.json'
        self.assertEqual(sha256(definition),self.status['definition_sha256'])
        self.assertEqual(self.start['definition'],read(definition))
        for name,digest in self.start['code_sha256'].items():self.assertEqual(sha256(REPO_ROOT/name),digest)
        for name in self.status['population_csv_sha256']:
            for row in csv_rows(RUN/name,POP_FIELDS):
                self.assertEqual(row['frame_identity_index_sha256'],self.status['frame_identity_index_sha256'])

    def test_raw_io_and_bounded_cleanup_reconciliation(self):
        present=[r for r in self.frames.values() if r['present']=='True']
        size=sum(int(r['source_bytes']) for r in present)
        telemetry=self.status['raw_access_telemetry']
        for key in ('source_hash_bytes_read','source_copy_bytes_read','source_copy_bytes_written'):
            self.assertEqual(telemetry[key],size)
        self.assertEqual(telemetry['raw_source_open_events'],2*len(present))
        self.assertEqual(self.status['source_guard_final_counter_capture_status'],'NOT_CAPTURED_BEFORE_CLI_REGISTRY_ERROR')
        self.assertEqual(self.status['metadata_closure_raw_source_open_events'],0)
        self.assertTrue(telemetry['cleanup_success'])
        self.assertEqual(telemetry['temporary_bytes_peak'],max(int(r['source_bytes']) for r in present))
        self.assertGreater(telemetry['copy_seconds'],0);self.assertGreater(telemetry['read_seconds'],0)
        self.assertTrue(all(re.fullmatch('[0-9a-f]{64}',r['source_sha256']) for r in present))

    def test_no_training_no_fit_no_model_no_2025_and_pending_decisions(self):
        for key in ('B1_DESIGN_FROZEN','B1_MISSING_POLICY_FROZEN','B1_NORMALIZATION_FROZEN',
            'B1_FAIRNESS_PRIMARY_POPULATION_FROZEN','B1_FORMAL_MODEL_IMPLEMENTED','B1_TRAINING_STARTED',
            'B1_NORMALIZATION_FITTED','2025_FINAL_TEST_EXECUTED'):self.assertIs(self.status[key],False)
        for key in ('2025_MODEL_INFERENCE_SCENES','2025_RAW_PIXELS_READ','MODEL_CHECKPOINT_LOADS',
                    'MODEL_FORWARD_CALLS','OPTIMIZER_STEPS','BACKWARD_CALLS'):self.assertEqual(self.status[key],0)
        for key in ('B1_SLOT_DEFINITION_FROZEN','B1_TENSOR_CONTRACT_FROZEN','B1_TEMPORAL_AUDIT_EXECUTED'):
            self.assertIs(self.status[key],True)
        self.assertEqual(self.summary['population_policy_status'],'CANDIDATE_ONLY_MISSING_POLICY_NOT_FROZEN')
        self.assertFalse((RUN/'failure.json').exists())

    def test_immutable_1802_baseline_files_and_parameter_fixture(self):
        history=read(RUN/'history_before.json');self.assertEqual(len(history),1802)
        for name,ref in history.items():
            data=(REPO_ROOT/name).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(),ref['sha256'])
            self.assertEqual(hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest(),ref['git_blob_sha1'])
        params=read(DESIGN/'candidate_parameter_inventory.json')
        self.assertEqual(params['B0_actual_parameters'],4329361)
        self.assertEqual(params['B1_six_channel_candidate_parameters'],4331761)
        self.assertEqual(params['delta_parameters'],2400)
        self.assertEqual(params['unchanged_parameter_tensor_count'],72)
        self.assertIs(params['TEST_FIXTURE_ONLY'],True)
        self.assertEqual(params['FORWARD_CALLS'],0)

    def test_cli_path_fix_and_immutable_predecessor_resolution(self):
        from scripts.audit_b1_temporal_v1 import parse_arguments
        definition=REPO_ROOT/'config/b1/b1_six_slot_audit_definition_v1.json'
        args=parse_arguments(['--definition',str(definition),'--definition-sha256',sha256(definition),
            '--run-directory',str(RUN),'--staging-root','FIXTURE_NO_SOURCE_OPEN'])
        self.assertIsInstance(args.definition,type(definition))
        self.assertEqual(sha256(args.definition),self.status['definition_sha256'])
        snapshot=read(RUN/'source_run_snapshot.json');source=REPO_ROOT/snapshot['source_run_relative_directory']
        self.assertTrue((source/'failure.json').exists());self.assertFalse((source/'final_status.json').exists())
        for name,ref in snapshot['files'].items():self.assertEqual(sha256(source/name),ref['sha256'])
        original=read(RUN/'source_audit_start.json')
        for name,digest in original['code_sha256'].items():self.assertEqual(sha256(RUN/'source_execution_code'/name),digest)
        self.assertEqual(self.start['execution_mode'],'METADATA_ONLY_CLOSURE_NO_RAW_REOPEN')
