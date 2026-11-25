"""Bounded, approval-gated four-task COSINE9 REAL/ZERO multi-seed package.

The package schedules the frozen COSINE9_V1 protocol four times: one B7 origin per
seed (2030, 2031) trained as the REAL physical DOTE arm and as the ZERO numeric
control that keeps the real masks. Every task reuses the reviewed single-task
worker (``dynamic_training.run_task``) over the frozen 2023 Train / 2024
Development population, so no training loop is copied here.

Provenance chain (each link is hash-bound, none is re-derived by hand):

    UQ E0 pair (seed2029 control) -> COSINE9 REAL seed2029 -> ZERO seed2029 -> this package

Boundary notes kept explicit for the reviewer:

* ``checkpoint_loads`` is zero. Both arms start from a fresh seed-driven original
  factory state, exactly like the reviewed seed2029 COSINE9/Zero pair, so no
  checkpoint is opened; the planning sheet's "one load per task" is not what the
  frozen protocol performs (the seed2029 ZERO receipt records zero loads too).
* the four tasks are strictly serial. The first failure writes a terminal failure
  receipt and blocks every later task; there is no retry and no replay.
* the inherited seed2029 evidence is bound by canonical proposal digests, terminal
  engineering receipts and the saved metadata hashes. It is *not* bound by
  "current tree equals the 2026-11-10 tree": the reviewed 2026-11-15
  core-innovation repair changed numerical files on purpose, so the delta is
  recorded explicitly (``INHERITED_DELTA_ALLOWANCE``) instead of pretending the
  tree never moved. Any further drift fails closed until the allowance is reviewed.
"""

import copy
import gc
import hashlib
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import torch

from ..core_innovation.stage3.planning import digest
from ..core_innovation.stage4.data import PopulationPlan, read, sha
from ..core_innovation.stage4.engine import epoch_order, resources, state_digest, write
from ..phase_b_v2_ablations.schedule import COSINE9, schedule_identity
from .cosine9_training import budget as single_task_budget
from .cosine9_training import code_hashes as inherited_code_hashes
from .cosine9_training import verify_schedule_receipts
from .dote_numeric_control import ZeroNumericDote
from .dynamic_terrain import PhysicalDote, model_factory
from .dynamic_training import run_task, runtime_binding
from .multiseed import load_inherited, worker_creation_flags
from .static_training import unpack, validate_approval
from .upper_quantile_diagnostics import UpperQuantileTail

KIND = "BOUNDED_TRAIN_COSINE9_MULTISEED_TERRAIN"
SCOPE = "FOUR_TASK_COSINE9_REAL_ZERO_SEED2030_2031"
ENTRY = "tools/research_readiness/start_cosine9_multiseed.py"
MODULE = "src/yuntapr/experimental/research_readiness/cosine9_multiseed.py"
MODEL = "B7"
ARMS = ("REAL", "ZERO")
SEEDS = (2030, 2031)
DYNAMIC_CONTROL = "ZERO_NUMERIC_RETAIN_REAL_MASKS"
TASKS = [
    dict(arm=arm, model=MODEL, seed=seed, schedule_profile=COSINE9)
    for seed in SEEDS
    for arm in ARMS
]
FILES = (ENTRY, MODULE)
STATIC_BYTES = 312828
STATIC_NAME = "B6_static.npz"
REAL_PROPOSAL = "docs/research_readiness/20261110_cosine9/EXECUTION_PROPOSAL.json"
REAL_TERMINAL = "docs/research_readiness/20261110_cosine9/TERMINAL_VERIFICATION.json"
ZERO_PROPOSAL = "docs/research_readiness/20261114_zero_cosine9/EXECUTION_PROPOSAL.json"
ZERO_TERMINAL = "docs/research_readiness/20261114_zero_cosine9/TERMINAL_VERIFICATION.json"
ZERO_CODE = "b4f15fb8dfeced23c28824f04b35158077678950"
# Numerical files that moved after the inherited seed2029 proposals were frozen:
# the reviewed 2026-11-15 core-innovation repair surface, the two files this
# package widens (seed set in engine.PairedExecutor / dynamic_training.run_task)
# and the supervisor tool. Any other drift is refused.
INHERITED_DELTA_ALLOWANCE = frozenset({
    "src/yuntapr/experimental/core_innovation/gfs.py",
    "src/yuntapr/experimental/core_innovation/stage2/environment.py",
    "src/yuntapr/experimental/core_innovation/stage4/data.py",
    "src/yuntapr/experimental/core_innovation/stage4/engine.py",
    "src/yuntapr/experimental/core_innovation/stage4/launch.py",
    "src/yuntapr/experimental/core_innovation/stage4/recovery.py",
    "src/yuntapr/experimental/research_readiness/dynamic_terrain.py",
    "src/yuntapr/experimental/research_readiness/dynamic_training.py",
    "src/yuntapr/experimental/research_readiness/upper_quantile_training.py",
    "tools/research_readiness/start_independent_process.py",
})
PACKAGE_TOTALS = (17280, 1910287815360, 571252)


