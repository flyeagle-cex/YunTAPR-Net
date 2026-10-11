"""Frozen public identity gate and checks affected by final safety edits."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sqlite3
import torch
from yuntapr.training.phase_b_v2_seed2026.data import Plan
from yuntapr.training.phase_b_v2_seed2026.protocol import OUT,LOCAL,ROOT,ORDER,LIMITS,CAMPAIGN,digest,atomic_json
from yuntapr.training.phase_b_v2_seed2026.resources import memory
from yuntapr.training.phase_b_v2_seed2026.checkpoint import Store
from yuntapr.training.phase_b_v2_seed2026.quota import Ledger

class MetadataBudget:
    def __init__(self):self.bytes=0
    def check(self):return memory()
    def admit_bytes(self,n):assert 0<n<128*1024**2
    def account_bytes(self,n):self.bytes+=n
    def emit(self,*args,**kwargs):pass

def main():
    budget=MetadataBudget();plan=Plan(budget)
    result=dict(status='PASS',metadata_only=True,raw_data_reads=0,optimizer_steps=0,
        train_scenes=len(plan.ids(2023)),development_scenes=len(plan.ids(2024)),
        distinct_files=len(plan.scope.entries),late_creation_references=plan.late_creation,
        original_order_and_pair_qualification=True,data_identity=plan.identity,public_metadata_bytes=budget.bytes)
    folder=LOCAL/'final_affected_checks';folder.mkdir(exist_ok=False)
    class C:
        key=digest({'cpu_fixture':True})
        def validate(self,p):assert p=={'engineering_only':'no_model_no_optimizer'}
    store=Store(folder/'checkpoint',C())
    try:
        ref=store.save('cpu_fixture',{'engineering_only':'no_model_no_optimizer'})
        assert store.read(ref)=={'engineering_only':'no_model_no_optimizer'}
        assert len(store.directories)>=6
    finally:store.close()
    q=Ledger.__new__(Ledger);q.con=sqlite3.connect(':memory:',isolation_level=None)
    q.con.executescript("CREATE TABLE campaign(status TEXT);INSERT INTO campaign VALUES('FAILED_NO_RETRY');")
    try:q.reserve('unused',1)
    except PermissionError:pass
    else:raise AssertionError('FAILED_CAMPAIGN_RESERVATION_NOT_REJECTED')
    finally:q.close()
    result['affected_checks']=['registered_checkpoint_ancestor_handles','failed_campaign_cannot_reserve']
    # Every pre-existing tracked file stays byte-identical to the known baseline.
    import subprocess
    changed=subprocess.check_output(['git','diff','--name-only','2131d576906e3dc6a4cbb91f2d03ea38331d3b42'],cwd=ROOT,text=True).splitlines()
    assert not changed,changed
    result['all_preexisting_tracked_files_unchanged']=True
    atomic_json(OUT/'final_prelaunch_checks.json',result)
    atomic_json(OUT/'execution_scope.json',dict(campaign=CAMPAIGN,authorization_basis='LATEST_DIRECT_HUMAN_RESEARCHER_INSTRUCTION',
        authorized_seed=2026,ordered_runs=[dict(model=m,arm=a,seed=2026) for m,a in ORDER],
        design='D1/Q1/N0/I3/B9/S0/V0',statistics='M-C',epochs_per_run=9,updates_per_epoch=5228,
        updates_per_run=47052,total_attempt_cap=282312,data=plan.identity,resource_hard_limits=LIMITS,
        approval_exclusions=['seed2027','seed2028','2025','FinalFit','automatic retry','automatic LAST recovery','historical B1 ratification'],
        interpretation='2024 DEVELOPMENT EXPLORATORY; NO CONFIRMATORY SIGNIFICANCE',
        historical_2025_path_attributes='NOT_INSTRUMENTED'))
    print(json.dumps({k:v for k,v in result.items() if k!='data_identity'},ensure_ascii=False))

if __name__=='__main__':main()
