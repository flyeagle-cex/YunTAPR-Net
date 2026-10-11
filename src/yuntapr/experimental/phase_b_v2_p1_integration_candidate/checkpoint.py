"""Registered same-byte checkpoint reader; old path-reopening readers are unused.

This version can restore only artificial dict state. It provides no live model
or optimizer mutation and no formal/private checkpoint adoption capability.
"""
from __future__ import annotations
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import torch
from yuntapr.experimental.phase_b_v2_runner_candidate.checkpoint import SyntheticStore
from yuntapr.experimental.phase_b_v2_full_payload_integrity.winio import ReadHandle
from .contract import Contract
from .scope import Workspace, lexical

SCHEMA = 'P1_REGISTERED_SAME_BYTES_ARTIFICIAL_v1'
MAX_PAYLOAD = 1024*1024
MAX_RECEIPT = 16*1024


def sha(value: bytes) -> str: return hashlib.sha256(value).hexdigest()


def pairs(rows):
    result = {}
    for key, value in rows:
        if key in result: raise ValueError('Duplicate receipt field')
        result[key] = value
    return result


def parse_receipt(value: bytes) -> dict:
    if not 0 < len(value) <= MAX_RECEIPT: raise ValueError('Receipt size bound')
    row = json.loads(value.decode('utf-8'), object_pairs_hook=pairs,
                     parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    fields = {'schema','scope','filename','bytes','sha256','contract_sha','workspace_key'}
    if type(row) is not dict or set(row) != fields or row['schema'] != SCHEMA or row['scope'] != 'SYNTHETIC_ENGINEERING_ONLY':
        raise ValueError('Receipt schema/source')
    if (type(row['filename']) is not str or re.fullmatch(r'[A-Za-z0-9_-]+\.pt', row['filename']) is None
            or '2025' in row['filename'] or type(row['bytes']) is not int or not 0 < row['bytes'] <= MAX_PAYLOAD
            or any(type(row[k]) is not str or re.fullmatch('[0-9a-f]{64}',row[k]) is None
                   for k in ('sha256','contract_sha'))
            or type(row['workspace_key']) is not str or re.fullmatch('[0-9a-f]{32}', row['workspace_key']) is None):
        raise ValueError('Receipt values')
    return row


@dataclass(frozen=True)
class Commit:
    reference: Path
    payload: Path
    receipt_sha: str
    payload_sha: str
    receipt_object: dict
    payload_object: dict


class Store(SyntheticStore):
    """Reuse old atomic save transport, never its unsafe read/constructor."""
    def __init__(self, workspace: Workspace, contract: Contract):
        if type(workspace) is not Workspace or type(contract) is not Contract:
            raise TypeError('Owned workspace and pinned contract required')
        self.workspace, self.contract, self.root = workspace, contract, workspace.root
        self._registered: dict[str, Commit] = {}
        self.failed = False

    @contextmanager
    def io(self): yield

    def _path(self, name):
        path = super()._path(name)
        lexical(path, self.root)
        return path

    def _bytes(self, path: Path, maximum: int, expected: dict | None = None) -> tuple[bytes, dict]:
        lexical(path, self.root)
        if path.parent != self.root: raise PermissionError('Immediate owned child only')
        with ReadHandle(str(path), payload=True) as handle:
            before = handle.before
            if os.path.normcase(handle.final_path) != os.path.normcase(str(path)):
                raise PermissionError('Opened object path mismatch')
            if expected is not None and before != expected: raise ValueError('Registered object changed')
            if not 0 < before['size'] <= maximum: raise ValueError('File size bound')
            data = bytearray(before['size'])
            view = memoryview(data); position = 0
            while position < len(data):
                count = handle.readinto(view[position:])
                if not count: raise ValueError('Truncated read')
                position += count
            if handle.readinto(bytearray(1)) or handle.snapshot() != before:
                raise ValueError('Concurrent content/metadata change')
            return bytes(data), dict(before)

    def save(self, name, payload, *, fault=None) -> Commit:
        if self.failed: raise PermissionError('Store failed; no retry/adoption')
        try:
            self._path(name) # reject lexical year before serialization/path operations
            payload = deepcopy(payload) # freeze caller-owned CPU containers/tensors
            self.contract.validate(payload)
            if shutil.disk_usage(self.root).free < 4*MAX_PAYLOAD:
                raise RuntimeError('Storage admission')
            # Bound serialized bytes before reusing transport. No optimizer update.
            buffer = io.BytesIO(); torch.save(payload, buffer)
            if buffer.tell() > MAX_PAYLOAD: raise ValueError('Serialized size bound')
            expected_bytes = buffer.getvalue()
            reference = super().save(name, payload, fault=fault)
            blob = self._path(name)
            raw, metadata = self._bytes(blob, MAX_PAYLOAD)
            old_ref, _ = self._bytes(reference, MAX_RECEIPT)
            old_row = json.loads(old_ref.decode('utf-8'), object_pairs_hook=pairs)
            if (set(old_row) != {'schema','filename','bytes','sha256'}
                    or old_row['schema'] != 'SYNTHETIC_B9_V0_CANDIDATE_v1'
                    or old_row['filename'] != blob.name or old_row['bytes'] != len(raw)
                    or old_row['sha256'] != sha(raw) or sha(raw) != sha(expected_bytes)):
                raise ValueError('Save-to-registration byte identity changed')
            row = dict(schema=SCHEMA, scope='SYNTHETIC_ENGINEERING_ONLY', filename=blob.name,
                       bytes=len(raw), sha256=sha(raw), contract_sha=self.contract.key,
                       workspace_key=self.workspace.key)
            # Upgrade our own new receipt only; never touch a published checkpoint.
            temp = self.workspace.file(name+'.p1.tmp')
            with temp.open('xb') as stream:
                stream.write((json.dumps(row, sort_keys=True)+'\n').encode())
                stream.flush(); os.fsync(stream.fileno())
            temp.replace(reference)
            ref_bytes, ref_meta = self._bytes(reference, MAX_RECEIPT)
            if parse_receipt(ref_bytes) != row: raise ValueError('Commit receipt changed')
            commit = Commit(reference, blob, sha(ref_bytes), sha(raw), ref_meta, metadata)
            self._registered[str(reference)] = commit
            return commit
        except BaseException:
            self.failed = True
            raise

    def read(self, reference: Path) -> dict:
        if self.failed: raise PermissionError('Store failed; no retry/adoption')
        try:
            lexical(reference, self.root)
            if reference.parent != self.root or str(reference) not in self._registered:
                raise PermissionError('No orphan/external receipt adoption')
            registered = self._registered[str(reference)]
            ref, _ = self._bytes(reference, MAX_RECEIPT, registered.receipt_object)
            if sha(ref) != registered.receipt_sha: raise ValueError('Receipt SHA mismatch')
            row = parse_receipt(ref)
            if (row['filename'] != registered.payload.name or row['workspace_key'] != self.workspace.key
                    or row['contract_sha'] != self.contract.key or row['sha256'] != registered.payload_sha):
                raise ValueError('Receipt registry/source mismatch')
            immutable, _ = self._bytes(registered.payload, MAX_PAYLOAD, registered.payload_object)
            if len(immutable) != row['bytes'] or sha(immutable) != row['sha256']:
                raise ValueError('Payload SHA mismatch; no deserialization')
            # Crucial: no path reopening after SHA. Deserializer sees ONLY these bytes.
            payload = torch.load(io.BytesIO(immutable), weights_only=True, map_location='cpu')
            self.contract.validate(payload)
            return payload
        except BaseException:
            self.failed = True
            raise

    def restore_fixture(self, reference: Path, target: 'FixtureState', *, epoch: int, update: int, last_sha: str):
        if type(target) is not FixtureState: raise PermissionError('No live model/optimizer restoration')
        payload = self.read(reference)
        registered = self._registered[str(reference)]
        if payload['epoch'] != epoch or payload['update'] != update or registered.payload_sha != last_sha:
            self.failed = True
            raise ValueError('No rollback or alternate LAST adoption')
        prepared = deepcopy(payload) # all validation before one artificial dict swap
        target._value = prepared


class FixtureState:
    """Artificial containers only; cannot accept nn.Module or Optimizer."""
    def __init__(self): self._value = None
    @property
    def value(self): return deepcopy(self._value)
