"""Build new human-review documents from the independently checked aggregates.

Existing documents and figures are referenced, never overwritten or regenerated.
LaTeX is self-contained and editable. Run only after the audit passes.
"""
from __future__ import annotations
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
from datetime import datetime, timezone

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "docs/phase_a_evidence_hardening"
OLD = REPO / "docs/v2_scientific_acceptance/runs/run_20261009T112710_013267Z/delivery_v2"
REF = "../v2_scientific_acceptance/runs/run_20261009T112710_013267Z/delivery_v2/"
BASELINE = "92687641e59c256a9443b8bfb420b6c947fdcb3a"


def write(name: str, value: str) -> None:
    p = OUT / name
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(value.rstrip() + "\n")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(name: str) -> list[dict[str, str]]:
    with (OLD/name).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def table(headers: list[str], body: list[list[str]]) -> str:
    return "|" + "|".join(headers) + "|\n|" + "|".join(["---"] * len(headers)) + "|\n" + "\n".join("|" + "|".join(row) + "|" for row in body)


def tex_escape(text: str) -> str:
    # Long identifiers may wrap at separators; Greek and relations use math
    # glyphs instead of relying on Unicode support in the Roman text font.
    escaped = "".join({"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_\allowbreak{}", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}", "θ": r"\(\theta\)", "≤": r"\(\le\)", "Δ": r"\(\Delta\)"}.get(c, c) for c in text)
    return re.sub(r"[0-9a-f]{40,64}", lambda m: r"\allowbreak{}".join(m.group()[i:i+8] for i in range(0,len(m.group()),8)), escaped)


def md_tex(markdown: str) -> str:
    """Small controlled converter for these review files; no external assets."""
    result = []
    lines = markdown.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("|"):
            body = []
            while i < len(lines) and lines[i].startswith("|"):
                body.append(lines[i].strip("|").split("|")); i += 1
            body = [r for r in body if not all(re.fullmatch(r":?-+:?", c.strip()) for c in r)]
            n = len(body[0])
            column = r"p{\dimexpr(\linewidth-" + str(2*(n-1)) + r"\tabcolsep)/" + str(n) + r"\relax}"
            result.append(r"\begin{center}\scriptsize\begin{longtable}{@{}" + column*n + r"@{}}\toprule")
            for j, row in enumerate(body):
                result.append(" & ".join(tex_escape(c.strip()) for c in row) + r"\\")
                if j == 0: result.append(r"\midrule\endhead")
            result.append(r"\bottomrule\end{longtable}\end{center}\normalsize")
            continue
        line = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line)
        line = line.replace("`", "").replace("**", "")
        if line.startswith("# "): result.append(r"\section*{" + tex_escape(line[2:]) + "}")
        elif line.startswith("## "): result.append(r"\subsection*{" + tex_escape(line[3:]) + "}")
        elif line.startswith("- "): result.append(r"\noindent\textbullet\quad " + tex_escape(line[2:]) + r"\par")
        else: result.append(tex_escape(line) + (r"\par" if line else ""))
        i += 1
    return "\n".join(result)


