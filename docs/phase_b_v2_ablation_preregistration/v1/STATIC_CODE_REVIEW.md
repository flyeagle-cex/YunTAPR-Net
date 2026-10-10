# 真实代码的静态审查与限制

本轮仅看源码文本/AST及仓库metadata字节SHA，未import yuntapr、torch或数据模块。函数行号与身份机器登记在source_identity.json；源码已发表，没修改任何正式loss、model、runner、冻结配置或历史文档。

|审查发现|影响|本轮处理|
|---|---|---|
|focal_bce_sum已有alpha/gamma形参|gamma0数学可表示，但训练调用固定2|给研究者数学映射，未改函数或调用|
|focal参数finite/bool及mask前置校验不完整|裸函数不能视作全套安全接口|规格列明未来拒绝条件，不自行修正式代码|
|pinball_sum没有最终分母、axis固定mean|权重实验必须在总损失组合，不能误改为rain mean|给组合接口与独立手算期望|
|b0_core_loss无lambda_q；formal_mode未执行授权gate|旧调用不能直接执行E2，形参/默认scope不是授权|新runner必须独立批准；本轮只非执行提案|
|seed_reproducibility、epoch_permutation和初始化proof固定2026|I3不能只改JSON seed就运行|建议以后显式参数化/匹配startup environment与排列SHA|
|formal_phase_a_v2的gamma2、旧scope/roots及BEST早停固定|不支持本18臂固定终点矩阵|不得调用/修改旧入口，本轮没有launcher|
|phase_a_validation_v2固定gamma2且全局FP64|适合作为三臂共同core，不能等同变动的训练目标|保持原报告数学；未运行验证|
|checkpoint_v2仅完成train+validation epoch保存，选择状态带旧BEST/earlystop|只做终点validation会改变恢复边界|本提案每epoch验证，epoch9固定主终点，未来新schema另审|
|v2 quantile transform FP64、相同prefix总和、epsilon1e-4与严格序守卫|不能放宽数值规则来减少失败|全继承；物理量仅显式只读转换，未模型forward|
|源代码无本训练链随机增强|当前对照应保持无增强|未来实际调用/样本顺序要另有执行审计，不仅靠文本搜索|

未检查原始数据完整性、外部mask字节、CUDA可用性、checkpoint反序列化、实际fresh/RNG或loss梯度。source_identity的external pins属于继承声明，不是本轮重开验证。AST与SHA通过只表示代码/元数据身份与文档可追溯，不能说明本18臂已工程集成、能安全启动或科学有效。

环境探测中两个Python环境未提供jsonschema库，本轮不安装依赖，使用标准库对本包声明的封闭JSON Schema子集做结构/常量检查，遇到未知关键字fail-closed。错误 marker路径首试失败，定位技能包内脚本后成功登记文档操作；这些是环境探测/路径故障，真实记录在tests/environment_preparation.json，不伪装成损失或科学测试失败。
