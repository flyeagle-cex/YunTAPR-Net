"""Finalize the executed smoke evidence; no model/data processing in reporting."""
from pathlib import Path
import csv,json
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import xml.etree.ElementTree as ET

def finalize_report(g,run):
 r=g.load(run,'B0_SMOKE/execution_results.json');cfg=g.load(run,'smoke_config.json')
 reader=g.load(run,'B0_SMOKE/reader_actual_metadata.json');first=reader['0'];align=first['alignment'];b13=first['b13'];label=first['imerg']
 meta=g.load(run,'B0_SMOKE/smoke_sample_metadata.json');metrics=g.load(run,'B0_SMOKE/diagnostic_metrics.json')
 ck=g.load(run,'B0_SMOKE/checkpoint_reload_check.json');env=g.load(run,'logs/environment.json');cache=g.load(run,'logs/staging_summary.json')
 steps=g.csvrows(run/'B0_SMOKE/step_log.csv');loads=g.load(run,'B0_SMOKE/dataloader_check.json')
 tree=ET.parse(run/'tests/pytest_final.xml');suites=list(tree.getroot().iter('testsuite'))
 tests={k:sum(int(s.get(k,0)) for s in suites) for k in ['tests','failures','errors','skipped']}
 unit_tests=sum(int(s.get('tests',0)) for s in ET.parse(run/'tests/pytest_unit.xml').getroot().iter('testsuite'))
 assert tests['tests']>=30 and tests['failures']==tests['errors']==tests['skipped']==0
 raw=g.check_snapshot(g.load(run,'logs/raw_inputs_before.json'));old=g.check_snapshot(g.load(run,'logs/old_evidence_before.json'))
 assert g.ok_integrity(raw) and g.ok_integrity(old)
 deps=g.packages();assert deps==g.load(run,'logs/packages_before.json')
 g.wjson(run,'logs/packages_after.json',deps)
 g.wjson(run,'logs/final_integrity.json',dict(raw_file_count=len(raw),old_evidence_file_count=len(old),raw_checks=raw,old_evidence_checks=old,all_registered_raw_unchanged=True,all_registered_old_evidence_unchanged=True,raw_write_operations=0,old_run_write_operations=0,dependencies_changed=False,scope='All 17 selected raw source files and all registered Stage-0 inputs checked by size, mtime_ns and SHA256; no full-library claim.'))
 g.write(run,'B0_SMOKE/himawari_b13_reader_report.md',f'''# Himawari B13 reader smoke

状态 PASS。读取 16 个真实 B13 源文件，推理阶段另对前 4 个再次读取。主 smoke 未用 synthetic observations。

变量 `{b13['variable']}`；packed dtype `{b13['packed_dtype']}`；decoded dtype `{b13['decoded_dtype']}`；shape `{b13['original_shape']}`；dimensions `{b13['dimensions']}`；units `{b13['attrs']['units']}`。

本批文件没有显式 `_FillValue`；`missing_value={b13['attrs']['missing_value']}`。实际 scale_factor={b13['attrs']['scale_factor']}、add_offset={b13['attrs']['add_offset']}、valid_min={b13['attrs']['valid_min']}、valid_max={b13['attrs']['valid_max']}。原 metadata 每样本完整保存在 reader_actual_metadata.json，不把实际 float32 存储常数替换成十进制近似值。

复用 Stage-0 `read_himawari.py` 的 decode_packed 和 _time 原函数 AST；快照和原脚本 hash 见 logs/reader_reuse.json。仅增加 tbb_13 变量选择/维度检查封装，不调用七通道读入函数，不加载其他通道。旧 task runner/config 不执行。IMERG 同样复用 P0 decode_values 的原函数体。

valid mask 在 packed domain 排除 sentinel/非有限/超 metadata 范围，再排除解码非有限值；invalid 保留 NaN。原纬度 descending 原样读取。固定坐标 gather 在空间接口中显式记录，不在 reader 内 flip。

16 个实际 crop 输入均 1024/1024 有效；这是本小样本事实，不是全月科学 QC 结论。为避免在 smoke 引入填补规则，本轮模型只接受完全有效输入 crop；遇到不满足的样本须拒绝并记录，不填零。该 eligibility 条件不是正式科研样本剔除政策。本轮未因此拒绝任何已选 raw 样本。
''')
 g.write(run,'B0_SMOKE/spatial_alignment_smoke_report.md',f'''# Spatial alignment smoke

**ENGINEERING_SMOKE_CROP_ONLY / PROVISIONAL_SMOKE_ALIGNMENT**。

输入原 shape={align['original_shape']}，源纬度 {align['original_lat_range']}（descending）、经度 {align['original_lon_range']}（ascending）。原 IMERG daily field={label['original_shape']}，真实 target lat/lon 为冻结的 130×140 coordinate anchor，逐值检查通过。

Crop 使用真实 IMERG coordinate 数组的 Python slices lat[44:76]、lon[54:86]，shape=32×32。未用 np.arange 构造坐标。经纬范围为 lat={align['output_lat_range']}、lon={align['output_lon_range']}，输出 lat/lon ascending。这些范围只描述本轮工程 crop，不是正式 model_input_bbox；model_input_bbox 与 context margin 仍 NOT_YET_FROZEN。

方法：对每个真实 target 中心，按绝对坐标差分别找到源 latitude/longitude 的最近索引，然后 np.ix_ gather。无平均、平滑、双线性插值或域外外推；若距离相等，NumPy argmin 取第一个源索引，未将其定为科学 tie rule。最大实际 latitude 偏移={align['max_abs_lat_offset_degrees']}°，longitude 偏移={align['max_abs_lon_offset_degrees']}°。

源行索引从 {align['source_row_indices'][0]} 到 {align['source_row_indices'][-1]}，明确将 descending 源坐标取样到 ascending target 坐标；这不是未记录的 flip。全部索引与每个样本原始/输出坐标范围见 reader_actual_metadata.json。

Missing handling：同索引 gather 原 valid mask；invalid 仍 NaN，不做最近有效像元搜索、不插值、不当 0。IMERG label 仅原数组 crop，不作空间重采样。真实 selected crop 均全有效；合成单元测试另覆盖 missing 与方向。

冻结云南主评价 mask（GADM4.1 CHN.30_1、center-in-polygon、3430 cells）只做只读 hash 保护，未生成/修改。训练 loss 和 diagnostic metric 在本小 crop 的 target-valid pixels 上计算，不宣称完整云南主评价。intersection comparison 未改角色。
''')
 g.write(run,'B0_SMOKE/tensor_contract.md',f'''# Tensor contract {cfg['sample_contract_version']}

- Dataset item x/y: [1,32,32]，float32；显式第 0 维 channel=1。
- DataLoader x/y: [B,1,32,32]，float32，B=1 或 4；axes=batch/channel/height(latitude)/width(longitude)。
- input_valid_mask/target_valid_mask 与对应 tensor 同 shape，torch.bool。
- x 在 Dataset 中保留 K；y 保留 mm hr-1。missing 保留 NaN，不转换为有效 0。真实模型输入要求全部有效且有限；目标 loss 使用 bool mask。
- 模型内部固定 x/300 仅是 ENGINEERING_SMOKE_ONLY 数值 conditioning；没有从数据拟合 mean/std、log1p 或其他归一化统计；不是正式 normalization 规范。
- channel axis 通过显式 x[None]/y[None] 添加；batch 通过 stack 添加。没有无记录 squeeze/unsqueeze，没有七通道或六时相合并。
- metadata 为每样本 dict，包含 source paths、source times、candidate analysis、causality_pass、mapping_status；DataLoader 使用自定义 collate 保持 metadata list。

所有输出 target coordinate 对应 frozen actual IMERG 数组的上述 slice。scope=ENGINEERING_SMOKE_CROP_ONLY。
''')
 g.write(run,'B0_SMOKE/loss_contract.md','''# Smoke loss contract

masked MSE = mean((prediction[valid] − target[valid])²)，valid=target_valid_mask。

先以 mask 索引，再减法/平方；不能用 NaN residual 乘 0 代替排除。valid subset 必须有限且非空。0 rain 为有效 target，明确进入 loss 和 metric；不按降水阈值筛像元。单位为 (mm hr-1)²；target 无 log1p 或其他变换。

仅用于 backward/optimizer 工程检查，不是论文正式 loss 冻结。单元测试包含 masked NaN、不参与梯度的 invalid 像元、0 rain 有效与全 invalid 拒绝。
''')
 g.write(run,'B0_SMOKE/time_mapping_smoke_report.md',f'''# Offline time mapping smoke

研究者在本轮明确批准候选用于工程 smoke（PROVENANCE/researcher_time_mapping_approval.md）。IMERG converted CF coordinate=T；candidate_analysis_time=T+30min；selected_himawari_nominal_time=analysis_time−10min。只取该 exact slot，不以未来帧替代。

16 个样本均从真实文件重读时间，核对旧 P0 metadata，并强制 obs_end<=analysis_time；future 帧或扫描结束晚于 analysis_time 立即拒绝。date_created 原值记录；不要求 date_created<=analysis_time，不据此声称真实时刻可获取。未使用 Himawari availability 或 GFS vintage。

每个实际样本保存 imerg_converted_time、candidate_analysis_time、selected_himawari_nominal_time、obs_start、obs_end、date_created、causality_pass 和 mapping_status=ENGINEERING_SMOKE_TIME_MAPPING_ONLY。还保留原接口别名 imerg_target_time、analysis_time、nominal_time。CSV/JSON 记录 UTC 与来源路径。

本轮没有把 T 定义为 native precipitation window start，也没有声称 [T,T+30min) 为科学标签区间。B0 formal 不能沿用此候选作为正式规则，除非后续获得科学证据及显式批准。

{g.TIME_LIMIT}
''')
 model=g.B0SmokeUNet(cfg['model_width'])
 g.write(run,'B0_SMOKE/model_summary.txt','ENGINEERING_SMOKE_MODEL; NOT FORMAL ARCHITECTURE\n'+str(model)+f"\nTrainable parameters: {r['parameter_count']}\nInput: B13 single time, 1 channel. Output: 1 nonnegative precipitation field via Softplus.\n")
 perf=dict(scope='SMOKE PERFORMANCE DIAGNOSTIC; NOT FORMAL BENCHMARK',batch_loading=loads,mean_forward_seconds=float(np.mean([float(x['forward_seconds']) for x in steps])),mean_backward_seconds=float(np.mean([float(x['backward_seconds']) for x in steps])),mean_optimizer_seconds=float(np.mean([float(x['optimizer_seconds']) for x in steps])),peak_gpu_allocated_bytes=r['peak_gpu_allocated_bytes'],peak_gpu_memory_status=r['peak_gpu_memory_status'],data_cache='Tiny aligned tensor cache inside this smoke Dataset; first accesses read original files through one-file staging; inference forces reread.',timing_limits='copy/read intervals exclude SHA verification, process import/startup and integrity hashing. Not end-to-end wall time; warmed local filesystem possible.')
 g.wjson(run,'B0_SMOKE/performance_diagnostic.json',perf)
 blockers=g.load(g.GATE,'DECISIONS/gate_assessment.json')['decisions']
 blocked=[x for x in blockers if x['blocks_formal']]
 g.write(run,'B0_FORMAL_EXPERIMENT_HOLD.md','# Formal B0 remains NOT_READY\n\n本轮只取得真实数据工程闭环 PASS；未解除 Stage-0 科学 gate。尤其本轮时间候选使用授权并非 D02/D08 正式批准。\n\n'+'\n'.join('- '+x['id']+'：'+x['decision']+'。证据/依赖沿用 '+str(g.GATE/'RESEARCHER_DECISIONS_REQUIRED.md') for x in blocked)+'\n\nGFS/DEM 不作为 B0 输入，因此其 future-stage 决策未被强加为本轮 smoke blocker。\n')
 status={**r,'engineering_status':'PASS','b0_engineering_smoke_gate':'PASS','pytest_pass':True,'tests':tests,'formal_b0_status':'NOT_READY','model_input_bbox_frozen':False,'scientific_time_mapping_frozen':False,'time_mapping_status':'ENGINEERING_SMOKE_TIME_MAPPING_ONLY','spatial_alignment_status':'PROVISIONAL_SMOKE_ALIGNMENT','formal_normalization_statistics_generated':False,'train_validation_test_split_executed':False,'old_stage0_conventions_modified':False,'dependencies_changed':False,'automatic_next_stage':False,'completed_utc':g.utc()}
 g.wjson(run,'b0_smoke_status.json',status)
 g.write(run,'README.md',f'''# B0 offline engineering smoke

入口：FINAL_B0_ENGINEERING_SMOKE_REPORT.md；机器状态：b0_smoke_status.json。独立 run `{run}`。工程源码在 src，pytest 在 tests，真实小样本追溯表/读取 metadata/梯度/checkpoint/诊断在 B0_SMOKE。

使用固定 Python `{g.PYTHON}`。代码可在新 run 重现；命令顺序如下（prepare 返回新路径，用它替换 NEW_RUN）：

```powershell
& 'F:\\pytorch\\Research\\.venv\\Scripts\\python.exe' 'src/scripts/run_b0_smoke.py' prepare
& 'F:\\pytorch\\Research\\.venv\\Scripts\\python.exe' 'NEW_RUN/src/scripts/run_b0_smoke.py' unit --run 'NEW_RUN'
& 'F:\\pytorch\\Research\\.venv\\Scripts\\python.exe' 'NEW_RUN/src/scripts/run_b0_smoke.py' execute --run 'NEW_RUN'
& 'F:\\pytorch\\Research\\.venv\\Scripts\\python.exe' 'NEW_RUN/src/scripts/run_b0_smoke.py' final_tests --run 'NEW_RUN'
& 'F:\\pytorch\\Research\\.venv\\Scripts\\python.exe' 'NEW_RUN/src/scripts/run_b0_smoke.py' finalize --run 'NEW_RUN'
```

只有明确授权时才开始另一轮。写文件使用独占创建；不能原路径覆盖执行。单位/时间/missing 合约见 B0_SMOKE 的独立说明。模型调用仅接受 B13 一帧；不导入 GFS/DEM/ERA5/DOTE/DTFM/MEE。七通道旧源码仅用于提取既有纯解码函数，其他通道数组未读取。pyarrow CSV/Parquet 双格式保持表格原字符串表示，JSON 保存类型化记录。

checkpoint 为 SMOKE CHECKPOINT / NOT SCIENTIFIC CHECKPOINT。诊断使用参与过 smoke updates 的 4 个真实样本，不是 held-out validation/test。没有论文图表或科研结论。下一阶段不自动启动。
''')
 report=f'''# Final B0 Engineering Smoke Report

**B0 ENGINEERING SMOKE: PASS**。**B0 FORMAL EXPERIMENT: NOT_READY / HOLD**。

独立 run：`{run}`。本轮是 offline engineering smoke，真实数据闭环已执行；没有科研实验许可升级。

## 1. Engineering status

PASS：真实文件 → B13 / IMERG reader → 候选时间配对 → 显式空间接口 → Tensor → B0SmokeDataset → DataLoader → small U-Net → forward → masked MSE → backward → optimizer → checkpoint save/reload → inference → diagnostic metric 全部真实执行。

## 2. Sample count

{r['sample_count']} 个真实样本。按已有 2024-07 P0 审计时间表选择首 16 个 exact nominal 候选，不按雨量挑选，不扫描全库。未以虚构数据替代主 smoke。

## 3. Sample date range

IMERG converted coordinate：{r['sample_date_range'][0]} 至 {r['sample_date_range'][1]}；candidate analysis_time 从 {meta[0]['candidate_analysis_time']} 至 {meta[-1]['candidate_analysis_time']}。不是 native half-hour window 宣告。

## 4. Real Himawari files

{r['unique_himawari_files']} 个文件；首 `{meta[0]['himawari_path']}`，末 `{meta[-1]['himawari_path']}`。逐条路径、时间和因果检查见 B0_SMOKE/smoke_sample_manifest.csv 与 JSON；17 个 raw 的原始 SHA 在 logs/raw_inputs_before.json。推理对前 4 个真实源重新读取。

## 5. Real IMERG files

{r['unique_imerg_files']} 个 daily file：`{meta[0]['imerg_path']}`，使用相应 16 个真实 converted coordinate 的 precipitation 切片；目标 units=mm hr-1，0 rain 有效。未读取 QI 作为 predictor。

## 6. B13 variable mapping

`tbb_13`；packed int16 → float32 K；shape 501×501；missing_value=-32768，无单独 _FillValue。复用原 Stage-0 decode_packed/_time 函数体，单变量封装；没有读七通道 tensor。详见 himawari_b13_reader_report.md、reader_actual_metadata.json、reader_reuse.json。

## 7. Time pairing

研究者本轮明确批准 ENGINEERING_SMOKE_TIME_MAPPING_ONLY：T 为 converted CF coordinate，analysis_time=T+30min，nominal=analysis_time−10min。每个实际文件重读 obs_start/obs_end/date_created，强制 obs_end<=analysis_time；本 16 个均通过。future 样本拒绝测试也已执行。date_created 仅记录，不作为 operational availability。native exact window 和正式跨源绑定未冻结。

{g.TIME_LIMIT}

## 8. Spatial smoke alignment

PROVISIONAL_SMOKE_ALIGNMENT：以真实 IMERG lat[44:76]/lon[54:86] 组成 32×32 crop，源 B13 按坐标最近点索引 gather。范围 lat={align['output_lat_range']}，lon={align['output_lon_range']}。明确 descending source → ascending target 的索引顺序；无 silent flip、插值、填补、域外外推或科学方法冻结。仅 ENGINEERING_SMOKE_CROP_ONLY，不是 model_input_bbox。

## 9. Tensor contract

item x/y=[1,32,32]；batch=[B,1,32,32]；float32；mask 相同 shape / bool。x 为 K，y 为 mm hr-1。显式添加 channel/batch，不无记录 squeeze。实际输入 crop 全有效；原缺测仍为 NaN+mask；模型不静默填零。

## 10. Dataset

B0SmokeDataset PASS，只服务本轮。__getitem__ 实际读 B13/IMERG，重验坐标、时间与因果，再做 smoke gather。缓存仅保存 16 个小 crop tensor；未构建 FormalTrainingDataset、全量 index 或科研样本库。

## 11. DataLoader

batch_size=1 与 4 均 PASS；shuffle=False、num_workers=0。Windows 未启用 multiprocessing。metadata 保留为逐样本 list；合约与加载秒数见 dataloader_check.json。

## 12. Model

ENGINEERING_SMOKE_MODEL：两级 encoder、bridge、skip connections 与 ConvTranspose decoder；width=8，输入单 B13 单时次，输出单 precipitation field（Softplus 非负）。没有 EfficientNet、quantile/probability heads；不宣称等价于完整 GPROF-IR 科学实现。不是正式 architecture freeze。

## 13. Parameter count

{r['parameter_count']} 个可训练参数；完整模块结构见 model_summary.txt。

## 14. Loss

masked MSE，只对 target_valid_mask=True 的原单位目标计算；invalid 像元先索引排除，0 rain 保留。target 无变换。模型内部固定 x/300 仅 smoke 数值 conditioning，不是数据拟合的 mean/std 或正式 normalization。

## 15. Updates

单 seed=42、1 epoch、{r['optimizer_steps']} optimizer steps，Adam lr=1e-3（ENGINEERING_SMOKE_ONLY）。没有 early stopping、调参、多 seed、正式训练/验证/测试。

## 16. Loss finite

4/4 步 loss finite。原值见 step_log.csv，仅用于工程数值检查，不讨论收敛或模型优劣。

## 17. Gradient

每步所有可训练参数 grad 非 None 且 finite；存在非零梯度。gradient_update_check.json 保存逐步证据。

## 18. Optimizer update

每步至少一个参数 tensor 在 optimizer.step 后实际变化；不是只调用 API 后推断成功。更新数量逐步保存。

## 19. Checkpoint

真实保存 `{ck['path']}`，含 model_state_dict、optimizer_state_dict、step、config、sample contract version。新建 model instance 后 weights-only reload；同输入最大绝对差 {ck['same_input_max_abs_diff']}，检查 rtol={ck['rtol']} / atol={ck['atol']} 通过；optimizer state 也重载。**SMOKE CHECKPOINT / NOT SCIENTIFIC CHECKPOINT**。

## 20. Inference

reload 后对 4 个真实样本重新读取原文件、配对并推理，输出 [4,1,32,32]、finite、无崩溃。数值保存 inference_outputs.npz；没有生成科研预测产品。

## 21. Diagnostic MAE / RMSE

MAE={metrics['MAE_mm_hr']:.9f} mm hr-1；RMSE={metrics['RMSE_mm_hr']:.9f} mm hr-1。**ENGINEERING_DIAGNOSTIC_ONLY / IN_SAMPLE**，{metrics['valid_pixels']} 个有效 crop 像元，含 {metrics['zero_rain_included']} 个真实 0 rain 像元。来自参与过 smoke update 的 4 个样本，没有 held-out 或整省评价含义，禁止论文引用或模型优劣结论。未做 occurrence threshold、CRPS 或概率指标。

## 22. Device

{env['device_used']}；torch {env['torch_version']}；CUDA_available={env['CUDA_available']}。CPU {env['CPU']}。无 CUDA 时按任务继续 CPU smoke。

## 23. Memory / timing

首 batch_size=1 load={loads['1']['load_seconds']:.6f}s；batch_size=4 load={loads['4']['load_seconds']:.6f}s（部分小 tensor 已在本轮 cache）。平均 forward={perf['mean_forward_seconds']:.6f}s、backward={perf['mean_backward_seconds']:.6f}s。GPU peak={r['peak_gpu_memory_status']}。这是 SMOKE PERFORMANCE DIAGNOSTIC，不是正式 benchmark。固定 random/NumPy/PyTorch seed；deterministic enabled、warn_only=True、CPU threads=2；不声称 CUDA bitwise 保证。

## 24. Pytest

先通过 {unit_tests} 个独立单元测试再读真实数据执行；最终 {tests['tests']} passed，failures/errors/skipped 全 0。覆盖用户列出的 30 类 reader、mask、causality、tensor、batch、forward/backward、update、checkpoint、inference、raw/Stage-0 保护与禁用输入要求。真实 stdout/XML 在 tests/pytest_final_output.txt、tests/pytest_final.xml。单位测试使用 synthetic fixture，主端到端只用上述真实文件。

## 25. Dependencies

始终 `{g.PYTHON}`。没有安装/升级依赖，全部 distribution 版本前后快照相同。numpy={env['numpy_version']}、netCDF4={env['netCDF4_version']}、pyarrow={env['pyarrow_version']}。教学模型因多通道/概率头/导入即运行而未导入。

## 26. Raw integrity / frozen conventions

全部 {len(raw)} 个选定 raw 文件与 {len(old)} 个登记 Stage-0 输入 size/mtime/SHA256 在测试后仍相同；原件/旧 run 写操作 0。冻结 registry、正式主 mask 和 comparison 保持原 hash。不声称全库所有文件都新做了哈希验证。

## 27. Cache

本轮新 run 内 cache/staging，单文件上限 {cache['max_bytes']} bytes。实际 {cache['copy_count']} 次 copy，累计 {cache['total_copied_bytes']} bytes，峰值单副本 {cache['max_single_temporary_bytes']} bytes；每次 size/hash 一致，copy累计={cache['copy_seconds']:.6f}s、read累计={cache['read_seconds']:.6f}s。cleanup failures=0，剩余副本=0。仅清理自身登记的临时副本；未删旧 diagnostic cache。累计 I/O 不是永久库复制量；SHA/启动/完整性耗时不在 copy/read 区间内。

## 28. Scientific limitations

时间绑定 provisional，native half-hour 语义未定；空间 crop/nearest gather/输入 conditioning/architecture/loss/lr 全是 smoke。没有 operational replay、正式 normalization、split、科研训练、多 seed、2025 评价、论文图表或科学结论。云南正式行政 mask 仍冻结，但本次小 crop metric 不是全省正式主评价。

## 29. Formal experiment blockers

Stage-0 Final Gate 中 10 项正式入口依赖原样保留，详见 B0_FORMAL_EXPERIMENT_HOLD.md：2025-10 缺月、native timing/正式 analysis binding、bbox/context、精确 Train/Val、missing/QC、正式归一化来源、availability 声明、正式概率实验协议、其余月份工程证据。本轮临时候选批准不等于这些科学项已解决；GFS/DEM 的未来阶段事项不成为 smoke 输入。

## 30. Gate conclusion

B0 ENGINEERING SMOKE PASS，B0 FORMAL EXPERIMENT NOT_READY。完成本次安全工程任务后停止，不自动进入正式 B0、B1 或任何下一 Stage。

{g.ENDING}
'''
 g.write(run,'FINAL_B0_ENGINEERING_SMOKE_REPORT.md',report)
 # Round-trip output tables using approved pyarrow only.
 serial=[]
 for p in sorted(run.rglob('*.csv')):
  if 'tests' in p.relative_to(run).parts:continue
  with p.open(encoding='utf-8-sig',newline='') as f:
   rd=csv.DictReader(f);fields=rd.fieldnames;rows=list(rd)
  t=pa.Table.from_pylist(rows,schema=pa.schema([(n,pa.string()) for n in fields]));q=p.with_suffix('.parquet')
  try:
   pq.write_table(t,q,compression='snappy');assert pq.read_table(q).equals(t)
  except Exception as e:g.wjson(run,'logs/parquet_error.json',{'path':str(p),'error':repr(e)});raise
  serial.append({'csv':str(p.relative_to(run)),'parquet':str(q.relative_to(run)),'rows':len(rows),'exact_roundtrip':True})
 g.wjson(run,'logs/csv_parquet_validation.json',{'engine':'pyarrow','column_schema':'string-valued CSV exact presentation; typed values in JSON/NPZ','checks':serial})
 required=['B0_SMOKE/himawari_b13_reader_report.md','B0_SMOKE/spatial_alignment_smoke_report.md','B0_SMOKE/tensor_contract.md','B0_SMOKE/loss_contract.md','B0_SMOKE/gradient_update_check.json','B0_SMOKE/checkpoints/b0_smoke_only.pt','logs/environment.json','b0_smoke_status.json','FINAL_B0_ENGINEERING_SMOKE_REPORT.md']
 assert all((run/x).is_file() for x in required)
 assert report.rstrip().endswith(g.ENDING)
 assert all(status[k] for k in ['real_data_end_to_end','dataset_pass','dataloader_pass','forward_pass','backward_pass','optimizer_pass','checkpoint_reload_pass','inference_pass','pytest_pass'])
 g.wjson(run,'logs/final_artifact_validation.json',{'status':'PASS','required_paths':required,'scientific_status':'NOT_READY_UNCHANGED','csv_parquet_roundtrip_pass':True,'utc':g.utc()})
 manifest=[]
 for p in sorted(run.rglob('*')):
  if p.is_file():manifest.append(dict(relative_path=str(p.relative_to(run)),size_bytes=p.stat().st_size,sha256=g.sha256(p)))
 g.table(run,'output_manifest.csv',manifest)
 pq.write_table(pa.Table.from_pylist(manifest),run/'output_manifest.parquet',compression='snappy')
 for x in manifest:assert g.sha256(run/x['relative_path'])==x['sha256']
 print(json.dumps({'run':str(run),'engineering_status':'PASS','tests':tests,'raw_files_unchanged':len(raw),'stage0_inputs_unchanged':len(old),'formal_experiment':'NOT_READY'},ensure_ascii=False))
