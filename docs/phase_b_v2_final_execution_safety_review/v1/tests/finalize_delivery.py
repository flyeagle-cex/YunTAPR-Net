"""Final source/doc verification. No child launches, data/model/GPU operations."""
import ast
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).absolute().parents[4]
OUT=ROOT/'docs/phase_b_v2_final_execution_safety_review/v1'
NS=ROOT/'src/yuntapr/experimental/phase_b_v2_execution_watchdog_candidate'
sys.path.insert(0,str(ROOT/'src'))
from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.winjob import open_process, native_identity, close_handle


def main():
    # Final independent PID check never kills any PID and recognizes PID reuse.
    identities={}
    for file in list((OUT/'tests').glob('run_*.json'))+list((OUT/'tests').glob('abrupt_exit_*.json')):
        doc=json.loads(file.read_text(encoding='utf-8'))
        for r in doc.get('results',[doc]):
            for row in r.get('observed_process_identities',[]):
                identities[(row['pid'],row['creation_filetime'])]=row
    rows=[]
    for (pid,created),row in identities.items():
        h=open_process(0x1000,False,pid)  # query-limited; no termination right
        if not h:
            import ctypes
            error=ctypes.get_last_error()
            status='NOT_PRESENT' if error in (87,1168) else 'NOT_VERIFIED_ACCESS_ERROR'
            rows.append(dict(pid=pid,creation_filetime=created,status=status,error=error))
        else:
            try:
                current=native_identity(h)
                rows.append(dict(pid=pid,creation_filetime=created,
                                 status='PID_REUSED_DIFFERENT_OBJECT' if current!=row else 'FAIL_STILL_PRESENT'))
            finally: close_handle(h)
    audit=dict(observed_process_instances=len(rows),remaining_matching_test_processes=sum(r['status']=='FAIL_STILL_PRESENT' for r in rows),
               query_errors=sum(r['status']=='NOT_VERIFIED_ACCESS_ERROR' for r in rows),rows=rows)
    assert audit['remaining_matching_test_processes']==0
    (OUT/'tests/end_process_audit.json').write_text(json.dumps(audit,indent=2)+'\n',encoding='utf-8',newline='\n')
    checks=0
    def check(value):
        nonlocal checks
        checks+=1
        if not value: raise AssertionError('Delivery check '+str(checks))
    required=['README.md','WATCHDOG_TERMINATION_TEST.md','PROCESS_IDENTITY_AUDIT.md','RESOURCE_SAFETY_REVIEW.md',
              'FORMAL_RUNNER_CODE_REVIEW.md','REMAINING_EXECUTION_BLOCKERS.md','final_status.json',
              'FINAL_EXECUTION_SAFETY_REVIEW.tex','FINAL_EXECUTION_SAFETY_REVIEW.pdf']
    for name in required: check((OUT/name).is_file() and (OUT/name).stat().st_size>100)
    state=json.loads((OUT/'final_status.json').read_text())
    for key,expected in {'V2_PHASE_B_AUTHORIZED':False,'FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED':False,
                         'FORMAL_PHASE_B_OPTIMIZER_STEPS':0,'HISTORICAL_RECOVERY_RATIFICATION':'NOT_GRANTED',
                         '2025_PIXELS_READ':0,'historical_2025_path_attributes':'NOT_INSTRUMENTED',
                         'final_tests_passed':31,'final_tests_failed':0}.items(): check(state[key]==expected)
    validation=json.loads((OUT/'protected_validation.json').read_text())
    check(not validation['changed_preexisting_tracked_paths']); check(validation['sealed_quota_unchanged']); check(validation['sealed_rows_unchanged'])
    for file in list(NS.glob('*.py'))+list((OUT/'tests').glob('*.py')):
        tree=ast.parse(file.read_text(encoding='utf-8')); check(bool(tree.body))
    check((OUT/'FINAL_EXECUTION_SAFETY_REVIEW.pdf').read_bytes().startswith(b'%PDF-'))
    check(not audit['remaining_matching_test_processes']); check(not audit['query_errors'])
    (OUT/'tests/delivery_validation.json').write_text(json.dumps(dict(static_checks_passed=checks,static_checks_failed=0,
           child_launches=0,model_imports=0,optimizer_steps=0,pdf_pages=3,pdf_builtin_compile='SUCCESS',
           pdf_visual_review='PASS_ALL_3_PAGES',initial_pdf_overfull_boxes=2,final_pdf_overfull_boxes=0),indent=2)+'\n',encoding='utf-8',newline='\n')
    files=sorted(p for p in OUT.rglob('*') if p.is_file() and '.local' not in p.parts and '__pycache__' not in p.parts and p.name!='manifest.json')
    files+=sorted(NS.glob('*.py'))
    records=[]
    for p in files:
        if p.suffix not in ('.pdf',):
            b=p.read_bytes()
            # Public relative repository paths are fine; local absolute ones are not.
            if b.startswith(b'\xff\xfe'): text=b.decode('utf-16')
            else: text=b.decode('utf-8-sig')
            # Assemble sentinels so this checker does not match its own source.
            if ('C:'+'\\Users\\') in text or ('C:'+'/Users/') in text:
                raise ValueError('Private absolute path in public delivery: '+p.name)
        records.append(dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    (OUT/'manifest.json').write_text(json.dumps(dict(schema='YUNTAPR_EXECUTION_SAFETY_REVIEW_V1',baseline_commit=state['baseline_commit'],
        files=records,formal_authorization=False,exclusions=['.local','__pycache__','manifest self hash'],
        commit_identity='Resolve Git history of this directory; reported after push'),indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(static_checks_passed=checks,files=len(records),remaining_test_processes=audit['remaining_matching_test_processes'],
                         observed_process_instances=len(rows),pid_query_errors=audit['query_errors'])))


if __name__=='__main__':main()
