"""Bounded Stage-4 work-package B: multi-seed candidate reproduction.

The module is deliberately torch-free and imports only the standard library at
module import time.  ``numpy`` and the frozen Stage-45 helper routines in
``tools/research_readiness/stage45_dev_acceptance.py`` are imported lazily from
inside the functions that need them, so the repository's base CPython can run
the unit tests without the training environment.

The scientific rules, thresholds, task list, file accounting, and gates below
are frozen.  Anything that changes them must change this module and the
pre-registration together, which is out of scope for an executor.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

KIND = "BOUNDED_STAGE4_MULTISEED_CANDIDATE_REPRODUCTION"
SCOPE = "FOUR_MODEL_COSINE9_REAL_ZERO_CANDIDATE_REPRODUCTION_V1"
STATUS = "COMPLETE_STAGE4_MULTISEED_CANDIDATE_REPRODUCTION"
DECISION = "MULTISEED_CANDIDATE_REPRODUCTION_Q2_Q3_EVALUATION"
ENTRY = "tools/research_readiness/start_multiseed_candidate_reproduction.py"
MODULE = "yuntapr.experimental.research_readiness.multiseed_candidate_reproduction"
MODEL = "B7"
ARMS = ("REAL", "ZERO")
SEEDS = (2030, 2031)
TASKS = ("REAL_s2030", "ZERO_s2030", "REAL_s2031", "ZERO_s2031")
REAL_TASKS = ("REAL_s2030", "REAL_s2031")
ZERO_TASKS = ("ZERO_s2030", "ZERO_s2031")
CONTROLS = {
    "REAL": "REAL_PHYSICAL_DOTE",
    "ZERO": "ZERO_NUMERIC_RETAIN_REAL_MASKS",
}
FINAL_2025_ACCESS = False

MIB = 1024 * 1024
GIB = 1024 * MIB
NODES = 32
SLOTS = 6
BANDS = ("08", "13")
GRID = (100, 100)
SUPERVISION_PIXELS_PER_SCENE = 3430
SCENE_BATCH_LIMIT = 8
SCENES = 963
ARRAY_SHARDS_PER_TASK = 121
ARRAY_BYTES_PER_TASK = 881_894_762
SUPERVISED_PIXELS = 3_303_090
CANDIDATE_THRESHOLD = 20.0
A0_THRESHOLD = 9.5373
SPLIT_THRESHOLD = 2.3612
TARGET_MASS = 20.01
THRESHOLD = 20.0
RAIN_THRESHOLD = 0.1
WEAK_UPPER = 1.0
MAX_SELECTED_ROWS = 50
MAX_INFEASIBLE_ROWS = 50
FROZEN_METRIC_TOLERANCE = 1e-12

PRIVATE_ROOT = Path("docs/research_readiness/.local")
SOURCE_VOLUME = Path(r"H:\葵花202303_202510")
SATELLITE_ROOT = SOURCE_VOLUME
SATELLITE_MANIFEST = Path(
    r"F:\codex_downloads\_cm\r24\docs\core_stage3\.local\plan_20261024_v3"
    r"\manifest_2024_fixed_f006.json"
)
PARENT_RESULTS_RELATIVE = (
    "docs/research_readiness/20261121_stage45_observation_feasibility/"
    "STAGE45_STEP4_EVALUATION_RESULTS_V1.json"
)
TERRAIN_RESULTS_RELATIVE = (
    "docs/research_readiness/20261121_stage45_observation_feasibility/"
    "STAGE45_STEP4_MULTISEED_TERRAIN_RESULTS_V1.json"
)
SEED2029_RESULTS_RELATIVE = (
    "docs/research_readiness/20261121_stage45_observation_feasibility/"
    "STAGE45_DEV_ACCEPTANCE_RESULTS_V1.json"
)

PARENT_RESULTS_SHA256 = (
    "2318032d94882dac9df50cf4ce47b8b0e687ad041759f2f86660f4fb3a567ebc"
)
PARENT_RESULTS_BYTES = 33_526
PARENT_COMPLETION_SHA256 = (
    "87fe93d4b443d0aef92b1970b8bed5e99bce9c8ac7ef4d4f5269bd480a34b7d4"
)
PARENT_COMPLETION_BYTES = 52_096
TERRAIN_RESULTS_BYTES = 9_900
SATELLITE_MANIFEST_BYTES = 7_225_685
SATELLITE_MANIFEST_INTERNAL_SHA256 = (
    "6bd5a8102929f3c3432753a4d6fb33e7e3ea69482c88abf13eabd729e26981de"
)
SP04_MANIFEST_SHA256 = (
    "e1c5d8ab1b58407503db4b56124f4a34a360507280b0e7989e8b9e2f60888473"
)

CHECKPOINTS = {
    "REAL_s2030": {
        "sha256": "ee7f81da1c6edf08b9417aff188bd3f00531bd768ff6cf0440434ad4bee204fc",
        "bytes": 53_906_437,
    },
    "ZERO_s2030": {
        "sha256": "c8e0f5747b2236174e54511b1f461868cac4d53fe8cffa9e87b189d4403a75c6",
        "bytes": 53_906_757,
    },
    "REAL_s2031": {
        "sha256": "ce2aad589e29a9ac4bf29ed9595f107b263f14b6f30596b92baf0bb760ab126d",
        "bytes": 53_906_885,
    },
    "ZERO_s2031": {
        "sha256": "47022bd59ba399c7773d482c7f0ae71017212d50435f90f10d6062b3bfa2faba",
        "bytes": 53_906_885,
    },
}

SATELLITE_FILES = {
    "REAL_s2030": {"files": 78, "bytes": 351_193_068, "s1_scenes": 13, "s1_rows": 72},
    "ZERO_s2030": {"files": 66, "bytes": 288_604_839, "s1_scenes": 11, "s1_rows": 70},
    "REAL_s2031": {"files": 132, "bytes": 590_955_098, "s1_scenes": 22, "s1_rows": 143},
    "ZERO_s2031": {"files": 144, "bytes": 644_432_923, "s1_scenes": 24, "s1_rows": 138},
}

EXPECTED = {
    "REAL_s2030": {
        "counts": {
            "scenes": SCENES,
            "n_valid": SUPERVISED_PIXELS,
            "n_rain": 407_820,
            "n_strong": 717,
            "n_weak": 246_473,
            "candidate_rows": 1119,
            "s1_rows": 72,
            "s1_scenes": 13,
            "satellite_files": 78,
            "satellite_bytes": 351_193_068,
        },
        "metrics": {
            "strong_physical_pinball_over20": 0.5110645240302718,
            "q32_support_tp": 149,
            "q32_support_fp": 4354,
            "point_a_tp": 0,
            "point_a_fp": 0,
            "weak_log_pinball": 0.08708345141541186,
        },
    },
    "ZERO_s2030": {
        "counts": {
            "scenes": SCENES,
            "n_valid": SUPERVISED_PIXELS,
            "n_rain": 407_820,
            "n_strong": 717,
            "n_weak": 246_473,
            "candidate_rows": 1131,
            "s1_rows": 70,
            "s1_scenes": 11,
            "satellite_files": 66,
            "satellite_bytes": 288_604_839,
        },
        "metrics": {
            "strong_physical_pinball_over20": 0.5088647063017728,
            "q32_support_tp": 148,
            "q32_support_fp": 4493,
            "point_a_tp": 0,
            "point_a_fp": 0,
            "weak_log_pinball": 0.0871356832605682,
        },
    },
    "REAL_s2031": {
        "counts": {
            "scenes": SCENES,
            "n_valid": SUPERVISED_PIXELS,
            "n_rain": 407_820,
            "n_strong": 717,
            "n_weak": 246_473,
            "candidate_rows": 1808,
            "s1_rows": 143,
            "s1_scenes": 22,
            "satellite_files": 132,
            "satellite_bytes": 590_955_098,
        },
        "metrics": {
            "strong_physical_pinball_over20": 0.5031727581453883,
            "q32_support_tp": 181,
            "q32_support_fp": 6019,
            "point_a_tp": 0,
            "point_a_fp": 0,
            "weak_log_pinball": 0.08926385613549269,
        },
    },
    "ZERO_s2031": {
        "counts": {
            "scenes": SCENES,
            "n_valid": SUPERVISED_PIXELS,
            "n_rain": 407_820,
            "n_strong": 717,
            "n_weak": 246_473,
            "candidate_rows": 1700,
            "s1_rows": 138,
            "s1_scenes": 24,
            "satellite_files": 144,
            "satellite_bytes": 644_432_923,
        },
        "metrics": {
            "strong_physical_pinball_over20": 0.5011434163139744,
            "q32_support_tp": 187,
            "q32_support_fp": 5791,
            "point_a_tp": 0,
            "point_a_fp": 0,
            "weak_log_pinball": 0.08922417583852392,
        },
    },
}

PER_TASK_BUDGET = {
    task: {
        "arrays_opens": ARRAY_SHARDS_PER_TASK,
        "arrays_bytes": ARRAY_BYTES_PER_TASK,
        "satellite_opens": SATELLITE_FILES[task]["files"],
        "satellite_bytes": SATELLITE_FILES[task]["bytes"],
        "scientific_opens": ARRAY_SHARDS_PER_TASK + SATELLITE_FILES[task]["files"],
        "scientific_bytes": ARRAY_BYTES_PER_TASK + SATELLITE_FILES[task]["bytes"],
    }
    for task in TASKS
}

BUDGET = {
    "kind": KIND,
    "model": MODEL,
    "tasks": list(TASKS),
    "total_scientific_file_opens": 907,
    "total_scientific_source_bytes": 5_410_034_087,
    "scientific_file_opens": 904,
    "scientific_source_bytes": 5_402_764_976,
    "arrays_open_instances": 484,
    "arrays_reference_bytes": 3_527_579_048,
    "satellite_open_instances": 420,
    "satellite_reference_bytes": 1_875_185_928,
    "metadata_open_instances": 3,
    "metadata_reference_bytes": 7_269_111,
    "checkpoint_loads": 0,
    "model_inference_passes": 0,
    "forward_batches": 0,
    "optimizer_updates": 0,
    "retrains": 0,
    "refits": 0,
    "retries": 0,
    "replays": 0,
    "maximum_seconds": 1800,
    "minimum_free_bytes": 8 * GIB,
    "maximum_scientific_file_opens": 3700,
    "maximum_scientific_source_bytes": 18_000_000_000,
    "maximum_output_bytes": 4 * GIB,
    "development_scenes": SCENES,
    "development_pixels": SUPERVISED_PIXELS,
    "per_task": PER_TASK_BUDGET,
}

DATA_SCOPE = {
    "role": "Development",
    "year": 2024,
    "scenes": SCENES,
    "n_valid": SUPERVISED_PIXELS,
    "n_rain": 407_820,
    "n_strong": 717,
    "n_weak": 246_473,
    "lead": 6,
    "mode": "retrospective",
    "population_ids_sha256": (
        "916302412bf024942aadeefe969d12c74452481ef24dedc30b1262b24609cf76"
    ),
    "partition_sha256": (
        "01b95f12d26a3f6f4ff05620414cdae66c5cec23bd2808b0af2de40e4615291c"
    ),
    "supervision_mask_sha256": (
        "70368bec3149e998922d565dab83347ba33f465df481a03ac3f90b85f1286d4b"
    ),
}

RULES = {
    "candidate_rule": "FP64 p * expm1(qlog[:, 31]) > 20.0",
    "a0_rule": "float32(p * mean(expm1(qlog), axis=1))",
    "a0_threshold": A0_THRESHOLD,
    "candidate_scenes": "scenes containing at least one S1 row",
    "satellite_slots": "slot_0_nominal .. slot_5_nominal",
    "satellite_bands": ["tbb_08", "tbb_13"],
    "area_mean_rule": (
        "mean of the 25 native SP04 centers for each target cell; all 25 "
        "centers must be valid, otherwise the cell is undefined"
    ),
    "split_rule": "SP04 area mean of tbb_08 minus SP04 area mean of tbb_13",
    "split_min_rule": "minimum split over the six causal slots for the scene",
    "split_threshold": SPLIT_THRESHOLD,
    "selection_rule": "S1 AND S2",
    "action_rule": (
        "blend the 31 sub-top quantiles toward the fixed q32 with "
        "u = (20.01/p - mean(nodes)) / ((31/32) * (q32 - mean(nodes[:31]))); "
        "require denominator > 0, 0 < u < 1, strictly increasing nodes and "
        "new A > 20"
    ),
    "action_constant": TARGET_MASS,
    "gates": [
        "gate1 strong physical pinball/20 strictly decreases",
        "gate2 strong fixed-A hits new >= 1 and >= baseline",
        "gate3 nonstrong fixed-A hits new <= baseline",
        "gate4 q32 support true positives unchanged",
        "gate5 q32 support false positives unchanged",
        "gate6 weak (0.1 < truth <= 1) log pinball delta == 0 within 1e-12",
        "gate7 occurrence Brier BY_CONSTRUCTION_EQUAL",
        "gate8 occurrence AP BY_CONSTRUCTION_EQUAL",
        "gate9 occurrence AUROC BY_CONSTRUCTION_EQUAL",
    ],
    "pass_rule": (
        "PASS iff gate1 strictly decreases, gates 2-6 pass, and zero weak or "
        "nonstrong rows are selected"
    ),
    "q2_rule": (
        "all REAL tasks PASS -> CANDIDATE_REPRODUCED_ACROSS_SEEDS; one or more "
        "but not all PASS -> PARTIAL; none PASS -> NOT_REPRODUCED"
    ),
    "q3_rule": (
        "ZERO tasks are descriptive only; an attribution warning is recorded "
        "when a zero-control selected-row readout improves like REAL"
    ),
    "control": "ZERO_NUMERIC_RETAIN_REAL_MASKS",
    "max_selected_rows": MAX_SELECTED_ROWS,
    "max_infeasible_rows": MAX_INFEASIBLE_ROWS,
    "final_2025_access": FINAL_2025_ACCESS,
}

EXECUTION_ENVIRONMENT = {
    "PYTHONHASHSEED": "2029",
    "PYTHONUTF8": "1",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "CUBLAS_WORKSPACE_CONFIG": ":4096:8",
}

SEED2029_REFERENCE_BASE = {
    "task": "B7_s2029",
    "decision": "PASS",
    "source": SEED2029_RESULTS_RELATIVE,
    "note": (
        "The already-recorded Stage-45 seed2029 nine-gate acceptance was PASS; "
        "this package references it and does not recompute it."
    ),
}


# ---------------------------------------------------------------------------
# Primitive helpers
# ---------------------------------------------------------------------------


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def read(path):
    return json.loads(Path(path).read_bytes())


def sha(path):
    digest_value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest_value.update(chunk)
    return digest_value.hexdigest()


def sha256_bytes(value):
    return hashlib.sha256(bytes(value)).hexdigest()


def digest(value):
    return sha256_bytes(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    )


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(
            json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
            + "\n"
        )


def private_seal(private):
    return digest(
        {
            key: value
            for key, value in private.items()
            if key not in ("proposal_sha256", "private_preparation_sha256")
        }
    )


def proposal_seal(proposal):
    return digest(
        {key: value for key, value in proposal.items() if key != "proposal_sha256"}
    )


def _require(condition, message, error=ValueError):
    if not condition:
        raise error(message)


def _absolute(value, label):
    path = Path(value)
    if not path.is_absolute():
        raise ValueError(f"Absolute {label} required")
    return path.resolve()


def _git(root, *arguments, text=True):
    return subprocess.check_output(
        ["git", "-C", str(root), *arguments], text=text, stderr=subprocess.STDOUT
    ).strip()


def _git_head(root):
    return _git(root, "rev-parse", "HEAD")


def _clean_tree(root):
    return _git(root, "status", "--porcelain") == ""


def _free_bytes(path):
    return shutil.disk_usage(path).free


def _plain(value):
    """Recursively convert numpy scalars/arrays so json.dumps is monomorphic."""
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if value is None or isinstance(value, (bool, str)):
        return value
    try:
        import numpy as np
    except ImportError:  # pragma: no cover - numpy is a test dependency
        np = None
    if np is not None and isinstance(value, np.ndarray):
        return value.tolist()
    if np is not None and isinstance(value, np.generic):
        return value.item()
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return float(value)
    return value


def _freeze(value):
    """A JSON-native deep copy used before seals and results serialization."""
    return json.loads(json.dumps(_plain(value), sort_keys=True, allow_nan=False))


def task_name(arm, seed):
    return f"{arm}_s{int(seed)}"


def _repository_root():
    for parent in Path(__file__).resolve().parents:
        if (
            (parent / "src").is_dir()
            and (parent / "tools/research_readiness/stage45_dev_acceptance.py").is_file()
        ):
            return parent
    raise RuntimeError("Cannot locate the YunTAPR repository root")


_HELPER_MODULE = None


def _helpers():
    """Load the frozen Stage-45 helper routines by path, once."""
    global _HELPER_MODULE
    if _HELPER_MODULE is None:
        import importlib.util

        path = _repository_root() / "tools/research_readiness/stage45_dev_acceptance.py"
        definition = importlib.util.spec_from_file_location("stage45_helpers_for_package_b", path)
        module = importlib.util.module_from_spec(definition)
        definition.loader.exec_module(module)
        _HELPER_MODULE = module
    return _HELPER_MODULE


def runtime_binding(python_executable=None):
    import numpy

    executable = Path(python_executable or sys.executable).resolve()
    return {
        "python_version": (
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        ),
        "python_executable": str(executable),
        "python_executable_sha256": sha(executable),
        "numpy_version": numpy.__version__,
    }


def code_hashes(root):
    root = Path(root)
    files = sorted((root / "src").rglob("*.py"))
    for relative in (
        ENTRY,
        "tools/research_readiness/stage45_dev_acceptance.py",
        "tools/research_readiness/start_independent_process.py",
    ):
        path = root / relative
        if path.is_file():
            files.append(path)
    return {
        path.relative_to(root).as_posix(): sha(path)
        for path in files
        if path.is_file()
    }


def execution_spec(root, proposal, namespace):
    """Return the frozen supervision specification for the executed package."""
    root = Path(root).resolve()
    namespace = Path(namespace).resolve()
    command = [
        str(Path(sys.executable).resolve()),
        "-B",
        str((root / ENTRY).resolve()),
        "execute",
        "--proposal",
        str((namespace / "PROPOSAL.json").resolve()),
        "--private-preparation",
        str((namespace / "PRIVATE_PREPARATION.json").resolve()),
        "--researcher-approval",
        str((namespace / "RESEARCHER_APPROVAL.json").resolve()),
    ]
    return {
        "kind": KIND,
        "cwd": str(root),
        "service_dir": str((namespace / "service").resolve()),
        "command": command,
        "environment": dict(EXECUTION_ENVIRONMENT),
        "proposal_sha256": proposal["proposal_sha256"],
    }


def artifact_identity(path):
    path = Path(path)
    _require(path.is_file(), f"Missing artifact: {path.name}")
    return {"bytes": path.stat().st_size, "sha256": sha(path)}


def validate_artifact(path, expected_bytes, expected_sha256, label):
    path = Path(path)
    _require(path.is_file(), f"Missing {label}: {path.name}")
    size = path.stat().st_size
    _require(size == int(expected_bytes), f"{label} byte count differs: {size}")
    current = sha(path)
    _require(current == expected_sha256, f"{label} SHA256 differs")
    return {"bytes": size, "sha256": current}


def require_fresh_namespace(namespace, root):
    namespace = _absolute(namespace, "--proposal parent directory")
    private = (Path(root).resolve() / PRIVATE_ROOT).resolve()
    _require(
        namespace.is_relative_to(private),
        f"The preparation namespace must live under {private}",
        PermissionError,
    )
    _require(not namespace.exists(), "Fresh private service namespace required", PermissionError)
    return namespace


def require_fresh_output(output_root):
    output_root = _absolute(output_root, "--output-root")
    _require(not output_root.exists(), "The output root must not exist before execution", PermissionError)
    _require(output_root.parent.is_dir(), "The output-root parent directory is missing", PermissionError)
    return output_root


def validate_approval(approval, proposal, private, commit=None):
    _require(isinstance(approval, dict), "A researcher approval object is required")
    _require(approval.get("approved_by_researcher") is True, "Researcher approval is required", PermissionError)
    _require(approval.get("authorization_scope") == proposal.get("scope"), "Approval scope differs", PermissionError)
    _require(approval.get("decision_id") == proposal.get("decision"), "Approval decision differs", PermissionError)
    _require(approval.get("proposal_sha256") == proposal.get("proposal_sha256"), "Approval proposal digest differs", PermissionError)
    code_commit = proposal.get("execution_code_commit")
    _require(isinstance(code_commit, str) and code_commit, "The execution commit is not bound")
    _require(approval.get("code_commit") == code_commit, "Approval code commit differs", PermissionError)
    if commit is not None:
        _require(commit == code_commit, "The approved commit is not checked out", PermissionError)
    _require(approval.get("tasks") == proposal.get("tasks"), "Approval task list differs", PermissionError)
    _require(approval.get("scientific_choices") == proposal.get("scientific_choices"), "Approval scientific choices differ", PermissionError)
    _require(approval.get("budget") == proposal.get("budget"), "Approval budget differs", PermissionError)
    _require(approval.get("output_root") == private.get("output_root"), "Approval output root differs", PermissionError)
    instruction = approval.get("researcher_instruction")
    _require(isinstance(instruction, str) and instruction, "Approval instruction is empty", PermissionError)
    _require(approval.get("final_2025_access") is False, "2025 must remain sealed", PermissionError)
    return {"approved_by_researcher": True, "code_commit": code_commit}


class Deadline:
    def __init__(self, seconds, clock=time.monotonic):
        self.seconds = float(seconds)
        self.clock = clock
        self.started = float(clock())

    @property
    def elapsed(self):
        return float(self.clock()) - self.started

    def remaining(self):
        return self.seconds - self.elapsed

    def check(self):
        if self.remaining() <= 0:
            raise TimeoutError("Stage-4 candidate reproduction deadline expired")


class ReadGuard:
    """Exact per-file byte/SHA verification with a global open/byte cap."""

    def __init__(self, deadline, maximum_opens, maximum_bytes, label="scientific"):
        self.deadline = deadline
        self.maximum_opens = int(maximum_opens)
        self.maximum_bytes = int(maximum_bytes)
        self.label = label
        self.opens = 0
        self.source_bytes = 0

    def __call__(self, path, expected_bytes, expected_sha256):
        if self.deadline is not None:
            self.deadline.check()
        self.opens += 1
        if self.opens > self.maximum_opens:
            raise RuntimeError(f"{self.label} file-open budget exceeded")
        content = Path(path).read_bytes()
        if len(content) != int(expected_bytes):
            raise ValueError(f"Input byte count changed: {Path(path).name}")
        actual = sha256_bytes(content)
        if actual != expected_sha256:
            raise ValueError(f"Input SHA256 changed: {Path(path).name}")
        self.source_bytes += len(content)
        if self.source_bytes > self.maximum_bytes:
            raise RuntimeError(f"{self.label} reference-byte budget exceeded")
        return content


# ---------------------------------------------------------------------------
# Array loading and per-task evaluation
# ---------------------------------------------------------------------------


def _validate_array_entry(entry, index):
    _require(isinstance(entry, dict), "Array-shard entry must be an object")
    name = entry.get("file")
    _require(
        isinstance(name, str)
        and name == f"batch_{index:03d}.npz",
        "Array shard name differs from batch_%03d.npz",
    )
    _require(isinstance(entry.get("bytes"), int) and entry["bytes"] > 0, "Array shard byte count malformed")
    value = entry.get("sha256")
    _require(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value),
        "Array shard SHA256 malformed",
    )
    return name


def load_task(entries, arrays_dir, read, deadline=None):
    """Read one task's 121 shards and retain only gate-level summaries."""
    import numpy as np

    arrays_dir = Path(arrays_dir)
    _require(isinstance(entries, list) and entries, "Private array-shard list missing")
    p_parts, truth_parts, q32_parts, a0_parts = [], [], [], []
    strong_qlog, weak_qlog, s1_qlog = [], [], []
    scene_ids = []
    candidate_rows, candidate_scene_ids = [], []
    s1_rows, s1_meta, s1_scene_ids = [], [], []
    candidate_scene_seen, s1_scene_seen = set(), set()
    position = 0
    for index, entry in enumerate(entries):
        name = _validate_array_entry(entry, index)
        content = read(arrays_dir / name, entry["bytes"], entry["sha256"])
        with np.load(io.BytesIO(content), allow_pickle=False) as archive:
            keys = set(archive.files)
            required = {"scene_ids", "supervision_mask", "p", "qlog", "truth_mm_h"}
            if keys != required:
                raise ValueError("Saved shard keys differ from the frozen readout")
            ids = archive["scene_ids"]
            mask = archive["supervision_mask"]
            p = archive["p"]
            qlog = archive["qlog"]
            truth = archive["truth_mm_h"]
        scenes = int(ids.shape[0]) if hasattr(ids, "shape") else 0
        _require(1 <= scenes <= SCENE_BATCH_LIMIT, "Array shard scene count is outside 1..8")
        if ids.shape != (scenes,) or ids.dtype.kind != "U" or any(not str(value) for value in ids):
            raise ValueError("Saved scene_ids shape/dtype differs")
        ids = [str(value) for value in ids]
        if any(not value.startswith("2024-") for value in ids):
            raise ValueError("Only the 2024 Development population is admitted")
        if scene_ids and ids[0] <= scene_ids[-1]:
            raise ValueError("Saved scene order is not strictly increasing")
        if len(set(ids)) != scenes:
            raise ValueError("Saved scene order contains duplicates")
        if mask.shape != (scenes, GRID[0], GRID[1]) or mask.dtype != np.bool_:
            raise ValueError("Saved supervision mask shape/dtype differs")
        if not np.array_equal(
            mask.sum(axis=(1, 2)), np.full(scenes, SUPERVISION_PIXELS_PER_SCENE)
        ):
            raise ValueError("Saved supervision mask population differs")
        n = scenes * SUPERVISION_PIXELS_PER_SCENE
        if p.shape != (n,) or p.dtype != np.float32 or not np.isfinite(p).all() or np.any((p < 0) | (p > 1)):
            raise ValueError("Saved FP32 probability differs")
        if truth.shape != (n,) or truth.dtype != np.float32 or not np.isfinite(truth).all() or (truth < 0).any():
            raise ValueError("Saved FP32 truth differs")
        if (
            qlog.shape != (n, NODES)
            or qlog.dtype != np.float64
            or not np.isfinite(qlog).all()
            or not np.all(np.diff(qlog, axis=1) > 0)
        ):
            raise ValueError("Saved FP64 log-quantiles differ")
        physical = np.expm1(qlog)
        q32 = physical[:, -1]
        a0 = np.float32(p.astype(np.float64) * physical.mean(axis=1))
        if not np.isfinite(a0).all():
            raise ValueError("A0 point readout is nonfinite")
        candidate = p.astype(np.float64) * q32 > CANDIDATE_THRESHOLD
        s1 = candidate & (a0.astype(np.float64) >= A0_THRESHOLD)
        strong = truth > THRESHOLD
        weak = (truth > RAIN_THRESHOLD) & (truth <= WEAK_UPPER)
        p_parts.append(p)
        truth_parts.append(truth)
        q32_parts.append(q32)
        a0_parts.append(a0)
        if strong.any():
            strong_qlog.append(qlog[strong])
        if weak.any():
            weak_qlog.append(qlog[weak])
        if s1.any():
            s1_qlog.append(qlog[s1])
        scene_start = position
        scene_ids.extend(ids)
        for scene_index in range(scenes):
            scene = ids[scene_index]
            segment = slice(
                scene_index * SUPERVISION_PIXELS_PER_SCENE,
                (scene_index + 1) * SUPERVISION_PIXELS_PER_SCENE,
            )
            for row in np.flatnonzero(candidate[segment]):
                row = int(row)
                global_row = (scene_start + scene_index) * SUPERVISION_PIXELS_PER_SCENE + row
                candidate_rows.append(global_row)
                if scene not in candidate_scene_seen:
                    candidate_scene_seen.add(scene)
                    candidate_scene_ids.append(scene)
            local = np.flatnonzero(s1[segment])
            if len(local):
                ys, xs = np.nonzero(mask[scene_index])
                for row in local:
                    row = int(row)
                    global_row = (scene_start + scene_index) * SUPERVISION_PIXELS_PER_SCENE + row
                    s1_rows.append(global_row)
                    s1_meta.append(
                        {
                            "scene_index": scene_start + scene_index,
                            "row": row,
                            "y": int(ys[row]),
                            "x": int(xs[row]),
                            "global_row": global_row,
                        }
                    )
                if scene not in s1_scene_seen:
                    s1_scene_seen.add(scene)
                    s1_scene_ids.append(scene)
        position += scenes
        if deadline is not None:
            deadline.check()
    _require(p_parts, "No saved Development shards were supplied")
    p = np.concatenate(p_parts)
    truth = np.concatenate(truth_parts)
    q32 = np.concatenate(q32_parts)
    a0 = np.concatenate(a0_parts)
    candidate_rows_array = np.asarray(candidate_rows, dtype=np.int64)
    s1_rows_array = np.asarray(s1_rows, dtype=np.int64)
    population = {
        "scene_ids": scene_ids,
        "p": p,
        "truth": truth,
        "q32": q32,
        "a0": a0,
        "strong": truth > THRESHOLD,
        "weak": (truth > RAIN_THRESHOLD) & (truth <= WEAK_UPPER),
        "rain": truth > RAIN_THRESHOLD,
        "candidate_rows": candidate_rows_array,
        "candidate_scene_ids": candidate_scene_ids,
        "s1_rows": s1_rows_array,
        "s1_meta": s1_meta,
        "s1_scene_ids": s1_scene_ids,
        "s1_index": {int(row): index for index, row in enumerate(s1_rows_array)},
        "strong_qlog": np.concatenate(strong_qlog) if strong_qlog else np.empty((0, NODES)),
        "weak_qlog": np.concatenate(weak_qlog) if weak_qlog else np.empty((0, NODES)),
        "s1_qlog": np.concatenate(s1_qlog) if s1_qlog else np.empty((0, NODES)),
    }
    population["candidate_strong"] = population["strong"][candidate_rows_array]
    _require(position == len(scene_ids), "Saved shard scene accounting differs")
    return population


