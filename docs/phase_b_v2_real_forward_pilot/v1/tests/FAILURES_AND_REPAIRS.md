# 初次失败与修复

35 项新增合成单元测试 attempt_001 全通过。随后只读公开冻结清单的计划核验首次失败：`KeyError: expected_nominal`。原 `paired_ids` 的接口是 `(B0 rows, B1 rows)`，新增计划构造器调用次序相反。修正为 `paired_ids(b, a)`；没有修改原核验函数、冻结清单或科学定义。

该失败发生在公开元数据阶段，原始数据句柄打开数与模型 forward 数均为 0。临时日志清理还因异常分支未关闭日志触发 Windows 文件占用错误；核验脚本改用 finally 关闭审计句柄。原始失败原因保留，不以扩大读取范围或替换场景修复。

真实 pilot attempt_001 在原始数据访问前出现 `AssertionError: Duplicate torch object ... with different rules`：同一个 deny callable 覆盖多个 PyTorch API，与 torch._dynamo 延迟规则注册冲突。此时 raw payload 打开、真实模型 forward 均为 0。修复为每个禁止 API 使用独立闭包，并增加延迟规则注册测试。

37 项针对当前版本的合成测试 attempt_002 通过。仅允许一次已证实零真实访问、零 forward 的包装函数修复续接；attempt_002 继承 attempt_001 的公开元数据字节消耗和原始开始时间，不重置 4 GiB/30 分钟预算。任一真实场景/forward 失败后均不能使用此修复入口。首败脱敏证据见 PRE_ACCESS_FAILURE.json。

最终 37 项合成测试 attempt_003 全通过。交付扫描首次因负面测试的人工根名称未明确含 synthetic 而拒绝发布；改为明确 synthetic 的非法根，含义和拒绝结果不变。扫描器中的用户名改为运行时从 home 名称取得，避免源文件本身披露个人用户名。

LaTeX 首次编译缺少 amssymb 已修复，内置编译随后成功。本地导出时 MiKTeX 的 hyperref 依赖等待安装，已停止本次自己的导出进程；删去不必要的超链接依赖并禁用自动安装后成功导出一页 PDF。最终源再次通过内置编译，渲染检查无裁切或重叠。以上均无新增真实数据读取或模型 forward。
