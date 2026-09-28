from pathlib import Path
OUT=Path(__file__).resolve().parents[1]
PROJECT=Path('F:\\pytorch\\Research')
RAW=Path('F:\\云南极端降水数据\\raw')
MAIN=RAW/"GFS"
THERMO=RAW/"GFS_thermo"
GFS=THERMO
IMERG=RAW/"IMERG"
BASELINE=Path('F:\\pytorch\\Research\\outputs\\stage0_continuous_engineering\\run_20260928T041855_828904Z')
CACHE=PROJECT/"cache/stage0_gfs_thermo_compatibility"/OUT.name
PYTHON=PROJECT/".venv/Scripts/python.exe"
REQUIRED=("T_850","T_700","T_500","RH_850","RH_700","RH_500")
CONFIG={"cache_max_bytes":134217728,"minimum_free_bytes":536870912,"boundary_files":[]}

EXTENSIONS={".nc",".nc4",".grib",".grib2",".grb",".grb2"}
SUPPLEMENT=THERMO
