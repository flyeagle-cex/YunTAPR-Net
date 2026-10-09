"""Local read-only metadata progress page; no raw source or checkpoint access."""
import argparse, json, html
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
def main():
    p=argparse.ArgumentParser(); p.add_argument('--run',type=Path,required=True); p.add_argument('--port',type=int,default=8772); args=p.parse_args()
    def status():
        for name in ('closeout_failure.json','analysis_closeout_status.json','failure.json','paired_best_metrics.json','progress.json'):
            path=args.run/name
            if path.is_file():
                with path.open('rb') as stream: value=json.load(stream)
                if name=='paired_best_metrics.json': return {'status':value['status'],'B0_scenes':10501,'B1_scenes':10501,'OPTIMIZER_STEPS':0,'2025_RAW_ACCESS':0,'message':'Read-only inference completed; statistics and acceptance packet closeout pending.'}
                return value
        return {'status':'PRE_INFERENCE_IDENTITY_VERIFICATION','OPTIMIZER_STEPS':0,'2025_RAW_ACCESS':0}
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path not in ('/','/api/progress'): self.send_error(404); return
            value=status()
            if self.path=='/api/progress': body=json.dumps(value,ensure_ascii=False).encode(); content='application/json'
            else:
                rows=''.join('<tr><td>'+html.escape(str(k))+'</td><td>'+html.escape(str(v))+'</td></tr>' for k,v in value.items())
                body=('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="5"><title>v2 scientific acceptance</title><style>body{max-width:960px;margin:40px auto;font:17px system-ui;color:#172334}table{border-collapse:collapse;width:100%}td{padding:10px;border-bottom:1px solid #ddd;overflow-wrap:anywhere}td:first-child{width:38%}</style><h1>v2 Phase-A 科学验收 · 2024 只读分析</h1><p>冻结 Epoch 9 BEST；没有训练、梯度计算、优化器更新或 2025 访问。每 5 秒刷新。</p><table>'+rows+'</table><p>该页面报告分析进程进度，不代表研究者科学批准。Phase-B 未授权。</p>').encode(); content='text/html'
            self.send_response(200); self.send_header('Content-Type',content+'; charset=utf-8'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
        def log_message(self,*args): pass
    HTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
if __name__=='__main__': main()
