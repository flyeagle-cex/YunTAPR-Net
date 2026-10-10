# 新增源码逐文件学习

先阅读上一轮[损失手册](../../phase_b_v2_ablation_implementation/v1/RESEARCHER_CODE_STUDY_GUIDE.md)。本轮顺序：synthetic→adapter→initialization→controls→resources/pins/safety→测试与工具。

## synthetic.py：人工张量与资格

SyntheticBatch是frozen dataclass，但Tensor内容仍可变，因此每次validate。x为FP32[2,1或6,501,501]；native_valid同形bool；rate为原FP32[2,1,100,100]，reference_valid/region_mask独立同形bool。输入/参考不要求梯度，模型参数需要梯度。

validate(kind)先核验scope、空data_years、两个人工ID、槽顺序，再检查shape/device/dtype/finite及3430有效监督。计数不能证明地理资格。to(device)用dataclasses.replace返回新batch，元数据保留。

make_synthetic_pair没有外部路径。arange/reshape/广播生成有限sin模式，clone使末槽成为独立Tensor。mask用<3430造人工布局；nextafter生成阈值上侧相邻值。练习：解释先double后比较0.1为什么可能改变边界，缺native像元为什么整场景拒绝。

## adapter.py：原输出到既有loss

forward_synthetic先验证batch/实验ID，检查exact模型类型、train模式、FP32参数与epsilon；autocast以BF16执行模型，原quantile头内部保留FP32 raw/FP64 q。函数返回output与loss，没有backward/optimizer。

loss_from_output检查LogDomainOutput、三个输出shape/device/finite、q守卫、概率support和sigmoid一致性，再调用已有candidate_loss。get_config决定唯一候选参数，科学CPB不乘lambda。练习：为何99×100不能自动resize为100×100。

## initialization.py：真实fresh与同形复制

seeded_environment是contextmanager：yield前固定随机源和确定性，finally恢复调用者；torch.random.fork_rng恢复Torch状态，Python/NumPy另存另还。进程hashseed保持2026，不伪称运行中修改环境变量可改变hash。

fresh_paired_models先过资源/SHA，再构造B0、重新seed构造B1。state_dict中的Tensor引用实际新参数，b[name].copy_(a[name])在no_grad中写入新初态，不是梯度优化。不同shape的两个输入权重before/after SHA必须相同，零skip保留。parameter_groups只分类计数，不构造AdamW。

state_digest包含dtype/shape/字节；state_dict不含非持久projection.indices，所以另摘要named_buffers。proof保存SHA和事实，不保存权重或批准。练习：同seed为何不能让不同输入通道的两模型天然拥有相同后续参数。

## controls.py：规则不是执行权

isolated_run_id重验RunSpec并加合成前缀。candidate_plan生成设计元数据；audit_plan比字段集合/类型/值，额外自报批准字段拒绝，合法仍can_launch=false。

synthetic_epoch_order用独立Generator(seed+epoch_index)，randperm不消耗全局模型随机流。endpoint_boundary是假想预算，不证明epoch实际完成；9之后next为None。

reject_resume复用旧身份检查后继续拒绝未认证批准；reject_formal_start调用永远抛错的BlockedRunner。练习：分别传True、APPROVED和dict观察为什么都不能启动。

## resources.py：构造前的资源检查

host_available_bytes读取Windows系统资源。resource_snapshot(full_backward)记录主机/磁盘，完整backward额外检查CUDA BF16和free/total；require_resources不足即抛ResourceLimit，不替调用者改参数。门槛不保证绝无OOM，其他进程可能改变资源。

## pins.py：来源身份

verify_frozen_sources先核验身份清单自身SHA，再读66个仓库公开文件字节；resolve/is_relative_to禁止外部路径。私有mask只声明未打开。SHA证明相同字节，不证明科学结论。

## safety.py：独立进程保护

reject_restricted_path拒绝raw/checkpoint/2025，CSV必须为绑定的精确仓库路径。install_process_file_guard安装sys.addaudithook监听open，先核验清单SHA再建立允许集。守卫不能在该测试进程撤销，退出进程即释放。

synthetic_operation_guards用ExitStack和patch临时把step、load/save/load_state_dict/expm1替为抛错函数，退出恢复。未构造optimizer来试step。Python仍可被外部代码改变，因此不是OS沙箱；正式权限须另行独立批准。

## __init__.py：scope标记

只有包说明与SCOPE常量；改变字符串不能让BlockedRunner获得训练循环。

## 测试与计算图

test_adapter_controls有86个CPU实例，覆盖完整目标接口、身份/shape/dtype/mask、候选越界、恢复/文件/资源拒绝。test_initialization有5例：3seed真实跨臂初态、顺序对照、SHA。test_cuda_e2e有6例完整模型，E0额外比较原loss全参数梯度。conftest限定CPU线程、安装守卫并独立写JSON。

autograd.grad(loss,(logit,qlog))检查输出处梯度；loss.backward沿完整图累积parameter.grad。retain_graph只用于E0二次反向对照，不是训练策略；zero_grad清梯度，不更新参数；detach只用于日志，objective保留计算图。

## 执行与交付脚本

run_checks启动有上限的子进程，append-only记录XML/log/JSON，无自动重试；test_process先过文件/资源门，CUDA首次失败停止。static_audit只读AST/SHA/结果，不import torch。build_delivery及export/close工具只处理文档和身份。

复现：项目CUDA Python运行scripts/phase_b_v2_isolated_integration/run_checks.py，指定--phase cpu或cuda、--attempt新编号。pytest复用上一轮私有依赖，不改项目环境。更换源码或依赖必须新测，旧PASS不自动继承。

## 实际代码摘录

下列函数按实际AST完整提取，不是第二份可导入实现。

