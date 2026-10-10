"""Bounded observed-data forward pilot; no formal execution capability."""
from pathlib import Path

ROOT = Path(__file__).absolute().parents[4]
BASELINE = 'edf883b55dd01dbf397b52224db58be85550c42a'
SCOPE = 'BOUNDED_REAL_FORWARD_ENGINEERING_ONLY'
SEED = 2026
LIMITS = {'max_scenes': 48, 'max_model_batches': 48,
          'max_scenes_per_model': 48, 'batch_size': 2,
          'max_content_bytes': 4 * 1024**3, 'max_elapsed_seconds': 1800,
          'max_working_set_bytes': 3 * 1024**3,
          'minimum_cuda_free_bytes': 5 * 1024**3}
FLAGS = {'V2_PHASE_B_AUTHORIZED': False,
         'FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED': False,
         'RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED': True,
         'FORMAL_OPTIMIZER_STEPS': 0, 'BACKWARDS': 0,
         'HISTORICAL_RECOVERY_RATIFICATION': 'NOT_GRANTED',
         '2025_PIXELS_READ': 0, 'historical_2025_path_attributes': 'NOT_INSTRUMENTED',
         'HISTORICAL_CHECKPOINT_READS': 0, 'SCALER_FITS': 0}

def formal_entry(*args, **kwargs):
    """The pilot cannot grant or consume formal training authorization."""
    raise PermissionError('FORMAL_ENTRY_NOT_IMPLEMENTED_IN_PILOT')
