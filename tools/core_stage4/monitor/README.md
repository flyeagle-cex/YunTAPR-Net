# Seed 2029 local receipt monitor

This is the existing standalone monitor copied into version control. The Python
server, page, styles, browser script and Python fixtures are byte-identical to
the deployed local copies. This export does not replace or restart that service.

Run with Python's standard library, supplying local paths yourself:

```powershell
python tools/core_stage4/monitor/server.py --experiment <local-experiment-directory> --port 0
```

For a recovery segment, also supply `--recovery-request <local-request.json>` and
`--source-commit <executed-commit>`. `--training-pid` is optional; without an
observed process, incomplete runs remain UNKNOWN. The service binds only to
127.0.0.1. It reads existing receipts and read-only SQLite snapshots on demand,
caches snapshots briefly and refreshes the page every 15 seconds. It never
imports the training executor or offers start, resume or stop endpoints.
The code contains experiment identity and budget constants; it is specific to
this seed and approved recovery, rather than a general experiment dashboard.

Runtime configuration, fixture databases, screenshots, raw metrics and service
logs are deliberately excluded from Git. The live page can display private
metrics; keep it local.

Existing test evidence is preserved under `docs/core_stage4/monitor_evidence/`.
Those files record the original checks and have not been relabeled as new runs.
The six original monitor checks, subsequent metric-parser check and three
recovery checks passed; browser checks covered initial and recovery states.
Earlier logs reflect the source at their respective test times. The two browser
check scripts now resolve `playwright` through normal Node package resolution
instead of a private machine path. Their logic is unchanged. For publication,
only syntax checks and byte-for-byte copy verification were performed; the
historical browser and training tests were not rerun.

Optional fixture checks from this directory: `python -m unittest -v test_monitor`.
The browser scripts require Playwright and Chrome, plus the matching initial or
early-recovery state described by their assertions; they are not endpoint
completion tests and are not automatically run on a live experiment.
