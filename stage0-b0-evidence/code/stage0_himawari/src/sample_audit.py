"""Reproducible random and targeted audits; incomplete inputs are explicit outcomes."""
from __future__ import annotations
import logging,time
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
from config import RAW,CONFIG
from common import MemoryMonitor,write_table,write_json
from read_himawari import load_himawari_sequence

LABELS=["t"]+[f"t_minus_{i*10}" for i in range(1,6)]
def frame_paths(row):
    return [RAW/row["path_"+label] for label in LABELS]

def select_samples(sequences,master):
    usable=sequences[sequences.sequence_complete & sequences.loadable]
    if len(usable)<50:raise RuntimeError(f"Only {len(usable)} complete loadable sequences; need >=50")
    rng=np.random.default_rng(CONFIG["seed"])
    chosen={}
    def add(target,reason):
        chosen.setdefault(target,[]).append(reason)
    random=usable.iloc[np.sort(rng.choice(len(usable),size=50,replace=False))]
    for t in random.target_time_utc:add(t,"random_seed_42")
    for t in sequences.head(6).target_time_utc:add(t,"month_boundary")
    for flag in ["ALL_FILL","PARTIAL_VALID","GRID_VARIANT","COORD_ANOMALY","READ_ERROR","OTHER"]:
        for t in master.loc[master["flags"].str.contains(flag,regex=False),"timestamp_filename_utc"].dropna().head(2):
            if t in set(sequences.target_time_utc):add(t,flag)
    for _,g in master.groupby("grid_tag"):
        t=g.timestamp_filename_utc.dropna().iloc[0]
        if t in set(sequences.target_time_utc):add(t,"grid_tag_representative")
    for t in sequences.loc[sequences.contains_satellite_transition,"target_time_utc"].head(4):
        add(t,"satellite_transition")
    for t in sequences.loc[~sequences.sequence_complete,"target_time_utc"].head(3):
        add(t,"incomplete_sequence")
    result=sequences[sequences.target_time_utc.isin(chosen)].copy()
    result["selection_reason"]=result.target_time_utc.map(lambda t:";".join(chosen[t]))
    return result

def sample_audit(sequences,master,staging,out):
    selection=select_samples(sequences,master)
    write_table(selection,out/"audit/random_and_targeted_sample_list_202407.csv",parquet=True)
    rows=[]
    for i,row in enumerate(selection.to_dict("records")):
        started=time.perf_counter()
        result=dict(target_time=row["target_time_utc"],selection_reason=row["selection_reason"],
                    sequence_complete=row["sequence_complete"],all_paths_exist=False,
                    all_7_channels_exist=False,shape_consistent=False,coords_consistent=False,
                    valid_fraction=None,contains_nan=None,
                    contains_quality_warning=row["contains_quality_warning"],load_seconds=None,
                    memory_peak_mb=None,manual_review_required=True,notes="",audit_status="NOT_RUN")
        if not row["sequence_complete"] or not row["loadable"]:
            present=[RAW/row["path_"+label] for label in LABELS if pd.notna(row["path_"+label])]
            result.update(all_paths_exist=all(p.exists() for p in present) and len(present)==6,
                          audit_status="EXPECTED_UNLOADABLE",notes=row["sequence_quality"])
        else:
            paths=frame_paths(row)
            result["all_paths_exist"]=all(p.exists() for p in paths)
            try:
                with MemoryMonitor() as memory:
                    x,mask=load_himawari_sequence(paths,staging,datetime.fromisoformat(row["target_time_utc"]),
                                                  verify_hash=i<3)
                    assert x.shape[:2]==(6,7) and x.dtype==np.float32
                    assert mask.shape==x.shape and mask.dtype==bool
                    assert np.isnan(x[~mask]).all() and np.isfinite(x[mask]).all()
                    result.update(all_7_channels_exist=True,shape_consistent=True,coords_consistent=True,
                                  valid_fraction=float(mask.mean()),contains_nan=bool(np.isnan(x).any()),
                                  manual_review_required=bool(row["contains_quality_warning"]),
                                  audit_status="PASS",notes="Nominal UTC order verified; internal times remain QC warnings.")
                    del x,mask
                result.update(memory.report())
            except Exception as error:
                result.update(audit_status="FAIL",notes=f"{type(error).__name__}: {error}")
        result["load_seconds"]=time.perf_counter()-started
        rows.append(result)
        if (i+1)%10==0:logging.info("Sample audit %d/%d",i+1,len(selection))
    report=pd.DataFrame(rows)
    write_table(report,out/"audit/sample_audit_202407.csv")
    random_rows=report[report.selection_reason.str.contains("random_seed_42")]
    assert len(random_rows)>=50 and random_rows.audit_status.eq("PASS").all(),"Random 50 sample audit failed"
    assert not report.audit_status.eq("FAIL").any(),"Targeted load failed"
    return selection,report
