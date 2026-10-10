# Fresh 初始化、排列与固定终点

CPU对三个seed各为E0/E1/E2独立构造一对真实模型，共18实例。不同seed的state SHA不同；同模型同seed跨三臂state、buffer和post-pair RNG摘要一致。CUDA的seed2026初态与CPU证据一致。没有保存正式初始化权重。

依据原paired_initialization规则分别重置Python/NumPy/Torch/CUDA，构造B0与B1，然后只复制同名同形状张量。唯一不同形状为backbone.enc0.conv1.weight和backbone.enc0.skip.weight；B1二者原生SHA保持，skip为0。参数总数4329410/4331810。使用原state_digest和parameter_groups分类，没有构造optimizer。

PYTHONHASHSEED在进程启动时固定2026，CUBLAS_WORKSPACE_CONFIG=:4096:8；逐run的Python/NumPy/Torch/CUDA seed取2026/2027/2028。context退出恢复调用者状态。SHA证明当前初始化字节，不证明批准；正式全程随机性和环境仍需绑定。

仅用10455个人工order_ID，独立Generator(seed+epoch_index)做randperm。每seed的9个epoch无丢失/重复，重复调用一致；seed2026与原epoch_permutation纯数学规则对照。未读取真实样本内容。

S0复用上一轮全部47052个LR位置通过证据，并核对源码字节未变；不重跑旧套件。新增epoch0/1/8/9边界检查，epoch9剩余0、next_epoch/next_lr为None。没有压缩50epoch cosine、按表现选BEST或自动换seed。

18候选run每个47052潜在更新，共846936；验证每epoch1313批，共212706。实际更新0。新命名空间以SYNTHETIC_ENGINEERING_ONLY__phase_b_v2_integration_v1__开头，与历史正式run隔离。
