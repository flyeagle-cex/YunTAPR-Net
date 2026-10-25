"""Default: metadata-only preparation. --execute requires a final start command."""
from pathlib import Path
import argparse,json,os,sys
ROOT=Path(__file__).resolve().parents[2];sys.dont_write_bytecode=True;sys.path.insert(0,str(ROOT/'src'))


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true')
    parser.add_argument('--preparation',type=Path,required=True);parser.add_argument('--stage3-run',type=Path);parser.add_argument('--request',type=Path);parser.add_argument('--mask-read-ledger',type=Path)
    parser.add_argument('--output',type=Path);parser.add_argument('--start-authorization-id');args=parser.parse_args(argv)
    if not args.execute:
        if not all((args.stage3_run,args.request,args.mask_read_ledger)) or args.output or args.start_authorization_id:parser.error('Preparation requires metadata inputs only; no start ID/output experiment')
        os.environ['CUDA_VISIBLE_DEVICES']=''
        def audit(event,values):
            if event=='open' and isinstance(values[0],(str,bytes,os.PathLike)) and os.fsdecode(values[0]).lower().endswith(('.nc','.hgt','.hgt.zip','.hdf5','.h5')):raise PermissionError('Preparation forbids raw source opens')
        sys.addaudithook(audit)
    else:
        if not args.output or not args.start_authorization_id:parser.error('--execute needs final researcher start authorization and new output')
        if os.environ.get('PYTHONHASHSEED')!='2029':parser.error('Set PYTHONHASHSEED=2029 before Python startup')
    os.environ['CUBLAS_WORKSPACE_CONFIG']=':4096:8';os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
    from yuntapr.experimental.core_innovation.stage4.launch import preparation,execute
    from yuntapr.experimental.core_innovation.stage4.data import PopulationPlan
    if args.execute:
        result=execute(args.preparation,args.output,start_authorization_id=args.start_authorization_id)
    else:
        if not args.preparation.resolve().is_relative_to(ROOT/'docs/core_stage4/.local'):raise PermissionError('Private preparation must remain in ignored scope')
        plan=PopulationPlan(args.stage3_run,args.request,root=ROOT);result=preparation(plan,args.stage3_run,args.request,args.mask_read_ledger)
        args.preparation.parent.mkdir(parents=True,exist_ok=True)
        with args.preparation.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
        result={k:result[k] for k in ('status','config','budget','preparation_sha256','raw_source_opens_during_preparation','optimizer_updates','final_start_authorized')}
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
