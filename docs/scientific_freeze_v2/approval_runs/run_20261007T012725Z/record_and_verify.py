"""One-time scientific approval record. Standard library, repository metadata only.

Run with --verify to recheck the immutable decision without writing artifacts.
No model imports, checkpoint deserialization, inference, or raw-source reads.
"""
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[4]
RUN = Path(__file__).resolve().parent.relative_to(ROOT).as_posix()
BASELINE = "93e0f4ed78625638391dd98a1a63078818daf8be"
HEAD_CANDIDATE = "config/science_v2/quantile_head_v2_candidate.json"
PROTOCOL_CANDIDATE = "config/science_v2/phase_a_protocol_candidate_v1.json"
HEAD_FROZEN = "config/science_v2/quantile_head_v2_frozen_v1.json"
PROTOCOL_FROZEN = "config/science_v2/phase_a_protocol_frozen_v1.json"
REGISTRY = "config/science_v2/scientific_freeze_v2_registry_v1.json"
APPROVAL = RUN + "/researcher_approval.txt"
NORM_SHA = "656fe7a929cbd8617b08427e8d1fa7029b26512253efb44faa576796137d4a31"


def path(rel):
    p = (ROOT / rel.replace("\\", "/")).resolve()
    if not p.is_relative_to(ROOT) or p.suffix.lower() not in {".json", ".yaml", ".csv", ".txt", ".md", ".py"}:
        raise ValueError("Only explicitly named repository text metadata is permitted")
    return p


def read(rel):
    return path(rel).read_bytes()


def load(rel):
    return json.loads(read(rel))


