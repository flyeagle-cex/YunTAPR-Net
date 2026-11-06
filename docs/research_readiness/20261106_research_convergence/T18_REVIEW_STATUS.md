# T18 推断方案版本与审查状态

状态 PROPOSED / AUTHORIZATION_PENDING。此文件记录理论候选与独立审查，未批准 H2 统计执行。

## 版本关系

- T18_INITIAL_PROTOCOL.md 保存初始完整候选，11792 字节，SHA256 FA0B23E9BC3E34B7E48F6F0E0180364FC36D85BC20E75EB289C3F5CF58B83D16。
- T18_R1_AMENDMENT.md 保存 C1–C3 修订及实施定义，8601 字节，SHA256 0D0026D7014763B7ED274A50FD702FC0DC5248930D68799983F0F499D99C362A。以其明确替换的条款为准，其余继承初稿。
- 网页总控已初审接受 R1 及实施补充。Harness 对 R1 的限定独立复核已 PASS（仅 PROPOSED 纸面候选）。总控接受与独立审核分别记录。

## 独立初审与修订

Harness 的 docs/audits/T18_H2_INFERENCE_REVIEW.md 为 NEEDS_REVISION，6335 字节，SHA256 E3879207B6913C430C9827733B0EED9453A2859B46413FF7CF8D60FDA77B4819。记录保存在审核者自身仓库，未由 Codex 复制或修改。

C1 补充总阳性、充分阳性块、Top 排名局部支持及 AP 贡献集中度门控。C2 补充预登记适用性材料、删一日扰动代理、ACF/Bartlett/四段变化与双锚点诊断。C3 区分分量失败、同分量两尺度失败、实现冲突和未定。数值均为 PROPOSED 的必要拒判保护，全部通过也不能证明平稳、弱依赖、AP 正则性或真实覆盖率。

Harness 初审自身提交为 collab/dsh-20261102@48e8a70194dcd3bd6d5baf8d5d8e77f59978f242。Codex 只读确认本地 HEAD、受跟踪与未跟踪树干净，并以 git ls-remote 独立确认远端同名分支 SHA 一致。一次性 Git 原生审批由研究者本人操作，Codex 未代点、未代审核者执行 Git 写入。

## 证据与权限限制

本轮只查阅统计方法原始论文、现有理论文本及管理/Git 状态。仅做二项临界索引的纯数学常数核对，不是模型指标计算或 bootstrap 覆盖验证。没有读取预测、标签、权重载荷或 2025，未训练、推理、校准或安装依赖。

原始方法来源为 Künsch 1989（https://doi.org/10.1214/aos/1176347265）、Clémençon 与 Vayatis 2009（https://icml.cc/2009/papers/309.pdf）、Romano 与 Wolf 2005（https://doi.org/10.1111/j.1468-0262.2005.00615.x）、Nordman 与 Lahiri 2014（https://arxiv.org/pdf/1403.3275）。这些文献不自动证明本项目完整 AP 与 Top1 配对 MBB 的适用性。本协议两尺度、固定尺度根及拒判阈值属于待审设计。

## 当前状态

理论候选及限定独立复核工程 PASS。本文件为 Codex 提交前记录，Codex 本次归档/Git 完成状态以其后 Shared/CODEX.md 和聊天的提交后回执为准。科学 NOT_VERIFIED。研究者掌握 NOT_ASSESSED。H2 为 INCONCLUSIVE / INDEPENDENT_NOT_VERIFIED。

独立 E 身份、真实采样过程与联合推断适用性论证、研究者最终科学批准、精确读取/计算/写入预算均未具备。理论审查通过不会解除这些执行门控。

Harness R1 审核 docs/audits/T18_H2_INFERENCE_REVIEW_R1.md 为 6456 字节，SHA256 8EE32488F8A8CBBF4369EE725F850390338E05BA1A49C7C46F69495CC3B546EF。Codex 已实际读取全文。研究者本人完成一次性原生许可后，Harness 自行提交并普通推送 R1，collab/dsh-20261102@3a7bc62852851501a65e7dfd8959abf2e8507c55。Codex 只读检查其提交仅含 R1 审核文件、工作树干净，并独立 ls-remote 核对远端 SHA 一致。

网页总控在会话 6ae89873-7ee8-83e8-858d-ad3bc2cf5f88 的正式答复 e13eff86-f4fa-45ef-be8a-447e86422951 确认 T18 纸面协议结项，理论与限定独立审查 PASS，保持 PROPOSED / AUTHORIZATION_PENDING。后续只复用已有 E 入口条件补明缺口，无合法独立 E 时停止在真实数据门槛，不新增重复理论任务或管理审计。
