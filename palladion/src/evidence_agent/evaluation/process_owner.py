"""Own an evaluator's entire process tree; never enumerate or kill foreign processes."""
from __future__ import annotations

import ctypes
import os
import signal
from multiprocessing.connection import Connection
from typing import Any, Callable


def study_entry(worker: Callable[[Connection, dict[str, Any]], None], pipe: Connection,
                 arguments: dict[str, Any], start: Any) -> None:
    """Establish ownership before importing/executing the selected worker workload."""
    start.wait()
    if os.name != "nt":
        getattr(os, "setsid")()
    worker(pipe, arguments)


class ProcessOwner:
    """Windows kill-on-close job with optional hard memory cap; POSIX process group.

    The child waits on a parent-controlled start event until assignment succeeds.
    This prevents a search grandchild escaping before the owner establishes its scope.
    POSIX callers requiring memory limits must set RLIMIT_AS inside their child.
    """

    def __init__(self, *, memory_bytes: int | None = None) -> None:
        if memory_bytes is not None and memory_bytes < 64 * 1024 * 1024:
            raise ValueError("Worker memory cap must be at least64MiB")
        self.closed = False
        self.job: Any = None
        self.kernel: Any = None
        if os.name != "nt":
            return
        from ctypes import wintypes

        class Basic(ctypes.Structure):
            _fields_ = [("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
                ("flags", wintypes.DWORD), ("min_working", ctypes.c_size_t),
                ("max_working", ctypes.c_size_t), ("active_limit", wintypes.DWORD),
                ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD),
                ("scheduling", wintypes.DWORD)]

        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in
                ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]

        class Extended(ctypes.Structure):
            _fields_ = [("basic", Basic), ("io", IO), ("process_memory", ctypes.c_size_t),
                ("job_memory", ctypes.c_size_t), ("peak_process", ctypes.c_size_t),
                ("peak_job", ctypes.c_size_t)]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
            ctypes.c_void_p, wintypes.DWORD]
        kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel = kernel
        self.job = kernel.CreateJobObjectW(None, None)
        if not self.job:
            raise ctypes.WinError(ctypes.get_last_error())
        information = Extended()
        information.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if memory_bytes is not None:
            information.basic.flags |= 0x200  # JOB_OBJECT_LIMIT_JOB_MEMORY
            information.job_memory = memory_bytes
        if not kernel.SetInformationJobObject(self.job, 9, ctypes.byref(information), ctypes.sizeof(information)):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def assign(self, pid: int) -> None:
        if self.kernel is None:
            return  # Child calls setsid before it acknowledges start.
        handle = self.kernel.OpenProcess(0x0100 | 0x0001, False, pid)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not self.kernel.AssignProcessToJobObject(self.job, handle):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            self.kernel.CloseHandle(handle)

    def close(self, pid: int | None = None) -> None:
        if self.closed:
            return
        self.closed = True
        if self.job is not None:
            self.kernel.CloseHandle(self.job)
            self.job = None
        elif os.name != "nt" and pid is not None:
            try:
                getattr(os, "killpg")(pid, getattr(signal, "SIGKILL"))
            except ProcessLookupError:
                pass
