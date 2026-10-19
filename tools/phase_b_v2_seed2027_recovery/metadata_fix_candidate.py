"""Non-launching repair: compare persisted reports using frozen JSON digest semantics."""
import hashlib,json

def canonical(value):
    # Same serialization as the frozen protocol.digest: tuple/list both become
    # JSON arrays, but values, ordering, keys and finite-number requirements remain.
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def validate_history_metrics(history,payload):
    if canonical(history['train'])!=canonical(payload['train']):raise ValueError('AUTHORIZED_LAST_TRAIN_METRICS')
    if canonical(history['development'])!=canonical(payload['validation']):raise ValueError('AUTHORIZED_LAST_DEVELOPMENT_METRICS')
    return dict(train_sha256=canonical(payload['train']),validation_sha256=canonical(payload['validation']))
