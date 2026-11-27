# 种子补齐正式训练包实现说明（V1）

## 范围
只新增 3 个代码/测试文件与本说明；既有模块、配置与 seed2029 证据链零修改。六任务：B2/2030、B2/2031、B5/2030、B6/2030、B5/2031、B6/2031，各 E0 九轮 4,320 更新。预算 25,920 更新、856,876 打开、2,865,430,597,384 字节；每任务 21,600 秒、整包 129,600 秒、初始 48 GiB、每任务 24 GiB、replay/重试 0。

## 复用与 seed 参数化
B2 分支复制 b2_runner.execute（初始化/ledger/九轮训练/Dev 评估），改用 fresh_b2(seed)、epoch_order(...,seed)，输出不再限制仓库 .local，completion 增加 code_commit 与逻辑字节/文件数；prepare 不建模型，worker 以结构契约加同 seed paired B3 引用核对替代 input_dimension_difference 全等。B5/B6 分支复制 static_training.worker，改用 TASKS seed、PYTHONHASHSEED=str(seed)、带 seed 的静态账本，pair_reference 取同 seed B4_s{seed}。其余复用 multiseed 的 load_inherited/endpoint/metric_values 等。seed 影响 fresh_b2、epoch_order、FormalDecision、paired_models(seed)、静态适配 RNG seed+10000 与 PYTHONHASHSEED。

## 基线与安全
B2 对比同 seed B3 Dev E9，B5/B6 对比同 seed B4 Dev E9；路径/SHA 钉在 budget.comparison_baselines 与 input_pins，并校验同 seed paired_initial_identity/paired_orders。摘要仅描述性（NOT_CLAIMED）。prepare 仅哈希元数据；dry_run 不读 Train/Dev、不建模型、不 torch.load；execute 串行失败即停，不重试/重放；approval 恰含八键且与 proposal 全等。

## 验证与风险
py_compile 通过；pytest 14 passed；git diff --check 通过；未训练、未读 2025。风险：B2 输出根改到仓库外私有目录需 Lead 接受；B5/B6 准备指纹由 inherited 同级推导；D: 空间不足 48 GiB，正式执行需 ≥48 GiB 新目录；启动前仍需独立进程/资源与批准门控。