def code_hashes(root):
    """Current tree identity, so any later drift cannot reuse this proposal."""
    value = inherited_code_hashes(root)
    value.update({name: sha(Path(root) / name) for name in FILES})
    return value


def budget(prepared):
    """Four copies of the reviewed single-task envelope plus the package caps."""
    single = single_task_budget(prepared)
    caps = dict(
        models=len(TASKS),
        updates_per_model=single["updates_per_model"],
        total_updates=len(TASKS) * single["updates_per_model"],
        source_bytes_per_model=single["source_bytes_per_model"],
        source_files_per_model=single["source_files_per_model"],
        total_source_bytes=len(TASKS) * single["source_bytes_per_model"],
        total_source_files=len(TASKS) * single["source_files_per_model"],
        max_model_seconds=single["max_model_seconds"],
        max_package_seconds=len(TASKS) * single["max_model_seconds"],
        initial_free_bytes=48 * 1024 ** 3,
        minimum_task_free_bytes=24 * 1024 ** 3,
        replay_allowance=0,
        additional_retry_allowance=0,
        checkpoint_loads=single["checkpoint_loads"],
    )
    totals = (caps["total_updates"], caps["total_source_bytes"], caps["total_source_files"])
    if totals != PACKAGE_TOTALS:
        raise ValueError("Four-task budget differs from the declared package: " + str(totals))
    return caps


def execution_spec(root, proposal, namespace):
    """Deterministic independent-supervisor specification for the frozen package."""
    root, namespace = Path(root), Path(namespace)
    return dict(
        kind=KIND,
        cwd=str(root.resolve()),
        service_dir=str((namespace / "service").resolve()),
        command=[sys.executable, "-B", str((root / ENTRY).resolve()), "execute",
                 "--proposal", str((namespace / "PROPOSAL.json").resolve()),
                 "--private-preparation", str((namespace / "PRIVATE_PREPARATION.json").resolve()),
                 "--researcher-approval", str((namespace / "RESEARCHER_APPROVAL.json").resolve())],
        environment={"PYTHONHASHSEED": str(SEEDS[0]), "PYTHONUTF8": "1", "OMP_NUM_THREADS": "1",
                     "MKL_NUM_THREADS": "1", "CUBLAS_WORKSPACE_CONFIG": ":4096:8"},
        proposal_sha256=proposal["proposal_sha256"],
    )


def task_package(private, arm, seed):
    return Path(private["output_root"]) / f"{arm}_s{seed}"


def task_folder(private, arm, seed):
    return task_package(private, arm, seed) / f"{MODEL}_s{seed}"


def origin_entry(choices, seed):
    return choices["origin_reference"][f"{MODEL}@{seed}"]


def private_seal(private):
    """Digest of the private plan before its own proposal pointer is attached."""
    return digest({key: value for key, value in private.items() if key != "proposal_sha256"})


def initial_digest(factory, seed, root):
    """Original B7 state digest from the frozen factory; no checkpoint is loaded."""
    saved = {name: os.environ.get(name) for name in ("PYTHONHASHSEED", "CUBLAS_WORKSPACE_CONFIG")}
    os.environ["PYTHONHASHSEED"] = str(seed)
    if not os.environ.get("CUBLAS_WORKSPACE_CONFIG"):
        os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    models = None
    try:
        with torch.random.fork_rng(devices=[]):
            models = factory(seed, Path(root))
            value = state_digest(models[MODEL].state_dict())
        return value
    finally:
        if models is not None:
            models.clear()
        gc.collect()
        for name, previous in saved.items():
            if previous is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = previous


