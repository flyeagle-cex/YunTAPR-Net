"""Read-only same-byte SHA decoding, real geography, and sealed paired batches."""
from __future__ import annotations
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import ntpath
from pathlib import Path
import time
from unittest.mock import patch
import netCDF4
import numpy as np
import torch
from yuntapr.data.himawari_b13 import read_b13_local
from yuntapr.data.imerg_v07 import read_imerg_local
from yuntapr.data import masks
from yuntapr.data.sample_schema import utc
from yuntapr.spatial.sp04_mapping import load_sp04
from yuntapr.experimental.phase_b_v2_real_data_preflight.audit import normalize_frozen
from yuntapr.experimental.phase_b_v2_full_payload_integrity.audit import canonical, reason
from yuntapr.experimental.phase_b_v2_full_payload_integrity.winio import ReadHandle
from yuntapr.training.phase_a_protocol import state_digest
from . import ROOT, SCOPE, LIMITS
from .plan import FrozenPlan, sha
from .resources import Budget, utcnow

class VerifiedReader:
    """Only the selected registry and exact pinned mask can reach CreateFileW."""
    def __init__(self, plan: FrozenPlan, budget: Budget):
        self.plan, self.budget = plan, budget
        self.handles = []
        self.reads = []; self.views = 0
        self.parents = set(plan.scope.parents)
        parent = ntpath.dirname(canonical(plan.mask_ref['path']))
        while True:
            self.parents.add(parent)
            next_parent = ntpath.dirname(parent)
            if parent == next_parent: break
            parent = next_parent

    def authenticate(self, path: str) -> tuple[str, str, int | None, str]:
        # canonical() is lexical; do not resolve/stat/open an unregistered path.
        if type(path) is not str:
            raise PermissionError('EXACT_STRING_SOURCE_REFERENCE')
        text = canonical(path)
        if text == canonical(self.plan.mask_ref['path']):
            raw = path.replace('/', '\\')
            if ('2025' in raw or not ntpath.isabs(raw) or raw.startswith('\\\\')
                or raw.count(':') != 1 or any(x in ('.', '..') for x in raw.split('\\'))):
                raise PermissionError('MASK_LEXICAL_REJECTION')
            return text, self.plan.mask_ref['sha256'], None, 'YUNNAN_MASK'
        text = self.plan.scope.authorized(path)
        kind, year, expected, size = self.plan.scope.entries[text]
        return text, expected, size, kind+'_'+str(year)

    def lock_parents(self) -> None:
        if len(self.parents) > 512: raise RuntimeError('SELECTED_DIRECTORY_HANDLE_LIMIT')
        for path in sorted(self.parents, key=lambda x: (x.count('\\'), x)):
            self.budget.check()
            if path not in self.parents: raise PermissionError('INDUCED_PARENT_ONLY')
            handle = ReadHandle(path, directory=True)
            try: self.plan.scope.authenticate_final(path, handle.final_path)
            except BaseException: handle.close(); raise
            self.handles.append(handle)
        self.budget.emit('PARENT_LOCKS', count=len(self.handles))

    def read(self, path: str) -> bytes:
        text, expected, frozen_size, group = self.authenticate(path)
        # Deidentified stable source key; no absolute or relative path published.
        key = sha((group+'\0'+text).encode())
        record = {'file_key': key, 'group': group, 'expected_sha256': expected,
                  'actual_sha256': None, 'bytes': 0, 'status': 'ATTEMPTED',
                  'opened_utc': utcnow(), 'open_success': False, 'error': None}
        self.reads.append(record); self.budget.emit('READ_RESERVED', **record)
        start = time.perf_counter()
        try:
            self.budget.check()
            with ReadHandle(text, payload=True) as handle:
                record['open_success'] = True
                self.plan.scope.authenticate_final(text, handle.final_path)
                size = handle.before['size']
                if frozen_size is not None and size != frozen_size:
                    raise ValueError('FROZEN_PAYLOAD_SIZE_MISMATCH')
                self.budget.admit_bytes(size)
                if self.budget.check()['working_set_bytes']+3*size+256*1024**2 > LIMITS['max_working_set_bytes']:
                    raise MemoryError('IMMUTABLE_DECODE_BUFFER_MEMORY_RESERVATION')
                buffer = bytearray(size); count = 0; digest = hashlib.sha256()
                while count < size:
                    self.budget.check()
                    request = min(8*1024**2, size-count)
                    self.budget.emit('READ_CHUNK_RESERVED', file_key=key,
                                     requested_bytes=request, file_bytes_before=count)
                    n = handle.readinto(memoryview(buffer)[count:count+request])
                    if not n: raise EOFError('FROZEN_SOURCE_SHORT_READ')
                    self.budget.account_bytes(n); digest.update(memoryview(buffer)[count:count+n])
                    count += n; record['bytes'] = count
                    self.budget.emit('READ_CHUNK', file_key=key, returned_bytes=n,
                                     file_bytes=count, accounted_content_bytes=self.budget.bytes)
                if handle.snapshot() != handle.before:
                    raise ValueError('SOURCE_CHANGED_WITHIN_READ_HANDLE')
                record['actual_sha256'] = digest.hexdigest()
                if record['actual_sha256'] != expected:
                    raise ValueError('SAME_BYTES_PAYLOAD_SHA_MISMATCH')
                payload = bytes(buffer)
            record['status'] = 'SHA_PASS'
            return payload
        except BaseException as error:
            record['status'] = 'FAILED'; record['error'] = reason(error)
            self.budget.stopped = True
            raise
        finally:
            record['closed_utc'] = utcnow(); record['read_sha_seconds'] = time.perf_counter()-start
            self.budget.emit('READ_FINISHED', **record)

    @contextmanager
    def view(self, payload: bytes, alias: str):
        """Frozen readers may access only this immutable memory object, once bound."""
        if type(payload) is not bytes or not alias.startswith('pilot_'):
            raise PermissionError('IMMUTABLE_MEMORY_VIEW_REQUIRED')
        original = netCDF4.Dataset
        def dataset(candidate, *args, **kwargs):
            if str(candidate) != alias or args or kwargs:
                raise PermissionError('NO_NETCDF_PATH_REOPEN_OR_FALLBACK')
            self.budget.check(); self.views += 1
            return original(alias, mode='r', memory=payload)
        with patch.object(netCDF4, 'Dataset', dataset):
            yield dataset

    def close(self) -> None:
        for handle in reversed(self.handles): handle.close()
        self.handles.clear()

