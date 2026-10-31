"""Metadata-only binding of the finite diagnostic executable and new budget.

No weight/static/weather payload is opened. No approval or formal output
namespace is created. The final proposal is not itself an execution grant.
"""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.research_readiness import start_extreme_diagnostic as execution

FILES = (
    "tools/research_readiness/start_extreme_diagnostic.py",
    "tools/research_readiness/extreme_diagnostic_provider.py",
    "tools/research_readiness/extreme_diagnostic_export.py",
    "tools/research_readiness/extreme_diagnostic_candidates.py",
    "tools/research_readiness/start_independent_process.py",
    "tools/core_stage4/monitor/server.py",
)


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path, value):execution.write(path, value)


def provider_files(root):
    root=Path(root)
    files=list((root/'src').rglob('*.py'))
    files.extend(p for p in (root/'config').rglob('*') if p.is_file() and p.suffix in ('.json','.yaml','.yml','.csv'))
    return {p.relative_to(root).as_posix():sha(p) for p in sorted(files)}


def native_runtime(venv):
    cfg=Path(venv).parent.parent/'pyvenv.cfg'
    homes=[line.split('=',1)[1].strip() for line in cfg.read_text(encoding='utf-8-sig').splitlines()
           if '=' in line and line.split('=',1)[0].strip()=='home']
    if len(homes)!=1:raise ValueError('Unique inherited native-base configuration required')
    native=(Path(homes[0])/'python.exe').resolve()
    query='import sys,json;print(json.dumps(dict(python_version=".".join(map(str,sys.version_info[:3])),cache_tag=sys.implementation.cache_tag,implementation=sys.implementation.name)))'
    identity=json.loads(subprocess.check_output([str(native),'-B','-c',query],encoding='utf-8'))
    identity.update(executable_sha256=sha(native),inherited_venv_config_sha256=sha(cfg),direct_native_base_required=True)
    return native,cfg,identity


