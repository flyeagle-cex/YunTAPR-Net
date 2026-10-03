"""TEST_FIXTURE_ONLY: approved metadata-path adapter, with no raw access.

All files created here live in isolated C: fixtures and are removed afterwards.
2025 paths are strings. No model, checkpoint, optimizer, or metric is used.
"""
import json
import os
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from yuntapr.contracts.loader import sha256
from yuntapr.evaluation import catalogue_execution_v1_1 as execution
from yuntapr.evaluation import catalogue_gate_b0 as gate
from tests.final_test_catalogue.test_catalogue_gate import (
    NoRawAccessTests, workspace_fixture, eligible_row, candidate_rows, population_rows)


def authorization():
    value=execution.authorization_bindings(gate.load_protocol(),'a'*64)
    return dict(value,created_utc='2026-10-03T00:00:00+00:00',researcher_request_sha256='b'*64)


def cap(value=None):
    # Inert fixture capability, never passed to real source discovery or execute.
    return execution.ExecutionAuthority(value or authorization(),'c'*64,execution._EXECUTION_SEAL)


def load_fixture(path,value):
    path.write_text(json.dumps(value,allow_nan=False),encoding='utf-8')
    with patch.object(execution.subprocess,'check_output',return_value=(execution.BASE+'\n').encode()):
        return execution.ExecutionAuthority.load(path,sha256(path))


class AuthorityTests(NoRawAccessTests):
    def test_complete_exact_authority_and_immutable_snapshot(self):
        with workspace_fixture() as root:
            value=authorization();a=load_fixture(root/'auth.json',value)
            a.require_catalogue();value['source_roots']['IMERG']='other'
            self.assertEqual(a.value['source_roots']['IMERG'],str(gate.legacy.IROOT))
            with self.assertRaises(TypeError):a.value['scope']='changed'
            with self.assertRaises(PermissionError):a.require_final()

    def test_missing_authority_precedes_protocol_and_source_access(self):
        with patch.object(gate,'load_protocol') as protocol:
            with self.assertRaises(PermissionError):execution.ExecutionAuthority.load(None,None)
            protocol.assert_not_called()

    def test_each_binding_mutation_rejected(self):
        mutations={'scope':gate.FINAL_SCOPE,'baseline_commit':'0'*40,
            'protocol_sha256':'0'*64,'implementation_sha256':{},
            'execution_implementation_sha256':{},'catalogue_implementation_sha256':'0'*64,
            'backend_implementation_sha256':'0'*64,'FINAL_sha256':'0'*64,
            'FINAL_identity_record_sha256':'0'*64,'normalization_sha256':'0'*64,
            'source_roots':{},'candidate_count':10271,'imerg_completion_manifest_path':r'F:\other.jsonl',
            'completion_manifest_metadata_path_exception_approved':False,
            'FINAL_verification_mode':'ACTUAL_BINARY_READ','FINAL_TEST_CATALOGUE_AUTHORIZED':False,
            'FINAL_TEST_2025_AUTHORIZED':True}
        with workspace_fixture() as root:
            for key,value in mutations.items():
                with self.subTest(key=key):
                    changed=authorization();changed[key]=value
                    with self.assertRaises(PermissionError):load_fixture(root/'auth.json',changed)

    def test_missing_extra_or_outcome_authority_field_rejected(self):
        with workspace_fixture() as root:
            for mutation in ('missing','extra','rain_count'):
                value=authorization()
                if mutation=='missing':del value['imerg_completion_manifest_path']
                else:value[mutation]=0
                with self.subTest(mutation=mutation):
                    with self.assertRaises(PermissionError):load_fixture(root/'auth.json',value)

    def test_authority_sha_mismatch_rejected(self):
        with workspace_fixture() as root:
            path=root/'auth.json';path.write_text(json.dumps(authorization()),encoding='utf-8')
            with self.assertRaises(ValueError):execution.ExecutionAuthority.load(path,'0'*64)

    def test_numeric_flags_cannot_impersonate_explicit_boolean(self):
        with workspace_fixture() as root:
            for key,value in (('FINAL_TEST_CATALOGUE_AUTHORIZED',1),('FINAL_TEST_2025_AUTHORIZED',0),
                             ('completion_manifest_metadata_path_exception_approved',1)):
                changed=authorization();changed[key]=value
                with self.subTest(key=key):
                    with self.assertRaises(PermissionError):load_fixture(root/'auth.json',changed)

    def test_invalid_manifest_request_sha_and_creation_time(self):
        with workspace_fixture() as root:
            for key,value in (('imerg_completion_manifest_sha256','unknown'),
                              ('researcher_request_sha256','unknown'),('created_utc','bad')):
                changed=authorization();changed[key]=value
                with self.subTest(key=key):
                    with self.assertRaises(ValueError):load_fixture(root/'auth.json',changed)

    def test_changed_git_baseline_rejected(self):
        with workspace_fixture() as root:
            path=root/'auth.json';path.write_text(json.dumps(authorization()),encoding='utf-8')
            with patch.object(execution.subprocess,'check_output',return_value=b'0'*40+b'\n'):
                with self.assertRaises(PermissionError):execution.ExecutionAuthority.load(path,sha256(path))

    def test_unsealed_or_fixture_authority_cannot_enable_real_backend(self):
        for a in (execution.ExecutionAuthority(authorization(),'c'*64,object()),
                  execution.ExecutionAuthority(authorization(),'c'*64,execution._EXECUTION_SEAL,True)):
            with self.assertRaises(PermissionError):a.require_catalogue()
            with self.assertRaises(PermissionError):execution.ExecutionSourceGuard(a)

    def test_execute_missing_authority_does_not_discover_or_create(self):
        args=SimpleNamespace(authorization=None,authorization_sha256=None)
        with patch.object(execution,'ExecutionBackend') as backend,patch.object(gate,'safe_artifact_path') as output:
            with self.assertRaises(PermissionError):execution.execute(args)
            backend.assert_not_called();output.assert_not_called()


