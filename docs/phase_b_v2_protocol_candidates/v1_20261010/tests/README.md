# 本轮检查范围

上一轮87项检查不重跑、不计入本轮。新增测试仅为候选预算的整数计算、纯合成角色支撑和单因素对照；不导入torch，不打开真实manifest内容、数据或checkpoint，没有forward/backward/optimizer step。

合成命令：python -m pytest -q tests/phase_b_v2_candidates -p no:cacheprovider --junitxml=docs/phase_b_v2_protocol_candidates/v1_20261010/tests/synthetic_attempt_001.xml。首次实际结果：23 passed / 0 failed。时间支持重叠测试不证明天气事件独立，也不授予任何执行权。

随后执行新候选资料、文档链接/来源/预算、LaTeX/PDF与Git边界的静态交付检查；当前数量和PDF页数在delivery_verification.json与final_status.json记录。文档构建日志、编译诊断和失败（如发生）保留。PDF渲染图与中间产物留本地，不上传截图、重复PDF或本机配置。

纯计划脚本：scripts/phase_b_v2_candidates/planning.py；构建脚本：build_delivery.py。禁止用这些脚本启动模型；candidate_design.json没有approved配置或可执行入口。

所有正式训练、校准拟合、真实reference验证、2025测试和新增模型推理未执行，原因是审批边界或资料尚未取得，而不是测试通过后即可自动运行。

最终 PDF 为 attempt 004，21页，三个 XeLaTeX pass 返回0，溢出/缺失字形/LaTeX warning均0；21页逐页目视复核。首次终端构建因缺少本机xurl失败，完整控制台已脱敏保留，之后三个导出成功；早期成功版本的格式问题已修复。最初report_source_binding仅为修复前身份，当前文件身份以report_source_binding_final为准。检查JSON中的工作区路径及测试XML的hostname已脱敏，原记录和渲染图保留本地。
