# 控制变量矩阵

冻结继承项的旧批准仅覆盖原科学定义；将其用于本实验及所有新增建议仍须批准。本轮协议整体PROPOSED_FOR_RESEARCHER_APPROVAL。各路径的观察SHA、关键行号和引用类型在source_identity.json记录；外部原始文件不打开。

|控制项|拟定值或规则|分类|静态证据与待审批内容|
|---|---|---|---|
|样本资格|M1完整六时隙交集，Train10455/Validation10501，两模型完全配对|继承冻结|四份manifest SHA来自协议；元数据字节核对，不重新跑数据资格|
|时间|标签[T,T+30min)，A=T+30min；六帧A−60至A−10，obs_end≤A|继承冻结|science_contract_v1.1/time与dataset_b1/check_frame；nominal/date_created不证明业务延迟|
|产品/通道|B13；IMERG V07 Final，3–10月2023/2024；2025拒绝|继承冻结|不可混V08/Early/Late、补帧或扩大B0集合|
|空间/有效性|SP04原映射、100×100、云南中心入界3430；B13全valid|继承冻结|映射/掩膜SHA；外部mask仅继承声明身份，本轮不验证其payload|
|标签|float32 y > float32(0.1) mm/h，在FP64提升前判断|继承冻结|total_loss及phase_a_validation_v2；相等边界是干，绝不按float64重判|
|scaler|mean271.60515414265217 K、std19.93959597783802 K、冻结SHA|继承冻结|B0/B1共用，normalize先FP64算再FP32；不refit|
|双头|发生1通道；33 raw = 32 allocation + 1 span，输出32 qlog|继承冻结|quantile_v2/heads与parameterization；不改骨干或SP04|
|quantile数学|tau=(i−0.5)/32；epsilon_w=epsilon_span=1e-4；FP64累计归一化|继承冻结|相同prefix终点作分母，q32=z0+span；不clamp/sort/nan_to_num|
|精度|BF16 forward，参数/raw q FP32，q transform/pinball FP64，TF32关闭，无GradScaler|继承冻结|log-domain loss不隐式expm1，守卫失效即停|
|优化器|AdamW betas(.9,.999)、eps1e-8、仅Conv2d.weight decay1e-4，其他0|继承冻结|foreach/fused/amsgrad等均false，不调LR补偿loss变化|
|LR/梯度|base1e-4/min1e-6，W5228/U261400，步前应用；全局clip5|继承冻结|lr_for_update与formal_phase_a_v2/update，非有限或剪裁失败即停|
|batch/尾部|physical2、accumulation1、drop_last=false；末batch1|继承冻结|每epoch5228更新，禁止补重复样本或OOM后自动减batch|
|alpha/gamma|alpha恒0.5；E0/E2 gamma2，E1 gamma0|唯一实验因素之一|gamma仅E1变化；gamma0=.5BCE，不改alpha|
|lambda_q|E0/E1=1、E2=2；仍S_qr/N_valid|唯一实验因素之二|现total_loss无lambda接口；未来由研究者实现再审查，不换分母|
|fresh身份|同seed同模型三条件完整初态相同；B0/B1共享同形状参数|继承策略+新增跨臂规则|锚点、原生B1shape不同张量、RNG/代码SHA；实物尚未生成|
|seeds/排列|2026/2027/2028；同seed全部臂相同seed+epoch排列|新增待审批|现reproducibility/permutation固定2026，未来参数化且环境seed对应|
|增强/缺测|无随机数据增强；M1缺测reject；无fallback/skip|继承冻结|源码链未见增强；审批后执行审计再次核验实际调用与顺序|
|预算/终点|9完整epoch、47052更新；主checkpoint固定9，不按BEST/early-stop|新增待审批|新固定预算替代旧max50+earlystop选择，LR50horizon不变|
|验证/保存|每epoch冻结顺序验证，epoch9全科学指标；完成训练与验证才能存LAST|保留边界+新增选择规则|9验证循环，endpoint不重复forward的工程方案需审查|
|评价口径|十箱、32tau、原真值雨强层、原core；E1−E0/E2−E0|继承诊断+新增主效应|效果界限、guardrails、多重比较未批准，禁止事后选择|
|恢复|只认可完成epoch LAST，任何恢复另有独立LAST SHA绑定批准|治理要求|不迁移历史参数；当前B1偏差不追认，自动resume=false|
|审计与权限|独立run roots、append-only日志，公开仅代码/聚合/报告|待审批工程资源|本轮未创建模型目录、未申请数据访问、未实例化模型|

同seed、同模型的对照只有gamma或lambda_q不同；时相是两模型之间原有差异，seed是预声明重复维度。未来比较同时改变其它项将成为协议偏离，先停止并登记，不把偏离run与主矩阵合并。
