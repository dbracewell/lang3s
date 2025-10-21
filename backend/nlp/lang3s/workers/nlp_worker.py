import asyncio
import json
import time
from typing import Dict, List, cast

import redis
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

from lang3s import config
from lang3s.core.doc_builder import create_document
from lang3s.db.helpers import add_documents_to_db
from lang3s.io.file import File
from lang3s.job_service import JobService, JobStatus
from lang3s.nlp.embedding import Embedder
from lang3s.nlp.process import nlp
from lang3s.utils import get_value

QUEUE_NAME = "doc_queue"
BATCH_SIZE = 10
BATCH_TIMEOUT = 0.2

app = FastAPI()
embedder = Embedder()
job_service = JobService(api_key=config.JOBS_API_KEY)
redis_client = redis.Redis(
    host=config.REDIS_HOST,
    port=config.REDIS_PORT,
    db=config.REDIS_DB,
    decode_responses=True,
)


async def process_batch(batch):
    jobs = dict()
    docs_by_id: Dict[str, List[File]] = dict()
    for task in batch:
        job_id = task["job_id"]
        if job_id not in jobs:
            jobs[job_id] = job_service.get_job(job_id)
        if job_id not in docs_by_id:
            docs_by_id[job_id] = list()

        job_service.update_job(job_id, status=JobStatus.PROCESSING)
        try:
            docs_by_id[job_id].append(File.model_validate_json(task["content"]))
        except Exception as e:
            print("ERROR", e)

    for job_id, files in docs_by_id.items():
        metadata = jobs[job_id].metadata
        tasks = metadata.get("tasks", None)
        if tasks:
            tasks = set(tasks)
        docs = [create_document(file) for file in files]
        nlp(docs, tasks=tasks)
        add_documents_to_db(docs)


async def worker_loop():
    print("👷 Batched worker started...")
    while True:
        batch = []
        start_time = time.time()
        while len(batch) < BATCH_SIZE and (time.time() - start_time) < BATCH_TIMEOUT:
            item = cast(str, await get_value(redis_client.rpop(QUEUE_NAME), None))
            if item:
                data = json.loads(item)
                batch.append(data)
            else:
                time.sleep(0.01)  # avoid busy waiting

        if batch:
            job_ids = {doc["job_id"] for doc in batch}
            await process_batch(batch)
            for job_id in job_ids:
                count = sum(1 for doc in batch if doc["job_id"] == job_id)
                job = job_service.update_job(job_id, completed_inc=count)
                if job.completed >= job.total:
                    job_service.update_job(job_id, status=JobStatus.COMPLETE)
        else:
            time.sleep(0.05)


class EmbeddingRequest(BaseModel):
    language: str
    text: str


@app.post("/embed")
@app.post("/embed/")
async def caption(request: EmbeddingRequest):
    return embedder([request.text])[0]


async def main():
    config = uvicorn.Config(app=app, host="0.0.0.0", port=8000)
    server = uvicorn.Server(config)

    uvicorn_task = asyncio.create_task(server.serve())
    background_task = asyncio.create_task(worker_loop())

    await asyncio.gather(uvicorn_task, background_task)


if __name__ == "__main__":
    asyncio.run(main())
