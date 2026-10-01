"""Package the recorded scheduler gate failure; NO CUDA, optimizer steps or retries.

This entrypoint is specific to the retained run_20261001T023702Z evidence.
It does not rerun the failed gate and does not change any protocol parameter.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from yuntapr.contracts.loader import sha256
from yuntapr.models.b0 import B0Model
from yuntapr.training.phase_a_protocol import head_pin, parameter_groups, require_engineering_scope

BASELINE = "11a4ab1a21275fb3a5b1b75bd7478cf3d6e0fd2b"
OUT = ROOT / "docs/phase_a_optimizer_dryrun/runs/run_20261001T023702Z"


def save(name, value):
    with (OUT / name).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def write(name, value):
    with (OUT / name).open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(value)


def main():
    if sys.argv[1:] != ["--scope", "ENGINEERING_ONLY"]:
        raise ValueError("Explicit --scope ENGINEERING_ONLY required")
    require_engineering_scope(sys.argv[2])
    if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() != BASELINE:
        raise ValueError("Unexpected baseline")
    save("packaging_attempts.json", {"initial_attempt": {"exit_code": 1, "error": "FileNotFoundError: run_20261001T023704Z/parameter_groups.json",
        "cause": "Report packager used protocol identity creation time instead of the actual run directory start time",
        "scientific_or_optimizer_execution": False, "files_written": 0},
        "resolution": "Point report packager to the existing run_20261001T023702Z; no protocol/scientific change"})
    # Inspect CPU module ownership solely to serialize the prior passing group gate.
    # No optimizer is constructed, no CUDA tensor or data sample is loaded.
    model = B0Model()
    _, groups = parameter_groups(model)
    groups.update(status="PASS", execution="CPU_OWNERSHIP_INSPECTION_NO_UPDATES", head_pin=head_pin(model))
    save("parameter_groups.json", groups)
    save("selected_dryrun_samples.json", {"status": "NOT_RUN", "reason": "STOP before real sample selection/read",
         "planned_count": 6, "planned_indices": [0, 2343, 4687, 7031, 9375, 11719],
         "selection_rule": "np.linspace(0,11719,6,dtype=int64)", "actual_selected_samples": [], "2025_pixels_read": False})
    boundary = {"status": "FAIL", "executed_in": "preliminary 16-test CPU protocol gate",
        "lr_1": 1e-4 / 5860, "lr_W_observed": .00010000000000000002,
        "lr_W_required": .0001, "lr_W_absolute_error": .00010000000000000002 - .0001,
        "lr_U": .000001, "lr_W_plus_1_status": "assertion not reached after W failure in boundary test",
        "actual_evaluation_order": "(base_lr * u) / W",
        "three_failed_tests": ["test_schedule_boundaries_no_off_by_one", "test_schedule_full_mathematical_monotonicity",
                               "test_finalfit_replay_same_epoch_horizon"],
        "failure_cause": "Float64 operation ordering rounds the warmup endpoint above base_lr, breaking exact boundary, range and same-epoch equality.",
        "researcher_approved_bound_resolution": "min_lr lower bound applies only to cosine; warmup 0<LR<=base_lr",
        "bound_resolution_did_not_cause_this_failure": True,
        "proposed_follow_up_for_researcher_review": "Evaluate base_lr*(u/W) to preserve the exact W endpoint without changing the mathematical formula or parameters; verify all boundaries in a new run.",
        "proposed_fix_applied": False, "optimizer_steps": 0,
        "stop_rule": "User attachment Section27: scheduler boundary failure => STOP; report problem, no parameter changes."}
    save("lr_schedule_boundary_tests.json", boundary)
    not_run = {"status": "NOT_RUN", "reason": "Scheduler boundary STOP before CUDA optimizer dry-run",
               "executed": False, "counted_as_pass": False}
    for name in ("determinism_run_a.json", "determinism_run_b.json", "precision_checks.json"):
        save(name, not_run)
    save("determinism_comparison.json", {**not_run, "bit_exact_pass": False,
         "run_a_model_state_sha256": None, "run_b_model_state_sha256": None})
    save("resume_checkpoint_test.json", {**not_run, "exact_pass": False, "temporary_checkpoint_created": False,
         "temporary_checkpoint_deleted": None, "optimizer_logically_equivalent": False, "global_update": None})
    save("checkpoint_provenance_guard.json", {**not_run, "real_serialized_checkpoint_loader_test": "NOT_RUN",
         "metadata_only_synthetic_unit_test": "PASS", "checkpoint_files_created": 0})
    write("optimizer_steps.csv", "status,run,global_update,loss,LR,pre_clip_norm,clip_threshold,clipping_triggered,reason\nNOT_RUN,,,,,,,,scheduler boundary STOP\n")
    write("optimizer_memory.csv", "status,run,global_update,allocated_MiB,reserved_MiB,device_free_MiB,reason\nNOT_RUN,,,,,,scheduler boundary STOP\n")
    names = ["checkpoint_best_separate_from_early_stop", "checkpoint_metadata_rejects_identity_and_boundary",
             "early_stop_strict_boundary_and_reset", "epoch_shuffle_independent_of_global_rng", "exact_approved_values",
             "exact_disjoint_optimizer_groups", "finalfit_replay_same_epoch_horizon",
             "global_validation_raw_numerators_unequal_partition", "grouped_ap_and_auc_ties", "head_implementation_pin",
             "no_formal_training_authorization", "schedule_boundaries_no_off_by_one",
             "schedule_full_mathematical_monotonicity", "shared_parameter_fails",
             "state_digest_includes_buffers_and_scalar_optimizer_steps", "unknown_parameter_fails"]
    failed = set(boundary["three_failed_tests"])
    # Transcribe actual tool-observed unittest outcomes; do not claim this is a rerun.
    lines = ["Recorded preliminary command: CUDA interpreter -B; unittest suite of ProtocolTests excluding test_real_replay_and_resume_evidence.",
             "This file transcribes the observed tool output. No tests were rerun after the STOP.", ""]
    lines += ["test_" + name + " ... " + ("FAIL" if "test_" + name in failed else "ok") for name in names]
    lines += ["", "test_finalfit_replay_same_epoch_horizon: AssertionError: 0.0001 != 0.00010000000000000002",
              "test_schedule_boundaries_no_off_by_one: AssertionError: 0.00010000000000000002 != 0.0001",
              "test_schedule_full_mathematical_monotonicity: warmup <= base_lr assertion is False",
              "Ran 16 tests in 1.652s", "FAILED (failures=3)", "Command process exit_code=1.",
              "137 historical tests: NOT_RUN this run (STOP); retained historical passing evidence belongs to the baseline only.",
              "Real replay/resume evidence test: NOT_RUN (STOP).", ""]
    write("test_results.txt", "\n".join(lines))
    save("test_summary.json", {"status": "FAIL", "preliminary_protocol_gate": {"executed": 16, "passed": 13,
         "failed": 3, "errors": 0, "skipped": 0, "failed_test_names": boundary["three_failed_tests"]},
         "historical_137_this_run": "NOT_RUN", "real_replay_evidence_test": "NOT_RUN", "complete_required_test_gate_pass": False})
    final = {"run_status": "STOPPED_SCHEDULER_BOUNDARY_FAILURE", "stop_condition": "SCHEDULER_BOUNDARY_FAILURE",
        "PHASE_A_TRAINING_PROTOCOL_VERSION": "v1.0", "PHASE_A_TRAINING_PROTOCOL_FROZEN": True,
        "HEAD_IMPLEMENTATION_DETAIL_PINNED": True, "FOCAL_ALPHA": .5, "FOCAL_GAMMA": 2., "OPTIMIZER": "AdamW",
        "BASE_LR": 1e-4, "WEIGHT_DECAY": 1e-4, "TRAIN_PHYSICAL_BATCH": 2, "GRADIENT_ACCUMULATION": 1,
        "EFFECTIVE_BATCH": 2, "AMP_MODE": "BF16", "VALIDATION_BATCH": 8, "NUM_WORKERS": 2,
        "MAX_EPOCHS": 50, "WARMUP_EPOCHS": 1, "MIN_LR": 1e-6, "EARLY_STOP_PATIENCE": 8,
        "EARLY_STOP_MIN_DELTA": 1e-4, "GRAD_CLIP_NORM": 5., "PRIMARY_SEED": 2026,
        "CHECKPOINT_METRIC": "global_val_core_loss", "DRYRUN_OPTIMIZER_STEP_PASS": False,
        "DRYRUN_MEMORY_SAFE": False, "DETERMINISTIC_REPLAY_PASS": False, "RESUME_REPLAY_EXACT_PASS": False,
        "CHECKPOINT_PROVENANCE_GUARD_PASS": False, "PROTOCOL_ENGINEERING_VALIDATED": False,
        "B0_FORMAL_TRAINING_STARTED": False, "FORMAL_TRAINING_AUTHORIZED": False,
        "actual_optimizer_steps": 0, "real_data_samples_read": 0, "2025_pixels_read": False,
        "formal_or_temporary_checkpoints_created": 0,
        "execution_status": {"protocol_freeze": "PASS", "head_pin": "PASS", "parameter_groups": "PASS",
            "scheduler": "FAIL", "optimizer_dryrun": "NOT_RUN", "optimizer_memory": "NOT_RUN",
            "A_B_deterministic_replay": "NOT_RUN", "temporary_checkpoint_resume": "NOT_RUN",
            "serialized_checkpoint_provenance_guard": "NOT_RUN", "full_required_test_suite": "NOT_RUN"},
        "boolean_interpretation": "False for unexecuted gates means not proven; consult execution_status. NOT_RUN is never PASS."}
    save("final_status.json", final)
    identity = json.loads((OUT / "protocol_identity.json").read_text(encoding="utf-8"))
    report = ["# PHASE_A_OPTIMIZER_DRYRUN_REPORT", "", "状态：**STOPPED_SCHEDULER_BOUNDARY_FAILURE**。协议已按研究者批准冻结，工程验证未通过。", "",
        f"Baseline `{BASELINE}`；run `{OUT.name}`。", "",
        "## 真实执行结果", "",
        "已创建独立 protocol v1.0 文档与完整 YAML，核验全部继承身份 SHA；Scientific Freeze v1.1 和历史文件未修改。研究者已确认：保留精确 warmup 公式，min_lr 下界仅作用于 cosine。",
        "CPU 小测试确认 head 实现和参数组正确：decay=4,322,832；no-decay=6,529；total=4,329,361，互斥且完整。初步16项 protocol 单元测试执行13 PASS、3 FAIL；无 skipped。", "",
        "## 触发 STOP 的问题", "",
        "当前 `base_lr * u / W` 按 `(base_lr*u)/W` 求值，在 u=W=5860 产生 `0.00010000000000000002`，规定端点为 `0.0001`。差值为 `2.710505431213761e-20`，是浮点操作顺序的数值边界错误，不是科研参数缺失。它导致端点精确比较、warmup<=base 上界、Phase-A/FinalFit相同epoch进度的精确比较共3项失败。", "",
        "附件第27节规定 scheduler boundary failure 必须 STOP、只报告问题、不自动修改研究者批准参数。本轮在此停止；未修正求值顺序，未放宽测试为 tolerance，未使用 clamp。",
        "可供研究者批准的后续修复是按等价数学公式 `base_lr*(u/W)` 求值，保留全部科学参数，再在独立新 run 验证完整 schedule。当前失败 run 必须保留。此建议尚未应用。", "",
        "## 未执行项目", "",
        "六个真实样本选择/reader/QC、GPU optimizer、20% VRAM gate、A/B bit-exact replay、Run C temporary checkpoint/resume、序列化checkpoint破坏保护、全部137历史测试均为 NOT_RUN。本轮未产生 optimizer.step、真实数据读取、GPU memory测量、checkpoint文件。CPU 单元测试只实例化 AdamW 检查 defaults/groups，未更新参数；metadata-only rejection 单元测试不能替代真实 checkpoint loader test。",
        "optimizer CSV 和各 replay/memory JSON 明确标为 NOT_RUN；任何未执行项目均不算 PASS。未执行137旧测试不构成其回归或通过结论；历史137 PASS证据仍属于既有 baseline。新增 validation helper 的 batch全局分子、AP exact ties、R==.1边界等已通过本轮 CPU 小测试，但不代表完整真实 Validation epoch 已执行。", "",
        "## 冻结身份", "", f"Protocol SHA256 `{identity['protocol_sha256']}`。", f"Document SHA256 `{identity['document_sha256']}`。",
        "全部来源/版本/hash 见 protocol_identity.json，参数名完整列表见 parameter_groups.json。config/document 是本轮冻结 overlay；实现代码保持失败时的版本，不能作为已经工程验证通过的训练入口。", "",
        "## 最终状态", "", "```json", json.dumps(final, indent=2, ensure_ascii=False), "```", "",
        "manifest 保存新产物 SHA 与全部 baseline 文件的 Git blob / disk SHA 核验。仅发布文本配置、源码、测试和失败证据；没有提交原始数据、wheel、venv、cache、模型或 optimizer 二进制。B0_FORMAL_TRAINING_STARTED=false，FORMAL_TRAINING_AUTHORIZED=false。发布后停止。", ""]
    write("PHASE_A_OPTIMIZER_DRYRUN_REPORT.md", "\n".join(report))
    # Verify every historical baseline blob, respecting repository line-ending normalization.
    expected = {}
    tree = subprocess.check_output(["git", "ls-tree", "-r", "-z", BASELINE], cwd=ROOT).decode("utf-8")
    for entry in tree.rstrip("\0").split("\0"):
        meta, name = entry.split("\t", 1)
        expected[name] = meta.split()[2]
    names = list(expected)
    actual = subprocess.run(["git", "hash-object", "--stdin-paths"], cwd=ROOT, input="\n".join(names)+"\n",
        text=True, encoding="utf-8", capture_output=True, check=True).stdout.splitlines()
    if len(names) != len(actual) or any(expected[n] != value for n, value in zip(names, actual)):
        raise ValueError("Historical baseline changed")
    new_sources = [ROOT / "src/yuntapr/training/phase_a_protocol.py", ROOT / "src/yuntapr/training/phase_a_validation.py",
        ROOT / "scripts/freeze_phase_a_protocol_v1.py", Path(__file__), ROOT / "tests/phase_a_protocol_v1/test_protocol_v1.py"]
    save("manifest.json", {"task": "PHASE_A_PROTOCOL_V1_FREEZE_AND_OPTIMIZER_DRYRUN", "baseline": BASELINE,
        "sealed_UTC": datetime.now(timezone.utc).isoformat(), "run_status": final["run_status"],
        "public_files": {p.relative_to(OUT).as_posix(): {"sha256": sha256(p), "bytes": p.stat().st_size}
                         for p in sorted(OUT.iterdir()) if p.is_file() and p.name != "manifest.json"},
        "source_files": {p.relative_to(ROOT).as_posix(): sha256(p) for p in new_sources},
        "protocol_files": {identity["protocol_path"]: identity["protocol_sha256"], identity["document_path"]: identity["document_sha256"]},
        "unchanged_baseline_files_sha256": {name: sha256(ROOT / name) for name in names},
        "unchanged_baseline_file_count": len(names), "optimizer_steps": 0, "temporary_checkpoint_files": 0,
        "raw_data_committed": False, "wheel_committed": False, "venv_committed": False, "cache_committed": False,
        "owned_staging_copies_created": 0, "formal_training_started": False, "formal_training_authorized": False})
    print(json.dumps(final), flush=True)


if __name__ == "__main__":
    main()
