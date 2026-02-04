import argparse
import gc
import logging
import multiprocessing
import os
import sys
import time
import traceback
from typing import Any, Dict, List, Optional, Tuple

import torch
from lang3s_job_service import File, Job, JobService, JobStatus

import lang3s.config as config
from lang3s.data.db import TextDatabase, db
from lang3s.logs import initialize_logging
from lang3s.models import Embedder, MultiTaskTransformer
from lang3s.pipeline import pipeline
from lang3s.services.client.redis_client import (
    ANNOTATION_QUEUE_NAME,
    DUCKDB_QUEUE_NAME,
    RedisClient,
    redis_batch_generator,
)
from lang3s.services.client.topic_model_client import TopicModelClient
from lang3s.utils.decorators import trace_mem

from .post_annotation import generate_corpus_summary, probe_metadata

initialize_logging(filename="nlp_worker.log")


logger = logging.getLogger("NLP_WORKER")
pid = os.getpid()
job_service = JobService(api_key=config.SYSTEM_API_KEY, api_host=config.NODEJS_HOST)
redis_client = RedisClient()
text_db = TextDatabase()
topic_model = TopicModelClient()


worker_embedder = None
worker_mtask = None


def init_worker():
    global worker_embedder, worker_mtask
    worker_embedder = Embedder()
    worker_mtask = MultiTaskTransformer()
    logger.info(f"👷 Batched Worker {pid} started...")


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


@trace_mem
def process_batch(batch, embedder, mtask):
    job_id = batch[0]["job_id"]
    job = get_job(job_id)
    completed = 0
    failed = 0

    if not job:
        logger.info(
            f"WORKER {pid}: ❌ Failed to process with {len(batch)} documents failed."
        )
        return 0, len(batch)

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
        return 0, len(batch)

    try:
        with torch.inference_mode():
            docs = pipeline(
                files,
                tasks=tasks,
                batch_size=len(files),
                embedder=embedder,
                mtask=mtask,
            )
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

        for doc in docs or []:
            doc.detach()

        gc.collect()
        if torch.backends.mps.is_available():
            torch.mps.empty_cache()
        elif torch.cuda.is_available():
            torch.cuda.empty_cache()

    except Exception as e:
        logger.error(f"WORKER ❌ {pid}: Error: {e}")
        logger.info(
            f"WORKER {pid}: ❌ Failed to process with {len(files)} documents failed."
        )
        traceback.print_exc(file=sys.stdout)
        update_job(job_id, failed=len(files))
        return 0, len(files)

    update_job(job_id, completed=completed, failed=failed)
    logger.info(
        f"WORKER {pid}: ✅ Finished processing batch {completed} successful, {failed} failed."
    )
    return completed, failed


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

        redis_client.enqueue(DUCKDB_QUEUE_NAME, {"status": "completed"})

        logger.info(f"WORKER {pid}: Finishing job {job_id}")
        try:
            logger.info(f"WORKER {pid}: Enabling embedding index")
            db.create_text_annotation_embedding_index()
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
            logger.info(f"WORKER {pid}: Refreshing views")
            db.refresh_annotation_views()
            logger.info(f"WORKER {pid}: Completed refreshing views")
        except Exception as e:
            logger.error(f"WORKER {pid}: Error constructing materialized views: {e}")

        try:
            logger.info(f"WORKER {pid}: Generating corpus summary")
            probe_metadata()
            generate_corpus_summary()
            logger.info(f"WORKER {pid}: Completed generating corpus summary")
        except Exception as e:
            logger.error(f"WORKER {pid}: Error generating corpus summary: {e}")

        status = JobStatus.FAILED if job.failed > 0 else JobStatus.COMPLETE
        job_service.update_job(job_id, completed_inc=20, status=status)
        logger.info(f"WORKER {pid}: 🏁 Job {job.id} finished with status; {status}")

        return True

    return False


def worker_loop(params: Tuple[int, int]):
    active_job_id = params[1]
    batch_size = params[0]

    for batch in redis_batch_generator(ANNOTATION_QUEUE_NAME, batch_size):
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

            try:
                if torch.backends.mps.is_available():
                    torch.mps.empty_cache()

                completed, failed = process_batch(batch, worker_embedder, worker_mtask)

            finally:
                if torch.backends.mps.is_available():
                    torch.mps.empty_cache()

            # Check to see if we are done
            if check_for_completion(active_job_id):
                time.sleep(60)
                return None, completed, failed
            return active_job_id, completed, failed
        else:
            if check_for_completion(active_job_id):
                return None, 0, 0
            return active_job_id, 0, 0

    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--num_workers",
        help="The number of worker processes to use",
        default=1,
        type=int,
    )
    parser.add_argument(
        "--batch_size",
        help="The number of documents to process in each worker process",
        default=150,
        type=int,
    )
    args = parser.parse_args()
    active_job_id = None
    total_docs_completed = 0
    total_docs_failed = 0

    while True:
        while redis_client.queue_length(ANNOTATION_QUEUE_NAME) == 0:
            time.sleep(5)

        with multiprocessing.Pool(
            processes=args.num_workers,
            initializer=init_worker,
        ) as pool:
            try:
                for i in range(5):
                    results = pool.map(
                        worker_loop,
                        [(args.batch_size, active_job_id)] * args.num_workers,
                    )
                    for result in results:
                        if result is not None:
                            active_job_id = result[0]
                            total_docs_completed += result[1]
                            total_docs_failed += result[2]

                    logger.info(
                        f"Total Documents Completed: {total_docs_completed}, Total Documents Failed: {total_docs_failed}"
                    )

                    if active_job_id is not None:
                        if check_for_completion(active_job_id):
                            break
                    else:
                        time.sleep(60)

            except KeyboardInterrupt:
                print("Shutting down...")
                pool.terminate()
                pool.join()
                exit(0)
