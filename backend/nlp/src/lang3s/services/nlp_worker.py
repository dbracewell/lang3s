import sys
import traceback

from lang3s.logging import initialize_logging

initialize_logging()
import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, cast

import redis
from lang3s_job_service import File, Job, JobService, JobStatus

import lang3s.config as config
from lang3s.clients.topic_model_client import TopicModelClient
from lang3s.db import Database, TextDatabase
from lang3s.pipeline import pipeline
from lang3s.utils import get_value

QUEUE_NAME = "doc_queue"
BATCH_SIZE = 1000
BATCH_TIMEOUT = 10

logger = logging.getLogger("NLP_WORKER")
pid = os.getpid()
job_service = JobService(api_key=config.SYSTEM_API_KEY, api_host=config.NODEJS_HOST)
redis_client = redis.Redis(
    host=config.REDIS_HOST,
    port=config.REDIS_PORT,
    db=config.REDIS_DB,
    decode_responses=True,
)
text_db = TextDatabase()
topic_model = TopicModelClient()


def get_job(job_id: int) -> Optional[Job]:
    try:
        return job_service.get_job(job_id)
    except Exception as e:
        logger.error(f"WORKER {pid}: ❌ Error getting job: {job_id} with error: {e}.")
        return None


def convert_tasks_to_files(batch: List[Dict]) -> List[File]:
    files = []
    for task in batch:
        try:
            files.append(File.model_validate_json(task["content"]))
        except Exception as e:
            logger.error(f"WORKER {pid}: Error getting File: {e}")
            traceback.print_exc(file=sys.stdout)
            continue

    return files


