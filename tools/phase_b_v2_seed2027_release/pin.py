"""Write the actual publication-only decision and source pin; NEVER launch."""
from pathlib import Path
import json,os,sys
ROOT=Path(__file__).absolute().parents[2]
sys.path.insert(0,str(ROOT/'src'));os.environ['YUNTAPR_REPLICATION_SEED']='2027'
from yuntapr.training.phase_b_v2_seed2027.protocol import OUT,CAMPAIGN,LIMITS,TOTAL,code_identity,digest
from yuntapr.training.phase_b_v2_seed2027.authority import PUBLICATION_DECISION,PUBLICATION_SCOPE
def main():
    source=code_identity();old=ROOT/'docs/phase_b_v2_formal_execution/seed2027_v1/prepared_release.json'
    dependency_sha=json.loads(old.read_bytes())['dependency_manifest_sha256']
    release=dict(schema='SEED2027_EXECUTION_PUBLICATION_WITHOUT_LAUNCH_v1',seed=2027,campaign=CAMPAIGN,
        publication_decision=PUBLICATION_DECISION,publication_scope=PUBLICATION_SCOPE,
        decision_origin='DIRECT_HUMAN_REPLY_IN_CURRENT_CONVERSATION',
        question_item_id='["request_user_input_async","call_08f7317c64254c38a53a6d7fc0dc153e",0]',
        launch_authorized=False,planned_attempt_cap=TOTAL,original_resource_limits=LIMITS,
        source_commit=source['commit'],source_sha256=source['sha256'],source_pins=source['pins'],
        config_sha256=__import__('hashlib').sha256((OUT/'config.json').read_bytes()).hexdigest(),
        dependency_manifest_sha256=dependency_sha,dependency_revalidation='REQUIRED_AT_FUTURE_AUTHORIZED_START',
        actual_training_runs=0,other_seeds_covered=[],no_new_data_access=True,
        original_preparation_ancestor='69ed793fed393a9466385f59de8fa062764c0445')
    with (OUT/'release.json').open('xb') as f:f.write((json.dumps(release,ensure_ascii=False,indent=2)+'\n').encode())
    print(json.dumps(dict(status='RELEASE_PUBLISHED_LAUNCH_WITHHELD',source_commit=source['commit'],source_sha256=source['sha256'])))
if __name__=='__main__':main()
