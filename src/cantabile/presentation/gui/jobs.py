"""Single-worker job runner for the local GUI."""

from __future__ import annotations

import queue
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

LogFn = Callable[[str], None]
JobFn = Callable[[LogFn], dict[str, Any]]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Job:
    """Mutable job state guarded by JobRunner's lock."""

    id: str
    action: str
    playlist: str = ""
    status: str = "queued"
    created_at: str = field(default_factory=_now)
    started_at: str = ""
    finished_at: str = ""
    logs: list[str] = field(default_factory=list)
    result: dict[str, Any] = field(default_factory=dict)
    error: str = ""


class JobRunner:
    """Run GUI-triggered workflows one at a time in a background thread."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._queue: queue.Queue[tuple[str, JobFn]] = queue.Queue()
        self._lock = threading.Lock()
        self._worker = threading.Thread(target=self._loop, daemon=True)
        self._worker.start()

    def enqueue(self, action: str, fn: JobFn, playlist: str = "") -> dict[str, Any]:
        job = Job(id=uuid.uuid4().hex[:12], action=action, playlist=playlist)
        with self._lock:
            self._jobs[job.id] = job
        self._queue.put((job.id, fn))
        return self.snapshot(job.id)

    def snapshot(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs[job_id]
            return _job_dict(job)

    def recent(self, limit: int = 12) -> list[dict[str, Any]]:
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda item: item.created_at, reverse=True)
            return [_job_dict(job) for job in jobs[:limit]]

    def _log(self, job_id: str, message: str) -> None:
        with self._lock:
            self._jobs[job_id].logs.append(message)

    def _loop(self) -> None:
        while True:
            job_id, fn = self._queue.get()
            with self._lock:
                job = self._jobs[job_id]
                job.status = "running"
                job.started_at = _now()
            try:
                result = fn(lambda message: self._log(job_id, message))
            except Exception as exc:  # noqa: BLE001 - surface workflow failures in GUI
                with self._lock:
                    job = self._jobs[job_id]
                    job.status = "failed"
                    job.error = str(exc)
                    job.finished_at = _now()
            else:
                with self._lock:
                    job = self._jobs[job_id]
                    job.status = "succeeded"
                    job.result = result
                    job.finished_at = _now()
            finally:
                self._queue.task_done()


def _job_dict(job: Job) -> dict[str, Any]:
    return {
        "id": job.id,
        "action": job.action,
        "playlist": job.playlist,
        "status": job.status,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "logs": list(job.logs),
        "result": dict(job.result),
        "error": job.error,
    }
