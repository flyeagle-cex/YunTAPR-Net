"""Prepare or execute one bounded Stage-45 Development nine-gate acceptance.

Preparation reads and hashes the frozen 121-shard COSINE9 Development readout,
counts the frozen candidate population, joins the six causal Himawari slots of
every candidate scene from the frozen manifest, and writes an unauthorized
proposal.  Execution is refused until a separate exact researcher approval
file is present.  The core never runs a model, a checkpoint or an optimizer.
"""

import argparse
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "research_readiness"))

import stage45_dev_acceptance as core  # noqa: E402


ENTRY = "tools/research_readiness/start_stage45_dev_acceptance.py"
KIND = core.KIND
SCOPE = core.AUTHORIZATION_SCOPE
READOUT_FOLDER = "docs/research_readiness/.local/b_readout_prepare_20261120_v2/readout"
RECEIPT = READOUT_FOLDER + "/completion.json"
ARRAYS = READOUT_FOLDER + "/arrays"
MANIFEST = Path(r"F:\codex_downloads\_cm\r24\docs\core_stage3\.local\plan_20261024_v3\manifest_2024_fixed_f006.json")
SATELLITE_ROOT = Path(r"H:\葵花202303_202510")
ENVIRONMENT = {"PYTHONHASHSEED": "2029", "PYTHONUTF8": "1", "OMP_NUM_THREADS": "1",
               "MKL_NUM_THREADS": "1", "CUBLAS_WORKSPACE_CONFIG": ":4096:8"}
EXPECTED_IDENTITY = {
    "population_ids_sha256": "916302412bf024942aadeefe969d12c74452481ef24dedc30b1262b24609cf76",
    "partition_sha256": "01b95f12d26a3f6f4ff05620414cdae66c5cec23bd2808b0af2de40e4615291c",
    "supervision_mask_sha256": "70368bec3149e998922d565dab83347ba33f465df481a03ac3f90b85f1286d4b",
    "population_sha256": "2f2cc75cfb6c209fd8195d3419207216c5c3f2a4fc8315b40a1d77cc537dedb8",
    "n_rain": 407820,
    "n_strong": 717,
    "proposal_sha256": "ed417346f82218fe981078872fb91c80211ad46e9b836f29e628daef842308a9",
    "checkpoint_sha256": "1c9b5f8c595935674f6952da6b239a50e26ca4eb4d90a217ab5593866d5b319e",
    "code_commit": "df2155ab3c5bc6bc8cb7a507c14e8bedab856544",
}
CODE_FILES = (
    ENTRY,
    "tools/research_readiness/stage45_dev_acceptance.py",
    "src/yuntapr/spatial/sp04_mapping.py",
    "src/yuntapr/data/himawari_b13.py",
    "config/spatial/sp04_coordinate_manifest_v1.json",
    "config/spatial/sp04_coordinate_axes_v1.csv",
    "config/spatial/sp04_target_cell_membership_v1.csv",
)


def _fail(message):
    raise SystemExit("STAGE45_PREPARE_REFUSED: " + message)


def _sha(path):
    hasher = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


def _git(root, *arguments):
    return subprocess.check_output(["git", "-C", str(root), *arguments], text=True).strip()


def _clean_checkout(root, commit):
    if not isinstance(commit, str) or len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit):
        _fail("code commit must be one lowercase 40-hex SHA")
    if _git(root, "rev-parse", "HEAD") != commit:
        _fail("git HEAD differs from --code-commit")
    if _git(root, "status", "--porcelain"):
        _fail("git working tree is not clean")


def _validate_namespace(source_root, namespace):
    local = (source_root / "docs/research_readiness/.local").resolve()
    namespace = Path(namespace).resolve()
    if namespace.exists():
        _fail("namespace already exists")
    if namespace.parent != local:
        _fail("namespace must be a direct child of docs/research_readiness/.local")
    return namespace


def _read_hashed(path, size, sha256):
    content = Path(path).read_bytes()
    if len(content) != int(size):
        raise ValueError("Array shard byte count changed: " + Path(path).name)
    actual = core.sha256_bytes(content)
    if actual != sha256:
        raise ValueError("Array shard SHA256 changed: " + Path(path).name)
    return content


