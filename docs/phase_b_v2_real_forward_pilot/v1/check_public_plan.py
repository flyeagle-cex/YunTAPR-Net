"""Pre-execution metadata-only identity check, no source file operations."""
import ast
import hashlib
import json
from pathlib import Path
import sys
import tempfile
HERE = Path(__file__).absolute().parent; ROOT = HERE.parents[2]
sys.path.insert(0,str(ROOT/'src'))
from yuntapr.experimental.phase_b_v2_real_forward_pilot.resources import Budget
from yuntapr.experimental.phase_b_v2_real_forward_pilot.plan import FrozenPlan
from yuntapr.experimental.phase_b_v2_integration.pins import verify_frozen_sources

with tempfile.TemporaryDirectory() as folder:
    budget=Budget(Path(folder))
    try:
        plan=FrozenPlan(budget)
        frozen=verify_frozen_sources()
        modules=list((ROOT/'src/yuntapr/experimental/phase_b_v2_real_forward_pilot').glob('*.py'))+list(HERE.glob('*.py'))
        for p in modules: ast.parse(p.read_bytes(),filename=p.name)
        status=dict(status='PUBLIC_PLAN_AND_STATIC_PASS', selected_scenes=len(plan.rows),
            distinct_raw_file_refs=len(plan.scope.entries), public_metadata_bytes=budget.bytes,
            raw_file_operations=0, model_constructions=0, model_forwards=0,
            model_source_pins=frozen, ast_checked_files=len(modules))
        (HERE/'tests/public_plan_check.json').write_bytes((json.dumps(status,indent=2)+'\n').encode())
        print(json.dumps({k:v for k,v in status.items() if k!='model_source_pins'}))
    finally: budget.close()
