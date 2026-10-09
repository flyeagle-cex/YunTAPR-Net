"""Read-only localhost handoff after final Phase-A evidence is published.

No training commands or mutable training-file reads. Serves only the final
audit, registered PDF/LaTeX and its immutable comparison metadata.
"""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess

REPO = Path(__file__).resolve().parents[2]


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def completed_state(audit, packet, commit):
    if audit['status'] != 'V2_PAIRED_PHASE_A_COMPLETE_RESEARCHER_REVIEW_REQUIRED' or \
            not audit['requirement_checks'] or any(v != 'PASS' for v in audit['requirement_checks'].values()) or \
            not audit['PDF_VISUALLY_VERIFIED'] or not audit['FINAL_GITHUB_ARTIFACT_PUBLICATION_VERIFIED']:
        raise ValueError('Real completed audit and PDF/publication proof required')
    if any(audit[k] != 0 for k in ('2025_RAW_ACCESS', '2025_PIXELS_READ',
                                  'CLOSEOUT_OPTIMIZER_STEPS', 'CLOSEOUT_BACKWARD_CALLS')) or \
            audit['V2_PHASE_B_AUTHORIZED'] or audit['AUTOMATIC_NEXT_STAGE'] or \
            audit['FORMAL_TRAINING_RUNNING'] or not audit['FORMAL_TRAINING_COMPLETED']:
        raise ValueError('Scope violation')
    return {'status': 'PHASE_A_COMPLETE_RESEARCHER_REVIEW_REQUIRED',
            'phase': 'STOPPED_AT_APPROVED_PHASE_A_BOUNDARY', 'completion_commit': commit,
            'FINAL_GITHUB_PUBLICATION_VERIFIED': True, 'PDF_VISUALLY_VERIFIED': True,
            '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0, 'V2_PHASE_B_AUTHORIZED': False,
            'FORMAL_TRAINING_RUNNING': False, 'CLOSEOUT_OPTIMIZER_STEPS': 0,
            'CLOSEOUT_BACKWARD_CALLS': 0, 'RESEARCHER_PHASE_A_REVIEW_REQUIRED': True,
            'models': {k: {'completed_epoch': m['early_stopping']['completed_epoch'],
                          'BEST_epoch': m['BEST']['epoch'], 'LAST_epoch': m['LAST']['epoch'],
                          'retained_optimizer_steps': audit['FORMAL_OPTIMIZER_STEPS_RETAINED'][k],
                          'validation_scenes': 10501, 'read_only_review_forwards': 1313,
                          'metrics': m['metrics']} for k, m in packet['models'].items()}}


