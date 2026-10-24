"""Prepare an isolated namespace; never writes the original v7 repository."""
from pathlib import Path
import ast
import json

WORK = Path(__file__).resolve().parents[2]
LIVE = WORK.parent / "YunTAPR-Net-push-chunks"
OLD = "phase_b_v2_seed2027_b1_epoch7_recovery_v7"
NEW = "phase_b_v2_seed2027_b0_e1_recovery_v1"
SOURCE = LIVE / "src/yuntapr/training" / OLD
TARGET = WORK / "recovery_overlay/yuntapr/training" / NEW
OUT = WORK / "docs/formal_recovery/seed2027_b0_e1_epoch1_v1"


def replace(text, old, new):
    if old not in text:
        raise ValueError("Source interface differs: " + old[:90])
    return text.replace(old, new)


def main():
    TARGET.mkdir(parents=True, exist_ok=True)
    for source in SOURCE.glob("*.py"):
        if source.name in ("protocol.py", "authority.py", "ancestor.py", "accounting.py", "recovery.py"):
            continue
        text = source.read_text(encoding="utf-8").replace(OLD, NEW)
        if source.name == "checkpoint.py":
            text = replace(text, "_B1_EPOCH7_RECOVERY_LAST_v7", "_B0_E1_EPOCH1_RECOVERY_LAST_v1")
        if source.name == "engine.py":
            first = text.index("def completed_result(ident):")
            last = text.index("\nclass Engine:", first)
            text = text[:first] + '''def completed_result(ident):
    from .ancestor import Guard, COMPLETE_RESULTS
    if ident in COMPLETE_RESULTS:
        release=verify_release()
        with Guard(release['failed_ancestor_sha256']) as guard:
            return guard.pool.metadata[COMPLETE_RESULTS[ident]]
    from yuntapr.experimental.phase_b_v2_status_snapshot_io.reader import read_json_snapshot
    return read_json_snapshot(OUT/(ident+'.json'),OUT)
''' + text[last:]
            text = text.replace("authorized_b1_epoch7_recovery", "authorized_b0_e1_epoch1_recovery")
            text = text.replace("AUTHORIZED_B1_EPOCH7_LAST_RESUMED", "AUTHORIZED_B0_E1_EPOCH1_LAST_RESUMED")
            text = text.replace("SEED2027_B1_EPOCH7_CONSOLE_FREE_RECOVERY_V7_NO_RETRY", "SEED2027_B0_E1_EPOCH1_ISOLATED_RECOVERY_V1_NO_RETRY")
        if source.name == "quota.py":
            text = replace(text, "from .protocol import ROOT,", "from .protocol import LIVE_ROOT,ROOT,")
            text = replace(text, "(ROOT/SOURCE_DB)", "(LIVE_ROOT/SOURCE_DB)")
            text = replace(text,
                '''adopted=old.execute("SELECT * FROM epochs WHERE (run=? AND epoch<=9) OR (run=? AND epoch<=?) ORDER BY run,epoch",(run_id(*ORDER[0]),SOURCE_RUN,SOURCE_EPOCH)).fetchall()''',
                '''adopted=old.execute("SELECT * FROM epochs WHERE (run IN (?,?) AND epoch<=9) OR (run=? AND epoch<=?) ORDER BY run,epoch",(run_id(*ORDER[0]),run_id(*ORDER[1]),SOURCE_RUN,SOURCE_EPOCH)).fetchall()''')
            text = replace(text,
                "values=(ident,i,'COMPLETE',9,47052,'34022dd6970a95a1fc8ef7a910d5b4a80a1f029ad3617dee577d6dff2b1f4673') if i==0 else ((ident,i,'RUNNING',SOURCE_EPOCH,SOURCE_UPDATE,LAST_SHA) if i==1 else (ident,i,'PENDING',0,0,None))",
                "values=(ident,i,'COMPLETE',9,47052,release['completed_last_sha256'][ident]) if i<2 else ((ident,i,'RUNNING',SOURCE_EPOCH,SOURCE_UPDATE,LAST_SHA) if i==2 else (ident,i,'PENDING',0,0,None))")
        if source.name in ("gui_owner.py", "task_entry.py", "supervisor.py"):
            text = text.replace("PYTHONPATH=str(ROOT/'src')", "PYTHONPATH=BOOTSTRAP_PATH")
            text = text.replace("job.spawn([sys.executable,'-m'", "job.spawn([sys.executable,'-B','-m'")
            text = text.replace("job.spawn([request['interpreter'],str(entry)", "job.spawn([request['interpreter'],'-B',str(entry)")
            text = text.replace("/src/yuntapr/training/", "/recovery_overlay/yuntapr/training/")
            text = text.replace("ROOT/'src/yuntapr/training/", "ROOT/'recovery_overlay/yuntapr/training/")
        if source.name == "gui_owner.py":
            text = replace(text, "sys.path.insert(0,str(ROOT/'src'))", '''LIVE_ROOT=ROOT.parent/'YunTAPR-Net-push-chunks'
sys.dont_write_bytecode=True
sys.path.insert(0,str(LIVE_ROOT/'src'))
import yuntapr.training
yuntapr.training.__path__.append(str(ROOT/'recovery_overlay/yuntapr/training'))''')
            text = replace(text, "from yuntapr.training."+NEW+".protocol import session_root,", "from yuntapr.training."+NEW+".protocol import BOOTSTRAP_PATH,session_root,")
        if source.name == "task_entry.py":
            text = replace(text, "PYTHONPATH=str(root/'src')", "PYTHONPATH=os.pathsep.join([str(root/'tools/seed2027_b0_e1_recovery/bootstrap'),str(root.parent/'YunTAPR-Net-push-chunks'/'src')])")
            text = replace(text, "sys.path.insert(0,str(root/'src'));os.chdir(root)", "sys.dont_write_bytecode=True;sys.path.insert(0,str(root.parent/'YunTAPR-Net-push-chunks'/'src'));os.chdir(root)\n    import yuntapr.training\n    yuntapr.training.__path__.append(str(root/'recovery_overlay/yuntapr/training'))")
        if source.name == "supervisor.py":
            text = replace(text, "from .protocol import ROOT,", "from .protocol import BOOTSTRAP_PATH,ROOT,")
        if source.name == "task_owner.py":
            text = text.replace("YunTAPR_Seed2027_B1E7V7_", "YunTAPR_Seed2027_B0E1R1_")
            text = replace(text, "ROOT/'src/yuntapr/training/", "ROOT/'recovery_overlay/yuntapr/training/")
            text = replace(text, "subprocess.list2cmdline([str(entry),", "subprocess.list2cmdline(['-B',str(entry),")
        if source.name == "control.py":
            text = replace(text, "release=verify_release()\n    from .protocol import require_predecessor", "from .authority import require_execution_authority\n    require_execution_authority(2027)\n    from .admission import require_launch_headroom\n    require_launch_headroom()\n    release=verify_release()\n    from .protocol import require_predecessor")
        if source.name == "release_check.py":
            text = replace(text, "release=verify_release()", "release=verify_published_release()")
        ast.parse(text)
        (TARGET/source.name).write_text(text, encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/".gitignore").write_text(".local/\n", encoding="utf-8")
    (OUT/".local").mkdir(exist_ok=True)
    for name in ("runtime.json", "gui_runtime.json"):
        destination = OUT/".local"/name
        if not destination.exists():
            destination.write_bytes((LIVE/"docs/phase_b_v2_formal_execution/seed2027_b1_epoch7_recovery_v7/.local"/name).read_bytes())
    (OUT/"config.json").write_bytes((LIVE/"docs/phase_b_v2_formal_execution/seed2027_b1_epoch7_recovery_v7/config.json").read_bytes())
    print(json.dumps(dict(prepared_namespace=NEW, original_repository_writes=0,
                          original_ledger_writes=0, training_launched=False)))


if __name__ == "__main__":
    main()
