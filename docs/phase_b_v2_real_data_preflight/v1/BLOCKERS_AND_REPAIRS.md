# 阻塞与修复记录

没有自动修正 SHA、路径、年份、资格、坐标或科学设置；没有选择另一数据集。运行只有 attempt_001，错误详情与私有路径留在 .local。已完成的独立 scaler/地理检查与受阻解码分别报告。

工程启动初次失败：新 .local 目录尚未建立，PowerShell 输出重定向失败；pytest 尚未执行，真实读取为0。创建该隔离日志目录后运行36项工具检查通过。环境探测发现 psutil 不可用，采用 Windows 原生内存计数器，未安装依赖或扩大读取权限。


```json
[
  {
    "stage": "FULL_UNSELECTED_PAYLOAD_IDENTITIES",
    "status": "NOT_VERIFIED",
    "reason": "All frozen paths checked by stat; only deterministic selected payloads byte-hashed. No full raw-file sweep in limited preflight."
  }
]
```

未选中文件当前内容身份尚未完整 byte-hash；已有冻结 SHA 引用与实际路径/大小检查不替代该证据。本轮有限预检不主动扩成全数据读取。资源、权限或完整性异常将停止相应读取，不自动重试或更换场景。

# 只读来源保护顺序修正

收尾静态审查发现初版 ReadLedger.register 在拒绝2025年份前调用 Path.resolve。Windows 路径解析可能查询文件属性；首次负面测试未计数这些内核操作，所以不能证实其零路径属性访问。没有调用2025 payload 的二进制读取、netCDF解码或像元处理。此缺口保留，不把应用层零内容读取冒充全系统零访问。

已修正：先检查封闭年份、词法根目录及日期，再允许2023/2024路径规范化；拒绝非法参数时不触发解析器。8项新增合成测试把解析器替换为必抛异常，使用人工不存在文件名；允许分支也以合成文件系统替身验证。最终44项只读工具测试通过。未重复真实解码。

实际预检执行的是修正前版本，SHA与最小差异补丁保留在 CODE_CHANGE_PROVENANCE.json 和 READONLY_GUARD_SOURCE_CHANGE.diff。正向冻结身份、读取、解码和预处理实现未改；交付版新增更早的非法输入阻断。本轮真实受控账本保持原测量，不虚构修正后真实运行记录。

2025_RAW_ACCESS=0在本交付中明确是受控数据内容读取计数；前期测试的底层路径属性查询NOT_INSTRUMENTED，整体严格就绪仍NOT_VERIFIED。正式训练、科学接受和历史恢复没有因此获得授权。

公开发布检查首次阻断：扫描脚本自身含本地用户名哨兵字面量。已删除该字面量，改用通用路径模式；未提交或推送含私有标识的版本。修复仅涉及公开材料生成器，没有再次读取原始数据。
