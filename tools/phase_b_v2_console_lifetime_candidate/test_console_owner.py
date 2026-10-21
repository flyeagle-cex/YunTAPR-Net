"""Actual GUI OS tasks, hidden artificial consoles and owned Job teardown.

Never launches real data/model code. Every fixture has a <=15 second deadline.
Failed runs and their receipts remain in distinct timestamped directories.
"""
from pathlib import Path
import ctypes as C
from ctypes import wintypes as W
from datetime import datetime, timezone
import hashlib, json, os, secrets, subprocess, sys, time, unittest

ROOT = Path(__file__).absolute().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
os.environ['PYTHONPATH'] = str(ROOT / 'src')
from yuntapr.experimental.phase_b_v2_console_lifetime_candidate import task_bridge as bridge
from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.winjob import (
    Job, K, bind, checked, open_process, native_identity, exited, close_handle, in_job)
from yuntapr.experimental.phase_b_v2_stability_review import native

RUN = bridge.LOCAL / ('artificial_tasks_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '_' + secrets.token_hex(4))
RUN.mkdir(parents=True)
RECORDS = []
DEAD = ('ABSENT', 'EXITED', 'PID_REUSED')
terminate = bind(K, 'TerminateProcess', [W.HANDLE, W.UINT], W.BOOL)
post = bind(C.WinDLL('user32', use_last_error=True), 'PostMessageW',
            [W.HWND, W.UINT, W.WPARAM, W.LPARAM], W.BOOL)


def wait_for(fn, seconds=5):
    deadline = time.monotonic() + seconds
    while not fn():
        if time.monotonic() >= deadline:
            raise TimeoutError('BOUNDED_ARTIFICIAL_WAIT')
        time.sleep(.02)


def held(identity):
    handle = checked(open_process(0x00100000 | 0x1000 | 1, False, identity['pid']))
    try:
        if native_identity(handle) != {k: identity[k] for k in ('pid', 'creation_filetime', 'image_path_key')}:
            raise PermissionError('ARTIFICIAL_NATIVE_IDENTITY')
        return handle
    except BaseException:
        close_handle(handle)
        raise


class Tests(unittest.TestCase):
    def test_01_scope_refuses_real_and_parent_paths_before_any_io(self):
        for folder in (ROOT / 'docs/phase_b_v2_formal_execution',
                       bridge.LOCAL / 'artificial_tasks_bad/../artificial_x',
                       bridge.LOCAL / 'artificial_tasks_2025/artificial_x'):
            with self.assertRaises(PermissionError):
                bridge.fixed_spec(folder, 'a' * 32)
        with self.assertRaises(PermissionError):
            bridge.fixed_spec(RUN / 'artificial_bad_nonce', 'APPROVED')

    def run_case(self, label, action):
        folder = RUN / ('artificial_' + label)
        folder.mkdir()
        nonce = secrets.token_hex(16)
        host = Job()
        spec = None
        handles = {}
        identities = {}
        row = dict(case=label, pass_case=False)
        started = time.monotonic()
        try:
            host.spawn([sys.executable, '-m',
                'yuntapr.experimental.phase_b_v2_console_lifetime_candidate.fixture',
                'client', str(folder), nonce], ROOT)
            wait_for(lambda: (folder / 'client.json').exists())
            identities['client'] = bridge.load(folder / 'client.json')
            handles['client'] = held(identities['client'])
            spec = bridge.start(folder, nonce)
            wait_for(lambda: (folder / 'ready.json').exists(), 7)
            for role in ('gui', 'owner', 'worker'):
                identities[role] = bridge.load(folder / (role + '.json'))
                handles[role] = held(identities[role])
                self.assertEqual(identities[role]['nonce'], nonce)
                self.assertEqual(identities[role]['console']['hwnd'], 0)
                self.assertEqual(identities[role]['console']['process_count'], 0)
                member = W.BOOL()
                checked(in_job(handles[role], host.handle, C.byref(member)))
                self.assertFalse(member.value)
            if action == 'console_control_event':
                signal = subprocess.run([sys.executable, '-m',
                    'yuntapr.experimental.phase_b_v2_console_lifetime_candidate.fixture',
                    'signal', str(folder), nonce], creationflags=subprocess.CREATE_NO_WINDOW,
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=3)
                self.assertEqual(signal.returncode, 0)
                self.assertTrue(bridge.load(folder / 'signal_receipt.json')['synthetic_only'])
                wait_for(lambda: exited(handles['client']))
            else:
                host.close()
                wait_for(lambda: exited(handles['client']))
            time.sleep(.25)
            for role in ('gui', 'owner', 'worker'):
                self.assertFalse(exited(handles[role]), role + ' must survive client closure')
            row['survived_client_close'] = True
            if action == 'gui_crash':
                checked(terminate(handles['gui'], 99))
                wait_for(lambda: all(exited(handles[r]) for r in ('gui', 'owner', 'worker')))
                self.assertFalse((folder / 'gui_termination.json').exists())
            elif action == 'owner_crash':
                checked(terminate(handles['owner'], 99))
                wait_for(lambda: all(exited(handles[r]) for r in ('gui', 'owner', 'worker')))
                receipt = bridge.load(folder / 'gui_termination.json')
                self.assertTrue(receipt['job_empty'])
                self.assertEqual(receipt['owner_exit_code'], 99)
            else:
                (folder / 'stop.request').write_text('artificial-only', encoding='ascii')
                wait_for(lambda: all(exited(handles[r]) for r in ('gui', 'owner', 'worker')))
                self.assertTrue(bridge.load(folder / 'termination.json')['job_empty'])
                self.assertTrue(bridge.load(folder / 'gui_termination.json')['job_empty'])
                self.assertEqual(bridge.load(folder / 'gui_termination.json')['owner_exit_code'], 0)
            self.assertEqual(identities['owner']['hash_probe'], identities['worker']['hash_probe'])
            self.assertFalse(identities['owner']['torch_imported'])
            self.assertFalse(identities['worker']['torch_imported'])
            row.update(pass_case=True, all_console_free=True, identities=identities,
                exit_path=action, worker_tree_stopped=True,
                gui_entry_sha256=spec['entry_sha256'], gui_binary_sha256=spec['gui_sha256'])
        finally:
            host.close()
            # Only retained, native-identity-bound artificial process handles.
            for role in ('gui', 'owner', 'worker', 'client'):
                handle = handles.get(role)
                if handle and not exited(handle):
                    terminate(handle, 99)
            for handle in handles.values():
                wait_for(lambda h=handle: exited(h))
                close_handle(handle)
            if spec is not None:
                # Task result settles after the venv GUI wrapper exits.
                deadline = time.monotonic() + 3
                while True:
                    try:
                        row['task_cleanup'] = bridge.remove_finished(spec)
                        break
                    except RuntimeError as exc:
                        if 'Retain running artificial task' not in str(exc) or time.monotonic() >= deadline:
                            raise
                        time.sleep(.1)
            row['elapsed_seconds'] = time.monotonic() - started
            row['leftovers'] = {r: native.process(i) for r, i in identities.items()}
            RECORDS.append(row)

    def test_02_artificial_console_control_event_owner_survives(self):
        self.run_case('console_control_event', 'console_control_event')

    def test_03_close_codex_like_job_owner_survives(self):
        self.run_case('client_job_close', 'close_client_job')

    def test_04_gui_bootstrap_crash_kills_entire_owned_tree(self):
        self.run_case('gui_crash', 'gui_crash')

    def test_05_owner_crash_kills_worker_and_records_failure(self):
        self.run_case('owner_crash', 'owner_crash')


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    leftovers = [(row['case'], role, probe) for row in RECORDS
                 for role, probe in row.get('leftovers', {}).items() if probe['status'] not in DEAD]
    report = dict(tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
        skipped=len(result.skipped), records=RECORDS, leftover_owned_processes=leftovers,
        synthetic_only=True, real_data_reads=0, checkpoint_reads=0, optimizer_steps=0,
        actual_codex_window_closed_in_test=False,
        pass_all=result.wasSuccessful() and len(RECORDS) == 4 and not leftovers)
    bridge.save(RUN, 'results.json', report)
    print(json.dumps(dict(results_relative_path=(RUN / 'results.json').relative_to(ROOT).as_posix(),
                         pass_all=report['pass_all'])))
    raise SystemExit(not report['pass_all'])
