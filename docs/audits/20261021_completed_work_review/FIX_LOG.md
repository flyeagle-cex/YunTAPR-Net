# 最小修复日志

修复提交 `7b916edc6e1cb48481e1daff333108d79685fd45`。基线 `96a2a61eeb9b0c4a8513133133c75bfdf4b58726`；独立分支 `audit/completed-work-20261021`。只在独立仓库写入。

## P1-001：seed2028 无法识别实际 seed2027 v7 完成账本

**证据**：`src/yuntapr/experimental/phase_b_v2_multiseed_candidate/protocol.py:require_predecessor` 原实现只读 `.git/phase_b_v2_seed2027_fresh_v1.sqlite`，只接受 FRESH_V1 COMPLETE、282312 次 RETURNED_VERIFIED、六组及54轮完成。当前获批 v7 的 `quota.py`、`accounting.py`、release 和实际状态明确采用独立 v7 账本，其新尝试额度是198664，保留祖先83648，累计消耗上限364969。

**真实影响**：即使 v7 将来全部完成，旧接口仍拒绝；若存在旧的 completed fresh 快照，旧实现还可能在 v7 仍 ACTIVE 时错误回退。当前 seed2028 的 authority 无条件拒绝，所以未观察到真实越权启动；这是未来接口 P1，不是已发生的训练安全事故。

**失败复现**：用真实 SQLite 合成账本、AST 提取原 `require_predecessor` 函数体，避免 import 训练路径或访问实盘账本。源码未改前，完整 v7 被 PermissionError 拒绝，ACTIVE v7 + stale COMPLETE fresh 未被拒绝；其余3项通过。[P1_001_before.txt](evidence/P1_001_before.txt)

**最小修改**：仅在上述函数中优先选已存在的明确 v7 namespace，按198664新尝试核验；v7未完成时立即拒绝，不回退旧账本。没有v7时保留原fresh检查。查询在只读连接、query_only和单一读事务中完成，并明确关闭连接。六组epoch9/update47052、54个LAST_COMMITTED条件保留。未改变累计预算，也未为其他未来恢复版本建立通用自动选择器。

**修改文件**：1个已有生产候选源码文件，14行增加/4行删除；新增针对性测试 `tests/completed_work_review/test_predecessor_interface.py`。新增 `tools/audits/completed_work_review.py` 是本轮元数据审查工具，不接入正式运行路径。

**验证**：5/5通过：完整v7只读识别、ACTIVE v7不回退、旧fresh兼容、缺1次核验返回拒绝、seed2028授权门继续拒绝。约0.4秒；使用独立 bundled Python 3.12.14标准库，没有torch、CUDA、模型构造或原始数据访问。[P1_001_after.txt](evidence/P1_001_after.txt)

**测试准备异常也保留**：首次系统临时目录ACL拒绝，未进入目标复现；改用隔离工作区。随后fixture未显式关闭SQLite导致Windows清理失败，修复fixture连接管理后才形成干净的基线复现。见 `P1_001_environment_attempt.txt`、`P1_001_fixture_attempt.txt`；不把这些异常算成原项目的两个新缺陷。最终测试cleanup仅删除已解析并检查位于独立fixture根下的合成目录。

**发布状态**：本轮未重签 prepared_release、未修改原release/pins/授权、未部署v7。旧发布凭证不覆盖本分支的新代码；未来若采用，必须在独立版本审查中重新绑定代码身份，并另行取得对应执行授权。补丁本身不授权seed2028。

## 历史问题与不修改项

- v5 `COMPLETE_PREFIX` ImportError：真实零更新失败；v6已补接口，v7有后续真实执行证据。本轮不修改v5。
- v6 Job snapshot WINERROR_5：真实零更新失败；v7绑定竞态修复与新指令。只读观察，不重复执行旧版本。
- v1物理分位数overflow：保留原失败、4个完整epoch和50537实际更新；v2模型变化已有研究者单独批准，不在本轮改模型。
- 历史独立恢复许可缺口、2025访问历史、GFS vintage、q32/强雨问题：进入研究者决策清单，未重写历史或调整科学设定。
- P2格式/架构/性能修改：未执行。

代码及测试diff见 [CODE_DIFF.patch](CODE_DIFF.patch)；完整交付文件与摘要由 `DELIVERY_MANIFEST.json` 核验。修复未改变既有正式训练结果。
