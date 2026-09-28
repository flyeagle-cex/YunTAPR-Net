"""Read existing Stage-0 evidence, write a NEW decision package only.

No raw-data discovery/read, old task execution, mask generation or model work.
Run modes: collect, render, finalize. Every write is contained in a new run.
"""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import csv, hashlib, io, json, os, sys
import importlib.metadata as md
import numpy as np
import netCDF4

ROOT = Path(r'F:\pytorch\Research\outputs')
PYTHON = Path(r'F:\pytorch\Research\.venv\Scripts\python.exe')
REQUEST = Path(r'C:\Users\chenerxiao\.codex\attachments\941e14c0-8939-4052-a477-98d4aac32de5\已粘贴的文本.txt')
RUNS = {
 'p0': ROOT/'stage0_p0_audit/run_20260927T161311_417313Z',
 'continuous_history': ROOT/'stage0_continuous_engineering/run_20260928T031444_178129Z',
 'continuous': ROOT/'stage0_continuous_engineering/run_20260928T041855_828904Z',
 'thermo': ROOT/'stage0_gfs_thermo_compatibility/run_20260928T084334_575397Z',
 'provenance': ROOT/'stage0_gfs_provenance_vintage_resolution/run_20260928T092552_449937Z',
 'spatial': ROOT/'stage0_spatial_static_closeout/run_20260928T095818_821492Z',
 'freeze': ROOT/'stage0_spatial_decision_update/run_20260928T102636_513428Z',
 'himawari': Path(r'F:\pytorch\Research\stage0_himawari\outputs\202407\resume_20260927T104625_772423Z'),
 'himawari_failed_history': Path(r'F:\pytorch\Research\stage0_himawari\outputs\202407\run_20260927T102645_638388Z'),
}
REPORTS = {
 'p0':'README_STAGE0_P0_AUDIT.md', 'continuous_history':'FINAL_CONTINUOUS_ENGINEERING_REPORT.md',
 'continuous':'FINAL_CONTINUOUS_ENGINEERING_REPORT.md', 'thermo':'FINAL_GFS_THERMO_COMPATIBILITY_REPORT.md',
 'provenance':'FINAL_GFS_PROVENANCE_VINTAGE_REPORT.md', 'spatial':'FINAL_STAGE0_SPATIAL_STATIC_REPORT.md',
 'freeze':'STAGE0_SPATIAL_DECISION_FREEZE_REPORT.md',
 'himawari':'reports/README_HIMAWARI_PREPROCESS_202407_v2.md',
 'himawari_failed_history':'reports/README_HIMAWARI_PREPROCESS_202407.md',
}
ENDING = ('Stage-0 final gate package complete.\n'
 'Engineering completion and scientific readiness were evaluated separately.\n'
 'No unresolved scientific decision was auto-frozen.\n'
 'No Stage-1/B0 execution was started automatically.\n'
 'All prior Stage-0 evidence runs remain unchanged.')
OUT = None
protected = {}
refs = []
checks = []
manifests = {}

def utc(): return datetime.now(timezone.utc).isoformat()
def sha(data): return hashlib.sha256(data).hexdigest()
def file_sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024), b''): h.update(b)
 return h.hexdigest()
def write(rel, data):
 p=(OUT/rel).resolve()
 if not p.is_relative_to(OUT.resolve()): raise ValueError('Output escape')
 p.parent.mkdir(parents=True, exist_ok=True)
 p.write_text(data, encoding='utf-8', newline='\n')
