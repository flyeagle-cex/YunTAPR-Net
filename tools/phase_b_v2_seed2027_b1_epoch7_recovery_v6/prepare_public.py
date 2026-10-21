"""Exact public allowlist and static source checks before publishing this release."""
from pathlib import Path
import ast,hashlib,json,subprocess
ROOT=Path(__file__).absolute().parents[2]
NAME='phase_b_v2_seed2027_b1_epoch7_recovery_v6'
OUT=ROOT/'docs/phase_b_v2_formal_execution/seed2027_b1_epoch7_recovery_v6'

def main():
    tests={'DELTA_TESTS.log':('DELTA_TESTS_attempt2.log',13),'CONSUMER_TESTS.log':('CONSUMER_TESTS_attempt2.log',5),'MONITOR_TESTS.log':('MONITOR_TESTS.log',5)}
    for public,(private,count) in tests.items():
        raw=(OUT/'.local'/private).read_text(encoding='utf-8')
        if f'Ran {count} tests' not in raw or '\nOK\n' not in raw:raise ValueError('TESTS_NOT_COMPLETE')
        if str(ROOT) in raw:raise ValueError('PRIVATE_PATH_IN_TEST_LOG')
        with (OUT/public).open('x',encoding='utf-8',newline='\n') as f:f.write(raw)
    protected=['src/yuntapr/models','src/yuntapr/losses','config/science_v2',
        'src/yuntapr/training/formal_phase_a_v2.py','src/yuntapr/training/phase_b_v2_seed2027_b1_epoch7_recovery_v4',
        'src/yuntapr/training/phase_b_v2_seed2027_b1_epoch7_recovery_v5']
    if subprocess.run(['git','diff','--quiet','HEAD','--',*protected],cwd=ROOT).returncode:
        raise ValueError('PROTECTED_SOURCE_CHANGED')
    paths=[]
    for folder in (ROOT/'src/yuntapr/training'/NAME,ROOT/'scripts'/NAME,ROOT/'tools'/NAME,
                   ROOT/'scripts/phase_b_v2_live_monitor_b1_epoch7_v6'):
        paths.extend(p for p in folder.iterdir() if p.is_file() and (p.suffix in ('.py','.ps1','.html') or p.name=='.gitignore'))
    paths.extend(p for p in OUT.iterdir() if p.is_file())
    pins={}
    for path in paths:
        raw=path.read_bytes().replace(b'\r\n',b'\n');text=raw.decode('utf-8')
        if ':'+chr(92)+'Users'+chr(92) in text or ':'+chr(92)*2+'Users'+chr(92)*2 in text:
            raise ValueError('PRIVATE_PATH_IN_PUBLIC_FILE')
        if path.suffix=='.py':ast.parse(text,filename=path.name)
        elif path.suffix=='.json':json.loads(text)
        path.write_bytes(raw);pins[path.relative_to(ROOT).as_posix()]={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
    row=dict(phase='SOURCE_FIXED_BEFORE_LAUNCH',baseline_commit='a32dc88fdbe128801d456f7f8a59a7f3256c5e4a',
        tests=dict(delta=13,consumer_paths=5,monitor=5,passed=23,failed=0,skipped=0),
        old_sources_unchanged=True,old_evidence_preserved=True,public_files=pins,
        new_optimizer_steps_before_launch=0,new_budget_granted=0,cumulative_cap=364969)
    manifest=OUT/'SOURCE_REVIEW.json'
    with manifest.open('x',encoding='utf-8',newline='\n') as f:json.dump(row,f,indent=2)
    subprocess.check_call(['git','add','-f','--',*pins,manifest.relative_to(ROOT).as_posix()],cwd=ROOT)
    check=subprocess.run(['git','diff','--cached','--check'],cwd=ROOT,capture_output=True,text=True)
    if check.returncode:raise ValueError(check.stdout[:1200])
    print(json.dumps(dict(public_files=len(pins)+1,static_checks='PASS',tests_passed=23)))

if __name__=='__main__':main()
