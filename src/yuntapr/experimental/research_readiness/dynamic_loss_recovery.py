"""Bounded B8/2029/E2 E8-to-E9 recovery, retaining the completed B7 endpoint."""
import copy
from dataclasses import asdict
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from ..core_innovation.stage3.metered_io import SourceMeter, path_key
from ..core_innovation.stage3.planning import digest
from ..core_innovation.stage4.data import PopulationPlan, read, sha
from ..core_innovation.stage4.engine import FormalDecision, PairedExecutor, resources, write
from ..core_innovation.stage4.launch import ReaderFactory
from ..core_innovation.stage4.recovery import RecoveryLedger, ResumeState, query, restore_last
from ..phase_b_v2_ablations.config import get_config
from .dynamic_terrain import DoteDefinition, PhysicalDote, model_factory
from .dynamic_training import TerrainTail, hashes as dynamic_hashes, loss_pair_summary, runtime_binding
from .multiseed import load_inherited, worker_creation_flags
from .static_training import unpack

ENTRY = 'tools/research_readiness/start_dynamic_loss_recovery.py'
MODULE = 'src/yuntapr/experimental/research_readiness/dynamic_loss_recovery.py'
STOP = 'docs/research_readiness/20261108_lambda2_stop/TERMINAL_VERIFICATION.json'
SCOPE = 'docs/research_readiness/20261108_lambda2_stop/RECOVERY_SCOPE.json'
SCOPE_SHA = '1779c23542b9005fa181727c3ae99a8b2f1e1d2a7ea66c64cfc178cd3aca3761'
PARENT_COMMIT = '8339fe407fdd084b0271c1af2ae42f98888bbd8e'
CHECKPOINT_SHA = 'accc2aba0ae53a9a1fe5bff28b9de689b7b41b3474f32195b8b6a68173c77984'
TASKS = [dict(model='B8', seed=2029)]
CHANGED_DEPENDENCIES = {
    'src/yuntapr/experimental/core_innovation/stage4/engine.py',
    'src/yuntapr/experimental/core_innovation/stage4/recovery.py',
    'src/yuntapr/experimental/research_readiness/dynamic_training.py',
    'tools/research_readiness/start_independent_process.py',
}


def hashes(root):
    result = dynamic_hashes(root)
    result.update({name: sha(root/name) for name in (ENTRY, MODULE)})
    return result


def budget(prepared, stop):
    weather_bytes = sum(role['bytes_per_pass'] for role in prepared['roles'].values())
    weather_files = sum(role['file_count'] for role in prepared['roles'].values())
    if (weather_bytes, weather_files) != (53063515668, 15868):
        raise ValueError('Frozen one-epoch source scope changed')
    prior = stop['actual']
    if (prior['returned_updates'], prior['reserved_source_bytes'], prior['source_files']) != (8640, 951352206452, 284363):
        raise ValueError('Unexpected stopped package accounting')
    return dict(new_updates=480, replayed_updates=480, new_source_bytes=weather_bytes+312828,
                new_source_files=weather_files+1, new_weather_source_bytes=weather_bytes,
                new_static_source_bytes=312828, max_wall_seconds=3600,
                minimum_initial_free_bytes=24*1024**3, minimum_task_free_bytes=24*1024**3,
                checkpoint_sha_reads=1, checkpoint_deserializations=1,
                cumulative_updates=9120, cumulative_source_bytes=prior['reserved_source_bytes']+weather_bytes+312828,
                cumulative_source_files=prior['source_files']+weather_files+1,
                prior_package_seconds=stop['wall_seconds_mtime_proxy_ceil'],
                cumulative_package_seconds=stop['wall_seconds_mtime_proxy_ceil']+3600,
                prior_B8_worker_seconds=21600, cumulative_B8_worker_seconds=25200,
                additional_retry_allowance=0)


