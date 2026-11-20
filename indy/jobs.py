"""Background jobs. Requests return a job id at once and the caller polls (worker contract:
never hold a request open for a long job). One worker thread, because the local model is
the bottleneck and running two jobs at once only makes both slower.

Jobs are persisted as JSON so a restart does not lose results. A job that was running when
the process died is marked failed with an honest message, never resumed silently.
"""

import inspect
import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


class JobContext:
    """Handed to a job that wants to say what it is doing, so the UI can show live progress."""

    def __init__(self, store: "JobStore", job_id: str):
        self._store, self._job_id = store, job_id

    def progress(self, text: str) -> None:
        self._store._update(self._job_id, progress=text[:200])


class JobStore:
    def __init__(self, state_dir: str | Path):
        self.dir = Path(state_dir) / "jobs"
        self.dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="indy-job")
        self._jobs: dict[str, dict] = {}
        for f in self.dir.glob("*.json"):
            try:
                job = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if job.get("status") in ("queued", "running"):
                job.update(status="failed", error="Interrupted by a restart; submit it again.")
                job["finished_at"] = _now()
                self._write(job)
            self._jobs[job["job_id"]] = job

    def _write(self, job: dict) -> None:
        (self.dir / f"{job['job_id']}.json").write_text(json.dumps(job, indent=2), encoding="utf-8")

    def _update(self, job_id: str, **fields) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.update(fields)
            self._write(job)

    def submit(self, kind: str, params: dict, fn) -> dict:
        job = {
            "job_id": uuid.uuid4().hex[:12], "kind": kind, "status": "queued",
            "params": params, "created_at": _now(), "result": None, "error": None,
        }  # fmt: skip
        with self._lock:
            self._jobs[job["job_id"]] = job
            self._write(job)
        self._pool.submit(self._run, job["job_id"], fn)
        return dict(job)

    def _run(self, job_id: str, fn) -> None:
        self._update(job_id, status="running", started_at=_now())
        try:
            result = fn(JobContext(self, job_id)) if inspect.signature(fn).parameters else fn()
        except Exception as exc:  # noqa: BLE001 - any failure is reported to the caller
            self._update(job_id, status="failed", error=str(exc) or type(exc).__name__,
                         finished_at=_now())  # fmt: skip
            return
        self._update(job_id, status="done", result=result, finished_at=_now(), progress="")

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def list(self) -> list[dict]:
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda j: j["created_at"], reverse=True)
            return [dict(j) for j in jobs]

    def find_active(self, kind: str, opportunity_id: str) -> dict | None:
        """A queued or running job of this kind for this opportunity, if there is one."""
        with self._lock:
            for j in self._jobs.values():
                if (j["kind"] == kind and j["status"] in ("queued", "running")
                        and j["params"].get("opportunity_id") == opportunity_id):  # fmt: skip
                    return dict(j)
        return None

    def busy(self) -> bool:
        with self._lock:
            return any(j["status"] in ("queued", "running") for j in self._jobs.values())
