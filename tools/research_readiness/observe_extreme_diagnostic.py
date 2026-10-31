"""Read-only local status and once-only factual terminal-receipt publication.

Never imports scientific libraries or opens raw data, weights, or joint arrays.
The optional publisher stages only its new deidentified observation receipt.
It never launches, resumes, retries, approves, or changes the diagnostic.
"""
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import subprocess
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / 'docs/research_readiness/.local'
TASKS = ('TRAIN_LABELS','B7_s2029','B8_s2029','B4_s2029','B7_s2030','B8_s2030','B4_s2030','B7_s2031','B8_s2031','B4_s2031')
BRANCH = 'prep/b2-stage-acceptance-20261025'
TERMINAL = {'COMPLETE_PENDING_RESEARCHER_REVIEW','FAILED_NO_RETRY','STOPPED_WITHOUT_TERMINAL_RECEIPT','DEADLINE_PASSED_WITHOUT_TERMINAL_RECEIPT'}


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path, maximum=16*1024**2):
    path=Path(path)
    if not path.exists():return None
    if path.stat().st_size>maximum:raise ValueError('Status metadata exceeds its size bound')
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write_new(path,value):
    with Path(path).open('x',encoding='utf-8',newline='\n') as f:
        json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')


def monitor_base():
    spec=importlib.util.spec_from_file_location('diagnostic_existing_process_monitor',ROOT/'tools/core_stage4/monitor/server.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


class Reader:
    def __init__(self,config_path,*,root=ROOT,process_token=None):
        self.root=Path(root).resolve();local=self.root/'docs/research_readiness/.local'
        if not Path(config_path).resolve().is_relative_to(local):raise PermissionError('Private observer configuration required')
        self.config=read(config_path)
        if (not Path(self.config['proposal']).resolve().is_relative_to(self.root/'docs/research_readiness')
                or any(not Path(self.config[k]).resolve().is_relative_to(local) for k in ('private_preparation','approval'))):
            raise PermissionError('Observer may bind only project proposal and private identities')
        self.p=read(self.config['proposal']);self.v=read(self.config['private_preparation'])
        if (self.p['tasks']!=list(TASKS) or self.p['final_2025_access'] is not False
                or digest({k:v for k,v in self.p.items() if k!='proposal_sha256'})!=self.p['proposal_sha256']
                or self.v['proposal_sha256']!=self.p['proposal_sha256']):raise PermissionError('Exact finite diagnostic identity required')
        self.folder=Path(self.v['output_root']).resolve()
        self.service=Path(self.config['service_dir']).resolve()
        self.executor_service=Path(self.config['executor_service_dir']).resolve()
        if any(not p.is_relative_to(local) for p in (self.folder,self.service,self.executor_service)):raise PermissionError('Only private diagnostic metadata may be observed')
        self.binding=read(self.folder/'binding.json')
        if (self.binding['proposal_sha256']!=self.p['proposal_sha256']
                or self.binding['code_commit']!=self.p['execution_code_commit']
                or self.binding['approval_sha256']!=sha(self.config['approval'])):raise PermissionError('Running package approval binding differs')
        self.pid=self.binding['controller_pid']
        self.process_token=process_token or monitor_base().process_token
        self.token=self.process_token(self.pid)
        self.lock=threading.RLock()

    def document(self,path):
        path=Path(path).resolve()
        if not path.is_relative_to(self.folder) or path.suffix!='.json':raise PermissionError('Only this package JSON may be read')
        try:return read(path)
        except (OSError,ValueError):return None

    def chunks(self,task):
        path=self.folder/task/'joint/chunks.jsonl';scenes=0;updating=False
        if not path.exists():return scenes,updating
        if path.stat().st_size>1024**2:raise ValueError('Chunk journal exceeds status size bound')
        for line in path.read_text(encoding='utf-8').splitlines():
            try:row=json.loads(line)
            except ValueError:updating=True;break
            if row.get('state')=='COMPLETE':scenes+=int(row['scenes'])
        return scenes,updating

    def snapshot(self):
        with self.lock:
            failure=self.document(self.folder/'failure.json');completion=self.document(self.folder/'completion.json')
            live=self.token is not None and self.process_token(self.pid)==self.token
            exited=read(self.executor_service/'target_exit.json') is not None
            state=('FAILED_NO_RETRY' if failure else 'COMPLETE_PENDING_RESEARCHER_REVIEW' if completion else 'RUNNING' if live else 'STOPPED_WITHOUT_TERMINAL_RECEIPT' if exited else 'UNKNOWN_PROCESS_STATE')
            rows=[];known_payload=known_meta=known_opens=0
            for task in TASKS:
                folder=self.folder/task;done=self.document(folder/'task_complete.json');failed=self.document(folder/'task_failure.json')
                verified=self.document(folder/'verified.json');claim=self.document(self.folder/(task+'_claim.json'))
                sealed=bool(done and verified and done['verified_sha256']==sha(folder/'verified.json'))
                scenes,updating=self.chunks(task) if task!='TRAIN_LABELS' else (959 if sealed else 0,False)
                accounting=(done if sealed else failed or {}).get('accounting',{})
                payload=accounting.get('payload_reserved_bytes',{});meta=accounting.get('metadata_archive_reserved_bytes',0)
                known_payload+=sum(payload.values());known_meta+=meta;known_opens+=accounting.get('metadata_open_instances',0)
                status=('COMPLETE' if sealed else 'FAILED' if failed else 'RUNNING' if claim and live else 'UNSEALED' if claim else 'PENDING')
                gate=verified.get('original_gate',{}).get('passed') if verified and task!='TRAIN_LABELS' else None
                rows.append(dict(task=task,status=status,scenes=scenes,required_scenes=959 if task=='TRAIN_LABELS' else 963,
                    original_metric_gate=gate,payload_archive_reserved_bytes=sum(payload.values()) if accounting else None,
                    metadata_archive_reserved_bytes=meta if accounting else None,journal_updating=updating,
                    error_type=failed.get('error_type') if failed else None))
            budget=self.p['budget'];remaining=max(0.,self.binding['absolute_wall_deadline']-time.time())
            synced=read(self.service/'terminal_sync.json');sync_failed=read(self.service/'terminal_sync_failure.json')
            publication=dict(state='SYNCED' if synced else 'STOP_PUBLICATION_NO_RETRY' if sync_failed else 'WAITING_TERMINAL',
                commit=synced.get('commit') if synced else None)
            return dict(state=state,read_only=True,snapshot_utc=datetime.now(timezone.utc).isoformat(),
                controller_observed=live,proposal_sha256=self.p['proposal_sha256'],execution_code_commit=self.p['execution_code_commit'],
                tasks=rows,tasks_complete=sum(row['status']=='COMPLETE' for row in rows),
                models_complete=sum(row['status']=='COMPLETE' for row in rows if row['task']!='TRAIN_LABELS'),
                remaining_seconds=remaining,budget=budget,
                known_sealed_or_failed_reservations=dict(payload_archive_bytes=known_payload,metadata_archive_bytes=known_meta,metadata_opens=known_opens,
                    prior_metadata_charge_bytes=budget['prior_metadata_archive_charge_bytes'],
                    cumulative_known_archive_bytes=known_payload+known_meta+budget['prior_metadata_archive_charge_bytes']),
                unsealed_tasks=[row['task'] for row in rows if row['status'] in ('RUNNING','UNSEALED')],
                accounting_note='Only sealed or failed-task accounting is summed; active/unsealed reads remain uncounted here',
                final_2025='FROZEN_NO_ACCESS',optimizer_updates=0,automatic_retry=False,
                scientific_acceptance='PENDING_RESEARCHER_REVIEW',independent_events='NOT_IDENTIFIED',physics_causality='NOT_VERIFIED',publication=publication)


def render(snapshot):
    states={'RUNNING':'运行中','FAILED_NO_RETRY':'已停止，零重试','COMPLETE_PENDING_RESEARCHER_REVIEW':'工程诊断完成，等待研究者审查','STOPPED_WITHOUT_TERMINAL_RECEIPT':'已退出，终态收据尚未核实','UNKNOWN_PROCESS_STATE':'进程状态暂未核实','DEADLINE_PASSED_WITHOUT_TERMINAL_RECEIPT':'时限已过，终态尚未封口'}
    task_states={'COMPLETE':'已封口','FAILED':'失败，后续停止','RUNNING':'运行中','UNSEALED':'未封口','PENDING':'等待前序'}
    rows=[]
    for r in snapshot['tasks']:
        gate='通过' if r['original_metric_gate'] is True else '未通过' if r['original_metric_gate'] is False else '待核查' if r['task']!='TRAIN_LABELS' else '标签身份封口' if r['status']=='COMPLETE' else '待核查'
        reserved='—' if r['payload_archive_reserved_bytes'] is None else f"{r['payload_archive_reserved_bytes']:,}"
        rows.append(f"<tr><th scope='row'>{escape(r['task'])}</th><td>{task_states[r['status']]}</td><td class='number'>{r['scenes']:,} / {r['required_scenes']:,}</td><td>{gate}</td><td class='number'>{reserved}</td></tr>")
    stamp=datetime.fromisoformat(snapshot['snapshot_utc']).astimezone(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')
    minutes=int(snapshot['remaining_seconds']//60)
    sync={'SYNCED':'终态收据已同步GitHub','STOP_PUBLICATION_NO_RETRY':'终态收据同步停止，原件保留','WAITING_TERMINAL':'终态封口后同步脱敏收据'}[snapshot['publication']['state']]
    return ("<!doctype html><html lang='zh-CN'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<meta http-equiv='refresh' content='15'><title>YunTAPR-Net · 联合诊断进度</title><style>"
        ":root{--ink:#173a57;--text:#223440;--muted:#4b5a66;--rule:#d8e0e6;--paper:#fff;--soft:#f4f7f9;--space:24px}*{box-sizing:border-box}"
        "body{margin:0;background:var(--paper);color:var(--text);font:16px/1.6 'Microsoft YaHei','Segoe UI',sans-serif}main{max-width:1180px;margin:auto;padding:32px var(--space)}"
        "header{border-bottom:2px solid var(--ink);padding-bottom:16px}h1{font-size:28px;line-height:1.3;margin:8px 0;color:var(--ink)}h2{font-size:20px;margin-top:28px}"
        "p{margin:12px 0}.meta,footer{font-size:14px;color:var(--muted)}.state{font-size:24px;font-weight:700;color:var(--ink)}.table{overflow:auto}table{border-collapse:collapse;width:100%;min-width:780px}"
        "th,td{padding:13px 12px;border-bottom:1px solid var(--rule);text-align:left}thead{background:var(--soft)}tbody th{font-weight:400;font-family:Consolas,monospace}.number{font-variant-numeric:tabular-nums;text-align:right}"
        "a{color:var(--ink);text-underline-offset:4px;display:inline-block;padding:10px 0}a:focus-visible{outline:2px solid var(--ink);outline-offset:4px}footer{border-top:1px solid var(--rule);margin-top:28px;padding-top:16px}"
        "@media(max-width:600px){main{padding:20px 16px}h1{font-size:24px}}</style><main><header><div>YunTAPR-Net / 科研运行记录</div><h1>极端降水联合诊断</h1>"
        f"<div class='meta'>北京时间 {stamp} · 本地只读页面 · 打开时每15秒刷新</div></header><p class='state'>{states[snapshot['state']]}</p>"
        f"<p>任务已封口 {snapshot['tasks_complete']} / 10；模型已封口 {snapshot['models_complete']} / 9。距离批准包的墙钟上限约 {minutes} 分钟。</p>"
        "<div class='table'><table><thead><tr><th>任务</th><th>状态</th><th class='number'>联合记录场景</th><th>原指标一致性门槛</th><th class='number'>已封口源档案预留 / 字节</th></tr></thead><tbody>"+''.join(rows)+"</tbody></table></div>"
        "<h2>验收与边界</h2><p>任务封口表示工程检查完成；科学验收和论文结论仍由研究者决定。进行中的读取未计入表内已封口合计，场景导出完成也不等于原指标一致性已经通过。</p>"
        "<p>只使用既有九模型和2023训练标签／2024开发人口。训练更新、额外重试、重放均为0，2025最终测试集封存。</p>"
        f"<footer>固定执行代码 {escape(snapshot['execution_code_commit'][:7])} · 提案 {escape(snapshot['proposal_sha256'][:8])}<br>{sync}<br>"
        "<a href='/api/status'>查看脱敏状态数据</a> · 此页面没有任务控制入口。</footer></main></html>").encode('utf-8')


def handler(reader):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            if self.path not in ('/','/api/status'):self.send_error(404);return
            snapshot=reader.snapshot();body=render(snapshot) if self.path=='/' else json.dumps(snapshot,ensure_ascii=False,allow_nan=False).encode('utf-8')
            self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8' if self.path=='/' else 'application/json; charset=utf-8')
            self.send_header('Cache-Control','no-store');self.send_header('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def do_POST(self):self.send_error(405,'Read-only observer')
        do_PUT=do_DELETE=do_PATCH=do_POST
    return Handler


def git(root,*arguments):
    return subprocess.check_output(['git','-C',str(root),*arguments],encoding='utf-8',errors='replace',stderr=subprocess.STDOUT,timeout=45).strip()


def publish_terminal(reader,snapshot):
    """Exact new factual receipt only; never publish raw diagnostics or conclusions."""
    relative=reader.config['receipt_relative_path'];target=(reader.root/relative).resolve()
    expected=Path(reader.config['proposal']).resolve().parent/'launch/completion_observation.json'
    if target!=expected or not target.is_relative_to(reader.root/'docs/research_readiness'):raise PermissionError('Only the new public terminal receipt may be written')
    if snapshot['state'] not in TERMINAL:raise PermissionError('Terminal observation required')
    write_new(target,dict(snapshot,observation_scope='Saved output metadata only; no model, source data, weight or joint-array reads',publication='Factual engineering receipt; scientific acceptance remains pending'))
    if git(reader.root,'branch','--show-current')!=BRANCH:raise PermissionError('Working branch changed; leave receipt local')
    if git(reader.root,'diff','--cached','--name-only'):raise PermissionError('Index contains other work; leave receipt local')
    git(reader.root,'fetch','origin',BRANCH)
    old=git(reader.root,'rev-parse','HEAD')
    if old!=git(reader.root,'rev-parse','origin/'+BRANCH):raise PermissionError('Local/remote heads differ; no automatic merge or repair')
    git(reader.root,'add','--',relative)
    git(reader.root,'diff','--cached','--check','--',relative)
    git(reader.root,'commit','--only','-m','Record bounded diagnostic terminal observation','--',relative)
    commit=git(reader.root,'rev-parse','HEAD')
    git(reader.root,'push','origin',commit+':refs/heads/'+BRANCH)
    if git(reader.root,'ls-remote','origin','refs/heads/'+BRANCH).split()[0]!=commit:raise RuntimeError('Remote terminal receipt SHA not verified')
    return commit


def finish_once(reader):
    try:
        while True:
            if ((reader.folder/'failure.json').exists() or (reader.folder/'completion.json').exists()
                    or (reader.executor_service/'target_exit.json').exists()
                    or time.time()>reader.binding['absolute_wall_deadline']+120):break
            time.sleep(30)
        snapshot=reader.snapshot()
        if snapshot['state'] not in TERMINAL:snapshot=dict(snapshot,state='DEADLINE_PASSED_WITHOUT_TERMINAL_RECEIPT')
        commit=publish_terminal(reader,snapshot)
        write_new(reader.service/'terminal_sync.json',dict(status='SYNCED',commit=commit,branch=BRANCH,source='Saved output metadata only'))
    except BaseException as error:
        write_new(reader.service/'terminal_sync_failure.json',dict(status='STOP_PUBLICATION_NO_RETRY',error_type=type(error).__name__,details=str(error)))


def serve(config,port=0):
    reader=Reader(config)
    with ThreadingHTTPServer(('127.0.0.1',port),handler(reader)) as server:
        write_new(reader.service/'service.json',dict(url=f'http://127.0.0.1:{server.server_port}/',read_only=True,pid=__import__('os').getpid()))
        threading.Thread(target=finish_once,args=(reader,),daemon=True).start()
        server.serve_forever(poll_interval=1)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,required=True);parser.add_argument('--port',type=int,default=0)
    args=parser.parse_args();serve(args.config,args.port)
