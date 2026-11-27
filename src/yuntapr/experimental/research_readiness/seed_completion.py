"""Seed completion: B2/B5/B6 formal training at seeds 2030 and 2031.

Nothing here grants authorization. The frozen seed2029 executors
(``b2_runner.execute`` and ``static_training.worker``) are replicated and
parameterized by seed here; they are imported read-only and never modified, so
the historical evidence chain stays byte-identical. No real training is run by
preparation or dry-run, and the controller never retries, resumes or replays.
"""
from pathlib import Path
from datetime import datetime, timezone
import gc,json,os,random,shutil,sqlite3,subprocess,sys,time
import numpy as np
import torch
from yuntapr.training.phase_a_protocol import state_digest,lr_for_update
from yuntapr.experimental.phase_b_v2_runner_candidate.optimizer import new_adamw,clip_and_check,check_finite
from yuntapr.experimental.core_innovation.stage2 import OFFSETS
from yuntapr.experimental.core_innovation.stage3.planning import digest
from yuntapr.experimental.core_innovation.stage3.metered_io import SourceMeter,path_key
from yuntapr.experimental.core_innovation.stage4.data import PopulationPlan,BatchReader,read,sha
from yuntapr.experimental.core_innovation.stage4.engine import (
    FormalDecision,PairedExecutor,cpu_tree,epoch_order,resources,write)
from yuntapr.experimental.core_innovation.stage4.evaluation import Evaluation,paired_difference
from yuntapr.experimental.core_innovation.stage4.launch import PassReader,ReaderFactory
from .b2 import STEM_RULE,INPUT_OFFSET_MINUTES,fresh_b2,forward_b2
from .b2_runner import B2Ledger,difference
from .multiseed import (BatchTail,code_hashes as _inherited_code_hashes,endpoint,load_inherited,
                        metric_values,worker_creation_flags)
from .static_training import model_factory,unpack
from .tail_diagnostics import TailDiagnostics

VERSION='v1'
SCOPE='SEED_COMPLETION_B2_B5_B6_2030_2031'
KIND='SEED_COMPLETION_FORMAL_TRAINING_PACKAGE'
ENTRY='tools/research_readiness/start_seed_completion.py'
TASKS=(('B2',2030),('B2',2031),('B5',2030),('B6',2030),('B5',2031),('B6',2031))
GIB=1024**3
WEATHER_SOURCE_BYTES=477571641012
WEATHER_SOURCE_FILES=142812
STATIC_SOURCE_BYTES={'B5':62828,'B6':312828}
STATIC_SOURCE_SHA256={'B5':'98d91515b8475f15343b931be0e14d8b005762987f6d4caeb69e9c9ce1d134b8',
                      'B6':'788572b1e82ba388d6ddcd6b1f8a987af818f44cdde9d5d613db5d35af5281bd'}
TERRAIN_RECEIPT_SHA256='180599379509dd5a49639feb1df9ca22ed97afd34d8e4d021c6eb4a24a0cd32d'
TERRAIN_RECEIPT_BYTES=31455
TERRAIN_ROOT=r'F:\pytorch\Research\YunTAPR_static_terrain_candidate_20261027_v1'
B2_PREPARATION={'path':r'D:\研究\极端降水预测\YunTAPR-B2-readiness-20261025\docs\research_readiness\.local\b2_preparation_20261025_v4.json',
                'sha256':'e399271726f429626223f271896db631f7499a41d51657f0629c1f97372afc9e','bytes':4720736}
B5B6_PREPARATION_NAME='b5_b6_corrected_start_preparation_20261027.json'
B5B6_PREPARATION_SHA256='44697e29d50c127f24a0c36d5b043206109dcd149444d995aab0ab0cf9977776'
B5B6_PREPARATION_BYTES=733
B5B6_PREPARATION_PROPOSAL_SHA256='36fc5dfbbc94c5576442ab95691595a7d4c3a130f373363015b5db13db6b57f1'
EVIDENCE={
 'b3_b4_three_seed_completion':('docs/research_readiness/20261025/evidence/b3_b4_three_seed_completion.json',
                                'e101ebd17b267d4fc0d93b53afe0ab432ce3e7a54f226f9058eac54237eecde4'),
 'b5_b6_seed2029_completion':('docs/research_readiness/20261025/evidence/b5_b6_completion_and_paired_evidence.json',
                              'a2ca0b49ec59e16ce295f3f8533e10533aa9e2c44d2fe746838c1a381e8f5161'),
 'b2_seed2029_completion':('docs/research_readiness/20261025/evidence/b2_completion_and_paired_evidence.json',
                            '96738035c5e3f6b32ce4bf7e2a4f656313ea742ad53eb9ac38eb627f8dc8b3e1'),
 'b5_b6_terrain_production':('docs/research_readiness/20261025/evidence/b5_b6_terrain_production.json',
                             '75204e2d8fd0eb37e9a13012fb7c74c523f23ffe436ec5b0446e8c4d134ead03'),
 'b5_b6_cached_real_check':('docs/research_readiness/20261025/evidence/b5_b6_cached_real_check.json',
                            'f082131741918dc77afe6872fb62cf9c02897ceb09afa59eed8cd6fc0250f797'),
 'b5_b6_corrected_start_checks':('docs/research_readiness/20261025/evidence/b5_b6_corrected_start_checks.json',
                                 'cd3444883f981439e88b8913555551f5f928887c6b303909c5f10e312c476697')}
STATIC_TRAINING_REL='src/yuntapr/experimental/research_readiness/static_training.py'
BASELINE_DEV={
 2030:{'B2':(r'F:\pytorch\Research\YunTAPR_B3_B4_s2030_s2031_20261026_v1\B3_s2030\B3_development_09.json',
             '2e816d8806e0ff5dd581f6b0737f13ba353be29bbc8e5e08ef2034d852ed9f27',1881219),
       'B5':(r'F:\pytorch\Research\YunTAPR_B3_B4_recovery1_20261026_v1\B4_s2030\B4_development_09.json',
             'bc5ee14ea4f353df212e9aeaef53ec49c1e0d899142bea1632f9cd73400b23a0',1883210),
       'B6':(r'F:\pytorch\Research\YunTAPR_B3_B4_recovery1_20261026_v1\B4_s2030\B4_development_09.json',
             'bc5ee14ea4f353df212e9aeaef53ec49c1e0d899142bea1632f9cd73400b23a0',1883210)},
 2031:{'B2':(r'F:\pytorch\Research\YunTAPR_B3_B4_recovery1_20261026_v1\B3_s2031\B3_development_09.json',
             'e8a07756b513c920bc83b43d83ea3c4d2f2ea37099a64f0a870778cb5b7cf5d9',1880965),
       'B5':(r'F:\pytorch\Research\YunTAPR_B3_B4_recovery1_20261026_v1\B4_s2031\B4_development_09.json',
             '27f4827b1537c86b647dbdce68e030de60475c43ba5981fc502fe8c80ddf3a5f',1884153),
       'B6':(r'F:\pytorch\Research\YunTAPR_B3_B4_recovery1_20261026_v1\B4_s2031\B4_development_09.json',
             '27f4827b1537c86b647dbdce68e030de60475c43ba5981fc502fe8c80ddf3a5f',1884153)}}
