"""Derive the authorized v7 zero-update reissue from v6; integrate the Job identity race fix."""
from pathlib import Path
import json

ROOT=Path(__file__).absolute().parents[2]
OLD='phase_b_v2_seed2027_b1_epoch7_recovery_v6'
NEW='phase_b_v2_seed2027_b1_epoch7_recovery_v7'


def write(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8',newline='\n') as f:f.write(text)


def main():
    for area in ('src/yuntapr/training','scripts'):
        src=ROOT/area/OLD;dst=ROOT/area/NEW
        for path in src.iterdir():
            if path.suffix not in ('.py','.ps1'):continue
            if path.name=='ancestor.py':continue  # rewritten separately for the v6 zero-update seal
            text=path.read_text(encoding='utf-8').replace(OLD,NEW)
            text=text.replace('seed2027_b1_epoch7_recovery_v6','seed2027_b1_epoch7_recovery_v7')
            text=text.replace('B1_EPOCH7_RECOVERY_V6','B1_EPOCH7_RECOVERY_V7')
            text=text.replace('B1_EPOCH7_CONSOLE_FREE_RECOVERY_V6_NO_RETRY','B1_EPOCH7_CONSOLE_FREE_RECOVERY_V7_NO_RETRY')
            text=text.replace('ONLY_DIRECTLY_APPROVED_SEED2027_EPOCH7_RECOVERY_V6','ONLY_DIRECTLY_APPROVED_SEED2027_EPOCH7_RECOVERY_V7')
            if path.name=='supervisor.py':
                text=text.replace('from .resources import host_admission',
                    'from yuntapr.experimental.phase_b_v2_job_identity_race_candidate.job import IdentitySafeJob\nfrom .resources import host_admission')
                text=text.replace('class FormalJob(Job):','class FormalJob(IdentitySafeJob):')
            if path.name=='protocol.py':
                text=text.replace('SEED2027_HUMAN_AUTHORIZED_B1_EPOCH7_RECOVERY_v6','SEED2027_HUMAN_AUTHORIZED_B1_EPOCH7_RECOVERY_v7')
                text=text.replace("'scripts/phase_b_v2_live_monitor_b1_epoch7_v6'","'scripts/phase_b_v2_live_monitor_b1_epoch7_v7','scripts/phase_b_v2_live_monitor_b1_epoch7_v6'")
                text=text.replace("'tools/phase_b_v2_seed2027_b1_epoch7_recovery_v7']","'tools/phase_b_v2_seed2027_b1_epoch7_recovery_v7','scripts/phase_b_v2_seed2027_b1_epoch7_recovery_v6','tools/phase_b_v2_seed2027_b1_epoch7_recovery_v6','tools/phase_b_v2_job_identity_race_candidate']")
            if path.name=='checkpoint.py':text=text.replace('RECOVERY_LAST_v6','RECOVERY_LAST_v7')
            if path.name=='release_check.py':text=text.replace('PRIOR_166305_CHARGED_REPLAY_922_ZERO_UPDATE_REISSUE_V6','PRIOR_166305_CHARGED_REPLAY_922_ZERO_UPDATE_REISSUE_V7')
            if path.name=='task_owner.py':text=text.replace('B1E7V6','B1E7V7')
            write(dst/path.name,text)
    out=ROOT/'docs/phase_b_v2_formal_execution/seed2027_b1_epoch7_recovery_v7'
    out.mkdir(parents=True,exist_ok=True);(out/'.local').mkdir(exist_ok=True)
    original=ROOT/'docs/phase_b_v2_formal_execution/seed2027_b1_epoch7_recovery_v6'
    for name in ('config.json','.local/runtime.json','.local/gui_runtime.json'):
        target=out/name
        with target.open('xb') as f:f.write((original/name).read_bytes())
    write(out/'.gitignore','/.local/\n')
    old_view=ROOT/'scripts/phase_b_v2_live_monitor_b1_epoch7_v6'
    new_view=ROOT/'scripts/phase_b_v2_live_monitor_b1_epoch7_v7'
    for name in ('server.py','app.html','Open-Monitor.ps1'):
        text=(old_view/name).read_text(encoding='utf-8')
        text=text.replace(OLD,NEW).replace('53087','53088').replace('B1_EPOCH7_V6','B1_EPOCH7_V7').replace('B1E7V6','B1E7V7')
        write(new_view/name,text)
    write(new_view/'.gitignore','/.local/\n')
    for name in ('pin.py','test_monitor.py'):
        text=(ROOT/'tools'/OLD/name).read_text(encoding='utf-8').replace(OLD,NEW)
        if name=='pin.py':
            text=text.replace('SEED2027_HUMAN_AUTHORIZED_B1_EPOCH7_RECOVERY_v6','SEED2027_HUMAN_AUTHORIZED_B1_EPOCH7_RECOVERY_v7')
            text=text.replace("'scripts/phase_b_v2_live_monitor_b1_epoch7_v6'","'scripts/phase_b_v2_live_monitor_b1_epoch7_v7'")
        write(ROOT/'tools'/NEW/name,text)
    print(json.dumps(dict(status='ISOLATED_V7_NAMESPACE_CREATED_NO_TRAINING')))


if __name__=='__main__':main()
