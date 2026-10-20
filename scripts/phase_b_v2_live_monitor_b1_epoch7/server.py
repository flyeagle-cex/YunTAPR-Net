"""Loopback GET-only progress monitor; no model/data imports or mutation endpoint."""
from pathlib import Path
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import argparse,json,sqlite3,sys,threading,time
ROOT=Path(__file__).absolute().parents[2];sys.path.insert(0,str(ROOT/'src'))
from yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v1.protocol import DB,OUT,LOCAL,CAMPAIGN,ORDER,LIMITS,run_id,LAST_SHA
from yuntapr.experimental.phase_b_v2_stability_review import native
from yuntapr.experimental.phase_b_v2_stability_review.classification import scope
APP_ID='YUNTAPR_READONLY_LIVE_SEED2027_B1_EPOCH7_V1'
PRIOR=ROOT/'docs/phase_b_v2_formal_execution/seed2027_epoch2_recovery_v2/.local'
CACHE={};LOCK=threading.Lock();SNAP=None;STAMP=0

def read_json(path,maximum=16*1024**2):
    from yuntapr.experimental.phase_b_v2_status_snapshot_io.reader import read_json_snapshot
    return read_json_snapshot(path,ROOT,maximum)


def history(ident):
    path=LOCAL/ident/'progress.json'
    if not path.exists() and ident in (run_id(*ORDER[0]),run_id(*ORDER[1])):path=PRIOR/ident/'progress.json'
    if not path.exists():return []
    s=path.stat();key=(str(path),s.st_mtime_ns,s.st_size)
    if ident in CACHE and CACHE[ident][0]==key:return CACHE[ident][1]
    result=[]
    for e in read_json(path)['epochs']:
        v=e['development']['summary']
        result.append(dict(epoch=e['epoch'],training=e['train']['weighted_training_mean'],
            **{k:v.get(k) for k in ('brier','auroc','average_precision','core_fp64','conditional_pinball','q32_signed_bias')},
            q32_coverage=v['coverage'][-1],last_sha=e['checkpoint']['payload_sha256']))
    CACHE[ident]=(key,result);return result

def tail_events(path):
    if not path.exists():return []
    with path.open('rb') as f:
        f.seek(0,2);end=f.tell();start=max(0,end-128*1024);f.seek(start);raw=f.read(128*1024)
    lines=raw.splitlines()
    if start:lines=lines[1:]
    if not raw.endswith(b'\n'):lines=lines[:-1]
    result=[]
    for line in lines:
        e=json.loads(line)
        if e.get('event') in ('STEP_RETURNED','VALIDATION_COMPLETE','EPOCH_LAST_COMMITTED','FAILED','SAFE_PAUSE_COMPLETE','AUTHORIZED_B1_EPOCH7_LAST_RESUMED'):
            result.append({k:e[k] for k in ('event','utc','run_id','epoch','update','training_objective','lr') if k in e})
    return result[-6:]

def derive(state,probes):
    if probes is None:return 'STARTING' if state=='ACTIVE' else state
    if probes['worker']['status']=='LIVE_MATCH' and probes['owner']['status']=='LIVE_MATCH' and probes['job']['status']=='PRESENT':return 'RUNNING'
    if any(probes[k]['status']=='UNKNOWN' for k in ('worker','owner','job')):return 'PROCESS_NOT_VERIFIED'
    if probes['job']['status']=='PRESENT' and probes['job']['pids']:return 'JOB_STILL_PRESENT'
    return 'STOPPED_UNCLEAN' if state=='ACTIVE' else state

