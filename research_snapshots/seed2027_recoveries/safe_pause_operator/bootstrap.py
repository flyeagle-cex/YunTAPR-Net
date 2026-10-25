"""Import the frozen campaign without changing its files or Python environment."""
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
CAMPAIGN_ROOT = ROOT.parent / 'YunTAPR-Net-seed2027-b1-e1-recovery-v2-20261022'
spec = importlib.util.spec_from_file_location('frozen_campaign_bootstrap', CAMPAIGN_ROOT / 'tools/seed2027_b1_e1_epoch6_recovery_v2/operate.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
from yuntapr.training.phase_b_v2_seed2027_b1_e1_epoch6_recovery_v2 import control, protocol, quota

assert 'torch' not in sys.modules
