"""Build a reviewable, non-training B0 readiness package from read-only evidence."""
import csv, hashlib, json, math, re, shutil, sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import netCDF4
from probe import RUN, SMOKE, FREEZE, P0, CONT, RAW, sha, fp, writej, clean
from contract_rules import validate_split, formal_gate

WORK=Path(__file__).parent
FINAL_LINES='''B0 formal-readiness resolution package complete.
The prior B0 engineering smoke remains PASS and unchanged.
No formal B0 training was started.
No provisional timing or spatial convention was silently frozen.
All remaining formal-entry decisions are explicitly assigned to the researcher.'''
PDF_URL='https://gpm.nasa.gov/sites/default/files/2023-07/IMERG_TechnicalDocumentation_final_230713.pdf'
WEB_URL='https://gpm.nasa.gov/data/imerg'

def readj(rel): return json.loads((RUN/rel).read_text(encoding='utf-8'))
def doc(rel,text):
    p=RUN/rel; p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f: f.write(text.strip()+'\n')
def table(rel,rows):
    p=RUN/rel; p.parent.mkdir(parents=True,exist_ok=True); assert not p.exists()
    frame=pd.DataFrame(rows); frame.to_csv(p,index=False,encoding='utf-8-sig')
    try:
        frame.to_parquet(p.with_suffix('.parquet'),engine='pyarrow',index=False)
        pd.testing.assert_frame_equal(frame,pd.read_parquet(p.with_suffix('.parquet'),engine='pyarrow'),check_dtype=False)
    except Exception as exc:
        with (RUN/'logs/parquet_errors.jsonl').open('a',encoding='utf-8') as f: f.write(json.dumps({'file':rel,'error':repr(exc)})+'\n')
        raise
def coordhash(a):
    a=np.asarray(a,dtype='<f8').copy(); a[a==0]=0
    return hashlib.sha256(str(a.shape).encode('ascii')+a.tobytes(order='C')).hexdigest()
def dtime(s): return datetime.fromisoformat(s.replace('Z','+00:00')).replace(tzinfo=None)

def provenance():
    records=[]
    for obj in readj('TIME/local_manifest_evidence.json'):
        records.append(obj['fingerprint'])
    historical=Path(r'C:\Users\chenerxiao\Documents\极端降水预测\scripts\download_imerg.py')
    logfile=RAW/'logs/download_2025_20260824_235209/imerg_attempt1.log'
    lines=logfile.read_text(encoding='utf-8',errors='replace').splitlines()
    # Only record the explicit launcher command; do not copy credentials/log payloads.
    evidence={'historical_converter_path':str(historical),'exists_now':historical.exists(),
              'launcher_log':fp(logfile),'launcher_line_number':1,'launcher_line':lines[0],
              'status':'HISTORICAL_PATH_IDENTIFIED_SOURCE_CODE_NOT_RECOVERED',
              'content_search_scope':'Known workspace, F:/pytorch/Research and Desktop .py/.ps1; 16 old cache/test-directory access denials; no matching converter recovered',
              'limitations':'Volume-wide discovery was filename based and skipped named system/environment dirs and links; absence of original script is not proven outside searched scope.'}
    assert not evidence['exists_now']
    records.append(fp(logfile)); writej('TIME/conversion_chain_search.json',evidence)
    refs=[]
    for name in [Path(r'C:\Users\chenerxiao\.codex\skills\gpm-imerg-download\SKILL.md'),
                 Path(r'C:\Users\chenerxiao\Desktop\降水反演的代码\gprof_ir-main\src\gprof_ir\imerg.py'),
                 Path(r'C:\Users\chenerxiao\Desktop\降水反演的代码\hydronn-main\hydronn\data\imerg.py')]:
        if name.exists():
            refs.append({**fp(name),'role':'REFERENCE_ONLY_NOT_LINKED_TO_LOCAL_CONVERSION',
                         'executed':False,'establishes_conversion_time_semantics':False})
    writej('TIME/reference_code_candidates.json',refs)
    records.extend({k:x[k] for k in ('path','sha256','size_bytes','mtime_ns')} for x in refs)
    writej('logs/additional_inputs_before.json',records)
    official=[dict(evidence_id='WEB01',url=PDF_URL,title='NASA IMERG V07 technical documentation, 13 July 2023',
                   accessed_utc='2026-09-28',locator='printed pages 21-22, especially page 22 native 3IMERGHH temporal sampling; page 6 value-added products',
                   access_method='Official PDF text viewed with web tool; no science data downloaded',original_file_sha256='NOT_DOWNLOADED',
                   scope='Native filename and half-hour sampling only; does not prove local converter ordering'),
              dict(evidence_id='WEB02',url=WEB_URL,title='NASA IMERG overview / FAQ',accessed_utc='2026-09-28',
                   locator='precipitation rate and temporal resolution explanation',access_method='Official web page read',
                   original_file_sha256='NOT_APPLICABLE_WEB_PAGE_NOT_ARCHIVED',scope='Product-level units and interval context')]
    table('TIME/official_sources.csv',official)
    doc('TIME/official_source_notes.md',f'''# Official source evidence — limited scope

NASA 的 V07 文档说明，原生 3IMERGHH 半小时窗从整点或半点开始，日期及起止时刻写入文件名和元数据；原生产品与增值转换产品的说明应区分。定位：印刷页 6、21–22。[NASA V07 documentation]({PDF_URL})

IMERG 降水率按时间段表达，单位为 mm/hr，不能当作瞬时观测，也不能直接把数值当成 mm 累积量。[NASA IMERG overview]({WEB_URL})

以上均为释义；本轮未下载官方 PDF 文件或科学数据，未虚构官方文件 SHA256。官方文字只证明产品层面的定义。局地转换文件的 T 和数组顺序仍需独立转换链证据。发现的第三方源码和本地下载 skill 仅登记为线索，没有执行其中的下载/安装/清理指令。''')

