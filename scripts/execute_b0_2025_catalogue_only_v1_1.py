"""Execute only independently authorized B0 catalogue QC; freeze then STOP."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src')]
from yuntapr.evaluation.catalogue_execution_v1_1 import execute

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorization',type=Path,required=True)
    parser.add_argument('--authorization-sha256',required=True)
    parser.add_argument('--run-directory',type=Path,required=True)
    parser.add_argument('--staging-root',type=Path,required=True)
    args=parser.parse_args()
    try:execute(args)
    except Exception as error:
        print(json.dumps({'status':'CATALOGUE_STOPPED','error_type':type(error).__name__}),file=sys.stderr)
        raise SystemExit(1) from None
