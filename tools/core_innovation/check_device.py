"""Single tiny synthetic device probe; no optimizer, weather data or training loop."""
from pathlib import Path
import argparse,json,os,subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
sys.dont_write_bytecode=True;sys.path.insert(0,str(ROOT/'src'))
os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'


def main():
    p=argparse.ArgumentParser();p.add_argument('--device',choices=('cpu','cuda:0'),required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    output=args.output.resolve()
    if not output.is_relative_to(ROOT/'docs/core_innovation'):raise ValueError('Evidence must stay in the development directory')
    if args.device=='cuda:0':
        free=int(subprocess.check_output(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True).strip().splitlines()[0])
        processes=subprocess.check_output(['nvidia-smi','--query-compute-apps=process_name','--format=csv,noheader,nounits'],text=True)
        if free<6144 or any('python' in line.lower() for line in processes.splitlines()):
            raise RuntimeError('SKIP_CUDA_INSUFFICIENT_HEADROOM_OR_PYTHON_COMPUTE_PROCESS')
    import numpy as np
    import torch
    from yuntapr.experimental.core_innovation.grid import GridSpec
    from yuntapr.experimental.core_innovation.dtfm import MaskedTerrainModulation
    torch.set_num_threads(1)
    device=torch.device(args.device);grid=GridSpec([25.,25.01,25.02],[101.,101.01,101.02])
    module=MaskedTerrainModulation(feature_channels=[2],condition_channels=[1],modulation_limit=.25).to(device)
    # Nonzero candidate weights only exercise condition gradients in this fixture.
    with torch.no_grad():module.projections[0].weight.fill_(.01)
    x=torch.ones((1,2,3,3),device=device,requires_grad=True)
    c=torch.ones((1,1,3,3),device=device,requires_grad=True);mask=torch.ones((1,1,3,3),device=device,dtype=torch.bool)
    y=module([x],[c],[mask],[mask],feature_grids=[grid],condition_grids=[grid]).values[0]
    y.sum().backward()
    if not all(bool(torch.isfinite(t).all()) for t in (y,x.grad,c.grad,module.projections[0].weight.grad)):raise AssertionError('Synthetic device forward/backward nonfinite')
    if not bool((c.grad!=0).any()):raise AssertionError('Condition gradient did not propagate')
    if device.type=='cuda':torch.cuda.synchronize()
    result={'scope':'ONE_TINY_SYNTHETIC_DEVICE_PROBE_NOT_FORMAL_TRAINING','device':str(device),'status':'PASS','shape':list(y.shape),
            'finite_feature_condition_and_parameter_gradients':True,'optimizer_updates':0,'weather_payload_reads':0,'weights_loaded':False,
            'peak_allocated_bytes':torch.cuda.max_memory_allocated() if device.type=='cuda' else None,'torch':torch.__version__}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