def seed_origins(root, prepared, terrain, choices, static_sha256, seeds=SEEDS):
    """Seal the seed-driven original state and the nine epoch orders per seed."""
    terrain = Path(terrain)
    receipt = read(terrain / "production_receipt.json")
    raw = (terrain / STATIC_NAME).read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if len(raw) != STATIC_BYTES or actual != static_sha256:
        raise ValueError("The static terrain pack identity differs")
    pack = unpack(raw, "B6", receipt)
    factory = model_factory(pack, receipt["scalers"], modulation_limit=choices["modulation_limit"])
    plan = PopulationPlan(prepared["private_inputs"]["stage3_run"], prepared["private_inputs"]["request"],
                          root=Path(root))
    if plan.identity != prepared["data"]:
        raise ValueError("Population changed")
    ids = plan.ids("Train")
    origins = {}
    for seed in seeds:
        origins[str(seed)] = dict(
            original_model_state_sha256=initial_digest(factory, seed, root),
            epoch_order_sha256=[digest(list(epoch_order(ids, seed, epoch))) for epoch in range(1, 10)],
        )
    repeat = initial_digest(factory, seeds[0], root)
    if repeat != origins[str(seeds[0])]["original_model_state_sha256"]:
        raise RuntimeError("Seed-driven initialization is not reproducible")
    del pack
    gc.collect()
    payload = dict(bytes=len(raw), sha256=actual, opens=1)
    return origins, payload


def inherited_delta(root, proposal):
    """Reviewed difference between a frozen proposal's record and this tree."""
    root = Path(root)
    missing = sorted(name for name in proposal["code_sha256"] if not (root / name).is_file())
    if missing:
        raise ValueError("An inherited dependency is missing: " + str(missing))
    differences = sorted(name for name, expected in proposal["code_sha256"].items()
                         if sha(root / name) != expected)
    unreviewed = sorted(set(differences) - INHERITED_DELTA_ALLOWANCE)
    if unreviewed:
        raise ValueError("An inherited dependency changed outside the reviewed repair surface: "
                         + str(unreviewed))
    return differences


def parent_delta(root, parent_proposal_path):
    """Read the frozen parent proposal and return its reviewed dependency delta."""
    return inherited_delta(root, read(parent_proposal_path))


def zero_inheritance(root, zero_path, real):
    """Approved ZERO protocol plus its hash binding to the completed seed2029 REAL arm."""
    root, real = Path(root), Path(real)
    zero, terminal = read(zero_path), read(root / ZERO_TERMINAL)
    if digest({key: value for key, value in zero.items() if key != "proposal_sha256"}) != zero["proposal_sha256"]:
        raise ValueError("Frozen ZERO proposal identity differs")
    differences = inherited_delta(root, zero)
    expected = dict(status="COMPLETE_TRAIN_AND_DEV_EVALUATION", engineering_status="PASS",
                    proposal_sha256=zero["proposal_sha256"], dynamic_control=DYNAMIC_CONTROL,
                    execution_code_commit=ZERO_CODE)
    if any(terminal.get(key) != value for key, value in expected.items()):
        raise ValueError("Completed ZERO/COSINE9 evidence is required")
    if terminal.get("schedule") != schedule_identity():
        raise ValueError("Completed ZERO schedule differs")
    if (terminal.get("updates"), terminal.get("source_bytes"), terminal.get("source_files")) != (4320, 477571953840, 142813):
        raise ValueError("Completed ZERO budget differs")
    if terminal.get("2025_final_test_accessed") is not False:
        raise ValueError("2025 final test access is not sealed")
    reuse = zero["scientific_choices"]["real_reuse"]
    identities = {}
    for name, identity in reuse["metadata_files"].items():
        path = real / name
        if not path.is_file():
            raise ValueError("Saved REAL metadata is missing: " + name)
        actual = dict(bytes=path.stat().st_size, sha256=sha(path))
        if actual != identity:
            raise ValueError("Saved REAL metadata changed: " + name)
        identities[name] = actual
    real_terminal_path = root / REAL_TERMINAL
    if sha(real_terminal_path) != reuse["terminal_sha256"]:
        raise ValueError("The reviewed REAL/COSINE9 terminal receipt changed")
    real_terminal = read(real_terminal_path)
    if real_terminal.get("engineering") != "PASS" or real_terminal.get("code_commit") != reuse["code_commit"]:
        raise ValueError("Completed REAL/COSINE9 evidence is required")
    if real_terminal.get("new_E9_checkpoint") != reuse["checkpoint_identity"]:
        raise ValueError("The reviewed REAL checkpoint identity differs")
    initial = read(real / "paired_initial_identity.json")
    orders = read(real / "paired_orders.json")
    origin = dict(original_model_state_sha256=initial[MODEL]["full_state_sha256"],
                  epoch_order_sha256=[orders[str(epoch)]["sha256"] for epoch in range(1, 10)])
    if origin != reuse["origin"]:
        raise ValueError("The ZERO protocol was bound to another REAL initialization or order")
    if real_terminal.get("initial_full_state") != origin["original_model_state_sha256"]:
        raise ValueError("The REAL terminal receipt records another initialization")
    for epoch in range(1, 10):
        if digest(orders[str(epoch)]["ids"]) != orders[str(epoch)]["sha256"]:
            raise ValueError("Saved REAL epoch order is inconsistent")
    return dict(
        proposal_sha256=zero["proposal_sha256"],
        code_commit=reuse["code_commit"],
        metadata_files=identities,
        origin=origin,
        changed_inherited_dependencies=differences,
        terminal_verification_sha256=sha(root / ZERO_TERMINAL),
        real_terminal_verification_sha256=reuse["terminal_sha256"],
        terminal_approval_id=terminal.get("approval_id"),
        scientific_status=terminal.get("scientific_status"),
        dynamic_control=zero["scientific_choices"]["dynamic_control"],
        real_masks_retained=zero["scientific_choices"]["real_masks_retained"],
        structurally_zero_loss_gradient_weights=zero["scientific_choices"]["structurally_zero_loss_gradient_weights"],
        evaluation=copy.deepcopy(zero["scientific_choices"]["evaluation"]),
    )


