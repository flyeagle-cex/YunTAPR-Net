"""Expose only the new isolated package alongside the unchanged legacy source."""
from pathlib import Path
import sys

sys.dont_write_bytecode = True
WORK = Path(__file__).resolve().parents[3]
LIVE = WORK.parent / "YunTAPR-Net-push-chunks"
sys.path.insert(0, str(LIVE / "src"))
import yuntapr.training

overlay = str(WORK / "recovery_overlay/yuntapr/training")
if overlay not in yuntapr.training.__path__:
    yuntapr.training.__path__.append(overlay)
