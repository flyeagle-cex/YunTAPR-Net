import hashlib
from pathlib import Path
import tempfile
import unittest

from paired_pipeline_frozen_inventory_v2 import verify_frozen_inventory


class FrozenInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "baseline.py").write_bytes(b"pinned code\n")
        self.expected = {"baseline.py": hashlib.sha256(b"pinned code\n").hexdigest()}

    def test_added_module_does_not_change_frozen_files(self):
        (self.root / "later.py").write_bytes(b"later module\n")
        self.assertEqual(verify_frozen_inventory(self.root, self.expected), self.expected)

    def test_changed_frozen_file_is_rejected(self):
        (self.root / "baseline.py").write_bytes(b"changed\n")
        with self.assertRaisesRegex(ValueError, "hash changed"):
            verify_frozen_inventory(self.root, self.expected)

    def test_missing_frozen_file_is_rejected(self):
        (self.root / "baseline.py").unlink()
        with self.assertRaisesRegex(ValueError, "file missing"):
            verify_frozen_inventory(self.root, self.expected)

    def test_empty_inventory_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            verify_frozen_inventory(self.root, {})
