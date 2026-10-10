"""Export the standalone teaching source and retain all render/compile attempts."""
from pathlib import Path
import argparse
import json
import shutil
import subprocess

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "docs/phase_b_v2_isolated_integration/v1"
NAME = "ISOLATED_INTEGRATION_REVIEW"
BASELINE = "ca524b1accdcb30524cf106bf40d533d698e61e7"


def main(attempt):
    if type(attempt) is not int or attempt < 1: raise ValueError("Positive append-only attempt required")
    compiler = json.loads((OUT / f"tests/compiler_attempt_{attempt:03d}.json").read_text(encoding="utf-8"))
    if json.loads(compiler["content"][0]["text"])["kind"] != "success": raise ValueError("Compilation unconfirmed")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO).decode().strip()
    tracked = subprocess.check_output(["git", "ls-tree", "--name-only", "HEAD", "--", (OUT/(NAME+".tex")).relative_to(REPO).as_posix()], cwd=REPO)
    if head != BASELINE or tracked: raise ValueError("Do not overwrite a published report")
    work = OUT / f".local/export_{attempt:03d}"; work.mkdir(exist_ok=False)
    passes = []
    for index in (1, 2, 3):
        result = subprocess.run(["xelatex", "-interaction=nonstopmode", "-halt-on-error", "-no-shell-escape",
            "-output-directory=" + str(work), str(OUT/(NAME+".tex"))], cwd=OUT, capture_output=True, timeout=120)
        (work / f"pass_{index}.log").write_bytes(result.stdout + result.stderr)
        passes.append({"pass": index, "returncode": result.returncode})
        if result.returncode: raise RuntimeError("Export failed; original logs retained")
    pdf = OUT/(NAME+".pdf")
    if pdf.exists(): shutil.copyfile(pdf, OUT/f".local/pdf_before_export_{attempt:03d}.pdf")
    shutil.copyfile(work/pdf.name, pdf)
    renders = OUT/f".local/render_{attempt:03d}"; renders.mkdir(exist_ok=False)
    render = subprocess.run(["pdftoppm", "-scale-to", "1300", "-png", str(pdf), str(renders/"page")], capture_output=True, timeout=120)
    (renders/"render.log").write_bytes(render.stdout+render.stderr)
    log = (work/(NAME+".log")).read_text(encoding="utf-8", errors="replace")
    record = {"status": "PASS" if render.returncode == 0 else "FAIL", "passes": passes,
              "pages_rendered": len(list(renders.glob("page-*.png"))), "render_returncode": render.returncode,
              "warnings": {k: log.count(k) for k in ("Overfull \\hbox", "Missing character", "LaTeX Warning")},
              "full_logs_private": work.relative_to(OUT).as_posix(), "renders_private": renders.relative_to(OUT).as_posix()}
    with (OUT/f"tests/export_attempt_{attempt:03d}.json").open("x", encoding="utf-8") as stream: json.dump(record, stream, indent=2)
    print(json.dumps(record))
    if render.returncode: raise RuntimeError("Render failed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--attempt", type=int, required=True)
    main(parser.parse_args().attempt)
