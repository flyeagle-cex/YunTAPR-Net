# 独立研究者执行决策门槛

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
