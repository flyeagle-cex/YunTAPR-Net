---
type: research-progress-snapshot
project: YunTAPR-Net
date: 2026-11-14
engineering: FAIL
correction_preparation: PASS
scientific: NOT_VERIFIED
researcher_knowledge: NOT_ASSESSED
execution: STOPPED_NEW_CORRECTIVE_LAUNCH_PENDING_RESEARCHER
---
# 评价启动停止与纠正准备

## 本次实际执行

研究者对代码4fada685、提案06340722的准确启动问题回复“是”，已记录为YT-POINT-20261114-001并单次派发。两轮限定元数据preflight通过，独立监督进程通过无Job/无包身份检查。目标控制器在2026-11-14 07:08:16北京时间返回1，停止于正式输出目录创建前的资源准入检查。

实际未创建worker、未加载权重、未读取科学载荷、未进行评价前向，优化器更新、重放及额外重试均0。此次启动额度已消费。新的多雨强阈值POD/FAR结果仍待取得。

## 已复现原因与修正

原读取保护将subprocess打开Windows NUL设备判作输出目录外写入。nvidia-smi通过stderr=DEVNULL使用该设备，资源探针捕获异常后返回gpu=null，控制器随即停止。使用旧固定代码的只读系统资源探针已复现该链路。原失败瞬间的资源数值未保存，已登记该证据缺口。

修正限定在读取保护对准确系统空设备的处理、失败错误中记录资源数值、以及正式输出创建前封口控制器记账。相似名称的普通文件仍须符合原写入范围。同一科学计算源码、权重、数据人口、阈值和A/B/C读出沿用原方案。

59项CPU/标准库合成回归检查全部通过，新增覆盖真实subprocess的DEVNULL重定向和准入失败记账。修正后的保护内真实资源探针通过，科学载荷与模型读取均0。Harness本轮审核尚未取得，真实CUDA评价及原指标复现仍待正式执行验证。

## 失败段扣记

两轮preflight实际元数据142,367,912字节/110次打开。旧控制器在正式目录创建前未封口记账，按其完整128MiB/512次元数据额度保守扣记。旧段合计276,585,640字节/622次打开。首次preflight至确认退出30.473463秒，向上扣31秒。

## 一次纠正启动提案

| 项目 | 准确绑定 |
|---|---|
| 执行代码 | `7a9c27ac28cf2cac2cc3fa918f3e1c58e63761ed` |
| 提案规范SHA256 | `4ae32d3790a68cb8eb32164f35311d6a5dd9fb44618e8c0f5b3869eb444ce142` |
| 任务 | E0 → COSINE9，两臂B7/seed2029固定E9 LAST |
| 数据 | 2024 Development，963场景、3,303,090有效像元时次、407,820有雨像元时次 |
| 读出与阈值 | A/B/C，FP32严格大于0.1、1、5、10、20、50 mm/h |
| 指标 | TP/FP/FN/TN、POD/FAR/CSI/Precision/F1/ETS/HSS/频率Bias、MAE/RMSE/平均Bias/CC |
| 新包限额 | 54,971,148,540字节、21,538次打开、7200秒、输出4GiB |
| 含失败段累计限额 | 55,247,734,180字节、22,160次打开、7231秒 |
| 优化器更新／重放／未来额外重试 | 0／0／0 |
| 资源准入 | 磁盘与主机可用内存各至少8GiB，GPU空闲至少5120MiB |

修正包固定副本干净，614份绑定源码身份已核对，仅一份绑定控制器文件变化。原模型、报告和科学来源清单一致，42份迁移到新固定副本的元数据指纹一致。缺批准入口实测在preflight前拒绝。纠正包批准文件、preflight声明及正式输出均未创建。启动决定待研究者对该新版本和累计限额明确批准。

## 科学与验收状态

本次实际执行工程FAIL，纠正准备工程PASS，科学NOT_VERIFIED，研究者掌握NOT_ASSESSED。单seed、反复使用2024 Dev、历史driver/cuDNN指纹缺口、弱雨Pinball约7.59%退化及独立天气事件数量未识别等局限继续登记。

## 资料入口

- [[资料快照/20261114_paired_point_stop/TERMINAL_VERIFICATION.json|停止终态与保守扣记]]
- [[资料快照/20261114_paired_point_stop/GUARDED_RESOURCE_REGRESSION.json|旧缺陷复现与修正资源探针]]
- [[资料快照/20261114_paired_point_stop/CPU_REGRESSION.json|59项合成回归检查]]
- [[资料快照/20261114_paired_point_correction_v2/EXECUTION_PROPOSAL.json|一次纠正启动准确提案]]
- [[资料快照/20261114_paired_point_correction_v2/PREPARATION_RECEIPT.json|准备身份与门禁收据]]
- [[进度快照_2026-11-14_总控意见与启动待批|上轮总控记录]]
- [[极端降水预测]] · [[各阶段模型训练与评价指标汇总]]
