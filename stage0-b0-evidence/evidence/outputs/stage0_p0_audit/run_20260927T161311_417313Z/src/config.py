"""Researcher-authorized scope and explicitly diagnostic engineering settings."""
from pathlib import Path
PROJECT=Path("F:/pytorch/Research")
OUTPUT=Path(__file__).resolve().parents[1]
CACHE=PROJECT/"cache/stage0_p0_audit"/OUTPUT.name
IMERG=Path("F:/\u4e91\u5357\u6781\u7aef\u964d\u6c34\u6570\u636e/raw/IMERG")
HIMAWARI=Path("H:/\u8475\u82b1202303_202510/202407")
PYTHON=PROJECT/".venv/Scripts/python.exe"
CONFIG={
 "imerg_root":str(IMERG),"himawari_root":str(HIMAWARI),"output":str(OUTPUT),"cache":str(CACHE),
 "imerg_expected_title":"GPM IMERG Final Run V07B regional subset","imerg_expected_source":"GPM_3IMERGHH_07",
 "imerg_expected_units":"mm hr-1","imerg_times_per_day":48,"imerg_interval_minutes":30,
 "read_chunk_first_dimension":8,"cache_limit_bytes":134217728,"cache_min_free_bytes":536870912,
 "precip_thresholds_mm_per_hr":[0.1,1,5,10,20],
 "fraction_denominator":"valid pixels; total-pixel fractions also retained",
 "coordinate_hash":"SHA256 of shape + canonical little-endian float64 numeric values; signed zero normalized",
 "latency_tail_quantile":0.99,"latency_tail_operator":">=",
 "latency_tail_definition":"p99 is a distribution-tail review marker only; it is not an exclusion criterion, QC threshold, or scientific threshold.",
 "analysis_time_offset_minutes":10,"causality_rule":"obs_end <= nominal_time + 10min",
 "date_created_definition":"product/file creation timestamp; operational availability not established",
 "std_ddof":1,"statistics_scope":"QC_STAT_ONLY","research_years":"UNCHANGED_RESEARCHER_DECISION",
 "coverage_bbox":"UNCHANGED","seed":42
}
