"""Path compatibility tests; no raw files, CUDA, model or optimizer access."""
from pathlib import Path
import tempfile, unittest
from scripts.paired_extended_path_adapter_v1 import path_sha256
from yuntapr.contracts.loader import sha256

class PathAdapterTests(unittest.TestCase):
    def test_path_and_string_hash_identical(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'identity.txt';p.write_bytes(b'identity fixture\x00\xff')
            self.assertEqual(path_sha256(str(p)),sha256(p))
            self.assertEqual(path_sha256(p),sha256(p))
    def test_missing_file_still_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):path_sha256(str(Path(directory)/'absent'))
    def test_invalid_path_not_silently_accepted(self):
        with self.assertRaises(TypeError):path_sha256(None)
