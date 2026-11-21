"""Read-only browser view of the one-shot A20-BISIDE-V1 run."""

import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path

from tail20_replay_monitor import count_rows, receipt


ROOT = Path(__file__).resolve().parents[2]
READINESS = ROOT / "docs/research_readiness"
PUBLIC = READINESS / "20261119_conditional_intensity_diagnostic" / "A20_EXECUTION_PROPOSAL.json"
EPOCHS = 9


def snapshot(output, service, proposal):
    now = datetime.now(timezone.utc)
    total = proposal["budget"]["total_updates"]
    time_limit = proposal["budget"]["max_model_seconds"]
    expected_dev_files = proposal["source_scope_summary"]["Development"]["file_count"]
    identity = proposal["execution_code_commit"]
    task = output / "B7_s2029"
    launch = receipt(service / "target_launch.json")
    exit_record = receipt(service / "target_exit.json")
    supervisor_failure = receipt(service / "independent_failure.json")
    runner_failure = receipt(output / "failure.json")
    done = receipt(output / "completion.json")
    started = launch.get("at")
    ended = exit_record.get("at") or supervisor_failure.get("at")
    elapsed = max(0, int((
        (datetime.fromisoformat(ended) if ended else now) - datetime.fromisoformat(started)
    ).total_seconds())) if started else 0

    updates = count_rows(
        task / "updates.sqlite",
        f"SELECT count(*) FROM updates WHERE model='B7' AND state='RETURNED' AND u BETWEEN 1 AND {total}",
    )
    per_epoch = total // EPOCHS
    epochs = []
    for epoch in range(1, EPOCHS + 1):
        target = per_epoch * epoch
        train = receipt(task / f"B7_train_{epoch:02d}.json")
        seal = receipt(task / f"B7_LAST_epoch_{epoch:02d}.receipt.json")
        train_sealed = train.get("updates") == target
        sealed = (train_sealed and seal.get("epoch") == epoch and seal.get("updates") == target
                  and seal.get("code_commit") == identity and bool(seal.get("checkpoint_sha256")))
        epochs.append(dict(epoch=epoch, train_sealed=train_sealed, sealed=sealed))
    closed_epochs = sum(epoch["sealed"] for epoch in epochs)
    current = min(closed_epochs + 1, EPOCHS)
    active = epochs[current - 1]
    predev = receipt(task / "B7_PREDEV_epoch_09.receipt.json")
    e9_saved = (
        predev.get("status") == "SEALED_TRAIN_BEFORE_DEV"
        and predev.get("updates") == total
        and predev.get("code_commit") == identity
        and bool(predev.get("checkpoint_sha256"))
    )
    science = done.get("point_a20_status")
    verified = (
        exit_record.get("return_code") == 0
        and done.get("status") == "COMPLETE_TRAIN_AND_DEV_EVALUATION"
        and done.get("proposal_sha256") == proposal["proposal_sha256"]
        and done.get("execution_code_commit") == identity
        and e9_saved and closed_epochs == EPOCHS
        and done.get("optimizer_updates") == total
        and done.get("source_bytes") == proposal["budget"]["total_source_bytes"]
        and done.get("source_files") == proposal["budget"]["total_source_files"]
        and science in ("PASS_DEV_POINT_A20_GATE", "FAIL_DEV_POINT_A20_GATE")
    )
    dev_read = None
    result = None
    if verified:
        state, updates = "complete", total
        comparison = done["gate"]["comparison"]
        checks = comparison["checks"]
        result = dict(
            passed=science == "PASS_DEV_POINT_A20_GATE", passed_guards=sum(x["pass_gate"] for x in checks.values()),
            guard_count=len(checks), point_a_tp=checks["point_a_tp"]["candidate"],
            point_a_fp=checks["point_a_fp"]["candidate"],
        )
    elif supervisor_failure or runner_failure or exit_record.get("return_code", 0) != 0:
        state = "stopped"
    elif exit_record or (started and elapsed > time_limit):
        state = "verify"
    elif closed_epochs == EPOCHS:
        state = "closing"
    elif active["train_sealed"]:
        if current == EPOCHS and not e9_saved:
            state = "saving"
        else:
            state = "development"
            dev_read = count_rows(task / f"B7_dev_reads_{current:02d}/reads.sqlite",
                                  "SELECT count(*) FROM file_io WHERE state='READ_COMPLETE'")
    else:
        state = "training" if started else "pending"

    return dict(
        state=state, updates=updates, total_updates=total, updates_per_epoch=per_epoch, epochs=epochs,
        closed_epochs=closed_epochs, current_epoch=current, e9_saved_before_dev=e9_saved,
        dev_files_read=dev_read, dev_files_total=expected_dev_files, result=result,
        started_at=started, elapsed_seconds=elapsed, time_limit_seconds=time_limit, as_of=now.isoformat(),
        proposal=proposal["proposal_sha256"][:8], code_commit=identity[:7],
    )


def serve(run, ready, *, proposal_file=PUBLIC, port=0):
    run, ready = run.resolve(), ready.resolve()
    if run.parent != (READINESS / ".local").resolve() or ready.parent != run:
        raise ValueError("Use the bound private A20 directory")
    proposal = receipt(run / "A20_EXECUTION_PROPOSAL.json")
    private = receipt(run / "PRIVATE_PREPARATION.json")
    output, service = run / "output", run / "service"
    if (proposal.get("authorization_scope") != "A20_BISIDE_V1_REAL_COSINE9_MATCHED"
            or proposal != receipt(proposal_file) or private["proposal_sha256"] != proposal["proposal_sha256"]
            or Path(private["output_root"]).resolve() != output.resolve()
            or Path(private["service_dir"]).resolve() != service.resolve()):
        raise ValueError("A fixed, published A20 proposal is required")
    assets = {
        "/": (Path(__file__).with_name("a20_biside_progress.html").read_bytes(), "text/html; charset=utf-8"),
        "/style.css": ((ROOT / "tools/b2_monitor/style.css").read_bytes(), "text/css; charset=utf-8"),
    }

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/api/progress":
                body = json.dumps(snapshot(output, service, proposal)).encode("utf-8")
                content_type = "application/json; charset=utf-8"
            elif self.path in assets:
                body, content_type = assets[self.path]
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
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
    parser.add_argument("--proposal", type=Path, default=PUBLIC)
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    serve(args.run, args.ready, proposal_file=args.proposal, port=args.port)
