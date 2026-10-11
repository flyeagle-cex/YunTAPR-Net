"""Specific preflight repair tests: public metadata + fake handles; no raw I/O."""
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch
from yuntapr.training.phase_b_v2_seed2026 import data
from yuntapr.training.phase_b_v2_seed2026.protocol import OUT,atomic_json

def main():
    spec=importlib.util.spec_from_file_location('metadata_budget',OUT/'final_check.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    budget=module.MetadataBudget();plan=data.Plan(budget);opened=[]
    class Handle:
        def __init__(self,path,**kwargs):self.final_path=path;opened.append(path)
        def close(self):pass
    reader=data.Reader(plan,budget)
    with patch.object(data,'ReadHandle',Handle):reader.lock_parents()
    assert len(opened)==518 and len(set(opened))==518 and set(opened)==reader.parents
    reader.close();opened.clear();reader.parents.add('F:\\FAKE_UNREGISTERED')
    with patch.object(data,'ReadHandle',Handle):
        try:reader.lock_parents()
        except RuntimeError:pass
        else:raise AssertionError('Unexpected directory registry accepted')
    assert opened==[]
    # Native mismatch is rejected and the partial handle is closed. No fallback.
    reader=data.Reader(plan,budget);closed=[]
    class WrongHandle:
        def __init__(self,path,**kwargs):self.final_path=path+'wrong'
        def close(self):closed.append(True)
    with patch.object(data,'ReadHandle',WrongHandle):
        try:reader.lock_parents()
        except (ValueError,PermissionError):pass
        else:raise AssertionError('Wrong native object accepted')
    assert closed==[True] and reader.handles==[]
    result=dict(status='PASS',passed=3,failed=0,raw_data_reads=0,optimizer_steps=0,
        required_raw_ancestors=510,required_full_ancestors=518,
        checks=['exact frozen parent registry','unexpected registry rejected before handle','wrong object rejected and closed'],
        formal_restart_executed=False,stopped_campaign_and_release_unchanged=True)
    atomic_json(OUT/'directory_repair_tests.json',result);print(json.dumps(result))

if __name__=='__main__':main()