def prepare(root, parent_proposal, parent_private, real, output_root):
    """Build one inspectable proposal/private pair for the four serial tasks."""
    root, output_root = Path(root), Path(output_root)
    if output_root.exists() or not output_root.parent.is_dir():
        raise PermissionError("A fresh output under an existing parent is required")
    parent, locations = read(parent_proposal), read(parent_private)
    if locations["proposal_sha256"] != parent["proposal_sha256"]:
        raise ValueError("Parent private preparation belongs to another proposal")
    if sha(Path(locations["inherited"])) != locations["inherited_file_sha256"]:
        raise ValueError("Inherited preparation identity differs")
    _, prepared = load_inherited(locations["inherited"])
    if prepared["data"] != parent["data"] or runtime_binding() != parent["runtime_binding"]:
        raise ValueError("Parent data or runtime identity differs")
    if parent["protocol"]["loss"] != "E0":
        raise ValueError("Only the frozen E0 loss is supported")
    if sha(parent_proposal) != sha(root / REAL_PROPOSAL):
        raise ValueError("The parent proposal must be the frozen REAL/COSINE9 proposal")
    reuse = zero_inheritance(root, ZERO_PROPOSAL, real)
    caps = budget(prepared)
    admission = resources()
    free = shutil.disk_usage(output_root.parent).free
    if free < caps["initial_free_bytes"]:
        raise RuntimeError("A new four-task output requires 48GiB free")
    choices = copy.deepcopy(read(root / ZERO_PROPOSAL)["scientific_choices"])
    choices.pop("real_reuse", None)
    origins, payload = seed_origins(root, prepared, locations["terrain"], choices,
                                    parent["static_source_sha256"][MODEL])
    choices.update(
        only_intervention="COSINE9_HORIZON_50_TO_9_EPOCHS_REAL_AND_ZERO_SEED2030_2031",
        initialization="FRESH_ORIGINAL_FACTORY_PER_SEED_NO_CHECKPOINT_LOAD",
        candidate_schedule=schedule_identity(),
        origin_reference=dict({MODEL: reuse["origin"]},
                              **{f"{MODEL}@{seed}": value for seed, value in origins.items()}),
        origin_provenance=dict(
            seed2029="INHERITED_REVIEWED_REAL_COSINE9_CONTROL",
            seeds_2030_2031="SEED_DRIVEN_ORIGINAL_FACTORY_DIGEST_COMPUTED_AT_PREPARE",
            verification="PAIRED_EXECUTOR_CHECK_ORIGIN_PAIR_REQUIRED_AT_EACH_TASK_START",
        ),
        zero_protocol_reuse=reuse,
        evaluation=copy.deepcopy(reuse["evaluation"]),
        decision_status="PROPOSED_PENDING_EXACT_RESEARCHER_BUDGET_APPROVAL",
    )
    protocol = dict(parent["protocol"])
    protocol.pop("seed", None)
    protocol.update(
        models=[MODEL], arms=list(ARMS), seed_scope="PER_TASK_2030_2031", loss="E0", lambda_q=1.0,
        quantile_profile="UNIFORM", schedule_profile=COSINE9, epochs=9, updates_per_epoch=480,
        updates_per_model=4320, total_updates=17280, paired_attempt_cap=17280, replay_allowance=0,
        endpoint="FIXED_EPOCH_9_LAST", BEST_selection=False,
        dynamic_control="PER_ARM_REAL_PHYSICAL_DOTE_OR_" + DYNAMIC_CONTROL,
    )
    delta = dict(allowance=sorted(INHERITED_DELTA_ALLOWANCE), parent=inherited_delta(root, parent),
                 zero=reuse["changed_inherited_dependencies"])
    private = dict(
        inherited=locations["inherited"], inherited_file_sha256=locations["inherited_file_sha256"],
        terrain=locations["terrain"], output_root=str(output_root), real=str(Path(real)),
        parent_proposal=str(Path(parent_proposal)), parent_private=str(Path(parent_private)),
        zero_proposal=ZERO_PROPOSAL, seeds=origins, static_payload=payload,
    )
    proposal = dict(
        kind=KIND,
        status="READY_WAITING_EXACT_RESEARCHER_APPROVAL",
        authorized=False,
        authorization_scope=SCOPE,
        final_2025_access=False,
        final_2025_status="SEALED_NOT_ACCESSED",
        tasks=[dict(task) for task in TASKS],
        data=prepared["data"],
        data_identity=prepared["data"],
        protocol=protocol,
        scientific_choices=choices,
        budget=caps,
        runtime_binding=runtime_binding(),
        code_sha256=code_hashes(root),
        reviewed_inherited_delta=delta,
        static_source_sha256={MODEL: parent["static_source_sha256"][MODEL]},
        source_scope_summary=parent["source_scope_summary"],
        execution_code_commit=None,
        execution_code_commit_status="PENDING_FREEZE_BOUND_BY_RESEARCHER_APPROVAL",
        parent_proposal_identity=dict(bytes=Path(parent_proposal).stat().st_size,
                                      sha256=sha(parent_proposal)),
        zero_protocol_identity=dict(path=ZERO_PROPOSAL, bytes=(root / ZERO_PROPOSAL).stat().st_size,
                                    sha256=sha(root / ZERO_PROPOSAL)),
        preparation_activity=dict(
            raw_payload_opens=0, static_payload_opens=payload["opens"], static_payload_bytes=payload["bytes"],
            checkpoint_loads=0, optimizer_updates=0, model_initializations=len(SEEDS) + 1,
            metadata_reads=dict(parent_proposals=2, zero_terminal=1,
                                control_metadata_files=len(reuse["metadata_files"]),
                                population_plan=1),
            note="No weather payload, checkpoint or optimizer state was opened; the static terrain pack was "
                 "read to seal the seed-driven initialization digests.",
        ),
        private_preparation_sha256=private_seal(private),
    )
    proposal["resources"] = dict(
        output_volume_free_bytes=free, admission=admission,
        RAM_GPU_admission="INHERIT_AND_RECHECK_EXISTING_MINIMUM_AT_START",
    )
    proposal["proposal_sha256"] = digest({key: value for key, value in proposal.items()
                                          if key != "proposal_sha256"})
    private["proposal_sha256"] = proposal["proposal_sha256"]
    return proposal, private


