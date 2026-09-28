"""CPU tensor loading only; no model, optimizer, or normalization statistics."""
from datetime import datetime
import time,logging
import numpy as np
import pandas as pd
import torch
from common import MemoryMonitor,write_table
from read_himawari import load_himawari_sequence
from sample_audit import frame_paths

def dummy_loading(selection,staging,out):
    selected=selection[selection.selection_reason.str.contains("random_seed_42")]
    rows=[]
    for i,row in enumerate(selected.to_dict("records")):
        started=time.perf_counter()
        with MemoryMonitor() as memory:
            x,m=load_himawari_sequence(frame_paths(row),staging,datetime.fromisoformat(row["target_time_utc"]))
            tensor=torch.from_numpy(x).to(dtype=torch.float32)
            mask=torch.from_numpy(m)
            h,w=x.shape[-2:]
            flat=tensor.reshape(42,h,w)
            batched=flat.unsqueeze(0)
            assert tensor.shape==(6,7,h,w) and flat.shape==(42,h,w) and batched.shape==(1,42,h,w)
            assert tensor.dtype==torch.float32 and mask.dtype==torch.bool
            nan_count=int(torch.isnan(tensor).sum().item())
            assert nan_count==int((~m).sum())
            rows.append(dict(target_time=row["target_time_utc"],status="PASS",dtype=str(tensor.dtype),
                             shape=str(tuple(tensor.shape)),flat_shape=str(tuple(flat.shape)),
                             batch_shape=str(tuple(batched.shape)),mask_shape=str(tuple(mask.shape)),
                             nan_count=nan_count,load_seconds=time.perf_counter()-started))
            del x,m,tensor,mask,flat,batched
        rows[-1].update(memory.report())
        if (i+1)%10==0:logging.info("PyTorch dummy loading %d/%d",i+1,len(selected))
    report=pd.DataFrame(rows)
    write_table(report,out/"audit/pytorch_dummy_loading_report_202407.csv")
    assert len(report)>=50 and report.status.eq("PASS").all()
    return report
