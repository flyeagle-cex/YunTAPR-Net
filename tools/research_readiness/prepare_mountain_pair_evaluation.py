"""Prepare the exact two-arm terrain evaluation from saved source identities."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from tools.research_readiness.prepare_paired_point_evaluation import prepare
from tools.research_readiness.start_mountain_pair_evaluation import LIMITS, SCOPE, TASKS, MODEL_BINDINGS
from tools.research_readiness.mountain_pair_metrics import CONTRACT

ENTRY = 'tools/research_readiness/start_mountain_pair_evaluation.py'
ALLOWED_DELTAS = [
    'src/yuntapr/experimental/core_innovation/stage2/environment.py',
    'src/yuntapr/experimental/core_innovation/stage4/data.py',
    'src/yuntapr/experimental/core_innovation/stage4/engine.py',
    'src/yuntapr/experimental/research_readiness/dynamic_terrain.py',
    'src/yuntapr/experimental/research_readiness/dynamic_training.py',
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('code-root', 'private-dir', 'output-root', 'public-root'):
        parser.add_argument('--' + flag, type=Path, required=True)
    args = parser.parse_args()
    campaign = dict(limits=LIMITS, scope=SCOPE, tasks=TASKS, models=MODEL_BINDINGS,
                    entry=ENTRY, launcher_kind='BOUNDED_MOUNTAIN_PAIR_EVALUATION', contract=CONTRACT,
                    allowed_source_differences=ALLOWED_DELTAS,
                    source_paths=[ROOT / 'docs/research_readiness/.local/cosine9_seed2029_execution_v1/B7_s2029',
                                  ROOT / 'docs/research_readiness/.local/zero_cosine9_seed2029_execution_v1/B7_s2029'],
                    additional_tools=[ENTRY, 'tools/research_readiness/mountain_pair_worker.py',
                                      'tools/research_readiness/mountain_pair_metrics.py',
                                      'tools/research_readiness/prepare_mountain_pair_evaluation.py',
                                      'tools/research_readiness/prepare_paired_point_evaluation.py'])
    proposal, _ = prepare(args.code_root, args.private_dir, args.output_root, args.public_root, campaign=campaign)
    print(proposal['proposal_sha256'])


if __name__ == '__main__':
    main()