def prepare(old_private, workspace, public, execution_root, prior_private=None):
    workspace,public,execution_root=map(lambda p:Path(p).resolve(),(workspace,public,execution_root))
    local=(ROOT/'docs/research_readiness/.local').resolve()
    if not workspace.is_relative_to(local) or workspace.exists() or public.exists():
        raise PermissionError('Fresh preparation directories required; preserve all history')
    if not public.is_relative_to((ROOT/'docs/research_readiness').resolve()):
        raise PermissionError('Public preparation must remain inside the research documentation tree')
    if prior_private is None:
        raise PermissionError('This version requires the preserved V2 metadata-cap failure')
    correction=None
    if prior_private is not None:
        prior_private=Path(prior_private).resolve();prior=read(prior_private)
        locations=read(prior_private.parent/'locations.json');previous=read(locations['proposal'])
        service=Path(locations['spec']).parent
        failure=read(service/'target_exit.json')
        prior_output=Path(prior['output_root'])
        stderr=(prior_output/'TRAIN_LABELS_console.log').read_text(encoding='utf-8')
        probe_path=ROOT/'docs/research_readiness/.local/extreme_diagnostic_lifetime_probe_20261031/result.json'
        probe=read(probe_path);records={r['runtime']:r for r in probe['records']}
        metadata_probe_path=ROOT/'docs/research_readiness/.local/extreme_diagnostic_metadata_probe_20261031_v1/checked_metadata/result.json'
        metadata_probe=read(metadata_probe_path)
        v1_receipt=read(ROOT/'docs/research_readiness/20261031_extreme_diagnostic_execution_v1/launch/failure_receipt.json')
        v2_receipt=read(Path(locations['proposal']).parent/'launch/failure_receipt.json')
        prior_target_seconds=v1_receipt['target_wall_seconds']+v2_receipt['target_wall_seconds']
        if (not prior_output.exists() or failure['return_code']!=1
                or not stderr.rstrip().endswith('PermissionError: Frozen metadata reservation cap exceeded')
                or (prior_output/'TRAIN_LABELS/source_reservations.jsonl').exists()
                or (prior_output/'TRAIN_LABELS/label_reads.sqlite').exists()
                or any(p.is_dir() and p.name.startswith(('B4_','B7_','B8_')) for p in prior_output.iterdir())
                or records['original_venv']['in_any_job'] is not True
                or records['same_native_base']['in_any_job'] is not False
                or records['same_native_base']['direct_parent_matches'] is not True
                or records['same_native_base']['package_status']!=15700
                or metadata_probe['status']!='PASS_REAL_FROZEN_METADATA_ONLY_NO_SCIENTIFIC_PAYLOAD'
                or metadata_probe['accounting']['payload_reserved_bytes']!={}
                or metadata_probe['accounting']['metadata_archive_reserved_bytes']>execution.LIMITS['worker_metadata_archive_cap_bytes']
                or prior_target_seconds>execution.LIMITS['prior_target_seconds_charge']):
            raise PermissionError('Exact preserved metadata failure and no-payload metadata/native identity proofs required')
        correction=dict(prior_proposal_sha256=previous['proposal_sha256'],prior_code_commit=previous['execution_code_commit'],
            prior_approval_sha256=sha(locations['approval']),prior_attempt_state='STOPPED_AT_SHARED_LABEL_METADATA_CAP_BEFORE_SCIENTIFIC_PAYLOAD',
            prior_model_loads=0,prior_source_payload_bytes=0,prior_optimizer_updates=0,prior_diagnostic_clock_started=True,
            lifetime_probe_sha256=sha(probe_path),metadata_probe_sha256=sha(metadata_probe_path),
            prior_metadata_counter='Not persisted by V2; conservatively charge its entire 64MiB/128-open worker allowance',
            prior_target_wall_seconds=prior_target_seconds,
            metadata_probe_accounting=metadata_probe['accounting'],
            scope='Metadata quota, before-open package enforcement and failure accounting only; scientific methods and numerical model path unchanged',
            prior_grant_reused=False,prior_outputs_and_claims_preserved=True)
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=execution_root,text=True).strip()
    if subprocess.check_output(['git','-c','core.longpaths=true','status','--porcelain'],cwd=execution_root,text=True).strip():
        raise PermissionError('Prepare against a clean fixed execution copy')
    old=read(old_private)
    if sha(old['engine'])!='0ca882baf7d4fcc00aa72543bff4773e98a27130b56b86fba41c7a3905eb8e93':
        raise ValueError('Only the previously gate-verified frozen provider')
    registry=read(old['registry']);runs={r['run_id']:r for r in registry['runs']}
    g0_path=ROOT/'docs/research_readiness/20261031_extreme_diagnostic_preparation_v1/proposal.json'
    g0=read(g0_path);expected={(r['model'],r['seed']):r for r in g0['models']}
    static_dir=None
    for node in ast.parse(Path(old['engine']).read_text(encoding='utf-8-sig')).body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='STATIC_TERRAIN' for t in node.targets):
            static_dir=Path(ast.literal_eval(node.value))
    if static_dir is None or (static_dir/'B6_static.npz').stat().st_size!=312828:
        raise ValueError('Inherited static metadata missing or size changed')
    public_static=read(ROOT/'docs/research_readiness/20261025/evidence/b7_b8_training_proposal.json')['static_source_sha256']['B7']
    roots={};models=[]
    for rid in execution.ORDER[1:]:
        run=runs[rid];identity=expected[(run['model'],int(run['seed']))]
        if (run['checkpoint_sha256']!=identity['checkpoint_sha256']
                or run['checkpoint_bytes']!=identity['inherited_checkpoint_bytes']
                or Path(run['checkpoint_path']).stat().st_size!=run['checkpoint_bytes']
                or run['read_scope']['dev_pass_bytes']!=26639253112
                or run['read_scope']['dev_pass_files']!=7950):
            raise ValueError('Saved core identity or metadata size does not match')
        if run['code_root'] not in roots:roots[run['code_root']]=provider_files(run['code_root'])
        prepared=read(run['private_preparation']['path'])['prepared']
        scope=prepared['roles']['Development']
        if (len(scope['files'])!=7950 or sum(i['bytes'] for i in scope['files'].values())!=26639253112
                or prepared['data']['population_sha256']!=g0['population']['source_identity_sha256']):
            raise ValueError('Frozen development membership differs')
        for path,info in scope['files'].items():
            if info['year']!=2024 and not (info['kind']=='static_mask' and info['year']==2023):
                raise PermissionError('No new population/year can enter')
        models.append(dict(run_id=rid,model=run['model'],seed=int(run['seed']),
            checkpoint_sha256=run['checkpoint_sha256'],checkpoint_bytes=run['checkpoint_bytes'],
            training_execution_commit=identity['training_execution_commit'],
            preparation_sha256=sha(run['private_preparation']['path']),
            provider_manifest_sha256=execution.digest(roots[run['code_root']])))
    prepared=read(runs['B4_s2029']['private_preparation']['path'])['prepared']
    labels={path:info for path,info in prepared['roles']['Train']['files'].items() if info['kind'] in ('IMERG','static_mask')}
    if len(labels)!=246 or sum(f['bytes'] for f in labels.values())!=180049094 or any(f['year']!=2023 for f in labels.values()):
        raise ValueError('Exact single 2023 label/mask scope missing')
    runtime,cfg,runtime_identity=native_runtime('F:/pytorch/Research/.venv/Scripts/python.exe')
    output=local/'extreme_diagnostic_execution_20261031_v3'
    if output.exists():raise PermissionError('Candidate formal output already exists')
    workspace.mkdir(exist_ok=False);public.mkdir(exist_ok=False)
    for name,key in [('provider_frozen.py','engine'),('run_registry.json','registry')]:
        with (workspace/name).open('xb') as stream:stream.write(Path(old[key]).read_bytes())
    scientific=dict(g0['proposed_methods'],
        point_probability_carrier='FP32 export of already-computed BF16/FP32 probabilities; values preserved; no sigmoid recomputation',
        joint_condition_rules=dict(signs='O>0,O<0,O=0 at850/700hPa',pressure='850 available,700 only',
            PWAT_reference_kg_m2=31.85768219039871,water_bins='below or at/above frozen reference',
            elevation_edges_m=[1000,2000],joint_truth_thresholds_mm_h=[20,50],
            rainfall_bins='(0.1,1],(1,5],(5,10],(10,20],(20,30],(30,50],(50,+inf)',
            truth_stratified_coverage='Descriptive only; conditioning on observed intensity changes nominal coverage interpretation'),
        model_path='Pinned original provider, unchanged forward and evaluator; new sidecar only',
        metadata_accounting='Code/library/approval-byte identity checks are pinned separately; worker frozen-metadata archives receive explicit finite reservations',
        event_id='NOT_IDENTIFIED; no independent-event claims or new observations',
        no_graphs='No new figure generation; numerical diagnostics and private arrays only')
    p=dict(status='READY_WAITING_EXACT_RESEARCHER_METHOD_AND_BUDGET_APPROVAL',authorized=False,
        authorization_scope=execution.SCOPE,execution_code_commit=head,tasks=list(execution.ORDER),models=models,
        scientific_choices=scientific,budget=dict(execution.LIMITS),data_identity=g0['population'],
        engine_sha256=sha(workspace/'provider_frozen.py'),registry_sha256=sha(workspace/'run_registry.json'),
        static_sha256=public_static,preparation_baseline_sha256=sha(g0_path),
        code_sha256={name:sha(execution_root/name) for name in FILES},
        runtime=runtime_identity,correction=correction,
        weights='Only existence/size checked now; actual SHA and strict load each once after approval',
        real_end_to_end_numerical_gate='NOT_VERIFIED_UNTIL_THE_APPROVED_SINGLE_PASS; previous19 core provider gates inherited',
        source_reference='239935204070 payload bytes +964353774 checkpoint archive access +1275068416 future metadata cap; charge previous metadata 67108864 separately',
        final_2025_access=False,training=False,automatic_follow_on=False)
    unchanged=('weather_static_label_bytes','weather_static_label_instances','checkpoint_archive_bytes',
        'checkpoint_sha_passes','checkpoint_loads','checkpoint_archive_reference_bytes','payload_archive_reference_bytes',
        'worker_metadata_open_cap','per_model_seconds','label_seconds','output_storage_cap_bytes','minimum_free_bytes',
        'minimum_host_available_bytes','minimum_gpu_free_mib','optimizer_updates','retries','replay')
    if p['scientific_choices']!=previous['scientific_choices'] or any(p['budget'][k]!=previous['budget'][k] for k in unchanged):
        raise ValueError('A metadata correction cannot silently change the method, payload or compute scope')
    p['budget_change_requiring_researcher_approval']=dict(metadata_cumulative_additional_bytes=256*1024**2,
        worker_metadata_old_bytes=67108864,worker_metadata_new_bytes=134217728,
        future_metadata_bytes=1275068416,prior_metadata_charge_bytes=67108864,
        cumulative_metadata_bytes=1342177280,cumulative_source_bytes=242241735124,
        prior_target_seconds_charge=12,future_maximum_seconds=21588,cumulative_maximum_seconds=21600,
        reason='Frozen SQLite metadata is hashed and connected separately; previous 64MiB worker cap was insufficient')
    p['proposal_sha256']=execution.digest(p)
    p_path=public/'proposal.json';write(p_path,p)
    private=dict(proposal_sha256=p['proposal_sha256'],engine=str(workspace/'provider_frozen.py'),
        registry=str(workspace/'run_registry.json'),output_root=str(output),torch_site=old['torch_site'],
        static_source=str(static_dir/'B6_static.npz'),label_files=labels,provider_manifests=roots,
        runtime_python=str(runtime),inherited_venv_config=str(cfg))
    private_path=workspace/'private.json';write(private_path,private)
    grant=workspace/'researcher_approval.json'
    service=workspace/'service';service.mkdir()
    spec=dict(kind='BOUNDED_EXTREME_DIAGNOSTIC',service_dir=str(service),cwd=str(execution_root),
        command=[private['runtime_python'],'-B',str(execution_root/'tools/research_readiness/start_extreme_diagnostic.py'),
                 'execute','--proposal',str(p_path),'--private-preparation',str(private_path),'--researcher-approval',str(grant)],
        environment=dict(PYTHONUTF8='1'))
    write(service/'spec.json',spec)
    write(workspace/'locations.json',dict(proposal=str(p_path),private=str(private_path),approval=str(grant),
        spec=str(service/'spec.json'),execution_root=str(execution_root)))
    write(public/'preparation_receipt.json',dict(status=p['status'],proposal_sha256=p['proposal_sha256'],
        execution_code_commit=head,checks=dict(nine_model_receipt_identities=True,checkpoint_sizes_only=True,
            development_source_manifests=True,single_train_label_manifest=True,frozen_provider_byte_identity=True,
            provider_code_manifests_bound=True),approval_file_created=grant.exists(),
        formal_output_created=output.exists(),raw_payload_reads=0,model_loads=0,inference=0,optimizer_updates=0,
        provider_code_tree_count=len(roots),private_preparation_sha256=sha(private_path),
        spec_sha256=sha(service/'spec.json'),final_2025_access=False,
        at=datetime.now(timezone.utc).isoformat()))
    print(json.dumps(dict(status=p['status'],execution_code_commit=head,proposal_sha256=p['proposal_sha256'],
                         approval_file_created=grant.exists(),formal_output_created=output.exists(),new_model_computation=0)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('old-private','workspace','public','execution-root'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--prior-private',type=Path)
    args=parser.parse_args();prepare(args.old_private,args.workspace,args.public,args.execution_root,args.prior_private)
