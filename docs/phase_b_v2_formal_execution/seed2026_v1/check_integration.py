"""New formal envelope checks only; no observations, model, or optimizer step."""
from __future__ import annotations
import ctypes as C
import json
import sqlite3
from pathlib import Path
import torch
from yuntapr.training.phase_b_v2_seed2026 import data,engine,evaluation,worker,supervisor,checkpoint
from yuntapr.training.phase_b_v2_seed2026.protocol import OUT,LOCAL,ORDER,CAMPAIGN,LIMITS,epoch_order,TRAIN_N,STEPS,digest,atomic_json,run_id
from yuntapr.training.phase_b_v2_seed2026.quota import Ledger
from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.winjob import ExtendedLimit,query_job,checked
from yuntapr.experimental.phase_b_v2_ablations.config import get_config,learning_rate_prefix

def main():
    LOCAL.mkdir(exist_ok=True);folder=LOCAL/'integration_checks';folder.mkdir(exist_ok=False)
    rows=[]
    def test(name,fn):
        try:fn();rows.append(dict(name=name,status='PASS'))
        except BaseException as exc:rows.append(dict(name=name,status='FAIL',error_type=type(exc).__name__,detail=str(exc)))
    def scope():
        assert len(ORDER)==6 and 6*9*STEPS==282312
        assert [get_config(a).gamma for _,a in ORDER]==[2,2,0,0,2,2]
        assert [get_config(a).lambda_q for _,a in ORDER]==[1,1,1,1,2,2]
        assert learning_rate_prefix(5228)==1e-4 and learning_rate_prefix(47052)>1e-6
    test('closed_six_run_budget_and_S0',scope)
    def coverage():
        ids=tuple('fixture_'+str(i) for i in range(TRAIN_N))
        for epoch in range(1,10):
            order=epoch_order(ids,epoch);assert order==epoch_order(ids,epoch) and set(order)==set(ids)
            batches=[order[i:i+2] for i in range(0,TRAIN_N,2)]
            assert len(batches)==STEPS and len(batches[-1])==1
    test('new_full_size_B9_coverage_without_updates',coverage)
    class TinyContract:
        key=digest({'test':'transport_only'})
        def validate(self,p):
            assert set(p)=={'synthetic_cpu_fixture'} and torch.equal(p['synthetic_cpu_fixture'],torch.tensor([1.,2.]))
    def transport():
        store=checkpoint.Store(folder/'transport',TinyContract())
        try:
            ref=store.save('fixture',dict(synthetic_cpu_fixture=torch.tensor([1.,2.])))
            assert torch.equal(store.read(ref)['synthetic_cpu_fixture'],torch.tensor([1.,2.]))
            receipt=store.receipt(ref);assert receipt['same_bytes_deserialized']
            try:store.read(Path('F:/forbidden/2025/foreign.ref.json'))
            except PermissionError:pass
            else:raise AssertionError('external_path_not_rejected')
        finally:store.close()
    test('formal_transport_registered_same_bytes_and_external_rejection',transport)
    def quota():
        q=Ledger.__new__(Ledger);q.con=sqlite3.connect(folder/'quota_fixture.sqlite',isolation_level=None)
        q.con.executescript('''CREATE TABLE campaign(id TEXT PRIMARY KEY,status TEXT,reason TEXT);
        CREATE TABLE runs(id TEXT PRIMARY KEY,ordinal INTEGER,status TEXT,epoch INTEGER,updates INTEGER,last_sha TEXT);
        CREATE TABLE attempts(n INTEGER PRIMARY KEY,run TEXT,update_no INTEGER,status TEXT,UNIQUE(run,update_no));
        CREATE TABLE epochs(run TEXT,epoch INTEGER,phase TEXT,train TEXT,validation TEXT,last_receipt TEXT,PRIMARY KEY(run,epoch));''')
        q.con.execute('INSERT INTO campaign VALUES(?,?,NULL)',(CAMPAIGN,'ACTIVE'))
        for i,(m,a) in enumerate(ORDER):q.con.execute('INSERT INTO runs VALUES(?,?,?,?,?,NULL)',(run_id(m,a),i,'PENDING',0,0))
        ident=run_id(*ORDER[0]);q.start_run(ident);q.begin_epoch(ident,1);q.reserve(ident,1)
        try:q.reserve(ident,1)
        except sqlite3.IntegrityError:pass
        else:raise AssertionError('duplicate_attempt')
        assert q.snapshot()['reserved']==1 and q.snapshot()['returned_verified']==0
        q.fail('ARTIFICIAL_FAILURE')
        try:q.start_run(run_id(*ORDER[1]))
        except PermissionError:pass
        else:raise AssertionError('failed_campaign_continued')
        assert q.snapshot()['reserved']==1;q.close()
    test('persistent_nonrefundable_reservation_and_failed_scope',quota)
    def joblimits():
        job=supervisor.FormalJob()
        try:
            limits=ExtendedLimit();checked(query_job(job.handle,9,C.byref(limits),C.sizeof(limits),None))
            assert limits.job_memory==LIMITS['max_job_commit_bytes'] and limits.process_memory==LIMITS['max_process_commit_bytes']
            assert limits.basic.flags & 0x2000 and not limits.basic.flags & 0x800
            assert job.pids()==[]
        finally:job.close()
    test('actual_kernel_formal_limits_no_child_launch',joblimits)
    def refusal():
        try:checkpoint.Store.restore(None)
        except PermissionError:pass
        else:raise AssertionError('unapproved_restore')
        try:run_id('B0_MATCHED_V2','E3')
        except PermissionError:pass
        else:raise AssertionError('extra_arm')
    test('no_unapproved_restore_or_extra_arm',refusal)
    report=dict(checks=rows,passed=sum(r['status']=='PASS' for r in rows),failed=sum(r['status']=='FAIL' for r in rows),
        model_forward_calls=0,optimizer_steps=0,raw_data_reads=0,checkpoint_fixture='CPU_TENSOR_ONLY')
    atomic_json(OUT/'integration_test_results.json',report)
    print(json.dumps(report,ensure_ascii=False));return bool(report['failed'])

if __name__=='__main__':raise SystemExit(main())