def validate_scope(proposal):
    if proposal.get("kind") != KIND or proposal.get("authorization_scope") != SCOPE:
        raise PermissionError("The exact four-task COSINE9 scope is required")
    if proposal.get("authorized") is not False or proposal.get("final_2025_access") is not False:
        raise PermissionError("A proposal cannot arrive authorized or with 2025 access")
    if [dict(task) for task in proposal.get("tasks", [])] != TASKS:
        raise PermissionError("Four exact REAL/ZERO seed2030/2031 tasks are required")
    protocol = proposal.get("protocol", {})
    expected = dict(loss="E0", lambda_q=1.0, quantile_profile="UNIFORM", schedule_profile=COSINE9, epochs=9,
                    updates_per_epoch=480, updates_per_model=4320, total_updates=17280,
                    paired_attempt_cap=17280, replay_allowance=0, endpoint="FIXED_EPOCH_9_LAST",
                    BEST_selection=False, seed_scope="PER_TASK_2030_2031")
    if any(protocol.get(key) != value for key, value in expected.items()):
        raise PermissionError("Protocol differs from the frozen four-task schedule")
    if sorted(protocol.get("arms", [])) != sorted(ARMS) or protocol.get("models") != [MODEL]:
        raise PermissionError("Protocol arms differ from REAL/ZERO on one B7 model")
    choices = proposal.get("scientific_choices", {})
    if choices.get("candidate_schedule") != schedule_identity():
        raise PermissionError("Candidate schedule identity differs")
    if (choices.get("dynamic_control") != DYNAMIC_CONTROL or choices.get("real_masks_retained") is not True
            or choices.get("structurally_zero_loss_gradient_weights") != 128):
        raise PermissionError("The ZERO numeric control protocol differs")
    origins = choices.get("origin_reference", {})
    if not isinstance(origins.get(MODEL), dict):
        raise PermissionError("The seed2029 REAL origin reference is required")
    for seed in SEEDS:
        entry = origins.get(f"{MODEL}@{seed}")
        if not isinstance(entry, dict) or set(entry) != {"original_model_state_sha256", "epoch_order_sha256"}:
            raise PermissionError("Seed " + str(seed) + " original initialization is not sealed")
        if len(entry["epoch_order_sha256"]) != 9:
            raise PermissionError("Seed " + str(seed) + " epoch orders are incomplete")
    for arm in ARMS:
        for seed in SEEDS:
            if not any(task["arm"] == arm and task["seed"] == seed for task in proposal["tasks"]):
                raise PermissionError("Seed " + str(seed) + " needs both the REAL and ZERO arm")
    commit = proposal.get("execution_code_commit")
    if commit is not None and not (isinstance(commit, str) and len(commit) == 40):
        raise PermissionError("execution_code_commit must stay pending or be a full commit id")


