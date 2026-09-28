"""Revalidate the one recovered serialization issue and rerun the new regression test."""
import os,subprocess,json
import pandas as pd
from config import *
from common import *
from table_schema import read_audit_csv
def main():
    base=CACHE/"pytest_schema_fix"
    if base.exists():raise FileExistsError(base)
    command=[str(PYTHON),"-B","-m","pytest","tests/test_thermo.py","-q","-p","no:cacheprovider",
             "--rootdir",".","--confcutdir",".","--import-mode","importlib","--basetemp",str(base),
             "--junitxml","tests/pytest_final.xml"]
    r=subprocess.run(command,cwd=OUT,env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1",PYTHONIOENCODING="utf-8"),
                     capture_output=True,text=True,encoding="utf-8",errors="replace")
    (OUT/"tests/pytest_final_output.txt").write_text(r.stdout+"\n"+r.stderr,encoding="utf-8")
    write_json(OUT/"logs/pytest_schema_fix_execution.json",{"argv":command,"cwd":str(OUT),"returncode":r.returncode,
        "previous_final_xml":"tests/pytest_before_schema_fix.xml"})
    assert r.returncode==0,r.stdout+r.stderr
    rows=[]
    for p in sorted(OUT.rglob("*.csv")):
        q=p.with_suffix(".parquet");assert q.exists(),str(q)
        df=read_audit_csv(p);back=pd.read_parquet(q,engine="pyarrow")
        pd.testing.assert_frame_equal(df,back)
        rows.append({"csv":str(p.relative_to(OUT)),"rows":len(df),"roundtrip":"PASS"})
    write_csv(OUT/"logs/parquet_final_validation.csv",rows)
    p=OUT/"logs/parquet_final_validation.csv";pd.read_csv(p).to_parquet(p.with_suffix(".parquet"),engine="pyarrow",index=False)
    write_json(OUT/"logs/parquet_final_summary.json",{"status":"PASS","verified_tables":len(rows),"initial_failures":1,
        "resolved_failures":1,"unresolved_failures":0,"recovery":"Explicit nullable boolean dtype; unknown stays null",
        "initial_failure_preserved":"logs/parquet_summary.json"})
    print(r.stdout,dumps({"roundtrip_tables":len(rows),"all_pass":True}),flush=True)
if __name__=="__main__":main()
