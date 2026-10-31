"""Lifetime boundary for trusted, stdin-gated workers; not a security sandbox."""
import ctypes
import math
import os
import signal
import subprocess
import time


class BoundaryUnavailable(RuntimeError):
    pass


class _WindowsJob:
    def __init__(self):
        from ctypes import wintypes as w
        class Basic(ctypes.Structure):
            _fields_ = [('process_time', ctypes.c_longlong), ('job_time', ctypes.c_longlong),
                        ('flags', w.DWORD), ('min_working_set', ctypes.c_size_t),
                        ('max_working_set', ctypes.c_size_t), ('active_limit', w.DWORD),
                        ('affinity', ctypes.c_size_t), ('priority', w.DWORD), ('scheduling', w.DWORD)]
        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in ('read_ops', 'write_ops', 'other_ops', 'read_bytes', 'write_bytes', 'other_bytes')]
        class Extended(ctypes.Structure):
            _fields_ = [('basic', Basic), ('io', IO), ('process_memory', ctypes.c_size_t),
                        ('job_memory', ctypes.c_size_t), ('peak_process_memory', ctypes.c_size_t), ('peak_job_memory', ctypes.c_size_t)]
        api = ctypes.WinDLL('kernel32', use_last_error=True)
        api.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
        api.CreateJobObjectW.restype = w.HANDLE
        api.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
        api.SetInformationJobObject.restype = w.BOOL
        api.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        api.AssignProcessToJobObject.restype = w.BOOL
        api.CloseHandle.argtypes = [w.HANDLE]
        api.CloseHandle.restype = w.BOOL
        self.api, self.handle = api, api.CreateJobObjectW(None, None)
        if not self.handle:
            raise BoundaryUnavailable('Cannot create worker job')
        settings = Extended()
        settings.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not api.SetInformationJobObject(self.handle, 9, ctypes.byref(settings), ctypes.sizeof(settings)):
            self.close()
            raise BoundaryUnavailable('Cannot configure worker job')

    def assign(self, process):
        if not self.api.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise BoundaryUnavailable('Cannot assign worker to lifetime job')

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


def run_worker(command, payload, *, timeout, cwd=None):
    """Run a trusted command that waits for stdin before starting workload.

    Attach the Windows job before releasing stdin. Closing the job kills worker
    descendants on timeout, cancellation and normal exit. POSIX uses a process
    group. These are lifetime controls, not filesystem/network isolation.
    stdout/stderr are discarded; workers persist reviewed reports themselves.
    """
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 86400:
        raise ValueError('Worker timeout must be finite, positive and at most one day')
    if not isinstance(payload, bytes) or len(payload) > 500000:
        raise ValueError('Worker input must be bounded bytes')
    if not isinstance(command, list) or not command or any(not isinstance(v, str) for v in command):
        raise ValueError('Worker command must be an explicit argument list')
    started = time.monotonic()
    job = _WindowsJob() if os.name == 'nt' else None
    process = None
    timed_out = False
    try:
        options = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {'start_new_session': True}
        process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.PIPE,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **options)
        if job:
            job.assign(process)
        try:
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, timeout)
            process.communicate(payload, timeout=remaining)
        except subprocess.TimeoutExpired:
            timed_out = True
    finally:
        if job:
            job.close()
        elif process:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if process:
            if process.poll() is None:
                process.kill()  # Also covers failure to attach a Windows job.
            process.wait(timeout=10)
            if process.stdin:
                process.stdin.close()
    return {'status': 'timeout' if timed_out else 'complete' if process.returncode == 0 else 'failed',
            'returncode': process.returncode, 'timeout_seconds': timeout,
            'duration_seconds': round(time.monotonic() - started, 4),
            'boundary': 'windows-kill-on-close-job' if job else 'posix-process-group',
            'sandbox': False, 'live_inference': False}