def wjson(rel, data): write(rel,json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def table(rel, rows, fields=None):
 fields=fields or list(rows[0])
 buf=io.StringIO(newline='');w=csv.DictWriter(buf,fieldnames=fields);w.writeheader();w.writerows(rows)
 write(rel,buf.getvalue())
def protect(p):
 p=Path(p).resolve()
 if str(p) not in protected:
  s=p.stat();protected[str(p)]={'size_bytes':s.st_size,'mtime_ns':s.st_mtime_ns,'sha256':file_sha(p)}
 return protected[str(p)]
def read(key, rel):
 p=RUNS[key]/rel;protect(p);return p.read_text(encoding='utf-8-sig')
def jread(key,rel):return json.loads(read(key,rel))
def cread(key,rel):return list(csv.DictReader(io.StringIO(read(key,rel))))
def evidence(eid, key, rel, section, conclusion):
 p=RUNS[key]/rel if key in RUNS else Path(key)/rel
 a=protect(p)
 refs.append(dict(evidence_id=eid,conclusion=conclusion,source_run=str(RUNS.get(key,Path(key))),source_file=str(p),field_or_section=section,sha256=a['sha256']))
 return eid
def check(item, expected, observed, source):
 checks.append(dict(item=item,expected=json.dumps(expected,ensure_ascii=False),observed=json.dumps(observed,ensure_ascii=False),status='CONSISTENT' if expected==observed else 'EVIDENCE_CONFLICT_RESEARCHER_REVIEW',evidence_source=source))
def coord_hash(a):
 a=np.asarray(a,dtype='<f8').copy();a[a==0]=0
 return sha(str(a.shape).encode('ascii')+a.tobytes(order='C'))
def mdtable(rows, cols):
 esc=lambda x:str(x).replace('|','/').replace('\n','<br>')
 return '| '+' | '.join(cols)+' |\n| '+' | '.join(['---']*len(cols))+' |\n'+'\n'.join('| '+' | '.join(esc(r.get(c,'')) for c in cols)+' |' for r in rows)+'\n'

def collect():
 global OUT
 if Path(sys.executable).resolve()!=PYTHON.resolve(): raise RuntimeError('Wrong interpreter')
 stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
 OUT=ROOT/'stage0_final_gate_package'/('run_'+stamp);OUT.mkdir(parents=True,exist_ok=False)
 write('PROVENANCE/researcher_final_gate_request.txt',REQUEST.read_text(encoding='utf-8-sig'));protect(REQUEST)
 write('src/build_gate.py',Path(__file__).read_text(encoding='utf-8-sig'))
 wjson('logs/environment.json',{'utc':utc(),'python':sys.executable,'versions':{n:md.version(n) for n in ['numpy','netCDF4','pandas','pyarrow','pytest']},'dependencies_installed_or_upgraded':False})
 statuses={};registry=[]
 for key,d in RUNS.items():
  statusrel=('reports/final_dry_run_status_202407_v2.json' if key=='himawari' else
    'final_continuous_engineering_status.json' if key=='continuous_history' else
    'reports/output_status_202407.csv' if key=='himawari_failed_history' else 'audit_final_status.json')
  if key=='himawari_failed_history':
   content=read(key,statusrel);s={'status':'DRY_RUN_FAILED','engineering_status':'FAILED_DEPENDENCY_GATE','underlying_output_status':'BLOCKED_NOT_GENERATED'}
   assert 'BLOCKED_NOT_GENERATED' in content
  else:s=jread(key,statusrel)
  statuses[key]=s;report=read(key,REPORTS[key]);mp=d/'output_manifest.csv'
  manifests[key]=cread(key,'output_manifest.csv') if mp.exists() else []
  eng=s.get('engineering_status',s.get('engineering_execution',s.get('engineering_execution','UNKNOWN')))
  if key=='himawari':eng='PASS' if s['status']=='READY_FOR_RESEARCHER_REVIEW' and s['automated_tests_passed']==22 and s['dummy_pass_count']==50 else 'UNKNOWN'
  registry.append(dict(run_type=d.parent.name if key not in ['himawari','himawari_failed_history'] else 'himawari_stage0_202407',run_path=str(d),timestamp=s.get('finished_utc',s.get('completed_utc',s.get('ended_utc',d.name))),engineering_status=eng,researcher_review_status=s.get('researcher_review_status','NEEDS_REVIEW' if key!='freeze' else 'APPROVED_SPECIFIED_SPATIAL_SCOPE_ONLY'),fingerprint=protect(d/statusrel)['sha256'],key_report=str(d/REPORTS[key]),audit_final_status_path=str(d/statusrel),manifest_path=str(mp) if mp.exists() else '',status='HISTORICAL_PRESERVED' if key.endswith('history') else 'CURRENT_EVIDENCE_WITH_SCOPE_LIMITS',notes='No output_manifest exists; targeted status/report hashes recorded here.' if not mp.exists() else 'Original manifest read; key evidence hash/size checked, not a raw scan.'))
  evidence('RUN_'+key,key,statusrel,'final status','Run engineering/research status; historical failures retained')
  evidence('REPORT_'+key,key,REPORTS[key],'full report','Original report read in full; historical scope retained')
 p0=statuses['p0'];th=statuses['thermo'];pr=statuses['provenance'];sp=statuses['spatial'];fr=statuses['freeze'];hi=statuses['himawari']
 grid=cread('p0','IMERG/imerg_grid_audit.csv')
 ggrid=cread('continuous','GFS/gfs_grid_audit.csv')
 gs=jread('continuous','GFS/gfs_inventory_summary.json')
 pair=cread('thermo','COMPATIBILITY/main_thermo_pairing.csv')
 coverage=cread('thermo','COMPATIBILITY/research_period_thermo_coverage.csv')
 matrix=cread('continuous','CROSS_SOURCE/research_period_data_matrix.csv')
 october=jread('continuous','CROSS_SOURCE/imerg_202510_targeted_presence.json')
 freeze=jread('freeze','freeze_registry.json')
 dem=jread('spatial','DEM/dem_audit_summary.json')
 read('continuous','docs/DECISION_LOG_STAGE0.md')
 schema=read('continuous','schemas/sample_index_schema.md')
 read('freeze','docs/RESEARCHER_APPROVAL_RECORD.md')
 read('freeze','PROVENANCE/generator_script_hashes.json')
 read('himawari','reports/final_dry_run_status_202407.json')
 read('himawari','audit/final_artifact_validation_202407.json')
 for eid,key,rel,sec,conclusion in [
  ('IMERG_GRID','p0','IMERG/imerg_grid_audit.csv','all 2465 rows; lat/lon count/hash/direction','Actual target grid exact coordinates'),
  ('GFS_GRID','continuous','GFS/gfs_grid_audit.csv','all 24388 rows','53x57 metadata audit only'),
  ('GFS_INVENTORY','continuous','GFS/gfs_inventory_summary.json','file_count/read_success','24388 main files'),
  ('THERMO_PAIR','thermo','COMPATIBILITY/main_thermo_pairing.csv','pair_status','12960 MATCHED_COMPLETE; MAIN_ONLY distinct'),
  ('THERMO_RESEARCH','thermo','COMPATIBILITY/research_period_thermo_coverage.csv','24 rows / complete_T_RH_pairs','8820 structural metadata complete candidate'),
  ('RESEARCH_MATRIX','continuous','CROSS_SOURCE/research_period_data_matrix.csv','2023-03 to 2025-10 / source status','Himawari only July audited; external NOT_AUDITED'),
  ('OCTOBER','continuous','CROSS_SOURCE/imerg_202510_targeted_presence.json','count/status','2025-10 IMERG MISSING'),
  ('CONVENTIONS','continuous','docs/DECISION_LOG_STAGE0.md','Frozen and provisional sections; later spatial update supersedes mask history','Existing rules, distinct unknowns'),
  ('SCHEMA','continuous','schemas/sample_index_schema.md','all fields','Provisional schema; no instantiated sample database'),
  ('FREEZE','freeze','freeze_registry.json','boundary/mask/dem/not_yet_frozen','Approved spatial conventions and immutable fingerprints'),
  ('SPATIAL_APPROVAL','freeze','docs/RESEARCHER_APPROVAL_RECORD.md','explicit approval scope','Researcher approved specified spatial rules only'),
  ('GENERATOR_HASHES','freeze','PROVENANCE/generator_script_hashes.json','registered generator scripts','Existing generation provenance; not rerun'),
  ('DEM_COVERAGE','spatial','DEM/dem_audit_summary.json','SRTM.yunnan_coverage / invalid cells','237 SRTM tiles; FULL frozen-polygon coverage'),
 ]:evidence(eid,key,rel,sec,conclusion)
 evidence('CURRENT_REQUEST',str(REQUEST.parent),REQUEST.name,'sections 1,6,9–18,24','Researcher-confirmed facts, approved rules, stage dependencies and undecided items')
 check('IMERG_inventory',[2465,'2019-01-01','2025-09-30'],[p0['imerg_files'],p0['imerg_first_date'],p0['imerg_last_date']],'RUN_p0')
 check('IMERG_grid',[2465,['130'],['140'],['ascending']],[len(grid),sorted(set(r['lat_count'] for r in grid)),sorted(set(r['lon_count'] for r in grid)),sorted(set(r['lat_direction'] for r in grid))],'IMERG_GRID')
 check('GFS_inventory',24388,gs['file_count'],'GFS_INVENTORY')
 check('GFS_grid',[24388,['53'],['57']],[len(ggrid),sorted(set(r['lat_count'] for r in ggrid)),sorted(set(r['lon_count'] for r in ggrid))],'GFS_GRID')
 check('thermo_inventory',12960,th['thermo_files'],'RUN_thermo')
 counts=Counter(r['pair_status'] for r in pair)
 check('thermo_pairing',{'MATCHED_COMPLETE':12960,'MAIN_ONLY':11428},dict(counts),'THERMO_PAIR')
 actual=[len(coverage),sum(int(r['expected_main_forecast_pairs']) for r in coverage),sum(int(r['complete_T_RH_pairs']) for r in coverage)]
 check('thermo_research',[24,8820,8820],actual,'THERMO_RESEARCH')
 check('thermo_research_cross_run',[8820,8820,8820,8820],[th['research_expected_pairs'],th['research_complete_pairs'],pr['research_period_t_rh_expected_pairs'],pr['research_period_t_rh_complete_pairs']],'RUN_thermo;RUN_provenance')
 check('IMERG_202510',['MISSING',0], [october['status'],october['count']],'OCTOBER')
 check('freeze_id','YunTAPR_STAGE0_SPATIAL_v1_run_20260928T102636_513428Z',freeze['freeze_id'],'FREEZE')
 check('freeze_registry_hash',fr['frozen_registry_sha256'],protect(RUNS['freeze']/'freeze_registry.json')['sha256'],'RUN_freeze;FREEZE')
 for name,a in freeze['artifacts'].items():
  p=RUNS['freeze']/a['relative_path'];s=protect(p)
  check('frozen_artifact_'+name,[a['size_bytes'],a['sha256']],[s['size_bytes'],s['sha256']],'FREEZE:'+name)
 boundary=json.loads((RUNS['freeze']/freeze['artifacts']['boundary']['relative_path']).read_text(encoding='utf-8-sig'))
 feature=boundary['features'][0] if boundary.get('type')=='FeatureCollection' else boundary
 ident={k:feature['properties'].get(k) for k in ['NAME_1','GID_1','HASC_1','ISO_1','ENGTYPE_1']}
 check('boundary_identity',{'NAME_1':'Yunnan','GID_1':'CHN.30_1','HASC_1':'CN.YN','ISO_1':'CN-YN','ENGTYPE_1':'Province'},ident,'FREEZE:boundary')
 check('geometry_hash',freeze['boundary']['geometry_sha256'],sha(json.dumps(feature['geometry'],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')),'FREEZE:boundary.geometry')
 maskpath=RUNS['freeze']/freeze['artifacts']['primary_mask']['relative_path']
 with netCDF4.Dataset(str(maskpath),'r') as ds:
  var=next(v for v in ds.variables.values() if v.dimensions==('lat','lon'))
  mask=np.asarray(var[:]);lat=np.asarray(ds.variables['lat'][:]);lon=np.asarray(ds.variables['lon'][:]);dims=list(var.dimensions)
  maskobs={'variable':var.name,'shape':list(mask.shape),'true_cells':int(mask.astype(bool).sum()),'false_cells':int((~mask.astype(bool)).sum()),'dimensions':dims,'lat_ascending':bool(np.all(np.diff(lat)>0)),'lat_hash':coord_hash(lat),'lon_hash':coord_hash(lon)}
 with np.load(RUNS['freeze']/freeze['artifacts']['coordinates']['relative_path'],allow_pickle=False) as a:
  check('coordinate_anchor_exact',True,bool(np.array_equal(lat,a['lat']) and np.array_equal(lon,a['lon'])),'FREEZE:coordinates')
 check('mask_shape_count_dimensions',[[130,140],3430,14770,['lat','lon'],True],[maskobs['shape'],maskobs['true_cells'],maskobs['false_cells'],dims,maskobs['lat_ascending']],'FREEZE:primary_mask')
 for name in ['lat_hash','lon_hash']:
  check('mask_'+name,freeze['mask'][name],maskobs[name],'FREEZE:mask')
  check('p0_mask_'+name,[freeze['mask'][name]],sorted(set(r[name] for r in grid)),'IMERG_GRID;FREEZE')
 check('intersection_role',False,freeze['intersection']['is_primary_evaluation_mask'],'FREEZE:intersection')
 check('SRTM_coverage',[237,'FULL',0],[dem['SRTM']['tile_count'],dem['SRTM']['yunnan_coverage'],dem['SRTM']['yunnan_invalid_touched_cells']],'DEM_COVERAGE')
 check('Himawari_dryrun_p0',[4390,4390,50,22],[hi['read_success'],p0['himawari_parsed'],hi['dummy_pass_count'],hi['automated_tests_passed']],'RUN_himawari;RUN_p0')
 check('Himawari_latency_tails',44,p0['latency_tail_review_files'],'RUN_p0')
 # Check only referenced output files, against the immutable old manifest where available.
 for key,d in RUNS.items():
  for row in manifests[key]:
   p=(d/row['relative_path']).resolve()
   if not p.is_relative_to(d.resolve()):raise RuntimeError('Manifest path escape')
   old=protected.get(str(p))
   if not old:continue
   expected_hash=row.get('sha256') or row.get('sha256_if_reasonable')
   if expected_hash and len(expected_hash)==64:check('manifest_sha:'+key+':'+row['relative_path'],expected_hash,old['sha256'],str(d/'output_manifest.csv'))
   size=row.get('size_bytes') or row.get('bytes')
   if size:check('manifest_size:'+key+':'+row['relative_path'],int(size),old['size_bytes'],str(d/'output_manifest.csv'))
 table('EVIDENCE/evidence_run_registry.csv',registry)
 table('EVIDENCE/evidence_fingerprint_check.csv',checks)
 table('evidence_registry.csv',refs)
 wjson('EVIDENCE/collected_facts.json',dict(statuses=statuses,freeze=freeze,mask_observed=maskobs,dem=dem,pair_counts=dict(counts),research_coverage=actual,imerg_202510=october,source_month_status_counts={k:dict(Counter(r[k] for r in matrix)) for k in ['Himawari_available','external_validation_available_if_known']},fingerprint_conflicts=[r for r in checks if r['status']!='CONSISTENT']))
 wjson('logs/input_protection_before.json',protected)
 wjson('logs/collection_log.json',{'completed_utc':utc(),'raw_files_opened':0,'raw_directories_scanned':0,'old_run_write_operations':0,'old_scripts_executed':0,'mask_generation_executed':False,'discovery_scope':str(ROOT),'explicit_himawari_exception':str(RUNS['himawari'].parent),'discovery_note':'Initial rg reported access denied for old freeze tests/tmp; no attempt to alter ACL. Targeted formal evidence remains accessible. No completeness claim for that unused test directory.','run_count':len(registry),'protected_file_count':len(protected),'fingerprint_checks':len(checks),'fingerprint_conflicts':sum(r['status']!='CONSISTENT' for r in checks)})
 print(json.dumps({'run':str(OUT),'checks':len(checks),'conflicts':[r for r in checks if r['status']!='CONSISTENT'],'mask':maskobs},ensure_ascii=False))

if __name__=='__main__':
 mode=sys.argv[1]
 if mode=='collect':collect()
 else:
  OUT=Path(sys.argv[2]).resolve()
  if not OUT.is_relative_to((ROOT/'stage0_final_gate_package').resolve()):raise ValueError('Wrong output root')
  from gate_package import render,finalize
  {'render':render,'finalize':finalize}[mode](sys.modules[__name__])