class PathAdapterTests(NoRawAccessTests):
    def test_staging_must_be_new_exact_owned_child_of_approved_cache(self):
        run=Path('run_fixture');expected=execution.STAGING_PARENT/('catalogue_only_'+run.name)
        with patch.object(Path,'resolve',return_value=Path(str(expected))),patch.object(Path,'exists',return_value=False):
            self.assertEqual(execution.execution_staging_path(str(expected),run),Path(str(expected)))
        for path in (r'C:\cache',str(execution.STAGING_PARENT),str(gate.legacy.HROOT/'cache')):
            with self.subTest(path=path):
                with self.assertRaises(PermissionError):execution.execution_staging_path(path,run)

    def test_staging_existing_or_redirected_child_rejected(self):
        run=Path('run_fixture');expected=execution.STAGING_PARENT/('catalogue_only_'+run.name)
        with patch.object(Path,'resolve',return_value=Path(str(expected))),patch.object(Path,'exists',return_value=True):
            with self.assertRaises(PermissionError):execution.execution_staging_path(str(expected),run)
        with patch.object(Path,'resolve',return_value=Path(r'F:\redirect')):
            with self.assertRaises(PermissionError):execution.execution_staging_path(str(expected),run)

    def test_only_exact_manifest_read_is_permitted_as_metadata(self):
        guard=execution.ExecutionSourceGuard(cap())
        guard.check(str(execution.METADATA_MANIFEST),'rb')
        self.assertEqual(guard.metadata_open_events,1)
        self.assertEqual(guard.raw_open_events,0);self.assertFalse(guard.qc_access)

    def test_manifest_neighbours_traversal_write_and_directory_rejected(self):
        guard=execution.ExecutionSourceGuard(cap())
        bad=(str(execution.METADATA_MANIFEST.parent/'other.jsonl'),
             str(execution.METADATA_MANIFEST.parent/'imerg_20250301.nc'),
             str(execution.METADATA_MANIFEST.parent/'..'/'manifests'/'imerg_manifest.jsonl'))
        for path in bad:
            with self.subTest(path=path):
                with self.assertRaises(PermissionError):guard.check(path,'rb')
        for mode,flags,directory in (('wb',0,False),('r+',0,False),('rb',os.O_CREAT,False),('r',0,True)):
            with self.subTest(mode=mode,flags=flags,directory=directory):
                with self.assertRaises(PermissionError):guard.check(str(execution.METADATA_MANIFEST),mode,flags,directory=directory)
        self.assertEqual(guard.metadata_open_events,0)

    def test_october_and_other_raw_product_still_rejected(self):
        guard=execution.ExecutionSourceGuard(cap())
        for path in (gate.legacy.IROOT/'2025'/'imerg_20251001.nc',
                     gate.legacy.HROOT/'202510'/'01'/'NC_H09_20251001_0020_R21_FLDK.06001_06001.nc',
                     gate.legacy.IROOT.parent/'GFS'/'data.nc'):
            with self.subTest(path=str(path)):
                with self.assertRaises(PermissionError):guard.check(str(path),'rb')

    def test_approved_metadata_location_requires_exact_resolved_path(self):
        backend=object.__new__(execution.ExecutionBackend);backend.authority=cap()
        source=Path(str(execution.METADATA_MANIFEST))
        with patch.object(Path,'resolve',return_value=source):
            backend._original_location(source,Path(str(gate.legacy.IROOT)))
        with patch.object(Path,'resolve',return_value=Path(r'F:\redirect.jsonl')):
            with self.assertRaises(ValueError):backend._original_location(source,Path(str(gate.legacy.IROOT)))

    def test_metadata_exception_does_not_replace_raw_location_verifier(self):
        backend=object.__new__(execution.ExecutionBackend);backend.authority=cap()
        source=Path(str(gate.legacy.IROOT/'2025'/'imerg_20250301.nc'));root=Path(str(gate.legacy.IROOT))
        with patch.object(execution.frozen_backend.RealCatalogueBackend,'_original_location') as original:
            backend._original_location(source,root);original.assert_called_once_with(source,root)

    def test_identity_only_policy_never_opens_final_binary(self):
        with gate.CatalogueOnlyGuard():
            with self.assertRaises(PermissionError):
                Path(r'F:\pytorch\Research\outputs\formal_training\b0_phase_b_finalfit\run_20261002T035929_487644Z\epoch_011.pt').open('rb')


