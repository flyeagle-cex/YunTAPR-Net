"""Structured dependency assessment and researcher-facing package rendering."""
from pathlib import Path
import csv, json, io, subprocess, sys
import xml.etree.ElementTree as ET
import importlib.metadata as md

def render(g):
 facts=json.loads((g.OUT/'EVIDENCE/collected_facts.json').read_text(encoding='utf-8'))
 if facts['fingerprint_conflicts']:raise RuntimeError('Evidence conflicts require investigation; no automatic truth selection')
 oldrefs=list(csv.DictReader((g.OUT/'evidence_registry.csv').open(encoding='utf-8-sig')))
 refmap={r['evidence_id']:r for r in oldrefs}
 def link(eid):
  r=refmap[eid];return f"[{eid}]({r['source_file'].replace(chr(92),'/')})"
 def links(ids):return '; '.join(link(e) for e in ids)
 frozen=[]
 def f(id,rule,scope,ids):frozen.append(dict(id=id,status='FROZEN',rule=rule,scope=scope,evidence_ids=ids,approval_evidence=['CURRENT_REQUEST'] if id not in ['F01','F02','F03','F04','F05','F10','F11'] else ['SPATIAL_APPROVAL','CURRENT_REQUEST']))
 f('F01','研究对象为云南省全境','科学研究空间原则',['SPATIAL_APPROVAL','FREEZE'])
 f('F02','主评价使用云南省行政区 mask','评价范围，不是矩形输入域',['FREEZE'])
 f('F03','GADM 4.1 China Level-1 / CHN.30_1；五身份字段同时确认','固定本地归档及其 hash；不得静默更换版本；未声称有新的官方获取凭据',['FREEZE','SPATIAL_APPROVAL'])
 f('F04','center-in-polygon；3430 true / 14770 false','PRIMARY_EVALUATION；intersection 3752 格仅作 sensitivity comparison',['FREEZE','RUN_freeze'])
 f('F05','真实 IMERG 130×140 lat/lon；latitude ascending','保留 float32 原坐标、逐值一致与坐标 hash；不重建坐标，不 flip/transpose',['FREEZE','IMERG_GRID'])
 f('F06','当前审计 IMERG V07B Final metadata；48 帧/日、30 min、约 0.1°','已批准采用的源身份/工程事实；不扩展为 native half-hour exact window 已证实',['RUN_p0','CONVENTIONS'])
 f('F07','0 mm/hr 为有效无雨；missing 不得当 0','缺测显式 mask；不得自动插值、填零或制造观测',['CONVENTIONS'])
 f('F08','Himawari 七通道 08/09/10/11/13/15/16；六个 causal nominal slots；obs_end <= analysis_time','七通道/六槽用于相应阶段；B0 仅 B13 单时次。槽位 −10/−20/−30/−40/−50/−60 min；与 IMERG 的正式绑定另待决',['CONVENTIONS','RUN_p0'])
 f('F09','NO_GFS_PRECIPITATION_USED_AS_MODEL_INPUT','禁止降水累积/降水率 predictor；PWAT 为整层水汽，不是降水 predictor',['RUN_continuous','CONVENTIONS'])
 f('F10',r'DEM 主来源 F:\云南极端降水数据\raw\SRTM','237 文件，对已冻结云南 polygon FULL；AWS_Skadi 独立，不拼接',['FREEZE','DEM_COVERAGE'])
 f('F11','DOTE dh/dx、dh/dy 必须基于真实物理距离','仅物理原则；DEM 聚合、地形参数与生产流程未冻结',['FREEZE','SPATIAL_APPROVAL'])
 f('F12','F/H 原始科研数据及既有审计 run 只读','历史 DRY_RUN_FAILED、报告与诊断 cache 均保留',['CONVENTIONS','CURRENT_REQUEST'])
 f('F13','surface pressure 支持未来 pressure-level physical validity feasibility','仅已有 PS/层压单位可比的可行性事实；未冻结或生产像元有效性 mask',['REPORT_continuous','REPORT_thermo','CURRENT_REQUEST'])
 f('F14','p99 is a distribution-tail review marker only; it is not an exclusion criterion, QC threshold, or scientific threshold.','44 LATENCY_TAIL_REVIEW 不作排除；TEMPORAL_ORDER_ERROR 独立判断；creation delay 原值保留',['RUN_p0','CONVENTIONS'])
 f('F15','2025 final test；2023–2024 development pool','V1.3 框架，候选每年 March–October 保留；具体 Train/Val 连续块未定，未执行 split',['CURRENT_REQUEST','CONVENTIONS'])
 f('F16','IMERG QI 仅 QC_STAT_ONLY，不作为 predictor','本轮不引入 QI 科学阈值或筛样规则',['CONVENTIONS','SCHEMA'])
 gaps=[]
 def gap(id,kind,item,status,detail,ids,confirmed=True):gaps.append(dict(id=id,classification=kind,item=item,status=status,confirmed_gap=confirmed,detail=detail,evidence_ids=ids))
 gap('G01','HARD_DATA_GAP','IMERG 2025-10','MISSING','候选 2025-03~10 final test 缺 31 日；不可自动缩短到 September。',['OCTOBER','RUN_p0'])
 gap('G02','DATA_COVERAGE_GAP','GFS main 研究期六层 T/RH','MAIN_ROOT_MISSING_COMPANION_CANDIDATE_COMPLETE','主库缺所需 T/RH；thermo 有 8820/8820 structural complete 对。缺口限主来源，未批准 integration。',['REPORT_continuous','THERMO_RESEARCH'])
 gap('G03','DATA_COVERAGE_GAP','Himawari 2024-07 nominal slots','PARTIAL','4390/4464，74 个名义时次未覆盖；六帧候选 4020 complete /444 incomplete。B0 单帧不可直接用六帧完整性剔除。',['RUN_himawari','RESEARCH_MATRIX'])
 gap('G04','METADATA_EVIDENCE_GAP','IMERG native exact half-hour window','PROVISIONAL','converted CF time 已验证；native 窗口起止及 analysis_time 绑定仍未完全建立。',['SCHEMA','CONVENTIONS'])
 gap('G05','METADATA_EVIDENCE_GAP','GFS operational release / historical vintage','NOT_ESTABLISHED','2026 retrospective acquisition 仅 PARTIALLY_ESTABLISHED，不能证明 2023–2025 contemporaneous availability。',['RUN_provenance'])
 gap('G06','SOURCE_PROVENANCE_GAP','GFS main/thermo acquisition-conversion-content chain','SUPPORTED_WITH_CAVEATS','原始内容/转换过程证据链未闭合；不能把 token/grid/time 一致升级成全部来源认证。',['RUN_provenance','REPORT_provenance'])
 gap('G07','METADATA_EVIDENCE_GAP','Himawari operational availability','NOT_ESTABLISHED','date_created 是 product/file creation timestamp；不是已验证 operational availability。',['RUN_p0','REPORT_himawari'])
 gap('U01','DATA_COVERAGE_GAP','独立外部验证','NOT_AUDITED','这是准备状态未知，不是已证明数据缺失。既有材料未建立可用独立验证集，不扫描/下载来补齐。',['RESEARCH_MATRIX','CONVENTIONS'],False)
 gap('U02','DATA_COVERAGE_GAP','Himawari 其余 23 个研究月份','NOT_AUDITED','只有目录证据；未证明缺文件，也未证明 READY。未来正式样本生产前需完成其选定范围工程验证。',['RESEARCH_MATRIX'],False)
 decisions=[]
 def d(id,title,category,stage,formal,full,why,current,options,eng,sci,defer,rec,ids,b4=False,terrain=False,paper=False,decision=True):
  decisions.append(dict(id=id,decision=title,category=category,due_stage=stage,blocks_smoke=False,blocks_formal=formal,blocks_full_stage0=full,required_before_B4=b4,required_before_B5_B8=terrain,required_before_final_paper=paper,requires_researcher_decision=decision,status='RESEARCHER_DECISION_REQUIRED' if decision else 'INFORMATIONAL_REVIEW_ONLY' if category=='D' else 'ENGINEERING_EVIDENCE_REQUIRED',why=why,current_evidence=current,options=options,engineering_consequence=eng,scientific_consequence=sci,if_deferred=defer,recommendation=rec,evidence_ids=ids))
 d('D01','2025-10 IMERG 缺月处理','B','BEFORE_B0_FORMAL',True,True,
   '完整 2025-03~10 final test 目前不可构建。','2465 日截止 2025-09-30，定向 October 计数 0。',
   '补齐同标准数据后验证；或由研究者显式批准研究期/测试协议修订并说明可比性；本轮不选择。',
   '现有月份可支持工程链路；完整正式测试 Dataset 保持 HOLD。','擅自删 October 会改变季节覆盖及测试问题。','smoke 可单独进入；完整正式实验与 full scientific closeout 仍阻塞。','先保留 March–October 框架与显式缺月状态，待研究者选定处理方案。',['OCTOBER','CURRENT_REQUEST'])
 d('D02','native IMERG half-hour 与 analysis_time 正式绑定','A','BEFORE_B0_FORMAL',True,True,
   '监督标签的时段和可使用卫星观测必须一致。','converted CF coordinate verified；native exact window PROVISIONAL。',
   '取得可追溯产品/转换证据后确定映射；证据不足时继续工程 fixture，推迟真实标签的正式配对。',
   '正式 sample pairing 前必须冻结 start/end/analysis_time 语义。','不自行采用 [T,T+30)；未证实绑定不能形成正式指标。','只允许非科研 smoke；正式配对阻塞。','先保存原时间及证据字段，正式映射由研究者依据证据确认。',['SCHEMA','CONVENTIONS'])
 d('D03','model_input_bbox 与输入输出空间映射','A','BEFORE_B0_FORMAL',True,True,
   '真实输入裁剪、padding 与目标 grid 映射影响全省输出。','bbox NOT_YET_FROZEN；97–107E/20–30N 是 common numerical overlap candidate。',
   '根据 B0 的 Himawari/IMERG 覆盖选择并批准输入域和显式映射；或继续保持未定，仅做工程 fixture。',
   'smoke 可声明临时已有数组域；正式 Dataset 必须固定空间接口。','不能把矩形公共交集当云南评价 mask 或正式天气背景范围。','不阻止 smoke；正式数据裁剪和可复现实验阻塞。','分别记录输入域、目标全 grid 和已冻结评价 mask，勿以公共交集替代决定。',['FREEZE','REPORT_spatial'])
 d('D04','省界外 weather-system context margin','A','BEFORE_B0_FORMAL',True,True,
   '影响输入域携带的省外天气信息及边界效应。','当前未选科学 margin；包络余量仅几何工程事实。',
   '结合可用覆盖与研究目标批准宽度/几何定义，并与 bbox 一起定版；或暂缓正式输入域。',
   '无需为 smoke 冻结；正式输入裁剪前需明确其规则或适用范围。','已有包络余量不自动成为科学 context 定义。','仅阻止正式输入域定版，不阻止工程链路验证。','与 D03 联合 review，避免两项相互矛盾，不预选数值。',['FREEZE','REPORT_spatial'])
 d('D05','正式 Train/Validation 时间块','A','BEFORE_B0_FORMAL',True,False,
   '影响无泄漏验证、归一化来源和实验可比性。','2025 final test、2023–2024 development pool 已保留；具体块未冻结。',
   '研究者选择明确连续时间块或有版本的事件划分及间隔规则；保持 2025 测试隔离。',
   '必须在正式 index、Train-only 统计和实验前定版。','不自动挑选任何 validation 月份。','smoke 可继续；正式 split 和训练不可开始。','将每个时间块与排除/缓冲规则写成可核验配置后再执行。',['CURRENT_REQUEST','CONVENTIONS'])
 d('D06','正式缺测、QC 和单帧/六帧样本纳入规则','A','BEFORE_B0_FORMAL',True,False,
   '工程读成功不代表每个训练样本/像元有效。','missing 不填零；无科学 QC 阈值；44 p99 尾部不是坏数据。',
   '在已冻结因果与显式 mask 原则下批准分阶段缺帧/缺像元处理、loss/metric 有效像元规则；未确定则暂缓正式样本。',
   'B0 必须按 B13 单时次条件，B1/B3 才采用对应六槽条件。','不可因六帧不完整剔除可用 B0 单帧；不可因延迟尾部剔除。','正式样本纳入策略未定；smoke 可用显式标注 fixture。','复用原 QC flags 和 null，不凭工程阈值创造科学剔除标准。',['SCHEMA','REPORT_himawari','CONVENTIONS'])
 d('D07','正式归一化来源及计算协议','A','BEFORE_B0_FORMAL',True,False,
   '正式统计不能泄漏 validation/final test 信息。','尚未执行正式 mean/std；具体 Train blocks 未冻结。',
   '先确认 Train-only 来源、统计对象、有效像元、版本和反变换协议；或保持正式归一化待定。',
   '未来依赖 D05/D06；本轮不计算统计量。','工程 fixture 参数不是训练统计，不可用于报告正式结果。','正式训练前 HOLD；不阻塞 raw/dummy 工程输入。','将统计来源与 split hash 绑定，等研究者确认协议后计算。',['CURRENT_REQUEST','SCHEMA'])
 d('D08','Himawari 观测因果与 operational availability 的正式声明','A','BEFORE_B0_FORMAL',True,True,
   '近实时结论不能用 product creation timestamp 冒充可用时间。','obs_end physical causality 已建立；date_created/availability 分离；4390 nominal/internal 数值不等。',
   '建立 operational evidence；或研究者明确批准有局限的 proxy/retrospective evaluation 声明，不能声称观测到的真实可用性。',
   '真实正式配对采用获批 analysis_time；NRT replay 另需 availability 规则。','物理因果的 retrospective baseline 与 operational NRT 可用性结论必须分开。','不妨碍 fixture smoke；当前未界定正式 B0 的时间解释，需先明确；不机械要求获取不可得实时日志才能做明确标注的 retrospective baseline。','先确认拟报告的是哪种时间语义与证据强度，再定规则，不自动代理。',['RUN_p0','REPORT_himawari','SCHEMA'])
 d('D09','GFS main + thermo Dataset-layer adoption','B','BEFORE_B4',False,True,
   'B4 所需 T/RH 补充及来源可追溯性。','12960 完整配对、研究期 8820/8820；SUPPORTED_WITH_CAVEATS / PARTIALLY_COMPATIBLE。',
   '研究者审阅来源不足后显式采用并登记局限；或先补 provenance，保持分库。',
   'B0 不读取 GFS；B4 合并前需明确 source role、冲突和 provenance 规则。','结构齐全不等于内容来源全部认证或研究者批准。','B0 不受影响；完整科学收口及 B4 adoption 保持未决。','保留双来源和 key/hash，不生成已批准 integration 的假状态。',['RUN_thermo','RUN_provenance','THERMO_RESEARCH'],b4=True)
 d('D10','GFS operational vintage rule','B','BEFORE_B4',False,True,
   '决定 B4/NRT replay 当时允许选择的 forecast。','release 与 historical operational vintage NOT_ESTABLISHED；2026 acquisition 不能证明 2023–2025 contemporaneous availability。',
   '基于官方发布证据；基于同历史时期实测 acquisition；或显式批准有局限的延迟 fallback；也可暂缓 NRT 使用。',
   '未选择 init+X，更未采用 init+5h；B4 取样前需版本化规则。','conversion/mtime/download time 都不能自动当 official release。','不阻塞 B0；阻塞 full scientific closeout 与 B4 operational replay。','并列保存可证实事实和 fallback 假设，由研究者选择，不补造 release。',['RUN_provenance','REPORT_provenance'],b4=True)
 d('D11','DEM aggregation / terrain 参数 / gradient production','C','BEFORE_B5_B8',False,False,
   '影响后续地形特征尺度与物理解释。','SRTM 主来源和物理距离原则已冻结，正式生产细节未冻结。',
   '在 B5 elevation 使用前确定聚合；在 B6 terrain 与 B7/B8 DOTE 前分别确定参数和流程。',
   'B0/B4 无需等 DEM 特征生产；本轮不 resample。','经纬度 index gradient 永远不能冒充物理梯度。','不阻塞当前 B0 或 Stage-0 工程收口；到对应地形阶段再决策。','分阶段定版，避免要求现在冻结 B8 的所有参数。',['FREEZE','DEM_COVERAGE'],terrain=True)
 d('D12','独立外部验证数据与启用时间','C','BEFORE_FINAL_PAPER',False,False,
   'IMERG 密集参考不能独立证明真实降水改进。','当前 NOT_AUDITED；未证明不存在，也未建立正式独立验证集。',
   '研究者选定可用站点/雷达/DPR 等独立资料与审计计划；在论文真实性结论前落实；B0 可先报告相对 IMERG 的内部验证。',
   '不要求 B0 开始前全部下载；后续验证需时间空间配对、独立性与许可审计。','没有独立观测时不得宣称对真实降水的全面优越性。','B0 smoke/formal 对 IMERG baseline 不因此阻塞；最终独立真实性结论 HOLD。','现在登记 NOT_AUDITED 和最终论文前里程碑，不伪造 READY。',['RESEARCH_MATRIX','CURRENT_REQUEST'],paper=True)
 d('D13','正式概率实验协议（包括 32 quantile levels）','A','BEFORE_B0_FORMAL',True,False,
   '固定输出、loss、metric 和多随机种子协议才能形成可复现实验。','既有 schema 明示 32 quantile levels 尚未冻结；本轮没有实验配置批准证据。',
   '在 B0 正式实验设计时版本化 quantile levels、损失/指标、checkpoint 选择与种子协议；smoke 仅用明确非科研 fixture 配置。',
   '属于未来 B0 实验设计门槛，不要求现在生产模型或冻结全部超参数。','避免把调试 loss/metric 输出称为论文结果。','smoke 和 Stage-0 工程交付可完成；正式实验协议仍待决。','只记录已知协议空缺，进入正式实验准备时由研究者确认，不替研究者选值。',['SCHEMA','CONVENTIONS'])
 d('R14','44 LATENCY_TAIL_REVIEW','D','NOW',False,False,
   '标记延迟分布尾部供查看。','本月 p99=844.6853707599998 秒，44 个 >=p99；不存在据此认定错误的证据。',
   '研究者可复核成因；若发现独立异常，另建证据/决策记录。','无需据此删除或阻止所有 B0；保留原 delay 和 marker。','p99 不是排除、QC 或科学阈值。','不阻止任何 B0 entry；没有额外证据时仅 informational。','保留记录并允许人工查看，不提高为硬 blocker。',['RUN_p0'],decision=False)
 d('E15','Himawari 正式研究期工程证据覆盖','A','BEFORE_B0_FORMAL',True,False,
   '正式实验不得将未审计月份标成 READY。','只有 2024-07 内容审计通过；其余 23 研究月 NOT_AUDITED。',
   '在未来正式数据准备任务中按批准范围完成 reader/QC/grid/causal validation。','这是后续实现前/随数据准备完成的工程检查，不是本轮全库扫描许可。','不得外推一个月结果，也不得把 NOT_AUDITED 当 MISSING。','smoke 可以复用已审计月；完整正式研究期 Dataset 就绪仍缺证据。','在下一步获授权的数据工程范围内解决，不重开本轮审计。',['RESEARCH_MATRIX','RUN_himawari'],decision=False)
 cats={'A':'BLOCKER_TO_B0','B':'BLOCKER_TO_FULL_STAGE0_SCIENTIFIC_CLOSEOUT','C':'DEFERABLE_TO_LATER_STAGE','D':'INFORMATIONAL_REVIEW_ONLY'}
 for x in decisions:x['category_name']=cats[x['category']]
 master=[]
 def m(item,eng,sci,frozen_status,ids,action):master.append(dict(item=item,engineering_status=eng,scientific_status=sci,frozen_status=frozen_status,evidence_ids=ids,next_action=action))
 m('IMERG','PASS / audited 2465 files','2025-10 MISSING; native window PROVISIONAL','产品/频率/真实 grid/0!=missing 已定；native window 未定',['RUN_p0','IMERG_GRID','OCTOBER','SCHEMA'],'D01/D02/D06；不得自动缩短研究期')
 m('Himawari','PASS / 2024-07 scope only','其他月 NOT_AUDITED；operational availability NOT_ESTABLISHED','七通道/六 causal slots/obs_end 约束已定；正式 label binding 未定',['RUN_himawari','RUN_p0','RESEARCH_MATRIX'],'D02/D06/D08/E15；44 尾部仅 R14 review')
 m('GFS main','PASS / metadata-grid-time audit','研究期主库 T/RH 缺失；非全像元 QC','禁用降水 predictor；PS 物理可行性事实确认',['REPORT_continuous','GFS_GRID','GFS_INVENTORY'],'B4 前 D09；B0 不依赖')
 m('GFS thermo','PASS / structural metadata','PARTIALLY_COMPATIBLE; 8820/8820 research candidate','Dataset integration NOT_YET_FROZEN',['RUN_thermo','THERMO_RESEARCH'],'D09；不自动合并')
 m('GFS provenance','PASS / evidence investigation','SUPPORTED_WITH_CAVEATS; conversion chain gap','来源认可不足不转为 FROZEN',['RUN_provenance','REPORT_provenance'],'D09：显式接受局限或补证据')
 m('GFS vintage','PASS / investigation complete','release/historical vintage NOT_ESTABLISHED','NOT_YET_FROZEN',['RUN_provenance'],'D10；B4/NRT replay 前解决，不阻塞 B0')
 m('DEM','PASS / 237 SRTM tiles coverage','FULL frozen Yunnan polygon coverage；不是高程精度验证','SRTM 主来源与 physical-distance 原则 FROZEN；生产参数未定',['FREEZE','DEM_COVERAGE'],'D11 在 B5–B8 对应阶段处理')
 m('Yunnan boundary','PASS / identity + hashes','GADM4.1 CHN.30_1 已获批准','FROZEN',['FREEZE','SPATIAL_APPROVAL'],'保持版本/归档/geometry hash，不静默替换')
 m('Yunnan evaluation mask','PASS / readback fingerprint','center-in-polygon; 3430/14770; actual 130x140','FROZEN PRIMARY；intersection NON_PRIMARY',['FREEZE','RUN_freeze','IMERG_GRID'],'直接使用冻结登记；本轮未重生成')
 m('spatial overlap','PASS / static geometric audit','97–107E,20–30N CANDIDATE ONLY；非 all-time all-variable validity','NOT_FROZEN_AS_MODEL_BBOX',['RUN_spatial','FREEZE'],'D03/D04；几何相交不证明科学 context 足够')
 m('model bbox','候选工程证据已提供','RESEARCHER_DECISION_REQUIRED','NOT_YET_FROZEN',['FREEZE','CURRENT_REQUEST'],'smoke 可用声明的临时域；formal 前固定输入与映射')
 m('external validation','NOT_AUDITED','独立有效性/可用性尚未建立','NOT_YET_FROZEN',['RESEARCH_MATRIX','CURRENT_REQUEST'],'D12：最终论文真实性结论前落实；不是 B0 mandatory input')
 requirements={
  'B0_ENGINEERING_SMOKE_ENTRY':{
   'status':'READY','meaning':'READY_FOR_ENGINEERING_IMPLEMENTATION_ONLY; not an executed/passed B0 and not formal experiment approval',
   'required':['明确工程 smoke 标签与独立 run；仅 B13 单时次','使用已审计 2024-07 reader / dummy-loading 证据作为实现基础','显式有效性 mask、float32 tensor、源方向记录、obs_end 因果原则','将未来 Dataset -> Tensor -> forward -> loss -> metric -> checkpoint -> inference 逐环验证；本轮不执行','空间/标签接口若尚未冻结，使用显式非科学 fixture/synthetic targets 验证接口；不做未经批准的真实监督时间配对','保持 raw/old-run 只读与审计可追溯'],
   'optional':['使用已冻结云南评价 mask 做 shape/hash 接口检查','使用已保存小样本中间格式；storage recommendation 尚非永久冻结','现有七通道/六槽 reader 能力可复用，但不是 B0 模型输入要求'],
   'not_required':['GFS main','GFS thermo','GFS vintage','DEM','DOTE','DTFM','MEE','完整 2025-03~10 测试数据','独立外部验证下载完成','正式 model_input_bbox/context margin 冻结','正式 Train/Val 划分及 Train mean/std'],
   'actual_execution':'NOT_RUN_THIS_TASK','model_input':['Himawari B13 single time'],'formal_science_metrics_allowed':False},
  'B0_FORMAL_EXPERIMENT_ENTRY':{
   'status':'NOT_READY','required':['研究期与 2025 final-test 框架保持，2025-10 缺月处理明确','真实 IMERG target grid 与 3430 主评价 mask（已满足）','native IMERG 窗口、analysis_time、单帧 selection 与 obs_end 因果绑定获批','正式 model_input_bbox/context 定义及裁剪/padding/输出映射获批','2023–2024 development 内 Train/Val 精确块和隔离规则获批','Train-only 归一化来源/有效像元/统计协议获批后再计算','missing/QC/sample inclusion 规则与分阶段单帧/六槽要求明确','实际拟用 Himawari 各研究月完成工程验证，不把 NOT_AUDITED 写 READY','正式概率实验 protocol（quantiles/loss/metrics/seeds/checkpoint）定版','明确 retrospective physical causality 与 operational NRT availability 的报告范围'],
   'optional':['外部验证可先规划；若要作真实降水独立优越性结论则必须先就绪'],
   'not_required':['GFS main','GFS thermo','GFS vintage','DEM','DOTE','DTFM','MEE','B8 全部 terrain hyperparameters'],
   'actual_execution':'NOT_RUN_THIS_TASK','model_input':['Himawari B13 single time'],'target':'IMERG (formal pairing pending)'} }
 matrix=[]
 def row(item,eng,frz,data,smoke,formal,b4,b58,full,status,ids,action,stage='NOW',paper=False):
  matrix.append(dict(item=item,engineering_complete=eng,scientific_definition_frozen=frz,data_ready=data,required_for_B0_smoke=smoke,required_for_B0_formal=formal,required_for_B4=b4,required_for_B5_B8=b58,required_for_full_stage0_closeout=full,status=status,evidence=';'.join(ids),researcher_action=action,due_stage=stage,required_before_final_paper=paper))
 row('IMERG audited source grid',True,True,'READY_WITHIN_AUDITED_SPAN',False,True,True,True,True,'PASS',['RUN_p0','IMERG_GRID'],'保持真实源坐标')
 row('Yunnan boundary and primary mask',True,True,'READY',False,True,True,True,True,'FROZEN',['FREEZE'],'保持冻结版本')
 row('Himawari July reader / dummy loading',True,True,'READY_FOR_ENGINEERING',True,True,True,True,True,'PASS_SCOPED',['RUN_himawari'],'B0 仅选择 B13 单时次；未开始新实现')
 row('GFS main / thermo metadata availability',True,False,'STRUCTURAL_CANDIDATE_ONLY',False,False,True,False,True,'PARTIALLY_COMPATIBLE',['RUN_thermo'],'D09/D10；B4 前还须与实际 predictor 像元有效性验证分开')
 row('SRTM primary source coverage',True,True,'FULL_FROZEN_POLYGON',False,False,False,True,True,'FROZEN_SOURCE',['FREEZE','DEM_COVERAGE'],'参数 D11 可后置')
 for x in decisions:
  row(x['id']+' '+x['decision'], False if x['id']=='E15' else 'NOT_APPLICABLE_SCIENTIFIC_DECISION' if x['requires_researcher_decision'] else True,
      False if x['requires_researcher_decision'] else 'NOT_APPLICABLE',
      'MISSING' if x['id']=='D01' else 'NOT_AUDITED' if x['id'] in ['D12','E15'] else 'NOT_ESTABLISHED' if x['id']=='D10' else 'NOT_APPLICABLE_RULE' if x['id'] not in ['D09','R14'] else 'CANDIDATE' if x['id']=='D09' else 'READY_FOR_REVIEW',
      x['blocks_smoke'],x['blocks_formal'],x['required_before_B4'],x['required_before_B5_B8'],x['blocks_full_stage0'],x['status'],x['evidence_ids'],x['recommendation'],x['due_stage'],x['required_before_final_paper'])
 package=dict(frozen_conventions=frozen,data_gaps=gaps,decisions=decisions,master=master,requirements=requirements,matrix=matrix,
   scientific_facts=dict(imerg_202510_status='MISSING',native_imerg_window_status='PROVISIONAL',gfs_release_status='NOT_ESTABLISHED',gfs_main_thermo_status='PARTIALLY_COMPATIBLE',main_thermo_researcher_approved=False,model_input_bbox=None,model_input_bbox_frozen=False,context_margin_frozen=False,formal_train_val_blocks_frozen=False,final_test_year=2025,development_years=[2023,2024],exact_train_blocks=None,exact_validation_blocks=None,intersection_primary=False,primary_mask_true_cells=facts['mask_observed']['true_cells'],latency_tail_count=44,latency_tail_exclusion=False,external_validation_status='NOT_AUDITED',external_required_B0_smoke=False,external_required_B0_formal_imerg_baseline=False,external_required_final_paper_independent_claim=True),
   scope=dict(raw_files_opened=0,raw_scan=False,old_scripts_executed=False,mask_generated=False,B0_started=False,formal_dataset_created=False,dependencies_changed=False),
   schema_status='NEEDS_UPDATE',stage0_engineering_scope='Completion of authorized existing audits and final-gate synthesis; not all raw months/all pixels or future stages validated')
 g.wjson('DECISIONS/gate_assessment.json',package)
 # Bind every master conclusion and every rule/decision/gap to exact old evidence.
 expanded=oldrefs.copy()
 for kind,entries in [('MASTER',master),('FROZEN',frozen),('GAP',gaps),('DECISION',decisions)]:
  for x in entries:
   name=x.get('id',x.get('item',''))
   for eid in x['evidence_ids']:
    r=refmap[eid].copy();r['evidence_id']=kind+':'+name+':'+eid
    r['conclusion']=x.get('rule',x.get('decision',x.get('detail',x.get('scientific_status',''))));expanded.append(r)
 g.table('evidence_registry.csv',expanded)
 g.table('STAGE0_CLOSEOUT_MATRIX.csv',matrix)
 g.write('STAGE0_MASTER_STATUS.md','# Stage-0 Master Status\n\n工程交付与科学规则分列。历史候选被后来显式批准的空间 freeze 更新，旧文件不改写。日期/范围不同的状态不是相互冲突；未见关键 fingerprint 冲突。\n\n'+g.mdtable([{**x,'evidence_source':links(x['evidence_ids'])} for x in master],['item','engineering_status','scientific_status','frozen_status','evidence_source','next_action'])+'\nPASS 仅限已授权审计的实际范围。Himawari 全研究期、GFS 全像元 QC、external validation 未因本轮汇总升级成 PASS。\n')
 g.write('FROZEN_CONVENTIONS.md','# Frozen conventions\n\n以下仅复述已有研究者批准规则与其限定的工程事实。本轮没有批准新科学约定。源身份事实与时间窗口/可用性推断分开。\n\n'+g.mdtable([{**x,'evidence':links(x['evidence_ids']),'approval':links(x['approval_evidence'])} for x in frozen],['id','rule','scope','evidence','approval'])+'\n正式空间版本：'+facts['freeze']['freeze_id']+'。所有 artifact/geometry/coordinate/generator hashes 仍以旧 freeze_registry.json 为准；本轮只核验和引用。\n')
 g.write('DATA_GAPS.md','# Data gaps and evidence limits\n\n已确认缺口共 '+str(sum(x['confirmed_gap'] for x in gaps))+' 项；工程缺口不等同原始文件错误。bbox/context 等未冻结选择不列为 data gap。\n\n'+g.mdtable([{**x,'evidence':links(x['evidence_ids'])} for x in gaps if x['confirmed_gap']],['id','classification','item','status','detail','evidence'])+'\n## 未审计范围：不计入已确认缺口数\n\n'+g.mdtable([{**x,'evidence':links(x['evidence_ids'])} for x in gaps if not x['confirmed_gap']],['id','classification','item','status','detail','evidence'])+'\nDATA_COVERAGE_GAP 为待核验的缺口类别，U01/U02 的实际缺失未知。独立验证 NOT_AUDITED 不能写成不存在或 READY。\n')
 decisionrows=[{**x,'evidence':links(x['evidence_ids'])} for x in decisions]
 g.write('RESEARCHER_DECISIONS_REQUIRED.md','# Researcher decisions and staged dependencies\n\nA=BLOCKER_TO_B0；B=BLOCKER_TO_FULL_STAGE0_SCIENTIFIC_CLOSEOUT；C=DEFERABLE_TO_LATER_STAGE；D=INFORMATIONAL_REVIEW_ONLY。每项仅一个主分类；独立 flags 反映交叉影响。A 在本包均指正式 B0，不阻塞非科学工程 smoke。D01 主类 B，同时阻塞完整研究期正式 B0。\n\n'+g.mdtable(decisionrows,['id','decision','category_name','due_stage','blocks_smoke','blocks_formal','blocks_full_stage0','status','evidence'])+'\nR14 是 review，不要求科研批准；E15 是未完成的覆盖工程证据，不伪装成科研决定。13 张 decision cards 仅对应需要研究者决定的条目；并非所有决定必须现在完成。B0 formal 的阶段特有实验配置不要求提前在 Stage-0 冻结。\n')
 for x in decisions:
  if not x['requires_researcher_decision']:continue
  sections=[('Decision',x['decision']),('Why it matters',x['why']),('Current evidence',x['current_evidence']+' '+links(x['evidence_ids'])),('Options',x['options']),('Engineering consequence',x['engineering_consequence']),('Scientific consequence',x['scientific_consequence']),('What happens if deferred',x['if_deferred']),('Codex recommendation',x['recommendation'])]
  g.write('DECISIONS/cards/'+x['id']+'.md','\n\n'.join('## '+k+'\n\n'+v for k,v in sections)+'\n')
 chunks=['# B0 Entry Requirements','本包判断下一步进入条件，不授权或执行 B0。READY 表示可以开展工程实现；不是已有 B0 forward/loss/metrics/checkpoint/inference 通过。']
 for name,v in requirements.items():
  chunks+=['## '+name,'状态：'+v['status']+'；本轮执行：'+v['actual_execution']]
  for kind in ['required','optional','not_required']:chunks+=['### '+kind,'\n'.join('- '+s for s in v[kind])]
 chunks+=['## 分离原则','Smoke 的 fixture 接口不得解释为真实科研标签配对；如果要求 smoke 就使用正式真实监督标签，则必须先解决 D02/D03/D04/D06/D08 等对应规则，不能沿用本包 READY 的非科学范围。正式实验的全部 gate 仍 NOT_READY。已冻结 target grid/行政 mask 不等于已冻结模型输入域。','独立外部验证：B0 smoke 不要求；正式 IMERG-reference baseline 不要求预先全部下载；最终关于真实降水的独立真实性结论前必须就绪。GFS/DEM 均不是 B0 mandatory input。','规范追溯：'+links(['RUN_himawari','RUN_p0','SCHEMA','FREEZE','CURRENT_REQUEST'])]
 g.write('B0_ENTRY_REQUIREMENTS.md','\n\n'.join(chunks)+'\n')
 g.write('SCHEMA/sample_schema_readiness.md',f'''# Formal sample schema readiness

状态：**NEEDS_UPDATE**。复用源：{link('SCHEMA')}。这是字段评估，不是新 schema 定版或正式样本库。

已有：源路径、UTC/null/evidence status、IMERG grid/units、时间窗口 provisional 状态、Himawari 六槽/七通道/obs_end/date_created/availability 分列、missing/QC flags、p99 marker、GFS init/lead/valid/release/vintage 与分库 provenance、surface pressure feasibility、bbox null 等。不能把这些字段都设为 B0 必填。

进入实现前需要描述并由对应任务补齐：

1. stage_profile / purpose：B0 单 B13 单时次；B1/B3 才有相应六槽输入；engineering_fixture 与 formal 实例显式区分。旧 fixed list[6]/list[7] 不能不加 profile 就强制用于 B0。
2. spatial_freeze_id、boundary/mask 文件和 geometry/coordinate hash、primary/non_primary role；旧泛化 Yunnan_mask_status 应引用真实已冻结版本。
3. native_window_rule_id、analysis_time_binding_id、temporal_evidence_status 与 formal eligibility；规则未批准时值仍 null/provisional。不能按旧候选 [T,T+30min) 实例化正式样本。
4. input_domain_config_id、context_rule_id、target_grid_id、显式裁剪/padding/重采样映射及坐标方向记录；本轮不选择规则或执行变换。
5. split_definition_id 与 Train/Val/Test assignment 的 provenance；normalization_artifact_id、Train-only 来源/split hash、有效像元规则；本轮不赋值、不统计。
6. sample_inclusion_policy_id、loss/metric valid-mask references、channel/time presence 与拒绝原因；latency tail 不自动进入 reject reason。
7. optional-by-stage GFS/DEM 字段、adoption/vintage rule id 与 source-pair evidence。B0 值可为 NOT_APPLICABLE，不伪造成 MISSING_INPUT。
8. formal probability/loss/metric protocol id、种子/checkpoint/inference 版本引用；精确 quantile levels 未冻结。
9. raw source identity/hash（适用时）、evidence run 与生成代码 hash、schema/version、execution purpose/quality status，防止工程 fixture 被提升为正式样本。

NEEDS_UPDATE 指 schema 可以基于上述明确差异继续设计；formal instance generation 仍受决策表约束。既有 schema 的 pipeline 提案不构成科学批准。没有创建全量 sample index、Dataset 或数据库。
''')
 g.write('docs/DECISION_LOG_STAGE0_FINAL_GATE.md','# Stage-0 final gate decision log\n\n本轮仅汇总，不产生新的研究者批准。\n\n- 采用已显式批准的空间 freeze 作为现行版本；旧 spatial audit 的 candidate 状态是历史，不修改旧报告。\n- GFS T/RH 从主库缺失到 companion 完整候选是证据扩展，不代表 Dataset adoption 或 provenance fully established。\n- Himawari dry-run 中 TIME_MISMATCH=4390 表达 nominal/internal 数值不等；P0 的 obs_end 因果核验针对另一个显式 analysis-time 关系，两者不冲突，也不解决 operational availability。\n- 44 latency tails 保持 INFORMATIONAL_REVIEW_ONLY，不据此排除或提高为所有 B0 blocker。\n- 工程 smoke 可开始实现的建议不代表当前授权启动；正式实验继续等待明确的依赖与规则。\n- 精确 Train/Val 块、bbox/context、native window、vintage、terrain 参数均未自动冻结。\n- Zarr storage recommendation 仍供 review；本轮未选永久格式。\n- 未扫 raw、未再生成 mask、未下载、未执行旧任务。\n')
 g.write('EVIDENCE/evidence_lineage_notes.md','# Evidence lineage and conflicts\n\n当前定向 fingerprint 检查无冲突。早期状态按来源时点保留，不自行覆盖：\n\n- 早期 continuous run 与 later continuous run 均注册；本包使用有正式 audit_final_status 的较晚 run 作为 expanded engineering baseline，并保留早期30 tests历史。\n- GFS 主库缺 T/RH 与 thermo 有补充候选可同时成立。\n- 旧 spatial audit 为 candidate；后续 researcher approval + freeze 明确更新其科学地位。\n- Himawari DRY_RUN_FAILED 为依赖 Gate 历史；resume v1/v2 原样保留，v2 为明示 revision，字段一致性已核查。\n- nominal/internal TIME_MISMATCH 与 obs_end physical causality 是不同判据；本包不把前者转为坏数据或删除条件。\n- 旧 manifest 无 SHA 时仅可比较登记 size；本轮额外保存当前关键文件 SHA 和前后完整性，不声称补出了历史 hash。\n- 本轮初始文件名定位遇到旧 tests/tmp 访问限制，改为指定正式证据读取，未改权限，未遗漏任何本包必需状态/报告。\n')
 g.write('README.md','# Stage-0 Final Gate Package\n\n先读 FINAL_STAGE0_GATE_REPORT.md，再看 B0_ENTRY_REQUIREMENTS.md 和 DECISIONS/cards。STAGE0_MASTER_STATUS 是唯一汇总入口；旧 run 保持其原时点结论。\n\nCSV/JSON 是机器可核验状态，Markdown 为研究者阅读版本。evidence_registry.csv 提供 source run/file/section/SHA；EVIDENCE/evidence_fingerprint_check.csv 是定向检查结果。DECISIONS/gate_assessment.json 是本包的结构化依赖评估，不是新科研定义。\n\n使用固定 Python：F:/pytorch/Research/.venv/Scripts/python.exe；无安装/升级。源码在 src；重现必须新建独立 run，不能对旧 run 执行 collect 或覆盖报告。pytest 仅校验决策包及只读证据，不运行旧任务、不生成数据或模型。\n\nNOT_RUN、NOT_AUDITED、NOT_ESTABLISHED 不会因为工程测试通过而升级。完整性证据限登记关键输入；无全 raw 内容 hash 声明。\n')
 g.write('src/gate_package.py',Path(__file__).read_text(encoding='utf-8-sig'))
 g.wjson('logs/render_log.json',dict(completed_utc=g.utc(),master_items=len(master),frozen_conventions=len(frozen),confirmed_data_gaps=sum(x['confirmed_gap'] for x in gaps),researcher_decision_cards=sum(x['requires_researcher_decision'] for x in decisions)))
 print(json.dumps({'rendered':str(g.OUT),'frozen':len(frozen),'cards':sum(x['requires_researcher_decision'] for x in decisions),'formal_blockers':sum(x['blocks_formal'] for x in decisions)},ensure_ascii=False))

