"""Artificial processes only; fixed 32 MiB allocation, no data/model/GPU imports."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

# An accidental model/data import is an error even before filesystem decoding.
class NoScienceImports:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'torch', 'numpy', 'netCDF4', 'h5py', 'cupy'}:
            raise PermissionError('NO_SCIENCE_OR_GPU_IMPORTS')


sys.meta_path.insert(0, NoScienceImports())
from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.winjob import K, Job, native_identity
from ctypes import wintypes as W
K.GetCurrentProcess.restype = W.HANDLE


def write(path: Path, value: dict):
    tmp = path.with_suffix('.tmp')
    with tmp.open('xb') as stream:
        stream.write(json.dumps(value).encode()); stream.flush(); os.fsync(stream.fileno())
    tmp.replace(path)


def main():
    folder, mode, nonce, parent = Path(sys.argv[1]), sys.argv[2], sys.argv[3], int(sys.argv[4])
    script = str(Path(__file__).absolute())
    if mode == 'wrapper':
        subprocess.Popen([sys.executable, script, str(folder), sys.argv[5], nonce, str(parent)])
        # Wrapper deliberately exits while real interpreter child remains active.
        return 0
    if mode == 'leaf':
        write(folder/'leaf.json', native_identity(K.GetCurrentProcess()))
        while True: time.sleep(.05)
    if mode == 'before_registration': return 7
    ident = native_identity(K.GetCurrentProcess())
    row = dict(ident, nonce=nonce, campaign='ARTIFICIAL_WATCHDOG_V1',
               no_science_imports=not any(x.startswith('torch') for x in sys.modules))
    if mode == 'foreign_pid': row['pid'] = parent
    if mode == 'missing_pid': row['pid'] = 4294967294
    if mode == 'bad_creation': row['creation_filetime'] += 1
    if mode == 'bad_image': row['image_path_key'] = '0'*64
    if mode == 'bad_nonce': row['nonce'] = '0'*32
    if mode == 'bad_campaign': row['campaign'] = 'APPROVED'
    if mode != 'no_registration': write(folder/'identity.json', row)
    if mode == 'driver_crash':
        inner = Job()
        inner.spawn([sys.executable, script, str(folder), 'leaf', nonce, str(parent)], folder)
        while not (folder/'leaf.json').exists(): time.sleep(.01)
        # No Python finally/Job.close: OS closes the driver's last job handle.
        time.sleep(.25)
        os._exit(17)
    if mode in {'tree_timeout', 'worker_exit_tree', 'close_job'}:
        subprocess.Popen([sys.executable, script, str(folder), 'leaf', nonce, str(parent)])
        while not (folder/'leaf.json').exists(): time.sleep(.01)
    if mode in {'unexpected_exit', 'worker_exit_tree'}:
        # Give the monitor a chance to retain the live identity before exit.
        # Exit-before-registration is independently tested without this pause.
        time.sleep(.15)
        return 9
    if mode == 'success':
        time.sleep(.2)
        write(folder/'complete.json', dict(nonce=nonce, status='SYNTHETIC_COMPLETE'))
        return 0
    if mode == 'memory':
        buf = bytearray(32*1024**2)
        for i in range(0, len(buf), 4096): buf[i] = 1
        write(folder/'allocation.json', dict(controlled_allocation_bytes=len(buf)))
    while True: time.sleep(.05)


if __name__ == '__main__': raise SystemExit(main())