def checked(root, proposal_path, private_path, approval_path, commit):
    root = Path(root)
    if not Path(approval_path).is_file():
        raise PermissionError("An explicit researcher approval file is required")
    proposal, private, approval = read(proposal_path), read(private_path), read(approval_path)
    validate_scope(proposal)
    validate_approval(approval, proposal, private, commit)
    if digest({key: value for key, value in proposal.items() if key != "proposal_sha256"}) != proposal["proposal_sha256"]:
        raise ValueError("Proposal identity differs")
    if private["proposal_sha256"] != proposal["proposal_sha256"]:
        raise ValueError("Private preparation belongs to another proposal")
    if code_hashes(root) != proposal["code_sha256"]:
        raise ValueError("The reviewed code identity changed")
    if runtime_binding() != proposal["runtime_binding"]:
        raise ValueError("The reviewed interpreter/runtime changed")
    if private_seal(private) != proposal["private_preparation_sha256"]:
        raise ValueError("The private preparation seal differs")
    if sha(Path(private["inherited"])) != private["inherited_file_sha256"]:
        raise ValueError("The inherited preparation changed")
    if sha(Path(private["parent_proposal"])) != proposal["parent_proposal_identity"]["sha256"]:
        raise ValueError("The parent proposal changed")
    if sha(Path(private["zero_proposal"])) != proposal["zero_protocol_identity"]["sha256"]:
        raise ValueError("The frozen ZERO protocol changed")
    reuse = zero_inheritance(root, private["zero_proposal"], private["real"])
    if reuse != proposal["scientific_choices"]["zero_protocol_reuse"]:
        raise ValueError("The reviewed ZERO protocol evidence changed")
    delta = dict(allowance=sorted(INHERITED_DELTA_ALLOWANCE),
                 parent=parent_delta(root, private["parent_proposal"]),
                 zero=reuse["changed_inherited_dependencies"])
    if delta != proposal["reviewed_inherited_delta"]:
        raise ValueError("The reviewed inherited delta changed")
    if private["seeds"] != {seed: origin_entry(proposal["scientific_choices"], int(seed))
                            for seed in private["seeds"]}:
        raise ValueError("The sealed per-seed initialization record differs")
    if set(private["seeds"]) != {str(seed) for seed in SEEDS}:
        raise ValueError("The package needs exactly the two declared seeds")
    _, prepared = load_inherited(private["inherited"])
    if prepared["data"] != proposal["data"] or budget(prepared) != proposal["budget"]:
        raise ValueError("Population or four-task budget differs")
    return proposal, private, approval, prepared


def task_completion(folder, arm, seed, commit, caps, origin):
    """Per-task engineering receipt plus schedule and origin verification."""
    folder = Path(folder)
    result = read(folder / "completion.json")
    expected = dict(status="COMPLETE_TRAIN_AND_DEV_EVALUATION", model=MODEL, seed=seed, epochs=9,
                    optimizer_updates=caps["updates_per_model"], replay=0, code_commit=commit,
                    endpoint="FIXED_EPOCH_9_LAST",
                    total_logical_source_bytes=caps["source_bytes_per_model"],
                    total_logical_source_files=caps["source_files_per_model"])
    if any(result.get(key) != value for key, value in expected.items()):
        raise RuntimeError("The " + arm + " seed" + str(seed) + " completion differs")
    if result.get("schedule") != schedule_identity():
        raise RuntimeError("The " + arm + " seed" + str(seed) + " schedule receipt differs")
    initial = read(folder / "paired_initial_identity.json")
    if initial[MODEL]["full_state_sha256"] != origin["original_model_state_sha256"]:
        raise RuntimeError("The " + arm + " seed" + str(seed) + " initialization differs from the sealed origin")
    orders = read(folder / "paired_orders.json")
    if [orders[str(epoch)]["sha256"] for epoch in range(1, 10)] != origin["epoch_order_sha256"]:
        raise RuntimeError("The " + arm + " seed" + str(seed) + " epoch order differs from the sealed origin")
    verify_schedule_receipts(folder)
    return dict(arm=arm, model=MODEL, seed=seed, status=result["status"], epochs=9,
                updates=result["optimizer_updates"], source_bytes=result["total_logical_source_bytes"],
                source_files=result["total_logical_source_files"],
                initial_full_state_sha256=initial[MODEL]["full_state_sha256"],
                epoch_order_sha256=list(origin["epoch_order_sha256"]), folder=str(folder))


