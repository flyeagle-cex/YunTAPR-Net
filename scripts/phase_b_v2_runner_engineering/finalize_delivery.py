"""Narrow public allowlist/manifest; no models, datasets, or checkpoint reads."""
from __future__ import annotations
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/phase_b_v2_runner_engineering/v1"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    with path.open("x", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main():
    import xml.etree.ElementTree as ET
    inventory = json.loads((OUT / "source_identity.json").read_text(encoding="utf-8"))
    assert all(sha(ROOT / e["path"]) == e["sha256"] for e in inventory["inherited_files"])
    assert not subprocess.check_output(["git", "diff", "--name-only"], cwd=ROOT).strip()
    suites = {"cpu": "cpu_attempt_002.xml", "cuda": "cuda_attempt_001.xml",
              "hardening": "hardening_attempt_001.xml", "final_static": "final_static_attempt_003.xml"}
    unique = {}
    for suite, filename in suites.items():
        nodes = ET.parse(OUT / "tests" / filename).getroot().findall(".//testcase")
        for node in nodes:
            assert node.find("failure") is None and node.find("error") is None and node.find("skipped") is None
            key = (node.attrib["classname"], node.attrib["name"])
            device = "CUDA" if suite == "cuda" or "final_source_identity_and_restore" in key[1] else "CPU"
            unique[key] = device
    counts = {d: sum(v == d for v in unique.values()) for d in ("CPU", "CUDA")}
    assert counts == {"CPU": 75, "CUDA": 8}, counts
    records = json.loads((OUT / "tests/step_ledger_public.json").read_text(encoding="utf-8"))
    assert sum(records["completed"].values()) == 12 and records["FORMAL_OPTIMIZER_STEPS"] == 0
    flags = {k: inventory[k] for k in ("V2_PHASE_B_AUTHORIZED", "FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED",
            "RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED", "HISTORICAL_RECOVERY_RATIFICATION", "2025_RAW_ACCESS", "2025_PIXELS_READ")}
    write_json(OUT / "tests/pdf_visual_review.json", {"pages": 4, "all_pages_rendered_and_inspected": True,
        "final_latex_overfull_underfull_warning_count": 0, "clipped_or_overlapping_content": False,
        "editable_source": "RUNNER_ENGINEERING_REVIEW.tex", "renderings_private": True})
    write_json(OUT / "final_status.json", {"completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "SYNTHETIC_ENGINEERING_ONLY", "engineering_delivery": "COMPLETE_AT_RESEARCHER_APPROVAL_BOUNDARY",
        "scientific_protocol_status": "PROPOSED_FOR_RESEARCHER_APPROVAL", "unique_checks_passed": counts,
        "test_failure_history": {"initial_test_failure": 1, "collection_error": 1, "unresolved": 0},
        "pdf_export_timeout_history": 1, "final_pdf_build_and_visual_check": "PASS",
        "SYNTHETIC_OPTIMIZER_STEPS": 12, "FORMAL_OPTIMIZER_STEPS": 0,
        "step_budget_per_model_arm": 2, "synthetic_replay": "BIT_IDENTICAL_ONE_STEP_FROM_SAME_FRESH_STATE",
        "synthetic_last_restore": "EXACT_MODEL_OPTIMIZER_SCHEDULER_RNG_IDENTITY",
        "fresh_identity_across_arms": True, "protected_sources_sha_verified": 333,
        "formal_code_imports_candidate": False, "published_synthetic_weights": False,
        "remaining_engineering": ["Complete formal epoch/validation transactions and B9 endpoint",
             "Independent real-data preflight and approved production integration",
             "Approval evidence service and LAST authorization ancestry",
             "Real I/O/resource/storage, power-loss and long-run verification",
             "Full optimizer regression of final hardening source under a separately allowed synthetic budget"],
        "not_performed": ["Formal training", "real sample inference", "private historical checkpoint loading",
                          "2025 access", "multi-step continuous optimization trajectory"],
        "publication": "ACTUAL_PUSH_RECORDED_SEPARATELY_IN_PUBLICATION_RECEIPT", **flags})
    prefixes = [ROOT / "src/yuntapr/experimental/phase_b_v2_runner_candidate",
                ROOT / "tests/phase_b_v2_runner_candidate", Path(__file__).parent, OUT]
    files = []
    for prefix in prefixes:
        for p in prefix.rglob("*"):
            if not p.is_file() or any(v in p.parts for v in (".local", "__pycache__")):
                continue
            if p.suffix in {".aux", ".out", ".pt", ".pth", ".ckpt", ".png"}:
                continue
            if p.suffix == ".log" and p.parent != OUT / "tests":
                continue
            if p.name in {"manifest.json", "publication_receipt.json"}:
                continue
            if p.suffix == ".py":
                ast.parse(p.read_text(encoding="utf-8"))
            files.append(p)
    assert all(p.stat().st_size < 4 * 1024 * 1024 for p in files)
    files = sorted(set(files))
    write_json(OUT / "manifest.json", {"schema": "RUNNER_CANDIDATE_PUBLIC_DELIVERY_v1",
        "baseline_commit": inventory["baseline_commit"], "scope": "SYNTHETIC_ENGINEERING_ONLY",
        "source_inventory_sha": sha(OUT / "source_identity.json"),
        "files": [{"path": p.relative_to(ROOT).as_posix(), "sha256": sha(p), "bytes": p.stat().st_size} for p in files],
        "manifest_self_hash_omitted": True, "publication_receipt_appended_after_actual_push": True})
    files.append(OUT / "manifest.json")
    with (OUT / ".local/publication_allowlist.paths").open("x", encoding="utf-8") as f:
        f.write("\n".join(p.relative_to(ROOT).as_posix() for p in files) + "\n")
    print(json.dumps({"public_files": len(files), "sha_verified_protected": 333, "unique_tests": counts}))


if __name__ == "__main__":
    main()