def snapshot():
    now=datetime.now(timezone.utc)
    result=dict(app_id=APP_ID,campaign=CAMPAIGN,utc=now.isoformat(),refresh_seconds=10,read_only=True,
        cap=363499,prior_reserved=164835,prior_verified=164834,adopted=83648,abandoned=81187,
        limits=LIMITS,pause_requested=False,reason=None,new_reserved=0,new_verified=0,
        worker=None,owner=None,job=None,heartbeat=None,events=[],current_phase=None)
    session=None;state='NOT_STARTED'
    if DB.exists():
        con=sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True,timeout=1)
        try:
            con.execute('PRAGMA query_only=ON');con.execute('BEGIN')
            state,result['reason']=con.execute('SELECT status,reason FROM campaign').fetchone()
            counts=dict(con.execute('SELECT status,count(*) FROM attempts GROUP BY status'))
            result.update(new_reserved=sum(counts.values()),new_verified=counts.get('RETURNED_VERIFIED',0),
                pause_requested=bool(con.execute('SELECT pause_requested FROM control').fetchone()[0]))
            runs=[dict(zip(('id','ordinal','status','epoch','updates','last_sha'),r)) for r in con.execute('SELECT * FROM runs ORDER BY ordinal')]
            session=con.execute('SELECT n FROM sessions ORDER BY n DESC LIMIT 1').fetchone()
            phases=con.execute("SELECT run,epoch,phase FROM epochs WHERE phase!='LAST_COMMITTED'").fetchall()
            if phases:result['current_phase']=dict(zip(('run','epoch','phase'),phases[-1]))
        finally:con.close()
    else:
        runs=[dict(id=run_id(m,a),ordinal=i,status='COMPLETE' if i==0 else ('WAITING_RECOVERY' if i==1 else 'PENDING'),epoch=9 if i==0 else (7 if i==1 else 0),updates=47052 if i==0 else (36596 if i==1 else 0),last_sha='34022dd6970a95a1fc8ef7a910d5b4a80a1f029ad3617dee577d6dff2b1f4673' if i==0 else (LAST_SHA if i==1 else None)) for i,(m,a) in enumerate(ORDER)]
    probes=None
    if session:
        folder=LOCAL/'sessions'/f'session_{session[0]:04d}';result['session']=session[0]
        if (folder/'heartbeat.json').exists():
            result['heartbeat']=read_json(folder/'heartbeat.json');result['heartbeat_age_seconds']=(now-datetime.fromisoformat(result['heartbeat']['utc'])).total_seconds()
        if (folder/'worker_identity.json').exists() and (folder/'supervisor_identity.json').exists():
            a=scope(read_json(folder/'supervisor_identity.json'),read_json(folder/'worker_identity.json'),CAMPAIGN,session[0])
            probes=dict(worker=native.process(a['worker']),owner=native.process(a['owner']),job=native.job(a['job_name']))
            result.update(probes);result['worker_pid']=a['worker']['pid'];result['owner_pid']=a['owner']['pid']
        result['events']=tail_events(folder/'access_and_events.jsonl')
    for run in runs:run['history']=history(run['id'])
    result.update(runs=runs,ledger_state=state,state=derive(state,probes),reserved=164835+result['new_reserved'],
        verified=164834+result['new_verified'],scientific_updates=sum(r['updates'] for r in runs),
        completed_runs=sum(r['status']=='COMPLETE' for r in runs))
    return result

def cached_snapshot():
    global SNAP,STAMP
    with LOCK:
        if SNAP is None or time.monotonic()-STAMP>=2:
            SNAP=snapshot();STAMP=time.monotonic()
        return SNAP

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def send(self,status,body,ctype):
        self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'")
        self.end_headers();self.wfile.write(body)
    def do_GET(self):
        if self.headers.get('Host') not in ('127.0.0.1:53082','localhost:53082'):
            return self.send(403,b'Loopback host required','text/plain')
        if self.path=='/':return self.send(200,(Path(__file__).parent/'app.html').read_bytes(),'text/html; charset=utf-8')
        if self.path=='/api/health':return self.send(200,json.dumps(dict(app_id=APP_ID,campaign=CAMPAIGN)).encode(),'application/json')
        if self.path!='/api/status':return self.send(404,b'Not found','text/plain')
        try:row=cached_snapshot();status=200
        except Exception as e:row=dict(error=type(e).__name__,message='Read-only snapshot unavailable; no control action performed.');status=503
        self.send(status,json.dumps(row,ensure_ascii=False,allow_nan=False).encode(),'application/json; charset=utf-8')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=53082);args=parser.parse_args()
    if args.port!=53082:raise ValueError('FIXED_LOOPBACK_PORT')
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler);server.daemon_threads=True;server.serve_forever()
