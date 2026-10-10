"""Non-executing, fail-closed review of this proposed protocol's metadata.

This tool deliberately has no training, tensor, data-reader or authorization
capability. A structurally valid proposal always remains execution-blocked.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any
import hashlib
import json
import math
import re
import sys

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "docs/phase_b_v2_ablation_preregistration/v1"
SUPPORTED = {"$schema", "title", "description", "$comment", "type", "const", "enum",
             "required", "properties", "additionalProperties", "items", "minItems",
             "maxItems", "uniqueItems", "minimum", "maximum", "pattern"}


def equal_json(left: Any, right: Any) -> bool:
    """JSON numeric equivalence without treating bool as an integer."""
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isfinite(left) and math.isfinite(right) and left == right
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(equal_json(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(equal_json(a,b) for a,b in zip(left,right))
    return left == right


def schema_errors(value: Any, schema: dict, at: str = "$", errors: list[str] | None = None) -> list[str]:
    """Validate only the explicitly documented closed-schema keyword subset.

    Unknown schema keywords fail rather than being ignored. This is not a
    replacement for a general Draft2020-12 library or a scientific approval.
    """
    errors = [] if errors is None else errors
    if type(schema) is not dict or set(schema) - SUPPORTED:
        errors.append(at + ": unsupported or malformed schema")
        return errors
    kinds = {"object": type(value) is dict, "array": type(value) is list,
             "integer": type(value) is int, "number": type(value) in (int,float) and math.isfinite(value),
             "boolean": type(value) is bool, "string": type(value) is str, "null": value is None}
    if "type" in schema and not kinds.get(schema["type"], False):
        errors.append(at + ": type mismatch")
        return errors
    if "const" in schema and not equal_json(value, schema["const"]):
        errors.append(at + ": proposed constant mismatch")
    if "enum" in schema and not any(equal_json(value, v) for v in schema["enum"]):
        errors.append(at + ": enum mismatch")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        errors.extend(at + ": missing " + k for k in schema.get("required", []) if k not in value)
        if schema.get("additionalProperties") is False:
            errors.extend(at + ": unknown " + k for k in value if k not in props)
        for k, child in props.items():
            if k in value:
                schema_errors(value[k], child, at + "." + k, errors)
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", math.inf):
            errors.append(at + ": array length mismatch")
        if schema.get("uniqueItems") and any(equal_json(value[i],value[j]) for i in range(len(value)) for j in range(i)):
            errors.append(at + ": duplicate items")
        if "items" in schema:
            for i, child in enumerate(value):
                schema_errors(child, schema["items"], f"{at}[{i}]", errors)
    if type(value) in (int, float):
        if not math.isfinite(value) or value < schema.get("minimum", -math.inf) or value > schema.get("maximum", math.inf):
            errors.append(at + ": numeric domain mismatch")
    if isinstance(value,str) and "pattern" in schema and re.search(schema["pattern"],value) is None:
        errors.append(at + ": string pattern mismatch")
    return errors


def safe_reference_path(path: str) -> bool:
    """Only repository source/config/metadata references; no absolute/raw paths."""
    if not isinstance(path,str) or "\\" in path or ":" in path:
        return False
    item = PurePosixPath(path)
    return (not item.is_absolute() and ".." not in item.parts and item.as_posix() == path
            and item.suffix in {".py", ".json", ".md", ".yaml", ".csv"}
            and (path.startswith(("src/yuntapr/", "config/", "docs/")) or path in {
                "scripts/phase_b_v2_candidates/planning.py", "scripts/phase_b_v2_candidates/build_delivery.py"})
            and not any(p.lower() in {"raw","weights","checkpoints","2025"} for p in item.parts))


@dataclass(frozen=True)
class ReviewResult:
    candidate_valid: bool
    review_status: str
    errors: tuple[str, ...]
    blockers: tuple[str, ...]
    can_launch_formal_training: bool = False
    runner_implemented: bool = False
    authority_scope: str = "STATIC_PROPOSAL_REVIEW_ONLY"


def review_protocol(proposal: dict, schema: dict, *, identity_sha: str | None = None,
                    expected_refs: list[dict] | None = None,
                    observed_hashes: dict[str,str] | None = None) -> ReviewResult:
    """Pure review of supplied metadata, never a test of approval authenticity."""
    errors = schema_errors(proposal,schema)
    if type(proposal) is not dict:
        return ReviewResult(False,"REJECTED",tuple(errors),("Malformed proposal",))
    if identity_sha is None or proposal.get("source_identity_sha256") != identity_sha:
        errors.append("source identity manifest missing/mismatch")
    if not expected_refs or not observed_hashes:
        errors.append("static source byte identities not supplied")
    else:
        if len({ref.get("path") for ref in expected_refs}) != len(expected_refs):
            errors.append("duplicate source reference")
        for ref in expected_refs:
            if not safe_reference_path(ref.get("path")) or observed_hashes.get(ref["path"]) != ref.get("sha256"):
                errors.append("source reference missing, unsafe or mismatched")
    blockers = ("Independent scientific approval not present",
                "Researcher loss implementation and review not present",
                "Explicit integration and test permission not present",
                "Execution-stage authorization not present",
                "Effect/guardrail/multiplicity/resources unresolved",
                "This reviewer has no runner or authority-issuing capability")
    return ReviewResult(not errors, "VALID_PROPOSAL_EXECUTION_BLOCKED" if not errors else "REJECTED",
                        tuple(errors), blockers)


def reject_nonfinite(value: str) -> None:
    raise ValueError("Non-JSON numeric constant: " + value)


def unique_object(pairs: list[tuple[str,Any]]) -> dict:
    result = {}
    for key,value in pairs:
        if key in result:
            raise ValueError("Duplicate ambiguous JSON key: " + key)
        result[key] = value
    return result


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_nonfinite,
                      object_pairs_hook=unique_object)


def static_identity_inputs() -> tuple[dict, dict[str,str]]:
    """Hash the pinned repository metadata/source only; never parse sample CSVs."""
    refs = load_json(OUT / "source_identity.json")
    observed = {}
    for ref in refs["repository_files"]:
        if not safe_reference_path(ref["path"]):
            raise ValueError("Unsafe metadata/source reference")
        path = (REPO / ref["path"]).resolve(strict=True)
        if not path.is_relative_to(REPO.resolve()) or path.suffix in {".nc", ".pt", ".pth", ".h5"}:
            raise ValueError("Reference leaves source repository")
        observed[ref["path"]] = hashlib.sha256(path.read_bytes()).hexdigest()
    return refs, observed


def main() -> None:
    refs, observed = static_identity_inputs()
    result = review_protocol(load_json(OUT / "protocol_proposed.json"), load_json(OUT / "protocol_schema.json"),
                             identity_sha=hashlib.sha256((OUT / "source_identity.json").read_bytes()).hexdigest(),
                             expected_refs=refs["repository_files"], observed_hashes=observed)
    print(json.dumps(asdict(result),ensure_ascii=False,indent=2))
    if not result.candidate_valid:
        sys.exit(1)


if __name__ == "__main__":
    main()
