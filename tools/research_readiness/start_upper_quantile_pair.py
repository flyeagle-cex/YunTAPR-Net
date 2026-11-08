"""Prepare or dispatch one externally approved B7 E0/UQ_MILD_V1 pair."""

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
    parser = argparse.ArgumentParser()
    modes = parser.add_subparsers(dest="mode", required=True)
    prepare_parser = modes.add_parser("prepare")
    prepare_parser.add_argument("--parent-proposal", type=Path, required=True)
    prepare_parser.add_argument("--parent-private", type=Path, required=True)
    prepare_parser.add_argument("--output-root", type=Path, required=True)
    for mode in ("execute", "worker"):
        child = modes.add_parser(mode)
        child.add_argument("--researcher-approval", type=Path, required=True)
        if mode == "worker":
            child.add_argument("--task-index", type=int, choices=(0, 1), required=True)
    for child in modes.choices.values():
        child.add_argument("--proposal", type=Path, required=True)
        child.add_argument("--private-preparation", type=Path, required=True)
    args = parser.parse_args()
    for key in ("proposal", "private_preparation", "researcher_approval", "parent_proposal", "parent_private", "output_root"):
        if hasattr(args, key):
            setattr(args, key, getattr(args, key).resolve())
    os.chdir(ROOT)
    from yuntapr.experimental.research_readiness import upper_quantile_training as tasks

    if args.mode == "prepare":
        if not args.private_preparation.is_relative_to(ROOT / "docs/research_readiness/.local"):
            raise PermissionError("Private preparation must remain ignored")
        public, private = tasks.prepare(ROOT, args.parent_proposal, args.parent_private, args.output_root)
        for path, value in ((args.proposal, public), (args.private_preparation, private)):
            with path.open("x", encoding="utf-8", newline="\n") as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.write("\n")
        print(json.dumps({key: public[key] for key in ("status", "authorized", "proposal_sha256", "budget")}))
        return
    if subprocess.check_output(["git", "-C", str(ROOT), "status", "--porcelain"], text=True).strip():
        raise PermissionError("The exact reviewed execution copy must be clean")
    commit = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    if args.mode == "worker":
        tasks.worker(ROOT, args.proposal, args.private_preparation, args.researcher_approval, commit, args.task_index)
    else:
        tasks.execute(ROOT, args.proposal, args.private_preparation, args.researcher_approval, commit)


if __name__ == "__main__":
    main()