def _load_arrays(source_root):
    arrays_dir = source_root / ARRAYS
    receipt_path = source_root / RECEIPT
    for path in (arrays_dir, receipt_path):
        if not path.exists():
            _fail("missing frozen readout asset: " + str(path))
    receipt = core.read_json(receipt_path)
    if receipt.get("status") != "COMPLETE_SINGLE_ARM_READOUT":
        _fail("the frozen readout is not a completed single-arm readout")
    result = receipt.get("result", {})
    full = result.get("full_dev_readout")
    if not isinstance(full, dict) or not isinstance(full.get("identity"), dict):
        _fail("the frozen readout lacks a full Development identity")
    identity = full["identity"]
    for key, value in EXPECTED_IDENTITY.items():
        if identity.get(key) != value:
            _fail("frozen readout identity differs at " + key)
    if receipt.get("proposal_sha256") != identity["proposal_sha256"]:
        _fail("frozen readout proposal identity differs")
    if result.get("checkpoint_sha256") != identity["checkpoint_sha256"]:
        _fail("frozen readout checkpoint identity differs")
    files = full.get("storage", {}).get("files")
    if not isinstance(files, list) or len(files) != 121:
        _fail("the frozen readout must contain exactly 121 array shards")
    expected_names = {f"batch_{index:03d}.npz" for index in range(121)}
    actual_names = {path.name for path in arrays_dir.glob("batch_*.npz")}
    if actual_names != expected_names:
        _fail("array shard names differ from the frozen 121-shard set")
    bytes_total = sum(int(entry["bytes"]) for entry in files)
    if bytes_total != core.FROZEN_EXPECTED["arrays_bytes"]:
        _fail("frozen array byte total differs")
    population = core.load_population(files, arrays_dir, _read_hashed, core.Deadline(3600))
    counts = core.counts_from_population(population)
    metrics = core.metrics_from_population(population)
    try:
        core._compare_expected(counts, core.FROZEN_EXPECTED["counts"], "counts")
        core._compare_expected(metrics, core.FROZEN_EXPECTED["metrics"], "baseline")
    except ValueError as error:
        _fail(str(error))
    return receipt, files, identity, counts, metrics, population


def _satellite_plan(candidate_scene_ids):
    if not MANIFEST.is_file():
        _fail("missing frozen satellite manifest")
    if not SATELLITE_ROOT.is_dir():
        _fail("missing frozen Himawari root")
    manifest = core.read_json(MANIFEST)
    if manifest.get("year") != 2024 or manifest.get("role") != "Development":
        _fail("satellite manifest is not the frozen 2024 Development manifest")
    scenes = manifest.get("scene_records")
    satellites = manifest.get("satellite_files")
    if not isinstance(scenes, list) or len(scenes) != 963:
        _fail("satellite manifest scene count differs")
    if not isinstance(satellites, list) or len(satellites) != 5778:
        _fail("satellite manifest file count differs")
    by_scene = {record.get("sample_id"): record for record in scenes}
    if len(by_scene) != len(scenes):
        _fail("satellite manifest scene ids are not unique")
    by_nominal = {entry.get("nominal"): entry for entry in satellites}
    if len(by_nominal) != len(satellites):
        _fail("satellite manifest nominal times are not unique")
    planned = []
    total_bytes = 0
    for scene in candidate_scene_ids:
        record = by_scene.get(scene)
        if record is None:
            _fail("candidate scene is absent from the frozen manifest: " + scene)
        for slot in range(6):
            nominal = record.get(f"slot_{slot}_nominal")
            satellite = by_nominal.get(nominal)
            if not isinstance(nominal, str) or satellite is None:
                _fail(f"candidate scene lacks frozen slot_{slot}: {scene}")
            if satellite.get("nominal") != nominal:
                _fail("satellite nominal join differs")
            relative = satellite.get("relative_path")
            size = satellite.get("expected_bytes")
            sha256 = satellite.get("expected_sha256")
            if not isinstance(relative, str) or not relative:
                _fail("satellite relative path missing")
            if not isinstance(size, int) or size <= 0:
                _fail("satellite expected bytes malformed")
            if not (isinstance(sha256, str) and len(sha256) == 64
                    and all(c in "0123456789abcdef" for c in sha256)):
                _fail("satellite expected SHA256 malformed")
            path = SATELLITE_ROOT / relative.replace("\\", "/")
            if not path.is_file() or path.stat().st_size != size:
                _fail("satellite asset missing or size differs: " + relative)
            planned.append(dict(scene=scene, slot=slot, nominal=nominal,
                                relative_path=relative, bytes=size, sha256=sha256))
            total_bytes += size
    if len(planned) != core.FROZEN_EXPECTED["satellite_files"]:
        _fail("candidate satellite file count differs")
    if total_bytes != core.FROZEN_EXPECTED["satellite_bytes"]:
        _fail("candidate satellite byte total differs")
    if len(planned) + 121 != core.BUDGET["maximum_scientific_file_opens"]:
        _fail("declared scientific file opens differ from the frozen cap")
    if total_bytes + core.FROZEN_EXPECTED["arrays_bytes"] != core.BUDGET["maximum_reference_bytes"]:
        _fail("declared scientific bytes differ from the frozen cap")
    return planned


