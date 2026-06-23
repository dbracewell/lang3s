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
import asyncio
import gc
import os
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import partial
from typing import Dict, List, Optional, Tuple

import redis
import torch
from joblib import Parallel, delayed
from sqlalchemy.ext.asyncio import AsyncSession

from lang3s.core.async_extras import run_sync
from lang3s.core.clients import RedisAsyncClient, RedisClient
from lang3s.core.clients.redis_client import (
    create_completed_status_message,
    redis_get_message_batch,
)
from lang3s.core.decorators import as_sync, sync_or_async, trace_mem
from lang3s.core.exceptions import try_catch
from lang3s.core.formatters import format_duration
from lang3s.core.logger import get_logger
from lang3s.core.schemas import File
from lang3s.data import filestore
from lang3s.data.constants import (
    ANNOTATION_QUEUE_NAME,
    CLAIM_EXTRACT_QUEUE_NAME,
    DUCKDB_QUEUE_NAME,
    ONTOLOGY_UPDATE_TOPIC,
)
from lang3s.data.db import (
    async_db_session,
    get_ontology,
)
from lang3s.data.models.job import JobStatus
from lang3s.data.repositories.job_repository import JobRepository
from lang3s.data.schemas import Document
from lang3s.data.schemas.claim import DocumentClaimRequest
from lang3s.data.schemas.job import JobMessage
from lang3s.nlp import pipeline

pid = None


async def ontology_listener():
    from lang3s.nlp.components.ner import get_ner_model

    logger = get_logger("NLP_WORKER")
    while True:
        try:
            async with RedisAsyncClient() as client:
                p = client.subscribe(ONTOLOGY_UPDATE_TOPIC)
                for message in p.listen():
                    if message["type"] == "message":
                        if message["data"] == "update":
                            logger = get_logger("NLP_WORKER")
                            logger.info("🛜 Updating ontology")
                            get_ontology(refresh=True)
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


def convert_tasks_to_files(batch: List[Dict]) -> List[File]:
    """
    Converts a batch of tasks into a list of Files.
    """
    logger = get_logger("NLP_WORKER")
    files = []
    for task in batch:
        try:
            files.append(File.model_validate(task["content"]))
        except Exception as e:
            logger.error(f"WORKER {pid}: Error getting File: {e}")
            traceback.print_exc(file=sys.stdout)
            continue

    return files


def _write_doc_to_disk(doc: Document, client: RedisClient) -> None:
    doc_id = filestore.write_document(doc)
    client.enqueue(DUCKDB_QUEUE_NAME, doc_id)


