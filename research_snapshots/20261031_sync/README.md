# Existing local source/metadata archival snapshot (2026-10-31)

This directory preserves pre-existing standalone metric code, its synthetic tests, workspace helpers,
and older worktree source/metadata. It adds no model, module, training, inference, or new scientific result.
Source suffixes have an additional `.txt` to prevent discovery/import/execution of old launchers.
Python formatting is normalized through AST; original comments are preserved in a comment header.
The AST is checked unchanged apart from string contents used for private-locator redaction.

`docs/sync_audit/20261031/archive_manifest.csv` lists every source, original byte SHA256, archived SHA256,
size, description and locator-redaction flag. Public archives replace private absolute locators only;
original files, scientific numbers, existing executors, approvals and historical weights remain untouched.
They are historical evidence, not runnable releases, current status, renewed authorization or scientific acceptance.
The pinned corrective metric engine originally has SHA256
`0ca882baf7d4fcc00aa72543bff4773e98a27130b56b86fba41c7a3905eb8e93`;
its existing `tools/research_readiness/resume_metric_backfill.py` wrapper supplies the corrected B0/B1
precision context. The archived engine alone must not be treated as the completed execution package.

Current scientific state is summarized in the synchronization report and current terminal receipts.
Older RUNNING, queued, budget or authorization fields are immutable historical observations, not current grants.
2025 Final Test remains sealed. Archives are never imported or run during this task.
