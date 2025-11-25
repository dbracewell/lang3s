import asyncio
import json
import logging
import time
from collections import defaultdict
from typing import Dict, List, cast

import redis

import lang3s.config as config
from lang3s.clients.topic_model_client import TopicModelClient
from lang3s.db import TextDatabase
from lang3s.pipeline import pipeline
from lang3s.utils import get_value
from lang3s_job_service import File, Job, JobService, JobStatus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

QUEUE_NAME = "doc_queue"
BATCH_SIZE = 100
BATCH_TIMEOUT = 2

job_service = JobService(
    api_key=config.SYSTEM_API_KEY, api_host=config.NODEJS_HOST
)
redis_client = redis.Redis(
    host=config.REDIS_HOST,
    port=config.REDIS_PORT,
    db=config.REDIS_DB,
    decode_responses=True,
)
text_db = TextDatabase()
topic_model = TopicModelClient()

logger = logging.Logger("NLP_WORKER", level=logging.INFO)


async def process_batch(batch):
    jobs: Dict[int, Job] = dict()
    docs_by_id: Dict[int, List[File]] = defaultdict(list)
    completed = defaultdict(int)
    failed = defaultdict(int)

    for task in batch:
        job_id = int(task["job_id"])

        if job_id not in jobs:
            try:
                jobs[job_id] = job_service.get_job(job_id)
            except Exception as e:
                failed[job_id] += 1
                logger.error(e)
                continue
        try:
            docs_by_id[job_id].append(File.model_validate_json(task["content"]))
        except Exception as e:
            logger.error(f"Error getting File: {e}")
            failed[job_id] += 1
            continue

    for job_id, files in docs_by_id.items():
        metadata = jobs[job_id].metadata
        tasks = metadata.get("tasks", None)
        if tasks:
            tasks = set(tasks)

        try:
            docs = pipeline(
                files, write_to_db=True, tasks=tasks, batch_size=len(files)
            )
            completed[job_id] += len(docs)
            try:
                topic_model.partial_fit(docs)
            except Exception as e:
                logger.error(f"Error processing topics: {e}")
        except Exception as e:
            logger.error(f"Error: {e}")
            failed[job_id] += len(files)
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
                        job_id,
                        completed_inc=completed[job_id],
                        failed_inc=failed[job_id],
                    )
                    if job.completed + job.failed >= job.total:
                        status = (
                            JobStatus.FAILED
                            if job.failed > 0
                            else JobStatus.COMPLETE
                        )
                        job_service.update_job(job_id, status=status)
                        logger.info(
                            f"🏁 Job {job.id} finished with status; {status}"
                        )
                        try:
                            topic_model.finalize()
                        except Exception as e:
                            logger.error(f"Error finalizing topics: {e}")
                except Exception as e:
                    logger.error(f"Error updating job: {e}")

        else:
            time.sleep(BATCH_TIMEOUT)


if __name__ == "__main__":
    asyncio.run(worker_loop())