@trace_mem
async def process_batch(batch: list[JobMessage], session: AsyncSession):
    """
    Processes a batch of documents through a defined pipeline and updates
    job status accordingly.

    This function processes a batch of documents for a specific job. It runs the
    provided documents through predefined pipeline tasks, handles file processing,
    tracks completed and failed documents, and updates external systems with the
    results. Resources are cleaned up post-execution, and any relevant topic models
    are updated if applicable.

    Parameters:
        batch (list[dict]): A list of documents to be processed. Each document must
        include the key "job_id".
        session (AsyncSession): An asynchronous database session object.

    Returns:
        tuple[int, int]: A tuple containing the count of successfully completed
        documents and the count of failed documents.
    """
    global pid
    # topic_model = TopicModelClient()
    logger = get_logger("NLP_WORKER")

    logger.info(f"🆕 Worker {pid} | Begin processing {len(batch)} documents.")

    job_id = batch[0].job_id
    completed = 0
    failed = 0
    start_time = time.perf_counter()

    files = [File.model_validate(msg.content) for msg in batch]
    failed += len(batch) - len(files)

    job_repository = JobRepository(session)
    job = await job_repository.get(job_id)
    if job is None:
        logger.error(f"WORKER {pid}: Error getting Job: {job_id}")
        return 0, 0

    if len(files) == 0:
        logger.info(
            f"❌ Worker {pid} | Completed: {0} | Failed: {len(batch)} | "
            f"{format_duration(start_time, time.perf_counter())}"
        )
        await job_repository.update(
            job_id=job.id,
            completed=0,
            failed=len(batch),
        )
        return 0, len(batch)

    metadata = job.metadata_json
    tasks = metadata.get("tasks", None)
    if tasks:
        tasks = set(tasks)  # type: ignore

    try:
        with (
            torch.inference_mode()
        ):  # Paranoia to make sure we are in inference mode everywhere
            docs = list(
                pipeline(
                    files,
                    tasks=tasks,
                    batch_size=len(files),
                )
            )
            logger.info(
                f"WORKER {pid}: 📝 Annotated {len(docs)} documents: "
                f"{format_duration(start_time, time.perf_counter())}"
            )
        completed += len(docs)

        # Forward the documents to the claim extraction module
        with RedisClient() as redis_client:
            for doc in docs:
                try:
                    claims = DocumentClaimRequest(
                        documentId=doc.id,
                        sentences=[s.content for s in doc.text.sentences],
                    )
                    redis_client.enqueue(
                        CLAIM_EXTRACT_QUEUE_NAME,
                        claims.model_dump(),
                    )
                    for sentence in doc.text.sentences:
                        if "claims" in sentence.metadata_json:
                            sentence.metadata_json.pop("claims")
                except Exception as e:
                    logger.error(e, exc_info=True)

        # Add the annotated documents to the database
        # and persist them in msgpack to the filestore
        with ThreadPoolExecutor(max_workers=20) as executor:
            with RedisClient() as client:
                executor.map(partial(_write_doc_to_disk, client=client), docs)

        start_time = time.perf_counter()
        for doc in docs:
            session.add(doc.to_database())
        await session.commit()
        logger.info(
            f"WORKER {pid}: 🗃️ Wrote {len(docs)} documents to the database: "
            f"{format_duration(start_time, time.perf_counter())}"
        )
        # with try_catch(
        #     on_error=lambda e: logger.error(
        #         f"WORKER {pid}: ❌ Error processing topics: {e}"
        #     )
        # ):
        #     # Send the documents to the topic model
        #     topic_model.partial_fit(docs)

        # Force memory to be freed
        for doc in docs or []:
            doc.detach()

        # Force memory cleaning
        gc.collect()
        if torch.backends.mps.is_available():
            torch.mps.empty_cache()
        elif torch.cuda.is_available():
            torch.cuda.empty_cache()

    except Exception:
        logger.info(
            f"❌ Worker {pid} | Completed: {0} | Failed: {len(files)} | "
            f"{format_duration(start_time, time.perf_counter())}"
        )
        traceback.print_exc(file=sys.stdout)
        await job_repository.update(
            job_id=job.id,
            completed=0,
            failed=len(batch),
        )
        return 0, len(files)

    await job_repository.update(
        job_id=job.id,
        completed=completed,
        failed=failed,
    )
    logger.info(
        f"{'❌' if failed > 0 else '✅'} Worker {pid} | Completed: {completed} | "
        f"Failed: {failed} | {format_duration(start_time, time.perf_counter())}"
    )
    return completed, failed


