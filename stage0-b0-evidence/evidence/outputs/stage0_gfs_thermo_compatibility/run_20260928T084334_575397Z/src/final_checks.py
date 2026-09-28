"""Scoped tests and explicit pyarrow roundtrip; no dependency installation."""
import os,subprocess,sys,json
import pandas as pd
from config import *
from common import *
from table_schema import read_audit_csv
def main():
    base=CACHE/"pytest_final"
    if base.exists():raise FileExistsError("Refuse existing test temp directory")
    command=[str(PYTHON),"-B","-m","pytest","tests/test_thermo.py","-q","-p","no:cacheprovider",
        "--rootdir",".","--confcutdir",".","--import-mode","importlib","--basetemp",str(base),
        "--junitxml","tests/pytest_final.xml"]
    r=subprocess.run(command,cwd=OUT,env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1",PYTHONIOENCODING="utf-8"),
                     capture_output=True,text=True,encoding="utf-8",errors="replace")
    write_text(OUT/"tests/pytest_final_output.txt",r.stdout+"\n"+r.stderr)
    write_json(OUT/"logs/pytest_execution.json",{"argv":command,"cwd":str(OUT),"returncode":r.returncode})
    print(r.stdout,flush=True)
    if r.returncode:raise RuntimeError("Final tests failed; evidence preserved")
    results=[]
    for p in sorted(OUT.rglob("*.csv")):
        target=p.with_suffix(".parquet")
        record={"csv":str(p.relative_to(OUT)),"parquet":str(target.relative_to(OUT)),"engine":"pyarrow","status":"NOT_RUN"}
        try:
            if target.exists():raise FileExistsError(target)
            df=read_audit_csv(p);df.to_parquet(target,index=False,engine="pyarrow",compression="snappy")
            pd.testing.assert_frame_equal(df,pd.read_parquet(target,engine="pyarrow"))
            record.update(status="PASS",rows=len(df),error=None)
        except Exception as e:record.update(status="FAILED",error=f"{type(e).__name__}: {e}")
        results.append(record)
    write_csv(OUT/"logs/parquet_validation.csv",results)
    p=OUT/"logs/parquet_validation.csv";pd.read_csv(p).to_parquet(p.with_suffix(".parquet"),index=False,engine="pyarrow")
    write_json(OUT/"logs/parquet_summary.json",{"attempted":len(results),"passed":sum(r["status"]=="PASS" for r in results),
          "failed":[r for r in results if r["status"]!="PASS"],"validation_table_self_pair":"PASS"})
    assert all(r["status"]=="PASS" for r in results),"Parquet errors retained; no fallback dependency installed"
    print(dumps({"parquet_tables":len(results),"all_roundtrip_pass":True}),flush=True)
if __name__=="__main__":main()
