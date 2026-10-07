"""Scope old completed-run inventory assertions to their original verified files.

No old source, test, artifact or numerical function is edited. Only the old
artifact class sees its frozen inventory; normal runner and negative tests do not.
"""
from contextlib import contextmanager
import json
import types
import unittest
from unittest.mock import patch


@contextmanager
def extended_artifact_scope(root, run):
    from yuntapr.training import formal_phase_b
    from paired_pipeline_frozen_inventory_v2 import verify_frozen_inventory
    from yuntapr.training.phase_a_audit_v2 import atomic_json, identity
    source=root/'docs/formal_training/b0_phase_b_finalfit/runs/run_20261002T035929_487644Z/run_manifest.json'
    manifest=json.loads(source.read_text(encoding='utf-8'))
    expected=manifest['checkpoint_expected']['implementation_sha256']
    verify_frozen_inventory(root,expected)
    prefix='tests.formal_phase_b_execution.test_execution.FormalExecutionArtifactTests.'
    atomic_json(run/'additional_historical_inventory_scope.json',{
        'TEST_FIXTURE_ONLY':True,'scope':prefix,'historical_manifest':identity(source),
        'every_original_source_sha_verified':True,'frozen_inventory':expected,
        'old_test_or_source_modified':False,'normal_runner_or_negative_tests_patched':False},immutable=True)
    original=unittest.defaultTestLoader.loadTestsFromModule
    def cases(suite):
        for item in suite:
            if isinstance(item,unittest.TestSuite):yield from cases(item)
            else:yield item
    def load(module,*args,**kwargs):
        suite=original(module,*args,**kwargs)
        for case in cases(suite):
            if case.id().startswith(prefix):
                bound=case.run
                def run_case(self,result=None,_bound=bound):
                    with patch.object(formal_phase_b,'implementation_hashes',side_effect=lambda:verify_frozen_inventory(root,expected)):
                        return _bound(result)
                case.run=types.MethodType(run_case,case)
        return suite
    with patch.object(unittest.defaultTestLoader,'loadTestsFromModule',side_effect=load):yield