def baseline_counts(population):
    truth = population["truth"]
    return {
        "scenes": len(population["scene_ids"]),
        "n_valid": int(len(truth)),
        "n_rain": int((truth > RAIN_THRESHOLD).sum()),
        "n_strong": int((truth > THRESHOLD).sum()),
        "n_weak": int(population["weak"].sum()),
        "candidate_rows": int(len(population["candidate_rows"])),
        "candidate_scenes": len(population["candidate_scene_ids"]),
        "s1_rows": int(len(population["s1_rows"])),
        "s1_scenes": len(population["s1_scene_ids"]),
    }


def baseline_metrics(population):
    return _helpers().metrics_from_population(population)


def _compare_expected(actual, expected, label):
    for key, value in expected.items():
        _require(key in actual, f"{label}.{key} is missing")
        if isinstance(value, dict):
            _compare_expected(actual[key], value, f"{label}.{key}")
        elif isinstance(value, int) and not isinstance(value, bool):
            _require(int(actual[key]) == int(value), f"{label}.{key} differs from the frozen preparation")
        else:
            delta = abs(float(actual[key]) - float(value))
            _require(
                delta <= FROZEN_METRIC_TOLERANCE,
                f"{label}.{key} differs from the frozen preparation by {delta:.3e}",
            )


