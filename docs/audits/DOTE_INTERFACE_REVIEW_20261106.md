# DOTE-INTERFACE-20261106.1 / LIVE.8｜限定新增差异审核

- 审核者：Harness（独立于 Codex）
- 审核对象：新增 `dote_direction_transform.py`、对应单测试、README/STAGE/REVIEW_INDEX、LIVE.8 tex/PDF、`VERIFICATION.json`
- 范围：只审新增接口与 8 项人工合成 CPU 检查；继承既有 43 测试、14 来源、8 端点身份，不重复全量审查
- 结论：**PASS（限定接口准备；不是真实数据接入或科学执行批准）**

## 1. 文件与指纹

Codex 起点 `d7fccd21921c1050afa1dc0981a502f74775995a`，8 文件尚未提交。`VERIFICATION.json` 的 7 个 artifact 指纹全部匹配；其自身为第 8 文件。

- 新接口：`dote_direction_transform.py` **11,696 B / `F1CF44EB...E9B2`**
- 新测试：`test_dote_direction_transform.py` **10,926 B / `FCC7FB88...EF305`**
- README：20,146 B / `58162B4B...B282`
- STAGE：32,185 B / `1FDCBB07...E13E`
- REVIEW_INDEX：20,792 B / `0DC16500...F91D`
- LIVE.8 tex：41,196 B / `3E2000A3...B62F`
- LIVE.8 PDF：**16 页 / 582,954 B / `CA884067...5B37`**
- 旧 LIVE.7：**587,127 B / `1624F80A...32D8`**，原字节保留。

## 2. 实际测试

按请求使用现有 `F:\devtools\miniconda3\python.exe`、`-X utf8 -B`、`sys.path` 指向当前 `src`，仅运行新增单测试：

```text
python -X utf8 -B -m unittest -v tests.research_readiness.test_dote_direction_transform
```

结果：**Ran 8 tests, OK**；failures/errors/skips 均 0。未运行旧 43 项 suite、真实数据、模型/梯度/推理/评价/训练；未安装依赖。

八个检查覆盖：

1. manifest digest、显式 population 与 time role；
2. duplicate/missing/ambiguous/wrong-window/synthetic-2025 拒绝；
3. 已知东向坡的 O/W/L/M、真实 mask、输入不变；
4. 对比 native 旋转（错误 speed 5）与 map 后 speed 4；
5. 共享场景旋转的 call-order 独立与 RNG 不变；
6. frame identity/单位/控制参数拒绝；
7. support 变化与 float32 overflow 停止、不裁剪；
8. frame-callable 合成路径无文件打开或正式执行器注册。

## 3. 接口审查

- `SceneManifestLookup` 使用现有 `scene_records` 与 `planning.digest` 口径；要求 `manifest_sha256` 与内容 digest 相符、`accepted_ids` 非空唯一有序、scene 唯一、analysis 唯一、window_start+30min=analysis，`sample_id` 与 window_start 一致；拒绝重复/缺失/冲突/2025。显式选择 `ANALYSIS_TIME_UTC` 或 `WINDOW_START_UTC`，不从 frame 猜 ID。
- `DirectionDoteTransform` 只接受继承的 retrospective f006 `EnvironmentFrame`；先复制 frame、按实际 terrain grid 做 native/目标 grid 映射（同 identity 不插值），在原生物理 wind/PS/PWAT 身份与单位校验后取局部 u/v；在 mask 之后对局部 u/v 应用固定方向或场景旋转，再用未改 `dote_proxy`/`complete_dote` 重算 O/W/L/M。
- 保留 frame/MEE/DEM/PS/PWAT/真实 mask、通道顺序与 f006 identity；若 wind 支持、受控 proxy 支持发生任何变化则抛 `FloatingPointError`，不裁剪/过滤/恢复 post-mask；float32 转换非有限则停止。
- 默认 `dynamic_terrain.py`、`stage4/data.py`、`dote_control_candidates.py` 三源指纹均未变；未改默认 reader/PhysicalDote，未注册正式执行器；`EXPERIMENT_READY=False`。
- `integration_state` 明确：真实 manifest 未读取/绑定，正式接线/执行器、科学判据、预算/允许路径、研究者 grant 全未落实；`experiment_ready=false`；科学 NOT_VERIFIED、外部 PARTIAL、掌握 NOT_ASSESSED。

## 4. 非阻断观察

1. `DirectionDoteTransform.physical` 比较了 `controlled.valid` 与 baseline proxy 支持，但没有单独比较最终 `complete_dote` 结果支持；当前控制/PWAT/mask 不变，正常应一致，正式接入前可再加一道最终 valid 相等断言。
2. `SceneManifestLookup` 的真实 manifest 未读取/绑定；其 schema 按当前 `scene_records` 代码路径实现，但本轮只以合成 manifest 验证，不能宣称真实清单已验证。
3. 8 项测试全部是人工合成 CPU 检查；不是科学效果、真实数据或梯度证据。旧 43 项/14 来源/8 端点本轮不重跑，也不被这 8 项覆盖。
4. LIVE.8 视觉检查为执行方自检（改动页 1/14/16），本审核未逐页像素复核；首次 13.40556pt 超宽在 Git/审核前停止并修正，失败日志保留。

## 5. 结论与状态

**PASS（限定接口准备）**：新增 scene lookup 与 frame-callable DOTE 局部风接口通过 8 项合成检查；身份、time role、映射顺序、真实 mask、输入不变、支持变化停止及真实执行门控均符合请求；未发现阻断性接口错误。

- 工程：**PASS（限定接口 + 8 项合成检查；Git 以实际回执为准）**
- 科学：**NOT_VERIFIED**
- 外部 Stage 4.5：**PARTIAL**
- 研究者掌握：**NOT_ASSESSED**

本轮未读取真实清单/权重/预测/标签/气象/缓存/2025，未运行模型/梯度/推理/评价/训练，未安装依赖，未修改 Codex/Shared 共同决策/规则或 main。