def prepare(root, original_proposal, original_private, output):
    root, output = Path(root), Path(output).resolve()
    original_proposal, original_private = Path(original_proposal).resolve(), Path(original_private).resolve()
    original, private, stop = read(original_proposal), read(original_private), read(root/STOP)
    if (digest({key:value for key,value in original.items() if key!='proposal_sha256'}) != original['proposal_sha256']
            or original['protocol']['loss'] != 'E2' or original['protocol']['lambda_q'] != 2.0):
        raise ValueError('Original E2 proposal digest or loss identity changed')
    if sha(root/SCOPE) != SCOPE_SHA or sha(root/STOP) != read(root/SCOPE)['terminal_verification_sha256']:
        raise ValueError('Researcher-visible recovery scope changed')
    if original['proposal_sha256'] != stop['proposal_sha256'] or stop['execution_commit'] != PARENT_COMMIT:
        raise ValueError('Exact stopped E2 package required')
    parent = Path(private['output_root'])
    if query(parent/'B8_s2029/updates.sqlite', 'SELECT model,state,COUNT(*),MIN(u),MAX(u) FROM updates GROUP BY model,state') != [('B8','RETURNED',4320,1,4320)]:
        raise ValueError('Stopped update ledger changed')
    if (parent/'B8_s2029/B8_LAST_epoch_09.pt').exists():
        raise PermissionError('An E9 checkpoint already exists')
    _, prepared = load_inherited(private['inherited'])
    if prepared['data'] != original['data'] or runtime_binding() != original['runtime_binding']:
        raise ValueError('Original data or E2 numerical runtime changed')
    current = hashes(root)
    if any(current.get(name) != value for name,value in original['code_sha256'].items() if name not in CHANGED_DEPENDENCIES):
        raise ValueError('Unchanged scientific dependency differs')
    names = ['failure.json', 'B7_s2029/completion.json', 'B7_s2029/B7_development_09.json',
             'B7_s2029/B7_LAST_epoch_09.receipt.json', 'B8_s2029/updates.sqlite',
             'B8_s2029/paired_initial_identity.json', 'B8_s2029/paired_orders.json',
             'B8_s2029/B8_train_09.json', 'B8_s2029/B8_LAST_epoch_08.receipt.json']
    names += [f'B8_s2029/B8_development_{epoch:02d}.json' for epoch in range(1,9)]
    pins = {name:sha(parent/name) for name in names}
    checkpoint = parent/'B8_s2029/B8_LAST_epoch_08.pt'
    seal = read(checkpoint.with_suffix('.receipt.json'))
    if (seal['checkpoint_sha256'], seal['epoch'], seal['updates'], seal['loss_config']) != (CHECKPOINT_SHA, 8, 3840, asdict(get_config('E2'))):
        raise ValueError('Exact E8 E2 checkpoint receipt required')
    if checkpoint.stat().st_size != 53905085:
        raise ValueError('Checkpoint file size changed')
    if output.exists() or not output.parent.is_dir() or shutil.disk_usage(output.parent).free < 24*1024**3:
        raise PermissionError('Fresh output and24GiB free space required')
    choices = copy.deepcopy(original['scientific_choices'])
    choices['recovery'] = dict(model='B8', seed=2029, checkpoint_epoch=8, checkpoint_updates=3840,
                               checkpoint_sha256=CHECKPOINT_SHA, execute_epochs=[9], replayed_updates=480,
                               restore='MODEL_ADAMW_SCHEDULE_PYTHON_NUMPY_CPU_AND_CUDA_RNG')
    proposal = dict(status='READY_FOR_RESEARCHER_DIRECTED_LIMITED_RECOVERY', authorized=False,
                    tasks=TASKS, data=original['data'], budget=budget(prepared,stop), scientific_choices=choices,
                    protocol=dict(loss='E2', lambda_q=2.0, seed=2029, endpoint='FIXED_EPOCH_9', epochs=[9]),
                    runtime_binding=original['runtime_binding'], code_sha256=current, parent_pins=pins,
                    original_proposal_file_sha256=sha(original_proposal), original_private_file_sha256=sha(original_private),
                    stop_sha256=sha(root/STOP), researcher_visible_scope_sha256=SCOPE_SHA,
                    checkpoint=dict(sha256=CHECKPOINT_SHA, bytes=53905085, epoch=8, updates=3840),
                    preparation=dict(raw_weather_reads=0, checkpoint_loads=0, optimizer_updates=0))
    proposal['proposal_sha256'] = digest(proposal)
    binding = dict(proposal_sha256=proposal['proposal_sha256'], original_proposal=str(original_proposal),
                   original_private=str(original_private), parent=str(parent), output_root=str(output))
    return proposal, binding


