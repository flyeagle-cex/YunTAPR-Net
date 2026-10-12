"""Archive one unlaunched release and pin the narrowed public scope metadata.

No new launch/campaign, quota mutation, permission creation, or extra budget.
"""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).absolute().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from yuntapr.training.phase_b_v2_seed2026_resume_v1.protocol import OUT,LOCAL,code_identity,atomic_json

def main():
    for path in (LOCAL/'launch.once',ROOT/'.git/phase_b_v2_seed2026_epoch3_recovery_20261013_v1.once',
                 ROOT/'.git/phase_b_v2_seed2026_epoch3_recovery_20261013_v1.sqlite'):
        if path.exists():raise PermissionError('NO_SOURCE_REPIN_AFTER_LAUNCH_OR_RESERVATION')
    old=(OUT/'release.json').read_bytes()
    with (OUT/'release_prepublication_001.json').open('xb') as stream:stream.write(old)
    row=json.loads(old);identity=code_identity()
    row.update(source_commit=identity['commit'],source_sha256=identity['sha256'],source_pins=identity['pins'])
    row['prepublication_change']='Remove unscoped approval flags; explicit previously approved recovery scope and all budgets unchanged'
    atomic_json(OUT/'release.json',row)
    status=json.loads((OUT/'final_status.json').read_bytes())
    status['source_commit']=identity['commit'];status['prepublication_versions_preserved']=True
    atomic_json(OUT/'final_status.json',status)
    print(json.dumps({'status':'UNLAUNCHED_SCOPE_PINNED','source_commit':identity['commit']}))

if __name__=='__main__':main()
