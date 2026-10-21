"""Restore three inherited path constants without altering ledger/authorization.

The failed v5 ancestor retained its v4 provider but omitted these exports. They
refer to the original SHA-bound result/checkpoint namespace, not a new source.
Only an in-memory test module or a separate future release may apply this delta.
"""
from __future__ import annotations
import ast
from types import ModuleType

NAMES=('COMPLETE_PREFIX','RECOVERY_PREFIX','SOURCE_CP')


def inherited_exports(previous: ModuleType) -> dict[str,str]:
    values={name:getattr(previous,name) for name in NAMES}
    for name,value in values.items():
        if (type(value) is not str or not value.startswith('docs/phase_b_v2_formal_execution/')
            or not value.endswith('/') or '2025' in value or ':' in value or '\\' in value
            or any(x in ('','.','..') for x in value.rstrip('/').split('/'))):
            raise ValueError('EXACT_INHERITED_ANCESTOR_PATH_CONSTANT_'+name)
    return values


def missing_imports(sources: dict[str,str],namespace: dict) -> dict[str,list[str]]:
    """Inspect function-local imports as well as imports at module scope."""
    failures={}
    for filename,source in sources.items():
        required={item.name for node in ast.walk(ast.parse(source,filename=filename))
                  if isinstance(node,ast.ImportFrom) and node.level==1 and node.module=='ancestor'
                  for item in node.names}
        missing=sorted(required-set(namespace))
        if missing:failures[filename]=missing
    return failures


def proposed_source(source: str) -> str:
    """Return a nonexecuting three-line delta. Never writes a formal module."""
    tree=ast.parse(source)
    if not any(isinstance(node,ast.ImportFrom) and node.module=='yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v4'
               and any(x.name=='ancestor' and x.asname=='prior' for x in node.names) for node in tree.body):
        raise ValueError('EXPECTED_V4_ANCESTOR_PROVIDER_REQUIRED')
    insertion=''.join(f'{name}=prior.{name}\n' for name in NAMES)
    return source.rstrip()+'\n\n# Explicitly preserve consumer-facing bindings from the original provider.\n'+insertion
