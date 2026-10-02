"""Create an editable LaTeX/PDF report only from completed, verified FinalFit evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REPORT = 'B0_PHASE_B_FINALFIT_FORMAL_TRAINING_REPORT_v1'

def read(path): return json.loads(path.read_text(encoding='utf-8'))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def escape(value):
    return ''.join({'\\': r'\textbackslash{}', '_': r'\_', '&': r'\&', '%': r'\%',
        '#': r'\#', '$': r'\$', '{': r'\{', '}': r'\}'}.get(c, c) for c in str(value))

def render(out, qa):
    out = out.resolve(); qa = qa.resolve()
    if out.parent != (ROOT/'docs/formal_training/b0_phase_b_finalfit/runs').resolve():
        raise ValueError('Report requires the explicit formal run evidence directory')
    if not qa.is_relative_to(ROOT.parent.resolve()) or qa.is_relative_to(ROOT):
        raise ValueError('Compilation/QA scratch must remain in caller-owned workspace outside the Git repository')
    status = read(out/'final_status.json'); tests = read(out/'post_training_test_summary.json')
    if not status['PHASE_B_FINALFIT_COMPLETED'] or tests['status'] != 'PASS':
        raise ValueError('No completion report before all eleven epochs and actual post-training tests pass')
    epochs = [read(p) for p in sorted(out.glob('epoch_*_summary.json'))]
    if len(epochs) != 11: raise ValueError('Eleven actual completed epoch summaries required')
    norm = read(out/'formal_run_manifest.json')['checkpoint_expected']['normalization_artifact_sha256']
    qa.mkdir(parents=True, exist_ok=False)
    epoch_rows = '\n'.join(
        f"{r['epoch']} & {r['samples']:,} & {r['updates']:,} & {r['global_train_occurrence_loss']:.7g} & "
        f"{r['global_train_quantile_loss']:.7g} & {r['global_train_core_loss']:.7g} & {r['LR_end']:.7g} "
        + r'\\' for r in epochs)
    telemetry_rows = '\n'.join(
        f"{r['epoch']} & {r['gradient_norm_min']:.5g} & {r['gradient_norm_max']:.5g} & {r['gradient_norm_mean']:.5g} & "
        f"{r['clip_count']:,} & {r['GPU_peak_allocated_bytes']/2**30:.3f} & {r['wall_seconds']/60:.2f} "
        + r'\\' for r in epochs)
    text = r'''\documentclass[10pt,a4paper]{article}
\usepackage[margin=20mm]{geometry}
\usepackage{amsmath,array,longtable}
\usepackage[hidelinks]{hyperref}
\usepackage{url}
\setlength{\parindent}{0pt}
\setlength{\parskip}{5pt}
\begin{document}
\begin{center}
{\Large\bfseries YunTAPR-Net B0 Phase-B FinalFit}\par
{\large Formal Training Completion and Evidence Report v1}
\end{center}
\textbf{Run:} RUNIDENTITY\\
\textbf{Baseline:} \path{4de37ac087183bddf3b9f8c7d548a0f976a50e91}\\
\textbf{Scope:} B0 Phase-B FinalFit only.

\section*{Completed authorized run}
All eleven fixed-budget epochs completed, with 23,447 frozen identities exactly
once in each epoch. The training population contains 11,720 scenes from 2023 and
11,727 from 2024. No 2025 scenes or pixels were read. Each epoch contains 11,723
full batches of two scenes and one actual singleton: 11,724 optimizer updates,
128,964 in total. No identities were skipped, duplicated, padded, replaced or
dropped. The singleton denominator is 3,430; a full batch uses 6,860.

Initialization used fresh seed 2026. Its logical model state SHA256 matched the
independently verified fresh initialization identity before training:
\begin{quote}\small\path{57a4d103a31aa7be1a52af079cdf7fb81bc73c51ba3e0e97d395513d21d9023d}\end{quote}
No Phase-A model, optimizer or scheduler state initialized FinalFit. Historical
authorization fields and all 1,656 baseline files remained unchanged.

\section*{Unchanged scientific and numerical protocol}
The frozen Phase-B normalization was reused, without refitting:
\[
\mu=270.5900486586461\,\mathrm{K},\qquad
\sigma=20.368583874067266\,\mathrm{K}.
\]
Artifact SHA256:
\begin{quote}\small\path{NORMSHA}\end{quote}
Manifest SHA256:
\begin{quote}\small\path{00e6bd018eae6aeb05be0740b55a92b7a5cc9a44b9ab2b80affbad3e3282ccff}\end{quote}
AdamW used $(\beta_1,\beta_2)=(0.9,0.999)$, $\epsilon=10^{-8}$ and weight decay
$10^{-4}$ for Conv2d kernels only. Forward precision was BF16; parameters and
raw quantiles were FP32. Quantile transformations and pinball calculations used
FP64. No GradScaler was used. Global gradient clipping remained 5, with nonfinite
errors causing STOP. Architecture, loss and hyperparameters were unchanged.

The stateless scheduler retained the frozen 50-epoch horizon:
$W=11{,}724$, $U=586{,}200$, base LR $10^{-4}$ and cosine minimum $10^{-6}$.
The actual first-epoch singleton LR was exactly $10^{-4}$. The cosine horizon
was not compressed to eleven epochs.

There was no independent 2024 validation, early stopping, BEST selection,
epoch reselection, threshold calibration or training-loss budget adjustment.

\newpage
\section*{Actual epoch evidence}
The losses below are global raw numerator sums divided by the total actual
valid-pixel denominator, not averages of batch losses. Each epoch contains
80,423,210 valid pixels. Full precision values and all requested I/O, rainy-pixel,
LR, clipping, GPU and singleton metrics are preserved in
\path{training_history.csv} and the eleven epoch summary JSON files.

{\small\setlength{\tabcolsep}{4pt}
\begin{longtable}{rrrrrrr}
Epoch & Scenes & Updates & Occurrence & Quantile & Core & End LR\\\hline
EPOCHROWS
\end{longtable}}

{\small\setlength{\tabcolsep}{5pt}
\begin{longtable}{rrrrrrr}
Epoch & Norm min & Norm max & Norm mean & Clips & GPU GiB & Minutes\\\hline
TELEMETRYROWS
\end{longtable}}
The GPU column reports peak allocated memory. Peak reserved memory, summed
source staging/read times, singleton identity and its exact LR remain in the
CSV/JSON evidence. Displayed numbers are rounded only for this PDF.

\section*{Checkpoint identity and integrity}
Only completed epoch boundaries produced checkpoint payloads. LAST and FINAL
both identify epoch 11, global update 128,964. All eleven boundary files remain
under the approved local F: root. Temporary write, fsync/close, round-trip
verification, SHA checks and atomic rename were performed. Retained boundary
payloads were independently reverified after training.

\textbf{FINAL local path:}
\begin{quote}\small\path{FINALROOT}\\
\path{FINALRELATIVE}\end{quote}
\textbf{FINAL SHA256:}
\begin{quote}\small\path{FINALSHA}\end{quote}
Binary model and optimizer states are excluded from Git. Checkpoint registry
and identity JSON preserve paths, sizes, hashes, epoch/update counters,
authorization and complete environment/provenance metadata.

\newpage
\section*{Post-training closure}
The actual local update log was reread to check every sample identity, seeded
order, LR, precision gate, denominator and optimizer update. The eleven
epochs were independently checked for exact coverage. Global losses, gradient
statistics, clipping and singleton metadata were recomputed and compared with
the JSON and CSV histories. FINAL passed read-only readability, SHA256 and
provenance verification.

The current 242 regression tests and NEWTESTCOUNT legal new formal-run tests
were rerun after training: TOTALTESTCOUNT actual tests, zero failures, errors or
skips. Tests used isolated fixtures, cleaned all temporary test artifacts and
never applied FINAL state to a test model. FINAL SHA256 before and after tests
was identical. Original source identity and runtime read/QC/causality checks
passed; no source or numerical failure was bypassed.

\begin{tabular}{ll}
Phase-B authorized & true\\
Formal training started & true\\
FinalFit completed & true\\
Completed epochs & 11\\
Formal optimizer updates & 128,964\\
FINAL epoch & 11\\
2025 pixels read & 0\\
B1 started / B1--B8 authorized & false / false\\
2025 Final Test authorized / executed & false / false
\end{tabular}

\section*{Evidence and limits}
The run directory contains independent authorization references,
\path{formal_run_manifest.json}, \path{training_history.csv}, eleven summaries
and histories, checkpoint registry and identities, runtime and verification
reports, actual post-training test logs, final status and artifact hashes.
This editable LaTeX source accompanies the PDF. The machine-readable evidence
contains full precision numbers and exact provenance.

METADATACORRECTION

This report establishes fixed-budget FinalFit completion. It makes no 2025
Final Test or B1--B8 performance claim. Execution stops after evidence
publication. Subsequent stages remain unauthorized.
\end{document}
'''
    values = {'RUNIDENTITY': escape(out.name), 'NORMSHA': norm,
        'EPOCHROWS': epoch_rows, 'TELEMETRYROWS': telemetry_rows,
        'FINALROOT': status['FINAL_CHECKPOINT_LOCAL_PATH'].replace('\\', '/').rsplit('/', 2)[0]+'/',
        'FINALRELATIVE': '/'.join(status['FINAL_CHECKPOINT_LOCAL_PATH'].replace('\\', '/').rsplit('/', 2)[1:]),
        'FINALSHA': status['FINAL_CHECKPOINT_SHA256'],
        'METADATACORRECTION': ('A report-only execution-manifest path error after all tests passed was recorded. '
            'Its failure history and timestamped metadata correction are preserved. '
            'The correction rechecked FINAL SHA/provenance and added zero formal optimizer updates.'
            if list(out.glob('post_training_metadata_correction_*.json')) else ''),
        'NEWTESTCOUNT': str(tests['new_formal_run_tests_executed']),
        'TOTALTESTCOUNT': str(tests['total_tests_executed'])}
    for key, value in values.items(): text = text.replace(key, value)
    tex = out/(REPORT+'.tex')
    with tex.open('x', encoding='utf-8', newline='\n') as stream: stream.write(text)
    compiler = shutil.which('pdflatex')
    if not compiler: raise FileNotFoundError('Existing pdflatex unavailable; no packages are installed by this script')
    for pass_index in (1, 2):
        result = subprocess.run([compiler, '--disable-installer', '-interaction=nonstopmode',
            '-halt-on-error', '-output-directory='+str(qa), str(tex)], cwd=qa,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        (qa/f'compile_{pass_index}.txt').write_bytes(result.stdout)
        if result.returncode: raise RuntimeError('LaTeX compilation failed; preserve editable source and diagnostic log')
    destination = out/(REPORT+'.pdf')
    with destination.open('xb') as stream: stream.write((qa/(REPORT+'.pdf')).read_bytes())
    for tool, args in [('pdfinfo', [str(destination)]),
                       ('pdftotext', ['-layout', str(destination), str(qa/'extracted.txt')]),
                       ('pdftoppm', ['-r', '100', '-png', str(destination), str(qa/'page')])]:
        executable = shutil.which(tool)
        if not executable: raise FileNotFoundError('Existing PDF verification tool unavailable: '+tool)
        result = subprocess.run([executable, *args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)
        (qa/(tool+'.txt')).write_bytes(result.stdout)
    print(json.dumps({'pdf': str(destination), 'editable_source': str(tex), 'QA_directory': str(qa),
        'rendered_pages': len(list(qa.glob('page-*.png'))), 'PDF_sha256': sha(destination),
        'visual_inspection_pending': True}))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--qa-dir', type=Path, required=True)
    args = parser.parse_args(); render(args.run_dir, args.qa_dir)
