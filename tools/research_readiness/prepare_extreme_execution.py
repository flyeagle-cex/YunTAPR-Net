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


def prepare(old_private, workspace, public, execution_root):
    workspace,public,execution_root=map(lambda p:Path(p).resolve(),(workspace,public,execution_root))
    local=(ROOT/'docs/research_readiness/.local').resolve()
    if not workspace.is_relative_to(local) or workspace.exists() or public.exists():
        raise PermissionError('Fresh preparation directories required; preserve all history')
    if not public.is_relative_to((ROOT/'docs/research_readiness').resolve()):
        raise PermissionError('Public preparation must remain inside the research documentation tree')
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
    output=local/'extreme_diagnostic_execution_20261031_v1'
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
        weights='Only existence/size checked now; actual SHA and strict load each once after approval',
        real_end_to_end_numerical_gate='NOT_VERIFIED_UNTIL_THE_APPROVED_SINGLE_PASS; previous19 core provider gates inherited',
        source_reference='239935204070 payload bytes +964353774 checkpoint archive access +1073741824 guarded metadata cap',
        final_2025_access=False,training=False,automatic_follow_on=False)
    p['proposal_sha256']=execution.digest(p)
    p_path=public/'proposal.json';write(p_path,p)
    private=dict(proposal_sha256=p['proposal_sha256'],engine=str(workspace/'provider_frozen.py'),
        registry=str(workspace/'run_registry.json'),output_root=str(output),torch_site=old['torch_site'],
        static_source=str(static_dir/'B6_static.npz'),label_files=labels,provider_manifests=roots,
        runtime_python='F:/pytorch/Research/.venv/Scripts/python.exe')
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
    args=parser.parse_args();prepare(args.old_private,args.workspace,args.public,args.execution_root)
