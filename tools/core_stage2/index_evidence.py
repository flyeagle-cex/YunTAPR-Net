"""Index existing delta outcomes and redact publication copies, without retesting."""
from pathlib import Path
import argparse, ast, hashlib, json, re, sys
ROOT = Path(__file__).resolve().parents[2]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path, default=ROOT/'docs/core_stage2/evidence_index.json')
    args = parser.parse_args()
    latest = {}; runs = []
    for folder in sorted((ROOT/'docs/core_stage2/test_runs').iterdir()):
        summary = json.loads((folder/'summary.json').read_text(encoding='utf-8'))
        original = (folder/'unittest.log').read_text(encoding='utf-8')
        public = original.replace(str(ROOT), '[REPO]').replace(sys.prefix, '[PYTHON_RUNTIME]')
        published = folder/'unittest.public.log'
        if published.exists() and published.read_text(encoding='utf-8') != public:
            raise ValueError('Existing public log differs; preserve it and investigate')
        if not published.exists(): published.write_text(public, encoding='utf-8', newline='\n')
        for name, case, outcome in re.findall(r'^([^\s]+) \(([^)]+)\) \.\.\. (ok|FAIL|ERROR|skipped[^\n]*)$', public, flags=re.M):
            identity = case if case.endswith('.'+name) else case+'.'+name
            latest[identity] = dict(outcome=outcome, evidence=published.relative_to(ROOT).as_posix())
        runs.append(dict(folder=folder.relative_to(ROOT).as_posix(), tests=summary['tests'],
                         failures=summary['failures'], errors=summary['errors']))
    expected = set()
    for file in (ROOT/'tests/core_stage2').glob('test_*.py'):
        tree = ast.parse(file.read_text(encoding='utf-8'))
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                for function in node.body:
                    if isinstance(function, ast.FunctionDef) and function.name.startswith('test_'):
                        expected.add(file.stem+'.'+node.name+'.'+function.name)
    if expected != set(latest) or any(r['outcome'] != 'ok' for r in latest.values()):
        raise ValueError('Missing or unresolved delta test evidence')
    files = list((ROOT/'src/yuntapr/experimental/core_innovation/stage2').glob('*.py')) + list((ROOT/'tests/core_stage2').glob('test_*.py'))
    report = dict(status='PASS_ALL_LATEST_DELTA_OUTCOMES', unique_delta_tests=len(latest), inherited_52_rerun=False,
        outcomes=latest, all_runs_including_failures=runs, optimizer_updates=0, raw_2025_reads=0,
        source_sha256={p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        limitation='This index inherits unchanged passing checks; it is not a newly rerun full suite. Synthetic engineering correctness does not establish meteorological skill.')
    output = args.output.resolve()
    if not output.is_relative_to(ROOT/'docs/core_stage2'): raise PermissionError('Scoped public index required')
    if output.exists(): raise FileExistsError('Use a new evidence index for a later source revision')
    output.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(unique_delta_tests=len(latest), test_runs=len(runs), status=report['status']), indent=2))
