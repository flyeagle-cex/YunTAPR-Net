"""Only a native held handle proving exit can suppress an identity-query fault.

Do not patch the published watchdog. No PID-only termination, broad WinError 5
ignore, executable allowlist relaxation, resource adjustment or retry is added.
"""
from __future__ import annotations
import ctypes as C
from ctypes import wintypes as W
from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.winjob import (
    Job as OriginalJob,checked,open_process,in_job,native_identity,exited,close_handle,
    query_job,SIZE)


class ExitedOwnedMember(Exception):
    """Not an authorization: the same retained member handle is already signaled."""
    def __init__(self,receipt: dict):
        self.receipt=receipt
        super().__init__('OWNED_MEMBER_EXIT_PROVEN_DURING_IDENTITY_QUERY')


class IdentitySafeJob(OriginalJob):
    def __init__(self):
        super().__init__()
        self.identity_exit_receipts=[]
        self.enumeration_resize_receipts=[]

    def pids(self) -> list[int]:
        """Return a complete native list or fail within three bounded queries.

        NumberOfAssignedProcesses and NumberOfProcessIdsInList are separate
        fields. An incomplete list is never interpreted as an empty Job.
        The kernel active-process limit of 16 is not changed.
        """
        for capacity in (32,64,128):
            class ProcessList(C.Structure):
                _fields_=[('assigned',W.DWORD),('count',W.DWORD),('ids',SIZE*capacity)]
            row=ProcessList()
            ok=query_job(self.handle,3,C.byref(row),C.sizeof(row),None)
            error=0 if ok else C.get_last_error()
            if not ok and error not in (122,234):raise C.WinError(error)
            assigned,count=int(row.assigned),int(row.count)
            if count>capacity or count>16 or (ok and count>assigned):
                raise RuntimeError(f'INVALID_JOB_COUNTS_ASSIGNED_{assigned}_RETURNED_{count}_CAPACITY_{capacity}')
            if ok and assigned==count:
                pids=list(row.ids[:count])
                if len(set(pids))!=count or any(not 0<pid<=0xFFFFFFFF for pid in pids):
                    raise RuntimeError('INVALID_NATIVE_JOB_PID_LIST')
                return pids
            if len(self.enumeration_resize_receipts)>=128:
                raise RuntimeError('JOB_ENUMERATION_AUDIT_BOUND')
            self.enumeration_resize_receipts.append(dict(capacity=capacity,
                assigned=assigned,returned=count,winerror=error,action='REQUERY_NEVER_RETURN_PARTIAL'))
        raise RuntimeError('INCOMPLETE_JOB_LIST_AFTER_THREE_BOUNDED_NATIVE_QUERIES')

    def bind(self,pid: int):
        if type(pid) is not int or not 0<pid<=0xFFFFFFFF:
            raise ValueError('INVALID_PID')
        if pid in self.handles:
            return super().bind(pid)
        handle=checked(open_process(0x00100000|0x0400|0x0010,False,pid))
        try:
            member=W.BOOL();checked(in_job(handle,self.handle,C.byref(member)))
            if not member.value:raise PermissionError('PID_OUTSIDE_OWNED_JOB')
            try:
                identity=native_identity(handle)
            except OSError as exc:
                # Unlike querying a PID again, this wait refers to the very
                # same native process object whose Job membership was checked.
                if not exited(handle):
                    exc.failed_job_member_pid=pid
                    exc.identity_exit_status='NATIVE_HANDLE_NOT_SIGNALED'
                    raise
                receipt=dict(pid=pid,owned_job_membership_verified=True,
                    retained_handle_signaled=True,identity_query_winerror=getattr(exc,'winerror',None),
                    action='EXCLUDE_EXITED_MEMBER_ONLY_NO_TERMINATION_NO_RETRY')
                if len(self.identity_exit_receipts)>=128:
                    raise RuntimeError('IDENTITY_EXIT_AUDIT_BOUND') from exc
                self.identity_exit_receipts.append(receipt)
                raise ExitedOwnedMember(receipt) from exc
            self.handles[pid]=handle;self.identities[pid]=identity
            return handle
        except BaseException:
            close_handle(handle)
            raise

    def snapshot(self) -> list[int]:
        pids=self.pids()
        for pid in pids:
            try:self.bind(pid)
            except ExitedOwnedMember:continue
            except OSError:
                # Preserve the original disappearance check; a current member
                # with a live/unknown identity fault remains fatal.
                if pid in self.pids():raise
        return pids
