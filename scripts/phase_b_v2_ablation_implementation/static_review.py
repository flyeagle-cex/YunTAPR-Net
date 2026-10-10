"""Read only allowed source/metadata; never import a model or candidate loss."""
from pathlib import Path
import argparse
import ast
import hashlib
import json
import subprocess

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "docs/phase_b_v2_ablation_implementation/v1"
SOURCE = REPO / "src/yuntapr/experimental/phase_b_v2_ablations"
BASELINE = "c6d938f4afc7780b29caf3ae84cfc2ef8ff70ed9"


def main(attempt: int) -> None:
    checks = []
    def check(name, value, details=None):
        checks.append({"name": name, "status": "PASS" if value else "FAIL", "details": details})
    previous = REPO / "docs/phase_b_v2_ablation_preregistration/v1"
    refs = json.loads((previous / "source_identity.json").read_text(encoding="utf-8"))["repository_files"]
    observed = []
    for ref in refs:
        path = (REPO / ref["path"]).resolve()
        if not path.is_relative_to(REPO.resolve()) or path.suffix not in {".py", ".json", ".md", ".yaml", ".csv"}:
            raise ValueError("Unexpected source reference path")
        observed.append(hashlib.sha256(path.read_bytes()).hexdigest() == ref["sha256"])
    check("41_inherited_source_metadata_byte_pins", len(refs) == 41 and all(observed))
    proposal = json.loads((previous / "protocol_proposed.json").read_text(encoding="utf-8"))
    check("science_proposal_still_unapproved", proposal["status"] == "PROPOSED_FOR_RESEARCHER_APPROVAL" and
          proposal["governance"]["V2_PHASE_B_AUTHORIZED"] is False and all(v is None for v in proposal["approvals"].values()))
    changed = subprocess.check_output(["git", "diff", BASELINE, "--name-only", "--", "src", "config", "docs/v2_scientific_acceptance",
        "docs/phase_a_evidence_hardening", "docs/phase_b_v2_protocol_candidates", "docs/phase_b_v2_ablation_preregistration"], cwd=REPO).decode().splitlines()
    check("no_frozen_or_historical_diff", all(p.startswith("src/yuntapr/experimental/") for p in changed), changed)
    configs = ast.parse((SOURCE / "config.py").read_text(encoding="utf-8"))
    constants = {node.targets[0].id: ast.literal_eval(node.value) for node in configs.body if isinstance(node, ast.Assign)
                 and isinstance(node.targets[0], ast.Name)}
    params = {a["id"]: (a["alpha"], a["gamma"], a["lambda_q"]) for a in proposal["arms"]}
    check("code_conditions_match_machine_preregistration", constants["_PARAMETERS"] == params)
    check("models_seeds_match_machine_preregistration", constants["MODELS"] == tuple(proposal["models"]) and
          constants["SEEDS"] == tuple(proposal["controls"]["seeds"]))
    check("fixed_budget_original_LR_proposal", proposal["controls"]["training"]["total_updates"] == 47052 and
          proposal["controls"]["scheduler"]["U"] == 261400 and len(proposal["runs"]) == 18)
    bad_imports, bad_calls, count = [], [], 0
    allowed_guard = "yuntapr.models.quantile_v2.outputs"
    for path in sorted(SOURCE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8")); count += 1
        for node in ast.walk(tree):
            imports = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            for name in imports:
                if name.startswith(("yuntapr.data", "yuntapr.training", "yuntapr.contracts", "torch.optim", "netCDF4", "xarray", "h5py")):
                    bad_imports.append(name)
                if name.startswith("yuntapr.models") and name != allowed_guard: bad_imports.append(name)
            if isinstance(node, ast.Call):
                symbol = node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id if isinstance(node.func, ast.Name) else ""
                if symbol in {"step", "expm1", "load_state_dict", "save", "load", "open"}: bad_calls.append(symbol)
    check("candidate_modules_parse", count == 8, {"modules": count})
    check("no_data_models_optimizer_imports", not bad_imports, bad_imports)
    check("no_optimizer_physical_or_state_file_calls", not bad_calls, bad_calls)
    readiness = ast.parse((SOURCE / "readiness.py").read_text(encoding="utf-8"))
    runner = next(n for n in readiness.body if isinstance(n, ast.ClassDef) and n.name == "BlockedRunner")
    run = next(n for n in runner.body if isinstance(n, ast.FunctionDef) and n.name == "run")
    check("runner_unconditionally_raises", len(run.body) == 1 and isinstance(run.body[0], ast.Raise))
    check("formal_sources_do_not_import_candidate", not any("experimental.phase_b_v2_ablations" in p.read_text(encoding="utf-8")
          for p in (REPO / "src/yuntapr").rglob("*.py") if "experimental" not in p.parts))
    report = {"scope": "STATIC_ONLY_NOT_ACTUAL_DATA_PREFLIGHT", "checks": checks,
              "passed": sum(c["status"] == "PASS" for c in checks), "failed": sum(c["status"] == "FAIL" for c in checks),
              "can_launch_formal_training": False, "raw_files_opened": 0, "checkpoint_files_opened": 0}
    path = OUT / f"tests/static_attempt_{attempt:03d}.json"
    with path.open("x", encoding="utf-8") as stream: json.dump(report, stream, indent=2)
    print(json.dumps(report))
    if report["failed"]: raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--attempt", type=int, required=True)
    main(parser.parse_args().attempt)
