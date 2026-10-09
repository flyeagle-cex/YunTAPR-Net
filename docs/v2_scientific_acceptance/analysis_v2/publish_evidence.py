"""Explicit evidence allowlist with byte-accurate staged content audit."""
import json,hashlib,subprocess,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parents[1]
OUT=ROOT/'runs/run_20261009T112710_013267Z/delivery_v2'
def git(*args):return subprocess.check_output(['git','-c','core.longpaths=true',*args],cwd=REPO)
def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',action='store_true');args=p.parse_args()
    manifest=json.loads((OUT/'acceptance_manifest.json').read_text(encoding='utf-8'))
    allow={r['repository_path']:r['sha256'] for r in manifest['artifacts']}
    for path in [OUT/'acceptance_manifest.json',ROOT/'analysis_v2/monitor.py',Path(__file__).resolve()]:allow[path.relative_to(REPO).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    assert git('branch','--show-current').strip()==b'main'
    assert git('rev-parse','HEAD').strip()==b'166b1f86291bbcde167dbec30d3ae43ac23bba4c'
    assert not git('diff','--name-only')
    for rel,sha in allow.items():
        assert rel.startswith('docs/v2_scientific_acceptance/') and Path(rel).suffix not in {'.pt','.pth','.ckpt'}
        assert hashlib.sha256((REPO/rel).read_bytes()).hexdigest()==sha
        assert (REPO/rel).stat().st_size<90_000_000
    spec=OUT/'publication_allowlist.paths'
    with spec.open('xb') as f:f.write(b'\0'.join(r.encode() for r in sorted(allow))+b'\0')
    if args.stage:
        assert not git('diff','--cached','--name-only','-z')
        git('add','-f','--pathspec-from-file='+str(spec),'--pathspec-file-nul')
        staged=git('diff','--cached','--name-only','-z').decode('utf-8').rstrip('\0').split('\0')
        assert set(staged)==set(allow)
        for rel in staged:assert hashlib.sha256(git('show',':'+rel)).hexdigest()==allow[rel]
    with (OUT/'publication_staged_byte_audit.json').open('x',encoding='utf-8') as f:json.dump({'status':'PASS' if args.stage else 'PREPARED_NOT_STAGED','files':allow,'staged_blob_bytes_equal_working_bytes':args.stage,'no_historical_file_changed':True,'no_checkpoint_binary':True,'scope':'Only new independent scientific acceptance artifacts; no automatic training/resume'},f,indent=2)
    print(len(allow),'files; total bytes',sum((REPO/r).stat().st_size for r in allow))
if __name__=='__main__':main()
