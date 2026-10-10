"""Future signed approval interfaces only. No issuer, verifier or real runner."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class FutureApprovalBinding:
    protocol_sha: str
    code_sha: str
    data_manifest_sha: str
    paired_qualification_sha: str
    scaler_sha: str
    mask_sha: str
    resource_plan_sha: str
    run_scope_sha: str
    independent_event_reference: str
    researcher_identity_reference: str


@dataclass(frozen=True)
class FutureResumeBinding:
    last_sha: str
    execution_authorization_ancestor: str
    completed_epoch_receipt_sha: str
    independent_new_resume_event: str


class FutureAuthorityVerifier(Protocol):
    """Must be independently implemented/reviewed; a reference is not proof."""
    def verify_independent_approval(self, binding: FutureApprovalBinding) -> None: ...
    def verify_independent_resume(self, binding: FutureResumeBinding) -> None: ...


def start_formal(*args, **kwargs) -> None:
    raise PermissionError("Formal data connector and independent approval verifier are absent; entry is non-executable")


def open_real_data(*args, **kwargs) -> None:
    raise PermissionError("2023/2024/2025 observational/scaler/mask preflight not authorized")

