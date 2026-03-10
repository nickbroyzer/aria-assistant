"""
Per-file locking for JSON data files.

Uses OS-level file locks (fcntl on Linux, msvcrt on Windows) via the
filelock library so locks work across gunicorn worker processes AND
across threads within a single process.

Usage:
    from file_locks import file_lock

    def save_jobs(data):
        with file_lock(JOBS_FILE):
            with open(JOBS_FILE, "w") as f:
                json.dump(data, f, indent=2)
"""

import os
import threading
from filelock import FileLock

LOCK_DIR = ".locks"
_cache_lock = threading.Lock()
_locks: dict[str, FileLock] = {}


def file_lock(filepath: str, timeout: int = 10) -> FileLock:
    """Return a FileLock for the given data file path.

    Lock files are stored in .locks/<basename>.lock.
    The returned object is a context manager:

        with file_lock("jobs.json"):
            ...
    """
    with _cache_lock:
        if filepath not in _locks:
            os.makedirs(LOCK_DIR, exist_ok=True)
            lock_path = os.path.join(LOCK_DIR, os.path.basename(filepath) + ".lock")
            _locks[filepath] = FileLock(lock_path, timeout=timeout)
        return _locks[filepath]
