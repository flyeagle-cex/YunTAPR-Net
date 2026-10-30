"""Non-executing final-test metadata checks; never opens final-year payloads.

The actual2025 reader/metric adapter remains unimplemented and unauthorized.
Passing these synthetic/catalog checks cannot unblind or authorize inference.
"""
from datetime import datetime
import re

MODELS=('B4','B7','B8','B7_ZERO_DOTE')
SEEDS=(2029,2030,2031)


def validate_catalog(catalog):
    expected={(m,s) for m in MODELS for s in SEEDS}
    if len(catalog)!=12 or {(x['model'],x['seed']) for x in catalog}!=expected:
        raise ValueError('All twelve proposed fixed endpoints required; not a best-seed selection')
    for x in catalog:
        if x['endpoint']!='FIXED_EPOCH_9_LAST' or x['epochs']!=9 or not re.fullmatch('[0-9a-f]{64}',x['checkpoint_sha256']):
            raise ValueError('Existing E9 LAST identity required; no BEST or fine tuning')
    if len({x['checkpoint_sha256'] for x in catalog})!=12:raise ValueError('Distinct registered endpoint identities required')
    return dict(status='PASS_PROPOSED_CATALOG_ONLY_NOT_A_RESEARCHER_FREEZE',models=12,payload_access_authorized=False)


def validate_synthetic_alignment(rows):
    """Exercise metadata dimensions/time uniqueness only, on fictitious2001."""
    ids=set()
    for row in rows:
        t=datetime.fromisoformat(row['analysis_time'])
        if row.get('synthetic_fixture') is not True or t.year!=2001:
            raise PermissionError('Synthetic2001 only; no real2025 population certification')
        if t.tzinfo is None or t.utcoffset().total_seconds()!=0 or t.hour not in (0,6,12,18) or t.minute!=0 or t.second!=0:
            raise ValueError('Explicit four-UTC analysis metadata')
        if row['sample_id'] in ids:raise ValueError('Duplicate scene identity')
        ids.add(row['sample_id'])
        if row['satellite_shape']!=[7,6] or row['GFS_variables']!=13 or row['lead_hours']!=6 or row['DEM_channels']!=6:
            raise ValueError('Proposed common full-modality dimensions changed')
        if row['target_shape']!=[100,100] or row['supervised_points']!=3430:
            raise ValueError('Frozen target geometry required')
    return dict(status='PASS_SYNTHETIC_METADATA_ONLY',scenes=len(ids),real_population='NOT_VERIFIED',actual_inference_adapter='NOT_IMPLEMENTED')


def authorize_payload(*args,**kwargs):
    raise PermissionError('DRAFT cannot authorize2025 reads, inference, metrics or unblinding')
