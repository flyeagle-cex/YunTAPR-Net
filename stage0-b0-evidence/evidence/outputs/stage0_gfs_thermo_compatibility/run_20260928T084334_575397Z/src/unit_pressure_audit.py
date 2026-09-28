"""Metadata-only unit comparison; no array conversion or pressure mask."""
import json,pandas as pd
from config import *
from common import write_csv
def main():
    m=pd.read_csv(BASELINE/"GFS/gfs_variable_mapping.csv")
    def units(target):return sorted(m[m.canonical_names.apply(lambda v:any(c==target or c.startswith(target+"_") for c in json.loads(v)))].units.unique().tolist())
    assert units("T")==["K"] and units("RH")==["%"] and units("PS")==["Pa"]
    rows=[{"quantity":"Temperature","thermo_units":"K","main_observed_units":json.dumps(units("T")),"status":"PASS","action_performed":"NONE; native K retained"},
          {"quantity":"Relative humidity","thermo_units":"%","main_observed_units":json.dumps(units("RH")),"status":"PASS","action_performed":"NONE; native percent retained, not converted to 0-1"},
          {"quantity":"Pressure coordinate vs main PS","thermo_units":"Pa","main_observed_units":json.dumps(units("PS")),"status":"PASS","action_performed":"Metadata feasibility only; actual [50000,70000,85000] Pa; no mask/DOTE/W/L/M"}]
    write_csv(OUT/"COMPATIBILITY/unit_pressure_compatibility.csv",rows)
if __name__=="__main__":main()
