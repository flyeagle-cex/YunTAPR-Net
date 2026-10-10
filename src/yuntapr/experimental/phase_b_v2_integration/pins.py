"""Verify only published sources and metadata; never open external data pins."""
from pathlib import Path
import hashlib
import json
REPO = Path(__file__).resolve().parents[4]
REFERENCE = 'docs/phase_b_v2_isolated_integration/v1/source_identity.json'
REFERENCE_SHA = '4fe9598f85610b07d377b2f4ac8a6dfbe13c88295127476c1d52bedf7eb1e4c5'

def verify_frozen_sources() -> int:
    path = REPO / REFERENCE
    if hashlib.sha256(path.read_bytes()).hexdigest() != REFERENCE_SHA:
        raise ValueError("Integration source identity manifest changed")
    record = json.loads(path.read_text(encoding="utf-8"))
    for item in record["repository_files"]:
        source = (REPO / item["path"]).resolve()
        if not source.is_relative_to(REPO.resolve()) or hashlib.sha256(source.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("Published source identity mismatch: " + item["path"])
    return len(record["repository_files"])
