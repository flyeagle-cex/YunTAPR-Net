# 合成梯度与环境验证报告

最终项目运行时：Python3.12.14、PyTorch2.11.0+cu128、pytest9.1.1，RTX5060Laptop、CUDA12.8，构建包含sm_120。来源tests/project_cuda_environment.json。测试依赖安装在本任务.local/test_dependencies，未修改项目CUDA运行时依赖。没有测量正式训练GPU耗时、模型吞吐或显存预算。

CPU suite attempt008：177 passed、0 failures、0 errors、0 skipped；CUDA attempt004：3 passed、0 failures、0 errors、0 skipped。11项静态检查通过。当前独立测试用例180，历史attempt不相加。CPU用的是同一项目CUDA Python解释器但输入留在CPU；CUDA另开限时60秒进程。

13个CPU梯度测试：gamma0/2解析Focal梯度；gamma0/2各一次gradcheck与gradgradcheck；全部32tau的正/负分段解析梯度；E0/E1/E2的总损失双头gradcheck；三臂q梯度权重及单坐标中央差分；invalid像元零梯度。计数按pytest实例为13，gradgradcheck等多个断言仍属于其所在一个实例。

gradcheck固定FP64、eps1e-6、atol1e-6、rtol1e-5；单坐标差分eps1e-6、rel2e-8、abs1e-9。测试点远离Pinball折点和q支撑/相邻序边界。不是通过增加容差或给q排序来制造通过。Focal解析导数是alpha_t*(p-z)*[m^gamma+gamma*b*pt*m^(gamma-1)]，m=1-pt；gamma0单独为alpha_t*(p-z)。Pinball对q的导数在欠预测处为-tau/32，在过预测处为(1-tau)/32，再乘lambda/N_valid。

无雨检查中q.grad是实际零张量，不是None；有效发生梯度保留。无效像元两头梯度0。P3折点仅检查值、finite与可反传，不断言唯一数学梯度。backward只求合成叶子的梯度；测试没有Optimizer实例或step，禁止torch.load/save和expm1的自动fixture会在误调用时抛错。

保留的实际尝试：attempt001的103项初轮通过；CPU002因导入冻结协议工具而缺yaml，出现1个collection error；改为只AST提取原lr_for_update纯函数，不import其模块。CPU003=162、004=174通过。旧torch2.7.1+cu118最小CUDA张量探测虽成功，但完整CUDA001在60秒超时，未形成测试完成数。找到历史工程记录的cu128环境后，CPU005/CUDA002因缺pytest启动失败；pytest安装到任务私有target后CPU006/CUDA003完成。相关完整输出均保留，不把未启动/超时记为通过。

这些结果仅证明受测候选数学与保护逻辑。没有真实2023/2024样本、封存2025、私有checkpoint、新模型forward或正式验证推理。核心科学假设、效应界限、多重比较和资源执行授权仍未批准。

最终边界复核的CPU007为176通过/1失败：标量设备错配应在finite算术前拒绝。代码将device检查前移并保留同形dtype合同，容差未改；CPU008=177通过/0失败，CUDA004=3通过/0失败。详见tests/scalar_device_repair.json与原失败日志。
