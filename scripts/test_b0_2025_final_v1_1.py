"""v1.1 Final Test entrypoint; no execution without post-freeze researcher grant."""
import argparse
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'scripts')]

def formal(args):
    from yuntapr.evaluation.final_test_b0_v1_1 import formal as execute
    return execute(args)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['run'])
    parser.add_argument('--authorization',type=Path);parser.add_argument('--authorization-sha256')
    parser.add_argument('--candidate-catalogue',type=Path)
    parser.add_argument('--eligible-population',type=Path)
    parser.add_argument('--catalogue-freeze-record',type=Path)
    args=parser.parse_args()
    formal(args)
