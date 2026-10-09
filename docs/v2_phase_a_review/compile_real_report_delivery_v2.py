"""Compile and render a real completed-pair LaTeX delivery copy.

No model/raw reads and no package installation. Compilation is not visual
verification; the agent must inspect every rendered real-report page.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

from build_paired_decision_packet_v2 import FROZEN, KINDS

REPO = Path(__file__).resolve().parents[2]
XE = Path('F:/MiKTex/miktex/bin/x64/xelatex.exe')
POPLER = Path('C:/Users/chenerxiao/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin')


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def identity(path):
    path = Path(path).resolve()
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'absolute_local_path': str(path), 'bytes': path.stat().st_size, 'sha256': digest}


def validate_packet(packet):
    if packet['status'] != 'PAIRED_DECISION_PACKET_PDF_AND_PUBLICATION_PENDING' or \
            not packet['PAIR_PHASE_A_TRAINING_COMPLETE'] or not packet['FULL_2024_BEST_REVIEW_EXECUTED']:
        raise ValueError('Only real completed paired review may generate the report')
    if set(packet['models']) != set(KINDS) or any(packet['frozen_identities'][k] != v for k, v in FROZEN.items()):
        raise ValueError('Paired model/frozen identity mismatch')
    if packet['2025_RAW_ACCESS'] or packet['2025_PIXELS_READ'] or packet['V2_PHASE_B_AUTHORIZED'] or \
            any(packet[k] != 0 for k in ('PACKET_GENERATION_FORWARD_CALLS', 'PACKET_GENERATION_BACKWARD_CALLS',
                                        'PACKET_GENERATION_OPTIMIZER_STEPS', 'PACKET_GENERATION_RAW_SOURCE_OPENS')):
        raise ValueError('Packet operation scope violation')
    for model in packet['models'].values():
        metrics = model['metrics']
        if (metrics['scenes'], metrics['forwards'], metrics['N_valid']) != (10501, 1313, 36018430) or \
                model['early_stopping']['termination_reason'] == 'NOT_TERMINATED':
            raise ValueError('Partial validation/training cannot generate the final report')


def save(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False); stream.write('\n')


def command(argv, cwd, prefix):
    started = time.monotonic()
    with prefix.with_suffix('.stdout.log').open('xb') as out, prefix.with_suffix('.stderr.log').open('xb') as err:
        result = subprocess.run([str(x) for x in argv], cwd=cwd, stdout=out, stderr=err)
    record = {'command': [str(x) for x in argv], 'exit_code': result.returncode,
              'seconds': time.monotonic() - started,
              'stdout': identity(prefix.with_suffix('.stdout.log')),
              'stderr': identity(prefix.with_suffix('.stderr.log'))}
    if result.returncode:
        save(prefix.with_suffix('.failure.json'), record)
        raise RuntimeError('Report command failed; no package installation or automatic retry')
    return record


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--packet-root', type=Path, required=True)
    p.add_argument('--delivery-name', default='pdf_delivery_v1')
    args = p.parse_args()
    root = args.packet_root.resolve()
    if not root.is_relative_to(REPO / 'docs/v2_phase_a_review/paired_packets'):
        raise PermissionError('Real independent packet root required; fixtures rejected')
    if not re.fullmatch(r'pdf_delivery_v\d+', args.delivery_name):
        raise PermissionError('Independent versioned delivery directory required')
    packet_path = root / 'paired_comparison_packet.json'
    packet = load(packet_path); validate_packet(packet)
    source = root / 'V2_PAIRED_PHASE_A_REVIEW.tex'
    manifest = load(root / 'packet_manifest.json')
    ref = next(x for x in manifest['artifacts'] if Path(x['absolute_local_path']).resolve() == source)
    if identity(source) != ref:
        raise ValueError('Original packet LaTeX changed')
    out = root / args.delivery_name
    if out.exists():
        raise FileExistsError('Do not overwrite an earlier report attempt')
    for binary in (XE, POPLER / 'pdfinfo.exe', POPLER / 'pdftoppm.exe'):
        if not binary.is_file():
            raise FileNotFoundError('Existing report runtime missing; do not install: ' + str(binary))
    formatter = REPO / 'docs/v2_phase_a_review/prepare_report_layout_copy_v1.py'
    subprocess.run([sys.executable, '-B', str(formatter), '--source', str(source), '--output', str(out)], check=True)
    try:
        passes = []
        for i in (1, 2):
            passes.append(command([XE, '-disable-installer', '-disable-write18', '-dont-parse-first-line', '-halt-on-error',
                                   '-interaction=nonstopmode', '-output-directory', '.',
                                   'V2_PAIRED_PHASE_A_REVIEW.tex'], out, out / f'compile_pass_{i}'))
        log = (out / 'V2_PAIRED_PHASE_A_REVIEW.log').read_text(encoding='utf-8', errors='replace')
        overfull = log.count('Overfull \\hbox') + log.count('Overfull \\vbox')
        if overfull or re.search(r'^! ', log, re.M):
            raise RuntimeError('Real report layout/error requires an independent repair copy')
        pdf = out / 'V2_PAIRED_PHASE_A_REVIEW.pdf'
        info_record = command([POPLER / 'pdfinfo.exe', pdf], out, out / 'pdfinfo')
        info = (out / 'pdfinfo.stdout.log').read_text(encoding='utf-8', errors='replace')
        pages = int(re.search(r'^Pages:\s+(\d+)', info, re.M).group(1))
        render = command([POPLER / 'pdftoppm.exe', '-r', '100', '-png', pdf, out / 'preview'],
                         out, out / 'render')
        previews = sorted(out.glob('preview-*.png'), key=lambda x: int(x.stem.rsplit('-', 1)[1]))
        if len(previews) != pages:
            raise RuntimeError('Not every real PDF page was rendered')
        if identity(source) != ref:
            raise ValueError('Original packet source changed during report compilation')
        audit = {'status': 'REAL_PAIRED_REPORT_COMPILE_AND_RENDER_PASS_VISUAL_PENDING',
                 'created_utc': datetime.now(timezone.utc).isoformat(), 'TEST_FIXTURE_ONLY': False,
                 'packet': identity(packet_path), 'original_packet_latex': ref,
                 'editable_latex': identity(out / source.name), 'pdf': identity(pdf),
                 'compile_passes': passes, 'overfull_box_count': overfull,
                 'pdfinfo': info_record, 'render': render, 'page_count': pages,
                 'pages': [{'page': i + 1, 'rendered_image': identity(path), 'visually_checked': False}
                           for i, path in enumerate(previews)],
                 'layout_manifest': identity(out / 'layout_copy_manifest.json'),
                 'compiler_script': identity(Path(__file__)), 'formatter_script': identity(formatter),
                 'software': {'xelatex': identity(XE), 'pdfinfo': identity(POPLER / 'pdfinfo.exe'),
                              'pdftoppm': identity(POPLER / 'pdftoppm.exe')},
                 'package_installation_allowed': False, 'shell_escape_allowed': False,
                 'PDF_VISUALLY_VERIFIED': False, 'RAW_SOURCE_OPENS': 0, 'OPTIMIZER_STEPS': 0,
                 '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0}
        save(out / 'compile_audit.json', audit)
        print(json.dumps({'status': audit['status'], 'output': str(out), 'pages': pages}, ensure_ascii=False))
    except BaseException as exc:
        save(out / 'report_compile_failure.json', {'status': 'REPORT_COMPILE_FAILED_STOP',
             'error': repr(exc), 'automatic_retry': False, 'original_source_unchanged': identity(source) == ref})
        raise


if __name__ == '__main__':
    main()
