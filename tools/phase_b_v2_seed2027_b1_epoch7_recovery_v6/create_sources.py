"""Create the separately human-authorized zero-update reissue; never launch."""
from pathlib import Path
ROOT=Path(__file__).absolute().parents[2]
OLD='phase_b_v2_seed2027_b1_epoch7_recovery_v5'
NEW='phase_b_v2_seed2027_b1_epoch7_recovery_v6'

def write(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8',newline='\n') as f:f.write(text)

def adapt(text):
    return (text.replace(OLD,NEW).replace('seed2027_b1_epoch7_recovery_v5','seed2027_b1_epoch7_recovery_v6').replace('B1_EPOCH7_RECOVERY_V5','B1_EPOCH7_RECOVERY_V6')
        .replace('B1_EPOCH7_CONSOLE_FREE_RECOVERY_V5_NO_RETRY','B1_EPOCH7_CONSOLE_FREE_RECOVERY_V6_NO_RETRY')
        .replace('SEED2027_HUMAN_AUTHORIZED_B1_EPOCH7_RECOVERY_v5','SEED2027_HUMAN_AUTHORIZED_B1_EPOCH7_RECOVERY_v6')
        .replace('RECOVERY_LAST_v5','RECOVERY_LAST_v6').replace('B1E7V5','B1E7V6'))

def main():
    for area in ('src/yuntapr/training','scripts'):
        for path in (ROOT/area/OLD).iterdir():
            if path.suffix not in ('.py','.ps1') or path.name in ('ancestor.py','authority.py'):continue
            text=adapt(path.read_text(encoding='utf-8'))
            if path.name=='protocol.py':
                text=text.replace("'tools/phase_b_v2_seed2027_b1_epoch7_recovery_v6']","'tools/phase_b_v2_seed2027_b1_epoch7_recovery_v6','scripts/phase_b_v2_seed2027_b1_epoch7_recovery_v5','tools/phase_b_v2_seed2027_b1_epoch7_recovery_v5']")
            write(ROOT/area/NEW/path.name,text)
    out=ROOT/'docs/phase_b_v2_formal_execution/seed2027_b1_epoch7_recovery_v6'
    (out/'.local').mkdir(parents=True,exist_ok=False)
    prior=out.with_name('seed2027_b1_epoch7_recovery_v5')
    for name in ('config.json','.local/runtime.json','.local/gui_runtime.json'):
        with (out/name).open('xb') as f:f.write((prior/name).read_bytes())
    write(out/'.gitignore','/.local/\n')
    for name in ('pin.py','test_monitor.py'):
        text=adapt((ROOT/'tools'/OLD/name).read_text(encoding='utf-8'))
        if name=='pin.py':text=text.replace('phase_b_v2_live_monitor_b1_epoch7_v5','phase_b_v2_live_monitor_b1_epoch7_v6')
        write(ROOT/'tools'/NEW/name,text)
    view=ROOT/'scripts/phase_b_v2_live_monitor_b1_epoch7_v6'
    for name in ('server.py','app.html','Open-Monitor.ps1'):
        text=adapt((ROOT/'scripts/phase_b_v2_live_monitor_b1_epoch7_v5'/name).read_text(encoding='utf-8'))
        text=text.replace('phase_b_v2_live_monitor_b1_epoch7_v5','phase_b_v2_live_monitor_b1_epoch7_v6').replace('53086','53087').replace('B1_EPOCH7_V5','B1_EPOCH7_V6')
        write(view/name,text)
    task_view=(ROOT/'scripts/phase_b_v2_live_monitor_b1_epoch7_v4/Task-View.py').read_text(encoding='utf-8')
    write(view/'Task-View.py',task_view.replace('phase_b_v2_seed2027_b1_epoch7_recovery_v4',NEW).replace('53085','53087'))
    write(view/'.gitignore','/.local/\n')

if __name__=='__main__':main()