def validate_approval(approval, proposal, private, commit):
    expected = dict(approved_by_researcher=True, code_commit=commit, proposal_sha256=proposal['proposal_sha256'],
                    tasks=proposal['tasks'], budget=proposal['budget'], scientific_choices=proposal['scientific_choices'],
                    output_root=private['output_root'], approved_replay_updates=480,
                    researcher_visible_scope_sha256=SCOPE_SHA)
    if any(approval.get(key) != value for key,value in expected.items()) or not approval.get('decision_id'):
        raise PermissionError('Researcher instruction and exact480-replay recovery binding required')


def checked(root, proposal_path, private_path, approval_path, commit):
    proposal, private, approval = map(read, (proposal_path, private_path, approval_path))
    validate_approval(approval, proposal, private, commit)
    if digest({key:value for key,value in proposal.items() if key!='proposal_sha256'}) != proposal['proposal_sha256']:
        raise ValueError('Recovery proposal digest changed')
    if private['proposal_sha256'] != proposal['proposal_sha256'] or hashes(root) != proposal['code_sha256']:
        raise ValueError('Bound recovery code or private identity changed')
    if runtime_binding() != proposal['runtime_binding']:
        raise ValueError('Recovery numerical runtime changed')
    if sha(private['original_proposal']) != proposal['original_proposal_file_sha256'] or sha(private['original_private']) != proposal['original_private_file_sha256']:
        raise ValueError('Original package binding changed')
    original, original_private = read(private['original_proposal']), read(private['original_private'])
    if Path(original_private['output_root']).resolve() != Path(private['parent']).resolve():
        raise ValueError('Recovery parent location changed')
    if sha(root/STOP) != proposal['stop_sha256'] or sha(root/SCOPE) != SCOPE_SHA:
        raise ValueError('Stopped package evidence changed')
    if any(sha(Path(private['parent'])/name) != value for name,value in proposal['parent_pins'].items()):
        raise ValueError('Inherited endpoint or replay evidence changed')
    _, prepared = load_inherited(original_private['inherited'])
    if prepared['data'] != proposal['data'] or budget(prepared,read(root/STOP)) != proposal['budget']:
        raise ValueError('Recovery population or exact budget changed')
    return proposal, private, approval, prepared, original, original_private


class B8E2Resume(ResumeState):
    kinds = ('B8',)
    loss_config = get_config('E2')

    def completed_epochs(self, kind):
        if kind != 'B8':
            raise PermissionError('Only B8 E9 can be resumed')
        return 8

    def validate(self, plan, decision):
        if (plan.identity != self.request['data_identity'] or decision.seed != 2029
                or decision.decision_id != self.request['decision_id']
                or self.request['checkpoint_sha256'] != CHECKPOINT_SHA):
            raise PermissionError('B8 E2 restoration identity changed')

    def ledger(self, path, identity):
        return RecoveryLedger(path,dict(identity,recovery=self.request), offsets={'B8':3840},
                              segment_cap=480, prior_updates=4320, cumulative_cap=4800, allowed_models=self.kinds)

    def restore(self, kind, model, optimizer, groups):
        self.completed_epochs(kind)
        checkpoint = self.parent/'B8_LAST_epoch_08.pt'
        if sha(checkpoint) != self.request['checkpoint_sha256']:
            raise ValueError('E8 checkpoint changed before its single load')
        restore_last(checkpoint, model, optimizer, groups, data_identity=self.request['data_identity'],
                     epoch=8, updates=3840, kind='B8', seed=2029, loss_config=asdict(self.loss_config))
        return 3840, [read(self.parent/f'B8_development_{epoch:02d}.json') for epoch in range(1,9)]


