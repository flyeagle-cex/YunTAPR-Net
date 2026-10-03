"""Count a six-input enc0 CPU fixture; no callable B1 model or forward."""
import argparse
import gc
from pathlib import Path
import sys
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from yuntapr.contracts.loader import sha256
from yuntapr.evaluation import catalogue_gate_b0 as gate
import torch
from yuntapr.models.b0 import B0Model
from yuntapr.models.blocks import ResidualBlock

def denied(*args,**kwargs):raise PermissionError('Parameter fixture prohibits forward and checkpoint operations')

def inventory(output):
    with gate.PreflightSourceGuard() as source,gate.legacy.FinalInferenceGuard(),\
         patch.object(torch.nn.Module,'_call_impl',denied),patch.object(torch,'load',denied),patch.object(torch,'save',denied):
        with torch.random.fork_rng(devices=[]):
            model=B0Model()
            before={n:{'shape':list(p.shape),'numel':p.numel()} for n,p in model.named_parameters()}
            model.backbone.enc0=ResidualBlock(6,48,8)
            torch.nn.init.zeros_(model.backbone.enc0.skip.weight);torch.nn.init.zeros_(model.backbone.enc0.skip.bias)
            after={n:{'shape':list(p.shape),'numel':p.numel()} for n,p in model.named_parameters()}
            assert set(before)==set(after)
            changed={n:{'b0':before[n],'six_channel_candidate':after[n]} for n in before if before[n]!=after[n]}
            assert set(changed)=={'backbone.enc0.conv1.weight','backbone.enc0.skip.weight'}
            total=sum(p['numel'] for p in before.values());candidate=sum(p['numel'] for p in after.values())
            assert total==4329361 and candidate==4331761 and candidate-total==2400
            evidence={'status':'MEASURED_ISOLATED_PARAMETER_FIXTURE_ONLY','TEST_FIXTURE_ONLY':True,
                'B0_actual_parameters':total,'B1_six_channel_candidate_parameters':candidate,
                'delta_parameters':candidate-total,'delta_percent':100*(candidate-total)/total,
                'changed_parameter_tensors':changed,'unchanged_parameter_tensor_count':len(before)-len(changed),
                'parameter_names_identical':True,'skip_initialization':'zeros; identical engineering policy to B0',
                'B1_FORMAL_MODEL_IMPLEMENTED':False,'FORWARD_CALLS':0,'CHECKPOINT_LOADS':0,
                'OPTIMIZER_STEPS':0,'BACKWARD_CALLS':0,'2025_RAW_PIXELS_READ':0,'raw_source_open_events':source.raw_open_events,
                'source_sha256':{n:sha256(ROOT/n) for n in ('src/yuntapr/models/b0.py','src/yuntapr/models/backbone_b0.py',
                    'src/yuntapr/models/blocks.py','src/yuntapr/models/probability_heads.py')},
                'count_script_sha256':sha256(Path(__file__)),'created_utc':gate.now()}
            del model,before,after;gc.collect()
        gate.save(gate.safe_artifact_path(output),evidence)
    return evidence

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    value=inventory(parser.parse_args().output)
    print({'B0_parameters':value['B0_actual_parameters'],'B1_candidate_parameters':value['B1_six_channel_candidate_parameters'],
        'delta':value['delta_parameters'],'raw_source_open_events':value['raw_source_open_events']})
