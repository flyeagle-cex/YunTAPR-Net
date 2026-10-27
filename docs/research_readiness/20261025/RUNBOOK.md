# B2本次运行已完成

2026-10-27最新：b251fd9/36fc5dfb纠正启动已明确获批并单次执行，B5真实更新从1开始，B6自动串行等待。见[真实启动收据](evidence/b5_b6_corrected_start_launch.json)。原失败及纠正批准均已消费，**不要重复任何execute入口，不要重启**；当前包43,187秒/8,640更新，累计源读取预算包括旧62,828字节。完成后执行器自动生成static_paired_summary.json；本机页面只读展示，不控制训练。

2026-10-27最新：d696fe2首次已获批调度，在第一遍气象读取前因旧ReaderFactory臂白名单拒绝B5而停止，0更新、62,828字节静态读取，B6未启动。**不要重跑原execute；原批准已消费、额外重试0。** 读取臂已最小修复，唯一待批准[修正启动提案](evidence/b5_b6_corrected_start_proposal.json)新目录未创建。累计只增加62,828字节/1次静态读取，13秒已从原时间扣除；新包43,187秒，8640更新不增加。详见[B5/B6报告](B5_B6_READINESS_REPORT.md)。原准备和命令保留历史时点。

2026-10-27 B5/B6状态：B0–B4限定基线已交接，真实DEM候选与真实缓存零更新检查通过。正式两模型训练**NOT_STARTED_WAITING_REQUIRED_APPROVAL**；新[集中协议与精确预算](B5_B6_READINESS_REPORT.md)和[机器可执行提案](evidence/b5_b6_training_proposal.json)已就绪，提案SHA为`41add1c3bbd851bbaa5076b3edaf795d065bdc4f73ef1c104d1e3887cf20e6c3`。本机false批准模板已实测在GPU、输出目录及优化器之前拒绝，未创建正式训练目录。

唯一新增正式入口（**尚未执行；须先取得本提案、最终执行commit、科学选择及精确预算的明确批准**）：

```powershell
python -B tools/research_readiness/start_static_pair.py execute --proposal docs/research_readiness/20261025/evidence/b5_b6_training_proposal.json --private-preparation PRIVATE_PREPARATION_JSON --researcher-approval EXPLICIT_RESEARCHER_APPROVAL_JSON
```

执行时沿用已有经过验证的底层Python3.12.14＋现有CUDA依赖路径及CREATE_NO_WINDOW，在最终commit独立固定副本运行；私有JSON用绝对路径传入，不复制原B2/B3/B4批准。依次B5/2029→B6/2029，每模型4,320更新、6小时，合计8,640更新、955,143,657,680源字节、285,626读取实例、12小时，初始48GiB/每任务24GiB，replay=0。获批后只做原启动绑定/资源入场，不循环审查。下方旧实验命令均保留历史，不可重用。

最新完成（2026-10-27）：B3/B4 seed2029、2030、2031的三组固定E9配对训练与2024 Dev评价全部完成；四个新增模型均为COMPLETE_TRAIN_AND_DEV_EVALUATION。943da95恢复包在北京时间00:27封口，390次必要重放已计费，无额外重试。总体Brier/AUROC/AP/条件Pinball三seed均改善；q32方向不一致，强雨仍有退化。总体科学验收继续IN_PROGRESS，2025继续冻结。 见[三seed完成与配对收据](evidence/b3_b4_three_seed_completion.json)。原execute与execute-recovery批准均已消费，禁止重复启动；仅保留只读页面与历史原件。

运行B2_s2029_formal_20261025_v1已经完成九轮、4,320更新及2024 Dev评价。原单次批准已执行完毕，replay额度为0；不要重复执行启动命令、复用授权或覆盖原运行目录。

科学协议固定于52060ce，实际训练执行提交为a35302186b4b5d3d7ec735885a8d93762e6d3567。权重和原始数据继续保留本机；当前只读进度页面已识别完成。

- [B2/B3固定第九轮报告](B2_TRAINING_AND_EVALUATION_REPORT.md)
- [完成与配对证据](evidence/b2_completion_and_paired_evidence.json)
- [阶段验收](B0_B4_STAGE_ACCEPTANCE.md)

本次并不授权B3/B4新seed、B5–B8、额外推理或2025最终测试。后续实验按既有计划由研究者另行决定。

## B3/B4四模型包：已停止，禁止重启（2026-10-26）

12:20:51：B3 seed2030已完成九轮，B4 seed2030在870更新处因window-CLOSE原生中止；两个seed2031任务未启动。见[停止收据](evidence/b3_b4_multiseed_stop.json)。B4仅E1/480更新检查点，390更新未保存，从E1恢复涉及重放，原replay=0不授权此操作。子进程控制台隔离已修复并测试，该停止核查时点不执行恢复；其后独立限额批准已用于完成恢复，不复用原批准、不重训已完成B3。以下启动描述保留历史时点。

研究者已明确批准整包，执行代码固定在52a8e90的独立副本。首个B3 seed2030已执行真实更新，后三任务串行等待；[启动收据](evidence/b3_b4_multiseed_launch.json)记录了有时间戳的首次快照，不是实时计数。正式目录已存在且授权已消费，禁止重新运行下面入口。只读页面使用原监测器的 `--campaign` 模式，私有网址和快捷方式保留本机，交给研究者自行查看，不持续聊天轮询。以下准备描述保留其原时点，原提案不改写。

独立入口 `tools/research_readiness/start_multiseed.py` 已准备。固定 B3/2030→B4/2030→B3/2031→B4/2031，完整预算17,280更新、1,910,286,564,048逻辑源字节、每模型6小时/串行24小时、零重放。启动需要[冻结提案](evidence/b3_b4_multiseed_proposal.json)、本机私有准备、与实际执行Git commit完全绑定的研究者批准；本次真实批准文件仅保留本机，已用于启动，不得复制其批准开展第二次执行。

本次已调用[多seed方案](B3_B4_MULTI_SEED_PLAN.md)中的单条 execute 命令，不要重跑。它使用现有CUDA Python环境、研究者确认的新输出目录并检查96GiB初始空闲；四个子目录独立、不覆盖历史模型。包目录存在即拒绝再次执行，失败不自动恢复或重放。源载荷只由原计量读取器打开；2025不在源范围内。每模型完整九轮收据及SHA到齐才标记完成，所有模型完成后输出三seed描述性汇总。不得拿B2或历史恢复授权替代本包批准。

## B7/B8候选启动入口（待明确批准）

审批绑定[核心创新协议](B7_B8_INNOVATION_PROTOCOL.md)及新提案，旧B0–B6授权不适用。使用研究者最终批准的准确Git提交建立独立、干净的执行副本；模型工作目录在已确认科研存储父目录下全新且互不覆盖。使用实际Python解释器，避免Windows虚拟环境重定向中间进程破坏父进程身份。GPU/依赖路径只保留本地。

```powershell
& $ResearchPython -B tools/research_readiness/start_dynamic_pair.py execute --proposal docs/research_readiness/20261025/evidence/b7_b8_training_proposal.json --private-preparation $PrivatePreparation --researcher-approval $ResearcherApproval
```

三个本地变量分别是实际解释器、私有定位JSON和研究者批准JSON；不是允许自行填写批准的模板。入口会核对Git、源码、科学参数、共同人口和预算绑定，B7→B8串行、失败即停、零重放。未批准时不运行execute；prepare只读元数据、不创建训练输出。九轮LAST与同次2024 Dev形成innovation_paired_summary.json，不新增评估推理，不解封2025。