def time_evidence():
    natives=readj('TIME/native_metadata_probes.json'); converted=readj('TIME/converted_metadata_probes.json')
    daymap={re.search(r'(\d{8})\.nc$',x['source']).group(1):x for x in converted if 'imerg_late_' not in x['source']}
    comparisons=[]
    for n in natives:
        if n.get('error'): continue
        p=Path(n['source']); m=re.search(r'(\d{8})-S(\d{6})-E(\d{6})',p.name)
        gd=n['groups']['/Grid']; tv=gd['variables']['time']; bv=gd['variables']['time_bnds']
        a=np.asarray(bv['raw_values']); v=np.asarray(tv['raw_values']); u=tv['attributes']['units']; cal=tv['attributes'].get('calendar','standard')
        bounds=[str(x) for x in np.asarray(netCDF4.num2date(a,u,calendar=cal)).flat]
        rawt=tv['decoded_values'][0]; is_final='3B-HHR-L.' not in p.name
        c=daymap.get(m[1]); idx=None; exact=False
        if c:
            cv=c['groups']['/']['variables']['time']['decoded_values']
            idx=cv.index(rawt) if rawt in cv else None; exact=idx is not None
        header=n['groups']['/']['attributes'].get('FileHeader','')
        get=lambda key: re.search(r'(?:^|\n)'+re.escape(key)+r'=([^;]*);',header).group(1)
        comparisons.append(dict(source=str(p),source_sha256=n['source_fingerprint']['sha256'],product='Final' if is_final else 'Late',
            date=m[1],native_calendar=cal,bounds_calendar_used=cal,native_time=rawt,bound_start=bounds[0],bound_end=bounds[1],
            duration_seconds=int(a.reshape(-1)[1]-a.reshape(-1)[0]),native_time_equals_bound_start=bool(v.flat[0]==a.flat[0]),
            filename_start=datetime.strptime(m[1]+m[2],'%Y%m%d%H%M%S').isoformat(),
            header_start=get('StartGranuleDateTime'),header_stop=get('StopGranuleDateTime'),
            converted_path=c['source'] if c else '',converted_time_index=idx,converted_coordinate_equal=exact,
            attribution_status='TEMPORAL_CONSISTENCY_ONLY_NOT_GRANULE_TO_ARRAY_PROVENANCE',formal_binding_frozen=False))
    finals=[x for x in comparisons if x['product']=='Final']
    assert len(finals)==9 and all(x['native_time_equals_bound_start'] and x['converted_coordinate_equal'] and x['duration_seconds']==1800 for x in finals)
    table('TIME/native_converted_time_comparison.csv',comparisons)
    candidates=[
      dict(candidate_id='T_START',T_interpretation='Window start',window='[T,T+30min)',candidate_analysis='T+30min if researcher adopts end-of-window analysis',candidate_frame='analysis-10min only as smoke reference; formal selection pending',evidence='9/9 sampled Final time equals lower bound and corresponding daily coordinate; official native interval evidence',limitation='Missing original converter/source-to-array identity; no formal researcher approval',status='CANDIDATE_ONLY_SUPPORTED_ON_SAMPLED_METADATA'),
      dict(candidate_id='T_CENTER',T_interpretation='Window center',window='[T-15min,T+15min)',candidate_analysis='T+15min if researcher adopts interval end',candidate_frame='Select an approved causal slot by actual obs_end; analysis-10min may not lie on a nominal 10min grid',evidence='Alternative interpretation for review; sampled native metadata does NOT support center interpretation',limitation='No evidence local converter shifted T to center; must establish independently',status='CANDIDATE_ONLY_NOT_SUPPORTED_BY_CURRENT_SAMPLES'),
      dict(candidate_id='T_OTHER_REFERENCE',T_interpretation='Other reference coordinate',window='From authoritative per-granule start/end/bounds, not guessed from T',candidate_analysis='Explicit researcher-approved function of verified native bounds',candidate_frame='Approved causal selection rule; no default latest-frame rule frozen',evidence='Native variable is described as representative time; local CF coordinate alone has no bounds',limitation='Reference transformation and target pairing must be documented',status='CANDIDATE_ONLY'),
      dict(candidate_id='NOT_ESTABLISHED',T_interpretation='Local global binding not established',window='NOT_ESTABLISHED',candidate_analysis='NOT_ESTABLISHED',candidate_frame='Formal sample construction remains disabled',evidence='Converter path recovered from history but code absent; only small metadata sample checked',limitation='Cannot treat daily sequence increments as proof of source granule to precipitation slice identity',status='NOT_ESTABLISHED')]
    for x in candidates: x.update(selected=False,scientific_rule_frozen=False,causality_rule='obs_end <= analysis_time',availability_rule='NOT_ESTABLISHED_date_created_record_only')
    table('TIME/b0_time_rule_candidates.csv',candidates)
    s=json.loads((SMOKE/'B0_SMOKE/smoke_sample_metadata.json').read_text(encoding='utf-8'))
    hm=readj('SPATIAL/himawari_coordinate_metadata.json')['groups']['/']
    rows=[dict(sample_id=x['sample_id'],nominal_time=x['selected_himawari_nominal_time'],obs_start=x['obs_start'],obs_end=x['obs_end'],date_created=x['date_created'],candidate_analysis_time=x['candidate_analysis_time'],mapping_status=x['mapping_status'],causality_pass=dtime(x['obs_end'])<=dtime(x['candidate_analysis_time'])) for x in s]
    assert all(x['causality_pass'] and x['mapping_status']=='ENGINEERING_SMOKE_TIME_MAPPING_ONLY' for x in rows)
    table('TIME/prior_smoke_time_evidence.csv',rows)
    doc('TIME/B0_FORMAL_TIME_SEMANTICS_EVIDENCE.md',f'''# B0 formal time semantics evidence

状态：**正式 IMERG–Himawari 绑定 NOT_YET_FROZEN；全库转换绑定 NOT_ESTABLISHED**。

## A. 实际 converted CF metadata

本轮只读抽查四个 Final 日文件：2021-08-25、2024-05-01、2024-05-27、2024-07-01。time 为当日午夜起分钟数，calendar=proleptic_gregorian，48 个坐标 0,30,…,1410；precipitation 为 (time,lat,lon)，(48,130,140)，单位 mm hr-1。title/source 标识 V07B Final / GPM_3IMERGHH_07。time 没有 bounds 属性，文件没有 time_bnds/time_bounds，也没有逐 slice 原生粒度文件标识。四文件完整 metadata/坐标、SHA256 在 converted_metadata_probes.json。未读取 precipitation 数组。

旧 P0 全库 time audit 可用作已完成工程证据；其 bounds presence CSV 是仅表头文件，不能单凭该空表声称逐行证明所有文件缺 bounds。这里关于缺 bounds 的直接证据限于四个新抽查 Final 文件。

## B. 转换链

日文件 history 声明转换了 48 个 source granules，manifest 记有 direct/Harmony 下载历史、日期与目标日文件。下载日志明确引用 `C:/Users/chenerxiao/Documents/极端降水预测/scripts/download_imerg.py`，本轮检查该路径不存在。全盘文件名发现和已知工作目录内容搜索未恢复可绑定到现存日文件的转换脚本版本。generic skill 与第三方库示例未证明是原生成代码，未执行。详见 conversion_chain_search.json、local_manifest_evidence.json、reference_code_candidates.json。

尚缺：原转换实现及 hash、native granule ID→日文件 slice 顺序映射、日期/时区处理、可能的重排/偏移。metadata 的时刻相等是证据增强，**不是数组来源身份已证实**。

## C. 新发现 native start/end/bounds

122 个原生命名缓存中按四个父目录各选排序首/中/尾，共尝试 12 个。9 个 Final（2021-08-25 原生 HDF5 3 个；2024-05-01 原生 HDF5 3 个；2024-05-27 Harmony 子集 3 个）均可读，time 为 seconds since 1980-01-06、calendar=julian，bounds=time_bnds。

9/9 的原生 time 等于 time_bnds 下界；上界−下界=1800 秒；对应 converted 日文件确有逐值相同解码时刻。原生 FileHeader start、filename S 一致。FileHeader stop 为 xx:29:59.999/xx:59:59.999，filename E 精度到秒，bounds 上界为下一整/半点，三者精度/端点约定分开保存，不伪造为冲突。bounds 解码继承 parent time 的 calendar，而不是默默改 calendar。详见 native_converted_time_comparison.csv。

另 2 个 Late 子集可读，1 个 2025-11-07 Late 临时文件报 `OSError(-51, NetCDF: Unknown file format)`，见 native_metadata_probes.json。该失败未删除、修复、替代任何文件；Late 不用于 Final 语义结论。

## D. 官方说明

原生产品层面的出处和限度见 [official_source_notes.md](official_source_notes.md) 及 official_sources.csv。官方文档不能代替本地 converter 证据，也不能代替研究者的跨源绑定批准。

## E. Himawari 实际时间字段

nominal_time 来自 `NC_H09_YYYYMMDD_HHMM_...nc` 文件名的排程标签，不能等同 obs_start/obs_end。源变量 start_time/end_time 的 long_name 分别为 observation start/end time，单位 days since 1858-11-17 0:0:0；历史 smoke 保存了真实解码值。本轮只复用这些已通过值和源变量 metadata，没有重跑 reader/model 链。

首 smoke 样本：nominal={rows[0]['nominal_time']}；obs_start={rows[0]['obs_start']}；obs_end={rows[0]['obs_end']}；date_created={rows[0]['date_created']}；candidate_analysis={rows[0]['candidate_analysis_time']}。16 条旧记录只做因果关系复核，全满足 obs_end<=analysis_time；旧文件不修改。

**FROZEN 物理因果约束：obs_end <= analysis_time。** obs_end 超时或不可解析的样本不能被视为已通过因果 gate；不得改时间、选未来帧绕过。date_created 只记录，不作为已证明 operational availability；本轮没有完成历史实时回放。

## F. 候选及边界

b0_time_rule_candidates.csv 明确列出 T=start、T=center、其他 reference、NOT_ESTABLISHED。T=start 受抽样证据支持程度更强，仍不自动选择。T=center 当前没有正面证据，且其候选 analysis 可能不在 10 分钟 nominal 网格上，禁止通过四舍五入静默选帧。各方案都还需批准 analysis 定义和单帧选择规则，并验证真实 obs_end。

The cross-source IMERG-Himawari time binding used in this B0 smoke run is provisional and was used only to test the engineering pipeline. It is not a frozen scientific sample timing convention.

`analysis_time=T+30min; nominal_time=analysis_time-10min` 始终标为 ENGINEERING_SMOKE_TIME_MAPPING_ONLY。没有将 [T,T+30min) 或 end-minus-10min 宣布为正式科研规则。''')

