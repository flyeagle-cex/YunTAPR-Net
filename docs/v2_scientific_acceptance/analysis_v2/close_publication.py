"""Verify published evidence commit; append a receipt, no old status overwrite."""
import json,subprocess,hashlib
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parents[1]
OUT=ROOT/'runs/run_20261009T112710_013267Z/delivery_v2'
def git(*args):return subprocess.check_output(['git','-c','core.longpaths=true',*args],cwd=REPO)
def main():
    head=git('rev-parse','HEAD').decode().strip();assert head=='bb7c25a8eb7147c70c94fe7aa6546a990342c417'
    remote=git('ls-remote','origin','refs/heads/main').decode().split()[0];assert head==remote
    changed=git('diff','--name-status','166b1f86291bbcde167dbec30d3ae43ac23bba4c',head).decode().splitlines()
    assert len(changed)==132 and all(line.startswith('A\tdocs/v2_scientific_acceptance/') for line in changed)
    assert not git('diff','--name-only')
    audit=json.loads((OUT/'publication_staged_byte_audit.json').read_text(encoding='utf-8'))
    for rel,sha in audit['files'].items():assert hashlib.sha256(git('show',head+':'+rel)).hexdigest()==sha
    manifest=json.loads((OUT/'acceptance_manifest.json').read_text(encoding='utf-8'))
    for ref in manifest['artifacts']:
        assert hashlib.sha256((REPO/ref['repository_path']).read_bytes()).hexdigest()==ref['sha256']
    receipt={'status':'GITHUB_MAIN_EVIDENCE_PUBLICATION_VERIFIED_STOP','verified_utc':datetime.now(timezone.utc).isoformat(),'evidence_commit':head,'remote_main_at_verification':remote,'github_commit_url':'https://github.com/flyeagle-cex/YunTAPR-Net/commit/'+head,'new_artifacts_published':132,'published_source_bytes_verified':131,'byte_audit_own_blob_bound_by_commit':True,'all_new_files_only':True,'historical_git_files_changed':0,'2025_RAW_ACCESS':0,'2025_PIXELS_READ':0,'MODEL_PARAMETERS_UPDATED':False,'BACKWARD_CALLS':0,'OPTIMIZER_STEPS':0,'FORMAL_OPTIMIZER_STEPS_ADDED':0,'V2_PHASE_B_AUTHORIZED':False,'RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED':True,'SCIENTIFIC_ACCEPTANCE_DECISION':'UNDECIDED','STOP':True,'next_action':'Researcher scientific review; no automatic subsequent stage','receipt_publication_note':'This append-only verification receipt is published in the following metadata-only commit; evidence commit identity remains fixed.'}
    with (OUT/'publication_verification.json').open('x',encoding='utf-8') as f:json.dump(receipt,f,ensure_ascii=False,indent=2)
    print(head,'verified against remote main; 132 new files only; no historical modification')
if __name__=='__main__':main()
