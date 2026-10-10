# 执行与恢复负面检查

|尝试|处理|
|---|---|
|无独立批准|BlockedRunner无条件抛错|
|True、APPROVED、AUTHORIZED_TO_EXECUTE、自报JSON|不能获得启动能力|
|gamma/lambda/alpha、seed、样本资格越界|闭合配置重验后拒绝|
|2025、错误年份、样本数或normalization改变|候选计划拒绝，文件守卫另禁2025|
|epoch>9、batch/accum/drop_last/LR horizon变化|拒绝，不自动修正|
|LAST/run/code/protocol/data/init身份错配|先绑定核验再拒绝|
|BEST、partial/train-only、更新数不完整|不能恢复|
|缺少独立LAST批准|FormalExecutionBlocked|
|只有批准reference字符串|未认证，仍拒绝；无state应用器|
|资源不足或完整GPU case失败|停止该测试/套件，不自动重试或降级|

复用既有review_checkpoint_binding，SHA字符串匹配不证明真实文件和批准事件。本轮未调用checkpoint_v2.verify_file/apply_verified，未打开BEST/LAST，未生成审批记录。

文件守卫拒绝raw、checkpoint、2025及非白名单CSV；白名单只含SHA绑定的精确公开元数据路径。操作守卫阻断step、torch.load/save、Module.load_state_dict和expm1。负面用例只检查人工路径，没有打开真实禁用文件。守卫属于独立测试进程，不能替代正式授权。

历史B1恢复仍NOT_GRANTED。SYNTHETIC_INTEGRATION_PASS与FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED明确分开，后者始终false。后续需要真实独立事件、验真及run/LAST绑定，不能将自报元数据升级为批准器。
