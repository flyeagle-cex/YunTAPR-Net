"""Finalize only after scoped tests pass. Never starts the next stage."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,shutil,sys,xml.etree.ElementTree as ET
import pandas as pd
from probe import RUN,SMOKE,FREEZE,RAW,fp,sha,writej
from build_package import FINAL_LINES,doc,table

def readj(rel): return json.loads((RUN/rel).read_text(encoding='utf-8'))
def main():
    latest=max((RUN/'tests').glob('pytest_attempt_*.xml'),key=lambda p:int(p.stem.split('_')[-1]))
    root=ET.parse(latest).getroot()
    suites=[root] if root.tag=='testsuite' else list(root.findall('testsuite'))
    counts={k:sum(int(x.get(k,0)) for x in suites) for k in ('tests','failures','errors','skipped')}
    assert counts['tests']==30 and not any(counts[k] for k in ('failures','errors','skipped'))
    immutable=readj('logs/immutable_inputs_before.json'); other=readj('logs/additional_inputs_before.json')
    staging=[json.loads(l) for l in (RUN/'logs/staging.jsonl').read_text(encoding='utf-8').splitlines()]
    checks={}
    for x in immutable+other+[s['before'] for s in staging]:
        current=fp(x['path']); checks[x['path']]={'before':x,'after':current,'unchanged':x==current}
    assert all(x['unchanged'] for x in checks.values())
    writej('logs/final_integrity.json',{'all_unchanged':True,'unique_checked_files':len(checks),
        'old_registered_evidence_count':len(immutable),'source_scope':'All135 protected registered evidence files, all sampled raw/native inputs and added local provenance references; no claim of hashing entire raw archives',
        'checks':list(checks.values())})
    # Explicitly retain non-scientific failures and the unrelated Late probe failure.
    writej('logs/recovery_notes.json',{
      'environment_display_attempt':{'error':'importlib.metadata.PackageNotFoundError: h5py','resolution':'Optional h5py absent; netCDF4 1.7.4 read native HDF5 metadata successfully; no installation or environment change'},
      'first_build_attempt':{'error':'source snapshot byte SHA assertion on discover.py','finding':'UTF-8-sig normalized source text identical; byte/line-ending difference only',
          'resolution':'Preserve original discovery snapshot and save distinct source snapshots by SHA prefix; no old artifact replacement'},
      'pytest_attempt_1':{'tests':30,'passed':29,'failed':1,'reason':'Default pandas CSV parser changed final floating-point ULP during readback',
          'resolution':'CSV already stores exact round-trip numeric text; use float_precision=round_trip, strict equality retained; no coordinates changed',
          'preserved_evidence':'tests/pytest_attempt_1.xml; tests/pytest_attempt_1.txt; tests/source_history/'},
      'native_probe_failure':{'count':1,'product':'Late cache, 2025-11-07; outside required Final evidence','error':'OSError(-51, NetCDF: Unknown file format)',
          'disposition':'Recorded, not removed, repaired, or treated as PASS; 9 Final probes independently pass'},
      'final_pytest':counts})
    for p in Path(__file__).parent.glob('*.py'):
        dest=RUN/'src'/p.name
        if dest.exists() and sha(dest)!=sha(p): dest=RUN/'src'/(p.stem+'_'+sha(p)[:12]+p.suffix)
        if not dest.exists(): shutil.copyfile(p,dest)
    src_rows=[dict(path=str(p.relative_to(RUN)),sha256=sha(p),size_bytes=p.stat().st_size) for p in sorted((RUN/'src').glob('*.py'))]
    table('PROVENANCE/generator_script_hashes.csv',src_rows)
    # External/local evidence registry: hashes are actual files, not invented URL hashes.
    evidence=[]
    for i,(path,check) in enumerate(sorted(checks.items()),1):
        evidence.append(dict(evidence_id=f'LOCAL{i:03d}',kind='LOCAL_FILE',path_or_url=path,
          sha256=check['before']['sha256'],size_bytes=check['before']['size_bytes'],
          role='IMMUTABLE_PRIOR_EVIDENCE' if any(x['path']==path for x in immutable) else 'READ_ONLY_SOURCE_OR_PROVENANCE',
          status='VERIFIED_UNCHANGED',limitation='See source-specific audit scope; metadata probing did not inspect precipitation arrays'))
    for r in pd.read_csv(RUN/'TIME/official_sources.csv',keep_default_na=False).to_dict('records'):
        evidence.append(dict(evidence_id=r['evidence_id'],kind='OFFICIAL_WEB_SOURCE',path_or_url=r['url'],sha256='',size_bytes=None,
             role=r['scope'],status='BROWSED_OFFICIAL_SOURCE',limitation=r['original_file_sha256']))
    for rel in ['logs/discovery_authorization.json','logs/discovery_summary.json','TIME/native_metadata_probes.json',
                'TIME/native_converted_time_comparison.csv','TIME/converted_metadata_probes.json','TIME/conversion_chain_search.json',
                'SPATIAL/frozen_spatial_anchor_verification.json','SPATIAL/candidate_coordinate_indices.json',
                'SPLIT/candidate_blocks.json','DATA_CONTRACT/b0_contract_candidate.json','logs/final_integrity.json']:
        p=RUN/rel
        evidence.append(dict(evidence_id='RUN_'+p.stem,kind='THIS_RUN_DERIVED_EVIDENCE',path_or_url=str(p),sha256=sha(p),size_bytes=p.stat().st_size,
          role='NEW_CANDIDATE_OR_VERIFICATION_NOT_SCIENTIFIC_APPROVAL',status='RECORDED',limitation='Candidate status never implies frozen science'))
    table('evidence_registry.csv',evidence)
    entries=readj('DATA_CONTRACT/entry_matrix_machine.json'); blockers=[x['item'] for x in entries if x['status']!='PASS']
    status=dict(run_id=RUN.name,completed_utc=datetime.now(timezone.utc).isoformat(),
      stage='Stage-1 / B0 Formal Readiness Resolution',package_status='COMPLETE',
      b0_engineering_smoke='PASS',prior_smoke_run=str(SMOKE),prior_smoke_unchanged=True,
      b0_formal_ready=False,b0_formal_status='B0_FORMAL_NOT_READY',formal_time_binding_frozen=False,
      time_mapping_status='ENGINEERING_SMOKE_TIME_MAPPING_ONLY',native_time_evidence='9 sampled Final native/subset granules support lower-bound T; converter identity/order NOT_ESTABLISHED globally',
      research_period_frozen=True,research_years=[2023,2024,2025],research_months=[3,4,5,6,7,8,9,10],
      imerg_2025_10_status='MISSING',late_october_files_not_substituted=31,
      model_input_bbox_frozen=False,weather_system_context_margin_frozen=False,covers_yunnan_context='PENDING_RESEARCHER_CONFIRMATION',
      train_val_blocks_frozen=False,final_test_year=2025,evaluation_mask_frozen=True,evaluation_mask_true_cells=3430,
      normalization_rule_defined=True,normalization_method_frozen=False,normalization_statistics_computed=False,
      formal_architecture_frozen=False,formal_loss_output_protocol_frozen=False,formal_training_started=False,
      raw_data_modified=False,old_audit_results_modified=False,dependencies_changed=False,
      science_data_downloaded=False,formal_split_executed=False,old_smoke_rerun=False,
      source_arrays_resampled=False,DEM_processed=False,DOTE_features_generated=False,
      engineering_tests=counts,test_status='PASS',test_report=str(latest),
      blockers=blockers,blocker_count=len(blockers),decision_cards=10,
      raw_integrity_scope='Sampled raw/native files plus protected source evidence hashes; all operations read-only; entire raw archive not rehashed',
      all_registered_prior_evidence_unchanged=True,checked_old_evidence_files=len(immutable),
      automatic_next_stage=False,stop_after_package=True)
    writej('b0_formal_readiness_status.json',status)
    copyseconds=sum(x['copy_seconds'] for x in staging); readseconds=sum(x['read_seconds'] for x in staging)
    peak=max(x['temporary_bytes'] for x in staging); total=sum(x['temporary_bytes'] for x in staging)
    writej('logs/staging_summary.json',dict(files_staged=len(staging),one_at_a_time=True,total_copy_seconds=copyseconds,
        total_metadata_read_seconds=readseconds,peak_temporary_bytes=peak,total_copied_bytes=total,
        all_size_and_sha_verified=all(x['size_verified'] and x['sha256_verified'] for x in staging),
        all_cleanup_success=all(x['cleanup_success'] for x in staging),bytes_remaining=sum(p.stat().st_size for p in (RUN/'cache/staging').glob('*') if p.is_file()),
        scope='Metadata inspection only, not a rerun of Stage0 storage benchmark',extra_io='Copy plus source/destination SHA reads add I/O; timing columns exclude hash time'))
    doc('README.md',f'''# YunTAPR-Net B0 Formal Readiness Resolution

结果：**B0_FORMAL_NOT_READY**，证据/候选/决策包已完成。科学入口仍有 {len(blockers)} 项 blocker；没有启动训练。旧 B0 smoke PASS 保持原样。此目录为独立新 run，不能将此包完成等同于科学约定冻结或模型可正式训练。

## 导航

- [最终报告](FINAL_B0_FORMAL_READINESS_REPORT.md)
- [状态 JSON](b0_formal_readiness_status.json)、[入口矩阵](B0_FORMAL_ENTRY_MATRIX.csv)
- [研究者决策清单](RESEARCHER_DECISIONS_REQUIRED.md)、DECISIONS/ 下 10 张卡
- TIME/：原生/转换 metadata、四种时间候选、来源链、官方出处
- GAPS/：Final October 缺口，Late 身份和搜索覆盖限制
- SPATIAL/：4 个实际坐标候选、形状/margin/padding/索引与冻结 hash 校验
- SPLIT/：3 个连续块候选，数量仅未扣 QC/buffer 的名义上界
- DATA_CONTRACT/、MODEL/：machine-readable候选契约与科学待决项
- evidence_registry.csv/.parquet、PROVENANCE/：输入与生成脚本 hash
- tests/：首轮失败及修复后结果均保留；logs/：搜索、环境、临时缓存和完整性

## 运行和复核

固定 Python：`F:\\pytorch\\Research\\.venv\\Scripts\\python.exe`。包版本实测记录于 logs/environment.json；没有安装或升级包。h5py 未安装，使用 netCDF4 读取 HDF5 metadata 成功；不因可选包缺失改环境。

本轮顺序：已授权文件名发现 → probe.py 只读 metadata/坐标及哈希保护 → build_package.py 分阶段断言 → run_checks.py 定向 pytest → finalize.py 校验旧证据、整理状态/报告。脚本历史按 hash 后缀保留，实际最终源文件 hash 在 PROVENANCE/generator_script_hashes.csv。第一次 build 因原 discovery 脚本换行编码字节差异中止，在归档各版本后继续。详情 logs/recovery_notes.json。

在完成包上复核测试可使用以下**只读**命令（不写回原测试日志）：

```powershell
& 'F:\\pytorch\\Research\\.venv\\Scripts\\python.exe' -X utf8 -B -m pytest '{RUN / 'tests/test_readiness.py'}' -q -p no:cacheprovider
```

不要在完成目录重跑写入构建脚本；写入函数采用排他创建，防止覆盖。要重建，应另建 run 并显式更新 probe.py 的 RUN，登记复用的 discovery 证据路径/hash，而非假装搜索当时状态仍代表新时点。旧 smoke 与 Stage0 目录始终作为只读依赖。测试覆盖契约和元数据，未重复 ML pipeline，也不是全月/全期 QC。

## 双格式与坐标

主要候选、矩阵及 registry 同时 CSV + Parquet，Parquet engine=pyarrow。CSV 使用 pandas 读取精确坐标应指定 `float_precision='round_trip'`，否则默认 C parser 可能产生一个 ULP 舍入差异；本轮首次一致性测试正是由此失败，源 CSV 与真实坐标未改动，修复读取后严格一致性通过。Parquet 无写入失败，也未更换依赖。坐标权威源为真实采样/冻结 NPZ/NetCDF + SHA，不用 arange 重建。

## 中文路径 bounded staging

只在本 run `cache/staging/` 创建随机英文名、单文件临时副本，每次验证 size 和 SHA256，用英文路径交给 netCDF4，仅读取 header/time/坐标。共 {len(staging)} 次，临时峰值 {peak:,} bytes，总复制 {total:,} bytes，copy {copyseconds:.6f}s，metadata read {readseconds:.6f}s，全部 cleanup 成功，当前临时数据为 0 bytes。没有删除 H 盘或任何已有诊断缓存。

源/副本 SHA 会增加读取 I/O，copy_seconds 与 read_seconds 不包含全部 hash 时间；本次数据是小规模 metadata probe 成本，**不是**重新做 Zarr/NetCDF 存储性能结论，也不能与旧 full-array benchmark 直接比较。唯一不可读的是 Late 的一个11月临时文件，错误已归档；科学 Final 证据不使用它。

## 完整性与限度

最终重新校验 {len(immutable)} 条保护证据及全部新增只读输入，合并 {len(checks)} 个文件全部大小/mtime/SHA不变。没有对整个原始库重新逐文件 hash，raw_data_modified=false 来源于只读操作边界和这些实测保护记录。全盘搜索是名称发现，有跳过/访问拒绝，未解包旧 archive；不是不存在任何备用数据的绝对证明。

没有正式 mean/std、Train/Val/Test 实例分配、数据重采样、GFS/DEM特征、B0训练或下一阶段执行。输出按用户明确要求为可编辑 Markdown/CSV/JSON，而非另生成未要求的 PDF 或图表。
''')
    candidates=pd.read_csv(RUN/'SPATIAL/b0_input_domain_candidates.csv',float_precision='round_trip')
    split=pd.read_csv(RUN/'SPLIT/b0_train_val_candidates.csv')
    spatial_rows='\n'.join(f"|{r.candidate_id}|{r.native_shape}|{r.target_shape}|3430|" for r in candidates.itertuples())
    split_rows='\n'.join(f"|{r.candidate_id}|{r.train_nominal_halfhour_slots}|{r.validation_nominal_halfhour_slots}|" for r in split.itertuples())
    doc('FINAL_B0_FORMAL_READINESS_REPORT.md',f'''# YunTAPR-Net — B0 Formal Readiness Resolution

**结论：B0_FORMAL_NOT_READY。** 本轮证据与决策包完成，30 项定向测试通过；正式入口仍有 {len(blockers)} 项 blocker。旧 B0 Engineering Smoke 仍为 PASS，未重跑或修改。正式训练未开始，完成后停止。

Run：`{RUN}`。固定解释器、真实版本、只读边界和完整日志见 README.md 与 logs/。全部候选由脚本实际计算并保存，没有把 NOT_RUN/NOT_AUDITED 当成 PASS。

## 1. 已解决的工程证据

- **时间证据增强**：发现原生命名缓存 122 个，小范围尝试 12 个文件。9 个 Final 原生/Harmony 子集均保存 time_bnds，time 等于下界，时间窗1800秒；与同日 converted CF 时刻相等。完整原生成脚本缺失，逐 granule→slice 身份/顺序未证实；正式绑定仍未冻结。详见 [时间证据](TIME/B0_FORMAL_TIME_SEMANTICS_EVIDENCE.md)。
- **缺口确认**：扩大 C–H 全盘文件名发现，但存在251个访问错误和1959个跳过目录。已知 Final root October 文件数0；发现31个 October Late 日文件，身份明确，未替代 Final；当前仍 MISSING。旧备份 archive 年份2021–2024，仅登记、未解包。不能推出官方当前不可获取该月。详见 [October决策卡](GAPS/IMERG_2025_10_DECISION_CARD.md)。
- **空间候选**：4 个候选使用真实坐标索引，均完整保留3430主评价中心；没有坐标重建、transpose、silent flip 或重采样。见 [空间决策](SPATIAL/B0_INPUT_DOMAIN_DECISION.md)。
- **split 候选**：3 组连续时间块，Train/Val互不重叠，仅2023/24，2025完全隔离；数量只是日历×48上界，未扣缺帧/因果/QC/buffer。见 [Train/Val决策](SPLIT/B0_TRAIN_VAL_DECISION.md)。
- **契约**：明确0!=missing、单帧B13、Train-only normalization范围与版本规则；没有拟合真实统计。正式partial/QC、normalization方法、架构和loss/output仍待批准。

|空间候选|native rows,cols|target rows,cols|主评价 cells|
|---|---|---|---|
{spatial_rows}

|split候选|Train名义槽位|Val名义槽位|
|---|---|---|
{split_rows}

以上均无 winner。空间 margin 和 stride 16/32 的假设 padding 数在 CSV，不代表模型层级或padding方案已选择。

## 2. FROZEN

继承而未修改：2023–2025 每年 March–October；Development为2023/24，FinalTest为2025；GADM4.1 Level-1 Yunnan（CHN.30_1，五项身份字段均承接已批准registry）；真实IMERG目标坐标；center-in-polygon主评价mask=(130,140)，3430cells；obs_end<=analysis_time；0雨与missing分开、原始数据只读、不得未来卫星帧。主mask SHA256：`9d921def661fc3e58cd1ed783fcf87abbf493da6ae5e5fea79c28043f73495ef`。intersection mask 保留为非主评价比较。

冻结规则的引用不表示全研究期数据完整，也不表示全部正式入口已就绪。B13 reader接口可复用既有PASS，但其他月份数据资格仍需验证。

## 3. NOT_YET_FROZEN / NOT_ESTABLISHED

正式IMERG–Himawari时间绑定、analysis时刻与单帧选法；model_input_bbox和天气context；Train/Val blocks及buffer/事件隔离；正式partial/missing/QC接受协议；Train-only统计方法/统计域和参数；native-to-target对齐；正式B0层级、概率头是否首版、loss/output/校准/评价与重复设计。原转换链全库映射及联合可用样本数为NOT_ESTABLISHED。除July2024外Himawari研究月资格为NOT_AUDITED，不能视为缺失或通过。

`normalization_rule_defined=true` 仅表示本轮已定义Train-only防泄漏范围规范；`normalization_method_frozen=false`、`normalization_statistics_computed=false`。没有自动把正式B0定义成确定性回归。

The cross-source IMERG-Himawari time binding used in this B0 smoke run is provisional and was used only to test the engineering pipeline. It is not a frozen scientific sample timing convention.

date_created 只记录，未建立 operational availability，未声称完成历史实时回放。

## 4. RESEARCHER_DECISION_REQUIRED

详见 [10张决策卡清单](RESEARCHER_DECISIONS_REQUIRED.md) 与 [16项入口矩阵](B0_FORMAL_ENTRY_MATRIX.csv)。矩阵4项规则/接口已满足、12项仍阻塞；同一科学决策可覆盖多个矩阵项。主要待决：时间绑定、October Final缺口、输入域/context、Train/Val及buffer、missing/QC、normalization方法、正式架构/概率头、loss/output/空间对齐与后续多月数据资格安排。

October三条路径：A批准补齐同版本Final；B显式修订研究期；C研究者另定方案。没有自动下载、缩短研究期或用Late替代。GFS/GFS_thermo/vintage、DEM、DOTE、DTFM、MEE、ERA5 Teacher不属于B0必需输入blocker。

## 5. 验证与可追溯性

最终 pytest：30 passed，0 failed/errors/skipped。测试涵盖候选不冻结、2025隔离、连续块不重叠及反例拒绝、真实坐标/冻结mask、zero/missing、Train-only拟合角色、旧证据完整性、单文件staging与双格式一致性。测试只验证契约与工程证据，未重复Dataset→Tensor→Model链，也未测试模型性能。

首轮29passed/1failed保留：CSV默认解析器对浮点尾数舍入，改用round_trip后严格逐值比较通过，没有改源坐标。第一次构建因discovery脚本字节换行差异中止，也保留原快照与修复说明。12个native尝试中的一个Late缓存报unknown format，失败未掩盖，不纳入9个Final有效证据。见 tests/ 和 logs/recovery_notes.json。

旧smoke manifest的120项、其manifest本身与Stage0冻结/审计锚点共135条保护记录，加新增来源合并{len(checks)}个文件，最终size/mtime/SHA全不变。只读输入只在本轮英文staging复制并清理，所有原始与旧缓存保留。证据hash见 evidence_registry.csv/.parquet，脚本hash见 PROVENANCE/generator_script_hashes.csv/.parquet。输出总清单见 output_manifest.csv/.parquet（不自包含这两个manifest）。

本轮没有正式mean/std、真实split实例分配、模型训练、数据重采样、GFS/DEM处理或DOTE特征；不自动进入下一Stage。

{FINAL_LINES}
''')
    # Final package structural check, separate from scientific/unit test status.
    required=['FINAL_B0_FORMAL_READINESS_REPORT.md','b0_formal_readiness_status.json','RESEARCHER_DECISIONS_REQUIRED.md',
        'B0_FORMAL_ENTRY_MATRIX.csv','B0_FORMAL_ENTRY_MATRIX.parquet','evidence_registry.csv','evidence_registry.parquet',
        'TIME/B0_FORMAL_TIME_SEMANTICS_EVIDENCE.md','TIME/b0_time_rule_candidates.csv','GAPS/IMERG_2025_10_DECISION_CARD.md',
        'SPATIAL/b0_input_domain_candidates.csv','SPATIAL/B0_INPUT_DOMAIN_DECISION.md','SPLIT/b0_train_val_candidates.csv',
        'SPLIT/B0_TRAIN_VAL_DECISION.md','DATA_CONTRACT/b0_missing_qc_contract_candidate.md','DATA_CONTRACT/b0_normalization_contract.md',
        'MODEL/B0_FORMAL_ARCHITECTURE_DECISION.md','README.md']
    assert all((RUN/p).exists() and (RUN/p).stat().st_size>0 for p in required)
    assert (RUN/'FINAL_B0_FORMAL_READINESS_REPORT.md').read_text(encoding='utf-8').rstrip().endswith(FINAL_LINES)
    assert not status['b0_formal_ready'] and status['blocker_count']==12
    # All local entry evidence paths resolve, including relative paths into this run.
    for r in entries:
        p=Path(r['evidence']); assert (p if p.is_absolute() else RUN/p).is_file(),r['item']
    writej('logs/package_validation.json',{'status':'PASS','required_outputs':required,'decisions':len(list((RUN/'DECISIONS').glob('*.md'))),
        'required_final_lines_exact':True,'entry_evidence_paths_exist':True,'pytest':counts,'formal_gate':'B0_FORMAL_NOT_READY'})
    outputs=[dict(relative_path=str(p.relative_to(RUN)),size_bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(RUN.rglob('*')) if p.is_file() and p.name not in ['output_manifest.csv','output_manifest.parquet']]
    table('output_manifest.csv',outputs)
    # Self-contained terminal validation without modifying finalized manifests.
    reread=pd.read_parquet(RUN/'output_manifest.parquet',engine='pyarrow')
    assert len(reread)==len(outputs)
    assert all(sha(RUN/x['relative_path'])==x['sha256'] for x in outputs)
    print(json.dumps({'package':'COMPLETE','formal_status':'B0_FORMAL_NOT_READY','tests':counts,
        'blockers':len(blockers),'integrity_files':len(checks),'manifest_files':len(outputs),'report':str(RUN/'FINAL_B0_FORMAL_READINESS_REPORT.md')},ensure_ascii=False))

if __name__=='__main__': main()
