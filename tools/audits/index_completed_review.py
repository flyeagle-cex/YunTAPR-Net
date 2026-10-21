"""Index already reviewed repository evidence; no training imports or raw paths."""
import csv
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/audits/20261021_completed_work_review"
BASE = "96a2a61eeb9b0c4a8513133133c75bfdf4b58726"
P = "docs/phase_b_v2_formal_execution/"
S = "stage0-b0-evidence/evidence/outputs/"
F = "docs/b1_scientific_freeze/runs/run_20261003T045139_110133Z/"
A = "docs/phase_b_v2_seed2026_scientific_analysis/v1/"
V = P + "seed2027_b1_epoch7_recovery_v7/"
T = "src/yuntapr/training/phase_b_v2_seed2027_b1_epoch7_recovery_v7/"
H = "docs/phase_a_evidence_hardening/"
sources = {
    "RUNTIME": ["docs/audits/20261021_completed_work_review/evidence/runtime_snapshot.json",
                "docs/audits/20261021_completed_work_review/evidence/v7_code_identity.json",
                "docs/audits/20261021_completed_work_review/evidence/seed2027_completed_e0.json",
                "docs/audits/20261021_completed_work_review/evidence/FINAL_LIVE_OBSERVATION.json",
                "docs/audits/20261021_completed_work_review/RUN_STATE_CHANGE.md"],
    "V7": [V+"release.json", V+"FAILED_ANCESTOR.json", V+"config.json",
           T+"authority.py", T+"accounting.py", T+"quota.py", T+"engine.py", T+"recovery.py"],
    "FREEZE": ["config/science_v2/scientific_freeze_v2_registry_v1.json",
               "config/science_v2/phase_a_protocol_frozen_v1.json",
               "config/science_v2/quantile_head_v2_frozen_v1.json",
               "docs/scientific_freeze_v2/approval_runs/run_20261007T012725Z/researcher_approval.txt"],
    "DATA": [F+"sample_set_freeze.json", F+"normalization_b1_2023_shared_v1.json",
             F+"b1_2023_formal_manifest.csv", F+"b1_2024_formal_manifest.csv",
             F+"b0_matched_control_2023_formal_manifest.csv", F+"b0_matched_control_2024_formal_manifest.csv",
             "src/yuntapr/data/dataset_b1.py", "src/yuntapr/data/himawari_b13.py",
             "src/yuntapr/data/imerg_v07.py", "src/yuntapr/data/formal_policy.py"],
    "SPATIAL": ["config/spatial/sp04_coordinate_manifest_v1.json",
                "config/spatial/sp04_target_cell_membership_v1.csv",
                "src/yuntapr/spatial/sp04_mapping.py", "src/yuntapr/spatial/projection.py"],
    "GFS": [S+"stage0_continuous_engineering/run_20260928T041855_828904Z/GFS/GFS_TIME_SEMANTICS_SUMMARY.md",
            S+"stage0_gfs_thermo_compatibility/run_20260928T084334_575397Z/THERMO/gfs_thermo_inventory_summary.md",
            S+"stage0_gfs_thermo_compatibility/run_20260928T084334_575397Z/TIME_LINEAGE/AUXILIARY_TIME_CONFLICT_REPORT.md",
            S+"stage0_gfs_thermo_compatibility/run_20260928T084334_575397Z/src/compat_rules.py",
            S+"stage0_gfs_thermo_compatibility/run_20260928T084334_575397Z/src/unit_pressure_audit.py",
            S+"stage0_gfs_provenance_vintage_resolution/run_20260928T092552_449937Z/FINAL_GFS_PROVENANCE_VINTAGE_REPORT.md",
            S+"stage0_final_gate_package/run_20260928T113745_449683Z/STAGE0_MASTER_STATUS.md"],
    "DEM": [S+"stage0_spatial_static_closeout/run_20260928T095818_821492Z/DEM/dem_audit_summary.json",
            S+"stage0_spatial_static_closeout/run_20260928T095818_821492Z/DEM/terrain_smoke_result.json",
            S+"stage0_spatial_static_closeout/run_20260928T095818_821492Z/src/audit_dem.py",
            S+"stage0_spatial_static_closeout/run_20260928T095818_821492Z/src/spatial_rules.py",
            H+"TERRAIN_STRATIFICATION_CANDIDATES.md"],
    "TEST2025": ["config/evaluation/b0_2025_catalogue_only_authorization_v1.1.json",
                 "docs/final_test_b0/catalogue_gate_v1_1/catalogue_only_runs/run_20261003T015507_526850Z/final_status.json"],
    "OLDTRAIN": ["docs/formal_training/b0_phase_a/runs/run_20261001T035003_243409Z/B0_PHASE_A_FORMAL_TRAINING_REPORT.md",
                 "docs/formal_training/b0_phase_b_finalfit/runs/run_20261002T035929_487644Z/final_status.json",
                 "docs/formal_training/b0_matched_phase_a/runs/run_20261003T093519_542831Z/final_status.json",
                 "docs/formal_training/b1_phase_a/runs/run_20261003T093522_417735Z/final_status.json"],
    "OLDFAIL": ["docs/paired_extended_pipeline/runs/run_20261005T043214_165890Z/b0_matched_phase_b_execution_result.json",
                "docs/paired_extended_pipeline/runs/run_20261005T043214_165890Z/phase_b_orchestration_failure_20261005T141344_810928Z.json"],
    "PHASEA": ["docs/v2_phase_a_review/paired_packets/run_20261009T072307_459014Z/V2_PAIRED_PHASE_A_REVIEW.md",
               "docs/v2_paired_phase_a_review/runs/run_20261009T072307_459014Z/B0_MATCHED_V2/final_review.json",
               "docs/v2_paired_phase_a_review/runs/run_20261009T072307_459014Z/B1_V2/final_review.json",
               H+"SCIENTIFIC_EVIDENCE_AUDIT.md", H+"final_status.json"],
    "MODEL": ["src/yuntapr/models/quantile_v2/parameterization.py",
              "src/yuntapr/models/quantile_v2/outputs.py", "src/yuntapr/models/probability_heads.py"],
    "METRICS": ["src/yuntapr/experimental/phase_b_v2_formal_integration_candidate/metrics.py",
                "src/yuntapr/experimental/phase_b_v2_ablations/metrics.py",
                "src/yuntapr/experimental/phase_b_v2_ablations/validation.py", T+"evaluation.py"],
    "SEED2026": [P+"seed2026_operator_v3/execution_status.json", A+"RECOMPUTATION_AUDIT.json"],
    "BACKUP": [A+"CHECKPOINT_PAYLOAD_AUDIT.json",
               "docs/phase_b_v2_multiseed_preparation/v1/BACKUP_VERIFICATION.json",
               "docs/phase_b_v2_multiseed_preparation/v1/README.md"],
    "RECOVERY": [P+"seed2027_b1_epoch7_recovery_v4/DELTA_TESTS_attempt1.log",
                 P+"seed2027_b1_epoch7_recovery_v5/FAILED_ANCESTOR.json",
                 P+"seed2027_b1_epoch7_recovery_v5/postmortem_20261021/failure_sanitized.txt",
                 P+"seed2027_b1_epoch7_recovery_v5/postmortem_20261021/final_status.json",
                 P+"seed2027_b1_epoch7_recovery_v6/FAILED_ANCESTOR.json", V+"FAILED_ANCESTOR.json"],
    "GOVERNANCE": [H+"RECOVERY_GOVERNANCE_GAP_REVIEW.md",
                   "docs/v2_scientific_acceptance/runs/run_20261009T112710_013267Z/delivery_v2/recovery_best_chronology_note.json",
                   "docs/v2_scientific_acceptance/runs/run_20261009T112710_013267Z/delivery_v2/RECOVERY_GOVERNANCE_DEVIATION.md"],
    "ANALYSIS": [A+"SCIENTIFIC_RESULTS.md", A+"FAILURES_AND_LIMITATIONS.md", A+"manifest.json",
                 A+"tables/final_metrics.csv", A+"tables/rain_strata.csv", A+"TEST_RESULTS.json"],
    "MAINLINE": [S+"stage0_spatial_decision_update/run_20260928T102636_513428Z/freeze_registry.json",
                 "config/science_contract_v1.1.yaml", "src/yuntapr/diagnostics/candidates.py",
                 H+"TERRAIN_STRATIFICATION_CANDIDATES.md"],
    "FIX": ["src/yuntapr/experimental/phase_b_v2_multiseed_candidate/protocol.py",
            "src/yuntapr/experimental/phase_b_v2_multiseed_candidate/authority.py",
            "tests/completed_work_review/test_predecessor_interface.py",
            "docs/audits/20261021_completed_work_review/evidence/P1_001_before.txt",
            "docs/audits/20261021_completed_work_review/evidence/P1_001_after.txt"],
}


