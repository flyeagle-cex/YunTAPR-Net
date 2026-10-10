# 研究者代码学习手册与注释源码副本

本轮研究者已委托Codex先实现候选，再由研究者学习与独立审查。以下副本与实际候选源码按SHA绑定，不是另一份可导入模块；修改学习副本不会修改真实实现。所有代码属于候选，最终科学决定仍由研究者作出。

## 建议学习顺序与小练习

1. config.py：先理解函数/关键字参数、dataclass、tuple和type检查。练习写出三臂的唯一不同项，手算18身份和每run47052更新。
2. validation.py：理解[B,C,H,W]、bool索引、shape/device/dtype与交集。练习画出两个mask交集，并解释invalid reference临时clean不等于修改源数据。
3. focal.py：对照F1–F4，先手算gamma0值/梯度，再理解gamma2对权重也求导。练习指出误删alpha会如何改变E1。
4. pinball.py：先看signed errors内核，再看公开严格q入口。练习手算高tau欠/过预测惩罚，解释mean32与sum像元的顺序。
5. total.py和metrics.py：用T1/T2核对两个分母、lambda一次与无雨None。练习合并两个不同雨数batch的CPB。
6. test_gradients.py：认识requires_grad、叶子、grad_fn、backward、autograd.grad及finite difference。练习从链式法则推导q梯度的lambda/N_valid因子。
7. readiness.py：阅读metadata而非真实state，尝试仅在个人合成副本中更改一个SHA，理解BLOCKED与数学PASS的区别。

## 共同语法与计算图

from .config是包内相对导入，__all__只定义公开名称，不授予权限。->Tensor、tuple[int,...]等是类型提示，不能替代if/raise检查。@dataclass自动生成构造与比较，frozen阻止普通字段重赋值但不冻结内部dict/Tensor。@property允许以属性形式读派生值；@classmethod的cls代表类。

Python中的and/or短路有助在错误dtype之前停止；type(x)is int排除bool。with上下文离开后恢复autocast设置。torch.where返回新Tensor；bool索引选择元素，.movedim重新安排轴，.squeeze(1)只删单例通道。reshape不等于detach，类型转换也保留可微路径。

forward是由输入算出loss并构图；backward按链式法则累加叶子.grad。autograd.grad直接返回梯度，默认不会像backward一样累加到.grad。detach/no_grad用于报告分支，不能放到训练loss中截断梯度。gradcheck把自动微分与FP64中央差分比较；在折点不适用唯一经典导数。当前仅合成叶子参与图，没有模型参数更新或Optimizer。