def finalize(g):
 a=json.loads((g.OUT/'DECISIONS/gate_assessment.json').read_text(encoding='utf-8'))
 before=json.loads((g.OUT/'logs/input_protection_before.json').read_text(encoding='utf-8'))
 integrity=[]
 for p,b in before.items():
  p=Path(p);s=p.stat();h=g.file_sha(p)
  integrity.append(dict(path=str(p),size_unchanged=s.st_size==b['size_bytes'],mtime_unchanged=s.st_mtime_ns==b['mtime_ns'],sha256_unchanged=h==b['sha256'],sha256_before=b['sha256'],sha256_after=h))
 g.table('logs/input_integrity_check.csv',integrity)
 intact=all(r['size_unchanged'] and r['mtime_unchanged'] and r['sha256_unchanged'] for r in integrity)
 if not intact:raise RuntimeError('Evidence changed; do not declare unchanged')
 envbefore=json.loads((g.OUT/'logs/environment.json').read_text(encoding='utf-8'))
 versions={n:md.version(n) for n in envbefore['versions']}
 g.wjson('logs/integrity_summary.json',dict(checked_files=len(integrity),all_registered_size_mtime_sha256_unchanged=intact,raw_files_opened=0,raw_write_operations=0,old_run_write_operations=0,full_raw_hash_claim=False,scope='Registered evidence files only; all were read-only. No scan of raw libraries or exhaustive hash of every old artifact.',dependencies_changed=versions!=envbefore['versions']))
 # Exact string-valued CSV/Parquet pair preserves status and IDs without inferred coercions.
 import pyarrow as pa
 import pyarrow.parquet as pq
 pairs=[]
 for p in sorted(g.OUT.rglob('*.csv')):
  with p.open(encoding='utf-8-sig',newline='') as fh:
   reader=csv.DictReader(fh);fields=reader.fieldnames;rows=list(reader)
  t=pa.Table.from_pylist(rows,schema=pa.schema([(n,pa.string()) for n in fields]))
  q=p.with_suffix('.parquet')
  try:
   pq.write_table(t,q,compression='snappy');equal=pq.read_table(q).equals(t)
   pairs.append({'csv':str(p.relative_to(g.OUT)),'parquet':str(q.relative_to(g.OUT)),'rows':len(rows),'exact_roundtrip':equal})
  except Exception as e:
   g.wjson('logs/parquet_error.json',{'file':str(p),'error':repr(e)});raise
 g.wjson('logs/parquet_validation.json',{'engine':'pyarrow','version':md.version('pyarrow'),'schema':'all CSV columns as strings; CSV/Parquet exact evidence presentation; typed canonical values in gate_assessment.json','pairs':pairs})
 cmd=[sys.executable,'-B','-m','pytest','tests/test_final_gate.py','--rootdir=.','--confcutdir=tests','--import-mode=importlib','-p','no:cacheprovider','--junitxml=tests/pytest_final.xml','-q']
 result=subprocess.run(cmd,cwd=g.OUT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
 g.write('tests/pytest_final_output.txt',result.stdout)
 g.wjson('logs/pytest_execution.json',dict(command=cmd,cwd=str(g.OUT),exit_code=result.returncode,ended_utc=g.utc()))
 if result.returncode:raise RuntimeError('Final tests failed; inspect preserved pytest output')
 xml=ET.parse(g.OUT/'tests/pytest_final.xml').getroot();suites=list(xml.iter('testsuite'))
 totals={k:sum(int(s.get(k,'0')) for s in suites) for k in ['tests','failures','errors','skipped']}
 # Recheck protected evidence after tests as well.
 for p,b in before.items():
  s=Path(p).stat()
  assert s.st_size==b['size_bytes'] and s.st_mtime_ns==b['mtime_ns'] and g.file_sha(p)==b['sha256'],p
 g.wjson('logs/post_test_integrity.json',{'checked_files':len(before),'all_unchanged':True,'utc':g.utc()})
 decisions=a['decisions'];frozen=a['frozen_conventions'];gaps=a['data_gaps']
 status=dict(stage0_engineering_status='PASS',stage0_engineering_scope=a['stage0_engineering_scope'],stage0_scientific_closeout_ready=False,stage0_scientific_closeout_status='NEEDS_RESEARCHER_DECISIONS',b0_engineering_smoke_ready=True,b0_engineering_smoke_readiness_scope='READY_FOR_NON_SCIENTIFIC_ENGINEERING_IMPLEMENTATION_ONLY; not an executed B0',b0_formal_experiment_ready=False,b0_execution_status='NOT_RUN_THIS_TASK',frozen_convention_count=len(frozen),data_gap_count=sum(x['confirmed_gap'] for x in gaps),not_audited_scope_count=sum(not x['confirmed_gap'] for x in gaps),b0_blocker_count=sum(x['blocks_formal'] for x in decisions),b0_blocker_count_definition='Unique unresolved formal-entry dependency IDs, not only primary category A; includes E15 engineering evidence',b0_smoke_blocker_count=sum(x['blocks_smoke'] for x in decisions),full_stage0_blocker_count=sum(x['blocks_full_stage0'] for x in decisions),researcher_decision_count=sum(x['requires_researcher_decision'] for x in decisions),gfs_release_status='NOT_ESTABLISHED',gfs_main_thermo_status='PARTIALLY_COMPATIBLE',main_thermo_researcher_approved=False,model_input_bbox_frozen=False,formal_train_val_blocks_frozen=False,raw_data_modified=False,old_evidence_runs_modified=False,evidence_conflict_count=0,tests=totals,raw_integrity_scope='No raw access; registered old evidence size/mtime/SHA checked before/after. No full raw hash claim.',dependencies_changed=False,completed_utc=g.utc(),automatic_next_stage=False)
 g.wjson('stage0_final_gate_status.json',status)
 formal=[x['id'] for x in decisions if x['blocks_formal']]
 full=[x['id'] for x in decisions if x['blocks_full_stage0']]
 report=f'''# Stage-0 Final Gate / Researcher Decision Package

| Gate | 当前结论 |
|---|---|
| Stage-0 engineering | PASS：已授权审计交付及本轮证据汇总完成 |
| Stage-0 scientific full closeout | NEEDS_RESEARCHER_DECISIONS |
| B0 engineering smoke entry | READY：仅限非科研工程实现入口，B0 本身未运行 |
| B0 formal experiment entry | NOT_READY |

本包：`{g.OUT}`。当前批准仅覆盖 Final Gate package，完成即停止。

## 1. Engineering 是否完成

是，在既有授权任务范围内完成。9 个 run 登记（含早期 continuous 与 Himawari DRY_RUN_FAILED 历史）；95 项关键 fingerprint 检查一致。PASS 不外推成全部研究月或全部变量像元的有效性。Himawari 仅 2024-07 有完整月工程证据；其余 23 研究月 NOT_AUDITED。主库/thermo 的 metadata presence 不等于全像元 QC。

## 2. Scientific closeout 是否完成

否。当前 full scientific closeout 相关未决依赖共 {status['full_stage0_blocker_count']} 项：{', '.join(full)}。Stage-0 工程不再循环等待未来 B8 超参数；B0 专属实验协议和地形生产细节按其阶段处理。

## 3. B0 engineering smoke 是否可以开始

具备进入工程实现的证据：已审计 Himawari 七通道 reader、50 个真实 dummy loading 通过记录，以及已冻结目标 grid/mask 可供接口复用。B0 只取 B13 单时次。未来验证 Dataset → Tensor → forward → loss → metric → checkpoint → inference，所有中间检查须真实执行。**这条完整 B0 链路本轮 NOT_RUN**。

READY 限非科学 fixture 接口验证；空间/标签规则未定时，可在未来工程任务声明临时数组域和 synthetic/非科学 targets，不能伪装成真实监督配对或论文结果。如果要求立即用正式真实监督标签，须先满足相应 formal gate。本包没有创建 fixture、Dataset 或模型，也没有授权自动进入下一阶段。

## 4. B0 formal experiment 是否可以开始

否。正式 Train/Validation/Final Test 与论文实验需要满足 B0_ENTRY_REQUIREMENTS.md。2025 final test、2023–2024 development pool 与候选每年 March–October 保持；精确 Train/Val 块未冻结，2025-10 没有被自动删除。

## 5. 真正的当前 blocker

Smoke：在上述非科学工程范围内，无剩余科学入口 blocker；未来每个工程环节仍需实现和测试。Formal：{status['b0_blocker_count']} 个独立依赖：{', '.join(formal)}。包括 October gap、native window/analysis_time、输入域/context、精确时间块、缺测/QC、Train-only 统计协议、Himawari availability 声明范围、正式概率实验协议及其他研究月工程证据。D03/D04 可联合 review 但记录为两个显式决定。此计数不是所有 category A 的简单总和：D01 主类 B 也阻塞 formal。

## 6. 与 B0 无关或可后置事项

GFS integration/vintage、DEM aggregation/terrain 参数、DOTE/DTFM/MEE 不属于 B13 单帧 B0 输入。44 LATENCY_TAIL_REVIEW 仅 INFORMATIONAL_REVIEW_ONLY。独立外部数据不要求在 B0 开始前全部下载。永久存储格式尚未冻结，但不是阻止一个小规模 smoke 的科学门槛。

## 7. B4 前必须解决

D09 main+thermo adoption 与来源局限处置、D10 release/vintage 规则；再在相应工程阶段验证 predictor 像元有效性和明确取样接口。当前 SUPPORTED_WITH_CAVEATS、PARTIALLY_COMPATIBLE、NOT_ESTABLISHED 原样保留。禁止 GFS precipitation predictor。init+5h、mtime、conversion/download time 均未自动作为 official release。

## 8. B5–B8 前必须解决

分阶段处理 D11：B5 elevation 聚合；B6 terrain 参数；B7/B8 gradient/DOTE 生产流程。SRTM 主来源与真实物理距离原则已冻结，AWS_Skadi 未拼接。没有要求现在冻结全部后期参数，没有生成正式地形特征。

## 9. 最终论文结论前必须解决

D12 独立观测数据选择、审计、独立性和匹配协议。当前 NOT_AUDITED，不等同 MISSING 或 READY。B0 可先规划相对 IMERG 的 baseline，但未有独立证据不能宣称全面改善真实降水；NRT operational 结论还须满足相应 availability/vintage 证据与获批解释。

## 10. 已冻结约定

{len(frozen)} 条详见 FROZEN_CONVENTIONS.md：云南全境行政评价、GADM4.1 CHN.30_1、3430 中心格、真实 IMERG 130×140 坐标、源身份/频率、0!=missing、七通道/六因果槽及 obs_end、禁用 GFS precipitation、PS feasibility、SRTM、物理地形梯度、原始只读、p99 仅 review、2025 test 框架、QI 仅 QC_STAT_ONLY。冻结版本 `{facts_freeze(g)}`。本轮没有新 freeze。

## 11. 数据缺口

{status['data_gap_count']} 项已确认的 data/metadata/provenance gap，见 DATA_GAPS.md；另 {status['not_audited_scope_count']} 个未审计范围不计成已证明缺失。主库 T/RH 缺口有完整 companion candidate，不能描述成所有来源均无 T/RH。bbox/context 是决策，未混入 data gap。

## 12. Researcher decisions / schema

13 张卡，每张仅包含要求的 8 个栏目。分类 A/B/C/D 与 NOW、BEFORE_B0_FORMAL、BEFORE_B4、BEFORE_B5_B8、BEFORE_FINAL_PAPER 明确分列。R14 为 informational，E15 为工程证据。Formal sample schema：NEEDS_UPDATE，主要缺少分阶段 B0 profile、正式 spatial freeze/hash 引用、规则版本与 split/normalization/protocol provenance；仅描述字段空缺，未实例化任何样本。

## 13. Evidence conflict

95 项关键检查 CONSISTENT，0 个 EVIDENCE_CONFLICT_RESEARCHER_REVIEW。旧 candidate → 后续显式冻结、主库缺变量 → 辅库候选补齐、dry-run nominal/internal mismatch → P0 物理因果核验均按各自时点和判据解释，不改写历史。旧 tests/tmp 有访问限制，但所有必需状态/报告/manifest 和关键产物均已定向读取；未改 ACL。全量原始数据没有重新核验。

## 14. Tests and serialization

pytest：{totals['tests']} passed；failures={totals['failures']}，errors={totals['errors']}，skipped={totals['skipped']}。真实输出 tests/pytest_final_output.txt 和 tests/pytest_final.xml。核验冻结证据、状态不升级、B0 两层依赖、实际 mask 指纹、历史失败保留、只读约束和 CSV/Parquet 精确回读。数据表使用 pyarrow CSV+Parquet 双格式；schema 明确采用字符串保存 CSV 原表示，类型化逻辑保存在 gate_assessment.json。未来 B0 未执行事项没有写成 PASS。

## 15. Raw and prior-run integrity

本轮 raw 文件读取/写入/目录扫描均 0；未执行旧脚本，未重生成 mask。{len(integrity)} 个登记关键输入 size/mtime/SHA256 前后及测试后均一致；所有写入限新 run。此范围不是全 raw 或全部旧文件的逐字节证明。没有下载、安装/升级、归一化、split、插值、resampling、训练。旧 DRY_RUN_FAILED 与其他历史报告保留。输出 manifest 覆盖本包，不给自身作循环 hash。

{g.ENDING}
'''
 g.write('FINAL_STAGE0_GATE_REPORT.md',report)
 g.write('src/gate_package.py',Path(__file__).read_text(encoding='utf-8-sig'))
 manifest=[]
 for p in sorted(g.OUT.rglob('*')):
  if p.is_file() and p.name not in ['output_manifest.csv','output_manifest.parquet']:
   manifest.append(dict(relative_path=str(p.relative_to(g.OUT)),size_bytes=p.stat().st_size,sha256=g.file_sha(p)))
 g.table('output_manifest.csv',manifest)
 pq.write_table(pa.Table.from_pylist(manifest),g.OUT/'output_manifest.parquet',compression='snappy')
 # Final artifacts validate after status/report creation, no silent post-test edits to policy.
 assert (g.OUT/'FINAL_STAGE0_GATE_REPORT.md').read_text(encoding='utf-8').rstrip().endswith(g.ENDING)
 assert status['frozen_convention_count']==len(a['frozen_conventions'])
 for r in manifest:assert g.file_sha(g.OUT/r['relative_path'])==r['sha256']
 print(json.dumps({'output':str(g.OUT),'status':status,'manifest_entries':len(manifest)},ensure_ascii=False))

def facts_freeze(g):return json.loads((g.OUT/'EVIDENCE/collected_facts.json').read_text(encoding='utf-8'))['freeze']['freeze_id']
