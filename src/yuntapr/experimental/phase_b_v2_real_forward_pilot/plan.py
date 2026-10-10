"""Pinned public metadata -> the original 48 positions, without raw path probes."""
from __future__ import annotations
import ast
import csv
from datetime import timedelta
import hashlib
import io
import json
import ntpath
import os
from pathlib import Path
import subprocess
from . import BASELINE, ROOT, LIMITS
from .resources import Budget
from yuntapr.experimental.phase_b_v2_full_payload_integrity.audit import Scope, canonical, valid_sha
from yuntapr.experimental.phase_b_v2_real_data_preflight.audit import paired_ids
from yuntapr.data.sample_schema import utc

SELECTION = 'docs/phase_b_v2_real_data_preflight/v1/DECODE_SELECTION.json'
SELECTION_SHA = '3d63d418fda3e388891379489014d29c2cbe99e8b82adee35f0b168087d90634'
SOURCE = 'docs/phase_b_v2_full_payload_integrity/v1/source_identity.json'
SOURCE_SHA = '67687abaec6cb12489ec2f2cb80abe173095bb7a3092f7c583c91b36e7c24143'
STATUS = 'docs/phase_b_v2_full_payload_integrity/v1/final_status.json'
STATUS_SHA = '8aac905afe7f0a4d49fa03acbf6f6634c34f8ac07a30d670b2f6270694d81b3a'
PROTOCOL = 'config/science_v2/phase_a_protocol_frozen_v1.json'
PROTOCOL_SHA = 'a0141f21cfa997d5adb72dff5afb32b17dc7edcf5f3397fc9c4bfe2ea42048be'

def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()

class PublicPins:
    def __init__(self, budget: Budget):
        self.budget, self.pins = budget, {}

    def read(self, relative: str, expected: str) -> bytes:
        valid_sha(expected)
        text = relative.replace('\\', '/')
        if ':' in text or text.startswith('/') or any(x in ('', '.', '..') for x in text.split('/')):
            raise PermissionError('REPOSITORY_METADATA_LEXICAL_SCOPE')
        if not text.endswith(('.json', '.csv', '.yaml', '.py')):
            raise PermissionError('PUBLIC_METADATA_EXTENSION')
        # These are repository metadata, not raw observations. Content is checked
        # before parsing; no external path contained in the bytes is opened here.
        with (ROOT/text).open('rb') as stream:
            size = os.fstat(stream.fileno()).st_size
            self.budget.admit_bytes(size)
            if self.budget.check()['working_set_bytes']+3*size+256*1024**2 > LIMITS['max_working_set_bytes']:
                raise MemoryError('PUBLIC_METADATA_BUFFER_MEMORY_RESERVATION')
            raw = stream.read(size)
            self.budget.account_bytes(len(raw))
            if len(raw) != size: raise EOFError('PUBLIC_METADATA_SHORT_READ')
        if sha(raw) != expected: raise ValueError('PINNED_PUBLIC_METADATA_SHA')
        self.pins[text] = {'path': text, 'sha256': expected, 'bytes': len(raw)}
        self.budget.emit('PUBLIC_METADATA_READ', **self.pins[text])
        return raw