PAIR_REFERENCE={2030:(r'F:\pytorch\Research\YunTAPR_B3_B4_recovery1_20261026_v1\B4_s2030',
                     '31eea2b5cdd6b22b058369cc18c14ff146b602d4d2f7e06c409ffc52953fc5fb',
                     '3cad8775b2ac64057a1c5a88f9301cefa008b975e821396b4a1995dab502545d'),
                2031:(r'F:\pytorch\Research\YunTAPR_B3_B4_recovery1_20261026_v1\B4_s2031',
                     'd50ba4e4c248435d36927f5747cec41e85b8e0c9dd6bbec9f8913895ac9e9b95',
                     '1d10a8057e6f69f721f29ce32cab8801cbc23f61ef2fd07324be1deaa18ae26c')}
SLOT=OFFSETS.index(INPUT_OFFSET_MINUTES)
B2_SCOPES={'Train':{'file_count':7918,'bytes_per_pass':26424262556,
                    'source_manifest_sha256':'f0c0a9188e771bfbba7c1e8a8ffdbfabd2d4e927bd1428d353b290be236a13dc'},
           'Development':{'file_count':7950,'bytes_per_pass':26639253112,
                          'source_manifest_sha256':'65e8b3754775ece7bbf60db0ca2b5320638c193fe20a9f21ee49828272514060'}}

def _comparison_baselines():
    result={}
    for seed in (2030,2031):
        entry={}
        for kind,model in (('B2','B3'),('B5','B4'),('B6','B4')):
            path,value,size=BASELINE_DEV[seed][kind]
            entry[kind]=dict(model=model,role='Development',endpoint='FIXED_EPOCH_9_LAST',
                             path=path,sha256=value,bytes=size)
        result[str(seed)]=entry
    return result

BUDGET=dict(version=VERSION,models=6,epochs=9,updates_per_epoch=480,updates_per_task=4320,
    total_updates=25920,weather_source_bytes_per_task=WEATHER_SOURCE_BYTES,
    weather_source_files_per_task=WEATHER_SOURCE_FILES,
    static_source_bytes_per_model=dict(STATIC_SOURCE_BYTES),static_source_files_per_model=1,
    source_bytes_per_task={f'{k}_s{s}':WEATHER_SOURCE_BYTES+STATIC_SOURCE_BYTES.get(k,0) for k,s in TASKS},
    source_files_per_task={f'{k}_s{s}':WEATHER_SOURCE_FILES+(1 if k in STATIC_SOURCE_BYTES else 0) for k,s in TASKS},
    total_source_bytes=2865430597384,total_source_files=856876,
    max_task_seconds=21600,task_wall_seconds={'B2':21600,'B5':21600,'B6':21600},
    max_package_seconds=129600,replay_allowance=0,additional_retry_allowance=0,
    initial_free_bytes=48*GIB,minimum_task_free_bytes=24*GIB,scopes=B2_SCOPES,
    comparison_baselines=_comparison_baselines())

def code_hashes(root):
    """Bind executable dependencies (new skeleton included) for drift checks."""
    root=Path(root);result=_inherited_code_hashes(root)
    for name in (ENTRY,'src/yuntapr/experimental/research_readiness/seed_completion.py',
                 'src/yuntapr/experimental/research_readiness/b2.py',
                 'src/yuntapr/experimental/research_readiness/b2_runner.py',
                 'src/yuntapr/experimental/research_readiness/static_training.py',
                 'src/yuntapr/experimental/research_readiness/static_terrain.py',
                 'src/yuntapr/experimental/research_readiness/multiseed.py'):
        result[name]=sha(root/name)
    return result

def task_for(index):
    if type(index)!=int or not 0<=index<len(TASKS):raise PermissionError('Only the six approved seed-completion tasks exist')
    return TASKS[index]

def worker_environment(seed):
    return dict(os.environ,PYTHONHASHSEED=str(seed),CUBLAS_WORKSPACE_CONFIG=':4096:8',
                OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONUTF8='1')

def worker_command(root,proposal,private,approval,index,*,worker_python=None):
    return [str(worker_python or sys.executable),'-B',str(Path(root)/ENTRY),'worker',
            '--proposal',str(proposal),'--private-preparation',str(private),
            '--researcher-approval',str(approval),'--task-index',str(index)]

def validate_package_closure(totals,budget):
    if (totals.get('optimizer_updates')!=budget['total_updates']
            or totals.get('total_logical_source_bytes')!=budget['total_source_bytes']
            or totals.get('total_logical_source_files')!=budget['total_source_files']):
        raise RuntimeError('Seed-completion package exact closure differs')
    return True

def validate_budget(budget):
    keys={f'{k}_s{s}' for k,s in TASKS}
    if set(budget['source_bytes_per_task'])!=keys or set(budget['source_files_per_task'])!=keys:raise ValueError('Six-task source map differs')
    for kind,seed in TASKS:
        key=f'{kind}_s{seed}'
        if budget['source_bytes_per_task'][key]!=WEATHER_SOURCE_BYTES+STATIC_SOURCE_BYTES.get(kind,0):raise ValueError('Per-task byte arithmetic differs')
        if budget['source_files_per_task'][key]!=WEATHER_SOURCE_FILES+(1 if kind in STATIC_SOURCE_BYTES else 0):raise ValueError('Per-task file arithmetic differs')
    if sum(budget['source_bytes_per_task'].values())!=budget['total_source_bytes']:raise ValueError('Total byte arithmetic differs')
    if sum(budget['source_files_per_task'].values())!=budget['total_source_files']:raise ValueError('Total file arithmetic differs')
    if (budget['total_updates']!=25920 or budget['total_source_bytes']!=2865430597384
            or budget['total_source_files']!=856876 or budget['max_package_seconds']!=129600
            or budget['replay_allowance']!=0 or budget['additional_retry_allowance']!=0
            or budget['max_task_seconds']!=21600 or any(v!=21600 for v in budget['task_wall_seconds'].values())
            or budget['initial_free_bytes']!=48*GIB or budget['minimum_task_free_bytes']!=24*GIB):
        raise ValueError('Package cap/storage arithmetic differs')
    if set(budget['comparison_baselines'])!={'2030','2031'}:raise ValueError('Exactly two independent seeds require baselines')
    for seed in ('2030','2031'):
        for kind,model in (('B2','B3'),('B5','B4'),('B6','B4')):
            entry=budget['comparison_baselines'][seed][kind]
            if entry['model']!=model or entry['endpoint']!='FIXED_EPOCH_9_LAST' or len(entry['sha256'])!=64:raise ValueError('Per-seed comparison baseline differs')
    return True

def verify_proposal_digest(proposal):
    expected=proposal.get('proposal_sha256')
    if not isinstance(expected,str) or len(expected)!=64:raise ValueError('Proposal digest missing')
    if digest({k:v for k,v in proposal.items() if k!='proposal_sha256'})!=expected:raise ValueError('Proposal digest differs')
    return expected

def validate_output_root(output_root):
    out=Path(output_root)
    if not out.is_absolute():raise PermissionError('Absolute fresh output root required')
    if out.exists():raise PermissionError('Seed-completion output root already exists; no replay')
    if not out.parent.is_dir():raise PermissionError('Output root parent must already exist')
    free=shutil.disk_usage(out.parent).free
    if free<BUDGET['initial_free_bytes']:raise RuntimeError('Reserve >=48GiB before the six-model seed-completion package')
    return out,free

def check_code_hashes(root,proposal):
    if code_hashes(root)!=proposal['code_sha256']:raise ValueError('Reviewed seed-completion code changed')
    return True

