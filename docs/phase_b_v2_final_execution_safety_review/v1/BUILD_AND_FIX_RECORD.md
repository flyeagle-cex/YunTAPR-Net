# 失败、修复与构建记录

|阶段|真实结果|处置|
|---|---|---|
|首次人工套件|19自动PASS；2个异常退出的具体分类NOT_VERIFIED|保留run_d07768eed92a.json。发现退出后再次QueryFullProcessImageName可能失败；持有句柄身份改用已验证的内核缓存，已退出对象不重新查询image；测试明确要求WORKER_UNEXPECTED_EXIT|
|修复后人工套件|19 PASS / 0 FAIL，16进程场景|run_6a6862278869.json；没有真实数据/模型/优化器|
|补充异常监控退出与静态保护|8 PASS / 0 FAIL；只新增1个driver_crash人工场景|abrupt_exit收据证明内层进程在外层stop前已被内核终止；final_guards.log|
|首次保护文件/额度对账|FAIL：sealed_rows_unchanged误报false；sealed_quota_unchanged一直true|保留initial_protected_validation_failure.json。SQL tuple / JSON list表示不同；只修复审计脚本规范表示，没有写原账本|
|表示回归、路径词法保护|1+3 PASS / 0 FAIL，新增进程0|最后三个用mock证明mkdir前拒绝；不会触发2025 resolve/stat/open|
|最终保护复核|3657既有tracked文件及三处封存锚点SHA不变；账本行一致|protected_validation.json；原两次额度COMPLETE_SEALED未重开|
|首次公开材料静态检查|FAIL：隐私扫描匹配到扫描器自身的路径检测字面量|保留initial_delivery_validation_failure.json。拆分检测字面量并继续检查所有公开文本；不禁用扫描、不触发任何模型/进程更新|
|首次PDF导出|成功3页，但2处overfull|拆分首段与缩小单独URL行；源LaTeX保留可编辑|
|最终PDF|内置编译成功；XeLaTeX成功；3页逐页PNG检查PASS，0 overfull|MiKTeX用户日志目录写入被沙箱拒绝的附带警告不影响输出；未安装/更新组件。中间日志/PNG仅.local，不上传私有路径|
|首次暂存diff检查|FAIL：Windows CRLF触发仓库空白规则；两份log被忽略|保留初始JSON与原字节副本于.local；只将本轮公开文本规范为LF，并显式允许两份脱敏测试log。未改历史文件或重新执行进程测试|

最终31项不同工程检查通过；主套件开发重放累计两轮19项，另8+1+3项，合计50个检查执行（不含静态交付核验）。顶层人工用例预留总数33，上限40；“用例”不等于Windows实际进程数，venv包装器、解释器及子孙成员单列在收据。

首轮与修复主套件没有同时登记执行源码SHA，不能追补成同期身份记录。manifest绑定最终交付代码；该限制在正文披露。机器收据包括预期故障导致的非零退出，它们是测试PASS，不是模型运行失败，更不涉及重试真实更新。

没有改动旧watchdog、正式源码、loss、模型、协议或历史证据。仅新候选namespace及本独立交付目录被提交。旧watchdog不具备本轮新的Job保护，禁止将其复用于正式运行；接入需研究者另批版本审查。
