"""Conservative launch headroom, without changing any frozen runtime limit."""
import shutil,subprocess
from .protocol import LIMITS,LOCAL
from .resources import system_memory


def launch_headroom():
    memory=system_memory()
    free=int(subprocess.check_output(['nvidia-smi','--id=0','--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True).strip())*1024**2
    required_commit=LIMITS['minimum_available_commit_bytes']+LIMITS['max_process_commit_bytes']+512*1024**2
    required_ram=LIMITS['minimum_available_ram_bytes']+LIMITS['max_working_set_bytes']+512*1024**2
    required_gpu=LIMITS['max_cuda_reserved_bytes']
    disk=shutil.disk_usage(LOCAL).free
    return dict(available_commit=memory['available_page'],available_ram=memory['available_phys'],available_gpu=free,
        required_commit=required_commit,required_ram=required_ram,required_gpu=required_gpu,
        disk_free=disk,minimum_disk=LIMITS['minimum_disk_free_bytes'],
        ready=memory['available_page']>=required_commit and memory['available_phys']>=required_ram and free>=required_gpu and disk>=LIMITS['minimum_disk_free_bytes'],
        runtime_limits_changed=False,preflight_only=True)


def require_launch_headroom():
    row=launch_headroom()
    if not row['ready']:raise MemoryError('INSUFFICIENT_PRELAUNCH_HEADROOM_NO_SESSION_CLAIMED')
    return row