def check_input_pins(proposal):
    for name,pin in proposal['input_pins'].items():
        path=Path(pin['path'])
        if not path.is_file():raise ValueError('Pinned input missing: '+name)
        if pin.get('bytes') is not None and path.stat().st_size!=pin['bytes']:raise ValueError('Pinned input size changed: '+name)
        if pin.get('sha256') is not None and sha(path)!=pin['sha256']:raise ValueError('Pinned input hash changed: '+name)
    return True

def validate_approval(approval,proposal,private,commit):
    keys={'approved_by_researcher','decision_id','code_commit','proposal_sha256',
          'tasks','budget','scientific_choices','output_root'}
    if set(approval)!=keys:raise PermissionError('Approval must contain exactly the reviewed keys')
    if approval['approved_by_researcher'] is not True:raise PermissionError('Explicit researcher approval required')
    if not isinstance(approval['decision_id'],str) or not approval['decision_id'].strip():raise PermissionError('Explicit researcher decision identifier required')
    expected=dict(code_commit=commit,proposal_sha256=proposal['proposal_sha256'],tasks=proposal['tasks'],
                  budget=proposal['budget'],scientific_choices=proposal['scientific_choices'],
                  output_root=private['output_root'])
    if any(approval[k]!=v for k,v in expected.items()):raise PermissionError('Seed-completion approval does not match the reviewed package')

def _pin(path,*,sha256=None,size=None):
    path=Path(path)
    return dict(path=str(path),sha256=sha(path) if sha256 is None else sha256,
                bytes=path.stat().st_size if size is None else size)

def _read_evidence(root,name):
    relative,value=EVIDENCE[name];path=Path(root)/relative
    if not path.is_file() or sha(path)!=value:raise ValueError('Inherited evidence changed: '+name)
    return path,read(path)

def _validate_terrain(terrain,public_terrain):
    terrain,public_terrain=Path(terrain),Path(public_terrain)
    receipt_path=terrain/'production_receipt.json'
    if not receipt_path.is_file() or sha(receipt_path)!=TERRAIN_RECEIPT_SHA256:raise ValueError('Terrain production receipt changed')
    if receipt_path.stat().st_size!=TERRAIN_RECEIPT_BYTES:raise ValueError('Terrain production receipt size changed')
    public=read(public_terrain)
    if public['status']!='COMPLETE_CANDIDATE_DEM_PRODUCTION_NOT_A_TRAINING_GRANT':raise ValueError('Terrain production receipt status differs')
    if public['artifacts_sha256']['production_receipt.json']!=TERRAIN_RECEIPT_SHA256:raise ValueError('Public terrain production evidence differs')
    receipt=read(receipt_path)
    if receipt['status']!=public['status']:raise ValueError('Terrain status binding differs')
    if (receipt['grid_sha256'],receipt['region_sha256'],receipt['aggregation_rule'],receipt['release_version'],
            receipt['vertical_datum'])!=(public['grid_sha256'],public['region_sha256'],public['aggregation_rule'],
                                          public['release_version'],public['vertical_datum']):
        raise ValueError('Terrain identity/derivation binding differs')
    if receipt.get('raw_2025_reads',0)!=0 or public.get('raw_2025_reads',0)!=0:raise PermissionError('Terrain evidence reported 2025 access')
    for kind in ('B5','B6'):
        path=terrain/f'{kind}_static.npz'
        if not path.is_file() or path.stat().st_size!=STATIC_SOURCE_BYTES[kind] or sha(path)!=STATIC_SOURCE_SHA256[kind]:raise ValueError('Pinned static terrain package changed: '+kind)
        if public['artifacts_sha256'][f'{kind}_static.npz']!=STATIC_SOURCE_SHA256[kind]:raise ValueError('Public static terrain package binding differs: '+kind)
    return receipt,public

def _validate_inherited(root,inherited,terrain):
    inherited=Path(inherited)
    if not inherited.is_file() or sha(inherited)!=B2_PREPARATION['sha256'] or inherited.stat().st_size!=B2_PREPARATION['bytes']:raise ValueError('B2 seed2029 private preparation changed')
    wrapper,prepared=load_inherited(inherited)
    if prepared.get('status')!='PREPARED_WAITING_FINAL_START':raise ValueError('Inherited B2 preparation is not in the prepared state')
    if prepared.get('raw_source_opens_during_preparation')!=0 or prepared.get('optimizer_updates')!=0:raise ValueError('Inherited B2 preparation consumed sources or updates')
    b5b6_path=inherited.resolve().parent/B5B6_PREPARATION_NAME
    if not b5b6_path.is_file() or sha(b5b6_path)!=B5B6_PREPARATION_SHA256 or b5b6_path.stat().st_size!=B5B6_PREPARATION_BYTES:raise ValueError('B5/B6 seed2029 corrected preparation changed')
    b5b6=read(b5b6_path)
    if b5b6['proposal_sha256']!=B5B6_PREPARATION_PROPOSAL_SHA256:raise ValueError('B5/B6 seed2029 corrected proposal identity differs')
    if sha(Path(b5b6['inherited']))!=B2_PREPARATION['sha256']:raise ValueError('B5/B6 inheritance does not reference the pinned B2 preparation')
    if sha(Path(b5b6['terrain'])/'production_receipt.json')!=TERRAIN_RECEIPT_SHA256:raise ValueError('B5/B6 inheritance does not reference the pinned terrain')
    return inherited,b5b6_path,wrapper,prepared

def _validate_preparation_evidence(root,prepared):
    precheck_path,precheck=_read_evidence(root,'b5_b6_cached_real_check')
    if (precheck['status']!='PASS_ACTUAL_STATIC_CACHED_REAL_ZERO_UPDATES' or precheck['source_data']!=prepared['data']
            or precheck['static_sha256']!=STATIC_SOURCE_SHA256 or precheck.get('optimizer_updates')!=0
            or precheck.get('raw_2025_reads')!=0):raise ValueError('Actual static data/numerical-path precheck binding differs')
    certificate_path,certificate=_read_evidence(root,'b5_b6_corrected_start_checks')
    changed=certificate['after_real_check_changes']
    if (changed['current_module_sha256']!=sha(Path(root)/STATIC_TRAINING_REL)
            or changed['numeric_AST_nodes_unchanged']!=['StaticTrainingModel','unpack','model_factory']
            or certificate.get('raw_weather_reads')!=0 or certificate.get('optimizer_updates')!=0):
        raise ValueError('Corrected static training certificate binding differs')
    _,closeout=_read_evidence(root,'b3_b4_three_seed_completion')
    if closeout['sources']['s2029/B4/development_09.json']['sha256']!='5663b31c1789c95f07e385afdcd29ff3e7bf791c8b87fd0f6d51553e56d035a2':raise ValueError('Inherited three-seed B4 comparison baseline changed')
    _,b5b6=_read_evidence(root,'b5_b6_seed2029_completion')
    if (b5b6['status']!='VERIFIED_COMPLETE_STATIC_PAIR_TRAIN_AND_DEV' or b5b6['static_source_sha256']!=STATIC_SOURCE_SHA256
            or b5b6['budget_closure']['new_updates']!=8640 or b5b6['budget_closure']['new_source_bytes']!=955143657680
            or b5b6['budget_closure']['new_source_files']!=285626 or b5b6['budget_closure']['replay_updates']!=0
            or b5b6['budget_closure']['additional_retries']!=0):raise ValueError('B5/B6 seed2029 completion evidence differs')
    if [(t['model'],t['seed'],t['status'],t['optimizer_updates'],t['total_source_bytes']) for t in b5b6['tasks']]!=[
            ('B5',2029,'COMPLETE_TRAIN_AND_DEV_EVALUATION',4320,477571703840),
            ('B6',2029,'COMPLETE_TRAIN_AND_DEV_EVALUATION',4320,477571953840)]:raise ValueError('B5/B6 seed2029 task completion differs')
    _,b2=_read_evidence(root,'b2_seed2029_completion')
    if (b2['status']!='VERIFIED_COMPLETE_TRAIN_AND_DEV_EVALUATION' or b2['data']!=prepared['data']
            or b2['completion']['status']!='COMPLETE_TRAIN_AND_DEV_EVALUATION' or b2['completion']['updates']!=4320
            or b2['actual_io']!=dict(opened_files=142812,delivered_bytes=477571641012,reserved_bytes=477571641012,passes=18)
            or b2['train_orders_match_B3_all_nine_epochs'] is not True):raise ValueError('B2 seed2029 completion evidence differs')
    return precheck_path,certificate_path,closeout,b5b6,b2