class RemainingReaders(ReaderFactory):
    def __call__(self, role, epoch, ids, folder):
        if epoch != 9 or Path(folder).name.split('_',1)[0] != 'B8' or role not in ('Train','Development'):
            raise PermissionError('Only B8 E9 Train and Development passes are authorized')
        return super().__call__(role, epoch, ids, folder)


def worker(root, proposal_path, private_path, approval_path, commit):
    started = time.monotonic()
    p,v,a,prepared,original,old_private = checked(root,proposal_path,private_path,approval_path,commit)
    output, parent = Path(v['output_root']), Path(v['parent'])
    if read(output/'authorization_binding.json')['controller_pid'] != os.getppid() or read(output/'task_1_claim.json') != dict(controller_pid=os.getppid(),code_commit=commit):
        raise PermissionError('Live once-only recovery controller required')
    if os.environ.get('PYTHONHASHSEED') != '2029' or shutil.disk_usage(output).free < p['budget']['minimum_task_free_bytes']:
        raise RuntimeError('Recovery seed or storage admission differs')
    def deadline():
        if time.monotonic()-started > p['budget']['max_wall_seconds']:
            raise RuntimeError('Recovery one-hour cap; no retry')
    import sqlite3
    path = Path(old_private['terrain'])/'B6_static.npz'
    db = sqlite3.connect(output/'B8_static_source.sqlite')
    db.execute('CREATE TABLE jobs(id TEXT PRIMARY KEY,state TEXT)')
    db.execute("INSERT INTO jobs VALUES ('static','PENDING')"); db.commit()
    meter = SourceMeter(db,{str(path):dict(bytes=312828,sha=original['static_source_sha256']['B8'],job_id='static')},max_files=1,max_bytes=312828)
    meter.active = {path_key(path)}
    try:
        with meter.open(path,'rb') as stream:
            raw = stream.read()
        terrain = read(Path(old_private['terrain'])/'production_receipt.json')
        pack = unpack(raw,'B6',terrain)
        static_reads = meter.totals()
        with db:
            db.execute("UPDATE jobs SET state='COMPLETE'")
    finally:
        db.close()
    plan = PopulationPlan(prepared['private_inputs']['stage3_run'],prepared['private_inputs']['request'],root=root)
    state = B8E2Resume(dict(parent=str(parent/'B8_s2029'), decision_id=a['decision_id'],data_identity=p['data'],
                           checkpoint_sha256=CHECKPOINT_SHA,prior_updates=4320,replayed_updates=480))
    folder = output/'B8_s2029'
    PairedExecutor(plan,folder,decision=FormalDecision(a['decision_id'],2029,p['data']['population_sha256'],True,True,True),
                   kinds=('B8',),recovery=state,deadline=deadline,tail_factory=lambda:TerrainTail(pack),code_commit=commit,
                   model_factory=model_factory(pack,terrain['scalers'],modulation_limit=p['scientific_choices']['modulation_limit']),
                   lambda_q=2.0,origin_reference=p['scientific_choices']['origin_reference']['B8']).run(
        RemainingReaders(plan,prepared,a['decision_id'],allowed_models=('B8',),dynamic_transform=PhysicalDote(pack,DoteDefinition(**p['scientific_choices']['DOTE']))))
    if read(folder/'B8_train_09.json') != read(parent/'B8_s2029/B8_train_09.json'):
        raise RuntimeError('Replayed E9 training summary differs from the stopped trajectory')
    if query(folder/'updates.sqlite','SELECT model,state,COUNT(*),MIN(u),MAX(u) FROM updates GROUP BY model,state') != [('B8','RETURNED',480,3841,4320)]:
        raise RuntimeError('Recovery segment update closure differs')
    total_bytes, total_files = 312828, 1
    for role in ('train','dev'):
        receipt = read(folder/f'B8_{role}_reads_09/pass_receipt.json')
        actual = receipt['actual_reads']
        if actual['opened_files'] != receipt['expected_files'] or actual['delivered_bytes'] != receipt['expected_bytes'] or actual['reserved_bytes'] != receipt['expected_bytes']:
            raise RuntimeError('Full E9 source pass closure differs')
        total_bytes += actual['reserved_bytes']; total_files += actual['opened_files']
    if (total_bytes,total_files) != (p['budget']['new_source_bytes'],p['budget']['new_source_files']):
        raise RuntimeError('Exact recovery source closure differs')
    seal = read(folder/'B8_LAST_epoch_09.receipt.json')
    if seal['updates'] != 4320 or seal['loss_config'] != asdict(get_config('E2')) or seal['code_commit'] != commit:
        raise RuntimeError('Recovery fixed E9 identity differs')
    deadline()
    write(folder/'completion.json',dict(status='COMPLETE_TRAIN_AND_DEV_EVALUATION',model='B8',seed=2029,
          epochs=9,inherited_epochs=8,optimizer_updates=480,replayed_updates=480,model_effective_updates=4320,
          total_logical_source_bytes=total_bytes,total_logical_source_files=total_files,static_source_reads=static_reads,
          checkpoint=seal,loss_arm='E2',lambda_q=2.0,code_commit=commit,endpoint='FIXED_EPOCH_9_LAST'))


