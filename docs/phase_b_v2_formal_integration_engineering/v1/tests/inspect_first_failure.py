"""One-off read of THIS campaign's failed synthetic artifact; no live restore.

The normal Store remains weights_only with no added globals. This forensic
reader permits only NumPy scalar constructors in the exact locally produced,
SHA-verified artifact. It cannot authorize a LAST or refund a consumed step.
"""
import hashlib
import json
import numpy as np
import torch
from yuntapr.training.phase_a_protocol import state_digest
from yuntapr.experimental.phase_b_v2_formal_integration_candidate.protocol import OUT,BASELINE,SCOPE
from yuntapr.experimental.phase_b_v2_formal_integration_candidate.storage import LOCAL,install_guard
from yuntapr.experimental.phase_b_v2_formal_integration_candidate.state import ActualQuota

install_guard();quota=ActualQuota();rows=quota.con.execute('SELECT model,status,source FROM quota ORDER BY id').fetchall()
assert len(rows)==1 and rows[0][:2]==('B0_MATCHED_V2','COMPLETED')
reference=LOCAL/'session_sk0d8u6b'/'LAST_SYNTHETIC_EPOCH1.ref.json'
record=json.loads(reference.read_text());assert record['filename']=='LAST_SYNTHETIC_EPOCH1.pt'
blob=reference.parent/record['filename'];raw=blob.read_bytes()
assert len(raw)==record['bytes'] and hashlib.sha256(raw).hexdigest()==record['sha256']
with torch.serialization.safe_globals([np._core.multiarray.scalar,np.dtype,np.dtypes.Float64DType]):
    payload=torch.load(blob,map_location='cpu',weights_only=True)
assert payload['identity']['source_commit']==BASELINE and payload['identity']['code_sha']==rows[0][2]
assert payload['identity']['scope']==SCOPE and payload['epoch']==1 and payload['update']==1
report={'scope':SCOPE,'failed_before_controller_last_commit':True,'quota_refunded':False,
        'state':{k:state_digest(payload[k]) for k in ('model','optimizer','scheduler','rng')},
        'initial_sha':payload['initial_sha'],'failed_blob_sha':record['sha256'],'source_code_sha':rows[0][2],
        'forensic_only_no_restore':True,'resource_peak':'NOT_RECORDED_BEFORE_FAILURE'}
(OUT/'tests'/'first_failure_state.json').write_bytes((json.dumps(report,indent=2)+'\n').encode())
print(json.dumps(report))
