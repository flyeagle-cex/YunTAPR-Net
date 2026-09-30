"""Load pinned science and explicit engineering revisions without changing D1-D8."""
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


def load_contract(root: Path = REPO_ROOT, *, version: str = "v1.1", engineering_version: int | None = None) -> tuple[dict, dict]:
    if version not in ("v1", "v1.1"):
        raise ValueError("Unsupported scientific contract version")
    science_path = root / f"config/science_contract_{version}.yaml"
    revision = engineering_version if engineering_version is not None else (2 if version == "v1" else 4)
    if (version == "v1" and revision != 2) or (version == "v1.1" and revision not in (3, 4)):
        raise ValueError("Unsupported science and engineering revision combination")
    engineering_path = root / f"config/b0_engineering_v{revision}.yaml"
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
    expected = {"downsample_kernel": 3, "downsample_padding": 1, "decoder_interpolation_mode": "nearest", "align_corners": None,
                "input_projection_skip_initialization": "zeros"}
    if any(engineering["backbone"][k] != v for k, v in expected.items()):
        raise ValueError("Unreviewed backbone engineering configuration")
    if engineering["projection"]["feature_reduction_operator"] != "arithmetic_mean":
        raise ValueError("Unsupported projection operator")
    if engineering["loss"]["quantile_axis_reduction"] != "mean":
        raise ValueError("Unsupported quantile axis reduction")
    if engineering["missing"]["requires_separate_validity_mask"] is not True or engineering["missing"]["placeholder_is_physical_observation"] is not False:
        raise ValueError("Missing-value policy must retain separate mask")
    if version == "v1.1":
        if science["normalization"]["status"] != "FROZEN" or science["normalization"]["policy"] != "TRAIN_ONLY_Z_SCORE":
            raise ValueError("Decision 8 must be frozen Train-only Z-score")
        if science["execution_status"]["FORMAL_TRAINING_AUTHORIZED"] is not False:
            raise ValueError("Formal training is not authorized")
        if engineering["quantile_numerics"]["epsilon_mono"] != 1e-4:
            raise ValueError("Unapproved monotonic quantile epsilon")
        if engineering["staging"]["max_temporary_bytes"] < 734003200:
            raise ValueError("Staging cannot accommodate verified inventory")
        for key in ("one_file_at_a_time", "verify_sha256", "cleanup_required"):
            if engineering["staging"][key] is not True:
                raise ValueError("Staging safeguards cannot be disabled")
        if revision == 4:
            numerics = engineering["quantile_numerics"]
            required = {"status": "ENGINEERING_CONFIG", "epsilon_mono": 1e-4,
                        "epsilon_domain": "log1p(mm h^-1)", "raw_dtype": "float32",
                        "accumulation_dtype": "float64", "qlog_output_dtype": "float64",
                        "physical_quantile_dtype": "float64", "recurrence": "sequential",
                        "monotonic_failure_action": "RAISE", "physical_overflow_action": "RAISE"}
            if any(numerics.get(k) != v for k, v in required.items()):
                raise ValueError("Unapproved quantile v4 precision configuration")
    return science, engineering
