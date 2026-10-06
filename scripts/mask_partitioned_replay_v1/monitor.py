"""Local read-only progress view for one independent diagnostic replay."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from mask_partitioned_replay_v1 import common as c
from quantile_autopsy_v1.monitor import alive, tail
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import argparse
import json


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--port", type=int, default=8767); args = parser.parse_args()
    run = args.run.resolve()
    if run.parent != c.RUN_ROOT.resolve() or not run.name.startswith("run_"):
        raise ValueError("Only a mask-partitioned diagnostic run is served")
    page = Path(__file__).with_name("ui.html").read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_GET(self):
            route = self.path.split("?", 1)[0]
            if route == "/": content, mime = page, "text/html; charset=utf-8"
            elif route == "/api/status":
                state = c.read(run / "progress.json"); state["process_alive"] = alive(state.get("pid"))
                state["stderr_tail"] = tail(run / "replay_stderr.txt")
                rec = run / "mask_partitioned_replay_reconciliation.json"
                state["reconciliation"] = c.read(rec) if rec.exists() else None
                content, mime = json.dumps(state, ensure_ascii=False, allow_nan=False).encode(), "application/json; charset=utf-8"
            elif route == "/api/gates":
                names = ("execution_scope.json", "observer_test_result.json", "replay_identity_preflight.json")
                content = json.dumps({n: c.read(run / n) if (run / n).exists() else None for n in names}, ensure_ascii=False).encode()
                mime = "application/json; charset=utf-8"
            elif route == "/api/summary":
                path = run / "mask_partitioned_quantile_extremes.json"
                content = json.dumps(c.read(path) if path.exists() else {"status": "NOT_COMPLETED"}, ensure_ascii=False).encode()
                mime = "application/json; charset=utf-8"
            else: self.send_error(404); return
            self.send_response(200); self.send_header("Content-Type", mime); self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store"); self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers(); self.wfile.write(content)
        def do_POST(self): self.send_error(405, "Read-only diagnostic dashboard")

    print(json.dumps({"url": f"http://127.0.0.1:{args.port}/", "run": str(run)}), flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
