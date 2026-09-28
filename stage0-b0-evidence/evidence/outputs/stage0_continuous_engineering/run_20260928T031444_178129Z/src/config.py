"""Scope/configuration only; no scientific thresholds or release rule are chosen."""
from pathlib import Path
OUT=Path(__file__).resolve().parents[1]
PROJECT=Path("F:/pytorch/Research")
RAW=Path("F:/\u4e91\u5357\u6781\u7aef\u964d\u6c34\u6570\u636e/raw")
GFS=RAW/"GFS"
SUPPLEMENT=RAW/"GFS_thermo"
IMERG=RAW/"IMERG"
HIM=Path("H:/\u8475\u82b1202303_202510")
CACHE=PROJECT/"cache/stage0_continuous_engineering"/OUT.name
PYTHON=PROJECT/".venv/Scripts/python.exe"
P0=PROJECT/"outputs/stage0_p0_audit/run_20260927T161311_417313Z"
HIM_AUDIT=PROJECT/"stage0_himawari/outputs/202407/resume_20260927T104625_772423Z"
EXTENSIONS={".grib",".grib2",".grb",".grb2",".nc",".nc4"}
REQUIRED=("PWAT","CAPE","RH_850","RH_700","RH_500","T_850","T_700","T_500","U_850","U_700","V_850","V_700","PS")
CONFIG={"cache_max_bytes":134217728,"minimum_free_bytes":536870912,
 "gfs_root":str(GFS),"secondary_root":str(SUPPLEMENT),"secondary_merge":False,
 "boundary_files":["2025/imerg_20250623.nc","2025/imerg_20250624.nc"],
 "research_candidate_years":[2023,2024,2025],"research_candidate_months":list(range(3,11)),
 "time_missing_policy":"UNKNOWN; never substitute zero epoch or file mtime",
 "release_time_policy":"NOT ESTABLISHED FROM CURRENT FILE METADATA",
 "coverage_reference":"observed main-root init hours and lead values; diagnostic grid, not a frozen vintage rule",
 "variable_coverage_denominator":"all discovered main-root files; metadata availability, not per-pixel validity",
 "common_overlap_status":"CANDIDATE ONLY","model_input_bbox":None,"statistics_scope":"QC_STAT_ONLY"}
