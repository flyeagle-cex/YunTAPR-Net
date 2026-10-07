"""Execution-layer ownership of updates, following the existing runner layout.

Library modules prepare/validate gradients; only this explicit scoped execution
operation calls optimizer.step. Scientific approval alone never invokes it.
"""
def optimizer_step(optimizer, scope):
    if scope not in ('FORMAL', 'ENGINEERING_ONLY', 'TEST_FIXTURE_ONLY'):
        raise PermissionError('Explicit update counter scope required')
    optimizer.step()
