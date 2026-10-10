# 未来数据与批准接口规范（当前不可执行）

当前Scene/Registry/Loader只接收人工ID和内存张量，scope必须SYNTHETIC_ENGINEERING_ONLY，years为空；无路径、读原始观测、数据下载或真实loader能力。train/development ID集合必须分离；内容摘要固定后拒绝变动。人为给张量换标签不能证明其来源：本工程只使用内部人工生成器，正式接入须另做来源证明。

未来真实适配器必须在独立批准的正式集成版本中实现，并提供以下契约，不能通过翻转bool激活：

|边界|未来必须核验的证据|
|---|---|
|数据权限|只读指定2023 train与2024 development路径/产品版本/许可；2025拒绝；原始文件SHA与访问账本|
|样本身份|冻结10455/10501配对合格ID、M1/Q1关系、train/dev互斥、无重复/遗漏|
|因果性|B13单帧或六帧、oldest→latest，分析时刻前60/50/40/30/20/10min，obs_end≤analysis，IMERG冻结目标窗口与版本|
|归一化|唯一冻结2023 shared scaler字节SHA，不重拟合、不取2024统计、不替代缺测|
|地理|冻结云南mask与SP04身份、轴/方向/空间配准；不得用人工mask进入真实评价|
|张量|输入FP32；独立bool原生valid；参考[ B,1,100,100 ] FP32；有雨在该FP32域严格>0.1；32q FP64；完整资格失败即停|
|运行范围|18RunSpec封闭矩阵；首批seed2026六组单独许可；B9、S0原50轨迹、V0、batch2/验证8/不丢尾批|

authorization.py仅定义FutureApprovalBinding、FutureResumeBinding与FutureAuthorityVerifier Protocol。批准绑定protocol/code/data/qualification/scaler/mask/resource/run-scope SHA、独立事件和研究者身份。恢复另外绑定具体LAST SHA、原执行批准祖先、完成边界receipt SHA和新的独立恢复事件。没有issuer或verifier实现；start_formal/open_real_data始终抛PermissionError。字符串、JSON、Git提交和测试结果不能成为批准证明。

获得真实preflight许可前，不打开实际scaler、云南mask、2023/2024原始观测/参考或私有checkpoint。当前复用fresh初始化时仅临时注入公开代码验证器，推迟scaler字节核验；这不替代未来正式preflight，也没有改变随机种子或参数配对算法。防火墙是合作式Python进程防误用，不是恶意任意Python/系统权限的安全沙箱。