def execute(root, proposal_path, private_path, approval_path, commit):
    started = time.monotonic()
    p,v,a,_,_,_ = checked(root,proposal_path,private_path,approval_path,commit)
    output, parent = Path(v['output_root']), Path(v['parent'])
    if output.exists() or shutil.disk_usage(output.parent).free < p['budget']['minimum_initial_free_bytes']:
        raise PermissionError('Fresh recovery output and24GiB required')
    admission = resources(); output.mkdir(exist_ok=False)
    write(output/'authorization_binding.json',dict(approval=a,controller_pid=os.getpid(),admission=admission))
    active = None
    try:
        write(output/'task_1_claim.json',dict(controller_pid=os.getpid(),code_commit=commit))
        env = dict(os.environ,PYTHONHASHSEED='2029',CUBLAS_WORKSPACE_CONFIG=':4096:8',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONUTF8='1')
        command = [sys.executable,'-B',str(root/ENTRY),'worker','--proposal',str(proposal_path),
                   '--private-preparation',str(private_path),'--researcher-approval',str(approval_path)]
        with (output/'B8_console.log').open('xb') as log:
            active = subprocess.Popen(command,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=worker_creation_flags())
            try:
                code = active.wait(timeout=p['budget']['max_wall_seconds']-(time.monotonic()-started))
            except subprocess.TimeoutExpired:
                active.kill(); active.wait()
                raise RuntimeError('Recovery one-hour deadline; no retry')
        if code:
            raise RuntimeError('B8 E2 recovery worker failed; no retry')
        report_paths = dict(B7=parent/'B7_s2029/B7_development_09.json',B8=output/'B8_s2029/B8_development_09.json')
        write(output/'loss_pair_summary.json',loss_pair_summary(p,output,report_paths=report_paths))
        if time.monotonic()-started > p['budget']['max_wall_seconds']:
            raise RuntimeError('Recovery closure one-hour deadline')
        write(output/'completion.json',dict(status='COMPLETE_TRAIN_AND_DEV_EVALUATION',new_updates=480,
              replayed_updates=480,cumulative_updates=9120,new_logical_source_bytes=p['budget']['new_source_bytes'],
              new_logical_source_files=p['budget']['new_source_files'],code_commit=commit,loss_arm='E2',lambda_q=2.0))
    except BaseException as error:
        if active is not None and active.poll() is None:
            active.kill(); active.wait()
        write(output/'failure.json',dict(status='STOP_NO_AUTOMATIC_REPLAY',error=type(error).__name__+': '+str(error),partial_counts='SEE_PRESERVED_LEDGERS'))
        raise
