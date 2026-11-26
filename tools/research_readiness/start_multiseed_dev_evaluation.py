"""Prepare/execute the bounded Stage-4 four-model Development evaluation.

This entry point deliberately exposes no training, proposal-freezing or retry
capability.  ``prepare`` writes a public proposal, a private preparation and a
supervisor specification; ``execute`` refuses to run until a researcher
approval file binds that exact proposal and commit.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

sys.dont_write_bytecode = True

from yuntapr.experimental.research_readiness import multiseed_dev_evaluation as arm


def _write(path, value):
    with open(path, "x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


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
        "models": [row["task"] for row in proposal["models"]],
        "output_root": private["output_root"],
        "service_dir": spec["service_dir"],
        "scientific_open_instances": proposal["source_scope_summary"][
            "scientific_open_instances"
        ],
        "scientific_reference_bytes": proposal["source_scope_summary"][
            "scientific_reference_bytes"
        ],
        "maximum_seconds": proposal["budget"]["maximum_seconds"],
        "authorized": proposal["authorized"],
        "final_2025_access": proposal["final_2025_access"],
    }


def prepare(args):
    proposal_path = Path(args.proposal).resolve()
    private_path = Path(args.private_preparation).resolve()
    namespace = proposal_path.parent
    arm.require_fresh_namespace(namespace, ROOT)
    if proposal_path.name != "PROPOSAL.json":
        raise PermissionError("The proposal must be written as PROPOSAL.json")
    if private_path.name != "PRIVATE_PREPARATION.json":
        raise PermissionError("The private preparation must be PRIVATE_PREPARATION.json")
    if private_path.parent != namespace:
        raise PermissionError("The private preparation must share the namespace")
    if namespace.exists():
        raise PermissionError("The preparation namespace must be fresh")
    parent_proposal = Path(args.parent_proposal).resolve()
    parent_private = Path(args.parent_private).resolve()
    package_root = Path(args.package_root).resolve()
    output_root = Path(args.output_root).resolve()
    if output_root.exists():
        raise PermissionError("The evaluation output root must be fresh")

    runtime = arm.runtime_binding()
    head = _git("rev-parse", "HEAD")
    proposal, private = arm.prepare(
        ROOT,
        parent_proposal,
        parent_private,
        package_root,
        output_root,
        runtime=runtime,
        head=head,
        service_dir=namespace / "service",
        runtime_python=sys.executable,
    )
    spec = arm.execution_spec(ROOT, proposal, namespace)
    arm.validate_entry(proposal, private, arm_stub_approval(proposal, output_root))

    namespace.mkdir(parents=True, exist_ok=False)
    (namespace / "service").mkdir(parents=False)
    _write(proposal_path, proposal)
    _write(private_path, private)
    _write(namespace / "EXECUTION_SPEC.json", spec)
    print(json.dumps(_summary(proposal, private, spec), indent=2, ensure_ascii=False))
    return 0


def arm_stub_approval(proposal, output_root):
    """A structural approval used only to exercise the read-only validators."""

    return {
        "approved_by_researcher": True,
        "authorization_scope": proposal["scope"],
        "decision_id": proposal["decision"],
        "proposal_sha256": proposal["proposal_sha256"],
        "code_commit": proposal["execution_code_commit"],
        "tasks": proposal["tasks"],
        "scientific_choices": proposal["scientific_choices"],
        "budget": proposal["budget"],
        "output_root": str(output_root),
        "researcher_instruction": "structural preflight only; not an approval",
        "final_2025_access": False,
    }


def _checked(root, proposal_path, private_path, approval_path, commit):
    proposal = _read(proposal_path)
    private = _read(private_path)
    approval = _read(approval_path)
    arm.checked(root, proposal, private, approval, commit)
    return proposal, private, approval


def execute(args):
    approval_path = Path(args.researcher_approval).resolve()
    if not approval_path.is_file():
        raise PermissionError("A researcher approval file is required")
    proposal_path = Path(args.proposal).resolve()
    private_path = Path(args.private_preparation).resolve()
    commit = _git("rev-parse", "HEAD")
    proposal, private, approval = _checked(
        ROOT, proposal_path, private_path, approval_path, commit
    )
    approval = dict(approval, path=str(approval_path))
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
        proposal_path=str(proposal_path),
        private_path=str(private_path),
        approval_path=str(approval_path),
    )
    print(
        json.dumps(
            {
                "status": completion["status"],
                "q1_summary": completion["q1_summary"],
                "scientific_acceptance": completion["scientific_acceptance"],
                "final_2025_access": completion["final_2025_access"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


def worker(args):
    approval_path = Path(args.researcher_approval).resolve()
    if not approval_path.is_file():
        raise PermissionError("A researcher approval file is required")
    proposal_path = Path(args.proposal).resolve()
    private_path = Path(args.private_preparation).resolve()
    proposal = _read(proposal_path)
    private = _read(private_path)
    approval = _read(approval_path)
    commit = _git("rev-parse", "HEAD")
    arm.task_worker(
        ROOT,
        proposal,
        private,
        approval,
        commit,
        int(args.task_index),
        seconds_cap=args.seconds_cap,
        proposal_path=str(proposal_path),
        private_path=str(private_path),
        approval_path=str(approval_path),
    )
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--proposal", required=True)
    prepare_parser.add_argument("--private-preparation", required=True)
    prepare_parser.add_argument("--parent-proposal", required=True)
    prepare_parser.add_argument("--parent-private", required=True)
    prepare_parser.add_argument("--package-root", required=True)
    prepare_parser.add_argument("--output-root", required=True)
    prepare_parser.set_defaults(handler=prepare)

    execute_parser = subparsers.add_parser("execute")
    execute_parser.add_argument("--proposal", required=True)
    execute_parser.add_argument("--private-preparation", required=True)
    execute_parser.add_argument("--researcher-approval", required=True)
    execute_parser.set_defaults(handler=execute)

    worker_parser = subparsers.add_parser("worker")
    worker_parser.add_argument("--task-index", required=True, type=int)
    worker_parser.add_argument("--seconds-cap", default=None, type=float)
    worker_parser.add_argument("--proposal", required=True)
    worker_parser.add_argument("--private-preparation", required=True)
    worker_parser.add_argument("--researcher-approval", required=True)
    worker_parser.set_defaults(handler=worker)

    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