def run(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT).decode().strip()


def main():
    fix = run("rev-parse", "HEAD")
    cached = {}
    for row in json.loads((OUT/"evidence/source_manifest.json").read_bytes())["observations"]:
        if row["source"] == "isolated_base":
            cached[row["path"]] = row
    index = {}
    lines = ["# 审查来源索引", "", "SHA和可用Git历史中的最后修改commit见机器索引；来源中的旧状态只适用于其原始时刻。", ""]
    for label, paths in sources.items():
        index[label] = []
        lines.extend(["## " + label, ""])
        for relative in paths:
            path = ROOT/relative
            if relative in cached and relative != "src/yuntapr/experimental/phase_b_v2_multiseed_candidate/protocol.py":
                actual = cached[relative]["sha256"]
            else:
                actual = hashlib.sha256(path.read_bytes()).hexdigest()
            last = run("log", "-1", "--format=%H", "--", relative)
            index[label].append(dict(path=relative, sha256=actual,
                                    last_change_commit_in_available_history=last or None,
                                    inspected_at_base=BASE, local_fix_commit=fix if label == "FIX" else None))
            lines.append(f"- [{path.name}](../../../{relative})")
        lines.append("")
    (OUT/"SOURCES.md").write_text("\n".join(lines), encoding="utf-8")
    (OUT/"evidence/REVIEWED_SOURCE_INDEX.json").write_text(json.dumps(index,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

    # Matrix rows are scientific work items, not a test-count scorecard.
    items = [
        ("实际v7运行/发布身份", "RUNTIME,V7", "EARLY_RUNNING_LATER_RESOURCE_GUARD_EXIT", "初期身份匹配；收尾PID不存在；GUI退出收据；667源pin一致", "旧RUNNING快照已陈旧；未探测native Job全集；远端404", "P0运行关注"),
        ("RUN-01资源保护退出", "RUNTIME,V7", "AVAILABLE_COMMIT_LIMIT_NO_AUTOMATIC_RECOVERY", "Owner traceback；GUI退出码1/Job清空；最后心跳19:15:09", "压力根因/精确退出时刻未定；不能证明审查零资源影响；不查最终账本", "P0运行事件"),
        ("Scientific Freeze与后续授权追溯", "FREEZE,V7", "IDENTITY_VERIFIED", "15个可读冻结引用SHA匹配；具体LAST/人类指令绑定", "私有mask不重开；平台原始消息非数字签名", ""),
        ("六槽时序/训练验证配对", "DATA", "METADATA_VERIFIED", "70560帧元数据；10455/10501场；无选中因果/配对错误", "不重新读取原始载荷", ""),
        ("当时业务可用性", "DATA,GFS", "NOT_ESTABLISHED", "27880次late-created引用；GFS历史首发缺证", "观测因果不等于实时获取；不外推NRT", "科研决定"),
        ("IMERG参考窗/缺测/有效mask", "DATA", "CODE_REVIEW_AND_INHERITED_RUN", "V07 Final；零雨有效；窗末分析；3430格", "未新解码数据；局部/历史工程策略不等于M1", ""),
        ("Train-only共享normalization", "DATA,FREEZE", "FROZEN_IDENTITY_VERIFIED", "2023-only；62730槽暴露；mu/sigma冻结", "未重拟合；旧独立B0的不同人口不可混比", ""),
        ("SP04科学网格", "SPATIAL", "PUBLIC_IDENTITY_VERIFIED", "实际float32轴/10000x25索引", "mask实际payload未新读", ""),
        ("GFS main/thermo结构与时间审计", "GFS", "INHERITED_PARTIALLY_COMPATIBLE", "24388 main/12960 thermo；8820研究期候选配对", "未批准正式组合；非全像元QC", ""),
        ("GFS forecast vintage/来源", "GFS", "RESEARCHER_DECISION_REQUIRED", "无直接primary time conflict；来源链有局限", "release/availability未建立；init+5h是假设", "科研决定"),
        ("DEM真实覆盖与QC", "DEM", "INHERITED_COMPLETED_AUDIT", "237 SRTM tiles；云南FULL；33x33真实梯度smoke", "非高程精度验证；生产特征未实现", ""),
        ("2025封存/访问历史", "TEST2025,RUNTIME", "AUDIT_RECORDS_ONLY", "旧catalogue/QC获批读2676986256像元；模型forward0", "不能声称从未读过；历史属性访问未instrument；本轮不读数据", "P0解释关注"),
        ("原独立B0 Phase-A", "OLDTRAIN", "HISTORICAL_COMPLETE", "19epoch BEST11；11720/11727人口", "不等于配对B0；不新加载checkpoint", ""),
        ("原独立B0 FinalFit", "OLDTRAIN", "HISTORICAL_COMPLETE", "11epoch/128964更新", "不授予当前新FinalFit许可；无最终测试结果", ""),
        ("v1 B0-Matched/B1 Phase-A", "OLDTRAIN", "HISTORICAL_COMPLETE", "21/16epoch；109788/83648保留更新", "B1另有5228丢弃更新/88876全部尝试", ""),
        ("v1 paired Phase-B FinalFit", "OLDFAIL", "FAILED_AFTER_FOUR_COMPLETE_EPOCHS", "50537实际更新；LAST41912；物理overflow", "不能标完成；本轮不恢复", "历史缺陷"),
        ("v2配对Phase-A与BEST复核", "PHASEA", "INHERITED_COMPLETE", "两模型17epoch；BEST9/update47052；10501场", "2024开发探索；历史恢复治理未追认", ""),
        ("发生/条件分位数数学及物理量API", "MODEL,FREEZE", "CODE_REVIEW_AND_INHERITED_RUN", "p(R>.1)；FP64单调qlog；物理显式转换", "无任意阈值尾部或精确全分布均值；不重做精度压力检查", ""),
        ("Brier/AUROC/AP/共同Core口径", "METRICS,PHASEA", "CODE_REVIEW_AND_PUBLISHED_RECEIPTS", "精确同分组；Core除N；条件pinball除R", "未重排全scoreDB；概率cutoff未冻结", ""),
        ("seed2026正式六组", "SEED2026,ANALYSIS", "RECEIPTS_VERIFIED_COMPLETE", "54收据digest；六组9epoch；282312保留/298474累计", "16162丢弃尝试；不读实盘账本", ""),
        ("seed2026指标追溯/历史分析", "SEED2026,ANALYSIS", "PUBLISHED_METRICS_MATCH", "六组最终表指标与原receipt一致；旧bootstrap证据继承", "单seed开发集探索区间；无确认性成功判据", ""),
        ("seed2026 checkpoint/备份", "BACKUP", "INHERITED_PAYLOAD_AND_BACKUP_AUDIT", "六份最终LAST SHA；42文件异盘副本", "本轮不读payload；非永久或离线恢复保证", ""),
        ("seed2027历史/恢复额度", "V7,RECOVERY", "RECORDED_ANCESTRY_RECONCILED", "旧166305/166304；adopt83648；cap364969", "1次旧不确定尝试；缺少部分原termination；不查全部旧账本", ""),
        ("v4/v5/v6发布与真实失败", "RECOVERY,V7", "HISTORICAL_FAILURE_PRESERVED", "v4spawn不确定；v5ImportError；v6WinError5；各零新增", "不把测试/发布当成功；v4根因不额外推断", "历史P1"),
        ("seed2027 E0两组", "RUNTIME,V7", "COMPLETED_E0_RECEIPTS_VERIFIED", "两份9epoch报告及receipt digest/LAST身份", "B0/E1期间保护退出，其余臂未完成；不是六组完成", ""),
        ("历史B1恢复治理", "GOVERNANCE", "NOT_RATIFIED", "BEST9早于恢复15；独立LAST批准未登记", "工程证据不代替研究者接受决定", "P0治理关注"),
        ("上尾/强雨科学限制", "ANALYSIS,PHASEA", "KNOWN_UNRESOLVED", "q32目标98.4375%而实际约95%；>50mm/h稀少暴露", "不能靠修改阈值/权重解决或声称全面优势", "科研决定"),
        ("DEM物理梯度/压力层掩膜", "DEM,MAINLINE,GFS", "REAL_SMOKE_AND_SYNTHETIC_CANDIDATES_ONLY", "WGS84物理距离真实smoke；synthetic坡向/风上坡；PS单位metadata", "真实above-surface mask、生产尺度/聚合未落地；行方向要适配", ""),
        ("DOTE/DTFM与B0-B8", "MAINLINE", "COMPATIBILITY_ONLY_NOT_IMPLEMENTED", "现有概率/目标网格接口未见硬冲突", "未找到V1.3全文；没有正式新模块、消融或有效性证据", ""),
        ("seed2028前序识别P1修复", "FIX,V7", "FIXED_ISOLATED_5_TESTS_PASS", "2项干净基线失败；5项回归通过；authority仍拒绝", "未发布/部署；旧prepared_release不覆盖新代码", "P1-001"),
    ]
    fields = ["item", "audit_base_commit", "git_commit", "source_ids", "source_paths", "source_sha256",
              "run_evidence", "verification_status", "limitations", "priority"]
    with (OUT/"EVIDENCE_MATRIX.csv").open("w",encoding="utf-8-sig",newline="") as stream:
        writer = csv.DictWriter(stream,fieldnames=fields); writer.writeheader()
        for item, labels, status, evidence, limits, priority in items:
            refs = [x for label in labels.split(",") for x in index[label]]
            writer.writerow(dict(item=item, audit_base_commit=BASE,
                git_commit=fix if labels.startswith("FIX") else (refs[0]["last_change_commit_in_available_history"] or "RUNTIME_UNCOMMITTED"),
                source_ids=labels, source_paths=json.dumps([r["path"] for r in refs],ensure_ascii=False),
                source_sha256=json.dumps({r["path"]:r["sha256"] for r in refs},ensure_ascii=False),
                run_evidence=evidence, verification_status=status, limitations=limits, priority=priority))
    audit = json.loads((OUT/"evidence/seed2026_receipt_audit.json").read_bytes())
    reports = audit["reports"]
    order = all(len({r["epochs"][i]["train_ids_sha"] for r in reports}) == 1 for i in range(9))
    dev = len({e["dev_ids_sha"] for r in reports for e in r["epochs"]}) == 1
    blocks = len({e["scene_blocks_sha"] for r in reports for e in r["epochs"]}) == 1
    checks = dict(paired_train_order_per_epoch=order, all_development_ids_same=dev, all_scene_blocks_same=blocks,
        complete_nine_epochs=all(r["epoch_sequence"] == list(range(1,10)) for r in reports),
        every_population_correct=all(e["scenes"] == 10501 and e["n_valid"] == 36018430 and e["train_scenes"] == 10455 and e["train_batches"] == 5228 for r in reports for e in r["epochs"]),
        all_block_populations_pool=all(e["blocks_pool_valid"] and e["blocks_pool_rain"] for r in reports for e in r["epochs"]),
        all_receipt_digests=all(e["receipt_match"] for r in reports for e in r["epochs"]),
        all_published_metric_matches=all(all(r["published_metric_matches"].values()) for r in reports),
        all_final_last_refs_match=all(r["final_ledger_last_match"] for r in reports))
    (OUT/"evidence/aggregate_verification.json").write_text(json.dumps(checks,indent=2)+"\n",encoding="utf-8")
    if not all(checks.values()):
        raise ValueError(checks)
    (OUT/"CODE_DIFF.patch").write_bytes(subprocess.check_output(["git","diff",BASE,fix,"--","src/yuntapr/experimental/phase_b_v2_multiseed_candidate/protocol.py","tests/completed_work_review/test_predecessor_interface.py"],cwd=ROOT))
    (OUT/"evidence/BRANCH.json").write_text(json.dumps(dict(base_commit=BASE,fix_commit=fix,
        branch=run("branch","--show-current"),independent_git_directory=run("rev-parse","--absolute-git-dir"),
        remote_publication="NOT_PERFORMED",remote_verification="CONNECTOR_404_UNVERIFIED",
        deployed=False,merged_to_main=False),indent=2)+"\n",encoding="utf-8")
    print(json.dumps(dict(source_groups=len(index),evidence_matrix_rows=len(items),aggregate_checks=checks,fix_commit=fix),indent=2))


if __name__ == "__main__":
    main()