### adapter.py：forward_synthetic，第36行起

SHA256：a056e32ca2a97c32bb045e3b5e5c4e05b6ca0288316f906af0d47d9e78422116。

```python
def forward_synthetic(model: torch.nn.Module, batch: SyntheticBatch, kind: str,
                      experiment_id: str) -> tuple[LogDomainOutput, CandidateLossResult]:
    """One full synthetic forward/loss; no backward, loop, optimizer or file I/O."""
    batch.validate(kind)
    get_config(experiment_id)  # reject invalid arm before model execution
    expected = {"B0_MATCHED_V2": B0MatchedV2, "B1_V2": B1V2}[kind]
    if type(model) is not expected or not model.training:
        raise ValueError("Exact frozen v2 architecture in train mode required")
    if any(p.dtype != torch.float32 or p.device != batch.x.device for p in model.parameters()):
        raise ValueError("Frozen FP32 parameter/device contract required")
    if model.heads.numerics.epsilon_w != 1e-4 or model.heads.numerics.epsilon_span != 1e-4:
        raise ValueError("Frozen v2 epsilon changed")
    with torch.autocast(batch.x.device.type, dtype=torch.bfloat16, enabled=True):
        output = model(batch.x, batch.native_valid)
        result = loss_from_output(output, batch, kind, experiment_id)
    if output.native_feature_shape != (2, 48, 501, 501) or output.target_feature_shape != (2, 48, 100, 100):
        raise ValueError("Native/SP04 feature shape mismatch")
    if output.rain_logit.dtype != torch.bfloat16:
        raise ValueError("Frozen BF16 occurrence path required, no precision fallback")
    if output.target_support_fraction.shape != (2, 1, 100, 100) or not bool((output.target_support_fraction == 1).all()):
        raise ValueError("Full SP04 support required")
    if not bool((output.b13_invalid_count == 0).all()) or not bool((output.b13_valid_fraction == 1).all()):
        raise ValueError("Native complete-support diagnostics mismatch")
    return output, result
```

### initialization.py：fresh_paired_models，第48行起

SHA256：2a232472d55006aa44d7129d10a01d07357037ae2d4bb42a43da287f3c4d0774。

```python
def fresh_paired_models(seed: int) -> tuple[dict[str, torch.nn.Module], dict]:
    admission = resource_snapshot(full_backward=False)
    require_resources(admission)  # before either full model constructor
    pins = verify_frozen_sources()
    numerics = CandidateNumerics(epsilon_w=1e-4, epsilon_span=1e-4)
    with seeded_environment(seed):
        anchor = B0MatchedV2(numerics=numerics, root=REPO)
        # Reset every proposed RNG source independently before B1 construction.
        random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)
        temporal = B1V2(numerics=numerics, root=REPO)
        a, b = anchor.state_dict(), temporal.state_dict()
        if a.keys() != b.keys():
            raise ValueError("Frozen paired tensor names differ")
        different = {name for name in a if a[name].shape != b[name].shape}
        if different != INPUT_DIFFERENCES:
            raise ValueError("Unexpected model input shape differences")
        native = {name: state_digest(b[name]) for name in sorted(different)}
        with torch.no_grad():
            for name in a:
                if name not in different:
                    if a[name].dtype != b[name].dtype:
                        raise ValueError("Paired state dtype differs")
                    b[name].copy_(a[name])
        if native != {name: state_digest(b[name]) for name in sorted(different)}:
            raise ValueError("Native B1 input initialization changed")
        if not all(torch.equal(a[name], b[name]) for name in a if name not in different):
            raise ValueError("Shared initialization not identical")
        models = {"B0_MATCHED_V2": anchor, "B1_V2": temporal}
        counts = {kind: parameter_groups(model, check_counts=False)[1]["counts"] for kind, model in models.items()}
        expected_totals = {"B0_MATCHED_V2": 4329410, "B1_V2": 4331810}
        if any(counts[k]["total"] != expected_totals[k] for k in models):
            raise ValueError("Frozen parameter count changed")
        proof = {"scope": SCOPE, "seed": seed, "actual_fresh_models_constructed": True,
                 "historical_checkpoint_loaded": False, "optimizer_created": False,
                 "state_sha256": {k: state_digest(m.state_dict()) for k, m in models.items()},
                 "buffers_sha256": {k: state_digest(dict(m.named_buffers())) for k, m in models.items()},
                 "shared_tensor_sha256": {n: state_digest(a[n]) for n in a if n not in different},
                 "native_B1_input_sha256": native, "same_shape_shared_bit_identical": True,
                 "native_zero_skip_preserved": bool((b["backbone.enc0.skip.weight"] == 0).all()),
                 "post_pair_rng_sha256": state_digest(capture_rng()), "parameter_counts": counts,
                 "source_pins_verified": pins, "resource_admission": admission,
                 "FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED": False}
    return models, proof
```

### controls.py：reject_resume，第62行起

SHA256：33c211f96b80ea500b65b0ee21e56e8557a62ddf5aa9d633d4f670e69a89ce74。

```python
def reject_resume(metadata: dict, expected: dict, *, checkpoint_kind: str,
                  resume_approval_reference: str | None = None) -> None:
    if checkpoint_kind != "LAST":
        raise ValueError("Only complete LAST can be proposed for independent review")
    # Existing candidate checker binds run/LAST/code/protocol/data/init and epoch.
    review_checkpoint_binding(metadata, expected, resume_approval_reference=resume_approval_reference)
    if resume_approval_reference is None:
        raise FormalExecutionBlocked("Independent LAST-bound resume approval is absent")
    raise FormalExecutionBlocked("A reference string is not authenticated human approval; no state loader exists")
```
