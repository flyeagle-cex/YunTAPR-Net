"""Seal only actually completed preparation; never authorizes formal FinalFit."""
from datetime import datetime,timezone
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'scripts')]
from prepare_b0_phase_b_finalfit_v1 import (read,save,sha256,preserve,BASELINE,REVIEW_ID,SCENES,PIXELS,STEPS,EPOCHS,UPDATES,TAIL_POLICY,INITIALIZATION,DECISION,PROTOCOL)
from yuntapr.training.phase_b_preparation import finalfit_lr


def main(out):
    manifest=read(out/'preparation_manifest.json')
    norm=read(out/'normalization_phaseB_finalfit_2023_2024.json')
    execution=read(out/'normalization_execution.json')
    sanity=read(out/'protocol_sanity.json');dryrun=read(out/'engineering_dryrun.json');tests=read(out/'test_summary.json')
    if not norm['ready'] or norm['eligible_scene_count']!=SCENES or norm['valid_pixel_count']!=PIXELS:
        raise ValueError('Full normalization gate not passed')
    if any(e['status']!='PASS' for e in [execution,sanity,dryrun,tests]):raise ValueError('A required gate did not pass')
    if not execution['cleanup_success'] or execution['owned_staging_files_remaining'] or not dryrun['temporary_model_optimizer_released'] or not tests['fixture_cleanup_success']:raise ValueError('Cleanup incomplete')
    if dryrun['FORMAL_OPTIMIZER_STEPS']!=0 or dryrun['checkpoint_load_calls']!=0:raise ValueError('Formal scope violation')
    preserved=preserve(out)
    status={'state':'PHASE_B_FINALFIT_PREPARATION_COMPLETED_FORMAL_TRAINING_NOT_AUTHORIZED','run_id':out.name,
        'B0_PHASE_A_ACCEPTED':True,'ACCEPT_B0_PHASE_A':True,'TRANSFER_EPOCH_BUDGET_TO_PHASE_B':11,
        'SELECTED_CHECKPOINT_EPOCH':11,'SELECTED_CHECKPOINT_VAL_CORE_LOSS':0.04730775889882134,
        'PHASE_B_FINALFIT_SCENES':SCENES,'PHASE_B_NORMALIZATION_READY':True,'PHASE_B_NORMALIZATION_PIXELS':PIXELS,
        'PHASE_B_STEPS_PER_EPOCH':STEPS,'PHASE_B_TOTAL_PLANNED_EPOCHS':EPOCHS,'PHASE_B_TOTAL_PLANNED_UPDATES':UPDATES,
        'FINALFIT_TAIL_BATCH_POLICY':TAIL_POLICY,'PHASE_B_MODEL_INITIALIZATION':INITIALIZATION,
        '2025_PIXELS_READ':0,'PHASE_B_FORMAL_TRAINING_STARTED':False,'PHASE_B_AUTHORIZED':False,
        'B1_TO_B8_AUTHORIZED':False,'FORMAL_OPTIMIZER_STEPS':0,'ENGINEERING_OPTIMIZER_STEPS':2,
        'ENGINEERING_BACKWARD_CALLS':2,'TEST_FIXTURE_ONLY':True,'TOTAL_FINAL_TESTS_EXECUTED':tests['total_tests_executed'],
        'TEST_FAILURES':sum(r['failures'] for r in tests['suites']),'TEST_ERRORS':sum(r['errors'] for r in tests['suites']),
        'TEST_SKIPS':sum(r['skipped'] for r in tests['suites']),'all_historical_artifacts_unchanged':True,
        'fresh_initialization_reproducible':True,'checkpoint_load_calls':0,'owned_staging_files_remaining':0,
        'temporary_fixture_cleanup_success':True,'completed_utc':datetime.now(timezone.utc).isoformat()}
    if (out/'final_status.json').exists():
        prior=read(out/'final_status.json')
        if any(prior.get(k)!=v for k,v in status.items() if k!='completed_utc'):
            raise ValueError('Existing final status differs from actual preparation gates')
        status=prior
    statistic_table='\n'.join(f'| {k} | {norm[k]:.15g} |' for k in ['mean_K','std_K','min_K','p1_K','q1_K','median_K','q3_K','p99_K','max_K','IQR_K'])
    suite_table='\n'.join(f'| {r["suite"]} | {r["executed"]} | {r["failures"]} | {r["errors"]} | {r["skipped"]} |' for r in tests['suites'])
    batch_table='\n'.join(f'| {b["batch_size"]} | {b["valid_denominator"]} | {b["loss"]:.12g} | {b["LR"]:.12g} | {b["pre_clip_norm"]:.12g} | {b["post_clip_norm"]:.12g} |' for b in dryrun['batches'])
    report=f'''# B0 Phase-A acceptance + Phase-B FinalFit preparation closure v1

研究者已接受 B0 Phase-A 作为 **CONTROL / BASELINE**，不是最终 YunTAPR-Net。本 run 只完成 preparation，`PHASE_B_AUTHORIZED=false`，`PHASE_B_FORMAL_TRAINING_STARTED=false`。真实工程 dry-run 的两个临时更新不属于正式训练；完成后停止。

## 1. 权威与历史身份

Baseline/Scientific Review commit：`{BASELINE}`；Scientific Review run：`{REVIEW_ID}`；本 run：`{out.name}`。
独立 acceptance 文件为 `docs/researcher_decisions/B0_PHASE_A_ACCEPTANCE_v1.md` 和 `config/decisions/b0_phase_a_acceptance_v1.yaml`。
`ACCEPT_B0_PHASE_A=true`，`B0_PHASE_A_ACCEPTED=true`；选定 epoch=11、Val core=0.04730775889882134。
BEST SHA256：`{manifest['formal_best']['sha256']}`；大小={manifest['formal_best']['bytes']} bytes。仅只读 identity hash，没有 torch.load 或 state 应用。
Protocol、Scientific Freeze、Phase-A normalization、Train/Validation manifests、SP04、Yunnan mask 的路径和 SHA 均绑定在 acceptance YAML，preparation manifest 和 historical preservation 中。
本轮再次检查全部 {preserved['files_checked']} 个 baseline 文件，完整 review、早前 H 阻塞 run、输出路径失败 run、正式 training run 和冻结 artifacts 全部保持原始 bytes。历史 review 的 UNDECIDED 状态保留；本独立研究者决定更新当前执行状态。

## 2. FinalFit population 与排序

独立 `phase_b_finalfit_manifest.csv` 含 23,447 个唯一身份：2023 March–October eligible Train=11,720，2024 March–October eligible Validation=11,727；2025=0。
清单来源是两份已冻结 manifest 与已冻结 formal source SHA ledger/eligibility/pairing。逐项比对路径、source role、时间、full-valid eligibility、bytes/SHA、IMERG V07 Final product 与 index；没有重新筛样本、partial/rejected scene、older fallback 或其它月份/product。
固定排序：UTC window_start 升序，再 sample_id、source_role；finalfit_index 从0开始。原 Train/Validation role 与原 index 单独保留，并统一标记当前 role=FinalFit。2024 此阶段成为训练 population，不再被视作独立的 FinalFit Validation 控制信号。
清单 SHA256：`{manifest['finalfit_manifest_sha256']}`。

## 3. 全量 FinalFit normalization

真正重读全部 23,447 原始 B13 文件：每场 501×501 full-valid native pixels，总计 **5,885,220,447**，与精确期望相等。
每文件经只读原始 H source → bounded English staging → size/source+copy SHA → 坐标/因果时间/full-valid QC → native pixel decode；不翻转、不插值、不重采样、不将缺测记0。
完整 int16 packed-code histogram 使用 runtime 相同 float32 scale/add_offset 解码后提升 float64；population mean/std，ddof=0；quantiles 为完整群体的 type-7/linear rank interpolation，无抽样、无 rounding/rebinning。
独立 merged per-frame float64 central moments 与 histogram mean/std 的差值分别为 {abs(norm['mean_K']-norm['streaming_mean_K']):.15g} K、{abs(norm['std_K']-norm['streaming_std_K']):.15g} K，均小于1e-9 K。Phase-A 常数未复用。

| Statistic | Kelvin |
|---|---|
{statistic_table}

Normalization artifact：`normalization_phaseB_finalfit_2023_2024.json`，SHA256=`{sha256(out/'normalization_phaseB_finalfit_2023_2024.json')}`。
完整逐场 read ledger 和 packed-code histogram 保存在该 run 的 F private directory；公开 `normalization_execution.json` 记录其 absolute path/bytes/SHA。实际读取2023/2024像元，2025_PIXELS_READ=0。
同时验证 {execution['imerg_days_identity_verified']} 个所需 IMERG daily 文件的冻结 SHA 与正/稳定 size；norm fit 仅使用 native B13，不使用任何 target statistics。

## 4. Fresh initialization、尾批与预算

`PHASE_B_MODEL_INITIALIZATION=FRESH_SEED_2026`。两次独立 fresh B0Model 初始化逻辑状态 SHA 一致：`{sanity['initial_model_state_sha256']}`。torch.load 被禁止，实际调用0；没有应用 epoch_011、Phase-A optimizer 或 scheduler state。
保持冻结 backbone/head/loss/AdamW参数组/BF16/FP64 quantiles/clip5 与 seed，未修改 alpha/gamma/LR 或 science/protocol artifacts。
`FINALFIT_EPOCHS=11`；early stopping=false，validation-triggered scheduler=false，不根据2025或后续表现重新选epoch。
physical batch=2、drop_last=false；前11,723批各2场，最后singleton1场：11,723×2+1=23,447。尾批不丢弃、不复制、不padding、不replacement，实际有效batch为1、accumulation=1。
全11个计划epoch均验证各身份恰好出现一次；epoch0用独立 torch.Generator seed2026，后续seed=2026+zero_based_epoch_index。epoch1 permutation 和真实dry-run选样在读取前登记。
tail loss沿用 actual batch 中全部 valid Yunnan supervised pixels 的分母，绝不固定除以2；quantile轴仍32分位均值。

## 5. Scheduler 数值推导与精确 replay

steps_per_epoch=ceil(23,447/2)=11,724，W=11,724，U=50×11,724=586,200。
base_lr=1e-4、min_lr=1e-6；1 epoch warmup + 50 epoch cosine horizon；计划实际11 epoch，总更新128,964。
warmup lr(u)=base_lr×(u/W)，随后 min_lr+(base_lr−min_lr)×(1+cos(pi×(u−W)/(U−W)))/2；在step前设置，update一基。
warmup允许低于min_lr，cosine阶段才要求min_lr下界。首步={finalfit_lr(1):.17g}，W={finalfit_lr(STEPS):.17g}，U={finalfit_lr(50*STEPS):.17g}，计划最后update={finalfit_lr(UPDATES):.17g}。
检查全部586,200个LR数值、warmup严格递增/cosine非递增和边界范围。A/B在200个共同quarter-epoch进度点（覆盖50-epoch horizon）float.hex完全一致，包含1/11/50 epoch端点；不是把cosine压缩成11 epoch，也没有用A的W=5860。
本数值sweep optimizer steps=0；不是正式训练。

## 6. 独立真实 ENGINEERING_ONLY dry-run

选样规则先登记：seed2026 epoch1 permutation 的首个batch2和最后singleton，三种身份没有按照降水或模型误差挑选。
用新的 PhaseBNormalizer 读取真实 H B13 + IMERG V07 Final；逐样本 source SHA、时间因果、full-valid、frozen supervised/rainy counts 均通过。
临时fresh seed2026 model和临时fresh AdamW完成各batch的forward/loss/backward/clip/step。参考loss按独立逐像元公式核验 actual valid-pixel denominator，occ tolerance1e-7、FP64 quantile tolerance1e-12。

| Batch size | Valid denominator | Core loss | LR | Preclip norm | Postclip norm |
|---|---|---|---|---|---|
{batch_table}

ENGINEERING_OPTIMIZER_STEPS=2、ENGINEERING_BACKWARD_CALLS=2；FORMAL_OPTIMIZER_STEPS=0。所有checkpoints load calls=0，不产生checkpoint binary。
temporary model/optimizer 已释放，owned staging已清理。详细dtype、数值、source audit和GPU memory见engineering_dryrun.json。没有正式11 epoch loop或新的模型交付。

## 7. Tests 与清理

最终实际执行 {tests['total_tests_executed']} 项：existing={tests['existing_171_executed']}，scientific-review={tests['scientific_review_tests']}，new preparation={tests['new_preparation_tests']}；failures/errors/skips均0。
测试fixture独立临时目录，temporary optimizer/backward/step仅TEST_FIXTURE_ONLY。原始数据与正式checkpoint tensors禁止作为fixture；artifact阶段仅允许BEST只读SHA。临时目录清理成功，正式BEST与所有baseline artifacts前后不变。测试不计入两个real engineering steps，更不计入formal steps。

| Suite | Executed | Failures | Errors | Skips |
|---|---|---|---|---|
{suite_table}

前置开发中12项测试的scheduler测试循环范围曾越过50 epoch；随后修正测试范围并全部通过，冻结scheduler未改。init的Path参数适配错误也在写入acceptance/run前修正，未改任何历史文件。此类调试与最终suite结果分开记录在implementation_gate_notes.json。

## 8. Staging I/O 与发布边界

normalization wall={execution['wall_seconds']:.3f}s；copy workload sum={execution['copy_seconds_sum']:.3f}s；read/QC/statistics context sum={execution['read_seconds_sum']:.3f}s；peak单文件temporary bytes={execution['peak_temporary_bytes']}。
本fit单进程、一次一个H文件，cap=734,003,200 bytes；source/copy SHA额外I/O不包含在copy计时，read计时包含QC与本场statistics。每文件size/SHA一致后仅删除本流程创建的UUID staging copy；H原始文件永久只读，既有diagnostic cache不删除。
不安装或升级环境包；运行python、torch、CUDA、GPU和包版本写在environment.json。
Git仅发布代码、测试、CSV/JSON/YAML、acceptance和report；不上传model/optimizer binary、raw、cache、venv或wheel。read ledger/histogram/permutation在F盘，仅公开identity。

## 9. 限制保留与最终授权

B0仍是single latest causal B13 control；没有multitemporal/multichannel/GFS/DEM/DOTE/DTFM/MEE/ERA5 teacher。接受B0不证明完整YunTAPR-Net，不排除已观察到的Validation degradation、低tau calibration deviation、月度/空间差异和强雨样本稀疏。设计信息限制不作为已证实物理误差原因。
Phase-A limitation inventory和Scientific Review全部原样保留，接受不会事后改BEST metric或science artifacts。
`B0_PHASE_A_ACCEPTED=true`；`TRANSFER_EPOCH_BUDGET_TO_PHASE_B=11`；`PHASE_B_NORMALIZATION_READY=true`。
`PHASE_B_AUTHORIZED=false`；`PHASE_B_FORMAL_TRAINING_STARTED=false`；2025_PIXELS_READ=0。正式FinalFit仍需独立研究者授权，完成本轮后STOP。
'''
    with (out/'PHASE_B_FINALFIT_PREPARATION_CLOSURE_REPORT.md').open('x',encoding='utf-8',newline='\n') as f:f.write(report)
    if not (out/'final_status.json').exists():save(out/'final_status.json',status)
    save(out/'completion_manifest.json',{'baseline_commit':BASELINE,'run_id':out.name,'status':status,'historical_preservation':preserved,
        'acceptance_sha256':sha256(DECISION),'phase_b_preparation_protocol_sha256':sha256(PROTOCOL),
        'code_sha256':{p.relative_to(ROOT).as_posix():sha256(p) for p in [ROOT/'scripts/prepare_b0_phase_b_finalfit_v1.py',ROOT/'scripts/validate_b0_phase_b_preparation_v1.py',ROOT/'scripts/test_b0_phase_b_preparation_v1.py',Path(__file__),ROOT/'src/yuntapr/training/phase_b_preparation.py',ROOT/'tests/phase_b_preparation/test_preparation.py']}})
    save(out/'artifact_sha256.json',{p.relative_to(out).as_posix():{'bytes':p.stat().st_size,'sha256':sha256(p)} for p in sorted(out.rglob('*')) if p.is_file() and p.name!='artifact_sha256.json'})
    readme=ROOT/'docs/phase_b_finalfit_preparation/README.md'
    with readme.open('x',encoding='utf-8',newline='\n') as f:
        f.write(f'# Phase-B FinalFit preparation\n\nCurrent run: `{out.name}`. Researcher accepts Phase-A as CONTROL / BASELINE and selects an 11-epoch budget. Full FinalFit normalization and protocol gates pass.\n\n[Closure report](runs/{out.name}/PHASE_B_FINALFIT_PREPARATION_CLOSURE_REPORT.md) · [Final status](runs/{out.name}/final_status.json).\n\n23,447 scenes, 5,885,220,447 native full-valid B13 pixels, fresh seed2026, batch2 plus singleton without drop/duplicate, 11,724 updates/epoch, 128,964 planned updates on the unchanged 50-epoch LR horizon. Two real ENGINEERING_ONLY updates and {tests["total_tests_executed"]} final tests passed.\n\n`PHASE_B_AUTHORIZED=false`; formal FinalFit has not started. Historical review/training/science remain unchanged. No formal training entrypoint is introduced.\n')
    print(json.dumps(status),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run-dir',type=Path,required=True)
    main(parser.parse_args().run_dir.resolve())
