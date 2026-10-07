"""Snapshot observed formal start from audit logs; never opens raw/model binaries."""
import hashlib,json
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[2]
AUTH=ROOT/'docs/v2_phase_a_authorized/pair_20261007T070503_825794Z'
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,value):
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
def main():
    a=load(AUTH/'authorization.json');public=Path(a['publication_root'])
    progress=load(public/'B0_MATCHED_V2/progress.json')
    assert progress['status']=='RUNNING' and progress['counters']['scope']=='FORMAL'
    assert progress['counters']['OPTIMIZER_STEPS']>0
    root=Path(a['checkpoint_roots']['B0_MATCHED_V2'])/a['run_ids']['B0_MATCHED_V2']
    prov=list(root.glob('audit/run_*/provenance.json'));assert len(prov)==1
    provenance=load(prov[0]);assert provenance['initialization']['models']==a['initial_state_sha256']
    assert provenance['code_sha256']==a['code_sha256']
    io=[];opens=0
    allowed=load(ROOT/'docs/v2_phase_a_execution/runs/run_20261007T031200_000001Z/source_allowlist.json')
    for log in sorted(root.glob('audit/run_*/raw_access_*.jsonl')):
        raw=log.read_bytes();lines=raw.splitlines(keepends=True);complete=[x for x in lines if x.endswith(b'\n')]
        for line in complete:
            e=json.loads(line)
            if e['event']=='RAW_SOURCE_OPEN_COMPLETED':assert e['path'] in allowed;opens+=1
            if e['event']=='NATIVE_DECODE' and e['source']!='FROZEN_STATIC_MASK':assert e['source'] in allowed
            assert not e['event'].startswith('DENIED')
        io.append({'path':str(log),'snapshot_bytes':len(raw),'snapshot_sha256':hashlib.sha256(raw).hexdigest(),'complete_lines':len(complete),'partial_trailing_lines':len(lines)-len(complete)})
    status={'observed_utc':datetime.now(timezone.utc).isoformat(),'pair_id':a['pair_id'],
        'V2_SCIENTIFIC_FREEZE_APPROVED':True,'FORMAL_TRAINING_AUTHORIZED':True,'V2_PHASE_A_AUTHORIZED':True,'V2_PHASE_A_STARTED':True,
        'V2_PHASE_B_AUTHORIZED':False,'2025_RAW_ACCESS':0,'2025_PIXELS_READ':0,
        'B0_MATCHED_V2_STATUS':'RUNNING','B1_V2_STATUS':'WAITING_FOR_B0_NORMAL_COMPLETION',
        'B1_V2_STARTED':False,'formal_counters':{'FORMAL_'+k:v for k,v in progress['counters'].items() if k!='scope'},
        'FORMAL_RAW_SOURCE_OPENS':opens,'raw_count_scope':'Completed logged events at observation; may include prefetched samples; not final counters',
        'progress_snapshot':progress,'io_log_snapshots':io,'provenance_path':str(prov[0]),'provenance_sha256':hashlib.sha256(prov[0].read_bytes()).hexdigest(),
        'authorization_commit':load(AUTH/'remote_launch_verification.json')['authorization_commit'],
        'full_goal_complete':False,'next_completion_requirement':'Both Phase-A models plus complete read-only paired review packet; STOP before Phase-B'}
    save(AUTH/'formal_start_status.json',status)
    save(AUTH/'B0_initial_provenance_snapshot.json',provenance)
    print(json.dumps({'status':'FORMAL_START_OBSERVED','epoch':progress['epoch'],'step':progress['step'],'formal_optimizer_steps':progress['counters']['OPTIMIZER_STEPS']}))
if __name__=='__main__':main()
