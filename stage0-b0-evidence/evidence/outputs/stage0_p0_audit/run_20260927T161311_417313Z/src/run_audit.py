"""Execute the authorized two-source P0 audit; no training or data alteration."""
from pathlib import Path
from datetime import datetime,timezone
import importlib.metadata as md,json,logging,platform,sys,time,traceback
from config import OUTPUT,CACHE,IMERG,HIMAWARI,PYTHON,CONFIG
from common import Staging,write_json,write_csv,write_text,sha256
from imerg_audit import run_imerg
from himawari_latency import run_himawari

def main():
    assert Path(sys.executable).resolve()==PYTHON.resolve()
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(OUTPUT/"logs/audit_run.log",encoding="utf-8"),logging.StreamHandler(sys.stdout)])
    started=time.perf_counter()
    logging.info("P0 DATA AUDIT START python=%s",sys.executable)
    write_json(OUTPUT/"config.json",CONFIG)
    env={"python":sys.executable,"version":sys.version,"os":platform.platform(),
         "packages":{d.metadata["Name"]:d.version for d in md.distributions()},
         "time_utc":datetime.now(timezone.utc).isoformat()}
    write_json(OUTPUT/"logs/environment_effective.json",env)
    write_text(OUTPUT/"environment.txt",json.dumps(env,indent=2))
    imerg=sorted(IMERG.rglob("*.nc"));himawari=sorted(HIMAWARI.rglob("*.nc"))
    assert imerg and himawari,"Authorized source tree is empty"
    manifest=[];selected=[]
    for kind,files,root in [("IMERG",imerg,IMERG),("HIMAWARI_202407",himawari,HIMAWARI)]:
        sample_indices={0,len(files)//4,len(files)//2,3*len(files)//4,len(files)-1}
        for i,p in enumerate(files):
            s=p.stat();manifest.append({"dataset":kind,"relative_path":str(p.relative_to(root)),
                                       "size_bytes":s.st_size,"mtime_ns":s.st_mtime_ns})
            if i in sample_indices:selected.append({"dataset":kind,"source_path":str(p),"sha256_before":sha256(p)})
    write_csv(OUTPUT/"logs/source_manifest_before.csv",manifest)
    write_csv(OUTPUT/"logs/source_sample_hashes_before.csv",selected)
    logging.info("Actual scan: IMERG=%d HIMAWARI_202407=%d",len(imerg),len(himawari))
    stage=Staging()
    try:
        tick=time.perf_counter();run_imerg(imerg,stage);imerg_seconds=time.perf_counter()-tick
        logging.info("IMERG audit complete seconds=%.3f",imerg_seconds)
        tick=time.perf_counter();run_himawari(himawari,stage);himawari_seconds=time.perf_counter()-tick
        status={"data_execution_status":"COMPLETED_PENDING_FINAL_CHECKS","imerg_files":len(imerg),
                "himawari_files":len(himawari),"imerg_seconds":imerg_seconds,"himawari_seconds":himawari_seconds,
                "total_data_run_seconds":time.perf_counter()-started,"ended_utc":datetime.now(timezone.utc).isoformat()}
        write_json(OUTPUT/"logs/data_execution_status.json",status)
        logging.info("DATA AUDIT FINISHED %s",status)
    except Exception as e:
        logging.exception("AUDIT_INFRASTRUCTURE_FAILURE")
        write_json(OUTPUT/"logs/audit_failure.json",{"status":"BLOCKED","error":str(e),"traceback":traceback.format_exc()})
        raise
if __name__=="__main__":main()
