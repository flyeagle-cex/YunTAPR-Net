"""Reuse the frozen metadata-only gate before the one approved new v3 launch."""
import runpy
from pathlib import Path
import sys
ROOT=Path(__file__).absolute().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from yuntapr.training.phase_b_v2_seed2026_operator_v3.protocol import OUT,LOCAL
module=runpy.run_path(str(ROOT/'scripts/prelaunch_seed2026_resume_v2.py'))
main=module['main'];main.__globals__.update(OUT=OUT,LOCAL=LOCAL)
if __name__=='__main__':main()
