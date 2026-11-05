import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
const out=path.resolve(process.argv[2]);
const require=createRequire(path.join(out,'entry.cjs'));
const {Workbook,SpreadsheetFile,FileBlob}=await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);
const d=JSON.parse(await fs.readFile(path.join(out,'evaluation_data_internal.json'),'utf8'));
const terrain=JSON.parse(await fs.readFile(path.join(out,'terrain_reaggregation_internal.json'),'utf8'));
const dist=JSON.parse(await fs.readFile(path.join(out,'terrain_distribution.json'),'utf8'));
if(terrain.status!=='PASS')throw Error('Terrain reaggregation not verified');
const preview=path.join(out,'previews');await fs.mkdir(preview,{recursive:true});
const template=path.resolve('../YunTAPR-metric-backfill-20261029/outputs/YunTAPR-Net基线指标与消融对照_v1_Tier0_20261029.xlsx');
const old=await SpreadsheetFile.importXlsx(await FileBlob.load(template));
const ref=await old.render({sheetName:old.worksheets.getItemAt(0).name,range:'A1:H14',scale:1,format:'png'});
await fs.writeFile(path.join(preview,'reference.png'),new Uint8Array(await ref.arrayBuffer()));
const wb=Workbook.create();
const titles=['01 策略名称与颜色','02 单时次反演指标','03 日累计反演指标','04 地形分层反演指标','05 评价定义与证据追溯'];
const sheets=titles.map(n=>wb.worksheets.add(n));
const T=[.1,1,5,10,20],metrics=['POD','FAR','CSI','HSS'];
const colors=['EAF2F8','FCEFE8','EAF4E8','F4ECF7','FFF4D6','E2F0ED','F7E6EC','E8EDF8','EDE8F5','F1F1F1'];
const labels=['策略一','策略二','策略三','策略四','策略五','策略六','策略七','策略八','策略九','策略十'];
const full=['单通道单时次反演','单通道六时次反演','七通道单时次反演','七通道六时次反演','七通道六时次融合 GFS 环境场','GFS 环境场融合 DEM 高程','GFS 环境场融合完整静态地形特征','完整静态地形融合 DOTE 动态地形特征（简单拼接）','DOTE 动态地形融合 DTFM 多尺度条件调制','策略九融合 ERA5 教师—学生知识蒸馏（可选，暂缓）'];
const col=n=>{let s='';for(n++;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
const quote=s=>`'${s}'`;
const trace=(letter,row)=>`${quote(titles[4])}!${letter}${row}`;
function value(ws,cell,v){ws.getRange(cell).values=[[v]];}
function formula(ws,cell,v){ws.getRange(cell).formulas=[[v]];}
function setup(ws,title,note,headers,rows,tableName,widths={}){
  const end=col(headers.length-1),last=5+rows.length;
  ws.showGridLines=false;ws.tabColor='#344C61';
  ws.getRange(`A1:${end}${last}`).format={font:{name:'Microsoft YaHei',size:10,color:'#243442'},verticalAlignment:'center',rowHeight:27};
  value(ws,'A2',title);ws.getRange('A2').format.font={name:'Microsoft YaHei',size:15,bold:true,color:'#243442'};
  value(ws,'A3',note);ws.getRange('A3').format.font={name:'Microsoft YaHei',size:10,color:'#5F6B72'};
  ws.getRange(`A5:${end}5`).values=[headers];
  if(rows.length)ws.getRange(`A6:${end}${last}`).values=rows;
  ws.getRange(`A5:${end}5`).format={fill:'#344C61',font:{name:'Microsoft YaHei',size:10,bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:54,horizontalAlignment:'center'};
  ws.getRange(`A6:${end}${last}`).setNumberFormat('0.0000');
  for(let c=0;c<headers.length;c++)ws.getRange(`${col(c)}5:${col(c)}${last}`).format.columnWidth=widths[c]||13;
  const table=ws.tables.add(`A5:${end}${last}`,true,tableName);table.showFilterButton=true;
  ws.freezePanes.freezeRows(5);ws.freezePanes.freezeColumns(1);
  return last;
}
function paint(ws,row,strategy,lastCol){ws.getRange(`A${row}:${col(lastCol)}${row}`).format.fill='#'+colors[strategy];}
function aggregate(ws,cell,refs,n,sd=false){
  const list=refs.join(',');
  formula(ws,cell,`=IF(COUNT(${list})=${n},${sd?'STDEV.S':'AVERAGE'}(${list}),"未定义")`);
}

const provenanceHeaders=['记录类别','策略名称','评价分组','Seed','阈值(mm/h)','N像元时次','真值事件N','TP','FP','FN','TN','POD','FAR','CSI','HSS','RMSE(mm/h)','Brier Score','状态说明','来源ID','Checkpoint SHA256','评价代码SHA256','训练版本或绑定状态'];
const raw=[];const lookup=new Map();const terrainLookup=new Map();
function addRaw(rr,g,t,n,ct,rmse,brier,source){
  const row=raw.length+6;
  raw.push([g==='全域'?'单时次原始统计':'高程原始统计',rr.strategy_name,g,rr.seed,t,n,ct.TP+ct.FN,ct.TP,ct.FP,ct.FN,ct.TN,null,null,null,null,rmse,brier,'本轮确认近似期望雨强；固定E9终点',source,rr.checkpoint_sha256,rr.evaluation_code_sha256,rr.training_commit]);
  return row;
}
for(const r of d.runs)for(const t of T)lookup.set(`${r.run_id}|${t}`,addRaw(r,'全域',t,r.n_valid,r.counts[t===.1?'0.1':t.toFixed(1)],r.rmse,r.brier,r.result_source));
const gNames={low:'低海拔 H<1000m',middle:'中海拔 1000≤H≤2000m',high:'高海拔 H>2000m'};
for(const r of terrain.rows){const rr=d.runs.find(x=>x.run_id===r.run_id);terrainLookup.set(`${r.run_id}|${r.group}|${r.threshold}`,addRaw(rr,gNames[r.group],r.threshold,r.n,r.counts,r.rmse,null,'SAVED_JOINT_'+r.run_id));}
const auditLast=setup(sheets[4],'评价定义与内部证据追溯','原始统计及权重身份仅供内部追溯；指标定义、缺口和待决事项见下方说明区。',provenanceHeaders,raw,'EvidenceRows',{0:23,1:12,2:29,3:10,4:13,5:16,6:15,15:17,16:15,17:47,18:31,19:74,20:74,21:58});
for(let i=0;i<raw.length;i++){
  const row=i+6,rr=raw[i],s=labels.indexOf(rr[1]);paint(sheets[4],row,s,21);
  formula(sheets[4],`L${row}`,`=IF(H${row}+J${row}=0,"未定义",H${row}/(H${row}+J${row}))`);
  formula(sheets[4],`M${row}`,`=IF(H${row}+I${row}=0,"未定义",I${row}/(H${row}+I${row}))`);
  formula(sheets[4],`N${row}`,`=IF(H${row}+I${row}+J${row}=0,"未定义",H${row}/(H${row}+I${row}+J${row}))`);
  formula(sheets[4],`O${row}`,`=IF((H${row}+I${row})*(I${row}+K${row})+(H${row}+J${row})*(J${row}+K${row})=0,"未定义",2*(H${row}*K${row}-I${row}*J${row})/((H${row}+I${row})*(I${row}+K${row})+(H${row}+J${row})*(J${row}+K${row})))`);
}
sheets[4].getRange(`D6:K${auditLast}`).setNumberFormat('#,##0');sheets[4].getRange(`E6:E${auditLast}`).setNumberFormat('0.0');
sheets[4].getRange(`D6:D${auditLast}`).setNumberFormat('0');
const notes=[
 ['定义','POD','TP/(TP+FN)。分母为0时未定义。'],
 ['定义','FAR','FP/(TP+FP)，不是FPR。无预测事件时未定义。'],
 ['定义','CSI','TP/(TP+FP+FN)。'],
 ['定义','HSS','2(TP×TN−FP×FN)/[(TP+FP)(FP+TN)+(TP+FN)(FN+TN)]。'],
 ['定义','RMSE','sqrt(mean((近似期望雨强−参考雨强)^2))，单位mm/h。日累计单位mm/day。'],
 ['定义','Brier Score','mean((P(R>0.1mm/h)−I(R>0.1mm/h))^2)，无量纲，真实发生概率输出。'],
 ['定义','日累计Bias','mean(预测日累计−参考日累计)，mm/day。当前无完整日，不计算。'],
 ['本轮确认','点估计与分类','近似期望雨强=p×mean(expm1(q_i))，i=1…32；不是精确尾部积分。预测值>阈值；真值按float32与float32阈值作严格>比较。'],
 ['本轮确认','日界',d.day_boundary+'；UTC按开始日期命名，左闭右开。每日期须48个连续、有效、无重复窗口，预测与标签完全相同。'],
 ['定义','日累计换算','IMERG和预测均为30分钟平均雨强mm/h：日量=Σ(48窗雨强×0.5小时)。缺测不填0。'],
 ['数据','时间对齐','单时次目标为IMERG V07 Final半小时窗口。核心样本起点UTC05:30/11:30/17:30/23:30，GFS为f006回溯场；不是整天连续输出。'],
 ['数据','空间与有效性','SP04 0.1°目标网格；云南行政区3430格点；有效性=IMERG有效mask∩云南mask，不按策略缩小mask。'],
 ['可比性','两种开发集','策略一、二：10455 Train/10501 Dev；策略三至九：959 Train/963 Dev。均为2024开发年；不得跨样本群体严格配对归因。'],
 ['统计','多Seed呈现','主表“均值”及“±样本标准差”分行显示，SD采用n−1。单Seed只列单Seed结果，不填SD。任何Seed指标未定义时不对其余Seed静默求平均。'],
 ['阈值','单时次/地形','0.1、1、5、10、20 mm/h。高程：H<1000；1000≤H≤2000；H>2000m。本次九份缓存恰为1000/2000m的点均为0。'],
 ['阈值','日累计','0.1、10、25、50 mm/day；100mm/day扩展未开展，当前没有完整日样本。'],
 ['已核验','19份单时次收据','各份既有gate通过；权重SHA与registry一致；五阈值四格计数总和=N；本轮由真实保存计数重新算比率，无新推理。'],
 ['已核验','9份高程补算',`一次获批缓存补算：${terrain.actual_bytes.toLocaleString('en-US')}字节、1089块、${terrain.actual_seconds.toFixed(2)}秒；三档高程五阈值。总体计数和RMSE与原件一致，无重试。`],
 ['缺口','日累计',`核心245日期仅963窗，最多4窗/日，完整日0。补足日历共缺10797窗/模型；这是日历缺口，不是已获准可用推理样本。内部缺口清单已保存。`],
 ['预算待定','新增日累计推理',`先确认完整日期、非整点GFS对齐及输入可用性。245天核心15终点共缺161955次场景前向；按历史耗时/源量线性估算约${d.daily.provisional_core_estimate.linear_wall_hours.toFixed(1)}小时串行墙钟、${(d.daily.provisional_core_estimate.linear_source_bytes/2**40).toFixed(2)}TiB。不含策略一、二、标签及重新准入；不是可执行预算或授权。`],
 ['缺口','其余策略高程分类','策略一、二、三、四、六、七未找到可直接配高程的完整逐像元预测；本轮无新增GPU/批量原始读取授权，统一待评价。'],
 ['分布','坡度（目标网格）',`3430点全部有效；最小${dist.slope_quantiles_degrees.min.toFixed(4)}°，Q25=${dist.slope_quantiles_degrees.q25.toFixed(4)}°，中位=${dist.slope_quantiles_degrees.q50.toFixed(4)}°，Q75=${dist.slope_quantiles_degrees.q75.toFixed(4)}°，最大${dist.slope_quantiles_degrees.max.toFixed(4)}°。`],
 ['待决','坡度与坡向','建议坡度采用冻结静态网格四分位分层（须保留未舍入阈值）；坡向按北[315,360)∪[0,45)、东[45,135)、南[135,225)、西[225,315)四组。未获确认，不计算分组指标。'],
 ['分布','坡向','上述建议四组格点数：北630、东1075、南739、西986。分布检查不等于分组规则获准。'],
 ['缺口','W/L/M动态分层','未找到训练集冻结的W/L/M分位数阈值。已有迎/背风符号与PWAT参考分组不等同W/L/M分位数。未使用开发集拟合。'],
 ['实现限制','策略七与策略九','策略七实际静态通道为H、东西/南北米制梯度、坡度、sin/cos坡向；策略九为单SP04调制替换，名称保留导师指定方案名，不声称已证明多尺度。'],
 ['原件缺口','科研原则与指定旧表','科研原则.txt和指定20261029导师汇报文件未找到。已读本轮任务原则、项目约定与2026-09-24 V1.3正式方案PDF。格式参考可用20261029 Tier0工作簿，数值依据最新20261031已核验结果。'],
 ['原件缺口','旧盘权重','策略一、二旧H盘路径本轮不可用。保存收据存在且通过一致性门槛；当前权重可访问性不等同历史身份已被推翻，不重复加载权重。'],
 ['保护','2025与其他工作','2025最终测试数据未访问；新训练/新推理/原始气象读取/模型加载均0；本轮不开展其他指标、报告平台或科学结论定稿。'],
 ['待研究者决定','日累计方案','共同完整日期范围、非整点GFS输入对齐和补充推理预算须另行批准；日界与近似期望雨强规则本轮已确认，无须重复确认。'],
 ['待研究者决定','样本不足','未定义分母与N/真值事件N均保留。小样本充分性标准及独立事件定义未冻结，不把海量相关像元当作独立事件，不据此作显著性或因果结论。'],
];
const notesStart=auditLast+4;
sheets[4].getRange(`A${notesStart}:C${notesStart}`).values=[['类别','项目','定义、证据和未完成事项']];
sheets[4].getRange(`A${notesStart}:C${notesStart}`).format={fill:'#344C61',font:{name:'Microsoft YaHei',size:10,bold:true,color:'#FFFFFF'},rowHeight:28};
for(let i=0;i<notes.length;i++){
 const r=notesStart+1+i;value(sheets[4],`A${r}`,notes[i][0]);value(sheets[4],`B${r}`,notes[i][1]);
 sheets[4].mergeCells(`C${r}:H${r}`);value(sheets[4],`C${r}`,notes[i][2]);
 sheets[4].getRange(`A${r}:H${r}`).format={font:{name:'Microsoft YaHei',size:10,color:'#243442'},wrapText:true,rowHeight:57,verticalAlignment:'center'};
}

const factors=['基线','增加卫星历史时次','增加卫星通道','多通道与多时次结合','增加GFS环境场','增加DEM高程','增加其余静态地形通道','增加DOTE动态地形','以DTFM条件调制替换简单拼接','可选ERA5知识蒸馏'];
const strategyRows=labels.map((l,i)=>[l,full[i],'#'+colors[i],factors[i],i===9?'暂缓，不进入本轮比较':`固定终点已完成；${d.groups[i].seeds.length}个Seed`,i===8?'当前为单SP04实现，尚非多尺度验证':i===6?'实际为6个静态通道，详见内部追溯':'' ]);
setup(sheets[0],'YunTAPR-Net 策略名称与颜色','2024开发集；策略十暂缓。颜色在本工作簿各表一致。',['策略','完整中文名称','固定颜色','新增因素','实验状态','实现范围说明'],strategyRows,'Strategies',{0:12,1:69,2:15,3:33,4:34,5:46});
strategyRows.forEach((r,i)=>paint(sheets[0],i+6,i,5));

const singleRows=[];const singleMeta=[];
for(const g of d.groups){
 for(const sd of g.seeds.length>1?[false,true]:[false]){
  singleMeta.push({g,sd,row:singleRows.length+6});
  singleRows.push([g.name,sd?'±样本标准差':g.seeds.length===1?'单Seed结果':'均值',g.seeds.length,g.protocol,g.train,g.dev,g.n_valid,...Array(22).fill(null)]);
 }
}
const sh=['策略名称','统计量','Seed数量','样本协议','Train场景数','Dev场景数','有效像元时次N',...T.flatMap(t=>metrics.map(m=>`${t} mm/h\n${m}${m==='FAR'?'↓':'↑'}`)),'RMSE↓\n(mm/h)','Brier Score↓'];
setup(sheets[1],'不同策略单时次（30分钟目标时间窗）降水反演性能对比表','近似期望雨强规则已于本轮确认。多Seed均值及±样本标准差分行显示；两种样本协议须分别比较。',sh,singleRows,'InstantMetrics',{0:12,1:19,2:12,3:26,4:15,5:15,6:20,27:17,28:18});
for(const {g,sd,row}of singleMeta){
 paint(sheets[1],row,g.strategy,28);sheets[1].getRange(`C${row}:G${row}`).setNumberFormat('#,##0');
 sheets[1].getRange(`C${row}`).format.horizontalAlignment='center';
 const runs=d.runs.filter(r=>r.strategy===g.strategy);
 T.forEach((t,ti)=>metrics.forEach((m,mi)=>aggregate(sheets[1],`${col(7+ti*4+mi)}${row}`,runs.map(r=>trace(col(11+mi),lookup.get(`${r.run_id}|${t}`))),runs.length,sd)));
 aggregate(sheets[1],`AB${row}`,runs.map(r=>trace('P',lookup.get(`${r.run_id}|0.1`))),runs.length,sd);
 aggregate(sheets[1],`AC${row}`,runs.map(r=>trace('Q',lookup.get(`${r.run_id}|0.1`))),runs.length,sd);
}

const dayRows=d.groups.map(g=>[g.name,g.seeds.length,0,d.day_boundary,...Array(18).fill('待评价'),'缺少共同连续48窗；未填0']);
setup(sheets[2],'不同策略24小时日累计降水反演性能对比表','完整共同日期=0；本表不含估计指标。内部UTC日期起点00:00，左闭右开；缺测不补零。',['策略名称','Seed数量','有效日期数','正式日界',...[.1,10,25,50].flatMap(t=>metrics.map(m=>`${t} mm/day\n${m}${m==='FAR'?'↓':'↑'}`)),'RMSE↓\n(mm/day)','Bias\n(mm/day)','状态'],dayRows,'DailyMetrics',{0:12,1:12,2:15,3:72,20:18,21:18,22:40});
dayRows.forEach((_,i)=>{paint(sheets[2],i+6,i,22);sheets[2].getRange(`B${i+6}:C${i+6}`).setNumberFormat('#,##0');});

const terrainRows=[];const terrainMeta=[];
for(const si of [4,7,8,5,6,0,1,2,3])for(const g of [d.groups[si]])for(const group of ['low','middle','high'])for(const t of T){
 const rr=terrain.rows.filter(r=>r.strategy===g.strategy&&r.group===group&&r.threshold===t);
 for(const sd of rr.length>1?[false,true]:[false]){
  const row=terrainRows.length+6;terrainMeta.push({g,group,t,rr,sd,row});
  terrainRows.push([g.name,'高程',gNames[group],t,sd?'±样本标准差':!rr.length?'待评价':rr.length===1?'单Seed结果':'均值',rr.length,rr.length?rr[0].n:'待评价',rr.length?rr[0].counts.TP+rr[0].counts.FN:'待评价',...Array(5).fill(rr.length?null:'待评价'),rr.length?'真实预测补算；独立事件数未定义':'缺少可配高程的逐像元预测']);
 }
}
for(const g of d.groups)for(const category of ['坡度','坡向','W/L/M动态地形'])terrainRows.push([g.name,category,'分组规则或训练集阈值待确认','待确认','待评价',0,'待评价','待评价',...Array(5).fill('待评价'),'未按开发集结果选择分组；未计算']);
setup(sheets[3],'不同策略在云南复杂地形条件下的降水反演性能对比表','五个雨强阈值与单时次主表一致；完整地形分类结果当前覆盖策略五、八、九。', ['策略名称','地形类别','高程或动态地形分组','阈值(mm/h)','统计量','已评价Seed数','有效像元时次N','真值超阈N','POD↑','FAR↓','CSI↑','HSS↑','RMSE↓(mm/h)','状态与限制'],terrainRows,'TerrainMetrics',{0:12,1:20,2:39,3:15,4:19,5:16,6:21,7:19,12:20,13:53});
for(let i=0;i<terrainRows.length;i++)paint(sheets[3],i+6,labels.indexOf(terrainRows[i][0]),13);
for(const {g,group,t,rr,sd,row}of terrainMeta){
 sheets[3].getRange(`F${row}:H${row}`).setNumberFormat('#,##0');sheets[3].getRange(`D${row}`).setNumberFormat('0.0');
 sheets[3].getRange(`D${row}:F${row}`).format.horizontalAlignment='center';
 if(!rr.length)continue;
 for(let mi=0;mi<4;mi++)aggregate(sheets[3],`${col(8+mi)}${row}`,rr.map(r=>trace(col(11+mi),terrainLookup.get(`${r.run_id}|${group}|${t}`))),rr.length,sd);
 aggregate(sheets[3],`M${row}`,rr.map(r=>trace('P',terrainLookup.get(`${r.run_id}|${group}|${t}`))),rr.length,sd);
}
wb.recalculate();
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:50},maxChars:3000});
await fs.writeFile(path.join(out,'formula_scan.ndjson'),errors.ndjson);
const check=await wb.inspect({kind:'table',range:`'${titles[1]}'!A5:AC20`,include:'values,formulas',tableMaxRows:16,tableMaxCols:29,maxChars:1700});
await fs.writeFile(path.join(out,'workbook_check.ndjson'),check.ndjson);
for(let i=0;i<sheets.length;i++){
 const range=i===0?'A1:F15':i===1?'A1:M20':i===2?'A1:H15':i===3?'A1:N22':'A1:Q12';
 const img=await wb.render({sheetName:titles[i],range,scale:1,format:'png'});
 await fs.writeFile(path.join(preview,`sheet${i+1}.png`),new Uint8Array(await img.arrayBuffer()));
}
const definitionsImage=await wb.render({sheetName:titles[4],range:`A${notesStart}:H${notesStart+8}`,scale:1,format:'png'});
await fs.writeFile(path.join(preview,'definitions.png'),new Uint8Array(await definitionsImage.arrayBuffer()));
const final=path.join(out,'YunTAPR-Net_三类反演评价_20261105.xlsx');
await (await SpreadsheetFile.exportXlsx(wb)).save(final);
await fs.writeFile(path.join(out,'build_metadata.json'),JSON.stringify({file:final,sheets:titles,raw_rows:raw.length,notes_start:notesStart,main_rows:singleRows.length,terrain_rows:terrainRows.length,template,formulas:'Per-seed ratios from raw counts; mean and sample SD from same protocol seeds',native_Excel_check:'NOT_RUN',expected_metrics:d.groups},null,2));
console.log(JSON.stringify({saved:final,worksheets:5,raw_rows:raw.length,main_rows:singleRows.length,terrain_rows:terrainRows.length,notes_start:notesStart}));
