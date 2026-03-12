import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, Optional

from .models import gen_id, now_utc

logger = logging.getLogger("job_queue")

ProgressCallback = Callable[[float, str, Optional[Dict[str, Any]]], Awaitable[None]]
JobProcessor = Callable[[str, Dict[str, Any], ProgressCallback], Awaitable[Dict[str, Any]]]


class JobQueueManager:
    def __init__(self, db):
        self.db = db
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._processors: Dict[str, JobProcessor] = {}
        self._worker_task: Optional[asyncio.Task] = None

    def register_processor(self, kind: str, processor: JobProcessor):
        self._processors[kind] = processor

    async def start(self):
        await self._recover_incomplete_jobs()
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker_loop())
            logger.info("Job queue worker started")

    async def shutdown(self):
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    async def enqueue(self, kind: str, payload: Dict[str, Any], meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        job = {
            "id": gen_id(),
            "kind": kind,
            "status": "queued",
            "progress_pct": 0.0,
            "message": "Queued",
            "payload": payload,
            "meta": meta or {},
            "queued_at": now_utc(),
            "started_at": None,
            "finished_at": None,
            "updated_at": now_utc(),
            "result": None,
            "error": None,
        }
        await self.db.analysis_jobs.insert_one(job.copy())
        await self._queue.put(job["id"])
        return job

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        return await self.db.analysis_jobs.find_one({"id": job_id}, {"_id": 0})

    async def list_jobs(self, kind: Optional[str] = None, limit: int = 20):
        query = {"kind": kind} if kind else {}
        return await self.db.analysis_jobs.find(query, {"_id": 0}).sort("queued_at", -1).to_list(limit)

    async def update_job(
        self,
        job_id: str,
        *,
        status: Optional[str] = None,
        progress_pct: Optional[float] = None,
        message: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        extra_fields: Optional[Dict[str, Any]] = None,
    ):
        fields: Dict[str, Any] = {"updated_at": now_utc()}
        if status is not None:
            fields["status"] = status
            if status == "running":
                fields["started_at"] = now_utc()
            if status in {"completed", "failed", "cancelled"}:
                fields["finished_at"] = now_utc()
        if progress_pct is not None:
            fields["progress_pct"] = round(max(0.0, min(progress_pct, 100.0)), 2)
        if message is not None:
            fields["message"] = message
        if result is not None:
            fields["result"] = result
        if error is not None:
            fields["error"] = error
        if extra_fields:
            fields.update(extra_fields)
        await self.db.analysis_jobs.update_one({"id": job_id}, {"$set": fields})

    async def _recover_incomplete_jobs(self):
        jobs = await self.db.analysis_jobs.find(
            {"status": {"$in": ["queued", "running"]}},
            {"_id": 0, "id": 1},
        ).sort("queued_at", 1).to_list(500)
        for job in jobs:
            await self.update_job(job["id"], status="queued", progress_pct=0, message="Recovered after restart")
            await self._queue.put(job["id"])

    async def _worker_loop(self):
        while True:
            job_id = await self._queue.get()
            try:
                job = await self.get_job(job_id)
                if not job or job.get("status") not in {"queued", "running"}:
                    continue

                processor = self._processors.get(job["kind"])
                if processor is None:
                    await self.update_job(job_id, status="failed", error=f"No processor registered for '{job['kind']}'")
                    continue

                await self.update_job(job_id, status="running", progress_pct=1, message="Job started")

                async def progress(progress_pct: float, message: str, extra_fields: Optional[Dict[str, Any]] = None):
                    await self.update_job(
                        job_id,
                        progress_pct=progress_pct,
                        message=message,
                        extra_fields=extra_fields,
                    )

                result = await processor(job_id, job.get("payload", {}), progress)
                await self.update_job(job_id, status="completed", progress_pct=100, message="Job completed", result=result)
            except Exception as exc:
                logger.exception("Job %s failed", job_id)
                await self.update_job(job_id, status="failed", error=str(exc), message="Job failed")
            finally:
                self._queue.task_done()