def main() -> None:
    audit = read_json(OUT/"tests/audit_attempt_002/audit_results.json")
    if audit["status"] != "PASS": raise RuntimeError("Independent audit must pass before authoring")
    metrics = rows("PAIRED_STRATIFIED_ANALYSIS.csv")
    cmp = rows("PAIRED_STRATIFIED_COMPARISONS.csv")
    rel = rows("reliability_fixed_bins.csv")
    cov = rows("conditional_quantile_calibration.csv")
    all_cmp = [r for r in cmp if r["group"] == "ALL"]
    metric_table = table(["指标", "B0", "B1", "B1−B0", "95% 配对探索区间"], [[r["metric"], f'{float(r["B0"]):.9f}', f'{float(r["B1"]):.9f}', f'{float(r["B1_minus_B0"]):.9f}', f'[{float(r["delta_lower"]):.9f}, {float(r["delta_upper"]):.9f}]'] for r in all_cmp])
    rel_table = table(["模型/概率箱", "暴露数", "平均概率", "参考雨频率", "有效重采样次数"], [[r["model"].replace("_MATCHED_V2", "").replace("_V2", "")+" / "+r["lower"]+"–"+r["upper"], r["count"], f'{float(r["mean_probability"]):.6f}' if r["mean_probability"] else "不可估计", f'{float(r["observed_frequency"]):.6f}' if r["observed_frequency"] else "不可估计", r["bootstrap_valid_replicates"]] for r in rel])
    rain_table = table(["真实雨强 mm/h", "雨暴露数", "B0 条件 Pinball", "B1 条件 Pinball"], [[g, next(r["N_rain"] for r in metrics if r["group"]==g), *[f'{float(next(r["conditional_pinball"] for r in metrics if r["group"]==g and r["model"]==m)):.9f}' for m in ("B0_MATCHED_V2","B1_V2")]] for g in ("(5,10]", "(10,20]", "(20,30]", "(30,50]", "(50,inf)" )])
    limits = "本轮仅诊断与工程准备；RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED=true；V2_PHASE_B_AUTHORIZED=false；2025_RAW_ACCESS=0；2025_PIXELS_READ=0。"
    docs = {}
    docs["SCIENTIFIC_EVIDENCE_AUDIT.md"] = f"""# Phase-A 科学证据一致性审计

独立核验结果为 25 项通过、0 项失败。机器结果：[audit_results.json](tests/audit_attempt_002/audit_results.json)。128 个历史 acceptance manifest 条目的字节数和 SHA256 一致；历史报告、源代码、图表和失败记录未修改。该结论是证据一致性核验，不构成科学验收。

## 身份和适用范围

基线及本次读取时 GitHub main：{BASELINE}。主仓库为 YunTAPR-Net-push-chunks；另有旧 upload 和 v2 execution checkout，不同步、不清理。主仓库原已跟踪文件无改动；大量旧未跟踪文件仍保留。最初 cwd 是项目容器目录而非 Git 根目录。使用 Get-Process 未见训练 Python；CIM 详细命令行查询因系统权限失败，不宣称查清全部进程命令行。未停止任何进程。

Phase-A 配对训练与科学审查材料已完成，本轮目录在检查时尚不存在。历史 final_status 的 publication pending 是提交前快照，后续 publication_verification 收据确认 bb7c25a8 已发布；不能将旧快照字段误判为推理未完成，更不能改写快照。

2023 训练场景 10,455；2024 共同验证场景 10,501。两模型 scene_ids 全序列逐项相等且唯一，全部为 2024 年 3–10 月。云南有效暴露 N=36,018,430，参考有雨暴露 R=4,496,600；标签在源 float32 上取 IMERG>0.1 mm/h。两个 BEST 均为 Epoch 9/update 47,052，未重新选择。B0 最新卫星槽为分析时刻 T−10 分钟；B1 为 T−60 至 T−10 的六个因果槽，不能写成含 T 时刻未来观测。

## 指标及分母

S_occ 为 alpha=0.5、gamma=2 的 focal BCE 分子；S_qr 为真实有雨且有效云南像元的 32 tau 平均 Pinball 之和。Core=(S_occ+S_qr)/N。训练量化损失分量和科学 global_core_L_qr 使用 S_qr/N；科学 Conditional Pinball 使用 S_qr/R，单位为 log1p(mm/h)。二者不可直接互换，也不能把 minibatch 平均损失平均当作全局量。

Brier=有效云南像元上 (p−标签)^2 的平均，包含真实干像元。AUROC 使用精确 BF16 概率同分组排序、并列半分；AP 使用同分组末端非插值 precision 增量加权。固定概率分箱只用于可靠性诊断，不用于近似 AUROC/AP。单类别分层 AUROC 保持缺失，真实雨分层 AP=1 是条件化后的平凡值，不能作为发生识别证据。POD/FAR/CSI 因概率决策阈值未冻结保持不可估计。

{metric_table}

## 重建与对照

全部 22 分层点指标由 daily 分子/分母及精确 score counts 重建；月、季节、民用昼夜、真实雨强四种分区均守恒。对全部 110 个比较逐项核对 CSV/JSON 点值、绝对/相对差异、区间和有效重采样次数。32 tau 覆盖率、每 tau Pinball 及其探索区间逐项重建。可靠性所有分箱的计数、平均概率、雨频率及区间重建。旧 Markdown、LaTeX、PDF、SVG/PNG 与 manifest 字节身份一致；其中科学定义人工对照实际 loss/head 源码。文件哈希证明身份，不能单独证明文稿中每一句科学解释正确。

35 个非重叠七日 UTC 块覆盖 2024-03-01 至 2024-10-31，seed=2026，2,000 次，每次抽 35 块，B0/B1 共用次数矩阵。完整矩阵零差异重建；66 个 Core/Brier/Conditional Pinball 差异区间独立按池化分子分母重建。排名指标仅对固定 5 个重采样索引执行精确池化 smoke；全量排名 CI 复用已发表结果和绑定，未重复全部分析。训练相关性、跨周天气过程、季节非平稳、单一年份、单一种子和 BEST 选择偏差仍在。

## 未执行与异常

未读取卫星或 IMERG 原始像元、未打开模型 checkpoint、未新增模型推理。外部冻结静态 mask 仅引用已发表 SHA，未重新读文件；10 项其余冻结协议输入 SHA 已核对。本轮未运行旧训练全套或含 optimizer/backward 的 fixture。初次审计 24 pass/1 fail 保留：将文稿四舍五入的 20.24 错当源 float32 精确值；第二次改为严格对照 float32(20.24)，没有放宽其他指标容差。

{limits}
"""
    docs["PROBABILITY_AND_TAIL_DIAGNOSTICS.md"] = f"""# 概率校准与条件上尾诊断

来源：2024 共同验证集、冻结 Epoch 9 BEST 的已发表可靠性和分位数 CSV。本文没有拟合或应用温度、Isotonic、Platt 校准，也未改阈值或归一化。

## 发生概率

{rel_table}

分箱为 [k/10,(k+1)/10)，最后一箱含 1。两模型 0–0.5 箱均为平均概率高于参考雨频率，0.5–0.9 非空箱方向相反。空箱不填零预测/雨频率；B0 0.8–0.9 箱只有 12 个暴露且 1,988 个有效重采样，B1 该箱 154 个暴露。置信区间退化或接近端点不代表尾部已可靠校准；这些暴露高度相关，缺少事件级有效样本数。

AUROC/AP 描述排序区分；Brier 是整体概率误差；可靠性比较条件预测概率与参考频率。Brier 改善不能代替校准通过。本轮不新增分箱选择或数据驱动合箱，不把分箱平方误差当作完整 Brier 分解。所有区间来自配对周块探索分析，未校正多重比较和 BEST 选择。

## 条件分位数

tau_i=(i−0.5)/32，qlog 单位 log1p(mm/h)，覆盖集合仅为参考真实有雨且有效云南像元；coverage_i=mean[log1p(y)≤qlog_i]。全部 32 个点和区间已核对，原 CSV 继续作为逐 tau 权威表，不按结果选择分位数。

B0 q32 覆盖 0.95744184495，目标 0.984375，偏差 −2.693315505 个百分点；B1 0.95076991505，偏差 −3.360508495 个百分点。32 tau 平均绝对覆盖误差 B0=0.0141067991、B1=0.0165553088。总体条件 Pinball 配对差异区间跨零；下列强雨分层 B1 点值均更高。

{rain_table}

最强雨层仅 69 个相关场景像元暴露，不能当成 69 次独立极端事件。分层在真实雨强条件下进行，描述监督集合上的损失差异，不是从预测中筛出表现最好的样本。

## 上尾、发生概率及数值边界

B1 云南最大 q32=351.08272 mm/h，对应参考 y=0、p_rain=0.56640625；其 q32>100 mm/h 集合为 58 个暴露、44 格点、28 场景，30 暴露参考有雨，参考最大为源 float32 20.2399997711 mm/h（文稿约 20.24），p_rain 范围 0.1328125–0.84765625。这不是确定性暴雨预测或独立事件数量，且不代表完整概率校准集合。

现有 v2 head 为 32 allocation raw 通道和 1 span raw 通道，经正权重归一化累计生成 32 条件 qlog；不是直接输出 32 raw 通道。严格单调和支撑下界有实际 guard。BEST 聚合 crossing/support/nonfinite 均为零；tiny CPU fixture 对实际 API 验证正常单调、非有限 raw 拒绝、精度丢失拒绝、FP32 与 FP64 转换风险区别及实际 FP64 overflow 停止。浮点边界约 log(float64_max)=709.782712893384；边界比较只是筛查，最终转换还必须检查有限性。数值有限不等于物理可信。

待检验假设 H1：真实干像元缺少直接条件 quantile 监督可能关联巨大尾部。H2：最高条件 quantile 的尾部配置与发生 head 的联合一致性不足。H3：IMERG 参考误差、过程时空错位、季节及地形差异可能参与异常。当前证据未建立上述因果关系；不自动 clamp、换 loss 或结构。独立雨量站/雷达、审批后的事件和地形目录及独立年份才能进一步检验。

[原可靠性与全部分位数报告]({REF}PROBABILITY_CALIBRATION_REPORT.md)；[原上尾报告]({REF}UPPER_TAIL_PHYSICAL_REVIEW.md)。{limits}
"""
    docs["EVENT_CATALOGUE_CANDIDATES.md"] = """# 独立降水事件目录候选方法

状态：RESEARCHER_DECISION_REQUIRED。只完成数学规则和合成测试，未读取真实降水场、未建立真实目录。候选连通对象的数量不自动等于统计独立事件数。阈值、连接半径、时距、最低面积和持续时间均需先冻结，再读取模型表现。

## 数学对象与单位

令 y(t,r,c) 为参考降水率 mm/h，v 为独立有效性掩膜，阈值 θ>0；active=v 且 y>θ。θ 与 occurrence 的 0.1 标签阈值目的不同，也不同于 q32 描述阈值。IMERG 半小时产品的 mm/h 是该时段平均率，不能等同瞬时峰值；积累量用 y×Δt_hours，不把 mm/h 阈值冒充日累计气象等级。NASA 产品文档说明半小时和 0.1° 网格性质，正式协议应绑定实际产品版本和误差：[NASA IMERG V07 数据集](https://daac.gsfc.nasa.gov/datasets/GPM_3IMERGHH_07/summary)。

同一时刻用四邻域或八邻域，必须明确选择。相邻观测时槽只有在时间差恰好等于声明 cadence 时才可连边；跨槽连边条件为 Chebyshev 网格距离≤声明半径。图的连通分量为候选事件族。输入只有真值和有效性，接口无 B0/B1 预测或误差字段。合成 fixture θ=10 只是测试数字，不是科学极端定义。

## 合并、分割与缺测

同一图连通分量内的分裂和再合并保留一个事件族，并记录分支拓扑需求；两个相隔事件不因发生在同一日期而合并。默认接口无缺测时间桥接能力，缺测时段分割且标记 censored。像元缺测不是无雨；边界、缺测邻居、观测序列首尾均标记可能截断。合并有时会通过窄桥把多个天气过程组成长事件族，需先注册最大持续时间、物理移动半径及过长族人工审查规则，不能按模型得分再拆分。

原 frozen common intersection 是筛选后的场景集合，可能缺少连续时槽；仅用该集合会分割真实过程。未来需批准参考完整时间覆盖及缺测元数据权限，不为了连通补读 2025。当前聚合 daily NPZ 不能恢复时空对象，无法生成真实事件数量。

## 研究者选择槽位

- 强度定义：固定物理 θ、预先规定积累窗，或仅由 2023 参考气候分布定义的百分位；不得以 B0/B1 误差优劣选择。
- 空间连接：4/8 邻域、允许移动距离需从目标 cell footprint 与过程速度依据转换，云南外边界截断需单独标识。
- 时间连接：cadence、是否允许缺测桥接、连续干间隔及事件分离时间；当前实现只允许相邻完整槽。
- 纳入资格：最小完整面积、观测持续时间、缺测比例、边界对象处理。代码当前只输出未筛选组件，不擅自过滤。
- 事件级指标：参考峰值、面积、时间和体积（须面积权重），B0/B1 使用完全相同对象与有效性；事件等权与暴露等权结果分别说明。
- 独立性：气旋/雨带可跨连通分量或七日块；候选分量不证明独立，应按天气过程聚类或保留时间区块不确定性，预注册敏感性比较，不挑最佳定义。

## 已实现与测试范围

src/yuntapr/diagnostics/candidates.py 的 EventRule/event_components 无 I/O；返回暴露数、唯一格点、时槽、参考峰值、截断状态和未审批标记。验证严格阈值、持久过程、移动半径、4/8 邻域、缺时槽、缺像元、分裂合并、确定性和非法输入。尚未实现真实对象追踪、面积积分、天气过程命名或完整生产目录；这些属于审批后的阶段，不以测试通过代替独立性证明。
"""
    docs["TERRAIN_STRATIFICATION_CANDIDATES.md"] = """# 云南地形分层候选方案

状态：RESEARCHER_DECISION_REQUIRED。本轮无 DEM 下载、无真实地形分区、无 frozen mask 替换或真实分层模型评价。分区必须在模型表现评价前凭地理物理依据与无模型的地形资料确定。

## 数据与配准方案

候选 DEM 需登记产品版本、获取日期、SHA256、水平 CRS、垂直基准、填补来源、nodata、分辨率及覆盖范围。SRTM 全球 1 arc-second 产品是候选来源之一，不能把角秒直接视作固定米数，也不能忽略 void filling 来源：[USGS SRTM 用户指南](https://lpdaac.usgs.gov/documents/179/SRTM_User_Guide_V3.pdf)。实际选择与采购/下载本轮均未执行。

以现有 SP04/IMERG cell-center 和 cell bounds 为目标；先在合适米制坐标下求地形导数，再按真实目标 footprint 做面积加权 mean/median 与地形分布汇总。不同区域的重投影畸变与纬度 cell 面积要登记。坡度/坡向先在高分辨率 DEM 求出，再聚合，不把平滑后的 0.1° 高程坡度等同真实坡度。坡向用 sin/cos 圆周汇总，不平均 359° 与 1° 得 180°。本轮只实现 synthetic 网格中心身份拒绝检查，无 GIS 重采样。

## 变量与候选分层

高程 z（m）；坡度 arctan(sqrt(g_east²+g_north²))（degree）；坡向为最陡下坡方向，自北顺时针，平地定义缺失；起伏度为事先声明物理邻域内 max(z)−min(z)（m）。分层界限可以使用领域物理边界或只据 DEM 的预声明分位数，研究者需决定边界和尺度；不得由模型误差反推有利边界。演示分层 1000/2000 m 只用于边界合成测试，不是已批准云南分区。

迎风/背风必须有明确时刻、气压层或高度的风场；静态坡向不能独立给出迎风判断。候选代理 w_orog=u_east*g_east+v_north*g_north（m/s），正值表示流向上坡的几何分量，负值相反；不等于实际垂直速度。风资料的可用时间须因果，不得把事后再分析当作业务实时输入；气压层被山体遮挡、弱风和缺测保持不可估计。真实风资料与审批均未提供。

## 掩膜与不确定性

分层掩膜只能与冻结云南 mask 相交，并保留独立 DEM 完整性 mask。缺失 DEM 像元单独报告，不自动补平、不排除后重定义主评价集合。应记录每层格点、场景、有效暴露、有雨暴露、日期块和未来候选事件数；暴露数不是独立样本量。层内 B0/B1 必须共享同一样本条件，保留时间区块不确定性和样本稀少层。邻接地形层空间相关，应避免独立像元区间与过多层结果挑选。

## 合成实现范围

terrain_fields 接受北向上、行向南、列向东的米制规则网格，仅使用完整中央差分 stencil；边界和缺 stencil 输出 NaN。relief 使用声明方窗半径，完整窗口才给值。fixed_strata 使用左闭右开预声明边界，invalid=-1；require_same_grid 拒绝半格错位、翻转、形状不合和重复坐标，不静默修复。解析平面测试明确坡向约 206.565°、坡度和起伏度；平地/缺测/非法尺度/风向反转均验证。

研究者仍需选择 DEM、投影、垂直基准、聚合方式、窗口公里数、高程坡度起伏度分箱、圆周坡向规则、风来源及缺测政策。没有真实 DEM 和风场时，无法报告真实地形层样本数或误差。
"""
    docs["RECOVERY_GOVERNANCE_GAP_REVIEW.md"] = f"""# 历史 B1 恢复治理偏差复核

原 [治理偏差报告]({REF}RECOVERY_GOVERNANCE_DEVIATION.md)、9 个 source 文件和逻辑 chronology SHA 已核验；本轮没有新独立研究者 LAST-bound 恢复审批记录，状态仍为 NOT_EVIDENCED_IN_REGISTERED_RESUME_RECORDS。工程签名、JSON、远端发布或预检均不等同人类审批，本轮也不补签或追认。

冻结恢复规范要求“必须另有绑定具体 LAST SHA 和原授权祖先的研究者恢复批准。”实际恢复绑定使用原 Phase-A 授权和持续目标。绑定提交 f269272c821b49c5226ddf6d75eeb7108522cd34，LAST SHA=40f7f1204aba52815e1c8c2f3d2a5ce5d73da6b7b0297e1d79dc843cb3390649。上述身份有证据，缺失独立批准仍须研究者处置。

BEST Epoch 9/update 47,052 早于 LAST Epoch 14/update 73,192 和恢复 Epoch 15。BEST 参数未由受影响恢复段得到；后续完整训练历史、早停和无更好 checkpoint 的确认仍经历该恢复段。两个丢弃更新前缀 3,095/382 重放零差异；保留 88,876，全部尝试 92,353。技术可追溯性不能消除治理问题，也不能自行判定科研结果必然有效或无效。

研究者应独立决定偏差记录的处置、后续补救要求、BEST 科学审查是否可继续，以及正式验收。新增 synthetic 恢复检查器要求独立 LAST 批准、完成 epoch marker、原授权 SHA 和恢复状态核验，并永远返回 can_launch_formal_training=false；它不修补历史授权，也未接入正式 runner。

{limits}
"""
    docs["PHASE_B_ENTRY_READINESS_CHECKLIST.md"] = f"""# Phase-B 工程入口准备清单

结果：允许范围内的只读核验和合成准备完成；正式 v2 Phase-B 入口尚不具备启动资格。v1 训练路径存在不能代表 v2 已就绪。

|项目|本轮证据|状态/下一步|
|---|---|---|
|v2 模型入口|B0MatchedV2/B1V2，1/6 帧、32+1 raw head|静态源码核对；全模型 synthetic 推理未重复|
|checkpoint|两个 Epoch 9 BEST SHA、状态未改收据与历史指标身份|元数据核对；私有 checkpoint 字节未重读|
|冻结输入|协议内 10 个仓库输入 SHA|通过；外部静态 mask 未重新打开|
|数据年限|本轮只访问发表的 2024 聚合统计|2025 raw/pixels=0|
|随机性|seed=2026、2,000×35 配对重采样矩阵零差异|通过；不估计训练种子变异|
|数值保护|实际 v2 CPU tiny fixtures 无梯度更新|单调、有限性、支撑、物理溢出拒绝通过|
|恢复安全|checkpoint_v2 的身份先校验、完成 epoch marker、原授权链|静态核对；历史独立恢复审批缺口保留|
|批准检查|prepare-only assess_entry，严格 bool/身份/年份/恢复字段|合成通过；永远不能启动训练|
|正式 v2 Phase-B 协议及 runner|未发现已授权入口|RESEARCHER_DECISION_REQUIRED|

现有 src/yuntapr/training/phase_b_preparation.py 是旧 v1 单时相 FinalFit 规则：SCENES=23,447、2023=11,720、2024=11,727、EPOCHS=11；不能默认为 v2 的匹配训练集合或训练长度。v2 冻结 Phase-A 集合为 10,455/10,501，但不据此擅自定义 Phase-B 合并集合。数据资格、重新拟合 normalization、fresh/resume 初始化、训练预算、checkpoint 选择和评价策略均需研究者独立决定。

新 src/yuntapr/diagnostics/readiness.py 是待审核的检查表模拟器，不是 authorization 颁发器。即使 synthetic 字段全部满足仍不启动；JSON 中 true 不证明实际人类身份。未来正式入口需从独立研究者批准的不可变文档验证范围、SHA、代码版本、数据年限和 provenance，随后才可准备真实 preflight。本轮没有修改任何正式训练入口、冻结配置或权重。

停止条件：缺独立批准、SHA 不符、非完成 epoch、原授权链变化、2025 请求、格网不合、非有限值、支持/严格序丢失、源文件锁或清理失败。实际正式 run 的停止/恢复策略仍需由审批协议确定；不得自动跳过 batch、降级数据或修改 loss。

未执行：正式配置实例化、真实数据 preflight、checkpoint 反序列化、正式恢复、训练更新。后续测试若涉及合成 optimizer step，也必须与正式更新分别计数且取得该范围授权。本轮 48 个合成测试无 backward/optimizer step，历史 770 项不是本轮执行数。

{limits}
"""
    docs["RESEARCHER_DECISION_REQUIRED.md"] = """# 研究者必须独立决定的事项

以下全部仍为 RESEARCHER_DECISION_REQUIRED；本轮工程完成不自动选择任何选项。

|事项|可审查材料|依赖|
|---|---|---|
|Phase-A 正式科学验收|原验收包与本轮一致性/校准审计|研究者独立结论|
|B1 Epoch 14 LAST 恢复偏差处置|原治理源链和本轮复核|独立处置记录，不能以工程 pass 追认|
|Phase-B 目的、模型及范围|入口准备清单、v1/v2 不匹配项|新正式协议与执行授权|
|训练集合、normalization、初始化与训练预算|冻结 v2 输入及现有 v1 规则|科学设计；本轮不改配置|
|独立事件定义|事件候选图规则、合成测试|阈值/空间/时间/缺测/独立性预注册|
|地形分层|地形候选方案、配准合成测试|DEM/风来源、投影、尺度、分箱和掩膜批准|
|发生校准研究或上尾干预|全部 32 覆盖、可靠性和上尾诊断|新校准/结构/loss 实验审批|
|独立物理验证|58 暴露联合参考诊断|站点/雷达访问权限及资料|
|最终 2025 测试|目前封存|单独解封审批，不可借 Phase-B 自动获得|

可以安全接续的第一步是研究者审阅文档并登记明确批准/拒绝范围和证据身份。审批之后需再次核对远端 HEAD、dirty workspace、活动进程、冻结 SHA 与新授权 scope，按新授权实现 v2 专用 runner/preflight。事件及地形真实评价需要新的参考连续场、DEM/风或独立观测；正式训练需要额外计算资源。本轮未申请或消耗正式训练资源。批准前在此停止。
"""
    for name, value in docs.items(): write(name, value)
    write("README.md", f"""# Phase-A Scientific Evidence Hardening & Phase-B Engineering Readiness

已完成本轮授权的聚合审计、诊断、候选数学实现、合成测试和下一阶段准备；正式科学审批待决。未新建项目或重复训练/推理。

- [科学证据审计](SCIENTIFIC_EVIDENCE_AUDIT.md)：128 个历史文件 SHA、22 分层、32 tau 和探索区间。
- [概率及上尾诊断](PROBABILITY_AND_TAIL_DIAGNOSTICS.md)：稀疏空箱、条件覆盖不足、强雨层损失。
- [事件候选](EVENT_CATALOGUE_CANDIDATES.md) / [地形候选](TERRAIN_STRATIFICATION_CANDIDATES.md)：仅数学/合成，不是正式目录。
- [历史恢复治理复核](RECOVERY_GOVERNANCE_GAP_REVIEW.md)。
- [Phase-B 入口准备](PHASE_B_ENTRY_READINESS_CHECKLIST.md) / [研究者待决](RESEARCHER_DECISION_REQUIRED.md)。
- [可编辑 LaTeX](PHASE_A_HARDENING_REVIEW.tex) / [PDF](PHASE_A_HARDENING_REVIEW.pdf)。
- [机器审计](tests/audit_attempt_002/audit_results.json)、[合成测试](tests/synthetic_attempt_002.xml)、[测试说明](tests/README.md)。
- [既有图表及身份](figures/README.md)、[manifest](manifest.json)、[状态](final_status.json)。

实现沿现有 src/yuntapr 布局新增 diagnostics/candidates.py、diagnostics/readiness.py；审计 scripts/phase_a_evidence_hardening/audit.py。代码无正式入口，所有候选参数显式传入。原论文/源代码/权重/数据/旧失败证据均保留。

复现只读审计：python scripts/phase_a_evidence_hardening/audit.py --output 一个尚不存在的目录。合成测试：设置 PYTHONPATH=src 后 python -m pytest -q tests/phase_a_evidence_hardening -p no:cacheprovider。完整历史排名 bootstrap 不重跑，原报告审查限制见审计文档。

实际当前通过记录是第二次审计 25 pass/0 fail，第二次 synthetic 48 pass/0 fail；首次失败分别保留，不混算为最终失败。冻结 mask、checkpoint 原始字节、原始数据、站点雷达、真实事件和地形目录均未访问/执行。{limits}
""")
    write("tests/README.md", """# 实际执行记录

audit_attempt_001：24 pass/1 fail，完整异常/traceback 保存于 audit_results.json；原报告约 20.24 与源 float32 20.2399997711 精度误比较。修正为严格比较 float32 来源值；没有修改原统计。

audit_attempt_002：25 pass/0 fail。synthetic_attempt_001.xml：37 pass/1 fail，解析平面起伏度 100.00000000000001 与 100 的 exact assertion 不合；修为 abs=1e-12 的解析数值断言。synthetic_attempt_002.xml：48 pass/0 fail，增加实际 v2 tiny CPU 数值接口与配准拒绝测试。无 backward/optimizer 更新。

早期状态发现还出现：cwd 不是仓库（随后定位主仓库）；rg 遇旧 temp 目录权限错误；CIM 进程命令行权限拒绝（使用只读 Get-Process，未杀进程）；一次 Python 默认 GBK 解码历史 UTF-8 JSON 失败（改显式 UTF-8）；Git 网络代理沙箱连接失败，沙箱外经批准的 ls-remote 确认 main。未把失败当成通过或删除相关旧文件。发现阶段工具输出保留于本对话；核心实验和合成失败的完整日志在本目录。

不执行旧训练 full suite、optimizer/backward fixture、真实 pixel 测试、private checkpoint reopen、正式 v2 Phase-B 预检、真实事件/地形评价。PDF 和交付验证另有记录，不能把历史 28/770 checks 加入本轮通过数。
""")
    figures = sorted((OLD/"figures").glob("*.svg")) + sorted((OLD/"figures").glob("*.png"))
    refs = {"status": "REUSED_PUBLISHED_FIGURES_NO_NEW_GENERATION", "sources": [{"repository_path": str(p.relative_to(REPO)).replace("\\", "/"), "sha256": sha(p), "bytes": p.stat().st_size} for p in figures]}
    write("figures/figure_references.json", json.dumps(refs, ensure_ascii=False, indent=2))
    write("figures/README.md", f"""# 已发表科学图表复用

本轮未生成或编辑图像。复用旧图并核验字节身份，避免为新目录复制同一图表。四种图各有 SVG/PNG：发生可靠性、32 tau 条件覆盖、配对分层差异、云南 q32 与参考雨强。来源完整 SHA/bytes 见 figure_references.json；含实际暴露诊断 CSV 的 source manifest 亦已核对。

[原图表目录]({REF}figures/)；[原 provenance]({REF}figure_provenance.json)。本轮不继承上一轮本地绘图的范围授权。若后续需要新图，应按当前用户要求通过网页 GPT；此交付已有图足以支撑审查，无新制图依赖。
""")
    header = r"""\documentclass[UTF8,a4paper,10pt,fontset=fandol]{ctexart}
\usepackage[margin=20mm]{geometry}
\usepackage{booktabs,longtable,array,hyperref,amsmath}
\hypersetup{colorlinks=true,linkcolor=blue,urlcolor=blue}
\setlength{\parindent}{0pt}\setlength{\parskip}{5pt}
\renewcommand{\arraystretch}{1.12}\sloppy
\begin{document}
\begin{center}{\LARGE YunTAPR-Net}\par{\Large Phase-A 科学证据补强与 Phase-B 工程准备}\par 2026-10-10\end{center}
\textbf{审查结论：授权工程范围完成；科学验收、恢复追认、Phase-B 训练与 2025 解封均未批准。}
\par 基线 HEAD：\texttt{92687641e59c256a9443b8bfb420b6c947fdcb3a}。
\par 独立审计 25 项通过；合成测试 48 项通过。完整旧证据保留。
\section*{指标定义}
令 $V$ 为有效云南暴露，$R=\{j\in V:y_j>\mathrm{float32}(0.1)\}$，$N=|V|$。
\[
\rho_\tau(e)=\max(\tau e,(\tau-1)e),\quad
S_{qr}=\sum_{j\in R}\frac1{32}\sum_{i=1}^{32}\rho_{\tau_i}(\log(1+y_j)-q_{ji}).
\]
\[
L_{core}=\frac{S_{occ}+S_{qr}}N,\qquad
L_{qr,train}=\frac{S_{qr}}N,\qquad
L_{qr,conditional}=\frac{S_{qr}}{|R|}.
\]
\par 分母区别保持冻结；Pinball 单位是 log1p(mm/h)。tau=(i-0.5)/32。
"""
    tex = header + "\n\n".join("\\clearpage\n" + md_tex(value) for value in docs.values())
    tex += r"""
\clearpage\section*{公开方法参考与源码路径}
NASA IMERG V07 产品与算法：\url{https://gpm.nasa.gov/resources/documents}。
本轮只用于了解参考资料性质，不替换冻结产品。
\par USGS SRTM 用户指南：\url{https://lpdaac.usgs.gov/documents/179/SRTM_User_Guide_V3.pdf}。
\par 时间区块背景：K\"unsch (1989)，\url{https://doi.org/10.1214/aos/1176347265}。
本项目为固定非重叠周块，非重叠对象也不证明事件独立。
\par 概率评分背景：Brier (1950)，Verification of Forecasts Expressed in Terms of Probability；定义以当前源代码和冻结协议为准。
\par 代码入口：\texttt{src/yuntapr/diagnostics/}；新测试：\texttt{tests/phase\_a\_evidence\_hardening/}；只读审计：\texttt{scripts/phase\_a\_evidence\_hardening/audit.py}。
\par 逐 tau、完整可靠性区间和已发表 SVG/PNG 通过主目录 README 链接访问；本报告不生成新图。
\end{document}
"""
    write("PHASE_A_HARDENING_REVIEW.tex", tex)
    write("report_source_binding.json", json.dumps({"created_utc": datetime.now(timezone.utc).isoformat(), "baseline": BASELINE, "sources": {str(p.relative_to(REPO)).replace("\\", "/"): sha(p) for p in [OLD/"PAIRED_STRATIFIED_ANALYSIS.csv", OLD/"PAIRED_STRATIFIED_COMPARISONS.csv", OLD/"reliability_fixed_bins.csv", OLD/"conditional_quantile_calibration.csv", OUT/"tests/audit_attempt_002/audit_results.json", Path(__file__)]}, "latex_source_sha256": sha(OUT/"PHASE_A_HARDENING_REVIEW.tex")}, ensure_ascii=False, indent=2))
    print(json.dumps({"status": "DOCUMENT_SOURCES_CREATED", "markdown_reports": len(docs), "latex": "PHASE_A_HARDENING_REVIEW.tex"}))


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["--repair-latex"]:
        # Repair only this task's source, after preserving its original bytes.
        path = OUT / "PHASE_A_HARDENING_REVIEW.tex"
        original = (OUT/"tests/pdf_attempt_001/source.tex").read_text(encoding="utf-8")
        begin, rest = original.split("\\clearpage\n", 1)
        _, end = rest.rsplit("\\clearpage\\section*{公开方法参考与源码路径}", 1)
        names = ["SCIENTIFIC_EVIDENCE_AUDIT.md", "PROBABILITY_AND_TAIL_DIAGNOSTICS.md", "EVENT_CATALOGUE_CANDIDATES.md", "TERRAIN_STRATIFICATION_CANDIDATES.md", "RECOVERY_GOVERNANCE_GAP_REVIEW.md", "PHASE_B_ENTRY_READINESS_CHECKLIST.md", "RESEARCHER_DECISION_REQUIRED.md"]
        begin = begin.replace(r"\setlength{\parskip}{5pt}", r"\setlength{\parskip}{4pt}")
        begin = begin.replace(r"\renewcommand{\arraystretch}{1.12}\sloppy", r"\renewcommand{\arraystretch}{1.12}\sloppy" + "\n" + r"\ctexset{subsection={beforeskip=8pt,afterskip=5pt}}")
        path.write_text(begin + "\n\n".join("\\clearpage\n" + md_tex((OUT/n).read_text(encoding="utf-8")) for n in names) + "\\clearpage\\section*{公开方法参考与源码路径}" + end, encoding="utf-8")
        binding = read_json(OUT/"report_source_binding.json")
        binding["sources"][str(Path(__file__).relative_to(REPO)).replace("\\", "/")] = sha(Path(__file__))
        binding["latex_source_sha256"] = sha(path)
        binding["source_repair"] = "Table column raw escaping and whole-column repetition fixed; original source/generator preserved under tests/pdf_attempt_001"
        (OUT/"report_source_binding.json").write_text(json.dumps(binding, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    else:
        main()
