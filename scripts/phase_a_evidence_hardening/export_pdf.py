"""Export a PDF after the desktop compiler has confirmed source compilation."""
from pathlib import Path
import json
import shutil
import subprocess

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "docs/phase_a_evidence_hardening"


def main(*, attempt: int = 1) -> None:
    result = json.loads((OUT/"tests/pdf_compile_attempt_003.json").read_text(encoding="utf-8"))
    content = json.loads(result["content"][0]["text"])
    if content.get("kind") != "success": raise RuntimeError("Desktop compilation must succeed first")
    scratch = OUT/("tests/pdf_export" if attempt == 1 else f"tests/pdf_export_attempt_{attempt:03d}")
    scratch.mkdir(exist_ok=False)
    source = OUT/"PHASE_A_HARDENING_REVIEW.tex"
    records = []
    for attempt in (1, 2):
        command = ["xelatex", "-interaction=nonstopmode", "-halt-on-error", "-no-shell-escape", "-output-directory="+str(scratch), str(source)]
        process = subprocess.run(command, cwd=OUT, capture_output=True, timeout=120)
        (scratch/f"compile_pass_{attempt}.log").write_bytes(process.stdout + process.stderr)
        records.append({"pass": attempt, "returncode": process.returncode})
        if process.returncode:
            (scratch/"export_status.json").write_text(json.dumps({"status": "FAIL", "attempts": records}, indent=2), encoding="utf-8")
            raise RuntimeError("PDF export failed; complete compile output retained")
    destination = OUT/"PHASE_A_HARDENING_REVIEW.pdf"
    if destination.exists() and attempt == 1: raise FileExistsError("Final PDF already exists")
    shutil.copyfile(scratch/destination.name, destination)
    (scratch/"export_status.json").write_text(json.dumps({"status": "PASS", "attempts": records}, indent=2), encoding="utf-8")
    render = OUT/("tests/pdf_render" if attempt == 1 else f"tests/pdf_render_attempt_{attempt:03d}")
    render.mkdir(exist_ok=False)
    process = subprocess.run(["pdftoppm", "-scale-to", "1300", "-png", str(destination), str(render/"page")], capture_output=True, timeout=120)
    (render/"render.log").write_bytes(process.stdout + process.stderr)
    if process.returncode: raise RuntimeError("PDF rendering failed")
    print(json.dumps({"status": "PDF_EXPORTED_AND_RENDERED", "pages_rendered": len(list(render.glob("page-*.png")))}))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=int, default=1)
    args = parser.parse_args()
    if args.attempt < 1: raise ValueError("Positive append-only attempt required")
    main(attempt=args.attempt)
