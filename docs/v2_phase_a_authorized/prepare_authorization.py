"""Create publication-only authorization evidence; no training/model imports."""
import hashlib,json,subprocess
from datetime import datetime,timezone,timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
EXEC=ROOT.parent/'YunTAPR-Net-v2-phase-a-execution'
SCI='d049f7ab7b8a382f47a5fe54384ea9416a22cde9'
IMPL='a1af0325b481202941c57e8fc94f3b20e441630a'
PREFLIGHT='5c2f3e57ef6c93335998012a6bbdf24f05deafa4'
GATE=ROOT/'docs/v2_phase_a_execution/runs/run_20261007T031200_000001Z/preflight_manifest.json'
TEST=ROOT/'docs/v2_phase_a_execution/test_runs/run_20261007_full_004/test_summary.json'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def put(p,obj):
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')
def main():
    assert sha(GATE)=='d17bff69c08fce473c161965e0853868dd1cfd149573982e56b07fc509ca45b7'
    assert sha(TEST)=='42dda3065426c441ace057f740c6784545466f1babd5f68bf23fca243d75a16f'
    gate=load(GATE);now=datetime.now(timezone.utc)
    pair=now.strftime('pair_%Y%m%dT%H%M%S_%fZ')
    runs={'B0_MATCHED_V2':now.strftime('run_%Y%m%dT%H%M%S_%fZ'),'B1_V2':(now+timedelta(microseconds=1)).strftime('run_%Y%m%dT%H%M%S_%fZ')}
    roots={'B0_MATCHED_V2':r'F:\pytorch\Research\outputs\formal_training\b0_matched_v2_phase_a','B1_V2':r'F:\pytorch\Research\outputs\formal_training\b1_v2_phase_a'}
    out=ROOT/'docs/v2_phase_a_authorized'/pair;out.mkdir(exist_ok=False)
    public=ROOT/'docs/formal_training_v2'/pair
    for k,r in roots.items():assert not (Path(r)/runs[k]).exists()
    auth={'schema':'RESEARCHER_FORMAL_PAIRED_PHASE_A_V2_AUTHORIZATION_v1','scope':'FORMAL_PAIRED_PHASE_A_V2',
      'created_utc':now.isoformat(),'FORMAL_TRAINING_AUTHORIZED':True,'V2_PHASE_A_AUTHORIZED':True,
      'V2_PHASE_A_STARTED':False,'V2_PHASE_B_AUTHORIZED':False,'2025_RAW_ACCESS':False,'2025_PIXELS_READ':0,
      'scientific_commit':SCI,'execution_commit':IMPL,'finalized_preflight_commit':PREFLIGHT,
      'protocol_sha256':gate['protocol_sha256'],'head_sha256':gate['head_sha256'],'normalization_sha256':gate['normalization_sha256'],
      'code_sha256':gate['code_sha256'],'checkpoint_roots':roots,'models':list(runs),'run_ids':runs,'pair_id':pair,
      'publication_repository':str(ROOT),'publication_root':str(public),'execution_checkout':str(EXEC),
      'preflight_path':str(GATE),'preflight_sha256':sha(GATE),'test_summary_path':str(TEST),'test_summary_sha256':sha(TEST),
      'initial_state_sha256':gate['paired_initialization']['models'],
      'researcher_approval_reference':str(out/'FORMAL_PHASE_A_AUTHORIZATION_RECORD.md'),
      'resume_authorized':False,'launch_mode':'FRESH_SEQUENTIAL_B0_THEN_B1',
      'completion_boundary':'Both Phase-A runs complete; read-only 2024 BEST comparison packet; STOP; no Phase-B or 2025',
      'authorization_commit_binding':'Containing Git commit, remotely verified before launcher invokes train; no circular self SHA',
      'root_policy':'Retain preflight-pinned independent v2 roots; proposed alternative root was advisory'}
    record='''# Researcher formal Phase-A launch authorization

本记录为本次研究者明确授权的结构化转录与执行解释，不冒充平台消息签名。来源：当前对话任务 AUTHORIZE AND LAUNCH YunTAPR-Net v2 paired Phase-A 及随后 Goal。

研究者正式批准 FORMAL_TRAINING_AUTHORIZED=true、V2_PHASE_A_AUTHORIZED=true；只运行 B0_MATCHED_V2 Phase-A 与 B1_V2 Phase-A，顺序独占 GPU。V2_PHASE_B_AUTHORIZED=false，2025 raw/pixels 必须为零。科学冻结、implementation、final preflight commit 和各项 SHA 详见同目录 authorization.json、PAIR_IDENTITY.json 及两个 RUN_MANIFEST。

使用 seed=2026 fresh same-name same-shape paired initialization；禁止加载历史模型、optimizer、scheduler 或 RNG。Train 10,455、Validation 10,501，所有科学参数原样继承冻结 protocol。BEST 仅按 global_val_core_loss，早停 patience=8/min_delta=1e-4。upper-tail diagnostics 只读且不参与训练控制。数值合同违反立即停止，无修复、无跳 batch。

正式根目录沿用已通过预检的 runner 固定 v2 根目录，在其下使用新的唯一 run_id。研究者给出的 formal_training_v2 路径为建议，未改动绑定 implementation。两个模型各自从冻结 fresh paired state 开始；完整 train+validation+diagnostics 与 audit 完成后才提交有效 checkpoint。临时未提交状态不是可恢复 LAST。

授权证据必须先发布 GitHub main；独立启动包装器验证授权所在 commit、远端 main、授权文件 SHA 和执行代码身份后才能调用原版 train。实际代码仍在固定 implementation checkout，publication 在独立 main checkout。日志发布失败按已冻结队列政策处理，不改变训练。状态计数均来自 FORMAL scope，不混入 smoke/test。

意外中断时只允许从核验后的完整 LAST 恢复；本启动文件只授权 fresh train，不自动重试或自动挑选恢复 checkpoint。恢复操作必须另建绑定具体 LAST 和原授权 SHA 的记录，保存丢弃更新证据。禁止 Phase-B、FinalFit、2025、重设计与自动调参。

两模型结束后形成完整 BEST/LAST、history、diagnostics、counters、样本与 checkpoint 身份证据。Brier/AUROC/AP/conditional pinball 在固定 2024 validation 上对各自 BEST 只读评价，沿用历史 Scientific Review 指标定义；不回传训练、不重新选择 epoch，不读取 2025。该决策包尚未生成，不能把训练完成等同于 Goal 完成。

本文件发布时 V2_PHASE_A_STARTED=false。启动后另存启动收据，保持本批准记录不可变。RESEARCHER_PHASE_A_REVIEW_REQUIRED=true 在两模型审计完成后输出，随后停止。
'''
    (out/'FORMAL_PHASE_A_AUTHORIZATION_RECORD.md').write_text(record,encoding='utf-8',newline='\n')
    auth['researcher_approval_record_sha256']=sha(out/'FORMAL_PHASE_A_AUTHORIZATION_RECORD.md')
    put(out/'authorization.json',auth)
    identity={**auth,'authorization_sha256':sha(out/'authorization.json'),'data_identity':load(ROOT/'config/science_v2/phase_a_protocol_frozen_v1.json')['identity']}
    put(out/'PAIR_IDENTITY.json',identity)
    for k,name in [('B0_MATCHED_V2','B0_RUN_MANIFEST.json'),('B1_V2','B1_RUN_MANIFEST.json')]:
        put(out/name,{'model':k,'pair_id':pair,'run_id':runs[k],'absolute_checkpoint_root':str(Path(roots[k])/runs[k]),
            'initial_state_sha256':auth['initial_state_sha256'][k],'initialization':'FRESH_SEED_2026_SAME_NAME_SAME_SHAPE_PAIRED',
            'protocol_sha256':auth['protocol_sha256'],'head_sha256':auth['head_sha256'],'normalization_sha256':auth['normalization_sha256'],
            'execution_commit':IMPL,'code_sha256':auth['code_sha256'],'data_identity':identity['data_identity'],
            'authorization_sha256':identity['authorization_sha256'],'state':'AUTHORIZED_NOT_STARTED','formal_optimizer_steps':0,
            'train_scenes':10455,'validation_scenes':10501,'V2_PHASE_B_AUTHORIZED':False,'2025_RAW_ACCESS':0,'2025_PIXELS_READ':0})
    print(json.dumps({'authorization_directory':str(out),'pair_id':pair,'authorization_sha256':identity['authorization_sha256']},ensure_ascii=False))
if __name__=='__main__':main()
