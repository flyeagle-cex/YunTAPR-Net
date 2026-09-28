# Researcher decisions required

B0_FORMAL_NOT_READY。以下决策尚无批准，不以工程测试通过代替。

- [Formal time binding](DECISIONS/01_formal_time_binding.md)：批准 T/native window/analysis_time 的科学关系及单帧选择规则。
- [IMERG October gap](DECISIONS/02_2025_10_imerg.md)：决定如何处理同版本 Final 2025-10 缺口。
- [Model input bbox](DECISIONS/03_model_input_bbox.md)：在 SP01–SP04 或另行论证范围中选正式输入域，并批准坐标对齐。
- [Weather-system context](DECISIONS/04_context_margin.md)：确定天气系统上下文尺度及对称/非对称依据。
- [Train / Validation design](DECISIONS/05_train_val_blocks.md)：选择完整块、边界buffer/事件隔离和Validation调参协议。
- [Missing and QC](DECISIONS/06_missing_qc.md)：批准partial-frame/invalid-input策略、target有效性与loss/metric分母。
- [Formal architecture](DECISIONS/07_formal_b0_architecture.md)：批准正式U-Net/GPROF-IR-style配置，明确第一版概率头。
- [Normalization](DECISIONS/08_normalization.md)：批准Train-only范围内的方法、统计域、权重与版本规范。
- [Loss/output and spatial alignment](DECISIONS/09_loss_output_and_alignment.md)：批准正式loss/output、native-target对齐、missing传播、指标、概率校准和重复实验方案。
- [Multi-month data qualification](DECISIONS/10_monthly_data_qualification.md)：正式规则明确后，批准后续多月数据资格验证范围和缺口处置。

已冻结：研究期大框架及2025Test；真实IMERG目标网格；GADM4.1云南主mask；物理因果与missing语义。未冻结：上述具体时间/空间/分块/QC/归一化方法/模型与输出协议。GFS/DEM及后续模块不列为B0输入blocker。
