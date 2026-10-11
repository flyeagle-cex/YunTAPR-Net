"""Stdlib-only watchdog candidate. No data, model or execution authorization."""
SCOPE = 'SYNTHETIC_ENGINEERING_ONLY'


def start_formal(*args: object, **kwargs: object) -> None:
    raise PermissionError('Independent formal integration and execution approvals absent')