工程保护包括finite/shape/device/type拒绝、SHA检查和BlockedRunner；科学定义包括alpha/gamma、32tau、log域、雨阈值和分母。两者都重要，但工程PASS不能自动批准科学假设。[PyTorch autograd](https://docs.pytorch.org/docs/2.7/notes/autograd.html)及[混合精度说明](https://docs.pytorch.org/docs/2.7/amp.html)提供API背景；项目公式与来源定位见对应walkthrough/source_identity。

## 测试和交付工具也应理解

conftest.py的autouse fixture在每个测试前禁止step、torch.load/save和expm1，结束后由monkeypatch恢复原方法。synthetic_case只用linspace/arange/tensor构造小张量，clone().requires_grad_()建立可观察梯度的叶子。rate/masks没有梯度。test_losses用手算和冻结函数，不与新实现自己互证；test_gradients用解析式/差分；test_readiness只改内存metadata；test_cuda是可选独立进程的三臂CPU/GPU对照。

run_checks.py调用pytest子进程而不是模型runner，60秒timeout会终止自己启动的测试进程，保存完整输出与XML，不中断别人的任务。static_review.py只AST与SHA，无torch import；author_delivery.py/后续export/close工具处理文档和元数据，不读观测或权重。若修改真实候选源码，必须重新测试并用新版本身份归档，不能只改副本或覆盖已发表结果。

## __init__.py：实际源码、函数位置与副本

来源 src/yuntapr/experimental/phase_b_v2_ablations/__init__.py。

SHA256：55207122a41dd3112f3933750f78a1e2318249a38b01f37f4d00badec3de418b。参数语义见对应walkthrough；下面是实际完整注释源码副本。

|函数或方法（参数名）|源码行|阅读入口|
|---|---|---|

```python
"""Candidate loss APIs only: no model, data loader, optimizer or training loop."""
from .config import AblationConfig, RunSpec, get_config, proposed_runs
from .focal import occurrence_numerator
from .pinball import conditional_pinball_numerator
from .total import CandidateLossResult, candidate_loss, combine_numerators

__all__ = ["AblationConfig", "RunSpec", "get_config", "proposed_runs",
           "occurrence_numerator", "conditional_pinball_numerator",
           "CandidateLossResult", "candidate_loss", "combine_numerators"]
```

## config.py：实际源码、函数位置与副本

来源 src/yuntapr/experimental/phase_b_v2_ablations/config.py。

SHA256：5ae850c28417b555dc7825bd204f95f8275bc3ddc5b64cbfa230a2517d4d5e3a。参数语义见对应walkthrough；下面是实际完整注释源码副本。

|函数或方法（参数名）|源码行|阅读入口|
|---|---|---|
|finite_number(name, value)|12|完整type/default见下面源码|
|get_config(experiment_id)|34|完整type/default见下面源码|
|proposed_runs()|62|完整type/default见下面源码|
|workload()|66|完整type/default见下面源码|
|learning_rate_prefix(update)|75|完整type/default见下面源码|
|__post_init__(self)|26|完整type/default见下面源码|
|__post_init__(self)|46|完整type/default见下面源码|
|run_id(self)|54|完整type/default见下面源码|
|stage(self)|58|完整type/default见下面源码|

```python
"""Three closed, unapproved loss conditions and 18 candidate run identities."""
from __future__ import annotations
from dataclasses import dataclass
import math

_PARAMETERS = {"E0": (.5, 2., 1.), "E1": (.5, 0., 1.), "E2": (.5, 2., 2.)}
MODELS = ("B0_MATCHED_V2", "B1_V2")
SEEDS = (2026, 2027, 2028)
PROTOCOL_STATUS = "PROPOSED_FOR_RESEARCHER_APPROVAL"


def finite_number(name: str, value: object) -> float:
    """Reject booleans, strings, NaN and infinity rather than silently coerce."""
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{name}: finite Python int/float required, excluding bool")
    return float(value)


@dataclass(frozen=True)
class AblationConfig:
    experiment_id: str
    alpha: float
    gamma: float
    lambda_q: float

    def __post_init__(self) -> None:
        if type(self.experiment_id) is not str or self.experiment_id not in _PARAMETERS:
            raise ValueError("Unknown experiment ID; only E0/E1/E2 are candidates")
        values = tuple(finite_number(k, getattr(self, k)) for k in ("alpha", "gamma", "lambda_q"))
        if values != _PARAMETERS[self.experiment_id]:
            raise ValueError("Experiment parameters do not match the closed candidate condition")


def get_config(experiment_id: str) -> AblationConfig:
    if type(experiment_id) is not str or experiment_id not in _PARAMETERS:
        raise ValueError("Unknown experiment ID; no parameter search or automatic selection")
    return AblationConfig(experiment_id, *_PARAMETERS[experiment_id])


@dataclass(frozen=True)
class RunSpec:
    experiment_id: str
    model: str
    seed: int

    def __post_init__(self) -> None:
        get_config(self.experiment_id)
        if type(self.model) is not str or self.model not in MODELS:
            raise ValueError("Unknown candidate model identity")
        if type(self.seed) is not int or self.seed not in SEEDS:
            raise ValueError("Candidate seeds are exactly 2026/2027/2028")

    @property
    def run_id(self) -> str:
        return f"{self.experiment_id}__{self.model}__s{self.seed}"

    @property
    def stage(self) -> int:
        return 1 if self.seed == 2026 else 2


def proposed_runs() -> tuple[RunSpec, ...]:
    return tuple(RunSpec(arm, model, seed) for seed in SEEDS for arm in _PARAMETERS for model in MODELS)


def workload() -> dict[str, int]:
    """Pure arithmetic; these counts do not mean that any updates took place."""
    train_batches, val_batches = (10455 + 1) // 2, (10501 + 7) // 8
    return {"runs": 18, "epochs": 9, "updates_per_epoch": train_batches,
            "updates_per_run": 9 * train_batches, "updates_total": 18 * 9 * train_batches,
            "validation_batches_per_epoch": val_batches, "validation_batches_total": 18 * 9 * val_batches,
            "stage1_updates": 6 * 9 * train_batches, "stage2_updates": 12 * 9 * train_batches}


def learning_rate_prefix(update: int) -> float:
    """First nine epochs of the original 50-epoch trajectory, no optimizer."""
    if type(update) is not int or not 1 <= update <= 47052:
        raise ValueError("Candidate one-based update must be in [1,47052]")
    if update <= 5228:
        return 1e-4 * (update / 5228)  # warmup is not clamped to the cosine floor
    progress = (update - 5228) / (261400 - 5228)
    return 1e-6 + (1e-4 - 1e-6) * (1 + math.cos(math.pi * progress)) / 2
```

## validation.py：实际源码、函数位置与副本

来源 src/yuntapr/experimental/phase_b_v2_ablations/validation.py。

SHA256：05885c309b6cf930a57f30b25438c8664be2ddc5a36eb9f86de82654e886beb0。参数语义见对应walkthrough；下面是实际完整注释源码副本。

|函数或方法（参数名）|源码行|阅读入口|
|---|---|---|
|image_tensor(name, value, channels)|12|完整type/default见下面源码|
|same_shape_device(name, value, reference)|19|完整type/default见下面源码|
|boolean_mask(name, value, reference)|26|完整type/default见下面源码|
|finite_tensor(name, value)|32|完整type/default见下面源码|
|occurrence_logits(logit)|37|完整type/default见下面源码|
|quantiles(qlog)|46|完整type/default见下面源码|
|graph_zero(value, *, dtype)|54|完整type/default见下面源码|
|supervision(logit, qlog, rate, imerg_valid, yunnan_mask)|69|完整type/default见下面源码|

```python
"""Explicit tensor contracts; no output repair and no physical conversion."""
from __future__ import annotations
from dataclasses import dataclass
import torch
from yuntapr.models.quantile_v2.outputs import validate_log_quantiles


class ZeroValidPixelsError(ValueError):
    """Stop a loss call with zero supervision; never imply a skipped update."""


def image_tensor(name: str, value: torch.Tensor, channels: int) -> None:
    if not isinstance(value, torch.Tensor) or value.layout != torch.strided:
        raise ValueError(f"{name}: dense strided Tensor required")
    if value.ndim != 4 or value.shape[1] != channels or any(n <= 0 for n in value.shape):
        raise ValueError(f"{name}: nonempty [B,{channels},H,W] required")


def same_shape_device(name: str, value: torch.Tensor, reference: torch.Tensor) -> None:
    if not isinstance(value, torch.Tensor) or value.shape != reference.shape:
        raise ValueError(f"{name}: exact shape required; mask broadcasting is forbidden")
    if value.device != reference.device:
        raise ValueError(f"{name}: device mismatch")


def boolean_mask(name: str, value: torch.Tensor, reference: torch.Tensor) -> None:
    same_shape_device(name, value, reference)
    if value.dtype != torch.bool or value.layout != torch.strided:
        raise ValueError(f"{name}: dense bool Tensor required")


def finite_tensor(name: str, value: torch.Tensor) -> None:
    if not bool(torch.isfinite(value).all()):
        raise FloatingPointError(f"{name}: NaN/Inf forbidden, including masked output pixels")


def occurrence_logits(logit: torch.Tensor) -> None:
    image_tensor("logit", logit, 1)
    if logit.dtype not in (torch.float16, torch.bfloat16, torch.float32, torch.float64):
        raise ValueError("logit: real floating dtype required")
    if logit.device.type not in ("cpu", "cuda"):
        raise ValueError("logit: this candidate supports CPU/CUDA only")
    finite_tensor("logit", logit)


def quantiles(qlog: torch.Tensor) -> None:
    image_tensor("qlog", qlog, 32)
    if qlog.device.type not in ("cpu", "cuda"):
        raise ValueError("qlog: this candidate supports CPU/CUDA only")
    # Reuse the frozen FP64, finite, support and strict-order guards unchanged.
    validate_log_quantiles(qlog)


def graph_zero(value: torch.Tensor, *, dtype: torch.dtype | None = None) -> torch.Tensor:
    """Empty-view sum gives connected zero without overflowing sum(value)*0."""
    return value.reshape(-1)[:0].sum(dtype=dtype)


@dataclass(frozen=True)
class Supervision:
    valid: torch.Tensor
    rainy: torch.Tensor
    rainy_valid: torch.Tensor
    clean_rate: torch.Tensor
    n_valid: int
    n_rain: int


def supervision(logit: torch.Tensor, qlog: torch.Tensor, rate: torch.Tensor,
                imerg_valid: torch.Tensor, yunnan_mask: torch.Tensor) -> Supervision:
    occurrence_logits(logit)
    same_shape_device("qlog spatial slice", qlog[:, :1] if isinstance(qlog, torch.Tensor) and qlog.ndim == 4 else qlog, logit)
    quantiles(qlog)
    same_shape_device("rate", rate, logit)
    if rate.dtype != torch.float32 or rate.layout != torch.strided or rate.requires_grad:
        raise ValueError("rate: nondifferentiable dense float32 IMERG reference required")
    boolean_mask("imerg_valid", imerg_valid, logit)
    boolean_mask("yunnan_mask", yunnan_mask, logit)
    valid = imerg_valid & yunnan_mask
    n_valid = int(valid.sum().item())
    if n_valid == 0:
        raise ZeroValidPixelsError("ZERO_VALID_SUPERVISED_YUNNAN_PIXELS; no silent skip")
    if not bool(torch.isfinite(rate[valid]).all()) or bool((rate[valid] < 0).any()):
        raise ValueError("Supervised valid precipitation must be finite nonnegative")
    # Only an ephemeral arithmetic target is cleaned, exactly as in the old loss.
    clean = torch.where(valid, rate, torch.zeros_like(rate))
    rainy = clean > torch.tensor(.1, dtype=torch.float32, device=rate.device)
    rainy_valid = rainy & valid  # compare BEFORE converting rate to FP64
    return Supervision(valid, rainy, rainy_valid, clean, n_valid, int(rainy_valid.sum().item()))
```

## focal.py：实际源码、函数位置与副本

来源 src/yuntapr/experimental/phase_b_v2_ablations/focal.py。

SHA256：828189dfac57fdaf0520ffc8a37fb4b7608eccbd6154f3c04538049fc5313f94。参数语义见对应walkthrough；下面是实际完整注释源码副本。

|函数或方法（参数名）|源码行|阅读入口|
|---|---|---|
|occurrence_numerator(logit, rainy, valid, *, alpha, gamma)|9|完整type/default见下面源码|

```python
"""Stable candidate focal numerator, explicitly separate from normalization."""
from __future__ import annotations
import torch
from torch.nn import functional as F
from .config import finite_number
from .validation import boolean_mask, finite_tensor, graph_zero, occurrence_logits


def occurrence_numerator(logit: torch.Tensor, rainy: torch.Tensor, valid: torch.Tensor,
                         *, alpha: float, gamma: float) -> torch.Tensor:
    alpha, gamma = finite_number("alpha", alpha), finite_number("gamma", gamma)
    if not 0 <= alpha <= 1 or gamma < 0:
        raise ValueError("alpha in [0,1] and gamma>=0 required")
    occurrence_logits(logit)
    boolean_mask("rainy hard labels", rainy, logit)
    boolean_mask("valid", valid, logit)
    dtype = torch.float64 if logit.dtype == torch.float64 else torch.float32
    with torch.autocast(logit.device.type, enabled=False):
        if not bool(valid.any()):
            return graph_zero(logit, dtype=dtype)
        # FP16/BF16 inputs retain gradients through this cast; BCE computes FP32.
        logits, labels = logit[valid].to(dtype), rainy[valid]
        bce = F.binary_cross_entropy_with_logits(logits, labels.to(dtype), reduction="none")
        alpha_t = torch.where(labels, torch.full_like(logits, alpha), torch.full_like(logits, 1 - alpha))
        if gamma == 0:
            terms = alpha_t * bce  # deliberately .5*BCE for E1, not plain BCE
        else:
            pt = torch.exp(-bce)
            terms = alpha_t * (1 - pt).pow(gamma) * bce
        result = terms.sum()
    finite_tensor("occurrence numerator", result)
    return result
```

## pinball.py：实际源码、函数位置与副本

来源 src/yuntapr/experimental/phase_b_v2_ablations/pinball.py。

SHA256：cc4c4c742a2ce5c465dc8c2eee786b85378d4d8845d7e065783f986bc264e25f。参数语义见对应walkthrough；下面是实际完整注释源码副本。

|函数或方法（参数名）|源码行|阅读入口|
|---|---|---|
|frozen_taus(device)|7|完整type/default见下面源码|
|_pinball_from_errors(error, rainy_valid)|11|完整type/default见下面源码|
|conditional_pinball_numerator(qlog, log_target, rainy_valid)|32|完整type/default见下面源码|

```python
"""FP64 conditional pinball in log1p(mm/h), fixed 32-tau mean then sum."""
from __future__ import annotations
import torch
from .validation import boolean_mask, finite_tensor, graph_zero, image_tensor, quantiles, same_shape_device


def frozen_taus(device: torch.device | str | None = None) -> torch.Tensor:
    return (torch.arange(1, 33, device=device, dtype=torch.float64) - .5) / 32


def _pinball_from_errors(error: torch.Tensor, rainy_valid: torch.Tensor) -> torch.Tensor:
    """Private arithmetic kernel: signed errors are NOT model quantiles.

    This permits the P1-P4 hand-calculated constant-error fixtures without
    pretending that constant qlog is a legal strictly ordered v2 prediction.
    """
    image_tensor("error", error, 32)
    if error.dtype != torch.float64:
        raise ValueError("Pinball signed errors require FP64")
    boolean_mask("rainy_valid", rainy_valid, error[:, :1])
    finite_tensor("pinball errors", error)
    if not bool(rainy_valid.any()):
        return graph_zero(error)
    selected = error.movedim(1, -1)[rainy_valid.squeeze(1)]  # [N_rain,32]
    tau = frozen_taus(error.device)
    per_pixel = torch.maximum(tau * selected, (tau - 1) * selected).mean(dim=-1)
    result = per_pixel.sum()
    finite_tensor("quantile numerator", result)
    return result


def conditional_pinball_numerator(qlog: torch.Tensor, log_target: torch.Tensor,
                                  rainy_valid: torch.Tensor) -> torch.Tensor:
    quantiles(qlog)
    same_shape_device("log_target", log_target, qlog[:, :1])
    image_tensor("log_target", log_target, 1)
    if log_target.dtype != torch.float64:
        raise ValueError("log_target requires FP64")
    boolean_mask("rainy_valid", rainy_valid, log_target)
    finite_tensor("log_target", log_target)
    if bool((log_target < 0).any()):
        raise ValueError("log_target must be nonnegative log1p(mm/h)")
    threshold_log = torch.log1p(torch.tensor(.1, dtype=torch.float32, device=qlog.device).double())
    if bool((log_target[rainy_valid] <= threshold_log).any()):
        raise ValueError("rainy_valid cannot select a dry or threshold-equal reference target")
    with torch.autocast(qlog.device.type, enabled=False):
        # Only the explicitly declared singleton tau axis is expanded.
        error = log_target - qlog
        return _pinball_from_errors(error, rainy_valid)
```

## total.py：实际源码、函数位置与副本

来源 src/yuntapr/experimental/phase_b_v2_ablations/total.py。

SHA256：9ce37393d2af2fbc762d198b2088cb4645d104d35f81b507c236bc3b39cf1ec1。参数语义见对应walkthrough；下面是实际完整注释源码副本。

|函数或方法（参数名）|源码行|阅读入口|
|---|---|---|
|combine_numerators(s_occ, s_qr, n_valid, *, lambda_q)|11|完整type/default见下面源码|
|candidate_loss(logit, qlog, rate, imerg_valid, yunnan_mask, *, config)|51|完整type/default见下面源码|
|scientific_conditional_pinball(self)|46|完整type/default见下面源码|

```python
"""Candidate training objective and unweighted components, no optimizer."""
from __future__ import annotations
from dataclasses import dataclass
import torch
from .config import AblationConfig, finite_number
from .focal import occurrence_numerator
from .pinball import conditional_pinball_numerator
from .validation import finite_tensor, supervision


def combine_numerators(s_occ: torch.Tensor, s_qr: torch.Tensor, n_valid: int,
                       *, lambda_q: float) -> torch.Tensor:
    weight = finite_number("lambda_q", lambda_q)
    if weight <= 0 or type(n_valid) is not int or n_valid <= 0:
        raise ValueError("Positive lambda_q and positive integer N_valid required")
    for name, value in (("S_occ", s_occ), ("S_qr", s_qr)):
        if not isinstance(value, torch.Tensor) or value.ndim != 0 or value.layout != torch.strided or value.dtype not in (torch.float32, torch.float64):
            raise ValueError(f"{name}: FP32/FP64 scalar Tensor required")
    if s_occ.device != s_qr.device:
        raise ValueError("Numerator device mismatch")
    if s_occ.device.type not in ("cpu", "cuda"):
        raise ValueError("Numerator device must be CPU/CUDA")
    for name, value in (("S_occ", s_occ), ("S_qr", s_qr)):
        finite_tensor(name, value)
        if bool(value < 0):
            raise ValueError(f"{name}: loss numerator must be nonnegative")
    result = (s_occ + weight * s_qr) / n_valid  # weight exactly once
    finite_tensor("weighted training objective", result)
    return result


@dataclass(frozen=True)
class CandidateLossResult:
    experiment_id: str
    s_occ: torch.Tensor
    s_qr: torch.Tensor
    training_objective: torch.Tensor
    weighted_quantile_per_valid: torch.Tensor
    n_valid: int
    n_rain: int
    conditional_skipped: bool
    status: str = "VALID_SYNTHETIC_OR_CANDIDATE_LOSS_CALL"
    execution_authorization: bool = False

    @property
    def scientific_conditional_pinball(self) -> torch.Tensor | None:
        # No lambda here. None explicitly means not estimable, not zero skill.
        return self.s_qr / self.n_rain if self.n_rain else None


def candidate_loss(logit: torch.Tensor, qlog: torch.Tensor, rate: torch.Tensor,
                   imerg_valid: torch.Tensor, yunnan_mask: torch.Tensor,
                   *, config: AblationConfig) -> CandidateLossResult:
    if type(config) is not AblationConfig:
        raise ValueError("Explicit closed AblationConfig required")
    config.__post_init__()  # revalidate even if external code bypassed frozen setattr
    target = supervision(logit, qlog, rate, imerg_valid, yunnan_mask)
    s_occ = occurrence_numerator(logit, target.rainy, target.valid, alpha=config.alpha, gamma=config.gamma)
    with torch.autocast(logit.device.type, enabled=False):
        s_qr = conditional_pinball_numerator(qlog, torch.log1p(target.clean_rate.double()), target.rainy_valid)
        total = combine_numerators(s_occ, s_qr, target.n_valid, lambda_q=config.lambda_q)
        weighted = config.lambda_q * s_qr / target.n_valid
    return CandidateLossResult(config.experiment_id, s_occ, s_qr, total, weighted,
                               target.n_valid, target.n_rain, target.n_rain == 0)
```

## metrics.py：实际源码、函数位置与副本

来源 src/yuntapr/experimental/phase_b_v2_ablations/metrics.py。

SHA256：3450edb2755339801a5fd55864091b1c22e0628fa49fce71bc5bff72811f9021。参数语义见对应walkthrough；下面是实际完整注释源码副本。

|函数或方法（参数名）|源码行|阅读入口|
|---|---|---|
|common_validation_sums(logit, qlog, rate, imerg_valid, yunnan_mask)|38|完整type/default见下面源码|
|__post_init__(self)|17|完整type/default见下面源码|
|from_candidate(cls, result)|24|完整type/default见下面源码|
|conditional_pinball(self)|28|完整type/default见下面源码|
|pooled(self, other)|31|完整type/default见下面源码|

```python
"""Unweighted reporting interface; common core always uses E0 in FP64."""
from __future__ import annotations
from dataclasses import dataclass
import math
import torch
from .config import get_config
from .total import CandidateLossResult, candidate_loss


@dataclass(frozen=True)
class ReportingSums:
    s_occ: float
    s_qr: float
    n_valid: int
    n_rain: int

    def __post_init__(self) -> None:
        if not all(type(x) in (float, int) and math.isfinite(x) and x >= 0 for x in (self.s_occ, self.s_qr)):
            raise ValueError("Finite nonnegative unweighted reporting sums required")
        if type(self.n_valid) is not int or type(self.n_rain) is not int or not 0 <= self.n_rain <= self.n_valid or self.n_valid <= 0:
            raise ValueError("Positive N_valid and integer 0<=N_rain<=N_valid required")

    @classmethod
    def from_candidate(cls, result: CandidateLossResult) -> ReportingSums:
        return cls(float(result.s_occ.detach()), float(result.s_qr.detach()), result.n_valid, result.n_rain)

    @property
    def conditional_pinball(self) -> float | None:
        return self.s_qr / self.n_rain if self.n_rain else None

    def pooled(self, other: ReportingSums) -> ReportingSums:
        # Pool sums/counts rather than averaging unequal-batch metric values.
        return ReportingSums(self.s_occ + other.s_occ, self.s_qr + other.s_qr,
                             self.n_valid + other.n_valid, self.n_rain + other.n_rain)


@torch.no_grad()
def common_validation_sums(logit: torch.Tensor, qlog: torch.Tensor, rate: torch.Tensor,
                           imerg_valid: torch.Tensor, yunnan_mask: torch.Tensor) -> ReportingSums:
    """Fixed gamma2/lambda1 arithmetic, not an arm's weighted train objective.

    Caller-supplied tensors only. This function does not run a model or read data.
    The current tests call it exclusively with explicitly synthetic tensors.
    """
    result = candidate_loss(logit.double(), qlog, rate, imerg_valid, yunnan_mask, config=get_config("E0"))
    return ReportingSums.from_candidate(result)
```

## readiness.py：实际源码、函数位置与副本

来源 src/yuntapr/experimental/phase_b_v2_ablations/readiness.py。

SHA256：2f6ca9f1f5cf0da458cc008e05bb24d4c1ecd776172f35bf1b8cef81f23492e3。参数语义见对应walkthrough；下面是实际完整注释源码副本。

|函数或方法（参数名）|源码行|阅读入口|
|---|---|---|
|require_sha(value, name)|17|完整type/default见下面源码|
|state_metadata_digest(tensors)|36|完整type/default见下面源码|
|audit_fresh_metadata(records)|68|完整type/default见下面源码|
|review_checkpoint_binding(metadata, expected, *, resume_approval_reference)|99|完整type/default见下面源码|
|__post_init__(self)|28|完整type/default见下面源码|
|validate(self)|56|完整type/default见下面源码|
|describe(self)|140|完整type/default见下面源码|
|run(self, *args, **kwargs)|147|完整type/default见下面源码|

```python
"""Metadata-only identity checks and an unconditionally blocked runner stub.

No torch import, tensor state loading, dataset access or approval issuance.
Synthetically valid metadata never implies that real initial states exist.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
import hashlib
import json
import re
from typing import NoReturn, Sequence
from .config import RunSpec, proposed_runs, workload

INPUT_DIFFERENCES = {"backbone.enc0.conv1.weight", "backbone.enc0.skip.weight"}


def require_sha(value: object, name: str) -> None:
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"{name}: lowercase SHA256 required, never a path or credential")


@dataclass(frozen=True)
class TensorIdentity:
    shape: tuple[int, ...]
    dtype: str
    sha256: str

    def __post_init__(self) -> None:
        if type(self.shape) is not tuple or not self.shape or not all(type(n) is int and n > 0 for n in self.shape):
            raise ValueError("Nonempty positive integer shape required")
        if self.dtype != "float32":
            raise ValueError("Frozen candidate parameter dtype is float32")
        require_sha(self.sha256, "tensor identity")


def state_metadata_digest(tensors: dict[str, TensorIdentity]) -> str:
    if type(tensors) is not dict or not tensors or not all(type(k) is str and k and
            type(v) is TensorIdentity for k, v in tensors.items()):
        raise ValueError("Named tensor identity metadata required")
    for value in tensors.values():
        value.__post_init__()
    body = json.dumps({k: asdict(v) for k, v in sorted(tensors.items())}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()


@dataclass(frozen=True)
class FreshRecord:
    run: RunSpec
    tensors: dict[str, TensorIdentity]
    state_sha256: str
    post_pair_rng_sha256: str
    epoch_order_sha256: str
    initializer_code_sha256: str
    historical_checkpoint_loaded: bool = False

    def validate(self) -> None:
        if type(self.run) is not RunSpec:
            raise ValueError("Closed candidate RunSpec required")
        self.run.__post_init__()
        for name in ("state_sha256", "post_pair_rng_sha256", "epoch_order_sha256", "initializer_code_sha256"):
            require_sha(getattr(self, name), name)
        if self.historical_checkpoint_loaded is not False:
            raise ValueError("Historical model/optimizer/RNG state transfer forbidden")
        if state_metadata_digest(self.tensors) != self.state_sha256:
            raise ValueError("Declared state digest differs from supplied tensor metadata")


def audit_fresh_metadata(records: Sequence[FreshRecord]) -> dict:
    """Review declarations only; cannot prove origins or instantiate a model."""
    if len(records) != 18 or not all(type(r) is FreshRecord for r in records):
        raise ValueError("Exactly 18 fresh metadata records required")
    for r in records:
        r.validate()
    table = {r.run.run_id: r for r in records}
    if set(table) != {r.run_id for r in proposed_runs()}:
        raise ValueError("Missing, duplicate or unregistered run identity")
    if len({r.initializer_code_sha256 for r in records}) != 1:
        raise ValueError("Initializer code identity differs across arms")
    for seed in (2026, 2027, 2028):
        subset = [r for r in records if r.run.seed == seed]
        if len({r.post_pair_rng_sha256 for r in subset}) != 1 or len({r.epoch_order_sha256 for r in subset}) != 1:
            raise ValueError("Same-seed RNG/order metadata differs")
        for model in ("B0_MATCHED_V2", "B1_V2"):
            arms = [r for r in subset if r.run.model == model]
            if len({r.state_sha256 for r in arms}) != 1:
                raise ValueError("Same-model same-seed full fresh states differ across arms")
        a = table[RunSpec("E0", "B0_MATCHED_V2", seed).run_id].tensors
        b = table[RunSpec("E0", "B1_V2", seed).run_id].tensors
        if a.keys() != b.keys():
            raise ValueError("B0/B1 parameter names differ")
        different = {k for k in a if a[k].shape != b[k].shape}
        if different != INPUT_DIFFERENCES or any(a[k] != b[k] for k in a if k not in different):
            raise ValueError("Only two frozen input-shape differences permitted; shared tensors must match")
    return {"metadata_consistent": True, "actual_model_instantiated": False,
            "actual_initialization_proven": False, "scope": "DECLARED_OR_SYNTHETIC_METADATA_ONLY",
            "can_launch_formal_training": False}


def review_checkpoint_binding(metadata: dict, expected: dict, *, resume_approval_reference: str | None = None) -> dict:
    """No files are opened and no state can be applied by this review.

    A supplied reference is not authenticated here and cannot authorize resume.
    Future formal integration must bind a real independent event to LAST SHA.
    """
    fields = {"run_id", "last_sha256", "model_sha256", "optimizer_sha256", "rng_sha256",
              "scheduler_sha256", "code_sha256", "protocol_sha256", "data_sha256", "init_sha256",
              "completed_epoch", "retained_updates", "boundary", "original_execution_reference"}
    if type(metadata) is not dict or set(metadata) != fields or type(expected) is not dict:
        raise ValueError("Closed checkpoint metadata required")
    if metadata["run_id"] not in {r.run_id for r in proposed_runs()}:
        raise ValueError("Checkpoint run identity is not in candidate matrix")
    for key in fields:
        if key.endswith("sha256"):
            require_sha(metadata[key], key)
    epoch, updates = metadata["completed_epoch"], metadata["retained_updates"]
    if type(epoch) is not int or not 1 <= epoch <= 9 or type(updates) is not int or updates != epoch * 5228:
        raise ValueError("Complete-epoch retained budget mismatch")
    if metadata["boundary"] != "COMPLETED_TRAIN_AND_VALIDATION_EPOCH_ONLY":
        raise ValueError("Partial epoch is not a legal LAST")
    if type(metadata["original_execution_reference"]) is not str or not metadata["original_execution_reference"]:
        raise ValueError("Original execution provenance reference missing")
    binding = {"run_id", "last_sha256", "code_sha256", "protocol_sha256", "data_sha256", "init_sha256"}
    if set(expected) != binding or any(metadata[k] != expected[k] for k in binding):
        raise ValueError("Expected LAST/code/protocol/data/init/run binding differs")
    if resume_approval_reference is not None and (type(resume_approval_reference) is not str or not resume_approval_reference):
        raise ValueError("Nonempty independent-event reference or None required")
    return {"metadata_consistent": True, "remaining_retained_updates": 47052 - updates,
            "next_epoch": epoch + 1 if epoch < 9 else None, "approval_authenticity_verified": False,
            "resume_approval_reference_present": resume_approval_reference is not None,
            "can_apply_checkpoint_state": False, "can_launch_formal_training": False}


class FormalExecutionBlocked(RuntimeError):
    pass


class BlockedRunner:
    """Design skeleton with no execution implementation, even after flag edits."""

    def describe(self) -> dict:
        return {"runs": [r.run_id for r in proposed_runs()], "budget": workload(),
                "runner_implemented": False, "can_launch_formal_training": False,
                "required": ["Independent scientific approval", "Researcher code review",
                             "Explicit formal integration approval", "Data and compute permissions",
                             "Real fresh/data/code identities", "Separately bound stage execution authorization"]}

    def run(self, *args: object, **kwargs: object) -> NoReturn:
        raise FormalExecutionBlocked("Candidate skeleton has NO TRAINING CAPABILITY; new reviewed runner and independent approvals required")
```
