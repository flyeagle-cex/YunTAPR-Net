"""Separate caller commit headroom from system commit; read-only Win32 APIs."""
import ctypes as C
from ctypes import wintypes as W

class Global(C.Structure):
    _fields_=[('length',W.DWORD),('load',W.DWORD)]+[(n,C.c_uint64) for n in
        ('total_phys','available_phys','total_page','available_page','total_virtual','available_virtual','extended')]

class Performance(C.Structure):
    _fields_=[('cb',W.DWORD)]+[(n,C.c_size_t) for n in
        ('commit_total','commit_limit','commit_peak','physical_total','physical_available','system_cache',
         'kernel_total','kernel_paged','kernel_nonpaged','page_size')]+[(n,W.DWORD) for n in
        ('handles','processes','threads')]

def sample() -> dict:
    kernel=C.WinDLL('kernel32',use_last_error=True);psapi=C.WinDLL('psapi',use_last_error=True)
    global_status=kernel.GlobalMemoryStatusEx;global_status.argtypes=[C.POINTER(Global)];global_status.restype=W.BOOL
    performance=psapi.GetPerformanceInfo;performance.argtypes=[C.POINTER(Performance),W.DWORD];performance.restype=W.BOOL
    g=Global();g.length=C.sizeof(g);p=Performance();p.cb=C.sizeof(p)
    if not global_status(C.byref(g)) or not performance(C.byref(p),C.sizeof(p)):raise C.WinError(C.get_last_error())
    if p.commit_total>p.commit_limit or not 0<p.page_size<=65536:raise ValueError('MEMORY_API_UNITS_OR_VALUES')
    return dict(caller_available_commit_bytes=int(g.available_page),caller_commit_limit_bytes=int(g.total_page),
        system_commit_total_bytes=int(p.commit_total*p.page_size),system_commit_limit_bytes=int(p.commit_limit*p.page_size),
        system_available_commit_bytes=int((p.commit_limit-p.commit_total)*p.page_size),
        system_available_physical_bytes=int(p.physical_available*p.page_size),page_size_bytes=int(p.page_size),
        original_resource_thresholds_modified=False,settings_modified=False)