def selected_rows(population, split_min, threshold=SPLIT_THRESHOLD):
    """Return the S1 rows whose scene split_min reaches the frozen threshold."""
    rows = []
    for row in population["s1_rows"]:
        row = int(row)
        if row not in split_min:
            raise ValueError("S1 row lacks split_min")
        value = float(split_min[row])
        if value >= float(threshold):
            rows.append(row)
    return rows


def apply_action(nodes, probability):
    """Apply the frozen blend-to-top action, returning (record, reason)."""
    outcome = _helpers().blend_to_top(nodes, probability)
    if outcome[0] is None:
        return None, outcome[1]
    blended, fraction, new_a = outcome
    return {
        "nodes": blended,
        "fraction": float(fraction),
        "new_a": float(new_a),
    }, None


def _selected_record(population, row, split_min, action, reason):
    index = population["s1_index"][row]
    meta = population["s1_meta"][index]
    qlog = population["s1_qlog"][index]
    truth = float(population["truth"][row])
    record = {
        "scene": population["scene_ids"][meta["scene_index"]],
        "row": int(meta["row"]),
        "y": int(meta["y"]),
        "x": int(meta["x"]),
        "truth": truth,
        "p": float(population["p"][row]),
        "q32": float(population["q32"][row]),
        "a0": float(population["a0"][row]),
        "split_min": None if not math.isfinite(float(split_min[row])) else float(split_min[row]),
        "blend_fraction": None if action is None else float(action["fraction"]),
        "new_A": None if action is None else float(action["new_a"]),
        "activated": action is not None,
        "strong": bool(population["strong"][row]),
        "weak": bool(population["weak"][row]),
        "infeasible_reason": reason,
    }
    if action is None:
        record["normalized_pinball_change"] = None
    else:
        import numpy as np

        helpers = _helpers()
        nodes = np.expm1(qlog)
        old = float(
            helpers.physical_pinball_nodes_over20(np.asarray([truth]), nodes[None, :])[0]
        )
        new = float(
            helpers.physical_pinball_nodes_over20(
                np.asarray([truth]), np.asarray(action["nodes"], dtype=np.float64)[None, :]
            )[0]
        )
        record["normalized_pinball_change"] = new - old
    return record


