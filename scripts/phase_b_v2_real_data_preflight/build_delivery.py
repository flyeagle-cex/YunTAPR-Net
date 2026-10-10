"""Build public summaries from the single measured audit; no raw input access."""
from pathlib import Path
import hashlib
import json
import re
import ast
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"docs/phase_b_v2_real_data_preflight/v1"
result=json.loads((OUT/"audit_results.json").read_text(encoding="utf-8"))
ledger=json.loads((OUT/"DATA_ACCESS_LEDGER.json").read_text(encoding="utf-8"))
selection=json.loads((OUT/"DECODE_SELECTION.json").read_text(encoding="utf-8")) if (OUT/"DECODE_SELECTION.json").exists() else {}
checks=result["checks"]
def dump(name,value):
    with (OUT/name).open("x",encoding="utf-8",newline="\n") as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2);stream.write("\n")
def md(name,value):
    with (OUT/name).open("x",encoding="utf-8",newline="\n") as stream:stream.write(value.strip()+"\n")
def pretty(value):return json.dumps(value,ensure_ascii=False,indent=2)
def code(value):return "\n\n```json\n"+pretty(value)+"\n```\n"
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
xml=ET.parse(OUT/".local/unit_attempt_001.xml")
suites=list(xml.getroot().iter("testsuite"))
test_summary={"unit_tests":sum(int(s.attrib.get("tests",0)) for s in suites),
              "failures":sum(int(s.attrib.get("failures",0)) for s in suites),
              "errors":sum(int(s.attrib.get("errors",0)) for s in suites),
              "synthetic_training_tests_rerun":0,"model_forwards":0,"optimizer_steps":0,
              "initial_launch_failure":"Output directory missing; stopped before pytest or real data reads",
              "repair":"Created only isolated .local log directory",
              "environment_probe":"psutil unavailable; used Windows GetProcessMemoryInfo, no package installation"}
