"""
This module implements a batched worker for processing annotation tasks, handling
ML pipeline operations, job management, and integration with external services
including Redis and database systems.

It includes functionalities to initialize the worker, process job batches,
update job statuses, and finalize tasks through database and Redis client
executions. It supports fault handling and logging to facilitate tracing errors
and monitoring worker performance.
"""

import argparse
import gc
import os
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, cast

import torch
from joblib import Parallel, delayed
from lang3s_job_service import File, Job, JobService, JobStatus
from sqlalchemy import update

from lang3s import config
from lang3s.data.db import db, text_db
from lang3s.data.db.models import KeywordsTable
from lang3s.nlp.claim_extractor import create_sentence_context
from lang3s.nlp.keyword_extraction import generate_keyword_categories
from lang3s.nlp.ner import get_ner_model
from lang3s.ontology import ontology
from lang3s.pipeline import pipeline
from lang3s.services.client.redis_client import (
    ANNOTATION_QUEUE_NAME,
    CLAIM_EXTRACT_QUEUE_NAME,
    DUCKDB_QUEUE_NAME,
    ONTOLOGY_UPDATE_TOPIC,
    RedisClient,
    create_completed_status_message,
    redis_get_message_batch,
)
from lang3s.services.client.topic_model_client import TopicModelClient
from lang3s.utils import try_catch
from lang3s.utils.decorators import Result, trace_mem
from lang3s.utils.formatters import format_duration
from lang3s.utils.logger.service_logging import get_logger

from .post_annotation import generate_corpus_summary, probe_metadata

pid = None


def ontology_listener():
    logger = get_logger("NLP_WORKER")
    while True:
        try:
            with RedisClient() as client:
                p = client.subscribe(ONTOLOGY_UPDATE_TOPIC)
                for message in p.listen():
                    if message["type"] == "message":
                        if message["data"] == "update":
                            logger = get_logger("NLP_WORKER")
                            logger.info("🛜 Updating ontology")
                            ontology.refresh()
                            get_ner_model().refresh()
        except Exception as e:
            logger.error(f"Redis link dropped: {e}")
            time.sleep(5)


def init_worker():
    logger = get_logger("NLP_WORKER")
    global pid
    pid = os.getpid()
    logger.info(f"👷🏻 Worker {pid} Started.")
    threading.Thread(target=ontology_listener, daemon=True).start()


@dataclass
class WorkerResult:
    """
    Represents the result state of a worker's processing tasks.

    This class is a dataclass that encapsulates information about the number of
    completed and failed tasks, the currently active job ID (if any), and whether
    the most recent job has been completed.
    """

    completed_count: int = field(default=0)
    failed_count: int = field(default=0)
    active_job_id: int | None = field(default=None)
    job_completed: bool = field(default=False)


def get_job(job_id: int) -> Result[Job]:
    """
    Retrieves the job with the given job ID.
    """
    logger = get_logger("NLP_WORKER")
    job_service = JobService(api_key=config.SYSTEM_API_KEY, api_host=config.NODEJS_HOST)
    try:
        return Result(value=job_service.get_job(job_id), error=None)
    except Exception as e:
        logger.error(f"WORKER {pid}: Error getting Job: {e}")
        return Result(value=None, error=e)


def convert_tasks_to_files(batch: List[Dict]) -> List[File]:
    """
    Converts a batch of tasks into a list of Files.
    """
    logger = get_logger("NLP_WORKER")
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
    """
    Updates the job with the given job ID.
    """
    logger = get_logger("NLP_WORKER")
    job_service = JobService(api_key=config.SYSTEM_API_KEY, api_host=config.NODEJS_HOST)
    with try_catch(on_error=logger.error):
        job_service.update_job(
            job_id,
            total_inc=total_inc,
            completed_inc=completed,
            failed_inc=failed,
            metadata=metadata,
        )


