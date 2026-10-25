"""Fixed isolated recovery entry; no general command injection or retry loop."""
from pathlib import Path
import os
import sys

WORK = Path(__file__).resolve().parents[2]
LIVE = WORK.parent / "YunTAPR-Net-push-chunks"
sys.dont_write_bytecode = True
sys.path.insert(0, str(LIVE / "src"))
import yuntapr.training
yuntapr.training.__path__.append(str(WORK.parent / "YunTAPR-Net-completed-review-20261021/recovery_overlay/yuntapr/training"))
yuntapr.training.__path__.append(str(WORK.parent / "YunTAPR-Net-seed2027-b1-e1-recovery-20261022/recovery_overlay/yuntapr/training"))
yuntapr.training.__path__.append(str(WORK / "recovery_overlay/yuntapr/training"))
os.environ.update(PYTHONDONTWRITEBYTECODE="1", YUNTAPR_REPLICATION_SEED="2027")

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("check", "start", "status", "resources"):
        raise PermissionError("FIXED_RECOVERY_ACTION_ONLY")
    if sys.argv[1] == "check":
        from yuntapr.training.phase_b_v2_seed2027_b1_e1_epoch6_recovery_v2.release_check import main
        main()
    elif sys.argv[1] == "resources":
        import json
        from yuntapr.training.phase_b_v2_seed2027_b1_e1_epoch6_recovery_v2.admission import launch_headroom
        print(json.dumps(launch_headroom(), indent=2))
    else:
        from yuntapr.training.phase_b_v2_seed2027_b1_e1_epoch6_recovery_v2.control import main
        main()
