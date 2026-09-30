"""Bounded, caller-owned English staging for netCDF4 Unicode-path workaround.

The only unlink target is a UUID file created by this instance under staging_root.
Raw source files are opened read-only. No permanent monthly copy is made.
"""
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
import os
import shutil
import time
import uuid
from yuntapr.contracts.loader import REPO_ROOT, load_contract, sha256
from yuntapr.data.himawari_b13 import read_b13_local
from yuntapr.data.imerg_v07 import read_imerg_local
from yuntapr.spatial.sp04_mapping import SP04Mapping


@dataclass
class StagingRecord:
    source_path: str
    temporary_bytes: int
    copy_seconds: float | None = None
    read_seconds: float | None = None
    size_match: bool = False
    sha256_match: bool | None = None
    cleanup_success: bool = False
    error: str | None = None
    cleanup_error: str | None = None


class BoundedEnglishStaging:
    def __init__(self, staging_root: Path, max_bytes: int, verify_sha256: bool):
        self.root = staging_root.resolve()
        if not self.root.is_absolute():
            raise ValueError("Staging root must be an absolute English path")
        if not str(self.root).isascii() or max_bytes <= 0:
            raise ValueError("Staging root must be ASCII and max_bytes positive")
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max_bytes
        self.verify_sha256 = verify_sha256
        self.records: list[StagingRecord] = []
        self._active = False
        self._owned: set[Path] = set()

    @contextmanager
    def local(self, source: Path):
        source = source.resolve(strict=True)
        if self._active or source.is_relative_to(self.root):
            raise ValueError("Staging permits only one external source at a time")
        size = source.stat().st_size
        if size > self.max_bytes:
            raise ValueError("Source exceeds bounded staging byte cap")
        dest = (self.root / f"yuntapr_b0_{uuid.uuid4().hex}.nc").resolve()
        if dest.parent != self.root or dest in self._owned or dest.exists():
            raise ValueError("Unsafe staging destination")
        record = StagingRecord(str(source), size)
        self._active = True
        self._owned.add(dest)
        try:
            start = time.perf_counter()
            with source.open("rb") as reader, dest.open("xb") as writer:
                shutil.copyfileobj(reader, writer, 1024 * 1024)
            record.copy_seconds = time.perf_counter() - start
            record.size_match = dest.stat().st_size == size
            if not record.size_match:
                raise IOError("Staging copy size mismatch")
            if self.verify_sha256:
                record.sha256_match = sha256(source) == sha256(dest)
                if not record.sha256_match:
                    raise IOError("Staging SHA256 mismatch")
            start = time.perf_counter()
            try:
                yield dest
            finally:
                record.read_seconds = time.perf_counter() - start
        except Exception as error:
            record.error = repr(error)
            raise
        finally:
            if dest in self._owned and dest.parent == self.root:
                try:
                    dest.unlink(missing_ok=True)
                    record.cleanup_success = True
                    self._owned.remove(dest)
                except OSError as error:
                    record.cleanup_error = repr(error)
            self.records.append(record)
            self._active = False


def configured_staging(root=REPO_ROOT) -> BoundedEnglishStaging:
    """Require an explicit English staging root via the versioned env-var name."""
    _, engineering = load_contract(root)
    cfg = engineering["staging"]
    location = os.environ.get(cfg["staging_root_env_var"])
    if not location:
        raise ValueError(f"Set {cfg['staging_root_env_var']} to a bounded English staging directory")
    return BoundedEnglishStaging(Path(location), int(cfg["max_temporary_bytes"]), bool(cfg["verify_sha256"]))


class StagedB13Reader:
    def __init__(self, staging: BoundedEnglishStaging, mapping: SP04Mapping):
        self.staging = staging
        self.mapping = mapping

    def __call__(self, source_path: Path, nominal_time):
        with self.staging.local(source_path) as english_path:
            x, valid, frame = read_b13_local(english_path, self.mapping, nominal_time)
        return x, valid, replace(frame, path=source_path)


class StagedIMERGReader:
    def __init__(self, staging: BoundedEnglishStaging, mapping: SP04Mapping):
        self.staging = staging
        self.mapping = mapping

    def __call__(self, source_path: Path, index: int):
        with self.staging.local(source_path) as english_path:
            return read_imerg_local(english_path, index, self.mapping)
