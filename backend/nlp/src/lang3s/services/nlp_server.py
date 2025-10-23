from typing import Dict, List

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel, Field

from lang3s.io.file import File
from lang3s.job_service2 import JobService

app = FastAPI()
job_service = JobService()


class JobSubmission(BaseModel):
    job_type: str
    metadata: Dict[str, str | List[str]] = Field(default_factory=dict)


class AnnotateJobData(BaseModel):
    job_id: str
    file: File


@app.post("/create_job")
async def create_job(submission: JobSubmission):
    return job_service.create_job(submission.job_type, submission.metadata)


@app.post("/annotate")
async def annotate(data: AnnotateJobData):
    return await job_service.submit_job_data(
        job_id=data.job_id, data=data.file.model_dump_json()
    )


@app.get("/status/{job_id}")
async def status(job_id: str):
    return job_service.get_status(job_id)


@app.delete("/clear_completed")
async def clear_completed():
    return job_service.clear_jobs(all=False)


@app.delete("/clear_all")
async def clear_all():
    return job_service.clear_jobs(all=True)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8004)
