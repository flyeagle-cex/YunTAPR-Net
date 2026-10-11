"""First two frozen Train rows; reuse all same-byte decode/geographic logic."""
from __future__ import annotations
import ast
import csv
from datetime import timedelta
import io
import json
import ntpath
import subprocess
from yuntapr.data.sample_schema import utc
from yuntapr.experimental.phase_b_v2_real_forward_pilot.plan import (
    PublicPins,SOURCE,SOURCE_SHA,STATUS,STATUS_SHA,PROTOCOL,PROTOCOL_SHA)
from yuntapr.experimental.phase_b_v2_real_forward_pilot.adapter import RealAdapter
from yuntapr.experimental.phase_b_v2_full_payload_integrity.audit import Scope,valid_sha,canonical
from yuntapr.experimental.phase_b_v2_real_data_preflight.audit import paired_ids
from . import ROOT,BASELINE

class SmokePlan:
    def __init__(self,budget):
        if subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()!=BASELINE:
            raise PermissionError('SMOKE_REPOSITORY_BASELINE_MISMATCH')
        self.public=PublicPins(budget)
        prior=json.loads(self.public.read(STATUS,STATUS_SHA))
        if prior['overall_status']!='FULL_PAYLOAD_SHA_PASS' or prior['sha_matched_files']!=67006:
            raise ValueError('FROZEN_PAYLOAD_BASELINE_MISSING')
        pins={p['path']:p['sha256'] for p in json.loads(self.public.read(SOURCE,SOURCE_SHA))['public_source_pins']}
        source=self.public.read('src/yuntapr/data/dataset_b1.py',pins['src/yuntapr/data/dataset_b1.py'])
        constants={}
        for node in ast.parse(source).body:
            if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in ('H_ROOT','IMERG_ROOT','AUDIT'):
                constants[node.targets[0].id]=ast.literal_eval(node.value.args[0])
        self.protocol=json.loads(self.public.read(PROTOCOL,PROTOCOL_SHA))
        rows={}
        for kind in ('B1','B0_MATCHED'):
            ref=self.protocol['identity'][kind+'_2023']
            rows[kind]=list(csv.DictReader(io.StringIO(self.public.read(ref['path'],ref['sha256']).decode('utf-8-sig'))))
        a,b=rows['B1'],rows['B0_MATCHED']
        if len(a)!=10455 or len(b)!=10455 or len({r['sample_id'] for r in a})!=10455:
            raise ValueError('FROZEN_2023_M1_IDENTITY')
        paired_ids(b,a); self.rows=[]; desired=set()
        for index in (0,1):
            row,anchor=a[index],b[index]; start=utc(row['window_start']); analysis=utc(row['analysis_time'])
            if (int(row['index'])!=index or int(row['year'])!=2023 or start.year!=2023
                or row['role']!='Train' or row['eligibility']!='FORMAL_M1_COMMON_INTERSECTION'
                or int(row['target_valid_yunnan_cells'])!=3430 or analysis!=start+timedelta(minutes=30)
                or ntpath.basename(row['imerg_day_path'])!='imerg_'+start.strftime('%Y%m%d')+'.nc'
                or start.minute not in (0,30) or int(row['imerg_index'])!=start.hour*2+start.minute//30):
                raise ValueError('FIRST_TWO_TRAIN_FROZEN_IDENTITY')
            selected=dict(index=index,year=2023,sample_id=row['sample_id'],analysis_time=row['analysis_time'])
            for slot,offset in enumerate((60,50,40,30,20,10)):
                nominal=row[f'slot_{slot}_nominal']
                if utc(nominal)!=analysis-timedelta(minutes=offset): raise ValueError('FROZEN_CAUSALITY')
                desired.add(nominal)
            self.rows.append((selected,row,anchor))
        ref=constants['AUDIT']+'/frame_identity_index.json'
        frameindex=json.loads(self.public.read(ref,pins[ref]))
        months={utc(n).strftime('%Y%m') for n in desired}; self.frames={}
        for month in sorted(months):
            ref='native_frames/'+month+'.csv'
            raw=self.public.read(constants['AUDIT']+'/'+ref,frameindex['files'][ref])
            for frame in csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))):
                if frame['nominal'] in desired:
                    if frame['nominal'] in self.frames: raise ValueError('DUPLICATE_FROZEN_FRAME')
                    self.frames[frame['nominal']]=frame
        if set(self.frames)!=desired: raise ValueError('MISSING_FROZEN_FRAME')
        self.h_root=constants['H_ROOT']; self.scope=Scope({'B13':self.h_root,'IMERG':constants['IMERG_ROOT']})
        for selected,row,anchor in self.rows:
            self.scope.register(row['imerg_day_path'],'IMERG',2023,row['imerg_sha256'],None)
            for slot in range(6):
                frame=self.frames[row[f'slot_{slot}_nominal']]
                if (any(frame[k]!='True' for k in ('present','readable','decoded','full_valid','metadata_valid'))
                    or int(frame['valid_count'])!=251001 or not utc(frame['obs_start'])<=utc(frame['obs_end'])<=utc(row['analysis_time'])):
                    raise ValueError('M1_ACTUAL_CAUSAL_SOURCE')
                if slot==5 and (anchor['b13_sha256']!=frame['source_sha256'] or anchor['b13_relative_path']!=frame['relative_path']):
                    raise ValueError('PAIRED_LATEST_FRAME_IDENTITY')
                self.scope.register(ntpath.join(self.h_root,frame['relative_path']),'B13',2023,frame['source_sha256'],int(frame['source_bytes']))
        self.mask_ref=self.protocol['identity']['yunnan_mask']; valid_sha(self.mask_ref['sha256'])
        if '2025' in canonical(self.mask_ref['path']): raise PermissionError('MASK_YEAR_LEXICAL_REJECTION')
        norm=self.protocol['identity']['normalization']
        self.scaler=json.loads(self.public.read(norm['path'],norm['sha256']))
        if (self.scaler['fit_role']!='Train' or self.scaler['fit_years']!=[2023] or self.scaler['fit_scene_count']!=10455
            or not self.scaler['all_six_slots_share_identical_scaler']
            or self.protocol['B0_MATCHED_CONTROL_NORMALIZATION']!='USE_FROZEN_B1_SHARED_SCALER'):
            raise ValueError('SHARED_SCALER_IDENTITY')
        budget.emit('SMOKE_PLAN_READY',selected_scene_ids=[r[0]['sample_id'] for r in self.rows],
                    manifest_indices=[0,1],raw_unique_files=len(self.scope.entries))

class SmokeAdapter(RealAdapter):
    def scene(self,position):
        if position not in (0,1): raise PermissionError('ONLY_TWO_AUTHORIZED_REAL_SCENES')
        return super().scene(position)
    def pair(self,pair):
        if pair!=0 or self.next_scene!=0: raise PermissionError('NO_REAL_BATCH_REREAD')
        return super().pair(pair)
