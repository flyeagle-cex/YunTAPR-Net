# 实际工程结果与资源

所有数字均 SYNTHETIC_ENGINEERING_ONLY，不是科研性能证据。

|模型/臂|实际step|峰值allocated MiB|峰值reserved MiB|整项秒|
|---|---|---|---|---|
|B0_MATCHED_V2/E0|9|2806.47|3882|9.283|
|B0_MATCHED_V2/E1|3|2734.12|3816|2.525|
|B0_MATCHED_V2/E2|3|2734.12|3816|2.584|
|B1_V2/E0|9|2830.39|3892|7.038|
|B1_V2/E1|3|2756.49|3826|2.553|
|B1_V2/E2|3|2756.49|3826|2.534|

六组全部完成5场景epoch与5场景独立验证。每次训练/验证N_valid=17150；只来自人工3430-cell布局。B0/E0、B1/E0的epoch2连续执行与绑定epoch1 LAST的续跑，训练记录、共同评价及model/optimizer/scheduler/RNG摘要完全相同。每模型跨三臂fresh摘要相同。

两项额外CUDA故障测试向参考标签注入NaN：模型forward后、loss/optimizer前拒绝，更新0、LAST0、实例停用。CPU故障覆盖保存中断、锁异常、SHA与路径、缺失model/optimizer/RNG、seed/arm/code/protocol/epoch/update、覆盖缺失/重复/顺序、逐步LR/clip、分母、共同评价权重、AdamW状态与祖先错误。

实测RTX5060 Laptop，完整501×501模型，冻结BF16/FP32/FP64路径。计时包含创建、训练、验证、保存恢复、部分首次库启动；峰值包含E0基准和恢复引擎。没有真实I/O或长期GPU热稳态，不能据此估算正式耗时。资源不足时应停止，不改batch/模型/精度；本轮无资源不足跳过项。

当前未验证的正式功能：真实10501样本流式验证、真实数据读入/资格/时空配准、scaler和mask字节身份、9epoch实际运行、多个seed正式性能、独立审批事件验证服务、真实LAST授权祖先、长程资源/磁盘满/断电目录持久性。合成checkpoint仍只在专用临时目录；无正式模型权重发布。