@trace_mem
def process_batch(batch):
    """
    Processes a batch of documents through a defined pipeline and updates job status accordingly.

    This function processes a batch of documents for a specific job. It runs the provided documents through
    predefined pipeline tasks, handles file processing, tracks completed and failed documents, and updates
    external systems with the results. Resources are cleaned up post-execution, and any relevant topic models
    are updated if applicable.

    Parameters:
        batch (list[dict]): A list of documents to be processed. Each document must include the key "job_id".

    Returns:
        tuple[int, int]: A tuple containing the count of successfully completed documents and the count of
        failed documents.
    """
    global pid
    topic_model = TopicModelClient()
    logger = get_logger("NLP_WORKER")

    logger.info(f"🆕 Worker {pid} | Begin processing {len(batch)} documents.")

    job_id = batch[0]["job_id"]
    completed = 0
    failed = 0
    start_time = time.perf_counter()

    files = convert_tasks_to_files(batch)
    failed += len(batch) - len(files)

    result = get_job(job_id)
    if not result.is_ok or len(files) == 0:
        logger.info(
            f"❌ Worker {pid} | Completed: {0} | Failed: {len(batch)} | {format_duration(start_time, time.perf_counter())}"
        )
        update_job(job_id, failed=len(batch))
        return 0, len(batch)

    job: Job = cast(Job, result.value)
    metadata = job.metadata
    tasks = metadata.get("tasks", None)
    if tasks:
        tasks = set(tasks)

    try:
        with (
            torch.inference_mode()
        ):  # Paranoia to make sure we are in inference mode everywhere
            docs = pipeline(
                files,
                tasks=tasks,
                batch_size=len(files),
            )
            logger.info(
                f"WORKER {pid}: 📝 Annotated {len(docs)} documents: {format_duration(start_time, time.perf_counter())}"
            )
        completed += len(docs)

        # Add the annotated documents to the database
        # and persist them in msgpack to the filestore
        text_db.add_documents(docs)

        # Forward the documents to the claim extraction module
        for doc in docs:
            redis_client = RedisClient()
            redis_client.enqueue(
                CLAIM_EXTRACT_QUEUE_NAME, create_sentence_context(doc).model_dump()
            )

        with try_catch(
            on_error=lambda e: logger.error(
                f"WORKER {pid}: ❌ Error processing topics: {e}"
            )
        ):
            # Send the documents to the topic model
            topic_model.partial_fit(docs)

        # Force memory to be freed
        for doc in docs or []:
            doc.detach()

        # Force memory cleaning
        gc.collect()
        if torch.backends.mps.is_available():
            torch.mps.empty_cache()
        elif torch.cuda.is_available():
            torch.cuda.empty_cache()

    except Exception as e:
        logger.info(
            f"❌ Worker {pid} | Completed: {0} | Failed: {len(files)} | {format_duration(start_time, time.perf_counter())}"
        )
        traceback.print_exc(file=sys.stdout)
        update_job(job_id, failed=len(files))
        return 0, len(files)

    update_job(job_id, completed=completed, failed=failed)
    logger.info(
        f"{'❌' if failed > 0 else '✅'} Worker {pid} | Completed: {completed} | Failed: {failed} | {format_duration(start_time, time.perf_counter())}"
    )
    return completed, failed


def complete_job(job_id: int) -> None:
    """
    Marks a job as complete by performing a series of operations such as status updating,
    database updates, and generating summaries. Certain operations are attempted in
    a fault-tolerant way, logging relevant errors or skipping specific operations when
    errors occur. The function ensures appropriate final status updates for the job
    based on its outcome.

    Parameters:
        job_id (int): The unique identifier for the job to be completed.

    Raises:
        Ensures fault tolerance for most errors during execution and logs them accordingly.
        This function does not raise unhandled exceptions.
    """
    global pid
    result = get_job(job_id)
    if not result.is_ok:
        return

    job: Job = cast(Job, result.value)
    if job.status in ["failed", "complete"]:
        return

    logger = get_logger("NLP_WORKER")

    with RedisClient() as redis_client:
        redis_client.enqueue(DUCKDB_QUEUE_NAME, create_completed_status_message())

    job_service = JobService(api_key=config.SYSTEM_API_KEY, api_host=config.NODEJS_HOST)
    job_service.update_job(job_id, total_inc=20)

    logger.info(f"WORKER {pid}: 🏁 Finishing job {job_id}")
    try:
        logger.info(f"WORKER {pid}: Enabling embedding index")
        db.create_text_annotation_embedding_index()
    except Exception as e:
        if "pg_class_relname_nsp_index" in str(e):
            return
        logger.error(
            f"WORKER {pid}: Error creating text annotation embeddings index: {e}"
        )

    with try_catch(
        on_error=lambda e: logger.error(
            f"WORKER {pid}: Error categorizing keywords: {e}"
        )
    ):
        logger.info(f"WORKER {pid}: Generating keyword categories")
        updates = generate_keyword_categories()
        stmt = update(KeywordsTable)
        with db.get_session() as session:
            session.execute(stmt, updates)
        db.refresh_concept_views()
        logger.info(f"WORKER {pid}: Completed generating keyword categories")

    with try_catch(
        on_error=lambda e: logger.error(f"WORKER {pid}: Error finalizing topics: {e}")
    ):
        logger.info(f"WORKER {pid}: Finalizing topic model")
        topic_model = TopicModelClient()
        topic_model.finalize()

    with try_catch(
        on_error=lambda e: logger.error(
            f"WORKER {pid}: Error generating corpus summary: {e}"
        )
    ):
        logger.info(f"WORKER {pid}: Generating corpus summary")
        probe_metadata()
        generate_corpus_summary()
        logger.info(f"WORKER {pid}: Completed generating corpus summary")

    status = JobStatus.FAILED if job.failed > 0 else JobStatus.COMPLETE
    job_service.update_job(job_id, completed_inc=20, status=status)
    logger.info(f"WORKER {pid}: 🏁 Job {job.id} finished with status; {status}")