class ArtifactClosureTests(NoRawAccessTests):
    def _artifacts(self,root):
        candidates=candidate_rows();population=population_rows(candidates)
        gate.write_csv(root/'b0_2025_final_test_candidate_catalogue_v1.csv',candidates)
        gate.write_csv(root/'b0_2025_final_test_population_manifest_v1.csv',population,gate.POPULATION_COLUMNS)
        freeze={'version':'v1.1','status':'CATALOGUE_FROZEN','scope':gate.CATALOGUE_SCOPE,
            'protocol_sha256':gate.PROTOCOL_SHA,'implementation_sha256':gate.implementation_hashes(),
            'catalogue_authorization_sha256':'c'*64,
            'candidate_catalogue_sha256':sha256(root/'b0_2025_final_test_candidate_catalogue_v1.csv'),
            'eligible_population_manifest_sha256':sha256(root/'b0_2025_final_test_population_manifest_v1.csv'),
            'candidate_count':gate.COUNT,'eligible_count':gate.COUNT,'rejected_count':0,'rejection_reason_counts':{},
            '2025_CATALOGUE_QC_ACCESS':True,'2025_FINAL_TEST_EXECUTED':False,'2025_MODEL_INFERENCE_SCENES':0,
            '2025_FINAL_TEST_METRICS_COMPUTED':False,'2025_TARGET_OUTCOME_SUMMARIES_EXPOSED':False,
            'raw_access_telemetry':{'2025_PIXELS_READ':0,'b13_pixel_values_read':0,'imerg_pixel_values_read':0,'cleanup_success':True},
            'fixture_only':False,'freeze_completed_utc':'2026-10-03T00:00:00+00:00'}
        (root/'catalogue_freeze_record.json').write_text(json.dumps(freeze),encoding='utf-8')
        return freeze

    def test_complete_projection_hash_and_freeze_reconciliation(self):
        with workspace_fixture() as root:
            self._artifacts(root);freeze,digest=execution.verify_frozen_artifacts(root,cap())
            self.assertEqual(freeze['candidate_count'],gate.COUNT)
            self.assertEqual(digest,sha256(root/'catalogue_freeze_record.json'))

    def test_outcome_field_in_freeze_or_telemetry_is_rejected(self):
        with workspace_fixture() as root:
            original=self._artifacts(root)
            for nested in (False,True):
                changed=json.loads(json.dumps(original))
                (changed['raw_access_telemetry'] if nested else changed)['rain_count']=0
                (root/'catalogue_freeze_record.json').write_text(json.dumps(changed),encoding='utf-8')
                with self.subTest(nested=nested):
                    with self.assertRaises(ValueError):execution.verify_frozen_artifacts(root,cap())

    def test_changed_hash_count_cleanup_and_numeric_flags_rejected(self):
        with workspace_fixture() as root:
            original=self._artifacts(root)
            changes=(('candidate_catalogue_sha256','0'*64),('eligible_count',gate.COUNT-1),
                     ('2025_FINAL_TEST_EXECUTED',0),('2025_MODEL_INFERENCE_SCENES',False))
            for key,value in changes:
                changed=json.loads(json.dumps(original));changed[key]=value
                (root/'catalogue_freeze_record.json').write_text(json.dumps(changed),encoding='utf-8')
                with self.subTest(key=key):
                    with self.assertRaises(ValueError):execution.verify_frozen_artifacts(root,cap())
            for telemetry in ({'2025_PIXELS_READ':1,'cleanup_success':True},
                              {'2025_PIXELS_READ':0,'cleanup_success':False}):
                changed=json.loads(json.dumps(original));changed['raw_access_telemetry']=telemetry
                (root/'catalogue_freeze_record.json').write_text(json.dumps(changed),encoding='utf-8')
                with self.assertRaises(ValueError):execution.verify_frozen_artifacts(root,cap())

    def test_completed_or_failed_run_cannot_be_reused(self):
        with workspace_fixture() as root:
            (root/'preparation_manifest.json').write_text('{}',encoding='utf-8')
            args=SimpleNamespace(authorization='fixture',authorization_sha256='c'*64,run_directory=root)
            for name in ('final_status.json','failure.json'):
                target=root/name;target.write_text('{}',encoding='utf-8')
                with patch.object(execution.ExecutionAuthority,'load',return_value=cap()),patch.object(execution,'ExecutionBackend') as backend:
                    with self.assertRaises(ValueError):execution.execute(args)
                    backend.assert_not_called()
                target.unlink()
