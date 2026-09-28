"""Steps 4-7 runner; later stages consume its immutable CSV/Parquet outputs."""
from pathlib import Path
import argparse,logging,sys,time,traceback
import pandas as pd
from config import PYTHON,CONFIG
from common import write_json,write_table,MemoryMonitor,write_text,outpath
from read_himawari import Staging,read_himawari_7ch
from scan_files import scan_files
from build_master_index import build_master,finalize_qc
from grid_audit import grid_audit
from build_sequence_index import boundary_paths,build_sequences

def main():
    p=argparse.ArgumentParser();p.add_argument("--run-dir",required=True);p.add_argument("--year",type=int,default=2024);p.add_argument("--month",type=int,default=7)
    args=p.parse_args();out=outpath(Path(args.run_dir))
    assert Path(sys.executable).resolve()==PYTHON.resolve()
    assert (args.year,args.month)==(2024,7),"Only July authorized"
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.FileHandler(out/"resume_202407.log",encoding="utf-8"),
                                  logging.StreamHandler(sys.stdout)])
    try:
        write_json(out/"reports/config.json",CONFIG)
        paths,manifest=scan_files(args.year,args.month)
        assert len(paths)>0
        write_table(manifest,out/"index/raw_file_manifest_202407.csv")
        staging=Staging(out)
        # Reader smoke test gates the full monthly pass.
        x,m,lat,lon,metadata=read_himawari_7ch(paths[0],staging,verify_hash=True)
        assert x.shape==(7,len(lat),len(lon)) and m.dtype==bool
        logging.info("STEP4_READER_SMOKE_PASS shape=%s valid_fraction=%.6f",x.shape,m.mean())
        del x,m
        started=time.perf_counter()
        with MemoryMonitor() as memory:
            master=build_master(paths,staging,out)
        master,reference=finalize_qc(master)
        write_table(master,out/"index/himawari_master_index_202407.csv",parquet=True)
        write_table(grid_audit(master),out/"qc/grid_consistency_report_202407.csv")
        classes=master["quality_class"].value_counts()
        write_table(pd.DataFrame([{"quality_class":c,"file_count":int(classes.get(c,0))}
                    for c in CONFIG["qc_priority"]]),out/"qc/qc_summary_202407.csv")
        # Audit only exact required previous-day frames, not June monthly data.
        borderpaths=boundary_paths(args.year,args.month)
        boundary=build_master(borderpaths,staging,out,prefix="boundary") if borderpaths else master.iloc[:0].copy()
        if len(boundary):boundary,_=finalize_qc(boundary,reference)
        write_table(boundary,out/"index/boundary_frame_qc_202407.csv",parquet=True)
        sequences=build_sequences(master,boundary,args.year,args.month)
        write_table(sequences,out/"index/himawari_sequence_index_202407.csv",parquet=True)
        assert all(sequences[f"frame_{'t' if i==0 else 't_minus_'+str(i*10)}"].le(sequences.target_time_utc).all() for i in range(6))
        satellites=sorted(master.satellite.dropna().unique())
        if len(satellites)<2:
            write_table(pd.DataFrame([{"status":"NOT_APPLICABLE","reason":"comparison_not_available_in_202407",
                                      "satellites":",".join(satellites),"statistics_scope":"QC_STAT_ONLY"}]),
                        out/"qc/h08_h09_channel_comparison_202407.csv")
        result=dict(status="STEPS_4_7_PASS",raw_files_scanned=len(master),read_success=int(master.read_success.sum()),
                    read_failed=int((~master.read_success).sum()),reference_grid=reference,satellites=satellites,
                    total_targets=len(sequences),complete=int(sequences.sequence_complete.sum()),
                    incomplete=int((~sequences.sequence_complete).sum()),boundary_files=len(boundary),
                    elapsed_seconds=time.perf_counter()-started,**memory.report())
        write_json(out/"reports/monthly_status.json",result)
        logging.info("STEPS_4_7_COMPLETE %s",result)
    except Exception as error:
        logging.exception("MONTHLY_FAILURE")
        write_json(out/"reports/monthly_failure.json",{"status":"DRY_RUN_FAILED","error":str(error),"traceback":traceback.format_exc()})
        raise
if __name__=="__main__":main()
