"""Read-only localhost viewer of the v2 engineering run; no control routes."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from quantile_head_v2 import common as c
from quantile_autopsy_v1.monitor import alive
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
import argparse,json


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True,type=Path)
    parser.add_argument('--port',type=int,default=8768);args=parser.parse_args();run=args.run.resolve()
    if run.parent!=c.RUN_ROOT.resolve():raise ValueError('Exact v2 run required')
    page=Path(__file__).with_name('ui.html').read_bytes()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            route=self.path.split('?',1)[0]
            if route=='/':data,mime=page,'text/html; charset=utf-8'
            elif route=='/api/status':
                status=c.read(run/'progress.json');status['process_alive']=alive(status.get('pid'));status['run']=run.name
                result=run/'test_gate_result.json';status['test_gate']=c.read(result) if result.exists() else None
                publication=run/'publication_result.json';status['publication']=c.read(publication) if publication.exists() else None
                data,mime=json.dumps(status,ensure_ascii=False).encode(),'application/json; charset=utf-8'
            elif route in ('/report','/data-decision'):
                name='YUNTAPR_QUANTILE_HEAD_V2_DECISION_PACKET.md' if route=='/report' else 'V2_DATA_REUSE_DECISION_PACKET.md'
                path=ROOT/'docs/scientific_freeze_v2'/name
                if not path.exists():self.send_error(404,'Report not generated yet');return
                data,mime=path.read_bytes(),'text/plain; charset=utf-8'
            else:self.send_error(404);return
            self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(data)
        def do_POST(self):self.send_error(405,'Read-only engineering monitor')
    print(json.dumps({'url':f'http://127.0.0.1:{args.port}/','run':str(run)}),flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()


if __name__=='__main__':main()
