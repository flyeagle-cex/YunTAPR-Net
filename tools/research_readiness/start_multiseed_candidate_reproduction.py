"""Prepare or execute the frozen Stage-4 multi-seed candidate reproduction (B).

The controller writes only metadata.  It reads no array shard and no satellite
payload; the module's ``execute`` performs the bounded, guarded reads after the
researcher-approved launch.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

sys.dont_write_bytecode = True

from yuntapr.experimental.research_readiness import (  # noqa: E402
    multiseed_candidate_reproduction as arm,
)


def _write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(
            json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        )


def _read(path):
    return json.loads(Path(path).read_bytes())


def _git(*arguments):
    return subprocess.check_output(
        ["git", "-C", str(ROOT), *arguments], text=True
    ).strip()


def _summary(proposal, private, spec):
    return {
        "kind": proposal["kind"],
        "scope": proposal["scope"],
        "status": proposal["status"],
        "proposal_sha256": proposal["proposal_sha256"],
        "private_preparation_sha256": proposal["private_preparation_sha256"],
        "tasks": proposal["tasks"],
        "models": [row["checkpoint_sha256"] for row in proposal["models"]],
        "output_root": private["output_root"],
        "service_dir": private["service_dir"],
        "scientific_open_instances": proposal["budget"]["scientific_file_opens"],
        "scientific_reference_bytes": proposal["budget"]["scientific_source_bytes"],
        "total_scientific_file_opens": proposal["budget"][
            "total_scientific_file_opens"
        ],
        "total_scientific_source_bytes": proposal["budget"][
            "total_scientific_source_bytes"
        ],
        "maximum_seconds": proposal["budget"]["maximum_seconds"],
        "authorized": proposal["authorized"],
        "final_2025_access": proposal["final_2025_access"],
        "spec_environment": spec["environment"],
    }


def arm_stub_approval(proposal, output_root):
    return {
        "approved_by_researcher": True,
        "authorization_scope": proposal["scope"],
        "decision_id": proposal["decision"],
        "proposal_sha256": proposal["proposal_sha256"],
        "code_commit": proposal["execution_code_commit"],
        "tasks": proposal["tasks"],
        "scientific_choices": proposal["scientific_choices"],
        "budget": proposal["budget"],
        "output_root": str(Path(output_root)),
        "researcher_instruction": "structural preflight only; not an approval",
        "final_2025_access": False,
    }


def prepare(args):
    proposal_path = Path(args.proposal).resolve()
    private_path = Path(args.private_preparation).resolve()
    namespace = proposal_path.parent
    arm.require_fresh_namespace(namespace, ROOT)
    if proposal_path.name != "PROPOSAL.json":
        raise ValueError("The proposal must be named PROPOSAL.json")
    if private_path.name != "PRIVATE_PREPARATION.json":
        raise ValueError("The private preparation must be named PRIVATE_PREPARATION.json")
    if private_path.parent != namespace:
        raise ValueError("The proposal and private preparation must share a namespace")
    parent_results = Path(args.parent_results).resolve()
    arrays_root = Path(args.arrays_root).resolve()
    output_root = Path(args.output_root).resolve()
    if not parent_results.is_file():
        raise ValueError("The package-A results JSON is missing")
    if not arrays_root.is_dir():
        raise ValueError("The package-A arrays root is missing")
    arm.require_fresh_output(output_root)
    runtime = arm.runtime_binding(sys.executable)
    head = _git("rev-parse", "HEAD")
    proposal, private = arm.prepare(
        ROOT,
        parent_results,
        arrays_root,
        output_root,
        proposal_path,
        private_path,
        head=head,
        runtime_python=sys.executable,
        service_dir=namespace / "service",
    )
    if proposal["runtime_binding"] != runtime:
        raise ValueError("The prepared runtime binding differs from this interpreter")
    spec = arm.execution_spec(ROOT, proposal, namespace)
    arm.validate_entry(proposal, private, arm_stub_approval(proposal, output_root))
    namespace.mkdir(parents=True, exist_ok=False)
    (namespace / "service").mkdir(parents=False)
    _write(proposal_path, proposal)
    _write(private_path, private)
    _write(namespace / "EXECUTION_SPEC.json", spec)
    print(json.dumps(_summary(proposal, private, spec), indent=2, ensure_ascii=False))
    return 0


def _checked(root, proposal_path, private_path, approval_path, commit):
    proposal = _read(proposal_path)
    private = _read(private_path)
    approval = _read(approval_path)
    return arm.checked(root, proposal, private, approval, commit)


def execute(args):
    proposal_path = Path(args.proposal).resolve()
    private_path = Path(args.private_preparation).resolve()
    approval_path = Path(args.researcher_approval).resolve()
    if not approval_path.is_file():
        raise PermissionError("A researcher approval file is required")
    commit = _git("rev-parse", "HEAD")
    _checked(ROOT, proposal_path, private_path, approval_path, commit)
    proposal = _read(proposal_path)
    private = _read(private_path)
    approval = dict(_read(approval_path), path=str(approval_path))
    print(
        json.dumps(
            {
                "kind": proposal["kind"],
                "proposal_sha256": proposal["proposal_sha256"],
                "code_commit": commit,
                "tasks": proposal["tasks"],
                "maximum_seconds": proposal["budget"]["maximum_seconds"],
            },
            indent=2,
        )
    )
    completion = arm.execute(
        ROOT,
        proposal,
        private,
        approval,
        commit,
        proposal_path=proposal_path,
        private_path=private_path,
        approval_path=approval_path,
    )
    print(
        json.dumps(
            {
                "status": completion["status"],
                "decision": completion["decision"],
                "q2_decision": completion["q2_decision"],
                "q3_decision": completion["q3_decision"],
                "scientific_acceptance": completion["scientific_acceptance"],
                "final_2025_access": completion["final_2025_access"],
            },
            indent=2,
        )
    )
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--proposal", required=True)
    prepare_parser.add_argument("--private-preparation", required=True)
    prepare_parser.add_argument("--parent-results", required=True)
    prepare_parser.add_argument("--arrays-root", required=True)
    prepare_parser.add_argument("--output-root", required=True)
    execute_parser = subparsers.add_parser("execute")
    execute_parser.add_argument("--proposal", required=True)
    execute_parser.add_argument("--private-preparation", required=True)
    execute_parser.add_argument("--researcher-approval", required=True)
    args = parser.parse_args(argv)
    if args.mode == "prepare":
        return prepare(args)
    return execute(args)


if __name__ == "__main__":
    raise SystemExit(main())