def _seed_input_pins(root,inherited,b5b6_path,terrain,public_terrain):
    pins={'b2_seed2029_preparation':_pin(inherited,sha256=B2_PREPARATION['sha256'],size=B2_PREPARATION['bytes']),
          'b5_b6_seed2029_preparation':_pin(b5b6_path,sha256=B5B6_PREPARATION_SHA256,size=B5B6_PREPARATION_BYTES),
          'static_terrain_receipt':_pin(terrain/'production_receipt.json',sha256=TERRAIN_RECEIPT_SHA256,size=TERRAIN_RECEIPT_BYTES),
          'public_terrain_evidence':_pin(public_terrain,sha256=EVIDENCE['b5_b6_terrain_production'][1]),
          'b5_b6_zero_update_precheck':_pin(Path(root)/EVIDENCE['b5_b6_cached_real_check'][0],sha256=EVIDENCE['b5_b6_cached_real_check'][1]),
          'b5_b6_corrected_start_checks':_pin(Path(root)/EVIDENCE['b5_b6_corrected_start_checks'][0],sha256=EVIDENCE['b5_b6_corrected_start_checks'][1]),
          'b3_b4_three_seed_completion':_pin(Path(root)/EVIDENCE['b3_b4_three_seed_completion'][0],sha256=EVIDENCE['b3_b4_three_seed_completion'][1]),
          'b5_b6_seed2029_completion':_pin(Path(root)/EVIDENCE['b5_b6_seed2029_completion'][0],sha256=EVIDENCE['b5_b6_seed2029_completion'][1]),
          'b2_seed2029_completion':_pin(Path(root)/EVIDENCE['b2_seed2029_completion'][0],sha256=EVIDENCE['b2_seed2029_completion'][1])}
    for kind in ('B5','B6'):
        pins[f'static_terrain_{kind}']=_pin(terrain/f'{kind}_static.npz',sha256=STATIC_SOURCE_SHA256[kind],size=STATIC_SOURCE_BYTES[kind])
    for seed in (2030,2031):
        for kind in ('B2','B5','B6'):
            path,value,size=BASELINE_DEV[seed][kind]
            pins[f'baseline_{kind}_s{seed}']=_pin(path,sha256=value,size=size)
        pins[f'pair_reference_s{seed}_initial']=_pin(Path(PAIR_REFERENCE[seed][0])/'paired_initial_identity.json',sha256=PAIR_REFERENCE[seed][1])
        pins[f'pair_reference_s{seed}_orders']=_pin(Path(PAIR_REFERENCE[seed][0])/'paired_orders.json',sha256=PAIR_REFERENCE[seed][2])
    return pins

def _scientific_choices(receipt):
    return dict(b2_stem_rule=STEM_RULE,b2_input_offset_minutes=INPUT_OFFSET_MINUTES,b2_selected_slot=SLOT,
        b2_input_frames='LATEST_SLOT_OF_FROZEN_SIX_FRAME_BATCH',b2_loss='E0',
        b2_initialization_contract='FRESH_PAIRED_B3_REFERENCE_THEN_SQRT6_FANIN_INPUT_STEM',
        aggregation_rule=receipt['aggregation_rule'],
        footprint='ACTUAL_SP04_CENTRES_MIDPOINT_ENDPOINT_HALFSTEP_FLOAT32_EDGES',
        native_post_area='NEAREST_POST_VORONOI_CELLS_WGS84_ELLIPSOID_AREA',
        derivative_order='NATIVE_CENTRAL_GRADIENT_THEN_AREA_AVERAGE_EAST_NORTH_COMPONENTS_THEN_SLOPE_ASPECT',
        static_width=16,fusion='ADDITIVE_TARGET_SP04_FEATURE_RESIDUAL_ZERO_OUTPUT_INITIALIZATION',
        B5_channels=['elevation_m'],
        B6_channels=['elevation_m','east_gradient','north_gradient','slope_degrees','aspect_sin','aspect_cos'],
        flat_aspect='ZERO_NORMALIZED_VALUE_PLUS_SEPARATE_INVALID_INDICATOR',
        scaler_fit='2023_TRAIN_UNIQUE_SPATIAL_SUPPORT',source_release=receipt['release_version'],
        vertical_datum=receipt['vertical_datum'],epochs=9,batch=2,validation_batch=8,updates_per_epoch=480,
        endpoint='FIXED_EPOCH_9_LAST',
        seed_parameterization='MODEL_INIT_AND_EPOCH_ORDER_USE_TASK_SEED; PYTHONHASHSEED=str(seed); STATIC_ADAPTER_RNG=seed+10000',
        comparison_scope='DESCRIPTIVE_ONLY_SAME_SEED_B2_VS_B3_AND_B5_B6_VS_B4')