def _gate(gate, name, baseline, candidate, comparator, passed, **extra):
    record = {
        "gate": int(gate),
        "name": name,
        "baseline": baseline,
        "candidate": candidate,
        "comparator": comparator,
        "passed": bool(passed),
    }
    record.update(extra)
    return record


def evaluate_task(task, population, split_min, *, baseline=None, expected=None, satellite=None):
    """Compute the nine per-task gates against that task's own array baseline."""
    import numpy as np

    helpers = _helpers()
    if baseline is None:
        counts = baseline_counts(population)
        metrics = baseline_metrics(population)
        if expected is not None:
            _compare_expected(
                counts,
                {key: value for key, value in expected["counts"].items() if not key.startswith("satellite_")},
                f"{task}.counts",
            )
            _compare_expected(metrics, expected["metrics"], f"{task}.baseline")
    else:
        counts, metrics = baseline
    selection = selected_rows(population, split_min)
    activated = {}
    infeasible = {}
    for row in selection:
        index = population["s1_index"][row]
        nodes = np.expm1(population["s1_qlog"][index])
        action, reason = apply_action(nodes, float(population["p"][row]))
        if action is None:
            infeasible[row] = reason
        else:
            activated[row] = action

    a0 = population["a0"]
    truth = population["truth"]
    p = population["p"]
    q32 = population["q32"]
    strong = population["strong"]
    weak = population["weak"]
    new_a_all = a0.copy()
    for row, action in activated.items():
        new_a_all[row] = np.float32(action["new_a"])

    strong_base = helpers.physical_pinball_over20(truth[strong], population["strong_qlog"])
    strong_positions = {int(row): index for index, row in enumerate(np.flatnonzero(strong))}
    for row, action in activated.items():
        if strong[row]:
            strong_base[strong_positions[row]] = float(
                helpers.physical_pinball_nodes_over20(
                    np.asarray([float(truth[row])]),
                    np.asarray(action["nodes"], dtype=np.float64)[None, :],
                )[0]
            )
    gate1_candidate = float(strong_base.mean())
    gate1_baseline = float(metrics["strong_physical_pinball_over20"])
    gate1_passed = gate1_candidate < gate1_baseline

    new_tp = int(((new_a_all > THRESHOLD) & strong).sum())
    new_fp = int(((new_a_all > THRESHOLD) & ~strong).sum())
    gate2_passed = new_tp >= 1 and new_tp >= int(metrics["point_a_tp"])
    gate3_passed = new_fp <= int(metrics["point_a_fp"])

    new_q32_tp = int(((q32 > 20.0) & strong).sum())
    new_q32_fp = int(((q32 > 20.0) & ~strong).sum())
    gate4_passed = new_q32_tp == int(metrics["q32_support_tp"])
    gate5_passed = new_q32_fp == int(metrics["q32_support_fp"])

    weak_base = helpers.weak_log_pinball(truth[weak], population["weak_qlog"])
    weak_positions = {int(row): index for index, row in enumerate(np.flatnonzero(weak))}
    for row, action in activated.items():
        if weak[row]:
            weak_base[weak_positions[row]] = float(
                helpers.weak_log_pinball(
                    np.asarray([float(truth[row])]),
                    np.log1p(np.asarray(action["nodes"], dtype=np.float64))[None, :],
                )[0]
            )
    weak_candidate = float(weak_base.mean())
    gate6_passed = abs(weak_candidate - float(metrics["weak_log_pinball"])) <= FROZEN_METRIC_TOLERANCE

    by_construction = {
        "equal": True,
        "status": "BY_CONSTRUCTION_EQUAL",
        "reason": (
            "The action leaves p and q32 fixed, so Brier, AP and AUROC are "
            "unchanged without recomputation."
        ),
    }
    weak_selected = sum(1 for row in selection if weak[row])
    nonstrong_selected = sum(1 for row in selection if not strong[row])
    strong_selected = sum(1 for row in selection if strong[row])
    gates = [
        _gate(1, "strong_physical_pinball_over20", gate1_baseline, gate1_candidate, "lt", gate1_passed),
        _gate(
            2,
            "point_a_detection_restored",
            {"tp": int(metrics["point_a_tp"]), "fp": int(metrics["point_a_fp"])},
            {"tp": new_tp, "fp": new_fp},
            "ge",
            gate2_passed,
            requirement="candidate_tp>=1 and >= baseline",
        ),
        _gate(
            3,
            "point_a_false_positive_removed",
            {"tp": int(metrics["point_a_tp"]), "fp": int(metrics["point_a_fp"])},
            {"tp": new_tp, "fp": new_fp},
            "le",
            gate3_passed,
            requirement="candidate_fp<=baseline",
        ),
        _gate(4, "q32_support_true_positive_unchanged", int(metrics["q32_support_tp"]), new_q32_tp, "eq", gate4_passed),
        _gate(5, "q32_support_false_positive_unchanged", int(metrics["q32_support_fp"]), new_q32_fp, "eq", gate5_passed),
        _gate(6, "weak_log_pinball_unchanged", float(metrics["weak_log_pinball"]), weak_candidate, "eq", gate6_passed, tolerance=FROZEN_METRIC_TOLERANCE),
        _gate(7, "occurrence_brier_unchanged", metrics["occurrence_brier"], metrics["occurrence_brier"], "eq", True, **by_construction),
        _gate(8, "occurrence_ap_unchanged", metrics["occurrence_ap"], metrics["occurrence_ap"], "eq", True, **by_construction),
        _gate(9, "occurrence_auroc_unchanged", metrics["occurrence_auroc"], metrics["occurrence_auroc"], "eq", True, **by_construction),
    ]
    failing = [gate["name"] for gate in gates if not gate["passed"]]
    if weak_selected:
        failing.append("weak_rows_selected")
    if nonstrong_selected:
        failing.append("nonstrong_rows_selected")
    passed = bool(
        gate1_passed
        and gate2_passed
        and gate3_passed
        and gate4_passed
        and gate5_passed
        and gate6_passed
        and not weak_selected
        and not nonstrong_selected
    )

    ordered = sorted(selection)
    rows = [
        _selected_record(
            population,
            row,
            split_min,
            activated.get(row),
            infeasible.get(row),
        )
        for row in ordered[:MAX_SELECTED_ROWS]
    ]
    infeasible_rows = [
        _selected_record(
            population,
            row,
            split_min,
            None,
            infeasible[row],
        )
        for row in ordered[:MAX_INFEASIBLE_ROWS]
        if row in infeasible
    ]
    counts = dict(counts)
    if satellite is not None:
        counts["satellite_scenes"] = int(satellite["scenes"])
        counts["satellite_files"] = int(satellite["files"])
        counts["satellite_bytes"] = int(satellite["bytes"])
    candidate_metrics = {
        "strong_physical_pinball_over20": gate1_candidate,
        "q32_support_tp": new_q32_tp,
        "q32_support_fp": new_q32_fp,
        "point_a_tp": new_tp,
        "point_a_fp": new_fp,
        "weak_log_pinball": weak_candidate,
        "occurrence_brier": metrics["occurrence_brier"],
        "occurrence_ap": metrics["occurrence_ap"],
        "occurrence_auroc": metrics["occurrence_auroc"],
    }
    result = {
        "task": task,
        "arm": task.split("_")[0],
        "seed": int(task.split("_s")[1]),
        "status": "COMPLETE",
        "decision": "PASS" if passed else "FAIL",
        "failing_gates": failing,
        "gates": gates,
        "baseline_metrics": dict(metrics),
        "candidate_metrics": candidate_metrics,
        "counts": counts,
        "selection": {
            "rule": "S1 AND split_min >= 2.3612",
            "split_threshold": SPLIT_THRESHOLD,
            "candidate_rows": int(len(population["candidate_rows"])),
            "s1_rows": int(len(population["s1_rows"])),
            "selected_rows": int(len(selection)),
            "feasible_rows": int(len(activated)),
            "infeasible_rows": int(len(infeasible)),
            "strong_rows_selected": int(strong_selected),
            "weak_rows_selected": int(weak_selected),
            "nonstrong_rows_selected": int(nonstrong_selected),
        },
        "selected_rows": rows,
        "selected_rows_total": int(len(selection)),
        "selected_rows_omitted": int(max(0, len(selection) - len(rows))),
        "infeasible_rows": infeasible_rows,
        "satellite": None if satellite is None else dict(satellite),
        "automatic_retry": False,
        "final_2025_access": False,
    }
    return _freeze(result)


# ---------------------------------------------------------------------------
# Satellite planning and scene split_min
# ---------------------------------------------------------------------------


def validate_satellite_manifest(manifest):
    _require(isinstance(manifest, dict), "Satellite manifest must be an object")
    _require(manifest.get("manifest_sha256") == SATELLITE_MANIFEST_INTERNAL_SHA256, "Satellite manifest identity differs")
    _require(int(manifest.get("year", 0)) == 2024, "Satellite manifest year differs")
    _require(manifest.get("role") == "Development", "Satellite manifest role differs")
    records = manifest.get("scene_records")
    files = manifest.get("satellite_files")
    candidates = manifest.get("population_candidate_ids")
    _require(isinstance(records, list) and len(records) == SCENES, "Satellite scene-record count differs")
    _require(isinstance(files, list) and len(files) == 5778, "Satellite file count differs")
    _require(isinstance(candidates, list) and len(candidates) == SCENES, "Satellite candidate count differs")
    nominal = {}
    for entry in files:
        _require(isinstance(entry, dict), "Satellite file entry must be an object")
        value = entry.get("nominal")
        _require(isinstance(value, str) and value, "Satellite nominal time missing")
        _require(value not in nominal, "Duplicate satellite nominal time")
        _require(isinstance(entry.get("relative_path"), str) and entry["relative_path"], "Satellite relative path missing")
        _require(isinstance(entry.get("expected_bytes"), int) and entry["expected_bytes"] > 0, "Satellite byte count malformed")
        sha_value = entry.get("expected_sha256")
        _require(
            isinstance(sha_value, str)
            and len(sha_value) == 64
            and all(character in "0123456789abcdef" for character in sha_value),
            "Satellite SHA256 malformed",
        )
        _require(value.startswith("2024-"), "Only 2024 satellite slots are admitted")
        nominal[value] = entry
    for record in records:
        _require(isinstance(record, dict), "Satellite scene record must be an object")
        sample = record.get("sample_id")
        _require(isinstance(sample, str) and sample.startswith("2024-"), "Satellite scene id is not 2024")
        _require(sample not in ("", None), "Satellite scene id missing")
        for slot in range(SLOTS):
            value = record.get(f"slot_{slot}_nominal")
            _require(isinstance(value, str) and value in nominal, "Satellite scene slot is missing from the file index")
    return nominal


def build_satellite_plan(task, population, manifest, satellite_root):
    """Plan the six causal satellite files for every S1 scene of one task."""
    _require(task in TASKS, "Unknown candidate-reproduction task")
    nominal = validate_satellite_manifest(manifest)
    records = {record["sample_id"]: record for record in manifest["scene_records"]}
    root = Path(satellite_root)
    plan = []
    for scene in population["s1_scene_ids"]:
        _require(scene in records, "S1 scene is missing from the satellite manifest")
        record = records[scene]
        for slot in range(SLOTS):
            value = record[f"slot_{slot}_nominal"]
            entry = nominal[value]
            relative = entry["relative_path"].replace("\\", "/")
            plan.append(
                {
                    "scene": scene,
                    "slot": slot,
                    "nominal": value,
                    "relative_path": relative,
                    "path": str(root / relative),
                    "bytes": int(entry["expected_bytes"]),
                    "sha256": entry["expected_sha256"],
                }
            )
    _require(len(plan) == len(population["s1_scene_ids"]) * SLOTS, "Satellite plan is incomplete")
    return plan


