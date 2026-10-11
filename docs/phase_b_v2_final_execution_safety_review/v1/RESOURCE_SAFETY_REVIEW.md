# 资源安全审查

本表真实smoke数字仅引用旧 `docs/phase_b_v2_real_train_smoke/v1/final_status.json` 与 RESOURCE_REPORT.md，本轮没有测量GPU或访问观测文件。

| 项目 | 状态 | 实际证据与局限 |
|---|---|---|
| 两次smoke CUDA allocated / reserved | PASS（历史有限事务） | B0 2,834,127,872 / 3,416,260,608 bytes；B1 2,858,972,672 / 3,435,134,976 bytes；非设备全局峰值 |
| smoke CUDA admission / reserved上限 | PASS（历史+静态） | free 7,283,408,896 bytes≥5GiB；allocator fraction与阶段reserved守卫6GiB；本轮未调用CUDA |
| CPU working set / commit区分 | PASS | 实际worker peak working set 2,453,544,960 bytes；peak pagefile/commit 7,416,758,272 bytes，不能把后者写成工作集或忽略系统commit压力 |
| 外部CPU/time终止 | PASS（人工） | 真worker句柄；模拟24MiB/1.8秒阈值，清空Job；不代表真实GPU进程终止已复测 |
| 本轮人工采样资源 | PASS | worker WS峰值 53411840 bytes；tree WS 67100672 bytes；worker private commit 44249088 bytes；受控分配32MiB |
| 当前仓库卷可用空间 | PASS（时点测量） | 51131883520 bytes可用 / 268904165376 bytes总量；仅仓库卷，非未来正式checkpoint卷承诺 |
| checkpoint空间保护 | PASS（静态） | Store.save预留2×tensor bytes+64MiB且payload上限256MiB；SmokeStore.save有512MiB可用空间检查；无法保证写入期间没有其他进程耗尽空间 |
| 正式资源许可与全过程容量 | NOT_VERIFIED | 未确定真实加载worker/cache、exact-score SQLite、每轮checkpoint保留与系统commit/GPU其他使用者的预算 |
| 不足时修改模型/batch/精度回避 | PASS（源码审查） | 现有准入拒绝与异常停止；本轮人工进程只改模拟限额，无模型配置 |
| 长程稳定性/热降频/驱动挂起 | NOT_VERIFIED | 本轮最长单例2.031秒；两次smoke不能证明九轮稳定 |
| 掉电/文件系统目录持久性 | NOT_VERIFIED | fsync +原子replace / SQLite FULL不等于在所有存储栈上抗掉电；未故意掉电或填满磁盘 |

正式首批六组计划是282,312更新，不按两个smoke耗时外推总耗时。未来独立批准资源测量、正式存储卷/保留方案、commit与CUDA admission、正式watchdog参数及停止策略之后再验收。真实GPU回收、驱动卡死时的Job响应、系统级文件访问零记录尚无本轮证据。
