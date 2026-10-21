"""Bounded artificial processes; no torch, model, data, checkpoint or ledger."""
from __future__ import annotations
from pathlib import Path
import ctypes as C
from ctypes import wintypes as W
import json, os, sys, time
from .native_console import require_no_console, console_profile, detach_current_console
from .task_bridge import validate_scope, load, save, ROOT
from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.winjob import (
    Job, K, bind, native_identity, checked, exited, code, open_process, close_handle)

current = bind(K, 'GetCurrentProcess', [], W.HANDLE)


def identity(nonce: str) -> dict:
    return dict(**native_identity(current()), nonce=nonce, console=console_profile())


def main() -> None:
    if len(sys.argv) != 4:
        raise PermissionError('FIXED_ARTIFICIAL_ARGUMENTS')
    mode, raw_folder, nonce = sys.argv[1:]
    folder = Path(raw_folder)
    validate_scope(folder, nonce)
    if mode == 'signal':
        # Windows Terminal can expose a message-only console HWND; WM_CLOSE
        # then does not prove control-event delivery. Attach only to the held,
        # native-identity-bound fake client's private console and signal it.
        client = load(folder / 'client.json')
        if client['nonce'] != nonce:
            raise PermissionError('ARTIFICIAL_SIGNAL_NONCE')
        handle = checked(open_process(0x00100000 | 0x1000, False, client['pid']))
        attached = False
        free = bind(K, 'FreeConsole', [], W.BOOL)
        try:
            if native_identity(handle) != {k: client[k] for k in ('pid', 'creation_filetime', 'image_path_key')} or exited(handle):
                raise PermissionError('ARTIFICIAL_SIGNAL_NATIVE_CLIENT')
            detach_current_console()
            attach = bind(K, 'AttachConsole', [W.DWORD], W.BOOL)
            checked(attach(client['pid']))
            attached = True
            profile = console_profile()
            allowed = {client['pid'], os.getpid()}
            if client['pid'] not in profile['process_ids'] or set(profile['process_ids']) != allowed:
                raise PermissionError('REFUSE_EVENT_OUTSIDE_PRIVATE_FAKE_CONSOLE')
            handler_type = C.WINFUNCTYPE(W.BOOL, W.DWORD)
            handler = handler_type(lambda event: True)
            set_handler = bind(K, 'SetConsoleCtrlHandler', [handler_type, W.BOOL], W.BOOL)
            checked(set_handler(handler, True))
            generate = bind(K, 'GenerateConsoleCtrlEvent', [W.DWORD, W.DWORD], W.BOOL)
            checked(generate(1, 0))  # CTRL_BREAK, THIS private console only.
            time.sleep(.1)
            save(folder, 'signal_receipt.json', dict(nonce=nonce,
                 control_event=1, console_before=profile, synthetic_only=True))
        finally:
            if attached:
                checked(free())
            close_handle(handle)
        return
    if mode == 'client':
        # The isolated fake client owns this hidden console. Only its recorded
        # HWND is closed by tests, never the user's PowerShell/Codex console.
        # Some interpreter launchers attach to an inherited pseudoconsole even
        # when their wrapper was created with CREATE_NO_WINDOW. Detach THIS
        # artificial client first, then allocate its distinct test console.
        if console_profile()['process_count']:
            free = bind(K, 'FreeConsole', [], W.BOOL)
            checked(free())
        alloc = bind(K, 'AllocConsole', [], W.BOOL)
        checked(alloc())
        u = C.WinDLL('user32', use_last_error=True)
        hide = bind(u, 'ShowWindow', [W.HWND, C.c_int], W.BOOL)
        hwnd = console_profile()['hwnd']
        if not hwnd:
            raise RuntimeError('ARTIFICIAL_CONSOLE_MISSING')
        hide(hwnd, 0)
        save(folder, 'client.json', identity(nonce))
        time.sleep(14)
        return
    if mode not in ('owner', 'worker'):
        raise PermissionError('FIXED_ARTIFICIAL_MODE')
    detachment = detach_current_console()
    if os.environ.get('PYTHONHASHSEED') != '2026':
        raise PermissionError('PRE_INTERPRETER_HASH_ENVIRONMENT')
    save(folder, mode + '.json', dict(**identity(nonce), detachment=detachment,
         hash_probe=hash('fixed-artificial-startup'), torch_imported='torch' in sys.modules))
    if mode == 'worker':
        time.sleep(14)
        return
    job = Job()
    try:
        job.spawn([sys.executable, '-m', __package__ + '.fixture', 'worker', str(folder), nonce], ROOT)
        deadline = time.monotonic() + 9
        while not (folder / 'worker.json').exists():
            if time.monotonic() >= deadline:
                raise TimeoutError('ARTIFICIAL_WORKER_REGISTRATION')
            if exited(job.root):
                raise RuntimeError('ARTIFICIAL_WORKER_EARLY_EXIT_' + str(code(job.root)))
            time.sleep(.01)
        save(folder, 'ready.json', dict(nonce=nonce, worker=load(folder / 'worker.json')))
        while time.monotonic() < deadline:
            if (folder / 'stop.request').exists():
                break
            job.snapshot()
            time.sleep(.02)
        else:
            raise TimeoutError('ARTIFICIAL_STOP_DEADLINE')
    finally:
        job.stop()
        deadline = time.monotonic() + 2
        while (job.pids() or any(not exited(h) for h in job.handles.values())) and time.monotonic() < deadline:
            time.sleep(.01)
        empty = not job.pids() and all(exited(h) for h in job.handles.values())
        job.close()
        save(folder, 'termination.json', dict(job_empty=empty, synthetic_only=True,
             torch_imported='torch' in sys.modules, optimizer_steps=0))


if __name__ == '__main__':
    try:
        main()
    except BaseException:
        import traceback
        # Failure diagnostics remain inside the exact artificial scope.
        if len(sys.argv) == 4:
            role, raw_folder, token = sys.argv[1:]
            folder = Path(raw_folder)
            validate_scope(folder, token)
            if role in ('client', 'owner', 'worker', 'signal'):
                save(folder, role + '_failure.json', dict(traceback=traceback.format_exc()))
        raise
