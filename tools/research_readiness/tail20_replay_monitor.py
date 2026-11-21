"""Read-only loopback view of the authorized TAIL20 E9 replay."""

import argparse
from contextlib import closing
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sqlite3

from b_readout_monitor import receipt


ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / "docs/research_readiness/.local"
PUBLIC = ROOT / "docs/research_readiness/20261119_conditional_intensity_diagnostic"
SCOPE = "TAIL20_AUX_V1_E8_TO_E9_REPLAY"


def count_rows(path, sql):
    if not path.is_file():
        return 0
    try:
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=0.5)) as db:
            return db.execute(sql).fetchone()[0]
    except sqlite3.OperationalError:
        return None


def snapshot(output, service, proposal, dev_total):
    now = datetime.now(timezone.utc)
    budget = proposal["budget"]
    total = budget["total_updates"]
    last_update = budget["effective_updates"]
    folder = output / "B7_s2029"
    launch = receipt(service / "target_launch.json")
    worker_exit = receipt(service / "target_exit.json")
    supervisor_stop = receipt(service / "independent_failure.json")
    worker_failure = receipt(output / "failure.json")
    done = receipt(output / "completion.json")
    train = receipt(folder / "B7_train_09.json")
    predev = receipt(folder / "B7_PREDEV_epoch_09.receipt.json")
    dev_seal = receipt(folder / "B7_dev_reads_09/pass_receipt.json")
    checkpoint = receipt(folder / "B7_LAST_epoch_09.receipt.json")
    started = launch.get("at")
    ended = worker_exit.get("at") or supervisor_stop.get("at")
    elapsed = max(0, int(((datetime.fromisoformat(ended) if ended else now)
                         - datetime.fromisoformat(started)).total_seconds())) if started else 0
    replayed = count_rows(
        folder / "updates.sqlite",
        f"SELECT count(*) FROM updates WHERE model='B7' AND state='RETURNED' AND u>{last_update - total} AND u<={last_update}",
    )
    dev_read = count_rows(
        folder / "B7_dev_reads_09/reads.sqlite",
        "SELECT count(*) FROM file_io WHERE state='READ_COMPLETE'",
    )
    comparison = done.get("gate", {}).get("comparison", {})
    verified = (
        worker_exit.get("return_code") == 0
        and done.get("status") == "COMPLETE_TRAIN_AND_DEV_EVALUATION"
        and done.get("proposal_sha256") == proposal["proposal_sha256"]
        and done.get("execution_code_commit") == proposal["execution_code_commit"]
        and done.get("segment_updates") == total
        and done.get("optimizer_updates") == last_update
        and done.get("replayed_updates") == total
        and done.get("source_bytes") == budget["total_source_bytes"]
        and done.get("source_files") == budget["total_source_files"]
        and bool(checkpoint.get("checkpoint_sha256"))
        and done.get("checkpoint_sha256") == checkpoint.get("checkpoint_sha256")
        and comparison.get("status") in ("PASS_DEV_TAIL_GATE", "FAIL_DEV_TAIL_GATE")
    )
    weight_saved = predev.get("status") == "SEALED_TRAIN_BEFORE_DEV" and predev.get("updates") == last_update
    if verified:
        state = "complete"
        replayed, dev_read = total, dev_total
    elif supervisor_stop or worker_failure or worker_exit.get("return_code", 0) != 0:
        state = "stopped"
    elif worker_exit or (started and elapsed > budget["max_model_seconds"]):
        state = "verify"
    elif dev_seal:
        state = "closing"
    elif weight_saved:
        state = "development"
    elif train.get("updates") == last_update or replayed == total:
        state = "saving"
    elif started:
        state = "training"
    else:
        state = "pending"
    result = None
    if verified:
        guards = comparison["checks"]
        result = dict(passed=sum(check["pass_gate"] for check in guards.values()), total=len(guards),
                      gate_passed=comparison["status"] == "PASS_DEV_TAIL_GATE",
                      point_a_restored=comparison["point_a_detection_restored"])
    return dict(
        state=state, replayed=replayed, replay_total=total, start_step=last_update-total+1,
        end_step=last_update, predev_checkpoint=weight_saved, dev_read=dev_read, dev_total=dev_total,
        dev_pass_sealed=bool(dev_seal and not dev_seal.get("during_failure")),
        started_at=started, elapsed_seconds=elapsed, time_limit_seconds=budget["max_model_seconds"],
        as_of=now.isoformat(), proposal=proposal["proposal_sha256"][:8], result=result,
    )


def serve(run, ready, port):
    run, ready = run.resolve(), ready.resolve()
    if run.parent != LOCAL.resolve() or ready.parent != run:
        raise ValueError("Use the bound run's private directory")
    proposal = receipt(run / "TAIL20_RECOVERY_PROPOSAL.json")
    private = receipt(run / "PRIVATE_PREPARATION.json")
    output, service = run / "output", run / "service"
    if (proposal["authorization_scope"] != SCOPE or private["proposal_sha256"] != proposal["proposal_sha256"]
            or proposal != receipt(PUBLIC / "TAIL20_RECOVERY_PROPOSAL.json")
            or Path(private["output_root"]).resolve() != output.resolve()
            or Path(private["service_dir"]).resolve() != service.resolve()):
        raise ValueError("Expected the exact bound TAIL20 E9 replay")
    manifest = receipt(PUBLIC / "TAIL20_EXECUTION_PROPOSAL.json")
    source_scope = manifest["source_scope_summary"]
    if (manifest["execution_code_commit"] != proposal["scientific_choices"]["recovery"]["parent_execution_commit"]
            or sum(source_scope[role]["file_count"] for role in ("Train", "Development")) + 1
            != proposal["budget"]["total_source_files"]):
        raise ValueError("Development archive total differs from the bound replay")
    dev_total = source_scope["Development"]["file_count"]
    page = Path(__file__).with_name("tail20_replay_progress.html").read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/":
                body, content_type = page, "text/html; charset=utf-8"
            elif self.path == "/api/progress":
                body = json.dumps(snapshot(output, service, proposal, dev_total)).encode("utf-8")
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
        with ready.open("x", encoding="utf-8") as stream:
            json.dump({"url": f"http://127.0.0.1:{server.server_port}/"}, stream)
        server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--ready", type=Path, required=True)
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    serve(args.run, args.ready, args.port)
