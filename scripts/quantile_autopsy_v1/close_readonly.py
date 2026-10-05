"""Independent evidence closure after the replay process has exited.

No torch import, checkpoint deserialization, model construction, raw-source open,
backward or optimizer step. The original terminal error is preserved unchanged.
"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from quantile_autopsy_v1 import common as c
from collections import Counter
from datetime import datetime
import argparse
import csv
import json
import math
import os

KEYS=('sample_ids','update','LR','actual_denominator','loss','pre_clip_norm','post_clip_norm','clipped')
GUARD_ERROR='No checkpoint writes or other checkpoint reads in replay'

def check_terminal(original):
    if (original.get('status')!='REPRODUCTION_FAILURE' or original.get('error_type')!='PermissionError'
        or original.get('error')!=GUARD_ERROR or 'c.verify_snapshot(run)' not in original.get('traceback','')):
        raise ValueError('Only the known post-reproduction SHA closure error is eligible for read-only reconciliation')
    expected={'ENGINEERING_OPTIMIZER_STEPS':c.SUCCESS,'ENGINEERING_BACKWARD_CALLS':c.SUCCESS,
        'ENGINEERING_FORWARD_CALLS':c.FAIL_BATCH,'FORMAL_OPTIMIZER_STEPS_ADDED':0,
        'FORMAL_OPTIMIZER_STEPS':c.FORMAL_STEPS,'2025_RAW_ACCESS':0,'2025_PIXELS_READ':0,'B1_PHASE_B_STARTED':False}
    if original.get('counts')!=expected or original.get('exact_matches')!={k:c.SUCCESS for k in KEYS}:
        raise ValueError('Original replay counts do not establish exact numerical completion')
    return expected

def check_failure(failure,last_row):
    if (last_row.get('status')!='EXPECTED_FORWARD_OVERFLOW' or last_row.get('update')!=c.BOUNDARY+c.FAIL_BATCH
        or failure.get('update')!=last_row['update'] or not failure.get('captured_before_expm1')
        or failure.get('qlog_dtype')!='torch.float64' or not failure.get('qlog_all_finite')
        or not failure.get('raw_all_finite') or failure.get('qphysical_nonfinite_count',0)<1
        or failure.get('sample_identities') is None):
        raise ValueError('Actual pre-expm1 overflow capture is incomplete')
    if last_row['sample_ids']!=[r['sample_id'] for r in failure['sample_identities']]:
        raise ValueError('Failed sample identity mismatch')
    if last_row['qphysical_nonfinite_count']!=failure['qphysical_nonfinite_count']:
        raise ValueError('Physical nonfinite count mismatch')
    if last_row['qlog']['max']!=failure['qlog_max'] or failure['qlog_max']<=math.log1p(sys.float_info.max):
        raise ValueError('Observed float64 overflow boundary not exceeded')
    q=failure['qlog_32_at_pixel'];inc=failure['increments_32_at_pixel'];raw=failure['raw_32_at_pixel']
    if len(q)!=32 or len(inc)!=32 or len(raw)!=32 or len(failure['target_feature_48_at_pixel'])!=48:
        raise ValueError('Failed local vector shape mismatch')
    if not all(math.isfinite(v) for v in q+inc+raw) or not all(v>0 for v in inc):
        raise ValueError('Nonfinite or nonpositive captured accumulator')
    if not all(a<b for a,b in zip(q,q[1:])) or not math.isclose(q[-1],math.log1p(.1)+sum(inc),rel_tol=1e-14):
        raise ValueError('Captured strict monotonic recurrence mismatch')
    for key in ('qlog_per_tau_max','qlog_per_tau_median','increments_per_tau_max','increments_per_tau_mean','raw_per_tau_max'):
        if last_row[key]!=failure['observation'][key]:raise ValueError('Captured/journal tau values differ')
    return True

def replay_rows(rows,references,failure):
    rows=iter(rows);count=0;sample_ids=[];last=None
    for reference in references:
        row=next(rows,None)
        if row is None or row.get('status')!='SUCCESS_EXACT_MATCH':raise ValueError('Missing successful journal update')
        if not all(k in row and k in reference for k in KEYS):raise ValueError('Missing exact comparison field')
        c.exact_reconcile(reference,row);count+=1;sample_ids.extend(row['sample_ids'])
    last=next(rows,None)
    if count!=c.SUCCESS or last is None or next(rows,None) is not None:
        raise ValueError('Journal update count or trailing events incorrect')
    check_failure(failure,last);sample_ids.extend(last['sample_ids'])
    if len(sample_ids)!=2*c.FAIL_BATCH or len(set(sample_ids))!=len(sample_ids):
        raise ValueError('Replay scenes duplicated or incomplete')
    return {'successful_updates':count,'failed_forward_batch':c.FAIL_BATCH,'journal_rows':count+1,
            'exact_matches':{k:count for k in KEYS},'sample_ids':sample_ids,'last':last}

def rows(path):
    with Path(path).open(encoding='utf8') as f:
        for line in f:yield json.loads(line)

def source_key(path):return os.path.normcase(str(Path(path).resolve()))

def source_journals(run,sample_ids,records):
    wanted_ids=set(sample_ids)
    selected={r['sample_id']:r for r in records if r['sample_id'] in wanted_ids}
    if len(selected)!=len(sample_ids):raise ValueError('Unknown replay sample identity')
    allowed={};expected_sources={}
    for r in selected.values():
        dt=datetime.fromisoformat(r['window_start'])
        if dt.year not in (2023,2024) or not 3<=dt.month<=10:raise ValueError('2025/out-of-scope target')
        b13=source_key(Path(r'H:\葵花202303_202510')/r['b13_relative_path'])
        imerg=source_key(r['imerg_day_path'])
        pair={b13:{'sha256':r['b13_sha256'],'bytes':int(r['b13_bytes'])},
              imerg:{'sha256':r['imerg_sha256'],'bytes':None}}
        expected_sources[r['sample_id']]=pair;allowed.update(pair)
    raw_count=0;raw_sources=set()
    for p in sorted(run.glob('raw_access_*.jsonl')):
        for event in rows(p):
            key=source_key(event['path'])
            if key not in allowed or event['event']!='RAW_READ_ONLY_OPEN' or event['model_scope_authorized'] is not True:
                raise ValueError('Unapproved raw access journal event')
            raw_count+=1;raw_sources.add(key)
    seen=[];copy_count=temporary_bytes=0;copy_seconds=read_seconds=0.
    for p in sorted(run.glob('staging_worker_*.jsonl')):
        for event in rows(p):
            sid=event['sample_id'];record=selected.get(sid)
            if record is None or int(record['index'])!=event['index'] or int(record['year'])!=event['year']:
                raise ValueError('Staging scene identity differs from frozen manifest')
            pair=expected_sources[sid]
            if len(event['staging'])!=2 or {source_key(s['source_path']) for s in event['staging']}!=set(pair):
                raise ValueError('B0 latest B13 + IMERG source pair changed')
            for item in event['staging']:
                wanted=pair[source_key(item['source_path'])]
                if (not item['size_match'] or not item['sha256_match'] or not item['cleanup_success']
                    or item['error'] or item['cleanup_error'] or item['source_sha256']!=wanted['sha256']
                    or wanted['bytes'] is not None and item['temporary_bytes']!=wanted['bytes']):
                    raise ValueError('Staging actual source identity/cleanup verification failed')
                if not all(math.isfinite(item[k]) and item[k]>=0 for k in ('copy_seconds','read_seconds')):
                    raise ValueError('Nonfinite staging timing')
                copy_count+=1;temporary_bytes+=item['temporary_bytes']
                copy_seconds+=item['copy_seconds'];read_seconds+=item['read_seconds']
            seen.append(sid)
    if Counter(seen)!=Counter(sample_ids) or raw_sources!=set(allowed):
        raise ValueError('Actual source-read population differs from exactly 17252 replay scenes')
    return {'scenes':len(seen),'verified_copies':copy_count,'unique_sources':len(allowed),
        'raw_read_only_open_events':raw_count,'all_sources_match_frozen_manifest_SHA':True,
        'all_copy_size_SHA_cleanup_checks_pass':True,'temporary_bytes_cumulative':temporary_bytes,
        'copy_seconds_sum_across_workers':copy_seconds,'read_seconds_sum_across_workers':read_seconds,
        '2025_RAW_ACCESS':0,'raw_write_events':0,'no_extra_prefetch_scenes':True}

def close(run):
    run=run.resolve();dest=run/'readonly_closeout'
    if dest.exists():raise FileExistsError('Never replace a prior closure attempt')
    dest.mkdir()
    original=c.read(run/'replay_reconciliation.json');counts=check_terminal(original)
    # Preserve and verify the exact numerical implementation executed during replay.
    source_pins=c.read(run/'observer_test_result.json')['diagnostic_source_hashes'];archive=dest/'executed_sources';archive.mkdir()
    for relative,wanted in source_pins.items():
        src=c.ROOT/relative
        if c.digest(src)!=wanted:raise ValueError('Executed diagnostic source changed')
        (archive/(src.name+'.txt')).write_bytes(src.read_bytes())
    evidence=[c.pin(p) for p in sorted(run.rglob('*')) if p.is_file() and not p.is_relative_to(dest)]
    immutable=c.verify_snapshot(run)
    gate=c.read(run/'replay_identity_preflight.json')
    if not gate['provenance_verified_before_state_application'] or any(r['expected']!=r['actual'] for r in gate['state_hashes'].values()):
        raise ValueError('Pre-application restoration identity failed')
    failure=c.read(run/'failing_tensor_diagnostics.json')
    replay=replay_rows(rows(run/'replay_observations.jsonl'),c.historical_updates(5),failure)
    manifest=c.read(c.FAILED/'run_manifest.json')['manifest'];c.verify(manifest)
    records=c.csv_rows(manifest['path']);sources=source_journals(run,replay['sample_ids'],records)
    for item in failure['sample_identities']:
        record=records[item['index']]
        if any(item[k]!=record[k] for k in ('sample_id','window_start','analysis_time')):
            raise ValueError('Failed batch target binding differs from frozen manifest')
        if (item['imerg_sha256']!=record['imerg_sha256'] or item['imerg_index']!=int(record['imerg_index'])
            or item['normalization_sha256']!=c.read(c.FAILED/'run_manifest.json')['normalization']['sha256']):
            raise ValueError('Failed target/normalization identity mismatch')
        fr=item['frames'][0]
        if len(item['frames'])!=1 or fr['slot']!=5 or fr['source_sha256']!=record['b13_sha256']:
            raise ValueError('Failed B13 source/latest-slot identity mismatch')
        for k in ('nominal_time','obs_start','obs_end','date_created'):
            column='expected_nominal' if k=='nominal_time' else k
            if datetime.fromisoformat(fr[k])!=datetime.fromisoformat(record[column]):
                raise ValueError('Failed B13 actual CF metadata mismatch')
        if not datetime.fromisoformat(fr['obs_start'])<=datetime.fromisoformat(fr['obs_end'])<=datetime.fromisoformat(item['analysis_time']):
            raise ValueError('Failed batch causality constraint violated')
    # Cross-check every value in the 32-tau CSV against the complete JSON journal.
    with (run/'per_tau_growth_diagnostics.csv').open(encoding='utf8',newline='') as f:
        tau_rows=iter(csv.DictReader(f));tau_count=0
        for row in rows(run/'replay_observations.jsonl'):
            for t in range(32):
                actual=next(tau_rows,None)
                if actual is None or int(actual['update'])!=row['update'] or int(actual['tau_ordinal'])!=t+1 or actual['status']!=row['status']:
                    raise ValueError('Tau CSV coverage/order differs from JSON journal')
                for column,key in [('qlog_max','qlog_per_tau_max'),('qlog_median','qlog_per_tau_median'),
                    ('increment_max','increments_per_tau_max'),('increment_mean','increments_per_tau_mean'),('raw_max','raw_per_tau_max')]:
                    if float(actual[column])!=row[key][t]:raise ValueError('Tau CSV numeric mismatch')
                tau_count+=1
        if next(tau_rows,None) is not None:raise ValueError('Unexpected extra tau rows')
    stage=Path(r'F:\pytorch\Research\stage0_himawari\cache\staging')/('extended_paired_'+run.name+'_overflow_replay')
    if any(p.is_file() for p in stage.rglob('*')):raise ValueError('Owned temporary staging files remain')
    for ref in evidence:c.verify(ref)
    c.write(dest/'original_replay_evidence_manifest.json',{'utc':c.now(),'files':evidence})
    c.write(dest/'immutability_after.json',immutable)
    result={'status':'EXACT_NUMERICAL_REPRODUCTION_VERIFIED_WITH_CLOSEOUT_ERROR','utc':c.now(),
        'scope':'READ_ONLY_POSTPROCESSING_NO_REPLAY','original_execution_status':'REPRODUCTION_FAILURE',
        'original_terminal_error_preserved':c.pin(run/'replay_reconciliation.json'),
        'original_terminal_progress_preserved':c.pin(run/'progress.json'),
        'numerical_reproduction_verified':True,'successful_updates':replay['successful_updates'],
        'failed_forward_batch':c.FAIL_BATCH,'exception':c.ERROR,'exact_matches':replay['exact_matches'],
        'tolerance':0,'wall_seconds_excluded':True,'original_counts':counts,
        'postprocessing_forward_calls':0,'postprocessing_backward_calls':0,'postprocessing_optimizer_steps':0,
        'postprocessing_checkpoint_deserializations':0,'postprocessing_raw_source_opens':0,
        'restored_state_identities':gate['state_hashes'],'scheduler':gate['scheduler'],
        'epoch_5_permutation_sha256':gate['epoch_5_permutation_sha256'],'tau_csv_rows_verified':tau_count,
        'source_journal_audit':sources,'immutable_history':immutable,'staging_cleanup_success':True,
        'clone_final_model_state_sha256':'NOT_CAPTURED_DUE_TO_ORIGINAL_CLOSEOUT_ERROR',
        'clone_final_optimizer_state_sha256':'NOT_CAPTURED_DUE_TO_ORIGINAL_CLOSEOUT_ERROR',
        'formal_resume_authorized':False,'B1_PHASE_B_STARTED':False,'RESEARCHER_DECISION_REQUIRED':True,
        'explanation':'The replay had already completed exact numeric reconciliation and captured the expected forward exception. Hashing earlier completed checkpoints during closeout conflicted with its LAST-only checkpoint read guard. This independent process verifies bytes and saved journals, without reconstructing or updating a model. Original failure status is not rewritten.'}
    c.write(dest/'readonly_reconciliation.json',result)
    print(json.dumps({k:result[k] for k in ('status','successful_updates','failed_forward_batch','tau_csv_rows_verified')}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True,type=Path);args=p.parse_args();close(args.run)
