"""Read-only evidence reconciliation; no ML imports or raw-source reads."""
import collections
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / 'docs/v2_phase_a_execution/runs/run_20261007T031200_000001Z'
OUT = RUN / 'finalization'
SCIENCE = 'd049f7ab7b8a382f47a5fe54384ea9416a22cde9'
IMPLEMENTATION = 'a1af0325b481202941c57e8fc94f3b20e441630a'
def git(*args):
    return subprocess.check_output(['git','-c','core.longpaths=true',*args],cwd=ROOT).decode('utf-8').strip()
def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()
def ident(p):
    p=Path(p)
    return {'absolute_local_path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)}
def write(name,value):
    with (OUT/name).open('x',encoding='utf-8',newline='\n') as f:
        json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
def walk(value):
    if isinstance(value,dict):
        yield value
        for v in value.values():yield from walk(v)
    elif isinstance(value,list):
        for v in value:yield from walk(v)

def main():
    assert git('rev-parse','HEAD')==IMPLEMENTATION
    assert not git('diff','--name-only','HEAD')
    assert not git('diff','--name-only','--diff-filter=MD',SCIENCE,IMPLEMENTATION)
    assert git('branch','--show-current')=='main'
    assert git('remote','get-url','origin')=='https://github.com/flyeagle-cex/YunTAPR-Net.git'
    m=read(RUN/'preflight_manifest.json');s=read(RUN/'gpu_smoke.json')
    tests=read(ROOT/'docs/v2_phase_a_execution/test_runs/run_20261007_full_004/test_summary.json')
    assert m['status']==s['status']==tests['status']=='PASS'
    assert m['science_baseline']==SCIENCE and m['working_commit']==IMPLEMENTATION
    assert len(s['cases'])==8 and tests['total_tests']==770
    for suite in tests['suites']:
        assert suite['counts']['run']==suite['counts']['passed'] and suite['counts']['skipped']==0
    assert s['ENGINEERING_OPTIMIZER_STEPS']==4 and s['FORMAL_OPTIMIZER_STEPS']==0
    assert s['temporary_checkpoint_files_remaining']==0
    for path,digest in m['code_sha256'].items():assert sha(ROOT/path)==digest,path
    assert m['code_sha256']==tests['code_sha256']
    bindings={}
    for path,key in [('config/science_v2/phase_a_protocol_frozen_v1.json','protocol_sha256'),('config/science_v2/quantile_head_v2_frozen_v1.json','head_sha256')]:
        assert sha(ROOT/path)==m[key];bindings[path]=ident(ROOT/path)
    protocol=read(ROOT/'config/science_v2/phase_a_protocol_frozen_v1.json')
    for name,ref in protocol['identity'].items():
        p=Path(ref['path']);p=p if p.is_absolute() else ROOT/p
        assert sha(p)==ref['sha256'],name
        bindings[name]=ident(p)
    assert bindings['normalization']['sha256']==m['normalization_sha256']
    assert read(RUN/'initialization_process_0.json')==read(RUN/'initialization_process_1.json')==m['paired_initialization']
    allowed=read(RUN/'source_allowlist.json');seen={};total_bytes=0
    for line in (RUN/'source_identity_checks.jsonl').read_text(encoding='utf-8').splitlines():
        row=json.loads(line);p=row['path'];assert p not in seen
        ref=allowed[p];assert row['event']=='SOURCE_IDENTITY_PASS' and row['sha256']==ref['sha256']
        assert ref['year'] in (2023,2024) and 3<=ref['month']<=10
        if ref['expected_bytes'] is not None:assert row['bytes']==ref['expected_bytes']
        seen[p]=row;total_bytes+=row['bytes']
    assert set(seen)==set(allowed) and len(seen)==67006
    counts=collections.Counter()
    for ref in m['io']['log_files']:
        p=Path(ref['absolute_local_path']);assert ident(p)==ref
        for line in p.read_text(encoding='utf-8').splitlines():
            e=json.loads(line);kind=e['event'];counts[kind]+=1
            if kind=='RAW_SOURCE_OPEN_COMPLETED':assert e['path'] in allowed
            if kind=='NATIVE_DECODE' and e['source'] not in allowed:
                assert e['source']=='FROZEN_STATIC_MASK'
                assert Path(e['path']).resolve()==Path(protocol['identity']['yunnan_mask']['path']).resolve()
            assert not kind.startswith('DENIED')
    assert counts['RAW_SOURCE_OPEN_COMPLETED']==m['io']['RAW_SOURCE_OPENS']
    assert counts['NATIVE_DECODE']==m['io']['NATIVE_DECODES']
    assert m['io']['2025_RAW_ACCESS']==m['io']['2025_PIXELS_READ']==0
    # All historical formal checkpoint bytes, never deserialize or apply state.
    refs={}
    for rel in git('ls-files','docs/formal_training','docs/paired_phase_a_authorized/runs/run_20261003T085834_735920Z/all_completed_checkpoint_inventory.json','docs/scientific_freeze_v2/runs/run_20261006T145404_426214Z/historical_inventory_before.json').splitlines():
        p=ROOT/rel
        if p.suffix!='.json':continue
        for item in walk(read(p)):
            name=item.get('absolute_local_path',item.get('path',''))
            if name.endswith('.pt') and 'sha256' in item:
                key=str(Path(name).resolve()).lower()
                if key in refs:assert refs[key]['sha256']==item['sha256']
                refs[key]=item
    checkpoints=[]
    for p in sorted(Path('F:/pytorch/Research/outputs/formal_training').rglob('*.pt')):
        ref=refs.get(str(p.resolve()).lower());assert ref is not None,('unregistered checkpoint',str(p))
        actual=ident(p);assert actual['sha256']==ref['sha256'] and actual['bytes']==ref['bytes'],str(p)
        checkpoints.append(actual)
    assert len(checkpoints)==54
    roots={k:'F:/pytorch/Research/outputs/formal_training/'+v for k,v in [('B0_MATCHED_V2','b0_matched_v2_phase_a'),('B1_V2','b1_v2_phase_a')]}
    for p in roots.values():assert not Path(p).exists(),'Unexpected formal v2 root'
    current_storage={k:{**v,'closure_free_bytes':shutil.disk_usage(k).free} for k,v in m['storage'].items()}
    assert all(v['closure_free_bytes']>=v['required_bytes'] for v in current_storage.values())
    OUT.mkdir(exist_ok=False)
    status={'ENGINEERING_PREFLIGHT_STATUS':'PASS','V2_SCIENTIFIC_FREEZE_APPROVED':True,
        'FORMAL_TRAINING_AUTHORIZED':False,'V2_PHASE_A_AUTHORIZED':False,'V2_PHASE_A_STARTED':False,
        'V2_PHASE_B_AUTHORIZED':False,'B0_MATCHED_PHASE_B_RESUME_AUTHORIZED':False,'B1_PHASE_B_STARTED':False,
        'FORMAL_OPTIMIZER_STEPS':0,'2025_RAW_ACCESS':0,'2025_PIXELS_READ':0,'RESEARCHER_DECISION_REQUIRED':True}
    write('authorization_status.json',status)
    write('preflight_final_status.json',{**status,'run_closed':True,'closed_utc':datetime.now(timezone.utc).isoformat(),
        'source_files_verified':67006,'gpu_smoke_passed':8,'gpu_smoke_total':8,'tests_passed':770,'tests_total':770,
        'engineering_optimizer_steps':4,'closure_added_optimizer_steps':0})
    write('source_sha_audit.json',{'status':'PASS','files_verified':67006,'bytes_verified':total_bytes,
        'method':'Reconcile completed SHA receipts to exact frozen allowlist; no raw reread during closure',
        'allowlist':ident(RUN/'source_allowlist.json'),'receipts':ident(RUN/'source_identity_checks.jsonl')})
    write('gpu_smoke_summary.json',{'status':'PASS','passed':8,'total':8,'engineering_optimizer_steps':4,
        'formal_optimizer_steps':0,'temporary_checkpoints_remaining':0,'evidence':ident(RUN/'gpu_smoke.json'),
        'cases':[{k:c[k] for k in ('model','case','metrics','counters','peak_allocated_bytes','peak_reserved_bytes')} for c in s['cases']]})
    write('storage_budget_audit.json',{'status':'PASS','storage':current_storage,'log_budget':read(RUN/'measured_log_storage_budget.json'),
        'checkpoint_bytes_budget':m['checkpoint_bytes_budget']})
    write('io_reconciliation.json',{**m['io'],'status':'PASS','events_recounted':dict(counts),
        'closure_raw_access':0,'closure_pixels_read':0,'checkpoint_reads':'SHA256 streaming only; no deserialization'})
    write('historical_integrity_audit.json',{'status':'PASS','baseline':SCIENCE,'implementation':IMPLEMENTATION,
        'tracked_baseline_files_modified_or_deleted':[], 'tracked_worktree_changes':[],
        'scope':'All Git-tracked historical evidence; all 54 files under registered formal_training checkpoint root',
        'checkpoint_count':len(checkpoints),'checkpoints':checkpoints,'checkpoint_comparison':'Fresh byte SHA256 and size against historical registered identities'})
    write('identity_verification.json',{'status':'PASS','science_commit':SCIENCE,'implementation_commit':IMPLEMENTATION,
        'bindings':bindings,'runner_code_sha256':m['code_sha256'],'paired_initialization':m['paired_initialization'],
        'formal_checkpoint_roots':roots,'v2_roots_not_created':True,
        'publication_checkout':str(ROOT),'publication_branch':'main','publication_remote':git('remote','get-url','origin')})
    artifacts=[ident(p) for p in sorted(OUT.glob('*.json'))]
    write('preflight_manifest.json',{'status':'PASS','scope':'ENGINEERING_PREFLIGHT_CLOSURE_ONLY',
        'original_preflight_manifest':ident(RUN/'preflight_manifest.json'),'test_evidence':ident(ROOT/'docs/v2_phase_a_execution/test_runs/run_20261007_full_004/test_summary.json'),
        'artifacts':artifacts,'authorization':status,'script':ident(Path(__file__)),
        'original_preflight_manifest_preserved':True,'self_hash':'Bound by Git publication commit'})
    for p in OUT.glob('*.json'):read(p)
    print(json.dumps({'status':'PASS','closed':str(OUT),'checkpoints_verified':len(checkpoints),'source_receipts':len(seen)}))

if __name__=='__main__':main()
