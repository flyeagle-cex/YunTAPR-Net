"""Prepare a single-arm grant candidate from the saved mountain-pair bindings."""

import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.research_readiness import start_conditional_intensity_readout as entry
from tools.research_readiness import start_paired_point_evaluation as shared


PAIR_SHA = "85bc55e0101823b1291c3923c85685a7ad50315797327b9eae410f2fe49bdf61"
TOOLS = "tools/research_readiness/"
ENTRY = TOOLS + "start_conditional_intensity_readout.py"
CHANGED_FILES = {TOOLS + name for name in (
    "start_independent_process.py", "start_paired_point_evaluation.py", "paired_point_worker.py",
)}
NEW_FILES = {ENTRY, TOOLS + "conditional_intensity_readout.py",
             TOOLS + "extreme_diagnostic_candidates.py"}


def prepare(code_root, run_root, public_proposal):
    code_root, run_root, public_proposal = (p.resolve() for p in (code_root, run_root, public_proposal))
    if run_root.exists() or public_proposal.exists():
        raise FileExistsError("Choose a fresh preparation and proposal identity")
    old = shared.read(ROOT / "docs/research_readiness/20261115_mountain_pair_prepare/EXECUTION_PROPOSAL.json")
    private_old = shared.read(
        ROOT / "docs/research_readiness/.local/mountain_pair_prepare_20261115_v1/PRIVATE_PREPARATION.json")
    if (old["proposal_sha256"] != PAIR_SHA or private_old["proposal_sha256"] != PAIR_SHA
            or shared.digest({k: v for k, v in old.items() if k != "proposal_sha256"}) != PAIR_SHA
            or shared.digest({k: v for k, v in private_old.items() if k != "proposal_sha256"})
            != old["private_preparation_sha256"]):
        raise PermissionError("Saved mountain-pair bindings changed")

    def git(*args):
        return subprocess.check_output(["git", "-C", str(code_root), *args], text=True).strip()

    commit = git("rev-parse", "HEAD")
    if git("status", "--porcelain"):
        raise PermissionError("Use a clean fixed execution checkout")
    code_files = set(old["code_sha256"]) | NEW_FILES
    code_sha = {name: shared.sha(code_root / name) for name in sorted(code_files)}
    if any(code_sha[name] != sha for name, sha in old["code_sha256"].items() if name not in CHANGED_FILES):
        raise PermissionError("An inherited dependency changed outside the readout implementation")
    old_code_root = Path(private_old["code_root"]).resolve()

    def relocate(value):
        path = Path(value).resolve()
        return str(code_root / path.relative_to(old_code_root) if path.is_relative_to(old_code_root) else path)

    task = entry.TASK
    inputs = private_old["tasks"][task]
    drop = {paths["tail_report_path"] for paths in private_old["tasks"].values()}
    drop.update(paths["dev_report_path"] for name, paths in private_old["tasks"].items() if name != task)
    metadata = {
        relocate(path): info for path, info in private_old["metadata_files"].items() if path not in drop
    }
    scientific = {
        path: dict(info, tasks=[task]) for path, info in private_old["scientific_files"].items()
        if task in info["tasks"]
    }
    output = run_root / "readout"
    service = run_root / "service"
    private_file = run_root / "PRIVATE_PREPARATION.json"
    approval_file = run_root / "RESEARCHER_APPROVAL.json"
    private = dict(
        output_root=str(output), service_dir=str(service), code_root=str(code_root),
        runtime_python=private_old["runtime_python"], runtime_roots=private_old["runtime_roots"],
        preparation_path=relocate(private_old["preparation_path"]),
        static_source=private_old["static_source"], static_receipt=relocate(private_old["static_receipt"]),
        tasks={task: dict(checkpoint_path=inputs["checkpoint_path"],
                          dev_report_path=relocate(inputs["dev_report_path"]))},
        scientific_files=scientific, metadata_files=metadata,
        source_roots=[relocate(path) for path in private_old["source_roots"]],
    )
    model = next(row for row in old["models"] if row["task"] == task)
    proposal = dict(
        status="PREPARED_NO_COMPUTE_AUTHORIZATION", authorized=False,
        authorization_scope=entry.SCOPE, tasks=[task], models=[model],
        execution_code_commit=commit, code_sha256=code_sha,
        private_preparation_sha256=shared.digest(private),
        runtime=old["runtime"], data_identity=old["data_identity"], data_scope=entry.DATA_SCOPE,
        expected_summaries={task: old["expected_summaries"][task]}, static_sha256=old["static_sha256"],
        scientific_choices={key: old["scientific_choices"][key] for key in ("DOTE", "modulation_limit")},
        readout_identity=entry.READOUT_IDENTITY, budget=entry.BUDGET, final_2025_access=False,
        prior_pair_proposal_sha256=PAIR_SHA,
    )
    # Validates the saved input scope and file sizes. It never opens the archives.
    shared.validate_scientific_manifest(proposal, private, tasks=(task,), limits=entry.BUDGET)
    proposal["proposal_sha256"] = shared.digest(proposal)
    private["proposal_sha256"] = proposal["proposal_sha256"]
    run_root.mkdir(exist_ok=False)
    service.mkdir()
    shared.write(private_file, private)
    shared.write(public_proposal, proposal)
    shared.write(run_root / "EXECUTION_SPEC.json", dict(
        kind=entry.LAUNCH_KIND, service_dir=str(service), cwd=str(code_root),
        command=[private["runtime_python"], "-B", str(code_root / ENTRY), "execute",
                 "--proposal", str(public_proposal), "--private-preparation", str(private_file),
                 "--researcher-approval", str(approval_file)],
        environment=dict(PYTHONUTF8="1", PYTHONHASHSEED="2029", CUBLAS_WORKSPACE_CONFIG=":4096:8",
                         OMP_NUM_THREADS="1", MKL_NUM_THREADS="1"),
    ))
    return proposal["proposal_sha256"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("code-root", "run-root", "public-proposal"):
        parser.add_argument("--" + flag, type=Path, required=True)
    args = parser.parse_args()
    print(prepare(args.code_root, args.run_root, args.public_proposal))
