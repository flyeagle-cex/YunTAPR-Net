"""Derive the authorized v5 zero-update reissue from v4; fix the registration token."""
from pathlib import Path
import json

ROOT=Path(__file__).absolute().parents[2]
OLD='phase_b_v2_seed2027_b1_epoch7_recovery_v4'
NEW='phase_b_v2_seed2027_b1_epoch7_recovery_v5'


def write(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8',newline='\n') as f:f.write(text)


def main():
    for area in ('src/yuntapr/training','scripts'):
        src=ROOT/area/OLD;dst=ROOT/area/NEW
        for path in src.iterdir():
            if path.suffix not in ('.py','.ps1'):continue
            if path.name=='ancestor.py':continue  # rewritten separately for the v4 zero-update seal
            text=path.read_text(encoding='utf-8').replace(OLD,NEW)
            text=text.replace('seed2027_b1_epoch7_recovery_v4','seed2027_b1_epoch7_recovery_v5')
            text=text.replace('B1_EPOCH7_RECOVERY_V4','B1_EPOCH7_RECOVERY_V5')
            text=text.replace('B1_EPOCH7_CONSOLE_FREE_RECOVERY_V4_NO_RETRY','B1_EPOCH7_CONSOLE_FREE_RECOVERY_V5_NO_RETRY')
            text=text.replace('ONLY_DIRECTLY_APPROVED_SEED2027_EPOCH7_RECOVERY_V4','ONLY_DIRECTLY_APPROVED_SEED2027_EPOCH7_RECOVERY_V5')
            if path.name=='protocol.py':
                text=text.replace('SEED2027_HUMAN_AUTHORIZED_B1_EPOCH7_RECOVERY_v4','SEED2027_HUMAN_AUTHORIZED_B1_EPOCH7_RECOVERY_v5')
                text=text.replace("'scripts/phase_b_v2_live_monitor_b1_epoch7_v4'","'scripts/phase_b_v2_live_monitor_b1_epoch7_v5','scripts/phase_b_v2_live_monitor_b1_epoch7_v4'")
                text=text.replace("'tools/phase_b_v2_seed2027_b1_epoch7_recovery_v5']","'tools/phase_b_v2_seed2027_b1_epoch7_recovery_v5','scripts/phase_b_v2_seed2027_b1_epoch7_recovery_v4','tools/phase_b_v2_seed2027_b1_epoch7_recovery_v4']")
            if path.name=='checkpoint.py':text=text.replace('RECOVERY_LAST_v4','RECOVERY_LAST_v5')
            if path.name=='release_check.py':text=text.replace('PRIOR_166305_CHARGED_REPLAY_922','PRIOR_166305_CHARGED_REPLAY_922_ZERO_UPDATE_REISSUE_V5')
            if path.name=='task_owner.py':
                text=text.replace('B1E7V4','B1E7V5')
                text=text.replace('gui=true','gui=$true')  # runtime CommandNotFound fix
            write(dst/path.name,text)
    out=ROOT/'docs/phase_b_v2_formal_execution/seed2027_b1_epoch7_recovery_v5'
    out.mkdir(parents=True,exist_ok=True);(out/'.local').mkdir(exist_ok=True)
    original=ROOT/'docs/phase_b_v2_formal_execution/seed2027_b1_epoch7_recovery_v4'
    for name in ('config.json','.local/runtime.json'):
        target=out/name
        with target.open('xb') as f:f.write((original/name).read_bytes())
    write(out/'.gitignore','/.local/\n')
    old_view=ROOT/'scripts/phase_b_v2_live_monitor_b1_epoch7_v4'
    new_view=ROOT/'scripts/phase_b_v2_live_monitor_b1_epoch7_v5'
    for name in ('server.py','app.html','Open-Monitor.ps1'):
        text=(old_view/name).read_text(encoding='utf-8')
        text=text.replace(OLD,NEW).replace('53085','53086').replace('B1_EPOCH7_V4','B1_EPOCH7_V5').replace('B1E7V4','B1E7V5')
        write(new_view/name,text)
    write(new_view/'.gitignore','/.local/\n')
    for name in ('pin.py','test_monitor.py','prepare_gui_runtime.py'):
        text=(ROOT/'tools'/OLD/name).read_text(encoding='utf-8').replace(OLD,NEW)
        if name=='pin.py':
            text=text.replace('SEED2027_HUMAN_AUTHORIZED_B1_EPOCH7_RECOVERY_v4','SEED2027_HUMAN_AUTHORIZED_B1_EPOCH7_RECOVERY_v5')
            text=text.replace("'scripts/phase_b_v2_live_monitor_b1_epoch7_v4'","'scripts/phase_b_v2_live_monitor_b1_epoch7_v5'")
        write(ROOT/'tools'/NEW/name,text)
    print(json.dumps(dict(status='ISOLATED_V5_NAMESPACE_CREATED_NO_TRAINING')))


if __name__=='__main__':main()