def scene_split_min(plan, read, indices, deadline=None):
    """Compute one SP04 100x100 split_min map per S1 scene."""
    import numpy as np

    helpers = _helpers()
    grouped = {}
    for entry in plan:
        grouped.setdefault(entry["scene"], {})[entry["slot"]] = entry
    result = {}
    for scene, slots in grouped.items():
        if set(slots) != set(range(SLOTS)):
            raise ValueError("A candidate scene lacks one of the six causal satellite slots")
        splits = []
        for slot in range(SLOTS):
            entry = slots[slot]
            content = read(entry["path"], entry["bytes"], entry["sha256"])
            if deadline is not None:
                deadline.check()
            value08, valid08 = helpers.read_band(content, "08")
            value13, valid13 = helpers.read_band(content, "13")
            mean08 = helpers.sp04_area_mean(value08, valid08, indices)
            mean13 = helpers.sp04_area_mean(value13, valid13, indices)
            splits.append(mean08 - mean13)
        # np.min propagates NaN, so an undefined cell keeps the scene S2-fail.
        result[scene] = np.min(np.stack(splits), axis=0)
    return result


def _split_min_by_row(population, scene_maps):
    split_min = {}
    for meta in population["s1_meta"]:
        scene = population["scene_ids"][meta["scene_index"]]
        if scene not in scene_maps:
            raise ValueError("S1 scene lacks a split_min map")
        split_min[int(meta["global_row"])] = float(
            scene_maps[scene][meta["y"], meta["x"]]
        )
    return split_min


# ---------------------------------------------------------------------------
# Q2 / Q3 aggregation
# ---------------------------------------------------------------------------


def q2_summary(results, seed2029=None):
    rows = {}
    passing, failing = [], []
    for task in REAL_TASKS:
        result = results[task]
        record = {
            "task": task,
            "arm": result["arm"],
            "seed": result["seed"],
            "decision": result["decision"],
            "passed": result["decision"] == "PASS",
            "failing_gates": list(result["failing_gates"]),
            "selection": dict(result["selection"]),
            "baseline_metrics": dict(result["baseline_metrics"]),
            "candidate_metrics": dict(result["candidate_metrics"]),
        }
        rows[task] = record
        (passing if record["passed"] else failing).append(task)
    if len(passing) == len(REAL_TASKS):
        decision = "CANDIDATE_REPRODUCED_ACROSS_SEEDS"
    elif passing:
        decision = "PARTIAL"
    else:
        decision = "NOT_REPRODUCED"
    reference = dict(SEED2029_REFERENCE_BASE)
    if seed2029 is not None:
        reference.update(seed2029)
    return {
        "decision": decision,
        "real_tasks": list(REAL_TASKS),
        "passing_tasks": passing,
        "failing_tasks": failing,
        "per_task": rows,
        "seed2029_reference": reference,
        "rule": RULES["q2_rule"],
        "status": "COMPLETE",
        "automatic_retry": False,
        "final_2025_access": False,
    }


def q3_summary(results):
    rows = {}
    warnings = []
    for task in ZERO_TASKS:
        result = results[task]
        baseline = result["baseline_metrics"]
        candidate = result["candidate_metrics"]
        delta = float(candidate["strong_physical_pinball_over20"]) - float(
            baseline["strong_physical_pinball_over20"]
        )
        record = {
            "task": task,
            "decision": result["decision"],
            "selected_rows": int(result["selection"]["selected_rows"]),
            "feasible_rows": int(result["selection"]["feasible_rows"]),
            "infeasible_rows": int(result["selection"]["infeasible_rows"]),
            "strong_rows_selected": int(result["selection"]["strong_rows_selected"]),
            "weak_rows_selected": int(result["selection"]["weak_rows_selected"]),
            "nonstrong_rows_selected": int(result["selection"]["nonstrong_rows_selected"]),
            "baseline_metrics": dict(baseline),
            "candidate_metrics": dict(candidate),
            "strong_physical_pinball_over20_delta": delta,
            "point_a": {
                "baseline": {"tp": baseline["point_a_tp"], "fp": baseline["point_a_fp"]},
                "candidate": {"tp": candidate["point_a_tp"], "fp": candidate["point_a_fp"]},
            },
            "q32_support": {
                "baseline": {"tp": baseline["q32_support_tp"], "fp": baseline["q32_support_fp"]},
                "candidate": {"tp": candidate["q32_support_tp"], "fp": candidate["q32_support_fp"]},
            },
            "weak_log_pinball": {
                "baseline": baseline["weak_log_pinball"],
                "candidate": candidate["weak_log_pinball"],
            },
            "description": "Descriptive zero-control readout; not a reproduction decision.",
        }
        rows[task] = record
        if delta < 0.0 or int(candidate["point_a_tp"]) > int(baseline["point_a_tp"]):
            warnings.append(task)
    return {
        "decision": "DESCRIPTIVE_ONLY",
        "zero_tasks": list(ZERO_TASKS),
        "per_task": rows,
        "attribution_warning": bool(warnings),
        "attribution_warning_tasks": warnings,
        "warning": (
            "A ZERO control's selected rows improve like REAL; attributed physical "
            "reproduction is not established by this package."
            if warnings
            else None
        ),
        "rule": RULES["q3_rule"],
        "status": "COMPLETE",
        "automatic_retry": False,
        "final_2025_access": False,
    }


# ---------------------------------------------------------------------------
# Preparation
# ---------------------------------------------------------------------------


def _validate_parent_results(data):
    _require(isinstance(data, dict), "Parent results must be an object")
    _require(data.get("status") == "COMPLETE_STAGE4_MULTISEED_DEV_EVALUATION", "Parent results status differs")
    _require(data.get("kind") == "BOUNDED_STAGE4_MULTISEED_DEV_EVALUATION", "Parent results kind differs")
    _require(data.get("scope") == "FOUR_MODEL_COSINE9_REAL_ZERO_DEV_MOUNTAIN_EVALUATION_V1", "Parent results scope differs")
    _require(data.get("decision") == "DESCRIPTIVE_MULTISEED_REAL_ZERO_DEV_EVALUATION", "Parent results decision differs")
    _require(data.get("final_2025_access") is False, "Parent results accessed 2025")
    _require(data.get("automatic_retry") is False and data.get("replay") is False, "Parent results carry retries")
    rows = data.get("tasks")
    _require(isinstance(rows, list) and len(rows) == len(TASKS), "Parent task count differs")
    by_task = {row.get("task"): row for row in rows}
    _require(set(by_task) == set(TASKS), "Parent task names differ")
    for task in TASKS:
        row = by_task[task]
        _require(row.get("status") == "COMPLETE", f"Parent task {task} is incomplete")
        checkpoint = row.get("checkpoint", {})
        _require(checkpoint.get("sha256") == CHECKPOINTS[task]["sha256"], f"Parent checkpoint SHA differs for {task}")
        _require(int(checkpoint.get("bytes", -1)) == CHECKPOINTS[task]["bytes"], f"Parent checkpoint bytes differ for {task}")
        _require(int(row.get("arrays_batch_count", -1)) == ARRAY_SHARDS_PER_TASK, f"Parent array count differs for {task}")
        _require(int(row.get("arrays_bytes", -1)) == ARRAY_BYTES_PER_TASK, f"Parent array bytes differ for {task}")
        population = row.get("population", {})
        _require(int(population.get("scenes", -1)) == SCENES, f"Parent scene count differs for {task}")
        _require(int(population.get("n_valid", -1)) == SUPERVISED_PIXELS, f"Parent pixel count differs for {task}")
        _require(int(population.get("n_rain", -1)) == 407_820, f"Parent rain count differs for {task}")
        _require(int(population.get("n_strong", -1)) == 717, f"Parent strong count differs for {task}")
    return by_task


def _validate_parent_completion(data):
    _require(isinstance(data, dict), "Parent completion must be an object")
    _require(data.get("status") == "COMPLETE_STAGE4_MULTISEED_DEV_EVALUATION", "Parent completion status differs")
    _require(data.get("kind") == "BOUNDED_STAGE4_MULTISEED_DEV_EVALUATION", "Parent completion kind differs")
    _require(data.get("final_2025_access") is False, "Parent completion accessed 2025")
    rows = data.get("tasks")
    _require(isinstance(rows, list) and len(rows) == len(TASKS), "Parent completion task count differs")
    by_task = {row.get("task"): row for row in rows}
    _require(set(by_task) == set(TASKS), "Parent completion task names differ")
    for task in TASKS:
        row = by_task[task]
        _require(int(row.get("arrays_batch_count", -1)) == ARRAY_SHARDS_PER_TASK, f"Parent completion array count differs for {task}")
        _require(int(row.get("arrays_bytes", -1)) == ARRAY_BYTES_PER_TASK, f"Parent completion array bytes differ for {task}")
        values = row.get("arrays_sha256_list")
        _require(isinstance(values, list) and len(values) == ARRAY_SHARDS_PER_TASK, f"Parent arrays_sha256_list differs for {task}")
        for value in values:
            _require(
                isinstance(value, str)
                and len(value) == 64
                and all(character in "0123456789abcdef" for character in value),
                f"Parent array digest is malformed for {task}",
            )
    return by_task


def _validate_terrain_results(data):
    _require(isinstance(data, dict), "Terrain results must be an object")
    _require(str(data.get("status", "")).startswith("COMPLETE"), "Terrain results status differs")
    _require(data.get("automatic_retry") is False and data.get("replay") is False, "Terrain results carry retries")
    rows = data.get("tasks")
    _require(isinstance(rows, list) and len(rows) == len(TASKS), "Terrain results task count differs")
    by_task = {row.get("task", task_name(row.get("arm", ""), row.get("seed", 0))): row for row in rows}
    _require(set(by_task) == set(TASKS), "Terrain results task names differ")
    updates = 0
    source_bytes = 0
    for task in TASKS:
        row = by_task[task]
        updates += int(row.get("updates", 0))
        source_bytes += int(row.get("source_bytes", 0))
        sha_value = row.get("last_epoch_09_checkpoint_sha256", row.get("checkpoint_sha256"))
        bytes_value = row.get("last_epoch_09_checkpoint_bytes", row.get("checkpoint_bytes"))
        _require(sha_value == CHECKPOINTS[task]["sha256"], f"Terrain checkpoint SHA differs for {task}")
        _require(int(bytes_value or -1) == CHECKPOINTS[task]["bytes"], f"Terrain checkpoint bytes differ for {task}")
    _require(updates == 17_280, "Terrain update total differs")
    _require(source_bytes == 1_910_287_815_360, "Terrain source-byte total differs")
    return by_task


def _validate_seed2029_results(data):
    _require(isinstance(data, dict), "Seed2029 results must be an object")
    _require(data.get("status") == "COMPLETE_STAGE45_DEV_ACCEPTANCE", "Seed2029 acceptance status differs")
    _require(data.get("decision") == "PASS", "Seed2029 acceptance is not PASS")
    _require(data.get("final_2025_access") is False, "Seed2029 acceptance accessed 2025")
    return data


