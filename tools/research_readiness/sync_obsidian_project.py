"""Publish named public research receipts and a progress note to an Obsidian project."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
BUNDLES = ('20261115_v7_followup', '20261115_physical_pinball_prepare',
           '20261115_core_innovation_repair')


def fingerprint(data):
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    project = args.project.resolve()
    index = project / '极端降水预测.md'
    original = index.read_bytes()
    snapshot_name = '进度快照_2026-11-15_四项创新主线与首轮修复.md'
    source = ROOT / 'docs/research_readiness/20261115_core_innovation_repair/OBSIDIAN_SNAPSHOT.md'
    snapshot = source.read_bytes()
    copies = {}
    for bundle in BUNDLES:
        destination = project / '资料快照' / bundle
        destination.mkdir(parents=True, exist_ok=True)
        for path in sorted((ROOT / 'docs/research_readiness' / bundle).glob('*.json')):
            if path.resolve() == args.receipt.resolve():
                continue
            data = path.read_bytes()
            json.loads(data)
            target = destination / path.name
            target.write_bytes(data)
            assert target.read_bytes() == data
            copies[f'{bundle}/{path.name}'] = fingerprint(data)
    (project / snapshot_name).write_bytes(snapshot)
    assert (project / snapshot_name).read_bytes() == snapshot
    text = original.decode('utf-8-sig')
    text = re.sub(r'^updated:.*$', 'updated: 2026-11-15', text, count=1, flags=re.M)
    text = re.sub(r'^status:.*$', 'status: core-innovation-repair-in-progress', text, count=1, flags=re.M)
    marker = '<!-- CODEX_CURRENT_RESEARCH_STATUS -->'
    end = '<!-- /CODEX_CURRENT_RESEARCH_STATUS -->'
    current = (f'{marker}\n## 最新研究状态 · 2026-11-15\n\n'
               '研究者固定四项创新主线。PHYS20九轮完成且八门失败，当前优先修复物理输入契约和山区强雨证据保存。'
               '本轮人工检查通过，科学验收仍为NOT_VERIFIED。\n\n'
               f'详见 [[{snapshot_name[:-3]}]]。\n{end}\n\n')
    if marker in text:
        text = re.sub(re.escape(marker) + r'.*?' + re.escape(end) + r'\s*', current, text, count=1, flags=re.S)
    else:
        text = text.replace('## 当前状态', '## 2026-11-12 当前状态（历史快照）', 1)
        heading = text.index('\n', text.index('# 极端降水预测')) + 1
        text = text[:heading] + '\n' + current + text[heading:]
    # Preserve the prior index before replacing only its current navigation block.
    backup = ROOT / 'docs/research_readiness/.local/obsidian_sync_20261115'
    backup.mkdir(parents=True, exist_ok=True)
    backup_file = backup / (hashlib.sha256(original).hexdigest() + '.md')
    if not backup_file.exists():
        backup_file.write_bytes(original)
    if index.read_bytes() != original:
        raise RuntimeError('Obsidian index changed during publication; retain concurrent edits')
    temporary = index.with_name(index.name + '.codex-sync.tmp')
    temporary.write_text(text, encoding='utf-8', newline='\n')
    temporary.replace(index)
    result = dict(status='PUBLISHED_AND_READBACK_HASH_VERIFIED', date='2026-11-15',
                  snapshot_filename=snapshot_name, snapshot_identity=fingerprint(snapshot),
                  project_index_identity=fingerprint(index.read_bytes()),
                  previous_index_identity=fingerprint(original), previous_index_backup_preserved=True,
                  current_status_updated=True, historical_sections_preserved=True,
                  copied_public_receipts=copies)
    with args.receipt.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'status': result['status'], 'public_receipts': len(copies), 'snapshot': snapshot_name}, ensure_ascii=True))


if __name__ == '__main__':
    main()
