"""Explicit B0 sample assembly; accepts records, never builds a multi-year index."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable
import numpy as np
from torch.utils.data import Dataset
from yuntapr.data.sample_schema import B0Sample, HimawariFrame, select_latest_causal_frame, utc
from yuntapr.data.masks import read_frozen_yunnan_mask
from yuntapr.data.formal_policy import select_formal_frame, require_full_valid
from yuntapr.spatial.sp04_mapping import SP04Mapping


@dataclass(frozen=True)
class B0Record:
    sample_id: str
    imerg_window_start: datetime
    frames: tuple[HimawariFrame, ...]
    imerg_path: Path | None
    imerg_index: int | None
    imerg_product: str | None
    imerg_version: str | None
    imerg_run_type: str | None
    imerg_provenance_verified: bool = False


class B0Dataset(Dataset):
    """Readers are injected and must verify source coordinates and source identity.

    b13_reader(path, nominal) -> (x[501,501], valid[501,501], metadata_frame)
    imerg_reader(path, index) -> (y[100,100], valid[100,100], converted_T)
    Local science files remain outside the public repository.
    """

    def __init__(self, records: list[B0Record], mapping: SP04Mapping, yunnan_mask: np.ndarray | None,
                 b13_reader: Callable, imerg_reader: Callable | None, *,
                 frozen_mask_path: Path | None = None, engineering_fixture_mask: bool = False,
                 formal_supervised: bool = False, normalizer=None):
        self.records = records
        self.mapping = mapping
        self.yunnan_mask = yunnan_mask
        self.b13_reader = b13_reader
        self.imerg_reader = imerg_reader
        self.formal_supervised = formal_supervised
        self.normalizer = normalizer
        if formal_supervised and normalizer is None:
            raise ValueError("FORMAL_SUPERVISED_REQUIRES_NORMALIZATION")
        if yunnan_mask is not None and (yunnan_mask.dtype != bool or yunnan_mask.shape != (100, 100)):
            raise ValueError("Evaluation mask must be bool [100,100]")
        if yunnan_mask is not None:
            if frozen_mask_path is not None:
                verified = read_frozen_yunnan_mask(frozen_mask_path, mapping)
                if not np.array_equal(yunnan_mask, verified):
                    raise ValueError("Evaluation mask differs from frozen SHA-verified payload")
            elif not engineering_fixture_mask:
                raise ValueError("Evaluation mask requires frozen SHA-verified path; explicit engineering fixture only in tests")

    def __len__(self):
        return len(self.records)

    def __getitem__(self, index: int) -> B0Sample:
        record = self.records[index]
        start = utc(record.imerg_window_start)
        analysis = start + timedelta(minutes=30)
        expected = analysis - timedelta(minutes=10)
        expected_available = any(utc(f.nominal_time) == expected and f.path.is_file() for f in record.frames)
        older_available = any(utc(f.nominal_time) < expected and utc(f.obs_end) <= analysis and f.path.is_file() for f in record.frames)
        selected = (select_formal_frame(list(record.frames), analysis) if self.formal_supervised
                    else select_latest_causal_frame(list(record.frames), analysis))
        if not selected.path.is_file():
            raise FileNotFoundError(f"REQUIRED_HIMAWARI_FRAME_MISSING: {selected.path}")
        x, valid, observed = self.b13_reader(selected.path, selected.nominal_time)
        if not isinstance(x, np.ndarray) or x.shape != (501, 501) or valid.shape != x.shape or valid.dtype != bool:
            raise ValueError("B13 data/mask shape or dtype mismatch")
        if np.any(~valid) and not np.all(np.isnan(x[~valid])):
            raise ValueError("Invalid B13 must remain NaN, not an unmarked placeholder")
        if not np.isfinite(x[valid]).all():
            raise ValueError("Valid B13 contains nonfinite values")
        if not valid.any():
            raise ValueError("B13_ALL_FILL_REJECT_SAMPLE")
        if self.formal_supervised:
            require_full_valid(x, valid)
        if (utc(observed.obs_start), utc(observed.obs_end), utc(observed.nominal_time)) != (utc(selected.obs_start), utc(selected.obs_end), utc(selected.nominal_time)):
            raise ValueError("Himawari source metadata changed since frame selection")
        if observed.date_created != selected.date_created:
            raise ValueError("Himawari date_created changed since frame selection")
        if utc(observed.obs_end) > analysis:
            raise ValueError("Himawari future observation rejected")
        y = target_valid = None
        has_final = record.imerg_product == "IMERG" and record.imerg_version == "V07" and record.imerg_run_type == "Final" and record.imerg_path is not None
        if has_final:
            if not record.imerg_provenance_verified:
                raise ValueError("IMERG V07 Final provenance must be verified upstream before supervision")
            if record.imerg_index is None or self.imerg_reader is None:
                raise ValueError("IMERG Final reader/index missing")
            y, target_valid, converted_t = self.imerg_reader(record.imerg_path, record.imerg_index)
            if utc(converted_t) != start:
                raise ValueError("IMERG converted CF time is not selected window start")
            if y.shape != (100, 100) or target_valid.shape != y.shape or target_valid.dtype != bool:
                raise ValueError("IMERG target data/mask mismatch")
            if not np.isfinite(y[target_valid]).all() or np.any(y[target_valid] < 0):
                raise ValueError("Invalid IMERG valid precipitation")
            if np.any(np.isfinite(y[~target_valid])):
                raise ValueError("Invalid IMERG target must remain NaN")
        elif any(x is not None for x in (record.imerg_path, record.imerg_index)):
            raise ValueError("Non-V07-Final IMERG cannot substitute for supervision")
        native_mask = valid.reshape(1, 1, 501 * 501)
        members = self.mapping.indices.numpy().reshape(100, 100, 25)
        support = native_mask[0, 0, members].mean(-1).astype(np.float32)
        supervised = bool(has_final and self.yunnan_mask is not None and np.any(target_valid & self.yunnan_mask))
        if start.year == 2025 and start.month == 10:
            if has_final:
                raise ValueError("2025-10 V07 Final availability conflicts with frozen contract")
            supervised = False
        used_older = utc(selected.nominal_time) < expected
        formal_qc = bool(supervised and valid.all() and expected_available and utc(selected.nominal_time) == expected)
        normalized = None
        if self.formal_supervised:
            if not formal_qc:
                raise ValueError("FORMAL_SUPERVISION_ELIGIBILITY_REJECTED")
            normalized = self.normalizer.transform(x, valid, start)
        return B0Sample(
            sample_id=record.sample_id, analysis_time=analysis, imerg_window_start=start, imerg_window_end=analysis,
            himawari_path=selected.path, himawari_nominal_time=selected.nominal_time,
            himawari_obs_start=observed.obs_start, himawari_obs_end=observed.obs_end,
            himawari_date_created=observed.date_created, x_b13=x, b13_valid_mask=valid,
            y_imerg=y, imerg_valid_mask=target_valid, yunnan_eval_mask=self.yunnan_mask,
            target_support_fraction=support, observation_eligible=True, supervised_eligible=supervised,
            inference_eligible=True, internal_test_eligible=bool(supervised and start.year == 2025 and start.month in range(3, 10)),
            external_validation_eligible=False, imerg_product=record.imerg_product, imerg_version=record.imerg_version,
            imerg_run_type=record.imerg_run_type, imerg_provenance_verified=record.imerg_provenance_verified,
            qc_status="PASS" if supervised else "UNLABELED_OR_NO_VALID_SUPERVISION",
            reject_reason=None if supervised else "NO_V07_FINAL_OR_NO_VALID_YUNNAN_PIXELS",
            b13_invalid_count=int((~valid).sum()), b13_valid_fraction=float(valid.mean()),
            expected_latest_slot=expected, expected_latest_available=expected_available,
            older_causal_available=older_available, used_older_causal_frame=used_older,
            b13_full_valid=bool(valid.all()), formal_supervised_qc_pass=formal_qc,
            normalization_version=self.normalizer.version if normalized is not None else None,
            normalization_mu=self.normalizer.mu if normalized is not None else None,
            normalization_sigma=self.normalizer.sigma if normalized is not None else None,
            normalization_artifact_sha256=self.normalizer.artifact_sha256 if normalized is not None else None,
            x_b13_normalized=normalized,
            eligibility_scope="FORMAL_SUPERVISED_RULES_ENGINEERING_EXECUTION" if self.formal_supervised else "ENGINEERING_ONLY")
