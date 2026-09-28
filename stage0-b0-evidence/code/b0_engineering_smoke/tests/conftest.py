from pathlib import Path
import sys
import torch
RUN=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(RUN/'src'))
torch.set_num_threads(2)
