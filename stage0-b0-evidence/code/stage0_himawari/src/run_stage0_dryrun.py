"""Parameterized July-only orchestrator, with independent repeatable stage commands."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,importlib,json,logging,platform,re,subprocess,sys,traceback
import pandas as pd
from config import PROJECT,PYTHON
from common import write_json,write_text,outpath
from read_himawari import Staging
from sample_audit import sample_audit
from storage_benchmark import run_benchmark
from dummy_loader_test import dummy_loading
from reports import validate_sources,write_reports

def prepare():
    out=PROJECT/"outputs/202407"/datetime.now(timezone.utc).strftime("resume_%Y%m%dT%H%M%S_%fZ")
    out.mkdir(parents=True,exist_ok=False)
    for d in ("index","qc","audit","benchmark","reports"):(out/d).mkdir()
    env={"python":sys.executable,"python_version":sys.version,"os":platform.platform(),
         "started_utc":datetime.now(timezone.utc).isoformat(),"packages":{}}
    for name in ("numpy","pandas","xarray","netCDF4","zarr","numcodecs","pyarrow","torch","h5netcdf"):
        m=importlib.import_module(name);env["packages"][name]=getattr(m,"__version__","unknown")
    write_json(out/"reports/environment.json",env)
    return out

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--year",type=int,default=2024);parser.add_argument("--month",type=int,default=7)
    parser.add_argument("--run-dir");parser.add_argument("--phase",choices=["all","monthly","remaining","audit","benchmark","dummy","final"],default="all")
    args=parser.parse_args()
    assert Path(sys.executable).resolve()==PYTHON.resolve()
    if (args.year,args.month)!=(2024,7):raise ValueError("Only July 2024 authorized; no automatic all-year run")
    out=outpath(Path(args.run_dir)) if args.run_dir else prepare()
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s",
      handlers=[logging.FileHandler(out/"resume_202407.log",encoding="utf-8"),logging.StreamHandler(sys.stdout)])
    try:
        if args.phase in ("all","monthly"):
            subprocess.run([sys.executable,"-B",str(PROJECT/"tests/test_stage0.py")],check=True)
            subprocess.run([sys.executable,"-B",str(PROJECT/"src/run_monthly.py"),"--run-dir",str(out),
                            "--year",str(args.year),"--month",str(args.month)],check=True)
            if args.phase=="monthly":return
        master=pd.read_parquet(out/"index/himawari_master_index_202407.parquet",engine="pyarrow")
        boundary=pd.read_parquet(out/"index/boundary_frame_qc_202407.parquet",engine="pyarrow")
        sequences=pd.read_parquet(out/"index/himawari_sequence_index_202407.parquet",engine="pyarrow")
        staging=Staging(out)
        if args.phase in ("all","remaining","audit"):
            sample_audit(sequences,master,staging,out)
            logging.info("STEP8_SAMPLE_AUDIT_PASS")
        if args.phase in ("all","remaining","benchmark","dummy","final"):
            selection=pd.read_parquet(out/"audit/random_and_targeted_sample_list_202407.parquet",engine="pyarrow")
        if args.phase in ("all","remaining","benchmark"):
            run_benchmark(sequences,selection,master,boundary,staging,out)
            logging.info("STEP9_STORAGE_BENCHMARK_PASS")
        if args.phase in ("all","remaining","dummy"):
            dummy_loading(selection,staging,out)
            logging.info("STEP10_PYTORCH_DUMMY_PASS")
        if args.phase in ("all","remaining","final"):
            result=subprocess.run([sys.executable,"-B",str(PROJECT/"tests/test_stage0.py")],capture_output=True,text=True)
            text=result.stdout+result.stderr
            write_text(out/"audit/automated_tests_202407.txt",text)
            if result.returncode:raise RuntimeError("Scientific automated tests failed")
            match=re.search(r"Ran (\d+) tests",text)
            count=int(match.group(1)) if match else 0
            assert count>=14
            validate_sources(out)
            audit=pd.read_csv(out/"audit/sample_audit_202407.csv")
            bench=pd.read_csv(out/"benchmark/storage_benchmark_202407.csv")
            dummy=pd.read_csv(out/"audit/pytorch_dummy_loading_report_202407.csv")
            status=write_reports(out,master,sequences,audit,bench,dummy,count)
            print(json.dumps(status,indent=2))
    except Exception as error:
        logging.exception("RESUME_FAILED")
        failure=out/"reports"/datetime.now(timezone.utc).strftime("failure_%Y%m%dT%H%M%S_%fZ.json")
        write_json(failure,{"status":"DRY_RUN_FAILED","phase":args.phase,"error":str(error),"traceback":traceback.format_exc()})
        raise
if __name__=="__main__":main()
