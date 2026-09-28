"""Create a reviewed, binary-free public snapshot of a completed decision run."""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sys
from pathlib import Path


RUN = Path(r"F:\pytorch\Research\outputs\b0_spatial_probability_contract_resolution\run_20260928T144303_935304Z")
REPO = Path(r"C:\Users\chenerxiao\Documents\极端降水预测\YunTAPR-Net-push-chunks")
DEST = REPO / "stage0-b0-evidence" / "evidence" / "outputs" / "b0_spatial_probability_contract_resolution" / RUN.name
CODE_DEST = REPO / "stage0-b0-evidence" / "code" / "b0_spatial_probability_contract_tools"
ALLOWED = {".md", ".json", ".csv", ".py", ".txt"}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    assert RUN.is_dir() and REPO.is_dir()
    assert (RUN / "logs" / "final_status.json").is_file()
    status = json.loads((RUN / "logs" / "final_status.json").read_text(encoding="utf-8"))
    assert status["tests_passed"] == 40 and status["b0_formal_training_started"] is False
    assert not DEST.exists(), "Do not overwrite an existing public snapshot"
    DEST.mkdir(parents=True)
    rows = []
    excluded = []
    for source in sorted(RUN.rglob("*")):
        if not source.is_file():
            continue
        relative = source.relative_to(RUN)
        if source.suffix.lower() not in ALLOWED:
            excluded.append((relative.as_posix(), sha(source)))
            continue
        assert not any(part.lower() in {"boundary", "mask", "raw"} for part in relative.parts), relative
        target = DEST / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        assert sha(source) == sha(target)
        rows.append(dict(relative_path=relative.as_posix(), sha256=sha(target), bytes=target.stat().st_size))
    assert len(excluded) == 1 and excluded[0][0] == "SPATIAL/sp04_coordinate_arrays.npz", excluded
    assert not any(p.suffix.lower() in {".npz", ".nc", ".geojson", ".zip"} for p in DEST.rglob("*"))
    CODE_DEST.mkdir(parents=True, exist_ok=True)
    for name in ("build_contract.py", "contract_math.py", "test_contract.py", "finalize_contract.py", "export_public.py"):
        source = Path(__file__).with_name(name)
        target = CODE_DEST / name
        assert not target.exists(), target
        shutil.copy2(source, target)
        assert sha(source) == sha(target)
    (DEST / "PUBLIC_EXPORT_NOTICE.md").write_text(
        "# Public export scope\n\n"
        "This is the reviewed text/code/index-mapping evidence from the completed decision run. "
        "The local `SPATIAL/sp04_coordinate_arrays.npz` was deliberately excluded from public GitHub; "
        f"its SHA256 is `{excluded[0][1]}` and it remains in the local F: run. "
        "No source satellite/precipitation data, GADM geometry, or GADM-derived mask arrays were copied. "
        "The published `evidence_registry.csv` is the complete **local** registry and therefore lists that one excluded NPZ. "
        "Coordinate and source paths in text files are provenance metadata only.\n",
        encoding="utf-8")
    with (DEST / "public_export_manifest.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(json.dumps(dict(destination=str(DEST), copied_evidence_files=len(rows), excluded=excluded,
                          public_bytes=sum(x["bytes"] for x in rows)), ensure_ascii=False))


if __name__ == "__main__":
    main()
