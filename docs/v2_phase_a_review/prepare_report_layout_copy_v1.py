"""Create an editable layout-only delivery copy; keep original packet immutable."""
import argparse
import hashlib
import json
from pathlib import Path
import re

REPO = Path(__file__).resolve().parents[2]


def format_layout(text):
    replacements = {
        r'\begin{tabular}': r'\par\noindent\begin{tabular}',
        r'\end{tabular}': r'\end{tabular}\par',
        r'\setlength{\parskip}{5pt}': r'\setlength{\parskip}{5pt}\setlength{\emergencystretch}{2em}',
        r'\section{冻结来源与检查点登记}': r'\clearpage\section{冻结来源与检查点登记}',
        r'termination=EARLY\_STOP\_PATIENCE\_8': '终止原因：固定早停（patience=8）',
        r'termination=MAX\_EPOCH\_50': '终止原因：达到固定最大 epoch=50',
        'model/optimizer/scheduler/RNG/permutation': 'model、optimizer、scheduler、RNG 与 permutation',
        r'\textbf{RESEARCHER\_PHASE\_A\_REVIEW\_REQUIRED=true；V2\_PHASE\_B\_AUTHORIZED=false。}':
            r'\par\textbf{需要研究者审查配对 Phase-A；Phase-B 未授权。}\par',
    }
    labels = {
        r'protocol\_sha256': '科学协议 SHA256', r'head\_sha256': '分位数头 SHA256',
        r'normalization\_sha256': '归一化 SHA256', r'scientific\_commit': '科学冻结 commit',
        r'execution\_commit': '实现 commit', r'authorization\_sha256': '完成授权 SHA256',
        r'packet\_generator\_sha256': '决策包脚本 SHA256',
        r'B0\_MATCHED\_V2\_initial\_state\_sha256': 'B0 初始状态 SHA256',
        r'B1\_V2\_initial\_state\_sha256': 'B1 初始状态 SHA256',
        r'global\_val\_core\_loss': '全局验证核心损失',
        r'Brier\_Score': 'Brier', r'Average\_Precision': 'AP',
        r'conditional\_mean\_pinball': '条件平均 pinball',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    for old, new in labels.items():
        text = text.replace(old + ' & ', new + ' & ')
    return text


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--fixture-only', action='store_true')
    args = p.parse_args()
    source, out = args.source.resolve(), args.output.resolve()
    root = REPO / ('tmp/pdfs' if args.fixture_only else 'docs/v2_phase_a_review/paired_packets')
    if source.suffix != '.tex' or not source.is_relative_to(root) or not out.is_relative_to(root):
        raise PermissionError('Only independent report/fixture LaTeX copies allowed')
    original = source.read_bytes()
    text = original.decode('utf-8')
    formatted = format_layout(text)
    # Layout translation must preserve all frozen mathematical expressions and hashes.
    for pattern in (r'\$(?:\\.|[^$])*\$', r'\b[0-9a-f]{40,64}\b'):
        if re.findall(pattern, text) != re.findall(pattern, formatted):
            raise ValueError('Layout changes mathematical/identity content')
    out.mkdir(parents=True, exist_ok=False)
    target = out / 'V2_PAIRED_PHASE_A_REVIEW.tex'
    with target.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write('% Layout-only copy; original SHA256=' + hashlib.sha256(original).hexdigest() + '\n')
        stream.write(formatted)
    if source.read_bytes() != original:
        raise ValueError('Original packet source changed')
    with (out / 'layout_copy_manifest.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump({'status': 'LAYOUT_COPY_CREATED_PDF_PENDING', 'TEST_FIXTURE_ONLY': args.fixture_only,
            'original_source': str(source), 'original_sha256': hashlib.sha256(original).hexdigest(),
            'delivery_source': str(target), 'delivery_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
            'layout_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'original_unchanged': True, 'mathematical_expressions_and_hashes_unchanged': True,
            'PDF_VISUALLY_VERIFIED': False, 'RAW_SOURCE_OPENS': 0}, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(target)


if __name__ == '__main__':
    main()
