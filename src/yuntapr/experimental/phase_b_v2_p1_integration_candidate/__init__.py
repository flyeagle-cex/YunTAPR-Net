"""P1 engineering-only adapter. No real reader, model factory or optimizer step."""
SCOPE = 'SYNTHETIC_ENGINEERING_ONLY'


def start_formal(*args: object, **kwargs: object) -> None:
    raise PermissionError('Independent scientific, code, data, resource and execution approvals absent')


def restore_formal(*args: object, **kwargs: object) -> None:
    raise PermissionError('Independent LAST-bound recovery approval absent; fixture is never authority')
