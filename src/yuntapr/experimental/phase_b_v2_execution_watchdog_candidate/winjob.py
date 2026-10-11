"""Windows kernel containment, created atomically with the child process.

Only standard library imports. Handles, not untrusted PIDs, own termination.
PROC_THREAD_ATTRIBUTE_JOB_LIST closes the suspended-before-assignment orphan
window. No breakaway flag is permitted; no taskkill or PID-only kill fallback.
"""
from __future__ import annotations
import ctypes as C
from ctypes import wintypes as W
import hashlib
import os
import subprocess
from pathlib import Path

if os.name != 'nt':
    raise OSError('Windows Job Object backend required; no fallback')

K = C.WinDLL('kernel32', use_last_error=True)
P = C.WinDLL('psapi', use_last_error=True)
SIZE = C.c_size_t


class Startup(C.Structure):
    _fields_ = [('cb', W.DWORD), ('reserved', W.LPWSTR), ('desktop', W.LPWSTR), ('title', W.LPWSTR),
                ('x', W.DWORD), ('y', W.DWORD), ('xs', W.DWORD), ('ys', W.DWORD),
                ('xc', W.DWORD), ('yc', W.DWORD), ('fill', W.DWORD), ('flags', W.DWORD),
                ('show', W.WORD), ('cbreserved', W.WORD), ('reserved2', C.POINTER(C.c_byte)),
                ('stdin', W.HANDLE), ('stdout', W.HANDLE), ('stderr', W.HANDLE)]


class StartupEx(C.Structure):
    _fields_ = [('startup', Startup), ('attributes', C.c_void_p)]


class ProcessInfo(C.Structure):
    _fields_ = [('process', W.HANDLE), ('thread', W.HANDLE), ('pid', W.DWORD), ('tid', W.DWORD)]


class BasicLimit(C.Structure):
    _fields_ = [('process_time', C.c_int64), ('job_time', C.c_int64), ('flags', W.DWORD),
                ('min_ws', SIZE), ('max_ws', SIZE), ('active_limit', W.DWORD), ('affinity', SIZE),
                ('priority', W.DWORD), ('scheduling', W.DWORD)]


class ExtendedLimit(C.Structure):
    _fields_ = [('basic', BasicLimit), ('io', C.c_uint64*6), ('process_memory', SIZE),
                ('job_memory', SIZE), ('peak_process_memory', SIZE), ('peak_job_memory', SIZE)]


class Pids(C.Structure):
    _fields_ = [('assigned', W.DWORD), ('count', W.DWORD), ('ids', SIZE*32)]


class Memory(C.Structure):
    _fields_ = [('cb', W.DWORD), ('faults', W.DWORD), ('peak_ws', SIZE), ('ws', SIZE),
                ('peak_paged', SIZE), ('paged', SIZE), ('peak_nonpaged', SIZE), ('nonpaged', SIZE),
                ('pagefile', SIZE), ('peak_pagefile', SIZE), ('private', SIZE)]


def bind(lib, name, args, result):
    f = getattr(lib, name); f.argtypes = args; f.restype = result
    return f


create_job = bind(K, 'CreateJobObjectW', [C.c_void_p, W.LPCWSTR], W.HANDLE)
set_job = bind(K, 'SetInformationJobObject', [W.HANDLE, C.c_int, C.c_void_p, W.DWORD], W.BOOL)
query_job = bind(K, 'QueryInformationJobObject', [W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.c_void_p], W.BOOL)
terminate_job = bind(K, 'TerminateJobObject', [W.HANDLE, W.UINT], W.BOOL)
close_handle = bind(K, 'CloseHandle', [W.HANDLE], W.BOOL)
open_process = bind(K, 'OpenProcess', [W.DWORD, W.BOOL, W.DWORD], W.HANDLE)
in_job = bind(K, 'IsProcessInJob', [W.HANDLE, W.HANDLE, C.POINTER(W.BOOL)], W.BOOL)
wait = bind(K, 'WaitForSingleObject', [W.HANDLE, W.DWORD], W.DWORD)
process_id = bind(K, 'GetProcessId', [W.HANDLE], W.DWORD)
times = bind(K, 'GetProcessTimes', [W.HANDLE]+[C.POINTER(W.FILETIME)]*4, W.BOOL)
image = bind(K, 'QueryFullProcessImageNameW', [W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD)], W.BOOL)
exit_code = bind(K, 'GetExitCodeProcess', [W.HANDLE, C.POINTER(W.DWORD)], W.BOOL)
get_memory = bind(P, 'GetProcessMemoryInfo', [W.HANDLE, C.c_void_p, W.DWORD], W.BOOL)
init_attr = bind(K, 'InitializeProcThreadAttributeList', [C.c_void_p, W.DWORD, W.DWORD, C.POINTER(SIZE)], W.BOOL)
update_attr = bind(K, 'UpdateProcThreadAttribute', [C.c_void_p, W.DWORD, SIZE, C.c_void_p, SIZE, C.c_void_p, C.c_void_p], W.BOOL)
delete_attr = bind(K, 'DeleteProcThreadAttributeList', [C.c_void_p], None)
create_process = bind(K, 'CreateProcessW', [W.LPCWSTR, W.LPWSTR, C.c_void_p, C.c_void_p, W.BOOL,
                      W.DWORD, C.c_void_p, W.LPCWSTR, C.c_void_p, C.POINTER(ProcessInfo)], W.BOOL)
resume_thread = bind(K, 'ResumeThread', [W.HANDLE], W.DWORD)