def spatial():
    reg=json.loads((FREEZE/'freeze_registry.json').read_text(encoding='utf-8'))
    z=np.load(FREEZE/reg['artifacts']['coordinates']['relative_path']); lat=z['lat']; lon=z['lon']; z.close()
    h=np.load(RUN/'SPATIAL/himawari_actual_coordinates.npz'); hlat=h['latitude']; hlon=h['longitude']; h.close()
    with netCDF4.Dataset(str(FREEZE/reg['artifacts']['primary_mask']['relative_path']),'r') as nc:
        mask=np.asarray(nc['yunnan_mask'][:],dtype=bool)
        assert np.array_equal(lat,nc['lat'][:]) and np.array_equal(lon,nc['lon'][:])
    assert mask.shape==(130,140) and mask.sum()==3430
    assert coordhash(lat)==reg['mask']['lat_hash'] and coordhash(lon)==reg['mask']['lon_hash']
    # Cross-check real newly read July daily coordinates, not generated coordinates.
    im=next(x for x in readj('TIME/converted_metadata_probes.json') if 'imerg_20240701.nc' in x['source'])['groups']['/']['variables']
    assert np.array_equal(lat,np.asarray(im['lat']['raw_values'],dtype=im['lat']['dtype']))
    assert np.array_equal(lon,np.asarray(im['lon']['raw_values'],dtype=im['lon']['dtype']))
    west,south,east,north=reg['boundary']['bounds']
    requests=[('SP01','Polygon envelope with no added requested margin',(west,south,east,north)),
              ('SP02','Symmetric requested 0.25 degree context',(west-.25,south-.25,east+.25,north+.25)),
              ('SP03','Symmetric requested 0.50 degree context',(west-.5,south-.5,east+.5,north+.5)),
              ('SP04','Full currently audited common coordinate extent',(97.,20.,107.,30.))]
    candidates=[]; actual={}
    for cid,label,(w,s,e,n) in requests:
        # Bracket requested extent with actual native centers, preserving native row order.
        aw=float(hlon[hlon<=w].max()); ae=float(hlon[hlon>=e].min())
        ass=float(hlat[hlat<=s].max()); an=float(hlat[hlat>=n].min())
        hi=np.flatnonzero((hlat>=ass)&(hlat<=an)); hj=np.flatnonzero((hlon>=aw)&(hlon<=ae))
        ti=np.flatnonzero((lat>=ass)&(lat<=an)); tj=np.flatnonzero((lon>=aw)&(lon<=ae))
        assert len(hi)>0 and len(hj)>0 and len(ti)>0 and len(tj)>0
        assert np.all(np.diff(hi)==1) and np.all(np.diff(hj)==1)
        true=int(mask[np.ix_(ti,tj)].sum()); assert true==3430
        native_shape=[len(hi),len(hj)]; target_shape=[len(ti),len(tj)]
        actual[cid]={'native_row_indices':hi.tolist(),'native_col_indices':hj.tolist(),
                     'target_row_indices':ti.tolist(),'target_col_indices':tj.tolist(),
                     'native_lat_hash':coordhash(hlat[hi]),'native_lon_hash':coordhash(hlon[hj]),
                     'target_lat_hash':coordhash(lat[ti]),'target_lon_hash':coordhash(lon[tj])}
        rec=dict(candidate_id=cid,label=label,status='CANDIDATE_ONLY',selected=False,scientific_rule_frozen=False,
            requested_west=w,requested_south=s,requested_east=e,requested_north=n,
            actual_native_west=aw,actual_native_south=ass,actual_native_east=ae,actual_native_north=an,
            margin_west_degrees=west-aw,margin_east_degrees=ae-east,margin_south_degrees=south-ass,margin_north_degrees=an-north,
            native_shape=json.dumps(native_shape),target_shape=json.dumps(target_shape),
            native_rows=len(hi),native_cols=len(hj),target_rows=len(ti),target_cols=len(tj),
            native_lat_direction='descending',target_lat_direction='ascending',lon_direction='ascending',
            native_row_start=int(hi[0]),native_row_stop_exclusive=int(hi[-1]+1),native_col_start=int(hj[0]),native_col_stop_exclusive=int(hj[-1]+1),
            target_row_start=int(ti[0]),target_row_stop_exclusive=int(ti[-1]+1),target_col_start=int(tj[0]),target_col_stop_exclusive=int(tj[-1]+1),
            target_lat_min=float(lat[ti].min()),target_lat_max=float(lat[ti].max()),target_lon_min=float(lon[tj].min()),target_lon_max=float(lon[tj].max()),
            evaluation_true_cells_covered=true,evaluation_total_cells=3430,full_frozen_target_canvas='130x140 remains unchanged',
            native_crop_feasible=True,within_himawari_and_imerg=True,
            padding_policy='NOT_SELECTED; counts hypothetical stride multiples only; no padding applied',
            target_boundary_policy='Target centers inside bbox; does not assert whole target cell footprint inside bbox',
            resampling_method='NOT_YET_FROZEN_NO_RESAMPLING_PERFORMED')
        for stride in (16,32):
            rec[f'native_extra_rows_if_stride{stride}']=(-len(hi))%stride; rec[f'native_extra_cols_if_stride{stride}']=(-len(hj))%stride
            rec[f'target_extra_rows_if_stride{stride}']=(-len(ti))%stride; rec[f'target_extra_cols_if_stride{stride}']=(-len(tj))%stride
        candidates.append(rec)
    table('SPATIAL/b0_input_domain_candidates.csv',candidates)
    writej('SPATIAL/candidate_coordinate_indices.json',actual)
    writej('SPATIAL/frozen_spatial_anchor_verification.json',dict(freeze_registry_sha256=sha(FREEZE/'freeze_registry.json'),
        primary_mask_sha256=sha(FREEZE/reg['artifacts']['primary_mask']['relative_path']),
        lat_hash=coordhash(lat),lon_hash=coordhash(lon),mask_shape=list(mask.shape),true_cell_count=int(mask.sum()),
        actual_imerg_coordinates_equal=True,lat_ascending=bool(np.all(np.diff(lat)>0)),
        source_himawari_lat_descending=bool(np.all(np.diff(hlat)<0)),transpose_applied=False,flip_applied=False,
        coordinates_generated=False,source_arrays_resampled=False,formal_input_bbox=None))
    display='\n'.join(f"|{x['candidate_id']}|{x['actual_native_west']:.6f}–{x['actual_native_east']:.6f}; {x['actual_native_south']:.6f}–{x['actual_native_north']:.6f}|{x['native_shape']}|{x['target_shape']}|{x['evaluation_true_cells_covered']}|" for x in candidates)
    doc('SPATIAL/B0_INPUT_DOMAIN_DECISION.md',f'''# B0 input domain / context decision

**NOT_YET_FROZEN；四个候选均未选择。** 唯一正式评价 mask 仍为 GADM 4.1 Yunnan center-in-polygon，(130,140)，3430 true cells。intersection 3752 保留为非主评价敏感性比较，未替换或修改。

候选先定义 polygon envelope、对称 0.25°、对称 0.50° 或当前全部共同范围，再用**实际 Himawari 坐标向外包围**请求边界。没有 np.arange，没有数组翻转/转置，没有生成降水/温度裁剪数据，没有重采样。目标索引来自已冻结真实 IMERG 坐标，并重新逐值核对 2024-07-01 日文件。源纬度降序，目标纬度升序，需要未来明确的坐标映射；不能把轴方向差异隐式处理掉。

|候选|native 中心坐标包络 E; N|native 行列|target 行列|保留评价 cells|
|---|---|---|---|---|
{display}

pixel shape 指当前坐标中心筛选所得维度，不代表正式模型输入分辨率/插值方案已定。四向 margin 在 CSV 中按 polygon bounds 到实际 native 中心范围计算，单位 degree；经纬度角度 margin 不是相同物理距离，0.25/0.50 只是比较参数，不是天气系统科学尺度。

SP01 基本无额外上下文，边界可受卷积支持不足影响；SP02/03 加入逐级上下文，增加计算量；SP04 使用所有已审计共同范围，四向 margin 不对称，不能把它写成正式 bbox。所有候选均覆盖 3430 个主评价中心。目标子网格不是对正式 (130,140) mask 的替换，未来输出应按记录索引映射回冻结 canvas，仅在主 mask ∩ target-valid 上评价，不能把域外/无效像元记成 0 雨。

输入 native crop 可用连续原始索引切片完成；源整幅为 (501,501)，97–107E / 20–30N。正式对齐方法、缺测传播和边缘支持仍需批准。按中心取点不自动证明目标 cell footprint 完整被输入框覆盖；若日后采用面积聚合/保守重映射，必须检查额外 footprint 支持。

CSV 分别给 stride=16、32 假设下补齐行列数。这里没有选择 U-Net 深度、padding 位置/值/方式或正式分辨率，也没有执行 padding。未来 padding 必须有独立有效性 mask，不能以补零冒充观测。正式架构确认后重算实际尺寸约束。

数据覆盖结论仅沿用已审计 July 2024 Himawari 网格与 IMERG 目标坐标，不声称其余 Himawari 月已通过 QC。`covers_yunnan_context` 的科学充分性仍为 PENDING_RESEARCHER_CONFIRMATION；能覆盖 polygon 不等于足够天气上下文。

生成脚本/坐标/冻结 registry hashes 见 evidence_registry.csv、candidate_coordinate_indices.json 和 frozen_spatial_anchor_verification.json。''')

