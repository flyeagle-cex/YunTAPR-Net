from pathlib import Path
OUT=Path(__file__).resolve().parents[1]
PROJECT=Path('F:\\pytorch\\Research')
DATA=Path('F:\\云南极端降水数据')
MAIN=DATA/"raw/GFS"
THERMO=DATA/"raw/GFS_thermo"
BASE_MAIN=Path('F:\\pytorch\\Research\\outputs\\stage0_continuous_engineering\\run_20260928T041855_828904Z')
BASE_THERMO=Path('F:\\pytorch\\Research\\outputs\\stage0_gfs_thermo_compatibility\\run_20260928T084334_575397Z')
CACHE=PROJECT/"cache/stage0_gfs_provenance_vintage_resolution"/OUT.name
PYTHON=PROJECT/".venv/Scripts/python.exe"
GFS=MAIN
IMERG=DATA/"raw/IMERG"
REQUIRED=("T_850","T_700","T_500","RH_850","RH_700","RH_500")
CONFIG={"cache_max_bytes":33554432,"minimum_free_bytes":536870912,"boundary_files":[]}
