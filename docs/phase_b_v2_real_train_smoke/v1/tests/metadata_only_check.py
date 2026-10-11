"""Pinned repository metadata only; no raw handle or full model construction."""
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
from yuntapr.experimental.phase_b_v2_real_train_smoke.resources import Budget
from yuntapr.experimental.phase_b_v2_real_train_smoke.data import SmokePlan
from yuntapr.experimental.phase_b_v2_real_train_smoke import OUT

with tempfile.TemporaryDirectory() as directory:
    budget=Budget(Path(directory))
    with patch('yuntapr.experimental.phase_b_v2_real_forward_pilot.adapter.ReadHandle',side_effect=AssertionError('NO_RAW_HANDLE')):
        plan=SmokePlan(budget)
    expected=['2023-03-01T00:30:00+00:00','2023-03-01T01:00:00+00:00']
    assert [r[0]['sample_id'] for r in plan.rows]==expected
    assert len(plan.scope.entries)==10
    assert len(plan.frames)==9
    result=dict(status='PINNED_METADATA_ONLY_PASS',manifest_positions=[0,1],sample_ids=expected,
        distinct_B13_references=9,distinct_IMERG_references=1,pinned_public_files=len(plan.public.pins),
        raw_file_open_attempts=0,model_constructions=0,optimizer_steps=0,
        public_metadata_content_bytes=budget.bytes,source_pins=list(plan.public.pins.values()))
    (OUT/'tests/metadata_only_result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='source_pins'}))
    budget.close()
