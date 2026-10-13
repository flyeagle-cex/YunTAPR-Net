"""Readonly, metadata-only gate before consuming the one approved new launch."""
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).absolute().parents[1]
sys.path.insert(0,str(ROOT/'src'))
START=time.monotonic()
from yuntapr.training.phase_b_v2_seed2026_v2.data import Plan,Adapter
from yuntapr.experimental.phase_b_v2_real_forward_pilot.resources import memory
from yuntapr.training.phase_b_v2_seed2026_resume_v2.protocol import OUT,LOCAL,LIMITS,atomic_json

class MetadataBudget:
    def __init__(self):self.bytes=0;self.events=[]
    def check(self):
        if time.monotonic()-START>300:raise TimeoutError('METADATA_ONLY_PRELAUNCH_300_SECOND_CAP')
        m=memory()
        if m['working_set_bytes']>LIMITS['max_working_set_bytes']:raise MemoryError('METADATA_WORKING_SET')
        return m
    def admit_bytes(self,n):
        self.check()
        if self.bytes+n>128*1024**2:raise MemoryError('PUBLIC_METADATA_128_MIB_BOUND')
    def account_bytes(self,n):self.bytes+=n
    def emit(self,event,**fields):self.events.append(dict(event=event,**fields))

def main():
    OUT.mkdir(exist_ok=True);LOCAL.mkdir(exist_ok=True)
    if (LOCAL/'launch.once').exists():raise PermissionError('PRELAUNCH_ONLY_NO_RECHECK_LIVE_TASK')
    budget=MetadataBudget();adapter=None
    try:
        plan=Plan(budget);adapter=Adapter(plan,budget)
        adapter.reader.lock_parents();metadata=adapter.reader.full_metadata_gate()
        row=dict(status='PRELAUNCH_FROZEN_DIRECTORY_AND_METADATA_PASS',directory_handles=len(adapter.reader.handles),
            metadata=metadata,data_identity=plan.identity,public_metadata_bytes=budget.bytes,
            elapsed_seconds=time.monotonic()-START,raw_content_bytes=0,optimizer_attempts=0,
            model_constructed=False,locks_reacquired_and_retained_by_actual_worker=True)
        atomic_json(OUT/'prelaunch_directory_gate.json',row)
        print(json.dumps({k:row[k] for k in ('status','directory_handles','public_metadata_bytes','elapsed_seconds','raw_content_bytes')}))
    except BaseException as e:
        atomic_json(LOCAL/'prelaunch_failure.json',dict(status='FAIL',error_type=type(e).__name__,elapsed_seconds=time.monotonic()-START))
        raise
    finally:
        if adapter is not None:adapter.reader.close()

if __name__=='__main__':main()
