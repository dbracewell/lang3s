import datetime
from collections.abc import Iterable
from itertools import batched

import requests
from tqdm import tqdm

from lang3s.core.schemas import File
from lang3s.core.schemas.job import (
    Job,
    JobAnnotateRequest,
    JobCreateRequest,
    JobListResponse,
    JobType,
    JobUpdateRequest,
)


class JobService:
    def __init__(self, api_host: str, api_key: str):
        self._base_url: str = f"{api_host}/job"
        self.api_key: str = api_key

    def list_jobs(self) -> list[Job]:
        response = requests.get(
            self._base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        response.raise_for_status()
        return JobListResponse.model_validate(response.json()).root

    def create(self, request: JobCreateRequest) -> Job:
        response = requests.post(
            self._base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=request.model_dump(mode="json"),
        )
        response.raise_for_status()
        return Job.model_validate(response.json())

    def update(self, request: JobUpdateRequest) -> Job:
        response = requests.put(
            self._base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=request.model_dump(mode="json"),
        )
        response.raise_for_status()
        return Job.model_validate(response.json())

    def delete(self, job_id: int) -> Job:
        response = requests.delete(
            f"{self._base_url}/id/{job_id}",
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        response.raise_for_status()
        return Job.model_validate(response.json())

    def get(self, job_id: int) -> Job:
        response = requests.get(
            f"{self._base_url}/id/{job_id}",
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        response.raise_for_status()
        return Job.model_validate(response.json())

    def annotate(self, files: Iterable[File]) -> Job:
        job = self.create(
            JobCreateRequest(
                type_=JobType.Annotation,
                name=f"Annotation {datetime.datetime.now().isoformat()}",
            )
        )
        for batch in tqdm(batched(files, 100)):
            response = requests.post(
                f"{self._base_url}/annotate",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=JobAnnotateRequest(
                    id=job.id,
                    files=list(batch),
                ).model_dump(mode="json"),
            )
            response.raise_for_status()
        response = requests.post(
            f"{self._base_url}/annotate",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=JobAnnotateRequest(
                id=job.id,
                files=[],
                complete=True,
            ).model_dump(mode="json"),
        )
        response.raise_for_status()
        return self.get(job.id)
