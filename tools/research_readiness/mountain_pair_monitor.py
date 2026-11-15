"""Loopback-only receipt view for the approved REAL/ZERO mountain evaluation."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.research_readiness import v7_monitor as base

PROPOSAL = '85bc55e0101823b1291c3923c85685a7ad50315797327b9eae410f2fe49bdf61'
COMMIT = 'e8d2a9b0c3ab7f60aa678a0bcee2d60133852e74'
base.ARMS = (('REAL_COSINE9', 'REAL · 动态地形强迫'), ('ZERO_COSINE9', 'ZERO · 数值归零对照'))
base.PAGE = (base.PAGE.replace('V7 两臂联合评价', '山区×强雨匹配评价')
             .replace('00c5174611d2', PROPOSAL[:12])
             .replace('固定 E9 · Seed 2029 · 只读实时进度', 'REAL／ZERO · COSINE9 · 固定 E9 · Seed 2029')
             .replace('完成状态需要九轮收据和总完成收据；科学结论始终标记为待验证。', '完成状态依据两臂评价及总完成收据。主观察为海拔≥2,000米且雨强>20 mm/h，科学状态待验证。')
             .replace('训练控制', '执行控制')
             .replace('<span id="state"', '<span aria-live="polite" id="state"')
             .replace('</style>', 'button:focus-visible{outline:3px solid #17674a;outline-offset:3px}@media(prefers-reduced-motion:reduce){.fill{transition:none}}</style>'))


class Snapshot(base.Snapshot):
    def _arm(self, name, label):
        result = super()._arm(name, label)
        if (self.output / name / 'task_failure.json').exists():
            result['state'] = 'FAILED'
        return result

    def get(self):
        result = super().get()
        if result['state'] == 'RUNNING':
            active = next(arm['label'] for arm in result['arms'] if arm['state'] == 'RUNNING')
            result = dict(result, stage=f'当前阶段为{active}开发集读取与评价。两臂结束后汇总山区×雨强配对统计。')
        exit_receipt = self._json(self.service / 'target_exit.json')
        if exit_receipt and result['state'] in ('RUNNING', 'PENDING'):
            result = dict(result, state='STOPPED', stage='后台进程已退出，完成收据待核对。')
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--evaluation-service', type=Path, required=True)
    parser.add_argument('--monitor-service', type=Path, required=True)
    parser.add_argument('--port', type=int, default=0)
    args = parser.parse_args()
    output = args.output_root.resolve()
    private = ROOT / 'docs/research_readiness/.local'
    monitor = args.monitor_service.resolve()
    if output != (private / 'mountain_pair_evaluation_v1').resolve() or not monitor.is_relative_to(private):
        raise ValueError('Exact evaluation and private monitor namespaces required')
    binding = json.loads((output / 'binding.json').read_text(encoding='utf-8'))
    if binding['proposal_sha256'] != PROPOSAL or binding['code_commit'] != COMMIT:
        raise ValueError('Evaluation binding differs from the approved package')
    base.Handler.snapshot = Snapshot(output, args.evaluation_service.resolve(), binding['package_started_wall'])
    server = base.ThreadingHTTPServer(('127.0.0.1', args.port), base.Handler)
    server.daemon_threads = True
    with (monitor / 'monitor_service.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(dict(url=f'http://127.0.0.1:{server.server_port}/', pid=os.getpid(), read_only=True), stream)
    server.serve_forever(poll_interval=.5)


if __name__ == '__main__':
    main()
