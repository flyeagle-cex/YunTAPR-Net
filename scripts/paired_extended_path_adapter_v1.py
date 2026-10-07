"""Explicit filesystem adapter: accept PathLike/string SHA inputs identically.

The original project SHA implementation and every numerical function stay
unchanged. The adapter only constructs pathlib.Path before the same read-only
SHA call and dispatches an existing authorized entrypoint.
"""
from pathlib import Path
import argparse, runpy, sys

def path_sha256(value):
    from yuntapr.contracts.loader import sha256
    return sha256(Path(value))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--script',required=True,type=Path)
    parser.add_argument('arguments',nargs=argparse.REMAINDER)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    sys.path[:0]=[str(root/'src'),str(root),str(root/'scripts')]
    script=args.script.resolve()
    allowed_workspace=root.parent.resolve()
    if not script.is_relative_to(root.resolve()) and script.parent!=allowed_workspace:
        raise PermissionError('Only registered project/workspace entrypoints can be dispatched')
    import paired_extended_v1 as extended
    extended.sha256=path_sha256
    remainder=args.arguments[1:] if args.arguments[:1]==['--'] else args.arguments
    sys.argv=[str(script),*remainder]
    runpy.run_path(str(script),run_name='__main__')

if __name__=='__main__':main()
