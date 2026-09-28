# B0 Train-only normalization contract

normalization_rule_defined=true 表示本轮已把用户要求的防泄漏范围规则写成可检查 contract；不表示 estimator、训练统计值或参数已冻结。scientific_method_frozen=false；statistics_computed=false；parameters=null。

## 未来必须遵守的范围

1. 正式 Train blocks、时间/空间/QC 和统计域批准后，只允许其 Train 样本拟合 B13 normalization。Validation、2025 Test 和未归属数据不得参与任何 fitted statistics。
2. 先按源 metadata 解码并提取 missing mask，排除 invalid、padding 和占位值；保持真实有效观测。布尔 mask 与输入同索引，不能把 missing 视作 0 来计算统计量。IMERG 无雨 0 不因数值为 0 被当作 missing；本轮未定义 label transform。
3. 保存方法、参数、dtype、单位、通道、Train区间/正式 sample index hash、bbox/坐标hash、QC/valid-mask policy、计数/权重语义、软件/脚本 hash、版本和创建时间；禁止静默覆盖参数版本。
4. Validation/Test 只应用已拟合的 Train 参数；Test 不得反向选择 estimator、clipping、阈值、统计域或重新拟合。Train 规则变动应产生新版本并重新验证，不读取 Test 结果来调参。

## 待研究者决定

mean/std、稳健变换或物理固定尺度等方法如何选择；按 native/target grid、主 mask/context 的统计域；像元/时次/天气过程权重；partial 样本计数；极端值与常量通道的处理。这里只列选择维度，无默认公式或新阈值。若最终选固定物理尺度，同样版本化，且不能据 Test 调整。

工程测试只检查角色访问控制与 missing mask 语义，**未计算正式或全数据 mean/std，也未扫描真实数值求分布参数**。
