# Focal 候选实现逐段解读

阅读 config.py、validation.py 后，再打开 focal.py。occurrence_numerator(logit,rainy,valid,*,alpha,gamma) 返回零维 S_occ 张量，不除以 batch、有效像元数或有雨数。星号 * 表示 alpha/gamma 只能用关键字传递，减少把两参数顺序写反的风险。类型注解用于阅读；真正拒绝错误输入的是函数中的运行时检查。

logit=[B,1,H,W] 是未 sigmoid 的实数分数；rainy/valid 必须为同形、同设备的 bool。rainy 来自 rate 原 float32 严格大于 float32(.1)；Focal 裸函数不自行根据概率产生标签。valid 是 IMERG 有效性与云南掩膜交集，与 rainy 是两个不同概念。

设 b=BCEWithLogits(l,z)，pt=exp(-b)，alpha_t=alpha*z+(1-alpha)*(1-z)，则 S_occ=sum_valid alpha_t*(1-pt)^gamma*b。BCE 用 reduction='none' 保留逐元素值，再执行 focusing 和求和；不能先求 mean 再拿 scalar 计算 pt。稳定 BCE 直接吃 logits，不能先 sigmoid 再传给 BCEWithLogits。[PyTorch 2.7 BCE API](https://docs.pytorch.org/docs/2.7/generated/torch.nn.functional.binary_cross_entropy_with_logits.html) 给出了输入与 reduction 的定义；项目真实数学来自 src/yuntapr/losses/focal.py。

第一个代码段调用 finite_number：Python 中 bool 是 int 的子类，所以用 type(value) 精确排除 True/False；NaN 与 Inf 也拒绝。裸算术允许 alpha 属于 [0,1]、gamma>=0；正式候选配置只允许三个预声明组合，不开放参数搜索。随后检查 logit 与两个 masks，拒绝隐式广播。

第二段选择运算 dtype。logit.float() 的等价 .to(torch.float32) 转换不是 detach：例如原 BF16 叶子仍连接 BCE 的计算图，backward 后 grad 保留原叶子的 dtype。with torch.autocast(...,enabled=False) 只在本块内固定运算精度，退出后恢复外层上下文。

logit[valid] 是 bool 索引，将有效位置收集为 [N_valid]；rainy[valid] 同顺序收集标签。这样 invalid 像元不进入分子，避免先做乘 mask 再指望 NaN*0 消失。这里仍先检查全域 logit finite，不能用索引隐藏坏输出。无 valid 的裸函数返回 graph_zero；总损失入口则提前拒绝零监督。

torch.full_like(logits,alpha) 产生同 dtype/device 的类别权重；torch.where 根据每个 hard label 选择 alpha 或 1-alpha。alpha=.5 时两类权重都为 .5，正负类别不能在 E1 改为权重 1。gamma==0 使用 alpha_t*bce，避开不必要的 focusing 运算并保留系数；gamma2 使用 exp、pow 和 sum，与原 E0 定义一致。

F1/F3 的 l=0、gamma2 单像元期望 ln2/8；F2 的 gamma0 为 ln2/2；F4 两个相同有效元素为 ln2。103 项初轮套件包含这些手算检查；最终套件还覆盖不平衡 100 干/1 湿、±1000 和 ±1e30 logits、FP32/64及低精度输入。所有数值属于合成教学，不是科研评价结果。

gamma0 的单元素梯度为 alpha_t*(sigmoid(l)-z)。gamma2 还需要对 focusing 权重求导，不能把 pt.detach()；测试用完整解析式和 FP64 gradcheck/gradgradcheck 对照。valid=false 的位置梯度为0。finite 检查是工程保护；alpha/gamma、BCE及 focusing 是科学定义。

小练习：独立手算 l=0,z=false,gamma0 的值和梯度；解释为什么两类 l=0 损失相同而梯度符号相反；观察 sum 与 mean 的二倍关系；找出哪些行若删掉 .5 会改变 E1。学习练习不要求重新实现才能开展本轮候选开发，但正式接入前研究者仍需理解和审查。
