"""Loopback-only, read-only progress view for the fixed V7 paired evaluation."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sqlite3
import threading
import time
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_PROPOSAL = "00c5174611d23195bc212f7642a4964ee40b753a2c2b4cd104df857d5f623d5c"
ARM_BYTES = 26_639_253_112
ARM_FILES = 7_950
ARMS = (("CONTROL_E0", "E0 对照"), ("CANDIDATE_COSINE9", "COSINE9 候选"))
PAGE = r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><title>V7 两臂联合评价</title>
<style>
:root{font-family:Inter,"Segoe UI","Microsoft YaHei",sans-serif;color:#17212b;background:#f4f6f8;font-synthesis:none}*{box-sizing:border-box}body{margin:0}main{max-width:1050px;margin:0 auto;padding:34px 22px 50px}header{display:flex;justify-content:space-between;align-items:end;gap:16px;margin-bottom:22px}.eyebrow{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:#567080;font-weight:700}h1{font-size:29px;margin:8px 0 5px;letter-spacing:-.03em}.sub{margin:0;color:#5d6b75;font-size:14px}.live{background:#fff;border:1px solid #dfe5e9;border-radius:14px;padding:22px 24px;box-shadow:0 8px 24px #17212b0a}.state-line{display:flex;align-items:center;gap:10px}h2{font-size:17px;margin:0}.pill{font-size:12px;border-radius:999px;padding:6px 10px;background:#e8f4ef;color:#17674a;font-weight:700}.pill.pending{background:#eef1f4;color:#65717b}.pill.failed{background:#fae8e7;color:#9c3029}.stage{margin:12px 0 18px;color:#4d5b65}.arms{display:grid;grid-template-columns:1fr 1fr;gap:14px}.arm{border:1px solid #e4e9ec;border-radius:11px;padding:17px;background:#fcfdfd}.arm-head{display:flex;justify-content:space-between;align-items:center;gap:10px}.arm h3{margin:0;font-size:15px}.small{font-size:12px;color:#6d7a83}.track{height:8px;border-radius:8px;background:#e9eef0;margin:14px 0 9px;overflow:hidden}.fill{height:100%;background:#36876b;border-radius:8px;transition:width .4s}.fill.pending{background:#b9c3c9}.counts{display:flex;justify-content:space-between;color:#596771;font-size:12px;gap:8px}.facts{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:16px}.fact{border-top:1px solid #e9edef;padding-top:12px}.fact span{display:block;font-size:12px;color:#6d7a83;margin-bottom:5px}.fact strong{font-size:14px;font-variant-numeric:tabular-nums}.note{font-size:12px;line-height:1.6;color:#71808a;margin:16px 0 0}.lower{display:grid;grid-template-columns:1.2fr .8fr;gap:14px;margin-top:14px}.panel{background:#fff;border:1px solid #dfe5e9;border-radius:14px;padding:19px 21px}.panel h2{margin-bottom:13px}.line{display:flex;justify-content:space-between;gap:16px;padding:9px 0;border-top:1px solid #edf0f2;font-size:13px}.line span:first-child{color:#65727b}.line strong{font-variant-numeric:tabular-nums;text-align:right}.warn{color:#a34532}footer{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-top:16px;color:#71808a;font-size:12px}button{border:1px solid #cbd5da;background:white;border-radius:8px;padding:8px 12px;color:#22313a;font:inherit;cursor:pointer}button:hover{background:#f2f6f7}.mono{font-family:ui-monospace,Consolas,monospace}@media(max-width:700px){main{padding:22px 14px}.arms,.lower{grid-template-columns:1fr}.facts{grid-template-columns:1fr 1fr}header{align-items:start;flex-direction:column}h1{font-size:24px}}
</style></head><body><main>
<header><div><div class="eyebrow">YunTAPR-Net · 2024 Development</div><h1>V7 两臂联合评价</h1><p class="sub">固定 E9 · Seed 2029 · 只读实时进度</p></div><button id="refresh">立即刷新</button></header>
<section class="live"><div class="state-line"><h2 id="title">正在读取运行收据</h2><span id="state" class="pill">连接中</span></div><p id="stage" class="stage">读取本地状态…</p><div id="arms" class="arms"></div><div class="facts"><div class="fact"><span>已读取天气源</span><strong id="total">—</strong></div><div class="fact"><span>总体读取进度</span><strong id="progress">—</strong></div><div class="fact"><span>启动后用时</span><strong id="elapsed">—</strong></div><div class="fact"><span>执行时限余量</span><strong id="remaining">—</strong></div></div><p id="warning" class="note warn" hidden></p><p class="note">进度根据已交付天气文件/载荷计算，不表示源账本最终封口。完成状态需要九轮收据和总完成收据；科学结论始终标记为待验证。</p></section>
<div class="lower"><section class="panel"><h2>两臂状态</h2><div id="details"></div></section><section class="panel"><h2>运行边界</h2><div class="line"><span>更新 / replay / 自动重试</span><strong>0 / 0 / 0</strong></div><div class="line"><span>科学状态</span><strong>NOT_VERIFIED</strong></div><div class="line"><span>数据范围</span><strong>2024 Development</strong></div><div class="line"><span>训练控制</span><strong>只读，无启停操作</strong></div><div class="line"><span>方案指纹</span><strong class="mono">00c5174611d2</strong></div></section></div>
<footer><span id="updated">尚无快照</span><span>仅绑定本机 127.0.0.1 · 每 15 秒刷新</span></footer>
</main><script>
const $=id=>document.getElementById(id), nf=new Intl.NumberFormat('zh-CN');function duration(v){v=Math.max(0,Math.floor(v||0));return `${Math.floor(v/3600)}小时 ${Math.floor(v%3600/60)}分`}function render(s){const labels={RUNNING:'运行中',PENDING:'等待',COMPLETE:'已完成',FAILED:'失败',UNKNOWN:'状态待确认',STOPPED:'已停止'};const overall=s.arms.reduce((a,x)=>a+x.bytes,0),cap=s.arm_bytes*s.arms.length,pct=cap?100*overall/cap:0;$('state').textContent=labels[s.state]||s.state;$('state').className='pill '+(s.state==='PENDING'?'pending':s.state==='FAILED'||s.state==='STOPPED'?'failed':'');$('title').textContent=s.state==='RUNNING'?'两臂评价正在执行':s.state==='COMPLETE'?'两臂评价已完成':s.state==='FAILED'?'本次运行失败':s.state==='PENDING'?'评价尚未启动':'运行状态待确认';$('stage').textContent=s.stage;$('total').textContent=`${nf.format(s.arms.reduce((a,x)=>a+x.files,0))} / ${nf.format(s.arm_files*2)} 文件`;$('progress').textContent=`${pct.toFixed(1)}%`;$('elapsed').textContent=duration(s.elapsed_seconds);$('remaining').textContent=duration(s.remaining_seconds);$('arms').replaceChildren();$('details').replaceChildren();for(const a of s.arms){const percent=Math.min(100,100*a.bytes/s.arm_bytes),box=document.createElement('article');box.className='arm';box.innerHTML=`<div class="arm-head"><h3>${a.label}</h3><span class="small">${labels[a.state]||a.state}</span></div><div class="track"><div class="fill ${a.state==='PENDING'?'pending':''}" style="width:${percent.toFixed(2)}%"></div></div><div class="counts"><span>${nf.format(a.files)} / ${nf.format(s.arm_files)} 文件</span><span>${(a.bytes/1e9).toFixed(2)} / ${(s.arm_bytes/1e9).toFixed(2)} GB</span></div>`;$('arms').append(box);for(const [name,val] of [['已确认读取文件',`${nf.format(a.files)} / ${nf.format(s.arm_files)}`],['已交付载荷',`${(a.bytes/1e9).toFixed(3)} GB`],['账本读取状态',a.ledger],['任务状态',labels[a.state]||a.state]]){const row=document.createElement('div');row.className='line';row.innerHTML=`<span>${name}</span><strong>${val}</strong>`;$('details').append(row)}}$('warning').hidden=!s.warning;$('warning').textContent=s.warning||'';$('updated').textContent=`快照：${new Date(s.snapshot_utc).toLocaleString('zh-CN',{hour12:false,timeZone:'Asia/Shanghai'})} 北京时间`}
async function refresh(){try{const r=await fetch('/api/snapshot',{cache:'no-store'});if(!r.ok)throw 0;render(await r.json())}catch{$('updated').textContent='读取快照失败；15 秒后重试'}}$('refresh').onclick=refresh;refresh();setInterval(()=>{if(!document.hidden)refresh()},15000);
</script></body></html>'''


class Snapshot:
    def __init__(self, output: Path, service: Path, started: float):
        self.output, self.service, self.started = output, service, started
        self._cache = None
        self._cached_at = 0.0
        self._lock = threading.Lock()

    @staticmethod
    def _json(path: Path):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _arm(self, name: str, label: str):
        folder = self.output / name
        ledger = folder / "B7_development_09_reads" / "reads.sqlite"
        files = bytes_read = 0
        ledger_state = "等待读取账本"
        if ledger.is_file():
            try:
                with sqlite3.connect(ledger.as_uri() + "?mode=ro", uri=True, timeout=1) as db:
                    db.execute("PRAGMA query_only=ON")
                    grouped = db.execute("SELECT state,COUNT(*),COALESCE(SUM(actual_bytes),0) FROM file_io GROUP BY state").fetchall()
                files = sum(int(row[1]) for row in grouped if row[0] == "READ_COMPLETE")
                bytes_read = sum(int(row[2]) for row in grouped if row[0] == "READ_COMPLETE")
                ledger_state = "进行中" if any(row[0] == "INTENT" for row in grouped) else "已封口" if files >= ARM_FILES else "可读取"
            except sqlite3.Error:
                ledger_state = "账本暂忙，下次自动重试"
        failure = self._json(folder / "failure.json")
        complete = self._json(folder / "task_complete.json")
        claim = self._json(self.output / f"{name}_claim.json")
        state = "FAILED" if failure else "COMPLETE" if complete else "RUNNING" if folder.exists() and (claim or ledger.is_file()) else "PENDING"
        # Do not send failure payloads, paths, file identities, or source hashes to the UI.
        return dict(id=name, label=label, state=state, files=files, bytes=bytes_read, ledger=ledger_state)

    def get(self):
        with self._lock:
            if self._cache is not None and time.monotonic() - self._cached_at < 2:
                return self._cache
            arms = [self._arm(*arm) for arm in ARMS]
            failure = self._json(self.output / "failure.json")
            complete = self._json(self.output / "completion.json")
            if failure or any(a["state"] == "FAILED" for a in arms):
                state, stage = "FAILED", "检测到失败收据；保留现场，页面不会触发重试。"
            elif complete and all(a["state"] == "COMPLETE" for a in arms):
                state, stage = "COMPLETE", "两臂固定 E9 已留下完成收据；科学结论仍需独立审查。"
            elif any(a["state"] == "RUNNING" for a in arms):
                state = "RUNNING"
                active = next(a["label"] for a in arms if a["state"] == "RUNNING")
                stage = f"当前阶段：{active} 开发集读取/评价；完成后控制器按既定顺序自动接续另一臂。"
            else:
                state, stage = "PENDING", "两臂尚未发现活动读取账本。"
            now = datetime.now(timezone.utc)
            terminal = self.output / ("failure.json" if failure else "completion.json")
            stop_time = datetime.fromtimestamp(terminal.stat().st_mtime, timezone.utc) if terminal.exists() else now
            elapsed = max(0, int(stop_time.timestamp() - self.started))
            warning = "存在失败收据；请核对冻结输出，不要从页面启动重试。" if failure else None
            self._cache = dict(snapshot_utc=now.isoformat(), state=state, stage=stage, warning=warning,
                arms=arms, arm_bytes=ARM_BYTES, arm_files=ARM_FILES, elapsed_seconds=elapsed,
                remaining_seconds=max(0, 7200-elapsed), scientific_status="NOT_VERIFIED")
            self._cached_at = time.monotonic()
            return self._cache


class Handler(BaseHTTPRequestHandler):
    snapshot: Snapshot

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            body = PAGE.encode("utf-8")
            content_type = "text/html; charset=utf-8"
        elif path == "/api/snapshot":
            body = json.dumps(self.snapshot.get(), ensure_ascii=False, allow_nan=False).encode("utf-8")
            content_type = "application/json; charset=utf-8"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        self.send_error(405)

    def log_message(self, *_args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--service-dir", type=Path, required=True)
    parser.add_argument("--proposal-sha256", required=True)
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    output = args.output_root.resolve()
    service = args.service_dir.resolve()
    private = (ROOT / "docs/research_readiness/.local").resolve()
    if args.proposal_sha256 != EXPECTED_PROPOSAL:
        raise SystemExit("proposal identity mismatch")
    if output.name != "formal_output_v7" or not output.is_dir():
        raise SystemExit("unexpected or missing V7 output root")
    if not service.is_relative_to(private) or not service.is_dir():
        raise SystemExit("service directory must be an existing ignored .local directory")
    binding = json.loads((output / "binding.json").read_text(encoding="utf-8"))
    if binding.get("proposal_sha256") != EXPECTED_PROPOSAL:
        raise SystemExit("output binding identity mismatch")
    Handler.snapshot = Snapshot(output, service, float(binding["package_started_wall"]))
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.daemon_threads = True
    service_file = service / "v7_monitor_service.json"
    service_file.write_text(json.dumps({"url": f"http://127.0.0.1:{server.server_port}/", "pid": __import__("os").getpid(), "read_only": True}, indent=2), encoding="utf-8")
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        server.server_close()
        service_file.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