def prepare(root,*,output_root,inherited=None,terrain=None,public_terrain=None):
    """Build a public proposal and private preparation. Reads metadata only."""
    root=Path(root)
    if inherited is None or terrain is None or public_terrain is None:raise PermissionError('Explicit inherited/terrain/public-terrain paths required')
    inherited,terrain,public_terrain=Path(inherited).resolve(),Path(terrain).resolve(),Path(public_terrain).resolve()
    out,free=validate_output_root(output_root)
    inherited,b5b6_path,wrapper,prepared=_validate_inherited(root,inherited,terrain)
    receipt,public=_validate_terrain(terrain,public_terrain)
    precheck_path,certificate_path,closeout,b5b6,b2=_validate_preparation_evidence(root,prepared)
    pins=_seed_input_pins(root,inherited,b5b6_path,terrain,public_terrain)
    for name,pin in pins.items():
        if not Path(pin['path']).is_file():raise ValueError('Required pinned input missing: '+name)
        if pin.get('bytes') is not None and Path(pin['path']).stat().st_size!=pin['bytes']:raise ValueError('Required pinned input size differs: '+name)
        if pin.get('sha256') is not None and sha(pin['path'])!=pin['sha256']:raise ValueError('Required pinned input hash differs: '+name)
    proposal=dict(version=VERSION,scope=SCOPE,kind=KIND,entry=ENTRY,
        status='READY_WAITING_EXPLICIT_SEED_COMPLETION_APPROVAL',authorized=False,
        created_utc=datetime.now(timezone.utc).replace(second=0,microsecond=0).strftime('%Y-%m-%dT%H:%M:%SZ'),
        tasks=[dict(model=kind,seed=seed) for kind,seed in TASKS],data=prepared['data'],
        data_inputs=dict(stage3_run=prepared['private_inputs']['stage3_run'],
                         request=prepared['private_inputs']['request'],
                         mask_read_ledger=prepared['private_inputs']['mask_read_ledger'],
                         b2_preparation_sha256=B2_PREPARATION['sha256'],
                         b2_preparation_digest=prepared['preparation_sha256']),
        scientific_choices=_scientific_choices(receipt),budget=BUDGET,
        static_source_sha256=dict(STATIC_SOURCE_SHA256),static_source_bytes=dict(STATIC_SOURCE_BYTES),
        terrain_receipt_sha256=TERRAIN_RECEIPT_SHA256,grid_sha256=receipt['grid_sha256'],
        region_sha256=receipt['region_sha256'],scalers_sha256=digest(receipt['scalers']),
        baseline_E9_Dev_sha256={str(seed):{kind:BASELINE_DEV[seed][kind][1] for kind in ('B2','B5','B6')} for seed in (2030,2031)},
        pair_references={str(seed):dict(path=PAIR_REFERENCE[seed][0],paired_initial_identity_sha256=PAIR_REFERENCE[seed][1],
                                        paired_orders_sha256=PAIR_REFERENCE[seed][2]) for seed in (2030,2031)},
        input_pins=pins,storage_admission_free_bytes=free,raw_payload_opens_during_preparation=0,
        optimizer_updates=0,checkpoint_loads=0,raw_2025_reads=0,code_sha256=code_hashes(root))
    proposal['proposal_sha256']=digest(proposal)
    private=dict(version=VERSION,scope=SCOPE,proposal_sha256=proposal['proposal_sha256'],root=str(root.resolve()),
        output_root=str(out.resolve()),
        inherited=dict(b2_preparation=str(inherited.resolve()),b2_preparation_sha256=B2_PREPARATION['sha256'],
                       b5_b6_preparation=str(b5b6_path.resolve()),b5_b6_preparation_sha256=B5B6_PREPARATION_SHA256,
                       historical_pair=str(Path(wrapper['historical_b3_run']).resolve())),
        terrain=str(terrain.resolve()),public_terrain=str(public_terrain.resolve()),data=prepared['data'],
        prepared=dict(
            b2=dict(preparation_path=str(inherited.resolve()),preparation_sha256=prepared['preparation_sha256'],
                    data=prepared['data'],private_inputs=prepared['private_inputs'],
                    budget=dict(passes_per_role=prepared['budget']['passes_per_role'],
                                logical_source_read_instances=prepared['budget']['logical_source_read_instances'],
                                logical_raw_bytes=prepared['budget']['logical_raw_bytes'],
                                replay_allowance=prepared['budget']['replay_allowance']),
                    scopes={role:{key:scope[key] for key in ('file_count','bytes_per_pass','source_manifest_sha256')}
                            for role,scope in prepared['roles'].items()}),
            b5=dict(kind='B5',inherited=str(inherited.resolve()),terrain=str(terrain.resolve()),
                    static_source=str((terrain/'B5_static.npz').resolve()),static_source_sha256=STATIC_SOURCE_SHA256['B5'],
                    scalers_sha256=digest(receipt['scalers']),pair_reference=str(Path(PAIR_REFERENCE[2030][0]).resolve())),
            b6=dict(kind='B6',inherited=str(inherited.resolve()),terrain=str(terrain.resolve()),
                    static_source=str((terrain/'B6_static.npz').resolve()),static_source_sha256=STATIC_SOURCE_SHA256['B6'],
                    scalers_sha256=digest(receipt['scalers']),
                    pair_reference={str(seed):str(Path(PAIR_REFERENCE[seed][0]).resolve()) for seed in (2030,2031)})),
        evidence_pins=dict(precheck=precheck_path.name,certificate=certificate_path.name,
                           closeout=EVIDENCE['b3_b4_three_seed_completion'][0]),
        baseline_paths={str(seed):{kind:BASELINE_DEV[seed][kind][0] for kind in ('B2','B5','B6')} for seed in (2030,2031)},
        package_closure=dict(updates=BUDGET['total_updates'],bytes=BUDGET['total_source_bytes'],files=BUDGET['total_source_files']))
    return proposal,private

def checked(root,proposal,private,approval,commit):
    """Reload and re-verify proposal, private preparation, code and input pins."""
    root=Path(root);proposal,private,approval=map(read,(proposal,private,approval))
    expected=verify_proposal_digest(proposal);validate_approval(approval,proposal,private,commit)
    if private.get('proposal_sha256')!=expected:raise ValueError('Private seed-completion preparation differs')
    validate_budget(proposal['budget']);check_code_hashes(root,proposal);check_input_pins(proposal)
    if proposal['static_source_sha256']!=STATIC_SOURCE_SHA256:raise ValueError('Pinned static terrain hashes differ')
    if proposal['terrain_receipt_sha256']!=TERRAIN_RECEIPT_SHA256:raise ValueError('Pinned terrain receipt differs')
    if {str(seed):proposal['baseline_E9_Dev_sha256'][str(seed)] for seed in (2030,2031)}!={str(seed):{kind:BASELINE_DEV[seed][kind][1] for kind in ('B2','B5','B6')} for seed in (2030,2031)}:raise ValueError('Per-seed comparison baseline map differs')
    _,prepared=load_inherited(private['inherited']['b2_preparation'])
    if prepared['data']!=proposal['data'] or prepared['preparation_sha256']!=private['prepared']['b2']['preparation_sha256']:raise ValueError('Inherited B2 data/preparation drift')
    receipt_path=Path(private['terrain'])/'production_receipt.json'
    if sha(receipt_path)!=proposal['terrain_receipt_sha256']:raise ValueError('Terrain receipt changed after approval')
    if digest(read(receipt_path)['scalers'])!=proposal['scalers_sha256']:raise ValueError('Static scalers changed after approval')
    return proposal,private,approval

def _worker_deadline(started,budget):
    def check():
        if time.monotonic()-started>budget['max_task_seconds']:raise RuntimeError('Per-task 6h wall limit reached; no automatic replay')
    return check

def _write_folder_failure(folder,error):
    try:
        if Path(folder).is_dir() and not (Path(folder)/'failure.json').exists():
            write(Path(folder)/'failure.json',dict(status='STOP_NO_AUTOMATIC_REPLAY',error=type(error).__name__+': '+str(error)))
    except FileExistsError:pass

def _validate_b2_initialization(init,proposal,seed):
    expected=dict(stem_rule=proposal['scientific_choices']['b2_stem_rule'],
                  decision_status='FROZEN_BY_RESEARCHER_20261025',compatible_tensors=72,
                  selected_slot=proposal['scientific_choices']['b2_selected_slot'],
                  offset_before_analysis_minutes=proposal['scientific_choices']['b2_input_offset_minutes'],
                  new_formal_optimizer_updates=0)
    if any(init[k]!=v for k,v in expected.items()):raise ValueError('B2 reviewed initialization contract differs')
    if init['differing_input_kernels']!={'backbone.enc0.conv1.weight':{'B2':[48,7,3,3],'B3':[48,42,3,3]},
                                         'backbone.enc0.skip.weight':{'B2':[48,7,1,1],'B3':[48,42,1,1]}}:raise ValueError('B2 input-stem shapes differ')
    if init['b3_reference_sha256']!=read(Path(proposal['pair_references'][str(seed)]['path'])/'paired_initial_identity.json')['B3']['full_state_sha256']:raise ValueError('B2 reference B3 differs from the same-seed paired B3 initialization')

