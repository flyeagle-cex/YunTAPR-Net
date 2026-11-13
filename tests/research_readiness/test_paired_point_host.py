"""Synthetic WMI-host entry checks. No WMI process is created."""

from contextlib import contextmanager
import json
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch
from uuid import uuid4

from tools.research_readiness import start_independent_process as host


@contextmanager
def fixture():
    parent = Path(__file__).resolve().parents[2] / "docs/research_readiness/.local/paired_point_host_tests"
    parent.mkdir(parents=True, exist_ok=True)
    folder = parent / uuid4().hex
    folder.mkdir()
    try:
        entry = folder / "tools/research_readiness/start_paired_point_evaluation.py"
        entry.parent.mkdir(parents=True)
        entry.write_text("def validate_entry(*args):\n    return {}, {'runtime_python': "
                         + repr(sys.executable) + "}\n", encoding="utf-8")
        private = folder / "private"
        service = private / "service"
        service.mkdir(parents=True)
        config = private / "spec.json"
        command = [sys.executable, "-B", str(entry), "execute"]
        for flag in ("--proposal", "--private-preparation", "--researcher-approval"):
            command.extend((flag, str(private / (flag[2:] + ".json"))))
        spec = dict(kind="BOUNDED_PAIRED_POINT_EVALUATION", command=command,
                    cwd=str(folder), service_dir=str(service), environment={})
        config.write_text(json.dumps(spec), encoding="utf-8")
        with patch.object(host, "PRIVATE", private):
            yield config, entry, service, spec
    finally:
        if folder.resolve().parent != parent.resolve() or len(folder.name) != 32:
            raise RuntimeError("Synthetic fixture cleanup target changed")
        shutil.rmtree(folder)


class PairedHostTests(unittest.TestCase):
    def test_exact_entry_calls_approval_validator_without_spawning(self):
        with fixture() as (config, _, service, _), patch.object(host.subprocess, "run") as spawn:
            _, actual = host.validate_spec(config)
            self.assertEqual(actual, service.resolve())
            spawn.assert_not_called()

    def test_relative_approval_path_is_rejected(self):
        with fixture() as (config, _, _, spec):
            spec["command"][-1] = "relative.json"
            config.write_text(json.dumps(spec), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Absolute paired"):
                host.validate_spec(config)

    def test_missing_approval_rejects_before_launch_claim(self):
        with fixture() as (config, entry, service, _), patch.object(host.subprocess, "run") as spawn:
            entry.write_text("def validate_entry(*args):\n    raise PermissionError('No exact approval')\n", encoding="utf-8")
            with self.assertRaisesRegex(PermissionError, "No exact approval"):
                host.spawn(config)
            self.assertFalse((service / "independent_launch_claim.json").exists())
            spawn.assert_not_called()

    def test_other_mode_is_rejected_before_validator(self):
        with fixture() as (config, _, _, spec):
            spec["command"][3] = "worker"
            config.write_text(json.dumps(spec), encoding="utf-8")
            with self.assertRaisesRegex(PermissionError, "fixed two-E9"):
                host.validate_spec(config)


if __name__ == "__main__":
    unittest.main()
