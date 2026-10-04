"""Explicit audit-only dispatch into the original, unmodified formal entry.

The in-memory main dispatch is recorded and approved; numerical functions are
never replaced. Original files and their historical SHA identities stay intact.
"""
import argparse,runpy,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT),str(ROOT/'scripts')]

def launch(argv=None):
    parser=argparse.ArgumentParser(description='Researcher-approved governance adapter')
    parser.add_argument('--model',choices=('B0_MATCHED','B1'),required=True)
    args,remaining=parser.parse_known_args(argv)
    import paired_phase_a_entry as frozen_entry
    from authorized_paired_phase_a_entry import main as audited_main
    # Only the orchestration main is redirected, never execute_update or any numerical helper.
    frozen_entry.main=audited_main
    name='train_b1_phase_a_v1.py' if args.model=='B1' else 'train_b0_matched_phase_a_v1.py'
    sys.argv=[str(ROOT/'scripts'/name),*remaining]
    runpy.run_path(str(ROOT/'scripts'/name),run_name='__main__')

if __name__=='__main__':launch()
