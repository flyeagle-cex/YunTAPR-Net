"""Copy the pinned runner into a new scope; never launch or change old evidence."""
from pathlib import Path
import json

ROOT=Path(__file__).absolute().parents[2]
OLD='phase_b_v2_seed2027_restart_v2'
NEW='phase_b_v2_seed2027_restart_v3'

def main():
    source=ROOT/'src/yuntapr/training'/OLD
    target=ROOT/'src/yuntapr/training'/NEW
    target.mkdir(exist_ok=False)
    for path in source.glob('*.py'):
        text=path.read_text(encoding='utf-8').replace(OLD,NEW)
        text=text.replace('seed2027_restart_v2','seed2027_restart_v3').replace('seed2027_fresh_restart_v2','seed2027_fresh_restart_v3')
        text=text.replace('SEED2027_FRESH_RESTART_V2','SEED2027_FRESH_RESTART_V3')
        text=text.replace('SEED2027_HUMAN_AUTHORIZED_FRESH_RESTART_v2','SEED2027_HUMAN_AUTHORIZED_FRESH_RESTART_v3')
        text=text.replace('SEED2027_FRESH_RESTART_1127_PLUS_282312_NO_RETRY','SEED2027_FRESH_RESTART_2087_PLUS_282312_NO_RETRY')
        if path.name=='accounting.py':
            text=text.replace('PRIOR_RESERVED=1127','PRIOR_RESERVED=2087').replace('PRIOR_VERIFIED=1126','PRIOR_VERIFIED=2086').replace('COMBINED_CAP=283439','COMBINED_CAP=284399')
        if path.name=='checkpoint.py':
            text=text.replace('_FRESH_RESTART_LAST_v2','_FRESH_RESTART_LAST_v3').replace("q['old_campaign_reserved']!=1127","q['old_campaign_reserved']!=2087").replace("q['old_campaign_returned_verified']!=1126","q['old_campaign_returned_verified']!=2086").replace("q['abandoned_old_updates']!=1127","q['abandoned_old_updates']!=2087")
        if path.name=='release_check.py':text=text.replace('PRIOR_1127_CHARGED','PRIOR_2087_CHARGED')
        (target/path.name).write_text(text,encoding='utf-8',newline='\n')
    scripts=ROOT/'scripts'/NEW;scripts.mkdir(exist_ok=False)
    for path in (ROOT/'scripts'/OLD).glob('*.ps1'):
        (scripts/path.name).write_text(path.read_text(encoding='utf-8').replace(OLD,NEW).replace('seed2027_restart_v2','seed2027_restart_v3'),encoding='utf-8',newline='\n')
    old=ROOT/'docs/phase_b_v2_formal_execution/seed2027_restart_v2'
    out=ROOT/'docs/phase_b_v2_formal_execution/seed2027_restart_v3'
    (out/'.local').mkdir(parents=True,exist_ok=False)
    (out/'config.json').write_bytes((old/'config.json').read_bytes())
    (out/'.local/runtime.json').write_bytes((old/'.local/runtime.json').read_bytes())
    print(json.dumps(dict(status='ISOLATED_NAMESPACE_CREATED_NO_TRAINING')))

if __name__=='__main__':main()
