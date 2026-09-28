# B0 formal time semantics evidence

状态：**正式 IMERG–Himawari 绑定 NOT_YET_FROZEN；全库转换绑定 NOT_ESTABLISHED**。

## A. 实际 converted CF metadata

本轮只读抽查四个 Final 日文件：2021-08-25、2024-05-01、2024-05-27、2024-07-01。time 为当日午夜起分钟数，calendar=proleptic_gregorian，48 个坐标 0,30,…,1410；precipitation 为 (time,lat,lon)，(48,130,140)，单位 mm hr-1。title/source 标识 V07B Final / GPM_3IMERGHH_07。time 没有 bounds 属性，文件没有 time_bnds/time_bounds，也没有逐 slice 原生粒度文件标识。四文件完整 metadata/坐标、SHA256 在 converted_metadata_probes.json。未读取 precipitation 数组。

旧 P0 全库 time audit 可用作已完成工程证据；其 bounds presence CSV 是仅表头文件，不能单凭该空表声称逐行证明所有文件缺 bounds。这里关于缺 bounds 的直接证据限于四个新抽查 Final 文件。

## B. 转换链

日文件 history 声明转换了 48 个 source granules，manifest 记有 direct/Harmony 下载历史、日期与目标日文件。下载日志明确引用 `C:/Users/chenerxiao/Documents/极端降水预测/scripts/download_imerg.py`，本轮检查该路径不存在。全盘文件名发现和已知工作目录内容搜索未恢复可绑定到现存日文件的转换脚本版本。generic skill 与第三方库示例未证明是原生成代码，未执行。详见 conversion_chain_search.json、local_manifest_evidence.json、reference_code_candidates.json。

尚缺：原转换实现及 hash、native granule ID→日文件 slice 顺序映射、日期/时区处理、可能的重排/偏移。metadata 的时刻相等是证据增强，**不是数组来源身份已证实**。

## C. 新发现 native start/end/bounds

122 个原生命名缓存中按四个父目录各选排序首/中/尾，共尝试 12 个。9 个 Final（2021-08-25 原生 HDF5 3 个；2024-05-01 原生 HDF5 3 个；2024-05-27 Harmony 子集 3 个）均可读，time 为 seconds since 1980-01-06、calendar=julian，bounds=time_bnds。

9/9 的原生 time 等于 time_bnds 下界；上界−下界=1800 秒；对应 converted 日文件确有逐值相同解码时刻。原生 FileHeader start、filename S 一致。FileHeader stop 为 xx:29:59.999/xx:59:59.999，filename E 精度到秒，bounds 上界为下一整/半点，三者精度/端点约定分开保存，不伪造为冲突。bounds 解码继承 parent time 的 calendar，而不是默默改 calendar。详见 native_converted_time_comparison.csv。

另 2 个 Late 子集可读，1 个 2025-11-07 Late 临时文件报 `OSError(-51, NetCDF: Unknown file format)`，见 native_metadata_probes.json。该失败未删除、修复、替代任何文件；Late 不用于 Final 语义结论。

## D. 官方说明

原生产品层面的出处和限度见 [official_source_notes.md](official_source_notes.md) 及 official_sources.csv。官方文档不能代替本地 converter 证据，也不能代替研究者的跨源绑定批准。

## E. Himawari 实际时间字段

nominal_time 来自 `NC_H09_YYYYMMDD_HHMM_...nc` 文件名的排程标签，不能等同 obs_start/obs_end。源变量 start_time/end_time 的 long_name 分别为 observation start/end time，单位 days since 1858-11-17 0:0:0；历史 smoke 保存了真实解码值。本轮只复用这些已通过值和源变量 metadata，没有重跑 reader/model 链。

首 smoke 样本：nominal=2024-07-01T00:20:00+00:00；obs_start=2024-07-01T00:20:40.074697Z；obs_end=2024-07-01T00:29:38.162509Z；date_created=2024-07-01T00:38:48Z；candidate_analysis=2024-07-01T00:30:00+00:00。16 条旧记录只做因果关系复核，全满足 obs_end<=analysis_time；旧文件不修改。

**FROZEN 物理因果约束：obs_end <= analysis_time。** obs_end 超时或不可解析的样本不能被视为已通过因果 gate；不得改时间、选未来帧绕过。date_created 只记录，不作为已证明 operational availability；本轮没有完成历史实时回放。

## F. 候选及边界

b0_time_rule_candidates.csv 明确列出 T=start、T=center、其他 reference、NOT_ESTABLISHED。T=start 受抽样证据支持程度更强，仍不自动选择。T=center 当前没有正面证据，且其候选 analysis 可能不在 10 分钟 nominal 网格上，禁止通过四舍五入静默选帧。各方案都还需批准 analysis 定义和单帧选择规则，并验证真实 obs_end。

The cross-source IMERG-Himawari time binding used in this B0 smoke run is provisional and was used only to test the engineering pipeline. It is not a frozen scientific sample timing convention.

`analysis_time=T+30min; nominal_time=analysis_time-10min` 始终标为 ENGINEERING_SMOKE_TIME_MAPPING_ONLY。没有将 [T,T+30min) 或 end-minus-10min 宣布为正式科研规则。
