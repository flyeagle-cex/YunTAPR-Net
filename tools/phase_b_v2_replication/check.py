"""Offline configuration/source audit only, with no torch or observation IO."""
from pathlib import Path
import argparse,json,os,sys
ROOT=Path(__file__).absolute().parents[2]
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--seed',type=int,choices=(2027,2028),required=True);args=parser.parse_args()
    os.environ['YUNTAPR_REPLICATION_SEED']=str(args.seed);sys.path.insert(0,str(ROOT/'src'))
    from yuntapr.experimental.phase_b_v2_multiseed_candidate.protocol import OUT,DB,validate_plan,validate_preparation,verify_release
    plan=validate_plan(json.loads((OUT/'config.json').read_bytes()))
    release=validate_preparation()
    try:verify_release()
    except PermissionError as e:gate=str(e)
    else:raise RuntimeError('PREPARATION_MUST_NOT_GRANT_EXECUTION')
    if 'torch' in sys.modules:raise RuntimeError('OFFLINE_CHECK_IMPORTED_TORCH')
    print(json.dumps(dict(seed=args.seed,config='PASS',source_sha256=release['source_sha256'],source_commit=release['source_commit'],
          run_count=len(plan['runs']),attempt_cap=plan['attempt_cap'],ledger_exists=DB.exists(),execution_gate=gate,
          raw_data_reads=0,optimizer_updates=0)))
if __name__=='__main__':main()
