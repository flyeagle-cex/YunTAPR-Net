"""Bind a two-E9 evaluation proposal using saved metadata and code only."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
PUBLIC = ROOT / "docs/research_readiness/20261114_joint_amplitude_prepare"
TOOLS = (
    "tools/research_readiness/start_paired_point_evaluation.py",
    "tools/research_readiness/paired_point_worker.py",
    "tools/research_readiness/paired_point_metrics.py",
    "tools/research_readiness/paired_joint_amplitude.py",
    "tools/research_readiness/supplement_occurrence_metrics_20261113.py",
    "tools/research_readiness/start_independent_process.py",
)


def digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


class MetadataPreparation:
    def __init__(self):
        self.bytes = 0
        self.opens = 0
        self.records = []

    def raw(self, path):
        path = Path(path).resolve()
        size = path.stat().st_size
        if self.bytes + size > 256 * 1024**2 or self.opens + 1 > 256:
            raise PermissionError("Preparation metadata limit reached")
        self.bytes += size
        self.opens += 1
        raw = path.read_bytes()
        identity = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        self.records.append({"source_id": hashlib.sha256(str(path).encode()).hexdigest(), **identity})
        return raw, identity

    def read(self, path):
        raw, identity = self.raw(path)
        return json.loads(raw), identity


def write(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def prepare(code_root, private_dir, output_root, public_root=None):
    from tools.research_readiness.start_paired_point_evaluation import LIMITS, SCOPE, TASKS as ORDER

    code_root, private_dir, output_root = map(lambda p: Path(p).resolve(), (code_root, private_dir, output_root))
    public_root = Path(public_root).resolve() if public_root is not None else PUBLIC
    if output_root.exists() or not output_root.parent.is_dir():
        raise PermissionError("A fresh output namespace under an existing parent is required")
    public_root.mkdir(parents=True, exist_ok=True)
    private_dir.mkdir(exist_ok=False)
    cost = MetadataPreparation()
    old, _ = cost.read(ROOT / "docs/research_readiness/20261110_cosine9/EXECUTION_PROPOSAL.json")
    old_private, _ = cost.read(ROOT / "docs/research_readiness/.local/cosine9_prepare_20261110_v1/PRIVATE_PREPARATION.json")
    wrapper, identity = cost.read(old_private["inherited"])
    if identity["sha256"] != old_private["inherited_file_sha256"]:
        raise ValueError("Inherited preparation identity differs")
    prepared = wrapper["prepared"]
    if prepared["data"] != old["data"]:
        raise ValueError("Inherited population identity differs")
    scope = prepared["roles"]["Development"]
    if (scope["file_count"], scope["bytes_per_pass"], len(scope["ids"])) != (7950, 26639253112, 963):
        raise ValueError("Development scope differs")
    if any(not sid.startswith("2024-") for sid in scope["ids"]):
        raise PermissionError("Only the frozen 2024 Development scene population")
    current = subprocess.check_output(["git", "-C", str(code_root), "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(["git", "-C", str(code_root), "status", "--porcelain"], text=True).strip()
    if dirty:
        raise PermissionError("The fixed execution worktree must be clean")
    code_files = (sorted((code_root / "src").rglob("*.py"))
                  + sorted((code_root / "tools/core_stage4/monitor").rglob("*.py"))
                  + [code_root / name for name in TOOLS])
    code_sha = {path.relative_to(code_root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in code_files}
    for name, expected in old["code_sha256"].items():
        if name.startswith("src/") and code_sha.get(name) != expected:
            raise ValueError("Numerical source differs from the original COSINE9 binding: " + name)

    tasks = {}
    models = []
    summaries = {}
    report_paths = []
    source_paths = (
        ROOT / "docs/research_readiness/.local/uq_mild_seed2029_execution_v1/CONTROL_E0/B7_s2029",
        ROOT / "docs/research_readiness/.local/cosine9_seed2029_execution_v1/B7_s2029",
    )
    checkpoint_shas = (
        "a3f9208aa4e25e786c6797e658cc5fda4da9a29a05c87a693aa6a3fdc571565f",
        "1c9b5f8c595935674f6952da6b239a50e26ca4eb4d90a217ab5593866d5b319e",
    )
    scientific = {}

    def add_scientific(path, spec):
        key = str(Path(path).resolve())
        if any(os.path.normcase(key) == os.path.normcase(existing) for existing in scientific):
            raise ValueError("Duplicate scientific source identity")
        scientific[key] = spec

    for path, info in scope["files"].items():
        if info["year"] != 2024 and not (info["year"] == 2023 and info["kind"] == "static_mask"):
            raise PermissionError("Forbidden source year or role")
        add_scientific(path, dict(bytes=info["bytes"], sha256=info["sha"], category="weather", tasks=list(ORDER), opens_per_task=1))
    for task, folder, checkpoint_sha, checkpoint_bytes in zip(ORDER, source_paths, checkpoint_shas, (53904005, 53906821)):
        report = folder / "B7_development_09.json"
        saved, report_identity = cost.read(report)
        point = folder / "B7_LAST_epoch_09.pt"
        receipt, _ = cost.read(folder / "B7_LAST_epoch_09.receipt.json")
        if receipt.get("checkpoint_sha256") != checkpoint_sha or point.stat().st_size != checkpoint_bytes:
            raise ValueError("Fixed E9 receipt/size identity differs")
        tasks[task] = dict(checkpoint_path=str(point), dev_report_path=str(report))
        models.append(dict(task=task, model="B7", seed=2029, endpoint="FIXED_EPOCH_9_LAST",
                           checkpoint_bytes=point.stat().st_size, checkpoint_sha256=checkpoint_sha,
                           dev_report_bytes=report_identity["bytes"], dev_report_sha256=report_identity["sha256"]))
        summaries[task] = saved["groups"]["all"]["summary"]
        report_paths.append(report)
        add_scientific(point, dict(bytes=point.stat().st_size, sha256=checkpoint_sha, category="checkpoint", tasks=[task], opens_per_task=2))
    if [(summaries[t]["scenes"], summaries[t]["n_valid"], summaries[t]["n_rain"]) for t in ORDER] != [(963, 3303090, 407820)] * 2:
        raise ValueError("Saved reports have a different population")
    terrain = Path(old_private["terrain"])
    static = terrain / "B6_static.npz"
    if static.stat().st_size != 312828:
        raise ValueError("Frozen terrain archive size differs")
    add_scientific(static, dict(bytes=312828, sha256=old["static_source_sha256"]["B7"], category="static", tasks=list(ORDER), opens_per_task=1))
    inputs = prepared["private_inputs"]
    stage3 = Path(inputs["stage3_run"])
    request = Path(inputs["request"])
    request_body, _ = cost.read(request)
    files = [Path(old_private["inherited"]), *report_paths, terrain / "production_receipt.json", request]
    files += [stage3 / name for name in ("populations.json", "train_statistics.json", "statistics.sqlite")]
    files += [request.parent / request_body["roles"][role]["manifest"] for role in ("Train", "Development")]
    files += [path for path in (code_root / "config").rglob("*") if path.is_file() and path.suffix in (".json", ".yaml", ".yml", ".csv")]
    files += [code_root / name for name in (
        "docs/scientific_freeze/YUNTAPR_SCIENTIFIC_FREEZE_v1.1.md",
        "docs/scientific_freeze/YUNTAPR_SCIENTIFIC_FREEZE_v1.md",
        "docs/core_stage3/execution_summary/evidence.json",
        "docs/b0_pretraining_closure/runs/run_20260930T095416Z/formal_sample_eligibility_2023_2024.csv",
    ) if (code_root / name).is_file()]
    metadata = {}
    for path in sorted(set(path.resolve() for path in files)):
        _, metadata[str(path)] = cost.raw(path)
    native = Path(r"F:\conda_envs\rain-basics\python.exe")
    runtime = dict(old["runtime_binding"])
    runtime["executable_sha256"] = runtime.pop("python_executable_sha256")
    if hashlib.sha256(native.read_bytes()).hexdigest() != runtime["executable_sha256"]:
        raise ValueError("Original interpreter identity differs")
    runtime.update(gpu_name="NVIDIA GeForce RTX 5060 Laptop GPU", gpu_total_bytes=8546484224)
    volumes = sorted({str(Path(path).anchor) for path in scientific})
    if any(not Path(volume).is_dir() for volume in volumes):
        raise RuntimeError("A frozen source volume is unavailable")
    candidate_roots = {str(Path(path).parent) for path in metadata} | {
        str(ROOT / "docs"), str(code_root / "docs"), str(code_root / "config"),
        r"H:\葵花202303_202510", r"F:\云南极端降水数据\raw\IMERG", str(terrain),
    } | {str(Path(path).parent) for path in scientific}
    source_roots = []
    for name in sorted(candidate_roots, key=lambda name: len(Path(name).parts)):
        path = Path(name).resolve()
        if not any(path.is_relative_to(Path(parent)) for parent in source_roots):
            source_roots.append(str(path))
    private = dict(output_root=str(output_root), preflight_root=str(private_dir / "preflight"),
                   code_root=str(code_root), runtime_python=str(native),
                   runtime_roots=[str(native.parent / name) for name in ("Lib", "DLLs", "Library")],
                   preparation_path=str(Path(old_private["inherited"]).resolve()),
                   static_source=str(static), static_receipt=str(terrain / "production_receipt.json"),
                   tasks=tasks, scientific_files=scientific, metadata_files=metadata, source_roots=source_roots)
    proposal = dict(status="READY_PENDING_EXACT_RESEARCHER_APPROVAL", authorized=False,
                    authorization_scope=SCOPE, execution_code_commit=current, tasks=list(ORDER), models=models,
                    private_preparation_sha256=digest(private), code_sha256=code_sha, runtime=runtime,
                    data_identity=old["data"], data_scope=dict(year=2024, role="Development",
                        scenes=963, n_valid=3303090, n_rain=407820), expected_summaries=summaries,
                    static_sha256=old["static_source_sha256"]["B7"],
                    scientific_choices=dict(DOTE=old["scientific_choices"]["DOTE"], modulation_limit=.1,
                        point_methods=["A", "B", "C"], thresholds_mm_h=[.1, 1., 5., 10., 20., 50.],
                        classification_precision="FP32 strict > threshold, equality counts retained",
                        continuous_precision="FP64 physical point proxies", cutoff_selection="FIXED_NO_OPTIMIZATION",
                        joint_record_policy=dict(
                            strong_truth_rule="float32(reference_rate_mm_h) > float32(20.0)",
                            record_population="717 strong pixel-times per arm only",
                            record_fields=["scene_id", "analysis_time", "pixel_index", "truth_mm_h", "p_occ",
                                           "qlog[32]", "point_A_mm_h", "point_B_mm_h", "point_C_mm_h"],
                            identity_key=["scene_id", "analysis_time", "pixel_index"],
                            all_valid_population="streamed_joint_counts_only",
                            cross_arm_match="exact ordered key and exact reference value equality",
                            no_full_population_prediction_export=True)),
                    budget=LIMITS, final_2025_access=False)
    proposal["proposal_sha256"] = digest(proposal)
    private["proposal_sha256"] = proposal["proposal_sha256"]
    write(public_root / "EXECUTION_PROPOSAL.json", proposal)
    write(private_dir / "PRIVATE_PREPARATION.json", private)
    service = private_dir / "service"
    service.mkdir()
    write(private_dir / "EXECUTION_SPEC.json", dict(kind="BOUNDED_PAIRED_JOINT_AMPLITUDE_EVALUATION",
          service_dir=str(service), cwd=str(code_root), command=[str(native), "-B",
              str(code_root / TOOLS[0]), "execute", "--proposal", str(public_root / "EXECUTION_PROPOSAL.json"),
              "--private-preparation", str(private_dir / "PRIVATE_PREPARATION.json"),
              "--researcher-approval", str(private_dir / "RESEARCHER_APPROVAL.json")],
          environment=dict(PYTHONPATH=str(code_root / "src") + os.pathsep + str(code_root),
              PYTHONUTF8="1", PYTHONHASHSEED="2029", CUBLAS_WORKSPACE_CONFIG=":4096:8",
              OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")))
    write(public_root / "PREPARATION_RECEIPT.json", dict(status="PREPARED_NOT_LAUNCHED", code_commit=current,
          proposal_sha256=proposal["proposal_sha256"], metadata_files=len(metadata),
          metadata_preparation_bytes=cost.bytes, metadata_preparation_opens=cost.opens,
          metadata_preparation_limit_bytes=256*1024**2, source_volume_admission="PASS",
          numerical_source_binding="MATCHES_ORIGINAL_COSINE9", scientific_payload_reads=0,
          checkpoint_loads=0, new_inference=0, optimizer_updates=0,
          metadata_preparation_reads=cost.records))
    return proposal, private


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root", type=Path, required=True)
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--public-root", type=Path)
    args = parser.parse_args()
    proposal, _ = prepare(args.code_root, args.private_dir, args.output_root, public_root=args.public_root)
    print(json.dumps({k: proposal[k] for k in ("status", "execution_code_commit", "proposal_sha256", "budget")}))


if __name__ == "__main__":
    main()
