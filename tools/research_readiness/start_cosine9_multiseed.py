"""Prepare or execute the exactly approved four-task COSINE9 REAL/ZERO package."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.dont_write_bytecode = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    prepare = modes.add_parser("prepare")
    for flag in ("parent-proposal", "parent-private", "real", "output-root"):
        prepare.add_argument("--" + flag, type=Path, required=True)
    for mode in ("execute", "worker"):
        modes.add_parser(mode).add_argument("--researcher-approval", type=Path, required=True)
    modes.choices["worker"].add_argument("--task-index", type=int, required=True)
    for child in modes.choices.values():
        child.add_argument("--proposal", type=Path, required=True)
        child.add_argument("--private-preparation", type=Path, required=True)
    args = parser.parse_args()
    for name, value in vars(args).items():
        if isinstance(value, Path):
            setattr(args, name, value.resolve())
    os.chdir(ROOT)
    from yuntapr.experimental.research_readiness import cosine9_multiseed as tasks

    if args.mode == "prepare":
        namespace = args.proposal.parent
        if (not namespace.is_relative_to(ROOT / "docs/research_readiness/.local")
                or args.private_preparation.parent != namespace or namespace.exists()):
            raise PermissionError("A fresh ignored namespace is required")
        proposal, private = tasks.prepare(ROOT, args.parent_proposal, args.parent_private, args.real,
                                          args.output_root)
        namespace.mkdir(parents=True, exist_ok=False)
        (namespace / "service").mkdir(exist_ok=False)
        spec = tasks.execution_spec(ROOT, proposal, namespace)
        for path, value in ((args.proposal, proposal), (args.private_preparation, private),
                            (namespace / "EXECUTION_SPEC.json", spec)):
            with path.open("x", encoding="utf-8", newline="\n") as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.write("\n")
        print(json.dumps({key: proposal[key] for key in
                          ("status", "authorized", "proposal_sha256", "budget", "tasks")}
                         | {"execution_spec": str(namespace / "EXECUTION_SPEC.json")}))
        return
    if not args.researcher_approval.is_file():
        raise PermissionError("New exact researcher approval is required")
    if subprocess.check_output(["git", "-C", str(ROOT), "status", "--porcelain"], text=True).strip():
        raise PermissionError("The approved execution checkout must be clean")
    commit = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    if args.mode == "worker":
        tasks.worker(ROOT, args.proposal, args.private_preparation, args.researcher_approval, commit,
                     args.task_index)
    else:
        tasks.execute(ROOT, args.proposal, args.private_preparation, args.researcher_approval, commit)


if __name__ == "__main__":
    main()