def _validate_b2_orders(proposal,seed,orders):
    reference=read(Path(proposal['pair_references'][str(seed)]['path'])/'paired_orders.json')
    for epoch,order in orders.items():
        item=reference[str(epoch)]
        if tuple(item['ids'])!=tuple(order) or item['sha256']!=digest(order):raise ValueError('B2 epoch order differs from the same-seed B3/B4 paired order')

def _worker_b2(root,proposal,private,approval,commit,index,kind,seed,started):
    _,prepared=load_inherited(private['inherited']['b2_preparation'])
    if prepared['data']!=proposal['data'] or prepared['preparation_sha256']!=private['prepared']['b2']['preparation_sha256']:raise ValueError('Inherited B2 preparation changed')
    plan=PopulationPlan(prepared['private_inputs']['stage3_run'],prepared['private_inputs']['request'],root=root)
    if plan.identity!=proposal['data']:raise ValueError('Pinned B2 population identity changed')
    for role,scope in prepared['roles'].items():
        expected=proposal['budget']['scopes'][role]
        if (digest(scope['files'])!=scope['source_manifest_sha256'] or set(scope['ids'])!=set(plan.ids(role))
                or any(scope[k]!=expected[k] for k in expected) or len(scope['files'])!=scope['file_count']
                or sum(item['bytes'] for item in scope['files'].values())!=scope['bytes_per_pass']):raise ValueError('B2 private read scope changed')
    if (9*sum(scope['bytes_per_pass'] for scope in prepared['roles'].values())!=proposal['budget']['weather_source_bytes_per_task']
            or 9*sum(scope['file_count'] for scope in prepared['roles'].values())!=proposal['budget']['weather_source_files_per_task']):raise ValueError('B2 read budget changed')
    baseline=read(proposal['budget']['comparison_baselines'][str(seed)]['B2']['path'])
    package=Path(private['output_root']);folder=package/f'B2_s{seed}'
    if folder.exists():raise PermissionError('B2 output exists; no retry/resume/replay')
    deadline=_worker_deadline(started,proposal['budget'])
    model,init=fresh_b2(seed,stem_rule=proposal['scientific_choices']['b2_stem_rule'],root=root)
    _validate_b2_initialization(init,proposal,seed)
    folder.mkdir(parents=True,exist_ok=False)
    write(folder/'initialization.json',init)
    orders={epoch:epoch_order(plan.ids('Train'),seed,epoch) for epoch in range(1,10)}
    _validate_b2_orders(proposal,seed,orders)
    write(folder/'train_orders.json',{str(epoch):dict(ids=list(order),sha256=digest(order)) for epoch,order in orders.items()})
    ledger=B2Ledger(folder/'updates.sqlite',dict(approval=approval,data=plan.identity));total_bytes=total_files=0
    def reader(role,epoch,ids):
        nonlocal total_bytes,total_files
        scope=prepared['roles'][role]
        inner=BatchReader(plan,{role:ids},folder/f'B2_{role}_reads_{epoch:02d}',decision_id=approval['decision_id'],
                          max_files=scope['file_count'],max_bytes=scope['bytes_per_pass'],
                          source_bytes={name:item['bytes'] for name,item in scope['files'].items()})
        actual={name:{key:item[key] for key in ('bytes','sha')} for name,item in inner.meter.files.items()}
        wanted={name:{key:item[key] for key in ('bytes','sha')} for name,item in scope['files'].items()}
        if actual!=wanted:
            inner.close();raise PermissionError('Actual loader differs from reviewed source scope')
        total_bytes+=scope['bytes_per_pass'];total_files+=scope['file_count']
        return PassReader(inner,scope)
    try:
        model=model.cuda();optimizer,groups=new_adamw(model)
        buffer_sha=state_digest(dict(model.named_buffers()));u=0;report=None
        for epoch,order in orders.items():
            deadline();resources(backward=False);r=reader('Train',epoch,order)
            visited=[];model.train();nvalid=nrain=0;socc=sqr=0.
            try:
                for pos in range(0,959,2):
                    deadline();b=r.batch('Train',order[pos:pos+2]).to('cuda')
                    if b.identity!=plan.identity or b.ids!=order[pos:pos+2] or b.role!='Train':raise ValueError('Train identity/order drift')
                    optimizer.zero_grad(set_to_none=True)
                    for group in optimizer.param_groups:group['lr']=lr_for_update(u+1,steps_per_epoch=480)
                    with torch.autocast('cuda',dtype=torch.bfloat16):out,loss=forward_b2(model,b)
                    loss.training_objective.backward();clip_and_check(model);ledger.reserve(u+1);optimizer.step();u+=1;ledger.returned(u)
                    check_finite(model.state_dict());check_finite(optimizer.state_dict());visited.extend(b.ids)
                    nvalid+=loss.n_valid;nrain+=loss.n_rain;socc+=float(loss.s_occ.detach());sqr+=float(loss.s_qr.detach())
                    del b,out,loss
            finally:r.close()
            deadline()
            if tuple(visited)!=order or u!=epoch*480 or nvalid!=959*3430 or state_digest(dict(model.named_buffers()))!=buffer_sha:raise RuntimeError('Incomplete B2 epoch or changed buffers')
            training=dict(scenes=959,batches=480,updates=u,n_valid=nvalid,n_rain=nrain,s_occ_unweighted=socc,
                          s_qr_unweighted=sqr,weighted_mean=(socc+sqr)/nvalid,loss_arm='E0',train_order_sha256=digest(order))
            write(folder/f'B2_train_{epoch:02d}.json',training)
            optimizer.zero_grad(set_to_none=True);gc.collect();torch.cuda.empty_cache()
            ids=plan.ids('Development');r=reader('Development',epoch,ids)
            ev=Evaluation(ids,[plan.rows['Development'][sid]['analysis_time'] for sid in ids],plan.identity,
                          folder/f'B2_evaluation_{epoch:02d}',strong_scene_ids=plan.strong_scene_ids)
            tail=TailDiagnostics();model.eval()
            try:
                with torch.no_grad():
                    for pos in range(0,963,8):
                        deadline();b=r.batch('Development',ids[pos:pos+8]).to('cuda')
                        if b.identity!=plan.identity or b.ids!=ids[pos:pos+8] or b.role!='Development':raise ValueError('Development identity/order drift')
                        with torch.autocast('cuda',dtype=torch.bfloat16):out,_=forward_b2(model,b)
                        ev.add(out,b)
                        for i,sid in enumerate(b.ids):
                            tail.add(sid,b.rate[i,0].cpu().numpy(),out.conditional_quantiles_log[i].cpu().numpy(),
                                     (b.valid[i,0]&b.region[i,0]).cpu().numpy())
                        del b,out
                report=ev.finish()
            finally:
                ev.close();r.close()
            deadline()
            write(folder/f'B2_development_{epoch:02d}.json',report)
            write(folder/f'B2_tail_diagnostics_{epoch:02d}.json',tail.finish())
            payload=dict(identity=dict(data=plan.identity,approval=approval,model='B2',seed=seed),epoch=epoch,updates=u,
                         model=cpu_tree(model.state_dict()),optimizer=cpu_tree(optimizer.state_dict()),optimizer_groups=groups,
                         scheduler=dict(completed=u,steps_per_epoch=480,original_horizon=24000),
                         rng=dict(python=random.getstate(),numpy=np.random.get_state(),torch_cpu=torch.get_rng_state(),
                                  torch_cuda=torch.cuda.get_rng_state_all()),
                         training=training,validation=report,train_order_sha256=digest(order))
            checkpoint=folder/f'B2_LAST_epoch_{epoch:02d}.pt'
            with checkpoint.open('xb') as handle:
                torch.save(payload,handle);handle.flush();os.fsync(handle.fileno())
            write(checkpoint.with_suffix('.receipt.json'),dict(model='B2',epoch=epoch,updates=u,seed=seed,code_commit=commit,
                  checkpoint_sha256=sha(checkpoint),validation_receipt_sha256=digest(report),
                  population_sha256=plan.identity['population_sha256']))
            del payload
        if ledger.db.execute("SELECT COUNT(*) FROM updates WHERE state='RETURNED'").fetchone()[0]!=4320:raise RuntimeError('B2 update ledger incomplete')
        write(folder/'B2_minus_B3_E09.json',difference(baseline,report))
        if total_bytes!=proposal['budget']['source_bytes_per_task'][f'B2_s{seed}'] or total_files!=proposal['budget']['source_files_per_task'][f'B2_s{seed}']:raise RuntimeError('B2 logical source totals differ')
        result=dict(status='COMPLETE_TRAIN_AND_DEV_EVALUATION',model='B2',seed=seed,epochs=9,optimizer_updates=4320,
                     total_logical_source_bytes=total_bytes,total_logical_source_files=total_files,replay=0,
                     code_commit=commit,endpoint='FIXED_EPOCH_9_LAST',proposal_sha256=proposal['proposal_sha256'],
                     scientific_acceptance='NOT_IMPLIED_BY_RUN_COMPLETION')
        deadline();write(folder/'completion.json',result);return result
    except BaseException as error:
        _write_folder_failure(folder,error);raise
    finally:ledger.db.close()

