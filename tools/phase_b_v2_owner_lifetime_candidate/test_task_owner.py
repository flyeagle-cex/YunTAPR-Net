"""Actual on-demand OS tasks, artificial clients/owners/workers, no training."""
from pathlib import Path
from ctypes import wintypes as W
from datetime import datetime,timezone
import base64,ctypes as C,json,os,secrets,subprocess,sys,time,unittest
ROOT=Path(__file__).absolute().parents[2];sys.path.insert(0,str(ROOT/'src'));os.environ['PYTHONPATH']=str(ROOT/'src')
from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.winjob import Job,checked,open_process,in_job,native_identity,exited,close_handle,K
from yuntapr.experimental.phase_b_v2_stability_review import native

LOCAL=ROOT/'docs/phase_b_v2_owner_lifetime_repair/v1/.local'
RUN=LOCAL/('artificial_tasks_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'_'+secrets.token_hex(4));RUN.mkdir(parents=True)
terminate=K.TerminateProcess;terminate.argtypes=[W.HANDLE,W.UINT];terminate.restype=W.BOOL
RECORDS=[]

from yuntapr.experimental.phase_b_v2_owner_lifetime_candidate.task_bridge import quote,ps,start_artificial_owner as task_start
def load(path):return json.loads(path.read_text(encoding='utf-8'))
def wait_for(fn,seconds=6):
    end=time.monotonic()+seconds
    while not fn():
        if time.monotonic()>end:raise TimeoutError('ARTIFICIAL_DEADLINE')
        time.sleep(.01)


class Tests(unittest.TestCase):
    def run_case(self,label,crash=False,venv=False):
        folder=RUN/('artificial_'+label);folder.mkdir();nonce=secrets.token_hex(16)
        task='YunTAPR_ArtificialOwner_'+nonce;host=Job();owner_handle=None;registered=False;started=time.monotonic()
        python=load(ROOT/'docs/phase_b_v2_formal_execution/seed2027_b1_epoch7_recovery_v1/.local/runtime.json')['python'] if venv else sys.executable
        owner=worker=None
        try:
            host.spawn([sys.executable,'-m','yuntapr.experimental.phase_b_v2_owner_lifetime_candidate.fixture','client',str(folder),nonce,'legacy'],ROOT)
            wait_for(lambda:(folder/'client.json').exists());client=load(folder/'client.json')
            registration=task_start(task,folder,nonce,python);registered=True
            wait_for(lambda:(folder/'ready.json').exists(),seconds=8)
            owner=load(folder/'owner.json');worker=load(folder/'worker.json')
            self.assertEqual(owner['nonce'],nonce);owner_handle=checked(open_process(0x00100000|0x1000|1,False,owner['pid']))
            self.assertEqual(native_identity(owner_handle),{k:owner[k] for k in ('pid','creation_filetime','image_path_key')})
            member=W.BOOL();checked(in_job(owner_handle,host.handle,C.byref(member)));self.assertFalse(member.value)
            # Closing the artificial Codex Job must kill its client, not the
            # owner created by the OS scheduler in an independent Job tree.
            host.close();wait_for(lambda:native.process(client)['status'] in ('ABSENT','EXITED','PID_REUSED'))
            self.assertEqual(native.process(owner)['status'],'LIVE_MATCH');self.assertEqual(native.process(worker)['status'],'LIVE_MATCH')
            if crash:
                checked(terminate(owner_handle,99));wait_for(lambda:exited(owner_handle))
                wait_for(lambda:native.process(worker)['status'] in ('ABSENT','EXITED','PID_REUSED'))
                self.assertFalse((folder/'termination.json').exists())
            else:
                (folder/'stop.request').write_text('synthetic-only',encoding='utf-8');wait_for(lambda:(folder/'termination.json').exists())
                receipt=load(folder/'termination.json');self.assertTrue(receipt['job_empty']);self.assertFalse(receipt['torch_imported']);wait_for(lambda:exited(owner_handle))
            RECORDS.append(dict(case=label,task=task,registration=registration,client=client,owner=owner,worker=worker,
                owner_outside_artificial_codex_job=True,survived_artificial_codex_close=True,worker_tree_stopped=True,
                forced_owner_exit=crash,elapsed_seconds=time.monotonic()-started))
        finally:
            host.close()
            if owner_handle:
                if not exited(owner_handle):terminate(owner_handle,99);wait_for(lambda:exited(owner_handle))
                close_handle(owner_handle)
            if registered:
                ps("$ErrorActionPreference='Stop';"+f"$t=Get-ScheduledTask -TaskName {quote(task)};if($t.State -eq 'Running'){{Start-Sleep -Milliseconds 200;$t=Get-ScheduledTask -TaskName {quote(task)}}};if($t.State -eq 'Running'){{throw 'Artificial task still running; retain registration'}};Unregister-ScheduledTask -TaskName {quote(task)} -Confirm:$false")
    def test_01_task_owner_survives_codex_job_close_normal_stop(self):self.run_case('normal')
    def test_02_real_venv_wrapper_native_owner_survives(self):self.run_case('venv',venv=True)
    def test_03_task_owner_crash_still_stops_worker_tree(self):self.run_case('owner_crash',crash=True)

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    leftovers=[]
    for row in RECORDS:
        for key in ('client','owner','worker'):
            probe=native.process(row[key])
            if probe['status'] not in ('ABSENT','EXITED','PID_REUSED'):leftovers.append(dict(case=row['case'],role=key,probe=probe))
    report=dict(tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),records=RECORDS,
        leftover_owned_processes=leftovers,synthetic_only=True,raw_data_reads=0,gpu_model_operations=0,optimizer_steps=0,
        pass_all=result.wasSuccessful() and not leftovers)
    (RUN/'results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(results_relative_path=(RUN/'results.json').relative_to(ROOT).as_posix(),pass_all=report['pass_all'])))
    raise SystemExit(not report['pass_all'])
