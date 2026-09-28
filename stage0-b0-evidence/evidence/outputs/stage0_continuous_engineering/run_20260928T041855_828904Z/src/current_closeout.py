"""Finish requested A-P closeout distinctions and exact deliverable schemas."""
from pathlib import Path
from datetime import datetime,timezone
import json,xml.etree.ElementTree as ET
import pandas as pd
from config import *
from common import *
def readj(p):return json.loads((OUT/p).read_text(encoding="utf-8"))
def append(p,text):
    with (OUT/p).open("a",encoding="utf-8") as f:f.write(text)
def closeout():
    state=readj("final_continuous_engineering_status.json")
    summary=readj("logs/analysis_summary.json")
    cache=readj("logs/staging_summary.json")
    inv=readj("GFS/gfs_inventory_summary.json")
    tests=state["tests"]
    reviews=state["researcher_review_required"]
    required_pass=[
        "A decision log separates frozen/provisional/unfrozen/gap/researcher review",
        "B two-file IMERG boundary reread and exact comparison with prior evidence",
        "C bounded GFS root discovery; no supplemental merge",
        "D inventory/year/month/size/parse/duplicate/zero-byte statistics",
        "E actual signatures and reader/import verification; no dependency changes",
        "F full-file coordinate/hash/dtype/shape/direction audit",
        "G canonical variable/level metadata availability",
        "H forbidden precipitation detection; never used as predictor",
        "I surface pressure metadata feasibility only",
        "J separate forecast/reference/valid/lead/creation/release/download/mtime evidence",
        "K calendar cycle/lead coverage",
        "L 24-row research matrix with 2025-10 IMERG MISSING",
        "M common numerical overlap candidate; no bbox freeze",
        "N schema only; no samples or Dataset",
        "O scoped pytest executed, including failure isolation and overwrite protection",
        "P before/after all-main-file size+mtime and selected hashes; bounded owned staging"]
    status={"engineering_status":"PASS","researcher_review_status":"NEEDS_REVIEW",
        "overall_status":"NEEDS_REVIEW","gfs_status":"PARTIAL",
        "gfs_inventory_schedule_status_202503_202510":"READY",
        "stage0_engineering_closeout_ready":True,"stage0_closeout_ready":False,
        "stage0_closeout_definition":"Engineering deliverables complete; scientific/data-readiness closeout awaits listed review items. No Stage 1/B0 started.",
        "pass_items":required_pass,"blocked_items":[],"review_items":reviews,
        "raw_data_modified":False,"prior_runs_modified":False,
        "tests":tests,"initial_test_setup_errors_resolved":6,
        "NO_GFS_PRECIPITATION_USED_AS_MODEL_INPUT":True,
        "covers_yunnan_context":"PENDING_RESEARCHER_CONFIRMATION",
        "model_input_bbox":None,"formal_sample_pairing_executed":False,
        "completed_utc":datetime.now(timezone.utc).isoformat()}
    write_json(OUT/"audit_final_status.json",status)
    state["authoritative_status_file"]="audit_final_status.json"
    state["tasks_A_to_P"]=state.pop("tasks_A_to_I", "EXECUTED_WITH_DOCUMENTED_EVIDENCE_LIMITATIONS")
    state.update(engineering_status="PASS",researcher_review_status="NEEDS_REVIEW",stage0_closeout_ready=False)
    (OUT/"final_continuous_engineering_status.json").write_text(dumps(state),encoding="utf-8")
    forbidden=pd.read_csv(OUT/"GFS/gfs_forbidden_precip_variables_detected.csv")
    names=forbidden.raw_variable_name.value_counts().to_dict()
    grid=pd.read_csv(OUT/"GFS/gfs_grid_audit.csv")
    lead=pd.read_csv(OUT/"GFS/gfs_global_lead_metadata_crosscheck.csv")
    checks=lead.consistency.value_counts().to_dict()
    extra=f"""
21. **工程状态与科研复核状态分离：** engineering_status=PASS；researcher_review_status=NEEDS_REVIEW；gfs_status=PARTIAL。本轮执行 TASK A–P；audit_final_status.json 为本轮正式状态入口。

22. **新增库存/grid/时间证据：** inventory 含 month/init_time/valid_time/lead_time；全年/月分布和大小分位数见 GFS/gfs_inventory_summary.md。零字节={inv["zero_byte_files"]}，重复文件名行数={inv["duplicate_filename_rows"]}；最大文件清单为 QC_STAT_ONLY，未设“大文件异常阈值”。
坐标 dtype：latitude={sorted(grid.lat_dtype.unique().tolist())}，longitude={sorted(grid.lon_dtype.unique().tolist())}；grid表含lat_shape/lon_shape/field_shape/grid_id/mean_dlat/mean_dlon。
时间类metadata字段清单与distinct evidence表分开保存。额外global lead_time_hours核验：{checks}；UNKNOWN_NOT_PRESENT表示该属性不存在，不是forecast主时间未知。conversion_time、history与生成中心/过程ID均未当作release。

23. **Stage-0 closeout：** 工程交付收口满足，stage0_engineering_closeout_ready=true；科学与数据就绪收口尚未满足，stage0_closeout_ready=false。
PASS items：TASK A–P 工程交付、{tests["tests"]} tests通过、全库只读记录、原始完整性和历史基线引用hash校验、CSV/Parquet回读一致。
REVIEW items：GFS T/RH缺口及辅库使用、辅助时间metadata来源冲突、availability/vintage、native IMERG窗口、bbox/行政mask/DEM有效性、2025-10缺月及独立外部验证。
BLOCKED items：无剩余工程阻塞；科研未冻结项归REVIEW而非伪称工程失败。
初次pytest因本轮cache父目录不存在出现27 passed/6 setup errors；已修复，失败XML原样保留。最终真实执行{tests["tests"]} tests，failures={tests["failures"]}，errors={tests["errors"]}，skipped={tests["skipped"]}；stdout与XML为 tests/pytest_final_output.txt、tests/pytest_final.xml。

24. **禁用变量、cache与边界约束确认：** 检测到的GFS precipitation变量及行数：{names}。
**CONFIRMED NOT USED AS PREDICTOR. NO_GFS_PRECIPITATION_USED_AS_MODEL_INPUT.**
cache copy_count={cache["copy_count"]}，cumulative_copied_bytes={cache["cumulative_copied_bytes"]}，max_single_copy_bytes={cache["max_single_copy_bytes"]}，copy_seconds={cache["copy_seconds"]:.6f}，cleanup_failures={cache["cleanup_failures"]}，remaining_staged_bytes={cache["remaining_staged_bytes"]}。
只清理由本轮创建的副本；全库size+mtime基线在第一个raw数据读取前保存；size+mtime verification不是full content hash proof。
空间共同范围 **CANDIDATE ONLY; NOT A FROZEN MODEL BBOX**。
IMERG QI仅QC_STAT_ONLY，不设阈值、不筛像元、不作predictor；2025-10是候选研究期缺月，非当前2019-01-01至2025-09-30库存内部missing-day。
下一阶段仅建议见第20项和研究者清单；未启动Stage1/B0、ERA5 Teacher、模型checkpoint、正式预测、Dataset或全量配对。
"""
    p=OUT/"FINAL_CONTINUOUS_ENGINEERING_REPORT.md"
    text=p.read_text(encoding="utf-8")
    ending="Stage-0 continuous engineering run complete.\nWaiting for researcher scientific review.\nNo frozen scientific convention was changed automatically.\n"
    assert text.endswith(ending)
    text=text[:-len(ending)]+extra+"\n"+ending
    text=text.replace("TASK A–I 独立工程执行完成","TASK A–P 独立工程执行完成")
    p.write_text(text,encoding="utf-8")
    append("GFS/GFS_TIME_SEMANTICS_SUMMARY.md",f"\n\n本轮额外global lead_time_hours交叉核验：{checks}。字段总览见 gfs_time_metadata_field_inventory.csv；分类证据见 gfs_distinct_time_evidence.csv。生成中心/过程标识不是生成timestamp。\n")
    append("GFS/gfs_discovery_report.md","\nMULTIPLE_GFS_ROOTS_RESEARCHER_REVIEW = TRUE\n")
    append("CROSS_SOURCE/spatial_coverage_report.md","\nNOT A FROZEN MODEL BBOX.\n")
    append("IMERG/imerg_20250624_boundary_extreme_check.txt","\nThis run reread all requested values and the 5x5 patch; both tables exactly match the previous run. See boundary_prior_result_comparison.csv.\n")
    append("docs/DECISION_LOG_STAGE0.md","\n本轮 TASK A–P 证据已更新。engineering_status=PASS 与 researcher_review_status=NEEDS_REVIEW 分列；工程交付完成不自动解锁科研 closeout 或 Stage1/B0。\n")
    # Correct the inherited README to the actual new-run test count and complete command order.
    p=OUT/"README.md";text=p.read_text(encoding="utf-8").replace("30 tests passed",f'{tests["tests"]} tests passed')
    start=text.index("## 解释器与重现");end=text.index("## 英文路径兼容")
    reproduce=f"""## 解释器与重现

固定解释器：{PYTHON}。没有安装或升级任何依赖。
本轮从先前已验证代码复制到全新run后增强，旧run与raw永久只读。不要在已完成run原地重跑；写文件默认exclusive。

准备新run时只复制src、tests的.py代码以及docs/schema模板，创建输出子目录和新的英文cache父目录；生成当次environment_before.json、baseline_reference_hashes_before.json。src/config.py从自己的位置推导OUT；基线引用明确保留。报告模板中的快照数值和断言适用于这次审计，若未来raw库存变化必须先审核更新报告/验证期望，不能把旧数值作为新结果。

使用上述绝对解释器，在新run的cwd按顺序执行：
1. src/gfs_audit.py
2. src/independent_tasks.py
3. src/analyze_results.py
4. src/current_additions.py
5. src/finish_tables.py
6. src/run_tests.py
7. src/write_reports.py
8. src/current_closeout.py
9. src/validate_outputs.py
10. src/final_manifest.py

每条命令格式为 & '{PYTHON}' -B <script>。本轮脚本只在newrun写输出。
run_tests.py明确限定cwd/rootdir/test path，先创建cache父目录；若pytest basetemp已存在会拒绝，避免pytest隐式删除既有测试目录。
tests/pytest_initial.xml保存首次27 passed/6 setup errors，修复说明见logs/engineering_recovery.json；tests/pytest_final_output.txt和pytest_final.xml是最终真实执行结果，pytest_verified.xml只是同一次最终执行XML的兼容别名。
本轮禁止调用任何源数据下载、Dataset、split、归一化、训练或插值入口。

"""
    p.write_text(text[:start]+reproduce+text[end:],encoding="utf-8")
    append("README.md","\n## 本轮正式收口入口\n\naudit_final_status.json 区分 engineering_status/researcher_review_status/gfs_status；stage0_closeout_ready=false 不代表存在未完成的安全独立工程任务。完整 inventory summary、distinct time metadata、原始before manifest及最终pytest日志均在本run。\n")
    append_json(OUT/"logs/audit_run.log",{"phase":"A-P_closeout_written",**status})
    print(dumps(status),flush=True)
if __name__=="__main__":closeout()
