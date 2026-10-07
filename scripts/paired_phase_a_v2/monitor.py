"""Localhost-only, read-only progress. No source/checkpoint/control endpoints."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import time

PAGE = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>YunTAPR-Net v2 · 执行监控</title><style>body{font:16px system-ui;margin:40px auto;max-width:1100px;padding:0 24px;background:#f7f8fa;color:#1b2633}h1{font-size:25px}header{border-bottom:2px solid #244b68;padding-bottom:18px}section{margin:24px 0;padding:22px;background:white;border:1px solid #d6dde3}dt{color:#566575}dd{font-size:20px;margin:4px 0 20px}#fields{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}small{color:#566575}.failed{color:#b02b28}</style>
<header><small>YunTAPR-Net / Scientific Freeze v2</small><h1>配对 Phase-A 执行监控</h1><p>只读状态页 · 工程预检不授权正式训练 · 2025 数据继续封存</p></header>
<section><h2 id="status">正在读取状态</h2><p id="fresh"></p><div id="fields"></div></section><section><h2>诊断与审计详情</h2><pre id="details"></pre></section>
<script>const names={phase:'阶段',model:'模型',epoch:'Epoch',step:'Step',checked_files:'已核验文件',total_files:'文件总数',train_loss:'Train loss',validation_core_loss:'Validation core loss',LR:'LR',gradient_norm:'梯度范数',BEST_epoch:'BEST epoch',patience:'早停 counter / 8',ETA_seconds:'预计剩余秒数',gpu_memory_allocated:'GPU 已分配 bytes',tests_completed:'已完成测试',FORMAL_OPTIMIZER_STEPS:'正式 optimizer steps'};
async function poll(){try{let r=await fetch('/api/status',{cache:'no-store'});if(!r.ok)throw Error(r.status);let d=await r.json();document.getElementById('status').textContent=d.status||'等待状态';document.getElementById('status').className=(d.status||'').includes('FAIL')?'failed':'';document.getElementById('fresh').textContent='最近更新距今 '+d.age_seconds+' 秒；未见完成标记时不能视为完成。';let box=document.getElementById('fields');box.replaceChildren();Object.entries(names).forEach(([k,n])=>{if(d[k]!==undefined){let a=document.createElement('div'),dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=n;dd.textContent=String(d[k]);a.append(dt,dd);box.append(a)}});document.getElementById('details').textContent=JSON.stringify(d,null,2)}catch(e){document.getElementById('status').textContent='状态暂不可读：'+e.message}}poll();setInterval(poll,5000);</script></html>'''


def serve(run, port=8769):
    run = Path(run).resolve()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_POST(self): self.send_error(405, 'Read only')
        def do_GET(self):
            route = self.path.split('?',1)[0]
            if route == '/': body, mime = PAGE.encode(), 'text/html; charset=utf-8'
            elif route == '/api/status':
                file = run / 'progress.json'
                try:
                    value = json.loads(file.read_text(encoding='utf-8'))
                    value['age_seconds'] = round(time.time()-file.stat().st_mtime,1)
                    if value.get('pid'):
                        from quantile_autopsy_v1.monitor import alive
                        value['process_alive'] = alive(value['pid'])
                        if not value['process_alive'] and value.get('status') == 'RUNNING': value['status']='INTERRUPTED_NO_COMPLETION'
                except FileNotFoundError: value={'status':'WAITING_FOR_PROCESS','age_seconds':0}
                body, mime = json.dumps(value,ensure_ascii=False).encode(), 'application/json; charset=utf-8'
            else: self.send_error(404); return
            self.send_response(200); self.send_header('Content-Type',mime); self.send_header('Cache-Control','no-store')
            self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()
