# B0 Train / Validation block candidates

FROZEN 大框架：Development=2023、2024 每年 March–October；Final Test=2025 March–October。具体 Train/Val blocks、边界 purge/buffer、事件分组和调参协议 **NOT_YET_FROZEN**。本轮仅候选时间区间，不生成正式 sample index 或执行 split，不随机拆相邻 30 分钟样本。

|候选|Train 天数 / 名义 30min 槽位|Validation 天数 / 名义槽位|
|---|---|---|
|TV01_YEAR_HOLDOUT|245 / 11760|245 / 11760|
|TV02_2024_JUL_OCT|367 / 17616|123 / 5904|
|TV03_BOTH_OCTOBERS|428 / 20544|62 / 2976|

区间为 UTC [start,end_exclusive)，见 CSV/JSON。TV01 为跨年 holdout；TV02 为连续晚雨季 holdout；TV03 为两年 October holdout，后者季节偏差明显。每个候选优缺点和跨界事件风险已逐行列出，无 winner。

估计只按历法天数×48，并对照旧 IMERG inventory 有文件的天数，不读取全库数组，也不推定所有时刻有有效标签。Development 490 天、23520 个名义槽位；Final Test 245 天、11760 个计划槽位，其中已登记 214 天、10272 个上界槽位，October 缺 31 天 / 1488 槽。不能把 10272 个槽声称为真实可用 Test 样本。跨源时间绑定、Himawari 缺帧、valid-mask/QC 后的联合样本数均 NOT_ESTABLISHED。

Himawari 当前只有 2024-07 全月工程审计（4390/4464 文件，有缺口）；其他研究月份不能把 NOT_AUDITED 写成 MISSING 或 PASS。未执行新的多月审计。

天气过程隔离需要独立事件目录及跨分界核查；现无已批准事件划分。研究者可选择完整过程归属或固定时长 purge；具体小时数和双侧/单侧规则尚未设定，不以任意 24/48 小时作为已批准阈值。上表**尚未扣 buffer**。B0 单帧不要求六帧全部存在，但未来共享 sample index 时不得让同一输入/标签或事件跨 Train/Val。所有统计、筛选、阈值选择和模型选择只在已批准 Development/Train/Val 内完成，2025 不参与。

2025 October 缺口单独交研究者决定，不能借 split 方案自动把正式研究期缩短。
