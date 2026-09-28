"""Candidate-contract guards. No datasets, model training, or fitted statistics."""
from datetime import date
import numpy as np

def intervals(blocks):
    return [(date.fromisoformat(a),date.fromisoformat(b)) for a,b in blocks]

def validate_split(candidate):
    train,val=intervals(candidate['train_blocks']),intervals(candidate['validation_blocks'])
    for blocks in (train,val):
        for i,(a,b) in enumerate(blocks):
            if not a<b: raise ValueError('Empty/reversed block')
            if a.year not in (2023,2024) or b.year!=a.year: raise ValueError('Development year violation')
            if not (date(a.year,3,1)<=a<b<=date(a.year,11,1)): raise ValueError('Development season violation')
            if any(max(a,c)<min(b,d) for c,d in blocks[i+1:]): raise ValueError('Within-role overlap')
    if any(max(a,c)<min(b,d) for a,b in train for c,d in val): raise ValueError('Train/Val overlap')
    if candidate.get('status')!='CANDIDATE_ONLY' or candidate.get('selected',False): raise ValueError('Unapproved split')
    return True

def valid_target(values,fill_values=()):
    """Preserve original values; zero is physically valid; no imputation."""
    arr=np.asarray(values); mask=np.isfinite(arr)
    for fill in fill_values:
        if np.isfinite(fill): mask &= arr!=fill
    return mask

def normalization_scope_guard(split,mask):
    if split!='Train': raise ValueError('Fit normalization only on approved Train')
    if np.asarray(mask).dtype!=np.bool_: raise ValueError('Explicit boolean missing mask required')
    return True

def formal_gate(entries):
    return bool(entries) and all(x['status']=='PASS' and x['engineering_ready'] and
                                x['scientific_rule_frozen'] and x['data_ready'] and
                                not x['researcher_decision_required'] for x in entries)