def pairing_summary(results):
    """REAL and ZERO of one seed must share one initial state and one epoch order."""
    summary = {}
    for seed in SEEDS:
        arms = {result["arm"]: result for result in results if result["seed"] == seed}
        if sorted(arms) != sorted(ARMS):
            raise RuntimeError("Seed " + str(seed) + " needs one REAL and one ZERO result")
        real, zero = arms["REAL"], arms["ZERO"]
        if real["initial_full_state_sha256"] != zero["initial_full_state_sha256"]:
            raise RuntimeError("REAL and ZERO initialization differ for seed " + str(seed))
        if real["epoch_order_sha256"] != zero["epoch_order_sha256"]:
            raise RuntimeError("REAL and ZERO epoch order differs for seed " + str(seed))
        summary[str(seed)] = dict(
            initial_full_state_sha256=real["initial_full_state_sha256"],
            epoch_order_sha256=list(real["epoch_order_sha256"]),
            real_source_bytes=real["source_bytes"], zero_source_bytes=zero["source_bytes"],
            pairing="IDENTICAL_SEED_DRIVEN_ORIGINAL_STATE_AND_EPOCH_ORDER",
        )
    return summary


def spawn_worker(command, environment, log, timeout, *, cwd):
    """Run one bounded worker process; a failure or timeout stops the whole package."""
    with Path(log).open("xb") as stream:
        process = subprocess.Popen(command, cwd=str(cwd), env=environment, stdout=stream,
                                   stderr=subprocess.STDOUT, creationflags=worker_creation_flags())
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(10)
            raise RuntimeError("A task deadline was reached; no retry") from None
    if code != 0:
        raise RuntimeError("A package task failed; every later task is blocked, no retry")
    return code


