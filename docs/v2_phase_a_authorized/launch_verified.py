"""Remote-publication gate around the immutable runner. No training implementation."""
import argparse,hashlib,json,os,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def git(root,*args):return subprocess.check_output(['git','-c','core.longpaths=true','-c','http.version=HTTP/1.1',*args],cwd=root).decode('utf-8').strip()
def save(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
def main():
    p=argparse.ArgumentParser();p.add_argument('--authorization',type=Path,required=True);p.add_argument('--sha256',required=True);p.add_argument('--authorization-commit',required=True);p.add_argument('--verify-only',action='store_true');a=p.parse_args()
    assert sha(a.authorization)==a.sha256,'Authorization changed'
    auth=json.loads(a.authorization.read_text(encoding='utf-8'));repo=Path(auth['publication_repository']);execution=Path(auth['execution_checkout'])
    assert git(repo,'branch','--show-current')=='main'
    remote=git(repo,'ls-remote','origin','refs/heads/main').split()[0]
    # At launch, do not fetch or mutate either checkout; require exact published authorization HEAD.
    assert remote==git(repo,'rev-parse','HEAD')==a.authorization_commit,'Authorization commit not current remote main'
    rel=a.authorization.relative_to(repo).as_posix()
    recorded=subprocess.check_output(['git','show',a.authorization_commit+':'+rel],cwd=repo)
    assert hashlib.sha256(recorded).hexdigest()==a.sha256
    assert git(execution,'rev-parse','HEAD')==auth['execution_commit']
    assert not git(execution,'status','--porcelain','--untracked-files=normal')
    for rel,h in auth['code_sha256'].items():assert sha(execution/rel)==h,rel
    assert sha(auth['preflight_path'])==auth['preflight_sha256']
    assert sha(auth['test_summary_path'])==auth['test_summary_sha256']
    assert auth['FORMAL_TRAINING_AUTHORIZED'] and auth['V2_PHASE_A_AUTHORIZED'] and not auth['V2_PHASE_B_AUTHORIZED']
    for model,rid in auth['run_ids'].items():assert not (Path(auth['checkpoint_roots'][model])/rid).exists()
    assert not Path(auth['publication_root']).exists(),'Never restart a used fresh authorization'
    result={'status':'REMOTE_AUTHORIZATION_VERIFIED','authorization_commit':a.authorization_commit,'remote_main':remote,
        'authorization_sha256':a.sha256,'execution_commit':auth['execution_commit'],'verified_utc':datetime.now(timezone.utc).isoformat(),
        'V2_PHASE_B_AUTHORIZED':False,'2025_RAW_ACCESS':0,'2025_PIXELS_READ':0}
    if a.verify_only:print(json.dumps(result));return
    save(a.authorization.parent/'remote_launch_verification.json',result)
    env=os.environ.copy();env.update(PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1',PYTHONHASHSEED='2026',CUBLAS_WORKSPACE_CONFIG=':4096:8')
    command=[sys.executable,'-B',str(execution/'scripts/run_paired_phase_a_v2.py'),'train','--authorization',str(a.authorization),'--authorization-sha256',a.sha256]
    child=subprocess.Popen(command,cwd=execution,env=env)
    save(a.authorization.parent/'launch_process.json',{'pid':child.pid,'command':command,'pair_id':auth['pair_id'],'formal_started_claim':'Pending observed first formal forward/update',**result})
    rc=child.wait()
    save(a.authorization.parent/'process_exit.json',{'exit_code':rc,'utc':datetime.now(timezone.utc).isoformat(),
        'status':'RUNNER_EXITED_REVIEW_REQUIRED' if rc==0 else 'FAILED_STOP_NO_AUTOMATIC_RETRY','V2_PHASE_B_AUTHORIZED':False,
        'next_required_work':'Read-only completion audit and 2024 BEST paired comparison packet; no Phase-B'})
    raise SystemExit(rc)
if __name__=='__main__':main()