def split_candidates():
    specs=[('TV01_YEAR_HOLDOUT',[['2023-03-01','2023-11-01']],[['2024-03-01','2024-11-01']],
            '每个角色均完整暖季；跨年评估，训练年偏少','年份变化可检验迁移；2024 全年验证可能偏向该年；不对调 2025','休季隔开相邻块；天气过程跨界风险较小但未用事件目录证实'),
           ('TV02_2024_JUL_OCT',[['2023-03-01','2023-11-01'],['2024-03-01','2024-07-01']],[['2024-07-01','2024-11-01']],
            '按完整连续月份；同年验证偏向后半雨季','训练样本较多；Val 的季节/极端事件代表性须评审','2024-07-01 紧邻分界，强制研究者选择 buffer 或完整过程隔离方案'),
           ('TV03_BOTH_OCTOBERS',[['2023-03-01','2023-10-01'],['2024-03-01','2024-10-01']],[['2023-10-01','2023-11-01'],['2024-10-01','2024-11-01']],
            '训练各年 March–September；验证两个完整 October','训练季覆盖较多，验证仅 October 有强季节偏差；不代表全年验证','两处 October 1 紧邻分界，跨界天气过程须整体分配或设置批准的 purge')]
    month=pd.read_csv(CONT/'CROSS_SOURCE/research_period_data_matrix.csv')
    inv=pd.read_csv(P0/'IMERG/imerg_inventory.csv'); available=set(inv['date'])
    full=[]; flat=[]
    for cid,tr,va,continuity,tradeoff,risk in specs:
        c=dict(candidate_id=cid,train_blocks=tr,validation_blocks=va,status='CANDIDATE_ONLY',selected=False,
               interval_convention='UTC [start,end_exclusive)',final_test_year=2025,
               buffer_hours_selected=None,weather_event_catalog='NOT_ESTABLISHED',formal_sample_index_created=False)
        validate_split(c)
        counts={}
        for role,blocks in [('train',tr),('validation',va)]:
            days=[]
            for a,b in blocks:
                current=date.fromisoformat(a); stop=date.fromisoformat(b)
                while current<stop: days.append(current.isoformat()); current+=timedelta(days=1)
            assert len(days)==len(set(days))
            counts[role+'_calendar_days']=len(days); counts[role+'_nominal_halfhour_slots']=len(days)*48
            counts[role+'_imerg_inventory_days']=sum(d in available for d in days)
        c.update(counts); full.append(c)
        flat.append(dict(candidate_id=cid,status=c['status'],selected=False,scientific_rule_frozen=False,
            train_time_blocks=json.dumps(tr),validation_time_blocks=json.dumps(va),**counts,
            estimate_scope='Unbuffered upper bound, before missing/QC/causal alignment; NOT usable sample count',
            joint_usable_train_samples='NOT_ESTABLISHED',joint_usable_validation_samples='NOT_ESTABLISHED',
            continuity=continuity,boundary_leakage_risk=risk,advantages_and_limitations=tradeoff,
            buffer_options='No default: event-complete separation OR researcher-approved symmetric time purge; duration NOT_YET_FROZEN',
            adjacent_random_split_allowed=False,weather_event_isolation='Feasible only after independent event labels and boundary-crossing checks; not yet performed',
            data_coverage='IMERG inventory complete 2023/2024 Mar-Oct; Himawari July2024 partial 4390/4464, other23 research months NOT_AUDITED',
            final_test='2025-03-01 to 2025-11-01 exclusive; October Final missing; no tuning',formal_assignment_created=False))
    writej('SPLIT/candidate_blocks.json',full); table('SPLIT/b0_train_val_candidates.csv',flat)
    planned=245*48; actual214=214*48
    writej('SPLIT/period_count_bounds.json',{'development_days':490,'development_slots_upper_bound':490*48,
        'final_test_planned_days':245,'final_test_planned_slots':planned,'final_test_inventory_days':214,
        'final_test_inventory_slots_upper_bound':actual214,'missing_october_days':31,'missing_october_slots':31*48,
        'formal_usable_samples':'NOT_ESTABLISHED','statistics_fitted':False})
    display='\n'.join(f"|{c['candidate_id']}|{c['train_calendar_days']} / {c['train_nominal_halfhour_slots']}|{c['validation_calendar_days']} / {c['validation_nominal_halfhour_slots']}|" for c in full)
    doc('SPLIT/B0_TRAIN_VAL_DECISION.md',f'''# B0 Train / Validation block candidates

FROZEN 大框架：Development=2023、2024 每年 March–October；Final Test=2025 March–October。具体 Train/Val blocks、边界 purge/buffer、事件分组和调参协议 **NOT_YET_FROZEN**。本轮仅候选时间区间，不生成正式 sample index 或执行 split，不随机拆相邻 30 分钟样本。

|候选|Train 天数 / 名义 30min 槽位|Validation 天数 / 名义槽位|
|---|---|---|
{display}

区间为 UTC [start,end_exclusive)，见 CSV/JSON。TV01 为跨年 holdout；TV02 为连续晚雨季 holdout；TV03 为两年 October holdout，后者季节偏差明显。每个候选优缺点和跨界事件风险已逐行列出，无 winner。

估计只按历法天数×48，并对照旧 IMERG inventory 有文件的天数，不读取全库数组，也不推定所有时刻有有效标签。Development 490 天、23520 个名义槽位；Final Test 245 天、11760 个计划槽位，其中已登记 214 天、10272 个上界槽位，October 缺 31 天 / 1488 槽。不能把 10272 个槽声称为真实可用 Test 样本。跨源时间绑定、Himawari 缺帧、valid-mask/QC 后的联合样本数均 NOT_ESTABLISHED。

Himawari 当前只有 2024-07 全月工程审计（4390/4464 文件，有缺口）；其他研究月份不能把 NOT_AUDITED 写成 MISSING 或 PASS。未执行新的多月审计。

天气过程隔离需要独立事件目录及跨分界核查；现无已批准事件划分。研究者可选择完整过程归属或固定时长 purge；具体小时数和双侧/单侧规则尚未设定，不以任意 24/48 小时作为已批准阈值。上表**尚未扣 buffer**。B0 单帧不要求六帧全部存在，但未来共享 sample index 时不得让同一输入/标签或事件跨 Train/Val。所有统计、筛选、阈值选择和模型选择只在已批准 Development/Train/Val 内完成，2025 不参与。

2025 October 缺口单独交研究者决定，不能借 split 方案自动把正式研究期缩短。''')