class FrozenPlan:
    """Selected raw refs only. No alternate dataset, sorting or label selection."""
    def __init__(self, budget: Budget):
        if subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() != BASELINE:
            raise ValueError('PILOT_BASELINE_MISMATCH')
        self.public = PublicPins(budget)
        status = json.loads(self.public.read(STATUS, STATUS_SHA))
        if status['overall_status'] != 'FULL_PAYLOAD_SHA_PASS' or status['sha_matched_files'] != 67006:
            raise ValueError('KNOWN_FULL_INTEGRITY_BASELINE_MISSING')
        prior = json.loads(self.public.read(SOURCE, SOURCE_SHA))
        pins = {item['path']: item['sha256'] for item in prior['public_source_pins']}
        for ref in ('src/yuntapr/experimental/phase_b_v2_real_data_preflight/audit.py',
                    'src/yuntapr/data/dataset_b1.py'):
            source = self.public.read(ref, pins[ref])
            if ref.endswith('/dataset_b1.py'):
                constants = {}
                for node in ast.parse(source).body:
                    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                        name = node.targets[0].id
                        if name in ('H_ROOT', 'IMERG_ROOT', 'AUDIT'):
                            constants[name] = ast.literal_eval(node.value.args[0])
        self.scope = Scope({'B13': constants['H_ROOT'], 'IMERG': constants['IMERG_ROOT']})
        self.protocol = json.loads(self.public.read(PROTOCOL, PROTOCOL_SHA))
        self.selection = json.loads(self.public.read(SELECTION, SELECTION_SHA))['selected']
        if len(self.selection) != 48 or [r['year'] for r in self.selection] != [2023]*24+[2024]*24:
            raise ValueError('ORIGINAL_48_SELECTION_IDENTITY')
        if len({s['sample_id'] for s in self.selection}) != 48:
            raise ValueError('DUPLICATE_PILOT_SELECTION')
        self.rows, desired = [], set()
        for year in (2023, 2024):
            records = {}
            for model in ('B1', 'B0_MATCHED'):
                ref = self.protocol['identity'][f'{model}_{year}']
                records[model] = list(csv.DictReader(io.StringIO(self.public.read(ref['path'], ref['sha256']).decode('utf-8-sig'))))
            a, b = records['B1'], records['B0_MATCHED']
            n = 10455 if year == 2023 else 10501
            if len(a) != n or len(b) != n or len({r['sample_id'] for r in a}) != n:
                raise ValueError('FROZEN_M1_COUNTS')
            # Existing verifier's contract is B0 first, six-slot B1 second.
            paired_ids(b, a)
            for selected in self.selection:
                if selected['year'] != year: continue
                row = a[selected['index']]; anchor = b[selected['index']]
                start, analysis = utc(row['window_start']), utc(row['analysis_time'])
                if (row['sample_id'] != selected['sample_id'] or row['analysis_time'] != selected['analysis_time']
                    or int(row['index']) != selected['index'] or int(row['year']) != year
                    or start.year != year or analysis != start+timedelta(minutes=30)
                    or row['role'] != ('Train' if year == 2023 else 'Validation')
                    or row['eligibility'] != 'FORMAL_M1_COMMON_INTERSECTION'
                    or int(row['target_valid_yunnan_cells']) != 3430):
                    raise ValueError('SELECTED_ROLE_POSITION_QUALIFICATION')
                if ntpath.basename(row['imerg_day_path']) != 'imerg_'+start.strftime('%Y%m%d')+'.nc':
                    raise ValueError('IMERG_FROZEN_DAY_BINDING')
                if int(row['imerg_index']) != start.hour*2+start.minute//30 or start.minute not in (0, 30):
                    raise ValueError('IMERG_TARGET_INDEX')
                for slot, offset in enumerate((60, 50, 40, 30, 20, 10)):
                    nominal = row[f'slot_{slot}_nominal']
                    if utc(nominal) != analysis-timedelta(minutes=offset):
                        raise ValueError('FROZEN_CAUSAL_SLOT_ORDER')
                    desired.add(nominal)
                self.rows.append((selected, row, anchor))
        self.frames = {}
        index_path = constants['AUDIT']+'/frame_identity_index.json'
        index = json.loads(self.public.read(index_path, pins[index_path]))
        for relative, expected in index['files'].items():
            raw = self.public.read(constants['AUDIT']+'/'+relative, expected)
            for frame in csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))):
                if frame['nominal'] in desired:
                    if frame['nominal'] in self.frames: raise ValueError('DUPLICATE_SELECTED_FRAME')
                    self.frames[frame['nominal']] = frame
        if set(self.frames) != desired: raise ValueError('MISSING_SELECTED_FRAME')
        for selected, row, anchor in self.rows:
            self.scope.register(row['imerg_day_path'], 'IMERG', selected['year'], row['imerg_sha256'], None)
            for slot in range(6):
                frame = self.frames[row[f'slot_{slot}_nominal']]
                if (any(frame[k] != 'True' for k in ('present', 'readable', 'decoded', 'full_valid', 'metadata_valid'))
                    or int(frame['valid_count']) != 251001
                    or not utc(frame['obs_start']) <= utc(frame['obs_end']) <= utc(row['analysis_time'])):
                    raise ValueError('SELECTED_M1_FRAME_CAUSALITY')
                if slot == 5 and (anchor['b13_sha256'] != frame['source_sha256']
                                 or anchor['b13_relative_path'] != frame['relative_path']):
                    raise ValueError('B0_LATEST_SOURCE_IDENTITY')
                path = ntpath.join(constants['H_ROOT'], frame['relative_path'])
                self.scope.register(path, 'B13', selected['year'], frame['source_sha256'], int(frame['source_bytes']))
        self.h_root = constants['H_ROOT']
        self.mask_ref = self.protocol['identity']['yunnan_mask']
        if '2025' in canonical(self.mask_ref['path']) or not canonical(self.mask_ref['path']).endswith('.nc'):
            raise PermissionError('MASK_LEXICAL_IDENTITY')
        valid_sha(self.mask_ref['sha256'])
        norm = self.protocol['identity']['normalization']
        self.scaler = json.loads(self.public.read(norm['path'], norm['sha256']))
        if (self.scaler['fit_years'] != [2023] or self.scaler['fit_role'] != 'Train'
            or self.scaler['fit_scene_count'] != 10455 or not self.scaler['all_six_slots_share_identical_scaler']
            or self.protocol['B0_MATCHED_CONTROL_NORMALIZATION'] != 'USE_FROZEN_B1_SHARED_SCALER'):
            raise ValueError('FROZEN_SHARED_SCALER_ROLE')
        budget.emit('PLAN_READY', selection_sha256=SELECTION_SHA, scenes=48,
                    raw_unique_files=len(self.scope.entries), role_counts={'Train2023': 24, 'Development2024': 24},
                    mask_sha256=self.mask_ref['sha256'], scaler_sha256=norm['sha256'])
