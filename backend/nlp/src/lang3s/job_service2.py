import enum
import json
from typing import Dict, List, Optional, cast

import redis
import shortuuid

from lang3s.utils import get_value


class Status(str, enum.Enum):
    WAITING = "waiting"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class JobService:
    job_type_queues = {"annotate": "doc_queue"}

    def __init__(self) -> None:
        self.redis_client = redis.Redis(
            host="localhost", port=6379, db=0, decode_responses=True
        )

    def create_job(
        self,
        job_type: str,
        metadata: Optional[Dict[str, str | List[str]]] = None,
    ):
        job_id = str(shortuuid.uuid())
        self.redis_client.hset(
            f"job:{job_id}",
            mapping={
                "status": Status.WAITING.value,
                "total": "0",
                "completed": "0",
                "progress": "0",
                "job_type": job_type,
                "metadata": json.dumps(metadata),
            },
        )
        return {"job_id": job_id}

    def get_status(self, job_id: str):
        job_data = self.redis_client.hgetall(f"job:{job_id}")
        if not job_data:
            return {"error": "Job not found"}
        print(job_data)
        return job_data

    def set_status(self, job_id: str, status: Status):
        job_data = self.redis_client.hgetall(f"job:{job_id}")
        if not job_data:
            return {"error": "Job not found"}

        self.redis_client.hset(f"job:{job_id}", "status", status.value)

    async def submit_job_data(
        self,
        job_id: str,
        data: str,
    ):
        job = await get_value(self.get_status(job_id), None)
        if job is None:
            return {"error": "Job not found"}

        queue = self.job_type_queues.get(job["job_type"], None)
        if queue is None:
            return {"error": "Invalid job type"}

        self.redis_client.hincrby(f"job:{job_id}", "total", 1)

        task = {"job_id": job_id, "content": data}
        self.redis_client.rpush(queue, json.dumps(task))

        return {"job_id": job_id}

    async def update_progress(self, job_id: str, count: int):
        job_key = f"job:{job_id}"
        total = int(
            await get_value(self.redis_client.hget(job_key, "total"), "0")
        )

        completed = await get_value(
            self.redis_client.hincrby(job_key, "completed", count), count
        )

        progress = round(100 * completed / total, 2) if total else 0
        status = Status.DONE if completed >= total else Status.PROCESSING

        self.redis_client.hset(
            job_key, mapping={"progress": progress, "status": status.value}
        )

        if completed >= total:
            print(
                f"✅ Job {job_id}: {completed}/{total} ({progress}%) complete."
            )

    async def get_queue_data(self, queue_name: str):
        return cast(
            str, await get_value(self.redis_client.rpop(queue_name), None)
        )

    def clear_jobs(self, all: bool):
        deleted = 0
        for key in self.redis_client.keys("job:*"):  # type: ignore
            if self.redis_client.type(key) != "hash":
                continue

            status = self.redis_client.hget(key, "status")
            if status == Status.DONE.value or (
                all
                and status
                not in [Status.WAITING.value, Status.PROCESSING.value]
            ):
                self.redis_client.delete(key)
                deleted += 1

        return {"deleted_jobs": deleted}
