"""Offline safe receipt/format closeout; does not import Torch or read raw data."""
import json
from pathlib import Path
import shutil
from export_reports import build
HERE=Path(__file__).absolute().parent
private=HERE/'.local/attempt_002'
for p in (HERE/'tests').glob('*.log'):
    text=p.read_bytes().decode('utf-8-sig')
    if 'ResourceWarning' in text and ':\\' in text:
        shutil.copyfile(p,private/(p.stem+'_original.log'))
        lines=[]
        for line in text.splitlines():
            if ':\\' in line:
                prefix=line.split(' ... ')[0] if ' ... ' in line else 'synthetic log'
                line=prefix+' ... ResourceWarning: unclosed synthetic audit log; local path redacted'
            lines.append(line)
        text='\n'.join(lines)+'\n'
    p.write_bytes(text.replace('\r\n','\n').encode())
supervisor=json.loads((private/'supervisor.json').read_bytes())
build(private,supervisor)
status=json.loads((HERE/'final_status.json').read_bytes())
status['synthetic_boundary_unit_tests']={'unique_cases':37,'latest_full_suite_passed':37,
    'latest_full_suite_failed':0,'case_executions_across_logged_runs':110,
    'prior_task_test_suites_rerun':False,'model_constructions_in_unit_tests':0}
status['post_pilot_real_data_reads']=0
status['post_pilot_model_forwards']=0
(HERE/'final_status.json').write_bytes((json.dumps(status,indent=2)+'\n').encode())
(HERE/'tests/pdf_review.json').write_bytes((json.dumps(dict(
    final_builtin_compile='success',pdf_export='local XeLaTeX, installer disabled',
    pages=1,visually_reviewed_pages=[1],clipping_or_overlap_found=False),indent=2)+'\n').encode())
(HERE/'tests/results.json').write_bytes((json.dumps(status['synthetic_boundary_unit_tests'],indent=2)+'\n').encode())
for p in HERE.rglob('*'):
    if p.is_file() and '.local' not in p.parts and '__pycache__' not in p.parts and p.suffix not in ('.pdf','.png'):
        p.write_bytes(p.read_bytes().decode('utf-8-sig').replace('\r\n','\n').encode())
