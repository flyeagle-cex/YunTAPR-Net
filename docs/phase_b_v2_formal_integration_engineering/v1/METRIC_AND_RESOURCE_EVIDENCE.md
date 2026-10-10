# 指标算术与有界资源证据

以下仅为 SYNTHETIC_ENGINEERING_ONLY，不是新科研指标结果。

训练复用 `(S_occ_gamma_arm + lambda_q*S_qr)/N_valid`。共同评价复用 `common_validation_sums`：固定 gamma=2、alpha=0.5 的 FP64 分子，加未加权 FP64 `S_qr`，除全部有效像元；Conditional Pinball 除真实有雨有效像元。雨标签在原始 FP32 rate 上严格比较 `>float32(0.1)`。32 tau=(i−0.5)/32，覆盖事件为 log1p(rate)≤q_i，分母 N_rain。不对分位数排序修补，不调用物理域 expm1。

概率分数使用模型原生 sigmoid 输出再提升 FP64；BF16 并列分数原样保留，不从 FP64 logit 重算概率。十箱边界为 0.1…0.9，等于边界落右箱。雨强层沿用 (0.1,1]、(1,5]、(5,10]、(10,20]、(20,30]、(30,50]、(50,+∞)。空箱输出数量 0 和均值 null；无雨 CPB/覆盖/AP 为 null；单类 AUROC 为 null；全正类 AP=1。

精确 ranking 将原分数编码为 big-endian binary64 BLOB，按每个分数聚合正负例频数，维护全局及 35 日期块索引；AUROC 并列给半分，AP 在并列组末使用非插值精确率增量。没有用十箱替代。手算样例 p=(0.5,0.5,0.25,0.75)、y=(0,1,0,1) 得 Brier=0.15625、AUROC=0.875、AP=5/6；这是完全合成的单元测试数值。

日期块以标签窗口起点所在 UTC 日期为准，2024-03-01 起每七日一个非重叠块，共 35 块。保存 scene→block、源身份、分子/分母、各箱/雨层、32 覆盖计数及各块精确分数频数；最终 receipt 绑定整张精确分数表 SHA。未运行 bootstrap、未计算 p 值、不作确认性声明。

q32 上尾比较预声明 10/50/100/500/1000 mm/h 的 log1p 阈值，分别计全部/有雨/无雨暴露、场景与去重格点。上尾统计分母为全部有效像元，与仅有雨条件覆盖分母不同。另报告 q32 log 最小/最大和 log 空间 q32−q1 span 最大值。本轮没有新增分位数百分位分布、事件目录或物理验证。

## 内存、磁盘及实测限制

指标累计每批最多 8 场景、每场景最多 10000 格点；SQLite cache 1 MiB、数据库 64 MiB 上限、DELETE journal 和 FULL synchronization，暂存资源不足立即停止。保留的全局/35块 tail_grid 约 1.8 MB，32 分位数只处理当前 batch。数据库使用主键索引流式遍历，无全预测 Python 列表。64 MiB 对 BF16 分数并列很充分，但**未证明满足未来所有真实分数基数与磁盘开销**；超过上限停止，未来资源预算需独立审查。checkpoint payload 张量总量上限 256 MiB，写前至少保留两倍 tensor bytes 加 64 MiB 空间。文件系统掉电原子性、journal 与目录元数据最坏占用未作全平台保证。

GPU 为 NVIDIA GeForce RTX 5060 Laptop GPU，PyTorch 2.11.0+cu128。准入要求 host 可用≥8 GiB、CUDA 可用≥5 GiB、工作盘≥1 GiB；通过后才实例化原始模型。实际运行仍为 FP32 参数、CUDA BF16 模型路径与 FP64 分位数/共同评价，没有降低模型、batch 或精度。

成功事务的准确峰值和耗时见 `tests/gpu_B0_MATCHED_V2.json`、`tests/gpu_B1_V2.json`。时间包含构造、一步训练、独立验证、checkpoint 保存/安全读取/恢复与 SHA 核验；不等于纯推理延迟或正式训练耗时。首次失败前峰值未记录，明确为 NOT_RECORDED_BEFORE_FAILURE。没有测量业务传输/入库延迟，论文定位 A 仍为推荐候选。