def _array_entries(task, task_dir, completion_row, expected_bytes):
    task_dir = Path(task_dir)
    _require(task_dir.is_dir(), f"Array directory is missing for {task}")
    files = sorted(task_dir.glob("batch_*.npz"))
    _require(len(files) == ARRAY_SHARDS_PER_TASK, f"Array shard count differs for {task}")
    digests = completion_row["arrays_sha256_list"]
    entries = []
    total = 0
    for index in range(ARRAY_SHARDS_PER_TASK):
        name = f"batch_{index:03d}.npz"
        path = task_dir / name
        _require(path.is_file(), f"Array shard is missing: {task}/{name}")
        size = path.stat().st_size
        _require(size > 0, f"Array shard is empty: {task}/{name}")
        entries.append({"file": name, "bytes": int(size), "sha256": digests[index]})
        total += size
    _require(total == int(expected_bytes), f"Array shard byte total differs for {task}")
    return entries


def _metadata_manifest(parent_results, terrain_path, satellite_manifest):
    return [
        {
            "label": "parent_results",
            "name": "STAGE45_STEP4_EVALUATION_RESULTS_V1.json",
            "path": str(parent_results),
            "bytes": PARENT_RESULTS_BYTES,
            "sha256": PARENT_RESULTS_SHA256,
        },
        {
            "label": "terrain_results",
            "name": "STAGE45_STEP4_MULTISEED_TERRAIN_RESULTS_V1.json",
            "path": str(terrain_path),
            "bytes": TERRAIN_RESULTS_BYTES,
            "sha256": sha(terrain_path),
        },
        {
            "label": "satellite_manifest",
            "name": "manifest_2024_fixed_f006.json",
            "path": str(satellite_manifest),
            "bytes": SATELLITE_MANIFEST_BYTES,
            "sha256": sha(satellite_manifest),
        },
    ]


def _public_task_specs():
    rows = {}
    for task in TASKS:
        arm, seed = task.split("_s")
        rows[task] = {
            "task": task,
            "arm": arm,
            "seed": int(seed),
            "model": MODEL,
            "role": "Development",
            "year": 2024,
            "dynamic_control": CONTROLS[arm],
            "checkpoint_sha256": CHECKPOINTS[task]["sha256"],
            "checkpoint_bytes": CHECKPOINTS[task]["bytes"],
            "checkpoint_loads": 0,
            "arrays_files": ARRAY_SHARDS_PER_TASK,
            "arrays_bytes": ARRAY_BYTES_PER_TASK,
            "satellite_files": SATELLITE_FILES[task]["files"],
            "satellite_bytes": SATELLITE_FILES[task]["bytes"],
            "s1_rows": SATELLITE_FILES[task]["s1_rows"],
            "s1_scenes": SATELLITE_FILES[task]["s1_scenes"],
        }
    return rows


def prepare(
    root,
    parent_results_path,
    arrays_root,
    output_root,
    proposal_path,
    private_path,
    *,
    head=None,
    runtime_python=None,
    service_dir=None,
):
    root = Path(root).resolve()
    parent_results = _absolute(parent_results_path, "--parent-results")
    arrays_root = _absolute(arrays_root, "--arrays-root")
    output_root = _absolute(output_root, "--output-root")
    proposal_path = _absolute(proposal_path, "--proposal")
    private_path = _absolute(private_path, "--private-preparation")
    namespace = proposal_path.parent
    require_fresh_namespace(namespace, root)
    _require(proposal_path.name == "PROPOSAL.json", "The proposal must be PROPOSAL.json")
    _require(private_path.name == "PRIVATE_PREPARATION.json", "The private preparation must be PRIVATE_PREPARATION.json")
    _require(private_path.parent == namespace, "The proposal and private preparation must share a namespace")
    require_fresh_output(output_root)
    _require(arrays_root.is_dir(), "The package-A arrays root is missing")
    service_dir = _absolute(service_dir or (namespace / "service"), "--service-dir")
    runtime_python = _absolute(runtime_python or sys.executable, "--runtime-python")
    _require(runtime_python.is_file(), "The runtime interpreter is missing")
    head = _git_head(root) if head is None else head

    parent_identity = validate_artifact(
        parent_results, PARENT_RESULTS_BYTES, PARENT_RESULTS_SHA256, "Parent results"
    )
    parent_data = read(parent_results)
    parent_tasks = _validate_parent_results(parent_data)

    completion_path = arrays_root.parent / "completion.json"
    completion_identity = validate_artifact(
        completion_path, PARENT_COMPLETION_BYTES, PARENT_COMPLETION_SHA256, "Parent completion"
    )
    completion = read(completion_path)
    completion_tasks = _validate_parent_completion(completion)

    terrain_path = root / TERRAIN_RESULTS_RELATIVE
    terrain_identity = artifact_identity(terrain_path)
    _require(
        terrain_identity["bytes"] == TERRAIN_RESULTS_BYTES,
        "Terrain results byte count differs",
    )
    _validate_terrain_results(read(terrain_path))

    seed2029_path = root / SEED2029_RESULTS_RELATIVE
    _require(seed2029_path.is_file(), "The recorded seed2029 acceptance is missing")
    seed2029_identity = artifact_identity(seed2029_path)
    _validate_seed2029_results(read(seed2029_path))

    _require(SATELLITE_MANIFEST.is_file(), "The frozen satellite manifest is missing")
    manifest_identity = validate_artifact(
        SATELLITE_MANIFEST,
        SATELLITE_MANIFEST_BYTES,
        sha(SATELLITE_MANIFEST),
        "Satellite manifest",
    )
    manifest = read(SATELLITE_MANIFEST)
    validate_satellite_manifest(manifest)

    tasks = {}
    metadata_files = _metadata_manifest(
        parent_results, terrain_path, SATELLITE_MANIFEST
    )
    metadata_bytes = sum(entry["bytes"] for entry in metadata_files)
    _require(
        metadata_bytes == BUDGET["metadata_reference_bytes"],
        "Metadata reference bytes differ from the frozen budget",
    )
    arrays_opens = 0
    arrays_bytes = 0
    satellite_opens = 0
    satellite_bytes = 0
    for task in TASKS:
        arrays = _array_entries(
            task,
            arrays_root / task,
            completion_tasks[task],
            ARRAY_BYTES_PER_TASK,
        )
        tasks[task] = {
            "task": task,
            "arm": task.split("_s")[0],
            "seed": int(task.split("_s")[1]),
            "checkpoint_sha256": CHECKPOINTS[task]["sha256"],
            "checkpoint_bytes": CHECKPOINTS[task]["bytes"],
            "arrays": arrays,
            "arrays_bytes": sum(entry["bytes"] for entry in arrays),
            "satellite_bytes": SATELLITE_FILES[task]["bytes"],
            "satellite_files": SATELLITE_FILES[task]["files"],
            "s1_rows": SATELLITE_FILES[task]["s1_rows"],
            "s1_scenes": SATELLITE_FILES[task]["s1_scenes"],
        }
        arrays_opens += len(arrays)
        arrays_bytes += tasks[task]["arrays_bytes"]
        satellite_opens += SATELLITE_FILES[task]["files"]
        satellite_bytes += SATELLITE_FILES[task]["bytes"]
    _require(arrays_opens == BUDGET["arrays_open_instances"], "Array open total differs from the frozen budget")
    _require(arrays_bytes == BUDGET["arrays_reference_bytes"], "Array byte total differs from the frozen budget")
    _require(satellite_opens == BUDGET["satellite_open_instances"], "Satellite open total differs from the frozen budget")
    _require(satellite_bytes == BUDGET["satellite_reference_bytes"], "Satellite byte total differs from the frozen budget")
    _require(
        arrays_opens + satellite_opens == BUDGET["scientific_file_opens"],
        "Scientific open total differs from the frozen budget",
    )
    _require(
        arrays_bytes + satellite_bytes == BUDGET["scientific_source_bytes"],
        "Scientific byte total differs from the frozen budget",
    )

    source_scope = {
        "per_task": {
            task: {
                "arrays_opens": len(tasks[task]["arrays"]),
                "arrays_bytes": tasks[task]["arrays_bytes"],
                "satellite_files": tasks[task]["satellite_files"],
                "satellite_bytes": tasks[task]["satellite_bytes"],
                "s1_rows": tasks[task]["s1_rows"],
                "s1_scenes": tasks[task]["s1_scenes"],
            }
            for task in TASKS
        },
        "totals": {
            "arrays_open_instances": arrays_opens,
            "arrays_reference_bytes": arrays_bytes,
            "satellite_open_instances": satellite_opens,
            "satellite_reference_bytes": satellite_bytes,
            "scientific_file_opens": BUDGET["scientific_file_opens"],
            "scientific_source_bytes": BUDGET["scientific_source_bytes"],
            "metadata_open_instances": BUDGET["metadata_open_instances"],
            "metadata_reference_bytes": BUDGET["metadata_reference_bytes"],
            "total_scientific_file_opens": BUDGET["total_scientific_file_opens"],
            "total_scientific_source_bytes": BUDGET["total_scientific_source_bytes"],
        },
    }
    seed2029_reference = {
        "task": "B7_s2029",
        "decision": "PASS",
        "name": seed2029_path.name,
        "bytes": seed2029_identity["bytes"],
        "sha256": seed2029_identity["sha256"],
        "note": SEED2029_REFERENCE_BASE["note"],
    }
    private = {
        "kind": KIND,
        "scope": SCOPE,
        "code_root": str(root),
        "output_root": str(output_root),
        "arrays_root": str(arrays_root),
        "service_dir": str(service_dir),
        "runtime_python": str(runtime_python),
        "parent_results": str(parent_results),
        "parent_completion": str(completion_path),
        "terrain_results": str(terrain_path),
        "seed2029_results": str(seed2029_path),
        "satellite_manifest": str(SATELLITE_MANIFEST),
        "satellite_root": str(SATELLITE_ROOT),
        "metadata_files": metadata_files,
        "tasks": tasks,
        "expected": EXPECTED,
        "seed2029_reference": seed2029_reference,
        "proposal_sha256": None,
    }
    proposal = {
        "kind": KIND,
        "scope": SCOPE,
        "decision": DECISION,
        "status": "READY_WAITING_EXACT_RESEARCHER_APPROVAL",
        "authorized": False,
        "authorization_scope": SCOPE,
        "final_2025_access": FINAL_2025_ACCESS,
        "final_2025_status": "SEALED_NOT_ACCESSED",
        "scientific_status": "NOT_VERIFIED",
        "tasks": list(TASKS),
        "models": list(_public_task_specs().values()),
        "data": {
            "role": "Development",
            "year": 2024,
            "arrays_root_kind": "PACKAGE_A_RETAINED_PER_PIXEL_ARRAYS",
            "arrays_files": BUDGET["arrays_open_instances"],
            "arrays_bytes": BUDGET["arrays_reference_bytes"],
            "satellite_scope": "S1_CANDIDATE_SCENES_ONLY_SLOTS_0_5",
            "satellite_files": BUDGET["satellite_open_instances"],
            "satellite_bytes": BUDGET["satellite_reference_bytes"],
            "metadata_files": BUDGET["metadata_open_instances"],
            "metadata_bytes": BUDGET["metadata_reference_bytes"],
            "total_files": BUDGET["total_scientific_file_opens"],
            "total_bytes": BUDGET["total_scientific_source_bytes"],
        },
        "data_identity": dict(DATA_SCOPE),
        "protocol": {
            "lead": 6,
            "mode": "retrospective",
            "evaluation": "STAGE4_MULTISEED_CANDIDATE_REPRODUCTION",
            "model": MODEL,
            "arms": list(ARMS),
            "seeds": list(SEEDS),
            "endpoint": "FIXED_EPOCH_9_LAST",
            "satellite_slots": "SLOTS_0_THROUGH_5_CAUSAL",
            "bands": list(BANDS),
            "sp04_grid": list(GRID),
            "native_grid": [501, 501],
            "sp04_centers": 25,
            "checkpoint_loads": 0,
            "model_inference_passes": 0,
            "optimizer_updates": 0,
            "retries": 0,
            "replays": 0,
            "automatic_retry": False,
        },
        "scientific_choices": {
            "frozen_rules": RULES,
            "expected_baselines": EXPECTED,
            "task_specs": _public_task_specs(),
            "seed2029_reference": seed2029_reference,
            "metadata_identity": metadata_files,
            "parent_results_identity": {
                "name": parent_results.name,
                "bytes": parent_identity["bytes"],
                "sha256": parent_identity["sha256"],
            },
            "parent_completion_identity": {
                "name": completion_path.name,
                "bytes": completion_identity["bytes"],
                "sha256": completion_identity["sha256"],
            },
            "terrain_results_identity": {
                "name": terrain_path.name,
                "bytes": terrain_identity["bytes"],
                "sha256": sha(terrain_path),
            },
            "satellite_manifest_identity": {
                "name": SATELLITE_MANIFEST.name,
                "bytes": manifest_identity["bytes"],
                "sha256": sha(SATELLITE_MANIFEST),
                "manifest_sha256": SATELLITE_MANIFEST_INTERNAL_SHA256,
            },
            "sp04_manifest_sha256": SP04_MANIFEST_SHA256,
        },
        "budget": BUDGET,
        "runtime_binding": runtime_binding(runtime_python),
        "code_sha256": code_hashes(root),
        "source_scope_summary": source_scope,
        "execution_code_commit": head,
        "execution_code_commit_status": "BOUND_BY_RESEARCHER_APPROVAL",
        "private_preparation_sha256": None,
        "automatic_retry": False,
        "replay": False,
        "resources": {
            "maximum_seconds": BUDGET["maximum_seconds"],
            "minimum_free_bytes": BUDGET["minimum_free_bytes"],
            "maximum_output_bytes": BUDGET["maximum_output_bytes"],
            "checkpoint_loads": 0,
            "model_inference_passes": 0,
            "gpu_required": False,
        },
    }
    proposal["private_preparation_sha256"] = private_seal(private)
    proposal["proposal_sha256"] = proposal_seal(proposal)
    private["proposal_sha256"] = proposal["proposal_sha256"]
    return proposal, private


