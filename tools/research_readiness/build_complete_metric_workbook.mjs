// One worksheet, one categorized table; model explanations follow beneath it.
// Saved statistics only; no models, inference or raw meteorological payloads.
import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
const args=process.argv.slice(2),arg=k=>args[args.indexOf(k)+1];
for(const k of ['--runtime','--data','--output'])if(!args.includes(k))throw Error(`Missing ${k}`);
const require=createRequire(path.join(path.resolve(arg('--runtime')),'entry.cjs'));
const {Workbook,SpreadsheetFile}=await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);
const d=JSON.parse(await fs.readFile(arg('--data'),'utf8'));
if(d.status!=='COMPLETE_WITH_EXPLICIT_UNCOMPUTED_SUPPLEMENTAL_METHODS'&&!args.includes('--development-preview'))throw Error('No final dataset yet');
const output=path.resolve(arg('--output'));
try{await fs.access(output);throw Error('Never overwrite an existing workbook');}catch(e){if(e.code!=='ENOENT')throw e;}
const wb=Workbook.create(),sheet=wb.worksheets.add('完整指标');
const headers=['记录类型','模型或配对','seed或统计','损失臂','Train/Dev人口','方法或分组','阈值(mm/h)','来源Dev场景','全监督N','当前评价分母N','真值超阈像元时次N','Brier↓','AUROC↑','AP↑','条件Pinball↓','覆盖率（总体q32）','偏差（总体q32）','覆盖绝对误差↓','32分位平均覆盖误差↓','经验REL↓','经验RES↑','UNC','MAE(mm/h)','RMSE(mm/h)','MeanBias(mm/h)','PearsonCC','TP','FP','FN','TN','POD','FAR','CSI','HSS','不支持N','参与seed数','状态与范围','固定E9 SHA256','原训练commit或绑定状态','来源ID','参考来源ID','说明'];
const col=i=>{let n=i+1,s='';while(n){s=String.fromCharCode(65+(n-1)%26)+s;n=Math.floor((n-1)/26);}return s;};
const canonical=m=>m.startsWith('B0')?'B0':m.startsWith('B1_')?'B1':m;
const runid=(m,s,a)=>`${m}_s${s}`+(['B0','B1'].includes(m)?`_${a}`:'');
const empty=()=>Array(headers.length).fill('n.a.');
const records=new Map(d.records.map(r=>[r.run_id,r]));
const diag=new Map(),strata=new Map(),quantiles=new Map();
const fieldToColumn={brier:11,auroc:12,average_precision:13,conditional_pinball:14,q32_coverage:15,q32_signed_bias:16,q32_absolute_error:17,mean_absolute_32_coverage_error:18,empirical_score_reliability:19,empirical_score_resolution:20,uncertainty:21};
const archivedFields={Brier:11,AUROC:12,AP:13,conditional_pinball:14,q32_coverage:15,POD_r01_Pge05:30,FAR_r01_Pge05:31,CSI_r01_Pge05:32,HSS_r01_Pge05:33};
for(const x of d.details){
  const [eid,model,seed,arm,group,metric,value]=x;if(!/^\d+$/.test(seed)||typeof value!=='number')continue;
  const rid=runid(canonical(model),seed,arm);if(!records.has(rid))continue;
  if(group.includes('empirical_exact_score_brier')||group==='offline_quantile_diagnostic'){
    if(!diag.has(rid))diag.set(rid,{});if(metric in fieldToColumn)diag.get(rid)[metric]=value;
  }
  if(/^analysis_UTC_(00|06|12|18)$|^scene_max_ge20$/.test(group)){
    const key=`${rid}|${group}`;if(!strata.has(key))strata.set(key,{rid,group,values:{}});const v=strata.get(key).values;
    if(metric in fieldToColumn||['scenes','n_valid','n_rain'].includes(metric))v[metric]=value;
    if(metric==='coverage/31')v.q32_coverage=value;
  }
  const q=metric.match(/^(tau|coverage)\/(\d+)$/);
  if(group==='all'&&q){const key=`${rid}|Q${q[2]}`;if(!quantiles.has(key))quantiles.set(key,{rid,index:Number(q[2])});quantiles.get(key)[q[1]]=value;}
  const rain=metric.match(/^rain_strata\/(?:strata\/)?(\d+)\/(n|n_rain|conditional_pinball|q32_coverage|q32_covered)$/);
  if(group==='all'&&rain){
    const key=`${rid}|RAIN_${rain[1]}`;if(!strata.has(key))strata.set(key,{rid,group:`RAIN_${rain[1]}`,values:{}});strata.get(key).values[rain[2]==='n'?'n_rain':rain[2]]=value;
  }
  const tailRain=metric.match(/^strata\/(\d+)\/(n_rain|conditional_pinball|q32_coverage|q32_covered)$/);
  const altitude=metric.match(/^elevation_diagnostics\/bins\/([^/]+)\/(n_valid|n_rain|brier|conditional_pinball|q32_coverage)$/);
  if(group==='tail_diagnostics'&&(tailRain||altitude)){
    const m=tailRain||altitude,g=tailRain?`RAIN_${m[1]}`:m[1],key=`${rid}|${g}`;
    if(!strata.has(key))strata.set(key,{rid,group:g,values:{}});strata.get(key).values[m[2]]=value;
  }
}
// Supplement existing group rows with saved occurrence counts/rates. No inference.
for(const a of d.archive_groups||[]){
  if(a.group==='all')continue;
  const key=`${a.run_id}|${a.group}`;
  if(!strata.has(key))strata.set(key,{rid:a.run_id,group:a.group,values:{}});
  const target=strata.get(key);target.archive=a;
  for(const [old,k]of Object.entries({Brier:'brier',AUROC:'auroc',AP:'average_precision',conditional_pinball:'conditional_pinball',q32_coverage:'q32_coverage'})){
    const val=a.values[old];if(typeof target.values[k]==='number'&&Math.abs(target.values[k]-val)>1e-12)throw Error('Saved group identity/value drift');target.values[k]=val;
  }
  target.values.n_valid=a.n_valid;target.values.n_rain=a.n_rain;
}
const rows=[],rawIndices=new Map();
function savedRates(x,rates){for(let i=0;i<4;i++)if(typeof rates?.[i]==='number')x[30+i]=rates[i];}
function base(r,method,threshold,type='RAW'){
  const x=empty();Object.assign(x,{0:type,1:r.model,2:r.seed,3:r.arm,4:r.population,5:method,6:threshold??'n.a.',7:r.scenes,8:r.n_valid,9:r.n_valid,35:1,36:r.status,37:r.checkpoint,38:r.training_commit,39:r.source_id});return x;
}
function append(r,x,kind,method,threshold){
  const index=rows.length;rows.push(x);if(['RAW','STRATIFIED','QUANTILE'].includes(kind))rawIndices.set(`${r.run_id}|${method}|${threshold??''}`,index);
}
const classification=new Map(d.classifications.map(x=>[`${x[0]}|${x[5]}|${x[6]}`,x]));
for(const r of d.records){
  const x=base(r,'OCC_P：P≥0.5',0.1);
  [r.brier,r.auroc,r.ap,r.pinball,r.coverage,r.q32_bias,r.q32_error].forEach((v,i)=>x[11+i]=v);
  for(const [k,v] of Object.entries(diag.get(r.run_id)||{}))if(k in fieldToColumn&&fieldToColumn[k]>=18)x[fieldToColumn[k]]=v;
  if(typeof x[18]!=='number'){
    const q=[...quantiles.values()].filter(v=>v.rid===r.run_id&&Number.isFinite(v.tau)&&Number.isFinite(v.coverage));
    if(q.length===32)x[18]=q.reduce((sum,v)=>sum+Math.abs(v.coverage-v.tau),0)/32;
  }
  const c=classification.get(`${r.run_id}|OCC_P|0.1`);
  if(c){x[9]=c[7];x[10]=c[8]+c[10];for(let i=0;i<4;i++)x[26+i]=c[8+i];x[34]=0;savedRates(x,c.slice(16,20));}
  x[41]='概率指标与发生分类；q32名义0.984375';append(r,x,'RAW','OCC_P',0.1);
  for(const method of ['A','B','C']){
    const c=d.continuous.find(a=>a[0]===`${r.run_id}|${method}`);if(!c||typeof c[7]!=='number')continue;
    const x=base(r,`${method}：连续误差`,null);for(let i=0;i<4;i++)x[22+i]=c[7+i]??'n.a.';x[36]=c[12];x[39]=c[13];x[41]='全部监督像元；候选NOT_FROZEN';append(r,x,'RAW',`CONT_${method}`,null);
  }
  for(const c of d.classifications.filter(a=>a[0]===r.run_id&&a[5]!=='OCC_P')){
    const x=base(r,c[5],c[6]);x[9]=c[7];x[10]=c[8]+c[10];for(let i=0;i<4;i++)x[26+i]=c[8+i];savedRates(x,c.slice(16,20));x[34]=c[13];x[36]=c[14];x[39]=c[15];x[41]=c[5].startsWith('D_')?'仅当前模型支持子集；不作公平配对/跨seed汇总':'点估计Pred>r，Truth>r；候选NOT_FROZEN';append(r,x,'RAW',c[5],c[6]);
  }
  if(!d.continuous.some(c=>c[1]===r.run_id&&typeof c[7]==='number')){
    const x=base(r,'A/B/C未在原19项回填范围',null,'GAP');x[35]=0;x[36]='NOT_COMPUTED_NO_EXTRA_INFERENCE';x[41]='概率结果已完成；连续/五阈值点估计缺口不填零';rows.push(x);
  }
}
const rainLabels=['(0.1,1]','(1,5]','(5,10]','(10,20]','(20,30]','(30,50]','(50,∞)'];
for(const {rid,group,values:v,archive} of strata.values()){
  if(!Object.keys(v).some(k=>k in fieldToColumn))continue;const r=records.get(rid),rain=group.startsWith('RAIN_'),x=base(r,group,rain?rainLabels[Number(group.slice(5))]:0.1,'STRATIFIED');
  for(const [k,val]of Object.entries(v))if(k in fieldToColumn)x[fieldToColumn[k]]=val;
  x[7]=v.scenes??r.scenes;x[9]=v.n_valid??v.n_rain??'n.a.';x[10]=v.n_rain??'n.a.';x[39]='UNIFIED_METRICS_SAVED';
  if(archive){for(let i=0;i<4;i++)x[26+i]=archive.counts[['TP','FP','FN','TN'][i]];savedRates(x,archive.rates);x[39]=archive.source_id;}
  if(rain){x[16]='n.a.';x[17]='n.a.';x[41]='按真实雨强条件化的覆盖仅描述，不要求各层达到名义覆盖';}
  else x[41]='既有固定分组；非独立天气事件';append(r,x,'STRATIFIED',`GROUP_${group}`,x[6]);
}
for(const q of quantiles.values()){
  if(!Number.isFinite(q.tau)||!Number.isFinite(q.coverage))continue;
  const r=records.get(q.rid),x=base(r,`q${String(q.index+1).padStart(2,'0')} τ=${q.tau}`,null,'QUANTILE');
  x[9]=r.n_rain;x[10]=r.n_rain;x[15]=q.coverage;x[16]=q.coverage-q.tau;x[17]=Math.abs(q.coverage-q.tau);
  x[39]='UNIFIED_METRICS_SAVED';x[41]='仅有雨像元条件分位覆盖；本行偏差相对方法列所示τ。';append(r,x,'QUANTILE',`QUANTILE_${q.index}`,null);
}
for(const a of d.historical_proxies||[]){
  const x=empty();Object.assign(x,{0:'HISTORICAL_NOT_MAIN',1:a.model,2:a.seed,4:a.population,5:'旧phase-A诊断代理',22:a.mae,23:a.rmse,24:a.bias,25:a.cc??'n.a.',35:0,36:a.status,37:'NOT_MAIN_E9',38:'NOT_VERIFIED',39:a.source_id,41:`${a.generation}；仅继承旧值，不进入主E9配对或seed汇总`});rows.push(x);
}
const b9=empty();b9[0]='NOT_STARTED';b9[1]='B9';b9[35]=0;b9[36]='ERA5教师—学生蒸馏可选，未正式训练';rows.push(b9);
const performance=[...Array.from({length:15},(_,i)=>i+11),30,31,32,33];
const rawCount=rows.length,groups=new Map();
for(let i=0;i<rawCount;i++){
  const x=rows[i];if(!['RAW','STRATIFIED','QUANTILE'].includes(x[0])||String(x[5]).startsWith('D_'))continue;
  const key=[x[1],x[3],x[4],x[5],x[6]].join('|');if(!groups.has(key))groups.set(key,[]);groups.get(key).push(i);
}
const formulaRows=[];
function archivedPair(x,mode,seedCount){
  if(x[5]!=='OCC_P：P≥0.5'||x[6]!==0.1)return;
  const key=x[1].replace('−','-')+'|'+(mode?`seed-${mode==='MEAN'?'mean':'sample-sd'}`:`${x[3]}|s${x[2]}`);
  const a=(d.archive_pairs||[]).find(v=>v.comparison===key&&v.population===x[4]);
  if(!a||mode&&(x[3]!=='E0'||seedCount!==3))return;
  for(const [k,c]of Object.entries(archivedFields)){const value=a[k];if(value!==''&&value!=null)x[c]=Number(value);}
  x[39]='TIER0_ARCHIVED_PAIRS';x[41]+='；已有配对值直接复用';
}
function statistics(indices,type){
  if(indices.length<2)return;for(const mode of ['MEAN','SAMPLE_SD']){
    const x=[...rows[indices[0]]];x[0]=type+mode;x[2]=mode;x[35]=indices.length;x[37]='n.a.';x[39]='SAVED_MATCHED_SEED_ROWS';x[41]='同协议训练seed描述性统计；非独立年份或显著性';
    for(let c=11;c<=34;c++)x[c]='n.a.';
    if(type==='PAIR_')archivedPair(x,mode,indices.length);
    const index=rows.length;rows.push(x);formulaRows.push({index,indices,mode});
  }
}
for(const ids of groups.values())statistics(ids,'');
const pairs=[['B1','B0'],['B3','B2'],['B4','B3'],['B5','B4'],['B6','B4'],['B7','B6'],['B8','B7'],['B7','B7_ZERO_DOTE'],['B7','B7_PERP_GRADIENT']];
const pairMeta=[],pairGroups=new Map();
for(const [newer,older]of pairs)for(const [key,ni]of rawIndices){
  const a=rows[ni];if(a[1]!==newer||String(a[5]).startsWith('D_'))continue;
  const otherRecord=d.records.find(r=>r.model===older&&r.seed===a[2]&&r.arm===a[3]&&r.population===a[4]);if(!otherRecord)continue;
  const oi=[...rawIndices.values()].find(i=>{const b=rows[i];return b[1]===older&&b[2]===a[2]&&b[3]===a[3]&&b[4]===a[4]&&b[5]===a[5]&&b[6]===a[6];});if(oi===undefined)continue;
  const b=rows[oi];if(a[9]!==b[9])throw Error('Paired evaluation denominators differ');
  const x=[...a];x[0]='PAIR_DELTA';x[1]=`${newer}−${older}`;x[37]='n.a.';x[40]=b[39];x[41]='实验/新增−参考；'+a[41];
  for(let c=11;c<=34;c++)x[c]='n.a.';
  archivedPair(x,null,1);
  const index=rows.length;rows.push(x);pairMeta.push({index,ni,oi});
  const g=[x[1],x[3],x[4],x[5],x[6]].join('|');if(!pairGroups.has(g))pairGroups.set(g,[]);pairGroups.get(g).push(index);
}
for(const ids of pairGroups.values())statistics(ids,'PAIR_');
const start=6,end=5+rows.length;
sheet.showGridLines=false;sheet.freezePanes.freezeRows(5);sheet.freezePanes.freezeColumns(3);
sheet.mergeCells('A1:L1');sheet.getRange('A1').values=[['YunTAPR-Net V1.3 完整指标与消融对照']];sheet.getRange('A1').format.font={name:'Microsoft YaHei',size:15,bold:true,color:'#16324F'};
sheet.getRange('A1:L1').format.rowHeight=28;
sheet.mergeCells('A2:L2');sheet.getRange('A2').values=[['2024 Development｜固定E9 LAST｜两种人口分开｜全部已保存seed与正负结果｜2025冻结']];sheet.getRange('A2').format.font={name:'Microsoft YaHei',size:10};
sheet.mergeCells('A3:L3');sheet.getRange('A3').values=[['同一张表按记录类型、方法、阈值筛选。A/B/C均未冻结；D支持子集不进行公平排名。B0等模型说明在表格下方。']];sheet.getRange('A3:L3').format.wrapText=true;sheet.getRange('A3').format.rowHeight=30;
for(const [range,label]of [['A4:K4','实验与评价人口'],['L4:V4','概率、覆盖与经验分解'],['W4:Z4','点估计连续误差'],['AA4:AH4','事件识别'],['AI4:AP4','范围与证据']]){sheet.mergeCells(range);sheet.getRange(range).values=[[label]];sheet.getRange(range).format={fill:'#DCE6F1',font:{name:'Microsoft YaHei',bold:true,size:10},horizontalAlignment:'center'};}
sheet.getRange('A5:AP5').values=[headers];sheet.getRange(`A6:AP${end}`).values=rows;
sheet.getRange(`A5:AP${end}`).format.font={name:'Microsoft YaHei',size:10,color:'#111827'};sheet.getRange(`A5:AP${end}`).format.rowHeight=22;sheet.getRange(`A5:AP${end}`).format.columnWidth=18;
sheet.getRange('A5:AP5').format={fill:'#1F4E78',font:{name:'Microsoft YaHei',size:10,bold:true,color:'#FFFFFF'},wrapText:true,horizontalAlignment:'center',verticalAlignment:'center',rowHeight:48};
sheet.getRange(`L6:AH${end}`).setNumberFormat('0.00000000');sheet.getRange(`P6:S${end}`).setNumberFormat('0.0000%');sheet.getRange(`AE6:AH${end}`).setNumberFormat('0.0000%');sheet.getRange(`AA6:AD${end}`).setNumberFormat('#,##0');sheet.getRange(`H6:K${end}`).setNumberFormat('#,##0');sheet.getRange(`AI6:AJ${end}`).setNumberFormat('#,##0');
sheet.getRange(`H6:AJ${end}`).format.horizontalAlignment='right';sheet.getRange(`C6:E${end}`).format.horizontalAlignment='center';
sheet.getRange(`A5:B${end}`).format.columnWidth=30;sheet.getRange(`F5:F${end}`).format.columnWidth=42;sheet.getRange(`AK5:AK${end}`).format.columnWidth=55;sheet.getRange(`AL5:AM${end}`).format.columnWidth=70;sheet.getRange(`AN5:AO${end}`).format.columnWidth=44;sheet.getRange(`AP5:AP${end}`).format.columnWidth=85;
const formulas=rows.map(()=>Array(23).fill(''));
for(let i=0;i<rawCount;i++){
  const x=rows[i],r=i+start;if(x[0]!=='RAW'||typeof x[26]!=='number')continue;
  // Previously saved rates remain source values; only missing rates are built.
  if(x.slice(30,34).every(v=>typeof v==='number'))continue;
  formulas[i][19]=`=IF(SUM(AA${r},AC${r})=0,"n.a.",AA${r}/SUM(AA${r},AC${r}))`;
  formulas[i][20]=`=IF(SUM(AA${r}:AB${r})=0,"n.a.",AB${r}/SUM(AA${r}:AB${r}))`;
  formulas[i][21]=`=IF(SUM(AA${r}:AC${r})=0,"n.a.",AA${r}/SUM(AA${r}:AC${r}))`;
  formulas[i][22]=`=IF((AA${r}+AC${r})*(AC${r}+AD${r})+(AA${r}+AB${r})*(AB${r}+AD${r})=0,"n.a.",2*(AA${r}*AD${r}-AB${r}*AC${r})/((AA${r}+AC${r})*(AC${r}+AD${r})+(AA${r}+AB${r})*(AB${r}+AD${r})))`;
}
for(const {index,ni,oi}of pairMeta)for(const c of performance)if(typeof rows[index][c]!=='number')formulas[index][c-11]=`=IF(AND(ISNUMBER(${col(c)}${ni+start}),ISNUMBER(${col(c)}${oi+start})),${col(c)}${ni+start}-${col(c)}${oi+start},"n.a.")`;
for(const {index,indices,mode}of formulaRows)for(const c of performance){if(typeof rows[index][c]==='number')continue;const refs=indices.map(i=>`${col(c)}${i+start}`).join(',');formulas[index][c-11]=`=IF(COUNT(${refs})<${mode==='MEAN'?1:2},"n.a.",${mode==='MEAN'?'AVERAGE':'STDEV'}(${refs}))`;}
// Only rectangular formula blocks with real formulas are written; blank entries
// must not erase archived numeric probability/continuous source cells.
for(let c=0;c<23;c++){
  let i=0;while(i<rows.length){if(!formulas[i][c]){i++;continue;}let j=i;while(j+1<rows.length&&formulas[j+1][c])j++;sheet.getRange(`${col(c+11)}${i+start}:${col(c+11)}${j+start}`).formulas=formulas.slice(i,j+1).map(x=>[x[c]]);i=j+1;}
}
const table=sheet.tables.add(`A5:AP${end}`,true,'CompleteResearchMetrics');table.style='TableStyleLight9';
const definitions=[
 'B0：B13单通道、单时次。历史Train10455/Dev10501；seed2026/2027。',
 'B1：B13单通道、六时次。与B0同seed、同损失臂比较；E0/E1/E2不是三个独立seed。',
 'B2：七通道单时次t−10分钟，seed2029；B3：七通道六时次，seed2029/2030/2031。',
 'B4：B3增加13变量GFS MEE（气象环境编码器）；B5：B4增加海拔；B6：B4增加静态地形六通道。',
 'B7：B6增加DOTE动态地形数值及concat（拼接）残差融合。B8：相同条件信息下，单SP04 DTFM（地形条件特征调制）替换融合形式，不是多尺度已获验证。',
 'B7_ZERO_DOTE：8个数值置零、真实mask保留；128个输入权重无损失梯度，因此名义参数相等不代表有效容量相等。',
 'B7_PERP_GRADIENT：仅DOTE内部梯度固定90°旋转；真实GFS/DEM/mask保留。单seed方向性探针，分布及空间混杂仍在。',
 'B9：ERA5教师—学生蒸馏为可选计划，尚无正式训练或评价，不填写虚假数字。',
 'A：p×mean(expm1(q))物理尺度分位均值代理；B：混合中位数；C：p×expm1(mean(q))对数尺度均值逆变换代理，不是真实条件算术均值。全部NOT_FROZEN。',
 'OCC_P：P(rain>0.1)≥0.5；A/B/C分类：Pred>r且Truth>r。FAR为FP/(TP+FP)，不是FP/(FP+TN)。D只报告分位数可支持子集。',
 '连续误差为mm/h、CC无量纲；条件Pinball为冻结log1p(mm/h)尺度。经验REL/RES是样本分数分解，不是总体校准或因果证据。',
 'Brier：布里尔分数；AUROC：ROC曲线下面积；AP：平均精确率；REL：经验可靠性项；RES：经验分辨能力项；UNC：不确定性项。',
 '总体行覆盖列为q32，名义0.984375；QUANTILE行显示方法列指定q01–q32及τ。覆盖偏差/绝对误差均相对该行名义τ。按真实雨强分层仅描述。',
 'MEAN/SAMPLE_SD是同模型/方法/阈值的逐seed性能描述；PAIR为实验组−参考组。单seed不计算样本SD；D部分支持不汇总或公平排名。',
 '各性能指标只使用实际存在的数值，少于2个有效值不显示样本SD；不能把可用seed数当作独立天气事件数。',
 'TP/FP/FN/TN保留RAW逐seed计数；原始分类行的四计数之和等于当前评价分母。均值/SD不把seed计数合并成新人口。',
 '不同训练人口不得直接归因排名；同一2024 Dev被重复使用。核心959/963人口中>50mm/h仅6个像元时次，不是6场独立暴雨；无显著性或独立年份结论。',
 'PAIR覆盖/率差以百分格式显示，其数值表示百分点差而非相对改善比例。负对照保留全部正面、负面及近零结果。',
 'B0/B1的E1/E2、ZERO控制与新方向性探针未纳入原19-run点估计回填；缺失明确保留，不新增未批准推理，不以旧phase-A代理替代主表E9。',
 '32分位平均覆盖误差优先复用既有诊断；缺少该汇总但32个覆盖/τ齐全时，取其绝对偏差算术均值，不新增推理。',
 '既有Tier0总体、分组、分类及配对指标直接复用；HISTORICAL_NOT_MAIN是不同旧BEST权重的代理记录，不进入当前E9比较。新增推理只补缺失点估计；同次前向中的冻结概率gate不是额外推理轮次。',
 'DOTE是既有GFS与DEM的确定性物理启发代理量，不是新增观测或实测垂直速度；训练结果不能单独证明迎风抬升因果。',
 `数据状态：${d.status}；19项主回填完成${d.metric_runs_complete}/19；新方向性探针封口=${d.candidate_closed}。2025最终测试继续冻结。`
];
for(const s of d.sources)definitions.push(`证据 ${s[0]}：字节SHA256=${s[1]}；${s[5]||'LOCAL_ONLY原件，公开脱敏ID'}`);
const notesStart=end+3;
sheet.mergeCells(`A${notesStart}:L${notesStart}`);sheet.getRange(`A${notesStart}`).values=[['模型解释、指标口径与证据']];sheet.getRange(`A${notesStart}`).format.font={name:'Microsoft YaHei',size:12,bold:true};
for(let i=0;i<definitions.length;i++){const r=notesStart+1+i;sheet.mergeCells(`A${r}:L${r}`);sheet.getRange(`A${r}`).values=[[definitions[i]]];sheet.getRange(`A${r}:L${r}`).format={font:{name:'Microsoft YaHei',size:10},wrapText:true,rowHeight:32};}
if(JSON.stringify({headers,definitions,rows}).includes('导师'))throw Error('Forbidden audience wording found');
wb.recalculate();
// Check consequential formulas against independent arithmetic, including FAR.
let checked=0;
for(let i=0;i<rawCount;i++){
  const x=rows[i];if(x[0]!=='RAW'||typeof x[26]!=='number')continue;const [tp,fp,fn,tn]=x.slice(26,30);if(tp+fp+fn+tn!==x[9])throw Error('Contingency count mismatch');
  if(checked<8){const v=sheet.getRange(`AE${i+start}:AH${i+start}`).values[0],expected=[tp+fn?tp/(tp+fn):'n.a.',tp+fp?fp/(tp+fp):'n.a.',tp+fp+fn?tp/(tp+fp+fn):'n.a.',(tp+fn)*(fn+tn)+(tp+fp)*(fp+tn)?2*(tp*tn-fp*fn)/((tp+fn)*(fn+tn)+(tp+fp)*(fp+tn)):'n.a.'];for(let k=0;k<4;k++)if(typeof expected[k]==='number'&&(typeof v[k]!=='number'||Math.abs(v[k]-expected[k])>1e-10))throw Error('Classification formula mismatch');checked++;}
}
for(const p of [pairMeta[0],pairMeta[Math.floor(pairMeta.length/2)],pairMeta.at(-1)].filter(Boolean))for(const c of performance){
  const a=rows[p.ni][c],b=rows[p.oi][c];if(typeof a!=='number'||typeof b!=='number')continue;
  const actual=sheet.getRange(`${col(c)}${p.index+start}`).values[0][0];
  if(typeof actual!=='number'||Math.abs(actual-(a-b))>1e-10)throw Error('Paired formula mismatch');
}
const probe=pairMeta.find(p=>formulas[p.index][0]&&typeof rows[p.ni][11]==='number'&&typeof rows[p.oi][11]==='number');
if(probe){
  const source=sheet.getRange(`L${probe.ni+start}`),before=source.values[0][0];source.values=[[before+.001]];wb.recalculate();
  const expected=before+.001-rows[probe.oi][11],actual=sheet.getRange(`L${probe.index+start}`).values[0][0];
  if(typeof actual!=='number'||Math.abs(actual-expected)>1e-10)throw Error('Input-change recalculation mismatch');
  source.values=[[before]];wb.recalculate();
}
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:20},maxChars:3000});
await fs.mkdir(path.dirname(output),{recursive:true});await fs.writeFile(path.join(path.dirname(output),'formula_error_scan.ndjson'),errors.ndjson);
if(errors.ndjson.split('\n').some(line=>{try{const x=JSON.parse(line);return x.kind==='match'&&/#REF!|#DIV\/0!|#VALUE!|#NAME\?|#N\/A|#NUM!/.test(JSON.stringify(x));}catch{return false;}}))throw Error('Workbook formula error detected');
const previewDir=path.join(path.dirname(output),'previews');await fs.mkdir(previewDir,{recursive:true});const previews=[];
for(const range of ['A1:K12','L4:V12','W4:AH12','AI4:AP12',`A${notesStart}:L${notesStart+10}`]){const name=`single_table_${previews.length+1}.png`,blob=await wb.render({sheetName:'完整指标',range,scale:1.2,format:'png'});await fs.writeFile(path.join(previewDir,name),new Uint8Array(await blob.arrayBuffer()));previews.push(name);}
console.log((await wb.inspect({kind:'region',sheetId:'完整指标',range:'L5:V8',tableMaxRows:4,tableMaxCols:11,maxChars:2000})).ndjson);
const verification={status:'PASS_IN_MEMORY_SINGLE_TABLE_REQUIRES_VISUAL_REVIEW',worksheets:1,tableCount:1,columns:42,dataRows:rows.length,recordTypes:Object.fromEntries([...new Set(rows.map(x=>x[0]))].map(k=>[k,rows.filter(x=>x[0]===k).length])),notesStart,modelExplanationsBelow:true,noAudienceWording:true,metricRuns:d.metric_runs_complete,candidateClosed:d.candidate_closed,classificationChecks:checked,pairedArithmeticChecks:true,inputChangeRecalculation:true,defaultCandidate:'ALL_METHODS_SEPARATE_NO_SELECTION',previews};
await fs.writeFile(path.join(path.dirname(output),'workbook_verification.json'),JSON.stringify(verification,null,2));
if(args.includes('--layout-preview-only')){console.log(JSON.stringify(verification));process.exit(0);}
const xlsx=await SpreadsheetFile.exportXlsx(wb);await xlsx.save(output);console.log(JSON.stringify({status:'EXPORTED_SINGLE_TABLE_FOR_VISUAL_REVIEW',output,rows:rows.length,columns:42,worksheets:1}));
