import asyncio
import json
import logging
import time
from typing import Dict, List, cast

import redis
from lang3s_job_service import File, Job, JobService, JobStatus

import lang3s.config as config
from lang3s.clients.topic_model_client import TopicModelClient
from lang3s.db import TextDatabase
from lang3s.pipeline import pipeline
from lang3s.utils import get_value

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


QUEUE_NAME = "doc_queue"
BATCH_SIZE = 20
BATCH_TIMEOUT = 0.2

job_service = JobService(
    api_key=config.SYSTEM_API_KEY, api_host=config.BACKEND_HOST
)
redis_client = redis.Redis(
    host=config.REDIS_HOST,
    port=config.REDIS_PORT,
    db=config.REDIS_DB,
    decode_responses=True,
)
text_db = TextDatabase()
topic_model = TopicModelClient()

logger = logging.Logger("NLP_WORKER")


async def process_batch(batch):
    jobs: Dict[int, Job] = dict()
    docs_by_id: Dict[int, List[File]] = dict()
    completed = 0
    failed = 0

    for task in batch:
        job_id = int(task["job_id"])
        if job_id not in jobs:
            try:
                jobs[job_id] = job_service.get_job(job_id)
            except Exception as e:
                failed += 1
                print(e)
                continue
        if job_id not in docs_by_id:
            docs_by_id[job_id] = list()
        try:
            docs_by_id[job_id].append(File.model_validate_json(task["content"]))
        except Exception as e:
            print(e)
            failed += 1
            continue

    for job_id, files in docs_by_id.items():
        metadata = jobs[job_id].metadata
        tasks = metadata.get("tasks", None)
        if tasks:
            tasks = set(tasks)
        try:
            logger.info(f"✍️ Starting annotation on {len(files)} documents.")
            docs = pipeline(
                files, write_to_db=True, tasks=tasks, batch_size=len(files)
            )
            completed += len(docs)
            for doc in docs:
                topic_model.partial_fit(doc)
        except Exception as e:
            print(e)
            failed += len(files)
            continue

    return completed, failed


async def worker_loop():
    logger.info("👷 Batched worker started...")
    while True:
        batch = []
        start_time = time.time()
        while (
            len(batch) < BATCH_SIZE
            and (time.time() - start_time) < BATCH_TIMEOUT
        ):
            item = cast(
                str, await get_value(redis_client.rpop(QUEUE_NAME), None)
            )
            if item:
                data = json.loads(item)
                batch.append(data)
            else:
                time.sleep(BATCH_TIMEOUT)  # avoid busy waiting

        if batch:
            job_ids = {doc["job_id"] for doc in batch}
            completed, failed = await process_batch(batch)
            for job_id in job_ids:
                try:
                    job = job_service.update_job(
                        job_id, completed_inc=completed, failed_inc=failed
                    )
                    if job.completed + job.failed >= job.total:
                        status = (
                            JobStatus.FAILED
                            if job.failed > 0
                            else JobStatus.COMPLETE
                        )
                        job_service.update_job(job_id, status=status)
                        topic_model.finalize()
                except Exception as e:
                    print(e)
        else:
            time.sleep(BATCH_TIMEOUT)


if __name__ == "__main__":
    asyncio.run(worker_loop())
