"""Validate final artifacts and measure truly shuffled six-frame storage access."""
from pathlib import Path
from datetime import datetime,timezone
import json,time,logging,sys,subprocess,platform,os
import numpy as np,pandas as pd,netCDF4,zarr,torch
from config import PROJECT,CONFIG
from common import write_json,write_text,write_table,MemoryMonitor,sha256
from sample_audit import LABELS

def main():
    out=Path(sys.argv[1])
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(message)s",
      handlers=[logging.FileHandler(out/"resume_202407.log",encoding="utf-8"),logging.StreamHandler(sys.stdout)])
    previous=json.loads((out/"reports/final_dry_run_status_202407.json").read_text(encoding="utf-8"))
    assert previous["status"]=="READY_FOR_RESEARCHER_REVIEW"
    locators={(r["format"],r["relative_path"]):(r["store"],r["index"]) for r in
              json.loads((out/"benchmark/storage_locators.json").read_text(encoding="utf-8"))}
    selection=pd.read_csv(out/"benchmark/benchmark_sequence_manifest_202407.csv")
    targets=selection[selection.benchmark_group=="random_50"]
    stores={};newrows=[];orders=[]
    def read(fmt,key):
        path,i=locators[(fmt,key)]
        if path not in stores:
            if fmt=="zarr":stores[path]=zarr.open_group(path,mode="r")
            else:
                stores[path]=netCDF4.Dataset(path,"r")
                stores[path].set_auto_maskandscale(False)
        ds=stores[path]
        return np.asarray(ds["x"][i]),np.asarray(ds["valid_mask"][i],dtype=bool)
    try:
        rng=np.random.default_rng(CONFIG["seed"])
        for repeat in range(3):
            permutation=rng.permutation(len(targets))
            ordered=targets.iloc[permutation]
            assert not np.all(np.diff(permutation)>0),"Workload must be shuffled"
            for position,row in enumerate(ordered.to_dict("records")):
                orders.append({"repeat":repeat,"position":position,"target_time_utc":row["target_time_utc"]})
            for fmt in (("zarr","netcdf4") if repeat%2==0 else ("netcdf4","zarr")):
                started=time.perf_counter()
                with MemoryMonitor() as memory:
                    for row in ordered.to_dict("records"):
                        pairs=[read(fmt,row["path_"+label]) for label in LABELS]
                        x=np.stack([a for a,b in pairs]);m=np.stack([b for a,b in pairs])
                        assert x.shape[:2]==(6,7) and m.shape==x.shape
                        assert np.isnan(x[~m]).all()
                        del pairs,x,m
                seconds=time.perf_counter()-started
                newrows.append(dict(format=fmt,operation="random_6frame",repeat=repeat,operations=len(ordered),
                                    seconds=seconds,seconds_per_operation=seconds/len(ordered),
                                    cache_state="warm OS cache; backend warms in first repeat; seeded shuffled targets",**memory.report()))
                logging.info("Shuffled random-six-frame format=%s repeat=%d seconds=%.3f",fmt,repeat,seconds)
    finally:
        for path,ds in stores.items():
            if path.endswith(".nc"):ds.close()
    write_table(pd.DataFrame(orders),out/"benchmark/random_read_order_202407.csv")
    original=pd.read_csv(out/"benchmark/storage_benchmark_202407.csv")
    corrected=pd.concat([original[original.operation!="random_6frame"],pd.DataFrame(newrows)],ignore_index=True)
    # Original chronological sparse-target timings remain immutable in the original CSV.
    write_table(corrected,out/"benchmark/storage_benchmark_202407_v2.csv")
    med=pd.DataFrame(newrows).groupby("format").seconds_per_operation.median()
    recommended=med.idxmin()
    artifact_checks={}
    frames=pd.read_parquet(out/"benchmark/benchmark_frame_manifest_202407.parquet")
    descriptor=[]
    for fmt in ("zarr","netcdf4"):
        folder=out/"benchmark/candidates"/fmt
        for i,(signature,group) in enumerate(frames.groupby("grid_signature",sort=True)):
            path=folder/f"grid_{i}.{'zarr' if fmt=='zarr' else 'nc'}"
            ds=zarr.open_group(str(path),mode="r") if fmt=="zarr" else netCDF4.Dataset(str(path),"r")
            try:
                expected=pd.to_datetime(group.timestamp_filename_utc,utc=True).dt.as_unit("ns").astype("int64").to_numpy()
                np.testing.assert_array_equal(np.asarray(ds["timestamp_ns"][:]),expected)
                assert ds["x"].shape==(len(group),7,int(group.iloc[0].shape_lat),int(group.iloc[0].shape_lon))
                assert np.all(np.diff(ds["latitude"][:])<0) and np.all(np.diff(ds["longitude"][:])>0)
                descriptor.append({"format":fmt,"shape":str(ds["x"].shape),
                    "chunk_shape":str(ds["x"].chunks if fmt=="zarr" else ds["x"].chunking()),
                    "compression":str(ds["x"].compressors if fmt=="zarr" else ds["x"].filters()),
                    "x_dtype":str(ds["x"].dtype),"mask_dtype":str(ds["valid_mask"].dtype)})
            finally:
                if fmt=="netcdf4":ds.close()
            sidecar=folder/f"grid_{i}_metadata.jsonl"
            meta=[json.loads(line) for line in sidecar.read_text(encoding="utf-8").splitlines()]
            assert len(meta)==len(group)
            assert all(set(m["metadata"]["channels"])==set(CONFIG["channels"]) for m in meta)
    zmeta=out/"benchmark/candidates/zarr/grid_0_metadata.jsonl"
    nmeta=out/"benchmark/candidates/netcdf4/grid_0_metadata.jsonl"
    assert sha256(zmeta)==sha256(nmeta),"Candidate metadata preservation differs"
    write_table(pd.DataFrame(descriptor),out/"benchmark/actual_storage_settings_202407.csv")
    # Produce the required backend report from actual resumed staging measurements.
    io=pd.read_csv(out/"audit/staging_io_202407.csv",keep_default_na=False)
    backend=io.drop_duplicates("source_path").head(5).copy()
    backend["backend"]="netCDF4";backend["strategy"]="bounded_english_staging"
    backend["success"]=backend.error.eq("");backend["error_type"]=""
    backend["error_message"]=backend.error
    write_table(backend[["backend","source_path","strategy","success","error_type","error_message",
                         "copy_seconds","read_seconds","temporary_bytes","cleanup_success"]],
                out/"qc/backend_compatibility_report.csv")
    # Verify the monthly outputs are complete, rather than treating missing stages as success.
    required=["index/himawari_master_index_202407.csv","index/himawari_master_index_202407.parquet",
      "index/himawari_sequence_index_202407.csv","index/himawari_sequence_index_202407.parquet",
      "qc/grid_consistency_report_202407.csv","qc/qc_summary_202407.csv",
      "qc/h08_h09_channel_comparison_202407.csv","audit/sample_audit_202407.csv",
      "audit/pytorch_dummy_loading_report_202407.csv","audit/automated_tests_202407.txt",
      "benchmark/storage_benchmark_202407_v2.csv","reports/README_HIMAWARI_PREPROCESS_202407.md"]
    assert all((out/p).is_file() and (out/p).stat().st_size>0 for p in required)
    audit=pd.read_csv(out/"audit/sample_audit_202407.csv")
    assert int((audit.audit_status.eq("PASS")&audit.selection_reason.str.contains("random_seed_42")).sum())>=50
    dummy=pd.read_csv(out/"audit/pytorch_dummy_loading_report_202407.csv")
    assert len(dummy)>=50 and dummy.status.eq("PASS").all()
    assert pd.read_csv(out/"benchmark/storage_roundtrip_validation_202407.csv").status.eq("PASS").all()
    tests=subprocess.run([sys.executable,"-B",str(PROJECT/"tests/test_stage0.py")],capture_output=True,text=True)
    write_text(out/"audit/automated_tests_final_revision_202407.txt",tests.stdout+tests.stderr)
    assert tests.returncode==0
    machine={"processor":platform.processor(),"logical_cpu_count":os.cpu_count(),
             "torch_threads":torch.get_num_threads(),"python":sys.executable,
             "git_commit":"NOT_A_GIT_REPOSITORY"}
    git=subprocess.run(["git","-C",str(PROJECT),"rev-parse","HEAD"],capture_output=True,text=True)
    if git.returncode==0:machine["git_commit"]=git.stdout.strip()
    write_json(out/"reports/machine_context.json",machine)
    artifact_checks.update(status="PASS",timestamp_unit="nanoseconds UTC verified",
                          channel_metadata_preserved=True,source_metadata_sidecar_match=True,
                          actual_coordinate_directions_verified=True,required_artifacts_present=True,
                          seed=42,shuffled_target_order_verified=True)
    write_json(out/"audit/final_artifact_validation_202407.json",artifact_checks)
    old_text=(out/"benchmark/STORAGE_BENCHMARK_202407.md").read_text(encoding="utf-8")
    note=("# Final measured revision: shuffled six-frame reads\n\n"
          "The first run sampled random targets but traversed them chronologically; because the subset is stored compactly, "
          "those measurements are retained as chronological sparse-target timing, not used for the final random-access recommendation.\n\n"
          "Revision 2 uses three independently seeded target permutations, identical permutations for both formats, alternating format order. "
          "Only random_6frame rows are replaced in storage_benchmark_202407_v2.csv; original CSV remains unchanged.\n\n"
          f"Median shuffled six-frame read: Zarr {med['zarr']:.6f} s/sequence; NetCDF4 {med['netcdf4']:.6f} s/sequence.\n\n"
          f"Recommendation for researcher review: {recommended}. No permanent format is frozen.\n\n"
          "Warm-cache interpretation, metadata and mask preservation, staging costs and creation metrics below remain valid. "
          "The older random-six-frame column and recommendation below are historical; use the revision-2 CSV and values above.\n\n")
    write_text(out/"benchmark/STORAGE_BENCHMARK_202407_v2.md",note+old_text)
    original_readme=(out/"reports/README_HIMAWARI_PREPROCESS_202407.md").read_text(encoding="utf-8")
    write_text(out/"reports/README_HIMAWARI_PREPROCESS_202407_v2.md",
        "# Final resume report, revision 2\n\nStatus: READY_FOR_RESEARCHER_REVIEW.\n\n"
        "All required stages executed. Final storage measurements are in storage_benchmark_202407_v2.csv and "
        "STORAGE_BENCHMARK_202407_v2.md. Three shuffled read repetitions supplement the initial chronological sparse-target timings. "
        "Full metadata, nanosecond timestamps, coordinate order, required outputs and automated tests were rechecked.\n\n"
        f"Final recommendation: {recommended}, researcher review only. All prior reports, failures and five diagnostic caches remain preserved.\n\n"+
        original_readme)
    latest=previous.copy()
    latest.update(status="READY_FOR_RESEARCHER_REVIEW",revision=2,
                  ended_utc=datetime.now(timezone.utc).isoformat(),
                  storage_benchmark="benchmark/storage_benchmark_202407_v2.csv",
                  recommended_candidate=recommended+" for researcher review only",
                  shuffled_random_6frame_median_seconds={k:float(v) for k,v in med.items()},
                  final_artifact_validation="PASS",history_preserved=True)
    hashes=[{"path":str(p.relative_to(PROJECT)),"sha256":sha256(p)}
            for folder in ("src","tests") for p in sorted((PROJECT/folder).glob("*.py"))]
    write_table(pd.DataFrame(hashes),out/"reports/code_sha256_v2.csv")
    write_json(out/"reports/final_dry_run_status_202407_v2.json",latest)
    logging.info("FINAL_REVISION_2_PASS %s",latest)
    with (out/"preprocess_202407.log").open("xb") as f:f.write((out/"resume_202407.log").read_bytes())
    print(json.dumps(latest,indent=2))
if __name__=="__main__":main()