def _code_hashes(source_root):
    hashes = {}
    for relative in CODE_FILES:
        path = source_root / relative
        if not path.is_file():
            _fail("missing pinned code or config file: " + relative)
        hashes[relative] = _sha(path)
    return hashes


def prepare(args):
    source_root = Path(args.source_root).resolve()
    if not (source_root / ENTRY).is_file() or not (source_root / "tools/research_readiness/stage45_dev_acceptance.py").is_file():
        _fail("--source-root is not the YunTAPR-Net checkout")
    _clean_checkout(source_root, args.code_commit)
    namespace = _validate_namespace(source_root, args.namespace)
    receipt, files, identity, counts, metrics, population = _load_arrays(source_root)
    satellite = _satellite_plan(population["candidate_scene_ids"])
    code_sha256 = _code_hashes(source_root)
    runtime_python = Path(sys.executable)
    python_sha256 = _sha(runtime_python)
    service_dir = namespace / "service"
    output_root = namespace / "output"
    arrays_dir = source_root / ARRAYS
    arrays_bytes = sum(int(entry["bytes"]) for entry in files)
    satellite_bytes = sum(int(entry["bytes"]) for entry in satellite)
    data_identity = dict(
        readout_status=receipt["status"],
        readout_proposal_sha256=receipt["proposal_sha256"],
        checkpoint_sha256=identity["checkpoint_sha256"],
        identity=identity,
        arrays_files=len(files),
        arrays_bytes=arrays_bytes,
        satellite_files=len(satellite),
        satellite_bytes=satellite_bytes,
    )
    proposal = dict(
        kind=KIND,
        status="READY_WAITING_EXACT_DEV_ACCEPTANCE_APPROVAL",
        authorized=False,
        authorization_scope=SCOPE,
        tasks=[dict(core.TASK)],
        models=[],
        execution_code_commit=args.code_commit,
        code_sha256=code_sha256,
        python_sha256=python_sha256,
        budget=dict(core.BUDGET),
        data_identity=data_identity,
        scientific_choices=dict(
            candidate_rule="supervised rows with FP64 p * q32 > 20.0, q32 = expm1(qlog[-1])",
            candidate_threshold=core.CANDIDATE_THRESHOLD,
            a0_rule="a0 = float32(p * mean(expm1(qlog)))",
            a0_threshold=core.A0_THRESHOLD,
            split_rule="split = tbb_08 - tbb_13 at the candidate pixel after SP04 25-cell area mean; split_min over slot_0..slot_5",
            split_threshold=core.SPLIT_THRESHOLD,
            action_rule="keep q32 and p fixed; blend the 31 sub-top physical quantiles a fraction u toward the fixed top quantile q32, with u chosen so the FP32 point mass p*mean reaches 20.01; feasible iff 0 < u < 1, nodes remain strictly increasing, and new A = float32(p * mean(blended)) > 20.0",
            target_mass=core.TARGET_MASS,
            gates=[
                dict(gate=1, name="strong_physical_pinball_over20", comparator="lt"),
                dict(gate=2, name="point_a_detection_restored", comparator="ge", threshold=1),
                dict(gate=3, name="point_a_false_positive_removed", comparator="le", threshold=0),
                dict(gate=4, name="q32_support_true_positive_unchanged", comparator="eq"),
                dict(gate=5, name="q32_support_false_positive_unchanged", comparator="eq"),
                dict(gate=6, name="weak_log_pinball_unchanged", comparator="eq"),
                dict(gate=7, name="occurrence_brier_unchanged", comparator="by_construction_equal"),
                dict(gate=8, name="occurrence_ap_unchanged", comparator="by_construction_equal"),
                dict(gate=9, name="occurrence_auroc_unchanged", comparator="by_construction_equal"),
            ],
            decision="PASS iff gate1 improves, gate2 tp >= 1, gate3 fp == 0, gate6 unchanged, and no weak/nonstrong row is selected",
            baseline_metrics=dict(core.BASELINE_METRICS),
            baseline_counts=dict(core.BASELINE_COUNTS),
        ),
        final_2025_access=False,
    )
    private = dict(
        kind=KIND,
        output_root=str(output_root),
        service_dir=str(service_dir),
        code_root=str(source_root),
        runtime_python=str(runtime_python),
        arrays_dir=str(arrays_dir),
        arrays_files=files,
        satellite_root=str(SATELLITE_ROOT),
        satellite_files=satellite,
        manifest_path=str(MANIFEST),
        manifest_sha256=_sha(MANIFEST),
        identity=identity,
        data_identity=data_identity,
        baseline_metrics=metrics,
        baseline_counts=counts,
        budget=dict(core.BUDGET),
    )
    private_sha256 = core.private_digest(private)
    proposal["private_preparation_sha256"] = private_sha256
    proposal_sha256 = core.proposal_digest(proposal)
    proposal["proposal_sha256"] = proposal_sha256
    private["proposal_sha256"] = proposal_sha256
    execution_spec = dict(
        kind=KIND,
        cwd=str(source_root),
        service_dir=str(service_dir),
        command=[str(runtime_python), "-B", str(source_root / ENTRY), "execute",
                 "--proposal", str(namespace / "PROPOSAL.json"),
                 "--private-preparation", str(namespace / "PRIVATE_PREPARATION.json"),
                 "--researcher-approval", str(namespace / "RESEARCHER_APPROVAL.json")],
        environment=dict(ENVIRONMENT),
        proposal_sha256=proposal_sha256,
        final_2025_access=False,
        automatic_retry=False,
    )
    namespace.mkdir()
    service_dir.mkdir()
    core.write_json(namespace / "PROPOSAL.json", proposal)
    core.write_json(namespace / "PRIVATE_PREPARATION.json", private)
    core.write_json(namespace / "EXECUTION_SPEC.json", execution_spec)
    print(proposal_sha256)