def dispatch(root, proposal, private, approval, commit, *, proposal_path, private_path, approval_path,
             spawn=None):
    """Serial execution of the four declared tasks with failure-first-stop."""
    root, package = Path(root), Path(private["output_root"])
    caps, spawn = proposal["budget"], spawn or spawn_worker
    results, started, updates, delivered, files = [], time.monotonic(), 0, 0, 0
    try:
        for index, task in enumerate(proposal["tasks"]):
            arm, seed = task["arm"], task["seed"]
            remaining = caps["max_package_seconds"] - (time.monotonic() - started)
            if remaining <= 0:
                raise RuntimeError("The package time cap was reached; no later task may start")
            task_package(private, arm, seed).mkdir(parents=False)
            write(package / f"task_{index + 1}_claim.json", dict(
                index=index, arm=arm, model=task["model"], seed=seed, controller_pid=os.getpid(),
                code_commit=commit, started_monotonic=time.monotonic()))
            environment = dict(os.environ, PYTHONHASHSEED=str(seed), CUBLAS_WORKSPACE_CONFIG=":4096:8",
                               OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", PYTHONUTF8="1")
            command = [sys.executable, "-B", str(root / ENTRY), "worker", "--task-index", str(index),
                       "--proposal", str(proposal_path), "--private-preparation", str(private_path),
                       "--researcher-approval", str(approval_path)]
            spawn(command, environment, package / f"{arm}_s{seed}_console.log",
                  min(remaining, caps["max_model_seconds"]), cwd=root)
            result = task_completion(task_folder(private, arm, seed), arm, seed, commit, caps,
                                     origin_entry(proposal["scientific_choices"], seed))
            results.append(result)
            updates += result["updates"]
            delivered += result["source_bytes"]
            files += result["source_files"]
            expected = (caps["updates_per_model"] * (index + 1),
                        caps["source_bytes_per_model"] * (index + 1),
                        caps["source_files_per_model"] * (index + 1))
            if (updates, delivered, files) != expected:
                raise RuntimeError("The cumulative task budget differs after " + arm + " seed" + str(seed))
        pairing = pairing_summary(results)
        if (updates, delivered, files) != (caps["total_updates"], caps["total_source_bytes"],
                                           caps["total_source_files"]):
            raise RuntimeError("The package budget differs from the approved envelope")
        elapsed = round(time.monotonic() - started, 3)
        if elapsed > caps["max_package_seconds"]:
            raise RuntimeError("The package time cap was reached")
        completion = dict(
            status="COMPLETE_FOUR_TASK_COSINE9_REAL_ZERO_MULTISEED", kind=KIND, code_commit=commit,
            tasks=results, totals=dict(tasks_completed=len(results), updates=updates,
                                       source_bytes=delivered, source_files=files),
            budget=caps, schedule=schedule_identity(), pairing=pairing,
            scientific_acceptance="NOT_VERIFIED", automatic_retry=False, replay=False,
            elapsed_seconds=elapsed,
        )
        write(package / "completion.json", completion)
        return completion
    except BaseException as error:
        failure = package / "failure.json"
        if not failure.exists():
            write(failure, dict(status="STOP_NO_AUTOMATIC_RETRY_OR_REPLAY", kind=KIND,
                                error=type(error).__name__ + ": " + str(error), completed_tasks=len(results),
                                completed_updates=updates, completed_source_bytes=delivered,
                                completed_source_files=files, automatic_retry=False, replay=False))
        raise


def execute(root, proposal_path, private_path, approval_path, commit):
    """One bounded serial dispatch; the first failure permanently blocks the package."""
    root = Path(root)
    proposal, private, approval, prepared = checked(root, proposal_path, private_path, approval_path, commit)
    package, caps = Path(private["output_root"]), proposal["budget"]
    if package.exists():
        raise PermissionError("Approval consumed/output exists; no restart")
    if shutil.disk_usage(package.parent).free < caps["initial_free_bytes"]:
        raise RuntimeError("A new four-task output requires 48GiB free")
    volumes = {Path(name).anchor for scope in prepared["roles"].values() for name in scope["files"]}
    if any(not Path(volume).is_dir() for volume in volumes):
        raise RuntimeError("A frozen source volume is unavailable")
    admission = resources()
    package.mkdir()
    write(package / "authorization_binding.json", dict(
        approval=approval, controller_pid=os.getpid(), admission=admission, kind=KIND,
        seeds=list(SEEDS), arms=list(ARMS), schedule=schedule_identity(),
    ))
    return dispatch(root, proposal, private, approval, commit, proposal_path=proposal_path,
                    private_path=private_path, approval_path=approval_path)


def worker(root, proposal_path, private_path, approval_path, commit, index):
    """One claimed task under the independent supervisor; no claim, no work."""
    if type(index) is not int or not 0 <= index < len(TASKS):
        raise PermissionError("Only the four declared tasks can be claimed")
    root = Path(root)
    proposal, private, approval, prepared = checked(root, proposal_path, private_path, approval_path, commit)
    package, task = Path(private["output_root"]), proposal["tasks"][index]
    binding, claim = read(package / "authorization_binding.json"), read(package / f"task_{index + 1}_claim.json")
    if binding.get("approval") != approval or binding.get("controller_pid") != os.getppid():
        raise PermissionError("The authorization binding belongs to another controller")
    expected = dict(index=index, arm=task["arm"], model=task["model"], seed=task["seed"],
                    controller_pid=os.getppid(), code_commit=commit)
    if any(claim.get(key) != value for key, value in expected.items()):
        raise PermissionError("The task claim differs from the controller")
    if type(claim.get("started_monotonic")) is not float:
        raise PermissionError("The task claim has no monotonic start")
    arm, seed = task["arm"], task["seed"]
    reference = task_folder(private, "REAL", seed) if arm == "ZERO" else None
    result = run_task(
        root, proposal, private, approval, prepared, commit, MODEL, seed,
        started=claim["started_monotonic"], pair_reference=reference,
        static_name=f"{arm}_static_source.sqlite",
        dynamic_transform_factory=ZeroNumericDote if arm == "ZERO" else PhysicalDote,
        quantile_profile="UNIFORM", lambda_q=1.0, schedule_profile=COSINE9,
        tail_factory=UpperQuantileTail, cosine9_seeds=SEEDS,
        origin_reference=origin_entry(proposal["scientific_choices"], seed),
    )
    folder = task_folder(private, arm, seed)
    initial = read(folder / "paired_initial_identity.json")
    write(folder / "task_receipt.json", dict(
        kind=KIND, arm=arm, model=MODEL, seed=seed, status=result["status"],
        updates=result["optimizer_updates"], source_bytes=result["total_logical_source_bytes"],
        source_files=result["total_logical_source_files"], code_commit=commit,
        schedule=schedule_identity(), schedule_receipts_verified_by="COSINE9_MULTISEED_CONTROLLER",
        dynamic_control=DYNAMIC_CONTROL if arm == "ZERO" else "REAL_PHYSICAL_DOTE",
        initial_full_state_sha256=initial[MODEL]["full_state_sha256"],
        replay=0, automatic_retry=False, scientific_acceptance="NOT_VERIFIED",
    ))
    return result
