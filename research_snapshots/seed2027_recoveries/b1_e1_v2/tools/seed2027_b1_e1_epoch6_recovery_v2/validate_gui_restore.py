"""Validate the exact frozen GUI interpreter and real LAST, never train."""
import sys,traceback
import operate
from yuntapr.training.phase_b_v2_seed2027_b1_e1_epoch6_recovery_v2 import protocol as p
sys.stdout=(p.LOCAL/'gui_restore_stdout.txt').open('x',encoding='utf-8',buffering=1)
sys.stderr=(p.LOCAL/'gui_restore_stderr.txt').open('x',encoding='utf-8',buffering=1)
try:
    from ctypes import wintypes as W
    from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.winjob import K,native_identity
    from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.watchdog import interpreter_keys
    from yuntapr.training.phase_b_v2_seed2027_b1_e1_epoch6_recovery_v2.task_owner import gui_runtime
    K.GetCurrentProcess.restype=W.HANDLE
    actual=native_identity(K.GetCurrentProcess());allowed=interpreter_keys();runtime=gui_runtime(p.verify_release())
    if actual['image_path_key'] not in allowed or actual['image_path_key'] not in {x['image_path_key'] for x in runtime['binaries'].values()}:
        raise PermissionError('GUI_WORKER_EXACT_FROZEN_NATIVE_FAMILY')
    p.atomic_json(p.OUT/'GUI_INTERPRETER_IDENTITY.json',dict(status='PASS',native_identity=actual,
        frozen_gui_runtime_verified=True,supervisor_worker_interpreter_family_verified=True,
        same_frozen_venv=True,environment_files_modified=False,optimizer_step_calls=0))
    from validate_restore import main
    main()
except BaseException:
    traceback.print_exc();raise
