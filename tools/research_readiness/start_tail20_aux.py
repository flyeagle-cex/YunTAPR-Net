"""Prepare and execute a fixed COSINE9-matched point or tail objective."""

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Callable


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from tools.research_readiness.start_independent_process import host_identity, require_independent
from yuntapr.experimental.core_innovation.stage3.planning import digest
from yuntapr.experimental.core_innovation.stage4.data import read, sha
from yuntapr.experimental.core_innovation.stage4.engine import resources, write
from yuntapr.experimental.phase_b_v2_ablations.schedule import COSINE9, schedule_identity
from yuntapr.experimental.phase_b_v2_ablations.tail20_aux import TAIL20_PROFILE, profile_identity
from yuntapr.experimental.phase_b_v2_ablations.point_a20_aux import POINT_A20_PROFILE, profile_identity as point_a20_identity
from yuntapr.experimental.research_readiness.dynamic_training import run_task, runtime_binding
from yuntapr.experimental.research_readiness.multiseed import load_inherited
from yuntapr.experimental.research_readiness.physical_pinball_training import control_binding
from yuntapr.experimental.research_readiness.physical_pinball_training import code_hashes as inherited_hashes
from yuntapr.experimental.research_readiness.cosine9_training import budget as cosine_budget
from yuntapr.experimental.research_readiness.static_training import validate_approval
from yuntapr.experimental.research_readiness.tail20_evaluation import Tail20Observer


ENTRY = "tools/research_readiness/start_tail20_aux.py"
BASE = "docs/research_readiness/"
PARENT = BASE + "20261110_cosine9/EXECUTION_PROPOSAL.json"
BASELINE = BASE + "20261119_conditional_intensity_diagnostic/CONDITIONAL_TAIL_BASELINE.json"
CONTRACT = BASE + "20261119_conditional_intensity_diagnostic/CONDITIONAL_TAIL_V1.md"
GUARD_REFERENCE = BASE + "20261115_mountain_pair_prepare/EXECUTION_PROPOSAL.json"
GUARD_REFERENCE_SHA = "85bc55e0101823b1291c3923c85685a7ad50315797327b9eae410f2fe49bdf61"
GUARD_FILES = (
    "src/yuntapr/experimental/core_innovation/stage2/environment.py",
    "src/yuntapr/experimental/core_innovation/stage4/data.py",
    "src/yuntapr/experimental/research_readiness/dynamic_terrain.py",
)
SCOPE = "TAIL20_AUX_V1_REAL_COSINE9_MATCHED"
TASKS = [{"model": "B7", "seed": 2029, "quantile_profile": TAIL20_PROFILE, "schedule_profile": COSINE9}]
FILES = (ENTRY, BASELINE, CONTRACT, GUARD_REFERENCE, "tools/research_readiness/mountain_pair_metrics.py",
         "tools/research_readiness/conditional_tail_gate.py")
CHOICE_KEYS = ("DOTE", "channels", "normalization", "spatial_operator", "scales", "condition_channels",
               "projection_width", "modulation_limit", "condition_mask", "precision", "architecture")
POINT_DESIGN = BASE + "20261119_conditional_intensity_diagnostic/A20_BISIDE_V1.json"
POINT_LOSS = "src/yuntapr/experimental/phase_b_v2_ablations/point_a20_aux.py"
RECOVERY_DEPENDENCY = "src/yuntapr/experimental/core_innovation/stage4/recovery.py"
REVIEWED_RECOVERY_SHA = "33fb7e473a3e0f39459512924bb1a28dbdfb049742e6bd4b541150ef4acb148b"


@dataclass(frozen=True)
class MatchedArm:
    entry: str
    scope: str
    profile: str
    loss_identity: Callable[[], dict]
    intervention: str
    wall_seconds: int

    @property
    def tasks(self):
        return [{"model": "B7", "seed": 2029, "quantile_profile": self.profile, "schedule_profile": COSINE9}]


TAIL20_ARM = MatchedArm(ENTRY, SCOPE, TAIL20_PROFILE, profile_identity,
                        "ADD_STRONG_TRUTH_PHYSICAL_PINBALL_OVER20", 21600)
POINT_A20_ARM = MatchedArm("tools/research_readiness/start_a20_biside.py",
                           "A20_BISIDE_V1_REAL_COSINE9_MATCHED", POINT_A20_PROFILE, point_a20_identity,
                           "ADD_TWO_SIDED_SUPERVISION_ON_FIXED_POINT_A", 28800)


def clean_commit():
    def git(*args):
        return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()
    if git("status", "--porcelain"):
        raise PermissionError("A clean fixed execution checkout is required")
    return git("rev-parse", "HEAD")


