"""Prepare without raw reads; execute only an explicitly approved one-time replay."""
from pathlib import Path
import argparse,json,os,sys
ROOT=Path(__file__).resolve().parents[2];sys.dont_write_bytecode=True;sys.path.insert(0,str(ROOT/'src'))


def main():
    p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true')
    p.add_argument('--parent',type=Path);p.add_argument('--preparation',type=Path)
    p.add_argument('--recovery-request',type=Path,required=True);p.add_argument('--output',type=Path)
    p.add_argument('--authorization-id');p.add_argument('--approved-update-cap',type=int)
    p.add_argument('--approved-read-cap',type=int);p.add_argument('--approved-file-cap',type=int);a=p.parse_args()
    if not a.recovery_request.resolve().is_relative_to(ROOT/'docs/core_stage4/.local'):p.error('Recovery request must stay in private local scope')
    os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1';os.environ['CUBLAS_WORKSPACE_CONFIG']=':4096:8'
    if not a.execute:
        if not a.parent or not a.preparation or any((a.output,a.authorization_id,a.approved_update_cap,a.approved_read_cap,a.approved_file_cap)):p.error('Preparation accepts parent metadata only')
        os.environ['CUDA_VISIBLE_DEVICES']=''
        def audit(event,values):
            if event=='open' and isinstance(values[0],(str,bytes,os.PathLike)) and os.fsdecode(values[0]).lower().endswith(('.nc','.hgt','.hgt.zip','.hdf5','.h5')):raise PermissionError('Recovery preparation forbids weather-source reads')
        sys.addaudithook(audit)
        from yuntapr.experimental.core_innovation.stage4.recovery import build_request,write
        request=build_request(a.parent,a.preparation,ROOT);a.recovery_request.parent.mkdir(parents=True,exist_ok=True);write(a.recovery_request,request)
        result={k:request[k] for k in ('status','prior_updates','inherited_updates','new_updates','replayed_updates','cumulative_update_cap','cumulative_read_cap','cumulative_file_cap','source_verification_bytes','request_sha256')}
    else:
        if not a.output or os.environ.get('PYTHONHASHSEED')!='2029':p.error('Fresh output and PYTHONHASHSEED=2029 required')
        from yuntapr.experimental.core_innovation.stage4.recovery import execute
        result=execute(a.recovery_request,a.output,authorization_id=a.authorization_id,approved_update_cap=a.approved_update_cap,approved_read_cap=a.approved_read_cap,approved_file_cap=a.approved_file_cap,root=ROOT)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
