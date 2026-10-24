'use strict';
const $=id=>document.getElementById(id);
const nf=new Intl.NumberFormat('zh-CN');
const labels={PENDING:'待开始',TRAINING:'训练中',VALIDATION:'Dev 验证中',VALIDATED:'待封存 LAST',SEALED:'已封存 LAST'};
let snapshot=null,busy=false,lastGood=0,timer=null;
const number=(x,d=5)=>typeof x==='number'&&Number.isFinite(x)?x.toFixed(d):'—';
const count=x=>typeof x==='number'?nf.format(x):'—';
const gib=x=>typeof x==='number'?(x/2**30).toFixed(2)+' GiB':'—';
const cell=(row,text,cls)=>{const e=document.createElement('td');e.textContent=text;if(cls)e.className=cls;row.append(e);return e;};
const delta=(a,b)=>typeof a==='number'&&typeof b==='number'?b-a:null;
const deltaCell=(row,x,direction=0)=>{const text=x===null?'—':(x>0?'+':'')+number(x);cell(row,text,x!==null&&direction&&x!==0?(x*direction>0?'good':'bad'):'');};
function current(run){return run.epochs.find(e=>e.phase!=='SEALED')||run.epochs[8];}
function renderModels(s){
  $('models').replaceChildren();
  for(const run of s.runs){
    const art=document.createElement('article');art.className='model';
    const top=document.createElement('div');top.className='model-top';
    const h=document.createElement('h3');h.textContent=run.model;
    const n=document.createElement('span');n.className='model-count';n.textContent=count(run.returned)+' / 4,320';top.append(h,n);
    const p=document.createElement('p');p.textContent=run.model==='B3'?'7 通道 × 6 历史时次':'B3 + 13 变量 GFS MEE · width 16';
    const progress=document.createElement('progress');progress.max=4320;progress.value=run.returned;progress.setAttribute('aria-label',run.model+' 更新进度');
    const epochs=document.createElement('ol');epochs.className='epochs';
    for(const e of run.epochs){const li=document.createElement('li');li.textContent=e.epoch;li.className=e.phase;li.title=`第 ${e.epoch} 轮：${labels[e.phase]}，${e.updates}/480 次更新`;li.setAttribute('aria-label',li.title);epochs.append(li);}
    const note=document.createElement('div');note.className='epoch-legend';const e=current(run);note.textContent=run.sealed_epochs===9?'9 轮全部封存':`第 ${e.epoch}/9 轮 · ${labels[e.phase]} · 本轮 ${e.updates}/480 更新`;
    art.append(top,p,progress,epochs,note);$('models').append(art);
  }
}
function renderMetrics(){
  if(!snapshot)return;const body=$('metrics');body.replaceChildren();
  for(const run of snapshot.runs){if($('model-filter').value!=='all'&&$('model-filter').value!==run.model)continue;
    for(const e of run.epochs){const tr=document.createElement('tr'),m=e.metrics?.all||{};
      cell(tr,run.model+' / '+e.epoch);cell(tr,labels[e.phase],'phase');cell(tr,number(e.training_loss));
      for(const k of ['brier','auroc','average_precision','conditional_pinball'])cell(tr,number(m[k]));
      cell(tr,typeof m.q32_coverage==='number'?number(m.q32_coverage*100,2)+'%':'—');body.append(tr);
    }
  }
}
function renderPair(){
  if(!snapshot)return;const epoch=Number($('pair-epoch').value),a=snapshot.runs[0].epochs[epoch-1].metrics,b=snapshot.runs[1].epochs[epoch-1].metrics;
  $('paired').replaceChildren();$('strata').replaceChildren();
  if(!a||!b){for(const [id,cols]of [['paired',7],['strata',5]]){const tr=document.createElement('tr');const td=cell(tr,`第 ${epoch} 轮两模型 Dev 指标尚未齐备，暂不计算配对差值。`,'empty');td.colSpan=cols;$(id).append(tr);}return;}
  const names={all:'全体 Dev',analysis_UTC_00:'00 UTC',analysis_UTC_06:'06 UTC',analysis_UTC_12:'12 UTC',analysis_UTC_18:'18 UTC',scene_max_ge20:'场景最大雨强 ≥20'};
  for(const [key,label]of Object.entries(names)){if(!a[key]||!b[key])continue;const x=a[key],y=b[key],tr=document.createElement('tr');
    cell(tr,label);cell(tr,x.scenes===y.scenes?count(x.scenes):'人口不一致');
    if(!x.ids_sha||x.ids_sha!==y.ids_sha||x.scenes!==y.scenes||x.n_valid!==y.n_valid){const td=cell(tr,'人口不匹配，不计算差值','bad');td.colSpan=5;}
    else {deltaCell(tr,delta(x.brier,y.brier),-1);deltaCell(tr,delta(x.auroc,y.auroc),1);deltaCell(tr,delta(x.average_precision,y.average_precision),1);deltaCell(tr,delta(x.conditional_pinball,y.conditional_pinball),-1);deltaCell(tr,delta(x.q32_signed_bias,y.q32_signed_bias));}
    $('paired').append(tr);
  }
  let lower='0.1';for(let i=0;i<(a.all.rain_strata||[]).length;i++){const x=a.all.rain_strata[i],y=b.all.rain_strata[i],tr=document.createElement('tr');if(!y)continue;const upper=x.upper===null?'∞':String(x.upper);cell(tr,`(${lower}, ${upper}]`);cell(tr,count(x.n));cell(tr,number(x.conditional_pinball));cell(tr,number(y.conditional_pinball));deltaCell(tr,delta(x.conditional_pinball,y.conditional_pinball),-1);$('strata').append(tr);lower=upper;}
}
function render(s){
  snapshot=s;$('updates').textContent=count(s.returned);$('update-limit').textContent=' / '+count(s.limits.updates);$('total-progress').max=s.limits.updates;$('total-progress').value=s.returned;
  $('progress-heading').textContent=s.prior_updates?'累计正式更新尝试（含历史消耗）':'正式更新进度';
  $('recovery-note').hidden=!s.prior_updates;$('recovery-note').textContent=s.prior_updates?`历史已消耗 ${count(s.prior_updates)} 次；本次新增 ${count(s.segment_updates)} 次。有效模型轨迹 ${count(s.effective_updates)}/8,640；批准重放 480 次，B3/B4 均保持九轮。`:'';
  const stateText={RUNNING:'进程在运行',COMPLETE:'配对训练完成',FAILED:'训练已失败停止',UNKNOWN:'进程状态未确认'};
  $('state').textContent=stateText[s.state]||s.state;$('sealed').textContent=s.runs.reduce((n,r)=>n+r.sealed_epochs,0)+' / 18';$('uncertain').textContent=count(s.uncertain);
  const active=s.io.active.at(-1);$('phase').textContent=s.state==='COMPLETE'?'B3 / B4 第 9 轮终点已完成':s.state==='FAILED'?'已保留失败收据，不自动重试':active?`${active.model} · 第 ${active.epoch}/9 轮 · ${active.role==='dev'?'Dev 验证中':'训练中'}`:'等待下一阶段收据';
  $('failure').hidden=s.state!=='FAILED';$('failure').textContent=s.failure?'训练失败停止：'+s.failure.error+'。保留现有证据，不自动重试。':'';
  renderModels(s);renderMetrics();renderPair();
  const gpu=s.resources.gpu,memory=s.resources.memory;
  $('gpu-name').textContent=gpu?.name||'GPU（暂不可采集）';$('gpu-memory').textContent=gpu?`${number(gpu.used_mib/1024,2)} / ${number(gpu.total_mib/1024,2)} GiB`:'—';
  $('gpu-detail').textContent=gpu?`利用率 ${number(gpu.utilization,0)}% · ${number(gpu.temperature,0)} °C · ${number(gpu.power,1)} W`:'无设备采样值，训练进度仍由账本显示';
  $('ram').textContent=memory?gib(memory.available)+' RAM':'—';$('host-detail').textContent=`可用系统 commit ${gib(memory?.commit_available)} · 磁盘 ${gib(s.resources.disk_free)}`;
  $('io-bytes').textContent=gib(s.io.bytes)+' / '+gib(s.limits.bytes);$('io-progress').max=s.limits.bytes;$('io-progress').value=s.io.bytes;$('io-files').textContent=count(s.io.files)+' / '+count(s.limits.files)+' 次文件读取';
  $('io-detail').textContent=`已结束 ${s.io.sealed}/${s.total_passes||36} 次数据遍历；累计登记 ${count(s.io.reserved_bytes)} 字节，已交付 ${count(s.io.bytes)} 字节。${s.prior_updates?'包含历史失败读取及一次报错源文件核验。':''}逻辑量不等于磁盘物理流量。`;
  $('commit').textContent=s.source_commit;$('population').textContent=s.population_sha256;$('initial').textContent=s.common_initialization?'B3 / B4 公共权重 SHA 一致':'尚未确认';
  const identity=s.data_identity;$('statistics').textContent=Object.entries(identity).filter(([k])=>/stat|b13/i.test(k)).map(([k,v])=>k+' = '+(typeof v==='string'?v:JSON.stringify(v))).join(' · ')||'绑定执行账本中的既有 Train-only 统计';
  const checkpoints=s.runs.flatMap(r=>r.epochs.filter(e=>e.checkpoint_sha256).map(e=>`${r.model} E${e.epoch}: ${e.checkpoint_sha256}`));$('last').textContent=checkpoints.slice(-2).join(' · ')||'尚未生成完整 LAST 收据';
  $('sampling').textContent='采集时间 '+new Date(s.snapshot_utc).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})+'（北京时间） · 采集耗时 '+s.collection_ms+' ms';
}
async function refresh(){
  if(busy)return;busy=true;$('refresh').disabled=true;
  try{const response=await fetch('/api/snapshot',{cache:'no-store',signal:AbortSignal.timeout(6000)});if(!response.ok)throw Error('HTTP '+response.status);const data=await response.json();render(data);lastGood=Date.now();$('error').hidden=true;$('connection').textContent='本机采集正常 · 只读';}
  catch(e){$('error').hidden=false;$('connection').textContent='采集失败 · '+(lastGood?'保留上次结果':'尚无可用快照');}
  finally{busy=false;$('refresh').disabled=false;}
}
function schedule(){clearInterval(timer);if($('auto').checked&&!document.hidden)timer=setInterval(refresh,15000);}
const url=new URL(location.href);$('model-filter').value=['B3','B4'].includes(url.searchParams.get('model'))?url.searchParams.get('model'):'all';
for(let e=1;e<=9;e++){const option=document.createElement('option');option.value=e;option.textContent='第 '+e+' 轮';$('pair-epoch').append(option);}
$('pair-epoch').value=/^[1-9]$/.test(url.searchParams.get('epoch')||'')?url.searchParams.get('epoch'):'9';
function saveFilters(){const u=new URL(location.href);u.searchParams.set('model',$('model-filter').value);u.searchParams.set('epoch',$('pair-epoch').value);history.replaceState(null,'',u);}
$('refresh').addEventListener('click',refresh);$('auto').addEventListener('change',schedule);
$('model-filter').addEventListener('change',()=>{saveFilters();renderMetrics();});$('pair-epoch').addEventListener('change',()=>{saveFilters();renderPair();});
document.addEventListener('visibilitychange',()=>{schedule();if(!document.hidden&&$('auto').checked)refresh();});
refresh();schedule();