@dataclass(frozen=True)
class RealBatch:
    x: torch.Tensor
    native_valid: torch.Tensor
    rate: torch.Tensor
    reference_valid: torch.Tensor
    region: torch.Tensor
    scene_keys: tuple[str, ...]
    tensor_sha256: str
    supervision_sha256: str
    owner: object
    scope: str = SCOPE

    def validate(self, kind: str, owner: object) -> None:
        frames = {'B0_MATCHED_V2': 1, 'B1_V2': 6}.get(kind)
        if self.owner is not owner or self.scope != SCOPE or frames is None:
            raise PermissionError('REAL_LOADER_PROVENANCE_REQUIRED')
        if len(self.scene_keys) != 2 or len(set(self.scene_keys)) != 2:
            raise ValueError('FIXED_REAL_BATCH_TWO_IDENTITIES')
        for value, shape, dtype in ((self.x, (2, frames, 501, 501), torch.float32),
            (self.native_valid, (2, frames, 501, 501), torch.bool),
            (self.rate, (2, 1, 100, 100), torch.float32),
            (self.reference_valid, (2, 1, 100, 100), torch.bool),
            (self.region, (2, 1, 100, 100), torch.bool)):
            if value.shape != shape or value.dtype != dtype or value.requires_grad or value.device != self.x.device:
                raise ValueError('REAL_BATCH_SHAPE_DTYPE_DEVICE_GRAPH')
        if not bool(torch.isfinite(self.x).all()) or not bool(self.native_valid.all()):
            raise ValueError('M1_REAL_NATIVE_FULL_VALID_REQUIRED')
        if not bool((self.region.flatten(1).sum(1) == 3430).all()):
            raise ValueError('FROZEN_REAL_YUNNAN_COUNT')
        if not bool(((self.reference_valid & self.region).flatten(1).sum(1) == 3430).all()):
            raise ValueError('FROZEN_Q1_VALIDITY_COUNT')
        if not bool(torch.isfinite(self.rate[self.reference_valid]).all()) or bool((self.rate[self.reference_valid] < 0).any()):
            raise ValueError('REFERENCE_VALID_PIXEL_VALUES')
        if bool(torch.isfinite(self.rate[~self.reference_valid]).any()):
            raise ValueError('INVALID_REFERENCE_MUST_REMAIN_NAN')
        if state_digest(self.x) != self.tensor_sha256:
            raise ValueError('DECODED_INPUT_IDENTITY_CHANGED')
        if state_digest({'rate': self.rate, 'valid': self.reference_valid, 'region': self.region}) != self.supervision_sha256:
            raise ValueError('ACTUAL_REFERENCE_OR_GEOGRAPHY_CHANGED')

    def cuda(self) -> RealBatch:
        return RealBatch(*(getattr(self, key).to('cuda:0') for key in
            ('x', 'native_valid', 'rate', 'reference_valid', 'region')),
            self.scene_keys, self.tensor_sha256, self.supervision_sha256, self.owner)