def checked(ok):
    if not ok:
        raise C.WinError(C.get_last_error())
    return ok


def native_identity(handle) -> dict:
    """Creation time and image from a retained kernel handle, never JSON trust."""
    pid = process_id(handle)
    checked(pid)
    t = [W.FILETIME() for _ in range(4)]
    checked(times(handle, *map(C.byref, t)))
    buf = C.create_unicode_buffer(32768); n = W.DWORD(len(buf))
    checked(image(handle, 0, buf, C.byref(n)))
    # Hash the native path for public receipts; no private absolute path export.
    key = hashlib.sha256(os.path.normcase(buf.value).encode('utf-8')).hexdigest()
    return {'pid': pid, 'creation_filetime': (t[0].dwHighDateTime<<32)|t[0].dwLowDateTime,
            'image_path_key': key}


def memory(handle) -> dict:
    m = Memory(); m.cb = C.sizeof(m)
    checked(get_memory(handle, C.byref(m), C.sizeof(m)))
    return {'working_set_bytes': m.ws, 'peak_working_set_bytes': m.peak_ws,
            'private_commit_bytes': m.private, 'peak_pagefile_bytes': m.peak_pagefile}


def exited(handle) -> bool:
    result = wait(handle, 0)
    if result not in (0, 258):
        raise C.WinError(C.get_last_error())
    return result == 0


def code(handle) -> int:
    result = W.DWORD(); checked(exit_code(handle, C.byref(result)))
    return result.value


class Job:
    """An owned, non-inheritable kill-on-close job; all children inherit membership."""
    def __init__(self):
        self.handle = checked(create_job(None, None)); self.root = None
        self.handles = {}; self.identities = {}; self.terminated = False
        try:
            limits = ExtendedLimit()
            # KILL_ON_JOB_CLOSE, ACTIVE_PROCESS, JOB_MEMORY. No BREAKAWAY_OK.
            limits.basic.flags = 0x2000 | 0x8 | 0x200
            limits.basic.active_limit = 16
            limits.job_memory = 256*1024**2
            checked(set_job(self.handle, 9, C.byref(limits), C.sizeof(limits)))
        except BaseException:
            close_handle(self.handle); self.handle = None; raise

    def spawn(self, argv: list[str], cwd: Path) -> int:
        """Atomically contain process at creation, then resume. Failure cannot run it."""
        if self.root is not None:
            raise PermissionError('One launch only; no restart')
        size = SIZE(); init_attr(None, 1, 0, C.byref(size))
        buf = C.create_string_buffer(size.value); ptr = C.cast(buf, C.c_void_p)
        checked(init_attr(ptr, 1, 0, C.byref(size)))
        info = ProcessInfo(); thread = None
        try:
            jobs = (W.HANDLE*1)(self.handle)
            checked(update_attr(ptr, 0, 0x2000D, jobs, C.sizeof(jobs), None, None))
            startup = StartupEx(); startup.startup.cb = C.sizeof(startup); startup.attributes = ptr
            command = C.create_unicode_buffer(subprocess.list2cmdline(argv))
            checked(create_process(argv[0], command, None, None, False,
                                  0x08000000 | 0x00080000 | 0x4, None, str(cwd), C.byref(startup), C.byref(info)))
            thread = info.thread; self.root = info.process
            self.handles[info.pid] = info.process; self.identities[info.pid] = native_identity(info.process)
            member = W.BOOL(); checked(in_job(info.process, self.handle, C.byref(member)))
            if not member.value: raise PermissionError('Creation containment missing')
            if resume_thread(thread) == 0xFFFFFFFF: raise C.WinError(C.get_last_error())
            return info.pid
        except BaseException:
            self.stop(); raise
        finally:
            if thread: close_handle(thread)
            delete_attr(ptr)

    def pids(self) -> list[int]:
        p = Pids(); checked(query_job(self.handle, 3, C.byref(p), C.sizeof(p), None))
        if p.count > 16 or p.assigned != p.count:
            raise RuntimeError('Unexpected job member count')
        return list(p.ids[:p.count])

    def bind(self, pid: int):
        """Never kill the PID argument; reject non-members before registration."""
        if type(pid) is not int or pid <= 0 or pid > 0xFFFFFFFF:
            raise ValueError('INVALID_PID')
        if pid in self.handles:
            h = self.handles[pid]
            # A retained process handle cannot be rebound by PID reuse. Querying
            # the executable *again* after exit can fail despite valid ownership.
            if not h or process_id(h) != pid: raise ValueError('HANDLE_IDENTITY_CHANGED')
            return h
        h = checked(open_process(0x00100000 | 0x0400 | 0x0010, False, pid))
        try:
            member = W.BOOL(); checked(in_job(h, self.handle, C.byref(member)))
            if not member.value: raise PermissionError('PID_OUTSIDE_OWNED_JOB')
            ident = native_identity(h)
            self.handles[pid] = h; self.identities[pid] = ident
            return h
        except BaseException:
            close_handle(h); raise

    def snapshot(self) -> list[int]:
        pids = self.pids()
        for pid in pids:
            # A member exiting between enumeration and OpenProcess is normal.
            try: self.bind(pid)
            except OSError:
                if pid in self.pids(): raise
        return pids

    def stop(self):
        if self.handle and not self.terminated:
            checked(terminate_job(self.handle, 99)); self.terminated = True

    def close(self):
        if self.handle:
            close_handle(self.handle); self.handle = None
        for h in self.handles.values():
            if h: close_handle(h)
        self.handles.clear()
