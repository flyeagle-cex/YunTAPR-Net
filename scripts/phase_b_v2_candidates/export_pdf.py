"""Export and render the self-contained candidate report after compiler success."""
from pathlib import Path
import json
import shutil
import subprocess

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "docs/phase_b_v2_protocol_candidates/v1_20261010"


def main(attempt: int) -> None:
    if type(attempt) is not int or attempt < 1:
        raise ValueError("Positive append-only attempt required")
    result = json.loads((OUT/f"tests/pdf_compile_attempt_{attempt:03d}.json").read_text(encoding="utf-8"))
    if json.loads(result["content"][0]["text"]).get("kind") != "success":
        raise RuntimeError("Desktop compilation was not confirmed")
    suffix = "" if attempt == 1 else f"_attempt_{attempt:03d}"
    scratch, render = OUT/("tests/pdf_export"+suffix), OUT/("tests/pdf_render"+suffix)
    status_path = OUT/("tests/pdf_export_status"+suffix+".json")
    scratch.mkdir(exist_ok=False)
    records = []
    for index in (1,2,3):
        cmd = ["xelatex","-interaction=nonstopmode","-halt-on-error","-no-shell-escape",
               "-output-directory="+str(scratch),str(OUT/"PHASE_B_V2_CANDIDATE_REVIEW.tex")]
        result = subprocess.run(cmd,cwd=OUT,capture_output=True,timeout=120)
        # Full local diagnostics retained; public summary does not expose host paths.
        (scratch/f"compile_pass_{index}.log").write_bytes(result.stdout+result.stderr)
        records.append({"pass":index,"returncode":result.returncode})
        if result.returncode:
            status_path.write_text(json.dumps({"status":"FAIL","attempts":records}),encoding="utf-8")
            raise RuntimeError("Export failed; complete logs retained locally")
    final = OUT/"PHASE_B_V2_CANDIDATE_REVIEW.pdf"
    if final.exists():
        baseline = "6e692625ebdd9bdaeff65e22d0ce59af349d98c5"
        head = subprocess.check_output(["git","rev-parse","HEAD"],cwd=REPO).decode().strip()
        tracked = subprocess.check_output(["git","ls-tree","--name-only","HEAD","--",final.relative_to(REPO).as_posix()],cwd=REPO)
        backup = OUT/f".local/pdf_before_export_attempt_{attempt:03d}.pdf"
        if head != baseline or tracked or backup.exists():
            raise FileExistsError("Published/changed/foreign output cannot be replaced")
        shutil.copyfile(final,backup)
    shutil.copyfile(scratch/final.name,final)
    render.mkdir(exist_ok=False)
    result = subprocess.run(["pdftoppm","-scale-to","1300","-png",str(final),str(render/"page")],capture_output=True,timeout=120)
    (render/"render.log").write_bytes(result.stdout+result.stderr)
    log = (scratch/"PHASE_B_V2_CANDIDATE_REVIEW.log").read_text(encoding="utf-8",errors="replace")
    warning_counts = {key:log.count(key) for key in ("Overfull \\hbox", "Missing character", "LaTeX Warning")}
    status = {"status":"PASS" if result.returncode == 0 else "FAIL", "attempts":records,
              "render_returncode":result.returncode,"pages_rendered":len(list(render.glob("page-*.png"))),
              "warning_counts":warning_counts,"local_complete_logs":str(scratch.relative_to(OUT))+";"+str(render.relative_to(OUT)),
              "public_logs_policy":"summary only; no machine-specific paths or duplicate intermediates"}
    status_path.write_text(json.dumps(status,indent=2)+"\n",encoding="utf-8")
    if result.returncode:
        raise RuntimeError("Render failed")
    print(json.dumps(status))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt",type=int,default=1)
    main(parser.parse_args().attempt)
