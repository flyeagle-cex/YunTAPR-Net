"""Only new process-lifetime/once-only guards; no models, data or GPU imports."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('independent_host',ROOT/'tools/research_readiness/start_independent_process.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class IndependentHostTests(unittest.TestCase):
    def test_mfc_accepts_only_its_own_fixed_train_scope_and_budget(self):
        self._check_train_scope_and_budget(
            "BOUNDED_TRAIN_MFC700_MATCHED", "start_train_mfc700.py",
            "COSINE9_E9_2023_TRAIN_MFC700_MATCHED", "COSINE9_E9_2023_TRAIN_RH700_AMPLITUDE",
        )

    def test_mfc_amplitude_rejects_prior_matching_approval(self):
        self._check_train_scope_and_budget(
            "BOUNDED_TRAIN_MFC700_AMPLITUDE", "start_train_mfc700_amplitude.py",
            "COSINE9_E9_2023_TRAIN_MFC700_AMPLITUDE", "COSINE9_E9_2023_TRAIN_MFC700_MATCHED",
        )

    def test_stage45_candidates_reject_prior_amplitude_approval(self):
        self._check_train_scope_and_budget(
            "BOUNDED_TRAIN_STAGE45_CANDIDATE_MANIFEST", "start_train_stage45_candidates.py",
            "COSINE9_E9_2023_TRAIN_STAGE45_CANDIDATE_MANIFEST", "COSINE9_E9_2023_TRAIN_MFC700_AMPLITUDE",
        )

    def _check_train_scope_and_budget(self, kind, filename, scope, rejected_scope):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            service = root / "service"
            service.mkdir()
            entry_name = "tools/research_readiness/" + filename
            entry = root / entry_name
            entry.parent.mkdir(parents=True)
            entry.touch()
            source = root / "test_python.exe"
            source.touch()
            spec_path, proposal_path, private_path, grant_path = (
                root / name for name in ("spec.json", "proposal.json", "private.json", "grant.json")
            )
            environment = dict(PYTHONHASHSEED="2029", PYTHONUTF8="1", OMP_NUM_THREADS="1",
                               MKL_NUM_THREADS="1", CUBLAS_WORKSPACE_CONFIG=":4096:8")
            budget = dict(total_scientific_source_bytes=16066485320, total_scientific_source_opens=4637,
                          forward_batches=70, checkpoint_loads=1, max_seconds=2400,
                          optimizer_updates=0, refits=0, retries=0, replay=0)
            proposal = dict(authorization_scope=scope, authorized=False, final_2025_access=False,
                            proposal_sha256="synthetic", execution_code_commit="synthetic",
                            budget=budget, scientific_choices={},
                            tasks=[dict(model="B7", seed=2029, checkpoint="COSINE9_FIXED_E9", role="Train", year=2023)],
                            code_sha256={entry_name: module.sha(entry)}, python_sha256=module.sha(source))
            private = dict(proposal_sha256="synthetic", output_root=str(root / "output"),
                           service_dir=str(service), runtime_python=str(source))
            spec = dict(kind=kind, cwd=str(root), service_dir=str(service),
                        environment=environment,
                        command=[str(source), "-B", str(entry), "execute", "--proposal", str(proposal_path),
                                 "--private-preparation", str(private_path), "--researcher-approval", str(grant_path)])
            module.write(spec_path, spec)
            module.write(proposal_path, proposal)
            module.write(private_path, private)
            grant = dict(proposal, approved_by_researcher=True, decision_id="fixture",
                         code_commit="synthetic", output_root=private["output_root"])
            module.write(grant_path, grant)
            with patch.object(module, "PRIVATE", root), patch.object(
                    module.subprocess, "check_output", side_effect=["synthetic", ""]):
                self.assertEqual(module.validate_spec(spec_path), (spec, service))
                grant["authorization_scope"] = rejected_scope
                grant_path.write_text(json.dumps(grant), encoding="utf-8")
                with self.assertRaisesRegex(PermissionError, "scope, approval, or runtime differs"):
                    module.validate_spec(spec_path)

    def test_mfc_amplitude_supervisor_uses_the_bound_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = Path(tmp)
            configuration = service / "spec.json"
            fixture = dict(kind="BOUNDED_TRAIN_MFC700_AMPLITUDE", command=["synthetic"], cwd=tmp)
            module.write(configuration, fixture)
            module.write(service / "independent_launch_claim.json", dict(spec_sha256=module.sha(configuration)))
            with patch.object(module, "validate_spec", return_value=(fixture, service)), patch.object(
                    module, "host_identity", return_value=dict(in_any_job=False, package_status=15700)
            ), patch.object(module.subprocess, "Popen") as popen:
                process = popen.return_value
                process.pid = 123
                process.wait.return_value = 0
                self.assertEqual(module.supervise(configuration), 0)
                process.wait.assert_called_once_with(timeout=2400)

    def test_stage45_candidates_supervisor_uses_the_bound_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = Path(tmp)
            configuration = service / "spec.json"
            fixture = dict(kind="BOUNDED_TRAIN_STAGE45_CANDIDATE_MANIFEST", command=["synthetic"], cwd=tmp)
            module.write(configuration, fixture)
            module.write(service / "independent_launch_claim.json", dict(spec_sha256=module.sha(configuration)))
            with patch.object(module, "validate_spec", return_value=(fixture, service)), patch.object(
                    module, "host_identity", return_value=dict(in_any_job=False, package_status=15700)
            ), patch.object(module.subprocess, "Popen") as popen:
                process = popen.return_value
                process.pid = 123
                process.wait.return_value = 0
                self.assertEqual(module.supervise(configuration), 0)
                process.wait.assert_called_once_with(timeout=2400)

    def test_cross_checkout_configuration_must_be_absolute_before_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);entry=p/'start_dote_physical_control.py';entry.write_text('')
            folder=p/'service';folder.mkdir();configuration=p/'spec.json'
            flags=('--researcher-approval','--proposal','--private-preparation')
            for relative_flag in flags:
                command=[sys.executable,'-B',str(entry),'execute']
                for flag in flags:command.extend([flag,'relative.json' if flag==relative_flag else str(p/'absolute.json')])
                configuration.write_text(json.dumps(dict(kind='APPROVAL_BOUND_EXECUTION',command=command,service_dir=str(folder))))
                with self.subTest(flag=relative_flag),patch.object(module,'PRIVATE',p),patch.object(module,'read',side_effect=lambda path:json.loads(configuration.read_text()) if Path(path).name=='spec.json' else {}),patch.object(module.subprocess,'check_output') as run:
                    with self.assertRaisesRegex(ValueError,'requires absolute '+relative_flag):module.validate_spec(configuration)
                    run.assert_not_called()

    def test_nested_or_unknown_job_and_package_fail_closed(self):
        for job,package in ((True,15700),(None,15700),(False,0)):
            with self.assertRaises(PermissionError):module.require_independent(dict(in_any_job=job,package_status=package))
        module.require_independent(dict(in_any_job=False,package_status=15700))

    def test_second_dispatch_cannot_reuse_claim_or_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);configuration=p/'spec.json';configuration.write_text('{}')
            with patch.object(module,'validate_spec',return_value=({},p)),patch.object(module.subprocess,'run') as run:
                run.return_value.stdout='{"return_value":0,"supervisor_pid":123}'
                self.assertEqual(module.spawn(configuration)['supervisor_pid'],123)
                with self.assertRaises(FileExistsError):module.spawn(configuration)
                self.assertEqual(run.call_count,1)

    def test_target_not_started_when_supervisor_is_still_coupled(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);configuration=p/'spec.json';configuration.write_text('{}')
            module.write(p/'independent_launch_claim.json',dict(spec_sha256=module.sha(configuration)))
            with patch.object(module,'validate_spec',return_value=({},p)),patch.object(module,'host_identity',return_value=dict(in_any_job=True,package_status=15700)),patch.object(module.subprocess,'Popen') as popen:
                with self.assertRaises(PermissionError):module.supervise(configuration)
                popen.assert_not_called()


if __name__=='__main__':unittest.main()
