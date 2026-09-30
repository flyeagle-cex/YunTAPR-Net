"""Load the researcher-approved v1 contract without implicit defaults."""
from pathlib import Path
import hashlib
import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_contract(root: Path = REPO_ROOT) -> tuple[dict, dict]:
    science_path = root / "config/science_contract_v1.yaml"
    engineering_path = root / "config/b0_engineering_v1.yaml"
    science = yaml.safe_load(science_path.read_text(encoding="utf-8"))
    engineering = yaml.safe_load(engineering_path.read_text(encoding="utf-8"))
    if sha256(science_path) != engineering["scientific_contract_sha256"]:
        raise ValueError("Scientific contract SHA256 differs from engineering snapshot")
    if sha256(root / science["authoritative_document"]) != engineering["scientific_freeze_document_sha256"]:
        raise ValueError("Scientific Freeze document SHA256 differs from pinned version")
    if science["execution_status"]["B0_FORMAL_SCIENTIFIC_CONTRACT"] != "FROZEN":
        raise ValueError("B0 scientific contract is not FROZEN")
    if science["execution_status"]["B0_FORMAL_TRAINING_STARTED"] is not False or engineering["formal_training_started"] is not False:
        raise ValueError("Formal training must remain stopped")
    if science["missing_qc"]["partial_and_support_thresholds"]["status"] != "DEVELOPMENT_ESTIMATED_PARAMETER":
        raise ValueError("QC threshold status changed")
    for key in ("focal_alpha", "focal_gamma"):
        value = science["probability"]["loss"][key]
        if value["status"] != "DEVELOPMENT_ESTIMATED_PARAMETER" or value["numeric_value"] is not None:
            raise ValueError(f"Unexpected scientific value for {key}")
    channels = science["backbone"]["channels"]
    groups = engineering["backbone"]["groupnorm_groups"]
    if not all(c % groups == 0 for c in channels):
        raise ValueError("GroupNorm groups must divide every frozen channel count")
    expected = {"downsample_kernel": 3, "downsample_padding": 1, "decoder_interpolation_mode": "nearest", "align_corners": None}
    if any(engineering["backbone"][k] != v for k, v in expected.items()):
        raise ValueError("Unreviewed backbone engineering configuration")
    if engineering["projection"]["feature_reduction_operator"] != "arithmetic_mean":
        raise ValueError("Unsupported projection operator")
    if engineering["loss"]["quantile_axis_reduction"] != "mean":
        raise ValueError("Unsupported quantile axis reduction")
    if engineering["missing"]["requires_separate_validity_mask"] is not True or engineering["missing"]["placeholder_is_physical_observation"] is not False:
        raise ValueError("Missing-value policy must retain separate mask")
    return science, engineering
