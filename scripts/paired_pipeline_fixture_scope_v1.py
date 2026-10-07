"""Allow only new UUID test fixtures in four inherited workspace temp parents."""
from pathlib import Path
import re

class FixtureScope:
    def __init__(self, workspace):
        base=Path(workspace).resolve()/'tmp'
        self.parents=[base/n for n in ('paired_authorization_fixtures','final_test_b0_units',
            'final_test_catalogue_units','catalogue_backend_fixture_tests')]
        self.before={p:{q.name for q in p.iterdir()} if p.exists() else set() for p in self.parents}

    def allows(self, path):
        path=Path(path).resolve()
        for parent in self.parents:
            if path.is_relative_to(parent):
                parts=path.relative_to(parent).parts
                return bool(parts and parts[0] not in self.before[parent] and
                            re.fullmatch(r'(?:unit_|fixture_)?[0-9a-f]{32}',parts[0]))
        return False

    def cleanup_complete(self):
        return all(({q.name for q in p.iterdir()} if p.exists() else set())==self.before[p] for p in self.parents)
