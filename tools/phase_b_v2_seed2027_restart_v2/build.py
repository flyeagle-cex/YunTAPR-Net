"""Copy the pinned runner into a new scope; never launch or change old evidence."""
from pathlib import Path
import json

ROOT=Path(__file__).absolute().parents[2]
OLD='phase_b_v2_seed2027_restart_v1'
NEW='phase_b_v2_seed2027_restart_v2'

def main():
    source=ROOT/'src/yuntapr/training'/OLD
    target=ROOT/'src/yuntapr/training'/NEW
    target.mkdir(exist_ok=False)
    for path in source.glob('*.py'):
        text=path.read_text(encoding='utf-8').replace(OLD,NEW)
        text=text.replace('seed2027_restart_v1','seed2027_restart_v2').replace('seed2027_fresh_restart_v1','seed2027_fresh_restart_v2')
        text=text.replace('SEED2027_FRESH_RESTART_V1','SEED2027_FRESH_RESTART_V2')
        text=text.replace('SEED2027_HUMAN_AUTHORIZED_FRESH_RESTART_v1','SEED2027_HUMAN_AUTHORIZED_FRESH_RESTART_v2')
        text=text.replace('SEED2027_FRESH_RESTART_386_PLUS_282312_NO_RETRY','SEED2027_FRESH_RESTART_1127_PLUS_282312_NO_RETRY')
        if path.name=='protocol.py':
            text=text.replace("'tools/phase_b_v2_seed2027_restart']","'tools/phase_b_v2_seed2027_restart','tools/phase_b_v2_seed2027_restart_v2',\n           'scripts/phase_b_v2_seed2027_restart_v1']")
            text=text.replace('prior 386 +','prior 1127 +')
        if path.name=='accounting.py':
            text=text.replace('PRIOR_RESERVED=386','PRIOR_RESERVED=1127').replace('PRIOR_VERIFIED=385','PRIOR_VERIFIED=1126').replace('COMBINED_CAP=282698','COMBINED_CAP=283439')
        if path.name=='checkpoint.py':
            text=text.replace('_FRESH_RESTART_LAST_v1','_FRESH_RESTART_LAST_v2').replace("q['old_campaign_reserved']!=386","q['old_campaign_reserved']!=1127").replace("q['old_campaign_returned_verified']!=385","q['old_campaign_returned_verified']!=1126").replace("q['abandoned_old_updates']!=386","q['abandoned_old_updates']!=1127")
        if path.name=='release_check.py':text=text.replace('PRIOR_386_CHARGED','PRIOR_1127_CHARGED')
        (target/path.name).write_text(text,encoding='utf-8',newline='\n')
    scripts=ROOT/'scripts'/NEW;scripts.mkdir(exist_ok=False)
    for path in (ROOT/'scripts'/OLD).glob('*.ps1'):
        (scripts/path.name).write_text(path.read_text(encoding='utf-8').replace(OLD,NEW).replace('seed2027_restart_v1','seed2027_restart_v2'),encoding='utf-8',newline='\n')
    old=ROOT/'docs/phase_b_v2_formal_execution/seed2027_restart_v1'
    out=ROOT/'docs/phase_b_v2_formal_execution/seed2027_restart_v2'
    (out/'.local').mkdir(parents=True,exist_ok=False)
    (out/'config.json').write_bytes((old/'config.json').read_bytes())
    (out/'.local/runtime.json').write_bytes((old/'.local/runtime.json').read_bytes())
    print(json.dumps(dict(status='ISOLATED_NAMESPACE_CREATED_NO_TRAINING')))

if __name__=='__main__':main()
