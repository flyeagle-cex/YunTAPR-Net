"""Derive the authorized v4 delta without rewriting any predecessor source."""
from pathlib import Path
import json

ROOT=Path(__file__).absolute().parents[2]
OLD='phase_b_v2_seed2027_b1_epoch7_recovery_v3'
NEW='phase_b_v2_seed2027_b1_epoch7_recovery_v4'


def write(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8',newline='\n') as f:f.write(text)


def main():
    for area in ('src/yuntapr/training','scripts'):
        src=ROOT/area/OLD;dst=ROOT/area/NEW
        for path in src.iterdir():
            if path.suffix not in ('.py','.ps1'):continue
            text=path.read_text(encoding='utf-8').replace(OLD,NEW).replace('B1_EPOCH7_RECOVERY_V3','B1_EPOCH7_RECOVERY_V4')
            text=text.replace('seed2027_b1_epoch7_recovery_v3','seed2027_b1_epoch7_recovery_v4')
            text=text.replace('B1_EPOCH7_ZERO_UPDATE_REISSUE_OS_TASK_V3_NO_RETRY','B1_EPOCH7_CONSOLE_FREE_RECOVERY_V4_NO_RETRY')
            if path.name=='protocol.py':
                text=text.replace('OLD_RESERVED=PRIOR_RESERVED','OLD_RESERVED=PRIOR_RESERVED')
                text=text.replace('ABANDONED=81735','ABANDONED=82657')
                text=text.replace('prior165383 + remaining198664 = 364047','prior166305 + remaining198664 = 364969')
                text=text.replace("SEED2027_HUMAN_AUTHORIZED_B1_EPOCH7_RECOVERY_v3","SEED2027_HUMAN_AUTHORIZED_B1_EPOCH7_RECOVERY_v4")
                text=text.replace("release.get('additional_replay_attempts')!=0","release.get('additional_replay_attempts')!=922")
                text=text.replace("'scripts/phase_b_v2_live_monitor_b1_epoch7_v2'","'scripts/phase_b_v2_live_monitor_b1_epoch7_v4','scripts/phase_b_v2_live_monitor_b1_epoch7_v2'")
            if path.name=='accounting.py':
                text=text.replace('165383','166305').replace('165382','166304').replace('364047','364969').replace('81735','82657')
            if path.name=='checkpoint.py':text=text.replace('RECOVERY_LAST_v3','RECOVERY_LAST_v4')
            if path.name=='release_check.py':text=text.replace('PRIOR_165383_CHARGED_REPLAY_548','PRIOR_166305_CHARGED_REPLAY_922')
            if path.name=='task_owner.py':text=text.replace('B1E7V3','B1E7V4')
            write(dst/path.name,text)
    out=ROOT/'docs/phase_b_v2_formal_execution/seed2027_b1_epoch7_recovery_v4'
    out.mkdir(parents=True,exist_ok=True);(out/'.local').mkdir(exist_ok=True)
    original=ROOT/'docs/phase_b_v2_formal_execution/seed2027_b1_epoch7_recovery_v3'
    for name in ('config.json','.local/runtime.json'):
        target=out/name
        with target.open('xb') as f:f.write((original/name).read_bytes())
    write(out/'.gitignore','/.local/\n')
    old_view=ROOT/'scripts/phase_b_v2_live_monitor_b1_epoch7_v3'
    new_view=ROOT/'scripts/phase_b_v2_live_monitor_b1_epoch7_v4'
    for name in ('server.py','app.html','Open-Monitor.ps1'):
        text=(old_view/name).read_text(encoding='utf-8')
        text=text.replace(OLD,NEW).replace('53084','53085').replace('B1_EPOCH7_V3','B1_EPOCH7_V4').replace('B1E7V3','B1E7V4')
        text=text.replace('364047','364969').replace('165383','166305').replace('165382','166304').replace('81735','82657')
        write(new_view/name,text)
    write(new_view/'.gitignore','/.local/\n')
    for name in ('pin.py','test_monitor.py'):
        text=(ROOT/'tools'/OLD/name).read_text(encoding='utf-8').replace(OLD,NEW)
        text=text.replace('SEED2027_HUMAN_AUTHORIZED_B1_EPOCH7_RECOVERY_v3','SEED2027_HUMAN_AUTHORIZED_B1_EPOCH7_RECOVERY_v4')
        text=text.replace("additional_replay_attempts=0","additional_replay_attempts=922")
        text=text.replace("'scripts/phase_b_v2_live_monitor_b1_epoch7'","'scripts/phase_b_v2_live_monitor_b1_epoch7_v4'")
        write(ROOT/'tools'/NEW/name,text)


if __name__=='__main__':main()