def contracts():
    contract=dict(contract_version='B0_FORMAL_CONTRACT_CANDIDATE_v1',status='CANDIDATE_ONLY',
      formal_training_enabled=False,formal_ready=False,
      inputs=['Himawari_B13'],single_time=True,additional_model_input_channels_approved=False,
      prohibited_required_inputs=['GFS','GFS_thermo','GFS vintage','DEM','DOTE','DTFM','MEE','ERA5 Teacher'],
      final_test_year=2025,research_months=list(range(3,11)),development_years=[2023,2024],
      timing={'scientific_rule_frozen':False,'smoke_mapping_status':'ENGINEERING_SMOKE_TIME_MAPPING_ONLY',
              'causal_constraint':'obs_end <= analysis_time','date_created_role':'RECORD_ONLY',
              'operational_replay_established':False},
      spatial={'evaluation_mask_frozen':True,'mask_shape':[130,140],'mask_true_cells':3430,
               'model_input_bbox_frozen':False,'formal_model_input_bbox':None,'context_margin_frozen':False,
               'covers_yunnan_context':'PENDING_RESEARCHER_CONFIRMATION','alignment_method_frozen':False},
      qc={'rain_zero_is_valid':True,'missing_equals_zero':False,'interpolation_allowed':False,
          'formal_thresholds':None,'valid_target_rule':'finite AND not declared fill/missing; metadata decoding before checks',
          'all_fill_rule':'No valid B13 observation; cannot become valid through fill or interpolation',
          'partial_acceptance':'RESEARCHER_DECISION_REQUIRED','missing_frame_fallback':'NOT_APPROVED',
          'sequence_metadata_preserved':True,'six_frame_completeness_required_for_B0':False},
      normalization={'rule_defined':True,'scientific_method_frozen':False,'fit_roles':['Train'],
          'forbidden_fit_roles':['Validation','Test'],'missing_mask_required':True,'exclude_invalid_from_fit':True,
          'real_zero_is_observation':True,'fitted':False,'parameters':None,'method':'NOT_YET_FROZEN',
          'test_feedback_allowed':False,'versioning_required':True},
      architecture={'scientific_rule_frozen':False,'family_requirement':'U-Net / GPROF-IR-style baseline',
          'probability_head':'RESEARCHER_DECISION_REQUIRED','deterministic_default':False,'loss_protocol_frozen':False,
          'smoke_architecture_is_formal':False},
      split={'scientific_rule_frozen':False,'random_adjacent_split_allowed':False,'formal_split_executed':False},
      gap={'imerg_2025_10_status':'MISSING','product_substituted':False,'research_period_changed':False})
    writej('DATA_CONTRACT/b0_contract_candidate.json',contract)
    doc('DATA_CONTRACT/b0_missing_qc_contract_candidate.md','''# B0 missing / QC contract candidate

状态：工程语义已定义；完整正式接受/剔除与 loss mask 协议仍 RESEARCHER_DECISION_REQUIRED。

## FROZEN — 继承明确规则

- 输入为单时次 Himawari B13，原始文件永久只读；obs_end<=analysis_time 是硬因果约束，未来帧不允许进入。
- IMERG 真实 0 是无雨有效值，0 != missing；NaN、元数据 _FillValue/missing_value 和 masked pixels 保留独立布尔有效性语义。不得填成 0、插值、造值或以未来帧代替。
- 源 B13 按已有 packed metadata 解码，保留原 dtype、scale/add_offset、valid_min/max 与 missing_value。样本 int16 missing_value=-32768；scale≈0.01，offset≈273.15 K。元数据有效范围与新科研阈值不同；不能凭经验新增温度或雨量阈值。未来 metadata 改变须显式记录并审查。
- 冻结评价域为正式 center-in-polygon mask（3430），不是矩形全部 pixels。intersection 仅敏感性比较。

## PROVISIONAL — 整理工程状态，不新设阈值

|状态|工程含义|正式处置边界|
|---|---|---|
|B13 all_fill|解码后无有效 B13 观测|不能伪造为有效输入；保留拒绝/原因 metadata，计数分母与采样处置需批准|
|B13 partial|存在有效与无效像元|记录 invalid count/fraction；不得默认删整帧或默认填补|
|missing frame|已批准 nominal 位置无文件|记录缺帧；当前无授权 fallback，不静默替换帧|
|B13 invalid pixel|NaN/masked/declared fill或源 metadata 有效范围之外|保留 invalid mask；正式模型接收方式未定|
|IMERG target invalid|非有限数或 declared fill/missing|不得作真实 0；训练/评价不当作有效监督|
|IMERG target 0|有限且不等于 declared fill|保持有效，不因无雨被掩掉|

即使 B0 单帧，仍保留既有 sequence ID/slot availability、逐帧 QC、缺口/时间异常 metadata 以便溯源；不把六帧 completeness 当作 B0 接纳硬条件。creation_delay原值保留，date_created只记录。latency_tail_review 的 p99 只是分布尾部检查标记，不是排除条件、QC阈值或科学阈值；TEMPORAL_ORDER_ERROR 与 LATENCY_TAIL_REVIEW 分开，不删除/修改原始文件。

## RESEARCHER_DECISION_REQUIRED

partial-frame 可用比例/分布标准（本轮不提供新数值阈值）；无效输入的模型 mask 接口、是否整体拒绝、loss reduction 的有效分母；label validity 与 evaluation mask 的组合；重采样时缺测传播；训练域监督与主评价域的区分；missing-frame 的正式 causal fallback 是否允许；跨月 QC 扩展与严重时间异常接受策略。

若批准模型内部的 padding 或数值占位，必须保留有效性 mask，并明确占位不代表观测 0；当前未批准此策略。训练和评价的 target-invalid 像元不得进入有效监督/指标分母，但具体 normalization/loss reduction 未定。不能用 synthetic contract unit tests 冒充真实全月/全研究期 QC 已完成。

FROZEN 只表示明确继承的语义约束，不表示本候选文档整体已成为正式完整 QC 配置。''')
    doc('DATA_CONTRACT/b0_normalization_contract.md','''# B0 Train-only normalization contract

normalization_rule_defined=true 表示本轮已把用户要求的防泄漏范围规则写成可检查 contract；不表示 estimator、训练统计值或参数已冻结。scientific_method_frozen=false；statistics_computed=false；parameters=null。

## 未来必须遵守的范围

1. 正式 Train blocks、时间/空间/QC 和统计域批准后，只允许其 Train 样本拟合 B13 normalization。Validation、2025 Test 和未归属数据不得参与任何 fitted statistics。
2. 先按源 metadata 解码并提取 missing mask，排除 invalid、padding 和占位值；保持真实有效观测。布尔 mask 与输入同索引，不能把 missing 视作 0 来计算统计量。IMERG 无雨 0 不因数值为 0 被当作 missing；本轮未定义 label transform。
3. 保存方法、参数、dtype、单位、通道、Train区间/正式 sample index hash、bbox/坐标hash、QC/valid-mask policy、计数/权重语义、软件/脚本 hash、版本和创建时间；禁止静默覆盖参数版本。
4. Validation/Test 只应用已拟合的 Train 参数；Test 不得反向选择 estimator、clipping、阈值、统计域或重新拟合。Train 规则变动应产生新版本并重新验证，不读取 Test 结果来调参。

## 待研究者决定

mean/std、稳健变换或物理固定尺度等方法如何选择；按 native/target grid、主 mask/context 的统计域；像元/时次/天气过程权重；partial 样本计数；极端值与常量通道的处理。这里只列选择维度，无默认公式或新阈值。若最终选固定物理尺度，同样版本化，且不能据 Test 调整。

工程测试只检查角色访问控制与 missing mask 语义，**未计算正式或全数据 mean/std，也未扫描真实数值求分布参数**。''')
    doc('MODEL/B0_FORMAL_ARCHITECTURE_DECISION.md','''# Formal B0 architecture requirements

要求范围：single B13、single time，U-Net / GPROF-IR-style baseline，输出与冻结 IMERG 目标坐标显式对齐。输入不包含 GFS、GFS_thermo、GFS vintage、DEM terrain、DOTE、DTFM、MEE 或 ERA5 Teacher；不能把这些后续阶段模块当作 B0 必需入口。

正式层数、通道宽度、下采样倍率、padding、native-to-target 对齐/缺测传播、输出支持范围均 NOT_YET_FROZEN。旧 smoke small U-Net 仅证明工程链可运行，单确定性输出不构成正式 B0 deterministic regression 的批准。

需要研究者决定：第一版 B0 是否含概率头；若含，采用哪类概率表示（例如待评估的分位数或显式概率分布）；若先做确定性对照，也须明确其仅为经批准的对照角色以及与总体概率目标的关系。本轮无默认选项。输出非负性/无雨表示、极端阈值、概率一致性、loss、valid-mask reduction、评价与模型选择指标、随机种子/重复次数和校准协议，均需与 Train/Val 设计共同批准。

概率/确定性选项不是本轮性能推荐，也未下载源码、调用外部模型或训练。GPROF-IR-style 仅描述 baseline 家族，不声称已复现任何论文的全部配置。最后输出要对齐目标 lat/lon；裁剪候选不得改变正式云南 mask 或将 invalid/padding 计入评价。

B0 工程 smoke 保持 PASS。正式 architecture/loss/output 冻结状态仍 false。本轮没有重复 Dataset、DataLoader、forward/backward、optimizer、checkpoint 或 inference 验证。''')
    return contract