def _validate_execute(proposal, private, approval, source_root):
    if proposal.get("kind") != KIND or private.get("kind") != KIND:
        raise PermissionError("unexpected Stage-45 kind")
    if proposal.get("authorization_scope") != SCOPE:
        raise PermissionError("Stage-45 authorization scope differs")
    if proposal.get("tasks") != [dict(core.TASK)]:
        raise PermissionError("Stage-45 task differs")
    if proposal.get("authorized") is not False or proposal.get("final_2025_access") is not False:
        raise PermissionError("the proposal must remain unauthorized and 2025-frozen")
    if proposal.get("budget") != core.BUDGET:
        raise PermissionError("Stage-45 budget differs from the frozen caps")
    if proposal.get("execution_code_commit") != _git(source_root, "rev-parse", "HEAD"):
        raise PermissionError("execution commit differs from git HEAD")
    if _git(source_root, "status", "--porcelain"):
        raise PermissionError("the execution checkout is not clean")
    if core.proposal_digest(proposal) != proposal.get("proposal_sha256"):
        raise PermissionError("proposal digest changed")
    if core.private_digest(private) != proposal.get("private_preparation_sha256"):
        raise PermissionError("private preparation digest changed")
    if private.get("proposal_sha256") != proposal.get("proposal_sha256"):
        raise PermissionError("private proposal binding changed")
    if (approval.get("approved_by_researcher") is not True
            or not str(approval.get("decision_id", "")).strip()
            or approval.get("authorization_scope") != SCOPE
            or approval.get("proposal_sha256") != proposal.get("proposal_sha256")
            or approval.get("tasks") != proposal.get("tasks")
            or approval.get("budget") != proposal.get("budget")
            or approval.get("scientific_choices") != proposal.get("scientific_choices")
            or approval.get("code_commit") != proposal.get("execution_code_commit")
            or Path(approval.get("output_root", "")).resolve() != Path(private.get("output_root", "")).resolve()):
        raise PermissionError("a separate exact researcher approval is required")
    if Path(sys.executable).resolve() != Path(private["runtime_python"]).resolve():
        raise PermissionError("the bound runtime interpreter differs")
    if _sha(sys.executable) != proposal.get("python_sha256"):
        raise PermissionError("the bound runtime interpreter SHA256 differs")
    entry = source_root / ENTRY
    if not entry.is_file() or _sha(entry) != proposal.get("code_sha256", {}).get(ENTRY):
        raise PermissionError("the pinned Stage-45 entry changed")
    service_dir = Path(private["service_dir"]).resolve()
    if not service_dir.is_dir():
        raise PermissionError("the private service namespace is missing")
    output_root = Path(private["output_root"]).resolve()
    if output_root.exists():
        raise PermissionError("the output namespace must not exist")
    return output_root


