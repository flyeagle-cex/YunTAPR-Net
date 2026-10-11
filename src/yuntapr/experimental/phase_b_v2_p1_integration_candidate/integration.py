"""Minimal handoff adapter; no model factory, epoch loop, updater or real reader.

Published B9State/ActualQuota/Evaluator remain unchanged. A future authorized
version must call their boundary checks before a live restore. Here the exact
method is exercised only by an artificial boundary probe and FixtureState.
"""
from __future__ import annotations
from . import start_formal, restore_formal


def restore_artificial_boundary(store, reference, target, boundary) -> None:
    from .checkpoint import Store, FixtureState
    if type(store) is not Store or type(target) is not FixtureState or type(boundary) is not BoundaryProbe:
        raise PermissionError('Artificial integration types only')
    row=store.read(reference)
    commit=store._registered[str(reference)]
    try:
        # Use the published B9 implementation's nonrollback check verbatim.
        boundary.check_restore(commit.payload_sha,row['epoch'],row['update'])
    except BaseException:
        store.failed=True
        raise
    from copy import deepcopy
    target._value=deepcopy(row)


class BoundaryProbe:
    """Not a DB/state-machine constructor and cannot reserve any optimizer step."""
    def __init__(self, row: dict):
        from copy import deepcopy
        self._row=deepcopy(row)
    def read(self): return dict(self._row)
    def check_restore(self, sha, epoch, update):
        from yuntapr.experimental.phase_b_v2_formal_integration_candidate.state import B9State
        B9State.check_restore(self,sha,epoch,update)


class ArtificialRunner:
    """One namespace for the two remediated capabilities, without epoch execution."""
    def launch(self, artificial_case):
        from .launcher import run
        return run(artificial_case)

    def restore(self, store, reference, target, boundary):
        restore_artificial_boundary(store,reference,target,boundary)

    def start_formal(self,*args,**kwargs): start_formal(*args,**kwargs)
    def resume_formal(self,*args,**kwargs): restore_formal(*args,**kwargs)
