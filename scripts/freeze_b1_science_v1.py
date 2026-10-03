"""Metadata formalization or approved 2023-only B13 scaler fit; never training."""
import argparse,json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from yuntapr.data.b1_scientific_freeze import prepare,fit
def main():
    parser=argparse.ArgumentParser();parser.add_argument('operation',choices=('prepare','fit'))
    parser.add_argument('--run-directory',required=True,type=Path);parser.add_argument('--staging-root',type=Path)
    args=parser.parse_args()
    if args.operation=='fit' and args.staging_root is None:parser.error('--staging-root is required for fit')
    print(json.dumps(prepare(args.run_directory) if args.operation=='prepare' else fit(args.run_directory,args.staging_root)),flush=True)
if __name__=='__main__':main()
