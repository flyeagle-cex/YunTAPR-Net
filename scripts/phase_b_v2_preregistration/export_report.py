"""Export/render only this unpublished standalone report; retain each attempt."""
from pathlib import Path
import argparse
import json
import shutil
import subprocess

REPO=Path(__file__).resolve().parents[2]
OUT=REPO / "docs/phase_b_v2_ablation_preregistration/v1"
BASELINE="8fbc06ba341aeee43136c18f20ebd6acd3463efd"
NAME="PHASE_B_V2_ABLATION_REVIEW"


def main(attempt: int) -> None:
    if type(attempt) is not int or attempt<1:
        raise ValueError("Positive append-only attempt required")
    compiler=json.loads((OUT/f"tests/compiler_attempt_{attempt:03d}.json").read_text(encoding="utf-8"))
    if json.loads(compiler["content"][0]["text"])["kind"]!="success":
        raise ValueError("Desktop compilation not confirmed")
    head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=REPO).decode().strip()
    tracked=subprocess.check_output(["git","ls-tree","--name-only","HEAD","--",(OUT/(NAME+".pdf")).relative_to(REPO).as_posix()],cwd=REPO)
    if head!=BASELINE or tracked:
        raise RuntimeError("Published or changed baseline; no artifact replacement")
    work=OUT/f".local/export_{attempt:03d}"; work.mkdir(exist_ok=False)
    status_path=OUT/f"tests/export_attempt_{attempt:03d}.json"
    passes=[]
    for index in (1,2,3):
        result=subprocess.run(["xelatex","-interaction=nonstopmode","-halt-on-error","-no-shell-escape",
            "-output-directory="+str(work),str(OUT/(NAME+".tex"))],cwd=OUT,capture_output=True,timeout=120)
        (work/f"compile_pass_{index}.log").write_bytes(result.stdout+result.stderr)
        passes.append({"pass":index,"returncode":result.returncode})
        if result.returncode:
            with status_path.open("x",encoding="utf-8") as stream:
                json.dump({"status":"FAIL","passes":passes,"local_full_log":work.relative_to(OUT).as_posix()},stream)
            raise RuntimeError("Export failed; full logs retained")
    final=OUT/(NAME+".pdf")
    if final.exists():
        backup=OUT/f".local/pdf_before_attempt_{attempt:03d}.pdf"
        if backup.exists(): raise FileExistsError("Backup already exists")
        shutil.copyfile(final,backup)
    shutil.copyfile(work/final.name,final)
    renders=OUT/f".local/render_{attempt:03d}"; renders.mkdir(exist_ok=False)
    result=subprocess.run(["pdftoppm","-scale-to","1300","-png",str(final),str(renders/"page")],capture_output=True,timeout=120)
    (renders/"render.log").write_bytes(result.stdout+result.stderr)
    log=(work/(NAME+".log")).read_text(encoding="utf-8",errors="replace")
    record={"status":"PASS" if result.returncode==0 else "FAIL","passes":passes,"render_returncode":result.returncode,
        "pages_rendered":len(list(renders.glob("page-*.png"))),
        "warnings":{key:log.count(key) for key in ("Overfull \\hbox","Missing character","LaTeX Warning")},
        "local_full_logs":work.relative_to(OUT).as_posix(),"local_renders":renders.relative_to(OUT).as_posix()}
    with status_path.open("x",encoding="utf-8") as stream: json.dump(record,stream,indent=2)
    print(json.dumps(record))
    if result.returncode: raise RuntimeError("Rendering failed")


if __name__=="__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--attempt",type=int,default=1)
    main(parser.parse_args().attempt)
