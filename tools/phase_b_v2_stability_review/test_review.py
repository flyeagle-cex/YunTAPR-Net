"""New diagnosis/postmortem tests, <=15s per artificial process case, 0 allocation."""
from pathlib import Path
from datetime import datetime,timezone
import copy,hashlib,json,os,secrets,sys,time,unittest
ROOT=Path(__file__).absolute().parents[2];sys.path.insert(0,str(ROOT/'src'));os.environ['PYTHONPATH']=str(ROOT/'src')
from yuntapr.experimental.phase_b_v2_stability_review.classification import classify,scope,identity
from yuntapr.experimental.phase_b_v2_stability_review.receipts import LOCAL,save,verify
from yuntapr.experimental.phase_b_v2_stability_review import native
from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.winjob import Job,exited,memory

NOW='2026-10-18T01:00:00+00:00';BOOT='2026-10-17T23:24:30+00:00'
RUN=LOCAL/'tests'/('run_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+secrets.token_hex(4))
RUN.mkdir(parents=True,exist_ok=False)
CASES=[]

def snapshot(**kw):return dict(ledger_state='ACTIVE',heartbeat_utc='2026-10-17T12:51:02+00:00',termination_receipt_present=False,last_claimed=False,**kw)
def probes(owner='ABSENT',worker='ABSENT',job='ABSENT',pids=None):
    return dict(owner=dict(status=owner),worker=dict(status=worker),job=dict(status=job,pids=pids or []))

class ReviewTests(unittest.TestCase):
    def test_01_unclean_after_boot_no_last(self):
        r=classify(snapshot(),probes(),NOW,BOOT)
        self.assertEqual(r['effective_state'],'STOPPED_UNCLEAN_NO_LAST');self.assertTrue(r['heartbeat_before_current_boot'])
        self.assertTrue(r['observed_process_tree_empty']);self.assertFalse(r['resume_allowed'])
    def test_02_live_old_heartbeat_never_cleared(self):
        r=classify(snapshot(),probes(owner='LIVE_MATCH',worker='LIVE_MATCH',job='PRESENT',pids=[1]),NOW,BOOT)
        self.assertEqual(r['effective_state'],'LIVE_HEARTBEAT_STALE');self.assertFalse(r['observed_process_tree_empty'])
    def test_03_probe_failure_not_dead(self):
        for member in ('owner','worker','job'):
            p=probes();p[member]['status']='UNKNOWN'
            self.assertEqual(classify(snapshot(),p,NOW,BOOT)['effective_state'],'NOT_VERIFIED_NATIVE_PROBE')
    def test_04_orphan_job_blocks_restart(self):
        self.assertEqual(classify(snapshot(),probes(job='PRESENT',pids=[99]),NOW,BOOT)['effective_state'],'ORPHAN_JOB_PRESENT_DO_NOT_RESTART')
    def test_05_identity_mismatch_is_not_our_live_process(self):
        self.assertEqual(classify(snapshot(),probes(owner='PID_REUSED'),NOW,BOOT)['effective_state'],'STOPPED_UNCLEAN_NO_LAST')
    def test_06_last_claim_does_not_validate_weights(self):
        s=snapshot();s['last_claimed']=True;r=classify(s,probes(),NOW,BOOT)
        self.assertEqual(r['effective_state'],'STOPPED_UNCLEAN_LAST_NOT_VERIFIED');self.assertFalse(r['resume_allowed'])
    def test_07_old_receipt_not_new_cleanup(self):
        s=snapshot();s['termination_receipt_present']=True;s['ledger_state']='PAUSED'
        r=classify(s,probes(),NOW,BOOT);self.assertEqual(r['effective_state'],'STOPPED_WITH_PRIOR_RECEIPT_REQUIRES_SEPARATE_VALIDATION')
        self.assertEqual(r['historical_cleanup_execution'],'NOT_VERIFIED')
    def test_08_clock_skew_blocks_death_inference(self):
        self.assertEqual(classify(snapshot(),probes(),'2026-10-16T00:00:00+00:00',BOOT)['effective_state'],'NOT_VERIFIED_CLOCK_SKEW')
    def test_09_scope_nonce_job_and_bad_identity(self):
        me=dict(pid=10,creation_filetime=20,image_path_key='a'*64)
        owner=dict(**me,campaign='TEST',session=1,nonce='b'*32,job_name='Local\\TEST__1__'+'b'*32)
        worker=dict(**me,campaign='TEST',nonce='b'*32);scope(owner,worker,'TEST',1)
        for k,v in [('nonce','x'),('job_name','Local\\FOREIGN'),('campaign','OTHER')]:
            with self.assertRaises(ValueError):scope(dict(owner,**{k:v}),worker,'TEST',1)
        for bad in (dict(me,pid=True),dict(me,creation_filetime=0),dict(me,image_path_key='invalid')):
            with self.assertRaises(ValueError):identity(bad)
    def test_10_missing_registration_cannot_establish_identity(self):
        with self.assertRaises(ValueError):scope({}, {}, 'TEST',1)
    def test_11_append_only_receipt_and_integrity(self):
        folder=RUN/'receipts';r=classify(snapshot(),probes(),NOW,BOOT)
        first=save(r,folder=folder);before=first.read_bytes();second=save(r,folder=folder)
        self.assertNotEqual(first,second);self.assertEqual(first.read_bytes(),before)
        self.assertFalse(verify(first)['original_termination_receipt'])
        row=json.loads(second.read_bytes());row['record']['resume_allowed']=True
        second.write_bytes(json.dumps(row).encode())
        with self.assertRaises(ValueError):verify(second)
    def test_12_partial_receipt_is_not_committed(self):
        folder=RUN/'fault'
        with self.assertRaises(OSError):save({'artificial':True},folder=folder,fault='after_fsync')
        self.assertEqual(list(folder.glob('*.json')),[]);self.assertEqual(len(list(folder.glob('*.part'))),1)
    def test_13_receipt_scope_rejected_before_write(self):
        for p in (ROOT,LOCAL,LOCAL/'tests/../escape',LOCAL/'2025'):
            with self.assertRaises(PermissionError):save({},folder=p)
    def test_14_artificial_live_and_wrong_identity_no_kill(self):
        folder=RUN/'live';folder.mkdir();nonce=secrets.token_hex(16);job=Job();start=time.monotonic()
        try:
            pid=job.spawn([sys.executable,'-m','yuntapr.experimental.phase_b_v2_stability_review.fixture','child',str(folder),nonce],ROOT)
            deadline=start+5
            while not (folder/'child.json').exists():
                if time.monotonic()>deadline:raise TimeoutError('ARTIFICIAL_REGISTER_TIMEOUT')
                job.snapshot();time.sleep(.01)
            ident=json.loads((folder/'child.json').read_bytes())
            self.assertEqual(native.process(ident)['status'],'LIVE_MATCH')
            wrong=dict(ident,creation_filetime=ident['creation_filetime']+1)
            self.assertEqual(native.process(wrong)['status'],'PID_REUSED')
            self.assertFalse(exited(job.root));resources=memory(job.root)
        finally:
            job.stop();deadline=time.monotonic()+5
            while (job.pids() or any(h and not exited(h) for h in job.handles.values())) and time.monotonic()<deadline:time.sleep(.01)
            empty=not job.pids() and all(not h or exited(h) for h in job.handles.values())
            CASES.append(dict(case='live_identity_then_owned_cleanup',elapsed_seconds=time.monotonic()-start,
                job_empty_and_handles_signaled=empty,identities=list(job.identities.values()),
                resource_sample=locals().get('resources'),controlled_allocation_bytes=0));job.close()
        self.assertTrue(empty);self.assertIn(native.process(ident)['status'],('ABSENT','EXITED','PID_REUSED'))
        self.assertLess(time.monotonic()-start,15)
    def test_15_artificial_owner_crash_kills_tree_and_missing_finalizer_is_detected(self):
        folder=RUN/'owner_crash';folder.mkdir();nonce=secrets.token_hex(16);outer=Job();start=time.monotonic()
        try:
            outer.spawn([sys.executable,'-m','yuntapr.experimental.phase_b_v2_stability_review.fixture','owner-crash',str(folder),nonce],ROOT)
            deadline=start+6
            while not (folder/'owner.json').exists() or not exited(outer.root):
                if time.monotonic()>deadline:raise TimeoutError('ARTIFICIAL_OWNER_CRASH_TIMEOUT')
                outer.snapshot();time.sleep(.01)
            owner=json.loads((folder/'owner.json').read_bytes());child=json.loads((folder/'child.json').read_bytes())
            approved=scope(owner,child,'ARTIFICIAL_POSTMORTEM_V1',1)
            deadline=start+9
            while (outer.pids() or any(h and not exited(h) for h in outer.handles.values())) and time.monotonic()<deadline:time.sleep(.01)
            self.assertFalse(outer.pids())
            p=dict(owner=native.process(approved['owner']),worker=native.process(approved['worker']),job=native.job(approved['job_name']))
            while (p['owner']['status']=='LIVE_MATCH' or p['worker']['status']=='LIVE_MATCH') and time.monotonic()<deadline:
                time.sleep(.01)
                p=dict(owner=native.process(approved['owner']),worker=native.process(approved['worker']),job=native.job(approved['job_name']))
            self.assertEqual(p['job']['status'],'ABSENT')
            r=classify(snapshot(),p,NOW,BOOT);self.assertEqual(r['effective_state'],'STOPPED_UNCLEAN_NO_LAST')
            self.assertFalse(r['resume_allowed']);self.assertFalse((folder/'termination.json').exists())
            save(dict(artificial_only=True,observation=r),folder=folder/'receipts')
        finally:
            outer.stop();deadline=time.monotonic()+4
            while (outer.pids() or any(h and not exited(h) for h in outer.handles.values())) and time.monotonic()<deadline:time.sleep(.01)
            empty=not outer.pids() and all(not h or exited(h) for h in outer.handles.values())
            CASES.append(dict(case='owner_abrupt_exit_without_finally',elapsed_seconds=time.monotonic()-start,
                job_empty_and_handles_signaled=empty,identities=list(outer.identities.values()),
                postmortem_native_probes=locals().get('p'),controlled_allocation_bytes=0));outer.close()
        self.assertTrue(empty);self.assertLess(time.monotonic()-start,15)
    def test_16_no_heavy_imports(self):
        self.assertNotIn('torch',sys.modules)
    def test_17_empty_job_with_unsignaled_process_is_not_clean(self):
        r=classify(snapshot(),probes(worker='LIVE_MATCH',job='PRESENT'),NOW,BOOT)
        self.assertEqual(r['effective_state'],'LIVE_HEARTBEAT_STALE')
        self.assertFalse(r['observed_process_tree_empty'])

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ReviewTests))
    data=dict(tests=result.testsRun,passed=result.testsRun-len(result.failures)-len(result.errors),
        failures=[(str(t),trace) for t,trace in result.failures],errors=[(str(t),trace) for t,trace in result.errors],
        synthetic_only=True,new_optimizer_updates=0,controlled_allocation_bytes=0,max_case_seconds=15,process_cases=CASES)
    (RUN/'result.json').write_bytes((json.dumps(data,indent=2)+'\n').encode())
    print('RECEIPTS='+str(RUN.relative_to(ROOT)))
    raise SystemExit(not result.wasSuccessful())