def worker_loop(params: Tuple[int, int]) -> WorkerResult:
    active_job_id = params[0]
    batch_size = params[1]
    job_ids = []

    batch, completed_message = redis_get_message_batch(
        ANNOTATION_QUEUE_NAME,
        batch_size,
    )

    job_completed = False
    if completed_message:
        # Note we ignore that the status says complete to ensure the job is marked as complete
        job_completed = True
        job_ids.append(completed_message["job_id"])

    if not batch:
        return WorkerResult(
            active_job_id=active_job_id,
            job_completed=job_completed,
        )

    job_ids.extend(doc["job_id"] for doc in batch if doc["job_id"] not in job_ids)
    completed, failed = process_batch(batch)

    return WorkerResult(
        active_job_id=job_ids[0],
        job_completed=job_completed,
        completed_count=completed,
        failed_count=failed,
    )


def worker_loop_wrapper(params: Tuple[int, int]) -> WorkerResult:
    global pid
    if pid is None:
        init_worker()
    try:
        return worker_loop(params)
    except Exception as e:
        print(e)
        traceback.print_exc()
        return WorkerResult(
            active_job_id=params[0],
        )


def main():
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
    active_job_id: Optional[int] = None
    total_docs_completed = 0
    total_docs_failed = 0
    logger = get_logger("NLP_WORKER")

    while True:
        is_job_completed = False

        with RedisClient() as redis_client:
            try:
                while redis_client.queue_length(ANNOTATION_QUEUE_NAME) == 0:
                    # If Redis is empty, just sleep
                    time.sleep(5)
            except Exception as e:
                logger.error(f"Redis link dropped: {e}")
                time.sleep(5)
                continue

            with Parallel(
                n_jobs=args.num_workers,
                backend="loky",
                inner_max_num_threads=2,
                initializer=init_worker,
            ) as parallel:
                # Limit a process to a life of 5 cycles to prevent memory creep
                for _ in range(5):
                    tasks = [
                        delayed(worker_loop_wrapper)((active_job_id, args.batch_size))
                        for _ in range(args.num_workers)
                    ]
                    results = parallel(tasks)

                    # Filter out any unexpected None results and ensure correct typing
                    valid_results = [r for r in results if isinstance(r, WorkerResult)]

                    if not valid_results:
                        logger.warning(
                            "No valid worker results returned from parallel execution."
                        )
                        continue

                    # Determine the active job id from the returned results, prefer non-None values
                    active_job_id = next(
                        (
                            r.active_job_id
                            for r in valid_results
                            if r.active_job_id is not None
                        ),
                        active_job_id,
                    )

                    is_job_completed = any(r.job_completed for r in valid_results)
                    total_docs_completed += sum(
                        r.completed_count for r in valid_results
                    )
                    total_docs_failed += sum(r.failed_count for r in valid_results)
                    logger.info(
                        f"📈 Total Documents Completed: {total_docs_completed}, Total Documents Failed: {total_docs_failed}, Job Completed: {is_job_completed}, active_job_id: {active_job_id}"
                    )
                    if is_job_completed:
                        break  # break the loop to kill the processes

            if is_job_completed:
                if active_job_id is not None:
                    complete_job(active_job_id)
                else:
                    logger.error(
                        "Job marked as completed by workers but active_job_id is None; skipping complete_job."
                    )
                active_job_id = None
                total_docs_completed = 0
                total_docs_failed = 0


if __name__ == "__main__":
    main()
