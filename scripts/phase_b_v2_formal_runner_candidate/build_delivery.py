"""Finalize compact epoch-engine evidence. No model import or data preflight."""
from __future__ import annotations
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/phase_b_v2_formal_runner_candidate/v1"
BASELINE = "435f303a1bdebb30a687f8e02dd8576d0d28cb55"


def write(path: Path, text: str):
    with path.open("x",encoding="utf-8",newline="\n") as stream:stream.write(text.strip()+"\n")


def dump(path: Path, value):
    write(path,json.dumps(value,ensure_ascii=False,indent=2))


def sha(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source=json.loads((OUT/"source_identity.json").read_text(encoding="utf-8"))
    assert subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT).decode().strip()==BASELINE
    assert not subprocess.check_output(["git","diff","--name-only"],cwd=ROOT).strip()
    # The actual scaler is deliberately not opened by the packaging script.
    assert all(sha(ROOT/e["path"])==e["sha256"] for e in source["checked_public_files"])
    checkpoint_private=OUT/".local/synthetic_checkpoint_workspace"
    ledger=json.loads((checkpoint_private/"task_epoch_ledger.json").read_text(encoding="utf-8"))
    assert sum(ledger["reserved"].values())==sum(ledger["completed"].values())==30
    assert not ledger["failed"] and ledger["FORMAL_OPTIMIZER_STEPS"]==0
    cases=[json.loads(p.read_text(encoding="utf-8")) for p in sorted((OUT/"tests").glob("*_epochs.json"))]
    assert len(cases)==6 and all(c["status"]=="PASS" for c in cases)
    assert sum(c["SYNTHETIC_OPTIMIZER_STEPS"] for c in cases)==30
    assert all(c["resume_exact"] and c["resume_did_not_refund_quota"] for c in cases if c["arm"]=="E0")
    assert all(len({c["initial_sha"] for c in cases if c["model"]==m})==1 for m in ("B0_MATCHED_V2","B1_V2"))
    candidate_dir=ROOT/"src/yuntapr/experimental/phase_b_v2_formal_runner_candidate"
    code_digest=hashlib.sha256()
    for p in sorted(candidate_dir.glob("*.py")):
        ast.parse(p.read_text(encoding="utf-8"));code_digest.update(p.name.encode());code_digest.update(p.read_bytes())
    assert all(c["source_code_sha"]==code_digest.hexdigest() for c in cases)
    assert ledger["code_sha"]==code_digest.hexdigest()
    # Derive unique final results rather than counting rerun attempts twice.
    results={};attempts=[]
    for filename in ("cpu_attempt_001.xml","cpu_repair_attempt_001.xml","checkpoint_attempt_001.xml","cuda_attempt_001.xml","stop_attempt_001.xml"):
        tree=ET.parse(OUT/"tests"/filename);suite=tree.getroot().find("testsuite")
        attempts.append({"path":"tests/"+filename,**{k:int(suite.attrib[k]) for k in ("tests","failures","errors","skipped")}})
        for node in tree.findall(".//testcase"):
            key=(node.attrib["classname"],node.attrib["name"])
            device="CUDA" if filename.startswith(("cuda_","stop_")) else "CPU"
            results[key]=(device,node.find("failure") is None and node.find("error") is None and node.find("skipped") is None)
    counts={d:sum(device==d and passed for device,passed in results.values()) for d in ("CPU","CUDA")}
    assert counts=={"CPU":79,"CUDA":8} and all(p for _,p in results.values())
    # Retain complete logs privately; only machine paths are scrubbed publicly.
    raw=OUT/".local/raw_test_logs";raw.mkdir(exist_ok=True)
    for p in (OUT/"tests").glob("*"):
        if p.suffix not in (".log",".xml"):continue
        shutil.copy2(p,raw/p.name)
        text=p.read_text(encoding="utf-8")
        for prefix in (str(ROOT).replace("\\","\\\\"),str(ROOT),ROOT.as_posix()):text=text.replace(prefix,"REPOSITORY")
        text=text.replace("C:\\Users\\chenerxiao","USER_HOME")
        p.write_text(text,encoding="utf-8")
    flags={"V2_PHASE_B_AUTHORIZED":False,"FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED":False,
        "RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED":True,"HISTORICAL_RECOVERY_RATIFICATION":"NOT_GRANTED",
        "2025_RAW_ACCESS":0,"2025_PIXELS_READ":0}
    dump(OUT/"tests/attempt_summary.json",{"unique_passed":counts,"attempts":attempts,"initial_failures":1,
        "unresolved_failures":0,"SYNTHETIC_OPTIMIZER_STEPS":30,"FORMAL_OPTIMIZER_STEPS":0,"old_suites_reexecuted":False})
    dump(OUT/"tests/step_ledger_public.json",ledger)
    formal_imports=[p.relative_to(ROOT).as_posix() for p in (ROOT/"src/yuntapr/training").glob("*.py")
                    if "phase_b_v2_formal_runner_candidate" in p.read_text(encoding="utf-8")]
    assert not formal_imports
    dump(OUT/"tests/static_audit.json",{"candidate_code_sha":code_digest.hexdigest(),"matches_all_actual_cuda_runs":True,
        "public_files_sha_verified":402,"scaler_byte_check_deferred":source["deferred_observational_artifacts"],
        "protected_git_diff_empty":True,"formal_code_imports_candidate":formal_imports,"formal_entry":"UNCONDITIONALLY_BLOCKED",
        "real_data_connector":"ABSENT","fresh_algorithm":"REUSED_UNCHANGED_WITH_SCALER_VERIFIER_DEPENDENCY_DEFERRED",
        "actual_step_budget":{"total":30,"E0_per_model":9,"E1_per_model":3,"E2_per_model":3},**flags})

    write(OUT/"README.md","""# Phase-B v2 生产结构隔离 Runner 候选 v1

状态：SYNTHETIC_ENGINEERING_ONLY；RESEARCHER_DECISION_REQUIRED。已实现完整人工 epoch 事务，不具备真实数据读取和正式执行能力。

基线：435f303a1bdebb30a687f8e02dd8576d0d28cb55。新源码：src/yuntapr/experimental/phase_b_v2_formal_runner_candidate/，9 个模块。测试：tests/phase_b_v2_formal_runner_candidate/。本轮 79 CPU、8 CUDA 唯一检查通过；30 次合成更新；正式更新/运行均 0。

- EXISTING_FUNCTION_INVENTORY.md：既有功能与本轮新增结构。
- COMPLETION_AND_RESUME_CONTRACT.md：epoch → 完整验证 → LAST、恢复与额度。
- ENGINEERING_RESULTS.md：实际闭环、资源与未验证项。
- TEST_AND_FIX_RECORD.md / tests/：首轮失败、修复与真实日志。
- FUTURE_DATA_ADAPTER_SPEC.md：未来数据及批准接口，当前不可执行。
- EXECUTION_DECISION_GATE.md：压缩后的独立研究者决策。
- source_identity.json / manifest.json / final_status.json：来源、SHA 和真实状态。

本轮选择以简洁代码和 Markdown 交接；既有 LaTeX/PDF 审查材料继续保留，未复制旧报告。合成权重和完整机器日志只在本轮 .local 临时目录，不提交 GitHub。
""")
    write(OUT/"EXISTING_FUNCTION_INVENTORY.md","""# 复用清单与新增结构

|功能|已存在并复用|本轮新增|
|---|---|---|
|E0/E1/E2与损失|phase_b_v2_ablations/config、focal、pinball、total|无数学改写；adapter接收批次2/1及验证5|
|真实v2双模型、SP04、32tau|models/quantile_v2；spatial投影|无模型/投影改写|
|配对fresh|integration/initialization:fresh_paired_models|protocol临时替换来源校验依赖，仅避免读取被本轮禁止的scaler；原seed/参数拷贝算法原样执行|
|AdamW、clip=5、S0|runner_candidate/optimizer:new_adamw、clip_and_check、PrefixSchedule.prepare/commit|EpochSchedule只将合成恢复计数上限由2扩为6，不改LR数学|
|FP64共同评价|training/phase_a_validation_v2:LogDomainValidation|StreamingValidation加入完整场景覆盖，先求全局分子/分母再相除|
|原子文件事务|runner_candidate/checkpoint:SyntheticStore.save/read|EpochStore只替换临时根和I/O上下文；新增完整epoch LAST schema校验|
|RNG与状态摘要|runner_candidate/rng；phase_a_protocol:state_digest|无重写；绑定LAST恢复|
|旧短程Runner|仅支持内部batch2、2次更新|新EpochEngine支持Loader、batch2/2/1、完整验证、LAST、跨epoch恢复续跑|

新模块：protocol（固定协议与身份）、data（Scene/Registry/Loader/Coverage）、adapter（模型/损失接口）、metrics（流式共同评价）、engine（训练和验证事务）、checkpoint（epoch完成身份）、safety（独立30次额度与I/O守卫）、authorization（未来接口及当前无条件阻断）、__init__（人工用途声明）。

真实scaler的SHA只继承公开inventory引用，未打开其文件。402个公开文件本轮实际核验SHA；1个scaler只保留引用。真实云南mask未访问。Git只新增本轮文件，冻结源和历史证据未改。
""")
    write(OUT/"COMPLETION_AND_RESUME_CONTRACT.md","""# 完成边界与恢复契约

状态：READY → TRAINING → WAIT_VALIDATION → VALIDATING → 原子LAST提交 → READY。任何训练/验证/应用异常均使该实例poisoned，无自动重试、换seed或改参。

Loader固定训练batch=2、accumulation=1、drop_last=false；5个人工scene每epoch顺序为torch.Generator(seed+epoch_index)的确定性排列。Coverage拒绝重复、未知和缺失ID。训练与development角色的ID完全分开。验证配置batch=8，实际5场景为尾批5；StreamingValidation只用冻结FP64 gamma=2发生分子和未加权Pinball，global Core分母N_valid，Conditional Pinball分母N_rain，无雨时后者None。

每step：原S0全局update的LR先赋值 → BF16/FP64损失 → backward → 全参数梯度有限与clip=5 → 额度预留落盘 → AdamW.step → 额度完成落盘 → scheduler计数提交 → 参数与optimizer状态有限。无雨条件头梯度必须连接且为0；AdamW历史动量/衰减可能仍改变其参数，这不等于有雨损失。

本轮微型profile的科学协议身份仍B9/S0/V0，但实际人工终点为epoch2、每epoch3步；这不宣称运行了正式epoch。E1/E2只测试一个epoch；E0每模型连续两个epoch，再从epoch1 LAST恢复重放epoch2，总计9步。总预算30，新命名空间独立于上轮12次预算；台账不进入checkpoint、不允许恢复回滚。执行过程没有扩大额度。

LAST字段绑定：模型、AdamW所有moments、S0、Python/NumPy/CPU/CUDA RNG、seed/arm、协议/公开来源/当前源码/人工registry SHA、fresh祖先、训练/验证覆盖、逐步LR与clip、完成epoch及update、父LAST SHA。只有验证完整并原子提交后才推进completed_epoch。保存中断不产生可恢复receipt；SHA检查先于weights_only反序列化；全部身份和结构验证先于live状态应用。恢复只进入fresh引擎，并绑定具体synthetic LAST SHA；恢复实例保存到新的临时session，父SHA保留。应用异常停止，不保证部分应用自动回滚。

B9/V0终点采用冻结epoch9的逻辑判据，BEST不改变预算。纯逻辑测试验证10455个明确人工ID×9epoch的唯一覆盖、每epoch5228步、每run47052步，以及10501验证场景的1313 batch（末批5）；没有伪造真实样本合格目录。

正式执行祖先与研究者新的恢复事件，仅在FutureResumeBinding接口中定义，当前无验证器或执行能力。原历史BEST/LAST未打开、未修改、未追认。
""")
    rows=["# 实际工程结果与资源", "", "所有数字均 SYNTHETIC_ENGINEERING_ONLY，不是科研性能证据。", "",
          "|模型/臂|实际step|峰值allocated MiB|峰值reserved MiB|整项秒|", "|---|---|---|---|---|"]
    for c in cases:rows.append(f'|{c["model"]}/{c["arm"]}|{c["SYNTHETIC_OPTIMIZER_STEPS"]}|{c["peak_cuda_allocated_bytes"]/2**20:.2f}|{c["peak_cuda_reserved_bytes"]/2**20:.0f}|{c["elapsed_seconds"]:.3f}|')
    rows += ["", "六组全部完成5场景epoch与5场景独立验证。每次训练/验证N_valid=17150；只来自人工3430-cell布局。B0/E0、B1/E0的epoch2连续执行与绑定epoch1 LAST的续跑，训练记录、共同评价及model/optimizer/scheduler/RNG摘要完全相同。每模型跨三臂fresh摘要相同。", "",
       "两项额外CUDA故障测试向参考标签注入NaN：模型forward后、loss/optimizer前拒绝，更新0、LAST0、实例停用。CPU故障覆盖保存中断、锁异常、SHA与路径、缺失model/optimizer/RNG、seed/arm/code/protocol/epoch/update、覆盖缺失/重复/顺序、逐步LR/clip、分母、共同评价权重、AdamW状态与祖先错误。", "",
       "实测RTX5060 Laptop，完整501×501模型，冻结BF16/FP32/FP64路径。计时包含创建、训练、验证、保存恢复、部分首次库启动；峰值包含E0基准和恢复引擎。没有真实I/O或长期GPU热稳态，不能据此估算正式耗时。资源不足时应停止，不改batch/模型/精度；本轮无资源不足跳过项。", "",
       "当前未验证的正式功能：真实10501样本流式验证、真实数据读入/资格/时空配准、scaler和mask字节身份、9epoch实际运行、多个seed正式性能、独立审批事件验证服务、真实LAST授权祖先、长程资源/磁盘满/断电目录持久性。合成checkpoint仍只在专用临时目录；无正式模型权重发布。"]
    write(OUT/"ENGINEERING_RESULTS.md","\n".join(rows))
    write(OUT/"TEST_AND_FIX_RECORD.md","""# 测试与首轮失败记录

- cpu_attempt_001：45 passed、1 failed。流式累计的手工q首值0.05低于冻结log1p(0.1)支撑下界，原始guard正确拒绝。修复仅把夹具首值设为0.2；没有修改model、tau、epsilon、loss或容差。
- cpu_repair_attempt_001：仅重跑上述两个streaming测试，2 passed、45 deselected。
- checkpoint_attempt_001：32 passed；新完整epoch schema、故障注入及恢复计数。
- cuda_attempt_001：6 passed；30实际optimizer steps，一次固定预算campaign完成，未重跑成功组合。
- stop_attempt_001：2 passed；实际架构NaN参考异常停止，0 steps。

唯一最终检查79 CPU + 8 CUDA全部有通过记录；初次1失败保留，当前未解决0。tests/attempt_summary.json按testcase身份去重，重复修复不增加唯一数。新namespace实际source SHA与六个CUDA记录一致；没有测试后改变引擎源码再声称同版本通过。

完整机器日志留在.local/raw_test_logs；公开log/XML仅替换机器路径，不改变测试输出或失败原因。旧loss、隔离、批次、短程Runner测试未重跑。先前12次合成更新保持历史事实，本轮独立固定30次，正式更新仍0。
""")
    write(OUT/"FUTURE_DATA_ADAPTER_SPEC.md","""# 未来数据与批准接口规范（当前不可执行）

当前Scene/Registry/Loader只接收人工ID和内存张量，scope必须SYNTHETIC_ENGINEERING_ONLY，years为空；无路径、读原始观测、数据下载或真实loader能力。train/development ID集合必须分离；内容摘要固定后拒绝变动。人为给张量换标签不能证明其来源：本工程只使用内部人工生成器，正式接入须另做来源证明。

未来真实适配器必须在独立批准的正式集成版本中实现，并提供以下契约，不能通过翻转bool激活：

|边界|未来必须核验的证据|
|---|---|
|数据权限|只读指定2023 train与2024 development路径/产品版本/许可；2025拒绝；原始文件SHA与访问账本|
|样本身份|冻结10455/10501配对合格ID、M1/Q1关系、train/dev互斥、无重复/遗漏|
|因果性|B13单帧或六帧、oldest→latest，分析时刻前60/50/40/30/20/10min，obs_end≤analysis，IMERG冻结目标窗口与版本|
|归一化|唯一冻结2023 shared scaler字节SHA，不重拟合、不取2024统计、不替代缺测|
|地理|冻结云南mask与SP04身份、轴/方向/空间配准；不得用人工mask进入真实评价|
|张量|输入FP32；独立bool原生valid；参考[ B,1,100,100 ] FP32；有雨在该FP32域严格>0.1；32q FP64；完整资格失败即停|
|运行范围|18RunSpec封闭矩阵；首批seed2026六组单独许可；B9、S0原50轨迹、V0、batch2/验证8/不丢尾批|

authorization.py仅定义FutureApprovalBinding、FutureResumeBinding与FutureAuthorityVerifier Protocol。批准绑定protocol/code/data/qualification/scaler/mask/resource/run-scope SHA、独立事件和研究者身份。恢复另外绑定具体LAST SHA、原执行批准祖先、完成边界receipt SHA和新的独立恢复事件。没有issuer或verifier实现；start_formal/open_real_data始终抛PermissionError。字符串、JSON、Git提交和测试结果不能成为批准证明。

获得真实preflight许可前，不打开实际scaler、云南mask、2023/2024原始观测/参考或私有checkpoint。当前复用fresh初始化时仅临时注入公开代码验证器，推迟scaler字节核验；这不替代未来正式preflight，也没有改变随机种子或参数配对算法。防火墙是合作式Python进程防误用，不是恶意任意Python/系统权限的安全沙箱。
""")
    write(OUT/"EXECUTION_DECISION_GATE.md","""# 独立研究者执行决策门槛

状态全部RESEARCHER_DECISION_REQUIRED。D01/D02仅初步审查意见，没有被写成签署或批准。本轮工程委托不批准正式loss改变、科学验收、真实preflight或训练。

## 工程证据

已通过：79 CPU、8 CUDA；六组人工完整epoch（batch2/2/1）、独立验证与原子LAST；两模型E0连续epoch2对比LAST恢复续跑；输入/输出与FP32阈值/FP64共同评价；无雨批次梯度/step；NaN停止；场景一次覆盖、可重复shuffle；固定B9/V0纯逻辑与整数预算；checkpoint来源/完整性/覆盖/状态；正式入口阻断。30次合成更新，正式更新0。

尚未验证：真实样本与资格、scaler/mask字节、全量验证、实际9epoch、多seed真实表现、批准验证服务、正式恢复祖先、真实资源/I/O及长期故障耐久性。现有合成引擎终点2是工程夹具，不能声称完成正式B9。

## 必须由本人决定

|字段|候选依据与风险|当前状态|
|---|---|---|
|Phase-A科学接受范围、B1历史恢复独立处置|技术对账与BEST9身份不能替代科研接受或追认|未批准；历史恢复NOT_GRANTED|
|H-O/H-Q与E0/E1/E2、D1/Q1/N0/I3/B9/S0/V0|固定单因素矩阵；2024反复用于选择/诊断，只能开发探索|PROPOSED_FOR_RESEARCHER_APPROVAL|
|Brier最小有意义改善|绝对无量纲差便于统一解释；相对改善依赖基准；须基于应用价值及独立验证|数值NOT_YET_ESTABLISHED|
|q32覆盖误差标准|abs(coverage-0.984375)的百分点变化；覆盖提高可能只是分布变宽|数值NOT_YET_ESTABLISHED|
|副作用容忍|CPB用原log1p损失单位或相对变化；AUROC/AP绝对下降；同时看强雨层、全部tau、span/上尾|分别NOT_YET_ESTABLISHED|
|多重比较|Holm需有效p值和预定家族；配对max-stat需重抽样假设成立；或只探索效应/区间不作确认性判断|方法/家族/界限未选；功效未建立|
|正式代码集成与权限服务|审查engine、adapter、metrics、checkpoint、safety及来源；另建正式版本和独立批准验证器|未许可|
|真实preflight|明确只读2023 train、2024 development、冻结ID/scaler/mask/配准、文件SHA及访问日志；不训练、不读2025|需新的独立明确授权|
|资源与执行范围|GPU/软件版本/磁盘/时间窗口/停止预算；真实测量不能由合成秒数代替|未确认、未授权|

## 首批具体预算与恢复边界

seed2026×E0/E1/E2×B0/B1=6组，每组9epoch、10455场景/epoch、batch2不drop_last：5228更新/epoch、47052更新/组，共282312计划更新。开发验证10501场景、batch8、每epoch1313批，6组×9epoch为70902批。完整18组846936计划更新、212706计划验证批。以上均未执行；首批须单独覆盖这六组、数据、代码、资源及预算的真实许可。

其余seed以后按独立执行范围补齐，不根据首批表现改参数/主指标/阈值/样本。恢复需新的研究者独立决定，绑定具体LAST SHA和原始执行许可祖先；合成恢复成功不授权正式恢复。2025始终封存。B1历史恢复治理偏差独立保留，不能以本轮工程通过追认。

保持V2_PHASE_B_AUTHORIZED=false、FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED=false、RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED=true、HISTORICAL_RECOVERY_RATIFICATION=NOT_GRANTED、2025_RAW_ACCESS=0、2025_PIXELS_READ=0。本轮在此停止。
""")
    dump(OUT/"final_status.json",{"completed_at_utc":datetime.now(timezone.utc).isoformat(),"scope":"SYNTHETIC_ENGINEERING_ONLY",
        "engineering":"COMPLETE_AT_RESEARCHER_APPROVAL_BOUNDARY","protocol_status":"PROPOSED_FOR_RESEARCHER_APPROVAL",
        "checks_unique_pass":counts,"initial_test_failure":1,"unresolved_test_failures":0,
        "SYNTHETIC_OPTIMIZER_STEPS":30,"FORMAL_OPTIMIZER_STEPS":0,"formal_runs_executed":0,
        "complete_single_epochs":6,"two_models_exact_epoch2_resume_replay":True,"quota_refund_on_resume":False,
        "candidate_code_sha":code_digest.hexdigest(),"source_sha_verified_public_files":402,
        "real_scaler_byte_verification":"DEFERRED_NO_BYTE_ACCESS","real_yunnan_mask_bytes_read":0,
        "scientific_selected_epoch":None,"synthetic_endpoint_tested":2,
        "real_data_connector_enabled":False,"formal_approval_verifier_implemented":False,
        "published_weights":False,"protected_sources_modified":False,
        "remaining_formal_functions":"Independent approved adapter/preflight/approval-verifier and actual B9 execution/resource/recovery audits",
        "publication":"ACTUAL_PUSH_RECORDED_SEPARATELY_IN_RECEIPT",**flags})
    # Only public code, reports and scrubbed synthetic records; never any .local.
    files=[]
    for prefix in (candidate_dir,ROOT/"tests/phase_b_v2_formal_runner_candidate",Path(__file__).parent,OUT):
        for p in prefix.rglob("*"):
            if not p.is_file() or any(x in p.parts for x in (".local","__pycache__")):continue
            if p.name in ("manifest.json","publication_receipt.json"):continue
            assert p.suffix.lower() not in (".pt",".pth",".ckpt",".nc",".npy",".npz")
            if p.suffix==".py":ast.parse(p.read_text(encoding="utf-8"))
            files.append(p)
    files=sorted(set(files))
    dump(OUT/"manifest.json",{"baseline_commit":BASELINE,"scope":"SYNTHETIC_ENGINEERING_ONLY",
        "source_inventory_sha":sha(OUT/"source_identity.json"),"candidate_code_sha":code_digest.hexdigest(),
        "files":[{"path":p.relative_to(ROOT).as_posix(),"sha256":sha(p),"bytes":p.stat().st_size} for p in files],
        "self_hash_omitted":True,"publication_receipt_appended_after_verified_push":True})
    files.append(OUT/"manifest.json")
    write(OUT/".local/publication_allowlist.paths","\n".join(p.relative_to(ROOT).as_posix() for p in files))
    print(json.dumps({"public_files":len(files),"unique_passed":counts,"synthetic_steps":30,"candidate_code_sha":code_digest.hexdigest()}))


if __name__=="__main__":main()

