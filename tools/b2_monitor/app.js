const $=id=>document.getElementById(id);
const phases={SEALED:'已保存 LAST',VALIDATED:'评估完成',VALIDATION:'开发集评估',TRAINING:'训练中',PENDING:'等待'};
const states={RUNNING:'运行中',COMPLETE:'已完成',FAILED:'已停止',UNKNOWN:'进程未确认',BUDGET_ALERT:'预算异常'};
const number=new Intl.NumberFormat('zh-CN');
const fmt=(v,n=6)=>Number.isFinite(v)?v.toFixed(n):'—';
const duration=seconds=>{const n=Math.max(0,Math.floor(seconds||0));return [Math.floor(n/3600),Math.floor(n%3600/60),n%60].map(x=>String(x).padStart(2,'0')).join(':');};
let loading=false,lastGood=null,selectedTask='';
function put(id,text){$(id).textContent=text;}
function render(s){
  lastGood=s;
  let view=s;
  if(s.runs){
    put('page-title',s.innovation?'B7/B8 核心创新消融':s.static?'B5/B6 地形消融':s.recovery?'B3/B4 限额恢复':'B3/B4 多seed复现');put('subtitle',s.innovation?'Seed 2029 · DOTE / DTFM · E0 · 每模型九轮 LAST':s.static?'Seed 2029 · 海拔 / 完整静态地形 · E0 · 每模型九轮 LAST':s.recovery?`B4从E1恢复 · 必要重放 ${s.replay_returned} / 390 · 累计预算包含原失败段`:'Seed 2030 / 2031 · 固定串行 · E0 · 每模型九轮 LAST');
    put('time-label',s.static||s.innovation?'整包剩余时间额度':s.recovery?'恢复包剩余时间额度':'距离整包 24 小时时限');put('campaign-title',s.innovation?'B7 → B8 串行队列':s.static?'B5 → B6 串行队列':'四模型串行队列');$('campaign-section').hidden=false;
    if(s.b8_recovery){put('page-title','B8 限额恢复 · B7 固定E9对照');put('subtitle',`B8继承E1–E6 · 本次 ${number.format(s.segment_returned)} / 1,440 次更新 · 已重放 ${s.replay_returned} / 62 · 总计数包含原失败段`);put('time-label','本次恢复剩余时间额度');put('campaign-title','B7已完成 · B8恢复E7–E9');}
    const chosen=s.runs.find(r=>r.name===selectedTask)||s.runs.find(r=>r.state==='RUNNING')||s.runs.find(r=>r.state==='FAILED')||s.runs.find(r=>r.state==='PENDING')||s.runs.at(-1);
    view=chosen;
    $('task').replaceChildren();$('campaign-runs').replaceChildren();
    for(const r of s.runs){
      const option=document.createElement('option');option.value=r.name;option.textContent=`${r.model} · Seed ${r.seed}`;$('task').append(option);
      const row=document.createElement('div');row.className='campaign-run';
      const title=document.createElement('strong');title.textContent=`${r.model} · ${r.seed}`;
      const detail=document.createElement('span');detail.textContent=`${r.state==='PENDING'?(s.state==='FAILED'?'未启动（整包已停）':'等待'):states[r.state]||r.state} · ${number.format(r.returned)} / 4,320 步 · ${r.sealed_epochs} / 9 轮`;
      const progress=document.createElement('progress');progress.max=4320;progress.value=r.returned;progress.setAttribute('aria-label',`${r.model}种子${r.seed}更新进度`);
      row.append(title,detail,progress);$('campaign-runs').append(row);
    }
    $('task').value=chosen.name;put('timeline-title',`${chosen.model} · Seed ${chosen.seed} 九轮记录`);
  }
  const percent=Math.min(100,100*s.io.bytes/s.limits.bytes);
  put('state-title',s.state==='COMPLETE'?(s.innovation?'B7/B8及核心创新配对汇总已完成':s.static?'B5/B6及与B4配对汇总已完成':s.runs?'四模型及三seed汇总已完成':'九轮训练与评估已完成'):s.state==='FAILED'?'本次运行已停止':s.state==='UNKNOWN'?'已有收据，当前进程待确认':'正式训练进行中');
  put('state',states[s.state]||s.state);$('state').className='state '+(s.state==='FAILED'||s.state==='BUDGET_ALERT'?'failed':s.state==='UNKNOWN'?'unknown':'');
  const current=view.epochs[view.current_epoch-1];
  put('stage',s.state==='COMPLETE'?'固定第九轮 LAST 已绑定完成收据':`${s.runs?`${view.model} / Seed ${view.seed} · `:''}第 ${view.current_epoch} / 9 轮 · ${phases[view.phase]||view.phase} · 本轮已确认 ${current.updates} / 480 步`);
  put('percent',`${percent.toFixed(1)}%`);$('overall').value=percent;
  put('updates',`${number.format(s.returned)} / ${number.format(s.limits.updates)}`);put('epochs',`${s.sealed_epochs} / ${s.limits.epochs} 轮`);
  put('elapsed',duration(s.elapsed_seconds));put('remaining',s.state==='COMPLETE'?'已完成':duration(s.remaining_limit_seconds));
  const warning=s.message||(s.state==='UNKNOWN'?'无法确认训练进程。页面保留真实收据，不将无变化解释为完成。':s.state==='BUDGET_ALERT'?'检测到计数超出固定预算，请检查本地运行收据。':null);
  $('warning').hidden=!warning;put('warning',warning||'');
  $('timeline').replaceChildren();$('metrics').replaceChildren();
  for(const e of view.epochs){
    const li=document.createElement('li');li.className=e.phase;
    const label=document.createElement('strong');label.textContent=`E${String(e.epoch).padStart(2,'0')}`;
    const text=document.createElement('span');text.textContent=phases[e.phase];li.append(label,text);$('timeline').append(li);
    const tr=document.createElement('tr');if(e.epoch===view.current_epoch&&s.state!=='COMPLETE')tr.className='current';
    const m=e.metrics||{};
    const values=[e.epoch,phases[e.phase],fmt(e.training_loss),fmt(m.brier),fmt(m.auroc),fmt(m.average_precision),fmt(m.conditional_pinball),Number.isFinite(m.q32_coverage)?`${(m.q32_coverage*100).toFixed(3)}%`:'—'];
    values.forEach((value,i)=>{const td=document.createElement('td');td.textContent=value;if(i===1)td.className='status';tr.append(td);});$('metrics').append(tr);
  }
  const paired=s.paired_summary;$('paired-section').hidden=!paired;$('paired-metrics').replaceChildren();
  if(paired){
    const rows=[...Object.entries(paired.values).map(([label,m])=>({label,m,delta:false})),...Object.entries(paired.differences).map(([label,m])=>({label:label.replace('_minus_',' − '),m,delta:true}))];
    for(const {label,m,delta} of rows){const row=document.createElement('tr');const cells=[label,fmt(m.brier),fmt(m.auroc),fmt(m.average_precision),fmt(m.conditional_pinball),Number.isFinite(m.q32_coverage)?`${(100*m.q32_coverage).toFixed(5)}${delta?' pp':'%'}`:'—'];for(const value of cells){const cell=document.createElement('td');cell.textContent=value;row.append(cell);}$('paired-metrics').append(row);}
  }
  put('bytes',`${(s.io.bytes/1e9).toFixed(3)} / ${(s.limits.bytes/1e9).toFixed(3)} GB`);
  put('files',`${number.format(s.io.files)} / ${number.format(s.limits.files)}`);put('uncertain',String(s.uncertain));
  put('replay',s.b8_recovery?'62（额外重试0）':s.recovery?'390（额外重试0）':'0');
  const r=s.resources||{},g=r.gpu;
  put('gpu',g?.name||'暂不可用');put('gpu-use',g?`${fmt(g.used_mib/1024,2)} / ${fmt(g.total_mib/1024,2)} GiB · ${fmt(g.utilization,0)}%`:'—');
  put('memory',r.memory?`${fmt(r.memory.available/2**30,2)} GiB`:'—');put('disk',Number.isFinite(r.disk_free)?`${fmt(r.disk_free/2**30,2)} GiB`:'—');
  put('commit',s.source_commit.slice(0,12));
  put('updated',`快照：${new Date(s.snapshot_utc).toLocaleString('zh-CN',{hour12:false,timeZone:'Asia/Shanghai'})} 北京时间 · 本地只读`);
  document.title=`${s.state==='COMPLETE'?'完成':s.state==='FAILED'?'已停止':`${percent.toFixed(1)}%`} · ${s.innovation?'B7/B8核心创新':s.static?'B5/B6地形消融':s.runs?'B3/B4多seed':'B2训练进度'}`;
}
async function refresh(){
  if(loading)return;loading=true;$('refresh').disabled=true;
  try{const response=await fetch('/api/snapshot',{cache:'no-store'});if(!response.ok)throw new Error('busy');render(await response.json());}
  catch(error){put('updated',lastGood?'暂未取得新快照，已保留上次数据；15秒后重试。':'暂未取得收据，请稍后刷新。');}
  finally{loading=false;$('refresh').disabled=false;}
}
$('refresh').addEventListener('click',refresh);
$('task').addEventListener('change',()=>{selectedTask=$('task').value;if(lastGood)render(lastGood);});
document.addEventListener('visibilitychange',()=>{if(!document.hidden&&$('automatic').checked)refresh();});
setInterval(()=>{if($('automatic').checked&&!document.hidden)refresh();},15000);
refresh();
