"""No execution instruction for seeds2027/2028 exists in this preparation.

An editable config, JSON, CLI option, test or commit cannot supply that event.
This refusal must be replaced only in a separately reviewed, human-authorized
release. It does not change the approved/completed seed2026 scope.
"""
def require_execution_authority(seed: int) -> None:
    raise PermissionError(f'NEW_SEED_{seed}_EXECUTION_NOT_AUTHORIZED_PREPARATION_ONLY')
