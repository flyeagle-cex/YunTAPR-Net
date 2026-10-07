"""Synthetic fixture-path boundaries; no source/model access or updates."""
import unittest,tempfile
from pathlib import Path
from paired_pipeline_fixture_scope_v1 import FixtureScope

class FixtureScopeTests(unittest.TestCase):
    def test_new_uuid_children_allowed(self):
        with tempfile.TemporaryDirectory() as td:
            scope=FixtureScope(td)
            for p in scope.parents:
                for prefix in ('','unit_','fixture_'):
                    self.assertTrue(scope.allows(p/(prefix+'a'*32)/'synthetic.json'))

    def test_non_fixture_names_parent_and_escaped_paths_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            scope=FixtureScope(td);p=scope.parents[0]
            for target in (p,p/'history.json',p/'not_uuid/file.json',p/'../formal/epoch.pt'):
                self.assertFalse(scope.allows(target))

    def test_existing_children_protected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'tmp/paired_authorization_fixtures';old=p/('b'*32);old.mkdir(parents=True)
            scope=FixtureScope(td);self.assertFalse(scope.allows(old/'existing.json'))
            self.assertTrue(scope.cleanup_complete())

    def test_cleanup_receipt_detects_unremoved_new_child(self):
        with tempfile.TemporaryDirectory() as td:
            scope=FixtureScope(td);p=scope.parents[0]/('c'*32);p.mkdir(parents=True)
            self.assertFalse(scope.cleanup_complete());p.rmdir();self.assertTrue(scope.cleanup_complete())