def execute(args):
    proposal = core.read_json(args.proposal)
    private = core.read_json(args.private_preparation)
    approval = core.read_json(args.researcher_approval)
    source_root = Path(private.get("code_root", "")).resolve()
    if not source_root.is_dir() or not (source_root / ENTRY).is_file():
        raise SystemExit("STAGE45_EXECUTE_REFUSED: code root differs")
    output_root = _validate_execute(proposal, private, approval, source_root)
    output_root.mkdir()
    deadline = core.Deadline(core.BUDGET["maximum_seconds"])
    try:
        def verify_file(path):
            content = Path(path).read_bytes()
            return content, core.sha256_bytes(content)

        result = core.run(proposal, private, output_root, verify_file, deadline=deadline)
        completion = dict(
            status="COMPLETE_STAGE45_DEV_ACCEPTANCE",
            proposal_sha256=proposal["proposal_sha256"],
            private_preparation_sha256=proposal["private_preparation_sha256"],
            execution_code_commit=proposal["execution_code_commit"],
            decision=result["decision"],
            result=result,
            accounting=result["accounting"],
            final_2025_access=False,
            optimizer_updates=0,
            model_inference_passes=0,
            automatic_retry=False,
            finished=datetime.now(timezone.utc).isoformat(),
        )
        core.write_json(output_root / "completion.json", completion)
    except BaseException as error:
        core.write_json(output_root / "failure.json", dict(
            status="STOP_NO_RETRY",
            error_type=type(error).__name__,
            details=str(error),
            proposal_sha256=proposal.get("proposal_sha256"),
            execution_code_commit=proposal.get("execution_code_commit"),
            final_2025_access=False,
            automatic_retry=False,
            finished=datetime.now(timezone.utc).isoformat(),
        ))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    prepare_parser = modes.add_parser("prepare")
    prepare_parser.add_argument("--namespace", type=Path, required=True)
    prepare_parser.add_argument("--source-root", type=Path, required=True)
    prepare_parser.add_argument("--code-commit", required=True)
    execute_parser = modes.add_parser("execute")
    execute_parser.add_argument("--proposal", type=Path, required=True)
    execute_parser.add_argument("--private-preparation", type=Path, required=True)
    execute_parser.add_argument("--researcher-approval", type=Path, required=True)
    args = parser.parse_args()
    if args.mode == "prepare":
        prepare(args)
    else:
        execute(args)


if __name__ == "__main__":
    main()
