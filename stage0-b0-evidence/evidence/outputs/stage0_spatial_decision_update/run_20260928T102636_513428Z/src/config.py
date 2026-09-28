from pathlib import Path
OUT=Path(__file__).resolve().parents[1]
PROJECT=Path('F:\\pytorch\\Research')
DATA=Path('F:\\云南极端降水数据')
BASE=PROJECT/"outputs/stage0_spatial_static_closeout/run_20260928T095818_821492Z"
PYTHON=PROJECT/".venv/Scripts/python.exe"
CACHE=PROJECT/"cache/stage0_spatial_decision_update"/OUT.name
