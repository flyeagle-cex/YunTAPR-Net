"""Reuse tested self-detachment, rejecting ambiguous console API failures."""
from yuntapr.experimental.phase_b_v2_console_lifetime_candidate.native_console import detach_current_console

def isolate() -> dict:
    receipt=detach_current_console();after=receipt['after']
    if (after['hwnd']!=0 or after['process_count']!=0 or after['process_ids']
        or after['winerror'] not in (0,6)):
        raise PermissionError('CONSOLE_ISOLATION_NOT_NATIVE_VERIFIED')
    return receipt