def _worker_static(root,proposal,private,approval,commit,index,kind,seed,started):
    _,prepared=load_inherited(private['inherited']['b2_preparation'])
    if prepared['data']!=proposal['data'] or prepared['preparation_sha256']!=private['prepared']['b2']['preparation_sha256']:raise ValueError('Inherited B5/B6 preparation changed')
    plan=PopulationPlan(prepared['private_inputs']['stage3_run'],prepared['private_inputs']['request'],root=root)
    if plan.identity!=proposal['data']:raise ValueError('Pinned B5/B6 population identity changed')
    package=Path(private['output_root']);folder=package/f'{kind}_s{seed}'
    deadline=_worker_deadline(started,proposal['budget']);terrain=Path(private['terrain']);receipt_path=terrain/'production_receipt.json'
    if sha(receipt_path)!=proposal['terrain_receipt_sha256']:raise ValueError('Terrain production receipt changed')
    receipt=read(receipt_path)
    if digest(receipt['scalers'])!=proposal['scalers_sha256']:raise ValueError('Static Train-only scalers changed')
    packs={};static_db=package/f'{kind}_s{seed}_static_source.sqlite'
    db=sqlite3.connect(static_db);db.execute('CREATE TABLE jobs(id TEXT PRIMARY KEY,state TEXT)')
    db.execute("INSERT INTO jobs VALUES ('static','PENDING')");db.commit()
    path=terrain/f'{kind}_static.npz';n=proposal['static_source_bytes'][kind]
    meter=SourceMeter(db,{str(path):dict(bytes=n,sha=proposal['static_source_sha256'][kind],job_id='static')},max_files=1,max_bytes=n)
    meter.active={path_key(path)}
    try:
        with meter.open(path,'rb') as handle:raw=handle.read()
        pack=unpack(raw,kind,receipt);meter.active=set();source_totals=meter.totals()
        with db:db.execute("UPDATE jobs SET state='COMPLETE'")
    finally:db.close()
    packs[kind]=pack;deadline()
    PairedExecutor(plan,folder,decision=FormalDecision(approval['decision_id'],seed,proposal['data']['population_sha256'],True,True,True),
                   kinds=(kind,),deadline=deadline,tail_factory=BatchTail,code_commit=commit,
                   pair_reference=Path(proposal['pair_references'][str(seed)]['path']),
                   model_factory=model_factory(packs,receipt['scalers'])).run(
        ReaderFactory(plan,prepared,approval['decision_id'],allowed_models=(kind,)))
    result=endpoint(folder,kind,seed,commit)
    if source_totals.get('opened_files')!=1 or source_totals.get('delivered_bytes')!=n:raise RuntimeError('Static source metering differs')
    result.update(static_source_reads=source_totals,total_logical_source_bytes=result['logical_source_bytes']+n,
                  total_logical_source_files=result['logical_source_files']+1,proposal_sha256=proposal['proposal_sha256'])
    if (result['total_logical_source_bytes']!=proposal['budget']['source_bytes_per_task'][f'{kind}_s{seed}']
            or result['total_logical_source_files']!=proposal['budget']['source_files_per_task'][f'{kind}_s{seed}']):raise RuntimeError('B5/B6 logical source totals differ')
    deadline();write(folder/'completion.json',result);return result

def worker(root,proposal,private,approval,commit,index):
    """One once-only task worker launched by the approved live controller."""
    started=time.monotonic();proposal,private,approval=checked(root,proposal,private,approval,commit)
    kind,seed=task_for(index);package=Path(private['output_root'])
    binding=read(package/'authorization_binding.json');claim=read(package/f'task_{index+1}_claim.json')
    if (binding.get('controller_pid')!=os.getppid() or binding.get('approval')!=approval
            or claim!=dict(index=index,controller_pid=os.getppid(),code_commit=commit)):raise PermissionError('Worker must be started once by the approved live serial controller')
    if os.environ.get('PYTHONHASHSEED')!=str(seed):raise PermissionError('Worker hash seed must equal its task seed before process startup')
    if shutil.disk_usage(package).free<proposal['budget']['minimum_task_free_bytes']:raise RuntimeError('Output volume below 24GiB for this task; no cleanup/fallback')
    try:
        if kind=='B2':return _worker_b2(root,proposal,private,approval,commit,index,kind,seed,started)
        return _worker_static(root,proposal,private,approval,commit,index,kind,seed,started)
    except BaseException as error:
        failure=dict(index=index,model=kind,seed=seed,status='STOP_NO_AUTOMATIC_REPLAY',error=type(error).__name__+': '+str(error))
        try:write(package/f'task_{index+1}_failure.json',failure)
        except FileExistsError:pass
        raise

def validate_completion(kind,seed,budget,commit,result):
    key=f'{kind}_s{seed}'
    if (result.get('status')!='COMPLETE_TRAIN_AND_DEV_EVALUATION' or result.get('model')!=kind
            or result.get('seed')!=seed or result.get('code_commit')!=commit or result.get('optimizer_updates')!=4320
            or result.get('total_logical_source_bytes')!=budget['source_bytes_per_task'][key]
            or result.get('total_logical_source_files')!=budget['source_files_per_task'][key]):
        raise RuntimeError('Worker completion differs from the approved task/core budget')
    return True

def write_package_failure(out,error,updates=0,source_bytes=0,source_files=0):
    path=Path(out)/'failure.json'
    try:
        write(path,dict(status='STOP_NO_AUTOMATIC_REPLAY',error=type(error).__name__+': '+str(error),
                        completed_updates=updates,completed_source_bytes=source_bytes,completed_source_files=source_files,
                        partial_task_counters='SEE_PRESERVED_TASK_LEDGERS; NOT_COUNTED_AS_ZERO'))
    except FileExistsError:pass
    return path

