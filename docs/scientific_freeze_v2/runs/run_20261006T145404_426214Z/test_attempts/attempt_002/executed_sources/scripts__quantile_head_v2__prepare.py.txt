"""Capture historical bytes and researcher authority, without loading a model."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from quantile_head_v2 import common as c
from datetime import datetime, timezone
import argparse
import json
import subprocess


def references(value):
    if isinstance(value, dict):
        if 'absolute_local_path' in value and 'sha256' in value:
            yield value
        for child in value.values():
            yield from references(child)
    elif isinstance(value, list):
        for child in value:
            yield from references(child)


def prepare():
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip() != c.BASELINE:
        raise ValueError('Baseline changed')
    if subprocess.check_output(['git','diff','--name-only'],cwd=ROOT):
        raise ValueError('Historical tracked files modified')
    run = c.RUN_ROOT / ('run_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    run.mkdir(parents=True)
    c.progress(run, 'HISTORICAL_IDENTITY_PREFLIGHT', status='RUNNING', tests_completed=0)
    source = Path(r'C:\Users\chenerxiao\.codex\attachments\54eec106-d994-4f93-abc4-54791155edbd\已粘贴的文本.txt')
    destination = run / 'researcher_task_original.txt'
    destination.write_bytes(source.read_bytes())
    c.write(run / 'authority.json', {'recorded_at_utc':c.now(), 'bound_commit':c.BASELINE,
        'task_source':c.pin(source), 'task_copy':c.pin(destination),
        'approval_evidence_type':'USER_CHAT_TRANSCRIPTION_NOT_ORIGINAL_MESSAGE_BYTES',
        'message_timestamp':'NOT_EXPOSED',
        'epsilon_confirmation':'批准候选数值，仅用于工程验证',
        'epsilon_scope':'epsilon_w = epsilon_span = 1e-4; not final scientific approval',
        'floating_point_confirmation':'批准区分数学与浮点保证',
        'floating_point_scope':'Real-arithmetic proof; FP64 production transform with rejection guards, no repair and no automatic batch skip',
        'FORMAL_TRAINING_AUTHORIZED':False, '2025_RAW_ACCESS':0})
    excluded = {'config/science_v2','docs/scientific_freeze_v2','scripts/quantile_head_v2',
                'src/yuntapr/models/quantile_v2','tests/quantile_head_v2'}
    paths = set()
    for folder in ('config','docs','src','scripts','tests'):
        for p in (ROOT/folder).rglob('*'):
            if not p.is_file() or '__pycache__' in p.parts or p.suffix == '.pyc': continue
            rel = p.relative_to(ROOT).as_posix()
            if not any(rel == x or rel.startswith(x+'/') for x in excluded): paths.add(p.resolve())
    checkpoint_refs = {}
    for p in sorted(paths):
        if 'checkpoint' not in p.name or p.suffix != '.json': continue
        for ref in references(c.read(p)):
            cp = Path(ref['absolute_local_path']).resolve()
            if cp.suffix.lower() not in ('.pt','.pth','.ckpt'): continue
            if not cp.is_relative_to(Path(r'F:\pytorch\Research\outputs\formal_training').resolve()):
                raise ValueError('Unexpected historical checkpoint root')
            if str(cp) in checkpoint_refs and checkpoint_refs[str(cp)]['sha256'] != ref['sha256']:
                raise ValueError('Conflicting checkpoint identity')
            checkpoint_refs[str(cp)] = ref
            paths.add(cp)
    refs = []
    for index, p in enumerate(sorted(paths)):
        ref = c.pin(p)
        wanted = checkpoint_refs.get(str(p))
        if wanted and (ref['sha256'] != wanted['sha256'] or ref['bytes'] != wanted['bytes']):
            raise ValueError('Historical checkpoint SHA/size mismatch: ' + str(p))
        refs.append(ref)
        if index % 100 == 0:
            c.progress(run, 'HISTORICAL_IDENTITY_PREFLIGHT', status='RUNNING',
                       historical_files_verified=index+1, historical_files_total=len(paths))
    c.write(run/'historical_inventory_before.json', {'utc':c.now(),'baseline':c.BASELINE,'files':refs,
        'description':'immutable historical baseline（不可变历史基线）：旧配置、代码、测试、报告及已登记 checkpoint（完整训练状态文件）仅做字节哈希，不反序列化。',
        'checkpoint_count':len(checkpoint_refs), 'checkpoint_deserializations':0})
    c.progress(run, 'READY_FOR_ENGINEERING_TESTS', status='READY', historical_files_verified=len(refs),
               historical_checkpoint_count=len(checkpoint_refs), tests_completed=0, formal_optimizer_steps_added=0, raw_2025_access=0)
    print(json.dumps({'run':str(run),'historical_files':len(refs),'checkpoint_count':len(checkpoint_refs)}),flush=True)


if __name__ == '__main__':
    prepare()
