"""Reuse complete B9 envelope validation with a strictly CPU-artificial RNG adapter.

No model/optimizer construction, global RNG restoration, backward or GPU call.
The function clone substitutes only RNG topology validation in isolated globals;
it does not monkeypatch the published validator or relax its scientific fields.
"""
from __future__ import annotations
from copy import deepcopy
import math
import random
from types import FunctionType, SimpleNamespace
import numpy as np
import torch
from yuntapr.experimental.phase_b_v2_formal_integration_candidate import checkpoint as old
from yuntapr.experimental.phase_b_v2_formal_integration_candidate.protocol import digest, sha_string, FLAGS

MAX_TENSOR_BYTES = 256 * 1024


def cpu_rng(value: dict) -> None:
    if type(value) is not dict or set(value) != {'python', 'numpy', 'cpu', 'cuda'}:
        raise ValueError('Complete RNG fields required')
    random.Random().setstate(value['python'])
    v = value['numpy']
    if (type(v) is not dict or set(v) != {'name', 'keys', 'pos', 'gauss', 'cache'}
            or v['name'] != 'MT19937' or type(v['pos']) is not int or not 0 <= v['pos'] <= 624
            or type(v['gauss']) is not int or v['gauss'] not in (0, 1)
            or type(v['cache']) is not float or not math.isfinite(v['cache'])
            or type(v['keys']) is not torch.Tensor or v['keys'].dtype != torch.int64
            or v['keys'].shape != (624,) or bool(((v['keys'] < 0) | (v['keys'] > 2**32-1)).any())):
        raise ValueError('NumPy RNG signature/range')
    np.random.RandomState().set_state((v['name'], v['keys'].numpy().astype(np.uint32),
                                      v['pos'], v['gauss'], v['cache']))
    if (type(value['cpu']) is not torch.Tensor or value['cpu'].dtype != torch.uint8
            or value['cpu'].ndim != 1 or type(value['cuda']) is not list or value['cuda'] != []):
        raise ValueError('CPU-only artificial RNG topology')
    torch.Generator(device='cpu').set_state(value['cpu'])


_complete_validate = FunctionType(old.validate.__code__,
    {**old.validate.__globals__, 'rng': SimpleNamespace(validate=cpu_rng)},
    'complete_cpu_artificial_validate')


def bounded(value) -> int:
    """Whitelist plain containers/CPU tensors before serialization and after load."""
    nodes = 0
    def walk(x, depth=0):
        nonlocal nodes
        nodes += 1
        if nodes > 10000 or depth > 24: raise ValueError('Container bound exceeded')
        if type(x) is torch.Tensor:
            if x.device.type != 'cpu' or x.layout != torch.strided or x.requires_grad:
                raise ValueError('Detached dense CPU fixture tensors only')
            if not bool(torch.isfinite(x).all()): raise ValueError('Nonfinite fixture tensor')
            return x.numel()*x.element_size()
        if type(x) in (dict, list, tuple):
            if type(x) is dict:
                if any(type(k) not in (str, int) for k in x): raise ValueError('Plain keys only')
                return sum(walk(v, depth+1) for v in x.values())
            return sum(walk(v, depth+1) for v in x)
        if x is None or type(x) in (str, int, float, bool):
            if type(x) is str and len(x) > 4096: raise ValueError('String bound')
            if type(x) is float and not math.isfinite(x): raise ValueError('Nonfinite scalar')
            return 0
        raise TypeError('No custom objects in artificial checkpoint')
    size = walk(value)
    if size > MAX_TENSOR_BYTES: raise ValueError('Tensor byte bound')
    return size


class Contract:
    def __init__(self, identity, model_template, optimizer_template, initial_sha):
        sha_string(initial_sha)
        bounded(identity); bounded(model_template); bounded(optimizer_template)
        if (identity.get('scope') != 'SYNTHETIC_ENGINEERING_ONLY' or identity.get('flags') != FLAGS
                or identity.get('execution_authorization_ancestor') != 'SYNTHETIC_EVENT_NO_AUTHORITY'
                or identity.get('profile',{}).get('name') != 'SYNTHETIC_SMALL'):
            raise PermissionError('No real model checkpoint contract')
        self._identity = deepcopy(identity)
        self._model = deepcopy(model_template)
        self._optimizer = deepcopy(optimizer_template)
        self._initial = initial_sha
        self.key = digest({'identity': identity, 'initial': initial_sha,
                           'model': {k: [list(v.shape), str(v.dtype)] for k,v in model_template.items()},
                           'optimizer': optimizer_template})

    def validate(self, payload) -> None:
        bounded(payload)
        _complete_validate(payload, self._identity, self._model, self._optimizer, self._initial)
