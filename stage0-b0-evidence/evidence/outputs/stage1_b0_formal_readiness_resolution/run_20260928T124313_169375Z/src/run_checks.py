from pathlib import Path
import json,os,shutil,subprocess,sys
from probe import RUN,sha,writej

def main():
    source=Path(__file__).parent/'test_readiness.py'
    dest=RUN/'tests/test_readiness.py'
    if not dest.exists(): shutil.copyfile(source,dest)
    elif sha(source)!=sha(dest):
        history=RUN/'tests/source_history'; history.mkdir(exist_ok=True)
        old=history/('test_readiness_'+sha(dest)[:12]+'.py')
        if not old.exists(): shutil.copyfile(dest,old)
        shutil.copyfile(source,dest)
    attempts=list((RUN/'tests').glob('pytest_attempt_*.xml')); attempt=len(attempts)+1
    xml=RUN/f'tests/pytest_attempt_{attempt}.xml'; stdout=RUN/f'tests/pytest_attempt_{attempt}.txt'
    cmd=[sys.executable,'-X','utf8','-B','-m','pytest',str(dest),'-q','-p','no:cacheprovider','--junitxml',str(xml)]
    env=os.environ.copy(); env['PYTHONDONTWRITEBYTECODE']='1'
    proc=subprocess.run(cmd,cwd=RUN,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8')
    stdout.write_text(proc.stdout,encoding='utf-8')
    writej(f'logs/pytest_command_{attempt}.json',dict(command=cmd,exit_code=proc.returncode,stdout=str(stdout),xml=str(xml),
        code_sha256=sha(dest),scope='Contract tests, metadata/coordinate and integrity checks only; no prior smoke rerun'))
    print(proc.stdout); sys.exit(proc.returncode)

if __name__=='__main__': main()
