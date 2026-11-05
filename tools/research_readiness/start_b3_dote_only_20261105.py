"""Once-only hidden independent dispatcher for the new bounded ablation."""
import argparse,base64,json,os,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
from train_b3_dote_only_20261105 import validate_proposal,read,sha,write
from start_independent_process import host_identity,require_independent


def now():return datetime.now(timezone.utc).isoformat()


def spawn(proposal,approval):
    p,a=validate_proposal(proposal,approval)
    folder=Path(p['output_root']+'_dispatch')
    if folder.exists() or Path(p['output_root']).exists():raise PermissionError('Already claimed; no retry')
    folder.mkdir()
    write(folder/'launch_claim.json',dict(at=now(),proposal_sha256=p['proposal_sha256'],actual_researcher_reply=a['actual_researcher_reply'],automatic_retry=False))
    command=subprocess.list2cmdline([p['runtime']['python'],'-B',str(Path(__file__).resolve()),'supervise','--proposal',str(proposal),'--approval',str(approval)])
    payload=base64.b64encode(json.dumps(dict(command=command,cwd=str(ROOT)),ensure_ascii=False).encode()).decode()
    script="""$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$r=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String([Console]::In.ReadToEnd()))|ConvertFrom-Json
$s=New-CimInstance -ClassName Win32_ProcessStartup -ClientOnly -Property @{ShowWindow=[uint16]0;CreateFlags=[uint32]16777216}
$p=Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine=$r.command;CurrentDirectory=$r.cwd;ProcessStartupInformation=$s}
@{return_value=$p.ReturnValue;supervisor_pid=$p.ProcessId}|ConvertTo-Json -Compress
"""
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],input=payload,text=True,encoding='utf-8',errors='replace',capture_output=True,timeout=20,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    creation=json.loads(result.stdout);write(folder/'wmi_creation.json',dict(at=now(),**creation))
    if creation['return_value']!=0:raise RuntimeError('Creation failed; no retry')
    print(json.dumps(creation))


def supervise(proposal,approval):
    p,a=validate_proposal(proposal,approval);folder=Path(p['output_root']+'_dispatch')
    identity=host_identity();write(folder/'independence.json',dict(at=now(),**identity));require_independent(identity)
    environment=dict(os.environ,**p['runtime']['environment'],PYTHONPATH=p['runtime']['torch_site'],PYTHONIOENCODING='utf-8',PYTHONNOUSERSITE='1')
    environment.pop('CUDA_VISIBLE_DEVICES',None)
    command=[p['runtime']['python'],'-B',str(ROOT/'tools/research_readiness/train_b3_dote_only_20261105.py'),'--proposal',str(proposal),'--approval',str(approval)]
    with (folder/'stdout.log').open('xb') as stdout,(folder/'stderr.log').open('xb') as stderr:
        process=subprocess.Popen(command,cwd=ROOT,env=environment,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,close_fds=True,creationflags=subprocess.CREATE_NO_WINDOW)
        write(folder/'target_launch.json',dict(at=now(),pid=process.pid,supervisor_pid=os.getpid(),proposal_sha256=p['proposal_sha256']))
        try:code=process.wait(timeout=p['budget']['max_wall_seconds'])
        except subprocess.TimeoutExpired:
            process.kill();process.wait();write(folder/'target_exit.json',dict(at=now(),pid=process.pid,status='DEADLINE_NO_RETRY'));raise
    write(folder/'target_exit.json',dict(at=now(),pid=process.pid,return_code=code,automatic_retry=False))
    return code


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('spawn','supervise'));parser.add_argument('--proposal',type=Path,required=True);parser.add_argument('--approval',type=Path,required=True);a=parser.parse_args()
    proposal=a.proposal.resolve();approval=a.approval.resolve()
    if a.mode=='spawn':spawn(proposal,approval)
    else:raise SystemExit(supervise(proposal,approval))
