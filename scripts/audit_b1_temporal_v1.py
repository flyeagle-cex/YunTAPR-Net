"""Approved six-slot development audit only; this is not a B1 training entry."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from yuntapr.data.b1_temporal_audit import execute
def parse_arguments(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--definition',required=True,type=Path)
    parser.add_argument('--definition-sha256',required=True)
    parser.add_argument('--run-directory',required=True)
    parser.add_argument('--staging-root',required=True)
    return parser.parse_args(argv)

if __name__=='__main__':
    try:execute(parse_arguments())
    except Exception as error:
        print(json.dumps({'status':'B1_TEMPORAL_AUDIT_STOPPED','error_type':type(error).__name__}),file=sys.stderr)
        raise SystemExit(1) from None