def identity(rel):
    data = read(rel)
    return {"path": str(rel).replace("\\", "/"), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def write(rel, value):
    # No overwrite, including previous failed attempts or historical records.
    with path(rel).open("x", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n" if not isinstance(value, str) else value)


def git(*args):
    return subprocess.check_output(["git", "-c", "core.longpaths=true", *args], cwd=ROOT)


AUTH = {
    "V2_SCIENTIFIC_FREEZE_APPROVED": True,
    "FORMAL_TRAINING_AUTHORIZED": False,
    "V2_PHASE_A_AUTHORIZED": False,
    "V2_PHASE_A_STARTED": False,
    "V2_PHASE_B_AUTHORIZED": False,
    "B0_MATCHED_V2_PHASE_A_STARTED": False,
    "B1_V2_PHASE_A_STARTED": False,
    "B0_MATCHED_PHASE_B_RESUME_AUTHORIZED": False,
    "B1_PHASE_B_STARTED": False,
    "2025_RAW_ACCESS": 0,
    "RESEARCHER_TRAINING_AUTHORIZATION_REQUIRED": True,
}
DIAGNOSTICS = {
    "status": "FROZEN_PHASE_A_PLAN_REQUIREMENT_ONLY",
    "frequency": "EVERY_EPOCH",
    "read_only": True,
    "save_required": True,
    "minimum_metrics": [
        "Yunnan inside max qlog", "Yunnan outside max qlog",
        "q32 per-forward max p99", "q32 per-forward max p99.9",
        "FP64 physical overflow risk", "descriptive exceedance counts",
    ],
    "descriptive_thresholds_mm_h": [10, 50, 100, 500, 1000],
    "affects_loss": False, "affects_BEST_selection": False,
    "affects_early_stopping": False, "automatic_tuning": False,
    "automatic_batch_skip": False, "outcome_guided_protocol_change": False,
    "execution_in_this_approval_update": "NOT_RUN_NOT_AUTHORIZED",
    "scope_note": "仅登记研究者指定的逐 epoch 只读诊断要求；本次不新增统计口径、不实现或执行诊断、不生成结果。",
}


def expected():
    authority = {"researcher_approval": identity(APPROVAL), "binding_baseline_commit": BASELINE}
    h = copy.deepcopy(load(HEAD_CANDIDATE))
    h.update(version="QUANTILE_HEAD_V2_SCIENTIFIC_FREEZE_v1", status="FROZEN_RESEARCHER_APPROVED",
             authorization=AUTH, approval=authority, accepted_candidate=identity(HEAD_CANDIDATE))
    h["numerics"]["epsilon_status"] = "FROZEN_RESEARCHER_APPROVED"
    h["prohibited_repairs"] = ["clamp", "sort", "nan_to_num", "automatic_repair", "automatic_batch_skip"]
    p = copy.deepcopy(load(PROTOCOL_CANDIDATE))
    p.update(version="V2_PHASE_A_PROTOCOL_FROZEN_v1", status="FROZEN_RESEARCHER_APPROVED_TRAINING_NOT_AUTHORIZED",
             authorization=AUTH, approval=authority, accepted_candidate=identity(PROTOCOL_CANDIDATE))
    p["initialization"]["seed_status"] = "FROZEN_RESEARCHER_APPROVED"
    p["initialization"]["policy_status"] = "FROZEN_FRESH_SAME_NAME_SAME_SHAPE_PAIRED_INITIALIZATION"
    p.pop("CANDIDATE_REUSE_OF_V1_PROTOCOL")
    p["ACCEPTED_CANDIDATE_REUSE_OF_V1_PROTOCOL"] = True
    p["RESEARCHER_APPROVAL_REQUIRED"] = False
    p["approval_scope"] = "SCIENTIFIC_PROTOCOL_ONLY; separate formal training authorization remains required"
    p["description"] = "研究者接受已有 v2 候选 Phase-A 协议作为冻结协议；原数值设置不变，新增逐 epoch 只读上尾诊断计划。未授权正式训练。"
    p["shared_phase_a_normalization"] = {"mean_K": 271.60515414265217, "std_K": 19.93959597783802,
                                        "sha256": NORM_SHA, "refit": False}
    p["model_input_semantics"] = {"B0_MATCHED_V2": "LATEST_B13_ONLY", "B1_V2": "SIX_CAUSAL_B13_SLOTS"}
    p["upper_tail_diagnostics"] = DIAGNOSTICS
    return h, p


def verify():
    checks = []
    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append({"check": name, "status": "PASS"})
    h, p = expected()
    check("Frozen head equals accepted candidate plus explicit approved metadata", load(HEAD_FROZEN) == h)
    check("Frozen Phase-A preserves candidate settings and adds only approved records", load(PROTOCOL_FROZEN) == p)
    for rel in (HEAD_CANDIDATE, PROTOCOL_CANDIDATE):
        check("Original candidate byte-identical to baseline: " + rel, read(rel) == git("show", BASELINE + ":" + rel))
    registry = load(REGISTRY)
    check("Registry frozen head identity", registry["frozen_head"] == identity(HEAD_FROZEN))
    check("Registry frozen protocol identity", registry["frozen_phase_a_protocol"] == identity(PROTOCOL_FROZEN))
    check("Approval identity and baseline binding", registry["researcher_approval"] == identity(APPROVAL) and registry["binding_baseline_commit"] == BASELINE)
    check("Scientific acceptance does not authorize execution", registry["authorization"] == AUTH and h["authorization"] == p["authorization"] == AUTH)
    check("Training roots remain unset and runner remains unauthorized", p["checkpoint"]["roots"] is None and p["checkpoint"]["status"] == "FORMAL_V2_RUNNER_AND_ROOTS_NOT_AUTHORIZED")
    for name, item in p["identity"].items():
        if name == "yunnan_mask":
            continue  # Preserve recorded identity; no NetCDF or external source access.
        check("Existing repository identity SHA: " + name, identity(item["path"])["sha256"] == item["sha256"])
    normalization = load(p["identity"]["normalization"]["path"])
    check("Frozen normalization mean/std/2023-only fit", normalization["mean_K"] == 271.60515414265217 and normalization["std_K"] == 19.93959597783802 and normalization["fit_years"] == [2023] and normalization["fit_scene_count"] == 10455 and p["normalization_sha256"] == NORM_SHA)
    source = p["source_protocol_identity"]
    check("Inherited source protocol identity", identity(source["path"])["sha256"] == source["sha256"])
    samples = {}
    for model in ("B0_MATCHED", "B1"):
        for year, count in ((2023, 10455), (2024, 10501)):
            key = f"{model}_{year}"
            rows = list(csv.DictReader(io.StringIO(read(p["identity"][key]["path"]).decode("utf-8-sig"))))
            ids = [row["sample_id"] for row in rows]
            check("Frozen sample identities/count/year: " + key, len(rows) == count and len(set(ids)) == count and all(int(row["year"]) == year for row in rows))
            samples[key] = ids
    check("Matched sample sets and order", all(samples[f"B0_MATCHED_{y}"] == samples[f"B1_{y}"] for y in (2023, 2024)))
    check("Every-epoch diagnostics recorded with all non-interference restrictions", p["upper_tail_diagnostics"] == DIAGNOSTICS)
    # Only added files are permitted; every baseline tracked artifact must be untouched.
    changed = git("diff", "--name-status", "--diff-filter=DMRTUXB", BASELINE, "--").decode("utf-8")
    check("All baseline tracked files unchanged", not changed.strip())
    check("No model/data packages imported", not any(n in sys.modules for n in ("torch", "numpy", "netCDF4", "xarray", "h5py", "yuntapr")))
    return {"status": "PASS", "checks_passed": len(checks), "checks": checks,
            "scope": "Repository text metadata only; not a regression/GPU/training run",
            "external_mask_sha_recomputed": False, "checkpoint_files_opened": 0,
            "normalization_refit": False, "model_forward_calls": 0,
            "backward_calls": 0, "optimizer_steps_added": 0,
            "2025_RAW_ACCESS": 0, "raw_source_files_opened": 0}


def main():
    if sys.argv[1:] == ["--verify"]:
        result = verify()
        for item in load(RUN + "/artifact_manifest.json")["artifacts"]:
            if identity(item["path"]) != item:
                raise AssertionError("Artifact identity changed: " + item["path"])
        print(json.dumps({"status": result["status"], "checks_passed": result["checks_passed"], "artifact_hashes": "PASS"}))
        return
    if sys.argv[1:]:
        raise SystemExit("Use no arguments for one-time creation, or --verify")
    if git("rev-parse", "HEAD").decode().strip() != BASELINE:
        raise RuntimeError("Creation baseline mismatch")
    if git("diff", "--name-only", BASELINE, "--").strip():
        raise RuntimeError("Tracked working tree must be clean")
    recorded = datetime.now(timezone.utc).isoformat()
    h, p = expected()
    write(HEAD_FROZEN, h)
    write(PROTOCOL_FROZEN, p)
    write(REGISTRY, {
        "version": "SCIENTIFIC_FREEZE_V2_APPROVAL_REGISTRY_v1", "recorded_at_utc": recorded,
        "binding_baseline_commit": BASELINE, "researcher_message_timestamp": None,
        "timestamp_note": "记录时刻，不冒充未提供的研究者消息发送时刻。",
        "researcher_approval": identity(APPROVAL),
        "approval_source": "User message transcribed to UTF-8 with LF; hash identifies this transcription, not platform message bytes or a digital signature",
        "frozen_head": identity(HEAD_FROZEN), "frozen_phase_a_protocol": identity(PROTOCOL_FROZEN),
        "accepted_candidate_head": identity(HEAD_CANDIDATE), "accepted_candidate_protocol": identity(PROTOCOL_CANDIDATE),
        "authorization": AUTH, "action": "RECORD_APPROVAL_ONLY_THEN_PUSH_MAIN_AND_STOP",
        "historical_candidate_records": "IMMUTABLE; their former unapproved status describes their original engineering run",
        "implementation_changed": False, "training_runner_started": False,
    })
    result = verify()
    write(RUN + "/verification.json", result)
    write(RUN + "/final_status.json", {**AUTH, "STATUS": "SCIENTIFIC_FREEZE_V2_RECORDED_TRAINING_NOT_AUTHORIZED",
          "MODEL_PARAMETERS_UPDATED": False, "FORMAL_OPTIMIZER_STEPS_ADDED": 0,
          "FORWARD_CALLS": 0, "BACKWARD_CALLS": 0, "NORMALIZATION_REFIT": False,
          "UPPER_TAIL_DIAGNOSTICS_EXECUTED": False, "VERIFICATION": result["status"],
          "publication_status_at_creation": "PENDING_GIT_COMMIT_AND_PUSH"})
    report = """# Scientific Freeze v2 研究者批准记录

研究者已批准 Quantile Head v2 科学冻结及当前已登记的 Phase-A 候选协议。本次仅记录批准，没有执行训练或诊断。

## FROZEN

- 训练路径解耦、归一化单调分位数参数化 v2；发生阈值 0.1 mm/h；32 个条件分位数；tau_i=(i-0.5)/32；z0=log1p(0.1)。
- epsilon_w=epsilon_span=1e-4；FP64 归一化变换；严格浮点保护；禁止 clamp、sort、nan_to_num、自动修复、自动跳过批次。数学严格性与有限精度可表示性仍区分；不可表示时报告错误。总跨度不设物理上界，不保证未来物理转换绝不溢出。
- B0-Matched-v2 仅最新 B13；B1-v2 为六个因果 B13 槽位。2023 Train 样本集合 10,455；2024 Validation 样本集合 10,501。
- 共享 Phase-A normalization：mean=271.60515414265217 K，std=19.93959597783802 K；SHA256 `656fe7a929cbd8617b08427e8d1fa7029b26512253efb44faa576796137d4a31`。不重新拟合。
- seed=2026；分别重新设种子，执行全新同名同形配对初始化；禁止历史 checkpoint 转移。
- 原候选 Phase-A 协议数值设置原样继承：AdamW、focal alpha=0.5/gamma=2、batch=2、drop_last=false、5,228 steps/epoch、W=5,228、U=261,400、最多 50 epoch、base LR=1e-4、cosine min LR=1e-6、clip norm=5、validation batch=8、patience=8/min_delta=1e-4。完整设置以冻结 JSON 为准；未宣称这些参数对 v2 最优。

## 逐 epoch 只读上尾诊断计划

每个 epoch 必须保存：云南 mask 内/外 max qlog、q32 per-forward max 的 p99/p99.9、FP64 physical overflow risk，以及 10/50/100/500/1000 mm/h 的描述性超越计数。

这些诊断不得影响 loss、BEST selection、early stopping，不得触发自动调参或跳过 batch，不得成为 outcome-guided protocol change。本次仅登记要求，没有新增统计口径、实现诊断或生成任何诊断结果。

## 授权状态与证据

`V2_SCIENTIFIC_FREEZE_APPROVED=true`。所有正式训练授权仍为 false：`FORMAL_TRAINING_AUTHORIZED`、`V2_PHASE_A_AUTHORIZED`、`V2_PHASE_B_AUTHORIZED`、`B0_MATCHED_PHASE_B_RESUME_AUTHORIZED`。`V2_PHASE_A_STARTED=false`、`B1_PHASE_B_STARTED=false`、`2025_RAW_ACCESS=0`。模型参数未更新，新增 optimizer step=0。

正式 v2 runner 和 checkpoint roots 尚未授权；本次不设置目录、不启动训练。历史候选文件及审查结果保留原样，新冻结记录独立登记。

- [研究者批准原文转录](researcher_approval.txt)：UTF-8/LF 转录；SHA 绑定转录文件，不冒充平台消息签名。
- [当前冻结注册表](../../../../config/science_v2/scientific_freeze_v2_registry_v1.json)：绑定原候选 SHA、批准转录 SHA、冻结文件 SHA 和基线提交。
- [完整冻结 Phase-A 协议](../../../../config/science_v2/phase_a_protocol_frozen_v1.json)。
- [冻结 Quantile Head v2 合同](../../../../config/science_v2/quantile_head_v2_frozen_v1.json)。
- [核验结果](verification.json)、[最终状态](final_status.json)、[新增文件 SHA 清单](artifact_manifest.json)。

本轮仅运行标准库元数据一致性核验；未重新运行历史 GPU/regression suite。未打开原始数据、mask NetCDF 或 checkpoint 二进制；外部 mask SHA 仅继承原证据，未重算。原候选文件与全部基线已跟踪文件保持不变。

本记录绑定基线：`93e0f4ed78625638391dd98a1a63078818daf8be`。提交 GitHub main 后停止。
"""
    write(RUN + "/SCIENTIFIC_FREEZE_V2_APPROVAL_RECORD.md", report)
    files = [HEAD_FROZEN, PROTOCOL_FROZEN, REGISTRY] + sorted(x.relative_to(ROOT).as_posix() for x in path(APPROVAL).parent.iterdir() if x.is_file())
    write(RUN + "/artifact_manifest.json", {"binding_baseline_commit": BASELINE,
          "artifacts": [identity(rel) for rel in files], "self_hash": "Excluded to avoid circular hashing; Git commit binds this manifest"})
    print(json.dumps({"status": "RECORDED", "checks_passed": result["checks_passed"], "run": RUN}, ensure_ascii=False))


if __name__ == "__main__":
    main()
