"""Pinned Development-derived Phase-A normalization; fitting lives in an audit script."""
from dataclasses import dataclass
import json
from pathlib import Path
import numpy as np
from yuntapr.contracts.loader import REPO_ROOT, load_contract, sha256
from yuntapr.data.formal_policy import require_full_valid
from yuntapr.data.sample_schema import utc


@dataclass(frozen=True)
class PhaseANormalizer:
    version: str
    mu: float
    sigma: float
    artifact_sha256: str

    @classmethod
    def from_pinned(cls, root: Path = REPO_ROOT):
        science, config = load_contract(root)
        path = root / science["normalization"]["phase_a"]["artifact"]
        pin = config.get("normalization_artifact", {})
        if pin.get("path") != str(path.relative_to(root)).replace("\\", "/") or pin.get("sha256") != sha256(path):
            raise ValueError("NORMALIZATION_ARTIFACT_NOT_PINNED_OR_CHANGED")
        result = json.loads(path.read_text(encoding="utf-8"))
        if (result["fit_years"] != [2023] or result["fit_months"] != list(range(3, 11))
                or result["ddof"] != 0 or result["ready"] is not True
                or result["status"] != "DEVELOPMENT_DERIVED_PARAMETER"
                or result["valid_pixel_count"] != result["eligible_scene_count"] * 251001
                or result["2025_pixels_read"] is not False):
            raise ValueError("INVALID_PHASE_A_NORMALIZATION_POPULATION")
        if result["scientific_contract_sha256"] != sha256(root / "config/science_contract_v1.1.yaml"):
            raise ValueError("NORMALIZATION_SCIENCE_CONTRACT_MISMATCH")
        if sha256(path.with_name("normalization_phaseA_sample_manifest.csv")) != result["sample_manifest_sha256"]:
            raise ValueError("NORMALIZATION_SAMPLE_MANIFEST_CHANGED")
        return cls(result["normalization_version"], result["mean_K"], result["std_K"], pin["sha256"])

    def transform(self, raw_kelvin, valid, window_start):
        t = utc(window_start)
        if t.year not in (2023, 2024) or t.month not in range(3, 11):
            raise ValueError("PHASE_A_STATISTICS_ONLY_FOR_2023_TRAIN_2024_VALIDATION; 2025_REQUIRES_FINALFIT")
        require_full_valid(raw_kelvin, valid)
        if not np.isfinite(self.mu) or not np.isfinite(self.sigma) or self.sigma <= 0 or not self.artifact_sha256:
            raise ValueError("NORMALIZATION_STATISTICS_INVALID_OR_UNIDENTIFIED")
        result = ((raw_kelvin.astype(np.float64) - self.mu) / self.sigma).astype(np.float32)
        if not np.isfinite(result).all():
            raise ValueError("NONFINITE_NORMALIZED_B13")
        return result