def gap_report():
    g=readj('GAPS/october_presence.json'); disc=readj('logs/discovery_summary.json')
    assert len(g['late_october_files'])==31
    doc('GAPS/IMERG_2025_10_DECISION_CARD.md',f'''# IMERG 2025-10 decision card

**IMERG V07 Final 2025-10 = MISSING，未补齐。** 研究期仍为 2023–2025 March–October，2025 Final Test 不变。

## Current evidence

用户追加授权扩大全盘搜索。C、D、E、F、G、H 盘共检查 {disc['directories']} 个目录、{disc['files_names_seen']} 个文件名，登记 {disc['matched_names']} 条候选名称；{disc['access_errors']} 个访问错误、{disc['skipped_directories']} 个主动跳过目录。完整错误与跳过目录在 logs/volume_*.json，规则见 src/discover.py；跳过系统/环境目录、链接和本轮输出目录。它不是所有字节/任意命名/压缩包内容的穷尽搜索；**未找到不等于全盘绝对不存在**。

对已知 Final root 的 2025 年目录进行 October 名称定向检查，0 个文件。发现 `raw/IMERG_LATE/2025` 的 31 个 October 日文件和 1 个 smoke 同名文件。抽查 2025-10-01 global title/source 明确为 Late / GPM_3IMERGHHL_07；它们不满足 V07 Final 要求，不替代、不合并、不重新命名。

已登记备份 archive 为 2021–2024 年 IMERG tar.gz，备份 manifest 未指向 2025 Final archive。本轮未打开压缩包成员，也未读取全库降水数组。未识别任意改名或嵌套压缩包中的可能数据，这项搜索范围限制明确保留。

原 completion manifest 记录 2026-09-25 的 2025-10-01 Final 请求失败，错误为 No matching granules found；这是当时请求历史，**不能推出官方永久无该数据或现在无法下载**。本轮未联网请求数据、未修复旧下载任务。

## Options

- **A**：研究者批准后补齐同版本 IMERG V07 Final 2025-10，再审计产品身份、48-slot完整性、native bounds、坐标和QC；保持原研究期。
- **B**：研究者显式修改正式时间范围，记录新版本与比较公平性影响；绝不自动缩至 March–September。
- **C**：其他研究者提出的科研方案，先说明目标、可比性和产品一致性，再显式批准；不默认允许 Late/Early 替换。

## Consequences

当前完整 2025 Final Test 有 31 天 / 1488 名义槽位缺口。科学处理方案必须在正式入口前明确。本轮不下载、不改变研究期、不采用产品替代。''')

