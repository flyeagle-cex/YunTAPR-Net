"""Expose the exact new package and previous checkpoint implementation without pyc writes."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
WORK=Path(__file__).absolute().parents[3]
sys.path.insert(0,str(WORK.parent/'YunTAPR-Net-push-chunks/src'))
import yuntapr.training
for path in (WORK.parent/'YunTAPR-Net-completed-review-20261021/recovery_overlay/yuntapr/training',WORK/'recovery_overlay/yuntapr/training'):
    if str(path) not in yuntapr.training.__path__:yuntapr.training.__path__.append(str(path))
