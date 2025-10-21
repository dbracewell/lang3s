import enum
import json
import time
from datetime import date
from typing import Any, Dict, List, Optional

import requests


class File:
    def __init__(
        self,
        path: str,
        mime_type: str,
        content: str,
        encoding: Optional[str] = None,
        metadata: Dict[str, str] = {},
    ):
        self.path = path
        self.mime_type = mime_type
        self.content = content
        self.encoding = encoding
        self.metadata = metadata


class JobStatus(str, enum.Enum):
    WAITING = "waiting"
    COMPLETE = "complete"
    FAILED = "failed"
    PROCESSING = "processing"


class Job:
    def __init__(
        self,
        id: int,
        name: str,
        total: int,
        completed: int,
        failed: int,
        status: str,
        metadata: Dict[str, Any],
        createdAt: date,
        updatedAt: date,
    ) -> None:
        self.id = id
        self.name = name
        self.total = total
        self.completed = completed
        self.failed = failed
        self.status = JobStatus(status)
        self.createdAt = createdAt
        self.updatedAt = updatedAt
        self.metadata = metadata

    @property
    def progress(self):
        return self.completed / self.total if self.total > 0 else 0

    def __str__(self) -> str:
        return f"Job({self.id}, status={self.status.value}, total={self.total}, completed={self.completed}, failed={self.failed}, progress={self.progress:.2f})"


class JobService:
    def __init__(self, api_key: str, api_host: str = "http://localhost:3001") -> None:
        self.api_key = api_key
        self._api_root = f"{api_host}/api/trpc"

    def _call_api(self, endpoint: str, data: Dict[str, Any], method: str = "GET"):
        url = f"{self._api_root}/{endpoint}"
        if method == "GET":
            params = {"batch": 1, "input": json.dumps({"0": {"json": data}})}
            r = requests.get(url, params)
            r.raise_for_status()
            return r.json()[0]["result"]["data"]["json"]

        if method == "POST":
            params = {"json": data}
            headers = {"Content-Type": "application/json"}
            r = requests.post(url, headers=headers, json=params)
            r.raise_for_status()
            return r.json()["result"]["data"]["json"]

        raise Exception(f"Invalid method {method}")

    def create_job(self, name: str, metadata: Optional[Dict[str, Any]] = None) -> Job:
        resp = self._call_api(
            "jobs.create",
            {"api_key": self.api_key, "name": name, "metadata": metadata or {}},
            method="POST",
        )
        job = Job(**resp)
        print(f"✅ Created job: {job.id}")
        return job

    def get_job(self, job_id: int) -> Job:
        return Job(
            **self._call_api("jobs.get", {"api_key": self.api_key, "job_id": job_id})
        )

    def update_job(
        self,
        job_id: int,
        total_inc: Optional[int] = None,
        completed_inc: Optional[int] = None,
        failed_inc: Optional[int] = None,
        status: Optional[JobStatus] = None,
    ) -> Job:
        return Job(
            **self._call_api(
                "jobs.update",
                {
                    "api_key": self.api_key,
                    "job_id": job_id,
                    "total_increment": total_inc,
                    "completed_increment": completed_inc,
                    "failed_increment": failed_inc,
                    "status": status.value if status else None,
                },
                method="POST",
            )
        )

    def annotate_documents(self, job_id: int, batch: List[File]) -> Job:
        num_docs = len(batch)
        print(f"⬆️  Uploading {num_docs} documents...")
        job: Job
        for i in range(num_docs):
            job = Job(
                **self._call_api(
                    "jobs.annotate",
                    {
                        "api_key": self.api_key,
                        "job_id": job_id,
                        "file": batch[i].__dict__,
                    },
                    method="POST",
                )
            )
            if (i + 1) % 10 == 0 or i == num_docs - 1:
                print(f"  Uploaded {i + 1}/{num_docs}")
        print("✅ All documents uploaded.")
        return job

    def wait(self, job_id: int, interval: float = 1.0):
        print("⏳ Waiting for job to complete...")
        while True:
            data = self._call_api(
                "jobs.get", {"api_key": self.api_key, "job_id": job_id}
            )
            progress = float(data.get("progress", 0))
            status = data.get("status", "unknown")
            completed = data.get("completed", 0)
            total = data.get("total", 0)
            print(
                f"  Progress: {progress:.1f}% ({completed}/{total}) | Status: {status}"
            )
            if status == "done":
                print("🎉 Job completed!")
                break
            time.sleep(interval)

    def delete_job(self, job_id: int) -> Job:
        return Job(
            **self._call_api(
                "jobs.delete",
                {"api_key": self.api_key, "job_id": job_id},
                method="POST",
            )
        )
