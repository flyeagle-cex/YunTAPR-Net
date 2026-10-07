from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
if __name__=='__main__':
    import argparse
    from paired_phase_a_v2.publication import watch
    parser=argparse.ArgumentParser();parser.add_argument('--repository',required=True)
    parser.add_argument('--public',required=True);parser.add_argument('--stop-file',required=True)
    args=parser.parse_args();watch(args.repository,args.public,args.stop_file)
