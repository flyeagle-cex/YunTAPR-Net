"""Independently verify every historical code pin against the current workspace."""
import hashlib
from pathlib import Path


def verify_frozen_inventory(root, expected):
    root = Path(root).resolve()
    if not expected:
        raise ValueError("Frozen inventory must not be empty")
    verified = {}
    for relative, digest in expected.items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            raise ValueError("Frozen path escapes repository")
        if not path.is_file():
            raise ValueError("Frozen implementation file missing: " + relative)
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != digest:
            raise ValueError("Frozen implementation file hash changed: " + relative)
        verified[relative] = actual
    return verified
