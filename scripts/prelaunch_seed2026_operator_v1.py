"""Same frozen metadata gate; no payload rescanning or replacement sampling."""
import runpy
from pathlib import Path
ROOT=Path(__file__).absolute().parents[1]
import sys
sys.path.insert(0,str(ROOT/'src'))
from yuntapr.training.phase_b_v2_seed2026_operator_v1.protocol import OUT,LOCAL
module=runpy.run_path(str(ROOT/'scripts/prelaunch_seed2026_resume_v2.py'))
main=module['main'];main.__globals__.update(OUT=OUT,LOCAL=LOCAL)
if __name__=='__main__':main()