def code_hashes(arm=TAIL20_ARM):
    names = FILES
    if arm == POINT_A20_ARM:
        names += (arm.entry, POINT_DESIGN, POINT_LOSS, RECOVERY_DEPENDENCY,
                  "tools/research_readiness/start_independent_process.py")
    return inherited_hashes(ROOT) | {name: sha(ROOT / name) for name in names}


def budget(prepared, arm=TAIL20_ARM):
    return dict(cosine_budget(prepared), extra_development_passes=0,
                max_model_seconds=arm.wall_seconds, max_package_seconds=arm.wall_seconds,
                logical_source_scope="FROZEN_WEATHER_AND_STATIC; INHERITED_METADATA_POLICY")


def matched_guard_hashes():
    reference = read(ROOT / GUARD_REFERENCE)
    saved = reference.pop("proposal_sha256")
    if saved != GUARD_REFERENCE_SHA or digest(reference) != saved:
        raise ValueError("The successful mountain evaluation guard reference changed")
    return {name: reference["code_sha256"][name] for name in GUARD_FILES}


def arm_guard_hashes(arm):
    guards = matched_guard_hashes()
    if arm == POINT_A20_ARM:
        # The completed, separately reviewed replay changed the shared recovery module.
        # The new A20 arm is origin-only and pins that previously reviewed version.
        guards[RECOVERY_DEPENDENCY] = REVIEWED_RECOVERY_SHA
    return guards


def point_design_choices():
    design = read(ROOT / POINT_DESIGN)
    acceptance = design["predeclared_acceptance"]
    if (design["status"] != "SYNTHETIC_VALIDATED" or design["candidate"] != point_a20_identity()
            or design["implementation"][POINT_LOSS] != sha(ROOT / POINT_LOSS)
            or acceptance["frozen_baseline_sha256"] != sha(ROOT / BASELINE)
            or acceptance["point_a_tp_minimum"] != 1 or acceptance["point_a_fp_maximum"] != 0):
        raise ValueError("The validated A20 point design differs from the fixed implementation")
    return dict(point_design_sha256=sha(ROOT / POINT_DESIGN),
                acceptance="PASS_DEV_TAIL_GATE_AND_POINT_A_DETECTION_RESTORED",
                checkpoint_publication="ATOMIC_E9_BEFORE_DEVELOPMENT")


def reserve_disk(output, caps):
    if output.exists() or not output.parent.is_dir():
        raise PermissionError("Use a fresh output namespace under the bound parent")
    if shutil.disk_usage(output.parent).free < caps["initial_free_bytes"]:
        raise RuntimeError("24 GiB available disk space required")


def verify_admission(control):
    admission = resources()
    if any(admission[key] != value for key, value in control["hardware_binding"].items()):
        raise RuntimeError("The saved control GPU identity differs")
    return admission


def prepare(parent_private, output, service, *, arm=TAIL20_ARM):
    commit = clean_commit()
    parent_file = ROOT / PARENT
    parent, old = read(parent_file), read(parent_private)
    if (old["proposal_sha256"] != parent["proposal_sha256"]
            or sha(old["inherited"]) != old["inherited_file_sha256"]):
        raise ValueError("Frozen COSINE9 parent binding differs")
    control = Path(old["output_root"]) / "B7_s2029"
    guards = arm_guard_hashes(arm)
    binding = control_binding(ROOT, parent_file, control, guard_hashes=guards)
    _, prepared = load_inherited(old["inherited"])
    if prepared["data"] != parent["data"]:
        raise ValueError("The inherited Development/Train identity differs")
    caps = budget(prepared, arm)
    reserve_disk(output, caps)
    if not service.is_dir() or any(service.iterdir()):
        raise PermissionError("An empty fixed service namespace is required")
    admission = verify_admission(binding)
    choices = {key: parent["scientific_choices"][key] for key in CHOICE_KEYS}
    choices.update(only_intervention=arm.intervention,
                   candidate_loss=arm.loss_identity(), candidate_schedule=schedule_identity(),
                   origin_reference={"B7": binding["origin"]}, control_reuse=binding,
                   conditional_tail_baseline_sha256=sha(ROOT / BASELINE),
                   post_control_input_guard_sha256=guards,
                   final_dev_observer="EXISTING_E9_FORWARD_NO_EXTRA_PASS")
    if arm == POINT_A20_ARM:
        choices.update(point_design_choices())
    private = dict(output_root=str(output), service_dir=str(service),
                   inherited=old["inherited"], inherited_file_sha256=old["inherited_file_sha256"],
                   terrain=old["terrain"], control=str(control))
    proposal = dict(
        status="READY_WAITING_EXACT_RESEARCHER_APPROVAL", authorized=False, authorization_scope=arm.scope,
        execution_code_commit=commit, tasks=arm.tasks,
        protocol=dict(parent["protocol"], quantile_profile=arm.profile),
        data=prepared["data"], static_source_sha256=parent["static_source_sha256"],
        source_scope_summary=parent["source_scope_summary"], scientific_choices=choices,
        budget=caps, runtime_binding=binding["runtime_binding"], code_sha256=code_hashes(arm),
        private_preparation_sha256=digest(private), parent_proposal_sha256=sha(parent_file),
        admission_snapshot=admission, final_2025_access=False,
        preparation_activity=dict(raw_payload_opens=0, checkpoint_loads=0, optimizer_updates=0),
    )
    proposal["proposal_sha256"] = digest(proposal)
    private["proposal_sha256"] = proposal["proposal_sha256"]
    return proposal, private