def _comparison_summary(out,proposal):
    baselines=proposal['budget']['comparison_baselines']
    combined=dict(scope=SCOPE,endpoint='FIXED_EPOCH_9_LAST',seeds=[2030,2031],descriptive_only=True,
                  significance='NOT_CLAIMED',comparisons={})
    for seed in (2030,2031):
        seed_text=str(seed)
        b3=read(baselines[seed_text]['B2']['path']);b2=read(Path(out)/f'B2_s{seed}'/'B2_development_09.json')
        b4=read(baselines[seed_text]['B5']['path']);b5=read(Path(out)/f'B5_s{seed}'/'B5_development_09.json')
        b6=read(Path(out)/f'B6_s{seed}'/'B6_development_09.json')
        b2_difference=difference(b3,b2);paired_difference(b4,b5);paired_difference(b4,b6)
        values=dict(B3=metric_values(b3),B2=metric_values(b2),B4=metric_values(b4),B5=metric_values(b5),B6=metric_values(b6))
        keys=tuple(values['B3'])
        summary=dict(seed=seed,endpoint='FIXED_EPOCH_9_LAST',values=values,
            differences=dict(B2_minus_B3={k:values['B2'][k]-values['B3'][k] for k in keys},
                             B5_minus_B4={k:values['B5'][k]-values['B4'][k] for k in keys},
                             B6_minus_B4={k:values['B6'][k]-values['B4'][k] for k in keys},
                             B6_minus_B5={k:values['B6'][k]-values['B5'][k] for k in keys}),
            b2_group_differences=b2_difference,descriptive_only=True,significance='NOT_CLAIMED')
        write(Path(out)/f'seed{seed}_comparison_summary.json',summary);combined['comparisons'][seed_text]=summary
    write(Path(out)/'comparison_summary.json',combined);return combined

def execute(root,proposal,private,approval,commit,*,worker_python=None):
    """Serial six-task controller. Fresh output only; failure stops the package."""
    root=Path(root);started=time.monotonic()
    proposal_path,private_path,approval_path=Path(proposal),Path(private),Path(approval)
    proposal,private,approval=checked(root,proposal_path,private_path,approval_path,commit)
    out,free=validate_output_root(private['output_root'])
    admission=dict(resources(),initial_output_free_bytes=free)
    out.mkdir(parents=True,exist_ok=False)
    write(out/'authorization_binding.json',dict(approval=approval,controller_pid=os.getpid(),admission=admission,
                                                proposal_sha256=proposal['proposal_sha256'],code_commit=commit))
    total_updates=total_bytes=total_files=0;active=None
    try:
        for index,(kind,seed) in enumerate(TASKS):
            remaining=proposal['budget']['max_package_seconds']-(time.monotonic()-started)
            if remaining<=0:raise RuntimeError('Seed-completion package 36h limit reached; no replay')
            write(out/f'task_{index+1}_claim.json',dict(index=index,controller_pid=os.getpid(),code_commit=commit))
            command=worker_command(root,proposal_path,private_path,approval_path,index,worker_python=worker_python)
            with (out/f'{kind}_s{seed}_console.log').open('xb') as log:
                active=subprocess.Popen(command,cwd=str(root),env=worker_environment(seed),stdout=log,
                                        stderr=subprocess.STDOUT,creationflags=worker_creation_flags())
                try:code=active.wait(timeout=min(remaining,proposal['budget']['task_wall_seconds'][kind]))
                except subprocess.TimeoutExpired:
                    active.kill();active.wait();raise RuntimeError('Task wall-time limit; remaining tasks blocked, no replay')
            active=None
            if code:raise RuntimeError(f'{kind} seed{seed} worker stopped with exit {code}; dependent tasks blocked')
            result=read(out/f'{kind}_s{seed}'/'completion.json')
            validate_completion(kind,seed,proposal['budget'],commit,result)
            total_updates+=result['optimizer_updates'];total_bytes+=result['total_logical_source_bytes'];total_files+=result['total_logical_source_files']
        validate_package_closure(dict(optimizer_updates=total_updates,total_logical_source_bytes=total_bytes,
                                      total_logical_source_files=total_files),proposal['budget'])
        _comparison_summary(out,proposal)
        if time.monotonic()-started>proposal['budget']['max_package_seconds']:raise RuntimeError('Seed-completion package closure exceeded 36h')
        result=dict(status='COMPLETE_SEED_COMPLETION_PACKAGE',scope=SCOPE,models=6,seeds=[2030,2031],
                    optimizer_updates=total_updates,total_logical_source_bytes=total_bytes,total_logical_source_files=total_files,
                    replay=0,additional_retries=0,code_commit=commit,proposal_sha256=proposal['proposal_sha256'],
                    comparison_summary_sha256=sha(out/'comparison_summary.json'),
                    scientific_acceptance='NOT_IMPLIED_BY_RUN_COMPLETION')
        write(out/'package_completion.json',result);return result
    except BaseException as error:
        if active is not None and active.poll() is None:active.kill();active.wait()
        write_package_failure(out,error,total_updates,total_bytes,total_files);raise

def _as_mapping(value):
    return value if isinstance(value,dict) else read(value)

def dry_run(root,proposal,private,approval,commit):
    """No Train/Dev reads, no model construction, no checkpoint load."""
    root=Path(root);proposal,private,approval=map(_as_mapping,(proposal,private,approval))
    expected=verify_proposal_digest(proposal);validate_approval(approval,proposal,private,commit)
    if private.get('proposal_sha256')!=expected:raise ValueError('Private seed-completion preparation differs')
    if (proposal.get('version')!=VERSION or proposal.get('scope')!=SCOPE or proposal.get('kind')!=KIND
            or proposal.get('authorized') is not False
            or proposal.get('tasks')!=[dict(model=kind,seed=seed) for kind,seed in TASKS]):raise ValueError('Seed-completion proposal identity differs')
    validate_budget(proposal['budget']);check_code_hashes(root,proposal);check_input_pins(proposal)
    if proposal.get('static_source_sha256')!=STATIC_SOURCE_SHA256:raise ValueError('Pinned static terrain hashes differ')
    if proposal.get('terrain_receipt_sha256')!=TERRAIN_RECEIPT_SHA256:raise ValueError('Pinned terrain receipt differs')
    out,free=validate_output_root(private['output_root'])
    summary=dict(status='DRY_RUN_OK',scope=SCOPE,proposal_sha256=expected,tasks=proposal['tasks'],
                 model_count=proposal['budget']['models'],optimizer_updates=proposal['budget']['total_updates'],
                 total_source_bytes=proposal['budget']['total_source_bytes'],
                 total_source_files=proposal['budget']['total_source_files'],
                 max_task_seconds=proposal['budget']['max_task_seconds'],
                 max_package_seconds=proposal['budget']['max_package_seconds'],output_root=str(out.resolve()),
                 initial_free_bytes=free,replay_allowance=proposal['budget']['replay_allowance'],
                 train_or_dev_reads=0,raw_payload_opens=0,model_constructions=0,checkpoint_loads=0,
                 torch_load_calls=0,optimizer_updates_executed=0)
    print('DRY_RUN_OK')
    print(json.dumps({key:summary[key] for key in ('scope','proposal_sha256','tasks','optimizer_updates',
                     'total_source_bytes','total_source_files','output_root')},indent=2,ensure_ascii=False))
    return summary