def validate_scope(proposal):
    _require(isinstance(proposal, dict), "Proposal must be an object")
    _require(proposal.get("kind") == KIND, "Unexpected candidate-reproduction kind")
    _require(proposal.get("scope") == SCOPE, "Candidate-reproduction scope differs")
    _require(proposal.get("decision") == DECISION, "Candidate-reproduction decision differs")
    _require(proposal.get("status") == "READY_WAITING_EXACT_RESEARCHER_APPROVAL", "Proposal is not awaiting approval")
    _require(proposal.get("authorized") is False, "Proposal must remain unauthorized")
    _require(proposal.get("authorization_scope") == SCOPE, "Proposal authorization scope differs")
    _require(proposal.get("final_2025_access") is False, "2025 must remain sealed")
    _require(proposal.get("tasks") == list(TASKS), "Proposal task list differs")
    _require(proposal.get("budget") == BUDGET, "Proposal budget differs from the frozen caps")
    _require(proposal.get("data_identity") == DATA_SCOPE, "Proposal data identity differs")
    _require(proposal.get("protocol", {}).get("checkpoint_loads") == 0, "Checkpoint loads must be zero")
    _require(proposal.get("protocol", {}).get("model_inference_passes") == 0, "Inference must be zero")
    _require(proposal.get("protocol", {}).get("optimizer_updates") == 0, "Optimizer updates must be zero")
    _require(proposal.get("automatic_retry") is False and proposal.get("replay") is False, "Retries are not admitted")
    choices = proposal.get("scientific_choices", {})
    _require(choices.get("frozen_rules") == RULES, "Frozen rules differ")
    _require(choices.get("expected_baselines") == EXPECTED, "Expected baselines differ")
    _require(choices.get("parent_results_identity", {}).get("sha256") == PARENT_RESULTS_SHA256, "Parent results identity differs")
    _require(choices.get("parent_completion_identity", {}).get("sha256") == PARENT_COMPLETION_SHA256, "Parent completion identity differs")
    _require(choices.get("satellite_manifest_identity", {}).get("manifest_sha256") == SATELLITE_MANIFEST_INTERNAL_SHA256, "Satellite manifest identity differs")
    models = proposal.get("models")
    _require(isinstance(models, list) and len(models) == len(TASKS), "Model table differs")
    for row in models:
        task = row.get("task")
        _require(task in CHECKPOINTS, "Model table contains an unknown task")
        _require(row.get("checkpoint_sha256") == CHECKPOINTS[task]["sha256"], f"Checkpoint identity differs for {task}")
        _require(int(row.get("checkpoint_loads", -1)) == 0, f"Checkpoint loads differ for {task}")
    scope = proposal.get("source_scope_summary", {})
    _require(scope.get("totals", {}).get("scientific_file_opens") == BUDGET["scientific_file_opens"], "Source opens differ")
    _require(scope.get("totals", {}).get("scientific_source_bytes") == BUDGET["scientific_source_bytes"], "Source bytes differ")
    return True


def _verify_private(private, proposal, root):
    _require(private.get("kind") == KIND and private.get("scope") == SCOPE, "Private preparation kind differs")
    _require(private.get("proposal_sha256") == proposal.get("proposal_sha256"), "Private proposal digest differs")
    _require(private_seal(private) == proposal.get("private_preparation_sha256"), "Private preparation digest changed")
    for key in (
        "code_root",
        "output_root",
        "arrays_root",
        "service_dir",
        "runtime_python",
        "parent_results",
        "parent_completion",
        "terrain_results",
        "seed2029_results",
        "satellite_manifest",
        "satellite_root",
    ):
        _require(Path(private.get(key, "")).is_absolute(), f"Absolute private binding required for {key}")
    _require(Path(private["code_root"]).resolve() == Path(root).resolve(), "Private code root differs")
    _require(Path(private["output_root"]).exists() is False, "The output root already exists")
    _require(set(private.get("tasks", {})) == set(TASKS), "Private task table differs")
    for task in TASKS:
        row = private["tasks"][task]
        _require(int(row["arrays_bytes"]) == ARRAY_BYTES_PER_TASK, f"Private array bytes differ for {task}")
        _require(len(row["arrays"]) == ARRAY_SHARDS_PER_TASK, f"Private array count differs for {task}")
        _require(Path(private["arrays_root"]).is_dir(), "The arrays root is missing")
        for entry in row["arrays"]:
            path = Path(private["arrays_root"]) / task / entry["file"]
            _require(path.is_file(), f"Array shard is missing: {task}/{entry['file']}")
            _require(path.stat().st_size == int(entry["bytes"]), f"Array shard size differs: {task}/{entry['file']}")
    metadata = private.get("metadata_files")
    _require(isinstance(metadata, list) and len(metadata) == BUDGET["metadata_open_instances"], "Metadata manifest differs")
    total = 0
    for entry in metadata:
        path = Path(entry["path"])
        _require(path.is_file(), f"Metadata file is missing: {path.name}")
        _require(path.stat().st_size == int(entry["bytes"]), f"Metadata byte count differs: {path.name}")
        _require(sha(path) == entry["sha256"], f"Metadata digest differs: {path.name}")
        total += int(entry["bytes"])
    _require(total == BUDGET["metadata_reference_bytes"], "Metadata total differs")
    _require(Path(private["output_root"]).is_absolute(), "The output root must be absolute")
    return True


def validate_entry(proposal, private, approval, commit=None):
    validate_scope(proposal)
    _require(proposal_seal(proposal) == proposal.get("proposal_sha256"), "Proposal digest changed")
    _require(private.get("proposal_sha256") == proposal.get("proposal_sha256"), "Private proposal digest differs")
    _require(private_seal(private) == proposal.get("private_preparation_sha256"), "Private preparation digest changed")
    validate_approval(approval, proposal, private, commit)
    require_fresh_output(private["output_root"])
    _require(set(private.get("tasks", {})) == set(TASKS), "Private task table differs")
    root = Path(private["code_root"])
    _verify_private(private, proposal, root)
    return True


def checked(root, proposal, private, approval, commit):
    validate_scope(proposal)
    _require(proposal_seal(proposal) == proposal.get("proposal_sha256"), "Proposal digest changed")
    _require(private_seal(private) == proposal.get("private_preparation_sha256"), "Private preparation digest changed")
    _require(private.get("proposal_sha256") == proposal.get("proposal_sha256"), "Private proposal digest differs")
    _require(code_hashes(root) == proposal.get("code_sha256"), "Reviewed code digest differs", PermissionError)
    _require(runtime_binding(private["runtime_python"]) == proposal.get("runtime_binding"), "Runtime binding differs", PermissionError)
    head = _git_head(root)
    _require(head == commit == proposal.get("execution_code_commit"), "The approved commit is not checked out", PermissionError)
    _require(_clean_tree(root), "The approved checkout is dirty", PermissionError)
    metadata = private.get("metadata_files")
    _require(isinstance(metadata, list) and len(metadata) == BUDGET["metadata_open_instances"], "Metadata manifest differs")
    total = 0
    for entry in metadata:
        # Presence and byte count are checked here without opening the files:
        # the single metered read (with byte/SHA verification) happens in
        # load_metadata through the frozen metadata guard, so the declared
        # metadata open count stays exactly three.
        path = Path(entry["path"])
        _require(path.is_file(), f"Metadata file is missing: {entry['name']}")
        _require(path.stat().st_size == int(entry["bytes"]), f"Metadata byte count differs: {entry['name']}")
        total += int(entry["bytes"])
    _require(total == BUDGET["metadata_reference_bytes"], "Metadata total differs")
    _require(Path(private["arrays_root"]).is_dir(), "The arrays root is missing")
    for task in TASKS:
        row = private["tasks"][task]
        names = sorted(path.name for path in (Path(private["arrays_root"]) / task).glob("batch_*.npz"))
        _require(names == [f"batch_{index:03d}.npz" for index in range(ARRAY_SHARDS_PER_TASK)], f"Array shard names differ for {task}")
        for entry in row["arrays"]:
            path = Path(private["arrays_root"]) / task / entry["file"]
            _require(path.is_file(), f"Array shard is missing: {task}/{entry['file']}")
            _require(path.stat().st_size == int(entry["bytes"]), f"Array shard size differs: {task}/{entry['file']}")
    _require(Path(private["satellite_manifest"]).is_file(), "The satellite manifest is missing")
    require_fresh_output(private["output_root"])
    validate_approval(approval, proposal, private, commit)
    return head


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