def checked(p, v, approval, commit, *, arm=TAIL20_ARM):
    validate_approval(approval, p, v, commit)
    if (p.get("execution_code_commit") != commit or p.get("authorization_scope") != arm.scope
            or p.get("tasks") != arm.tasks or p.get("final_2025_access") is not False
            or p["protocol"] != dict(read(ROOT / PARENT)["protocol"], quantile_profile=arm.profile)
            or p["scientific_choices"]["candidate_loss"] != arm.loss_identity()
            or p["scientific_choices"]["only_intervention"] != arm.intervention
            or p["scientific_choices"]["candidate_schedule"] != schedule_identity()
            or p["scientific_choices"]["post_control_input_guard_sha256"] != arm_guard_hashes(arm)
            or p["scientific_choices"]["final_dev_observer"] != "EXISTING_E9_FORWARD_NO_EXTRA_PASS"):
        raise PermissionError("Only the exact approved B7 origin-only candidate is admitted")
    if arm == POINT_A20_ARM and any(p["scientific_choices"].get(key) != value
                                   for key, value in point_design_choices().items()):
        raise PermissionError("The fixed A20 gate and checkpoint order must match the proposal")
    key = "proposal_sha256"
    if (digest({k: x for k, x in p.items() if k != key}) != p[key] or v[key] != p[key]
            or digest({k: x for k, x in v.items() if k != key}) != p["private_preparation_sha256"]):
        raise PermissionError("Proposal or private identity changed")
    if (p["code_sha256"] != code_hashes(arm) or sha(ROOT / PARENT) != p["parent_proposal_sha256"]
            or sha(ROOT / BASELINE) != p["scientific_choices"]["conditional_tail_baseline_sha256"]
            or runtime_binding() != p["runtime_binding"] or sha(v["inherited"]) != v["inherited_file_sha256"]
            or any(sha(ROOT / name) != expected for name, expected in arm_guard_hashes(arm).items())):
        raise ValueError("Bound code, receipts, runtime or inherited source manifest changed")
    _, prepared = load_inherited(v["inherited"])
    if prepared["data"] != p["data"] or budget(prepared, arm) != p["budget"]:
        raise ValueError("Frozen population or budget changed")
    for filename, identity in p["scientific_choices"]["control_reuse"]["metadata_files"].items():
        file = Path(v["control"]) / filename
        if file.stat().st_size != identity["bytes"] or sha(file) != identity["sha256"]:
            raise ValueError("Matched control metadata changed")
    return prepared


def point_completion(folder, gate, p):
    checkpoint = folder / "B7_PREDEV_epoch_09.pt"
    seal = read(checkpoint.with_suffix(".receipt.json"))
    training = read(folder / "B7_train_09.json")
    if (seal["status"] != "SEALED_TRAIN_BEFORE_DEV" or (seal["model"], seal["epoch"]) != ("B7", 9)
            or seal["updates"] != p["budget"]["total_updates"]
            or seal["population_sha256"] != p["data"]["population_sha256"]
            or seal["code_commit"] != p["execution_code_commit"] or seal["loss_config"] != point_a20_identity()
            or seal["schedule"] != schedule_identity() or seal["checkpoint_bytes"] != checkpoint.stat().st_size
            or seal["train_receipt_sha256"] != digest(training)):
        raise RuntimeError("A20 E9 pre-Development checkpoint seal differs")
    comparison = gate["comparison"]
    passed = comparison["status"] == "PASS_DEV_TAIL_GATE" and comparison["point_a_detection_restored"] is True
    return dict(point_a20_status="PASS_DEV_POINT_A20_GATE" if passed else "FAIL_DEV_POINT_A20_GATE",
                predev_checkpoint_sha256=seal["checkpoint_sha256"], final_2025_access=False)


