---
type: research-progress-snapshot
project: YunTAPR-Net
date: 2026-11-14
engineering: FAIL
correction_preparation: PASS
scientific: NOT_VERIFIED
researcher_knowledge: NOT_ASSESSED
execution: STOPPED_NEW_VERSION_PENDING_RESEARCHER
---
# PyTorch初始化修正与补算待启

## 最新实际终态

研究者明确回复“批准，不要进行无意义的审核”，准确批准7a9c27a/4ae32d37的一次纠正包，记录为YT-POINT-CORRECT-20261114-001。两轮preflight、独立host和磁盘/内存/显存资源准入均通过。E0 worker在PyTorch随机种子与确定性配置初始化时停止，目标北京时间2026-11-14 07:37:13返回1。COSINE9未启动。

四个过程的元数据均已封口，合计284,740,136字节/220次打开，确认退出耗时87.031328秒，向上扣88秒。科学载荷读取、权重加载、模型构造和评价前向均0，优化器更新/重放/额外重试0。强雨POD/FAR补算仍待完成。

前一次NUL设备兼容失败保守扣276,585,640字节/622次打开/31秒。两次停止累计扣561,325,776字节/842次打开/119秒，科学载荷与评价前向仍0。

## 原因和针对性验证

PyTorch 2.11的torch.use_deterministic_algorithms会延迟导入Inductor/Dynamo并创建缓存。旧worker沿用系统临时目录，完整读取保护拒绝这些目录中的写入，tempfile最终报告找不到可用临时目录。此前真实检查覆盖模块导入和资源探针，遗漏了生产保护下完整seed_all路径。

修正将TMPDIR/TEMP/TMP、tempfile缓存目录及TORCHINDUCTOR_CACHE_DIR绑定到当前任务输出下的runtime目录。运行时身份检查、禁梯度、禁优化器构造、线程数和seed_all沿同一入口执行。

60项CPU/标准库合成回归全部通过。另以真实Torch/CUDA/NumPy和生产ReadGuard执行同一初始化入口，关闭worker子进程权限并拒绝全部科学输入，20.062秒通过。实际确认梯度关闭、确定性算法启用、cuDNN benchmark关闭及deterministic启用，元数据与科学载荷打开均0，模型构造、权重加载和评价前向均0。

## 新版本准确提案

| 项目 | 绑定值 |
|---|---|
| 执行代码 | `7f550c27a03f83f3f717b888e0e6df1e288fa2db` |
| 提案规范SHA256 | `0a615efc8cdccccc68b72f57b2f17357b3cdc95a861cb1a9b50049c751e83a14` |
| 任务 | E0 → COSINE9，B7/seed2029，两臂固定E9 LAST |
| 数据 | 2024 Development，963场景、3,303,090有效像元时次、407,820有雨像元时次 |
| 读出 | A/B/C三种继承的有限节点物理雨强代理全部报告 |
| 分类阈值 | FP32严格大于0.1、1、5、10、20、50 mm/h，保留相等计数 |
| 指标 | TP/FP/FN/TN、POD、FAR、CSI、Precision、F1、ETS、HSS、频率Bias、MAE、RMSE、平均Bias、CC |
| 新包限额 | 54,971,148,540字节、21,538次打开、7200秒，单臂3000秒，输出4GiB |
| 含两次停止累计 | 55,532,474,316字节、22,380次打开、7319秒 |
| 更新／重放／未来额外重试 | 0／0／0 |
| 资源准入 | 磁盘与主机可用内存各至少8GiB，GPU空闲至少5120MiB |

执行器仍需复现原六组概率指标，核对两臂监督mask及真值计数，R>20真值数717。身份、人口、原指标或资源检查失败即封口。原科学范围、模型身份和数据清单继承原批准方案。

固定副本和规范提案已绑定，614份绑定源码中本次仅worker变化，42份迁移元数据身份相符。新批准文件、preflight声明和正式输出均未创建，缺批准入口已在preflight前拒绝。本次新版本启动待研究者准确批准，旧两次批准已消费。

## 状态与限制

实际评价执行工程FAIL，纠正准备工程PASS，科学NOT_VERIFIED，研究者掌握NOT_ASSESSED。Harness本轮独立审核尚未取得。单seed、复用2024 Dev、弱雨Pinball约7.59%退化、历史driver/cuDNN指纹缺口及独立天气事件数量未识别等局限继续登记。真实评价与原指标复现仍待正式执行证据。

## 资料入口

- [[资料快照/20261114_paired_point_stop_v2/TERMINAL_VERIFICATION.json|本次停止终态与累计扣记]]
- [[资料快照/20261114_paired_point_stop_v2/CPU_REGRESSION.json|60项合成回归检查]]
- [[资料快照/20261114_paired_point_stop_v2/GUARDED_RUNTIME_INITIALIZATION.json|真实完整保护下初始化检查]]
- [[资料快照/20261114_paired_point_correction_v3/EXECUTION_PROPOSAL.json|新版本准确提案]]
- [[资料快照/20261114_paired_point_correction_v3/PREPARATION_RECEIPT.json|准备身份与门禁收据]]
- [[进度快照_2026-11-14_评价启动停止与纠正准备|上次停止与纠正准备记录]]
- [[极端降水预测]] · [[各阶段模型训练与评价指标汇总]]
