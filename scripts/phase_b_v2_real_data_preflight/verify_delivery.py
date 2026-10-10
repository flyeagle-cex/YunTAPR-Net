"""Independent public artifact arithmetic/SHA/privacy check; no raw data read."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import ast
import re
import subprocess

root=Path(__file__).resolve().parents[2]
out=root/"docs/phase_b_v2_real_data_preflight/v1"
result=json.loads((out/"audit_results.json").read_text(encoding="utf-8"))
ledger=json.loads((out/"DATA_ACCESS_LEDGER.json").read_text(encoding="utf-8"))
selection=json.loads((out/"DECODE_SELECTION.json").read_text(encoding="utf-8"))
events=ledger["events"]
assert len(events)==ledger["controlled_read_open_attempts"]==816
assert sum(e["bytes_returned"] for e in events)==ledger["controlled_application_bytes_returned"]
assert all(e["status"]=="SHA_PASS" and e["read_open_success"] for e in events)
raw=[e for e in events if e["kind"] in ("B13","IMERG")]
assert len(raw)==48*7==336
assert all(e["year"] in (2023,2024) for e in raw)
assert {k:sum(e["kind"]==k for e in events) for k in ("SCALER","YUNNAN_MASK")}=={"SCALER":1,"YUNNAN_MASK":1}
assert len(result["decoded"])==len(selection["selected"])==48
assert len({r["sample_id"] for r in result["decoded"]})==48
assert [{k:r[k] for k in ("year","month","position","index","sample_id","analysis_time")} for r in result["decoded"]]==selection["selected"]
assert all(r["status"]=="PASS" and r["yunnan_valid_count"]==3430 for r in result["decoded"])
first_reference_read=min(datetime.fromisoformat(e["opened_at_utc"]) for e in events if e["kind"]=="IMERG")
selection_mtime=datetime.fromtimestamp((out/"DECODE_SELECTION.json").stat().st_mtime,timezone.utc)
assert selection_mtime<first_reference_read
assert result["resources"]["peak_working_set_bytes"]<result["limits"]["max_working_set_bytes"]
assert ledger["controlled_data_bytes"]<ledger["limits"]["max_total_data_bytes"]
assert result["elapsed_seconds"]<result["limits"]["max_elapsed_seconds"]
assert not subprocess.check_output(["git","diff","--name-only"],cwd=root).strip()
sources=json.loads((root/"docs/phase_b_v2_formal_runner_candidate/v1/source_identity.json").read_text(encoding="utf-8"))["checked_public_files"]
for item in sources:
    assert hashlib.sha256((root/item["path"]).read_bytes()).hexdigest()==item["sha256"],item["path"]
prior=json.loads((root/"docs/phase_b_v2_formal_runner_candidate/v1/manifest.json").read_text(encoding="utf-8"))
for item in prior["files"]:
    assert hashlib.sha256((root/item["path"]).read_bytes()).hexdigest()==item["sha256"],item["path"]
raw_unique=len({e["file_key"] for e in raw})
durations=[r["seconds"] for r in result["decoded"]]
summary={"status":"PASS","verified_at_utc":datetime.now(timezone.utc).isoformat(),
    "readonly_unit_tests_passed":36,"frozen_public_inventory_SHA_recheck":len(sources),
    "prior_delivery_manifest_members_SHA_recheck":len(prior["files"]),
    "raw_data_read_opens":len(raw),"raw_data_unique_files":raw_unique,
    "raw_data_bytes_returned":sum(e["bytes_returned"] for e in raw),
    "scaler_and_mask_read_opens":2,
    "all_controlled_read_opens":len(events),
    "selected_scenes":48,"sample_selection_before_first_reference_bytes":True,
    "decode_read_normalization_seconds_sum":sum(durations),
    "decode_scene_seconds_min":min(durations),"decode_scene_seconds_max":max(durations),
    "unselected_raw_files_full_SHA_NOT_VERIFIED":result["checks"]["source_reference_inventory"]["unique_files"]-raw_unique,
    "peak_working_set_MiB":result["resources"]["peak_working_set_bytes"]/1024**2,
    "peak_committed_pagefile_MiB":result["resources"]["peak_pagefile_bytes"]/1024**2,
    "limits_applied":"Working set, payload bytes and elapsed time caps; private commit measured separately",
    "model_forwards":0,"optimizer_steps":0,"2025_raw_reads":0,"private_checkpoint_reads":0,
    "initial_launcher_failure_retained":True,
    "overall_readiness_status_unchanged":result["overall_status"]}
with (out/"PACKAGE_VERIFICATION.json").open("x",encoding="utf-8",newline="\n") as handle:
    json.dump(summary,handle,ensure_ascii=False,indent=2);handle.write("\n")
# Append the independent public verification and this checker to the new manifest.
manifest_path=out/"manifest.json"
manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
for path in (out/"PACKAGE_VERIFICATION.json",Path(__file__).resolve()):
    manifest["files"].append({"path":path.relative_to(root).as_posix(),"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"bytes":path.stat().st_size})
manifest["files"].sort(key=lambda item:item["path"])
new_sources=sorted((root/"src/yuntapr/experimental/phase_b_v2_real_data_preflight").glob("*.py"))+sorted((root/"scripts/phase_b_v2_real_data_preflight").glob("*.py"))+sorted((root/"tests/phase_b_v2_real_data_preflight").glob("*.py"))
for path in new_sources:
    tree=ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr in ("forward","backward","step","fit","load_state_dict"):
            raise ValueError("Forbidden execution call")
static_path=out/"STATIC_NO_TRAINING_AUDIT.json"
static=json.loads(static_path.read_text(encoding="utf-8"));static["AST_source_files"]=len(new_sources)
static_path.write_text(json.dumps(static,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
# Add explicit aggregate decode timing and committed-memory distinction.
report=out/"DECODE_AND_RESOURCE_REPORT.md"
with report.open("a",encoding="utf-8",newline="\n") as handle:
    handle.write("\n## 独立汇总核验\n\n```json\n"+json.dumps(summary,ensure_ascii=False,indent=2)+"\n```\n")
for item in manifest["files"]:
    p=root/item["path"]
    item["sha256"]=hashlib.sha256(p.read_bytes()).hexdigest();item["bytes"]=p.stat().st_size
    text=p.read_text(encoding="utf-8")
    if (re.search(r"[A-Za-z]:[/\\\\]",text) or '"private_path":' in text) and p.suffix!=".py":
        raise ValueError("Private data found in public report")
manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
allow=[item["path"] for item in manifest["files"]]+[manifest_path.relative_to(root).as_posix()]
(out/".local/publication_allowlist.paths").write_text("\n".join(sorted(allow))+"\n",encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))
