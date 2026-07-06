"""In-process render-job status registry (leaf module).

The Prefab studio (Plan 3) and the ``local://render/jobs/{id}/status``
resource (Plan 2) read this so live status works independent of whether the
host supports the MCP task protocol. Placed in app.shared so resources (which
must not import app.handlers) can read it.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass
class RenderJob:
    job_id: str
    version_id: int
    phase: str = "pending"
    progress: int = 0
    total: int = 0
    message: str = ""
    out_path: str | None = None
    error: str | None = None
    done: bool = False


class RenderJobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, RenderJob] = {}
        self._lock = Lock()

    def start(self, *, job_id: str, version_id: int, phase: str = "pending") -> RenderJob:
        with self._lock:
            job = RenderJob(job_id=job_id, version_id=version_id, phase=phase)
            self._jobs[job_id] = job
            return job

    def update(self, job_id: str, **fields: object) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            for k, v in fields.items():
                setattr(job, k, v)

    def get(self, job_id: str) -> RenderJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def clear(self) -> None:
        with self._lock:
            self._jobs.clear()


RENDER_JOBS = RenderJobRegistry()
