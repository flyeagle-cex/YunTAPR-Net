"""OS-owned on-demand ARTIFICIAL owner adapter. No formal execution entry.

Only the fixed fake owner fixture can be registered. Real recovery integration
requires its independently authorized release/nonce/quota and is not enabled.
"""
from pathlib import Path
import base64,json,os,subprocess,sys
ROOT=Path(__file__).absolute().parents[4]
LOCAL=ROOT/'docs/phase_b_v2_owner_lifetime_repair/v1/.local'

def quote(s):return "'"+str(s).replace("'","''")+"'"

def ps(script):
    encoded=base64.b64encode(script.encode('utf-16-le')).decode('ascii')
    r=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',encoded],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=20)
    if r.returncode:raise RuntimeError('SCHEDULED_ARTIFICIAL_TEST_ERROR_'+str(r.returncode)+': '+r.stderr[-1200:])
    return r.stdout.strip()

def start_artificial_owner(name,folder,nonce,python):
    # This registry accepts ONLY a fixed artificial fixture, never a caller's
    # arbitrary command/module, formal supervisor, input dataset or checkpoint.
    if (not folder.is_absolute() or folder.parent.parent!=LOCAL or not folder.parent.name.startswith('artificial_tasks_')
        or not folder.name.startswith('artificial_') or '..' in folder.parts or '2025' in str(folder)
        or len(nonce)!=32 or any(c not in '0123456789abcdef' for c in nonce) or name!='YunTAPR_ArtificialOwner_'+nonce):
        raise PermissionError('ARTIFICIAL_TASK_SCOPE')
    if type(python) is not str or '2025' in python or '..' in Path(python).parts or not Path(python).is_absolute():
        raise PermissionError('REGISTERED_TEST_INTERPRETER_ONLY')
    runtime=ROOT/'docs/phase_b_v2_formal_execution/seed2027_b1_epoch7_recovery_v1/.local/runtime.json'
    allowed={os.path.normcase(sys.executable),os.path.normcase(json.loads(runtime.read_text(encoding='utf-8'))['python'])}
    if os.path.normcase(python) not in allowed:raise PermissionError('REGISTERED_TEST_INTERPRETER_ONLY')
    # Task Scheduler does not inherit the Codex shell's PYTHONPATH. A fixed
    # ASCII bootstrap binds project imports for both this owner and its worker.
    entry=folder/'fixed_artificial_entry.py'
    entry.write_text("from pathlib import Path\nimport os,sys\nr=Path(__file__).absolute().parents[6]\nos.environ['PYTHONPATH']=str(r/'src')\nsys.path.insert(0,str(r/'src'))\nfrom yuntapr.experimental.phase_b_v2_owner_lifetime_candidate.fixture import main\nmain()\n",encoding='ascii')
    args=subprocess.list2cmdline([str(entry),'owner',str(folder),nonce,'task-owned'])
    script="$ErrorActionPreference='Stop';[Console]::OutputEncoding=[Text.Encoding]::UTF8;"+f"$name={quote(name)};if(Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue){{throw 'No overwrite'}};"
    script+=f"$a=New-ScheduledTaskAction -Execute {quote(python)} -Argument {quote(args)} -WorkingDirectory {quote(ROOT)};"
    script+="$p=New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited;"
    script+="$s=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Seconds 30) -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries;"
    script+="Register-ScheduledTask -TaskName $name -InputObject (New-ScheduledTask -Action $a -Principal $p -Settings $s)|Out-Null;"
    script+="$t=Get-ScheduledTask -TaskName $name;if($t.Triggers.Count -ne 0 -or $t.Settings.RestartCount -ne 0 -or $t.Principal.RunLevel -ne 'Limited'){throw 'Artificial task policy mismatch'};Start-ScheduledTask -TaskName $name;"
    script+="[pscustomobject]@{registered=$true;triggers=0;automatic_retries=0;run_level='Limited'}|ConvertTo-Json -Compress"
    return json.loads(ps(script))
