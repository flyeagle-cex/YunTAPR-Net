"""Prepare or execute one exactly approved ZERO_DOTE/COSINE9 control."""

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
    for child in modes.choices.values():
        child.add_argument("--proposal", type=Path, required=True)
        child.add_argument("--private-preparation", type=Path, required=True)
    args = parser.parse_args()
    for name, value in vars(args).items():
        if isinstance(value, Path):
            setattr(args, name, value.resolve())
    os.chdir(ROOT)
    from yuntapr.experimental.research_readiness import zero_cosine9_training as tasks

    if args.mode == "prepare":
        if not args.private_preparation.is_relative_to(ROOT / "docs/research_readiness/.local"):
            raise PermissionError("Private preparation must remain ignored")
        proposal, private = tasks.prepare(ROOT, args.parent_proposal, args.parent_private, args.real, args.output_root)
        for path, value in ((args.proposal, proposal), (args.private_preparation, private)):
            with path.open("x", encoding="utf-8", newline="\n") as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.write("\n")
        print(json.dumps({k: proposal[k] for k in ("status", "authorized", "proposal_sha256", "budget")}))
        return
    if not args.researcher_approval.is_file():
        raise PermissionError("New exact researcher approval is required")
    if subprocess.check_output(["git", "-C", str(ROOT), "status", "--porcelain"], text=True).strip():
        raise PermissionError("The approved execution checkout must be clean")
    commit = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    if args.mode == "worker":
        tasks.worker(ROOT, args.proposal, args.private_preparation, args.researcher_approval, commit)
    else:
        tasks.execute(ROOT, args.proposal, args.private_preparation, args.researcher_approval, commit)


if __name__ == "__main__":
    main()
