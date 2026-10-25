"""Local read-only inventory and checkpoint hashing; no deserialization."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import re
import sqlite3
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def git(repo, *args):
    r = subprocess.run(['git', '-c', 'core.longpaths=true', '-C', str(repo), *args], capture_output=True, text=True, encoding='utf-8', errors='replace')
    return dict(returncode=r.returncode, output=r.stdout.strip(), stderr=r.stderr.strip())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--workspace', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--private-output', type=Path, required=True)
    p.add_argument('--checkpoint-root', type=Path, action='append', default=[])
    p.add_argument('--process-receipt', type=Path)
    a = p.parse_args()
    if not a.private_output.resolve().is_relative_to(ROOT/'docs/research_readiness/.local'):
        p.error('Private inventory must remain ignored')
    repos = []
    private = []
    extra = []
    checkpoint_inventory = []
    for repo in sorted(a.workspace.iterdir()):
        if not repo.is_dir() or not (repo/'.git').exists():
            continue
        head, branch, status = [git(repo, *args) for args in [('rev-parse', 'HEAD'), ('branch', '--show-current'), ('status', '--porcelain')]]
        dirty = status['output'].splitlines()
        repos.append(dict(alias=repo.name, commit=head['output'], branch=branch['output'] or 'DETACHED',
                          changed_entries=len(dirty), status_exitcode=status['returncode'], status_warning=bool(status['stderr'])))
        private.append(dict(path=str(repo), status=status))
        # Metadata scope only. Do not crawl raw satellite/2025 input directories.
        for scope in ('docs/core_stage4/.local', 'docs/core_stage3/.local', 'docs/phase_b_v2_formal_execution'):
            folder = repo/scope
            if folder.exists():
                for name in ('completion.json', '*LAST*.receipt.json'):
                    for receipt in sorted(folder.rglob(name)):
                        d = json.loads(receipt.read_text(encoding='utf-8-sig'))
                        extra.append(dict(repo_alias=repo.name, path=receipt.relative_to(repo).as_posix(),
                                          sha256=sha(receipt), status=d.get('status'),
                                          model=d.get('model'), epoch=d.get('epoch'), updates=d.get('updates')))
        # Tracked result/config names expose preparation-only seeds as such.
        tracked = git(repo, 'ls-files', '*B2*', '*b2*', '*s2030*', '*s2031*', '*seed2030*', '*seed2031*')
        private[-1]['candidate_paths'] = tracked['output'].splitlines()
    for folder in a.checkpoint_root:
        if not folder.is_dir():
            checkpoint_inventory.append(dict(root_alias=folder.name, status='NOT_PRESENT'))
            continue
        for extension in ('*.pt', '*.pth', '*.ckpt'):
            for cp in folder.rglob(extension):
                checkpoint_inventory.append(dict(root_alias=folder.name, relative_path=cp.relative_to(folder).as_posix(), bytes=cp.stat().st_size))
    run = a.workspace/'YunTAPR-seed2029-recovery-20261024/docs/core_stage4/.local/seed2029_recovery1_20261024_v1'
    last = {}
    for model in ('B3', 'B4'):
        cp = run/f'{model}_LAST_epoch_09.pt'
        receipt = json.loads(cp.with_suffix('.receipt.json').read_text(encoding='utf-8'))
        found = sha(cp)
        if found != receipt['checkpoint_sha256']:
            raise ValueError('LAST file does not match historical receipt')
        last[model] = dict(epoch=9, bytes=cp.stat().st_size, sha256=found,
                           status='FILE_HASH_MATCHES_RECEIPT', deserialized=False)
    ledgers = {}
    for alias, folder in [('original', a.workspace/'YunTAPR-seed2029-launch-prep-20261024/docs/core_stage4/.local/seed2029_formal_20261024_v1'), ('recovery', run)]:
        path = folder/'updates.sqlite'
        before = sha(path)
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True) as db:
            db.execute('PRAGMA query_only=ON')
            rows = list(db.execute('SELECT model,state,COUNT(*),MIN(u),MAX(u) FROM updates GROUP BY model,state'))
        if sha(path) != before:
            raise ValueError('Read-only ledger changed')
        ledgers[alias] = dict(sha256=before, rows=rows)
    process_time = None
    if a.process_receipt:
        observation = json.loads(a.process_receipt.read_text(encoding='utf-8-sig'))
        if observation['status'] != 'VERIFIED_LOCAL_PROCESS_SNAPSHOT':
            raise ValueError('Process observation is not verified')
        procs = observation['processes']
        process_status = 'VERIFIED_FROM_EXPLICIT_READ_ONLY_CIM_RECEIPT'
        process_time = observation['observed_at']
        private.append(dict(process_receipt_path=str(a.process_receipt), sha256=sha(a.process_receipt)))
        process_stderr = ''
    else:
        observed = subprocess.run(['powershell', '-NoProfile', '-Command',
            "$ErrorActionPreference='Stop'; @(Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python|wsl|ssh|train' } | Select-Object ProcessId,ParentProcessId,Name,CommandLine) | ConvertTo-Json -Depth 3"], capture_output=True, text=True, encoding='utf-8', errors='replace')
        process_status = 'VERIFIED' if observed.returncode == 0 and not observed.stderr.strip() else 'NOT_VERIFIED_ACCESS_LIMIT'
        procs = json.loads(observed.stdout) if process_status == 'VERIFIED' and observed.stdout.strip() else []
        process_stderr = observed.stderr
    if isinstance(procs, dict):
        procs = [procs]
    private.append(dict(process_observation=procs, stderr=process_stderr))
    gpu = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total,memory.used,utilization.gpu', '--format=csv'], capture_output=True, text=True)
    main_docs = {}
    # Verified against GitHub main blob identities returned by the connected tool.
    expected = {'CURRENT_STATUS.md': '509ca24dd466296a40985f42efc7d20b6c6405a1',
                'SCIENTIFIC_RESULTS.md': '48b3704f75783873e287ab090c6e97ac5188db3f',
                'EXPERIMENT_MATRIX.csv': '4e8e0a67f3a1d86fe217da8f3878bb123ae43ca2',
                'EVIDENCE_INDEX.md': '7a1621c0bb9081448120eacb5fea7c3dadae5027'}
    for name, blob in expected.items():
        data = (ROOT/'docs/research_progress'/name).read_bytes()
        local_blob = hashlib.sha1(f'blob {len(data)}\0'.encode()+data).hexdigest()
        if local_blob != blob:
            raise ValueError('Copied public evidence differs from GitHub main: '+name)
        main_docs[name] = dict(git_blob_sha1=blob, sha256=hashlib.sha256(data).hexdigest())
    summary = dict(status='READ_ONLY_AUDIT_COMPLETE_WITH_STATED_SCOPE',
                   as_of=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec='seconds'),
                   public_main_commit='6c505d0ec63ed39f679720b82a65f601139dcd35', github_main_files=main_docs,
                   repositories=repos, discovered_completion_and_LAST_metadata=extra,
                   checkpoint_inventory=checkpoint_inventory, verified_E9_checkpoints=last, update_ledgers=ledgers,
                   process_status=process_status, process_observed_at=process_time,
                   matching_process_count=None if process_status.startswith('NOT_VERIFIED') else len(procs),
                   matching_processes=[dict(name=q['Name'], pid=q['ProcessId']) for q in procs],
                   gpu_snapshot=gpu.stdout.strip(), scope='Local named workspaces and declared checkpoint roots; no claim about other hosts',
                   raw_weather_reads=0, checkpoint_loads=0, checkpoint_hash_bytes=sum(v['bytes'] for v in last.values()),
                   new_formal_updates=0, source_data_deleted=0, historical_weights_overwritten=0)
    save(a.private_output, private)
    save(a.output, summary)
    print(json.dumps(dict(status=summary['status'], repos=len(repos), metadata_receipts=len(extra), checkpoint_files=len(checkpoint_inventory),
                          checkpoint_hashes='PASS', process_status=process_status, matching_process_count=summary['matching_process_count'], raw_weather_reads=0)))


if __name__ == '__main__':
    main()
