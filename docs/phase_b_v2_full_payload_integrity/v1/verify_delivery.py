"""Verify public receipts and source identities only; no raw filesystem access."""
import ast
import csv
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).absolute().parent;ROOT=HERE.parents[2]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def verify():
    status=json.loads((HERE/'final_status.json').read_text())
    matched=0;counts={};total=0;keys=set();size=0;metadata_attempts=0;opens=0
    with gzip.open(HERE/'PAYLOAD_SHA_RECEIPTS.csv.gz','rt',encoding='utf-8',newline='') as stream:
        for i,row in enumerate(csv.DictReader(stream)):
            assert int(row['i'])==i and row['file_key'] not in keys
            keys.add(row['file_key']);total+=int(row['read_bytes']);counts[row['kind']]=counts.get(row['kind'],0)+1
            assert row['year'] in ('2023','2024')
            assert len(row['expected_sha'])==64
            if row['size']:size+=int(row['size'])
            metadata_attempts+=int(row['metadata_attempts']);opens+=int(row['payload_attempts'])
            if row['status']=='SHA_PASS':
                assert row['actual_sha']==row['expected_sha'] and int(row['read_bytes'])==int(row['size'])
                matched+=1
    assert len(keys)==status['registered_files'] and matched==status['sha_matched_files'] and total==status['payload_bytes_returned']
    ledger=json.loads((HERE/'READ_SCOPE_AND_RESOURCE_LEDGER.json').read_text())
    assert ledger['metadata_handle_attempts']==metadata_attempts and ledger['payload_open_attempts']==opens
    assert total+ledger['public_metadata_bytes']<=ledger['limits']['max_total_content_bytes']
    if status['overall_status']=='FULL_PAYLOAD_SHA_PASS':
        assert len(keys)==matched==67006 and counts=={'B13':66516,'IMERG':490}
        assert size==status['predicted_payload_bytes']
        assert ledger['payload_open_successes']==ledger['metadata_handle_successes']==67006
        assert status['failure'] is None and not ledger['failed_files']
        assert status['inflight_read_uncertainty_upper_bytes']==0
        assert status['elapsed_seconds']<=ledger['limits']['max_elapsed_seconds']
    for key in ('V2_PHASE_B_AUTHORIZED','FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED','FORMAL_OPTIMIZER_STEPS','2025_PIXELS_READ'):
        assert status[key] in (0,False)
    assert status['historical_2025_path_attributes']=='NOT_INSTRUMENTED'
    assert status['RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED'] is True
    assert status['prior_full_preflight_overall_status']=='NOT_VERIFIED_UNCHANGED'
    for item in json.loads((HERE/'source_identity.json').read_text())['public_source_pins']:
        assert sha(ROOT/item['path'])==item['sha256']
    manifest=json.loads((HERE/'manifest.json').read_text())
    for item in manifest['files']:
        path=ROOT/item['path'];assert '.local' not in path.parts and '__pycache__' not in path.parts
        assert sha(path)==item['sha256']
        if path.suffix=='.py':ast.parse(path.read_bytes().decode())
        if path.suffix not in ('.gz',):
            raw=path.read_bytes();assert b'\r' not in raw
            forbidden=(b'C:'+bytes([92])+b'Users'+bytes([92]),b'F:'+bytes([92])+b'pytorch'+bytes([92]),b'gh'+b'p_',b'github'+b'_pat_')
            assert not any(s in raw for s in forbidden),path.name
    changes=subprocess.check_output(['git','diff','--name-only',status['baseline_commit']],cwd=ROOT,text=True).splitlines()
    allowed=('src/yuntapr/experimental/phase_b_v2_full_payload_integrity/','docs/phase_b_v2_full_payload_integrity/v1/')
    assert all(p.startswith(allowed) for p in changes)
    return {'status':'PASS','matched':matched,'registered':len(keys),'payload_bytes':total,'kind_counts':counts,'source_pins':len(json.loads((HERE/'source_identity.json').read_text())['public_source_pins'])}
if __name__=='__main__':print(json.dumps(verify()))
