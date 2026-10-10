"""One bounded read-only attempt; no alternative roots, download or training."""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"src"))
from yuntapr.experimental.phase_b_v2_real_data_preflight.audit import run
if __name__ == "__main__":
    result = run()
    import json
    print(json.dumps({"status":result["overall_status"],"checks":{k:v.get("status") for k,v in result["checks"].items()},
                      "decoded_scenes":len(result["decoded"]),"blocker_count":len(result["blockers"]),
                      "elapsed_seconds":result["elapsed_seconds"]},ensure_ascii=False))

