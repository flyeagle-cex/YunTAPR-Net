---
type: research-progress-snapshot
project: YunTAPR-Net
date: 2026-11-14
engineering: FAIL
technical_fix_self_checks: PASS
harness_review: PENDING
scientific: NOT_VERIFIED
researcher_knowledge: NOT_ASSESSED
execution: STOPPED_PARTIAL_CONTROL_E0
---
# 配对评价V3停止与Harness待审

## 研究者职责分工

GPT网页负责总控和科研任务统筹，Harness负责独立审核，Codex负责技术实现、受权执行、监控及证据归档。研究者保留最终科学决策、准确执行批准和验收。

## 实际执行终态

研究者明确要求启动7f550c2/0a615efc固定包，记录为YT-POINT-V3-20261114-001，独立执行器单次派发。两轮preflight、独立host、资源准入和运行时初始化通过，E0进入开发集读取阶段。

北京时间2026-11-14 07:51:36目标退出1，控制器报Output links outside the claimed namespace并终止worker，终止确认成功。自首次preflight至确认退出126.208717秒，向上扣127秒。E0未完成，COSINE9未启动，完整点指标与配对completion均未生成。本轮原准确批准已消费，更新、重放和额外重试均0。

E0保存的读取账本有457个READ_COMPLETE、1,285,614,934字节的天气读取及1个PENDING job。权重加载和模型初始化阶段已通过，worker完整来源记账与前向次数未封口。新POD/FAR等完整配对指标仍待后续执行证据。

Codex曾依据保留目录和读取账本误报仍在运行，现已向总控更正并将target_exit收据设为监控状态优先来源。

## 技术诊断与修复

原失败未记录具体触发输出条目。停止后的检查没有找到仍存的链接或目录外目标。使用纯合成并发临时文件已复现旧实现的竞态，Windows对已删除文件的Path.resolve可能返回扩展DOS前缀或NTFS $Deleted路径，使包含关系检查误判目录越界，另有FileNotFound竞态。历史具体触发文件尚待Harness独立核对，历史归因按推断登记。

技术修复改用不跟随链接的lstat/scandir快照，拒绝symlink和reparse point，跳过已经消失的文件和目录，继续统计输出存储及preflight/console文件。修复提交为525ee38ae9c1a446202055b8cb0422f6947b5712，实际执行版本为7f550c27a03f83f3f717b888e0e6df1e288fa2db。修复版本尚未进行新的正式评价。

63项CPU回归自测通过。修复后的5秒并发创建/删除测试完成13,504次快照、错误数0，科学源读取、模型加载和评价前向均0。旧合成复现出现857次边界异常和133次FileNotFound。该自测证据交由Harness独立审核。

## 来源记账范围

| 项目 | 已保存证据或暂记上界 |
|---|---|
| 两preflight与控制器封口元数据 | 213,555,786字节／165次打开 |
| E0 worker终态记账 | 未封口，完整实际量待独立对账 |
| 暂扣整份控制臂载荷 | 26,747,373,950字节／7,953次打开 |
| 暂扣整份worker元数据额度 | 512MiB／2,048次打开 |
| 此次来源保守上界 | 27,497,800,648字节／10,166次打开 |
| 含此前两次停止的累计保守上界 | 28,059,126,424字节／11,008次打开／246秒 |

上述上界使用缺失worker的完整已批准额度保守记账，完整实际源字节数仍待Harness独立对账。已保存的457次成功天气读取单独登记。预算余量的后续使用仍需研究者准确批准。

## 网页总控与Harness交接

网页总控已实际接收研究者职责分工及随后终态更正，终态回执为a347fbc3-4c52-46e1-9a1f-3bedfc7e5fb0。总控安排Harness限定核对本次故障修复、Windows并发路径处理及缺失worker记账；Codex归档准确修复提交、工程证据和Obsidian记录；后续科研建议及新执行申请由总控汇总给研究者决定。

Harness待审包已整理为HARNESS_REVIEW_REQUEST.md。Computer Use因无法可靠识别当前浏览器URL而停止，Harness界面递交尚未完成，独立审核状态PENDING。总控回复内容已直接取得，其回执证据范围限定为消息内容。

## 验收状态

执行工程FAIL，修复自测PASS，科学NOT_VERIFIED，研究者知识掌握NOT_ASSESSED。当前完整性能指标缺口、单seed、复用2024 Development、历史环境指纹缺口及既有弱雨代价继续登记。科学验收和后续决策由研究者保留。

## 资料入口

- [[资料快照/20261114_paired_point_execution_v3/TERMINAL_VERIFICATION.json|实际终态、身份和记账范围]]
- [[资料快照/20261114_paired_point_execution_v3/OUTPUT_BOUNDARY_FIX.json|技术复现与修复自测]]
- [[资料快照/20261114_paired_point_execution_v3/HARNESS_REVIEW_REQUEST|Harness限定待审包]]
- [[资料快照/20261114_paired_point_execution_v3/CONTROLLER_TERMINAL_ACK.txt|网页总控终态与职责回执]]
- [[资料快照/20261114_paired_point_execution_v3/CONTROLLER_RECEIPTS.json|总控回执身份和交接状态]]
- [[进度快照_2026-11-14_PyTorch初始化修正与补算待启|上一份准备快照]]
- [[极端降水预测]] · [[各阶段模型训练与评价指标汇总]]
