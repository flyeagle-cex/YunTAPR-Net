# DYNAMIC-E2-TERMINAL-20261108｜E2 恢复终态与四格结果有限复核

- 审核者：Harness（独立于 Codex）
- 范围：只复核已保存 JSON/SQLite 元数据、恢复终态和四格算术；未训练/推理/重评，未读权重载荷、原始源、缓存或 2025，未改 Codex
- 结论：**PASS_WITH_LIMITATIONS（限定工程终态/证据身份与算术复核；科学 NOT_VERIFIED）**

## 1. 收据与启动终态

- `TERMINAL_VERIFICATION.json`：6,444 B / `A2852EB8A8B880A99C84097A6FEE75E9C9CEB7EC18D0AAA750C2FC680175970A`
- `RESULTS.json`：9,527 B / `1D351FE3F8FC5C5DD6FC7F8D223DD52A4D79C2FFE629D3FE644BB76B5B64BDAF`
- WMI `target_exit.json`：`return_code=0`、无自动重试；实际总时长 **2319.634027 s < 3600 s**。
- outer/B8 `completion.json` 均为 `COMPLETE_TRAIN_AND_DEV_EVALUATION`；代码提交 `f3b90f654b67fda538f4f156422841b69cc50b23`。

## 2. 恢复终态核对

- `updates.sqlite` 实测 **480 行、全部 RETURNED、范围 3841–4320**；仅 B8。
- 源读取回执相加：static 312,828 B/1 次 + Train 26,424,262,556 B/7,918 次 + Dev 26,639,253,112 B/7,950 次 = **53,063,828,496 B / 15,869 次**，与 completion/terminal 一致。
- B8 E9 Train 摘要与失败前保存文件字节和字段完全一致；B8 E9 checkpoint receipt 的 SHA 为 `ed3438be2add635cd8dc7ccb28ed48268cd5c327bc85d7e08ff5a5077168220c`、`53,905,789 B`；本次未重开该 checkpoint，只核收据（root 已单次直接哈希）。
- B7 完整 E9 继承：原 B7 completion 为 4320 更新，E9 receipt SHA `349f33212a1ddd305ca1d2ae4e3d8fee02d6fbec67f0aff293f7d261f2e34b47`；恢复任务只含 B8，未重训 B7。
- B8 E9 canonical report digest 与 receipt `validation_receipt_sha256=c3529106...c5ed` 一致；B7/B8 `development_09.json` 的 `source_identity`、`population_ids_sha256`、`partition_sha256` 和六个 group 的 `ids_sha`/`source_sha` 均一致；分母均为 **963 场景 / 3,303,090 有效 / 407,820 有雨**。

## 3. 四格主结果与算术

| cell | conditional Pinball E0→E2 | 相对变化 | Brier 变化 | occurrence AP E0→E2 | q32 coverage E0→E2 |
|---|---:|---:|---:|---:|---:|
| B7 | .1274012942 → .1268047058 | **−0.0005965885（改善 0.4683%）** | +.0017892440（退化） | .5934546325 → .5897196254（下降） | .934824 → .945341（上升） |
| B8 | .1268828708 → .1270777079 | **+.0001948372（退化 0.1536%）** | −.0004239061（改善） | .5941484641 → .5907630682（下降） | .940542 → .946324（上升） |

- B8−B7 conditional Pinball：E0 **−0.0005184234** → E2 **+0.0002730022**；交互 **+0.0007914256**。
- R>20：**717** 个像元时次；q32 覆盖 B7 **30/717**、B8 **44/717**（约 .04184/.06137）。这不是 POD、概率校准或独立事件证据；独立事件数 **NOT_ESTIMATED**，AP20[q32] **NOT_VERIFIED**。
- 由保存的 B7/B8 tail 分层求和得到 717/30/44；不是重新评价。

## 4. 限制

1. 单 seed 2029、重复使用的 2024 Development；无独立复现或跨年泛化。
2. 历史 E0 的完整数值环境指纹缺失，E0 继续条件继承；不能作严格数值环境等价声明。
3. B7 主指标改善但 Brier 退化；B8 主指标退化；AP 两者下降、q32 覆盖两者上升，方向混合，不作 DTFM 保留/移除或性能因果结论。
4. B8 checkpoint SHA/字节数只取收据与 root 直接哈希记录；本次未重读权重载荷。B7 继承同样只核保存收据/报告。
5. 本审核未重审代码、未重跑测试、未执行推理/评价/训练；科学 NOT_VERIFIED，外部 Stage 4.5 PARTIAL，研究者掌握 NOT_ASSESSED。

## 5. 结论

恢复终态的完成、更新范围、源读取、时长、E9 Train 摘要、B8 收据、B7 继承、报告身份和四格算术均一致，未发现阻断性证据错误。工程可记 **PASS_WITH_LIMITATIONS（限定终态/元数据复核）**；四格仅作单 seed 描述性结果，不能升级为科学确认。

本轮只读已保存元数据，未启动、未读取载荷、未生成批准，未改 Codex/Shared 共同决策或 main。
