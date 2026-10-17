"""Actual human decision: publish the execution version, DO NOT launch.

This is a publication-scope record, not a scientific/execution approval or an
authorization service. JSON fields, a CLI invocation and Git cannot override it.
"""
PUBLICATION_DECISION='只发布执行版本，暂不启动'
PUBLICATION_SCOPE='SEED2027_EXECUTION_RELEASE_ONLY_NO_START'

def require_execution_authority(seed: int) -> None:
    if type(seed) is not int or seed!=2027:
        raise PermissionError('THIS_PUBLICATION_DOES_NOT_COVER_OTHER_SEEDS')
    raise PermissionError('SEED2027_LAUNCH_WITHHELD_BY_RESEARCHER')
