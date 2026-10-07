"""Allowlisted text publication from a separate checkout; failures stay queued."""
from pathlib import Path
import json
import subprocess
import time
from yuntapr.training.phase_a_audit_v2 import atomic_json, append_event, digest


def publish(repository, public, *, expected_remote='https://github.com/flyeagle-cex/YunTAPR-Net.git'):
    repo, public = Path(repository).resolve(), Path(public).resolve()
    if not public.is_relative_to(repo / 'docs'):
        raise PermissionError('Only repository docs evidence may be published')
    def git(*args):
        return subprocess.check_output(['git','-c','core.longpaths=true','-c','http.version=HTTP/1.1',*args],cwd=repo).decode().strip()
    if git('remote','get-url','origin') != expected_remote or git('branch','--show-current') != 'main':
        raise PermissionError('Exact GitHub main destination required')
    allowed = {'checkpoint_registry.json','last_checkpoint_identity.json','best_checkpoint_identity.json',
               'training_validation_history.json','final_report.json','pair_training_completed.json'}
    paths = [p for p in public.rglob('*.json') if p.name in allowed or
             (p.name.startswith('epoch_') and p.name.endswith(('_report.json','_complete.json')))]
    if not paths: return {'status':'NOTHING_TO_PUBLISH'}
    names = [p.relative_to(repo).as_posix() for p in sorted(paths)]
    if set(git('diff','--cached','--name-only').splitlines()) - set(names):
        raise PermissionError('Publisher refuses unrelated staged content')
    for p in paths:
        if p.stat().st_size > 50 * 1024**2: raise ValueError('Text artifact too large for automatic publication')
        json.loads(p.read_text(encoding='utf-8'))
    before = {str(p):digest(p) for p in paths}
    git('add','--',*names)
    staged = git('diff','--cached','--name-only').splitlines()
    if set(staged)-set(names): raise PermissionError('Staging scope changed')
    if staged: git('commit','-m','Register completed v2 Phase-A epoch evidence')
    git('push','origin','main')
    local=git('rev-parse','HEAD'); remote=git('ls-remote','origin','refs/heads/main').split()[0]
    if local != remote: raise RuntimeError('Remote publication not verified')
    return {'status':'PUSHED_AND_REMOTE_VERIFIED','commit':local,'artifact_sha256':before}


def watch(repository, public, stop_file):
    """Independent observer, never imports or modifies a model/optimizer."""
    public=Path(public); last=None
    while True:
        fingerprint=[(str(p),p.stat().st_mtime_ns) for p in public.rglob('*.json')
                     if p.name.endswith(('_report.json','_complete.json')) or p.name=='pair_training_completed.json']
        if fingerprint != last:
            try:
                result=publish(repository,public)
                append_event(public/'publication_attempts.jsonl','PUBLICATION_RESULT',**result)
                last=fingerprint
            except Exception as exc:
                append_event(public/'publication_attempts.jsonl','PUBLICATION_FAILED_PENDING',error=repr(exc))
        if Path(stop_file).exists():
            try:
                result=publish(repository,public)
                atomic_json(public/('publication_final_'+str(time.time_ns())+'.json'),result,immutable=True)
            except Exception as exc:
                append_event(public/'publication_attempts.jsonl','FINAL_PUBLICATION_PENDING',error=repr(exc))
            return
        time.sleep(30)
