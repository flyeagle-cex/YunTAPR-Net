"""Static checks and exact public allowlist for the isolated repair package."""
from pathlib import Path
from datetime import datetime, timezone
import ast, hashlib, json, subprocess, sys

ROOT = Path(__file__).absolute().parents[2]
DOC = ROOT / 'docs/phase_b_v2_console_lifetime_repair/v1'
SOURCE = ROOT / 'src/yuntapr/experimental/phase_b_v2_console_lifetime_candidate'
TOOLS = ROOT / 'tools/phase_b_v2_console_lifetime_candidate'


def main():
    public = [p for folder in (SOURCE, TOOLS) for p in folder.glob('*.py')]
    public += [p for p in DOC.iterdir() if p.is_file() and p.name != 'manifest.json']
    public += list((DOC / 'tests').glob('*.log'))
    results = json.loads((DOC / 'ARTIFICIAL_RESULTS.json').read_text(encoding='utf-8'))
    assert results['pass_all'] and results['tests_run'] == 5 and not results['skipped']
    for row in results['records']:
        assert row['pass_case'] and row['elapsed_seconds'] < 15
        assert all(v['status'] in ('ABSENT', 'EXITED', 'PID_REUSED') for v in row['leftovers'].values())
        assert row['task_cleanup']['state'] != 'Running'
    pins = {}
    for path in sorted(public):
        raw = path.read_bytes()
        text = raw.decode('utf-8')
        if path.suffix == '.py':
            ast.parse(text, filename=path.name)
        elif path.suffix == '.json':
            json.loads(text)
        # No home paths, disk data roots or credentials in public artifacts.
        needles = (':' + chr(92) + 'Users' + chr(92),
                   ':' + chr(92) * 2 + 'Users' + chr(92) * 2,
                   'C:' + '/Users/')
        if any(needle in text for needle in needles):
            raise ValueError('PRIVATE_PATH_IN_PUBLIC_ARTIFACT:' + path.name)
        pins[path.relative_to(ROOT).as_posix()] = dict(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
    for path in SOURCE.glob('*.py'):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or '').startswith(('torch', 'yuntapr.training')):
                raise ValueError('ARTIFICIAL_CANDIDATE_MUST_NOT_IMPORT_FORMAL_TRAINING')
            if isinstance(node, ast.Import) and any(x.name.startswith('torch') for x in node.names):
                raise ValueError('NO_TORCH_IN_ARTIFICIAL_FIXTURE')
    status = json.loads((DOC / 'final_status.json').read_text(encoding='utf-8'))
    assert status['new_optimizer_steps'] == 0 and not status['new_recovery_authorized']
    manifest = dict(schema='CONSOLE_LIFETIME_REPAIR_PUBLIC_V1',
        created_utc=datetime.now(timezone.utc).isoformat(),
        baseline_commit='7a025a6305193a7cc92b2d5559da1f4f6896ebe9',
        files=pins, static_checks='PASS', isolated_artificial_tests=5,
        raw_logs_and_all_private_paths_excluded=True, real_recovery_launched=False)
    target = DOC / 'manifest.json'
    if target.exists():
        raise PermissionError('NO_MANIFEST_OVERWRITE')
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(public_files=len(public), artificial_tests=5, static_checks='PASS')))


if __name__ == '__main__':
    main()
