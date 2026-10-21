"""Register only the fixed GUI artificial bootstrap; cannot launch training."""
from __future__ import annotations
from pathlib import Path
import hashlib, json, os, subprocess
from yuntapr.experimental.phase_b_v2_owner_lifetime_candidate.task_bridge import quote, ps

ROOT = Path(__file__).absolute().parents[4]
LOCAL = ROOT / 'docs/phase_b_v2_console_lifetime_repair/v1/.local'
ENTRY = ROOT / 'src/yuntapr/experimental/phase_b_v2_console_lifetime_candidate/gui_entry.py'


def validate_scope(folder: Path, nonce: str) -> None:
    # Lexical rejection precedes *all* existence/stat/resolve/open operations.
    if (not folder.is_absolute() or '..' in folder.parts or '2025' in str(folder)
        or folder.parent.parent != LOCAL
        or not folder.parent.name.startswith('artificial_tasks_')
        or not folder.name.startswith('artificial_')
        or type(nonce) is not str or len(nonce) != 32
        or any(c not in '0123456789abcdef' for c in nonce)):
        raise PermissionError('ARTIFICIAL_CONSOLE_SCOPE_ONLY')


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def save(folder: Path, name: str, value: dict) -> None:
    with (folder / name).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=True, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())


def interpreter_pair() -> tuple[str, str]:
    runtime = load(ROOT / 'docs/phase_b_v2_formal_execution/seed2027_b1_epoch7_recovery_v3/.local/runtime.json')
    python = Path(runtime['python'])
    if not python.is_absolute() or python.name.lower() != 'python.exe' or '2025' in str(python) or '..' in python.parts:
        raise PermissionError('FIXED_PUBLISHED_INTERPRETER')
    return str(python), str(python.with_name('pythonw.exe'))


def fixed_spec(folder: Path, nonce: str) -> dict:
    validate_scope(folder, nonce)
    python, gui = interpreter_pair()
    return dict(schema='ARTIFICIAL_GUI_OWNER_V1', nonce=nonce,
        task_name='YunTAPR_ArtificialConsole_' + nonce,
        execute=gui, arguments=subprocess.list2cmdline([str(ENTRY), str(folder), nonce]),
        python=python, gui_sha256=hashlib.sha256(Path(gui).read_bytes()).hexdigest(),
        entry_sha256=hashlib.sha256(ENTRY.read_bytes()).hexdigest(),
        synthetic_only=True, formal_execution=False, retries=0, max_seconds=15)


def start(folder: Path, nonce: str) -> dict:
    spec = fixed_spec(folder, nonce)
    save(folder, 'request.json', spec)
    script = "$ErrorActionPreference='Stop';[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
    script += f"$name={quote(spec['task_name'])};if(Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue){{throw 'No artificial overwrite'}};"
    script += f"$a=New-ScheduledTaskAction -Execute {quote(spec['execute'])} -Argument {quote(spec['arguments'])} -WorkingDirectory {quote(ROOT)};"
    script += "$p=New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited;"
    script += "$s=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Seconds 15) -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries;"
    script += "Register-ScheduledTask -TaskName $name -InputObject (New-ScheduledTask -Action $a -Principal $p -Settings $s)|Out-Null;"
    script += "$t=Get-ScheduledTask -TaskName $name;if($t.Triggers.Count -ne 0 -or $t.Settings.RestartCount -ne 0 -or $t.Principal.RunLevel -ne 'Limited'){throw 'Fixed artificial policy'};Start-ScheduledTask -TaskName $name;"
    script += "[pscustomobject]@{registered=$true;retries=0;triggers=0}|ConvertTo-Json -Compress"
    registration = json.loads(ps(script))
    save(folder, 'registration.json', registration)
    return spec


def remove_finished(spec: dict) -> dict:
    name = spec['task_name']
    if name != 'YunTAPR_ArtificialConsole_' + spec['nonce']:
        raise PermissionError('OWNED_ARTIFICIAL_TASK_ONLY')
    script = "$ErrorActionPreference='Stop';[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
    script += f"$t=Get-ScheduledTask -TaskName {quote(name)};$i=Get-ScheduledTaskInfo -TaskName {quote(name)};if($t.State -eq 'Running'){{throw 'Retain running artificial task'}};"
    script += "$r=[pscustomobject]@{state=[string]$t.State;last_result=$i.LastTaskResult};"
    script += f"Unregister-ScheduledTask -TaskName {quote(name)} -Confirm:$false;$r|ConvertTo-Json -Compress"
    return json.loads(ps(script))