async def complete_job(job_id: int, session: AsyncSession) -> None:
    """
    Marks a job as complete by performing a series of operations such as status
    updating, database updates, and generating summaries. Certain operations are
    attempted in a fault-tolerant way, logging relevant errors or skipping specific
    operations when errors occur. The function ensures appropriate final status
    updates for the job based on its outcome.

    Parameters:
        job_id (int): The unique identifier for the job to be completed.
        session (AsyncSession): An asynchronous database session object.

    Raises:
        Ensures fault tolerance for most errors during execution and logs them
        accordingly. This function does not raise unhandled exceptions.
    """
    global pid
    job_repository = JobRepository(session)
    job = await job_repository.get(job_id)
    if job is None:
        return

    if job.status in [JobStatus.Failed, JobStatus.Completed]:
        return

    logger = get_logger("NLP_WORKER")

    with RedisClient() as redis_client:
        redis_client.enqueue(DUCKDB_QUEUE_NAME, create_completed_status_message())

    await job_repository.update(job_id=job.id, total=20)

    logger.info(f"WORKER {pid}: 🏁 Finishing job {job_id}")
    try:
        logger.info(f"WORKER {pid}: Enabling embedding index")
        # db.create_text_annotation_embedding_index()
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
        # updates = generate_keyword_categories()
        # stmt = update(KeywordsTable)
        # with db.get_session() as session:
        #     session.execute(stmt, updates)
        # db.refresh_concept_views()
        logger.info(f"WORKER {pid}: Completed generating keyword categories")

    with try_catch(
        on_error=lambda e: logger.error(f"WORKER {pid}: Error finalizing topics: {e}")
    ):
        logger.info(f"WORKER {pid}: Finalizing topic model")
        # topic_model = TopicModelClient()
        # topic_model.finalize()

    with try_catch(
        on_error=lambda e: logger.error(
            f"WORKER {pid}: Error generating corpus summary: {e}"
        )
    ):
        logger.info(f"WORKER {pid}: Generating corpus summary")
        # probe_metadata()
        # generate_corpus_summary()
        logger.info(f"WORKER {pid}: Completed generating corpus summary")

    status = JobStatus.Failed if job.failed > 0 else JobStatus.Completed
    await job_repository.update(job_id, completed=20, status=status)
    logger.info(f"WORKER {pid}: 🏁 Job {job.id} finished with status; {status}")


async def worker_loop(params: Tuple[int, int]) -> WorkerResult:
    active_job_id = params[0]
    batch_size = params[1]
    job_ids = []

    batch, completed_message = redis_get_message_batch(
        ANNOTATION_QUEUE_NAME,
        batch_size,
    )

    job_completed = False
    if completed_message:
        # Note we ignore that the status says complete to
        # ensure the job is marked as complete
        job_completed = True
        job_ids.append(completed_message.job_id)

    if not batch:
        return WorkerResult(
            active_job_id=active_job_id,
            job_completed=job_completed,
        )

    job_ids.extend(doc.job_id for doc in batch if doc.job_id not in job_ids)
    async with async_db_session() as session:
        completed, failed = await process_batch(batch, session)

    return WorkerResult(
        active_job_id=job_ids[0],
        job_completed=job_completed,
        completed_count=completed,
        failed_count=failed,
    )


@as_sync
async def worker_loop_wrapper(params: Tuple[int, int]) -> WorkerResult:
    global pid
    if pid is None:
        init_worker()
    try:
        return await worker_loop(params)
    except Exception as e:
        print(e)
        traceback.print_exc()
        return WorkerResult(
            active_job_id=params[0],
        )


async def main():
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

    logger.info("Annotation server started...")
    while True:
        is_job_completed = False

        async with RedisAsyncClient() as redis_client:
            try:
                while await redis_client.queue_length(ANNOTATION_QUEUE_NAME) == 0:
                    time.sleep(5)
            except redis.exceptions.TimeoutError:
                time.sleep(5)
                continue
            except Exception as e:
                logger.error(f"Redis link dropped: {e}")
                time.sleep(5)
                continue

            parallel: Parallel
            with Parallel(
                n_jobs=args.num_workers,
                backend="loky",
                inner_max_num_threads=8,
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

                    # Determine the active job id from the returned results,
                    # prefer non-None values
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
                        f"📈 Total Documents Completed: {total_docs_completed}, "
                        f"Total Documents Failed: {total_docs_failed}, "
                        f"Job Completed: {is_job_completed}, "
                        f"active_job_id: {active_job_id}"
                    )
                    if is_job_completed:
                        break  # break the loop to kill the processes

            if is_job_completed:
                if active_job_id is not None:
                    async with async_db_session() as session:
                        await complete_job(active_job_id, session)
                else:
                    logger.error(
                        "Job marked as completed by workers but active_job_id is None; "
                        "skipping complete_job."
                    )
                active_job_id = None
                total_docs_completed = 0
                total_docs_failed = 0

    logger.info("Annotation server stopping...")


if __name__ == "__main__":
    asyncio.run(main())
