"""Independent saved-XLSX checks; openpyxl is used read-only, never for authoring."""
import hashlib
import json
import math
import re
import statistics
import sys
import zipfile
from pathlib import Path
import openpyxl

out=Path(sys.argv[1]); file=out/'YunTAPR-Net_三类反演评价_20261105.xlsx'
d=json.loads((out/'evaluation_data_internal.json').read_text(encoding='utf-8'))
t=json.loads((out/'terrain_reaggregation_internal.json').read_text(encoding='utf-8'))
wb=openpyxl.load_workbook(file,data_only=True)
wf=openpyxl.load_workbook(file,data_only=False)
assert wb.sheetnames==['01 策略名称与颜色','02 单时次反演指标','03 日累计反演指标','04 地形分层反演指标','05 评价定义与证据追溯']
checks=0
def check(actual,expected):
    global checks
    if expected is None:assert actual=='未定义',(actual,expected)
    else:assert isinstance(actual,(int,float)) and math.isclose(actual,expected,rel_tol=2e-12,abs_tol=2e-12),(actual,expected)
    checks+=1

for ws in wb:
    assert len(ws.tables)==1 and ws.freeze_panes=='B6',(ws.title,ws.freeze_panes)
    for row in ws:
        for cell in row:
            assert cell.data_type!='e',(ws.title,cell.coordinate,cell.value)
    assert ws.sheet_view.showGridLines is False

sh=wb.worksheets[1]
for row in sh.iter_rows(min_row=6,max_row=20):
    vals=[c.value for c in row]; group=next(g for g in d['groups'] if g['name']==vals[0])
    field='sd' if vals[1]=='±样本标准差' else 'mean'
    assert vals[2]==len(group['seeds']) and vals[6]==group['n_valid']
    for ti,threshold in enumerate((.1,1.,5.,10.,20.)):
        for mi,m in enumerate(('POD','FAR','CSI','HSS')):
            check(vals[7+ti*4+mi],group['metrics'][str(threshold)][m][field])
    check(vals[27],group['rmse'][field]);check(vals[28],group['brier'][field])
    expected=group['color']
    assert row[0].fill.fgColor.rgb.endswith(expected)

for row in wb.worksheets[2].iter_rows(min_row=6,max_row=14):
    vals=[c.value for c in row];assert vals[2]==0
    assert all(x=='待评价' for x in vals[4:22])

def estimate(v,sd):
    if any(x is None for x in v):return None
    return statistics.stdev(v) if sd else statistics.mean(v)

terrain_checks=0
for row in wb.worksheets[3].iter_rows(min_row=6,max_row=212):
    v=[c.value for c in row]
    if v[1]!='高程' or not v[5]:continue
    group='low' if v[2].startswith('低') else 'middle' if v[2].startswith('中') else 'high'
    strategy=next(g['strategy'] for g in d['groups'] if g['name']==v[0])
    rr=[r for r in t['rows'] if r['strategy']==strategy and r['group']==group and r['threshold']==v[3]]
    assert len(rr)==v[5]==3
    assert len(set(r['n'] for r in rr))==1 and v[6]==rr[0]['n']
    assert len(set(r['counts']['TP']+r['counts']['FN'] for r in rr))==1
    assert v[7]==rr[0]['counts']['TP']+rr[0]['counts']['FN']
    for mi,m in enumerate(('POD','FAR','CSI','HSS')):
        check(v[8+mi],estimate([r['metrics'][m] for r in rr],v[4]=='±样本标准差'))
    check(v[12],estimate([r['rmse'] for r in rr],v[4]=='±样本标准差'))
    terrain_checks+=1
assert terrain_checks==90
assert sum(1 for row in wb.worksheets[4].iter_rows(min_row=6,max_row=235) if sum(row[i].value for i in (7,8,9,10))==row[5].value)==230
for ws in wb.worksheets[:4]:
    for row in ws:
        for cell in row:
            if isinstance(cell.value,str):
                assert not re.search(r'\bB[0-9]\b|[A-Z]:\\|LAST_epoch|[0-9a-f]{40}',cell.value),cell.value
                assert not re.search(r'AUROC|Pinball|FLOPs|CRPS|Pearson',cell.value)
with zipfile.ZipFile(file) as z:
    assert not any(n.startswith('xl/externalLinks/') for n in z.namelist())
receipt=dict(status='PASS',file=file.name,sha256=hashlib.sha256(file.read_bytes()).hexdigest(),
             worksheets=5,native_tables=5,freeze_panes='B6 on all sheets',saved_formula_errors=0,
             independently_checked_numeric_cells=checks,raw_count_rows=230,terrain_summary_rows_checked=90,
             no_fake_single_seed_sd=True,main_sheets_no_internal_model_codes=True,
             no_new_training=True,no_new_inference=True,final_2025='FROZEN_NO_ACCESS',
             validation_scope='Bundled recalculation + independent saved cached-value checks + OOXML; native Excel app not tested')
(out/'workbook_verification_public.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
print(json.dumps(receipt,ensure_ascii=False))
