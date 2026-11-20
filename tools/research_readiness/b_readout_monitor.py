"""Serve the B readout progress on loopback using output filenames and receipts."""

import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path


def receipt(path):
    try:
        return json.loads(path.read_bytes())
    except (OSError, ValueError):
        return {}


def snapshot(output, service, proposal, total, time_limit):
    now = datetime.now(timezone.utc)
    launch = receipt(service / "target_launch.json")
    started_at = launch.get("at")
    seconds = max(0, int((now - datetime.fromisoformat(started_at)).total_seconds())) if started_at else 0
    finish = receipt(output / "completion.json")
    exit_record = receipt(service / "target_exit.json")
    files = {p.name for p in (output / "arrays").glob("batch_*.npz")}
    contiguous = next((i for i in range(total) if f"batch_{i:03d}.npz" not in files), total)
    # The next file can only be opened after the prior one has been closed and hashed.
    confirmed = max(0, contiguous - 1)
    if (finish.get("proposal_sha256") == proposal and finish.get("status") == "COMPLETE_SINGLE_ARM_READOUT"
            and finish.get("result", {}).get("forward_calls") == total and contiguous == total):
        state, confirmed = "complete", total
    elif (receipt(output / "failure.json") or receipt(service / "independent_failure.json")
          or exit_record.get("return_code", 0) != 0):
        state = "stopped"
    elif exit_record or seconds > time_limit:
        state = "verify"
    elif contiguous == total:
        state = "closing"
    elif started_at:
        state = "running"
    else:
        state = "pending"
    end = finish.get("finished") or exit_record.get("at")
    if started_at and end:
        seconds = max(0, int((datetime.fromisoformat(end) - datetime.fromisoformat(started_at)).total_seconds()))
    return dict(state=state, confirmed=confirmed, total=total, elapsed_seconds=seconds,
                started_at=started_at, as_of=now.isoformat(), proposal=proposal[:8])


def serve(run, proposal_file, ready_file, port=0):
    proposal = receipt(proposal_file)
    if proposal["authorization_scope"] != "REAL_COSINE9_FULL_DEV_READOUT_V1":
        raise ValueError("A B readout proposal is required")
    private = receipt(run / "PRIVATE_PREPARATION.json")
    if private["proposal_sha256"] != proposal["proposal_sha256"]:
        raise ValueError("Run and proposal identities differ")
    output, service = Path(private["output_root"]), Path(private["service_dir"])
    page = Path(__file__).with_name("b_readout_progress.html").read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/":
                body, content_type = page, "text/html; charset=utf-8"
            elif self.path == "/api/progress":
                body = json.dumps(snapshot(
                    output, service, proposal["proposal_sha256"],
                    proposal["budget"]["forward_batches"], proposal["budget"]["maximum_seconds"],
                )).encode("utf-8")
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

        def log_message(self, *_args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", port), Handler) as server:
        with ready_file.open("x", encoding="utf-8") as stream:
            json.dump({"url": f"http://127.0.0.1:{server.server_port}/"}, stream)
        server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--ready", type=Path, required=True)
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    serve(args.run, args.proposal, args.ready, args.port)


if __name__ == "__main__":
    main()