dump("READONLY_TOOL_TEST_RESULTS.json",test_summary)
text=(OUT/".local/unit_attempt_001.log").read_text(encoding="utf-8-sig")
# Success log has no traceback; refuse publication of local paths/user names.
if ":\\" in text or "hostname" in text.lower():raise ValueError("Private log content refused")
md("READONLY_TOOL_TEST_RESULTS.log",text)
new_sources=sorted((ROOT/"src/yuntapr/experimental/phase_b_v2_real_data_preflight").glob("*.py"))+sorted((ROOT/"scripts/phase_b_v2_real_data_preflight").glob("*.py"))+sorted((ROOT/"tests/phase_b_v2_real_data_preflight").glob("*.py"))
for p in new_sources:
    tree=ast.parse(p.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr in ("backward","step","forward","fit","load_state_dict"):
            raise ValueError("Training/inference/fit API refused: "+p.name)
dump("STATIC_NO_TRAINING_AUDIT.json",{"status":"PASS","AST_source_files":len(new_sources),
    "forbidden_call_attributes":["backward","step","forward","fit","load_state_dict"],
    "frozen_sources_modified":False,"imports":"Frozen metadata validators, readers and SP04 only; no model or optimizer",
    "limits":"Cooperative code audit, not a malicious-process sandbox"})
md("README.md",f"""
# Phase-B v2 首次真实数据只读预检 v1

本轮独立授权仅覆盖冻结 2023 Train / 2024 Development、shared scaler、云南 mask 与 SP04。真实预检状态：**{result["overall_status"]}**；科学审批与训练许可均未升级。基线 {result["baseline_commit"]}。

- FROZEN_DATA_IDENTITY_AUDIT.md：冻结 ID、配对资格与准确文件引用。
- TEMPORAL_CAUSALITY_AUDIT.md：六时相、观测完成时间与 Final 标签角色。
- SCALER_MASK_SP04_AUDIT.md：真实字节 SHA、归一化和地理轴。
- DECODE_AND_RESOURCE_REPORT.md：预先固定取样、限定解码、CPU 资源。
- DATA_ACCESS_LEDGER.json：受控读取账本及计数范围。
- BLOCKERS_AND_REPAIRS.md：阻塞、初次工具启动失败与修复。
- REAL_DATA_READINESS_GATE.md / final_status.json：真实完成范围及停止边界。
- audit_results.json / DECODE_SELECTION.json / manifest.json：机器证据及 SHA。

代码位于 src/yuntapr/experimental/phase_b_v2_real_data_preflight/；入口 scripts/phase_b_v2_real_data_preflight/run_preflight.py。只读检测不会实例化模型，未接入正式 Runner，未改冻结源文件。原始影像、降水数组、地理 mask 数组、私有路径和机器日志不公开。

本轮按明确指定的 Markdown/JSON 交付；不重复旧 PDF。公开证据不是科学接受或执行授权。
""")
md("FROZEN_DATA_IDENTITY_AUDIT.md","""
# 冻结数据身份审计

依据冻结 v2 Phase-A 协议 a0141f21cfa997d5adb72dff5afb32b17dc7edcf5f3397fc9c4bfe2ea42048be、四份样本 manifest 及 frame_identity_index，未另选数据源、补样本、改变划分或重新搜索磁盘。

原始顺序按 index、唯一 sample_id 与 UTC 严格递增检查；角色按 2023 Train / 2024 Validation 检查，后者科研解释仍是开发验证。B0/B1 比较目标窗口、IMERG 路径引用及 SHA、index、资格、云南有效格点数和最新时相；B0 最新文件大小、SHA、CF 时间还与 B1 slot5 逐项核对。
"""+code(checks.get("frozen_sample_identity",{"status":"NOT_VERIFIED"}))+code(checks.get("source_reference_inventory",{"status":"NOT_VERIFIED"}))+"""
所有 stat 均针对 manifest 明确引用的路径，不遍历原始目录、不下载。日文件被多个场景引用是正常复用，不等于重复场景。相同路径的不同 SHA/大小/年份直接阻塞。stat 可证明当时路径存在及登记大小符合，不能证明未选中文件完整内容未变化；未读取的 payload SHA 明确 NOT_VERIFIED。
"""+code(checks.get("protected_sources",{"status":"NOT_VERIFIED"})))
md("TEMPORAL_CAUSALITY_AUDIT.md","""
# 时间因果性审计

分析时刻为 IMERG 目标窗口开始后 30 分钟。B1 oldest→latest 为分析前 60/50/40/30/20/10 分钟，B0 取同一 slot5；检查 nominal、obs_start≤obs_end≤analysis_time。IMERG 日路径和半小时 index 必须与窗口绑定。
"""+code(checks.get("temporal_metadata",{"status":"NOT_VERIFIED"}))+"""
限定实际解码还核对 CF obs_start、obs_end、date_created 与冻结帧记录一致，并再次检查截止时刻。date_created 晚于分析时刻不被误写为观测时间越界；它说明观测完成的因果性与文件生产/传输/入库可用性不同。文件生成与业务延迟没有获得近实时可用性证明。

实际解码只接受 GPM_3IMERGHH_07、IMERG Final Run V07、48 个半小时片段及 mm hr-1。Final 参考用于回顾性监督与开发验证；不能把其事后可用性写成业务实时参考已到达，也不能把 2024 写成新的独立确认集。
""")
md("SCALER_MASK_SP04_AUDIT.md","""
# Shared scaler、真实云南 mask 与 SP04

本轮读取冻结 scaler 和真实 mask 文件字节；不使用人工 3430 格点排列。scaler JSON 数值由 Python binary64 解析，原始 Kelvin 是 FP32，计算为 ((x.astype(float64)-mean_K)/std_K).astype(float32)。未拟合、裁剪或替换统计量。B0 与 B1 的固定预处理共用同一 artifact。

mask 使用冻结正式 read_frozen_yunnan_mask；SP04 使用原 load_sp04。原始 mask 为 130×140，裁切 [10:110,20:120] 成 100×100，必须仍有3430中心入界格点；经纬度以原始 FP32 位模式比较，禁止翻转、重建或换掩膜。SP04 10000×25 成员映射须覆盖250000唯一原生中心。

观测/参考有效掩膜表示数据有效性；云南评价 mask 表示地理范围。二者分别构造，监督交集计数，不以相互赋值替代。
"""+code(checks.get("scaler_mask_sp04",{"status":"NOT_VERIFIED"}))+"""
scaler 原始较早 JSON 中的 B0 adoption 待决文字未改写；本次使用同一 scaler 的依据是后续冻结 v2 协议 USE_FROZEN_B1_SHARED_SCALER，不生成新的研究者批准。
""")
md("DECODE_AND_RESOURCE_REPORT.md","""
# 限定解码与资源

取样在任何参考降水像元读取前固定：冻结各月顺序的索引 0、floor(n/2)、n−1。冻结仅有3–10月，2023/2024共16月，最多48实际场景；72是研究者同意的总上限。没有用降水值或模型输出筛样本，不足3场景的月份停止、不补选。
"""+code(checks.get("limited_decode",{"status":"NOT_VERIFIED"}))+code({"selected_scenes":len(selection.get("selected",[])),
    "elapsed_seconds":result["elapsed_seconds"],"resources":result["resources"],"limits":result["limits"]})+"""
每个成功场景的形状、dtype、有效性、CF 时间及耗时见 audit_results.json。只公开工程检查，不公开降水数组、图像、雨强分布或任何模型性能指标。限定解码不是全量数据 QC；受阻项目不会被标成通过。

读取先做完整文件 SHA，再以同一已计数 bytes buffer 调用 frozen netCDF readers。未创建原始数据的磁盘暂存副本。CPU 峰值由 Windows GetProcessMemoryInfo 的进程生命期 PeakWorkingSetSize 提供；不是GPU显存，也不是每场景独立峰值。耗时包含来源审计、stat、解码等预检工作，不能外推训练时长。

账本统计受控 Python application read 的成功/尝试次数及 read 返回字节，内存 netCDF view 不另记物理读取；不是操作系统底层打开次数或物理磁盘流量。前期一次已授权 PowerShell scaler 查看发生在计数器安装前，底层字节/打开数 NOT_INSTRUMENTED，单独披露，未伪装成全部已测量。
"""+code({"controlled_read_open_attempts":ledger["controlled_read_open_attempts"],
    "controlled_read_open_successes":ledger["controlled_read_open_successes"],
    "controlled_application_bytes_returned":ledger["controlled_application_bytes_returned"],
    "groups":ledger["groups"],"in_memory_netcdf_views":ledger["in_memory_netcdf_views"]}))
md("BLOCKERS_AND_REPAIRS.md","""
# 阻塞与修复记录

没有自动修正 SHA、路径、年份、资格、坐标或科学设置；没有选择另一数据集。运行只有 attempt_001，错误详情与私有路径留在 .local。已完成的独立 scaler/地理检查与受阻解码分别报告。

工程启动初次失败：新 .local 目录尚未建立，PowerShell 输出重定向失败；pytest 尚未执行，真实读取为0。创建该隔离日志目录后运行36项工具检查通过。环境探测发现 psutil 不可用，采用 Windows 原生内存计数器，未安装依赖或扩大读取权限。
"""+code(result["blockers"])+"""
未选中文件当前内容身份尚未完整 byte-hash；已有冻结 SHA 引用与实际路径/大小检查不替代该证据。本轮有限预检不主动扩成全数据读取。资源、权限或完整性异常将停止相应读取，不自动重试或更换场景。
""")
md("REAL_DATA_READINESS_GATE.md",f"""
# 真实数据就绪门槛

本轮总状态：**{result["overall_status"]}**。仅在身份、时序、scaler/mask/SP04 与限定解码全部证实符合冻结协议时才可给出 REAL_DATA_READ_ONLY_PREFLIGHT_PASS。未完成的身份项目不以样本成功代替。

{code({k:v.get("status","NOT_VERIFIED") for k,v in checks.items()})}

正式训练仍不可启动。真实只读 preflight 授权没有授权 loss 科学接受、正式源码集成、独立批准验证服务、模型推理或 seed2026 六组训练。必须由研究者独立决定效应界限、副作用容忍、多重比较、Phase-A接受范围、历史B1恢复处置、代码集成、资源与具体执行范围。真实恢复另需绑定LAST SHA、原授权祖先及新的独立决定。

本轮不自动扩大未选中 payload 身份检查或派生训练工作。2025仍封存；历史恢复仍NOT_GRANTED；2024仍为开发验证。本轮停止于此。
{code({k:result[k] for k in ("V2_PHASE_B_AUTHORIZED","FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED","RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED","HISTORICAL_RECOVERY_RATIFICATION","FORMAL_OPTIMIZER_STEPS","2025_RAW_ACCESS","2025_PIXELS_READ","HISTORICAL_CHECKPOINT_READS","MODEL_FORWARDS","MODEL_PARAMETER_UPDATES","SCALER_FITS")})}
""")
status={k:v for k,v in result.items() if k not in ("decoded",)}
status["tool_tests"]=test_summary
status["engineering_delivery"]="COMPLETE_WITH_EXPLICIT_NOT_VERIFIED_ITEMS"
status["publication"]="ACTUAL_PUSH_IDENTITY_RECORDED_SEPARATELY"
dump("final_status.json",status)
files=sorted(p for p in OUT.iterdir() if p.is_file() and p.name not in ("manifest.json","publication_receipt.json"))
files+=new_sources
manifest={"baseline_commit":result["baseline_commit"],"scope":"REAL_DATA_READ_ONLY_PREFLIGHT",
    "files":[{"path":p.relative_to(ROOT).as_posix(),"sha256":digest(p),"bytes":p.stat().st_size} for p in files],
    "source_protection":"Previous protected inventory and delivery manifests byte-checked before raw reads",
    "self_hash_omitted":True,"publication_receipt_appended_after_verified_push":True,
    "private_paths_raw_payloads_and_credentials_excluded":True}
dump("manifest.json",manifest)
allow=[p.relative_to(ROOT).as_posix() for p in files]+[(OUT/"manifest.json").relative_to(ROOT).as_posix()]
(OUT/".local/publication_allowlist.paths").write_text("\n".join(sorted(allow))+"\n",encoding="utf-8")
print(pretty({"public_files":len(allow),"status":result["overall_status"],"tests":test_summary["unit_tests"],"decoded_scenes":len(result["decoded"])}))
