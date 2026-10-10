# 实际合成检查与保留失败

当前结果：synthetic_attempt_008为CPU177/0/0，cuda_attempt_004为CUDA3/0/0，static_attempt_002为11/0。CPU+CUDA共180个不同pytest实例，不把103/162/174等历史重复相加。XML hostname已脱敏，公开.log保留完整console，原记录在.local。

CPU002：缺yaml造成1个collection error；测试改为只AST提取冻结lr_for_update纯数学函数，不修改原模块或安装yaml。CUDA001：旧cu118不含sm_120，完整loss测试60秒超时，0完成数；最小FP64单张量探测成功不等于完整CUDA通过。CPU005/CUDA002：项目cu128环境缺pytest，未启动测试；pytest9.1.1及依赖安装至本任务.local/test_dependencies，未改正式环境。其后CPU006/CUDA003通过。修复未改变科学参数或测试容差。

合成运行工具：python scripts/phase_b_v2_ablation_implementation/run_checks.py --attempt <新编号>；默认CPU。显式--cuda仅运行三个CUDA loss用例，子进程限时60秒。失败/超时不覆写旧日志，不假装PASS。项目解释器若无pytest，将PYTHONPATH指向任务私有test_dependencies。静态入口：python scripts/phase_b_v2_ablation_implementation/static_review.py --attempt <新编号>，不import torch或候选loss。

conftest自动保护禁止optimizer step、torch.load/save及expm1；fixture只创建小型合成logit/q/float32参考/masks，H1–2、W1–3，不构造正式模型。测试报告中的forward/backward是loss算术，不是模型训练。所有raw、2025、正式模型forward与optimizer更新计数为0。

最终边界复核的CPU007为176通过/1失败：标量设备错配应在finite算术前拒绝。代码将device检查前移并保留同形dtype合同，容差未改；CPU008=177通过/0失败，CUDA004=3通过/0失败。详见tests/scalar_device_repair.json与原失败日志。
