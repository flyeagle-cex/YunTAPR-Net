"""Chinese source-grounded reports; no unapproved scientific decisions."""
import json
import pandas as pd,numpy as np
from config import OUTPUT,CACHE,CONFIG,PYTHON
from common import write_text,write_csv

def mdtable(frame):
    def value(v):
        if pd.isna(v):return ""
        if isinstance(v,(float,np.floating)):return f"{v:.6f}".rstrip("0").rstrip(".")
        return str(v).replace("|","/").replace("\n"," ")
    columns=[str(k) for k in frame.columns]
    return "\n".join(["| "+" | ".join(columns)+" |","|"+"|".join(["---"]*len(columns))+"|"]+
                     ["| "+" | ".join(value(v) for v in row)+" |" for row in frame.itertuples(index=False,name=None)])

def write_reports(s,inv,years,meta,times,grids,precip,qi,lat,stats,anomalies,bounds_count):
    grid=grids.iloc[0]
    imerg=f"""# IMERG 全库审计总结

IMERG 文件级审计需复核数量：{s['imerg_needs_review_file_count']}。所有数值统计仅为 QC_STAT_ONLY。

1. 实际文件数：**{s['imerg_files']}**。成功打开 {s['imerg_open_success']}，失败 {s['imerg_open_failed']}。
2. 实际覆盖日期：{s['imerg_first_date']} 至 {s['imerg_last_date']}，年份为 {list(s['years'])}。
3. 各年份文件数：

{mdtable(years)}

4. title 完全等于 GPM IMERG Final Run V07B regional subset 的文件：{s['imerg_expected_title_files']}/{s['imerg_files']}。版本结论基于文件实际提供的 metadata，不伪造上游原生 granule 验证。
5. source 完全等于 GPM_3IMERGHH_07：{s['imerg_expected_source_files']}/{s['imerg_files']}。
6. 全部 48 帧检查：{s['imerg_48_frames_files']}/{s['imerg_files']}。
7. 严格相邻 30 min：{s['imerg_strict_30min_files']}/{s['imerg_files']}；同时满足文件名日期、当日 00:00–23:30 完整序列：{s['imerg_exact_daily_slots_files']}/{s['imerg_files']}。
8. 最早至最晚实际库存日期之间缺日：{s['imerg_missing_dates_within_observed_span']}。日期区间之外不计缺日；2025 年实际部分年度覆盖不自动视作库内缺失。
9. 重复日期关联文件：{s['imerg_duplicate_date_files']}。完整表见 imerg_duplicate_dates.csv。
10. unique grid / lat hash / lon hash：{s['imerg_unique_grid_count']} / {s['imerg_unique_lat_hash_count']} / {s['imerg_unique_lon_hash_count']}。实际 precipitation shape 集合：{s['imerg_unique_precipitation_shapes']}。既逐值比较坐标，又计算稳定 SHA256，未只比较范围和 shape。
11. precipitation units 实际集合：{s['imerg_units']}；没有自动换算。
12. NaN/FillValue 等无效降水像元总数：{s['imerg_invalid_precip_pixel_count']}；QI 无效像元总数：{s['imerg_invalid_QI_pixel_count']}。原始 NaN、FillValue 命中数另行保留，两者可能重叠，不相加。**0 mm/hr 是有效无雨，缺失没有转换为 0。**
13. 有效降水全库范围：{s['imerg_precip_min']:.6f}–{s['imerg_precip_max']:.6f} mm hr-1；有效负值像元数：{s['imerg_negative_precip_count']}。最高 20 个文件极值列于 imerg_precip_extreme_examples.csv；排名不是错误标签，未自行设定极值剔除阈值，其科学含义需要研究者判断。
14. needs_review 文件及完整原因见 imerg_needs_review.csv。没有删除、排除、替换或覆盖任何文件。
15. 对 YunTAPR-Net 的影响：库存时间跨度、实际网格和时间一致性提供工程证据；正式年份、空间范围及降水极值的科学解释仍由研究者决定。没有生成配对库、Dataset 或执行重采样。
16. “库存数据更多”、2025 部分年度、转换 history 的时间差异属于数据库存/生产记录现象，不自动改变科研设计。

实际参考坐标：lat={grid['lat_min']} 至 {grid['lat_max']}（{grid['lat_direction']}），lon={grid['lon_min']} 至 {grid['lon_max']}（{grid['lon_direction']}）；mean dlat={grid['mean_dlat']}，mean dlon={grid['mean_dlon']}。未自动 flip 纬度、未冻结或修改 bbox。

time 审计只使用当前 daily subset 的坐标、units、calendar；全库 metadata 中发现 time-bound 变量/属性文件数：{bounds_count}。未推测或写入 native granule start/end。

R_eq_0_fraction 和 R_gt_*_fraction 分母为每文件有效像元数，另附 *_total_fraction 以全部像元为分母。无有效像元时比例留空。precip_nan_fraction 指应用文件所带 missing/FillValue/有效范围与非有限值检查之后的缺失比例；raw_nan_count 单独保留。

QI 中位数逐文件精确计算，保留原数据中有效的 0；QI 全库描述范围 {qi.QI_min.min():.6f}–{qi.QI_max.max():.6f}。没有设定 QI 阈值、删除像元、作为模型输入或计算训练 normalization。
"""
    write_text(OUTPUT/"IMERG/IMERG_AUDIT_SUMMARY.md",imerg)
    maxrow=lat.loc[lat.creation_delay_seconds.idxmax()]
    display=stats[["metric","count","min","mean","median","p90","p95","p99","max","std"]]
    latency=f"""# 2024-07 Himawari latency 审计总结

1. 实际重新扫描 {s['himawari_files']} 个文件；四个 UTC 时间全部成功解析 {s['himawari_parsed']}。范围仅为 202407。
2–4. nominal→obs_start、扫描时长、obs_end→date_created 分布如下；额外保留 nominal→date_created。单位为秒，std 使用样本标准差 ddof=1；每行 count 对应该指标实际可计算样本。

{mdtable(display)}

5. creation delay：p50={s['creation_delay_quantiles_seconds']['p50']:.6f} s，p95={s['creation_delay_quantiles_seconds']['p95']:.6f} s，p99={s['creation_delay_quantiles_seconds']['p99']:.6f} s，max={s['creation_delay_max_seconds']:.6f} s。最大值文件：{maxrow['relative_path']}。
6. causal_as_latest 检查 obs_end <= nominal_time + 10min：True={s['causal_as_latest_true']}，False={s['causal_as_latest_false']}，不可计算={s['causal_as_latest_unknown']}；可计算样本通过比例={s['causal_as_latest_pass_fraction']:.8%}。
7. obs_end 超过 nominal+10min 文件数：{s['causal_as_latest_false']}。反例表 causal_as_latest_false_examples.csv 即使为空也保留列结构。
8. date_created < obs_end 文件数：{int(lat.created_before_end.eq(True).sum())}。这是独立的 TEMPORAL_ORDER_ERROR，不依赖 p99。
9. date_created 只能称为 product/file creation timestamp 或 metadata creation timestamp，不能直接等同于业务链路中的可下载/可读取时间。
10. operational availability 的证据结论：**Not established from current metadata alone.**

## 尾部标记与错误分类

按全部 {s['himawari_parsed']} 个成功解析样本计算 creation_delay p99={s['creation_delay_quantiles_seconds']['p99']:.6f} s；用 >= 比较，共 {s['latency_tail_review_files']} 个 LATENCY_TAIL_REVIEW 文件。原始 delay 数值完整保留。

**{CONFIG['latency_tail_definition']}**

尾部样本只供研究者查看，不表示错误，不删除、不剔除、不修改。TEMPORAL_ORDER_ERROR、PARSE_ERROR、MISSING_TIME_METADATA 等则单独分类。每文件可对应多个原因；异常表行数不应等同于唯一文件数。

实际 anomaly_type 计数：{json.dumps(s['himawari_anomaly_counts'],ensure_ascii=False)}。

nominal 来自文件名，start/end 的原始值、units、calendar 和 UTC 解析值全部保留，date_created 原字符串也保留。因果性仅判断观测是否结束，不要求 date_created <= analysis_time；未建立 operational availability_time，未重建 IMERG–Himawari 配对库。
"""
    write_text(OUTPUT/"HIMAWARI_202407/HIMAWARI_202407_LATENCY_SUMMARY.md",latency)
    write_csv(OUTPUT/"HIMAWARI_202407/himawari_202407_largest_creation_delays.csv",
              lat.sort_values("creation_delay_seconds",ascending=False).head(20))
    root=f"""# YunTAPR-Net Stage-0 / P0 数据工程审计

最终状态：**{s['status']}**。工程执行：**{s['engineering_execution']}**。

本轮目录：{OUTPUT}。此前 Himawari Stage-0 dry-run 报告与诊断 cache 均未修改。

- IMERG：{s['imerg_files']} 个文件；Himawari：仅 2024-07 的 {s['himawari_files']} 个文件。
- pytest：{s['pytest_test_count']} 个测试，failures/errors={s['pytest_failures']}。最终结果见 tests/pytest_final_output.txt 和 tests/pytest_final.xml。
- 原始 F/H 数据完整性核验：{s['source_integrity_pass']}。全部 {s['imerg_files']+s['himawari_files']} 个原件大小和修改时间复核，两库共 10 个跨时段样本 SHA256 再核验。这不是全库内容哈希证明；所有原件只读打开。
- IMERG needs_review 文件数={s['imerg_needs_review_file_count']}；Himawari anomaly_type={s['himawari_anomaly_counts']}。若只有 LATENCY_TAIL_REVIEW，则 NEEDS_REVIEW 表示等待研究者查看尾部，不代表工程失败或数据错误。
- 只新增本任务明确要求的 pytest 及 4 个缺失依赖，全部原有包版本未变。日志：logs/dependency_change_record.json。
- Windows 中文路径 netCDF4 问题已复现，逐文件复制到 {CACHE}，检查大小并抽检 SHA256，仅清理本流程创建的英文副本，未复制整个原始库。
- 缓存统计：{json.dumps(s['staging'])}。累计复制字节是 I/O 流量，不是持久占用。
- 数据审计耗时：IMERG {s['timing']['imerg_seconds']:.3f} s；Himawari {s['timing']['himawari_seconds']:.3f} s。按单文件/分块处理，没有把整个数据库载入 RAM。
- 单文件异常写入对应 status/error 和日志并继续，未隐瞒或自动修复。

## 输出导航

IMERG/：库存、年度库存、缺日/重复日期、元数据、时间、网格逐值/hash、降水 QC、QI、极值示例及完整 16 项总结。
HIMAWARI_202407/：逐文件时间原值/UTC 解析、延迟分布、分类异常、因果性反例与完整 10 项总结。
tests/：科学逻辑、中文路径 fallback、安全测试与 pytest 结果。
logs/：环境、精确依赖变更、运行日志、源码 hash、源文件完整性、缓存 I/O 和输出核验。
config.json：所有工程规则；audit_final_status.json：最终状态；output_manifest.csv：全部输出路径。

## 研究者本人仍需决定

正式研究年份不因库存更长而改变；降水极值的科学解释、44 类尾部样本的具体数量以最终状态为准、延迟尾部成因由研究者判断。p99 不是剔除/QC/科研阈值。operational availability 需要当前 metadata 之外的链路证据。

首次 pytest 跨盘收集触及系统目录而失败，初始 XML 保留；随后通过 rootdir/confcutdir/cwd 限定测试范围，最终测试真实执行。没有将 NOT_RUN 当作 PASS。

没有模型训练、归一化、划分训练集、重采样、空间插值、IMERG/Himawari 网格对齐、GFS/DEM 处理、重建配对库、Dataset、bbox 修改或全量 Himawari 预处理。全部描述统计为 QC_STAT_ONLY。QI 没有筛选阈值，没有作为模型输入。

Stage-0 P0 engineering audit complete.
Waiting for researcher review.
No scientific convention was changed automatically.
"""
    root=root.replace("44 类尾部样本的具体数量以最终状态为准、",f"{s['latency_tail_review_files']} 个延迟尾部样本的复核、")
    write_text(OUTPUT/"README_STAGE0_P0_AUDIT.md",root)
    commands=f"""# 复现命令（PowerShell）

固定解释器：{PYTHON}。这些命令不会升级科研环境。

    Set-Location -LiteralPath '{OUTPUT}'
    $env:PYTHONDONTWRITEBYTECODE = '1'
    & '{PYTHON}' -B -m pytest tests/test_p0.py -q -p no:cacheprovider --rootdir '{OUTPUT}' --confcutdir '{OUTPUT}' --import-mode importlib --basetemp '{CACHE}/pytest_new_unique_run'
    & '{PYTHON}' -B src/run_audit.py
    & '{PYTHON}' -B src/finalize_audit.py

当前目录已有结果，不要原地重跑数据入口。全部结果独占创建，禁止静默覆盖。独立重现时，创建新的 outputs/stage0_p0_audit/run_时间戳 目录，仅复制 src/ 和 tests/test_p0.py，并建立 IMERG/、HIMAWARI_202407/、tests/、logs/。config.py 从自身位置识别输出目录，cache 随 run 名称独立，原始目录不变。

精确依赖变更见 logs/dependency_change_record.json 与 pytest_install.log；无需再次安装。新增 pytest 9.1.1、pluggy 1.6.0、colorama 0.4.6、iniconfig 2.3.0、Pygments 2.21.0，没有升级原有包。

固定排序遍历；文件完整性抽检覆盖各库起点、四分位、中点、四分之三及末尾。seed=42。p99 使用 linear 分位数，比较符 >=；std ddof=1。不是科学阈值。没有批准下一阶段。
"""
    write_text(OUTPUT/"RUN_COMMANDS_STAGE0_P0.md",commands)
