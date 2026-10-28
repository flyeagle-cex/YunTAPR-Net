"""Only new process-lifetime/once-only guards; no models, data or GPU imports."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('independent_host',ROOT/'tools/research_readiness/start_independent_process.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class IndependentHostTests(unittest.TestCase):
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