def load_metadata(private, guard):
    entries = {entry["label"]: entry for entry in private["metadata_files"]}
    _require(set(entries) == {"parent_results", "terrain_results", "satellite_manifest"}, "Metadata labels differ")
    loaded = {}
    for label, entry in entries.items():
        content = guard(entry["path"], entry["bytes"], entry["sha256"])
        loaded[label] = json.loads(content.decode("utf-8"))
    parent_tasks = _validate_parent_results(loaded["parent_results"])
    _validate_terrain_results(loaded["terrain_results"])
    validate_satellite_manifest(loaded["satellite_manifest"])
    return loaded["parent_results"], loaded["terrain_results"], loaded["satellite_manifest"], parent_tasks


def run_task(task, private, manifest, read, deadline, indices):
    _require(task in TASKS, "Unknown candidate-reproduction task")
    row = private["tasks"][task]
    population = load_task(row["arrays"], Path(private["arrays_root"]) / task, read, deadline)
    counts = baseline_counts(population)
    expected = EXPECTED[task]
    _compare_expected(
        counts,
        {key: value for key, value in expected["counts"].items() if not key.startswith("satellite_")},
        f"{task}.counts",
    )
    metrics = baseline_metrics(population)
    _compare_expected(metrics, expected["metrics"], f"{task}.baseline")
    plan = build_satellite_plan(task, population, manifest, private["satellite_root"])
    _require(len(plan) == expected["counts"]["satellite_files"], f"Satellite plan count differs for {task}")
    plan_bytes = sum(int(entry["bytes"]) for entry in plan)
    _require(plan_bytes == expected["counts"]["satellite_bytes"], f"Satellite plan bytes differ for {task}")
    scene_maps = scene_split_min(plan, read, indices, deadline)
    split_min = _split_min_by_row(population, scene_maps)
    satellite = {
        "scenes": len(population["s1_scene_ids"]),
        "files": len(plan),
        "bytes": plan_bytes,
        "slots": list(range(SLOTS)),
        "bands": list(BANDS),
        "files_sha256": digest(
            [
                {
                    "scene": entry["scene"],
                    "slot": entry["slot"],
                    "nominal": entry["nominal"],
                    "relative_path": entry["relative_path"],
                    "bytes": entry["bytes"],
                    "sha256": entry["sha256"],
                }
                for entry in plan
            ]
        ),
    }
    result = evaluate_task(
        task,
        population,
        split_min,
        baseline=(counts, metrics),
        satellite=satellite,
    )
    _require(result["counts"]["satellite_files"] == len(plan), "Satellite count was not retained")
    return result


def _output_bytes(output_root):
    return sum(path.stat().st_size for path in Path(output_root).rglob("*") if path.is_file())


def execute(
    root,
    proposal,
    private,
    approval,
    commit,
    *,
    proposal_path,
    private_path,
    approval_path,
):
    root = Path(root).resolve()
    proposal_path = Path(proposal_path)
    private_path = Path(private_path)
    approval_path = Path(approval_path)
    for path in (proposal_path, private_path, approval_path):
        _require(path.is_file(), f"A live execution path is required: {path.name}")
    _require(
        proposal_path.parent.resolve()
        == approval_path.parent.resolve()
        == private_path.parent.resolve(),
        "Execution files must share the service namespace",
    )
    _require(
        Path(private["service_dir"]).parent.resolve() == approval_path.parent.resolve(),
        "Approval must live beside the private service namespace",
    )

    sys.path.insert(0, str(root))
    from tools.research_readiness.start_independent_process import (  # noqa: PLC0415
        host_identity,
        require_independent,
    )

    require_independent(host_identity())
    head = checked(root, proposal, private, approval, commit)
    _require(head == commit, "The approved commit changed")
    output_root = Path(private["output_root"])
    _require(_free_bytes(output_root.parent) >= BUDGET["minimum_free_bytes"], "Insufficient free disk for the frozen minimum", PermissionError)
    _require(SATELLITE_ROOT.is_dir(), "The frozen satellite archive root is unavailable; no run may start")
    output_root.mkdir(parents=False)
    deadline = Deadline(BUDGET["maximum_seconds"])
    completed = {}
    metadata_guard = ReadGuard(deadline, BUDGET["metadata_open_instances"], BUDGET["metadata_reference_bytes"], "metadata")
    scientific_guard = ReadGuard(deadline, BUDGET["scientific_file_opens"], BUDGET["scientific_source_bytes"], "scientific")
    started = time.monotonic()
    try:
        write(
            output_root / "authorization_binding.json",
            {
                "at": now(),
                "kind": KIND,
                "proposal_sha256": proposal["proposal_sha256"],
                "private_preparation_sha256": proposal["private_preparation_sha256"],
                "execution_code_commit": commit,
                "controller_pid": os.getpid(),
                "tasks": list(TASKS),
                "approval": {
                    "approved_by_researcher": approval["approved_by_researcher"],
                    "decision_id": approval["decision_id"],
                    "code_commit": approval["code_commit"],
                    "output_root": approval["output_root"],
                },
                "automatic_retry": False,
                "replay": False,
                "scientific_status": "NOT_VERIFIED",
            },
        )
        _parent, _terrain, manifest, _parent_tasks = load_metadata(private, metadata_guard)
        indices = _helpers().sp04_membership(Path(private["code_root"]))
        for index, task in enumerate(TASKS):
            _require(deadline.remaining() > 0, "The frozen execution deadline expired")
            _require(_free_bytes(output_root) >= BUDGET["minimum_free_bytes"], "Insufficient free disk during execution", PermissionError)
            write(
                output_root / f"task_{index + 1}_claim.json",
                {
                    "at": now(),
                    "index": index,
                    "task": task,
                    "controller_pid": os.getpid(),
                    "execution_code_commit": commit,
                    "maximum_seconds": BUDGET["maximum_seconds"],
                    "automatic_retry": False,
                },
            )
            result = run_task(task, private, manifest, scientific_guard, deadline, indices)
            write(output_root / f"{task}_result.json", result)
            completed[task] = result
            _require(_output_bytes(output_root) <= BUDGET["maximum_output_bytes"], "The output-byte cap was exceeded")
        _require(metadata_guard.opens == BUDGET["metadata_open_instances"], "Metadata open accounting differs")
        _require(metadata_guard.source_bytes == BUDGET["metadata_reference_bytes"], "Metadata byte accounting differs")
        _require(scientific_guard.opens == BUDGET["scientific_file_opens"], "Scientific open accounting differs")
        _require(scientific_guard.source_bytes == BUDGET["scientific_source_bytes"], "Scientific byte accounting differs")
        q2 = q2_summary(completed, private.get("seed2029_reference"))
        q3 = q3_summary(completed)
        totals = {
            "scientific_file_opens": scientific_guard.opens,
            "scientific_source_bytes": scientific_guard.source_bytes,
            "arrays_open_instances": BUDGET["arrays_open_instances"],
            "arrays_reference_bytes": BUDGET["arrays_reference_bytes"],
            "satellite_open_instances": BUDGET["satellite_open_instances"],
            "satellite_reference_bytes": BUDGET["satellite_reference_bytes"],
            "metadata_open_instances": metadata_guard.opens,
            "metadata_reference_bytes": metadata_guard.source_bytes,
            "total_scientific_file_opens": scientific_guard.opens + metadata_guard.opens,
            "total_scientific_source_bytes": scientific_guard.source_bytes + metadata_guard.source_bytes,
            "checkpoint_loads": 0,
            "model_inference_passes": 0,
            "forward_batches": 0,
            "optimizer_updates": 0,
            "retries": 0,
            "replays": 0,
        }
        _require(
            totals["total_scientific_file_opens"] == BUDGET["total_scientific_file_opens"],
            "Total open accounting differs from the frozen budget",
        )
        _require(
            totals["total_scientific_source_bytes"] == BUDGET["total_scientific_source_bytes"],
            "Total byte accounting differs from the frozen budget",
        )
        elapsed = time.monotonic() - started
        _require(elapsed <= BUDGET["maximum_seconds"], "The frozen execution deadline expired", TimeoutError)
        results_name = "STAGE45_STEP4_MULTISEED_CANDIDATE_REPRODUCTION_RESULTS_V1.json"
        results_payload = {
            "status": STATUS,
            "kind": KIND,
            "scope": SCOPE,
            "decision": q2["decision"],
            "proposal_sha256": proposal["proposal_sha256"],
            "private_preparation_sha256": proposal["private_preparation_sha256"],
            "execution_code_commit": commit,
            "task_order": list(TASKS),
            "tasks": [completed[task] for task in TASKS],
            "q2": q2,
            "q3": q3,
            "frozen_rules": RULES,
            "expected_baselines": EXPECTED,
            "totals": totals,
            "budget": BUDGET,
            "scientific_status": "NOT_VERIFIED",
            "scientific_acceptance": "NOT_VERIFIED",
            "final_2025_access": False,
            "access_2025": False,
            "automatic_retry": False,
            "replay": False,
            "checkpoint_loads": 0,
            "model_inference_passes": 0,
            "optimizer_updates": 0,
            "elapsed_seconds": elapsed,
            "notes": [
                "Q2 is the pre-registered REAL-seed reproduction decision.",
                "Q3 is descriptive for the ZERO control and does not establish physical attribution.",
                "The action leaves p and q32 fixed by construction.",
                "No arrays are retained by this package.",
            ],
        }
        results_path = output_root / results_name
        write(results_path, results_payload)
        results_bytes = results_path.stat().st_size
        results_sha = sha(results_path)
        completion = {
            "at": now(),
            "status": STATUS,
            "kind": KIND,
            "scope": SCOPE,
            "decision": q2["decision"],
            "q2_decision": q2["decision"],
            "q3_decision": q3["decision"],
            "proposal_sha256": proposal["proposal_sha256"],
            "private_preparation_sha256": proposal["private_preparation_sha256"],
            "execution_code_commit": commit,
            "results": {
                "name": results_name,
                "bytes": results_bytes,
                "sha256": results_sha,
            },
            "tasks": [
                {
                    "task": task,
                    "decision": completed[task]["decision"],
                    "selected_rows": completed[task]["selection"]["selected_rows"],
                    "feasible_rows": completed[task]["selection"]["feasible_rows"],
                    "infeasible_rows": completed[task]["selection"]["infeasible_rows"],
                    "weak_rows_selected": completed[task]["selection"]["weak_rows_selected"],
                    "nonstrong_rows_selected": completed[task]["selection"]["nonstrong_rows_selected"],
                }
                for task in TASKS
            ],
            "totals": totals,
            "budget": BUDGET,
            "scientific_status": "NOT_VERIFIED",
            "scientific_acceptance": "NOT_VERIFIED",
            "final_2025_access": False,
            "access_2025": False,
            "automatic_retry": False,
            "replay": False,
            "checkpoint_loads": 0,
            "model_inference_passes": 0,
            "optimizer_updates": 0,
            "elapsed_seconds": elapsed,
        }
        write(output_root / "completion.json", completion)
        return completion
    except BaseException as error:
        failure = output_root / "execution_failure.json"
        if not failure.exists():
            write(
                failure,
                {
                    "at": now(),
                    "status": "STOP_NO_RETRY",
                    "kind": KIND,
                    "scope": SCOPE,
                    "proposal_sha256": proposal.get("proposal_sha256"),
                    "execution_code_commit": commit,
                    "error": type(error).__name__ + ": " + str(error),
                    "completed_tasks": list(completed),
                    "automatic_retry": False,
                    "replay": False,
                    "scientific_status": "NOT_VERIFIED",
                    "scientific_acceptance": "NOT_VERIFIED",
                    "final_2025_access": False,
                },
            )
        raise
