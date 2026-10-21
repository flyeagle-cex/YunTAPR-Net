"""Query console attachment; never broadcast a control event to a user console."""
from __future__ import annotations
import ctypes as C
from ctypes import wintypes as W
from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.winjob import K, bind

console_window = bind(K, 'GetConsoleWindow', [], W.HWND)
console_processes = bind(K, 'GetConsoleProcessList', [C.POINTER(W.DWORD), W.DWORD], W.DWORD)


def console_profile() -> dict:
    """GetConsoleProcessList=0 and HWND=0 identify an unattached process."""
    ids = (W.DWORD * 64)()
    C.set_last_error(0)
    count = console_processes(ids, len(ids))
    return dict(hwnd=int(console_window() or 0), process_count=int(count),
                process_ids=list(ids[:min(count, len(ids))]),
                winerror=C.get_last_error())


def require_no_console() -> dict:
    profile = console_profile()
    if profile['hwnd'] or profile['process_count']:
        raise PermissionError('ARTIFICIAL_OWNER_MUST_HAVE_NO_CONSOLE')
    return profile


def detach_current_console() -> dict:
    """Detach only the calling process, retaining all existing Job membership.

    CREATE_NO_WINDOW applies to the process being created. A venv launcher can
    create another native interpreter which attaches to a console. Assert the
    final Python process, not just the launch flags or wrapper PID.
    """
    before = console_profile()
    detached = bool(before['hwnd'] or before['process_count'])
    if detached:
        free = bind(K, 'FreeConsole', [], W.BOOL)
        if not free():
            raise C.WinError(C.get_last_error())
    return dict(before=before, detached=detached, after=require_no_console())