PAGE = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>YunTAPR-Net v2 · Phase-A 完成</title><style>
body{font:16px/1.65 system-ui,sans-serif;color:#182631;background:#f6f8fa;margin:0;padding:24px}
main{max-width:1050px;margin:auto}h1{font-size:27px;margin:0}h2{font-size:19px;margin:0 0 12px;overflow-wrap:anywhere}
section{background:white;border:1px solid #d4dce2;padding:20px;margin-top:20px}p{margin:8px 0}a{color:#125c92}
.status{color:#18613f}.mono{font-family:ui-monospace,monospace;overflow-wrap:anywhere}
.table{overflow-x:auto}table{width:100%;border-collapse:collapse;text-align:left}th,td{padding:10px;border-bottom:1px solid #dce2e8;white-space:nowrap}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.6 ui-monospace,monospace}
@media(max-width:500px){body{padding:14px}section{padding:14px}h1{font-size:24px}}
</style><main><p>YunTAPR-Net / Scientific Freeze v2</p><h1>配对 Phase-A 已完成</h1>
<p>正式训练、完整审计与全量 2024 BEST 只读复核已结束。当前等待研究者审查。</p>
<section><h2 class="status">已在授权 Phase-A 边界停止</h2><p>2025 原始数据访问：0；2025 像元读取：0；收尾 optimizer / backward：0。</p>
<p>Phase-B 未授权；此页面不能启动训练或恢复。</p><p><a href="/report.pdf">完整 PDF 报告</a> · <a href="/report.tex">可编辑 LaTeX 源</a></p>
<p>GitHub main 完成提交：<span id="commit" class="mono"></span></p></section>
<section><h2>共同 2024 验证样本集合：10,501 场景</h2><div class="table"><table><thead><tr><th>模型</th><th>完成 epoch</th><th>BEST</th><th>保留 updates</th><th>核心损失</th><th>Brier</th><th>AUROC</th><th>AP</th></tr></thead><tbody id="rows"></tbody></table></div>
<p>开发阶段验证指标；不构成 2025 泛化评价。两模型各完成 1,313 次只读复核 forward。</p></section>
<section><h2>最终审计状态</h2><pre id="details"></pre></section></main>
<script>fetch('/api/status').then(r=>r.json()).then(s=>{document.getElementById('commit').textContent=s.completion_commit;
const rows=document.getElementById('rows');for(const [name,m] of Object.entries(s.models)){const tr=document.createElement('tr');
for(const value of [name,m.completed_epoch,m.BEST_epoch,m.retained_optimizer_steps,m.metrics.global_val_core_loss,m.metrics.Brier_Score,m.metrics.AUROC,m.metrics.Average_Precision]){
const td=document.createElement('td');td.textContent=typeof value==='number'&&!Number.isInteger(value)?value.toPrecision(10):String(value);tr.appendChild(td);}rows.appendChild(tr);}
document.getElementById('details').textContent=JSON.stringify(s,null,2);}).catch(e=>document.getElementById('details').textContent='状态读取失败：'+e.message);</script></html>'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--final-audit', type=Path, required=True)
    p.add_argument('--completion-commit', required=True)
    p.add_argument('--pdf-audit', type=Path, required=True)
    p.add_argument('--port', type=int, default=8771)
    args = p.parse_args()
    audit_path = args.final_audit.resolve()
    if not audit_path.is_relative_to(REPO / 'docs/v2_phase_a_review/final_completion'):
        raise PermissionError('Independent final audit path required')
    git = lambda *a: subprocess.check_output(['git', '-c', 'core.longpaths=true', *a], cwd=REPO)
    remote = git('ls-remote', 'origin', 'refs/heads/main').decode().split()[0]
    subprocess.run(['git', 'merge-base', '--is-ancestor', args.completion_commit, remote], cwd=REPO, check=True)
    relative = audit_path.relative_to(REPO).as_posix()
    if hashlib.sha256(git('show', args.completion_commit + ':' + relative)).hexdigest() != sha(audit_path):
        raise ValueError('Published final audit changed')
    audit = load(audit_path)
    packet_ref = next(r for r in audit['source_evidence'] if Path(r['absolute_local_path']).name == 'paired_comparison_packet.json')
    packet_path = Path(packet_ref['absolute_local_path']).resolve()
    if not packet_path.is_relative_to(REPO) or sha(packet_path) != packet_ref['sha256']:
        raise ValueError('Registered packet changed')
    state = completed_state(audit, load(packet_path), args.completion_commit)
    pdf_path = args.pdf_audit.resolve()
    pdf_ref = next(r for r in audit['source_evidence'] if Path(r['absolute_local_path']).resolve() == pdf_path)
    if not pdf_path.is_relative_to(REPO) or sha(pdf_path) != pdf_ref['sha256']:
        raise ValueError('Registered PDF audit changed')
    pdf_audit = load(pdf_path)
    files = {}
    for route, key in (('/report.pdf', 'pdf'), ('/report.tex', 'editable_latex')):
        ref = pdf_audit[key]; path = Path(ref['absolute_local_path']).resolve()
        if not path.is_relative_to(REPO) or sha(path) != ref['sha256']:
            raise ValueError('Registered report changed')
        files[route] = path
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_POST(self): self.send_error(405, 'Read only')
        def do_GET(self):
            route = self.path.split('?', 1)[0]
            if route == '/': body, mime = PAGE.encode(), 'text/html; charset=utf-8'
            elif route == '/api/status': body, mime = json.dumps(state, ensure_ascii=False).encode(), 'application/json; charset=utf-8'
            elif route in files: body, mime = files[route].read_bytes(), ('application/pdf' if route.endswith('.pdf') else 'text/plain; charset=utf-8')
            else: self.send_error(404); return
            self.send_response(200); self.send_header('Content-Type', mime); self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(body)
    print(json.dumps({'status': state['status'], 'url': f'http://127.0.0.1:{args.port}/', 'TRAINING_LAUNCH_SUPPORTED': False}), flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
