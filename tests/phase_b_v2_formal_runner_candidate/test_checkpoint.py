"""Full epoch schema failure injection using manually made metadata, NO steps."""
import copy
import pytest
import torch
from yuntapr.training.phase_a_protocol import state_digest
from yuntapr.experimental.phase_b_v2_ablations.config import RunSpec, learning_rate_prefix
from yuntapr.experimental.phase_b_v2_formal_runner_candidate.checkpoint import validate_last, SCHEMA, EpochStore
from yuntapr.experimental.phase_b_v2_formal_runner_candidate.protocol import run_identity
from yuntapr.experimental.phase_b_v2_formal_runner_candidate.safety import install_guard
from yuntapr.experimental.phase_b_v2_formal_runner_candidate.data import Coverage, ROLES
from yuntapr.experimental.phase_b_v2_integration.controls import synthetic_epoch_order
from yuntapr.experimental.phase_b_v2_runner_candidate import rng
from yuntapr.experimental.phase_b_v2_formal_runner_candidate.engine import EpochSchedule

install_guard()


def fixture():
    # All state counters below are hand-made schema fixtures, never real updates.
    train = tuple(f"SYNTHETIC_ENGINEERING_ONLY/order_{i:05d}" for i in range(5))
    val = tuple(f"SYNTHETIC_ENGINEERING_ONLY/order_{i:05d}" for i in range(10000,10005))
    order = synthetic_epoch_order(train,2026,0)
    c = Coverage(train); c.add(order)
    d = Coverage(val); d.add(val)
    train_receipt = {"coverage":c.finish(),"batches":3,"N_valid":17150,"N_rain":0,"batch_records":[
        {"synthetic_update":i+1,"synthetic_epoch":1,"scene_ids":list(order[2*i:2*i+2]),"lr":learning_rate_prefix(i+1),
         "batch":len(order[2*i:2*i+2]),"N_valid":3430*len(order[2*i:2*i+2]),"limit":5.,"post_clip_norm":1.}
        for i in range(3)]}
    validation = {"coverage":d.finish(),"N_valid":17150,"N_rain":0,"forwards":1,"numerator_dtype":"float64",
                  "lambda_in_common_metric":False}
    model = {"synthetic_fixture":torch.ones(2)}
    initial = state_digest(model)
    identity = run_identity(RunSpec("E0","B0_MATCHED_V2",2026),"0"*64)
    template = {"param_groups":[{"params":[0],"lr":1e-4}],"_shapes":{0:(2,)}}
    opt = {"param_groups":[{"params":[0],"lr":learning_rate_prefix(3)}],"state":{
        0:{"step":torch.tensor(3.),"exp_avg":torch.ones(2),"exp_avg_sq":torch.ones(2)}}}
    schedule = EpochSchedule();schedule.completed=3
    payload = {"schema":SCHEMA,"identity":identity,"initial_sha":initial,"model":model,"optimizer":opt,
        "scheduler":schedule.state_dict(),"rng":rng.capture(),"ancestor":{"campaign":"SYNTHETIC_EPOCH_ENGINE_v1","parent_last_sha":None},
        "epoch_receipt":{"epoch":1,"update":3,"train":train_receipt,"validation":validation,
                         "formal_epoch":0,"FORMAL_OPTIMIZER_STEPS":0}}
    return payload,identity,model,template,train,val,initial


def test_full_metadata_last_roundtrip():
    p,*args=fixture(); validate_last(p,*args)
    store=EpochStore();ref=store.save("handmade_epoch_metadata",p)
    validate_last(store.read(ref),*args)
    assert state_digest(store.read(ref))==state_digest(p)


@pytest.mark.parametrize("fault",["seed","arm","code","protocol","year2025","model_missing","optimizer_missing",
    "epoch","update","train_missing_scene","val_missing_scene","duplicate_scene","order","wrong_step_lr",
    "clip","wrong_denominator","metric_weighted","scheduler","optimizer_step","optimizer_moment",
    "nan","ancestor","formal_updates","bool_formal_updates","unknown_field","rng_missing"])
def test_full_last_rejects_faults(fault):
    original,*args=fixture();p=copy.deepcopy(original)
    if fault in ("seed","arm"):p["identity"]["run"]["seed" if fault=="seed" else "experiment_id"]="INVALID"
    elif fault in ("code","protocol"):p["identity"][fault+"_sha"]="0"*64
    elif fault=="year2025":p["identity"]["synthetic_data_years"]=[2025]
    elif fault in ("model_missing","optimizer_missing","rng_missing"):p.pop(fault.removesuffix("_missing"))
    elif fault=="epoch":p["epoch_receipt"]["epoch"]=9
    elif fault=="update":p["epoch_receipt"]["update"]=4
    elif fault in ("train_missing_scene","val_missing_scene"):
        p["epoch_receipt"]["train" if fault.startswith("train") else "validation"]["coverage"]["visited_ids"].pop()
    elif fault=="duplicate_scene":p["epoch_receipt"]["train"]["coverage"]["visited_ids"][1]=p["epoch_receipt"]["train"]["coverage"]["visited_ids"][0]
    elif fault=="order":p["epoch_receipt"]["train"]["coverage"]["visited_ids"].reverse()
    elif fault=="wrong_step_lr":p["epoch_receipt"]["train"]["batch_records"][0]["lr"]=1e-4
    elif fault=="clip":p["epoch_receipt"]["train"]["batch_records"][0]["post_clip_norm"]=6.
    elif fault=="wrong_denominator":p["epoch_receipt"]["validation"]["N_valid"]=6860
    elif fault=="metric_weighted":p["epoch_receipt"]["validation"]["lambda_in_common_metric"]=True
    elif fault=="scheduler":p["scheduler"]["original_horizon"]=47052
    elif fault=="optimizer_step":p["optimizer"]["state"][0]["step"]=torch.tensor(2.)
    elif fault=="optimizer_moment":p["optimizer"]["state"][0].pop("exp_avg_sq")
    elif fault=="nan":p["model"]["synthetic_fixture"][0]=float("nan")
    elif fault=="ancestor":p["ancestor"]["parent_last_sha"]="0"*64
    elif fault=="formal_updates":p["epoch_receipt"]["FORMAL_OPTIMIZER_STEPS"]=3
    elif fault=="bool_formal_updates":p["epoch_receipt"]["FORMAL_OPTIMIZER_STEPS"]=False
    elif fault=="unknown_field":p["approved"]=True
    with pytest.raises((ValueError,FloatingPointError,KeyError)):validate_last(p,*args)
    assert state_digest(original["model"])==state_digest(args[1])


@pytest.mark.parametrize("completed",[3,6])
def test_epoch_schedule_restores_true_s0_prefix(completed):
    schedule=EpochSchedule();schedule.completed=completed
    other=EpochSchedule();other.load_state_dict(schedule.state_dict())
    opt=torch.optim.AdamW([torch.nn.Parameter(torch.ones(1))])
    assert other.prepare(opt)==learning_rate_prefix(completed+1)


@pytest.mark.parametrize("count",[True,7,47052])
def test_epoch_schedule_rejects_overscope(count):
    s=EpochSchedule();state=s.state_dict();state["completed"]=count
    with pytest.raises(ValueError):s.load_state_dict(state)

