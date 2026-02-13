import datetime
import enum
import json
import time
from typing import Any, Dict, List, Optional, Type, TypeVar, Union, cast

import requests
from pydantic import BaseModel, Field


class File(BaseModel):
    path: Optional[str] = Field(default=None)
    docId: Optional[str] = Field(default=None)
    mime_type: str = Field(default="text/plain")
    encoding: Optional[str] = Field(default=None)
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class JobStatus(str, enum.Enum):
    WAITING = "waiting"
    COMPLETE = "complete"
    FAILED = "failed"
    PROCESSING = "processing"


class Job(BaseModel):
    id: int
    name: str
    total: int = Field(default=0)
    completed: int = Field(default=0)
    failed: int = Field(default=0)
    status: JobStatus = Field(default=JobStatus.WAITING)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    createdAt: datetime.datetime = Field(default_factory=datetime.datetime.now)
    updatedAt: datetime.datetime = Field(default_factory=datetime.datetime.now)

    @property
    def progress(self):
        return 100 * self.completed / self.total if self.total > 0 else 0

    def __str__(self) -> str:
        return f"Job({self.id}, status={self.status.value}, total={self.total}, completed={self.completed}, failed={self.failed}, progress={self.progress:.2f})"


T = TypeVar("T", bound=BaseModel)


class JobService:
    def __init__(self, api_key: str, api_host: str = "http://localhost:3001") -> None:
        self.api_key = api_key
        self._api_root = f"{api_host}/api/trpc"

    def _call_api_obj(
        self,
        endpoint: str,
        data: Dict[str, Any],
        return_type: Type[T],
        method: str = "GET",
    ) -> T:
        return cast(
            T,
            self._call_api(
                endpoint=endpoint,
                data=data,
                return_type=return_type,
                method=method,
            ),
        )

    def _call_api_list(
        self,
        endpoint: str,
        data: Dict[str, Any],
        return_type: Type[T],
        method: str = "GET",
    ) -> List[T]:
        return cast(
            List[T],
            self._call_api(
                endpoint=endpoint,
                data=data,
                return_type=return_type,
                method=method,
            ),
        )

    def _call_api(
        self,
        endpoint: str,
        data: Dict[str, Any],
        return_type: Type[T],
        method: str = "GET",
    ) -> Union[T, List[T]]:
        url = f"{self._api_root}/{endpoint}"

        if method == "GET":
            params = {"batch": 1, "input": json.dumps({"0": {"json": data}})}
            r = requests.get(
                url, params, headers={"lang3s-api-key": self.api_key.strip()}
            )
            r.raise_for_status()
            body = r.json()[0]["result"]["data"]["json"]
            if isinstance(body, list):
                return [return_type.model_validate(i) for i in body]
            return return_type.model_validate(body)

        if method == "POST":
            params = {"json": data}
            headers = {
                "Content-Type": "application/json",
                "lang3s-api-key": self.api_key,
            }
            r = requests.post(url, headers=headers, json=params)
            r.raise_for_status()
            body = r.json()["result"]["data"]["json"]
            if isinstance(body, list):
                return [return_type.model_validate(i) for i in body]
            return return_type.model_validate(body)

        raise Exception(f"Invalid method {method}")

    def create_job(self, name: str, metadata: Optional[Dict[str, Any]] = None) -> Job:
        job = self._call_api_obj(
            "jobs.create",
            {"name": name, "metadata": metadata or {}},
            method="POST",
            return_type=Job,
        )
        print(f"✅ Created job: {job.id}")
        return job

    def get_job(self, job_id: int) -> Job:
        return self._call_api_obj("jobs.get", {"job_id": job_id}, return_type=Job)

    def update_job(
        self,
        job_id: int,
        total_inc: Optional[int] = None,
        completed_inc: Optional[int] = None,
        failed_inc: Optional[int] = None,
        status: Optional[JobStatus] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Job:
        return self._call_api_obj(
            "jobs.update",
            {
                "job_id": job_id,
                "total_increment": total_inc,
                "completed_increment": completed_inc,
                "failed_increment": failed_inc,
                "status": status.value if status else None,
                "metadata": metadata or None,
            },
            return_type=Job,
            method="POST",
        )

    def annotate_documents(
        self,
        files: List[File],
        metadata: Optional[Dict[str, Any]] = None,
        wait_for_completion=True,
    ) -> Job:
        job = self.create_job(
            f"annotation-{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            metadata=metadata,
        )
        num_docs = len(files)
        print(f"⬆️  Uploading {num_docs} documents...")

        total_processed = 0
        for i in range(0, num_docs, 20):
            try:
                batch = [files[i].__dict__ for i in range(i, min(i + 20, len(files)))]
                job = self._call_api_obj(
                    "jobs.annotate",
                    {"job_id": job.id, "files": batch},
                    return_type=Job,
                    method="POST",
                )
                total_processed += len(batch)
            except Exception as e:
                print(f"Failed to upload {files[i].path}", e)
                continue

            if total_processed % 100 == 0 or i == num_docs - 1:
                print(f"  Uploaded {i + 1}/{num_docs}")

        if total_processed == num_docs:
            print("✅ All documents uploaded.")
        else:
            print(f"❌ {total_processed} out of {num_docs} documents uploaded.")

        if total_processed > 0:
            job = self.update_job(job.id, metadata={"all_documents_sent": True})

        if wait_for_completion:
            self.wait(job.id)

        return self.get_job(job.id)

    def wait(self, job_id: int, interval: float = 5.0):
        print("⏳ Waiting for job to complete...")
        while True:
            try:
                job = self.get_job(job_id)
                print(
                    f"  Progress: {job.progress:.1f}% ({job.completed}/{job.total}) | Status: {job.status.value}"
                )
                if job.status == JobStatus.COMPLETE:
                    print("🎉 Job completed!")
                    break
            except Exception:
                pass
            time.sleep(interval)

    def delete_job(self, job_id: int) -> Job:
        return self._call_api_obj(
            "jobs.delete", {"job_id": job_id}, method="POST", return_type=Job
        )
