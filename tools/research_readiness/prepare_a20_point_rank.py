"""Prepare the fixed A20 rank readout from two completed Dev receipts."""

import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.research_readiness import start_a20_point_rank as entry
from tools.research_readiness import start_paired_point_evaluation as shared


DOCS = Path("docs/research_readiness/20261119_conditional_intensity_diagnostic")
TOOLS = "tools/research_readiness/"
WIRING = {
    TOOLS + name for name in ("start_independent_process.py", "start_paired_point_evaluation.py",
                              "paired_point_worker.py", "start_conditional_intensity_readout.py")
}
ADDED = {entry.ENTRY, TOOLS + "point_rank_readout.py", TOOLS + "prepare_a20_point_rank.py"}
INHERITED_CHANGES = {
    "src/yuntapr/experimental/core_innovation/stage4/engine.py",
    "src/yuntapr/experimental/core_innovation/stage4/recovery.py",
    "src/yuntapr/experimental/research_readiness/dynamic_training.py",
    "src/yuntapr/experimental/research_readiness/physical_pinball_training.py",
}


def metadata(path):
    return dict(bytes=path.stat().st_size, sha256=shared.sha(path))


def prepare(code_root, run_root, public_proposal, b_private, a20_output):
    code_root, run_root, public_proposal, b_private, a20_output = (
        p.resolve() for p in (code_root, run_root, public_proposal, b_private, a20_output)
    )
    if run_root.exists() or public_proposal.exists():
        raise FileExistsError("Use a fresh private preparation namespace and proposal")
    if not run_root.is_relative_to((ROOT / "docs/research_readiness/.local").resolve()):
        raise PermissionError("Use an ignored private run directory")

    def git(*args):
        return subprocess.check_output(["git", "-C", str(code_root), *args], text=True).strip()

    code_commit = git("rev-parse", "HEAD")
    if git("status", "--porcelain"):
        raise PermissionError("A clean fixed execution checkout is required")
    base = shared.read(code_root / DOCS / "B_RECOVERY_PROPOSAL.json")
    old = shared.read(b_private)
    reference = shared.read(code_root / DOCS / "B_READOUT_RESULTS.json")
    def canonical(value):
        return shared.digest({k: v for k, v in value.items() if k != "proposal_sha256"})
    if (canonical(base) != base["proposal_sha256"] or base["proposal_sha256"] != old["proposal_sha256"]
            or canonical(old) != base["private_preparation_sha256"]
            or reference["proposal_sha256"] != base["proposal_sha256"]):
        raise PermissionError("Saved COSINE9 readout identities differ")
    report_b = Path(old["output_root"]) / "completion.json"
    control_meta = metadata(report_b)
    if control_meta["sha256"] != reference["completion_receipt_sha256"]:
        raise ValueError("Sealed COSINE9 completion receipt differs")
    files = entry.control_shards(shared.read(report_b), reference["proposal_sha256"], reference["checkpoint_sha256"])

    summary_a = shared.read(code_root / DOCS / "A20_RESULTS.json")
    a_proposal = shared.read(code_root / DOCS / "A20_RESTART_PROPOSAL.json")
    completion_a = metadata(a20_output / "completion.json")
    if (canonical(a_proposal) != a_proposal["proposal_sha256"]
            or summary_a["completion_receipt_sha256"] != completion_a["sha256"]
            or summary_a["e9_checkpoint_sha256"] != entry.A20_SHA
            or summary_a["proposal_sha256"] != a_proposal["proposal_sha256"]
            or a_proposal["data"] != base["data_identity"]
            or base["runtime"]["executable_sha256"] != a_proposal["runtime_binding"]["python_executable_sha256"]
            or any(base["runtime"][key] != a_proposal["runtime_binding"][key]
                   for key in ("python_version", "torch_version", "cuda_build", "numpy_version"))
            or {k: summary_a["fixed_point_a"][k] for k in ("tp", "fp")} != entry.CONTRACT["fixed_a_counts"]["A20"]):
        raise PermissionError("A20 sealed fixed-E9 point evidence differs")
    code_sha = {name: shared.sha(code_root / name) for name in sorted(set(base["code_sha256"]) | ADDED)}
    for name, old_sha in base["code_sha256"].items():
        expected = a_proposal["code_sha256"][name] if name in INHERITED_CHANGES else old_sha
        if name not in WIRING and expected != code_sha[name]:
            raise PermissionError("An unrelated inherited dependency changed: " + name)

    old_code = Path(old["code_root"]).resolve()
    def relocate(raw):
        path = Path(raw).resolve()
        return str(code_root / path.relative_to(old_code) if path.is_relative_to(old_code) else path)

    arm = a20_output / "B7_s2029"
    checkpoint = arm / "B7_LAST_epoch_09.pt"
    dev_report = arm / "B7_development_09.json"
    last = shared.read(checkpoint.with_suffix(".receipt.json"))
    if (last["checkpoint_sha256"] != entry.A20_SHA or last["epoch"] != 9 or last["updates"] != 4320
            or checkpoint.stat().st_size != entry.A20_BYTES):
        raise ValueError("A20 LAST checkpoint seal or size differs")
    report_meta = metadata(dev_report)
    saved_report = shared.read(dev_report)
    if shared.digest(saved_report) != last["validation_receipt_sha256"]:
        raise ValueError("A20 Dev report differs from its checkpoint seal")
    b_task = base["tasks"][0]
    metas = {relocate(path): info for path, info in old["metadata_files"].items()
             if path != old["tasks"][b_task]["dev_report_path"]}
    metas.update({str(dev_report): report_meta, str(report_b): control_meta})
    science = {path: dict(info, tasks=[entry.TASK]) for path, info in old["scientific_files"].items()
               if info["category"] in ("weather", "static")}
    science[str(checkpoint)] = dict(bytes=entry.A20_BYTES, sha256=entry.A20_SHA, category="checkpoint",
                                    tasks=[entry.TASK], opens_per_task=2)
    for shard in files:
        path = report_b.parent / "arrays" / shard["file"]
        science[str(path)] = dict(bytes=shard["bytes"], sha256=shard["sha256"], category="saved_control",
                                  tasks=[entry.TASK], opens_per_task=1)
    output, service = run_root / "ranking", run_root / "service"
    private = dict(
        output_root=str(output), service_dir=str(service), code_root=str(code_root),
        runtime_python=old["runtime_python"], runtime_roots=old["runtime_roots"],
        preparation_path=relocate(old["preparation_path"]), static_source=old["static_source"],
        static_receipt=relocate(old["static_receipt"]), control_completion=str(report_b),
        tasks={entry.TASK: dict(checkpoint_path=str(checkpoint), dev_report_path=str(dev_report))},
        scientific_files=science, metadata_files=metas,
        source_roots=[relocate(p) for p in old["source_roots"]] + [str(report_b.parent), str(a20_output)],
    )
    model = dict(
        task=entry.TASK, model="B7", seed=2029, endpoint="FIXED_EPOCH_9_LAST",
        checkpoint_bytes=entry.A20_BYTES, checkpoint_sha256=entry.A20_SHA,
        dev_report_sha256=report_meta["sha256"], dev_report_bytes=report_meta["bytes"],
        dynamic_control="REAL_PHYSICAL_DOTE",
    )
    proposal = dict(
        status="PREPARED_NO_COMPUTE_AUTHORIZATION", authorized=False, authorization_scope=entry.SCOPE,
        tasks=[entry.TASK], models=[model], execution_code_commit=code_commit, code_sha256=code_sha,
        private_preparation_sha256=shared.digest(private), runtime=base["runtime"], data_identity=base["data_identity"],
        data_scope=entry.DATA_SCOPE, ranking_contract=entry.CONTRACT, budget=entry.BUDGET,
        expected_summaries={entry.TASK: saved_report["groups"]["all"]["summary"]},
        static_sha256=base["static_sha256"], scientific_choices=base["scientific_choices"],
        control_reference={k: reference[k] for k in ("proposal_sha256", "checkpoint_sha256", "completion_receipt_sha256")},
        candidate_origin_proposal_sha256=a_proposal["proposal_sha256"], final_2025_access=False,
    )
    shared.validate_scientific_manifest(proposal, private, tasks=(entry.TASK,), limits=entry.BUDGET)
    private["proposal_sha256"] = proposal["proposal_sha256"] = shared.digest(proposal)
    run_root.mkdir(exist_ok=False)
    service.mkdir()
    private_path = run_root / "PRIVATE_PREPARATION.json"
    shared.write(private_path, private)
    shared.write(public_proposal, proposal)
    shared.write(run_root / "EXECUTION_SPEC.json", dict(
        kind=entry.LAUNCH_KIND, service_dir=str(service), cwd=str(code_root),
        command=[private["runtime_python"], "-B", str(code_root / entry.ENTRY), "execute",
                 "--proposal", str(public_proposal), "--private-preparation", str(private_path),
                 "--researcher-approval", str(run_root / "RESEARCHER_APPROVAL.json")],
        environment=dict(PYTHONUTF8="1", PYTHONHASHSEED="2029", CUBLAS_WORKSPACE_CONFIG=":4096:8",
                         OMP_NUM_THREADS="1", MKL_NUM_THREADS="1"),
    ))
    return proposal["proposal_sha256"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("code-root", "run-root", "public-proposal", "b-private", "a20-output"):
        parser.add_argument("--" + flag, type=Path, required=True)
    args = parser.parse_args()
    print(prepare(args.code_root, args.run_root, args.public_proposal, args.b_private, args.a20_output))