class RealAdapter:
    def __init__(self, plan: FrozenPlan, budget: Budget):
        self.plan, self.budget = plan, budget
        self.owner = object(); self.next_scene = 0
        self.reader = VerifiedReader(plan, budget)
        self.mapping = None

    def initialize_geometry(self) -> None:
        # Separate initialization preserves partial receipts on any first failure.
        self.mapping = load_sp04(ROOT)
        self.reader.lock_parents()
        payload = self.reader.read(self.plan.mask_ref['path'])
        alias = 'pilot_mask_readonly.nc'
        with self.reader.view(payload, alias) as view, patch.object(masks, 'sha256',
            lambda path: sha(payload) if str(path) == alias else (_ for _ in ()).throw(PermissionError('MASK_EXACT_ALIAS'))):
            with view(alias) as ds:
                if ds['yunnan_mask'].dimensions != ('lat', 'lon') or str(ds['yunnan_mask'].dtype) != 'uint8':
                    raise ValueError('ACTUAL_MASK_NATIVE_DTYPE_AXES')
            self.yunnan = masks.read_frozen_yunnan_mask(Path(alias), self.mapping)
        if self.yunnan.shape != (100, 100) or int(self.yunnan.sum()) != 3430:
            raise ValueError('ACTUAL_FROZEN_MASK_REQUIRED')
        self.budget.emit('GEOGRAPHY_READY', actual_mask_sha256=sha(payload),
                         mask_count=3430, target_shape=[100, 100],
                         mapping_sha256=self.plan.protocol['identity']['SP04_mapping']['sha256'])

    def scene(self, position: int) -> tuple[dict, dict]:
        if position != self.next_scene or not 0 <= position < 48:
            raise ValueError('ORIGINAL_SELECTION_ORDER_ONLY')
        start = time.perf_counter(); selected, row, _ = self.plan.rows[position]
        values, provenance = [], []
        for slot in range(6):
            frame = self.plan.frames[row[f'slot_{slot}_nominal']]
            payload = self.reader.read(ntpath.join(self.plan.h_root, frame['relative_path']))
            with self.reader.view(payload, 'pilot_b13_readonly.nc'):
                x, valid, actual = read_b13_local(Path('pilot_b13_readonly.nc'), self.mapping, frame['nominal'])
            if (x.dtype != np.float32 or x.shape != (501, 501) or valid.dtype != bool
                or not valid.all() or not np.isfinite(x).all()
                or actual.obs_start != utc(frame['obs_start']) or actual.obs_end != utc(frame['obs_end'])
                or actual.date_created != utc(frame['date_created'])
                or not actual.obs_start <= actual.obs_end <= utc(row['analysis_time'])):
                raise ValueError('ACTUAL_B13_CONTRACT_OR_CAUSALITY')
            norm = normalize_frozen(x, self.plan.scaler)
            if norm.dtype != np.float32 or not np.isfinite(norm).all():
                raise ValueError('ACTUAL_FROZEN_NORMALIZATION')
            values.append(norm)
            provenance.append({'slot': slot, 'offset_minutes': (60, 50, 40, 30, 20, 10)[slot],
                               'source_sha256': frame['source_sha256'], 'observation_causal': True,
                               'file_created_after_analysis': actual.date_created > utc(row['analysis_time'])})
        payload = self.reader.read(row['imerg_day_path'])
        alias = 'pilot_imerg_readonly.nc'
        with self.reader.view(payload, alias) as view:
            with view(alias) as ds:
                if ds.source != 'GPM_3IMERGHH_07' or 'IMERG Final Run V07' not in ds.title or ds['precipitation'].shape != (48, 130, 140):
                    raise ValueError('IMERG_FINAL_V07_DAILY_IDENTITY')
            y, valid, t = read_imerg_local(Path(alias), int(row['imerg_index']), self.mapping)
        if (t != utc(row['window_start']) or y.dtype != np.float32 or y.shape != (100, 100)
            or valid.dtype != bool or int((valid & self.yunnan).sum()) != 3430
            or not np.isfinite(y[valid]).all() or np.any(y[valid] < 0)
            or np.isfinite(y[~valid]).any() or np.shares_memory(valid, self.yunnan)):
            raise ValueError('REAL_REFERENCE_GRID_VALIDITY_IDENTITY')
        self.budget.check(); self.next_scene += 1
        key = sha(selected['sample_id'].encode())
        receipt = {'position': position, 'scene_key': key, 'year': selected['year'],
                   'role': 'Train' if selected['year'] == 2023 else 'DevelopmentValidation',
                   'manifest_index': selected['index'], 'frames': provenance,
                   'target_sha256': row['imerg_sha256'], 'seconds': time.perf_counter()-start,
                   'input_dtype': 'float32', 'target_dtype': 'float32',
                   'target_units': 'mm hr-1', 'yunnan_valid_cells': 3430,
                   'FP32_threshold_semantics': 'reference_float32 > float32(0.1)'}
        self.budget.emit('SCENE_DECODED', **receipt)
        return {'x': np.stack(values), 'y': y[None], 'valid': valid[None], 'key': key}, receipt

    def pair(self, pair: int) -> tuple[dict[str, RealBatch], list[dict]]:
        items, receipts = [], []
        for position in (pair*2, pair*2+1):
            item, receipt = self.scene(position); items.append(item); receipts.append(receipt)
        x = torch.from_numpy(np.stack([item['x'] for item in items]))
        rate = torch.from_numpy(np.stack([item['y'] for item in items]))
        valid = torch.from_numpy(np.stack([item['valid'] for item in items]))
        region = torch.from_numpy(np.stack([self.yunnan[None]]*2))
        if not np.array_equal((rate.numpy() > np.float32(.1)), (rate > torch.tensor(.1, dtype=torch.float32)).numpy()):
            raise ValueError('FP32_THRESHOLD_OPERATION_DRIFT')
        keys = tuple(item['key'] for item in items)
        supervision = state_digest({'rate': rate, 'valid': valid, 'region': region})
        result = {}
        for kind, source in (('B0_MATCHED_V2', x[:, 5:6].clone()), ('B1_V2', x)):
            batch = RealBatch(source, torch.ones_like(source, dtype=torch.bool), rate, valid,
                              region, keys, state_digest(source), supervision, self.owner)
            batch.validate(kind, self.owner); result[kind] = batch
        if not torch.equal(result['B0_MATCHED_V2'].x, result['B1_V2'].x[:, 5:6]):
            raise ValueError('REAL_PAIRED_LATEST_TENSOR')
        return result, receipts