def matrix_and_cards(contract):
    specs=[
      ('formal_time_binding',False,False,False,True,'TIME/B0_FORMAL_TIME_SEMANTICS_EVIDENCE.md','原转换链未闭合，analysis/单帧绑定待批准'),
      ('imerg_2025_10',True,False,False,True,'GAPS/IMERG_2025_10_DECISION_CARD.md','Final 缺 31 天；Late 不替代；缺口处置未批准'),
      ('model_input_bbox',True,False,False,True,'SPATIAL/B0_INPUT_DOMAIN_DECISION.md','4 个工程候选无正式选择'),
      ('weather_context_margin',True,False,False,True,'SPATIAL/b0_input_domain_candidates.csv','科学上下文充分性尚未批准'),
      ('train_blocks',True,False,False,True,'SPLIT/B0_TRAIN_VAL_DECISION.md','Train blocks、buffer、事件隔离未批准'),
      ('validation_blocks',True,False,False,True,'SPLIT/B0_TRAIN_VAL_DECISION.md','Val blocks 与模型选择设计未批准'),
      ('final_test_rule',True,True,True,False,'SPLIT/period_count_bounds.json','规则层面 PASS；2025 March–October；数据缺口另列'),
      ('missing_qc',True,False,False,True,'DATA_CONTRACT/b0_missing_qc_contract_candidate.md','partial、有效分母及输入缺测处置尚未批准'),
      ('train_only_normalization',True,False,False,True,'DATA_CONTRACT/b0_normalization_contract.md','Train-only 范围已定义；方法/统计域未批，未拟合'),
      ('b13_reader',True,True,True,False,str(SMOKE/'B0_SMOKE/himawari_b13_reader_report.md'),'reader 工程接口复用旧 PASS；不代表所有月份数据通过'),
      ('target_grid',True,True,True,False,'SPATIAL/frozen_spatial_anchor_verification.json','真实 IMERG lat/lon 与冻结坐标逐值相等'),
      ('yunnan_evaluation_mask',True,True,True,False,str(FREEZE/'freeze_registry.json'),'GADM4.1 center-in-polygon; 130x140; 3430; 哈希一致'),
      ('formal_b0_architecture',True,False,False,True,'MODEL/B0_FORMAL_ARCHITECTURE_DECISION.md','只建立要求，正式配置及概率头第一版待批准'),
      ('formal_loss_output_protocol',False,False,False,True,'MODEL/B0_FORMAL_ARCHITECTURE_DECISION.md','损失、输出、校准、指标/重复设计尚未批准'),
      ('formal_spatial_alignment',True,False,False,True,'SPATIAL/B0_INPUT_DOMAIN_DECISION.md','smoke nearest gather 不等于正式对齐；重采样/缺测传播未批准'),
      ('multi_month_himawari_qc',False,False,False,True,str(CONT/'CROSS_SOURCE/research_period_data_matrix.csv'),'除2024-07外研究月 NOT_AUDITED；待正式规则批准后安排数据资格验证')]
    entries=[]
    for item,eng,sci,data,decision,evidence,reason in specs:
        passed=eng and sci and data and not decision
        entries.append(dict(item=item,engineering_ready=eng,scientific_rule_frozen=sci,data_ready=data,
                            researcher_decision_required=decision,status='PASS' if passed else 'BLOCKED',
                            evidence=evidence,blocking_reason='' if passed else reason,
                            scope_note=reason if passed else 'Engineering-ready means evidence/contract preparation only; NOT formal execution-ready'))
    assert not formal_gate(entries)
    table('B0_FORMAL_ENTRY_MATRIX.csv',entries)
    writej('DATA_CONTRACT/entry_matrix_machine.json',entries)
    cards=[
      ('01_formal_time_binding','Formal time binding','TIME/B0_FORMAL_TIME_SEMANTICS_EVIDENCE.md',
       '批准 T/native window/analysis_time 的科学关系及单帧选择规则。',
       '9 个 Final 原生时间坐标等于 bounds 下界，日文件时刻相等；原 converter 缺失；smoke 仍 provisional。',
       'T=start 并经证据补强后批准；T=center 需新增证据；从独立 native bounds 映射；证据不足保持 NOT_ESTABLISHED。',
       '改变标签窗、可用卫星槽和问题定义；不能把时间一致性等同在线可用性。',
       'obs_end<=analysis_time；不得未来帧；date_created 不作 availability。'),
      ('02_2025_10_imerg','IMERG October gap','GAPS/IMERG_2025_10_DECISION_CARD.md',
       '决定如何处理同版本 Final 2025-10 缺口。','定向目录和扩大文件名搜索未发现 Final；31 个日文件是 Late。',
       'A 批准补齐 V07 Final；B 明确修订研究期；C 其他研究者方案。','完整2025 Test缺31天，处理影响比较范围。',
       '2023–2025 March–October；2025 Final Test；当前不替代产品。'),
      ('03_model_input_bbox','Model input bbox','SPATIAL/B0_INPUT_DOMAIN_DECISION.md',
       '在 SP01–SP04 或另行论证范围中选正式输入域，并批准坐标对齐。','4 候选均在实际坐标共同范围并覆盖3430主评价中心。',
       'polygon包络附近、0.25°/0.50°请求margin、全共同坐标范围，或提出新候选重新检查。','形状、计算量和边界输入支持不同；全范围不是自动默认。',
       '主评价 mask 和真实目标网格不改变。'),
      ('04_context_margin','Weather-system context','SPATIAL/b0_input_domain_candidates.csv',
       '确定天气系统上下文尺度及对称/非对称依据。','CSV四向角度margin可算；科学充分性未证实。',
       '对称角度候选、按可用覆盖非对称候选、提出物理距离/天气过程准则后重审。','角度相同不等于物理距离相同，context增加成本且可能影响泛化。',
       '云南全境主评价，不以context改变评价区域。'),
      ('05_train_val_blocks','Train / Validation design','SPLIT/B0_TRAIN_VAL_DECISION.md',
       '选择完整块、边界buffer/事件隔离和Validation调参协议。','3候选无重叠且仅2023/24；样本数是未扣QC/buffer上界。',
       'TV01跨年；TV02晚季；TV03双October；或批准完整天气过程方案。','各有年份/季节代表性风险；无事件目录不能声称事件隔离已完成。',
       'Development2023/24 March–October；FinalTest2025不调参；不随机拆相邻样本。'),
      ('06_missing_qc','Missing and QC','DATA_CONTRACT/b0_missing_qc_contract_candidate.md',
       '批准partial-frame/invalid-input策略、target有效性与loss/metric分母。','元数据解码、0!=missing等工程语义已确定；无新阈值。',
       '显式mask接口或经批准的样本拒绝策略；新QC阈值须另有科学依据。','改变样本组成及有效监督面积；不可用隐式填零影响无雨频率。',
       '0为有效无雨；missing不造值；原始数据只读；物理因果约束。'),
      ('07_formal_b0_architecture','Formal architecture','MODEL/B0_FORMAL_ARCHITECTURE_DECISION.md',
       '批准正式U-Net/GPROF-IR-style配置，明确第一版概率头。','small U-Net smoke PASS仅工程证据，无正式架构批准。',
       '概率B0第一版（表示待选）；或明确批准确定性对照角色；层宽/深度/padding一并记录。','输出定义影响loss、概率评价与总体方案对照关系。',
       'single B13, single time, target-grid aligned；不引入GFS/DEM等后续模块。'),
      ('08_normalization','Normalization','DATA_CONTRACT/b0_normalization_contract.md',
       '批准Train-only范围内的方法、统计域、权重与版本规范。','范围规则已定义；没有任何真实拟合统计。',
       '经批准后采用标准化/稳健方法或物理固定尺度；当前无选择。','统计域和无效像元处理会改变模型输入分布。',
       'Val/Test不参与拟合，Test不能反向调参；invalid排除且版本化。'),
      ('09_loss_output_and_alignment','Loss/output and spatial alignment','MODEL/B0_FORMAL_ARCHITECTURE_DECISION.md',
       '批准正式loss/output、native-target对齐、missing传播、指标、概率校准和重复实验方案。','smoke对齐与单输出仅工程候选，无正式批准。',
       '随架构科学目标联合选择，不指定默认loss/插值/阈值。','决定学习目标、网格支持和可比性，不能据2025挑选。',
       '目标真坐标与主mask不改变；Test不调参；不以未来信息输入。'),
      ('10_monthly_data_qualification','Multi-month data qualification',str(CONT/'CROSS_SOURCE/research_period_data_matrix.csv'),
       '正式规则明确后，批准后续多月数据资格验证范围和缺口处置。','2024-07 Himawari审计完成但有缺帧；其他研究月NOT_AUDITED。',
       '按正式规则分月只读验证；根据真实缺口再提交决策；不预先认定丢失。','名义calendar槽位不是实际可训练样本。',
       '本轮不启动全量处理或训练，不把NOT_AUDITED当PASS。')]
    for name,title,link,decision,evidence,options,consequence,frozen in cards:
        doc(f'DECISIONS/{name}.md',f'''# {title}

## Decision required

{decision}

## Current evidence

{evidence} 证据：{link}

## Options

{options}

## Consequences

{consequence}

## What is already frozen

{frozen}

## What must not be changed automatically

不自动选择候选，不改旧Stage-0/smoke证据，不修改原始数据；不新增科学阈值，不据Test调参，不运行正式训练。任何新科研约定需研究者显式批准并新建可追溯版本。
''')
    doc('RESEARCHER_DECISIONS_REQUIRED.md','# Researcher decisions required\n\nB0_FORMAL_NOT_READY。以下决策尚无批准，不以工程测试通过代替。\n\n'+
        '\n'.join(f'- [{title}](DECISIONS/{name}.md)：{decision}' for name,title,link,decision,*rest in cards)+
        '\n\n已冻结：研究期大框架及2025Test；真实IMERG目标网格；GADM4.1云南主mask；物理因果与missing语义。未冻结：上述具体时间/空间/分块/QC/归一化方法/模型与输出协议。GFS/DEM及后续模块不列为B0输入blocker。')
    return entries

