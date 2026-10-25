const $=id=>document.getElementById(id);
const phases={SEALED:'已保存 LAST',VALIDATED:'评估完成',VALIDATION:'开发集评估',TRAINING:'训练中',PENDING:'等待'};
const states={RUNNING:'运行中',COMPLETE:'已完成',FAILED:'已停止',UNKNOWN:'进程未确认',BUDGET_ALERT:'预算异常'};
const number=new Intl.NumberFormat('zh-CN');
const fmt=(v,n=6)=>Number.isFinite(v)?v.toFixed(n):'—';
const duration=seconds=>{const n=Math.max(0,Math.floor(seconds||0));return [Math.floor(n/3600),Math.floor(n%3600/60),n%60].map(x=>String(x).padStart(2,'0')).join(':');};
let loading=false,lastGood=null;
function put(id,text){$(id).textContent=text;}
function render(s){
  lastGood=s;
  const percent=Math.min(100,100*s.io.bytes/s.limits.bytes);
  put('state-title',s.state==='COMPLETE'?'九轮训练与评估已完成':s.state==='FAILED'?'本次运行已停止':s.state==='UNKNOWN'?'已有收据，当前进程待确认':'正式训练进行中');
  put('state',states[s.state]||s.state);$('state').className='state '+(s.state==='FAILED'||s.state==='BUDGET_ALERT'?'failed':s.state==='UNKNOWN'?'unknown':'');
  const current=s.epochs[s.current_epoch-1];
  put('stage',s.state==='COMPLETE'?'固定第九轮 LAST 已绑定完成收据':`第 ${s.current_epoch} / 9 轮 · ${phases[s.phase]||s.phase} · 本轮已确认 ${current.updates} / 480 步`);
  put('percent',`${percent.toFixed(1)}%`);$('overall').value=percent;
  put('updates',`${number.format(s.returned)} / 4,320`);put('epochs',`${s.sealed_epochs} / 9 轮`);
  put('elapsed',duration(s.elapsed_seconds));put('remaining',s.state==='COMPLETE'?'已完成':duration(s.remaining_limit_seconds));
  const warning=s.message||(s.state==='UNKNOWN'?'无法确认训练进程。页面保留真实收据，不将无变化解释为完成。':s.state==='BUDGET_ALERT'?'检测到计数超出固定预算，请检查本地运行收据。':null);
  $('warning').hidden=!warning;put('warning',warning||'');
  $('timeline').replaceChildren();$('metrics').replaceChildren();
  for(const e of s.epochs){
    const li=document.createElement('li');li.className=e.phase;
    const label=document.createElement('strong');label.textContent=`E${String(e.epoch).padStart(2,'0')}`;
    const text=document.createElement('span');text.textContent=phases[e.phase];li.append(label,text);$('timeline').append(li);
    const tr=document.createElement('tr');if(e.epoch===s.current_epoch&&s.state!=='COMPLETE')tr.className='current';
    const m=e.metrics||{};
    const values=[e.epoch,phases[e.phase],fmt(e.training_loss),fmt(m.brier),fmt(m.auroc),fmt(m.average_precision),fmt(m.conditional_pinball),Number.isFinite(m.q32_coverage)?`${(m.q32_coverage*100).toFixed(3)}%`:'—'];
    values.forEach((value,i)=>{const td=document.createElement('td');td.textContent=value;if(i===1)td.className='status';tr.append(td);});$('metrics').append(tr);
  }
  put('bytes',`${(s.io.bytes/1e9).toFixed(3)} / ${(s.limits.bytes/1e9).toFixed(3)} GB`);
  put('files',`${number.format(s.io.files)} / ${number.format(s.limits.files)}`);put('uncertain',String(s.uncertain));
  const r=s.resources||{},g=r.gpu;
  put('gpu',g?.name||'暂不可用');put('gpu-use',g?`${fmt(g.used_mib/1024,2)} / ${fmt(g.total_mib/1024,2)} GiB · ${fmt(g.utilization,0)}%`:'—');
  put('memory',r.memory?`${fmt(r.memory.available/2**30,2)} GiB`:'—');put('disk',Number.isFinite(r.disk_free)?`${fmt(r.disk_free/2**30,2)} GiB`:'—');
  put('commit',s.source_commit.slice(0,12));
  put('updated',`快照：${new Date(s.snapshot_utc).toLocaleString('zh-CN',{hour12:false,timeZone:'Asia/Shanghai'})} 北京时间 · 本地只读`);
  document.title=`${s.state==='COMPLETE'?'完成':`E${s.current_epoch} ${percent.toFixed(1)}%`} · B2训练进度`;
}
async function refresh(){
  if(loading)return;loading=true;$('refresh').disabled=true;
  try{const response=await fetch('/api/snapshot',{cache:'no-store'});if(!response.ok)throw new Error('busy');render(await response.json());}
  catch(error){put('updated',lastGood?'暂未取得新快照，已保留上次数据；15秒后重试。':'暂未取得收据，请稍后刷新。');}
  finally{loading=false;$('refresh').disabled=false;}
}
$('refresh').addEventListener('click',refresh);
document.addEventListener('visibilitychange',()=>{if(!document.hidden&&$('automatic').checked)refresh();});
setInterval(()=>{if($('automatic').checked&&!document.hidden)refresh();},15000);
refresh();