def update_job(
    job_id: int,
    total_inc: Optional[int] = None,
    completed: Optional[int] = None,
    failed: Optional[int] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    try:
        job_service.update_job(
            job_id,
            total_inc=total_inc,
            completed_inc=completed,
            failed_inc=failed,
            metadata=metadata,
        )
    except Exception as e:
        logger.error(
            f"WORKER {pid}: ❌ Failed to update job: {job_id} with error: {e}."
        )


async def process_batch(batch):
    job_id = batch[0]["job_id"]
    job = get_job(job_id)
    completed = 0
    failed = 0

    if not job:
        logger.info(
            f"WORKER {pid}: ❌ Failed to process with {len(batch)} documents failed."
        )
        return

    metadata = job.metadata
    tasks = metadata.get("tasks", None)
    if tasks:
        tasks = set(tasks)

    files = convert_tasks_to_files(batch)
    failed += len(batch) - len(files)

    if len(files) == 0:
        logger.info(
            f"WORKER {pid}: ❌ Failed to process with {len(batch)} documents failed."
        )
        update_job(job_id, failed=len(batch))
        return

    try:
        docs = pipeline(files, tasks=tasks, batch_size=len(files))
        completed += len(docs)

        start = time.perf_counter()
        logger.info(
            f"WORKER {pid}: 💽 Starting writing of {len(docs)} documents to database"
        )
        text_db.add_documents(docs)
        end = time.perf_counter()
        logger.info(
            f"WORKER {pid}: ✅ Finished writing {len(docs)} documents to database: {(end - start):.2f}s"
        )

        try:
            topic_model.partial_fit(docs)
        except Exception as e:
            logger.error(f"WORKER {pid}: ❌ Error processing topics: {e}")

    except Exception as e:
        logger.error(f"WORKER ❌ {pid}: Error: {e}")
        traceback.print_exc(file=sys.stdout)
        logger.info(
            f"WORKER {pid}: ❌ Failed to process with {len(files)} documents failed."
        )
        update_job(job_id, failed=len(files))
        return

    update_job(job_id, completed=completed, failed=failed)
    logger.info(
        f"WORKER {pid}: ✅ Finished processing batch {completed} successful, {failed} failed."
    )


def check_for_completion(job_id: Optional[int] = None) -> bool:
    if job_id is None:
        return False

    job = get_job(job_id)
    if job is None:
        return True

    if job.status in ["failed", "complete"]:
        return True

    if job.metadata.get("is_finalizing", False):
        return True

    if job.completed + job.failed >= job.total:
        job = job_service.get_job(job_id)
        if job.metadata.get("is_finalizing", False):
            return True

        update_job(
            job_id,
            total_inc=20,
            metadata={"is_finalizing": True},
        )
        logger.info(f"WORKER {pid}: Finishing job {job_id}")
        try:
            db = Database()
            logger.info(f"WORKER {pid}: Indexing text annotation embeddings")
            with db.cursor() as cursor:
                cursor.execute(
                    'CREATE INDEX IF NOT EXISTS "text_annotation_embedding_index" ON "text_annotations" USING hnsw ("embedding" halfvec_cosine_ops);'
                )
        except Exception as e:
            if "pg_class_relname_nsp_index" in str(e):
                return True
            logger.error(
                f"WORKER {pid}: Error creating text annotation embeddings index: {e}"
            )

        try:
            logger.info(f"WORKER {pid}: Finalizing topic model")
            topic_model.finalize()
        except Exception as e:
            logger.error(f"WORKER {pid}: Error finalizing topics: {e}")

        try:
            db = Database()
            logger.info(f"WORKER {pid}: Refreshing views")
            db.refresh_views()
            logger.info(f"WORKER {pid}: Completed refreshing views")
        except Exception as e:
            logger.error(f"WORKER {pid}: Error constructing materialized views: {e}")

        status = JobStatus.FAILED if job.failed > 0 else JobStatus.COMPLETE
        job_service.update_job(job_id, completed_inc=20, status=status)
        logger.info(f"WORKER {pid}: 🏁 Job {job.id} finished with status; {status}")

        return True

    return False


async def worker_loop():
    logger.info(f"👷 Batched Worker {pid} started...")
    total_processed = 0
    active_job_id = None

    while True:
        batch = []
        start_time = time.time()

        if total_processed >= 0:
            logger.info(f"WORKER {pid}: ⌛ {total_processed} total documents processed")

        count = redis_client.llen(QUEUE_NAME)
        logger.info(f"WORKER {pid}: ⌛ {QUEUE_NAME} has {count} documents")

        if count == 0:
            time.sleep(BATCH_TIMEOUT)
            continue

        # Try to gather upto BATCH_SIZE tasks to process within a BATCH_TIMEOUT period
        while len(batch) < BATCH_SIZE and (time.time() - start_time) < BATCH_TIMEOUT:
            # Keep grabbing tasks will the batch is < BATCH_SIZE and there are tasks on the queue
            while len(batch) < BATCH_SIZE and redis_client.llen(QUEUE_NAME) > 0:
                # Pop an item and make sure we got it before another process, and if we did,
                # parse it and add it to the batch
                item = cast(str, await get_value(redis_client.rpop(QUEUE_NAME), None))
                if item:
                    data = json.loads(item)
                    batch.append(data)

        if batch:
            # We only allow one annotation job to run at a time
            # Make sure this is true
            job_ids = {doc["job_id"] for doc in batch}

            # If for some reason we have more than one unique job_id, kill them all
            if len(job_ids) > 1:
                logger.error(
                    f"WORKER {pid}:  ❌ Found more than one job id: {job_ids}. Can only annotate one job at a time"
                )
                continue

            # Keep track of the active job id
            active_job_id = list(job_ids)[0]

            # Send things off to be processed
            logger.info(f"WORKER {pid}: Sending {len(batch)} documents for processing")
            await process_batch(batch)

            # Check to see if we are done
            if check_for_completion(active_job_id):
                # if we are, update our active job id to be None
                active_job_id = None

        else:
            # We don't have a batch, so check if we are done
            if check_for_completion(active_job_id):
                # if we are, (means our active job id was not none), set active job id to None and sleep
                active_job_id = None
                time.sleep(BATCH_TIMEOUT * 3)
            else:
                # We are not done, so wait a minute and try everything again
                time.sleep(BATCH_TIMEOUT * 60)


if __name__ == "__main__":
    asyncio.run(worker_loop())
