"""Run only the explicit test directory, capturing stdout and preserving every earlier result."""
import os,subprocess,sys
from pathlib import Path
from config import *
from common import write_text,write_json
def main():
    CACHE.mkdir(parents=True,exist_ok=True)
    base=CACHE/"pytest_final"
    if base.exists():raise FileExistsError("Use a fresh run; do not let pytest delete a previous basetemp")
    command=[str(PYTHON),"-B","-m","pytest","tests/test_continuous.py","-q","-p","no:cacheprovider",
             "--rootdir",".","--confcutdir",".","--import-mode","importlib","--basetemp",str(base),
             "--junitxml","tests/pytest_final.xml"]
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1",PYTHONIOENCODING="utf-8")
    result=subprocess.run(command,cwd=OUT,env=env,capture_output=True,text=True,encoding="utf-8",errors="replace")
    write_text(OUT/"tests/pytest_final_output.txt",result.stdout+"\n"+result.stderr)
    write_json(OUT/"logs/pytest_command.json",{"cwd":str(OUT),"argv":command,"returncode":result.returncode,
        "junit_alias_note":"pytest_verified.xml is a byte-identical alias of this one test execution"})
    if (OUT/"tests/pytest_final.xml").exists():
        write_text(OUT/"tests/pytest_verified.xml",(OUT/"tests/pytest_final.xml").read_text(encoding="utf-8"))
    print(result.stdout,result.stderr,flush=True)
    raise SystemExit(result.returncode)
if __name__=="__main__":main()
