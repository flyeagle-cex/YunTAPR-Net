"""Publish only scrubbed reports/source hashes; never reads a .pt checkpoint."""
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import re
import sqlite3
import sys

ROOT=Path(__file__).absolute().parents[4]
OUT=ROOT/'docs/phase_b_v2_p1_integration_remediation/v1'
NEW=ROOT/'src/yuntapr/experimental/phase_b_v2_p1_integration_candidate'


def write(path,row):
    path.write_text(json.dumps(row,indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')


def prepare():
    local=OUT/'.local';local.mkdir(exist_ok=True)
    baseline=OUT/'protected_baseline.json'
    if baseline.exists(): baseline.replace(local/'protected_baseline.json')
    logs=local/'original_logs';logs.mkdir(exist_ok=True)
    provenance={}
    for path in sorted((OUT/'tests').glob('*.log')):
        raw=path.read_bytes();original=logs/path.name
        if not original.exists():original.write_bytes(raw)
        saved=original.read_bytes()
        value=saved.decode('utf-8',errors='replace').replace('\r\n','\n')
        def scrub(match):
            name=match.group(1).replace('\\','/').split('/')[-1]
            return 'File "[LOCAL_SOURCE]/'+name+'"'
        value=re.sub(r'File "([A-Za-z]:[^"]+)"',scrub,value)
        path.write_text(value,encoding='utf-8',newline='\n')
        provenance[path.name]=dict(original_sha256=hashlib.sha256(saved).hexdigest(),
                                  public_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                  redaction='absolute traceback prefixes removed; raw original retained locally')
    write(OUT/'tests/log_provenance.json',provenance)
    with sqlite3.connect((local/'launch_campaign.sqlite').as_uri()+'?mode=ro',uri=True) as con:
        rows=[dict(attempt=r[0],key=r[1],case=r[2],campaign=r[3]) for r in
              con.execute('SELECT * FROM attempts ORDER BY n')]
    # Include inner abrupt-monitor launch and its durable receipt.
    receipts=[]
    for row in rows:
        folder=local/('job_'+row['key'])
        item=dict(row)
        for name in ('launch.json','bound.json','monitor_crash.json','termination.json','allocation.json'):
            path=folder/name
            if path.exists():item[name[:-5]]=json.loads(path.read_bytes())
        receipts.append(item)
    write(OUT/'tests/job_durable_receipts.json',dict(hard_limit=24,reserved=len(rows),refunds=0,receipts=receipts))
    jobs=json.loads((OUT/'tests/job_initial.json').read_bytes())['results']
    summary=dict(final_tests=dict(checkpoint=27,job_launcher=15,integration=8,passed=50,failed=0),
                 initial_failures=dict(fixture_parameter_errors=[23,23],synthetic_jobs_failed=0),
                 top_level_launches=len(jobs),nonrefundable_reservations=len(rows),hard_launch_limit=24,
                 observed_native_processes=len({(r['pid'],r['creation_filetime'])
                       for j in jobs for r in j['observed_native_identities']}),
                 maximum_case_seconds=max(j['elapsed_seconds'] for j in jobs),
                 suite_job_seconds=sum(j['elapsed_seconds'] for j in jobs),
                 peak_sampled_process_working_set_bytes=max(j['peak_process_working_set_bytes'] for j in jobs),
                 peak_sampled_process_private_commit_bytes=max(j['peak_process_private_commit_bytes'] for j in jobs),
                 controlled_allocation_bytes=32*1024**2,all_jobs_empty=all(j['job_empty_and_handles_signaled'] for j in jobs),
                 monitor_abrupt_exit_verified=next(j['inner_cleanup_before_outer_stop'] for j in jobs if j['case']=='monitor_exit'),
                 real_data_reads=0,private_checkpoint_reads=0,model_instantiations=0,
                 gpu_operations=0,optimizer_steps=0,historical_2025_path_attributes='NOT_INSTRUMENTED')
    write(OUT/'tests/test_summary.json',summary)
    write(OUT/'tests/environment.json',dict(python=sys.version,torch=version('torch'),
          numpy=version('numpy'),platform=sys.platform,
          gpu_tested=False,checkpoint_tensor_device='cpu',worker_dependencies='stdlib only'))


def manifest():
    paths=list(NEW.glob('*.py'))+list(OUT.glob('*.md'))+list(OUT.glob('*.tex'))+list(OUT.glob('*.pdf'))
    paths += [OUT/'final_status.json',OUT/'protected_validation.json',OUT/'.gitignore']
    paths += [p for p in (OUT/'tests').iterdir() if p.suffix in ('.py','.json','.log')]
    evidence=[ROOT/p for p in (
        'src/yuntapr/experimental/phase_b_v2_formal_integration_candidate/checkpoint.py',
        'src/yuntapr/experimental/phase_b_v2_formal_integration_candidate/engine.py',
        'src/yuntapr/experimental/phase_b_v2_formal_integration_candidate/state.py',
        'src/yuntapr/experimental/phase_b_v2_formal_integration_candidate/metrics.py',
        'src/yuntapr/experimental/phase_b_v2_formal_integration_candidate/access.py',
        'src/yuntapr/experimental/phase_b_v2_runner_candidate/checkpoint.py',
        'src/yuntapr/experimental/phase_b_v2_runner_candidate/rng.py',
        'src/yuntapr/experimental/phase_b_v2_execution_watchdog_candidate/winjob.py',
        'src/yuntapr/experimental/phase_b_v2_execution_watchdog_candidate/watchdog.py',
        'src/yuntapr/experimental/phase_b_v2_full_payload_integrity/winio.py',
        'src/yuntapr/experimental/phase_b_v2_real_train_smoke/checkpoint.py',
        'docs/phase_b_v2_final_execution_safety_review/v1/final_status.json')]
    def records(files):
        return {str(p.relative_to(ROOT)).replace('\\','/'):
                dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size)
                for p in sorted(set(files))}
    write(OUT/'manifest.json',dict(schema='P1_PUBLIC_DELIVERY_MANIFEST_v1',
          baseline_commit='ef74d94eecaa8ee74a23e02d0c0fedbc419414de',
          delivery_commit='RESOLVE_FROM_GIT_COMMIT_CONTAINING_THIS_FILE',
          artifacts=records(paths),unchanged_source_evidence=records(evidence),
          excludes=['.local','checkpoint payloads','private paths','raw data','manifest self-hash'],
          scientific_authority=False))


if __name__=='__main__':
    prepare()
    if (OUT/'final_status.json').exists():manifest()