def execute(p, v, approval, commit, *, arm=TAIL20_ARM):
    started = time.monotonic()
    require_independent(host_identity())
    prepared = checked(p, v, approval, commit, arm=arm)
    package = Path(v["output_root"])
    reserve_disk(package, p["budget"])
    volumes = {Path(name).anchor for scope in prepared["roles"].values() for name in scope["files"]}
    if not volumes or any(not Path(volume).is_dir() for volume in volumes):
        raise RuntimeError("A frozen source volume is unavailable")
    if os.environ.get("PYTHONHASHSEED") != "2029":
        raise PermissionError("Frozen process seed required")
    if arm == POINT_A20_ARM:
        service = Path(v["service_dir"])
        launch = read(service / "target_launch.json")
        claim = read(service / "independent_launch_claim.json")
        if ((launch["pid"], launch["supervisor_pid"]) != (os.getpid(), os.getppid())
                or launch["kind"] != "BOUNDED_A20_BISIDE_TRAINING"
                or launch["spec_sha256"] != claim["spec_sha256"]
                or launch["automatic_retry"] is not False or claim["automatic_retry"] is not False):
            raise PermissionError("A live one-shot A20 supervisor is required")
    admission = verify_admission(p["scientific_choices"]["control_reuse"])
    baseline = read(ROOT / BASELINE)
    package.mkdir(exist_ok=False)
    try:
        write(package / "authorization_binding.json", dict(
            approval=approval, code_commit=commit, controller_pid=os.getpid(), admission=admission))
        result = run_task(
            ROOT, p, v, approval, prepared, commit, "B7", 2029, started=started,
            pair_reference=Path(v["control"]), static_name="B7_static_source.sqlite",
            quantile_profile=arm.profile, schedule_profile=COSINE9,
            final_dev_observer_factory=lambda pack, ids: Tail20Observer(pack, ids, baseline),
        )
        caps = p["budget"]
        if (result["status"] != "COMPLETE_TRAIN_AND_DEV_EVALUATION" or result["code_commit"] != commit
                or result["optimizer_updates"] != caps["total_updates"] or result["replay"] != 0
                or result["total_logical_source_bytes"] != caps["total_source_bytes"]
                or result["total_logical_source_files"] != caps["total_source_files"]
                or result.get("schedule") != schedule_identity()):
            raise RuntimeError("The matched candidate endpoint differs from the bound run")
        folder = package / "B7_s2029"
        gate = read(folder / "B7_tail20_gate_09.json")
        checkpoint = read(folder / "B7_LAST_epoch_09.receipt.json")
        completion = dict(
            status="COMPLETE_TRAIN_AND_DEV_EVALUATION", execution_code_commit=commit,
            proposal_sha256=p["proposal_sha256"], checkpoint_sha256=checkpoint["checkpoint_sha256"],
            optimizer_updates=result["optimizer_updates"], source_bytes=result["total_logical_source_bytes"],
            source_files=result["total_logical_source_files"], gate=gate, automatic_retry=False)
        if arm == POINT_A20_ARM:
            completion.update(point_completion(folder, gate, p))
        write(package / "completion.json", completion)
    except BaseException as error:
        write(package / "failure.json", dict(status="STOP_NO_AUTOMATIC_RETRY",
              error_type=type(error).__name__, details=str(error)))
        raise


def main(*, arm=TAIL20_ARM):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    prep, launch = sub.add_parser("prepare"), sub.add_parser("execute")
    for child in (prep, launch):
        child.add_argument("--proposal", type=Path, required=True)
        child.add_argument("--private-preparation", type=Path, required=True)
    for name in ("parent-private", "output-root", "service-dir"):
        prep.add_argument("--" + name, type=Path, required=True)
    launch.add_argument("--researcher-approval", type=Path, required=True)
    args = parser.parse_args()
    if args.mode == "prepare":
        if not all(".local" in target.resolve().parts for target in
                   (args.output_root, args.service_dir, args.private_preparation)):
            raise PermissionError("Use ignored local execution paths")
        if args.proposal.exists() or args.private_preparation.exists():
            raise FileExistsError("Preparation files must use fresh names")
        p, v = prepare(args.parent_private.resolve(), args.output_root.resolve(), args.service_dir.resolve(), arm=arm)
        write(args.proposal, p)
        write(args.private_preparation, v)
        print(json.dumps(dict(proposal_sha256=p["proposal_sha256"], execution_code_commit=p["execution_code_commit"],
                              budget=p["budget"], authorized=False)))
    else:
        if not args.researcher_approval.is_file():
            raise PermissionError("Separate exact researcher approval is required")
        execute(read(args.proposal), read(args.private_preparation), read(args.researcher_approval), clean_commit(), arm=arm)


if __name__ == "__main__":
    main()