def main():
    for name in ['TIME','GAPS','SPATIAL','SPLIT','DATA_CONTRACT','MODEL','DECISIONS','tests','PROVENANCE']:
        (RUN/name).mkdir(exist_ok=True)
    # Immutable source snapshot for this run; no rewriting existing script evidence.
    for p in WORK.glob('*.py'):
        dest=RUN/'src'/p.name
        if dest.exists() and sha(dest)!=sha(p):
            # Preserve the prior snapshot even for harmless CRLF/encoding differences.
            dest=RUN/'src'/(p.stem+'_'+sha(p)[:12]+p.suffix)
        if not dest.exists(): shutil.copyfile(p,dest)
    provenance(); time_evidence(); spatial(); split_candidates(); contract=contracts(); gap_report(); entries=matrix_and_cards(contract)
    table('DISCOVERY/file_name_candidates_dual.csv',list(csv.DictReader((RUN/'DISCOVERY/file_name_candidates.csv').open(encoding='utf-8-sig'))))
    writej('logs/build_validation.json',{'completed':True,'steps':['provenance','native/converted time evidence','spatial actual-coordinate candidates','nonoverlapping development split candidates','candidate contracts','entry matrix and decision cards'],
                                      'step_assertions_passed':True,'entry_matrix_rows':len(entries),'formal_blockers':sum(x['status']!='PASS' for x in entries),
                                      'training_started':False,'datasets_or_model_executed':False})
    print('BUILD_COMPLETE',len(entries),'entry rows',sum(x['status']!='PASS' for x in entries),'blockers',flush=True)

if __name__=='__main__': main()
