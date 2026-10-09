"""Final evidence-only local page, preserving prior failed-run status."""
from http.server import HTTPServer,BaseHTTPRequestHandler
from pathlib import Path
import json,html,argparse
def main():
    p=argparse.ArgumentParser();p.add_argument('--delivery',type=Path,required=True);p.add_argument('--port',type=int,default=8772);args=p.parse_args()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path not in ('/','/api/progress'):self.send_error(404);return
            status=json.loads((args.delivery/'final_status.json').read_text(encoding='utf-8'))
            receipt=args.delivery/'publication_verification.json'
            if receipt.is_file():status['publication']=json.loads(receipt.read_text(encoding='utf-8'))
            if self.path=='/api/progress':body=json.dumps(status,ensure_ascii=False).encode();mime='application/json'
            else:
                rows=''.join('<tr><td>'+html.escape(k)+'</td><td>'+html.escape(str(v))+'</td></tr>' for k,v in status.items())
                body=('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="10"><title>v2 scientific acceptance</title><style>body{max-width:980px;margin:40px auto;font:17px system-ui;color:#172334}td{padding:9px;border-bottom:1px solid #ddd;overflow-wrap:anywhere}table{width:100%;border-collapse:collapse}</style><h1>v2 Phase-A 科学验收证据已完成</h1><p>两模型冻结 Epoch 9 BEST；2024 只读分析完成。28 项检查通过，4 张图及 11 页可编辑报告。没有训练、优化器更新或 2025 访问。等待研究者科学验收，Phase-B 未授权。</p><table>'+rows+'</table><p>v1 文档生成失败原样保留；本页显示独立 delivery_v2。此页面不自动启动任何工作。</p>').encode();mime='text/html'
            self.send_response(200);self.send_header('Content-Type',mime+'; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def log_message(self,*args):pass
    HTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
if __name__=='__main__':main()
